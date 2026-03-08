"""
Exchange Integration Service for Crypto Bag Tracker

This module provides integration with cryptocurrency exchanges (Coinbase, Binance)
to import trade history, deposits, withdrawals, and account balances for tax tracking.
"""

import os
import logging
import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from enum import Enum
import requests

logger = logging.getLogger(__name__)


class ExchangeType(str, Enum):
    """Supported exchange types"""
    COINBASE = "coinbase"
    BINANCE = "binance"


class ExchangeTransaction:
    """Standardized transaction format across exchanges"""
    def __init__(
        self,
        exchange: str,
        tx_id: str,
        tx_type: str,  # buy, sell, send, receive, deposit, withdrawal
        asset: str,
        amount: float,
        price_usd: Optional[float],
        fee: float,
        fee_asset: str,
        timestamp: datetime,
        raw_data: Dict[str, Any]
    ):
        self.exchange = exchange
        self.tx_id = tx_id
        self.tx_type = tx_type
        self.asset = asset
        self.amount = amount
        self.price_usd = price_usd
        self.fee = fee
        self.fee_asset = fee_asset
        self.timestamp = timestamp
        self.raw_data = raw_data

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "tx_id": self.tx_id,
            "tx_type": self.tx_type,
            "asset": self.asset,
            "amount": self.amount,
            "price_usd": self.price_usd,
            "fee": self.fee,
            "fee_asset": self.fee_asset,
            "timestamp": self.timestamp.isoformat(),
            "value_usd": self.amount * (self.price_usd or 0)
        }


class CoinbaseClient:
    """
    Coinbase OAuth2 API Client
    
    Note: This client requires OAuth2 tokens obtained through the OAuth flow.
    Users must authenticate via Coinbase OAuth to grant access to their accounts.
    """
    
    BASE_URL = "https://api.coinbase.com"
    
    def __init__(self, access_token: str):
        self.access_token = access_token
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make authenticated request to Coinbase API"""
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "CB-VERSION": "2024-01-01"
        }
        
        try:
            response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Coinbase API error: {e}")
            raise
    
    def get_accounts(self) -> List[Dict]:
        """Get list of user's accounts with balances"""
        response = self._make_request("GET", "/v2/accounts?limit=100")
        return response.get("data", [])
    
    def get_transactions(self, account_id: str, limit: int = 100) -> List[Dict]:
        """Get transactions for an account"""
        response = self._make_request(
            "GET", 
            f"/v2/accounts/{account_id}/transactions?limit={limit}"
        )
        return response.get("data", [])
    
    def get_all_transactions(self) -> List[ExchangeTransaction]:
        """Get all transactions across all accounts"""
        all_transactions = []
        accounts = self.get_accounts()
        
        for account in accounts:
            account_id = account.get("id")
            currency = account.get("currency", {}).get("code", "UNKNOWN")
            
            try:
                transactions = self.get_transactions(account_id)
                
                for tx in transactions:
                    tx_type = tx.get("type", "unknown")
                    amount_data = tx.get("amount", {})
                    native_amount = tx.get("native_amount", {})
                    
                    # Map Coinbase transaction types to our standard types
                    type_map = {
                        "buy": "buy",
                        "sell": "sell",
                        "send": "send",
                        "receive": "receive",
                        "fiat_deposit": "deposit",
                        "fiat_withdrawal": "withdrawal",
                        "trade": "trade"
                    }
                    
                    std_type = type_map.get(tx_type, tx_type)
                    
                    # Parse timestamp
                    created_at = tx.get("created_at", "")
                    try:
                        timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        timestamp = datetime.now(timezone.utc)
                    
                    # Get USD value if available
                    price_usd = None
                    if native_amount.get("currency") == "USD":
                        try:
                            total_usd = abs(float(native_amount.get("amount", 0)))
                            amount = abs(float(amount_data.get("amount", 0)))
                            if amount > 0:
                                price_usd = total_usd / amount
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                    
                    exchange_tx = ExchangeTransaction(
                        exchange="coinbase",
                        tx_id=tx.get("id", ""),
                        tx_type=std_type,
                        asset=amount_data.get("currency", currency),
                        amount=abs(float(amount_data.get("amount", 0))),
                        price_usd=price_usd,
                        fee=0.0,  # Fee info might be in details
                        fee_asset="USD",
                        timestamp=timestamp,
                        raw_data=tx
                    )
                    all_transactions.append(exchange_tx)
                    
            except Exception as e:
                logger.error(f"Error fetching transactions for account {account_id}: {e}")
                continue
        
        return sorted(all_transactions, key=lambda x: x.timestamp, reverse=True)


