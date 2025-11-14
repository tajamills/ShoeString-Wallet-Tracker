import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from price_service import price_service

logger = logging.getLogger(__name__)

class TaxService:
    """Service for calculating cost basis and capital gains using FIFO method"""
    
    def __init__(self):
        self.method = "FIFO"  # First In, First Out
        
        # Known exchange and service addresses for categorization
        self.known_addresses = {
            # Exchanges
            '0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be': 'Binance',
            '0xd551234ae421e3bcba99a0da6d736074f22192ff': 'Binance',
            '0x564286362092d8e7936f0549571a803b203aaced': 'Binance',
            '0x0681d8db095565fe8a346fa0277bffde9c0edbbf': 'Binance',
            '0xfe9e8709d3215310075d67e3ed32a380ccf451c8': 'Binance',
            '0xa090e606e30bd747d4e6245a1517ebe430f0057e': 'Coinbase',
            '0x503828976d22510aad0201ac7ec88293211d23da': 'Coinbase',
            '0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740': 'Coinbase',
            '0x71660c4005ba85c37ccec55d0c4493e66fe775d3': 'Coinbase',
            '0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0': 'Kraken',
            '0xfa52274dd61e1643d2205169732f29114bc240b3': 'Kraken',
            '0x2910543af39aba0cd09dbb2d50200b3e800a63d2': 'Kraken',
            '0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13': 'Kraken',
            '0xe93381fb4c4f14bda253907b18fad305d799241a': 'Kraken',
            '0x73bceb1cd57c711feac4224d062b0f6ff338501e': 'Gemini',
            '0xd24400ae8bfebb18ca49be86258a3c749cf46853': 'Gemini',
            '0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8': 'Gemini',
            '0x5f65f7b609678448494de4c87521cdf6cef1e932': 'Gemini',
            # DeFi Protocols
            '0x7a250d5630b4cf539739df2c5dacb4c659f2488d': 'Uniswap V2',
            '0xe592427a0aece92de3edee1f18e0157c05861564': 'Uniswap V3',
            '0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45': 'Uniswap',
            '0x11111112542d85b3ef69ae05771c2dccff4faa26': '1inch',
            '0x1111111254fb6c44bac0bed2854e76f90643097d': '1inch V4',
            '0xdef1c0ded9bec7f1a1670819833240f027b25eff': '0x Exchange',
            '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2': 'WETH Contract',
            # NFT Marketplaces
            '0x7be8076f4ea4a4ad08075c2508e481d6c946d12b': 'OpenSea',
            '0x7f268357a8c2552623316e2562d90e642bb538e5': 'OpenSea',
            # Bridges
            '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'Circle USDC',
            '0xdac17f958d2ee523a2206206994597c13d831ec7': 'Tether USDT',
        }
    
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
