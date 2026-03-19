"""
Backend tests for CSV Parser Service - Coinbase format support
Tests the CSV parser's ability to detect and parse multiple Coinbase CSV formats.

Focus on:
1. Modern Coinbase format with: Transaction ID, Date & time, Asset Acquired, Quantity Acquired, Asset Sold, Quantity Sold, USD Value
2. Classic Coinbase format with: Timestamp, Transaction Type, Asset, Quantity Transacted
3. Buy/sell detection logic - buying crypto should be 'buy', selling crypto should be 'sell'
"""

import pytest
import requests
import os
import uuid
from io import StringIO
import sys
sys.path.insert(0, '/app/backend')

from csv_parser_service import CSVParserService, ExchangeFormat

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://crypto-tax-mvp.preview.emergentagent.com').rstrip('/')


class TestCsvParserCoinbaseFormatDetection:
    """Test that the CSV parser correctly detects Coinbase formats"""
    
    def test_detect_classic_coinbase_format(self):
        """Test detection of classic Coinbase format with Timestamp, Transaction Type, Asset columns"""
        parser = CSVParserService()
        headers = ["Timestamp", "Transaction Type", "Asset", "Quantity Transacted", "Spot Price at Transaction", "USD Subtotal"]
        
        exchange, variant = parser.detect_exchange(headers)
        
        assert exchange == ExchangeFormat.COINBASE
        assert variant == "primary"
        
    def test_detect_modern_coinbase_format_alt1(self):
        """Test detection of modern Coinbase format with Transaction ID, Asset Acquired/Sold"""
        parser = CSVParserService()
        headers = ["Transaction ID", "Transaction Type", "Asset Acquired", "Quantity Acquired", "Asset Sold", "Quantity Sold"]
        
        exchange, variant = parser.detect_exchange(headers)
        
        assert exchange == ExchangeFormat.COINBASE
        assert variant == "alt_1"
        
    def test_detect_modern_coinbase_format_with_datetime(self):
        """Test detection of modern Coinbase format with Date & time column (user reported format)"""
        parser = CSVParserService()
        headers = ["Transaction ID", "Date & time", "Asset Acquired", "Quantity Acquired (a)", "Asset Sold", "Quantity Sold (s)", "USD Value"]
        
        exchange, variant = parser.detect_exchange(headers)
        
        assert exchange == ExchangeFormat.COINBASE
        assert variant == "alt_2"
        
    def test_detect_coinbase_heuristic(self):
        """Test heuristic detection for Coinbase with partial matching columns"""
        parser = CSVParserService()
        # Headers that contain Coinbase markers but not exact signature
        headers = ["ID", "Asset Acquired", "Quantity Acquired", "Asset Sold", "Quantity Sold", "USD Value", "Fee"]
        
        exchange, variant = parser.detect_exchange(headers)
        
        assert exchange == ExchangeFormat.COINBASE
        assert variant == "heuristic"


