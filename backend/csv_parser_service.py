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
    LEDGER = "ledger"
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
            # Format 5: Comprehensive format with both Acquired and Disposed columns (RAW TX export)
            ["Transaction ID", "Transaction Type", "Date & time", "Asset Acquired", "Asset Disposed"],
            # Format 6: CoinTracker/Generic Universal Format
            ["Date", "Received Quantity", "Received Currency", "Sent Quantity", "Sent Currency"],
        ]
    },
    ExchangeFormat.BINANCE: {
        "required": ["Date(UTC)", "Pair", "Side", "Price", "Executed", "Amount"],
        "optional": ["Fee", "Total"]
    },
    ExchangeFormat.KRAKEN: {
        "required": ["txid", "refid", "time", "type", "asset", "amount"],
        "optional": ["fee", "balance"],
        # Alternative Kraken formats (tax reports, ledgers, etc.)
        "alt_signatures": [
            # Kraken Ledger/Transaction Report (new format)
            ["Date", "Type", "Transaction ID", "Received Quantity", "Received Currency"],
            # Kraken Income Report
            ["Asset Amount", "Asset Name", "Received Date", "Income", "Type"],
            # Kraken Gains Report (capital gains)
            ["Asset Amount", "Asset Name", "Received Date", "Date Sold", "Proceeds (USD)", "Cost Basis (USD)", "Gain (USD)"],
        ]
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
    },
    ExchangeFormat.LEDGER: {
        # Ledger Live wallet export format
        "required": ["Operation Date", "Currency Ticker", "Operation Type", "Operation Amount"],
        "optional": ["Operation Fees", "Operation Hash", "Account Name", "Countervalue at Operation Date"]
    }
}


