"""
Backend tests for Exchange Integration feature
Tests the Crypto Bag Tracker exchange API endpoints
"""

import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://wallet-tax-hub.preview.emergentagent.com').rstrip('/')


class TestExchangeSupportedEndpoint:
    """Tests for GET /api/exchanges/supported - public endpoint"""
    
    def test_get_supported_exchanges(self, api_client):
        """Test that supported exchanges returns Coinbase and Binance"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/supported")
        
        assert response.status_code == 200
        data = response.json()
        assert "exchanges" in data
        assert len(data["exchanges"]) >= 2
        
        # Check for expected exchanges
        exchange_ids = [ex["id"] for ex in data["exchanges"]]
        assert "coinbase" in exchange_ids
        assert "binance" in exchange_ids
        
    def test_supported_exchanges_structure(self, api_client):
        """Test the response structure for supported exchanges"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/supported")
        
        assert response.status_code == 200
        data = response.json()
        
        for exchange in data["exchanges"]:
            assert "id" in exchange
            assert "name" in exchange
            assert "auth_type" in exchange
            assert "description" in exchange
            assert "features" in exchange
            
    def test_coinbase_exchange_details(self, api_client):
        """Test Coinbase exchange has correct auth type and features"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/supported")
        
        assert response.status_code == 200
        data = response.json()
        
        coinbase = next((ex for ex in data["exchanges"] if ex["id"] == "coinbase"), None)
        assert coinbase is not None
        assert coinbase["auth_type"] == "oauth2"
        assert "trades" in coinbase["features"]
        
    def test_binance_exchange_details(self, api_client):
        """Test Binance exchange has correct auth type"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/supported")
        
        assert response.status_code == 200
        data = response.json()
        
        binance = next((ex for ex in data["exchanges"] if ex["id"] == "binance"), None)
        assert binance is not None
        assert binance["auth_type"] == "api_key"


class TestExchangeConnectEndpoint:
    """Tests for POST /api/exchanges/connect - requires auth and Unlimited subscription"""
    
    def test_connect_requires_authentication(self, api_client):
        """Test that connecting exchange requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/exchanges/connect", json={
            "exchange": "coinbase",
            "access_token": "fake_token"
        })
        
        # Should return 401 or 403 when not authenticated
        assert response.status_code in [401, 403]
        
    def test_free_user_cannot_connect_exchange(self, authenticated_free_client):
        """Test that FREE users get 403 when trying to connect exchange"""
        client, email = authenticated_free_client
        
        response = client.post(f"{BASE_URL}/api/exchanges/connect", json={
            "exchange": "coinbase",
            "access_token": "test_token"
        })
        
        assert response.status_code == 403
        assert "Unlimited" in response.json().get("detail", "") or "upgrade" in response.json().get("detail", "").lower()
        
    def test_connect_coinbase_requires_access_token(self, authenticated_premium_client):
        """Test that connecting Coinbase requires an access token"""
        response = authenticated_premium_client.post(f"{BASE_URL}/api/exchanges/connect", json={
            "exchange": "coinbase"
        })
        
        assert response.status_code == 400
        assert "access_token" in response.json().get("detail", "").lower() or "token" in response.json().get("detail", "").lower()
        
    def test_connect_binance_requires_api_credentials(self, authenticated_premium_client):
        """Test that connecting Binance requires API key and secret"""
        # Missing api_key
        response = authenticated_premium_client.post(f"{BASE_URL}/api/exchanges/connect", json={
            "exchange": "binance",
            "api_secret": "test_secret"
        })
        
        assert response.status_code == 400
        
        # Missing api_secret
        response = authenticated_premium_client.post(f"{BASE_URL}/api/exchanges/connect", json={
            "exchange": "binance",
            "api_key": "test_key"
        })
        
        assert response.status_code == 400
        
    def test_connect_unsupported_exchange(self, authenticated_premium_client):
        """Test that connecting unsupported exchange returns error"""
        response = authenticated_premium_client.post(f"{BASE_URL}/api/exchanges/connect", json={
            "exchange": "kraken",  # Not supported
            "api_key": "test_key",
            "api_secret": "test_secret"
        })
        
        assert response.status_code == 400
        assert "unsupported" in response.json().get("detail", "").lower()


class TestExchangeConnectedEndpoint:
    """Tests for GET /api/exchanges/connected - requires auth"""
    
    def test_connected_requires_authentication(self, api_client):
        """Test that getting connected exchanges requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/connected")
        
        assert response.status_code in [401, 403]
        
    def test_get_connected_exchanges_empty(self, authenticated_premium_client):
        """Test getting connected exchanges when none are connected"""
        response = authenticated_premium_client.get(f"{BASE_URL}/api/exchanges/connected")
        
        assert response.status_code == 200
        data = response.json()
        assert "exchanges" in data
        assert isinstance(data["exchanges"], list)


