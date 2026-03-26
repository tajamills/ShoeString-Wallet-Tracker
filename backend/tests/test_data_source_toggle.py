"""
Tests for Unified Tax Data Source Toggle Feature
Tests the data_source parameter ('wallet_only', 'exchange_only', 'combined')
and data_sources_used response field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://portfolio-gains-calc.preview.emergentagent.com').rstrip('/')

# Test data
TEST_WALLET_ADDRESS = "0x742d35Cc6634C0532925a3b844Bc9e7595f5fEb6"


class TestDataSourceToggle:
    """Test the data_source parameter in /api/tax/unified endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token, free_user_auth_token):
        """Setup test clients"""
        self.client = api_client
        self.premium_token = premium_auth_token
        self.free_token, self.free_email = free_user_auth_token
    
    def get_headers(self, token):
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # ==================== DATA SOURCE PARAMETER TESTS ====================
    
    def test_wallet_only_data_source(self):
        """Test data_source='wallet_only' returns only wallet transactions"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.premium_token),
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "data_source": "wallet_only"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify data_source in response
        assert data.get("data_source") == "wallet_only"
        
        # Verify data_sources_used structure
        data_sources_used = data.get("data_sources_used", {})
        # Note: wallet boolean depends on if wallet has transactions
        # For this test wallet, it may or may not have transactions
        assert data_sources_used.get("exchange") is False, "Exchange should be False for wallet_only"
        assert data_sources_used.get("exchange_tx_count") == 0, "Exchange tx count should be 0"
        # wallet_tx_count can be >= 0 depending on the wallet
        assert isinstance(data_sources_used.get("wallet_tx_count"), int)
    
    def test_exchange_only_data_source(self):
        """Test data_source='exchange_only' returns only exchange transactions"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.premium_token),
            json={
                "chain": "ethereum",
                "data_source": "exchange_only"
                # Note: address is optional for exchange_only
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify data_source in response
        assert data.get("data_source") == "exchange_only"
        
        # Verify data_sources_used structure
        data_sources_used = data.get("data_sources_used", {})
        assert data_sources_used.get("wallet") is False, "Wallet should be False for exchange_only"
        assert data_sources_used.get("wallet_tx_count") == 0, "Wallet tx count should be 0"
    
    def test_combined_data_source(self):
        """Test data_source='combined' returns both wallet and exchange transactions"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.premium_token),
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "data_source": "combined"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify data_source in response
        assert data.get("data_source") == "combined"
        
        # Verify data_sources_used structure exists
        data_sources_used = data.get("data_sources_used", {})
        assert "wallet" in data_sources_used
        assert "exchange" in data_sources_used
        assert "wallet_tx_count" in data_sources_used
        assert "exchange_tx_count" in data_sources_used
    
    def test_default_data_source_is_combined(self):
        """Test that default data_source is 'combined' when not specified"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.premium_token),
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum"
                # data_source not specified - should default to combined
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("data_source") == "combined", "Default data_source should be 'combined'"
    
    # ==================== DATA SOURCES USED RESPONSE TESTS ====================
    
    def test_data_sources_used_structure(self):
        """Test data_sources_used object has all required fields"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.premium_token),
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "data_source": "combined"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        data_sources_used = data.get("data_sources_used", {})
        
        # Verify all required fields exist
        required_fields = ["wallet", "wallet_tx_count", "exchange", "exchange_tx_count"]
        for field in required_fields:
            assert field in data_sources_used, f"Missing field: {field}"
        
        # Verify types
        assert isinstance(data_sources_used["wallet"], bool), "wallet should be boolean"
        assert isinstance(data_sources_used["exchange"], bool), "exchange should be boolean"
        assert isinstance(data_sources_used["wallet_tx_count"], int), "wallet_tx_count should be int"
        assert isinstance(data_sources_used["exchange_tx_count"], int), "exchange_tx_count should be int"
    
    def test_wallet_only_excludes_exchange_data(self):
        """Test wallet_only truly excludes exchange transactions"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.premium_token),
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "data_source": "wallet_only"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        tax_data = data.get("tax_data", {})
        sources = tax_data.get("sources", {})
        
        # Exchange count should be 0
        assert sources.get("exchange_count", 0) == 0, "Exchange count should be 0 for wallet_only"
    
    def test_exchange_only_excludes_wallet_data(self):
        """Test exchange_only truly excludes wallet transactions"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.premium_token),
            json={
                "chain": "ethereum",
                "data_source": "exchange_only"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        tax_data = data.get("tax_data", {})
        sources = tax_data.get("sources", {})
        
        # Wallet count should be 0
        assert sources.get("wallet_count", 0) == 0, "Wallet count should be 0 for exchange_only"
    
    # ==================== VALIDATION TESTS ====================
    
    def test_wallet_only_requires_address(self):
        """Test that wallet_only data_source requires an address"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.premium_token),
            json={
                "chain": "ethereum",
                "data_source": "wallet_only"
                # No address provided
            }
        )
        # Should return 400 for missing address
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        assert "address" in response.text.lower() or "required" in response.text.lower()
    
    def test_combined_requires_address(self):
        """Test that combined data_source requires an address"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.premium_token),
            json={
                "chain": "ethereum",
                "data_source": "combined"
                # No address provided
            }
        )
        # Should return 400 for missing address
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    
    def test_exchange_only_does_not_require_address(self):
        """Test that exchange_only data_source does NOT require an address"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.premium_token),
            json={
                "chain": "ethereum",
                "data_source": "exchange_only"
                # No address - should still work
            }
        )
        # Should succeed without address
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"


