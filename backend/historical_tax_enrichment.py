"""
Historical Tax Enrichment Service

This service enriches on-chain wallet transactions with historical price data
for accurate cost basis and tax calculations.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from price_service import price_service
import time

logger = logging.getLogger(__name__)


class HistoricalTaxEnrichment:
    """
    Enriches on-chain transactions with historical prices for tax calculations.
    
    Key responsibilities:
    1. Fetch historical prices at the time of each transaction
    2. Calculate cost basis for each acquisition (buy/receive)
    3. Apply FIFO matching for disposals (sell/send)
    4. Validate data to catch anomalies (like -$37B bugs)
    """
    
    # Maximum reasonable values for validation
    MAX_SINGLE_TX_VALUE_USD = 100_000_000_000  # $100B max per transaction
    MAX_SINGLE_PRICE_USD = 1_000_000  # $1M max per coin
    
    def __init__(self):
        self.price_cache = {}
        self.rate_limit_delay = 0.3  # Reduced from 1.5s - CryptoCompare allows higher rates
        self.last_api_call = 0
    
    def _rate_limit(self):
        """Ensure we don't exceed rate limits"""
        elapsed = time.time() - self.last_api_call
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_api_call = time.time()
    
    def _get_historical_price(self, symbol: str, timestamp: int) -> Optional[float]:
        """
        Get historical price for a symbol at a specific Unix timestamp.
        Uses caching to avoid redundant API calls.
        """
        # Convert timestamp to date string (DD-MM-YYYY)
        try:
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            date_str = dt.strftime('%d-%m-%Y')
        except (ValueError, OSError) as e:
            logger.warning(f"Invalid timestamp {timestamp}: {e}")
            return None
        
        cache_key = f"{symbol}_{date_str}"
        
        # Check cache
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]
        
        # Rate limit
        self._rate_limit()
        
        # Fetch historical price
        price = price_service.get_historical_price(symbol, date_str)
        
        if price:
            self.price_cache[cache_key] = price
            logger.debug(f"Historical price for {symbol} on {date_str}: ${price}")
        else:
            # Try to get current price as fallback for recent transactions
            fallback = price_service.get_current_price(symbol)
            if fallback:
                self.price_cache[cache_key] = fallback
                logger.warning(f"Using current price for {symbol} on {date_str}: ${fallback}")
                return fallback
        
        return price
    
    def _validate_transaction(self, tx: Dict) -> tuple:
        """
        Validate a transaction for reasonable values.
        Returns (is_valid, warning_message)
        """
        amount = abs(tx.get('amount', 0))
        price = tx.get('price_usd', 0) or 0
        total = tx.get('total_usd', 0) or (amount * price)
        
        warnings = []
        
        # Check for unreasonable total values
        if abs(total) > self.MAX_SINGLE_TX_VALUE_USD:
            warnings.append(f"Suspiciously large transaction value: ${total:,.2f}")
        
        # Check for unreasonable prices
        if price > self.MAX_SINGLE_PRICE_USD:
            warnings.append(f"Suspiciously high price: ${price:,.2f}")
        
        # Check for zero or negative amounts
        if amount <= 0:
            warnings.append(f"Zero or negative amount: {amount}")
        
        # Check for negative prices
        if price < 0:
            warnings.append(f"Negative price: ${price}")
        
        return len(warnings) == 0, warnings
    
    def enrich_wallet_transactions(
        self,
        transactions: List[Dict],
        symbol: str,
        current_price: float
    ) -> List[Dict]:
        """
        Enrich wallet transactions with historical prices.
        Uses batch price lookup to minimize API calls for large wallets.
        """
        enriched = []
        validation_warnings = []
        
        if not transactions:
            return enriched
        
        # BATCH OPTIMIZATION: Collect all unique (asset, date) pairs first
        price_requests = {}
        for tx in transactions:
            value = tx.get('value', 0) or tx.get('amount', 0)
            if not value or value <= 0:
                continue
            
            tx_asset = tx.get('asset', symbol).upper()
            timestamp = tx.get('timestamp') or tx.get('blockTime')
            
            if timestamp and timestamp > 0:
                try:
                    dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
                    date_str = dt.strftime('%d-%m-%Y')
                    cache_key = f"{tx_asset}_{date_str}"
                    if cache_key not in self.price_cache:
                        price_requests[cache_key] = (tx_asset, int(timestamp))
                except (ValueError, OSError):
                    pass
        
        # Limit price lookups to avoid excessive API calls
        MAX_PRICE_LOOKUPS = 200
        if len(price_requests) > MAX_PRICE_LOOKUPS:
            logger.warning(f"Limiting price lookups from {len(price_requests)} to {MAX_PRICE_LOOKUPS}")
            native_keys = {k: v for k, v in price_requests.items() if v[0] == symbol.upper()}
            other_keys = {k: v for k, v in price_requests.items() if v[0] != symbol.upper()}
            price_requests = {**native_keys, **dict(list(other_keys.items())[:MAX_PRICE_LOOKUPS - len(native_keys)])}
        
        # BULK OPTIMIZATION: Use bulk historical price fetch for native token
        # One API call gets 2000 days of prices instead of 200+ individual calls
        unique_assets = set(v[0] for v in price_requests.values())
        for asset in unique_assets:
            bulk_prices = price_service.get_bulk_historical_prices(asset)
            if bulk_prices:
                for cache_key, (req_asset, req_ts) in list(price_requests.items()):
                    if req_asset == asset:
                        date_str = cache_key.split('_', 1)[1] if '_' in cache_key else ''
                        if date_str in bulk_prices:
                            self.price_cache[cache_key] = bulk_prices[date_str]
                            del price_requests[cache_key]
        
        # Fetch remaining prices individually (only for dates not covered by bulk)
        # Limit to avoid timeout - skip very old dates that won't have API data
        remaining = len(price_requests)
        if remaining > 50:
            logger.warning(f"Skipping {remaining - 50} price lookups for very old dates, using current price as fallback")
            # Sort by timestamp and keep only the 50 most recent
            sorted_requests = sorted(price_requests.items(), key=lambda x: x[1][1], reverse=True)
            price_requests = dict(sorted_requests[:50])
        
        logger.info(f"Price enrichment: {len(transactions)} txs, {len(price_requests)} prices still needed after bulk fetch")
        
        for cache_key, (asset, ts) in price_requests.items():
            if cache_key in self.price_cache:
                continue
            price = self._get_historical_price(asset, ts)
            if price:
                self.price_cache[cache_key] = price
        
        # Now enrich all transactions using cached prices
        for tx in transactions:
            # Skip transactions with zero value
            value = float(tx.get('value', 0))
            if value <= 0:
                continue
            
            # Get the actual asset for this transaction
            tx_asset = tx.get('asset', symbol).upper()
            
            # Get timestamp
            timestamp = tx.get('timestamp') or tx.get('blockTime')
            
            # Determine price based on asset type - use pre-fetched batch cache
            price = None
            price_source = 'none'
            
            if timestamp and timestamp > 0:
                try:
                    dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
                    date_str = dt.strftime('%d-%m-%Y')
                    cache_key = f"{tx_asset}_{date_str}"
                    price = self.price_cache.get(cache_key)
                    if price:
                        price_source = 'historical'
                except (ValueError, OSError):
                    pass
            
            # Fallback logic - ONLY for native tokens, NOT for random ERC-20s
            if not price:
                is_native_token = tx_asset == symbol.upper()
                
                if is_native_token:
                    # For native token (ETH, BTC, etc.), use current price as fallback
                    price = current_price
                    price_source = 'current_native'
                else:
                    # For ERC-20 tokens, try to get current price
                    price = price_service.get_current_price(tx_asset)
                    if price:
                        price_source = 'current_lookup'
                    else:
                        # Unknown token - assign $0 to avoid billion-dollar bugs
                        price = 0
                        price_source = 'unknown_token'
                        logger.warning(f"Unknown token {tx_asset} - assigned $0 price")
            
            # Calculate total USD value
            total_usd = value * price if price else 0
            
            # Enrich transaction
            enriched_tx = {
                **tx,
                'price_usd': price,
                'total_usd': total_usd,
                'value_usd': total_usd,
                'price_source': price_source,
                'amount': value,
                'asset': tx_asset,  # Preserve the actual asset
            }
            
            # Validate
            is_valid, warnings = self._validate_transaction(enriched_tx)
            if not is_valid:
                enriched_tx['validation_warnings'] = warnings
                validation_warnings.extend([f"TX {tx.get('hash', 'unknown')}: {w}" for w in warnings])
                logger.warning(f"Transaction validation warnings: {warnings}")
            
            enriched.append(enriched_tx)
        
        if validation_warnings:
            logger.warning(f"Total validation warnings: {len(validation_warnings)}")
        
        return enriched
    
    def calculate_on_chain_tax_data(
        self,
        transactions: List[Dict],
        symbol: str,
        current_price: float,
        current_balance: float = 0
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive tax data from on-chain transactions only.
        
        For large wallets (1000+ txs), filters to native token + top tokens
        to avoid thousands of price API calls for obscure ERC-20 tokens.
        """
        # For large wallets, filter to native token + top tokens by tx count
        filtered_txs = transactions
        if len(transactions) > 500:
            # Count transactions per asset
            asset_counts = {}
            for tx in transactions:
                asset = (tx.get('asset') or symbol).upper()
                asset_counts[asset] = asset_counts.get(asset, 0) + 1
            
            # Keep native token + top 10 tokens by frequency
            top_assets = sorted(asset_counts.items(), key=lambda x: -x[1])[:10]
            top_asset_names = {a[0] for a in top_assets}
            top_asset_names.add(symbol.upper())
            
            filtered_txs = [tx for tx in transactions if (tx.get('asset') or symbol).upper() in top_asset_names]
            logger.info(f"Large wallet optimization: {len(transactions)} txs -> {len(filtered_txs)} txs "
                       f"(tracking {len(top_asset_names)} assets: {', '.join(list(top_asset_names)[:5])}...)")
        
        # Enrich transactions with historical prices
        enriched = self.enrich_wallet_transactions(filtered_txs, symbol, current_price)
        
        if not enriched:
            return self._empty_tax_data()
        
        # Group transactions by asset for per-asset FIFO calculation
        asset_groups = {}
        total_validation_issues = []
        
        for tx in enriched:
            tx_type = tx.get('type', '').lower()
            tx_asset = tx.get('asset', symbol).upper()
            
            # Skip unknown tokens with $0 price from tax calculations
            if tx.get('price_source') == 'unknown_token':
                logger.info(f"Skipping unknown token {tx_asset} from tax calculations")
                continue
            
            # Collect validation warnings
            if tx.get('validation_warnings'):
                total_validation_issues.extend(tx['validation_warnings'])
            
            tx_record = {
                'tx_id': tx.get('hash', f"wallet_{id(tx)}"),
                'source': 'on-chain',
                'date': self._format_date(tx.get('timestamp')),
                'timestamp': tx.get('timestamp'),
                'amount': tx.get('amount', 0),
                'price_usd': tx.get('price_usd', 0),
                'total_usd': tx.get('total_usd', 0),
                'asset': tx_asset,
                'price_source': tx.get('price_source', 'unknown')
            }
            
            if tx_asset not in asset_groups:
                asset_groups[tx_asset] = {'buys': [], 'sells': []}
            
            if tx_type in ['received', 'buy', 'deposit', 'reward', 'staking', 'airdrop']:
                asset_groups[tx_asset]['buys'].append(tx_record)
            elif tx_type in ['sent', 'sell', 'send', 'withdrawal']:
                asset_groups[tx_asset]['sells'].append(tx_record)
        
        # Run FIFO per asset and aggregate
        all_realized_gains = []
        all_remaining_lots = []
        all_buys = []
        all_sells = []
        
        for asset, groups in asset_groups.items():
            buys = sorted(groups['buys'], key=lambda x: x.get('timestamp', 0) or 0)
            sells = sorted(groups['sells'], key=lambda x: x.get('timestamp', 0) or 0)
            all_buys.extend(buys)
            all_sells.extend(sells)
            
            if buys or sells:
                asset_realized = self._calculate_fifo_gains(buys.copy(), sells.copy())
                all_realized_gains.extend(asset_realized)
                
                asset_remaining = self._get_remaining_lots(buys.copy(), sells.copy())
                # Use correct current price for each asset
                if asset == symbol.upper():
                    asset_price = current_price
                else:
                    asset_price = price_service.get_current_price(asset) or 0
                
                for lot in asset_remaining:
                    lot['current_price'] = asset_price
                    lot['current_value'] = lot['amount'] * asset_price
                    lot['unrealized_gain'] = lot['current_value'] - lot.get('cost_basis', 0)
                all_remaining_lots.extend(asset_remaining)
        
        realized_gains = all_realized_gains
        remaining_lots = all_remaining_lots
        
        # Calculate unrealized totals
        total_unrealized_cost = sum(lot.get('cost_basis', 0) for lot in remaining_lots)
        total_unrealized_value = sum(lot.get('current_value', 0) for lot in remaining_lots)
        unrealized = {
            'lots': remaining_lots,
            'total_cost_basis': total_unrealized_cost,
            'total_current_value': total_unrealized_value,
            'total_gain': total_unrealized_value - total_unrealized_cost,
            'total_gain_percentage': ((total_unrealized_value - total_unrealized_cost) / total_unrealized_cost * 100) if total_unrealized_cost > 0 else 0
        }
        
        # Calculate totals with validation
        total_realized = sum(g['gain_loss'] for g in realized_gains)
        short_term = sum(g['gain_loss'] for g in realized_gains if g['holding_period'] == 'short-term')
        long_term = sum(g['gain_loss'] for g in realized_gains if g['holding_period'] == 'long-term')
        
        # Flag if totals seem unreasonable
        if abs(total_realized) > self.MAX_SINGLE_TX_VALUE_USD:
            total_validation_issues.append(f"WARNING: Total realized gains seem unreasonable: ${total_realized:,.2f}")
            logger.error(f"VALIDATION: Unreasonable total realized gains: ${total_realized:,.2f}")
        
        return {
            'method': 'FIFO',
            'data_source': 'on-chain',
            'symbol': symbol,
            'sources': {
                'on_chain_count': len(enriched),
                'buys_count': len(all_buys),
                'sells_count': len(all_sells),
                'assets_tracked': len(asset_groups),
                'historical_prices_used': sum(1 for tx in enriched if tx.get('price_source') == 'historical'),
                'current_prices_used': sum(1 for tx in enriched if tx.get('price_source') == 'current')
            },
            'realized_gains': realized_gains,
            'unrealized_gains': unrealized,
            'remaining_lots': remaining_lots,
            'summary': {
                'total_realized_gain': total_realized,
                'total_unrealized_gain': unrealized.get('total_gain', 0),
                'total_gain': total_realized + unrealized.get('total_gain', 0),
                'short_term_gains': short_term,
                'long_term_gains': long_term,
                'total_transactions': len(enriched),
                'buy_count': len(all_buys),
                'sell_count': len(all_sells),
                'current_balance': current_balance,
                'current_price': current_price,
                'current_value': current_balance * current_price
            },
            'validation': {
                'has_issues': len(total_validation_issues) > 0,
                'issues': total_validation_issues[:20]
            },
            'enriched_transactions': enriched
        }
    
    def _calculate_fifo_gains(self, buys: List[Dict], sells: List[Dict]) -> List[Dict]:
        """Calculate realized gains using FIFO method with detailed logging"""
        realized = []
        
        # Create buy queue
        buy_queue = []
        for buy in buys:
            buy_queue.append({
                **buy,
                'remaining': buy['amount']
            })
        
        for sell in sells:
            sell_amount = sell['amount']
            sell_price = sell['price_usd'] or 0
            sell_date = sell['date']
            sell_timestamp = sell.get('timestamp')
            remaining_to_sell = sell_amount
            
            logger.debug(f"Processing sell: {sell_amount} at ${sell_price} on {sell_date}")
            
            while remaining_to_sell > 0 and buy_queue:
                lot = buy_queue[0]
                
                if lot['remaining'] <= 0:
                    buy_queue.pop(0)
                    continue
                
                # Match amount
                matched = min(lot['remaining'], remaining_to_sell)
                
                # Calculate gain/loss
                proceeds = matched * sell_price
                cost_basis = matched * (lot['price_usd'] or 0)
                gain_loss = proceeds - cost_basis
                
                # Log large gains for debugging
                if abs(gain_loss) > 1_000_000:
                    logger.warning(f"LARGE GAIN/LOSS: ${gain_loss:,.2f} from selling {matched} units "
                                 f"(buy price: ${lot['price_usd']}, sell price: ${sell_price})")
                
                # Determine holding period
                holding_period = self._get_holding_period(lot.get('timestamp'), sell_timestamp)
                
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
                    'holding_period': holding_period,
                    'buy_price_source': lot.get('price_source'),
                    'sell_price_source': sell.get('price_source')
                })
                
                # Update remaining
                lot['remaining'] -= matched
                remaining_to_sell -= matched
                
                if lot['remaining'] <= 0:
                    buy_queue.pop(0)
        
        return realized
    
    def _get_remaining_lots(self, buys: List[Dict], sells: List[Dict]) -> List[Dict]:
        """Get remaining unsold lots after FIFO matching"""
        buy_queue = []
        for buy in buys:
            buy_queue.append({
                **buy,
                'remaining': buy['amount']
            })
        
        # Process sells
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
                'cost_basis': lot['remaining'] * (lot['price_usd'] or 0),
                'asset': lot['asset'],
                'price_source': lot.get('price_source')
            }
            for lot in buy_queue if lot['remaining'] > 0
        ]
    
    def _calculate_unrealized(self, remaining_lots: List[Dict], current_price: float) -> Dict:
        """Calculate unrealized gains from remaining lots"""
        lots_with_gains = []
        total_cost = 0
        total_value = 0
        
        for lot in remaining_lots:
            cost = lot.get('cost_basis', 0)
            amount = lot.get('amount', 0)
            value = amount * current_price
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
    
    def _get_holding_period(self, buy_timestamp, sell_timestamp) -> str:
        """Determine if holding period is short-term or long-term"""
        try:
            if not buy_timestamp or not sell_timestamp:
                return 'unknown'
            
            buy_time = buy_timestamp
            sell_time = sell_timestamp
            
            # Handle datetime objects
            if isinstance(buy_time, datetime):
                buy_time = buy_time.timestamp()
            if isinstance(sell_time, datetime):
                sell_time = sell_time.timestamp()
            
            # Calculate days held
            days_held = (sell_time - buy_time) / 86400  # seconds per day
            
            # Long-term = held more than 1 year (365 days)
            if days_held > 365:
                return 'long-term'
            return 'short-term'
        except Exception as e:
            logger.warning(f"Error calculating holding period: {e}")
            return 'unknown'
    
    def _format_date(self, timestamp) -> str:
        """Format timestamp to date string"""
        try:
            if isinstance(timestamp, (int, float)) and timestamp > 0:
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                return dt.strftime('%Y-%m-%d')
            return 'Unknown'
        except:
            return 'Unknown'
    
    def _empty_tax_data(self) -> Dict:
        """Return empty tax data structure"""
        return {
            'method': 'FIFO',
            'data_source': 'on-chain',
            'sources': {'on_chain_count': 0, 'buys_count': 0, 'sells_count': 0},
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
            'validation': {'has_issues': False, 'issues': []},
            'enriched_transactions': []
        }


# Singleton instance
historical_tax_enrichment = HistoricalTaxEnrichment()
