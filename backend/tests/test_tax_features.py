"""
Tax Features Integration Tests
Tests the tax calculation, Form 8949 export, and transaction categorization endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tax-analysis-phase2.preview.emergentagent.com').rstrip('/')

# Test wallet address (Vitalik's address for consistent test data)
TEST_WALLET_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


class TestTaxDataInWalletAnalysis:
    """Tests for tax_data being returned in wallet analysis for premium users"""
    
    def test_premium_user_gets_tax_data(self, authenticated_premium_client):
        """Premium user should receive tax_data in wallet analysis response"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/wallet/analyze",
            json={"address": TEST_WALLET_ADDRESS, "chain": "ethereum"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify tax_data exists and has expected structure
        assert "tax_data" in data, "tax_data should be present in response for premium user"
        
        tax_data = data["tax_data"]
        assert tax_data is not None, "tax_data should not be None for premium user"
        
        # Verify tax_data structure
        assert "method" in tax_data, "tax_data should have method"
        assert tax_data["method"] == "FIFO", "Method should be FIFO"
        assert "summary" in tax_data, "tax_data should have summary"
        assert "realized_gains" in tax_data, "tax_data should have realized_gains"
        assert "unrealized_gains" in tax_data, "tax_data should have unrealized_gains"
    
    def test_tax_summary_structure(self, authenticated_premium_client):
        """Tax summary should have all required fields"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/wallet/analyze",
            json={"address": TEST_WALLET_ADDRESS, "chain": "ethereum"}
        )
        
        assert response.status_code == 200
        tax_data = response.json().get("tax_data", {})
        summary = tax_data.get("summary", {})
        
        # Verify all expected summary fields
        expected_fields = [
            "total_realized_gain",
            "total_unrealized_gain",
            "short_term_gains",
            "long_term_gains",
            "total_transactions",
            "buy_count",
            "sell_count"
        ]
        
        for field in expected_fields:
            assert field in summary, f"Summary should have {field}"
    
    def test_free_user_no_tax_data(self, authenticated_free_client):
        """Free user should NOT receive tax_data in wallet analysis response"""
        client, email = authenticated_free_client
        
        response = client.post(
            f"{BASE_URL}/api/wallet/analyze",
            json={"address": TEST_WALLET_ADDRESS, "chain": "ethereum"}
        )
        
        # Check if it's rate limited (free users have limit)
        if response.status_code == 429:
            pytest.skip("Free user rate limited - skipping test")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # tax_data should be None or not present for free users
        tax_data = data.get("tax_data")
        assert tax_data is None, "Free user should NOT have tax_data"


class TestForm8949Export:
    """Tests for Form 8949 CSV export endpoint"""
    
    def test_form_8949_returns_400_when_no_realized_gains(self, authenticated_premium_client):
        """Form 8949 export should return 400 when wallet has no realized gains (no sell transactions)"""
        # Vitalik's wallet has only received transactions, no sells, so no realized gains
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/export-form-8949",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "filter_type": "all"
            }
        )
        
        # Expected: 400 because there are no realized gains to report
        # Form 8949 is for reporting SALES, and if there are no sales, nothing to export
        assert response.status_code == 400, f"Expected 400 when no realized gains, got {response.status_code}"
        assert "No tax data available" in response.text or "realized_gains" in response.text.lower()
    
    def test_form_8949_endpoint_validates_request(self, authenticated_premium_client):
        """Form 8949 endpoint should accept valid request structure"""
        # Test with valid request format
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/export-form-8949",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "filter_type": "all"
            }
        )
        
        # Should get 400 (no realized gains) or 200 (if there were gains)
        # NOT 422 (validation error) or 500 (server error)
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
    
    def test_form_8949_accepts_filter_types(self, authenticated_premium_client):
        """Form 8949 should accept different filter types"""
        for filter_type in ["all", "short-term", "long-term"]:
            response = authenticated_premium_client.post(
                f"{BASE_URL}/api/tax/export-form-8949",
                json={
                    "address": TEST_WALLET_ADDRESS,
                    "chain": "ethereum",
                    "filter_type": filter_type
                }
            )
            
            # Should not be validation error
            assert response.status_code != 422, f"Filter type '{filter_type}' should be valid"
    
    def test_free_user_blocked_from_form_8949(self, authenticated_free_client):
        """Free user should get 403 when trying to export Form 8949"""
        client, email = authenticated_free_client
        
        response = client.post(
            f"{BASE_URL}/api/tax/export-form-8949",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "filter_type": "all"
            }
        )
        
        assert response.status_code == 403, f"Expected 403 for free user, got {response.status_code}"
        assert "premium" in response.text.lower() or "upgrade" in response.text.lower()


class TestTransactionCategories:
    """Tests for transaction categorization endpoints"""
    
    def test_save_categories_premium_user(self, authenticated_premium_client):
        """Premium user should be able to save transaction categories"""
        # Create test categories
        test_categories = {
            "0x1234567890abcdef1234567890abcdef12345678": "trade",
            "0xabcdef1234567890abcdef1234567890abcdef12": "income"
        }
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/save-categories",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "categories": test_categories
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "message" in data, "Response should have message"
        assert data.get("count") == len(test_categories), f"Count should be {len(test_categories)}"
    
    def test_get_categories_premium_user(self, authenticated_premium_client):
        """Premium user should be able to retrieve saved categories"""
        # First save some categories
        test_categories = {
            "0xtest_hash_unique": "payment"
        }
        
        save_response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/save-categories",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "categories": test_categories
            }
        )
        assert save_response.status_code == 200
        
        # Now retrieve categories
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/tax/categories/{TEST_WALLET_ADDRESS}?chain=ethereum"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "categories" in data, "Response should have categories"
        categories = data.get("categories", {})
        assert isinstance(categories, dict), "Categories should be a dict"
    
    def test_categories_persisted_correctly(self, authenticated_premium_client):
        """Saved categories should be correctly persisted and retrieved"""
        unique_hash = f"0x{uuid.uuid4().hex}"
        test_categories = {
            unique_hash: "gift_received"
        }
        
        # Save
        save_response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/save-categories",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "categories": test_categories
            }
        )
        assert save_response.status_code == 200
        
        # Retrieve and verify
        get_response = authenticated_premium_client.get(
            f"{BASE_URL}/api/tax/categories/{TEST_WALLET_ADDRESS}?chain=ethereum"
        )
        assert get_response.status_code == 200
        
        retrieved = get_response.json().get("categories", {})
        assert unique_hash in retrieved, f"Saved hash {unique_hash} should be in retrieved categories"
        assert retrieved[unique_hash] == "gift_received", "Category value should match"
    
    def test_free_user_blocked_from_save_categories(self, authenticated_free_client):
        """Free user should get 403 when trying to save categories"""
        client, email = authenticated_free_client
        
        response = client.post(
            f"{BASE_URL}/api/tax/save-categories",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "categories": {"0xtest": "trade"}
            }
        )
        
        assert response.status_code == 403, f"Expected 403 for free user, got {response.status_code}"


class TestTaxSummaryExport:
    """Tests for tax summary CSV export"""
    
    def test_premium_user_can_export_tax_summary(self, authenticated_premium_client):
        """Premium user should be able to export tax summary"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/export-summary",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "filter_type": "all"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        csv_content = response.text
        assert "Tax Summary" in csv_content, "CSV should contain Tax Summary"
        assert "FIFO" in csv_content, "CSV should mention FIFO method"
    
    def test_free_user_blocked_from_tax_summary(self, authenticated_free_client):
        """Free user should get 403 for tax summary export"""
        client, email = authenticated_free_client
        
        response = client.post(
            f"{BASE_URL}/api/tax/export-summary",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "filter_type": "all"
            }
        )
        
        assert response.status_code == 403, f"Expected 403 for free user, got {response.status_code}"


class TestAuthentication:
    """Tests for authentication required on tax endpoints"""
    
    def test_form_8949_requires_auth(self, api_client):
        """Form 8949 endpoint should require authentication"""
        response = api_client.post(
            f"{BASE_URL}/api/tax/export-form-8949",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "filter_type": "all"
            }
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_save_categories_requires_auth(self, api_client):
        """Save categories endpoint should require authentication"""
        response = api_client.post(
            f"{BASE_URL}/api/tax/save-categories",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "categories": {}
            }
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_get_categories_requires_auth(self, api_client):
        """Get categories endpoint should require authentication"""
        response = api_client.get(
            f"{BASE_URL}/api/tax/categories/{TEST_WALLET_ADDRESS}"
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
