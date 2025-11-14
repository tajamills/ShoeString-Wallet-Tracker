import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from price_service import price_service

logger = logging.getLogger(__name__)

class TaxService:
    """Service for calculating cost basis and capital gains using FIFO method"""
    
    def __init__(self):
        self.method = "FIFO"  # First In, First Out
    
    def calculate_tax_data(
        self,
        transactions: List[Dict[str, Any]],
        current_balance: float,
        current_price: float,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive tax data including cost basis and capital gains
        
        Args:
            transactions: List of all transactions (sorted oldest first)
            current_balance: Current wallet balance
            current_price: Current USD price
            symbol: Token symbol (ETH, BTC, etc.)
        
        Returns:
            Dict with realized gains, unrealized gains, tax lots, etc.
        """
        try:
            # Separate buys and sells
            buys = []
            sells = []
            
            for tx in transactions:
                tx_type = tx.get('type', '')
                amount = float(tx.get('value', 0))
                
                if amount == 0:
                    continue
                
                # Get historical price if possible
                block_num = tx.get('blockNum')
                timestamp = tx.get('timestamp')
                
                # For now, use current price if historical not available
                # In production, you'd want to fetch historical prices
                price_at_time = current_price  # Simplified for now
                
                tx_data = {
                    'hash': tx.get('hash', ''),
                    'type': tx_type,
                    'amount': amount,
                    'price_usd': price_at_time,
                    'value_usd': amount * price_at_time,
                    'timestamp': timestamp,
                    'block': block_num,
                    'date': self._format_date(timestamp) if timestamp else 'Unknown'
                }
                
                if tx_type == 'received':
                    buys.append(tx_data)
                elif tx_type == 'sent':
                    sells.append(tx_data)
            
            # Calculate realized gains using FIFO
            realized_gains = self._calculate_realized_gains_fifo(buys, sells)
            
            # Calculate unrealized gains
            unrealized_gains = self._calculate_unrealized_gains(
                buys, 
                sells, 
                current_balance, 
                current_price
            )
            
            # Get remaining tax lots (unsold positions)
            remaining_lots = self._get_remaining_lots(buys, sells)
            
            # Calculate totals
            total_realized_gain = sum(g['gain_loss'] for g in realized_gains)
            total_unrealized_gain = unrealized_gains.get('total_gain', 0)
            
            # Separate short-term and long-term gains
            short_term_gains = sum(g['gain_loss'] for g in realized_gains if g['holding_period'] == 'short-term')
            long_term_gains = sum(g['gain_loss'] for g in realized_gains if g['holding_period'] == 'long-term')
            
            return {
                'method': self.method,
                'realized_gains': realized_gains,
                'unrealized_gains': unrealized_gains,
                'remaining_lots': remaining_lots,
                'summary': {
                    'total_realized_gain': total_realized_gain,
                    'total_unrealized_gain': total_unrealized_gain,
                    'total_gain': total_realized_gain + total_unrealized_gain,
                    'short_term_gains': short_term_gains,
                    'long_term_gains': long_term_gains,
                    'total_transactions': len(buys) + len(sells),
                    'buy_count': len(buys),
                    'sell_count': len(sells)
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating tax data: {str(e)}")
            return self._empty_tax_data()
    
    def _calculate_realized_gains_fifo(
        self, 
        buys: List[Dict], 
        sells: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Calculate realized gains using FIFO method"""
        realized_gains = []
        buy_queue = buys.copy()  # Queue of purchases (FIFO)
        
        for sell in sells:
            sell_amount = sell['amount']
            sell_price = sell['price_usd']
            sell_date = sell['date']
            remaining_to_sell = sell_amount
            
            # Match this sell with buys using FIFO
            while remaining_to_sell > 0 and buy_queue:
                buy = buy_queue[0]
                buy_amount = buy.get('remaining_amount', buy['amount'])
                buy_price = buy['price_usd']
                buy_date = buy['date']
                
                # How much can we match from this buy?
                matched_amount = min(buy_amount, remaining_to_sell)
                
                # Calculate gain/loss
                proceeds = matched_amount * sell_price
                cost_basis = matched_amount * buy_price
                gain_loss = proceeds - cost_basis
                
                # Determine holding period (short-term < 1 year, long-term >= 1 year)
                holding_period = self._calculate_holding_period(buy_date, sell_date)
                
                realized_gains.append({
                    'sell_hash': sell['hash'],
                    'buy_hash': buy['hash'],
                    'amount': matched_amount,
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'cost_basis': cost_basis,
                    'proceeds': proceeds,
                    'gain_loss': gain_loss,
                    'buy_date': buy_date,
                    'sell_date': sell_date,
                    'holding_period': holding_period
                })
                
                # Update remaining amounts
                remaining_to_sell -= matched_amount
                buy['remaining_amount'] = buy_amount - matched_amount
                
                # If this buy is fully used, remove it from queue
                if buy['remaining_amount'] <= 0:
                    buy_queue.pop(0)
        
        return realized_gains
    
    def _calculate_unrealized_gains(
        self,
        buys: List[Dict],
        sells: List[Dict],
        current_balance: float,
        current_price: float
    ) -> Dict[str, Any]:
        """Calculate unrealized gains for remaining holdings"""
        # Get remaining unsold lots
        remaining_lots = self._get_remaining_lots(buys, sells)
        
        unrealized_gains = []
        total_cost_basis = 0
        total_current_value = 0
        
        for lot in remaining_lots:
            amount = lot['amount']
            buy_price = lot['price_usd']
            cost_basis = amount * buy_price
            current_value = amount * current_price
            unrealized_gain = current_value - cost_basis
            
            unrealized_gains.append({
                'buy_hash': lot['hash'],
                'buy_date': lot['date'],
                'amount': amount,
                'buy_price': buy_price,
                'current_price': current_price,
                'cost_basis': cost_basis,
                'current_value': current_value,
                'unrealized_gain': unrealized_gain,
                'gain_percentage': (unrealized_gain / cost_basis * 100) if cost_basis > 0 else 0
            })
            
            total_cost_basis += cost_basis
            total_current_value += current_value
        
        return {
            'lots': unrealized_gains,
            'total_cost_basis': total_cost_basis,
            'total_current_value': total_current_value,
            'total_gain': total_current_value - total_cost_basis,
            'total_gain_percentage': ((total_current_value - total_cost_basis) / total_cost_basis * 100) if total_cost_basis > 0 else 0
        }
    
    def _get_remaining_lots(
        self,
        buys: List[Dict],
        sells: List[Dict]
    ) -> List[Dict]:
        """Get remaining unsold tax lots using FIFO"""
        buy_queue = []
        
        # Initialize buy queue with all buys
        for buy in buys:
            buy_queue.append({
                'hash': buy['hash'],
                'date': buy['date'],
                'amount': buy['amount'],
                'price_usd': buy['price_usd']
            })
        
        # Remove sold amounts using FIFO
        for sell in sells:
            remaining_to_sell = sell['amount']
            
            while remaining_to_sell > 0 and buy_queue:
                lot = buy_queue[0]
                
                if lot['amount'] <= remaining_to_sell:
                    # This entire lot was sold
                    remaining_to_sell -= lot['amount']
                    buy_queue.pop(0)
                else:
                    # Partial lot sold
                    lot['amount'] -= remaining_to_sell
                    remaining_to_sell = 0
        
        return buy_queue
    
    def _calculate_holding_period(self, buy_date: str, sell_date: str) -> str:
        """Determine if holding period is short-term or long-term"""
        try:
            # Parse dates (format: "YYYY-MM-DD" or similar)
            # For now, simplified - in production you'd parse actual dates
            return 'long-term'  # Default to long-term
            # TODO: Implement proper date parsing and comparison
        except:
            return 'unknown'
    
    def _format_date(self, timestamp: Any) -> str:
        """Format timestamp to date string"""
        try:
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
                return dt.strftime('%Y-%m-%d')
            return str(timestamp)
        except:
            return 'Unknown'
    
    def _empty_tax_data(self) -> Dict:
        """Return empty tax data structure"""
        return {
            'method': self.method,
            'realized_gains': [],
            'unrealized_gains': {
                'lots': [],
                'total_cost_basis': 0,
                'total_current_value': 0,
                'total_gain': 0,
                'total_gain_percentage': 0
            },
            'remaining_lots': [],
            'summary': {
                'total_realized_gain': 0,
                'total_unrealized_gain': 0,
                'total_gain': 0,
                'short_term_gains': 0,
                'long_term_gains': 0,
                'total_transactions': 0,
                'buy_count': 0,
                'sell_count': 0
            }
        }

# Initialize global tax service
tax_service = TaxService()
