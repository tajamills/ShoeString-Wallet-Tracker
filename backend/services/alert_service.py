"""
Alert Service - Handles price monitoring and alert triggering
"""
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
import os

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing price alerts and monitoring"""
    
    def __init__(self):
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        self.alpha_vantage_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
        self.price_cache: Dict[str, Dict] = {}
        self.cache_ttl = 60  # Cache prices for 60 seconds
        
        # Common crypto symbol to CoinGecko ID mapping
        self.crypto_id_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "XRP": "ripple",
            "ADA": "cardano",
            "DOGE": "dogecoin",
            "DOT": "polkadot",
            "MATIC": "matic-network",
            "LINK": "chainlink",
            "AVAX": "avalanche-2",
            "UNI": "uniswap",
            "ATOM": "cosmos",
            "LTC": "litecoin",
            "XLM": "stellar",
            "ALGO": "algorand",
            "VET": "vechain",
            "FIL": "filecoin",
            "AAVE": "aave",
            "MKR": "maker",
            "COMP": "compound-governance-token",
            "SNX": "havven",
            "CRV": "curve-dao-token",
            "SUSHI": "sushi",
            "YFI": "yearn-finance",
            "USDC": "usd-coin",
            "USDT": "tether",
            "DAI": "dai",
            "SHIB": "shiba-inu",
            "PEPE": "pepe",
            "ARB": "arbitrum",
            "OP": "optimism",
            "APT": "aptos",
            "SUI": "sui",
            "SEI": "sei-network",
            "INJ": "injective-protocol",
            "TIA": "celestia",
            "NEAR": "near",
            "FTM": "fantom",
            "SAND": "the-sandbox",
            "MANA": "decentraland",
            "AXS": "axie-infinity",
            "APE": "apecoin",
            "LDO": "lido-dao",
            "RPL": "rocket-pool",
            "GMX": "gmx",
            "BLUR": "blur",
        }
    
    async def get_crypto_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current price for a cryptocurrency"""
        symbol = symbol.upper()
        
        # Check cache first
        cache_key = f"crypto_{symbol}"
        if cache_key in self.price_cache:
            cached = self.price_cache[cache_key]
            if datetime.now(timezone.utc) - cached["timestamp"] < timedelta(seconds=self.cache_ttl):
                return cached["data"]
        
        # Get CoinGecko ID
        coin_id = self.crypto_id_map.get(symbol, symbol.lower())
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.coingecko_base}/simple/price",
                    params={
                        "ids": coin_id,
                        "vs_currencies": "usd",
                        "include_24hr_change": "true",
                        "include_24hr_vol": "true",
                        "include_market_cap": "true"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if coin_id in data:
                        result = {
                            "symbol": symbol,
                            "price": data[coin_id].get("usd", 0),
                            "change_24h": data[coin_id].get("usd_24h_change", 0),
                            "volume_24h": data[coin_id].get("usd_24h_vol", 0),
                            "market_cap": data[coin_id].get("usd_market_cap", 0),
                            "source": "coingecko",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        
                        # Cache the result
                        self.price_cache[cache_key] = {
                            "data": result,
                            "timestamp": datetime.now(timezone.utc)
                        }
                        
                        return result
                        
        except Exception as e:
            logger.error(f"Error fetching crypto price for {symbol}: {e}")
        
        return None
    
    async def get_stock_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current price for a stock using Alpha Vantage or Yahoo Finance"""
        symbol = symbol.upper()
        
        # Check cache first
        cache_key = f"stock_{symbol}"
        if cache_key in self.price_cache:
            cached = self.price_cache[cache_key]
            if datetime.now(timezone.utc) - cached["timestamp"] < timedelta(seconds=self.cache_ttl):
                return cached["data"]
        
        # Try Yahoo Finance (free, no API key needed)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Use Yahoo Finance quote endpoint
                response = await client.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                    params={"interval": "1d", "range": "2d"},
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result_data = data.get("chart", {}).get("result", [])
                    
                    if result_data:
                        meta = result_data[0].get("meta", {})
                        indicators = result_data[0].get("indicators", {}).get("quote", [{}])[0]
                        
                        current_price = meta.get("regularMarketPrice", 0)
                        previous_close = meta.get("previousClose", current_price)
                        
                        change_24h = 0
                        if previous_close > 0:
                            change_24h = ((current_price - previous_close) / previous_close) * 100
                        
                        result = {
                            "symbol": symbol,
                            "price": current_price,
                            "change_24h": change_24h,
                            "previous_close": previous_close,
                            "volume_24h": indicators.get("volume", [0])[-1] if indicators.get("volume") else 0,
                            "market_cap": meta.get("marketCap", 0),
                            "source": "yahoo",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        
                        # Cache the result
                        self.price_cache[cache_key] = {
                            "data": result,
                            "timestamp": datetime.now(timezone.utc)
                        }
                        
                        return result
                        
        except Exception as e:
            logger.error(f"Error fetching stock price for {symbol}: {e}")
        
        return None
    
    async def get_price(self, symbol: str, asset_type: str) -> Optional[Dict[str, Any]]:
        """Get price for any asset type"""
        if asset_type == "crypto":
            return await self.get_crypto_price(symbol)
        elif asset_type == "stock":
            return await self.get_stock_price(symbol)
        return None
    
    def check_alert_condition(
        self, 
        alert_type: str, 
        target_value: float, 
        current_price: float, 
        change_24h: float
    ) -> bool:
        """Check if an alert condition is met"""
        if alert_type == "price_above":
            return current_price >= target_value
        elif alert_type == "price_below":
            return current_price <= target_value
        elif alert_type == "percent_change_up":
            return change_24h >= target_value
        elif alert_type == "percent_change_down":
            return change_24h <= -abs(target_value)
        return False
    
    async def search_assets(self, query: str, asset_type: Optional[str] = None) -> List[Dict]:
        """Search for assets by name or symbol"""
        results = []
        query = query.upper()
        
        # Search crypto
        if asset_type is None or asset_type == "crypto":
            for symbol, coin_id in self.crypto_id_map.items():
                if query in symbol or query in coin_id.upper():
                    results.append({
                        "symbol": symbol,
                        "name": coin_id.replace("-", " ").title(),
                        "type": "crypto"
                    })
        
        # For stocks, we'd need to search an exchange list
        # For now, allow any stock symbol
        if asset_type is None or asset_type == "stock":
            # Common stocks for quick results
            common_stocks = [
                ("AAPL", "Apple Inc."),
                ("GOOGL", "Alphabet Inc."),
                ("MSFT", "Microsoft Corporation"),
                ("AMZN", "Amazon.com Inc."),
                ("TSLA", "Tesla Inc."),
                ("META", "Meta Platforms Inc."),
                ("NVDA", "NVIDIA Corporation"),
                ("AMD", "Advanced Micro Devices"),
                ("NFLX", "Netflix Inc."),
                ("DIS", "Walt Disney Co."),
                ("BA", "Boeing Co."),
                ("JPM", "JPMorgan Chase & Co."),
                ("V", "Visa Inc."),
                ("MA", "Mastercard Inc."),
                ("PYPL", "PayPal Holdings Inc."),
                ("SQ", "Block Inc."),
                ("COIN", "Coinbase Global Inc."),
                ("MSTR", "MicroStrategy Inc."),
                ("RIOT", "Riot Platforms Inc."),
                ("MARA", "Marathon Digital Holdings"),
            ]
            
            for symbol, name in common_stocks:
                if query in symbol or query in name.upper():
                    results.append({
                        "symbol": symbol,
                        "name": name,
                        "type": "stock"
                    })
        
        return results[:20]  # Limit results


# Singleton instance
alert_service = AlertService()
