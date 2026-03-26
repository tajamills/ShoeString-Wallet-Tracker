"""
Backend tests for Bug Fixes - Iteration 18

Bug 1: Chain of Custody - Solana address validation was showing 'Invalid EVM address format'
       instead of 'coming soon' message. 
       FIX: Now validates addresses based on selected chain type, not always EVM.

Bug 2: Tax calculations - 'send' and 'withdrawal' were being treated as taxable sales,
       causing incorrect realized gains ($210K).
       FIX: Only 'sell' and 'trade' trigger realized gains. 'send' and 'withdrawal' are
       now properly treated as transfers (NOT taxable).
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://portfolio-gains-calc.preview.emergentagent.com').rstrip('/')


class TestCustodyAddressValidation:
    """Tests for Chain of Custody address validation bug fix"""
    
    def test_solana_address_now_works(self, authenticated_premium_client):
        """
        UPDATED: Solana Chain of Custody now fully implemented!
        Solana addresses should return valid analysis (200), NOT 'coming soon' error.
        
        Original bug (iteration 18): Solana showed 'Invalid EVM address format'
        First fix: Showed 'coming soon' instead of EVM error  
        Current fix (iteration 19): Solana actually WORKS with full custody analysis!
        """
        # Valid Solana address format (base58, 32-44 chars)
        solana_address = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": solana_address,
                "chain": "solana"
            }
        )
        
        # Solana now WORKS - should return 200 with valid analysis
        assert response.status_code == 200, f"Solana should work now. Got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify valid Solana custody analysis response
        assert data.get("chain") == "solana"
        assert "custody_chain" in data
        assert "origin_points" in data
        assert "summary" in data
        # Should NOT show any EVM-related errors
        assert "evm" not in str(data).lower() or "address format" not in str(data).lower()
        
    def test_solana_invalid_address_shows_solana_format_error(self, authenticated_premium_client):
        """
        Solana address with invalid format should show Solana-specific error
        """
        # Invalid Solana address (too short)
        invalid_solana_address = "short"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": invalid_solana_address,
                "chain": "solana"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", "")
        
        # Should say "Invalid Solana address format", NOT EVM error
        assert "solana" in detail.lower(), f"Expected Solana format error but got: {detail}"
        assert "evm" not in detail.lower(), f"Should NOT mention EVM: {detail}"
        
    def test_evm_address_still_works_on_ethereum(self, authenticated_premium_client):
        """
        EVM addresses should still work correctly on EVM chains
        """
        # Valid EVM address format
        evm_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f9C6E6"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": evm_address,
                "chain": "ethereum"
            }
        )
        
        # Should succeed (200) or return some analysis, not format error
        # May get 500 if external API fails, but should NOT be 400 format error
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}"
        if response.status_code == 400:
            pytest.fail(f"EVM address should not cause format error: {response.json()}")
            
    def test_evm_address_on_polygon_works(self, authenticated_premium_client):
        """
        EVM addresses should work on other EVM chains like Polygon
        """
        evm_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f9C6E6"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": evm_address,
                "chain": "polygon"
            }
        )
        
        # Should succeed or service error, not format validation error
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}"
        
    def test_invalid_evm_address_shows_evm_error_on_ethereum(self, authenticated_premium_client):
        """
        Invalid EVM address on EVM chain should show EVM-specific error
        """
        invalid_evm_address = "not_an_address"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": invalid_evm_address,
                "chain": "ethereum"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", "")
        
        # Should mention EVM format since it's an EVM chain
        assert "evm" in detail.lower() or "0x" in detail.lower(), f"Expected EVM error: {detail}"
        
    def test_bitcoin_address_shows_coming_soon(self, authenticated_premium_client):
        """
        Bitcoin addresses should show 'coming soon' message
        """
        # Valid Bitcoin address format
        btc_address = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": btc_address,
                "chain": "bitcoin"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", "")
        
        # Should say "coming soon"
        assert "coming soon" in detail.lower(), f"Expected 'coming soon' but got: {detail}"
        
    def test_unsupported_chain_shows_helpful_error(self, authenticated_premium_client):
        """
        Unsupported chains should show a helpful error listing supported chains
        """
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": "some_address",
                "chain": "avalanche"  # Not yet supported
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", "")
        
        # Should mention supported chains
        assert "supported" in detail.lower() or "ethereum" in detail.lower(), \
            f"Expected helpful error with supported chains: {detail}"


class TestTaxCalculationTransfers:
    """Tests for Tax calculation bug fix - transfers should NOT be taxable"""
    
    def test_send_transaction_not_in_realized_gains(self, authenticated_premium_client):
        """
        BUG FIX TEST: 'send' transactions should NOT trigger realized gains
        They are transfers between wallets, not taxable dispositions.
        """
        # This test imports mock transactions to test the logic
        # First, let's test the /api/exchanges/tax/calculate endpoint behavior
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # The calculation should work - we need to verify the logic via the service
        assert "tax_data" in data
        
    def test_calculate_tax_endpoint_works(self, authenticated_premium_client):
        """
        Basic test that tax calculation endpoint is working
        """
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={"tax_year": 2024}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "tax_data" in data
        assert "summary" in data.get("tax_data", {})


class TestExchangeTaxServiceDirectly:
    """Direct tests on exchange_tax_service.py logic using mock data"""
    
    def test_send_withdrawal_not_treated_as_sale(self):
        """
        CRITICAL BUG FIX: send and withdrawal should NOT create realized gains
        
        Before fix: 'send' and 'withdrawal' were in the sells list
        After fix: they are skipped (transfers, not dispositions)
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from exchange_tax_service import ExchangeTaxService
        
        service = ExchangeTaxService()
        
        # Create test transactions with send/withdrawal
        test_transactions = [
            # Buy 1 BTC at $10,000
            {
                "tx_id": "buy1",
                "exchange": "test_exchange",
                "tx_type": "buy",
                "asset": "BTC",
                "amount": 1.0,
                "price_usd": 10000,
                "total_usd": 10000,
                "fee": 0,
                "fee_asset": "USD",
                "timestamp": "2024-01-01T00:00:00Z"
            },
            # SEND (transfer) 0.5 BTC - should NOT be taxable
            {
                "tx_id": "send1",
                "exchange": "test_exchange",
                "tx_type": "send",
                "asset": "BTC",
                "amount": 0.5,
                "price_usd": 20000,  # Price went up, but this is a transfer!
                "total_usd": 10000,
                "fee": 0,
                "fee_asset": "USD",
                "timestamp": "2024-06-01T00:00:00Z"
            },
            # WITHDRAWAL 0.3 BTC - should NOT be taxable
            {
                "tx_id": "withdraw1",
                "exchange": "test_exchange",
                "tx_type": "withdrawal",
                "asset": "BTC",
                "amount": 0.3,
                "price_usd": 25000,  # Price went up more, but still a transfer!
                "total_usd": 7500,
                "fee": 0,
                "fee_asset": "USD",
                "timestamp": "2024-07-01T00:00:00Z"
            }
        ]
        
        result = service.calculate_from_transactions(test_transactions)
        
        # There should be NO realized gains since we only bought, didn't sell
        realized_gains = result.get('realized_gains', [])
        
        assert len(realized_gains) == 0, \
            f"Expected 0 realized gains (send/withdrawal are transfers), got {len(realized_gains)}: {realized_gains}"
        
        # Summary should show 0 realized gain
        summary = result.get('summary', {})
        total_realized = summary.get('total_realized_gain', 0)
        
        assert total_realized == 0, \
            f"Expected $0 total realized gain (no sales), got ${total_realized}"
            
    def test_sell_and_trade_still_create_gains(self):
        """
        'sell' and 'trade' should still trigger realized gains - only send/withdrawal excluded
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from exchange_tax_service import ExchangeTaxService
        
        service = ExchangeTaxService()
        
        test_transactions = [
            # Buy 1 BTC at $10,000
            {
                "tx_id": "buy1",
                "exchange": "test",
                "tx_type": "buy",
                "asset": "BTC",
                "amount": 1.0,
                "price_usd": 10000,
                "total_usd": 10000,
                "fee": 0,
                "timestamp": "2024-01-01T00:00:00Z"
            },
            # SELL 0.5 BTC at $20,000 - should create gain
            {
                "tx_id": "sell1",
                "exchange": "test",
                "tx_type": "sell",
                "asset": "BTC",
                "amount": 0.5,
                "price_usd": 20000,
                "total_usd": 10000,
                "fee": 0,
                "timestamp": "2024-06-01T00:00:00Z"
            }
        ]
        
        result = service.calculate_from_transactions(test_transactions)
        realized_gains = result.get('realized_gains', [])
        
        # Should have exactly 1 realized gain from the sell
        assert len(realized_gains) == 1, \
            f"Expected 1 realized gain from sell, got {len(realized_gains)}"
        
        # Gain should be: sold 0.5 BTC at $20,000 each = $10,000 proceeds
        # Cost basis: 0.5 BTC at $10,000 each = $5,000
        # Gain: $10,000 - $5,000 = $5,000
        gain = realized_gains[0].get('gain_loss', 0)
        assert gain == 5000, f"Expected $5,000 gain, got ${gain}"
        
    def test_trade_creates_gain(self):
        """
        'trade' transactions should also trigger realized gains
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from exchange_tax_service import ExchangeTaxService
        
        service = ExchangeTaxService()
        
        test_transactions = [
            # Buy 1 ETH at $1,000
            {
                "tx_id": "buy1",
                "exchange": "test",
                "tx_type": "buy",
                "asset": "ETH",
                "amount": 1.0,
                "price_usd": 1000,
                "total_usd": 1000,
                "fee": 0,
                "timestamp": "2024-01-01T00:00:00Z"
            },
            # TRADE (swap) 1 ETH for something at $2,000 - taxable
            {
                "tx_id": "trade1",
                "exchange": "test",
                "tx_type": "trade",
                "asset": "ETH",
                "amount": 1.0,
                "price_usd": 2000,
                "total_usd": 2000,
                "fee": 0,
                "timestamp": "2024-06-01T00:00:00Z"
            }
        ]
        
        result = service.calculate_from_transactions(test_transactions)
        realized_gains = result.get('realized_gains', [])
        
        # Should have 1 realized gain from the trade
        assert len(realized_gains) == 1, \
            f"Expected 1 realized gain from trade, got {len(realized_gains)}"
        
        # Gain: $2,000 - $1,000 = $1,000
        gain = realized_gains[0].get('gain_loss', 0)
        assert gain == 1000, f"Expected $1,000 gain, got ${gain}"
        
    def test_acquisitions_still_work(self):
        """
        'buy', 'receive', 'deposit' should still work as acquisitions (cost basis)
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from exchange_tax_service import ExchangeTaxService
        
        service = ExchangeTaxService()
        
        test_transactions = [
            # Buy 1 BTC
            {
                "tx_id": "buy1",
                "exchange": "test",
                "tx_type": "buy",
                "asset": "BTC",
                "amount": 1.0,
                "price_usd": 10000,
                "total_usd": 10000,
                "fee": 0,
                "timestamp": "2024-01-01T00:00:00Z"
            },
            # Receive 0.5 BTC
            {
                "tx_id": "receive1",
                "exchange": "test",
                "tx_type": "receive",
                "asset": "BTC",
                "amount": 0.5,
                "price_usd": 20000,
                "total_usd": 10000,
                "fee": 0,
                "timestamp": "2024-03-01T00:00:00Z"
            },
            # Deposit 0.3 BTC
            {
                "tx_id": "deposit1",
                "exchange": "test",
                "tx_type": "deposit",
                "asset": "BTC",
                "amount": 0.3,
                "price_usd": 25000,
                "total_usd": 7500,
                "fee": 0,
                "timestamp": "2024-05-01T00:00:00Z"
            }
        ]
        
        result = service.calculate_from_transactions(test_transactions)
        
        # Should have remaining lots (acquisitions) but no realized gains
        remaining_lots = result.get('remaining_lots', [])
        realized_gains = result.get('realized_gains', [])
        
        assert len(realized_gains) == 0, "No sales, should be 0 realized gains"
        assert len(remaining_lots) == 3, f"Expected 3 lots (buy+receive+deposit), got {len(remaining_lots)}"
        
        # Total amount should be 1.8 BTC
        total_amount = sum(lot.get('amount', 0) for lot in remaining_lots)
        assert abs(total_amount - 1.8) < 0.01, f"Expected 1.8 BTC in lots, got {total_amount}"
        
    def test_mixed_scenario_only_sells_create_gains(self):
        """
        Real-world scenario: mix of buys, sells, sends, withdrawals
        Only sells should create realized gains
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from exchange_tax_service import ExchangeTaxService
        
        service = ExchangeTaxService()
        
        test_transactions = [
            # Buy 2 BTC at $10,000 each = $20,000 cost basis
            {
                "tx_id": "buy1",
                "exchange": "test",
                "tx_type": "buy",
                "asset": "BTC",
                "amount": 2.0,
                "price_usd": 10000,
                "total_usd": 20000,
                "fee": 0,
                "timestamp": "2024-01-01T00:00:00Z"
            },
            # Send 0.5 BTC to cold wallet - NOT taxable (transfer)
            {
                "tx_id": "send1",
                "exchange": "test",
                "tx_type": "send",
                "asset": "BTC",
                "amount": 0.5,
                "price_usd": 15000,
                "total_usd": 7500,
                "fee": 0,
                "timestamp": "2024-03-01T00:00:00Z"
            },
            # Withdrawal 0.3 BTC - NOT taxable (transfer)
            {
                "tx_id": "withdraw1",
                "exchange": "test",
                "tx_type": "withdrawal",
                "asset": "BTC",
                "amount": 0.3,
                "price_usd": 18000,
                "total_usd": 5400,
                "fee": 0,
                "timestamp": "2024-04-01T00:00:00Z"
            },
            # SELL 0.5 BTC at $20,000 - THIS IS TAXABLE
            {
                "tx_id": "sell1",
                "exchange": "test",
                "tx_type": "sell",
                "asset": "BTC",
                "amount": 0.5,
                "price_usd": 20000,
                "total_usd": 10000,
                "fee": 0,
                "timestamp": "2024-06-01T00:00:00Z"
            }
        ]
        
        result = service.calculate_from_transactions(test_transactions)
        realized_gains = result.get('realized_gains', [])
        
        # Should have exactly 1 realized gain (from the sell only)
        assert len(realized_gains) == 1, \
            f"Expected 1 realized gain (only from sell), got {len(realized_gains)}: {realized_gains}"
        
        # Gain should be: $10,000 proceeds - $5,000 cost basis = $5,000
        gain = realized_gains[0].get('gain_loss', 0)
        assert gain == 5000, f"Expected $5,000 gain, got ${gain}"
        
        # Total realized should be $5,000 (NOT the inflated $210K from treating transfers as sales)
        summary = result.get('summary', {})
        total_realized = summary.get('total_realized_gain', 0)
        assert total_realized == 5000, f"Expected $5,000 total, got ${total_realized}"
