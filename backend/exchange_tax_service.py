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
        tax_year: Optional[int] = None,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate tax data from exchange transactions only.
        
        Args:
            transactions: List of exchange transactions from DB
            asset_filter: Optional filter for specific asset
            tax_year: Optional filter for specific tax year
            as_of_date: Optional date string (YYYY-MM-DD) for unrealized gains valuation.
                        If tax_year is provided and as_of_date is not, defaults to Dec 31 of tax_year.
        
        Returns:
            Complete tax data with cost basis, gains, etc.
        """
        if not transactions:
            return self._empty_result()
        
        # If tax_year provided but no as_of_date, default to end of tax year
        if tax_year and not as_of_date:
            as_of_date = f"{tax_year}-12-31"
        
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
        
        # Match transfers before processing
        from transfer_matcher_service import transfer_matcher_service
        match_result = transfer_matcher_service.match_transfers(normalized)
        normalized = match_result['transactions']
        logger.info(f"Transfer matching: {match_result['matched_count']} pairs matched")
        
        # Sort by timestamp (oldest first for FIFO)
        normalized.sort(key=lambda x: x['timestamp'])
        
        # Separate by asset for per-asset calculations
        assets = {}
        income_events = []  # Track income separately (staking, rewards, etc.)
        
        for tx in normalized:
            asset = tx['asset']
            if asset not in assets:
                assets[asset] = {'buys': [], 'sells': [], 'income': []}
            
            tx_type = tx['tx_type'].lower()
            
            # CRITICAL: Proper categorization for cost basis
            # - Actual BUYS: buy, trade (crypto bought with fiat/crypto)
            # - Income: reward, staking, airdrop, mining (new cost basis = fair market value)
            # - Transfers IN: receive, deposit (should NOT add new cost basis)
            # - Transfers OUT: send, withdrawal (NOT taxable)
            # - Disposals: sell, trade (triggers capital gains)
            
            if tx_type in ['buy', 'trade']:
                # Actual purchases - add to cost basis
                assets[asset]['buys'].append(tx)
            elif tx_type in ['reward', 'staking', 'airdrop', 'mining', 'interest', 'income']:
                # Income events - these DO create new cost basis (FMV at receipt)
                # AND they count as taxable income in the year received
                assets[asset]['buys'].append(tx)
                assets[asset]['income'].append(tx)  # Track for income reporting
                income_events.append(tx)
            elif tx_type in ['receive', 'deposit', 'transfer']:
                # Transfers IN - these are typically transfers between your own wallets
                # They should NOT add new cost basis (that would double-count)
                # The original buy cost basis should flow through from FIFO
                # Only add if explicitly marked as a new acquisition (not a transfer)
                if tx.get('is_new_acquisition', False):
                    # Explicitly marked as new acquisition (not transfer)
                    assets[asset]['buys'].append(tx)
                else:
                    # Default: skip receives - they're likely transfers
                    # Cost basis comes from the original buy on source exchange
                    logger.debug(f"Skipping receive/deposit (likely transfer): {tx['amount']} {asset}")
            elif tx_type in ['sell']:
                # Sales are taxable events
                assets[asset]['sells'].append(tx)
            elif tx_type in ['send', 'withdrawal']:
                # Transfers OUT - NOT taxable dispositions
                logger.debug(f"Skipping transfer out (not taxable): {tx_type} {tx['amount']} {asset}")
        
        # Calculate gains for each asset
        all_realized = []
        all_remaining = []
        
        for asset, data in assets.items():
            realized = self._calculate_fifo_gains(data['buys'], data['sells'], tax_year)
            remaining = self._get_remaining_lots(data['buys'], data['sells'])
            
            all_realized.extend(realized)
            all_remaining.extend(remaining)
        
        # Calculate unrealized gains using as_of_date for proper tax year valuation
        unrealized = self._calculate_unrealized_gains(all_remaining, as_of_date)
        
        # Calculate summary
        total_realized = sum(g['gain_loss'] for g in all_realized)
        short_term = sum(g['gain_loss'] for g in all_realized if g['holding_period'] == 'short-term')
        long_term = sum(g['gain_loss'] for g in all_realized if g['holding_period'] == 'long-term')
        
        # Calculate income summary (staking, rewards, airdrops, etc.)
        income_summary = self._calculate_income_summary(income_events, tax_year)
        
        # Calculate cost basis breakdown (purchases vs income)
        cost_basis_breakdown = self._calculate_cost_basis_breakdown(assets)
        
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
            'income': income_summary,  # NEW: Income tracking (staking, rewards, etc.)
            'cost_basis_breakdown': cost_basis_breakdown,  # NEW: Breakdown of cost basis sources
            'summary': {
                'total_realized_gain': total_realized,
                'short_term_gains': short_term,
                'long_term_gains': long_term,
                'total_unrealized_gain': unrealized.get('total_gain', 0),
                'total_cost_basis': unrealized.get('total_cost_basis', 0),
                'total_current_value': unrealized.get('total_current_value', 0),
                'dispositions_count': len(all_realized),
                'open_positions': len(all_remaining),
                'total_income': income_summary.get('total_income', 0),  # NEW
                'cost_from_purchases': cost_basis_breakdown.get('purchases', 0),  # NEW
                'cost_from_income': cost_basis_breakdown.get('income', 0)  # NEW
            },
            'tax_year': tax_year,
            'as_of_date': as_of_date or 'current',
            'valuation_note': f"Holdings valued as of {as_of_date or 'current market price'}"
        }
    
    def _normalize_transaction(self, tx: Dict) -> Dict:
        """Normalize exchange transaction to standard format"""
        # Check for acquisition date override (for transfers from external wallets)
        acquisition_date_override = tx.get('acquisition_date_override')
        cost_basis_override = tx.get('cost_basis_override')
        is_transfer = tx.get('is_transfer', False)
        
        timestamp_val = tx.get('timestamp', '')
        try:
            if isinstance(timestamp_val, datetime):
                dt = timestamp_val
            elif isinstance(timestamp_val, str) and timestamp_val:
                dt = datetime.fromisoformat(timestamp_val.replace('Z', '+00:00'))
            else:
                dt = datetime.now(timezone.utc)
        except:
            dt = datetime.now(timezone.utc)
        
        # Ensure timezone awareness
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        # Use acquisition date override if available (for transfers)
        acquisition_date = dt
        if acquisition_date_override:
            try:
                if isinstance(acquisition_date_override, datetime):
                    acquisition_date = acquisition_date_override
                elif isinstance(acquisition_date_override, str):
                    acquisition_date = datetime.fromisoformat(acquisition_date_override.replace('Z', '+00:00'))
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
    
    def _calculate_unrealized_gains(self, remaining_lots: List[Dict], as_of_date: Optional[str] = None) -> Dict:
        """
        Calculate unrealized gains with prices.
        
        Args:
            remaining_lots: List of lots still held
            as_of_date: Optional date string (YYYY-MM-DD) for historical valuation.
                        If None, uses current prices.
                        For tax year calculations, use "2024-12-31" etc.
        """
        lots_with_gains = []
        total_cost = 0
        total_value = 0
        
        # Get prices (current or historical) for each asset
        price_cache = {}
        valuation_date = as_of_date or "current"
        
        for lot in remaining_lots:
            asset = lot['asset']
            
            # Get price (with caching)
            if asset not in price_cache:
                try:
                    if as_of_date:
                        # Convert YYYY-MM-DD to DD-MM-YYYY for price service
                        parts = as_of_date.split('-')
                        if len(parts) == 3:
                            date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
                            price_cache[asset] = price_service.get_historical_price(asset, date_str) or 0
                        else:
                            price_cache[asset] = price_service.get_current_price(asset) or 0
                    else:
                        price_cache[asset] = price_service.get_current_price(asset) or 0
                except:
                    price_cache[asset] = 0
            
            valuation_price = price_cache[asset]
            cost = lot['cost_basis']
            value = lot['amount'] * valuation_price
            gain = value - cost
            
            lots_with_gains.append({
                **lot,
                'current_price': valuation_price,
                'valuation_date': valuation_date,
                'current_value': value,
                'unrealized_gain': gain,
                'gain_percentage': (gain / cost * 100) if cost > 0 else 0
            })
            
            total_cost += cost
            total_value += value
        
        return {
            'lots': lots_with_gains,
            'valuation_date': valuation_date,
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
            'income': {
                'total_income': 0,
                'by_type': {},
                'by_asset': {},
                'events': []
            },
            'cost_basis_breakdown': {
                'purchases': 0,
                'income': 0,
                'total': 0,
                'by_asset': {}
            },
            'summary': {
                'total_realized_gain': 0,
                'short_term_gains': 0,
                'long_term_gains': 0,
                'total_unrealized_gain': 0,
                'total_cost_basis': 0,
                'total_current_value': 0,
                'dispositions_count': 0,
                'open_positions': 0,
                'total_income': 0,
                'cost_from_purchases': 0,
                'cost_from_income': 0
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
    
    def _calculate_income_summary(self, income_events: List[Dict], tax_year: Optional[int] = None) -> Dict:
        """
        Calculate income summary from staking rewards, airdrops, etc.
        
        Per IRS Revenue Ruling 2023-14:
        - Staking rewards are taxable as ordinary income when received
        - Fair Market Value at receipt determines the income amount
        - This becomes the cost basis for future capital gains calculation
        
        Args:
            income_events: List of income transactions (staking, rewards, etc.)
            tax_year: Optional filter for specific tax year
        
        Returns:
            Income summary with breakdown by type and asset
        """
        if not income_events:
            return {
                'total_income': 0,
                'by_type': {},
                'by_asset': {},
                'events': []
            }
        
        by_type = {}  # {staking: $X, reward: $Y, ...}
        by_asset = {}  # {ETH: $X, SOL: $Y, ...}
        filtered_events = []
        
        for event in income_events:
            # Filter by tax year if specified
            if tax_year:
                event_year = event.get('timestamp', datetime.now(timezone.utc))
                if isinstance(event_year, datetime):
                    if event_year.year != tax_year:
                        continue
            
            # Calculate FMV at receipt (this is the taxable income)
            fmv = event.get('total_usd') or (event.get('amount', 0) * (event.get('price_usd') or 0))
            if not fmv or fmv <= 0:
                continue
            
            tx_type = event.get('tx_type', 'income').lower()
            asset = event.get('asset', 'UNKNOWN')
            
            # Aggregate by type
            if tx_type not in by_type:
                by_type[tx_type] = 0
            by_type[tx_type] += fmv
            
            # Aggregate by asset
            if asset not in by_asset:
                by_asset[asset] = {'total_income': 0, 'count': 0}
            by_asset[asset]['total_income'] += fmv
            by_asset[asset]['count'] += 1
            
            # Track individual events (limited for performance)
            if len(filtered_events) < 1000:
                filtered_events.append({
                    'asset': asset,
                    'type': tx_type,
                    'amount': event.get('amount', 0),
                    'fmv': fmv,
                    'price_usd': event.get('price_usd'),
                    'date': event.get('timestamp').isoformat() if isinstance(event.get('timestamp'), datetime) else str(event.get('timestamp')),
                    'exchange': event.get('exchange', 'Unknown')
                })
        
        total_income = sum(by_type.values())
        
        return {
            'total_income': total_income,
            'by_type': by_type,  # e.g., {'staking': 150.25, 'reward': 50.00}
            'by_asset': by_asset,  # e.g., {'ETH': {'total_income': 100, 'count': 50}}
            'events': filtered_events,
            'tax_year': tax_year,
            'note': 'Income is taxable as ordinary income at FMV when received (IRS Rev. Rul. 2023-14)'
        }
    
    def _calculate_cost_basis_breakdown(self, assets: Dict) -> Dict:
        """
        Calculate cost basis breakdown by source (purchases vs income).
        
        This helps distinguish:
        - Cost from actual purchases (money you spent)
        - Cost from income (FMV of staking rewards, etc.)
        
        Args:
            assets: Dict of assets with their buy/sell/income transactions
        
        Returns:
            Cost basis breakdown
        """
        purchases_cost = 0
        income_cost = 0
        by_asset = {}
        
        for asset, data in assets.items():
            asset_purchase_cost = 0
            asset_income_cost = 0
            
            for tx in data.get('buys', []):
                tx_type = tx.get('tx_type', '').lower()
                cost = tx.get('total_usd') or (tx.get('amount', 0) * (tx.get('price_usd') or 0))
                
                if tx_type in ['buy', 'trade']:
                    asset_purchase_cost += cost
                    purchases_cost += cost
                elif tx_type in ['reward', 'staking', 'airdrop', 'mining', 'interest', 'income']:
                    asset_income_cost += cost
                    income_cost += cost
            
            if asset_purchase_cost > 0 or asset_income_cost > 0:
                by_asset[asset] = {
                    'from_purchases': asset_purchase_cost,
                    'from_income': asset_income_cost,
                    'total': asset_purchase_cost + asset_income_cost
                }
        
        return {
            'purchases': purchases_cost,
            'income': income_cost,
            'total': purchases_cost + income_cost,
            'by_asset': by_asset
        }


# Singleton
exchange_tax_service = ExchangeTaxService()
