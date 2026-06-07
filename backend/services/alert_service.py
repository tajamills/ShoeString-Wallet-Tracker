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
        
        # ISO 20022 Compliant Cryptocurrencies (marked with iso20022 flag)
        self.iso20022_coins = {"XRP", "XLM", "ALGO", "XDC", "IOTA", "HBAR", "MIOTA", "QNT", "ADA", "XTZ"}
        
        # Common crypto symbol to CoinGecko ID mapping - Top 200+ coins
        self.crypto_id_map = {
            # === ISO 20022 COMPLIANT COINS ===
            "XRP": "ripple",
            "XLM": "stellar",
            "ALGO": "algorand",
            "XDC": "xdce-crowd-sale",
            "IOTA": "iota",
            "HBAR": "hedera-hashgraph",
            "QNT": "quant-network",
            "ADA": "cardano",
            "XTZ": "tezos",
            
            # === TOP CRYPTOCURRENCIES ===
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "BNB": "binancecoin",
            "SOL": "solana",
            "DOGE": "dogecoin",
            "TRX": "tron",
            "TON": "the-open-network",
            "DOT": "polkadot",
            "MATIC": "matic-network",
            "LINK": "chainlink",
            "AVAX": "avalanche-2",
            "SHIB": "shiba-inu",
            "DAI": "dai",
            "LTC": "litecoin",
            "BCH": "bitcoin-cash",
            "UNI": "uniswap",
            "ATOM": "cosmos",
            "LEO": "leo-token",
            "ETC": "ethereum-classic",
            "OKB": "okb",
            "NEAR": "near",
            "APT": "aptos",
            "FIL": "filecoin",
            "ICP": "internet-computer",
            "VET": "vechain",
            "CRO": "crypto-com-chain",
            "INJ": "injective-protocol",
            "IMX": "immutable-x",
            "RUNE": "thorchain",
            "STX": "stacks",
            "OP": "optimism",
            "MKR": "maker",
            "GRT": "the-graph",
            "ARB": "arbitrum",
            "THETA": "theta-token",
            "SUI": "sui",
            "RENDER": "render-token",
            "FTM": "fantom",
            "AAVE": "aave",
            "TIA": "celestia",
            "FLOW": "flow",
            "EGLD": "elrond-erd-2",
            "AXS": "axie-infinity",
            "SAND": "the-sandbox",
            "MANA": "decentraland",
            "XMR": "monero",
            "NEO": "neo",
            "EOS": "eos",
            "KAVA": "kava",
            "MINA": "mina-protocol",
            "XEC": "ecash",
            "SNX": "havven",
            "CAKE": "pancakeswap-token",
            "CFX": "conflux-token",
            "KLAY": "klay-token",
            "FXS": "frax-share",
            "RPL": "rocket-pool",
            "LDO": "lido-dao",
            "CRV": "curve-dao-token",
            "GMX": "gmx",
            "BLUR": "blur",
            "APE": "apecoin",
            "DYDX": "dydx",
            "1INCH": "1inch",
            "ENS": "ethereum-name-service",
            "COMP": "compound-governance-token",
            "SUSHI": "sushi",
            "YFI": "yearn-finance",
            "BAL": "balancer",
            "ZRX": "0x",
            "LRC": "loopring",
            "ENJ": "enjincoin",
            "CHZ": "chiliz",
            "GALA": "gala",
            "ANKR": "ankr",
            "AUDIO": "audius",
            "MASK": "mask-network",
            "OCEAN": "ocean-protocol",
            "FET": "fetch-ai",
            "AGIX": "singularitynet",
            "RNDR": "render-token",
            "WLD": "worldcoin-wld",
            "SEI": "sei-network",
            "PYTH": "pyth-network",
            "JUP": "jupiter-exchange-solana",
            "JTO": "jito-governance-token",
            "BONK": "bonk",
            "WIF": "dogwifcoin",
            "PEPE": "pepe",
            "FLOKI": "floki",
            "ORDI": "ordinals",
            "SATS": "sats-ordinals",
            "STG": "stargate-finance",
            "PENDLE": "pendle",
            "STRK": "starknet",
            "ZK": "zksync",
            "W": "wormhole",
            "ETHFI": "ether-fi",
            "ENA": "ethena",
            "ONDO": "ondo-finance",
            
            # === STABLECOINS ===
            "USDC": "usd-coin",
            "USDT": "tether",
            "BUSD": "binance-usd",
            "TUSD": "true-usd",
            "FRAX": "frax",
            "LUSD": "liquity-usd",
            "USDP": "paxos-standard",
            
            # === MORE TOP 200 COINS ===
            "KAS": "kaspa",
            "BSV": "bitcoin-cash-sv",
            "BTT": "bittorrent",
            "BTCB": "bitcoin-bep2",
            "WBTC": "wrapped-bitcoin",
            "WETH": "weth",
            "STETH": "staked-ether",
            "WSTETH": "wrapped-steth",
            "CBETH": "coinbase-wrapped-staked-eth",
            "RETH": "rocket-pool-eth",
            "LUNC": "terra-luna",
            "USTC": "terrausd",
            "LUNA": "terra-luna-2",
            "FLR": "flare-networks",
            "SGB": "songbird",
            "CSPR": "casper-network",
            "ROSE": "oasis-network",
            "ZIL": "zilliqa",
            "ONE": "harmony",
            "QTUM": "qtum",
            "ICX": "icon",
            "ZEC": "zcash",
            "DASH": "dash",
            "DCR": "decred",
            "SC": "siacoin",
            "RVN": "ravencoin",
            "ZEN": "horizen",
            "BTG": "bitcoin-gold",
            "DGB": "digibyte",
            "WAVES": "waves",
            "ONT": "ontology",
            "IOST": "iostoken",
            "HOT": "holotoken",
            "RSR": "reserve-rights-token",
            "CELO": "celo",
            "SKL": "skale",
            "CTSI": "cartesi",
            "NKN": "nkn",
            "AR": "arweave",
            "HNT": "helium",
            "IOTX": "iotex",
            "KDA": "kadena",
            "FLUX": "zelcash",
            "TFUEL": "theta-fuel",
            "GLM": "golem",
            "STORJ": "storj",
            "BAT": "basic-attention-token",
            "CVC": "civic",
            "REQ": "request-network",
            "BAND": "band-protocol",
            "REN": "republic-protocol",
            "NMR": "numeraire",
            "MLN": "melon",
            "KNC": "kyber-network-crystal",
            "OGN": "origin-protocol",
            "CELR": "celer-network",
            "MTL": "metal",
            "POLS": "polkastarter",
            "ALICE": "my-neighbor-alice",
            "TLM": "alien-worlds",
            "ILV": "illuvium",
            "GODS": "gods-unchained",
            "IMX": "immutable-x",
            "MAGIC": "magic",
            "PRIME": "echelon-prime",
            "PIXEL": "pixels",
            "PORTAL": "portal-2",
            "RONIN": "ronin",
            "BEAM": "beam-2",
            "SUPER": "superfarm",
            "HIGH": "highstreet",
            "VOXEL": "voxies",
            "YGG": "yield-guild-games",
            "PYR": "vulcan-forged",
            "GAFI": "gamefi",
            "UFO": "ufo-gaming",
            "ATLAS": "star-atlas",
            "POLIS": "star-atlas-dao",
            "GMT": "stepn",
            "GST": "green-satoshi-token",
            "FITFI": "step-app-fitfi",
            "SWEAT": "sweatcoin",
            "C98": "coin98",
            "SFP": "safepal",
            "TWT": "trust-wallet-token",
            "BICO": "biconomy",
            "API3": "api3",
            "ACH": "alchemy-pay",
            "JASMY": "jasmycoin",
            "RAD": "radicle",
            "GTC": "gitcoin",
            "AUCTION": "auction",
            "RARE": "superrare",
            "LOOKS": "looksrare",
            "X2Y2": "x2y2",
            "SUDOSWAP": "sudoswap",
            "DEGO": "dego-finance",
            "PERP": "perpetual-protocol",
            "ZKS": "zkswap",
            "QUICK": "quickswap",
            "VELO": "velodrome-finance",
            "AERO": "aerodrome-finance",
            "JOE": "joe",
            "SPELL": "spell-token",
            "MIM": "magic-internet-money",
            "CVX": "convex-finance",
            "FXN": "f-x-protocol",
            "LQTY": "liquity",
            "RDNT": "radiant-capital",
            "GNS": "gains-network",
            "VELA": "vela-exchange",
            "HFT": "hashflow",
            "OSMO": "osmosis",
            "SCRT": "secret",
            "JUNO": "juno-network",
            "EVMOS": "evmos",
            "INJ": "injective-protocol",
            "KUJIRA": "kujira",
            "AKT": "akash-network",
            "KUJI": "kujira",
            "NTRN": "neutron-3",
            "DYM": "dymension",
            "MANTA": "manta-network",
            "ALT": "altlayer",
            "METIS": "metis-token",
            "CANTO": "canto",
            "BOBA": "boba-network",
            "MOVR": "moonriver",
            "GLMR": "moonbeam",
            "ASTR": "astar",
            "SDN": "shiden",
            "CFG": "centrifuge",
            "PARA": "parallel-finance",
            "NODL": "nodle-network",
            "PHA": "phala",
            "CLV": "clover-finance",
            "LIT": "litentry",
            "TRAC": "origintrail",
            "PEOPLE": "constitutiondao",
            "ENS": "ethereum-name-service",
            "ID": "space-id",
            "ARK": "ark",
            "LSK": "lisk",
            "STRAX": "stratis",
            "WAXP": "wax",
            "XNO": "nano",
            "HIVE": "hive",
            "STEEM": "steem",
            "LEO": "leo-token",
            "HT": "huobi-token",
            "GT": "gatechain-token",
            "KCS": "kucoin-shares",
            "MX": "mx-token",
            "BGB": "bitget-token",
            "WOO": "woo-network",
            "NEXO": "nexo",
            "CRO": "crypto-com-chain",
            "FTT": "ftx-token",
        }
    
    async def get_crypto_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current price for a cryptocurrency with fallback to Binance"""
        symbol = symbol.upper()
        
        # Check cache first
        cache_key = f"crypto_{symbol}"
        if cache_key in self.price_cache:
            cached = self.price_cache[cache_key]
            if datetime.now(timezone.utc) - cached["timestamp"] < timedelta(seconds=self.cache_ttl):
                return cached["data"]
        
        # Get CoinGecko ID
        coin_id = self.crypto_id_map.get(symbol, symbol.lower())
        
        # Try CoinGecko first
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
                
                # If CoinGecko rate limited (429), try Binance fallback
                if response.status_code == 429:
                    logger.warning(f"CoinGecko rate limited for {symbol}, trying Binance fallback")
                    return await self._get_binance_price(symbol, cache_key)
                        
        except Exception as e:
            logger.error(f"Error fetching crypto price for {symbol}: {e}")
            # Try Binance fallback on any error
            return await self._get_binance_price(symbol, cache_key)
        
        # If CoinGecko didn't have the coin, try Binance
        return await self._get_binance_price(symbol, cache_key)
    
    async def _get_binance_price(self, symbol: str, cache_key: str) -> Optional[Dict[str, Any]]:
        """Fallback price source using multiple APIs"""
        # Try Coinbase first (more accessible globally)
        result = await self._get_coinbase_price(symbol)
        if result:
            self.price_cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now(timezone.utc)
            }
            return result
        
        # Try KuCoin as second fallback
        result = await self._get_kucoin_price(symbol)
        if result:
            self.price_cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now(timezone.utc)
            }
            return result
        
        # Return cached data if available (even if stale)
        if cache_key in self.price_cache:
            cached = self.price_cache[cache_key]
            cached["data"]["stale"] = True
            return cached["data"]
        
        return None
    
    async def _get_coinbase_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get price from Coinbase API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Coinbase spot price endpoint
                response = await client.get(
                    f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    price = float(data.get("data", {}).get("amount", 0))
                    
                    if price > 0:
                        return {
                            "symbol": symbol,
                            "price": price,
                            "change_24h": 0,  # Coinbase spot doesn't include 24h change
                            "volume_24h": 0,
                            "market_cap": 0,
                            "source": "coinbase",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        
        except Exception as e:
            logger.error(f"Coinbase fallback failed for {symbol}: {e}")
        
        return None
    
    async def _get_kucoin_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get price from KuCoin API"""
        try:
            pair = f"{symbol}-USDT"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://api.kucoin.com/api/v1/market/stats",
                    params={"symbol": pair}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == "200000":
                        stats = data.get("data", {})
                        return {
                            "symbol": symbol,
                            "price": float(stats.get("last", 0)),
                            "change_24h": float(stats.get("changeRate", 0)) * 100,
                            "volume_24h": float(stats.get("volValue", 0)),
                            "market_cap": 0,
                            "source": "kucoin",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        
        except Exception as e:
            logger.error(f"KuCoin fallback failed for {symbol}: {e}")
        
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
