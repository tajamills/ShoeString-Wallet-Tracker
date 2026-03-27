"""
Backend tests for Exchange CSV Import feature
Tests the Crypto Bag Tracker exchange API endpoints with CSV import approach

Endpoints tested:
- GET /api/exchanges/supported - returns supported exchanges with export instructions
- POST /api/exchanges/import-csv - imports CSV file and auto-detects exchange
- GET /api/exchanges/transactions - returns imported transactions
- DELETE /api/exchanges/transactions - deletes imported transactions
- GET /api/exchanges/export-instructions/{id} - returns step-by-step export guide
"""

import pytest
import requests
import os
import uuid
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://proceeds-validator.preview.emergentagent.com').rstrip('/')


class TestExchangeSupportedEndpoint:
    """Tests for GET /api/exchanges/supported - public endpoint"""
    
    def test_get_supported_exchanges(self, api_client):
        """Test that supported exchanges returns 6 exchanges"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/supported")
        
        assert response.status_code == 200
        data = response.json()
        assert "exchanges" in data
        assert len(data["exchanges"]) == 6
        
        # Check for all expected exchanges
        exchange_ids = [ex["id"] for ex in data["exchanges"]]
        assert "coinbase" in exchange_ids
        assert "binance" in exchange_ids
        assert "kraken" in exchange_ids
        assert "gemini" in exchange_ids
        assert "crypto_com" in exchange_ids
        assert "kucoin" in exchange_ids
        
    def test_supported_exchanges_structure(self, api_client):
        """Test the response structure for supported exchanges"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/supported")
        
        assert response.status_code == 200
        data = response.json()
        
        for exchange in data["exchanges"]:
            assert "id" in exchange
            assert "name" in exchange
            assert "instructions" in exchange  # CSV export instructions
            
    def test_coinbase_exchange_details(self, api_client):
        """Test Coinbase exchange has correct name and instructions"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/supported")
        
        assert response.status_code == 200
        data = response.json()
        
        coinbase = next((ex for ex in data["exchanges"] if ex["id"] == "coinbase"), None)
        assert coinbase is not None
        assert coinbase["name"] == "Coinbase"
        assert "CSV" in coinbase["instructions"] or "Report" in coinbase["instructions"]


class TestExchangeExportInstructionsEndpoint:
    """Tests for GET /api/exchanges/export-instructions/{exchange_id} - public endpoint"""
    
    def test_get_coinbase_instructions(self, api_client):
        """Test getting Coinbase export instructions"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/export-instructions/coinbase")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "name" in data
        assert "steps" in data
        assert data["name"] == "Coinbase"
        assert len(data["steps"]) > 0
        
    def test_get_binance_instructions(self, api_client):
        """Test getting Binance export instructions"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/export-instructions/binance")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "name" in data
        assert "steps" in data
        assert data["name"] == "Binance"
        
    def test_get_kraken_instructions(self, api_client):
        """Test getting Kraken export instructions"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/export-instructions/kraken")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Kraken"
        assert "steps" in data
        
    def test_get_instructions_includes_notes(self, api_client):
        """Test that export instructions include optional notes field"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/export-instructions/coinbase")
        
        assert response.status_code == 200
        data = response.json()
        
        # Notes field should exist (may or may not have value)
        assert "notes" in data
        
    def test_invalid_exchange_returns_404(self, api_client):
        """Test that invalid exchange ID returns 404"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/export-instructions/invalid_exchange")
        
        assert response.status_code == 404


