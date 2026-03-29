"""
Iteration 30 Tests - Tax Summary 2025 Fix & Manual Acquisition Entry
Tests:
1. P0: 2025 Tax Summary API - verify it returns realized gains instead of empty array
2. P1: Manual Acquisition endpoint POST /api/exchanges/manual-acquisition
3. P1: Orphan Disposal Summary endpoint GET /api/exchanges/orphan-disposal-summary
4. P1: Manual Acquisitions list endpoint GET /api/exchanges/manual-acquisitions
5. P1: Delete Manual Acquisition endpoint DELETE /api/exchanges/manual-acquisition/{tx_id}
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://proceeds-validator.preview.emergentagent.com').rstrip('/')


class TestTaxSummary2025:
    """P0: Test 2025 Tax Summary API - verify timestamp normalization fix"""
    
    def test_unified_tax_2025_returns_structure(self, authenticated_premium_client):
        """Verify 2025 tax summary returns proper structure (not empty array)"""
        # Use exchange_only data source which doesn't require wallet address
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/unified",
            json={"tax_year": 2025, "data_source": "exchange_only"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "tax_data" in data, "Response should contain tax_data"
        
        tax_data = data["tax_data"]
        # Verify it's a dict, not an empty array (the bug was returning [])
        assert isinstance(tax_data, dict), f"tax_data should be dict, got {type(tax_data)}"
        
        # Verify required fields exist
        assert "summary" in tax_data, "tax_data should have summary"
        assert "realized_gains" in tax_data, "tax_data should have realized_gains"
        
        # Verify summary has numeric fields
        summary = tax_data["summary"]
        assert "total_realized_gain" in summary, "summary should have total_realized_gain"
        assert "short_term_gains" in summary, "summary should have short_term_gains"
        assert "long_term_gains" in summary, "summary should have long_term_gains"
        
        print(f"2025 Tax Summary: total_realized_gain={summary.get('total_realized_gain')}")
        print(f"Test PASSED: 2025 tax summary returns proper dict structure")
    
    def test_unified_tax_2024_still_works(self, authenticated_premium_client):
        """Verify 2024 tax summary still works after fix"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/unified",
            json={"tax_year": 2024, "data_source": "exchange_only"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "tax_data" in data
        assert isinstance(data["tax_data"], dict)
        print("Test PASSED: 2024 tax summary still works")
    
    def test_unified_tax_no_year_filter(self, authenticated_premium_client):
        """Verify tax summary works without year filter"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/unified",
            json={"data_source": "exchange_only"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "tax_data" in data
        assert isinstance(data["tax_data"], dict)
        print("Test PASSED: Tax summary without year filter works")


class TestManualAcquisitionEndpoints:
    """P1: Test Manual Acquisition CRUD endpoints"""
    
    def test_add_manual_acquisition_success(self, authenticated_premium_client):
        """Test adding a manual acquisition"""
        unique_id = uuid.uuid4().hex[:8]
        
        payload = {
            "asset": "TEST_ASSET",
            "amount": 100.5,
            "price_usd": 1.0,
            "timestamp": "2024-01-15",
            "source": "OTC Purchase",
            "notes": f"Test acquisition {unique_id}"
        }
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/manual-acquisition",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "transaction" in data, "Response should contain transaction details"
        
        tx = data["transaction"]
        assert tx["asset"] == "TEST_ASSET"
        assert tx["amount"] == 100.5
        assert tx["price_usd"] == 1.0
        assert "tx_id" in tx
        
        print(f"Test PASSED: Manual acquisition added with tx_id={tx['tx_id']}")
        
        # Return tx_id for cleanup
        return tx["tx_id"]
    
    def test_add_manual_acquisition_validation_errors(self, authenticated_premium_client):
        """Test validation errors for manual acquisition"""
        # Test missing required fields
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/manual-acquisition",
            json={"asset": "BTC"}  # Missing amount, price_usd, timestamp
        )
        assert response.status_code == 422, "Should return 422 for missing fields"
        
        # Test negative amount
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/manual-acquisition",
            json={
                "asset": "BTC",
                "amount": -10,
                "price_usd": 50000,
                "timestamp": "2024-01-15"
            }
        )
        assert response.status_code == 400, "Should return 400 for negative amount"
        
        print("Test PASSED: Validation errors handled correctly")
    
    def test_add_manual_acquisition_invalid_timestamp(self, authenticated_premium_client):
        """Test invalid timestamp format"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/manual-acquisition",
            json={
                "asset": "BTC",
                "amount": 1.0,
                "price_usd": 50000,
                "timestamp": "invalid-date"
            }
        )
        assert response.status_code == 400, "Should return 400 for invalid timestamp"
        print("Test PASSED: Invalid timestamp rejected")


