"""
Binance Loan Management Module
Comprehensive loan data retrieval and management
"""

import requests
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class LoanPosition:
    """Represents a single loan position"""
    order_id: str
    loan_coin: str
    collateral_coin: str
    total_debt: float
    principal: float
    interest: float
    current_ltv: float
    initial_ltv: float
    margin_call_ltv: float
    liquidation_ltv: float
    collateral_amount: float
    hourly_interest_rate: float
    loan_date: datetime
    loan_term: int
    status: str
    raw_data: dict

@dataclass
class LoanSummary:
    """Summary of all loan positions"""
    total_positions: int
    total_debt_usd: float
    total_collateral_usd: float
    average_ltv: float
    highest_ltv: float
    margin_call_risk: int
    liquidation_risk: int
    total_daily_interest: float
    active_loan_coins: List[str]
    active_collateral_coins: List[str]

class BinanceLoanManager:
    """Manages Binance loan data retrieval and analysis"""
    
    def __init__(self, binance_client):
        self.client = binance_client
        self.loan_positions = []
        self.loan_summary = None
        self.last_update = None
        
    def get_all_loan_data(self) -> Dict:
        """Get comprehensive loan data from all available endpoints"""
        try:
            logger.info("Fetching comprehensive loan data from Binance")
            
            loan_data = {
                'ongoing_orders': self.get_ongoing_loans(),
                'borrow_history': self.get_borrow_history(),
                'repay_history': self.get_repay_history(),
                'ltv_adjustment_history': self.get_ltv_adjustment_history(),
                'loan_income': self.get_loan_income(),
                'vip_ongoing_orders': self.get_vip_ongoing_loans(),
                'summary': None,
                'positions': [],
                'timestamp': datetime.now().isoformat()
            }
            
            # Process ongoing loans into structured positions
            if loan_data['ongoing_orders'].get('success'):
                loan_data['positions'] = self._process_loan_positions(
                    loan_data['ongoing_orders']['data']
                )
                loan_data['summary'] = self._calculate_loan_summary(
                    loan_data['positions']
                )
            
            self.last_update = datetime.now()
            return loan_data
            
        except Exception as e:
            logger.error(f"Error fetching loan data: {str(e)}")
            return {'error': f'Failed to fetch loan data: {str(e)}'}
    
    def get_ongoing_loans(self) -> Dict:
        """Get all ongoing loan orders"""
        try:
            logger.info("Fetching ongoing loan orders")
            
            params = {
                'current': 1,
                'size': 100  # Maximum allowed
            }
            
            result = self.client.binance_request('/sapi/v1/loan/ongoing/orders', params)
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'data': result,
                'count': len(result.get('rows', [])),
                'endpoint': '/sapi/v1/loan/ongoing/orders'
            }
            
        except Exception as e:
            logger.error(f"Error fetching ongoing loans: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_borrow_history(self, days: int = 30) -> Dict:
        """Get loan borrow history"""
        try:
            logger.info(f"Fetching borrow history for last {days} days")
            
            end_time = int(time.time() * 1000)
            start_time = end_time - (days * 24 * 60 * 60 * 1000)  # X days ago
            
            params = {
                'startTime': start_time,
                'endTime': end_time,
                'current': 1,
                'size': 100
            }
            
            result = self.client.binance_request('/sapi/v1/loan/borrow/history', params)
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'data': result,
                'count': len(result.get('rows', [])),
                'endpoint': '/sapi/v1/loan/borrow/history'
            }
            
        except Exception as e:
            logger.error(f"Error fetching borrow history: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_repay_history(self, days: int = 30) -> Dict:
        """Get loan repay history"""
        try:
            logger.info(f"Fetching repay history for last {days} days")
            
            end_time = int(time.time() * 1000)
            start_time = end_time - (days * 24 * 60 * 60 * 1000)
            
            params = {
                'startTime': start_time,
                'endTime': end_time,
                'current': 1,
                'size': 100
            }
            
            result = self.client.binance_request('/sapi/v1/loan/repay/history', params)
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'data': result,
                'count': len(result.get('rows', [])),
                'endpoint': '/sapi/v1/loan/repay/history'
            }
            
        except Exception as e:
            logger.error(f"Error fetching repay history: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_ltv_adjustment_history(self, days: int = 30) -> Dict:
        """Get LTV adjustment history"""
        try:
            logger.info(f"Fetching LTV adjustment history for last {days} days")
            
            end_time = int(time.time() * 1000)
            start_time = end_time - (days * 24 * 60 * 60 * 1000)
            
            params = {
                'startTime': start_time,
                'endTime': end_time,
                'current': 1,
                'size': 100
            }
            
            result = self.client.binance_request('/sapi/v1/loan/ltv/adjustment/history', params)
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'data': result,
                'count': len(result.get('rows', [])),
                'endpoint': '/sapi/v1/loan/ltv/adjustment/history'
            }
            
        except Exception as e:
            logger.error(f"Error fetching LTV adjustment history: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_loan_income(self, days: int = 30) -> Dict:
        """Get loan income history"""
        try:
            logger.info(f"Fetching loan income for last {days} days")
            
            end_time = int(time.time() * 1000)
            start_time = end_time - (days * 24 * 60 * 60 * 1000)
            
            params = {
                'startTime': start_time,
                'endTime': end_time,
                'current': 1,
                'size': 100
            }
            
            result = self.client.binance_request('/sapi/v1/loan/income', params)
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'data': result,
                'count': len(result.get('rows', [])),
                'endpoint': '/sapi/v1/loan/income'
            }
            
        except Exception as e:
            logger.error(f"Error fetching loan income: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_vip_ongoing_loans(self) -> Dict:
        """Get VIP loan ongoing orders"""
        try:
            logger.info("Fetching VIP ongoing loan orders")
            
            params = {
                'current': 1,
                'size': 100
            }
            
            result = self.client.binance_request('/sapi/v1/loan/vip/ongoing/orders', params)
            
            if 'error' in result:
                return {'success': False, 'error': result['error']}
            
            return {
                'success': True,
                'data': result,
                'count': len(result.get('rows', [])),
                'endpoint': '/sapi/v1/loan/vip/ongoing/orders'
            }
            
        except Exception as e:
            logger.error(f"Error fetching VIP ongoing loans: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _process_loan_positions(self, ongoing_data: Dict) -> List[Dict]:
        """Process raw ongoing loan data into structured positions"""
        positions = []
        
        try:
            if not ongoing_data or 'rows' not in ongoing_data:
                return positions
            
            for loan in ongoing_data['rows']:
                try:
                    position = {
                        'order_id': loan.get('orderId', ''),
                        'loan_coin': loan.get('loanCoin', ''),
                        'collateral_coin': loan.get('collateralCoin', ''),
                        'total_debt': float(loan.get('totalDebt', 0)),
                        'principal': float(loan.get('principal', 0)),
                        'interest': float(loan.get('interest', 0)),
                        'current_ltv': float(loan.get('currentLTV', 0)),
                        'initial_ltv': float(loan.get('initialLTV', 0)),
                        'margin_call_ltv': float(loan.get('marginCallLTV', 0)),
                        'liquidation_ltv': float(loan.get('liquidationLTV', 0)),
                        'collateral_amount': float(loan.get('collateralAmount', 0)),
                        'hourly_interest_rate': float(loan.get('hourlyInterestRate', 0)),
                        'loan_date': datetime.fromtimestamp(int(loan.get('loanDate', 0)) / 1000),
                        'loan_term': int(loan.get('loanTerm', 0)),
                        'status': loan.get('status', 'UNKNOWN'),
                        
                        # Calculated fields
                        'daily_interest': float(loan.get('hourlyInterestRate', 0)) * 24 * float(loan.get('principal', 0)),
                        'ltv_utilization': (float(loan.get('currentLTV', 0)) / float(loan.get('marginCallLTV', 1))) * 100 if float(loan.get('marginCallLTV', 0)) > 0 else 0,
                        'liquidation_risk': 'HIGH' if float(loan.get('currentLTV', 0)) > float(loan.get('marginCallLTV', 0)) * 0.9 else 'MEDIUM' if float(loan.get('currentLTV', 0)) > float(loan.get('marginCallLTV', 0)) * 0.7 else 'LOW',
                        
                        # Raw data for debugging
                        'raw_data': loan
                    }
                    
                    positions.append(position)
                    
                except Exception as e:
                    logger.warning(f"Error processing loan position: {str(e)}")
                    continue
            
            logger.info(f"Processed {len(positions)} loan positions")
            return positions
            
        except Exception as e:
            logger.error(f"Error processing loan positions: {str(e)}")
            return positions
    
    def _calculate_loan_summary(self, positions: List[Dict]) -> Dict:
        """Calculate summary statistics for all loan positions"""
        try:
            if not positions:
                return {
                    'total_positions': 0,
                    'total_debt_usd': 0,
                    'total_collateral_usd': 0,
                    'average_ltv': 0,
                    'highest_ltv': 0,
                    'margin_call_risk': 0,
                    'liquidation_risk': 0,
                    'total_daily_interest': 0,
                    'active_loan_coins': [],
                    'active_collateral_coins': []
                }
            
            total_debt = sum(pos['total_debt'] for pos in positions)
            total_principal = sum(pos['principal'] for pos in positions)
            total_daily_interest = sum(pos['daily_interest'] for pos in positions)
            
            ltvs = [pos['current_ltv'] for pos in positions if pos['current_ltv'] > 0]
            average_ltv = sum(ltvs) / len(ltvs) if ltvs else 0
            highest_ltv = max(ltvs) if ltvs else 0
            
            margin_call_risk = sum(1 for pos in positions if pos['liquidation_risk'] in ['HIGH', 'MEDIUM'])
            liquidation_risk = sum(1 for pos in positions if pos['liquidation_risk'] == 'HIGH')
            
            loan_coins = list(set(pos['loan_coin'] for pos in positions))
            collateral_coins = list(set(pos['collateral_coin'] for pos in positions))
            
            return {
                'total_positions': len(positions),
                'total_debt_usd': total_debt,
                'total_principal_usd': total_principal,
                'total_interest_usd': total_debt - total_principal,
                'average_ltv': average_ltv,
                'highest_ltv': highest_ltv,
                'margin_call_risk': margin_call_risk,
                'liquidation_risk': liquidation_risk,
                'total_daily_interest': total_daily_interest,
                'total_annual_interest': total_daily_interest * 365,
                'active_loan_coins': sorted(loan_coins),
                'active_collateral_coins': sorted(collateral_coins),
                'risk_distribution': {
                    'low': sum(1 for pos in positions if pos['liquidation_risk'] == 'LOW'),
                    'medium': sum(1 for pos in positions if pos['liquidation_risk'] == 'MEDIUM'),
                    'high': sum(1 for pos in positions if pos['liquidation_risk'] == 'HIGH')
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating loan summary: {str(e)}")
            return {'error': str(e)}
    
    def get_loan_by_id(self, order_id: str) -> Optional[Dict]:
        """Get specific loan by order ID"""
        try:
            for position in self.loan_positions:
                if position.get('order_id') == order_id:
                    return position
            return None
        except Exception as e:
            logger.error(f"Error getting loan by ID: {str(e)}")
            return None
    
    def get_loans_by_coin(self, coin: str, loan_type: str = 'both') -> List[Dict]:
        """Get loans filtered by coin and type"""
        try:
            filtered_loans = []
            
            for position in self.loan_positions:
                if loan_type == 'loan' and position.get('loan_coin') == coin:
                    filtered_loans.append(position)
                elif loan_type == 'collateral' and position.get('collateral_coin') == coin:
                    filtered_loans.append(position)
                elif loan_type == 'both' and (position.get('loan_coin') == coin or position.get('collateral_coin') == coin):
                    filtered_loans.append(position)
            
            return filtered_loans
            
        except Exception as e:
            logger.error(f"Error filtering loans by coin: {str(e)}")
            return []