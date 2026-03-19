"""
Price Service - Fetches cryptocurrency prices from multiple sources.
- Current prices: Binance.US (fast) → CoinGecko (fallback)
- Historical prices: CryptoCompare (best free data) → CoinGecko (fallback)
"""

import requests
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
import time
import threading

logger = logging.getLogger(__name__)


class PriceService:
    def __init__(self):
        self.binance_url = "https://api.binance.us/api/v3"
        self.cryptocompare_url = "https://min-api.cryptocompare.com/data/v2"
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        self.cache = {}
        self.cache_duration = 60
        self.historical_cache_duration = 86400 * 7
        self._lock = threading.Lock()
        self._last_coingecko_request = 0
        self._min_coingecko_interval = 1.5
        
        # Binance.US pairs (USD)
        self.binance_symbols = {
            'ETH': 'ETHUSD', 'BTC': 'BTCUSD', 'SOL': 'SOLUSD',
            'DOGE': 'DOGEUSD', 'XRP': 'XRPUSD', 'ADA': 'ADAUSD',
            'MATIC': 'MATICUSD', 'DOT': 'DOTUSD', 'LINK': 'LINKUSD',
            'AVAX': 'AVAXUSD', 'ATOM': 'ATOMUSD', 'LTC': 'LTCUSD',
            'ALGO': 'ALGOUSD', 'XLM': 'XLMUSD', 'UNI': 'UNIUSD'
        }
        
        # CoinGecko IDs
        self.coin_ids = {
            'ETH': 'ethereum', 'BTC': 'bitcoin', 'SOL': 'solana',
            'MATIC': 'polygon-ecosystem-token', 'BNB': 'binancecoin',
            'ALGO': 'algorand', 'AVAX': 'avalanche-2', 'FTM': 'fantom',
            'DOGE': 'dogecoin', 'OP': 'optimism', 'ARB': 'arbitrum',
            'XRP': 'ripple', 'XLM': 'stellar', 'WETH': 'weth',
            'WBTC': 'wrapped-bitcoin', 'USDT': 'tether', 'USDC': 'usd-coin'
        }
        
        # Fallback prices
        self.fallback_prices = {
            'ETH': 2200.0, 'BTC': 85000.0, 'SOL': 140.0, 'BNB': 600.0,
            'MATIC': 0.40, 'ALGO': 0.22, 'AVAX': 25.0, 'FTM': 0.50,
            'DOGE': 0.18, 'OP': 2.00, 'ARB': 0.80, 'XRP': 2.30,
            'XLM': 0.35, 'USDT': 1.0, 'USDC': 1.0, 'DAI': 1.0
        }
    
    def _coingecko_rate_limit(self):
        with self._lock:
            elapsed = time.time() - self._last_coingecko_request
            if elapsed < self._min_coingecko_interval:
                time.sleep(self._min_coingecko_interval - elapsed)
            self._last_coingecko_request = time.time()
    
    def _get_from_cache(self, key: str) -> Optional[float]:
        with self._lock:
            if key in self.cache:
                value, expiry = self.cache[key]
                if time.time() < expiry:
                    return value
                del self.cache[key]
        return None
    
    def _set_cache(self, key: str, value: float, duration: int):
        with self._lock:
            self.cache[key] = (value, time.time() + duration)
    
    # ========== BINANCE ==========
    
    def get_current_price_binance(self, symbol: str) -> Optional[float]:
        binance_pair = self.binance_symbols.get(symbol.upper())
        if not binance_pair:
            return None
        try:
            response = requests.get(
                f"{self.binance_url}/ticker/price",
                params={'symbol': binance_pair},
                timeout=5
            )
            if response.status_code == 200:
                price = float(response.json().get('price', 0))
                if price > 0:
                    return price
        except Exception as e:
            logger.debug(f"Binance price failed for {symbol}: {e}")
        return None
    
    # ========== CRYPTOCOMPARE ==========
    
    def get_bulk_historical_prices(self, symbol: str, days: int = 2000) -> Dict[str, float]:
        """
        Fetch up to 2000 days of daily prices in a SINGLE API call.
        Returns: {timestamp_str: price} dict for fast lookups.
        Much faster than individual get_historical_price calls.
        """
        cache_key = f"bulk_{symbol.upper()}_{days}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            response = requests.get(
                f"{self.cryptocompare_url}/histoday",
                params={'fsym': symbol.upper(), 'tsym': 'USD', 'limit': min(days, 2000)},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('Response') == 'Success':
                    history = data.get('Data', {}).get('Data', [])
                    prices = {}
                    for point in history:
                        ts = point.get('time', 0)
                        close = point.get('close', 0)
                        if ts and close > 0:
                            # Store by date string for easy lookup
                            from datetime import datetime, timezone
                            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                            date_str = dt.strftime('%d-%m-%Y')
                            prices[date_str] = float(close)
                    
                    if prices:
                        logger.info(f"CryptoCompare bulk: {symbol} fetched {len(prices)} daily prices")
                        self._set_cache(cache_key, prices, 3600)
                        return prices
        except Exception as e:
            logger.warning(f"CryptoCompare bulk failed for {symbol}: {e}")
        return {}
    
    def get_historical_price_cryptocompare(self, symbol: str, timestamp: int) -> Optional[float]:
        """CryptoCompare has excellent free historical data going back to 2010"""
        try:
            response = requests.get(
                f"{self.cryptocompare_url}/histoday",
                params={'fsym': symbol.upper(), 'tsym': 'USD', 'limit': 1, 'toTs': timestamp},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('Response') == 'Success':
                    history = data.get('Data', {}).get('Data', [])
                    if history:
                        close_price = history[0].get('close', 0)
                        if close_price > 0:
                            logger.info(f"CryptoCompare: {symbol} at {timestamp} = ${close_price:.4f}")
                            return float(close_price)
        except Exception as e:
            logger.warning(f"CryptoCompare failed for {symbol}: {e}")
        return None
    
    # ========== COINGECKO ==========
    
    def _get_current_price_coingecko(self, symbol: str) -> Optional[float]:
        coin_id = self.coin_ids.get(symbol.upper())
        if not coin_id:
            return None
        try:
            self._coingecko_rate_limit()
            response = requests.get(
                f"{self.coingecko_url}/simple/price",
                params={'ids': coin_id, 'vs_currencies': 'usd'},
                timeout=10
            )
            if response.status_code == 200:
                price = response.json().get(coin_id, {}).get('usd')
                if price:
                    return float(price)
            elif response.status_code == 429:
                logger.warning(f"CoinGecko rate limited for {symbol}")
        except Exception as e:
            logger.warning(f"CoinGecko price failed for {symbol}: {e}")
        return None
    
    def _get_historical_price_coingecko(self, symbol: str, date_str: str) -> Optional[float]:
        coin_id = self.coin_ids.get(symbol.upper())
        if not coin_id:
            return None
        try:
            self._coingecko_rate_limit()
            response = requests.get(
                f"{self.coingecko_url}/coins/{coin_id}/history",
                params={'date': date_str, 'localization': 'false'},
                timeout=15
            )
            if response.status_code == 200:
                price = response.json().get('market_data', {}).get('current_price', {}).get('usd')
                if price:
                    return float(price)
            elif response.status_code == 429:
                logger.warning(f"CoinGecko rate limited for historical {symbol}")
        except Exception as e:
            logger.warning(f"CoinGecko historical failed for {symbol}: {e}")
        return None
    
    # ========== PUBLIC API ==========
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price: Binance → CoinGecko → Fallback"""
        symbol_upper = symbol.upper()
        
        if symbol_upper in ['USDT', 'USDC', 'DAI', 'BUSD']:
            return 1.0
        
        cache_key = f"current_{symbol_upper}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        # Try Binance
        price = self.get_current_price_binance(symbol_upper)
        if price:
            self._set_cache(cache_key, price, self.cache_duration)
            return price
        
        # Try CoinGecko
        price = self._get_current_price_coingecko(symbol_upper)
        if price:
            self._set_cache(cache_key, price, self.cache_duration)
            return price
        
        # Fallback
        return self.fallback_prices.get(symbol_upper)
    
    def get_historical_price(self, symbol: str, date_str: str) -> Optional[float]:
        """Get historical price: CryptoCompare → CoinGecko (date format: DD-MM-YYYY)"""
        symbol_upper = symbol.upper()
        
        if symbol_upper in ['USDT', 'USDC', 'DAI', 'BUSD']:
            return 1.0
        
        cache_key = f"historical_{symbol_upper}_{date_str}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        # Convert date to timestamp
        try:
            dt = datetime.strptime(date_str, '%d-%m-%Y')
            timestamp = int(dt.replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            logger.warning(f"Invalid date: {date_str}")
            return None
        
        # Try CryptoCompare (best historical data)
        price = self.get_historical_price_cryptocompare(symbol_upper, timestamp)
        if price:
            self._set_cache(cache_key, price, self.historical_cache_duration)
            return price
        
        # Try CoinGecko
        price = self._get_historical_price_coingecko(symbol_upper, date_str)
        if price:
            self._set_cache(cache_key, price, self.historical_cache_duration)
            return price
        
        logger.warning(f"No price for {symbol} on {date_str}")
        return None
    
    def get_price_at_block(self, symbol: str, timestamp: int) -> Optional[float]:
        """Get price at Unix timestamp"""
        try:
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            return self.get_historical_price(symbol, dt.strftime('%d-%m-%Y'))
        except Exception as e:
            logger.error(f"Error in get_price_at_block: {e}")
            return None
    
    def get_multiple_prices(self, symbols: list) -> Dict[str, float]:
        """Get current prices for multiple symbols"""
        return {s.upper(): p for s in symbols if (p := self.get_current_price(s))}
    
    def add_coin_mapping(self, symbol: str, coingecko_id: str):
        """Add custom token mapping"""
        self.coin_ids[symbol.upper()] = coingecko_id


# Global instance
price_service = PriceService()
