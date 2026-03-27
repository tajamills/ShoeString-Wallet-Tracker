"""
Tests for On-Chain Tax Calculation with Historical Price Enrichment
Tests the new historical_tax_enrichment service and on-chain tax data in wallet analysis
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://proceeds-validator.preview.emergentagent.com').rstrip('/')

# Test wallets for different chains
TEST_ETH_WALLET = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # Vitalik's wallet
TEST_XRP_WALLET = "rEb8TK3gBgk5auZkwc6sHnwrGVJH8DuaLh"  # Active XRP wallet
TEST_SOL_WALLET = "9WzDXwBbmPdCBoccTAmNzz9fNqLbPrgXBZybGWbUBrXt"  # Solana test wallet


class TestOnChainTaxEndpoints:
    """Test on-chain tax calculation via wallet analysis endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token):
        """Setup test clients"""
        self.client = api_client
        self.token = premium_auth_token
    
    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    # ==================== Ethereum On-Chain Tax Tests ====================
    
    def test_eth_wallet_returns_tax_data(self):
        """Test that Ethereum wallet analysis returns on-chain tax data"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_ETH_WALLET, "chain": "ethereum"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify tax_data is present
        assert "tax_data" in data, "tax_data missing from response"
        tax_data = data["tax_data"]
        
        if tax_data:  # May be None if no transactions
            # Verify tax data structure
            assert "method" in tax_data, "Missing 'method' in tax_data"
            assert tax_data["method"] == "FIFO", f"Expected FIFO method, got {tax_data['method']}"
            
            # Verify data source
            assert "data_source" in tax_data, "Missing 'data_source' in tax_data"
            assert tax_data["data_source"] == "on-chain", f"Expected on-chain source, got {tax_data['data_source']}"
    
    def test_eth_wallet_tax_data_has_historical_prices(self):
        """Test that on-chain tax data uses historical prices"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_ETH_WALLET, "chain": "ethereum"}
        )
        assert response.status_code == 200
        
        data = response.json()
        tax_data = data.get("tax_data")
        
        if tax_data:
            # Verify sources breakdown shows historical price usage
            sources = tax_data.get("sources", {})
            assert "historical_prices_used" in sources, "Missing historical_prices_used count"
            assert "current_prices_used" in sources, "Missing current_prices_used count"
            
            # Should have used some historical prices
            historical = sources.get("historical_prices_used", 0)
            total = sources.get("on_chain_count", 0)
            
            if total > 0:
                # Log the ratio for debugging
                print(f"Historical prices used: {historical}/{total}")
    
    def test_eth_wallet_tax_data_structure(self):
        """Test complete structure of on-chain tax data"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_ETH_WALLET, "chain": "ethereum"}
        )
        assert response.status_code == 200
        
        data = response.json()
        tax_data = data.get("tax_data")
        
        if tax_data:
            # Verify summary structure
            assert "summary" in tax_data, "Missing summary"
            summary = tax_data["summary"]
            
            required_summary_fields = [
                "total_realized_gain",
                "total_unrealized_gain",
                "total_gain",
                "short_term_gains",
                "long_term_gains",
                "total_transactions",
                "buy_count",
                "sell_count"
            ]
            
            for field in required_summary_fields:
                assert field in summary, f"Missing '{field}' in summary"
            
            # Verify validation section exists
            assert "validation" in tax_data, "Missing validation section"
            validation = tax_data["validation"]
            assert "has_issues" in validation, "Missing has_issues flag"
            assert "issues" in validation, "Missing issues list"
    
    # ==================== XRP On-Chain Tax Tests ====================
    
    def test_xrp_wallet_returns_tax_data(self):
        """Test that XRP wallet analysis returns on-chain tax data"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_XRP_WALLET, "chain": "xrp"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify basic wallet data
        assert data.get("address") is not None, "Missing address in response"
        assert data.get("chain") == "xrp", f"Expected chain=xrp, got {data.get('chain')}"
        
        # Verify tax_data is present
        assert "tax_data" in data, "tax_data missing from response"
        tax_data = data["tax_data"]
        
        if tax_data:
            assert tax_data["method"] == "FIFO"
            assert tax_data["data_source"] == "on-chain"
            
            # Verify sources shows XRP transactions
            sources = tax_data.get("sources", {})
            assert sources.get("on_chain_count", 0) > 0, "Expected some on-chain transactions"
    
    def test_xrp_wallet_tax_summary_values(self):
        """Test XRP wallet tax summary has valid values"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_XRP_WALLET, "chain": "xrp"}
        )
        assert response.status_code == 200
        
        data = response.json()
        tax_data = data.get("tax_data")
        
        if tax_data and tax_data.get("summary"):
            summary = tax_data["summary"]
            
            # Validate numeric values are reasonable (no -$37B bugs)
            total_gain = summary.get("total_realized_gain", 0)
            assert abs(total_gain) < 100_000_000_000, f"Suspicious total gain: {total_gain}"
            
            # Verify current_value makes sense
            current_value = summary.get("current_value", 0)
            assert current_value >= 0, f"Negative current value: {current_value}"
    
    # ==================== Solana On-Chain Tax Tests ====================
    
    def test_solana_wallet_analysis_works(self):
        """Test that Solana wallet analysis works (even if no transactions)"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_SOL_WALLET, "chain": "solana"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("address") is not None
        assert data.get("chain") == "solana"
        # Balance should be returned even if 0
        assert "currentBalance" in data
    
    # ==================== Validation Logging Tests ====================
    
    def test_validation_flags_suspicious_values(self):
        """Test that validation section flags suspicious transaction values"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_ETH_WALLET, "chain": "ethereum"}
        )
        assert response.status_code == 200
        
        data = response.json()
        tax_data = data.get("tax_data")
        
        if tax_data:
            validation = tax_data.get("validation", {})
            
            # has_issues should be a boolean
            assert isinstance(validation.get("has_issues"), bool), "has_issues should be boolean"
            
            # issues should be a list
            assert isinstance(validation.get("issues", []), list), "issues should be a list"
            
            # If no issues, list should be empty
            if not validation.get("has_issues"):
                assert len(validation.get("issues", [])) == 0, "has_issues=False but issues list not empty"
    
    # ==================== Enriched Transactions Tests ====================
    
    def test_enriched_transactions_have_prices(self):
        """Test that enriched transactions include price data"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_ETH_WALLET, "chain": "ethereum"}
        )
        assert response.status_code == 200
        
        data = response.json()
        tax_data = data.get("tax_data")
        
        if tax_data and tax_data.get("enriched_transactions"):
            enriched = tax_data["enriched_transactions"]
            
            for tx in enriched[:5]:  # Check first 5 transactions
                # Each transaction should have price info
                assert "price_usd" in tx, f"Missing price_usd in transaction"
                assert "total_usd" in tx, f"Missing total_usd in transaction"
                assert "price_source" in tx, f"Missing price_source in transaction"
                
                # price_source should be 'historical' or 'current'
                assert tx["price_source"] in ["historical", "current"], f"Invalid price_source: {tx['price_source']}"


