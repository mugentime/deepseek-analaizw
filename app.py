from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import hashlib
import hmac
import time
import os
from datetime import datetime, timedelta
import json

# Create Flask app instance
app = Flask(__name__)
CORS(app)

# Configure Flask app
app.config['DEBUG'] = False
app.config['TESTING'] = False

# Global storage for strategies, webhooks, and tracked positions
strategies = []
webhook_activity = []
tracked_positions = []

# Global settings for rebalancing
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
BINANCE_SPOT_URL = 'https://api.binance.com'   # Spot API for Earn and Loans

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
        'message': 'Successfully connected to Binance API'
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
        flexible_data = binance_request('/sapi/v1/simple-earn/flexible/position', flexible_params, base_url=BINANCE_SPOT_URL)
        
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

@app.route('/api/loans/<client_id>')
def get_loan_positions(client_id):
    """Get Binance loan positions and LTV status"""
    try:
        # Get ongoing loans
        loans_data = binance_request('/sapi/v1/loan/ongoing/orders', {'current': 1, 'size': 100}, base_url=BINANCE_SPOT_URL)
        
        if 'error' in loans_data:
            return jsonify({'error': f'Loans API error: {loans_data["error"]}'})
        
        loan_positions = []
        total_collateral_btc = 0
        total_debt_btc = 0
        
        if 'rows' in loans_data:
            for loan in loans_data['rows']:
                try:
                    loan_coin = loan.get('loanCoin', '')
                    collateral_coin = loan.get('collateralCoin', '')
                    principal_amount = float(loan.get('initialPrincipal', 0))
                    collateral_amount = float(loan.get('initialCollateral', 0))
                    current_ltv = float(loan.get('currentLTV', 0))
                    liquidation_ltv = float(loan.get('liquidationLTV', 0))
                    
                    if principal_amount > 0:
                        loan_positions.append({
                            'loan_coin': loan_coin,
                            'collateral_coin': collateral_coin,
                            'principal_amount': principal_amount,
                            'collateral_amount': collateral_amount,
                            'current_ltv': current_ltv * 100,  # Convert to percentage
                            'liquidation_ltv': liquidation_ltv * 100,
                            'status': loan.get('status', ''),
                            'order_id': loan.get('orderId', '')
                        })
                        
                        # Convert to BTC equivalent (simplified)
                        if loan_coin == 'BTC':
                            total_debt_btc += principal_amount
                        elif loan_coin == 'USDT':
                            total_debt_btc += principal_amount / 50000  # Rough BTC price
                        
                        if collateral_coin == 'BTC':
                            total_collateral_btc += collateral_amount
                        elif collateral_coin == 'USDT':
                            total_collateral_btc += collateral_amount / 50000
                
                except Exception as e:
                    print(f"Error processing loan: {str(e)}")
                    continue
        
        # Calculate overall LTV
        overall_ltv = 0
        if total_collateral_btc > 0:
            overall_ltv = (total_debt_btc / total_collateral_btc) * 100
        
        # Determine health status
        health_status = "healthy"
        if overall_ltv > 80:
            health_status = "critical"
        elif overall_ltv > 70:
            health_status = "warning"
        elif overall_ltv > 60:
            health_status = "caution"
        
        return jsonify({
            'success': True,
            'loan_summary': {
                'total_collateral_btc': total_collateral_btc,
                'total_debt_btc': total_debt_btc,
                'overall_ltv': overall_ltv,
                'health_status': health_status,
                'active_loans': len(loan_positions),
                'target_ltv': rebalance_settings['target_ltv']
            },
            'loan_positions': loan_positions
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch loan positions: {str(e)}'})

@app.route('/api/ltv-status/<client_id>')
def get_ltv_status(client_id):
    """Get current LTV status for loans"""
    loans_data = get_loan_positions(client_id)
    
    if not loans_data or 'error' in loans_data:
        return jsonify({'error': 'Failed to get loan data'})
    
    loan_summary = loans_data['loan_summary']
    current_ltv = loan_summary['overall_ltv']
    target_ltv = rebalance_settings['target_ltv']
    threshold = rebalance_settings['rebalance_threshold']
    
    ltv_diff = current_ltv - target_ltv
    needs_rebalance = abs(ltv_diff) > threshold
    
    action_required = None
    recommended_actions = []
    
    if needs_rebalance:
        if current_ltv > target_ltv:
            action_required = 'reduce_ltv'
            recommended_actions = [
                f"Current LTV ({current_ltv:.1f}%) is above target ({target_ltv}%)",
                "Recommended actions: Repay loans or add collateral",
                "Priority: 1) Repay with available balance, 2) Add more collateral"
            ]
        else:
            action_required = 'increase_ltv'
            recommended_actions = [
                f"Current LTV ({current_ltv:.1f}%) is below target ({target_ltv}%)",
                "Recommended actions: Borrow more against collateral",
                "Can increase capital efficiency by borrowing more"
            ]
    else:
        recommended_actions = [
            f"LTV ({current_ltv:.1f}%) is within target range",
            "No rebalancing needed"
        ]
    
    return jsonify({
        'success': True,
        'ltv_status': {
            'current_ltv': current_ltv,
            'target_ltv': target_ltv,
            'ltv_diff': ltv_diff,
            'needs_rebalance': needs_rebalance,
            'action_required': action_required,
            'total_collateral_btc': loan_summary['total_collateral_btc'],
            'total_debt_btc': loan_summary['total_debt_btc'],
            'health_status': loan_summary['health_status'],
            'recommended_actions': recommended_actions
        }
    })

@app.route('/api/rebalance-settings', methods=['GET', 'POST'])
def handle_rebalance_settings():
    """Get or update rebalancing settings"""
    global rebalance_settings
    
    if request.method == 'GET':
        return jsonify({'success': True, 'settings': rebalance_settings})
    
    elif request.method == 'POST':
        data = request.get_json()
        if data:
            if 'target_ltv' in data:
                rebalance_settings['target_ltv'] = float(data['target_ltv'])
            if 'rebalance_threshold' in data:
                rebalance_settings['rebalance_threshold'] = float(data['rebalance_threshold'])
            if 'min_rebalance_interval' in data:
                rebalance_settings['min_rebalance_interval'] = int(data['min_rebalance_interval'])
            if 'max_borrow_amount_usd' in data:
                rebalance_settings['max_borrow_amount_usd'] = float(data['max_borrow_amount_usd'])
            if 'min_repay_amount_usd' in data:
                rebalance_settings['min_repay_amount_usd'] = float(data['min_repay_amount_usd'])
        
        return jsonify({'success': True, 'settings': rebalance_settings})

@app.route('/api/calculate-rebalance/<client_id>')
def calculate_rebalance_actions(client_id):
    """Calculate required rebalancing actions"""
    ltv_data = get_ltv_status(client_id)
    
    if 'error' in ltv_data:
        return jsonify({'error': ltv_data['error']})
    
    ltv_status = ltv_data['ltv_status']
    actions = []
    
    if not ltv_status['needs_rebalance']:
        return jsonify({'success': True, 'actions': actions, 'message': 'No rebalancing needed'})
    
    # Calculate actions based on LTV difference
    if ltv_status['action_required'] == 'reduce_ltv':
        # Need to repay debt or add collateral
        ltv_reduction_needed = ltv_status['ltv_diff']
        current_debt_btc = ltv_status['total_debt_btc']
        target_debt_btc = ltv_status['total_collateral_btc'] * (ltv_status['target_ltv'] / 100)
        debt_reduction_btc = current_debt_btc - target_debt_btc
        
        # Convert to USDT (rough estimate)
        debt_reduction_usdt = debt_reduction_btc * 50000
        
        if debt_reduction_usdt > rebalance_settings['min_repay_amount_usd']:
            actions.append({
                'action_type': 'repay',
                'asset': 'USDT',
                'amount': debt_reduction_usdt,
                'description': f'Repay ${debt_reduction_usdt:.2f} to reduce LTV'
            })
    
    elif ltv_status['action_required'] == 'increase_ltv':
        # Can borrow more
        current_debt_btc = ltv_status['total_debt_btc']
        target_debt_btc = ltv_status['total_collateral_btc'] * (ltv_status['target_ltv'] / 100)
        additional_borrow_btc = target_debt_btc - current_debt_btc
        
        # Convert to USDT and apply safety margin
        additional_borrow_usdt = additional_borrow_btc * 50000 * 0.9  # 90% safety margin
        max_borrow = rebalance_settings['max_borrow_amount_usd']
        
        borrow_amount = min(additional_borrow_usdt, max_borrow)
        
        if borrow_amount > 50:  # Minimum $50
            actions.append({
                'action_type': 'borrow',
                'asset': 'USDT',
                'amount': borrow_amount,
                'description': f'Borrow ${borrow_amount:.2f} to increase LTV'
            })
    
    return jsonify({'success': True, 'actions': actions})

@app.route('/api/perform-rebalance/<client_id>', methods=['POST'])
def perform_rebalance(client_id):
    """Execute rebalancing actions"""
    # Get calculated actions
    actions_data = calculate_rebalance_actions(client_id)
    
    if 'error' in actions_data:
        return jsonify({'error': actions_data['error']})
    
    actions = actions_data['actions']
    
    if not actions:
        return jsonify({'success': True, 'message': 'No actions to perform'})
    
    # Get before LTV
    before_ltv_data = get_ltv_status(client_id)
    before_ltv = before_ltv_data['ltv_status']['current_ltv'] if 'ltv_status' in before_ltv_data else 0
    
    executed_actions = []
    successful_actions = 0
    failed_actions = 0
    
    for action in actions:
        try:
            if action['action_type'] == 'repay':
                # In a real implementation, this would make API calls to repay loans
                # For now, we'll simulate success
                executed_actions.append({
                    'action': action,
                    'success': True,
                    'message': f'Simulated repay of {action["amount"]:.2f} {action["asset"]}'
                })
                successful_actions += 1
                
            elif action['action_type'] == 'borrow':
                # In a real implementation, this would make API calls to borrow
                # For now, we'll simulate success
                executed_actions.append({
                    'action': action,
                    'success': True,
                    'message': f'Simulated borrow of {action["amount"]:.2f} {action["asset"]}'
                })
                successful_actions += 1
                
        except Exception as e:
            executed_actions.append({
                'action': action,
                'success': False,
                'error': str(e)
            })
            failed_actions += 1
    
    # Get after LTV (in real implementation, this would show actual changes)
    after_ltv_data = get_ltv_status(client_id)
    after_ltv = after_ltv_data['ltv_status']['current_ltv'] if 'ltv_status' in after_ltv_data else before_ltv
    
    return jsonify({
        'success': failed_actions == 0,
        'message': f'Rebalancing completed. {successful_actions} successful, {failed_actions} failed.',
        'before_ltv': before_ltv,
        'after_ltv': after_ltv,
        'executed_actions': executed_actions
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
    print("🚀 Starting Efficient Trading Platform...")
    print(f"📊 Flask app: {app}")
    print(f"🔧 Environment: {os.environ.get('FLASK_ENV', 'production')}")
    print(f"🔑 API Key configured: {bool(BINANCE_API_KEY and BINANCE_API_KEY.strip())}")
    print(f"🔐 Secret Key configured: {bool(BINANCE_SECRET_KEY and BINANCE_SECRET_KEY.strip())}")
    
    try:
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)
    except Exception as e:
        print(f"❌ Failed to start app: {e}")
        import traceback
        traceback.print_exc()
        raise