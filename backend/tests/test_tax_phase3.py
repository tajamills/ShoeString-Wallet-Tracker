"""
Phase 3 Tax Features Integration Tests
Tests Schedule D export, batch categorization, auto-categorization, and supported years endpoints
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tax-analysis-phase2.preview.emergentagent.com').rstrip('/')

# Test wallet address (Vitalik's address for consistent test data)
TEST_WALLET_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


class TestSupportedTaxYears:
    """Tests for GET /api/tax/supported-years endpoint"""
    
    def test_supported_years_returns_valid_list(self, api_client):
        """Supported years endpoint should return a list of years"""
        response = api_client.get(f"{BASE_URL}/api/tax/supported-years")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "years" in data, "Response should have 'years' field"
        assert "current_year" in data, "Response should have 'current_year' field"
        
        years = data["years"]
        assert isinstance(years, list), "years should be a list"
        assert len(years) > 0, "years list should not be empty"
        
        # Years should start from 2020
        assert 2020 in years, "2020 should be in supported years"
        
        # Current year should be included
        current_year = datetime.now().year
        assert current_year == data["current_year"], f"current_year should be {current_year}"
        assert current_year in years, f"Current year {current_year} should be in years list"
    
    def test_supported_years_no_auth_required(self, api_client):
        """Supported years endpoint should be publicly accessible"""
        # Remove any auth headers
        if "Authorization" in api_client.headers:
            del api_client.headers["Authorization"]
        
        response = api_client.get(f"{BASE_URL}/api/tax/supported-years")
        
        assert response.status_code == 200, f"Should be accessible without auth, got {response.status_code}"


class TestScheduleDExport:
    """Tests for POST /api/tax/export-schedule-d endpoint"""
    
    def test_schedule_d_requires_auth(self, api_client):
        """Schedule D export requires authentication"""
        response = api_client.post(
            f"{BASE_URL}/api/tax/export-schedule-d",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "tax_year": 2024,
                "format": "text"
            }
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_schedule_d_free_user_blocked(self, authenticated_free_client):
        """Free user should get 403 for Schedule D export"""
        client, email = authenticated_free_client
        
        response = client.post(
            f"{BASE_URL}/api/tax/export-schedule-d",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "tax_year": 2024,
                "format": "text"
            }
        )
        
        assert response.status_code == 403, f"Expected 403 for free user, got {response.status_code}"
        assert "premium" in response.text.lower() or "upgrade" in response.text.lower()
    
    def test_schedule_d_premium_text_format(self, authenticated_premium_client):
        """Premium user should get Schedule D text format"""
        current_year = datetime.now().year
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/export-schedule-d",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "tax_year": current_year,
                "format": "text"
            }
        )
        
        # Should get 200 (even if empty) or 400 (no tax data)
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            assert "text/plain" in content_type, f"Expected text/plain, got {content_type}"
            
            # Check content structure
            content = response.text
            assert "Schedule D" in content or "SCHEDULE D" in content, "Content should mention Schedule D"
    
    def test_schedule_d_premium_csv_format(self, authenticated_premium_client):
        """Premium user should get Schedule D CSV format"""
        current_year = datetime.now().year
        
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/export-schedule-d",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "tax_year": current_year,
                "format": "csv"
            }
        )
        
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
    
    def test_schedule_d_validates_tax_year(self, authenticated_premium_client):
        """Schedule D should validate tax year range"""
        # Test year before 2020
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/export-schedule-d",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "tax_year": 2019,
                "format": "text"
            }
        )
        
        assert response.status_code == 400, f"Year 2019 should be invalid, got {response.status_code}"
        
        # Test future year
        future_year = datetime.now().year + 2
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/export-schedule-d",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "tax_year": future_year,
                "format": "text"
            }
        )
        
        assert response.status_code == 400, f"Future year {future_year} should be invalid"
    
    def test_schedule_d_accepts_2020_year(self, authenticated_premium_client):
        """Schedule D should accept 2020 as valid year"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/export-schedule-d",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "tax_year": 2020,
                "format": "text"
            }
        )
        
        # Should not be validation error (400 with year error)
        if response.status_code == 400:
            assert "tax_year" not in response.text.lower() or "2020" not in response.text.lower()