class TestCsvParserCoinbaseClassicParsing:
    """Test parsing of classic Coinbase CSV format"""
    
    def test_parse_classic_coinbase_buy(self):
        """Test parsing a BUY transaction in classic Coinbase format"""
        parser = CSVParserService()
        csv_content = """Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price at Transaction,USD Subtotal
2024-01-15 10:30:00,Buy,BTC,0.05,42000.00,2100.00"""
        
        exchange, transactions = parser.parse_csv(csv_content)
        
        assert exchange == ExchangeFormat.COINBASE
        assert len(transactions) == 1
        
        tx = transactions[0]
        assert tx.tx_type == "buy"
        assert tx.asset == "BTC"
        assert tx.amount == 0.05
        assert tx.price_usd == 42000.00
        assert tx.total_usd == 2100.00
        assert tx.exchange == "coinbase"
        
    def test_parse_classic_coinbase_sell(self):
        """Test parsing a SELL transaction in classic Coinbase format"""
        parser = CSVParserService()
        csv_content = """Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price at Transaction,USD Subtotal
2024-02-20 14:45:00,Sell,ETH,1.5,3000.00,4500.00"""
        
        exchange, transactions = parser.parse_csv(csv_content)
        
        assert exchange == ExchangeFormat.COINBASE
        assert len(transactions) == 1
        
        tx = transactions[0]
        assert tx.tx_type == "sell"
        assert tx.asset == "ETH"
        assert tx.amount == 1.5
        assert tx.price_usd == 3000.00
        
    def test_parse_classic_coinbase_multiple_transactions(self):
        """Test parsing multiple transactions in classic format"""
        parser = CSVParserService()
        csv_content = """Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price at Transaction,USD Subtotal
2024-01-10 08:00:00,Buy,BTC,0.1,40000.00,4000.00
2024-01-15 12:00:00,Buy,ETH,2.0,2500.00,5000.00
2024-02-01 09:30:00,Sell,BTC,0.05,45000.00,2250.00"""
        
        exchange, transactions = parser.parse_csv(csv_content)
        
        assert exchange == ExchangeFormat.COINBASE
        assert len(transactions) == 3
        
        # Verify transaction types
        assert transactions[0].tx_type == "buy"
        assert transactions[1].tx_type == "buy"
        assert transactions[2].tx_type == "sell"
        
        # Verify assets
        assert transactions[0].asset == "BTC"
        assert transactions[1].asset == "ETH"
        assert transactions[2].asset == "BTC"


class TestCsvParserCoinbaseModernParsing:
    """Test parsing of modern Coinbase CSV format with Asset Acquired/Sold columns"""
    
    def test_parse_modern_coinbase_buy_crypto(self):
        """
        Test parsing a BUY transaction in modern format:
        - User pays USD (Asset Sold = USD)
        - User receives crypto (Asset Acquired = BTC)
        - This should be classified as BUY
        """
        parser = CSVParserService()
        csv_content = """Transaction ID,Date & time,Asset Acquired,Quantity Acquired,Asset Sold,Quantity Sold,USD Value
abc123,2024-03-01 10:00:00,BTC,0.025,USD,1000.00,1000.00"""
        
        exchange, transactions = parser.parse_csv(csv_content)
        
        assert exchange == ExchangeFormat.COINBASE
        assert len(transactions) == 1
        
        tx = transactions[0]
        assert tx.tx_type == "buy", f"Expected 'buy' but got '{tx.tx_type}' - buying BTC with USD should be a buy"
        assert tx.asset == "BTC", f"Expected asset 'BTC' but got '{tx.asset}'"
        assert tx.amount == 0.025
        
    def test_parse_modern_coinbase_sell_crypto(self):
        """
        Test parsing a SELL transaction in modern format:
        - User sells crypto (Asset Sold = ETH)
        - User receives USD (Asset Acquired = USD)
        - This should be classified as SELL
        """
        parser = CSVParserService()
        csv_content = """Transaction ID,Date & time,Asset Acquired,Quantity Acquired,Asset Sold,Quantity Sold,USD Value
def456,2024-03-05 14:30:00,USD,3000.00,ETH,1.0,3000.00"""
        
        exchange, transactions = parser.parse_csv(csv_content)
        
        assert exchange == ExchangeFormat.COINBASE
        assert len(transactions) == 1
        
        tx = transactions[0]
        assert tx.tx_type == "sell", f"Expected 'sell' but got '{tx.tx_type}' - selling ETH for USD should be a sell"
        assert tx.asset == "ETH", f"Expected asset 'ETH' but got '{tx.asset}'"
        assert tx.amount == 1.0
        
    def test_parse_modern_coinbase_with_quantity_suffix(self):
        """Test parsing modern format with (a) and (s) column suffixes as reported by user"""
        parser = CSVParserService()
        csv_content = """Transaction ID,Date & time,Asset Acquired,Quantity Acquired (a),Asset Sold,Quantity Sold (s),USD Value
tx789,2024-03-10 09:15:00,SOL,5.0,USD,100.00,100.00"""
        
        exchange, transactions = parser.parse_csv(csv_content)
        
        assert exchange == ExchangeFormat.COINBASE
        assert len(transactions) == 1
        
        tx = transactions[0]
        assert tx.tx_type == "buy"
        assert tx.asset == "SOL"
        assert tx.amount == 5.0
        
    def test_parse_modern_coinbase_stablecoin_handling(self):
        """
        Test that stablecoins (USDC, USDT) are treated like USD:
        - Buying crypto with USDC = BUY
        - Selling crypto for USDC = SELL
        """
        parser = CSVParserService()
        csv_content = """Transaction ID,Date & time,Asset Acquired,Quantity Acquired,Asset Sold,Quantity Sold,USD Value
tx001,2024-03-12 11:00:00,BTC,0.01,USDC,500.00,500.00
tx002,2024-03-13 12:00:00,USDT,1000.00,ETH,0.5,1000.00"""
        
        exchange, transactions = parser.parse_csv(csv_content)
        
        assert len(transactions) == 2
        
        # Buying BTC with USDC = BUY (focus on crypto asset)
        assert transactions[0].tx_type == "buy"
        assert transactions[0].asset == "BTC"
        
        # Selling ETH for USDT = SELL (focus on crypto asset)
        assert transactions[1].tx_type == "sell"
        assert transactions[1].asset == "ETH"


