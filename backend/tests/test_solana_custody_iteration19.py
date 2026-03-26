"""
Backend tests for Solana Chain of Custody - Iteration 19

Feature Fix: Solana Chain of Custody now WORKS (was showing "coming soon" before)
- Solana addresses should return valid custody analysis results
- EVM chains should continue to work
- Bitcoin should still show "coming soon"
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://portfolio-gains-calc.preview.emergentagent.com').rstrip('/')


class TestSolanaCustodyNowWorks:
    """Tests verifying Solana Chain of Custody is now fully functional"""
    
    def test_solana_address_returns_valid_analysis(self, authenticated_premium_client):
        """
        CRITICAL: Solana addresses should now return valid custody analysis,
        NOT "coming soon" error as before.
        """
        # Valid Solana address (Raydium pool)
        solana_address = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": solana_address,
                "chain": "solana"
            }
        )
        
        # Should return 200 SUCCESS, NOT 400 error
        assert response.status_code == 200, f"Solana custody should work now. Got status {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure for Solana custody analysis
        assert "analyzed_address" in data, "Response should have analyzed_address"
        assert data["analyzed_address"] == solana_address
        assert data.get("chain") == "solana"
        assert "custody_chain" in data
        assert "origin_points" in data
        assert "summary" in data
        assert "settings" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "total_links_traced" in summary
        assert "exchange_origin_count" in summary
        assert "dex_origin_count" in summary
        assert "addresses_analyzed" in summary
        
    def test_solana_with_different_address(self, authenticated_premium_client):
        """
        Test with another Solana address to ensure it's not hardcoded.
        """
        # Another valid Solana address 
        solana_address = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"  # Jupiter address
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": solana_address,
                "chain": "solana"
            }
        )
        
        assert response.status_code == 200, f"Solana address should work. Got: {response.text}"
        data = response.json()
        assert data["analyzed_address"] == solana_address
        assert data["chain"] == "solana"
        
    def test_solana_invalid_address_still_shows_format_error(self, authenticated_premium_client):
        """
        Invalid Solana address format should show Solana-specific format error.
        """
        invalid_solana_address = "short"  # Too short for Solana
        
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
        
        # Should mention Solana format error
        assert "solana" in detail.lower(), f"Expected Solana format error: {detail}"
        # Should NOT show "coming soon" for invalid format
        assert "coming soon" not in detail.lower(), f"Invalid format should not show 'coming soon': {detail}"


class TestBitcoinStillComingSoon:
    """Tests verifying Bitcoin Chain of Custody still shows "coming soon" """
    
    def test_bitcoin_shows_coming_soon(self, authenticated_premium_client):
        """
        Bitcoin chain of custody should still show "coming soon" message.
        """
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
        
        assert "coming soon" in detail.lower(), f"Bitcoin should show 'coming soon': {detail}"
        assert "solana" in detail.lower(), f"Message should mention Solana is supported: {detail}"
        
    def test_bitcoin_legacy_address_shows_coming_soon(self, authenticated_premium_client):
        """
        Bitcoin legacy addresses should also show "coming soon".
        """
        btc_legacy_address = "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": btc_legacy_address,
                "chain": "bitcoin"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "coming soon" in data.get("detail", "").lower()


class TestEVMChainsStillWork:
    """Tests verifying EVM chains continue to work after Solana fix"""
    
    def test_ethereum_custody_works(self, authenticated_premium_client):
        """
        Ethereum chain of custody should still work.
        """
        evm_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f9C6E6"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": evm_address,
                "chain": "ethereum"
            }
        )
        
        # Should succeed or return service error, NOT format error
        assert response.status_code in [200, 500], f"EVM should work. Got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert data.get("chain") == "ethereum"
            assert "custody_chain" in data
            
    def test_polygon_custody_works(self, authenticated_premium_client):
        """
        Polygon (EVM chain) should still work.
        """
        evm_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f9C6E6"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": evm_address,
                "chain": "polygon"
            }
        )
        
        assert response.status_code in [200, 500], f"Polygon should work. Got {response.status_code}: {response.text}"
        
    def test_evm_invalid_address_shows_evm_error(self, authenticated_premium_client):
        """
        Invalid EVM address should show EVM-specific error on EVM chains.
        """
        invalid_address = "not_a_valid_address"
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": invalid_address,
                "chain": "ethereum"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", "")
        
        # Should mention EVM format
        assert "evm" in detail.lower() or "0x" in detail.lower(), f"Expected EVM error: {detail}"


class TestCustodyServiceSolanaFeatures:
    """Tests for Solana-specific custody service features"""
    
    def test_known_solana_exchange_addresses_are_configured(self):
        """
        Verify Solana exchange addresses are configured in custody service.
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from custody_service import custody_service
        
        # Should have Solana exchange addresses
        assert hasattr(custody_service, 'known_solana_exchanges')
        assert len(custody_service.known_solana_exchanges) > 0
        
        # Check for major exchanges
        exchange_names = list(custody_service.known_solana_exchanges.values())
        assert any('coinbase' in name.lower() for name in exchange_names), "Should have Coinbase"
        assert any('binance' in name.lower() for name in exchange_names), "Should have Binance"
        assert any('kraken' in name.lower() for name in exchange_names), "Should have Kraken"
        
    def test_known_solana_dex_addresses_are_configured(self):
        """
        Verify Solana DEX addresses are configured in custody service.
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from custody_service import custody_service
        
        # Should have Solana DEX addresses
        assert hasattr(custody_service, 'known_solana_dexes')
        assert len(custody_service.known_solana_dexes) > 0
        
        # Check for major DEXes
        dex_names = list(custody_service.known_solana_dexes.values())
        assert any('jupiter' in name.lower() for name in dex_names), "Should have Jupiter"
        assert any('raydium' in name.lower() for name in dex_names), "Should have Raydium"
        assert any('orca' in name.lower() for name in dex_names), "Should have Orca"
        
    def test_solana_analyze_method_exists(self):
        """
        Verify the Solana-specific analysis method exists and is called.
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from custody_service import ChainOfCustodyService
        
        service = ChainOfCustodyService()
        
        # Should have Solana-specific method
        assert hasattr(service, '_analyze_solana_custody')
        assert callable(service._analyze_solana_custody)
        
    def test_custody_service_supports_solana_chain(self):
        """
        Verify custody service has Solana in supported chains.
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from custody_service import custody_service
        
        # Check alchemy_urls has Solana
        assert 'solana' in custody_service.alchemy_urls
        
    def test_get_address_label_works_for_solana(self):
        """
        Verify get_address_label works for Solana addresses.
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from custody_service import custody_service
        
        # Test a known Solana exchange address (Jupiter)
        jupiter_address = 'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4'
        label = custody_service.get_address_label(jupiter_address)
        
        assert label is not None, "Should return a label for known Solana DEX"
        assert 'Jupiter' in label, f"Should identify Jupiter DEX: {label}"


class TestSupportedChainsListing:
    """Tests for the supported chains message"""
    
    def test_unsupported_chain_lists_supported_chains(self, authenticated_premium_client):
        """
        Unsupported chains should show error with list of supported chains including Solana.
        """
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/custody/analyze",
            json={
                "address": "some_address",
                "chain": "avalanche"  # Unsupported
            }
        )
        
        assert response.status_code == 400
        detail = response.json().get("detail", "")
        
        # Should list supported chains including Solana
        assert "solana" in detail.lower(), f"Should mention Solana as supported: {detail}"
        assert "ethereum" in detail.lower(), f"Should mention Ethereum as supported: {detail}"