class TestExchangeDisconnectEndpoint:
    """Tests for DELETE /api/exchanges/{exchange_id} - requires auth"""
    
    def test_disconnect_requires_authentication(self, api_client):
        """Test that disconnecting exchange requires authentication"""
        response = api_client.delete(f"{BASE_URL}/api/exchanges/coinbase")
        
        assert response.status_code in [401, 403]
        
    def test_disconnect_not_connected_exchange(self, authenticated_premium_client):
        """Test disconnecting an exchange that's not connected returns 404"""
        # Try to disconnect an exchange that was never connected
        response = authenticated_premium_client.delete(f"{BASE_URL}/api/exchanges/nonexistent")
        
        assert response.status_code == 404
        assert "not connected" in response.json().get("detail", "").lower() or "not found" in response.json().get("detail", "").lower()


class TestExchangeSyncEndpoint:
    """Tests for POST /api/exchanges/{exchange_id}/sync - requires auth and Unlimited"""
    
    def test_sync_requires_authentication(self, api_client):
        """Test that syncing exchange requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/exchanges/coinbase/sync")
        
        assert response.status_code in [401, 403]
        
    def test_free_user_cannot_sync(self, authenticated_free_client):
        """Test that FREE users get 403 when trying to sync exchange"""
        client, email = authenticated_free_client
        
        response = client.post(f"{BASE_URL}/api/exchanges/coinbase/sync")
        
        assert response.status_code == 403
        
    def test_sync_not_connected_exchange(self, authenticated_premium_client):
        """Test syncing an exchange that's not connected returns 404"""
        response = authenticated_premium_client.post(f"{BASE_URL}/api/exchanges/nonexistent/sync")
        
        assert response.status_code == 404


class TestExchangeTransactionsEndpoint:
    """Tests for GET /api/exchanges/transactions - requires auth and Unlimited"""
    
    def test_transactions_requires_authentication(self, api_client):
        """Test that getting exchange transactions requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/transactions")
        
        assert response.status_code in [401, 403]
        
    def test_free_user_cannot_get_transactions(self, authenticated_free_client):
        """Test that FREE users get 403 when trying to get transactions"""
        client, email = authenticated_free_client
        
        response = client.get(f"{BASE_URL}/api/exchanges/transactions")
        
        assert response.status_code == 403
        assert "Unlimited" in response.json().get("detail", "") or "subscription" in response.json().get("detail", "").lower()
        
    def test_get_transactions_empty(self, authenticated_premium_client):
        """Test getting transactions when no exchanges connected returns empty list"""
        response = authenticated_premium_client.get(f"{BASE_URL}/api/exchanges/transactions")
        
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        assert "summary" in data
        
    def test_transactions_supports_filters(self, authenticated_premium_client):
        """Test that transactions endpoint accepts filter params"""
        # Test with limit param
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/transactions",
            params={"limit": 10}
        )
        assert response.status_code == 200
        
        # Test with exchange filter
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/transactions",
            params={"exchange": "coinbase"}
        )
        assert response.status_code == 200


class TestExchangeIntegrationFlow:
    """Integration tests for the full exchange flow"""
    
    def test_full_flow_free_user_blocked(self, authenticated_free_client):
        """Test that free users are blocked at every step"""
        client, email = authenticated_free_client
        
        # Can view supported exchanges (public)
        response = client.get(f"{BASE_URL}/api/exchanges/supported")
        assert response.status_code == 200
        
        # Cannot connect
        response = client.post(f"{BASE_URL}/api/exchanges/connect", json={
            "exchange": "coinbase",
            "access_token": "test"
        })
        assert response.status_code == 403
        
        # Cannot sync
        response = client.post(f"{BASE_URL}/api/exchanges/coinbase/sync")
        assert response.status_code == 403
        
        # Cannot get transactions
        response = client.get(f"{BASE_URL}/api/exchanges/transactions")
        assert response.status_code == 403
