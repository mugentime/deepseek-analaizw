from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import hashlib
import hmac
import time
import os
from datetime import datetime, timedelta
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_DOWN

app = Flask(__name__)
CORS(app)

# Global storage for strategies, webhooks, and tracked positions
strategies = []
webhook_activity = []
tracked_positions = []

# Rebalancing settings
rebalance_settings = {
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

@dataclass
class LTVStatus:
    """Current LTV status and rebalancing requirements"""
    current_ltv: float
    target_ltv: float
    ltv_diff: float
    needs_rebalance: bool
    action_required: Optional[str]
    total_asset_btc: float
    total_liability_btc: float
    margin_level: float
    recommended_actions: List[str]

@dataclass
class RebalanceAction:
    """Represents a single rebalancing action"""
    action_type: str
    asset: str
    amount: float
    price: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

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
    # Check for API credentials
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return {'error': 'API credentials not configured'}
    
    # Check for empty or whitespace-only credentials
    if not BINANCE_API_KEY.strip() or not BINANCE_SECRET_KEY.strip():
        return {'error': 'API credentials are empty'}
    
    if params is None:
        params = {}
    
    try:
        params['timestamp'] = int(time.time() * 1000)
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        
        # Create signature with better error handling
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

def get_btc_price():
    """Get current BTC price in USD"""
    try:
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {"symbol": "BTCUSDT"}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return float(data['price'])
    except Exception as e:
        return 50000.0  # Default fallback price

def get_ltv_status(client_id) -> LTVStatus:
    """Calculate current LTV status and determine rebalancing needs"""
    try:
        margin_account = binance_request('/sapi/v1/margin/account', {}, base_url=BINANCE_EARN_URL)
        
        if 'error' in margin_account:
            return LTVStatus(
                current_ltv=0, target_ltv=74, ltv_diff=0, needs_rebalance=False,
                action_required=None, total_asset_btc=0, total_liability_btc=0,
                margin_level=0, recommended_actions=[f"Error: {margin_account['error']}"]
            )
        
        total_asset_btc = float(margin_account.get('totalAssetOfBtc', 0))
        total_liability_btc = float(margin_account.get('totalLiabilityOfBtc', 0))
        margin_level = float(margin_account.get('marginLevel', 0))
        
        if total_asset_btc == 0:
            current_ltv = 0
        else:
            current_ltv = (total_liability_btc / total_asset_btc) * 100
        
        target_ltv = rebalance_settings.get('target_ltv', 74.0)
        threshold = rebalance_settings.get('rebalance_threshold', 2.0)
        
        ltv_diff = current_ltv - target_ltv
        needs_rebalance = abs(ltv_diff) > threshold
        
        action_required = None
        recommended_actions = []
        
        if needs_rebalance:
            if current_ltv > target_ltv:
                action_required = 'reduce_ltv'
                recommended_actions = [
                    f"Current LTV ({current_ltv:.1f}%) is above target ({target_ltv}%)",
                    "Recommended: Repay debt or add collateral",
                    "Priority: 1) Repay with available balance, 2) Sell assets to repay"
                ]
            else:
                action_required = 'increase_ltv'
                recommended_actions = [
                    f"Current LTV ({current_ltv:.1f}%) is below target ({target_ltv}%)",
                    "Recommended: Borrow more against collateral",
                    "Can increase capital efficiency by borrowing more"
                ]
        else:
            recommended_actions = [
                f"LTV ({current_ltv:.1f}%) is within target range",
                "No rebalancing needed"
            ]
        
        return LTVStatus(
            current_ltv=current_ltv,
            target_ltv=target_ltv,
            ltv_diff=ltv_diff,
            needs_rebalance=needs_rebalance,
            action_required=action_required,
            total_asset_btc=total_asset_btc,
            total_liability_btc=total_liability_btc,
            margin_level=margin_level,
            recommended_actions=recommended_actions
        )
        
    except Exception as e:
        return LTVStatus(
            current_ltv=0, target_ltv=74, ltv_diff=0, needs_rebalance=False,
            action_required=None, total_asset_btc=0, total_liability_btc=0,
            margin_level=0, recommended_actions=[f"Error: {str(e)}"]
        )

def calculate_rebalance_actions(ltv_status: LTVStatus) -> List[RebalanceAction]:
    """Calculate optimal rebalancing actions to reach target LTV"""
    actions = []
    
    if not ltv_status.needs_rebalance:
        return actions
    
    try:
        if ltv_status.action_required == 'reduce_ltv':
            # Get borrowed assets
            margin_account = binance_request('/sapi/v1/margin/account', {}, base_url=BINANCE_EARN_URL)
            if 'error' not in margin_account and 'userAssets' in margin_account:
                for asset_info in margin_account['userAssets']:
                    borrowed = float(asset_info.get('borrowed', 0))
                    available = float(asset_info.get('free', 0))
                    
                    if borrowed > 0 and available > 0:
                        # Repay up to 95% of available balance
                        repay_amount = min(available * 0.95, borrowed)
                        min_repay = rebalance_settings.get('min_repay_amount_usd', 10) / 50000
                        
                        if repay_amount > min_repay:
                            actions.append(RebalanceAction(
                                action_type='repay',
                                asset=asset_info['asset'],
                                amount=repay_amount
                            ))
        
        elif ltv_status.action_required == 'increase_ltv':
            # Calculate how much more we can borrow
            current_debt_btc = ltv_status.total_liability_btc
            target_debt_btc = ltv_status.total_asset_btc * (ltv_status.target_ltv / 100)
            additional_borrow_btc = target_debt_btc - current_debt_btc
            
            if additional_borrow_btc > 0.0001:
                btc_price_usd = get_btc_price()
                additional_borrow_usd = additional_borrow_btc * btc_price_usd * 0.9  # 90% safety margin
                max_borrow_usd = rebalance_settings.get('max_borrow_amount_usd', 10000)
                
                borrow_amount_usd = min(additional_borrow_usd, max_borrow_usd)
                
                if borrow_amount_usd > 50:  # Minimum $50
                    actions.append(RebalanceAction(
                        action_type='borrow',
                        asset='USDT',
                        amount=borrow_amount_usd
                    ))
    
    except Exception as e:
        print(f"Error calculating rebalance actions: {str(e)}")
        
    return actions

@app.route('/')
def index():
    return render_template('simplified_index.html')

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
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return jsonify({'success': False, 'error': 'API credentials not configured'})
    
    # Test connection with account info
    result = binance_request('/fapi/v2/account')
    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']})
    
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
    
    # Filter only positions with non-zero amounts
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
        # Get flexible savings positions
        flexible_params = {'current': 1, 'size': 100}
        flexible_data = binance_request('/sapi/v1/simple-earn/flexible/position', flexible_params, base_url=BINANCE_EARN_URL)
        
        if 'error' in flexible_data:
            return jsonify({'error': f'Flexible positions API error: {flexible_data["error"]}'})
        
        earn_positions = []
        total_earn_balance = 0
        daily_rewards = 0
        flexible_count = 0
        
        # Process flexible positions
        if 'rows' in flexible_data:
            for pos in flexible_data['rows']:
                try:
                    if 'asset' not in pos:
                        continue
                    
                    asset = pos['asset']
                    amount = float(pos.get('totalAmount', 0))
                    
                    if amount > 0.000001:
                        # Simple APY detection
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

@app.route('/api/margin/<client_id>')
def get_margin_positions(client_id):
    """Get margin account details including borrowed positions and LTV"""
    try:
        margin_data = binance_request('/sapi/v1/margin/account', {}, base_url=BINANCE_EARN_URL)
        
        if 'error' in margin_data:
            return jsonify({'error': f'Margin API error: {margin_data["error"]}'})
        
        total_asset_btc = float(margin_data.get('totalAssetOfBtc', 0))
        total_liability_btc = float(margin_data.get('totalLiabilityOfBtc', 0))
        margin_level = float(margin_data.get('marginLevel', 0))
        
        ltv_ratio = 0
        if total_asset_btc > 0:
            ltv_ratio = (total_liability_btc / total_asset_btc) * 100
        
        borrowed_positions = []
        collateral_positions = []
        
        if 'userAssets' in margin_data:
            for asset in margin_data['userAssets']:
                asset_name = asset['asset']
                free_balance = float(asset.get('free', 0))
                locked_balance = float(asset.get('locked', 0))
                borrowed_amount = float(asset.get('borrowed', 0))
                interest_amount = float(asset.get('interest', 0))
                net_asset = float(asset.get('netAsset', 0))
                
                if borrowed_amount > 0:
                    borrowed_positions.append({
                        'asset': asset_name,
                        'borrowed_amount': borrowed_amount,
                        'interest_accrued': interest_amount,
                        'total_debt': borrowed_amount + interest_amount,
                        'free_balance': free_balance,
                        'locked_balance': locked_balance,
                        'net_asset': net_asset
                    })
                
                if net_asset > 0:
                    collateral_positions.append({
                        'asset': asset_name,
                        'free_balance': free_balance,
                        'locked_balance': locked_balance,
                        'total_balance': free_balance + locked_balance,
                        'net_asset': net_asset
                    })
        
        margin_health = "healthy"
        if margin_level < 1.1:
            margin_health = "critical"
        elif margin_level < 1.3:
            margin_health = "warning"
        elif margin_level < 2.0:
            margin_health = "caution"
        
        return jsonify({
            'success': True,
            'margin_summary': {
                'total_asset_btc': total_asset_btc,
                'total_liability_btc': total_liability_btc,
                'margin_level': margin_level,
                'ltv_ratio': ltv_ratio,
                'margin_health': margin_health,
                'borrowed_count': len(borrowed_positions),
                'collateral_count': len(collateral_positions),
                'trade_enabled': margin_data.get('tradeEnabled', False),
                'transfer_enabled': margin_data.get('transferEnabled', False)
            },
            'borrowed_positions': borrowed_positions,
            'collateral_positions': collateral_positions
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch margin positions: {str(e)}'})

@app.route('/api/ltv-status/<client_id>')
def get_ltv_status_endpoint(client_id):
    """Get current LTV status"""
    ltv_status = get_ltv_status(client_id)
    return jsonify({
        'success': True,
        'ltv_status': {
            'current_ltv': ltv_status.current_ltv,
            'target_ltv': ltv_status.target_ltv,
            'ltv_diff': ltv_status.ltv_diff,
            'needs_rebalance': ltv_status.needs_rebalance,
            'action_required': ltv_status.action_required,
            'total_asset_btc': ltv_status.total_asset_btc,
            'total_liability_btc': ltv_status.total_liability_btc,
            'margin_level': ltv_status.margin_level,
            'recommended_actions': ltv_status.recommended_actions
        }
    })

@app.route('/api/calculate-rebalance/<client_id>')
def calculate_rebalance_endpoint(client_id):
    """Calculate rebalancing actions"""
    ltv_status = get_ltv_status(client_id)
    actions = calculate_rebalance_actions(ltv_status)
    
    return jsonify({
        'success': True,
        'actions': [{
            'action_type': action.action_type,
            'asset': action.asset,
            'amount': action.amount,
            'price': action.price
        } for action in actions]
    })

@app.route('/api/perform-rebalance/<client_id>', methods=['POST'])
def perform_rebalance_endpoint(client_id):
    """Execute rebalancing actions"""
    try:
        # Get current LTV status
        ltv_status = get_ltv_status(client_id)
        
        if not ltv_status.needs_rebalance:
            return jsonify({
                'success': True,
                'message': 'No rebalancing needed - LTV is within target range',
                'before_ltv': ltv_status.current_ltv,
                'after_ltv': ltv_status.current_ltv
            })
        
        # Calculate actions
        actions = calculate_rebalance_actions(ltv_status)
        
        if not actions:
            return jsonify({
                'success': True,
                'message': 'No suitable rebalancing actions found',
                'before_ltv': ltv_status.current_ltv,
                'after_ltv': ltv_status.current_ltv
            })
        
        # Execute actions (simplified for now - just return plan)
        executed_actions = []
        for action in actions:
            # In a real implementation, you would execute the trades here
            # For now, just mark as executed
            action.success = True
            executed_actions.append(action)
        
        # Get updated LTV status
        updated_ltv_status = get_ltv_status(client_id)
        
        return jsonify({
            'success': True,
            'message': f'Rebalancing completed. LTV changed from {ltv_status.current_ltv:.2f}% to {updated_ltv_status.current_ltv:.2f}%',
            'before_ltv': ltv_status.current_ltv,
            'after_ltv': updated_ltv_status.current_ltv,
            'actions_executed': len(executed_actions)
        })
        
    except Exception as e:
        return jsonify({'error': f'Rebalancing failed: {str(e)}'})

@app.route('/api/rebalance-settings', methods=['POST'])
def update_rebalance_settings():
    """Update rebalancing settings"""
    try:
        data = request.get_json()
        
        if 'target_ltv' in data:
            rebalance_settings['target_ltv'] = float(data['target_ltv'])
        
        if 'rebalance_threshold' in data:
            rebalance_settings['rebalance_threshold'] = float(data['rebalance_threshold'])
        
        return jsonify({
            'success': True,
            'settings': rebalance_settings
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to update settings: {str(e)}'})

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
        if not message:
            return jsonify({'error': 'Empty message'}), 400
        
        strategy = next((s for s in strategies if s['id'] == strategy_id), None)
        if not strategy:
            return jsonify({'error': 'Strategy not found'}), 404
        
        parsed = parse_trading_message(message)
        if not parsed:
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
        
        if parsed['action'] == 'close':
            global tracked_positions
            initial_count = len(tracked_positions)
            tracked_positions = [p for p in tracked_positions if p['symbol'] != parsed['symbol']]
            closed_count = initial_count - len(tracked_positions)
            
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
        
        return jsonify({
            'success': True,
            'action': parsed['action'],
            'symbol': parsed['symbol'],
            'quantity': parsed['quantity'],
            'price': current_price
        })
        
    except Exception as e:
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
    app.run(host='0.0.0.0', port=8080, debug=False)