class TestExchangeImportCSVEndpoint:
    """Tests for POST /api/exchanges/import-csv - requires auth and Unlimited subscription"""
    
    def test_import_requires_authentication(self, api_client):
        """Test that importing CSV requires authentication"""
        # Create a simple CSV content
        csv_content = "Timestamp,Transaction Type,Asset,Quantity Transacted\n2024-01-01,Buy,BTC,0.1"
        files = {'file': ('test.csv', csv_content, 'text/csv')}
        
        response = api_client.post(f"{BASE_URL}/api/exchanges/import-csv", files=files)
        
        # Should return 401 or 403 when not authenticated
        assert response.status_code in [401, 403]
        
    def test_free_user_cannot_import_csv(self, authenticated_free_client):
        """Test that FREE users get 403 when trying to import CSV"""
        client, email = authenticated_free_client
        
        csv_content = "Timestamp,Transaction Type,Asset,Quantity Transacted\n2024-01-01,Buy,BTC,0.1"
        files = {'file': ('test.csv', csv_content, 'text/csv')}
        
        # Remove Content-Type for multipart
        headers = {"Authorization": client.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/exchanges/import-csv",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 403
        assert "Unlimited" in response.json().get("detail", "") or "upgrade" in response.json().get("detail", "").lower()
        
    def test_import_requires_csv_file(self, authenticated_premium_client):
        """Test that import endpoint requires a CSV file"""
        # Try uploading non-CSV file
        files = {'file': ('test.txt', 'not csv content', 'text/plain')}
        headers = {"Authorization": authenticated_premium_client.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/exchanges/import-csv",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 400
        assert "CSV" in response.json().get("detail", "") or "csv" in response.json().get("detail", "").lower()


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
        
    def test_get_transactions_returns_structure(self, authenticated_premium_client):
        """Test getting transactions returns proper structure"""
        response = authenticated_premium_client.get(f"{BASE_URL}/api/exchanges/transactions")
        
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        assert "summary" in data or "count" in data
        
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
        
        # Test with asset filter
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/transactions",
            params={"asset": "BTC"}
        )
        assert response.status_code == 200


class TestExchangeDeleteTransactionsEndpoint:
    """Tests for DELETE /api/exchanges/transactions - requires auth"""
    
    def test_delete_requires_authentication(self, api_client):
        """Test that deleting transactions requires authentication"""
        response = api_client.delete(f"{BASE_URL}/api/exchanges/transactions")
        
        assert response.status_code in [401, 403]
        
    def test_delete_returns_count(self, authenticated_premium_client):
        """Test that delete endpoint returns deleted count"""
        response = authenticated_premium_client.delete(f"{BASE_URL}/api/exchanges/transactions")
        
        assert response.status_code == 200
        data = response.json()
        assert "deleted_count" in data or "message" in data
        
    def test_delete_with_exchange_filter(self, authenticated_premium_client):
        """Test deleting transactions with exchange filter"""
        response = authenticated_premium_client.delete(
            f"{BASE_URL}/api/exchanges/transactions",
            params={"exchange": "coinbase"}
        )
        
        assert response.status_code == 200


class TestExchangeIntegrationFlow:
    """Integration tests for the full CSV import flow"""
    
    def test_full_flow_free_user_blocked(self, authenticated_free_client):
        """Test that free users are blocked at every step except public endpoints"""
        client, email = authenticated_free_client
        
        # Can view supported exchanges (public)
        response = client.get(f"{BASE_URL}/api/exchanges/supported")
        assert response.status_code == 200
        
        # Can view export instructions (public)
        response = client.get(f"{BASE_URL}/api/exchanges/export-instructions/coinbase")
        assert response.status_code == 200
        
        # Cannot import CSV
        csv_content = "Timestamp,Transaction Type,Asset,Quantity Transacted\n2024-01-01,Buy,BTC,0.1"
        files = {'file': ('test.csv', csv_content, 'text/csv')}
        headers = {"Authorization": client.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/exchanges/import-csv",
            files=files,
            headers=headers
        )
        assert response.status_code == 403
        
        # Cannot get transactions
        response = client.get(f"{BASE_URL}/api/exchanges/transactions")
        assert response.status_code == 403
        
    def test_all_six_exchanges_have_instructions(self, api_client):
        """Test that all 6 supported exchanges have export instructions"""
        exchanges = ["coinbase", "binance", "kraken", "gemini", "crypto_com", "kucoin"]
        
        for exchange_id in exchanges:
            response = api_client.get(f"{BASE_URL}/api/exchanges/export-instructions/{exchange_id}")
            assert response.status_code == 200, f"Failed to get instructions for {exchange_id}"
            data = response.json()
            assert "name" in data
            assert "steps" in data
            assert len(data["steps"]) > 0, f"No steps for {exchange_id}"
