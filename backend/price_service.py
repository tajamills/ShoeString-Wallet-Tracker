import requests
import logging
from typing import Dict, Optional
from datetime import datetime
import time
import threading

logger = logging.getLogger(__name__)

class PriceService:
    """Service for fetching cryptocurrency prices from CoinGecko API with aggressive caching"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.cache = {}  # Simple in-memory cache
        self.cache_duration = 60  # 60 seconds for current prices (was 300)
        self.historical_cache_duration = 86400  # 24 hours for historical
        self._lock = threading.Lock()
        self._last_request_time = 0
        self._min_request_interval = 1.5  # 1.5 seconds between requests (rate limit protection)
        
        # Map chain symbols to CoinGecko IDs
        self.coin_ids = {
            'ETH': 'ethereum',
            'BTC': 'bitcoin',
            'MATIC': 'polygon-ecosystem-token',
            'BNB': 'binancecoin',
            'SOL': 'solana',
            'ALGO': 'algorand',
            'AVAX': 'avalanche-2',
            'FTM': 'fantom',
            'DOGE': 'dogecoin',
            'OP': 'optimism',
            'USDT': 'tether',
            'USDC': 'usd-coin',
            'DAI': 'dai',
            'WETH': 'weth',
            'WBTC': 'wrapped-bitcoin',
            'ARB': 'arbitrum',
            'XRP': 'ripple',
            'XLM': 'stellar'
        }
        
        # Fallback prices - more comprehensive and updated
        self.fallback_prices = {
            'ETH': 3500.0,
            'BTC': 95000.0,
            'MATIC': 0.45,
            'BNB': 650.0,
            'SOL': 180.0,
            'ALGO': 0.25,
            'AVAX': 35.0,
            'FTM': 0.70,
            'DOGE': 0.35,
            'OP': 2.50,
            'USDT': 1.0,
            'USDC': 1.0,
            'DAI': 1.0,
            'WETH': 3500.0,
            'WBTC': 95000.0,
            'ARB': 1.20,
            'XRP': 2.50,
            'XLM': 0.40
        }
    
    def _rate_limit_wait(self):
        """Ensure we don't exceed rate limits"""
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                time.sleep(self._min_request_interval - elapsed)
            self._last_request_time = time.time()
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current USD price for a cryptocurrency with aggressive caching"""
        symbol_upper = symbol.upper()
        
        try:
            # Check cache first
            cache_key = f"current_{symbol_upper}"
            if cache_key in self.cache:
                cached_data, cached_time = self.cache[cache_key]
                if time.time() - cached_time < self.cache_duration:
                    return cached_data
            
            # Get CoinGecko ID
            coin_id = self.coin_ids.get(symbol_upper)
            if not coin_id:
                logger.debug(f"No CoinGecko ID for symbol: {symbol}, using fallback")
                return self.fallback_prices.get(symbol_upper)
            
            # Rate limit protection
            self._rate_limit_wait()
            
            # Fetch from CoinGecko
            url = f"{self.base_url}/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            # Handle rate limiting explicitly
            if response.status_code == 429:
                logger.warning(f"CoinGecko rate limited, using fallback for {symbol}")
                return self.fallback_prices.get(symbol_upper)
            
            response.raise_for_status()
            data = response.json()
            
            price = data.get(coin_id, {}).get('usd')
            
            # Cache result
            if price:
                self.cache[cache_key] = (price, time.time())
                # Also update fallback price
                self.fallback_prices[symbol_upper] = price
            
            return price or self.fallback_prices.get(symbol_upper)
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching price for {symbol}, using fallback")
            return self.fallback_prices.get(symbol_upper)
        except Exception as e:
            logger.warning(f"Error fetching price for {symbol}: {str(e)}. Using fallback.")
            return self.fallback_prices.get(symbol_upper)
    
    def get_historical_price(self, symbol: str, date: str) -> Optional[float]:
        """
        Get historical USD price for a cryptocurrency on a specific date
        Date format: DD-MM-YYYY (e.g., '01-01-2024')
        """
        try:
            # Check cache
            cache_key = f"historical_{symbol}_{date}"
            if cache_key in self.cache:
                cached_data, cached_time = self.cache[cache_key]
                # Historical prices don't change, cache forever
                return cached_data
            
            # Get CoinGecko ID
            coin_id = self.coin_ids.get(symbol.upper())
            if not coin_id:
                logger.warning(f"No CoinGecko ID for symbol: {symbol}")
                return None
            
            # Fetch from CoinGecko
            url = f"{self.base_url}/coins/{coin_id}/history"
            params = {
                'date': date,
                'localization': 'false'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            price = data.get('market_data', {}).get('current_price', {}).get('usd')
            
            # Cache result (historical prices don't change)
            if price:
                self.cache[cache_key] = (price, time.time())
            
            return price
            
        except Exception as e:
            logger.error(f"Error fetching historical price for {symbol} on {date}: {str(e)}")
            return None
    
    def get_multiple_prices(self, symbols: list) -> Dict[str, float]:
        """Get current prices for multiple cryptocurrencies"""
        try:
            # Filter to valid symbols
            coin_ids = []
            symbol_to_id = {}
            
            for symbol in symbols:
                coin_id = self.coin_ids.get(symbol.upper())
                if coin_id:
                    coin_ids.append(coin_id)
                    symbol_to_id[coin_id] = symbol.upper()
            
            if not coin_ids:
                return {}
            
            # Fetch from CoinGecko
            url = f"{self.base_url}/simple/price"
            params = {
                'ids': ','.join(coin_ids),
                'vs_currencies': 'usd'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Map back to symbols
            result = {}
            for coin_id, price_data in data.items():
                symbol = symbol_to_id.get(coin_id)
                if symbol:
                    result[symbol] = price_data.get('usd')
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching multiple prices: {str(e)}")
            return {}
    
    def add_coin_mapping(self, symbol: str, coingecko_id: str):
        """Add a custom token mapping"""
        self.coin_ids[symbol.upper()] = coingecko_id
    
    def get_price_at_block(self, symbol: str, timestamp: int) -> Optional[float]:
        """Get price at a specific timestamp (Unix timestamp)"""
        try:
            # Convert timestamp to date format DD-MM-YYYY
            dt = datetime.fromtimestamp(timestamp)
            date_str = dt.strftime('%d-%m-%Y')
            
            return self.get_historical_price(symbol, date_str)
            
        except Exception as e:
            logger.error(f"Error getting price at block: {str(e)}")
            return None

# Initialize global price service
price_service = PriceService()
