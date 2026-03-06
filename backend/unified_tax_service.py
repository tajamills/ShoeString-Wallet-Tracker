"""
Unified Tax Service - Combines on-chain wallet transactions with exchange CSV imports
for comprehensive tax calculation using FIFO method.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from price_service import price_service

logger = logging.getLogger(__name__)


class UnifiedTaxService:
    """
    Unified tax service that combines:
    - On-chain wallet transactions (from wallet analysis)
    - Exchange CSV imports (from exchange_transactions collection)
    
    Provides:
    - FIFO cost basis calculation across all sources
    - Realized/unrealized capital gains
    - Form 8949 compatible data
    - Tax lot tracking
    """
    
    def __init__(self):
        self.method = "FIFO"
    
    def normalize_wallet_transaction(self, tx: Dict, symbol: str) -> Dict:
        """Convert on-chain wallet transaction to unified format"""
        tx_type = tx.get('type', '')
        amount = float(tx.get('value', 0))
        
        # Determine if buy or sell
        if tx_type == 'received':
            unified_type = 'buy'
        elif tx_type == 'sent':
            unified_type = 'sell'
        else:
            unified_type = tx_type
        
        # Parse timestamp
        timestamp = tx.get('timestamp')
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        elif isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)
        
        return {
            'source': 'wallet',
            'tx_id': tx.get('hash', f"wallet_{id(tx)}"),
            'tx_type': unified_type,
            'asset': symbol,
            'amount': abs(amount),
            'price_usd': tx.get('value_usd', 0) / amount if amount else 0,
            'total_usd': tx.get('value_usd', 0),
            'fee': 0,
            'fee_asset': symbol,
            'timestamp': dt,
            'date': dt.strftime('%Y-%m-%d'),
            'raw': tx
        }
    
    def normalize_exchange_transaction(self, tx: Dict) -> Dict:
        """Convert exchange CSV transaction to unified format"""
        # Parse timestamp
        timestamp_str = tx.get('timestamp', '')
        try:
            if isinstance(timestamp_str, str):
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                dt = datetime.now(timezone.utc)
        except:
            dt = datetime.now(timezone.utc)
        
        return {
            'source': f"exchange:{tx.get('exchange', 'unknown')}",
            'tx_id': tx.get('tx_id', f"exchange_{id(tx)}"),
            'tx_type': tx.get('tx_type', 'unknown'),
            'asset': tx.get('asset', ''),
            'amount': abs(float(tx.get('amount', 0))),
            'price_usd': tx.get('price_usd'),
            'total_usd': tx.get('total_usd') or tx.get('value_usd'),
            'fee': float(tx.get('fee', 0)),
            'fee_asset': tx.get('fee_asset', 'USD'),
            'timestamp': dt,
            'date': dt.strftime('%Y-%m-%d'),
            'raw': tx
        }
    
    def merge_transactions(
        self,
        wallet_transactions: List[Dict],
        exchange_transactions: List[Dict],
        symbol: str,
        asset_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Merge and sort transactions from all sources
        
        Args:
            wallet_transactions: On-chain transactions from wallet analysis
            exchange_transactions: Imported exchange transactions
            symbol: Symbol for wallet transactions (ETH, BTC, etc.)
            asset_filter: Optional filter to include only specific asset
        
        Returns:
            Unified list sorted by timestamp (oldest first for FIFO)
        """
        unified = []
        
        # Normalize wallet transactions
        for tx in wallet_transactions:
            normalized = self.normalize_wallet_transaction(tx, symbol)
            if asset_filter and normalized['asset'].upper() != asset_filter.upper():
                continue
            unified.append(normalized)
        
        # Normalize exchange transactions
        for tx in exchange_transactions:
            normalized = self.normalize_exchange_transaction(tx)
            if asset_filter and normalized['asset'].upper() != asset_filter.upper():
                continue
            unified.append(normalized)
        
        # Sort by timestamp (oldest first for FIFO)
        unified.sort(key=lambda x: x['timestamp'])
        
        return unified
    
    def calculate_unified_tax_data(
        self,
        wallet_transactions: List[Dict],
        exchange_transactions: List[Dict],
        symbol: str,
        current_price: float,
        current_balance: float = 0,
        asset_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive tax data from all transaction sources
        
        Args:
            wallet_transactions: On-chain transactions
            exchange_transactions: Exchange CSV transactions
            symbol: Asset symbol
            current_price: Current USD price
            current_balance: Current on-chain balance (optional)
            asset_filter: Filter for specific asset
        
        Returns:
            Comprehensive tax data with realized/unrealized gains
        """
        try:
            # Merge all transactions
            all_transactions = self.merge_transactions(
                wallet_transactions,
                exchange_transactions,
                symbol,
                asset_filter
            )
            
            if not all_transactions:
                return self._empty_tax_data()
            
            # Separate buys and sells
            buys = []
            sells = []
            
            for tx in all_transactions:
                tx_type = tx['tx_type'].lower()
                
                # Enrich with price data if missing
                if not tx['price_usd'] and tx['amount'] > 0:
                    # Try to get historical price or use current
                    tx['price_usd'] = current_price
                    tx['total_usd'] = tx['amount'] * current_price
                
                if tx_type in ['buy', 'receive', 'received', 'deposit', 'reward', 'staking', 'airdrop']:
                    buys.append(tx)
                elif tx_type in ['sell', 'send', 'sent', 'withdrawal', 'trade']:
                    # For trades, check if it's a sell (disposing of asset)
                    sells.append(tx)
            
            # Calculate realized gains using FIFO
            realized_gains = self._calculate_fifo_gains(buys, sells)
            
            # Calculate unrealized gains from remaining lots
            remaining_lots = self._get_remaining_lots(buys, sells)
            unrealized_gains = self._calculate_unrealized(remaining_lots, current_price)
            
            # Calculate totals
            total_realized = sum(g['gain_loss'] for g in realized_gains)
            short_term = sum(g['gain_loss'] for g in realized_gains if g['holding_period'] == 'short-term')
            long_term = sum(g['gain_loss'] for g in realized_gains if g['holding_period'] == 'long-term')
            
            return {
                'method': self.method,
                'sources': {
                    'wallet_count': len([t for t in all_transactions if t['source'] == 'wallet']),
                    'exchange_count': len([t for t in all_transactions if t['source'].startswith('exchange:')])
                },
                'realized_gains': realized_gains,
                'unrealized_gains': unrealized_gains,
                'remaining_lots': remaining_lots,
                'summary': {
                    'total_realized_gain': total_realized,
                    'total_unrealized_gain': unrealized_gains.get('total_gain', 0),
                    'total_gain': total_realized + unrealized_gains.get('total_gain', 0),
                    'short_term_gains': short_term,
                    'long_term_gains': long_term,
                    'total_transactions': len(all_transactions),
                    'buy_count': len(buys),
                    'sell_count': len(sells)
                },
                'all_transactions': all_transactions
            }
            
        except Exception as e:
            logger.error(f"Error calculating unified tax data: {str(e)}")
            return self._empty_tax_data()
    
    def _calculate_fifo_gains(self, buys: List[Dict], sells: List[Dict]) -> List[Dict]:
        """Calculate realized gains using FIFO method"""
        realized = []
        
        # Create a queue of buy lots
        buy_queue = []
        for buy in buys:
            buy_queue.append({
                'tx_id': buy['tx_id'],
                'source': buy['source'],
                'date': buy['date'],
                'timestamp': buy['timestamp'],
                'amount': buy['amount'],
                'remaining': buy['amount'],
                'price_usd': buy['price_usd'] or 0,
                'asset': buy['asset']
            })
        
        # Process each sell
        for sell in sells:
            sell_amount = sell['amount']
            sell_price = sell['price_usd'] or 0
            sell_date = sell['date']
            sell_timestamp = sell['timestamp']
            remaining_to_sell = sell_amount
            
            while remaining_to_sell > 0 and buy_queue:
                lot = buy_queue[0]
                
                if lot['remaining'] <= 0:
                    buy_queue.pop(0)
                    continue
                
                # Match amount
                matched = min(lot['remaining'], remaining_to_sell)
                
                # Calculate gain/loss
                proceeds = matched * sell_price
                cost_basis = matched * lot['price_usd']
                gain_loss = proceeds - cost_basis
                
                # Determine holding period
                holding_period = self._get_holding_period(lot['timestamp'], sell_timestamp)
                
                realized.append({
                    'sell_id': sell['tx_id'],
                    'buy_id': lot['tx_id'],
                    'sell_source': sell['source'],
                    'buy_source': lot['source'],
                    'asset': sell['asset'],
                    'amount': matched,
                    'buy_price': lot['price_usd'],
                    'sell_price': sell_price,
                    'cost_basis': cost_basis,
                    'proceeds': proceeds,
                    'gain_loss': gain_loss,
                    'buy_date': lot['date'],
                    'sell_date': sell_date,
                    'holding_period': holding_period
                })
                
                # Update remaining
                lot['remaining'] -= matched
                remaining_to_sell -= matched
                
                if lot['remaining'] <= 0:
                    buy_queue.pop(0)
        
        return realized
    
    def _get_remaining_lots(self, buys: List[Dict], sells: List[Dict]) -> List[Dict]:
        """Get remaining unsold lots after FIFO matching"""
        # Rebuild buy queue
        buy_queue = []
        for buy in buys:
            buy_queue.append({
                'tx_id': buy['tx_id'],
                'source': buy['source'],
                'date': buy['date'],
                'timestamp': buy['timestamp'],
                'amount': buy['amount'],
                'remaining': buy['amount'],
                'price_usd': buy['price_usd'] or 0,
                'asset': buy['asset']
            })
        
        # Simulate sells
        for sell in sells:
            remaining_to_sell = sell['amount']
            
            while remaining_to_sell > 0 and buy_queue:
                lot = buy_queue[0]
                
                if lot['remaining'] <= 0:
                    buy_queue.pop(0)
                    continue
                
                matched = min(lot['remaining'], remaining_to_sell)
                lot['remaining'] -= matched
                remaining_to_sell -= matched
                
                if lot['remaining'] <= 0:
                    buy_queue.pop(0)
        
        # Return lots with remaining balance
        return [
            {
                'tx_id': lot['tx_id'],
                'source': lot['source'],
                'date': lot['date'],
                'amount': lot['remaining'],
                'price_usd': lot['price_usd'],
                'cost_basis': lot['remaining'] * lot['price_usd'],
                'asset': lot['asset']
            }
            for lot in buy_queue if lot['remaining'] > 0
        ]
    
    def _calculate_unrealized(self, remaining_lots: List[Dict], current_price: float) -> Dict:
        """Calculate unrealized gains from remaining lots"""
        lots_with_gains = []
        total_cost = 0
        total_value = 0
        
        for lot in remaining_lots:
            cost = lot['cost_basis']
            value = lot['amount'] * current_price
            gain = value - cost
            
            lots_with_gains.append({
                **lot,
                'current_price': current_price,
                'current_value': value,
                'unrealized_gain': gain,
                'gain_percentage': (gain / cost * 100) if cost > 0 else 0
            })
            
            total_cost += cost
            total_value += value
        
        return {
            'lots': lots_with_gains,
            'total_cost_basis': total_cost,
            'total_current_value': total_value,
            'total_gain': total_value - total_cost,
            'total_gain_percentage': ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
        }
    
    def _get_holding_period(self, buy_time: datetime, sell_time: datetime) -> str:
        """Determine if holding period is short-term or long-term"""
        try:
            if isinstance(buy_time, str):
                buy_time = datetime.fromisoformat(buy_time.replace('Z', '+00:00'))
            if isinstance(sell_time, str):
                sell_time = datetime.fromisoformat(sell_time.replace('Z', '+00:00'))
            
            delta = sell_time - buy_time
            
            # Long-term = held more than 1 year (365 days)
            if delta.days > 365:
                return 'long-term'
            return 'short-term'
        except:
            return 'unknown'
    
    def _empty_tax_data(self) -> Dict:
        """Return empty tax data structure"""
        return {
            'method': self.method,
            'sources': {'wallet_count': 0, 'exchange_count': 0},
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
            },
            'all_transactions': []
        }
    
    def get_assets_summary(
        self,
        wallet_transactions: List[Dict],
        exchange_transactions: List[Dict],
        symbol: str
    ) -> List[Dict]:
        """
        Get summary of all assets across wallet and exchanges
        
        Returns list of assets with transaction counts and totals
        """
        assets = {}
        
        # Process wallet transactions
        for tx in wallet_transactions:
            asset = symbol
            if asset not in assets:
                assets[asset] = {'asset': asset, 'wallet_txs': 0, 'exchange_txs': 0, 'total_bought': 0, 'total_sold': 0}
            assets[asset]['wallet_txs'] += 1
            
            amount = float(tx.get('value', 0))
            if tx.get('type') == 'received':
                assets[asset]['total_bought'] += amount
            elif tx.get('type') == 'sent':
                assets[asset]['total_sold'] += amount
        
        # Process exchange transactions
        for tx in exchange_transactions:
            asset = tx.get('asset', 'UNKNOWN')
            if asset not in assets:
                assets[asset] = {'asset': asset, 'wallet_txs': 0, 'exchange_txs': 0, 'total_bought': 0, 'total_sold': 0}
            assets[asset]['exchange_txs'] += 1
            
            amount = float(tx.get('amount', 0))
            tx_type = tx.get('tx_type', '').lower()
            if tx_type in ['buy', 'receive', 'deposit']:
                assets[asset]['total_bought'] += amount
            elif tx_type in ['sell', 'send', 'withdrawal']:
                assets[asset]['total_sold'] += amount
        
        return list(assets.values())


# Singleton instance
unified_tax_service = UnifiedTaxService()
