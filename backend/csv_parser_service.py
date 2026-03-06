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
# Each exchange can have multiple signature sets to handle format variations
EXCHANGE_SIGNATURES = {
    ExchangeFormat.COINBASE: {
        # Classic Coinbase format
        "required": ["Timestamp", "Transaction Type", "Asset", "Quantity Transacted"],
        "optional": ["Spot Price at Transaction", "USD Subtotal"],
        # Alternative Coinbase formats (newer exports have different column names)
        "alt_signatures": [
            # Format 2: Transaction ID based
            ["Transaction ID", "Transaction Type", "Asset Acquired", "Quantity Acquired"],
            # Format 3: Date & time based (user reported)
            ["Transaction ID", "Date & time", "Asset Acquired", "Quantity Acquired (a)"],
            # Format 4: Simpler variation
            ["Date", "Transaction Type", "Asset", "Quantity"],
        ]
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
    
    def detect_exchange(self, headers: List[str]) -> Tuple[ExchangeFormat, str]:
        """
        Auto-detect exchange based on CSV column headers
        
        Returns:
            Tuple of (ExchangeFormat, format_variant)
            format_variant can be: 'primary', 'alt_1', 'alt_2', etc.
        """
        headers_lower = [h.lower().strip() for h in headers]
        
        for exchange, signature in EXCHANGE_SIGNATURES.items():
            # Check primary required columns
            required = signature.get("required", [])
            if required:
                if all(col in headers for col in required):
                    return exchange, "primary"
                # Also check lowercase
                if all(col.lower() in headers_lower for col in required):
                    return exchange, "primary"
            
            # Check alternative signatures
            alt_signatures = signature.get("alt_signatures", [])
            for idx, alt_required in enumerate(alt_signatures):
                if all(col in headers for col in alt_required):
                    return exchange, f"alt_{idx + 1}"
                # Also check lowercase
                if all(col.lower() in headers_lower for col in alt_required):
                    return exchange, f"alt_{idx + 1}"
        
        # Additional heuristics for common variations
        # Look for exchange-specific markers in headers
        if any("coinbase" in h.lower() for h in headers):
            return ExchangeFormat.COINBASE, "heuristic"
        if any("binance" in h.lower() for h in headers):
            return ExchangeFormat.BINANCE, "heuristic"
        
        # Coinbase often has these columns in various formats
        coinbase_markers = ["asset acquired", "asset sold", "quantity acquired", "quantity sold", "usd value"]
        if sum(1 for marker in coinbase_markers if any(marker in h.lower() for h in headers)) >= 2:
            return ExchangeFormat.COINBASE, "heuristic"
        
        return ExchangeFormat.UNKNOWN, ""
    
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
        
        # Detect exchange and format variant
        format_variant = "primary"
        if exchange_hint:
            try:
                exchange = ExchangeFormat(exchange_hint.lower())
            except ValueError:
                exchange, format_variant = self.detect_exchange(headers)
        else:
            exchange, format_variant = self.detect_exchange(headers)
        
        if exchange == ExchangeFormat.UNKNOWN:
            # Provide helpful error with actual headers for debugging
            raise ValueError(
                f"Could not detect exchange format. Headers found: {', '.join(headers[:10])}... "
                "Supported exchanges: Coinbase, Binance, Kraken, Gemini, Crypto.com, KuCoin. "
                "Please ensure your CSV export is from one of these exchanges."
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
        
        # Pass format_variant to parser for exchanges with multiple formats
        transactions = parser(rows, headers, format_variant)
        return exchange, transactions
    
    def _parse_coinbase(self, rows: List[Dict], headers: List[str], format_variant: str = "primary") -> List[ExchangeTransaction]:
        """Parse Coinbase CSV format - supports multiple export formats"""
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                # Try to detect format based on available columns
                # Format 1: Classic Coinbase (Timestamp, Transaction Type, Asset, Quantity Transacted)
                if "Timestamp" in row or "timestamp" in [k.lower() for k in row.keys()]:
                    tx = self._parse_coinbase_classic(row, i)
                # Format 2: Newer Coinbase (Date & time, Asset Acquired/Sold, Quantity Acquired/Sold)
                elif any(k for k in row.keys() if "date & time" in k.lower() or "date &amp; time" in k.lower()):
                    tx = self._parse_coinbase_modern(row, i)
                # Format 3: Alternative format with Transaction ID
                elif "Transaction ID" in row or any("transaction id" in k.lower() for k in row.keys()):
                    tx = self._parse_coinbase_txid_format(row, i)
                # Format 4: Simple date format
                elif "Date" in row:
                    tx = self._parse_coinbase_simple(row, i)
                else:
                    # Try modern format as fallback (most common new export)
                    tx = self._parse_coinbase_modern(row, i)
                
                if tx:
                    transactions.append(tx)
                    
            except Exception as e:
                logger.warning(f"Error parsing Coinbase row {i}: {e}")
                continue
        
        return transactions
    
    def _parse_coinbase_classic(self, row: Dict, idx: int) -> Optional[ExchangeTransaction]:
        """Parse classic Coinbase format (Timestamp, Transaction Type, Asset, Quantity Transacted)"""
        # Get values with case-insensitive key lookup
        def get_val(keys):
            for k in keys:
                if k in row:
                    return row[k]
                for row_key in row.keys():
                    if row_key.lower() == k.lower():
                        return row[row_key]
            return ""
        
        timestamp_str = get_val(["Timestamp", "timestamp"])
        tx_type = get_val(["Transaction Type", "transaction type"]).lower()
        asset = get_val(["Asset", "asset"])
        amount = self._parse_float(get_val(["Quantity Transacted", "quantity transacted"]))
        spot_price = self._parse_float(get_val(["Spot Price at Transaction", "spot price at transaction", "Spot Price Currency", "USD Spot Price at Transaction"]))
        subtotal = self._parse_float(get_val(["USD Subtotal", "Subtotal", "subtotal"]))
        fees = self._parse_float(get_val(["Fees and/or Spread", "Fees", "fees"]))
        
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
            "staking income": "staking",
            "learning reward": "reward",
            "advanced trade buy": "buy",
            "advanced trade sell": "sell",
        }
        std_type = type_map.get(tx_type, tx_type)
        
        if not asset or amount == 0:
            return None
        
        return ExchangeTransaction(
            exchange="coinbase",
            tx_id=f"cb_{idx}_{timestamp.timestamp() if timestamp else idx}",
            tx_type=std_type,
            asset=asset,
            amount=abs(amount),
            price_usd=spot_price if spot_price else None,
            total_usd=abs(subtotal) if subtotal else None,
            fee=abs(fees),
            fee_asset="USD",
            timestamp=timestamp or datetime.now(timezone.utc),
            raw_data=row
        )
    
    def _parse_coinbase_modern(self, row: Dict, idx: int) -> Optional[ExchangeTransaction]:
        """
        Parse modern Coinbase format with Asset Acquired/Sold columns
        Headers like: Transaction ID, Date & time, Asset Acquired, Quantity Acquired (a), 
                      Asset Sold, Quantity Sold (s), USD Value
        """
        def get_val(keys):
            for k in keys:
                if k in row:
                    return row[k]
                for row_key in row.keys():
                    if k.lower() in row_key.lower():
                        return row[row_key]
            return ""
        
        # Get timestamp
        timestamp_str = get_val(["Date & time", "Date &amp; time", "Date", "Timestamp"])
        timestamp = self._parse_timestamp(timestamp_str)
        
        # Get transaction ID
        tx_id = get_val(["Transaction ID", "ID"]) or f"cb_{idx}_{timestamp.timestamp() if timestamp else idx}"
        
        # Determine if this is a buy or sell based on which columns have values
        asset_acquired = get_val(["Asset Acquired", "Asset acquired"])
        qty_acquired = self._parse_float(get_val(["Quantity Acquired (a)", "Quantity Acquired", "Qty Acquired"]))
        asset_sold = get_val(["Asset Sold", "Asset sold"])
        qty_sold = self._parse_float(get_val(["Quantity Sold (s)", "Quantity Sold", "Qty Sold"]))
        
        # USD value
        usd_value = self._parse_float(get_val(["USD Value", "Value", "USD", "Total"]))
        
        # Transaction type hint
        tx_type_hint = get_val(["Transaction Type", "Type", "transaction type"]).lower()
        
        # Fees
        fees = self._parse_float(get_val(["Fees", "Fee", "Fees and/or Spread"]))
        
        # Normalize asset names for comparison
        asset_acquired_upper = asset_acquired.upper() if asset_acquired else ""
        asset_sold_upper = asset_sold.upper() if asset_sold else ""
        
        # Priority: Focus on the crypto asset, not USD/stablecoins
        stablecoins = ["USD", "USDC", "USDT", "BUSD", "DAI", "GUSD", "PAX", "TUSD"]
        
        # Determine transaction type and primary asset
        # Rule: If selling crypto for USD/stablecoin = SELL
        #       If buying crypto with USD/stablecoin = BUY
        #       If swapping crypto for crypto = TRADE (track the sold asset)
        
        if qty_sold > 0 and asset_sold_upper and asset_sold_upper not in stablecoins:
            # Selling a crypto asset (not a stablecoin) - this is a SELL
            asset = asset_sold
            amount = qty_sold
            
            if tx_type_hint in ["send"]:
                tx_type = "send"
            else:
                tx_type = "sell"
            
            price_usd = usd_value / amount if amount > 0 and usd_value else None
            
        elif qty_acquired > 0 and asset_acquired_upper and asset_acquired_upper not in stablecoins:
            # Acquiring a crypto asset (not a stablecoin) - this is a BUY
            asset = asset_acquired
            amount = qty_acquired
            
            if tx_type_hint in ["receive", "reward", "staking income", "learning reward", "staking_income", "learning_reward"]:
                tx_type = tx_type_hint.replace(" ", "_")
            else:
                tx_type = "buy"
            
            price_usd = usd_value / amount if amount > 0 and usd_value else None
            
        elif qty_acquired > 0 and asset_acquired:
            # Fallback: acquiring something (could be stablecoin)
            asset = asset_acquired
            amount = qty_acquired
            tx_type = "buy"
            price_usd = usd_value / amount if amount > 0 and usd_value else None
            
        elif qty_sold > 0 and asset_sold:
            # Fallback: selling something
            asset = asset_sold
            amount = qty_sold
            tx_type = "sell"
            price_usd = usd_value / amount if amount > 0 and usd_value else None
            
        else:
            # Try fallback parsing
            asset = get_val(["Asset", "Currency", "Crypto"])
            amount = self._parse_float(get_val(["Quantity", "Amount", "Qty"]))
            tx_type = tx_type_hint or "unknown"
            price_usd = None
            
            if not asset or amount == 0:
                return None
        
        # Skip if no meaningful data
        if not asset or amount == 0:
            return None
        
        return ExchangeTransaction(
            exchange="coinbase",
            tx_id=tx_id,
            tx_type=tx_type,
            asset=asset.upper() if asset else "",
            amount=abs(amount),
            price_usd=price_usd,
            total_usd=abs(usd_value) if usd_value else None,
            fee=abs(fees),
            fee_asset="USD",
            timestamp=timestamp or datetime.now(timezone.utc),
            raw_data=row
        )
    
    def _parse_coinbase_txid_format(self, row: Dict, idx: int) -> Optional[ExchangeTransaction]:
        """Parse Coinbase format with Transaction ID as primary identifier"""
        # This format overlaps with modern, delegate to modern parser
        return self._parse_coinbase_modern(row, idx)
    
    def _parse_coinbase_simple(self, row: Dict, idx: int) -> Optional[ExchangeTransaction]:
        """Parse simple Coinbase format with just Date column"""
        def get_val(keys):
            for k in keys:
                if k in row:
                    return row[k]
            return ""
        
        timestamp_str = get_val(["Date"])
        tx_type = get_val(["Transaction Type", "Type"]).lower()
        asset = get_val(["Asset", "Currency"])
        amount = self._parse_float(get_val(["Quantity", "Amount"]))
        price = self._parse_float(get_val(["Price", "Spot Price"]))
        total = self._parse_float(get_val(["Total", "Subtotal", "USD"]))
        fees = self._parse_float(get_val(["Fee", "Fees"]))
        
        timestamp = self._parse_timestamp(timestamp_str)
        
        if not asset or amount == 0:
            return None
        
        return ExchangeTransaction(
            exchange="coinbase",
            tx_id=f"cb_{idx}_{timestamp.timestamp() if timestamp else idx}",
            tx_type=tx_type or "unknown",
            asset=asset,
            amount=abs(amount),
            price_usd=price if price else None,
            total_usd=abs(total) if total else None,
            fee=abs(fees),
            fee_asset="USD",
            timestamp=timestamp or datetime.now(timezone.utc),
            raw_data=row
        )
    
    def _parse_binance(self, rows: List[Dict], headers: List[str], format_variant: str = "primary") -> List[ExchangeTransaction]:
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
    
    def _parse_kraken(self, rows: List[Dict], headers: List[str], format_variant: str = "primary") -> List[ExchangeTransaction]:
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
    
    def _parse_gemini(self, rows: List[Dict], headers: List[str], format_variant: str = "primary") -> List[ExchangeTransaction]:
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
    
    def _parse_crypto_com(self, rows: List[Dict], headers: List[str], format_variant: str = "primary") -> List[ExchangeTransaction]:
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
    
    def _parse_kucoin(self, rows: List[Dict], headers: List[str], format_variant: str = "primary") -> List[ExchangeTransaction]:
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
    
    def get_supported_exchanges(self) -> List[Dict[str, Any]]:
        """Return list of supported exchanges with export instructions and accepted columns"""
        return [
            {
                "id": "coinbase",
                "name": "Coinbase",
                "instructions": "Go to Coinbase → Settings → Statements → Generate Report → Transaction History CSV",
                "accepted_columns": [
                    "Timestamp, Transaction Type, Asset, Quantity Transacted (Classic format)",
                    "Transaction ID, Date & time, Asset Acquired/Sold, Quantity Acquired/Sold, USD Value (Modern format)"
                ],
                "notes": "We support multiple Coinbase CSV export formats. Both classic and modern exports are accepted."
            },
            {
                "id": "binance",
                "name": "Binance",
                "instructions": "Go to Binance → Orders → Trade History → Export Complete Trade History",
                "accepted_columns": ["Date(UTC), Pair, Side, Price, Executed, Amount, Fee"],
                "notes": "Export your complete trade history as CSV"
            },
            {
                "id": "kraken",
                "name": "Kraken",
                "instructions": "Go to Kraken → History → Export → Select Ledgers or Trades",
                "accepted_columns": ["txid, refid, time, type, asset, amount, fee"],
                "notes": "Select 'Ledgers' for best results"
            },
            {
                "id": "gemini",
                "name": "Gemini",
                "instructions": "Go to Gemini → Account → Statements → Download Trade History CSV",
                "accepted_columns": ["Date, Time (UTC), Type, Symbol, Amount, Fee, USD Amount"],
                "notes": None
            },
            {
                "id": "crypto_com",
                "name": "Crypto.com",
                "instructions": "Go to Crypto.com App → Accounts → Transaction History → Export",
                "accepted_columns": ["Timestamp (UTC), Transaction Description, Currency, Amount, Native Amount"],
                "notes": "Export from the mobile app or web interface"
            },
            {
                "id": "kucoin",
                "name": "KuCoin",
                "instructions": "Go to KuCoin → Orders → Trade History → Export",
                "accepted_columns": ["tradeCreatedAt, symbol, side, price, size, fee"],
                "notes": None
            }
        ]


# Singleton instance
csv_parser_service = CSVParserService()
