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
            'from_address': tx.get('from', ''),
            'to_address': tx.get('to', ''),
            'raw': tx
        }
    
    def detect_transfers_between_sources(
        self,
        wallet_transactions: List[Dict],
        exchange_transactions: List[Dict],
        tolerance_hours: int = 24
    ) -> List[Dict]:
        """
        Detect transfers from wallet to exchange.
        
        When a wallet "send" matches an exchange "receive" by:
        - Same asset
        - Similar amount (within 1%)
        - Similar time (within tolerance_hours)
        
        We can link them and use the wallet's original acquisition date
        for the exchange transaction.
        
        Returns list of matched transfer pairs.
        """
        matches = []
        
        # Get wallet sends
        wallet_sends = [tx for tx in wallet_transactions if tx.get('tx_type') == 'sell']
        
        # Get exchange receives
        exchange_receives = [tx for tx in exchange_transactions 
                           if tx.get('tx_type') in ['receive', 'deposit', 'buy'] 
                           and tx.get('source', '').startswith('exchange:')]
        
        for send in wallet_sends:
            send_amount = send.get('amount', 0)
            send_asset = send.get('asset', '').upper()
            send_time = send.get('timestamp')
            
            for receive in exchange_receives:
                receive_amount = receive.get('amount', 0)
                receive_asset = receive.get('asset', '').upper()
                receive_time = receive.get('timestamp')
                
                # Check asset match
                if send_asset != receive_asset:
                    continue
                
                # Check amount match (within 1% to account for fees)
                if send_amount > 0 and receive_amount > 0:
                    amount_diff = abs(send_amount - receive_amount) / send_amount
                    if amount_diff > 0.01:  # More than 1% difference
                        continue
                
                # Check time match
                if send_time and receive_time:
                    time_diff = abs((receive_time - send_time).total_seconds())
                    if time_diff > tolerance_hours * 3600:
                        continue
                    
                    # Found a match!
                    matches.append({
                        'wallet_send': send,
                        'exchange_receive': receive,
                        'asset': send_asset,
                        'amount': send_amount,
                        'wallet_send_time': send_time.isoformat() if hasattr(send_time, 'isoformat') else str(send_time),
                        'exchange_receive_time': receive_time.isoformat() if hasattr(receive_time, 'isoformat') else str(receive_time),
                        'time_diff_hours': time_diff / 3600,
                        'from_wallet_address': send.get('from_address', ''),
                        'to_exchange_address': send.get('to_address', ''),
                        'is_transfer': True
                    })
                    break  # One match per send
        
        return matches
    
    def normalize_exchange_transaction(self, tx: Dict) -> Optional[Dict]:
        """Convert exchange CSV transaction to unified format with STRICT validation.
        Returns None for invalid/suspicious transactions that should be skipped."""
        
        # STRICT validation thresholds - anything above these is bad data
        MAX_AMOUNT_PER_TX = 1_000_000_000  # 1 billion units max (even BTC doesn't have this much)
        MAX_PRICE_USD = 500_000  # $500k per unit max (even BTC isn't this high)
        MAX_TX_VALUE_USD = 100_000_000_000  # $100B max transaction value
        
        # Parse timestamp
        timestamp_str = tx.get('timestamp', '')
        try:
            if isinstance(timestamp_str, str):
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                dt = datetime.now(timezone.utc)
        except:
            dt = datetime.now(timezone.utc)
        
        # Parse amount
        try:
            amount = abs(float(tx.get('amount', 0)))
        except (ValueError, TypeError):
            amount = 0
        
        # Parse price
        price_usd = tx.get('price_usd')
        try:
            price_usd = float(price_usd) if price_usd else None
        except (ValueError, TypeError):
            price_usd = None
        
        # Parse total
        total_usd = tx.get('total_usd') or tx.get('value_usd')
        try:
            total_usd = float(total_usd) if total_usd else None
        except (ValueError, TypeError):
            total_usd = None
        
        # STRICT VALIDATION - Skip bad transactions entirely
        asset = tx.get('asset', '')
        tx_id = tx.get('tx_id', 'unknown')
        
        # Check for unreasonable amounts
        if amount > MAX_AMOUNT_PER_TX:
            logger.error(f"SKIPPING BAD TX: Amount {amount:,.2f} exceeds max for {asset} (tx: {tx_id})")
            return None
        
        # Check for unreasonable prices
        if price_usd and price_usd > MAX_PRICE_USD:
            logger.error(f"SKIPPING BAD TX: Price ${price_usd:,.2f} exceeds max for {asset} (tx: {tx_id})")
            return None
        
        # Calculate total if not provided
        if not total_usd and price_usd and amount:
            total_usd = amount * price_usd
        
        # Check for unreasonable total value
        if total_usd and abs(total_usd) > MAX_TX_VALUE_USD:
            logger.error(f"SKIPPING BAD TX: Value ${total_usd:,.2f} exceeds max for {asset} (tx: {tx_id})")
            return None
        
        # Skip zero-amount transactions
        if amount <= 0:
            return None
        
        return {
            'source': f"exchange:{tx.get('exchange', 'unknown')}",
            'tx_id': tx_id,
            'tx_type': tx.get('tx_type', 'unknown'),
            'asset': asset,
            'amount': amount,
            'price_usd': price_usd,
            'total_usd': total_usd,
            'fee': float(tx.get('fee', 0)) if tx.get('fee') else 0,
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
        asset_filter: Optional[str] = None,
        detect_transfers: bool = True
    ) -> tuple:
        """
        Merge and sort transactions from all sources
        
        Args:
            wallet_transactions: On-chain transactions from wallet analysis
            exchange_transactions: Imported exchange transactions
            symbol: Symbol for wallet transactions (ETH, BTC, etc.)
            asset_filter: Optional filter to include only specific asset
            detect_transfers: Whether to detect wallet→exchange transfers
        
        Returns:
            Tuple of (unified_transactions, detected_transfers)
        """
        unified = []
        detected_transfers = []
        
        # First normalize all transactions
        normalized_wallet = []
        for tx in wallet_transactions:
            normalized = self.normalize_wallet_transaction(tx, symbol)
            if asset_filter and normalized['asset'].upper() != asset_filter.upper():
                continue
            normalized_wallet.append(normalized)
        
        normalized_exchange = []
        skipped_count = 0
        for tx in exchange_transactions:
            normalized = self.normalize_exchange_transaction(tx)
            if normalized is None:
                skipped_count += 1
                continue
            if asset_filter and normalized['asset'].upper() != asset_filter.upper():
                continue
            normalized_exchange.append(normalized)
        
        if skipped_count > 0:
            logger.warning(f"Skipped {skipped_count} invalid exchange transactions due to validation failures")
        
        # Detect transfers between wallet and exchange
        if detect_transfers and normalized_wallet and normalized_exchange:
            detected_transfers = self.detect_transfers_between_sources(
                normalized_wallet, normalized_exchange
            )
            
            # Mark matched exchange receives as transfers and set original acquisition date
            transfer_exchange_ids = set()
            wallet_acquisition_dates = {}
            
            for match in detected_transfers:
                exchange_tx_id = match['exchange_receive'].get('tx_id')
                wallet_send_time = match['wallet_send'].get('timestamp')
                from_address = match.get('from_wallet_address', '')
                
                transfer_exchange_ids.add(exchange_tx_id)
                
                # Find the original acquisition date from wallet history
                # (when the wallet first received this asset)
                wallet_acquisition_dates[exchange_tx_id] = {
                    'is_transfer': True,
                    'transfer_from_wallet': from_address,
                    'wallet_send_time': wallet_send_time
                }
            
            # Update exchange transactions with transfer info
            for tx in normalized_exchange:
                tx_id = tx.get('tx_id')
                if tx_id in wallet_acquisition_dates:
                    tx['is_transfer'] = True
                    tx['transfer_from_wallet'] = wallet_acquisition_dates[tx_id].get('transfer_from_wallet')
                    tx['linked_wallet_send_time'] = wallet_acquisition_dates[tx_id].get('wallet_send_time')
        
        # Combine all transactions
        unified.extend(normalized_wallet)
        unified.extend(normalized_exchange)
        
        # Sort by timestamp (oldest first for FIFO)
        unified.sort(key=lambda x: x['timestamp'])
        
        return unified, detected_transfers
    
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
            # Merge all transactions and detect transfers
            all_transactions, detected_transfers = self.merge_transactions(
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
                    # Log the missing price for debugging
                    logger.warning(f"Missing price for tx {tx.get('tx_id', 'unknown')}: "
                                 f"{tx['amount']} {tx['asset']} on {tx.get('date', 'unknown')}, "
                                 f"using current price ${current_price}")
                    tx['price_usd'] = current_price
                    tx['total_usd'] = tx['amount'] * current_price
                    tx['price_source'] = 'fallback_current'
                else:
                    tx['price_source'] = 'original'
                
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
            
            # Count transfers detected
            transfers_count = len(detected_transfers)
            transfer_assets = list(set(t.get('asset', '') for t in detected_transfers))
            
            return {
                'method': self.method,
                'sources': {
                    'wallet_count': len([t for t in all_transactions if t['source'] == 'wallet']),
                    'exchange_count': len([t for t in all_transactions if t['source'].startswith('exchange:')])
                },
                'detected_transfers': {
                    'count': transfers_count,
                    'assets': transfer_assets,
                    'details': detected_transfers[:20]  # Limit to 20 for response size
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
                    'sell_count': len(sells),
                    'transfers_detected': transfers_count
                },
                'all_transactions': all_transactions
            }
            
        except Exception as e:
            logger.error(f"Error calculating unified tax data: {str(e)}")
            return self._empty_tax_data()
    
    def _calculate_fifo_gains(self, buys: List[Dict], sells: List[Dict]) -> List[Dict]:
        """Calculate realized gains using FIFO method with STRICT validation"""
        realized = []
        
        # STRICT validation thresholds - skip transactions exceeding these
        MAX_AMOUNT = 1_000_000_000  # 1 billion units
        MAX_PRICE = 500_000  # $500k per unit
        MAX_GAIN_PER_TX = 10_000_000_000  # $10B per single transaction match
        
        # Create a queue of buy lots - FILTER OUT BAD DATA
        buy_queue = []
        for buy in buys:
            amount = buy['amount']
            price = buy['price_usd'] or 0
            
            # SKIP bad transactions
            if amount > MAX_AMOUNT:
                logger.error(f"FIFO: Skipping buy with bad amount {amount:,.0f} (tx: {buy.get('tx_id', 'unknown')})")
                continue
            if price > MAX_PRICE:
                logger.error(f"FIFO: Skipping buy with bad price ${price:,.0f} (tx: {buy.get('tx_id', 'unknown')})")
                continue
            if amount <= 0:
                continue
            
            buy_queue.append({
                'tx_id': buy['tx_id'],
                'source': buy['source'],
                'date': buy['date'],
                'timestamp': buy['timestamp'],
                'amount': amount,
                'remaining': amount,
                'price_usd': price,
                'asset': buy['asset']
            })
        
        # Process each sell
        for sell in sells:
            sell_amount = sell['amount']
            sell_price = sell['price_usd'] or 0
            sell_date = sell['date']
            sell_timestamp = sell['timestamp']
            
            # SKIP bad sell transactions
            if sell_amount > MAX_AMOUNT:
                logger.error(f"FIFO: Skipping sell with bad amount {sell_amount:,.0f} (tx: {sell.get('tx_id', 'unknown')})")
                continue
            if sell_price > MAX_PRICE:
                logger.error(f"FIFO: Skipping sell with bad price ${sell_price:,.0f} (tx: {sell.get('tx_id', 'unknown')})")
                continue
            if sell_amount <= 0:
                continue
            
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
                
                # SKIP unreasonable gain/loss (indicates bad data somewhere)
                if abs(gain_loss) > MAX_GAIN_PER_TX:
                    logger.error(f"FIFO: Skipping match with unreasonable gain ${gain_loss:,.0f}")
                    logger.error(f"  Matched: {matched}, Buy price: ${lot['price_usd']}, Sell price: ${sell_price}")
                    lot['remaining'] -= matched
                    remaining_to_sell -= matched
                    if lot['remaining'] <= 0:
                        buy_queue.pop(0)
                    continue
                
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
        
        # Final sanity check on total
        total_realized = sum(g['gain_loss'] for g in realized)
        if abs(total_realized) > 100_000_000_000:  # $100B total is definitely wrong
            logger.error(f"FIFO: Total realized gains ${total_realized:,.0f} is unreasonable - data issue likely")
        
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