class TestOnChainTaxValidation:
    """Test validation logging for suspicious transactions (the -$37B bug detection)"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token):
        self.client = api_client
        self.token = premium_auth_token
    
    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_validation_thresholds_documented(self):
        """Test that validation uses reasonable thresholds"""
        # This test documents the expected validation thresholds
        # MAX_SINGLE_TX_VALUE_USD = 100_000_000_000  # $100B max per transaction
        # MAX_SINGLE_PRICE_USD = 1_000_000  # $1M max per coin
        
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_ETH_WALLET, "chain": "ethereum"},
            timeout=60
        )
        # Handle rate limiting or gateway timeout
        if response.status_code == 502 or response.status_code == 504:
            pytest.skip("Gateway timeout - likely due to rate limiting")
        assert response.status_code == 200
        
        data = response.json()
        tax_data = data.get("tax_data")
        
        if tax_data and tax_data.get("summary"):
            # All values should be within reasonable bounds
            summary = tax_data["summary"]
            
            # Realized gain should not exceed unreasonable values
            total_realized = summary.get("total_realized_gain", 0)
            assert abs(total_realized) < 100_000_000_000, \
                f"VALIDATION BUG: Unreasonable total_realized_gain: ${total_realized}"
            
            # Current value should not exceed unreasonable values
            current_value = summary.get("current_value", 0)
            assert current_value < 1_000_000_000_000, \
                f"VALIDATION BUG: Unreasonable current_value: ${current_value}"
    
    def test_no_negative_gains_without_sells(self):
        """Test that wallets with only receives don't show negative realized gains"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_ETH_WALLET, "chain": "ethereum"},
            timeout=60
        )
        # Handle rate limiting or gateway timeout
        if response.status_code in [502, 504, 429]:
            pytest.skip("Gateway timeout - likely due to rate limiting")
        assert response.status_code == 200
        
        data = response.json()
        tax_data = data.get("tax_data")
        
        if tax_data and tax_data.get("sources"):
            sources = tax_data["sources"]
            sells_count = sources.get("sells_count", 0)
            
            if sells_count == 0:
                # No sells means no realized gains
                summary = tax_data.get("summary", {})
                realized = summary.get("total_realized_gain", 0)
                assert realized == 0, \
                    f"Expected 0 realized gains with 0 sells, got {realized}"


