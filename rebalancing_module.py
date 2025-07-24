"""
Rebalancing Module for Binance Loans
Maintains target LTV ratio by automatically managing borrowing and repaying of loans
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
import requests

logger = logging.getLogger(__name__)

@dataclass
class RebalanceAction:
    """Represents a single rebalancing action"""
    action_type: str  # 'borrow', 'repay', 'add_collateral'
    asset: str
    amount: float
    price: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

@dataclass
class LTVStatus:
    """Current LTV status and rebalancing requirements"""
    current_ltv: float
    target_ltv: float
    ltv_diff: float
    needs_rebalance: bool
    action_required: Optional[str]  # 'reduce_ltv', 'increase_ltv', None
    total_collateral_btc: float
    total_debt_btc: float
    health_status: str
    recommended_actions: List[str]

class LoanRebalancingEngine:
    """Main rebalancing engine for maintaining target LTV on Binance loans"""
    
    def __init__(self, binance_client, settings: Dict):
        self.client = binance_client
        self.settings = settings
        self.last_rebalance_time = 0
        self.rebalance_history = []
        
    def get_ltv_status(self) -> LTVStatus:
        """Calculate current LTV status and determine rebalancing needs"""
        try:
            # Get ongoing loans
            loans_data = self.client.request('/sapi/v1/loan/ongoing/orders', {'current': 1, 'size': 100})
            
            if 'error' in loans_data:
                return self._create_error_status(f"Failed to get loans: {loans_data['error']}")
            
            total_collateral_btc = 0
            total_debt_btc = 0
            active_loans = 0
            
            if 'rows' in loans_data:
                for loan in loans_data['rows']:
                    try:
                        loan_coin = loan.get('loanCoin', '')
                        collateral_coin = loan.get('collateralCoin', '')
                        principal_amount = float(loan.get('initialPrincipal', 0))
                        collateral_amount = float(loan.get('initialCollateral', 0))
                        
                        if principal_amount > 0:
                            active_loans += 1
                            
                            # Convert to BTC equivalent (simplified)
                            debt_btc = self._convert_to_btc(principal_amount, loan_coin)
                            collateral_btc = self._convert_to_btc(collateral_amount, collateral_coin)
                            
                            total_debt_btc += debt_btc
                            total_collateral_btc += collateral_btc
                    
                    except Exception as e:
                        logger.warning(f"Error processing loan: {str(e)}")
                        continue
            
            # Calculate LTV
            current_ltv = 0
            if total_collateral_btc > 0:
                current_ltv = (total_debt_btc / total_collateral_btc) * 100
            
            target_ltv = self.settings.get('target_ltv', 74.0)
            threshold = self.settings.get('rebalance_threshold', 2.0)
            
            ltv_diff = current_ltv - target_ltv
            needs_rebalance = abs(ltv_diff) > threshold
            
            # Determine health status
            health_status = "healthy"
            if current_ltv > 85:
                health_status = "critical"
            elif current_ltv > 75:
                health_status = "warning"
            elif current_ltv > 65:
                health_status = "caution"
            
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
            
            return LTVStatus(
                current_ltv=current_ltv,
                target_ltv=target_ltv,
                ltv_diff=ltv_diff,
                needs_rebalance=needs_rebalance,
                action_required=action_required,
                total_collateral_btc=total_collateral_btc,
                total_debt_btc=total_debt_btc,
                health_status=health_status,
                recommended_actions=recommended_actions
            )
            
        except Exception as e:
            logger.error(f"Error calculating LTV status: {str(e)}")
            return self._create_error_status(f"Error: {str(e)}")
    
    def _create_error_status(self, error_msg: str) -> LTVStatus:
        """Create error LTV status"""
        return LTVStatus(
            current_ltv=0, target_ltv=74, ltv_diff=0, needs_rebalance=False,
            action_required=None, total_collateral_btc=0, total_debt_btc=0,
            health_status="error", recommended_actions=[error_msg]
        )
    
    def _convert_to_btc(self, amount: float, asset: str) -> float:
        """Convert asset amount to BTC equivalent"""
        if asset == 'BTC':
            return amount
        elif asset in ['USDT', 'BUSD', 'USDC']:
            # Use approximate BTC price (in real implementation, get from API)
            btc_price = self._get_btc_price()
            return amount / btc_price
        else:
            # For other assets, would need price conversion
            # For now, return 0 or implement specific conversions
            return 0
    
    def get_loan_positions(self) -> List[Dict]:
        """Get list of active loan positions"""
        try:
            loans_data = self.client.request('/sapi/v1/loan/ongoing/orders', {'current': 1, 'size': 100})
            
            if 'error' in loans_data:
                logger.error(f"Error getting loan positions: {loans_data['error']}")
                return []
            
            loan_positions = []
            
            if 'rows' in loans_data:
                for loan in loans_data['rows']:
                    try:
                        loan_coin = loan.get('loanCoin', '')
                        collateral_coin = loan.get('collateralCoin', '')
                        principal_amount = float(loan.get('initialPrincipal', 0))
                        collateral_amount = float(loan.get('initialCollateral', 0))
                        current_ltv = float(loan.get('currentLTV', 0)) * 100
                        liquidation_ltv = float(loan.get('liquidationLTV', 0)) * 100
                        
                        if principal_amount > 0:
                            loan_positions.append({
                                'loan_coin': loan_coin,
                                'collateral_coin': collateral_coin,
                                'principal_amount': principal_amount,
                                'collateral_amount': collateral_amount,
                                'current_ltv': current_ltv,
                                'liquidation_ltv': liquidation_ltv,
                                'status': loan.get('status', ''),
                                'order_id': loan.get('orderId', ''),
                                'interest_rate': float(loan.get('interestRate', 0))
                            })
                    
                    except Exception as e:
                        logger.warning(f"Error processing loan position: {str(e)}")
                        continue
            
            return loan_positions
            
        except Exception as e:
            logger.error(f"Error getting loan positions: {str(e)}")
            return []
    
    def get_available_balances(self) -> Dict[str, float]:
        """Get available balances that can be used for repaying loans or adding collateral"""
        try:
            # Get spot wallet balances
            account_data = self.client.request('/api/v3/account', {})
            
            if 'error' in account_data:
                logger.error(f"Error getting account data: {account_data['error']}")
                return {}
            
            available_balances = {}
            
            if 'balances' in account_data:
                for balance in account_data['balances']:
                    asset = balance['asset']
                    free_balance = float(balance.get('free', 0))
                    
                    if free_balance > 0:
                        available_balances[asset] = free_balance
            
            return available_balances
            
        except Exception as e:
            logger.error(f"Error getting available balances: {str(e)}")
            return {}
    
    def calculate_optimal_rebalance(self, ltv_status: LTVStatus) -> List[RebalanceAction]:
        """Calculate optimal rebalancing actions to reach target LTV"""
        actions = []
        
        if not ltv_status.needs_rebalance:
            return actions
        
        try:
            if ltv_status.action_required == 'reduce_ltv':
                # LTV too high - need to reduce debt or add collateral
                actions.extend(self._calculate_debt_reduction_actions(ltv_status))
            
            elif ltv_status.action_required == 'increase_ltv':
                # LTV too low - can borrow more
                actions.extend(self._calculate_borrowing_actions(ltv_status))
        
        except Exception as e:
            logger.error(f"Error calculating rebalance actions: {str(e)}")
            
        return actions
    
    def _calculate_debt_reduction_actions(self, ltv_status: LTVStatus) -> List[RebalanceAction]:
        """Calculate actions to reduce LTV (repay loans or add collateral)"""
        actions = []
        
        # Get loan positions and available balances
        loan_positions = self.get_loan_positions()
        available_balances = self.get_available_balances()
        
        # Calculate target debt reduction needed
        current_debt_btc = ltv_status.total_debt_btc
        target_debt_btc = ltv_status.total_collateral_btc * (ltv_status.target_ltv / 100)
        debt_reduction_needed_btc = current_debt_btc - target_debt_btc
        
        if debt_reduction_needed_btc <= 0:
            return actions
        
        # Convert to USDT for easier calculation
        debt_reduction_needed_usdt = debt_reduction_needed_btc * self._get_btc_price()
        
        # Strategy 1: Repay using available balances
        for loan in loan_positions:
            loan_coin = loan['loan_coin']
            principal_amount = loan['principal_amount']
            available_amount = available_balances.get(loan_coin, 0)
            
            if available_amount > 0:
                # Repay up to 95% of available balance (keep some buffer)
                repay_amount = min(available_amount * 0.95, principal_amount)
                min_repay_usd = self.settings.get('min_repay_amount_usd', 10)
                
                # Convert repay amount to USD equivalent for comparison
                if loan_coin in ['USDT', 'BUSD', 'USDC']:
                    repay_amount_usd = repay_amount
                elif loan_coin == 'BTC':
                    repay_amount_usd = repay_amount * self._get_btc_price()
                else:
                    repay_amount_usd = repay_amount  # Fallback
                
                if repay_amount_usd > min_repay_usd:
                    actions.append(RebalanceAction(
                        action_type='repay',
                        asset=loan_coin,
                        amount=repay_amount
                    ))
        
        # Strategy 2: Add collateral if have suitable assets
        if len(actions) == 0 or debt_reduction_needed_usdt > 1000:  # If still need significant reduction
            for asset, balance in available_balances.items():
                if asset in ['BTC', 'ETH', 'BNB'] and balance > 0:  # Common collateral assets
                    # Add up to 90% of balance as collateral
                    collateral_amount = balance * 0.9
                    
                    # Convert to USD equivalent
                    if asset == 'BTC':
                        collateral_usd = collateral_amount * self._get_btc_price()
                    else:
                        collateral_usd = collateral_amount * 100  # Rough estimate for other assets
                    
                    if collateral_usd > 100:  # Minimum $100 worth
                        actions.append(RebalanceAction(
                            action_type='add_collateral',
                            asset=asset,
                            amount=collateral_amount
                        ))
                        break  # Only add one collateral action at a time
        
        return actions
    
    def _calculate_borrowing_actions(self, ltv_status: LTVStatus) -> List[RebalanceAction]:
        """Calculate actions to increase LTV (borrow more)"""
        actions = []
        
        # Calculate how much more we can borrow
        current_debt_btc = ltv_status.total_debt_btc
        target_debt_btc = ltv_status.total_collateral_btc * (ltv_status.target_ltv / 100)
        additional_borrow_btc = target_debt_btc - current_debt_btc
        
        if additional_borrow_btc <= 0.0001:  # Minimum meaningful amount
            return actions
        
        # Convert to USD and apply safety margin
        btc_price_usd = self._get_btc_price()
        additional_borrow_usd = additional_borrow_btc * btc_price_usd * 0.9  # 90% safety margin
        max_borrow_usd = self.settings.get('max_borrow_amount_usd', 10000)
        
        # Limit borrowing amount
        borrow_amount_usdt = min(additional_borrow_usd, max_borrow_usd)
        
        if borrow_amount_usdt > 50:  # Minimum $50
            actions.append(RebalanceAction(
                action_type='borrow',
                asset='USDT',
                amount=borrow_amount_usdt
            ))
        
        return actions
    
    def _get_btc_price(self) -> float:
        """Get current BTC price in USD"""
        try:
            # Use Binance API to get current BTC price
            url = "https://api.binance.com/api/v3/ticker/price"
            params = {"symbol": "BTCUSDT"}
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            return float(data['price'])
        except Exception as e:
            logger.warning(f"Failed to get BTC price, using default: {str(e)}")
            return 50000.0  # Default fallback price
    
    def execute_rebalance_actions(self, actions: List[RebalanceAction]) -> List[RebalanceAction]:
        """Execute the calculated rebalancing actions"""
        executed_actions = []
        
        for action in actions:
            try:
                if action.action_type == 'repay':
                    # Find the loan to repay
                    loans = self.get_loan_positions()
                    target_loan = None
                    
                    for loan in loans:
                        if loan['loan_coin'] == action.asset:
                            target_loan = loan
                            break
                    
                    if target_loan:
                        result = self.client.request('/sapi/v1/loan/repay', {
                            'orderId': target_loan['order_id'],
                            'amount': action.amount
                        }, method='POST')
                        
                        if 'error' not in result:
                            action.success = True
                            logger.info(f"Successfully repaid {action.amount} {action.asset}")
                        else:
                            action.error = result['error']
                    else:
                        action.error = f"No active loan found for {action.asset}"
                
                elif action.action_type == 'borrow':
                    # Create new loan (simplified - would need collateral asset specification)
                    result = self.client.request('/sapi/v1/loan/borrow', {
                        'loanCoin': action.asset,
                        'loanAmount': action.amount,
                        'collateralCoin': 'BTC',  # Default collateral
                        'loanTerm': 7  # 7 days default
                    }, method='POST')
                    
                    if 'error' not in result:
                        action.success = True
                        logger.info(f"Successfully borrowed {action.amount} {action.asset}")
                    else:
                        action.error = result['error']
                
                elif action.action_type == 'add_collateral':
                    # Add collateral to existing loan (simplified)
                    loans = self.get_loan_positions()
                    if loans:
                        target_loan = loans[0]  # Add to first loan for simplicity
                        result = self.client.request('/sapi/v1/loan/adjust/ltv', {
                            'orderId': target_loan['order_id'],
                            'amount': action.amount,
                            'direction': 'ADDITIONAL'
                        }, method='POST')
                        
                        if 'error' not in result:
                            action.success = True
                            logger.info(f"Successfully added {action.amount} {action.asset} as collateral")
                        else:
                            action.error = result['error']
                    else:
                        action.error = "No active loans to add collateral to"
                
                executed_actions.append(action)
                
            except Exception as e:
                action.success = False
                action.error = str(e)
                logger.error(f"Failed to execute {action.action_type} {action.amount} {action.asset}: {str(e)}")
                executed_actions.append(action)
        
        # Update last rebalance time
        self.last_rebalance_time = time.time()
        
        # Store in history
        self.rebalance_history.extend(executed_actions)
        
        # Keep only last 100 actions in memory
        if len(self.rebalance_history) > 100:
            self.rebalance_history = self.rebalance_history[-100:]
        
        return executed_actions
    
    def can_rebalance(self) -> Tuple[bool, str]:
        """Check if rebalancing is allowed based on time constraints and other factors"""
        min_interval = self.settings.get('min_rebalance_interval', 300)  # 5 minutes default
        
        if self.last_rebalance_time > 0:
            time_since_last = time.time() - self.last_rebalance_time
            if time_since_last < min_interval:
                return False, f"Must wait {min_interval - time_since_last:.0f} more seconds"
        
        # Add other checks here (market hours, volatility, etc.)
        
        return True, "Rebalancing allowed"
    
    def perform_full_rebalance(self) -> Dict:
        """Perform complete rebalancing process"""
        # Check if rebalancing is allowed
        can_rebalance, reason = self.can_rebalance()
        if not can_rebalance:
            return {
                'success': False,
                'error': reason,
                'ltv_status': self.get_ltv_status().__dict__
            }
        
        # Get current LTV status
        ltv_status = self.get_ltv_status()
        
        if not ltv_status.needs_rebalance:
            return {
                'success': True,
                'message': 'No rebalancing needed - LTV is within target range',
                'ltv_status': ltv_status.__dict__,
                'actions_taken': []
            }
        
        # Calculate optimal actions
        planned_actions = self.calculate_optimal_rebalance(ltv_status)
        
        if not planned_actions:
            return {
                'success': True,
                'message': 'No suitable rebalancing actions found',
                'ltv_status': ltv_status.__dict__,
                'actions_taken': []
            }
        
        # Execute actions
        executed_actions = self.execute_rebalance_actions(planned_actions)
        
        # Get updated LTV status
        updated_ltv_status = self.get_ltv_status()
        
        # Prepare response
        successful_actions = [a for a in executed_actions if a.success]
        failed_actions = [a for a in executed_actions if not a.success]
        
        return {
            'success': len(failed_actions) == 0,
            'message': f'Rebalancing completed. LTV changed from {ltv_status.current_ltv:.2f}% to {updated_ltv_status.current_ltv:.2f}%',
            'actions_taken': [a.__dict__ for a in executed_actions],
            'successful_actions': len(successful_actions),
            'failed_actions': len(failed_actions),
            'before_ltv': ltv_status.current_ltv,
            'after_ltv': updated_ltv_status.current_ltv,
            'ltv_status': updated_ltv_status.__dict__
        }