"""
Exchange-Only Tax Service

Calculates cost basis and capital gains purely from exchange CSV imports.
No wallet analysis required.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from price_service import price_service

logger = logging.getLogger(__name__)


class ExchangeTaxService:
    """
    Tax service for exchange-only calculations.
    Works entirely from imported CSV data.
    """
    
    # Stablecoins pegged to USD - these are essentially USD equivalents
    STABLECOINS = {'USDC', 'USDT', 'BUSD', 'DAI', 'GUSD', 'PAX', 'TUSD', 'USDP', 'UST', 'FRAX'}
    
    def __init__(self):
        self.method = "FIFO"
    
    def _is_stablecoin(self, asset: str) -> bool:
        """Check if an asset is a stablecoin"""
        return asset.upper() in self.STABLECOINS
    
    def calculate_from_transactions(
        self,
        transactions: List[Dict],
        asset_filter: Optional[str] = None,
        tax_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate tax data from exchange transactions only.
        
        Args:
            transactions: List of exchange transactions from DB
            asset_filter: Optional filter for specific asset
            tax_year: Optional filter for specific tax year
        
        Returns:
            Complete tax data with cost basis, gains, etc.
        """
        if not transactions:
            return self._empty_result()
        
        # Normalize and filter transactions
        normalized = []
        excluded_stablecoin_count = 0
        
        for tx in transactions:
            norm = self._normalize_transaction(tx)
            
            # Skip pure stablecoin <-> USD transactions (not taxable)
            # e.g., buying USDC with USD, selling USDC for USD
            if self._is_stablecoin(norm['asset']):
                excluded_stablecoin_count += 1
                continue
            
            # Apply asset filter
            if asset_filter and norm['asset'].upper() != asset_filter.upper():
                continue
            
            normalized.append(norm)
        
        if not normalized:
            return self._empty_result()
        
        logger.info(f"Processing {len(normalized)} crypto transactions (excluded {excluded_stablecoin_count} stablecoin transactions)")
        
        # Sort by timestamp (oldest first for FIFO)
        normalized.sort(key=lambda x: x['timestamp'])
        
        # Separate by asset for per-asset calculations
        assets = {}
        for tx in normalized:
            asset = tx['asset']
            if asset not in assets:
                assets[asset] = {'buys': [], 'sells': []}
            
            tx_type = tx['tx_type'].lower()
            # CRITICAL: Only actual sales should trigger realized gains
            # Buys, deposits, rewards = acquisition (add to cost basis)
            # Sells, trades = disposal (triggers capital gains)
            # Sends, withdrawals = transfers (NOT taxable - moves between wallets)
            if tx_type in ['buy', 'receive', 'deposit', 'reward', 'staking', 'airdrop']:
                assets[asset]['buys'].append(tx)
            elif tx_type in ['sell', 'trade']:
                # Only actual sales and trades are taxable events
                assets[asset]['sells'].append(tx)
            # 'send' and 'withdrawal' are transfers - NOT taxable dispositions
            # They should not create realized gains
            elif tx_type in ['send', 'withdrawal']:
                # Log for debugging but don't treat as sale
                logger.debug(f"Skipping transfer (not taxable): {tx_type} {tx['amount']} {asset}")
        
        # Calculate gains for each asset
        all_realized = []
        all_remaining = []
        
        for asset, data in assets.items():
            realized = self._calculate_fifo_gains(data['buys'], data['sells'], tax_year)
            remaining = self._get_remaining_lots(data['buys'], data['sells'])
            
            all_realized.extend(realized)
            all_remaining.extend(remaining)
        
        # Calculate unrealized gains with current prices
        unrealized = self._calculate_unrealized_gains(all_remaining)
        
        # Calculate summary
        total_realized = sum(g['gain_loss'] for g in all_realized)
        short_term = sum(g['gain_loss'] for g in all_realized if g['holding_period'] == 'short-term')
        long_term = sum(g['gain_loss'] for g in all_realized if g['holding_period'] == 'long-term')
        
        # Get unique exchanges
        exchanges = list(set(tx.get('exchange', 'unknown') for tx in transactions))
        
        # Get asset summary
        asset_summary = self._get_asset_summary(normalized)
        
        return {
            'method': self.method,
            'exchanges': exchanges,
            'total_transactions': len(normalized),
            'realized_gains': all_realized,
            'unrealized': unrealized,
            'remaining_lots': all_remaining,
            'asset_summary': asset_summary,
            'summary': {
                'total_realized_gain': total_realized,
                'short_term_gains': short_term,
                'long_term_gains': long_term,
                'total_unrealized_gain': unrealized.get('total_gain', 0),
                'total_cost_basis': unrealized.get('total_cost_basis', 0),
                'total_current_value': unrealized.get('total_current_value', 0),
                'dispositions_count': len(all_realized),
                'open_positions': len(all_remaining)
            },
            'tax_year': tax_year
        }
    
    def _normalize_transaction(self, tx: Dict) -> Dict:
        """Normalize exchange transaction to standard format"""
        # Check for acquisition date override (for transfers from external wallets)
        acquisition_date_override = tx.get('acquisition_date_override')
        cost_basis_override = tx.get('cost_basis_override')
        is_transfer = tx.get('is_transfer', False)
        
        timestamp_str = tx.get('timestamp', '')
        try:
            if isinstance(timestamp_str, str):
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                dt = datetime.now(timezone.utc)
        except:
            dt = datetime.now(timezone.utc)
        
        # Use acquisition date override if available (for transfers)
        acquisition_date = dt
        if acquisition_date_override:
            try:
                if isinstance(acquisition_date_override, str):
                    acquisition_date = datetime.fromisoformat(acquisition_date_override.replace('Z', '+00:00'))
                else:
                    acquisition_date = acquisition_date_override
            except:
                pass
        
        amount = abs(float(tx.get('amount', 0)))
        price_usd = tx.get('price_usd')
        total_usd = tx.get('total_usd') or tx.get('value_usd')
        
        # Use cost basis override if available
        if cost_basis_override is not None:
            total_usd = cost_basis_override
            if amount > 0:
                price_usd = cost_basis_override / amount
        
        # Calculate price if we have total but not price
        if not price_usd and total_usd and amount > 0:
            price_usd = abs(float(total_usd)) / amount
        
        return {
            'tx_id': tx.get('tx_id', ''),
            'exchange': tx.get('exchange', 'unknown'),
            'tx_type': tx.get('tx_type', 'unknown'),
            'asset': tx.get('asset', 'UNKNOWN'),
            'amount': amount,
            'price_usd': float(price_usd) if price_usd else 0,
            'total_usd': float(total_usd) if total_usd else 0,
            'fee': float(tx.get('fee', 0)),
            'fee_asset': tx.get('fee_asset', 'USD'),
            'timestamp': dt,  # Original transaction timestamp
            'acquisition_date': acquisition_date,  # Date for holding period calculation
            'date': acquisition_date.strftime('%Y-%m-%d'),  # Use acquisition date for tax purposes
            'is_transfer': is_transfer,
            'manually_adjusted': tx.get('manually_adjusted', False)
        }
    
    def _calculate_fifo_gains(
        self, 
        buys: List[Dict], 
        sells: List[Dict],
        tax_year: Optional[int] = None
    ) -> List[Dict]:
        """Calculate realized gains using FIFO"""
        realized = []
        
        # Create buy queue
        buy_queue = []
        for buy in buys:
            buy_queue.append({
                'tx_id': buy['tx_id'],
                'exchange': buy['exchange'],
                'date': buy['date'],
                'timestamp': buy['timestamp'],
                'acquisition_date': buy.get('acquisition_date', buy['timestamp']),  # Use override if available
                'amount': buy['amount'],
                'remaining': buy['amount'],
                'price_usd': buy['price_usd'],
                'asset': buy['asset'],
                'is_transfer': buy.get('is_transfer', False),
                'manually_adjusted': buy.get('manually_adjusted', False)
            })
        
        # Process sells
        for sell in sells:
            # Filter by tax year if specified
            sell_year = sell['timestamp'].year
            if tax_year and sell_year != tax_year:
                continue
            
            sell_amount = sell['amount']
            sell_price = sell['price_usd']
            remaining_to_sell = sell_amount
            
            while remaining_to_sell > 0 and buy_queue:
                lot = buy_queue[0]
                
                if lot['remaining'] <= 0:
                    buy_queue.pop(0)
                    continue
                
                matched = min(lot['remaining'], remaining_to_sell)
                
                proceeds = matched * sell_price
                cost_basis = matched * lot['price_usd']
                gain_loss = proceeds - cost_basis
                
                # Use acquisition_date for holding period calculation (handles transfers correctly)
                buy_date_for_holding = lot.get('acquisition_date') or lot['timestamp']
                holding_period = self._get_holding_period(buy_date_for_holding, sell['timestamp'])
                
                realized.append({
                    'asset': sell['asset'],
                    'amount': matched,
                    'buy_date': lot['date'],
                    'buy_exchange': lot['exchange'],
                    'sell_date': sell['date'],
                    'sell_exchange': sell['exchange'],
                    'buy_price': lot['price_usd'],
                    'sell_price': sell_price,
                    'cost_basis': cost_basis,
                    'proceeds': proceeds,
                    'gain_loss': gain_loss,
                    'holding_period': holding_period,
                    'is_transfer': lot.get('is_transfer', False),
                    'manually_adjusted': lot.get('manually_adjusted', False),
                    'acquisition_date': buy_date_for_holding.strftime('%Y-%m-%d') if hasattr(buy_date_for_holding, 'strftime') else str(buy_date_for_holding)
                })
                
                lot['remaining'] -= matched
                remaining_to_sell -= matched
                
                if lot['remaining'] <= 0:
                    buy_queue.pop(0)
        
        return realized
    
    def _get_remaining_lots(self, buys: List[Dict], sells: List[Dict]) -> List[Dict]:
        """Get remaining unsold lots"""
        # Rebuild buy queue
        buy_queue = []
        for buy in buys:
            buy_queue.append({
                'tx_id': buy['tx_id'],
                'exchange': buy['exchange'],
                'date': buy['date'],
                'timestamp': buy['timestamp'],
                'amount': buy['amount'],
                'remaining': buy['amount'],
                'price_usd': buy['price_usd'],
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
                'asset': lot['asset'],
                'exchange': lot['exchange'],
                'date': lot['date'],
                'amount': lot['remaining'],
                'price_usd': lot['price_usd'],
                'cost_basis': lot['remaining'] * lot['price_usd']
            }
            for lot in buy_queue if lot['remaining'] > 0
        ]
    
    def _calculate_unrealized_gains(self, remaining_lots: List[Dict]) -> Dict:
        """Calculate unrealized gains with current prices"""
        lots_with_gains = []
        total_cost = 0
        total_value = 0
        
        # Get current prices for each asset
        price_cache = {}
        
        for lot in remaining_lots:
            asset = lot['asset']
            
            # Get current price (with caching)
            if asset not in price_cache:
                try:
                    price_cache[asset] = price_service.get_current_price(asset) or 0
                except:
                    price_cache[asset] = 0
            
            current_price = price_cache[asset]
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
        """Determine holding period"""
        try:
            delta = sell_time - buy_time
            return 'long-term' if delta.days > 365 else 'short-term'
        except:
            return 'unknown'
    
    def _get_asset_summary(self, transactions: List[Dict]) -> List[Dict]:
        """Get summary per asset"""
        assets = {}
        
        for tx in transactions:
            asset = tx['asset']
            if asset not in assets:
                assets[asset] = {
                    'asset': asset,
                    'buy_count': 0,
                    'sell_count': 0,
                    'total_bought': 0,
                    'total_sold': 0,
                    'total_buy_value': 0,
                    'total_sell_value': 0,
                    'exchanges': set()
                }
            
            assets[asset]['exchanges'].add(tx['exchange'])
            tx_type = tx['tx_type'].lower()
            
            if tx_type in ['buy', 'receive', 'deposit', 'reward']:
                assets[asset]['buy_count'] += 1
                assets[asset]['total_bought'] += tx['amount']
                assets[asset]['total_buy_value'] += tx['total_usd'] or (tx['amount'] * tx['price_usd'])
            elif tx_type in ['sell', 'send', 'withdrawal']:
                assets[asset]['sell_count'] += 1
                assets[asset]['total_sold'] += tx['amount']
                assets[asset]['total_sell_value'] += tx['total_usd'] or (tx['amount'] * tx['price_usd'])
        
        # Convert sets to lists
        result = []
        for asset, data in assets.items():
            data['exchanges'] = list(data['exchanges'])
            data['net_position'] = data['total_bought'] - data['total_sold']
            result.append(data)
        
        return sorted(result, key=lambda x: x['total_buy_value'], reverse=True)
    
    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            'method': self.method,
            'exchanges': [],
            'total_transactions': 0,
            'realized_gains': [],
            'unrealized': {
                'lots': [],
                'total_cost_basis': 0,
                'total_current_value': 0,
                'total_gain': 0,
                'total_gain_percentage': 0
            },
            'remaining_lots': [],
            'asset_summary': [],
            'summary': {
                'total_realized_gain': 0,
                'short_term_gains': 0,
                'long_term_gains': 0,
                'total_unrealized_gain': 0,
                'total_cost_basis': 0,
                'total_current_value': 0,
                'dispositions_count': 0,
                'open_positions': 0
            },
            'tax_year': None
        }
    
    def generate_form_8949_data(
        self,
        realized_gains: List[Dict],
        holding_period_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Generate Form 8949 compatible data
        
        Args:
            realized_gains: List of realized gain entries
            holding_period_filter: 'short-term', 'long-term', or None for all
        
        Returns:
            List of Form 8949 line items
        """
        lines = []
        
        for gain in realized_gains:
            if holding_period_filter and gain['holding_period'] != holding_period_filter:
                continue
            
            lines.append({
                'description': f"{gain['amount']:.8f} {gain['asset']}",
                'date_acquired': gain['buy_date'],
                'date_sold': gain['sell_date'],
                'proceeds': gain['proceeds'],
                'cost_basis': gain['cost_basis'],
                'adjustment_code': '',
                'adjustment_amount': 0,
                'gain_or_loss': gain['gain_loss'],
                'holding_period': gain['holding_period'],
                'exchange': gain.get('sell_exchange', 'Unknown')
            })
        
        return lines


# Singleton
exchange_tax_service = ExchangeTaxService()
