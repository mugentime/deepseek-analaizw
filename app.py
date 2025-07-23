from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import hashlib
import hmac
import time
import os
from datetime import datetime, timedelta
import json
from rebalancing_module import RebalancingEngine

# Setup logging
try:
    from logging_config import setup_logging, get_logger
    setup_logging()
    logger = get_logger('app')
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('app')

app = Flask(__name__)
CORS(app)

# Global storage for strategies, webhooks, tracked positions, and rebalancing
strategies = []
webhook_activity = []
tracked_positions = []
rebalancing_settings = {
    'target_ltv': 74.0,
    'rebalance_threshold': 2.0,
    'min_rebalance_interval': 300,
    'max_borrow_amount_usd': 10000,
    'min_repay_amount_usd': 10
}

# Binance API configuration
BINANCE_API_KEY = os.environ.get('BINANCE_API_KEY')
BINANCE_SECRET_KEY = os.environ.get('BINANCE_SECRET_KEY')
BINANCE_BASE_URL = 'https://fapi.binance.com'  # Futures API
BINANCE_EARN_URL = 'https://api.binance.com'   # Spot API for Earn

def create_binance_signature(query_string):
    """Create HMAC SHA256 signature for Binance API"""
    if not BINANCE_SECRET_KEY:
        raise ValueError("BINANCE_SECRET_KEY is not configured")
    
    try:
        return hmac.new(
            BINANCE_SECRET_KEY.encode('utf-8'), 
            query_string.encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()
    except Exception as e:
        raise ValueError(f"Failed to create signature: {str(e)}")

def binance_request(endpoint, params=None, method='GET', base_url=BINANCE_BASE_URL):
    """Make authenticated request to Binance API"""
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return {'error': 'API credentials not configured'}
    
    if not BINANCE_API_KEY.strip() or not BINANCE_SECRET_KEY.strip():
        return {'error': 'API credentials are empty'}
    
    if params is None:
        params = {}
    
    try:
        params['timestamp'] = int(time.time() * 1000)
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        
        signature = create_binance_signature(query_string)
        params['signature'] = signature
        
        headers = {'X-MBX-APIKEY': BINANCE_API_KEY}
        
        if method == 'GET':
            response = requests.get(f"{base_url}{endpoint}", params=params, headers=headers, timeout=10)
        elif method == 'POST':
            response = requests.post(f"{base_url}{endpoint}", params=params, headers=headers, timeout=10)
        else:
            return {'error': f'Unsupported method: {method}'}
        
        if response.status_code == 200:
            return response.json()
        else:
            return {'error': f'API Error {response.status_code}: {response.text}'}
            
    except ValueError as e:
        return {'error': f'Configuration error: {str(e)}'}
    except requests.exceptions.RequestException as e:
        return {'error': f'Network error: {str(e)}'}
    except Exception as e:
        return {'error': f'Request failed: {str(e)}'}

# Mock Binance client for rebalancing engine
class MockBinanceClient:
    def get_margin_account(self):
        return binance_request('/sapi/v1/margin/account', {}, base_url=BINANCE_EARN_URL)
    
    def margin_repay(self, asset, amount):
        params = {'asset': asset, 'amount': amount}
        return binance_request('/sapi/v1/margin/repay', params, method='POST', base_url=BINANCE_EARN_URL)
    
    def margin_borrow(self, asset, amount):
        params = {'asset': asset, 'amount': amount}
        return binance_request('/sapi/v1/margin/borrow', params, method='POST', base_url=BINANCE_EARN_URL)
    
    def spot_order(self, symbol, side, quantity):
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': quantity
        }
        return binance_request('/api/v3/order', params, method='POST', base_url=BINANCE_EARN_URL)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({
        'status': 'operational',
        'api_configured': bool(BINANCE_API_KEY and BINANCE_SECRET_KEY),
        'webhook_count': len(webhook_activity),
        'tracked_positions': len(tracked_positions),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/debug/config')
def debug_config():
    """Debug endpoint to check API configuration"""
    return jsonify({
        'binance_api_key_set': bool(BINANCE_API_KEY and BINANCE_API_KEY.strip()),
        'binance_secret_key_set': bool(BINANCE_SECRET_KEY and BINANCE_SECRET_KEY.strip()),
        'api_key_length': len(BINANCE_API_KEY) if BINANCE_API_KEY else 0,
        'secret_key_length': len(BINANCE_SECRET_KEY) if BINANCE_SECRET_KEY else 0,
        'api_key_preview': BINANCE_API_KEY[:8] + '...' if BINANCE_API_KEY and len(BINANCE_API_KEY) > 8 else 'NOT_SET',
        'secret_key_preview': BINANCE_SECRET_KEY[:8] + '...' if BINANCE_SECRET_KEY and len(BINANCE_SECRET_KEY) > 8 else 'NOT_SET',
        'env_vars_available': {
            'BINANCE_API_KEY': 'BINANCE_API_KEY' in os.environ,
            'BINANCE_SECRET_KEY': 'BINANCE_SECRET_KEY' in os.environ
        }
    })

@app.route('/api/connect', methods=['POST'])
def connect_api():
    """Test Binance API connection"""
    logger.info("Attempting to connect to Binance API")
    
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        logger.error("API credentials not configured")
        return jsonify({'success': False, 'error': 'API credentials not configured'})
    
    result = binance_request('/fapi/v2/account')
    if 'error' in result:
        logger.error(f"Binance API connection failed: {result['error']}")
        return jsonify({'success': False, 'error': result['error']})
    
    logger.info("Successfully connected to Binance Futures API")
    return jsonify({
        'success': True,
        'client_id': 'live_client',
        'message': 'Successfully connected to Binance Futures API'
    })

@app.route('/api/balance/<client_id>')
def get_balance(client_id):
    """Get account balance and summary"""
    account_data = binance_request('/fapi/v2/account')
    if 'error' in account_data:
        return jsonify({'error': account_data['error']})
    
    total_wallet_balance = float(account_data.get('totalWalletBalance', 0))
    available_balance = float(account_data.get('availableBalance', 0))
    total_unrealized_pnl = float(account_data.get('totalUnrealizedPnL', 0))
    can_trade = account_data.get('canTrade', False)
    
    return jsonify({
        'success': True,
        'account_summary': {
            'total_wallet_balance': total_wallet_balance,
            'available_balance': available_balance,
            'total_unrealized_pnl': total_unrealized_pnl,
            'can_trade': can_trade
        }
    })

@app.route('/api/positions/<client_id>')
def get_positions(client_id):
    """Get open futures positions"""
    positions_data = binance_request('/fapi/v2/positionRisk')
    if 'error' in positions_data:
        return jsonify({'error': positions_data['error']})
    
    open_positions = []
    for pos in positions_data:
        position_amt = float(pos.get('positionAmt', 0))
        if position_amt != 0:
            open_positions.append({
                'symbol': pos['symbol'],
                'position_side': pos['positionSide'],
                'position_amount': position_amt,
                'entry_price': float(pos.get('entryPrice', 0)),
                'mark_price': float(pos.get('markPrice', 0)),
                'unrealized_pnl': float(pos.get('unRealizedProfit', 0)),
                'percentage': float(pos.get('percentage', 0))
            })
    
    return jsonify({
        'success': True,
        'positions': open_positions
    })

@app.route('/api/earn/<client_id>')
def get_earn_positions(client_id):
    """Get Binance Earn positions"""
    try:
        flexible_params = {'current': 1, 'size': 100}
        flexible_data = binance_request('/sapi/v1/simple-earn/flexible/position', flexible_params, base_url=BINANCE_EARN_URL)
        
        if 'error' in flexible_data:
            return jsonify({'error': f'Flexible positions API error: {flexible_data["error"]}'})
        
        earn_positions = []
        total_earn_balance = 0
        daily_rewards = 0
        flexible_count = 0
        
        if 'rows' in flexible_data:
            for pos in flexible_data['rows']:
                try:
                    if 'asset' not in pos:
                        continue
                    
                    asset = pos['asset']
                    amount = float(pos.get('totalAmount', 0))
                    
                    if amount > 0.000001:
                        apy = 0
                        if 'latestAnnualPercentageRate' in pos and pos['latestAnnualPercentageRate']:
                            try:
                                apy = float(pos['latestAnnualPercentageRate']) * 100
                            except:
                                pass
                        
                        daily_reward = amount * (apy / 100) / 365 if apy > 0 else 0
                        yesterday_rewards = float(pos.get('yesterdayRealTimeRewards', 0))
                        
                        earn_positions.append({
                            'asset': asset,
                            'type': 'flexible',
                            'amount': amount,
                            'apy': apy,
                            'daily_rewards': daily_reward,
                            'can_redeem': pos.get('canRedeem', True),
                            'yesterday_rewards': yesterday_rewards
                        })
                        
                        total_earn_balance += amount
                        daily_rewards += daily_reward
                        flexible_count += 1
                
                except Exception as e:
                    print(f"Error processing flexible position: {str(e)}")
                    continue
        
        return jsonify({
            'success': True,
            'summary': {
                'total_earn_balance': total_earn_balance,
                'daily_rewards': daily_rewards,
                'flexible_count': flexible_count,
                'locked_count': 0,
                'total_positions': flexible_count
            },
            'earn_positions': earn_positions
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch earn positions: {str(e)}'})

@app.route('/api/ltv-status/<client_id>')
def get_ltv_status(client_id):
    """Get current LTV status for rebalancing"""
    try:
        client = MockBinanceClient()
        engine = RebalancingEngine(client, rebalancing_settings)
        ltv_status = engine.get_ltv_status()
        
        return jsonify({
            'success': True,
            'ltv_status': ltv_status.__dict__
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get LTV status: {str(e)}'})

@app.route('/api/calculate-rebalance/<client_id>')
def calculate_rebalance(client_id):
    """Calculate rebalancing actions without executing"""
    try:
        client = MockBinanceClient()
        engine = RebalancingEngine(client, rebalancing_settings)
        ltv_status = engine.get_ltv_status()
        actions = engine.calculate_optimal_rebalance(ltv_status)
        
        return jsonify({
            'success': True,
            'actions': [action.__dict__ for action in actions],
            'ltv_status': ltv_status.__dict__
        })
    except Exception as e:
        return jsonify({'error': f'Failed to calculate rebalance: {str(e)}'})

@app.route('/api/perform-rebalance/<client_id>', methods=['POST'])
def perform_rebalance(client_id):
    """Execute rebalancing"""
    try:
        client = MockBinanceClient()
        engine = RebalancingEngine(client, rebalancing_settings)
        result = engine.perform_full_rebalance()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Failed to perform rebalance: {str(e)}'})

@app.route('/api/rebalance-settings', methods=['GET', 'POST'])
def rebalance_settings_api():
    """Get or update rebalancing settings"""
    global rebalancing_settings
    
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'settings': rebalancing_settings
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        if 'target_ltv' in data:
            rebalancing_settings['target_ltv'] = float(data['target_ltv'])
        if 'rebalance_threshold' in data:
            rebalancing_settings['rebalance_threshold'] = float(data['rebalance_threshold'])
        
        return jsonify({
            'success': True,
            'settings': rebalancing_settings
        })

@app.route('/api/strategies')
def get_strategies():
    return jsonify(strategies)

@app.route('/api/strategies', methods=['POST'])
def create_strategy():
    data = request.get_json()
    strategy_id = len(strategies) + 1
    
    new_strategy = {
        'id': strategy_id,
        'name': data.get('name', f'Strategy {strategy_id}'),
        'description': data.get('description', ''),
        'created_at': datetime.now().isoformat(),
        'total_signals': 0
    }
    
    strategies.append(new_strategy)
    return jsonify({'success': True, 'strategy_id': strategy_id})

@app.route('/api/tracked-positions')
def get_tracked_positions():
    current_time = datetime.now()
    for pos in tracked_positions:
        created_time = datetime.fromisoformat(pos['created_at'])
        age_minutes = int((current_time - created_time).total_seconds() / 60)
        pos['age_minutes'] = age_minutes
    
    return jsonify({
        'success': True,
        'tracked_positions': tracked_positions,
        'total_positions': len(tracked_positions)
    })

@app.route('/api/webhooks/activity')
def get_webhook_activity():
    return jsonify(webhook_activity)

@app.route('/webhook/tradingview/strategy/<int:strategy_id>', methods=['POST'])
def tradingview_webhook(strategy_id):
    """Handle TradingView webhooks"""
    try:
        message = request.get_data(as_text=True).strip()
        logger.info(f"Received webhook for strategy {strategy_id}: {message}")
        
        if not message:
            logger.warning("Empty webhook message received")
            return jsonify({'error': 'Empty message'}), 400
        
        strategy = next((s for s in strategies if s['id'] == strategy_id), None)
        if not strategy:
            logger.error(f"Strategy {strategy_id} not found")
            return jsonify({'error': 'Strategy not found'}), 404
        
        parsed = parse_trading_message(message)
        if not parsed:
            logger.error(f"Failed to parse webhook message: {message}")
            return jsonify({'error': 'Failed to parse message'}), 400
        
        price_data = requests.get(f"{BINANCE_BASE_URL}/fapi/v1/ticker/price?symbol={parsed['symbol']}")
        current_price = float(price_data.json()['price']) if price_data.status_code == 200 else 0
        
        webhook_entry = {
            'strategy_id': strategy_id,
            'strategy_name': strategy['name'],
            'timestamp': datetime.now().isoformat(),
            'raw_message': message,
            'parsed_data': {
                'action': parsed['action'],
                'symbol': parsed['symbol'],
                'quantity': parsed['quantity'],
                'price': current_price
            }
        }
        
        webhook_activity.insert(0, webhook_entry)
        strategy['total_signals'] += 1
        
        logger.info(f"Processed {parsed['action']} signal for {parsed['symbol']} - Price: ${current_price}")
        
        if parsed['action'] == 'close':
            global tracked_positions
            initial_count = len(tracked_positions)
            tracked_positions = [p for p in tracked_positions if p['symbol'] != parsed['symbol']]
            closed_count = initial_count - len(tracked_positions)
            
            logger.info(f"Closed {closed_count} tracked positions for {parsed['symbol']}")
            
            return jsonify({
                'success': True,
                'action': 'close',
                'symbol': parsed['symbol'],
                'closed_positions': closed_count,
                'message': f'Closed {closed_count} tracked positions for {parsed["symbol"]}'
            })
        
        if parsed['action'] in ['buy', 'sell']:
            tracked_position = {
                'symbol': parsed['symbol'],
                'side': 'LONG' if parsed['action'] == 'buy' else 'SHORT',
                'quantity': parsed['quantity'],
                'entry_price': current_price,
                'strategy_id': strategy_id,
                'created_at': datetime.now().isoformat()
            }
            tracked_positions.append(tracked_position)
            
            logger.info(f"Added tracked position: {parsed['action']} {parsed['quantity']} {parsed['symbol']} @ ${current_price}")
        
        return jsonify({
            'success': True,
            'action': parsed['action'],
            'symbol': parsed['symbol'],
            'quantity': parsed['quantity'],
            'price': current_price
        })
        
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/debug-parse', methods=['POST'])
def debug_parse():
    """Debug endpoint to test message parsing"""
    message = request.get_data(as_text=True).strip()
    parsed = parse_trading_message(message)
    
    return jsonify({
        'raw_message': message,
        'parsed_result': parsed or {'error': 'Failed to parse'}
    })

def parse_trading_message(message):
    """Parse trading signals from TradingView"""
    try:
        parts = message.strip().split()
        if len(parts) < 2:
            return None
        
        action = parts[0].lower()
        symbol = parts[1].upper()
        
        if not symbol.endswith('USDT'):
            symbol += 'USDT'
        
        if action == 'close':
            return {
                'action': action,
                'symbol': symbol,
                'quantity': 0
            }
        
        quantity = float(parts[2]) if len(parts) > 2 else 0.01
        
        if action in ['buy', 'sell']:
            return {
                'action': action,
                'symbol': symbol,
                'quantity': quantity
            }
        
        return None
    except:
        return None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    
    logger.info(f"Starting Efficient Trading Platform on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"API configured: {bool(BINANCE_API_KEY and BINANCE_SECRET_KEY)}")
    logger.info(f"Rebalancing settings: Target LTV {rebalancing_settings['target_ltv']}%, Threshold {rebalancing_settings['rebalance_threshold']}%")
    
    app.run(host='0.0.0.0', port=port, debug=debug)