class TestStablecoinExclusion:
    """Test that stablecoins are excluded from cost basis calculations"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token):
        """Setup test clients"""
        self.client = api_client
        self.premium_token = premium_auth_token
        
        # Import from parent directory
        import sys
        sys.path.insert(0, '/app/backend')
    
    def get_headers(self, token):
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_stablecoins_set_defined(self):
        """Test that STABLECOINS set is defined in exchange_tax_service"""
        import sys
        sys.path.insert(0, '/app/backend')
        from exchange_tax_service import ExchangeTaxService
        
        # Verify STABLECOINS set exists
        assert hasattr(ExchangeTaxService, 'STABLECOINS'), "STABLECOINS set should be defined"
        
        # Verify expected stablecoins are included
        expected_stablecoins = {'USDC', 'USDT', 'BUSD', 'DAI'}
        for coin in expected_stablecoins:
            assert coin in ExchangeTaxService.STABLECOINS, f"{coin} should be in STABLECOINS"
    
    def test_is_stablecoin_method(self):
        """Test _is_stablecoin helper method"""
        import sys
        sys.path.insert(0, '/app/backend')
        from exchange_tax_service import ExchangeTaxService
        
        service = ExchangeTaxService()
        
        # Should return True for stablecoins
        assert service._is_stablecoin('USDC') is True
        assert service._is_stablecoin('USDT') is True
        assert service._is_stablecoin('usdc') is True  # case insensitive
        
        # Should return False for non-stablecoins
        assert service._is_stablecoin('BTC') is False
        assert service._is_stablecoin('ETH') is False
        assert service._is_stablecoin('SOL') is False
    
    def test_exchange_tax_excludes_stablecoins(self):
        """Test that exchange tax calculation excludes stablecoin transactions"""
        import sys
        sys.path.insert(0, '/app/backend')
        from exchange_tax_service import exchange_tax_service
        
        # Create test transactions including stablecoins
        transactions = [
            {
                'tx_id': 'tx1',
                'exchange': 'coinbase',
                'tx_type': 'buy',
                'asset': 'BTC',
                'amount': 0.1,
                'price_usd': 50000,
                'total_usd': 5000,
                'timestamp': '2024-01-15T10:00:00Z'
            },
            {
                'tx_id': 'tx2',
                'exchange': 'coinbase',
                'tx_type': 'buy',
                'asset': 'USDC',  # Stablecoin - should be excluded
                'amount': 1000,
                'price_usd': 1,
                'total_usd': 1000,
                'timestamp': '2024-01-16T10:00:00Z'
            },
            {
                'tx_id': 'tx3',
                'exchange': 'coinbase',
                'tx_type': 'sell',
                'asset': 'USDT',  # Stablecoin - should be excluded
                'amount': 500,
                'price_usd': 1,
                'total_usd': 500,
                'timestamp': '2024-01-17T10:00:00Z'
            }
        ]
        
        result = exchange_tax_service.calculate_from_transactions(transactions)
        
        # Should only process BTC, not stablecoins
        assert result['total_transactions'] == 1, "Should only have 1 transaction (BTC), stablecoins excluded"
        
        # Asset summary should only have BTC
        assets = [a['asset'] for a in result.get('asset_summary', [])]
        assert 'BTC' in assets or len(assets) == 0  # BTC should be there if any
        assert 'USDC' not in assets, "USDC should be excluded"
        assert 'USDT' not in assets, "USDT should be excluded"


class TestFreeTierAccess:
    """Test that free users are blocked from unified tax calculation"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, free_user_auth_token):
        """Setup test clients"""
        self.client = api_client
        self.free_token, self.free_email = free_user_auth_token
    
    def get_headers(self, token):
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_free_user_blocked_wallet_only(self):
        """Test free user is blocked from wallet_only data source"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.free_token),
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "data_source": "wallet_only"
            }
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    def test_free_user_blocked_exchange_only(self):
        """Test free user is blocked from exchange_only data source"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.free_token),
            json={
                "chain": "ethereum",
                "data_source": "exchange_only"
            }
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    def test_free_user_blocked_combined(self):
        """Test free user is blocked from combined data source"""
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.get_headers(self.free_token),
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "data_source": "combined"
            }
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
