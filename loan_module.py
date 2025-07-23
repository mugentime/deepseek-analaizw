"""
Rebalancing Module for Binance Margin Trading
Maintains target LTV ratio by automatically managing borrowing and repaying
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
    action_type: str  # 'borrow', 'repay', 'buy', 'sell'
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
    total_asset_btc: float
    total_liability_btc: float
    margin_level: float
    recommended_actions: List[str]

class RebalancingEngine:
    """Main rebalancing engine for maintaining target LTV"""
    
    def __init__(self, binance_client, settings: Dict):
        self.client = binance_client
        self.settings = settings
        self.last_rebalance_time = 0
        self.rebalance_history = []
        
    def get_ltv_status(self) -> LTVStatus:
        """Calculate current LTV status and determine rebalancing needs"""
        try:
            margin_account = self.client.get_margin_account()
            
            total_asset_btc = float(margin_account.get('totalAssetOfBtc', 0))
            total_liability_btc = float(margin_account.get('totalLiabilityOfBtc', 0))
            margin_level = float(margin_account.get('marginLevel', 0))
            
            if total_asset_btc == 0:
                current_ltv = 0
            else:
                current_ltv = (total_liability_btc / total_asset_btc) * 100
            
            target_ltv = self.settings.get('target_ltv', 74.0)
            threshold = self.settings.get('rebalance_threshold', 2.0)
            
            ltv_diff = current_ltv - target_ltv
            needs_rebalance = abs(ltv_diff) > threshold
            
            action_required = None
            recommended_actions = []
            
            if needs_rebalance:
                if current_ltv > target_ltv:
                    action_required = 'reduce_ltv'
                    recommended_actions = [
                        f"Current LTV ({current_ltv:.1f}%) is above target ({target_ltv}%)",
                        "Recommended actions: Repay debt or add collateral",
                        "Priority: 1) Repay with available balance, 2) Sell assets to repay"
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
                total_asset_btc=total_asset_btc,
                total_liability_btc=total_liability_btc,
                margin_level=margin_level,
                recommended_actions=recommended_actions
            )
            
        except Exception as e:
            logger.error(f"Error calculating LTV status: {str(e)}")
            return LTVStatus(
                current_ltv=0, target_ltv=74, ltv_diff=0, needs_rebalance=False,
                action_required=None, total_asset_btc=0, total_liability_btc=0,
                margin_level=0, recommended_actions=[f"Error: {str(e)}"]
            )
    
    def get_borrowed_assets(self) -> List[Dict]:
        """Get list of borrowed assets with details"""
        try:
            margin_account = self.client.get_margin_account()
            borrowed_assets = []
            
            for asset_info in margin_account.get('userAssets', []):
                borrowed = float(asset_info.get('borrowed', 0))
                if borrowed > 0:
                    borrowed_assets.append({
                        'asset': asset_info['asset'],
                        'borrowed': borrowed,
                        'free': float(asset_info.get('free', 0)),
                        'locked': float(asset_info.get('locked', 0)),
                        'interest': float(asset_info.get('interest', 0)),
                        'net': float(asset_info.get('netAsset', 0))
                    })
            
            return borrowed_assets
        except Exception as e:
            logger.error(f"Error getting borrowed assets: {str(e)}")
            return []
    
    def get_available_for_repay(self) -> Dict[str, float]:
        """Get available balances that can be used for repaying debt"""
        try:
            margin_account = self.client.get_margin_account()
            available_assets = {}
            
            for asset_info in margin_account.get('userAssets', []):
                free_balance = float(asset_info.get('free', 0))
                if free_balance > 0:
                    available_assets[asset_info['asset']] = free_balance
            
            return available_assets
        except Exception as e:
            logger.error(f"Error getting available assets: {str(e)}")
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
        """Calculate actions to reduce LTV (repay debt or add collateral)"""
        actions = []
        
        # Get borrowed assets and available balances
        borrowed_assets = self.get_borrowed_assets()
        available_balances = self.get_available_for_repay()
        
        # Calculate target debt reduction needed
        current_debt_btc = ltv_status.total_liability_btc
        target_debt_btc = ltv_status.total_asset_btc * (ltv_status.target_ltv / 100)
        debt_reduction_needed_btc = current_debt_btc - target_debt_btc
        
        if debt_reduction_needed_btc <= 0:
            return actions
        
        # Strategy 1: Repay using available balances
        for borrowed_asset in borrowed_assets:
            asset = borrowed_asset['asset']
            borrowed_amount = borrowed_asset['borrowed']
            available_amount = available_balances.get(asset, 0)
            
            if available_amount > 0:
                # Repay up to 95% of available balance (keep some buffer)
                repay_amount = min(available_amount * 0.95, borrowed_amount)
                min_repay = self.settings.get('min_repay_amount_usd', 10) / 50000  # Convert to asset units (approx)
                
                if repay_amount > min_repay:
                    actions.append(RebalanceAction(
                        action_type='repay',
                        asset=asset,
                        amount=repay_amount
                    ))
        
        # Strategy 2: If still need to reduce debt, consider selling assets
        # (Implementation would depend on specific strategy)
        
        return actions
    
    def _calculate_borrowing_actions(self, ltv_status: LTVStatus) -> List[RebalanceAction]:
        """Calculate actions to increase LTV (borrow more)"""
        actions = []
        
        # Calculate how much more we can borrow
        current_debt_btc = ltv_status.total_liability_btc
        target_debt_btc = ltv_status.total_asset_btc * (ltv_status.target_ltv / 100)
        additional_borrow_btc = target_debt_btc - current_debt_btc
        
        if additional_borrow_btc <= 0.0001:  # Minimum meaningful amount
            return actions
        
        # Convert to USD and apply safety margin
        btc_price_usd = self._get_btc_price()
        additional_borrow_usd = additional_borrow_btc * btc_price_usd * 0.9  # 90% safety margin
        max_borrow_usd = self.settings.get('max_borrow_amount_usd', 10000)
        
        # Limit borrowing amount
        borrow_amount_usd = min(additional_borrow_usd, max_borrow_usd)
        
        if borrow_amount_usd > 50:  # Minimum $50
            actions.append(RebalanceAction(
                action_type='borrow',
                asset='USDT',
                amount=borrow_amount_usd
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
                    result = self.client.margin_repay(action.asset, action.amount)
                    action.success = True
                    logger.info(f"Successfully repaid {action.amount} {action.asset}")
                
                elif action.action_type == 'borrow':
                    result = self.client.margin_borrow(action.asset, action.amount)
                    action.success = True
                    logger.info(f"Successfully borrowed {action.amount} {action.asset}")
                
                elif action.action_type == 'buy' or action.action_type == 'sell':
                    # For spot trading to rebalance
                    symbol = f"{action.asset}USDT"
                    side = 'BUY' if action.action_type == 'buy' else 'SELL'
                    result = self.client.spot_order(symbol, side, action.amount)
                    action.success = True
                    logger.info(f"Successfully executed {action.action_type} {action.amount} {action.asset}")
                
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