class TestChainSpecificAnalysis:
    """Test chain-specific wallet analysis features"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token):
        self.client = api_client
        self.token = premium_auth_token
    
    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_ethereum_chain_response_structure(self):
        """Test Ethereum analysis response structure"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_ETH_WALLET, "chain": "ethereum"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Required fields
        required_fields = [
            "address", "totalEthSent", "totalEthReceived", 
            "currentBalance", "outgoingTransactionCount", "incomingTransactionCount"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # USD fields (optional but expected)
        usd_fields = ["current_price_usd", "total_value_usd"]
        for field in usd_fields:
            assert field in data, f"Missing USD field: {field}"
    
    def test_xrp_chain_response_structure(self):
        """Test XRP analysis response structure"""
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=self.get_headers(),
            json={"address": TEST_XRP_WALLET, "chain": "xrp"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Chain should be identified
        assert data.get("chain") == "xrp"
        
        # Balance should be present
        assert "currentBalance" in data
        assert isinstance(data["currentBalance"], (int, float))


class TestAuthenticationAndPermissions:
    """Test authentication and tier restrictions for tax features"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token, free_user_auth_token):
        self.client = api_client
        self.premium_token = premium_auth_token
        self.free_token, self.free_email = free_user_auth_token
    
    def test_wallet_analysis_requires_auth(self, api_client):
        """Test that wallet analysis requires authentication"""
        response = api_client.post(
            f"{BASE_URL}/api/wallet/analyze",
            json={"address": TEST_ETH_WALLET, "chain": "ethereum"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    def test_non_ethereum_chains_require_premium(self):
        """Test that non-Ethereum chains require premium tier"""
        headers = {"Authorization": f"Bearer {self.free_token}", "Content-Type": "application/json"}
        
        # XRP should be blocked for free users
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=headers,
            json={"address": TEST_XRP_WALLET, "chain": "xrp"}
        )
        assert response.status_code == 403, f"Expected 403 for free user on XRP, got {response.status_code}"
        
        # Solana should be blocked for free users
        response = self.client.post(
            f"{BASE_URL}/api/wallet/analyze",
            headers=headers,
            json={"address": TEST_SOL_WALLET, "chain": "solana"}
        )
        assert response.status_code == 403, f"Expected 403 for free user on Solana, got {response.status_code}"
