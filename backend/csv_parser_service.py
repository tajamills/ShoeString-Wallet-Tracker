"""
Exchange CSV Parser Service

Auto-detects and parses CSV exports from various cryptocurrency exchanges.
Supports: Coinbase, Binance, Kraken, Gemini, Crypto.com, KuCoin
"""

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ExchangeFormat(str, Enum):
    COINBASE = "coinbase"
    BINANCE = "binance"
    KRAKEN = "kraken"
    GEMINI = "gemini"
    CRYPTO_COM = "crypto_com"
    KUCOIN = "kucoin"
    UNKNOWN = "unknown"


# Column signatures for auto-detection
EXCHANGE_SIGNATURES = {
    ExchangeFormat.COINBASE: {
        "required": ["Timestamp", "Transaction Type", "Asset", "Quantity Transacted"],
        "optional": ["Spot Price at Transaction", "USD Subtotal"]
    },
    ExchangeFormat.BINANCE: {
        "required": ["Date(UTC)", "Pair", "Side", "Price", "Executed", "Amount"],
        "optional": ["Fee", "Total"]
    },
    ExchangeFormat.KRAKEN: {
        "required": ["txid", "refid", "time", "type", "asset", "amount"],
        "optional": ["fee", "balance"]
    },
    ExchangeFormat.GEMINI: {
        "required": ["Date", "Time (UTC)", "Type", "Symbol", "Amount"],
        "optional": ["Fee", "USD Amount"]
    },
    ExchangeFormat.CRYPTO_COM: {
        "required": ["Timestamp (UTC)", "Transaction Description", "Currency", "Amount"],
        "optional": ["Native Currency", "Native Amount"]
    },
    ExchangeFormat.KUCOIN: {
        "required": ["tradeCreatedAt", "symbol", "side", "price", "size"],
        "optional": ["fee", "feeCurrency"]
    }
}


class ExchangeTransaction:
    """Standardized transaction format"""
    def __init__(
        self,
        exchange: str,
        tx_id: str,
        tx_type: str,
        asset: str,
        amount: float,
        price_usd: Optional[float],
        total_usd: Optional[float],
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
        self.total_usd = total_usd
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
            "total_usd": self.total_usd,
            "fee": self.fee,
            "fee_asset": self.fee_asset,
            "timestamp": self.timestamp.isoformat(),
            "value_usd": self.total_usd or (self.amount * (self.price_usd or 0))
        }


