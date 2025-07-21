#!/usr/bin/env python3

"""
SIMPLIFIED Trading Platform - Focus on Wallet Management and Webhooks
Removed performance tracking and Pine Script creation - back to basics
"""

import os
import json
import logging
import sqlite3
import hmac
import hashlib
import time
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Global variables
api_clients = {}
webhook_count = 0
open_positions = {}  # Track open positions for close signals

# Binance symbol precision mapping - ALL PAIRS SUPPORTED
SYMBOL_PRECISION = {
    "BTCUSDT": {"quantity": 3, "price": 2},
    "ETHUSDT": {"quantity": 3, "price": 2},
    "SOLUSDT": {"quantity": 2, "price": 3},
    "AVAXUSDT": {"quantity": 1, "price": 3},
    "ADAUSDT": {"quantity": 0, "price": 5},
    "DOTUSDT": {"quantity": 1, "price": 3},
    "LINKUSDT": {"quantity": 2, "price": 3},
    "MATICUSDT": {"quantity": 0, "price": 5},
    "LTCUSDT": {"quantity": 3, "price": 2},
    "BCHUSDT": {"quantity": 3, "price": 2},
    "XRPUSDT": {"quantity": 0, "price": 4},
    "XRPUSDC": {"quantity": 0, "price": 4}
}

def get_symbol_precision(symbol: str) -> dict:
    """Get precision settings for a symbol"""
    return SYMBOL_PRECISION.get(symbol, {"quantity": 3, "price": 2})

def format_quantity_for_binance(quantity: str, symbol: str) -> str:
    """Format quantity according to Binance symbol precision"""
    try:
        precision = get_symbol_precision(symbol)
        qty_decimal_places = precision["quantity"]
        
        qty_float = float(quantity)
        
        # Apply minimum quantity rules
        if symbol in ["XRPUSDC", "XRPUSDT"]:
            if qty_float < 1:
                qty_float = 1
        elif symbol in ["ADAUSDT", "MATICUSDT"]:
            if qty_float < 1:
                qty_float = 1
        elif symbol in ["BTCUSDT", "ETHUSDT"]:
            if qty_float < 0.001:
                qty_float = 0.001
        
        formatted_qty = f"{qty_float:.{qty_decimal_places}f}"
        
        if qty_decimal_places == 0:
            formatted_qty = str(int(qty_float))
        
        logger.info(f"📊 Formatted quantity: {quantity} -> {formatted_qty} for {symbol}")
        return formatted_qty
        
    except Exception as e:
        logger.error(f"❌ Error formatting quantity: {e}")
        return quantity

def get_current_market_price(symbol: str) -> float:
    """Get current market price from Binance"""
    try:
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        
        logger.info(f"🔍 Fetching current market price for {symbol}")
        
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            price = float(data['price'])
            logger.info(f"✅ Current {symbol} price: ${price}")
            return price
        else:
            logger.error(f"❌ Failed to get price for {symbol}: HTTP {response.status_code}")
            return get_fallback_price(symbol)
            
    except Exception as e:
        logger.error(f"❌ Error getting market price for {symbol}: {e}")
        return get_fallback_price(symbol)

def get_fallback_price(symbol: str) -> float:
    """Fallback prices when Binance API is unavailable - ALL PAIRS SUPPORTED"""
    fallback_prices = {
        'BTCUSDT': 45000.0,
        'ETHUSDT': 2400.0,
        'SOLUSDT': 22.45,
        'AVAXUSDT': 18.92,
        'ADAUSDT': 0.4567,
        'DOTUSDT': 6.789,
        'LINKUSDT': 12.34,
        'MATICUSDT': 0.8901,
        'LTCUSDT': 85.67,
        'BCHUSDT': 220.50,
        'XRPUSDT': 0.6234,
        'XRPUSDC': 0.6234
    }
    price = fallback_prices.get(symbol, 1.0)
    logger.warning(f"⚠️ Using fallback price for {symbol}: ${price}")
    return price