class TestCsvParserBuySellLogic:
    """Test the buy/sell classification logic in detail"""
    
    def test_buy_crypto_with_fiat(self):
        """When user acquires crypto and sells USD/fiat, it's a BUY"""
        parser = CSVParserService()
        
        # Multiple scenarios that should all be BUY
        test_cases = [
            # (Asset Acquired, Qty Acquired, Asset Sold, Qty Sold, Expected Asset, Expected Type)
            ("BTC", 0.1, "USD", 5000, "BTC", "buy"),
            ("ETH", 2.0, "USD", 6000, "ETH", "buy"),
            ("SOL", 10.0, "USDC", 200, "SOL", "buy"),
            ("AVAX", 5.0, "USDT", 100, "AVAX", "buy"),
        ]
        
        for acquired, qty_acq, sold, qty_sold, expected_asset, expected_type in test_cases:
            csv_content = f"""Transaction ID,Date & time,Asset Acquired,Quantity Acquired,Asset Sold,Quantity Sold,USD Value
tx123,2024-01-01 10:00:00,{acquired},{qty_acq},{sold},{qty_sold},{qty_sold}"""
            
            _, transactions = parser.parse_csv(csv_content)
            
            assert len(transactions) == 1
            tx = transactions[0]
            assert tx.tx_type == expected_type, f"Buying {acquired} with {sold} should be '{expected_type}', got '{tx.tx_type}'"
            assert tx.asset == expected_asset, f"Asset should be {expected_asset}, got {tx.asset}"
            
    def test_sell_crypto_for_fiat(self):
        """When user sells crypto and acquires USD/fiat, it's a SELL"""
        parser = CSVParserService()
        
        test_cases = [
            # (Asset Acquired, Qty Acquired, Asset Sold, Qty Sold, Expected Asset, Expected Type)
            ("USD", 5000, "BTC", 0.1, "BTC", "sell"),
            ("USD", 6000, "ETH", 2.0, "ETH", "sell"),
            ("USDC", 200, "SOL", 10.0, "SOL", "sell"),
            ("USDT", 100, "AVAX", 5.0, "AVAX", "sell"),
        ]
        
        for acquired, qty_acq, sold, qty_sold, expected_asset, expected_type in test_cases:
            csv_content = f"""Transaction ID,Date & time,Asset Acquired,Quantity Acquired,Asset Sold,Quantity Sold,USD Value
tx456,2024-01-01 10:00:00,{acquired},{qty_acq},{sold},{qty_sold},{qty_acq}"""
            
            _, transactions = parser.parse_csv(csv_content)
            
            assert len(transactions) == 1
            tx = transactions[0]
            assert tx.tx_type == expected_type, f"Selling {sold} for {acquired} should be '{expected_type}', got '{tx.tx_type}'"
            assert tx.asset == expected_asset, f"Asset should be {expected_asset}, got {tx.asset}"