class TestOrphanDisposalSummary:
    """P1: Test Orphan Disposal Summary endpoint"""
    
    def test_orphan_disposal_summary_structure(self, authenticated_premium_client):
        """Test orphan disposal summary returns correct structure"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/orphan-disposal-summary"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "orphan_assets" in data, "Response should contain orphan_assets"
        assert "total_shortfall_usd" in data, "Response should contain total_shortfall_usd"
        assert "has_orphans" in data, "Response should contain has_orphans"
        assert "message" in data, "Response should contain message"
        
        # Verify orphan_assets is a list
        assert isinstance(data["orphan_assets"], list), "orphan_assets should be a list"
        
        # If there are orphan assets, verify structure
        if data["orphan_assets"]:
            orphan = data["orphan_assets"][0]
            assert "asset" in orphan, "Orphan should have asset"
            assert "shortfall" in orphan, "Orphan should have shortfall"
            assert "shortfall_usd" in orphan, "Orphan should have shortfall_usd"
            assert "recommendation" in orphan, "Orphan should have recommendation"
        
        print(f"Test PASSED: Orphan summary has {len(data['orphan_assets'])} orphan assets")
        print(f"Total shortfall USD: ${data['total_shortfall_usd']:.2f}")


class TestManualAcquisitionsList:
    """P1: Test Manual Acquisitions List endpoint"""
    
    def test_get_manual_acquisitions_list(self, authenticated_premium_client):
        """Test getting list of manual acquisitions"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/manual-acquisitions"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "manual_acquisitions" in data, "Response should contain manual_acquisitions"
        assert "count" in data, "Response should contain count"
        
        # Verify manual_acquisitions is a list
        assert isinstance(data["manual_acquisitions"], list), "manual_acquisitions should be a list"
        
        print(f"Test PASSED: Found {data['count']} manual acquisitions")


class TestDeleteManualAcquisition:
    """P1: Test Delete Manual Acquisition endpoint"""
    
    def test_delete_manual_acquisition_success(self, authenticated_premium_client):
        """Test deleting a manual acquisition"""
        # First create one to delete
        payload = {
            "asset": "DELETE_TEST",
            "amount": 50.0,
            "price_usd": 2.0,
            "timestamp": "2024-02-01",
            "source": "Test",
            "notes": "To be deleted"
        }
        
        create_response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/manual-acquisition",
            json=payload
        )
        assert create_response.status_code == 200
        tx_id = create_response.json()["transaction"]["tx_id"]
        
        # Now delete it
        delete_response = authenticated_premium_client.delete(
            f"{BASE_URL}/api/exchanges/manual-acquisition/{tx_id}"
        )
        
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
        
        data = delete_response.json()
        assert data.get("success") == True, "Response should indicate success"
        
        print(f"Test PASSED: Manual acquisition {tx_id} deleted successfully")
    
    def test_delete_nonexistent_acquisition(self, authenticated_premium_client):
        """Test deleting a non-existent manual acquisition"""
        response = authenticated_premium_client.delete(
            f"{BASE_URL}/api/exchanges/manual-acquisition/nonexistent_tx_id_12345"
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Test PASSED: 404 returned for non-existent acquisition")


class TestAuthenticationRequired:
    """Test that all endpoints require authentication"""
    
    def test_manual_acquisition_requires_auth(self, api_client):
        """Test manual acquisition endpoint requires auth"""
        response = api_client.post(
            f"{BASE_URL}/api/exchanges/manual-acquisition",
            json={"asset": "BTC", "amount": 1, "price_usd": 50000, "timestamp": "2024-01-01"}
        )
        assert response.status_code in [401, 403], "Should require authentication"
        print("Test PASSED: Manual acquisition requires auth")
    
    def test_orphan_summary_requires_auth(self, api_client):
        """Test orphan summary endpoint requires auth"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/orphan-disposal-summary")
        assert response.status_code in [401, 403], "Should require authentication"
        print("Test PASSED: Orphan summary requires auth")
    
    def test_manual_acquisitions_list_requires_auth(self, api_client):
        """Test manual acquisitions list requires auth"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/manual-acquisitions")
        assert response.status_code in [401, 403], "Should require authentication"
        print("Test PASSED: Manual acquisitions list requires auth")
    
    def test_delete_manual_acquisition_requires_auth(self, api_client):
        """Test delete manual acquisition requires auth"""
        response = api_client.delete(f"{BASE_URL}/api/exchanges/manual-acquisition/test_id")
        assert response.status_code in [401, 403], "Should require authentication"
        print("Test PASSED: Delete manual acquisition requires auth")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_acquisitions(self, authenticated_premium_client):
        """Clean up any TEST_ prefixed manual acquisitions"""
        # Get all manual acquisitions
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/manual-acquisitions"
        )
        
        if response.status_code == 200:
            data = response.json()
            for tx in data.get("manual_acquisitions", []):
                asset = tx.get("asset", "")
                if asset.startswith("TEST_") or asset == "DELETE_TEST":
                    tx_id = tx.get("tx_id")
                    if tx_id:
                        authenticated_premium_client.delete(
                            f"{BASE_URL}/api/exchanges/manual-acquisition/{tx_id}"
                        )
                        print(f"Cleaned up test acquisition: {tx_id}")
        
        print("Test PASSED: Cleanup completed")