class ExchangeTransaction:
    """Standardized transaction format with amount validation"""
    
    # Max circulating supply for common coins (to detect raw unit imports)
    # Keep these TIGHT to catch bad data
    MAX_REASONABLE_AMOUNTS = {
        'BTC': 21_000_000,  # Max BTC supply
        'ETH': 150_000_000,  # ~120M supply
        'SOL': 600_000_000,  # ~580M supply
        'XRP': 100_000_000_000,  # 100B max supply
        'XLM': 50_000_000_000,  # ~50B supply
        'DOGE': 150_000_000_000,  # Large supply
        'ALGO': 10_000_000_000,
        'MATIC': 10_000_000_000,
        'AVAX': 1_000_000_000,
        'ADA': 50_000_000_000,
        'DOT': 1_500_000_000,
    }
    
    # For unknown tokens, be very conservative
    DEFAULT_MAX_AMOUNT = 100_000_000_000  # 100B max for unknown tokens
    
    # Decimals for detecting raw unit values
    CHAIN_DECIMALS = {
        'BTC': 8,   # satoshis
        'ETH': 18,  # wei
        'SOL': 9,   # lamports
        'MATIC': 18,
        'AVAX': 18,
        'ALGO': 6,  # microalgos
    }
    
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
        self.asset = asset.upper() if asset else ''
        self.amount = self._validate_and_fix_amount(amount, self.asset)
        self.price_usd = price_usd
        self.total_usd = total_usd
        self.fee = fee
        self.fee_asset = fee_asset
        self.timestamp = timestamp
        self.raw_data = raw_data
    
    def _validate_and_fix_amount(self, amount: float, asset: str) -> float:
        """Validate amount and auto-convert if it looks like raw units (satoshis, lamports, etc.)"""
        if amount <= 0:
            return 0
        
        max_amount = self.MAX_REASONABLE_AMOUNTS.get(asset, self.DEFAULT_MAX_AMOUNT)
        decimals = self.CHAIN_DECIMALS.get(asset, 0)
        
        # If amount exceeds max supply, it might be in raw units
        if amount > max_amount:
            if decimals > 0:
                converted = amount / (10 ** decimals)
                
                # Only accept conversion if result is reasonable
                if converted <= max_amount:
                    logger.warning(f"Auto-converting {asset} amount from {amount:,.0f} to {converted:.8f} (detected raw units)")
                    return converted
            
            # Can't convert or still too large - skip it
            logger.error(f"Skipping unreasonable {asset} amount: {amount:,.0f} (max allowed: {max_amount:,})")
            return 0
        
        return amount

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
            ExchangeFormat.LEDGER: self._parse_ledger,
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
        
        # Check if this is the comprehensive RAW TX format (has both Asset Acquired AND Asset Disposed columns)
        headers_set = set(h.lower() for h in headers)
        is_comprehensive = "asset disposed" in ' '.join(headers_set) or any("asset disposed" in h.lower() for h in headers)
        
        # Check if this is CoinTracker/Universal format (Received Quantity, Sent Quantity)
        is_universal = any("received quantity" in h.lower() for h in headers) and any("sent quantity" in h.lower() for h in headers)
        
        for i, row in enumerate(rows):
            try:
                # Format 6: CoinTracker/Universal format
                if is_universal:
                    tx = self._parse_coinbase_universal(row, i)
                # Format 5: Comprehensive RAW TX format (has both acquired and disposed in same row)
                elif is_comprehensive or any(k for k in row.keys() if "asset disposed" in k.lower()):
                    tx = self._parse_coinbase_comprehensive(row, i)
                # Format 1: Classic Coinbase (Timestamp, Transaction Type, Asset, Quantity Transacted)
                elif "Timestamp" in row or "timestamp" in [k.lower() for k in row.keys()]:
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
                    # Try comprehensive format as fallback
                    tx = self._parse_coinbase_comprehensive(row, i)
                
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
                    # Also check if key is contained in row_key (for partial matches)
                    if k.lower() in row_key.lower():
                        return row[row_key]
            return ""
        
        timestamp_str = get_val(["Timestamp", "timestamp"])
        tx_type = get_val(["Transaction Type", "transaction type"]).lower()
        asset = get_val(["Asset", "asset"])
        amount = self._parse_float(get_val(["Quantity Transacted", "quantity transacted"]))
        
        # Handle multiple price column names
        spot_price_raw = get_val([
            "Price at Transaction",  # New format
            "Spot Price at Transaction", 
            "spot price at transaction", 
            "Spot Price Currency", 
            "USD Spot Price at Transaction"
        ])
        # Clean price string (remove $ and commas)
        spot_price = self._parse_float(str(spot_price_raw).replace('$', '').replace(',', '')) if spot_price_raw else None
        
        # Handle multiple subtotal/total column names
        subtotal_raw = get_val([
            "Total (inclusive of fees and/or spread)",  # New format
            "Total (inclusive of fees)",
            "Subtotal",
            "USD Subtotal", 
            "subtotal"
        ])
        subtotal = self._parse_float(str(subtotal_raw).replace('$', '').replace(',', '')) if subtotal_raw else None
        
        fees_raw = get_val(["Fees and/or Spread", "Fees", "fees"])
        fees = self._parse_float(str(fees_raw).replace('$', '').replace(',', '')) if fees_raw else 0
        
        timestamp = self._parse_timestamp(timestamp_str)
        
        # Map transaction types - expanded list
        type_map = {
            "buy": "buy",
            "sell": "sell",
            "send": "send",
            "receive": "receive",
            "convert": "trade",
            "rewards income": "reward",
            "reward income": "reward",  # Added
            "coinbase earn": "reward",
            "staking income": "staking",
            "learning reward": "reward",
            "advanced trade buy": "buy",
            "advanced trade sell": "sell",
            "retail staking transfer": "transfer",  # Internal staking transfer
            "retail unstaking transfer": "transfer",  # Internal unstaking transfer
            "incentives rewards payout": "reward",
            "withdrawal": "send",  # USD withdrawal
        }
        std_type = type_map.get(tx_type, tx_type)
        
        # Skip USD withdrawals (not crypto transactions)
        if asset == "USD" and tx_type in ["withdrawal", "send"]:
            return None
        
        if not asset or amount == 0:
            return None
        
        return ExchangeTransaction(
            exchange="coinbase",
            tx_id=get_val(["ID", "id"]) or f"cb_{idx}_{timestamp.timestamp() if timestamp else idx}",
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
    
    def _parse_coinbase_comprehensive(self, row: Dict, idx: int) -> Optional[ExchangeTransaction]:
        """
        Parse comprehensive Coinbase RAW TX format
        Headers: Transaction ID, Transaction Type, Date & time, Asset Acquired, 
                 Quantity Acquired (Bought, Received, etc), Cost Basis (incl. fees and/or spread) (USD),
                 Data Source, Asset Disposed (Sold, Sent, etc), Quantity Disposed, Proceeds (USD)
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
        timestamp_str = get_val(["Date & time", "Date &amp; time", "Timestamp"])
        timestamp = self._parse_timestamp(timestamp_str)
        
        # Get transaction ID
        tx_id = get_val(["Transaction ID"]) or f"cb_{idx}"
        
        # Get transaction type
        tx_type_raw = get_val(["Transaction Type"]).lower()
        
        # Get acquired asset info
        asset_acquired = get_val(["Asset Acquired"])
        qty_acquired = self._parse_float(get_val(["Quantity Acquired", "Quantity Acquired (Bought"]))
        cost_basis = self._parse_float(get_val(["Cost Basis"]))
        
        # Get disposed asset info
        asset_disposed = get_val(["Asset Disposed", "Asset Disposed (Sold"])
        qty_disposed = self._parse_float(get_val(["Quantity Disposed"]))
        proceeds = self._parse_float(get_val(["Proceeds"]))
        
        # Stablecoins - we want to focus on crypto, not stablecoin movements
        stablecoins = {"USD", "USDC", "USDT", "BUSD", "DAI", "GUSD", "PAX", "TUSD", "USDP"}
        
        # Map transaction types
        type_map = {
            "buy": "buy",
            "sell": "sell",
            "send": "send",
            "receive": "receive",
            "converted from": "sell",  # Selling one crypto
            "converted to": "buy",      # Buying another crypto
            "convert": "trade",
            "rewards": "reward",
            "reward": "reward",
            "staking income": "staking",
            "learning reward": "reward",
            "stake": "stake",
            "unstake": "unstake",
            "deposit": "receive",
            "withdrawal": "send",
        }
        
        std_type = type_map.get(tx_type_raw, tx_type_raw)
        
        # Determine primary asset and amount based on transaction type
        # For "Converted from" - the disposed asset is being sold
        # For "Converted to" - the acquired asset is being bought
        # For "Buy" - asset acquired is the main one
        # For "Sell/Send" - asset disposed is the main one
        
        if tx_type_raw in ["sell", "send", "converted from", "withdrawal"]:
            # Focus on what's being disposed/sold
            if asset_disposed and asset_disposed.upper() not in stablecoins:
                asset = asset_disposed
                amount = qty_disposed
                price_usd = proceeds / qty_disposed if qty_disposed > 0 and proceeds else None
                total_usd = proceeds
            elif asset_acquired and asset_acquired.upper() not in stablecoins:
                # Fallback to acquired if disposed is stablecoin
                asset = asset_acquired
                amount = qty_acquired
                price_usd = cost_basis / qty_acquired if qty_acquired > 0 and cost_basis else None
                total_usd = cost_basis
            else:
                return None  # Skip pure stablecoin transactions
                
        elif tx_type_raw in ["buy", "receive", "converted to", "rewards", "reward", "deposit", "staking income", "unstake"]:
            # Focus on what's being acquired
            if asset_acquired and asset_acquired.upper() not in stablecoins:
                asset = asset_acquired
                amount = qty_acquired
                price_usd = cost_basis / qty_acquired if qty_acquired > 0 and cost_basis else None
                total_usd = cost_basis
            elif asset_disposed and asset_disposed.upper() not in stablecoins:
                # Fallback to disposed if acquired is stablecoin
                asset = asset_disposed
                amount = qty_disposed
                std_type = "sell"  # If we're using disposed, it's actually a sell
                price_usd = proceeds / qty_disposed if qty_disposed > 0 and proceeds else None
                total_usd = proceeds
            else:
                return None  # Skip pure stablecoin transactions
        else:
            # For other types, try to find the crypto asset
            if asset_acquired and asset_acquired.upper() not in stablecoins:
                asset = asset_acquired
                amount = qty_acquired
                price_usd = cost_basis / qty_acquired if qty_acquired > 0 and cost_basis else None
                total_usd = cost_basis
            elif asset_disposed and asset_disposed.upper() not in stablecoins:
                asset = asset_disposed
                amount = qty_disposed
                price_usd = proceeds / qty_disposed if qty_disposed > 0 and proceeds else None
                total_usd = proceeds
            else:
                return None
        
        # Skip if no meaningful data
        if not asset or amount == 0:
            return None
        
        return ExchangeTransaction(
            exchange="coinbase",
            tx_id=tx_id,
            tx_type=std_type,
            asset=asset.upper(),
            amount=abs(amount),
            price_usd=price_usd,
            total_usd=abs(total_usd) if total_usd else None,
            fee=0,  # Fees are included in cost basis
            fee_asset="USD",
            timestamp=timestamp or datetime.now(timezone.utc),
            raw_data=row
        )
    
    def _parse_coinbase_universal(self, row: Dict, idx: int) -> Optional[ExchangeTransaction]:
        """
        Parse CoinTracker/Universal CSV format.
        
        Headers: Date, Received Quantity, Received Currency, Sent Quantity, Sent Currency, 
                 Fee Amount, Fee Currency, Tag, ...
        
        This format shows received and sent in the same row:
        - If only Received: it's a buy/receive/reward
        - If only Sent: it's a sell/send
        - If both: it's a trade/swap
        """
        def get_val(keys):
            for k in keys:
                if k in row:
                    return row[k]
                for row_key in row.keys():
                    if k.lower() == row_key.lower():
                        return row[row_key]
            return ""
        
        # Parse timestamp
        date_str = get_val(["Date", "date", "Timestamp"])
        timestamp = self._parse_timestamp(date_str)
        
        # Parse received side
        received_qty = self._parse_float(get_val(["Received Quantity", "received quantity"]))
        received_currency = get_val(["Received Currency", "received currency"]).strip().upper()
        
        # Parse sent side
        sent_qty = self._parse_float(get_val(["Sent Quantity", "sent quantity"]))
        sent_currency = get_val(["Sent Currency", "sent currency"]).strip().upper()
        
        # Parse fees
        fee_amount = self._parse_float(get_val(["Fee Amount", "fee amount", "Fee"]))
        fee_currency = get_val(["Fee Currency", "fee currency"]).strip().upper() or "USD"
        
        # Parse tag (transaction type hint)
        tag = get_val(["Tag", "tag", "Type"]).lower()
        
        # Skip empty rows or rows with only USD movements
        stablecoins = {"USD", "USDC", "USDT", "BUSD", "DAI", "GUSD"}
        
        has_received = received_qty > 0 and received_currency and received_currency not in stablecoins
        has_sent = sent_qty > 0 and sent_currency and sent_currency not in stablecoins
        
        # Skip if no crypto movement
        if not has_received and not has_sent:
            # Check if it's a stablecoin buy (USD sent, USDC received, etc.)
            if received_currency in stablecoins and sent_currency == "USD":
                return None  # Skip stablecoin purchases
            if sent_currency in stablecoins and received_currency == "USD":
                return None  # Skip stablecoin sales
            return None
        
        # Determine transaction type and primary asset
        if has_received and not has_sent:
            # Pure receive: could be buy, reward, staking, etc.
            asset = received_currency
            amount = received_qty
            
            # Check if USD was sent (it's a buy)
            usd_sent = self._parse_float(get_val(["Sent Quantity"])) if get_val(["Sent Currency"]).upper() in stablecoins else 0
            
            if "reward" in tag or "staking" in tag or "income" in tag:
                tx_type = "reward"
                total_usd = None  # Income - needs FMV lookup
            elif "airdrop" in tag:
                tx_type = "airdrop"
                total_usd = None
            elif usd_sent > 0:
                tx_type = "buy"
                total_usd = usd_sent
            else:
                tx_type = "receive"
                total_usd = None
                
        elif has_sent and not has_received:
            # Pure send: could be sell, send, withdrawal
            asset = sent_currency
            amount = sent_qty
            
            # Check if USD was received (it's a sell)
            usd_received = self._parse_float(get_val(["Received Quantity"])) if get_val(["Received Currency"]).upper() in stablecoins else 0
            
            if usd_received > 0:
                tx_type = "sell"
                total_usd = usd_received
            else:
                tx_type = "send"
                total_usd = None
                
        else:
            # Both received and sent - it's a trade/swap
            # Primary focus on what was received (the "buy" side of the trade)
            asset = received_currency
            amount = received_qty
            tx_type = "trade"
            
            # If sent currency is a stablecoin, use that as the USD value
            if sent_currency in stablecoins:
                total_usd = sent_qty
            else:
                total_usd = None
        
        if not asset or amount == 0:
            return None
        
        return ExchangeTransaction(
            exchange="coinbase",  # Using coinbase as generic source
            tx_id=f"univ_{idx}_{timestamp.timestamp() if timestamp else idx}",
            tx_type=tx_type,
            asset=asset,
            amount=abs(amount),
            price_usd=total_usd / amount if total_usd and amount else None,
            total_usd=total_usd,
            fee=abs(fee_amount) if fee_currency in stablecoins else 0,
            fee_asset=fee_currency,
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
        """Parse Kraken CSV format - supports multiple export types"""
        transactions = []
        
        # Detect which Kraken format we're dealing with
        headers_lower = [h.lower() for h in headers]
        
        # Format 1: Ledger/Transaction Report (new format with Date, Type, Transaction ID)
        if "date" in headers_lower and "transaction id" in headers_lower and "received quantity" in headers_lower:
            return self._parse_kraken_ledger(rows, headers)
        
        # Format 2: Income Report (Asset Amount, Asset Name, Received Date, Income, Type)
        if "asset amount" in headers_lower and "asset name" in headers_lower and "income" in headers_lower:
            return self._parse_kraken_income(rows, headers)
        
        # Format 3: Gains Report (Asset Amount, Asset Name, Received Date, Date Sold, Proceeds)
        if "asset amount" in headers_lower and "date sold" in headers_lower and "proceeds (usd)" in headers_lower:
            return self._parse_kraken_gains(rows, headers)
        
        # Original/Legacy Kraken format (txid, refid, time, type, asset, amount)
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
    
    def _parse_kraken_ledger(self, rows: List[Dict], headers: List[str]) -> List[ExchangeTransaction]:
        """Parse Kraken Ledger/Transaction Report format"""
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                tx_id = row.get("Transaction ID", f"kr_led_{i}")
                timestamp_str = row.get("Date", "")
                tx_type = row.get("Type", "").lower()
                
                # Get received side
                received_qty = self._parse_float(row.get("Received Quantity", "0"))
                received_currency = row.get("Received Currency", "").upper()
                received_cost = self._parse_float(row.get("Received Cost Basis (USD)", "0"))
                
                # Get sent side
                sent_qty = self._parse_float(row.get("Sent Quantity", "0"))
                sent_currency = row.get("Sent Currency", "").upper()
                sent_cost = self._parse_float(row.get("Sent Cost Basis (USD)", "0"))
                
                # Get fee
                fee_amount = self._parse_float(row.get("Fee Amount", "0"))
                fee_currency = row.get("Fee Currency", "").upper()
                
                timestamp = self._parse_timestamp(timestamp_str)
                
                # Clean currency names
                for old, new in [(".HOLD", ""), ("USD.HOLD", "USD")]:
                    received_currency = received_currency.replace(old.upper(), new)
                    sent_currency = sent_currency.replace(old.upper(), new)
                    fee_currency = fee_currency.replace(old.upper(), new)
                
                # Map transaction types
                type_map = {
                    "trade": "trade",
                    "deposit": "deposit",
                    "withdrawal": "withdrawal",
                    "transfer": "transfer",
                    "income": "reward",
                    "staking": "staking",
                }
                std_type = type_map.get(tx_type, tx_type)
                
                # For trades, create transaction for the received asset (the buy side)
                if tx_type == "trade" and received_qty > 0 and received_currency and received_currency != "USD":
                    transactions.append(ExchangeTransaction(
                        exchange="kraken",
                        tx_id=f"{tx_id}_buy",
                        tx_type="buy",
                        asset=received_currency,
                        amount=received_qty,
                        price_usd=sent_cost / received_qty if received_qty and sent_cost else None,
                        total_usd=sent_cost if sent_cost else None,
                        fee=fee_amount if fee_currency == "USD" else 0,
                        fee_asset=fee_currency or "USD",
                        timestamp=timestamp or datetime.now(timezone.utc),
                        raw_data=row
                    ))
                
                # For trades where we're selling crypto for USD
                elif tx_type == "trade" and sent_qty > 0 and sent_currency and sent_currency != "USD" and received_currency == "USD":
                    transactions.append(ExchangeTransaction(
                        exchange="kraken",
                        tx_id=f"{tx_id}_sell",
                        tx_type="sell",
                        asset=sent_currency,
                        amount=sent_qty,
                        price_usd=received_qty / sent_qty if sent_qty else None,
                        total_usd=received_qty,
                        fee=fee_amount if fee_currency == "USD" else 0,
                        fee_asset=fee_currency or "USD",
                        timestamp=timestamp or datetime.now(timezone.utc),
                        raw_data=row
                    ))
                
                # For income/rewards
                elif tx_type == "income" and received_qty > 0 and received_currency:
                    transactions.append(ExchangeTransaction(
                        exchange="kraken",
                        tx_id=tx_id,
                        tx_type="reward",
                        asset=received_currency,
                        amount=received_qty,
                        price_usd=None,
                        total_usd=received_cost if received_cost else None,
                        fee=fee_amount,
                        fee_asset=fee_currency or received_currency,
                        timestamp=timestamp or datetime.now(timezone.utc),
                        raw_data=row
                    ))
                
                # For deposits
                elif tx_type == "deposit" and received_qty > 0 and received_currency:
                    transactions.append(ExchangeTransaction(
                        exchange="kraken",
                        tx_id=tx_id,
                        tx_type="deposit",
                        asset=received_currency,
                        amount=received_qty,
                        price_usd=None,
                        total_usd=received_cost if received_cost else None,
                        fee=fee_amount,
                        fee_asset=fee_currency or "USD",
                        timestamp=timestamp or datetime.now(timezone.utc),
                        raw_data=row
                    ))
                
                # For withdrawals
                elif tx_type == "withdrawal" and sent_qty > 0 and sent_currency:
                    transactions.append(ExchangeTransaction(
                        exchange="kraken",
                        tx_id=tx_id,
                        tx_type="withdrawal",
                        asset=sent_currency,
                        amount=sent_qty,
                        price_usd=None,
                        total_usd=sent_cost if sent_cost else None,
                        fee=fee_amount,
                        fee_asset=fee_currency or sent_currency,
                        timestamp=timestamp or datetime.now(timezone.utc),
                        raw_data=row
                    ))
                
                # For transfers (internal moves between wallets)
                elif tx_type == "transfer" and received_qty > 0 and received_currency:
                    transactions.append(ExchangeTransaction(
                        exchange="kraken",
                        tx_id=tx_id,
                        tx_type="transfer",
                        asset=received_currency,
                        amount=received_qty,
                        price_usd=None,
                        total_usd=received_cost if received_cost else None,
                        fee=0,
                        fee_asset=received_currency,
                        timestamp=timestamp or datetime.now(timezone.utc),
                        raw_data=row
                    ))
                
            except Exception as e:
                logger.warning(f"Error parsing Kraken ledger row {i}: {e}")
                continue
        
        return transactions
    
    def _parse_kraken_income(self, rows: List[Dict], headers: List[str]) -> List[ExchangeTransaction]:
        """Parse Kraken Income Report format"""
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                amount = self._parse_float(row.get("Asset Amount", "0"))
                asset = row.get("Asset Name", "").upper()
                date_str = row.get("Received Date", "")
                income_usd = self._parse_float(row.get("Income", "0"))
                tx_type = row.get("Type", "income").lower()
                
                timestamp = self._parse_timestamp(date_str)
                
                if not asset or amount == 0:
                    continue
                
                transactions.append(ExchangeTransaction(
                    exchange="kraken",
                    tx_id=f"kr_inc_{i}_{asset}",
                    tx_type="reward",
                    asset=asset,
                    amount=amount,
                    price_usd=income_usd / amount if amount and income_usd else None,
                    total_usd=income_usd if income_usd else None,
                    fee=0,
                    fee_asset="USD",
                    timestamp=timestamp or datetime.now(timezone.utc),
                    raw_data=row
                ))
            except Exception as e:
                logger.warning(f"Error parsing Kraken income row {i}: {e}")
                continue
        
        return transactions
    
    def _parse_kraken_gains(self, rows: List[Dict], headers: List[str]) -> List[ExchangeTransaction]:
        """Parse Kraken Gains Report format (capital gains export)"""
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                amount = self._parse_float(row.get("Asset Amount", "0"))
                asset = row.get("Asset Name", "").upper()
                acquired_date = row.get("Received Date", "")
                sold_date = row.get("Date Sold", "")
                proceeds = self._parse_float(row.get("Proceeds (USD)", "0"))
                cost_basis = self._parse_float(row.get("Cost Basis (USD)", "0"))
                gain = self._parse_float(row.get("Gain (USD)", "0"))
                holding_type = row.get("Type", "")  # "Long Term" or "Short Term"
                
                # Parse the sell date as the transaction timestamp
                timestamp = self._parse_timestamp(sold_date)
                acquired_timestamp = self._parse_timestamp(acquired_date)
                
                if not asset or amount == 0:
                    continue
                
                # This is a sell transaction with known cost basis
                transactions.append(ExchangeTransaction(
                    exchange="kraken",
                    tx_id=f"kr_gain_{i}_{asset}",
                    tx_type="sell",
                    asset=asset,
                    amount=amount,
                    price_usd=proceeds / amount if amount else None,
                    total_usd=proceeds,
                    fee=0,
                    fee_asset="USD",
                    timestamp=timestamp or datetime.now(timezone.utc),
                    raw_data={
                        **row,
                        "cost_basis": cost_basis,
                        "gain_loss": gain,
                        "holding_period": holding_type,
                        "acquired_date": acquired_date
                    }
                ))
            except Exception as e:
                logger.warning(f"Error parsing Kraken gains row {i}: {e}")
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
    
    def _parse_ledger(self, rows: List[Dict], headers: List[str], format_variant: str = "primary") -> List[ExchangeTransaction]:
        """Parse Ledger Live wallet export CSV format
        
        Ledger CSV columns:
        - Operation Date: ISO timestamp (e.g., 2026-03-06T15:11:46.000Z)
        - Status: Confirmed/Pending
        - Currency Ticker: Asset symbol (BTC, ETH, etc.)
        - Operation Type: IN (receive), OUT (send)
        - Operation Amount: Amount transferred
        - Operation Fees: Transaction fees
        - Operation Hash: Transaction hash
        - Account Name: Ledger account name
        - Account xpub: Extended public key (for reference)
        - Countervalue Ticker: Fiat currency (usually USD)
        - Countervalue at Operation Date: USD value at time of transaction
        - Countervalue at CSV Export: Current USD value
        """
        transactions = []
        
        for i, row in enumerate(rows):
            try:
                # Get basic fields
                timestamp_str = row.get("Operation Date", "")
                status = row.get("Status", "")
                asset = row.get("Currency Ticker", "")
                op_type = row.get("Operation Type", "").upper()
                amount = self._parse_float(row.get("Operation Amount", "0"))
                fee = self._parse_float(row.get("Operation Fees", "0"))
                tx_hash = row.get("Operation Hash", "")
                account_name = row.get("Account Name", "Ledger")
                
                # Get USD value at operation date for cost basis
                usd_value = self._parse_float(row.get("Countervalue at Operation Date", "0"))
                
                # Skip pending transactions or invalid rows
                if status != "Confirmed" or not asset or amount == 0:
                    continue
                
                # Parse timestamp
                timestamp = self._parse_timestamp(timestamp_str)
                
                # Determine transaction type
                # IN = received crypto - likely a transfer from exchange, NOT a new buy
                # OUT = sent crypto - transfer out, NOT a sell
                # Ledger wallet transactions are typically transfers, not actual purchases
                if op_type == "IN":
                    # Mark as receive/transfer, NOT a buy
                    # The original cost basis comes from where the crypto was purchased
                    tx_type = "receive"  # NOT "buy" - this avoids double-counting cost basis
                elif op_type == "OUT":
                    tx_type = "send"  # Transfer out, NOT a sell (preserves cost basis)
                else:
                    tx_type = op_type.lower()
                
                # Calculate price per unit if we have USD value
                price_usd = usd_value / abs(amount) if amount != 0 and usd_value > 0 else None
                
                transactions.append(ExchangeTransaction(
                    exchange="ledger",
                    tx_id=tx_hash or f"ledger_{i}_{timestamp.timestamp() if timestamp else i}",
                    tx_type=tx_type,
                    asset=asset,
                    amount=abs(amount),
                    price_usd=price_usd,
                    total_usd=usd_value if usd_value > 0 else None,
                    fee=abs(fee),
                    fee_asset=asset,  # Fees are typically in the same asset
                    timestamp=timestamp or datetime.now(timezone.utc),
                    raw_data={
                        **row,
                        "account_name": account_name,
                        "ledger_export": True
                    }
                ))
                
            except Exception as e:
                logger.warning(f"Error parsing Ledger row {i}: {e}")
                continue
        
        logger.info(f"Parsed {len(transactions)} Ledger transactions")
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
            },
            {
                "id": "ledger",
                "name": "Ledger Live",
                "instructions": "Go to Ledger Live → Portfolio → Export operations (gear icon) → Export to CSV",
                "accepted_columns": ["Operation Date, Currency Ticker, Operation Type, Operation Amount, Countervalue at Operation Date"],
                "notes": "Export your complete wallet history from Ledger Live. IN operations are treated as acquisitions, OUT operations are treated as transfers (not sales)."
            }
        ]


# Singleton instance
csv_parser_service = CSVParserService()