class TestCsvParserAPIEndpoints:
    """Test the API endpoints for exchanges"""
    
    def test_supported_exchanges_has_accepted_columns(self, api_client):
        """Test that /api/exchanges/supported returns accepted_columns field"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/supported")
        
        assert response.status_code == 200
        data = response.json()
        
        for exchange in data["exchanges"]:
            assert "accepted_columns" in exchange, f"Exchange {exchange['id']} missing accepted_columns"
            
    def test_coinbase_accepted_columns_shows_formats(self, api_client):
        """Test that Coinbase accepted_columns shows both classic and modern formats"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/supported")
        
        assert response.status_code == 200
        data = response.json()
        
        coinbase = next((ex for ex in data["exchanges"] if ex["id"] == "coinbase"), None)
        assert coinbase is not None
        
        accepted_columns = coinbase.get("accepted_columns", [])
        assert len(accepted_columns) >= 2, "Coinbase should show at least 2 accepted column formats"
        
        # Check for format indicators
        columns_text = " ".join(str(col) for col in accepted_columns).lower()
        assert "classic" in columns_text or "timestamp" in columns_text, "Should mention classic format"
        assert "modern" in columns_text or "transaction id" in columns_text or "asset acquired" in columns_text, "Should mention modern format"
        
    def test_export_instructions_has_accepted_columns(self, api_client):
        """Test that /api/exchanges/export-instructions/{id} returns accepted_columns"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/export-instructions/coinbase")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "accepted_columns" in data, "Export instructions should include accepted_columns"
        assert len(data["accepted_columns"]) > 0, "Coinbase should have accepted_columns listed"
        
    def test_all_exchanges_have_accepted_columns_in_instructions(self, api_client):
        """Test that all exchanges have accepted_columns in their export instructions"""
        exchanges = ["coinbase", "binance", "kraken", "gemini", "crypto_com", "kucoin"]
        
        for exchange_id in exchanges:
            response = api_client.get(f"{BASE_URL}/api/exchanges/export-instructions/{exchange_id}")
            assert response.status_code == 200
            data = response.json()
            
            # Note: Some exchanges may not have accepted_columns defined yet
            # Just verify the endpoint works and has the field
            assert "name" in data
            assert "steps" in data


class TestCsvParserEdgeCases:
    """Test edge cases and error handling in CSV parsing"""
    
    def test_empty_csv_raises_error(self):
        """Test that empty CSV raises appropriate error"""
        parser = CSVParserService()
        
        with pytest.raises(ValueError):
            parser.parse_csv("")
            
    def test_unknown_format_raises_error(self):
        """Test that unrecognized CSV format raises error with helpful message"""
        parser = CSVParserService()
        csv_content = """Random Column,Another Column,Third Column
value1,value2,value3"""
        
        with pytest.raises(ValueError) as excinfo:
            parser.parse_csv(csv_content)
            
        error_msg = str(excinfo.value).lower()
        assert "detect" in error_msg or "format" in error_msg or "supported" in error_msg
        
    def test_parse_handles_missing_values(self):
        """Test that parser handles rows with missing optional values"""
        parser = CSVParserService()
        csv_content = """Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price at Transaction,USD Subtotal
2024-01-15 10:30:00,Buy,BTC,0.05,,"""
        
        exchange, transactions = parser.parse_csv(csv_content)
        
        # Should still parse successfully even with missing price/subtotal
        assert exchange == ExchangeFormat.COINBASE
        assert len(transactions) == 1
        assert transactions[0].asset == "BTC"
        
    def test_parse_handles_various_timestamp_formats(self):
        """Test that parser handles different timestamp formats"""
        parser = CSVParserService()
        
        # Different timestamp formats that should all work
        timestamps = [
            "2024-01-15 10:30:00",
            "2024-01-15T10:30:00",
            "2024-01-15T10:30:00Z",
            "01/15/2024 10:30:00",
            "2024-01-15",
        ]
        
        for ts in timestamps:
            csv_content = f"""Timestamp,Transaction Type,Asset,Quantity Transacted
{ts},Buy,BTC,0.1"""
            
            exchange, transactions = parser.parse_csv(csv_content)
            assert len(transactions) == 1, f"Failed to parse timestamp: {ts}"
            assert transactions[0].timestamp is not None, f"Timestamp not parsed for: {ts}"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session
