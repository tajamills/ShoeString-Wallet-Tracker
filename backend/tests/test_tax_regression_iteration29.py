"""
Tax Regression Tests - Iteration 29
=====================================
Verify tax math functionality after CSS/styling changes to TaxSummaryDashboard.js

Tests cover:
- GET /api/tax/summary - Tax summary calculation (via /api/tax/unified)
- GET /api/custody/validation-status - Validation status check
- GET /api/custody/beta/pre-export-check - Pre-export validation
- GET /api/exchanges/transactions - Transaction retrieval
- GET /api/custody/tax-lots - Tax lot tracking
- GET /api/custody/tax-lots/disposals - Disposal calculations (via /api/custody/tax-lots/disposals)
- GET /api/custody/classify/effectiveness - Effectiveness metrics
- POST /api/tax/export-form-8949 - Form 8949 export

Test user: mobiletest@test.com / test123456
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://proceeds-validator.preview.emergentagent.com').rstrip('/')


class TestTaxRegressionAfterCSSChanges:
    """Regression tests for tax APIs after CSS-only changes to TaxSummaryDashboard.js"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token):
        """Setup authenticated client for all tests"""
        self.client = api_client
        self.token = premium_auth_token
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})
    
    # ========================================
    # TAX SUMMARY / UNIFIED TAX ENDPOINT
    # ========================================
    
    def test_unified_tax_endpoint_returns_200(self, api_client, premium_auth_token):
        """Test POST /api/tax/unified returns 200 with correct structure"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.post(f"{BASE_URL}/api/tax/unified", json={
            "data_source": "exchange_only",
            "tax_year": 2024
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "tax_data" in data, "Response should contain tax_data"
        assert "data_source" in data, "Response should contain data_source"
        assert data["data_source"] == "exchange_only"
        
        # Verify tax_data structure
        tax_data = data["tax_data"]
        assert "summary" in tax_data, "tax_data should contain summary"
        assert "realized_gains" in tax_data, "tax_data should contain realized_gains"
        
        # Verify summary structure (even if values are 0)
        summary = tax_data["summary"]
        assert "short_term_gains" in summary or "total_realized_gain" in summary, "Summary should have gain fields"
        
        print(f"PASS: Unified tax endpoint returns correct structure")
        print(f"  - Data source: {data['data_source']}")
        print(f"  - Realized gains count: {len(tax_data.get('realized_gains', []))}")
    
    def test_unified_tax_with_year_filter(self, api_client, premium_auth_token):
        """Test POST /api/tax/unified with tax_year filter"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        for year in [2024, 2025, 2026]:
            response = api_client.post(f"{BASE_URL}/api/tax/unified", json={
                "data_source": "exchange_only",
                "tax_year": year
            })
            
            assert response.status_code == 200, f"Year {year}: Expected 200, got {response.status_code}"
            data = response.json()
            assert data.get("tax_year") == year, f"Response should reflect tax_year {year}"
        
        print(f"PASS: Unified tax endpoint works with year filters (2024, 2025, 2026)")
    
    # ========================================
    # VALIDATION STATUS ENDPOINT
    # ========================================
    
    def test_validation_status_endpoint(self, api_client, premium_auth_token):
        """Test GET /api/custody/validation-status returns correct structure"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/custody/validation-status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should contain success field"
        assert data["success"] == True, "success should be True"
        assert "validation_status" in data, "Response should contain validation_status"
        
        # Verify validation_status structure
        status = data["validation_status"]
        # Common fields that should be present
        expected_fields = ["can_export", "validation_status", "issues_count"]
        for field in expected_fields:
            if field in status:
                print(f"  - {field}: {status[field]}")
        
        print(f"PASS: Validation status endpoint returns correct structure")
    
    # ========================================
    # PRE-EXPORT CHECK ENDPOINT
    # ========================================
    
    def test_pre_export_check_endpoint(self, api_client, premium_auth_token):
        """Test GET /api/custody/beta/pre-export-check returns correct structure"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/custody/beta/pre-export-check?tax_year=2024")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify key fields
        assert "can_export" in data, "Response should contain can_export"
        assert "validation_status" in data, "Response should contain validation_status"
        
        # These fields may or may not be present depending on validation state
        optional_fields = ["blocking_issues_count", "unresolved_review_count", "recommendation"]
        for field in optional_fields:
            if field in data:
                print(f"  - {field}: {data[field]}")
        
        print(f"PASS: Pre-export check endpoint returns correct structure")
        print(f"  - can_export: {data['can_export']}")
        print(f"  - validation_status: {data['validation_status']}")
    
    # ========================================
    # TRANSACTIONS ENDPOINT
    # ========================================
    
    def test_transactions_endpoint(self, api_client, premium_auth_token):
        """Test GET /api/exchanges/transactions returns correct structure"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/exchanges/transactions?limit=100")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "transactions" in data, "Response should contain transactions"
        assert "count" in data, "Response should contain count"
        assert isinstance(data["transactions"], list), "transactions should be a list"
        
        # Verify transaction structure if any exist
        if data["transactions"]:
            tx = data["transactions"][0]
            expected_tx_fields = ["tx_id", "asset", "amount", "tx_type"]
            for field in expected_tx_fields:
                if field not in tx:
                    print(f"  Warning: Transaction missing field '{field}'")
        
        print(f"PASS: Transactions endpoint returns correct structure")
        print(f"  - Transaction count: {data['count']}")
    
    def test_transactions_with_filters(self, api_client, premium_auth_token):
        """Test GET /api/exchanges/transactions with various filters"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        # Test with asset filter
        response = api_client.get(f"{BASE_URL}/api/exchanges/transactions?asset=BTC&limit=50")
        assert response.status_code == 200, f"Asset filter: Expected 200, got {response.status_code}"
        
        # Test with tx_type filter
        response = api_client.get(f"{BASE_URL}/api/exchanges/transactions?tx_type=buy&limit=50")
        assert response.status_code == 200, f"tx_type filter: Expected 200, got {response.status_code}"
        
        print(f"PASS: Transactions endpoint works with filters")
    
    # ========================================
    # TAX LOTS ENDPOINT
    # ========================================
    
    def test_tax_lots_endpoint(self, api_client, premium_auth_token):
        """Test GET /api/custody/tax-lots returns correct structure"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/custody/tax-lots")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should contain success"
        assert data["success"] == True, "success should be True"
        assert "lots" in data, "Response should contain lots"
        assert "count" in data, "Response should contain count"
        assert isinstance(data["lots"], list), "lots should be a list"
        
        # Verify lot structure if any exist
        if data["lots"]:
            lot = data["lots"][0]
            expected_lot_fields = ["asset", "quantity", "cost_basis_per_unit"]
            for field in expected_lot_fields:
                if field not in lot:
                    print(f"  Warning: Lot missing field '{field}'")
        
        print(f"PASS: Tax lots endpoint returns correct structure")
        print(f"  - Lot count: {data['count']}")
    
    def test_tax_lots_with_asset_filter(self, api_client, premium_auth_token):
        """Test GET /api/custody/tax-lots with asset filter"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/custody/tax-lots?asset=BTC")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "lots" in data, "Response should contain lots"
        
        print(f"PASS: Tax lots endpoint works with asset filter")
    
    # ========================================
    # TAX DISPOSALS ENDPOINT
    # ========================================
    
    def test_tax_disposals_endpoint(self, api_client, premium_auth_token):
        """Test GET /api/custody/tax-lots/disposals returns correct structure"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/custody/tax-lots/disposals")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should contain success"
        assert data["success"] == True, "success should be True"
        assert "disposals" in data, "Response should contain disposals"
        assert "count" in data, "Response should contain count"
        assert isinstance(data["disposals"], list), "disposals should be a list"
        
        # Verify total_gain_loss field
        assert "total_gain_loss" in data, "Response should contain total_gain_loss"
        
        print(f"PASS: Tax disposals endpoint returns correct structure")
        print(f"  - Disposal count: {data['count']}")
        print(f"  - Total gain/loss: {data['total_gain_loss']}")
    
    def test_tax_disposals_with_year_filter(self, api_client, premium_auth_token):
        """Test GET /api/custody/tax-lots/disposals with tax_year filter"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/custody/tax-lots/disposals?tax_year=2024")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "disposals" in data, "Response should contain disposals"
        
        print(f"PASS: Tax disposals endpoint works with tax_year filter")
    
    # ========================================
    # CLASSIFICATION EFFECTIVENESS ENDPOINT
    # ========================================
    
    def test_classification_effectiveness_endpoint(self, api_client, premium_auth_token):
        """Test GET /api/custody/classify/effectiveness returns correct structure"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/custody/classify/effectiveness")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should contain success"
        assert data["success"] == True, "success should be True"
        assert "effectiveness" in data, "Response should contain effectiveness"
        
        # Verify effectiveness structure
        effectiveness = data["effectiveness"]
        expected_fields = ["user_id", "auto_classified_count", "user_confirmed_count"]
        for field in expected_fields:
            if field in effectiveness:
                print(f"  - {field}: {effectiveness[field]}")
        
        print(f"PASS: Classification effectiveness endpoint returns correct structure")
    
    # ========================================
    # FORM 8949 EXPORT ENDPOINT
    # ========================================
    
    def test_form_8949_export_endpoint(self, api_client, premium_auth_token):
        """Test POST /api/tax/export-form-8949 returns correct response"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.post(f"{BASE_URL}/api/tax/export-form-8949", json={
            "tax_year": 2024,
            "format": "csv",
            "data_source": "exchange_only"
        })
        
        # Can be 200 (success with CSV) or 400 (no data found) - both are valid
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            # Should return CSV content
            content_type = response.headers.get('content-type', '')
            assert 'text/csv' in content_type or 'application/octet-stream' in content_type, \
                f"Expected CSV content type, got {content_type}"
            print(f"PASS: Form 8949 export returns CSV data")
        else:
            # 400 means no data found - this is expected for test user with no realized gains
            data = response.json()
            assert "detail" in data or "error" in data, "400 response should have error message"
            print(f"PASS: Form 8949 export returns expected 400 (no realized gains for test user)")
    
    # ========================================
    # ADDITIONAL TAX CALCULATION TESTS
    # ========================================
    
    def test_exchange_tax_calculate_endpoint(self, api_client, premium_auth_token):
        """Test POST /api/exchanges/tax/calculate returns correct structure"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.post(f"{BASE_URL}/api/exchanges/tax/calculate", json={
            "tax_year": 2024
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "has_data" in data, "Response should contain has_data"
        assert "tax_data" in data, "Response should contain tax_data"
        
        print(f"PASS: Exchange tax calculate endpoint returns correct structure")
        print(f"  - has_data: {data['has_data']}")
    
    def test_tax_supported_years_endpoint(self, api_client, premium_auth_token):
        """Test GET /api/tax/supported-years returns correct structure"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/tax/supported-years")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "years" in data, "Response should contain years"
        assert "current_year" in data, "Response should contain current_year"
        assert isinstance(data["years"], list), "years should be a list"
        assert len(data["years"]) > 0, "years should not be empty"
        
        print(f"PASS: Supported years endpoint returns correct structure")
        print(f"  - Years: {data['years']}")
        print(f"  - Current year: {data['current_year']}")
    
    # ========================================
    # ASSET BALANCES ENDPOINT
    # ========================================
    
    def test_asset_balances_endpoint(self, api_client, premium_auth_token):
        """Test GET /api/custody/tax-lots/balances returns correct structure"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/custody/tax-lots/balances")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should contain success"
        assert data["success"] == True, "success should be True"
        assert "balances" in data, "Response should contain balances"
        assert "asset_count" in data, "Response should contain asset_count"
        
        print(f"PASS: Asset balances endpoint returns correct structure")
        print(f"  - Asset count: {data['asset_count']}")


class TestTaxAPIAuthentication:
    """Test that tax APIs properly require authentication"""
    
    def test_unified_tax_requires_auth(self, api_client):
        """Test POST /api/tax/unified requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/tax/unified", json={
            "data_source": "exchange_only"
        })
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print(f"PASS: Unified tax endpoint requires authentication")
    
    def test_validation_status_requires_auth(self, api_client):
        """Test GET /api/custody/validation-status requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/custody/validation-status")
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print(f"PASS: Validation status endpoint requires authentication")
    
    def test_tax_lots_requires_auth(self, api_client):
        """Test GET /api/custody/tax-lots requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/custody/tax-lots")
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print(f"PASS: Tax lots endpoint requires authentication")
    
    def test_transactions_requires_auth(self, api_client):
        """Test GET /api/exchanges/transactions requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/transactions")
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print(f"PASS: Transactions endpoint requires authentication")


class TestTaxMathCalculations:
    """Test that tax math calculations return valid numeric values"""
    
    def test_unified_tax_returns_numeric_values(self, api_client, premium_auth_token):
        """Test that unified tax endpoint returns valid numeric values"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.post(f"{BASE_URL}/api/tax/unified", json={
            "data_source": "exchange_only",
            "tax_year": 2024
        })
        
        assert response.status_code == 200
        data = response.json()
        
        tax_data = data.get("tax_data", {})
        summary = tax_data.get("summary", {})
        
        # Verify numeric fields are actually numbers (not strings, not None)
        numeric_fields = ["short_term_gains", "long_term_gains", "total_realized_gain", "total_income"]
        for field in numeric_fields:
            if field in summary:
                value = summary[field]
                assert isinstance(value, (int, float)), f"{field} should be numeric, got {type(value)}"
                print(f"  - {field}: {value} (type: {type(value).__name__})")
        
        print(f"PASS: Unified tax returns valid numeric values")
    
    def test_disposals_gain_loss_is_numeric(self, api_client, premium_auth_token):
        """Test that disposals endpoint returns numeric gain/loss values"""
        api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/custody/tax-lots/disposals")
        
        assert response.status_code == 200
        data = response.json()
        
        # total_gain_loss should be numeric
        total_gain_loss = data.get("total_gain_loss")
        assert isinstance(total_gain_loss, (int, float)), f"total_gain_loss should be numeric, got {type(total_gain_loss)}"
        
        # Each disposal's gain_loss should be numeric
        for disposal in data.get("disposals", []):
            if "gain_loss" in disposal:
                assert isinstance(disposal["gain_loss"], (int, float)), "disposal gain_loss should be numeric"
        
        print(f"PASS: Disposals endpoint returns valid numeric gain/loss values")
        print(f"  - total_gain_loss: {total_gain_loss}")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