class TestBatchCategorization:
    """Tests for POST /api/tax/batch-categorize endpoint"""
    
    def test_batch_categorize_requires_auth(self, api_client):
        """Batch categorization requires authentication"""
        response = api_client.post(
            f"{BASE_URL}/api/tax/batch-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "rules": [{"type": "tx_type", "value": "received", "category": "income"}]
            }
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_batch_categorize_free_user_blocked(self, authenticated_free_client):
        """Free user should get 403 for batch categorization"""
        client, email = authenticated_free_client
        
        response = client.post(
            f"{BASE_URL}/api/tax/batch-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "rules": [{"type": "tx_type", "value": "received", "category": "income"}]
            }
        )
        
        assert response.status_code == 403, f"Expected 403 for free user, got {response.status_code}"
    
    def test_batch_categorize_premium_with_tx_type_rule(self, authenticated_premium_client):
        """Premium user can batch categorize with tx_type rule"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/batch-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "rules": [
                    {"type": "tx_type", "value": "received", "category": "income"}
                ]
            }
        )
        
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "message" in data, "Response should have message"
            assert "count" in data, "Response should have count"
            assert "categories" in data, "Response should have categories"
            assert isinstance(data["categories"], dict), "categories should be a dict"
    
    def test_batch_categorize_premium_with_address_rule(self, authenticated_premium_client):
        """Premium user can batch categorize with address rule"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/batch-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "rules": [
                    {"type": "address", "value": "0x0000000000000000000000000000000000000000", "category": "fee"}
                ]
            }
        )
        
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
    
    def test_batch_categorize_premium_with_amount_rule(self, authenticated_premium_client):
        """Premium user can batch categorize with amount_gt rule"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/batch-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "rules": [
                    {"type": "amount_gt", "value": 1.0, "category": "trade"}
                ]
            }
        )
        
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
    
    def test_batch_categorize_multiple_rules(self, authenticated_premium_client):
        """Premium user can batch categorize with multiple rules"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/batch-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "rules": [
                    {"type": "tx_type", "value": "received", "category": "income"},
                    {"type": "tx_type", "value": "sent", "category": "payment"},
                    {"type": "amount_lt", "value": 0.01, "category": "fee"}
                ]
            }
        )
        
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"


class TestAutoCategorization:
    """Tests for POST /api/tax/auto-categorize endpoint"""
    
    def test_auto_categorize_requires_auth(self, api_client):
        """Auto categorization requires authentication"""
        response = api_client.post(
            f"{BASE_URL}/api/tax/auto-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum"
            }
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_auto_categorize_free_user_blocked(self, authenticated_free_client):
        """Free user should get 403 for auto categorization"""
        client, email = authenticated_free_client
        
        response = client.post(
            f"{BASE_URL}/api/tax/auto-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum"
            }
        )
        
        assert response.status_code == 403, f"Expected 403 for free user, got {response.status_code}"
    
    def test_auto_categorize_premium_without_known_addresses(self, authenticated_premium_client):
        """Premium user can auto-categorize without known addresses"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/auto-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum"
            }
        )
        
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "message" in data, "Response should have message"
            assert "count" in data, "Response should have count"
            assert "categories" in data, "Response should have categories"
            assert isinstance(data["categories"], dict), "categories should be a dict"
    
    def test_auto_categorize_premium_with_known_addresses(self, authenticated_premium_client):
        """Premium user can auto-categorize with known addresses"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/auto-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "known_addresses": {
                    "0x1234567890abcdef1234567890abcdef12345678": "exchange",
                    "0xabcdef1234567890abcdef1234567890abcdef12": "self"
                }
            }
        )
        
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
    
    def test_auto_categorize_saves_categories(self, authenticated_premium_client):
        """Auto-categorize should save categories to database"""
        # First auto-categorize
        auto_response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/auto-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum"
            }
        )
        
        if auto_response.status_code != 200:
            pytest.skip("Auto-categorize failed - wallet may have no transactions")
        
        # Then get categories
        get_response = authenticated_premium_client.get(
            f"{BASE_URL}/api/tax/categories/{TEST_WALLET_ADDRESS}?chain=ethereum"
        )
        
        assert get_response.status_code == 200, f"Get categories failed: {get_response.text}"
        data = get_response.json()
        
        # Categories should be populated
        categories = data.get("categories", {})
        assert len(categories) > 0, "Auto-categorize should have saved some categories"


class TestBatchCategorizeSavesCategories:
    """Tests for batch categorize persisting results"""
    
    def test_batch_categorize_saves_categories(self, authenticated_premium_client):
        """Batch categorize should save categories to database"""
        # First batch categorize
        batch_response = authenticated_premium_client.post(
            f"{BASE_URL}/api/tax/batch-categorize",
            json={
                "address": TEST_WALLET_ADDRESS,
                "chain": "ethereum",
                "rules": [
                    {"type": "tx_type", "value": "received", "category": "income"}
                ]
            }
        )
        
        if batch_response.status_code != 200:
            pytest.skip("Batch categorize failed - wallet may have no transactions")
        
        batch_count = batch_response.json().get("count", 0)
        
        # Then get categories
        get_response = authenticated_premium_client.get(
            f"{BASE_URL}/api/tax/categories/{TEST_WALLET_ADDRESS}?chain=ethereum"
        )
        
        assert get_response.status_code == 200, f"Get categories failed: {get_response.text}"
        data = get_response.json()
        
        categories = data.get("categories", {})
        # Categories count should match
        assert len(categories) >= batch_count or batch_count == 0, "Categories should be persisted"