class BinanceFuturesAPI:
    """Live Binance Futures API Client"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://fapi.binance.com"
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})
    
    def generate_signature(self, params: dict) -> str:
        """Generate HMAC SHA256 signature"""
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            url = f"{self.base_url}/fapi/v1/ping"
            response = self.session.get(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_current_price(self, symbol: str) -> float:
        """Get current market price for a symbol"""
        try:
            url = f"{self.base_url}/fapi/v1/ticker/price"
            params = {"symbol": symbol}
            
            response = self.session.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return float(data['price'])
            else:
                logger.error(f"Failed to get price: HTTP {response.status_code}")
                return get_fallback_price(symbol)
                
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return get_fallback_price(symbol)
    
    def get_account_info(self) -> dict:
        """Get account information"""
        try:
            url = f"{self.base_url}/fapi/v2/account"
            timestamp = int(time.time() * 1000)
            params = {"timestamp": timestamp}
            params["signature"] = self.generate_signature(params)
            
            response = self.session.get(url, params=params, timeout=10)
            return response.json() if response.status_code == 200 else {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return {"error": str(e)}
    
    def get_balance(self) -> dict:
        """Get account balance"""
        try:
            account_info = self.get_account_info()
            if "error" in account_info:
                return account_info
            
            return {
                "account_summary": {
                    "total_wallet_balance": float(account_info.get("totalWalletBalance", 0)),
                    "available_balance": float(account_info.get("availableBalance", 0)),
                    "total_unrealized_pnl": float(account_info.get("totalUnrealizedProfit", 0)),
                    "can_trade": account_info.get("canTrade", False)
                }
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_positions(self) -> list:
        """Get current positions"""
        try:
            account_info = self.get_account_info()
            if "error" in account_info:
                return [account_info]
            
            positions = []
            for pos in account_info.get("positions", []):
                position_amt = float(pos.get("positionAmt", 0))
                if position_amt != 0:
                    positions.append({
                        "symbol": pos.get("symbol", ""),
                        "position_side": "LONG" if position_amt > 0 else "SHORT",
                        "position_amount": position_amt,
                        "entry_price": float(pos.get("entryPrice", 0)),
                        "unrealized_pnl": float(pos.get("unrealizedProfit", 0))
                    })
            return positions
        except Exception as e:
            return [{"error": str(e)}]
    
    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = "MARKET") -> dict:
        """Place an order"""
        try:
            formatted_quantity = format_quantity_for_binance(str(quantity), symbol)
            
            url = f"{self.base_url}/fapi/v1/order"
            timestamp = int(time.time() * 1000)
            
            params = {
                "symbol": symbol,
                "side": side.upper(),
                "type": order_type.upper(),
                "quantity": formatted_quantity,
                "timestamp": timestamp
            }
            params["signature"] = self.generate_signature(params)
            
            logger.info(f"📡 Placing order: {params}")
            
            pre_order_price = self.get_current_price(symbol)
            logger.info(f"📊 Pre-order {symbol} price: ${pre_order_price}")
            
            response = self.session.post(url, params=params, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                actual_price = float(data.get("avgPrice", data.get("price", pre_order_price)))
                if actual_price == 0:
                    actual_price = pre_order_price
                
                logger.info(f"✅ Order executed at: ${actual_price}")
                
                return {
                    "success": True,
                    "order_id": data.get("orderId"),
                    "status": data.get("status", "FILLED"),
                    "execution_price": actual_price,
                    "formatted_quantity": formatted_quantity,
                    "message": f"Order placed successfully: {side} {formatted_quantity} {symbol} @ ${actual_price}",
                    "pre_order_price": pre_order_price
                }
            else:
                error_code = data.get('code', 'Unknown')
                error_msg = data.get('msg', 'Unknown error')
                
                if error_code == -1111:
                    return {
                        "success": False,
                        "error": f"Precision error: {formatted_quantity} {symbol}. Try different quantity.",
                        "error_code": error_code,
                        "binance_msg": error_msg,
                        "suggestion": f"For {symbol}, try quantities like: {self.get_quantity_suggestions(symbol)}"
                    }
                elif error_code == -2019:
                    return {
                        "success": False,
                        "error": "Insufficient balance for this trade",
                        "error_code": error_code,
                        "binance_msg": error_msg
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Binance error {error_code}: {error_msg}",
                        "error_code": error_code,
                        "binance_msg": error_msg
                    }
            
        except Exception as e:
            logger.error(f"❌ Order placement failed: {e}")
            return {
                "success": False,
                "error": f"Order placement failed: {str(e)}"
            }
    
    def get_quantity_suggestions(self, symbol: str) -> str:
        """Get quantity suggestions for ANY trading pair"""
        suggestions = {
            "BTCUSDT": "0.001, 0.01, 0.1",
            "ETHUSDT": "0.01, 0.1, 1", 
            "SOLUSDT": "0.5, 1, 5, 10",
            "AVAXUSDT": "0.5, 1, 5, 10",
            "ADAUSDT": "50, 100, 500",
            "DOTUSDT": "1, 5, 10, 50",
            "LINKUSDT": "1, 5, 10, 25",
            "MATICUSDT": "50, 100, 500",
            "LTCUSDT": "0.1, 1, 5",
            "BCHUSDT": "0.1, 1, 5",
            "XRPUSDT": "10, 50, 100",
            "XRPUSDC": "10, 50, 100"
        }
        return suggestions.get(symbol, "0.001, 0.01, 0.1, 1, 10")

def parse_tradingview_template(raw_data: str, strategy_id: int) -> dict:
    """Enhanced TradingView template parser"""
    try:
        logger.info(f"🔍 Parsing TradingView template: {raw_data}")
        
        clean_data = raw_data.strip()
        parts = clean_data.split()
        
        logger.info(f"🔍 Split parts: {parts}")
        
        # Initialize defaults
        symbol = "UNKNOWN"
        action = "buy"
        quantity = "0.001"
        leverage = "1"
        price = None
        
        # Extract symbol - SUPPORTS ALL CRYPTO PAIRS
        crypto_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT", "MATICUSDT", "LTCUSDT", "BCHUSDT", "XRPUSDT", "XRPUSDC"]
        
        symbol_found = False
        for part in parts:
            part_upper = part.upper()
            if part_upper in crypto_symbols:
                symbol = part_upper
                symbol_found = True
                break
        
        if not symbol_found:
            for part in parts:
                part_upper = part.upper()
                if len(part_upper) >= 6 and (part_upper.endswith('USDT') or part_upper.endswith('USDC')):
                    symbol = part_upper
                    symbol_found = True
                    break
        
        # Extract quantity
        quantity_found = False
        for i, part in enumerate(parts):
            if part.replace('.', '').isdigit():
                try:
                    qty_value = float(part)
                    if 0.001 <= qty_value <= 1000:
                        quantity = str(qty_value)
                        quantity_found = True
                        logger.info(f"✅ Found quantity: {quantity}")
                        break
                except ValueError:
                    continue
            
            if ':' in part:
                try:
                    key, value = part.split(':', 1)
                    if key.lower() in ['quantity', 'qty', 'q', 'amount']:
                        qty_value = float(value)
                        if 0.001 <= qty_value <= 1000:
                            quantity = str(qty_value)
                            quantity_found = True
                            logger.info(f"✅ Found quantity from key:value: {quantity}")
                            break
                except (ValueError, IndexError):
                    continue
        
        # Extract leverage
        leverage_found = False
        for i, part in enumerate(parts):
            if part.lower() == 'leverage':
                try:
                    if i + 1 < len(parts):
                        leverage_value = int(parts[i + 1])
                        if 1 <= leverage_value <= 125:
                            leverage = str(leverage_value)
                            leverage_found = True
                            logger.info(f"✅ Found leverage: {leverage}")
                            break
                except (ValueError, IndexError):
                    continue
        
        # Determine action
        raw_lower = clean_data.lower()
        if "short" in raw_lower or "sell" in raw_lower:
            action = "sell"
        elif "buy" in raw_lower or "long" in raw_lower:
            action = "buy"
        elif "close" in raw_lower or "exit" in raw_lower:
            action = "close"
        
        # Apply symbol-specific defaults - WORKS WITH ALL PAIRS
        if symbol.startswith("BTC") and not quantity_found:
            quantity = "0.001"  # BTC pairs
        elif symbol.startswith("ETH") and not quantity_found:
            quantity = "0.01"   # ETH pairs
        elif symbol.startswith("SOL") and not quantity_found:
            quantity = "0.5"    # SOL pairs
        elif symbol in ["XRPUSDC", "XRPUSDT"] and not quantity_found:
            quantity = "10"     # XRP pairs
        elif symbol in ["ADAUSDT", "MATICUSDT"] and not quantity_found:
            quantity = "50"     # Low-price pairs
        
        template_issue = "{{strategy.order.alert_message}}" in raw_data
        
        logger.info(f"✅ Final extraction: symbol={symbol}, action={action}, quantity={quantity}, leverage={leverage}")
        
        return {
            "action": action,
            "symbol": symbol,
            "quantity": quantity,
            "leverage": leverage,
            "price": price,
            "source": "tradingview_template_working",
            "strategy_id": str(strategy_id),
            "parsing_method": "enhanced_v5_with_price_fix",
            "raw_template": raw_data,
            "debug_parts": parts,
            "extraction_notes": {
                "symbol_found": symbol_found,
                "quantity_found": quantity_found,
                "leverage_found": leverage_found,
                "template_issue": template_issue,
                "market_order": True
            },
            "warning": "Template variables not resolved by TradingView" if template_issue else None
        }
        
    except Exception as e:
        logger.error(f"❌ Error parsing TradingView template: {e}")
        return {
            "action": "unknown", 
            "symbol": "UNKNOWN", 
            "quantity": "0.001",
            "error": "template_parse_failed", 
            "raw_data": raw_data
        }

def init_database():
    """Initialize SQLite database"""
    try:
        db_path = os.environ.get('DATABASE_PATH', 'strategy_analysis.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Strategies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_signals INTEGER DEFAULT 0
            )
        ''')
        
        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity REAL,
                price REAL,
                raw_data TEXT,
                FOREIGN KEY (strategy_id) REFERENCES strategies (id)
            )
        ''')
        
        # Create sample strategy if none exist
        cursor.execute('SELECT COUNT(*) FROM strategies')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO strategies (name, description)
                VALUES (?, ?)
            ''', (
                "Sample Strategy",
                "A sample strategy for webhook testing"
            ))
            logger.info("✅ Created sample strategy")
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Database initialized at {db_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False

# Track open positions for close signal processing
def track_position(strategy_id: int, symbol: str, side: str, quantity: float, price: float):
    """Track an open position"""
    position_key = f"{strategy_id}_{symbol}"
    open_positions[position_key] = {
        'strategy_id': strategy_id,
        'symbol': symbol,
        'side': side,
        'quantity': quantity,
        'entry_price': price,
        'timestamp': datetime.now()
    }
    logger.info(f"📍 Tracking position: {position_key} - {side} {quantity} {symbol} @ ${price}")

def get_open_position(strategy_id: int, symbol: str) -> dict:
    """Get tracked open position"""
    position_key = f"{strategy_id}_{symbol}"
    return open_positions.get(position_key)

def close_position(strategy_id: int, symbol: str):
    """Close tracked position"""
    position_key = f"{strategy_id}_{symbol}"
    if position_key in open_positions:
        position = open_positions.pop(position_key)
        logger.info(f"📍 Closed position: {position_key}")
        return position
    return None

# Flask Routes
@app.route('/')
def home():
    """Serve the main dashboard"""
    try:
        return render_template('simplified_index.html')
    except Exception as e:
        logger.error(f"Error loading template: {e}")
        return jsonify({
            "error": "Template not found",
            "message": "Please ensure simplified_index.html is in the templates folder",
            "status": "running",
            "app": "Simplified Trading Platform",
            "version": "4.0.0-simplified"
        })

@app.route('/health')
def health():
    """Health check endpoint"""
    db_status = "connected" if init_database() else "error"
    api_key = os.environ.get('BINANCE_API_KEY', '')
    api_secret = os.environ.get('BINANCE_API_SECRET', '')
    api_configured = bool(api_key and api_secret)
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "version": "4.0.0-simplified",
        "mode": "LIVE_TRADING",
        "api_configured": api_configured,
        "active_connections": len(api_clients),
        "webhook_count": webhook_count,
        "open_positions_tracked": len(open_positions),
        "price_fetching": "enabled"
    })

@app.route('/api/connect', methods=['POST'])
def connect_api():
    """Connect to Binance LIVE API"""
    try:
        api_key = os.environ.get('BINANCE_API_KEY', '')
        api_secret = os.environ.get('BINANCE_API_SECRET', '')
        
        if not api_key or not api_secret:
            return jsonify({
                "success": False, 
                "error": "BINANCE_API_KEY and BINANCE_API_SECRET must be set in Railway environment variables"
            }), 400
        
        # FIXED: Always use a single persistent client ID so the frontend can reliably reference it
        client_id = "live_client"  # Fixed client ID
        api_client = BinanceFuturesAPI(api_key=api_key, api_secret=api_secret)
        
        if not api_client.test_connection():
            return jsonify({
                "success": False, 
                "error": "Failed to connect to Binance LIVE API. Check credentials."
            }), 400
        
        # Overwrite or create the client entry each time to guarantee the key exists
        api_clients[client_id] = api_client
        logger.info(f"✅ Binance LIVE API connected: {client_id}")
        
        return jsonify({
            "success": True, 
            "client_id": client_id,
            "mode": "LIVE_TRADING",
            "message": "Connected to LIVE Binance API"
        })
    
    except Exception as e:
        logger.error(f"❌ Error connecting to LIVE API: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    """Get all strategies"""
    try:
        db_path = os.environ.get('DATABASE_PATH', 'strategy_analysis.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM strategies ORDER BY created_at DESC')
        strategies = cursor.fetchall()
        conn.close()
        
        strategies_data = []
        for s in strategies:
            strategies_data.append({
                'id': s[0], 
                'name': s[1], 
                'description': s[2], 
                'created_at': s[3], 
                'total_signals': s[4]
            })
        
        return jsonify(strategies_data)
        
    except Exception as e:
        logger.error(f"❌ Error getting strategies: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies', methods=['POST'])
def create_strategy():
    """Create a new strategy"""
    try:
        data = request.json or {}
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return jsonify({'error': 'Strategy name is required'}), 400
        
        db_path = os.environ.get('DATABASE_PATH', 'strategy_analysis.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategies (name, description)
            VALUES (?, ?)
        ''', (name, description))
        
        strategy_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Strategy created: {name} (ID: {strategy_id})")
        return jsonify({
            'success': True,
            'strategy_id': strategy_id,
            'message': 'Strategy created successfully',
            'webhook_url': f"/webhook/tradingview/strategy/{strategy_id}"
        })
        
    except Exception as e:
        logger.error(f"❌ Error creating strategy: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/tradingview/strategy/<int:strategy_id>', methods=['POST'])
def strategy_webhook(strategy_id):
    """Strategy webhook with FIXED close signal processing"""
    global webhook_count
    try:
        data = {}
        raw_data = request.get_data(as_text=True)
        webhook_count += 1
        
        logger.info(f"🎯 Strategy {strategy_id} webhook #{webhook_count}")
        logger.info(f"🎯 Raw data: {raw_data}")
        
        # Parse data
        try:
            data = request.get_json(force=True) or {}
            logger.info(f"🎯 Parsed as JSON: {data}")
        except:
            try:
                if raw_data:
                    data = json.loads(raw_data)
                    logger.info(f"🎯 Parsed raw data as JSON: {data}")
                else:
                    data = {}
            except:
                data = parse_tradingview_template(raw_data, strategy_id)
                logger.info(f"🎯 Parsed from template: {data}")
        
        if not data or (not data.get('action') and not data.get('symbol')):
            logger.warning(f"⚠️ No valid data found")
            return jsonify({
                "status": "received_but_unparseable",
                "message": "Webhook received but data format not recognized",
                "strategy_id": strategy_id,
                "raw_data": raw_data,
                "timestamp": datetime.now().isoformat()
            })
        
        # Extract signal data
        symbol = data.get('symbol', 'UNKNOWN')
        action = data.get('action', 'unknown').upper()
        quantity_str = data.get('quantity', '0.001')
        
        try:
            quantity_float = float(quantity_str)
            if quantity_float <= 0:
                quantity_float = 0.001
                quantity_str = "0.001"
        except (ValueError, TypeError):
            quantity_float = 0.001
            quantity_str = "0.001"
        
        # Get real market price
        real_market_price = 0
        if symbol != "UNKNOWN":
            real_market_price = get_current_market_price(symbol)
            logger.info(f"💰 REAL market price for {symbol}: ${real_market_price}")
        
        price = real_market_price if real_market_price > 0 else get_fallback_price(symbol)
        
        logger.info(f"📝 Processing signal: symbol={symbol}, action={action}, quantity={quantity_str}, REAL_PRICE=${price}")
        
        # Store signal in database
        db_path = os.environ.get('DATABASE_PATH', 'strategy_analysis.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO signals (strategy_id, symbol, action, quantity, price, raw_data)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            strategy_id, 
            symbol,
            action,
            quantity_float,
            price,
            json.dumps({
                **data,
                "webhook_received": True,
                "real_market_price": price,
                "price_source": "binance_api" if real_market_price > 0 else "fallback"
            })
        ))
        
        signal_id = cursor.lastrowid
        cursor.execute('UPDATE strategies SET total_signals = total_signals + 1 WHERE id = ?', (strategy_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Signal stored: ID={signal_id}, symbol={symbol}, action={action}, price=${price}")
        
        # Execute trade if API client available
        execution_result = {"success": False, "message": "No API client connected"}
        trade_executed = False
        actual_execution_price = price
        
        if api_clients and symbol != "UNKNOWN" and action != "UNKNOWN":
            client_id = list(api_clients.keys())[0]
            client = api_clients[client_id]
            
            try:
                trade_quantity = quantity_float
                logger.info(f"💱 Attempting trade: {action} {trade_quantity} {symbol} @ expected ${price}")
                
                if action == "BUY":
                    execution_result = client.place_order(symbol=symbol, side="BUY", quantity=trade_quantity)
                    trade_executed = execution_result.get("success", False)
                    if trade_executed:
                        # Track the position for future close signals
                        track_position(strategy_id, symbol, "LONG", trade_quantity, execution_result.get("execution_price", price))
                        
                elif action == "SELL":
                    execution_result = client.place_order(symbol=symbol, side="SELL", quantity=trade_quantity)
                    trade_executed = execution_result.get("success", False)
                    if trade_executed:
                        # Track the position for future close signals
                        track_position(strategy_id, symbol, "SHORT", trade_quantity, execution_result.get("execution_price", price))
                        
                elif action == "CLOSE":
                    # FIXED: Handle close signals properly
                    logger.info(f"🔄 Processing CLOSE signal for {symbol}")
                    
                    # Check if we have a tracked position for this strategy and symbol
                    open_position = get_open_position(strategy_id, symbol)
                    
                    if open_position:
                        logger.info(f"📍 Found open position: {open_position}")
                        
                        # Determine the opposite side to close the position
                        close_side = "SELL" if open_position['side'] == "LONG" else "BUY"
                        close_quantity = open_position['quantity']
                        
                        logger.info(f"🔄 Closing position: {close_side} {close_quantity} {symbol}")
                        execution_result = client.place_order(symbol=symbol, side=close_side, quantity=close_quantity)
                        trade_executed = execution_result.get("success", False)
                        
                        if trade_executed:
                            # Remove from tracked positions
                            closed_position = close_position(strategy_id, symbol)
                            logger.info(f"✅ Successfully closed position: {closed_position}")
                            
                            # Calculate P&L if possible
                            if closed_position:
                                entry_price = closed_position['entry_price']
                                exit_price = execution_result.get("execution_price", price)
                                pnl = 0
                                
                                if closed_position['side'] == "LONG":
                                    pnl = (exit_price - entry_price) * close_quantity
                                else:  # SHORT
                                    pnl = (entry_price - exit_price) * close_quantity
                                
                                logger.info(f"📊 Position P&L: ${pnl:.2f} (Entry: ${entry_price}, Exit: ${exit_price})")
                                execution_result["pnl"] = pnl
                                execution_result["entry_price"] = entry_price
                                execution_result["exit_price"] = exit_price
                    else:
                        logger.warning(f"⚠️ No open position found for {strategy_id}_{symbol}")
                        execution_result = {
                            "success": False, 
                            "message": f"No open position found to close for {symbol}",
                            "tracked_positions": len(open_positions),
                            "position_keys": list(open_positions.keys())
                        }
                
                # Get actual execution price from order result
                if trade_executed and "execution_price" in execution_result:
                    actual_execution_price = execution_result["execution_price"]
                    logger.info(f"💰 Actual execution price: ${actual_execution_price}")
                    
                    # Update the signal record with actual execution price
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute('UPDATE signals SET price = ? WHERE id = ?', (actual_execution_price, signal_id))
                    conn.commit()
                    conn.close()
                    
                logger.info(f"💱 Trade execution result: {execution_result}")
                    
            except Exception as e:
                execution_result = {"success": False, "error": str(e)}
                logger.error(f"❌ Trade execution failed: {e}")
        
        # Prepare response
        response_data = {
            "status": "success",
            "message": "Webhook processed successfully with REAL market price fetching",
            "strategy_id": strategy_id,
            "signal_id": signal_id,
            "execution_result": execution_result,
            "parsed_data": {
                "symbol": symbol,
                "action": action,
                "quantity": quantity_str,
                "quantity_float": quantity_float,
                "price": actual_execution_price,
                "market_price_fetched": price,
                "leverage": data.get('leverage', '1'),
                "source": data.get('source', 'direct')
            },
            "position_tracking": {
                "total_tracked_positions": len(open_positions),
                "position_keys": list(open_positions.keys()),
                "action_processed": action
            },
            "price_info": {
                "market_price_fetched": price,
                "actual_execution_price": actual_execution_price,
                "price_source": "binance_api" if real_market_price > 0 else "fallback",
                "price_fix_enabled": True
            },
            "raw_data": raw_data,
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ Error processing strategy webhook: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e),
            "raw_data": request.get_data(as_text=True),
            "help": "Check the webhook configuration and data format"
        }), 500

@app.route('/api/webhooks/activity')
def get_webhook_activity():
    """Get recent webhook activity"""
    try:
        db_path = os.environ.get('DATABASE_PATH', 'strategy_analysis.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.id, s.strategy_id, s.timestamp, s.symbol, s.action, 
                   s.quantity, s.price, s.raw_data, st.name as strategy_name
            FROM signals s
            LEFT JOIN strategies st ON s.strategy_id = st.id
            ORDER BY s.timestamp DESC 
            LIMIT 50
        ''')
        
        signals = cursor.fetchall()
        conn.close()
        
        webhook_activity = []
        for signal in signals:
            try:
                raw_data_dict = json.loads(signal[7]) if signal[7] else {}
            except:
                raw_data_dict = {}
            
            webhook_activity.append({
                "signal_id": signal[0],
                "strategy_id": signal[1],
                "strategy_name": signal[8] or f"Strategy {signal[1]}",
                "timestamp": signal[2],
                "status": "success",
                "parsed_data": {
                    "action": signal[4],
                    "symbol": signal[3],
                    "quantity": str(signal[5]) if signal[5] else "0",
                    "price": f"{signal[6]:.4f}" if signal[6] and signal[6] > 0 else "0.0000"
                }
            })
        
        return jsonify(webhook_activity)
        
    except Exception as e:
        logger.error(f"❌ Error getting webhook activity: {e}")
        return jsonify([])

# FIXED: Route parameter fixes – balance & positions now require <client_id>
@app.route('/api/balance/<client_id>')
def get_balance(client_id):
    """Get account balance"""
    if client_id not in api_clients:
        return jsonify({"error": "Client not found"}), 404
    
    try:
        balance_data = api_clients[client_id].get_balance()
        return jsonify(balance_data)
    except Exception as e:
        logger.error(f"❌ Error getting balance: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/positions/<client_id>')
def get_positions(client_id):
    """Get current positions"""
    if client_id not in api_clients:
        return jsonify({"error": "Client not found"}), 404
    
    try:
        positions = api_clients[client_id].get_positions()
        return jsonify({"positions": positions})
    except Exception as e:
        logger.error(f"❌ Error getting positions: {e}")
        return jsonify({"error": str(e)}), 500

# NEW – Earn (Savings/Staking) Placeholder
@app.route('/api/earn/<client_id>', methods=['GET'])
def get_earn(client_id):
    """Placeholder endpoint for Binance Earn positions.
    
    Provides a static response for now so that the frontend does not raise
    404 errors while the real implementation is still under development.
    """
    if client_id not in api_clients:
        return jsonify({"error": "Client not found"}), 404
    
    return jsonify({
        "earn_positions": [],
        "message": "Earn functionality not implemented yet"
    })

@app.route('/api/binance/info')
def binance_info():
    """Information about Binance Futures trading"""
    return jsonify({
        "trading_type": "USDM Futures (USD-M Perpetual)",
        "api_endpoint": "https://fapi.binance.com",
        "explanation": {
            "why_usdm": "USDM (USD-Margined) futures use stablecoins like USDT as collateral",
            "leverage": "Supports up to 125x leverage depending on symbol",
            "symbols": "Trades pairs like XRPUSDC, BTCUSDT, ETHUSDT",
            "margin_type": "Cross margin by default, can switch to isolated"
        },
        "current_config": {
            "testnet": False,
            "live_trading": True,
            "margin_mode": "Cross margin (default)",
            "position_mode": "One-way mode (default)",
            "price_fetching": "enabled"
        },
        "symbol_precision": SYMBOL_PRECISION
    })

@app.route('/api/tracked-positions')
def get_tracked_positions():
    """Get currently tracked positions"""
    try:
        tracked_data = []
        for position_key, position in open_positions.items():
            tracked_data.append({
                "position_key": position_key,
                "strategy_id": position["strategy_id"],
                "symbol": position["symbol"],
                "side": position["side"],
                "quantity": position["quantity"],
                "entry_price": position["entry_price"],
                "timestamp": position["timestamp"].isoformat(),
                "age_minutes": int((datetime.now() - position["timestamp"]).total_seconds() / 60)
            })
        
        return jsonify({
            "success": True,
            "tracked_positions": tracked_data,
            "total_positions": len(open_positions),
            "message": "These positions are tracked for close signal processing"
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting tracked positions: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/debug-parse', methods=['POST'])
def debug_parse():
    """Debug endpoint to test message parsing"""
    try:
        raw_data = request.get_data(as_text=True)
        parsed_result = parse_tradingview_template(raw_data, 999)
        
        return jsonify({
            "raw_message": raw_data,
            "parsed_result": parsed_result,
            "parts_breakdown": raw_data.split(),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"❌ Internal server error: {error}")
    return jsonify({"success": False, "error": "Internal server error"}), 500

# Initialize application
def initialize_application():
    """Initialize the application"""
    try:
        logger.info("🔥 Initializing SIMPLIFIED Trading Platform")
        logger.info("=" * 60)
        
        if init_database():
            logger.info("✅ Database initialized")
        else:
            logger.error("❌ Database initialization failed")
        
        api_key = os.environ.get('BINANCE_API_KEY', '')
        api_secret = os.environ.get('BINANCE_API_SECRET', '')
        
        if api_key and api_secret:
            logger.info("✅ Binance API credentials configured")
            logger.info(f"🔥 LIVE TRADING MODE - API Key: {api_key[:8]}...{api_key[-4:]}")
        else:
            logger.warning("⚠️ Binance API credentials not configured")
        
        logger.info("🔥 REAL MARKET PRICE FETCHING ENABLED")
        logger.info("✅ CLOSE SIGNAL PROCESSING FIXED")
        logger.info("=" * 60)
        logger.info("🎉 Simplified application initialized successfully!")
        logger.info("🎯 Focus: Wallet Management + Working Webhooks")
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        raise

# Initialize on startup
initialize_application()

# Main execution
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"🌐 Starting Simplified Trading Platform on {host}:{port}")
    logger.info(f"🎯 SIMPLIFIED MODE: Wallet + Working Webhooks")
    
    try:
        app.run(
            host=host,
            port=port,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        raise
