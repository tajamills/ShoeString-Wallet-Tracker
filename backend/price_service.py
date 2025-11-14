import requests
import logging
from typing import Dict, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class PriceService:
    """Service for fetching cryptocurrency prices from CoinGecko API"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.cache = {}  # Simple in-memory cache
        self.cache_duration = 300  # 5 minutes
        
        # Map chain symbols to CoinGecko IDs
        self.coin_ids = {
            'ETH': 'ethereum',
            'BTC': 'bitcoin',
            'MATIC': 'polygon-ecosystem-token',
            'BNB': 'binancecoin',
            'SOL': 'solana',
            'USDT': 'tether',
            'USDC': 'usd-coin',
            'DAI': 'dai',
            'WETH': 'weth',
            'WBTC': 'wrapped-bitcoin',
            'ARB': 'arbitrum'
        }
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current USD price for a cryptocurrency"""
        try:
            # Check cache
            cache_key = f"current_{symbol}"
            if cache_key in self.cache:
                cached_data, cached_time = self.cache[cache_key]
                if time.time() - cached_time < self.cache_duration:
                    return cached_data
            
            # Get CoinGecko ID
            coin_id = self.coin_ids.get(symbol.upper())
            if not coin_id:
                logger.warning(f"No CoinGecko ID for symbol: {symbol}")
                return None
            
            # Fetch from CoinGecko
            url = f"{self.base_url}/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            price = data.get(coin_id, {}).get('usd')
            
            # Cache result
            if price:
                self.cache[cache_key] = (price, time.time())
            
            return price
            
        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {str(e)}")
            return None
    
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