class BinanceClient:
    """
    Binance API Client with HMAC authentication
    
    Requires API Key and Secret from Binance account.
    """
    
    BASE_URL = "https://api.binance.com"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        return int(time.time() * 1000)
    
    def _sign(self, params: str) -> str:
        """Generate HMAC SHA256 signature"""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, method: str, endpoint: str, signed: bool = True, **kwargs) -> Any:
        """Make authenticated request to Binance API"""
        url = f"{self.BASE_URL}{endpoint}"
        headers = {"X-MBX-APIKEY": self.api_key}
        
        params = kwargs.get("params", {})
        
        if signed:
            params["timestamp"] = self._get_timestamp()
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            params["signature"] = self._sign(query_string)
        
        try:
            response = requests.request(
                method, url, headers=headers, params=params, timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Binance API error: {e}")
            raise
    
    def get_account(self) -> Dict:
        """Get account information including balances"""
        return self._make_request("GET", "/api/v3/account")
    
    def get_my_trades(self, symbol: str, limit: int = 500) -> List[Dict]:
        """Get trade history for a specific symbol"""
        return self._make_request(
            "GET", 
            "/api/v3/myTrades",
            params={"symbol": symbol, "limit": limit}
        )
    
    def get_deposit_history(self) -> List[Dict]:
        """Get deposit history"""
        return self._make_request("GET", "/sapi/v1/capital/deposit/hisrec")
    
    def get_withdrawal_history(self) -> List[Dict]:
        """Get withdrawal history"""
        return self._make_request("GET", "/sapi/v1/capital/withdraw/history")
    
    def get_all_transactions(self) -> List[ExchangeTransaction]:
        """Get all transactions (trades, deposits, withdrawals)"""
        all_transactions = []
        
        # Get account info for active symbols
        try:
            account = self.get_account()
            balances = account.get("balances", [])
            
            # Get list of assets with balance or history
            active_assets = set()
            for balance in balances:
                if float(balance.get("free", 0)) > 0 or float(balance.get("locked", 0)) > 0:
                    active_assets.add(balance.get("asset"))
            
            # Common trading pairs to check
            common_pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", "DOTUSDT"]
            
            # Get trades for common pairs
            for symbol in common_pairs:
                try:
                    trades = self.get_my_trades(symbol)
                    
                    for trade in trades:
                        is_buyer = trade.get("isBuyer", False)
                        timestamp = datetime.fromtimestamp(
                            trade.get("time", 0) / 1000, 
                            tz=timezone.utc
                        )
                        
                        # Parse symbol to get base and quote asset
                        base_asset = symbol.replace("USDT", "").replace("BTC", "").replace("ETH", "")
                        if not base_asset:
                            base_asset = symbol[:3]
                        
                        exchange_tx = ExchangeTransaction(
                            exchange="binance",
                            tx_id=str(trade.get("id", "")),
                            tx_type="buy" if is_buyer else "sell",
                            asset=base_asset,
                            amount=float(trade.get("qty", 0)),
                            price_usd=float(trade.get("price", 0)),  # Price in quote asset
                            fee=float(trade.get("commission", 0)),
                            fee_asset=trade.get("commissionAsset", ""),
                            timestamp=timestamp,
                            raw_data=trade
                        )
                        all_transactions.append(exchange_tx)
                        
                except Exception as e:
                    logger.debug(f"No trades found for {symbol}: {e}")
                    continue
            
            # Get deposits
            try:
                deposits = self.get_deposit_history()
                for deposit in deposits:
                    timestamp = datetime.fromtimestamp(
                        deposit.get("insertTime", 0) / 1000,
                        tz=timezone.utc
                    )
                    
                    exchange_tx = ExchangeTransaction(
                        exchange="binance",
                        tx_id=deposit.get("txId", ""),
                        tx_type="deposit",
                        asset=deposit.get("coin", ""),
                        amount=float(deposit.get("amount", 0)),
                        price_usd=None,
                        fee=0.0,
                        fee_asset="",
                        timestamp=timestamp,
                        raw_data=deposit
                    )
                    all_transactions.append(exchange_tx)
            except Exception as e:
                logger.debug(f"Could not fetch deposits: {e}")
            
            # Get withdrawals
            try:
                withdrawals = self.get_withdrawal_history()
                for withdrawal in withdrawals:
                    timestamp = datetime.fromisoformat(
                        withdrawal.get("applyTime", "").replace("Z", "+00:00")
                    ) if withdrawal.get("applyTime") else datetime.now(timezone.utc)
                    
                    exchange_tx = ExchangeTransaction(
                        exchange="binance",
                        tx_id=withdrawal.get("id", ""),
                        tx_type="withdrawal",
                        asset=withdrawal.get("coin", ""),
                        amount=float(withdrawal.get("amount", 0)),
                        price_usd=None,
                        fee=float(withdrawal.get("transactionFee", 0)),
                        fee_asset=withdrawal.get("coin", ""),
                        timestamp=timestamp,
                        raw_data=withdrawal
                    )
                    all_transactions.append(exchange_tx)
            except Exception as e:
                logger.debug(f"Could not fetch withdrawals: {e}")
                
        except Exception as e:
            logger.error(f"Error fetching Binance transactions: {e}")
        
        return sorted(all_transactions, key=lambda x: x.timestamp, reverse=True)


class ExchangeService:
    """
    Main service for managing exchange integrations
    """
    
    def __init__(self):
        pass
    
    def connect_coinbase(self, access_token: str) -> CoinbaseClient:
        """Connect to Coinbase with OAuth token"""
        return CoinbaseClient(access_token)
    
    def connect_binance(self, api_key: str, api_secret: str) -> BinanceClient:
        """Connect to Binance with API credentials"""
        return BinanceClient(api_key, api_secret)
    
    def get_combined_transactions(
        self,
        coinbase_token: Optional[str] = None,
        binance_key: Optional[str] = None,
        binance_secret: Optional[str] = None
    ) -> List[Dict]:
        """
        Get combined transactions from all connected exchanges
        """
        all_transactions = []
        
        if coinbase_token:
            try:
                client = self.connect_coinbase(coinbase_token)
                transactions = client.get_all_transactions()
                all_transactions.extend([tx.to_dict() for tx in transactions])
                logger.info(f"Fetched {len(transactions)} transactions from Coinbase")
            except Exception as e:
                logger.error(f"Error fetching Coinbase transactions: {e}")
        
        if binance_key and binance_secret:
            try:
                client = self.connect_binance(binance_key, binance_secret)
                transactions = client.get_all_transactions()
                all_transactions.extend([tx.to_dict() for tx in transactions])
                logger.info(f"Fetched {len(transactions)} transactions from Binance")
            except Exception as e:
                logger.error(f"Error fetching Binance transactions: {e}")
        
        # Sort all transactions by timestamp
        all_transactions.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return all_transactions
    
    def calculate_exchange_summary(self, transactions: List[Dict]) -> Dict:
        """
        Calculate summary statistics from exchange transactions
        """
        summary = {
            "total_transactions": len(transactions),
            "by_exchange": {},
            "by_type": {},
            "by_asset": {},
            "total_fees_usd": 0.0
        }
        
        for tx in transactions:
            exchange = tx.get("exchange", "unknown")
            tx_type = tx.get("tx_type", "unknown")
            asset = tx.get("asset", "unknown")
            
            # By exchange
            if exchange not in summary["by_exchange"]:
                summary["by_exchange"][exchange] = {"count": 0, "volume_usd": 0}
            summary["by_exchange"][exchange]["count"] += 1
            summary["by_exchange"][exchange]["volume_usd"] += tx.get("value_usd", 0)
            
            # By type
            if tx_type not in summary["by_type"]:
                summary["by_type"][tx_type] = 0
            summary["by_type"][tx_type] += 1
            
            # By asset
            if asset not in summary["by_asset"]:
                summary["by_asset"][asset] = {"buys": 0, "sells": 0, "total": 0}
            summary["by_asset"][asset]["total"] += 1
            if tx_type == "buy":
                summary["by_asset"][asset]["buys"] += 1
            elif tx_type == "sell":
                summary["by_asset"][asset]["sells"] += 1
            
            # Fees
            if tx.get("fee"):
                summary["total_fees_usd"] += tx.get("fee", 0)
        
        return summary


# Singleton instance
exchange_service = ExchangeService()