class CSVParserService:
    """Service for parsing exchange CSV files"""
    
    def detect_exchange(self, headers: List[str]) -> ExchangeFormat:
        """Auto-detect exchange based on CSV column headers"""
        headers_lower = [h.lower().strip() for h in headers]
        headers_set = set(headers)
        
        for exchange, signature in EXCHANGE_SIGNATURES.items():
            required = signature["required"]
            # Check if all required columns are present
            if all(col in headers for col in required):
                return exchange
            # Also check lowercase
            if all(col.lower() in headers_lower for col in required):
                return exchange
        
        # Additional heuristics for common variations
        if any("coinbase" in h.lower() for h in headers):
            return ExchangeFormat.COINBASE
        if any("binance" in h.lower() for h in headers):
            return ExchangeFormat.BINANCE
        
        return ExchangeFormat.UNKNOWN
    
    def parse_csv(self, content: str, exchange_hint: Optional[str] = None) -> Tuple[ExchangeFormat, List[ExchangeTransaction]]:
        """
        Parse CSV content and return detected exchange + transactions
        
        Args:
            content: CSV file content as string
            exchange_hint: Optional hint for exchange type
        
        Returns:
            Tuple of (detected_exchange, list_of_transactions)
        """
        # Read CSV
        reader = csv.DictReader(io.StringIO(content))
        headers = reader.fieldnames or []
        
        if not headers:
            raise ValueError("CSV file appears to be empty or malformed")
        
        # Detect exchange
        if exchange_hint:
            try:
                exchange = ExchangeFormat(exchange_hint.lower())
            except ValueError:
                exchange = self.detect_exchange(headers)
        else:
            exchange = self.detect_exchange(headers)
        
        if exchange == ExchangeFormat.UNKNOWN:
            raise ValueError(
                f"Could not detect exchange format. Headers found: {', '.join(headers[:5])}... "
                "Supported exchanges: Coinbase, Binance, Kraken, Gemini, Crypto.com, KuCoin"
            )
        
        # Parse based on detected exchange
        rows = list(reader)
        
        parser_map = {
            ExchangeFormat.COINBASE: self._parse_coinbase,
            ExchangeFormat.BINANCE: self._parse_binance,
            ExchangeFormat.KRAKEN: self._parse_kraken,
            ExchangeFormat.GEMINI: self._parse_gemini,
            ExchangeFormat.CRYPTO_COM: self._parse_crypto_com,
            ExchangeFormat.KUCOIN: self._parse_kucoin,
        }
        
        parser = parser_map.get(exchange)
        if not parser:
            raise ValueError(f"No parser available for {exchange}")
        
        transactions = parser(rows, headers)
        return exchange, transactions
    
    def _parse_coinbase(self, rows: List[Dict], headers: List[str]) -> List[ExchangeTransaction]:
        """Parse Coinbase CSV format"""
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                # Coinbase format: Timestamp, Transaction Type, Asset, Quantity Transacted, Spot Price, Subtotal
                timestamp_str = row.get("Timestamp", "")
                tx_type = row.get("Transaction Type", "").lower()
                asset = row.get("Asset", "")
                amount = self._parse_float(row.get("Quantity Transacted", "0"))
                spot_price = self._parse_float(row.get("Spot Price at Transaction", "0"))
                subtotal = self._parse_float(row.get("USD Subtotal", "") or row.get("Subtotal", "0"))
                fees = self._parse_float(row.get("Fees and/or Spread", "") or row.get("Fees", "0"))
                
                # Parse timestamp
                timestamp = self._parse_timestamp(timestamp_str)
                
                # Map transaction types
                type_map = {
                    "buy": "buy",
                    "sell": "sell",
                    "send": "send",
                    "receive": "receive",
                    "convert": "trade",
                    "rewards income": "reward",
                    "coinbase earn": "reward",
                    "staking income": "staking"
                }
                std_type = type_map.get(tx_type, tx_type)
                
                if not asset or amount == 0:
                    continue
                
                transactions.append(ExchangeTransaction(
                    exchange="coinbase",
                    tx_id=f"cb_{i}_{timestamp.timestamp() if timestamp else i}",
                    tx_type=std_type,
                    asset=asset,
                    amount=abs(amount),
                    price_usd=spot_price if spot_price else None,
                    total_usd=abs(subtotal) if subtotal else None,
                    fee=abs(fees),
                    fee_asset="USD",
                    timestamp=timestamp or datetime.now(timezone.utc),
                    raw_data=row
                ))
            except Exception as e:
                logger.warning(f"Error parsing Coinbase row {i}: {e}")
                continue
        
        return transactions
    
    def _parse_binance(self, rows: List[Dict], headers: List[str]) -> List[ExchangeTransaction]:
        """Parse Binance CSV format"""
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                # Binance format: Date(UTC), Pair, Side, Price, Executed, Amount, Fee
                timestamp_str = row.get("Date(UTC)", "") or row.get("Date", "")
                pair = row.get("Pair", "") or row.get("Market", "")
                side = row.get("Side", "").lower()
                price = self._parse_float(row.get("Price", "0"))
                executed = self._parse_float(row.get("Executed", "") or row.get("Filled", "0"))
                amount = self._parse_float(row.get("Amount", "") or row.get("Total", "0"))
                fee = self._parse_float(row.get("Fee", "0"))
                fee_asset = row.get("Fee Coin", "") or row.get("Fee Currency", "")
                
                # Extract base asset from pair (e.g., BTCUSDT -> BTC)
                asset = pair.replace("USDT", "").replace("USD", "").replace("BUSD", "")[:5]
                
                timestamp = self._parse_timestamp(timestamp_str)
                
                if not asset or executed == 0:
                    continue
                
                transactions.append(ExchangeTransaction(
                    exchange="binance",
                    tx_id=f"bn_{i}_{timestamp.timestamp() if timestamp else i}",
                    tx_type="buy" if side == "buy" else "sell",
                    asset=asset,
                    amount=abs(executed),
                    price_usd=price if "USD" in pair else None,
                    total_usd=abs(amount) if "USD" in pair else None,
                    fee=abs(fee),
                    fee_asset=fee_asset or asset,
                    timestamp=timestamp or datetime.now(timezone.utc),
                    raw_data=row
                ))
            except Exception as e:
                logger.warning(f"Error parsing Binance row {i}: {e}")
                continue
        
        return transactions
    
    def _parse_kraken(self, rows: List[Dict], headers: List[str]) -> List[ExchangeTransaction]:
        """Parse Kraken CSV format"""
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                tx_id = row.get("txid", f"kr_{i}")
                timestamp_str = row.get("time", "")
                tx_type = row.get("type", "").lower()
                asset = row.get("asset", "")
                amount = self._parse_float(row.get("amount", "0"))
                fee = self._parse_float(row.get("fee", "0"))
                
                # Clean up Kraken asset names (XXBT -> BTC, XETH -> ETH)
                asset = asset.replace("XXBT", "BTC").replace("XETH", "ETH").replace("ZUSD", "USD")
                if asset.startswith("X") or asset.startswith("Z"):
                    asset = asset[1:]
                
                timestamp = self._parse_timestamp(timestamp_str)
                
                type_map = {
                    "trade": "trade",
                    "deposit": "deposit",
                    "withdrawal": "withdrawal",
                    "staking": "staking",
                    "transfer": "transfer"
                }
                std_type = type_map.get(tx_type, tx_type)
                
                if not asset or amount == 0:
                    continue
                
                transactions.append(ExchangeTransaction(
                    exchange="kraken",
                    tx_id=tx_id,
                    tx_type=std_type,
                    asset=asset,
                    amount=abs(amount),
                    price_usd=None,
                    total_usd=None,
                    fee=abs(fee),
                    fee_asset=asset,
                    timestamp=timestamp or datetime.now(timezone.utc),
                    raw_data=row
                ))
            except Exception as e:
                logger.warning(f"Error parsing Kraken row {i}: {e}")
                continue
        
        return transactions
    
    def _parse_gemini(self, rows: List[Dict], headers: List[str]) -> List[ExchangeTransaction]:
        """Parse Gemini CSV format"""
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                date_str = row.get("Date", "")
                time_str = row.get("Time (UTC)", "")
                tx_type = row.get("Type", "").lower()
                symbol = row.get("Symbol", "")
                amount = self._parse_float(row.get("Amount", "0"))
                fee = self._parse_float(row.get("Fee", "") or row.get("Fee (USD)", "0"))
                usd_amount = self._parse_float(row.get("USD Amount", "") or row.get("USD", "0"))
                
                timestamp_str = f"{date_str} {time_str}".strip()
                timestamp = self._parse_timestamp(timestamp_str)
                
                # Extract asset from symbol (e.g., BTCUSD -> BTC)
                asset = symbol.replace("USD", "")[:5] if symbol else ""
                
                type_map = {
                    "buy": "buy",
                    "sell": "sell",
                    "credit": "deposit",
                    "debit": "withdrawal"
                }
                std_type = type_map.get(tx_type, tx_type)
                
                if not asset or amount == 0:
                    continue
                
                transactions.append(ExchangeTransaction(
                    exchange="gemini",
                    tx_id=f"gm_{i}_{timestamp.timestamp() if timestamp else i}",
                    tx_type=std_type,
                    asset=asset,
                    amount=abs(amount),
                    price_usd=abs(usd_amount / amount) if amount else None,
                    total_usd=abs(usd_amount) if usd_amount else None,
                    fee=abs(fee),
                    fee_asset="USD",
                    timestamp=timestamp or datetime.now(timezone.utc),
                    raw_data=row
                ))
            except Exception as e:
                logger.warning(f"Error parsing Gemini row {i}: {e}")
                continue
        
        return transactions
    
    def _parse_crypto_com(self, rows: List[Dict], headers: List[str]) -> List[ExchangeTransaction]:
        """Parse Crypto.com CSV format"""
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                timestamp_str = row.get("Timestamp (UTC)", "")
                description = row.get("Transaction Description", "")
                asset = row.get("Currency", "")
                amount = self._parse_float(row.get("Amount", "0"))
                native_amount = self._parse_float(row.get("Native Amount", "0"))
                
                timestamp = self._parse_timestamp(timestamp_str)
                
                # Determine type from description
                desc_lower = description.lower()
                if "buy" in desc_lower:
                    tx_type = "buy"
                elif "sell" in desc_lower:
                    tx_type = "sell"
                elif "deposit" in desc_lower or "transfer in" in desc_lower:
                    tx_type = "deposit"
                elif "withdraw" in desc_lower or "transfer out" in desc_lower:
                    tx_type = "withdrawal"
                elif "reward" in desc_lower or "cashback" in desc_lower:
                    tx_type = "reward"
                elif "staking" in desc_lower:
                    tx_type = "staking"
                else:
                    tx_type = "other"
                
                if not asset or amount == 0:
                    continue
                
                transactions.append(ExchangeTransaction(
                    exchange="crypto_com",
                    tx_id=f"cdc_{i}_{timestamp.timestamp() if timestamp else i}",
                    tx_type=tx_type,
                    asset=asset,
                    amount=abs(amount),
                    price_usd=abs(native_amount / amount) if amount and native_amount else None,
                    total_usd=abs(native_amount) if native_amount else None,
                    fee=0,
                    fee_asset="USD",
                    timestamp=timestamp or datetime.now(timezone.utc),
                    raw_data=row
                ))
            except Exception as e:
                logger.warning(f"Error parsing Crypto.com row {i}: {e}")
                continue
        
        return transactions
    
    def _parse_kucoin(self, rows: List[Dict], headers: List[str]) -> List[ExchangeTransaction]:
        """Parse KuCoin CSV format"""
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                timestamp_str = row.get("tradeCreatedAt", "") or row.get("Time", "")
                symbol = row.get("symbol", "") or row.get("Symbol", "")
                side = row.get("side", "").lower() or row.get("Side", "").lower()
                price = self._parse_float(row.get("price", "") or row.get("Price", "0"))
                size = self._parse_float(row.get("size", "") or row.get("Amount", "0"))
                fee = self._parse_float(row.get("fee", "") or row.get("Fee", "0"))
                fee_currency = row.get("feeCurrency", "") or row.get("Fee Currency", "")
                
                timestamp = self._parse_timestamp(timestamp_str)
                
                # Extract asset from symbol (e.g., BTC-USDT -> BTC)
                asset = symbol.split("-")[0] if "-" in symbol else symbol[:5]
                
                if not asset or size == 0:
                    continue
                
                transactions.append(ExchangeTransaction(
                    exchange="kucoin",
                    tx_id=f"kc_{i}_{timestamp.timestamp() if timestamp else i}",
                    tx_type="buy" if side == "buy" else "sell",
                    asset=asset,
                    amount=abs(size),
                    price_usd=price if "USDT" in symbol or "USD" in symbol else None,
                    total_usd=abs(size * price) if price and ("USDT" in symbol or "USD" in symbol) else None,
                    fee=abs(fee),
                    fee_asset=fee_currency or asset,
                    timestamp=timestamp or datetime.now(timezone.utc),
                    raw_data=row
                ))
            except Exception as e:
                logger.warning(f"Error parsing KuCoin row {i}: {e}")
                continue
        
        return transactions
    
    def _parse_float(self, value: str) -> float:
        """Safely parse float from string"""
        if not value:
            return 0.0
        try:
            # Remove currency symbols, commas, whitespace
            cleaned = str(value).replace("$", "").replace(",", "").replace(" ", "").strip()
            if cleaned in ["", "-", "N/A", "n/a"]:
                return 0.0
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_timestamp(self, value: str) -> Optional[datetime]:
        """Parse timestamp from various formats"""
        if not value:
            return None
        
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S UTC",
            "%Y-%m-%d %H:%M:%S%z",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(value.strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        
        # Try ISO format as fallback
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
        
        return None
    
    def get_supported_exchanges(self) -> List[Dict[str, str]]:
        """Return list of supported exchanges with export instructions"""
        return [
            {
                "id": "coinbase",
                "name": "Coinbase",
                "instructions": "Go to Coinbase → Settings → Statements → Generate Report → Transaction History CSV"
            },
            {
                "id": "binance",
                "name": "Binance",
                "instructions": "Go to Binance → Orders → Trade History → Export Complete Trade History"
            },
            {
                "id": "kraken",
                "name": "Kraken",
                "instructions": "Go to Kraken → History → Export → Select Ledgers or Trades"
            },
            {
                "id": "gemini",
                "name": "Gemini",
                "instructions": "Go to Gemini → Account → Statements → Download Trade History CSV"
            },
            {
                "id": "crypto_com",
                "name": "Crypto.com",
                "instructions": "Go to Crypto.com App → Accounts → Transaction History → Export"
            },
            {
                "id": "kucoin",
                "name": "KuCoin",
                "instructions": "Go to KuCoin → Orders → Trade History → Export"
            }
        ]


# Singleton instance
csv_parser_service = CSVParserService()
