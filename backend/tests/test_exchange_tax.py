"""
Backend tests for Exchange Tax Calculator feature
Tests the new exchange tax endpoints that calculate cost basis and capital gains from CSV imports.

Endpoints tested:
- POST /api/exchanges/tax/calculate - calculates tax from exchange transactions
- GET /api/exchanges/tax/form-8949 - returns Form 8949 line items
- GET /api/exchanges/tax/form-8949/csv - exports Form 8949 as CSV file
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://fifo-calculator-1.preview.emergentagent.com').rstrip('/')


class TestExchangeTaxCalculateEndpoint:
    """Tests for POST /api/exchanges/tax/calculate"""
    
    def test_calculate_requires_authentication(self, api_client):
        """Test that tax calculation requires authentication"""
        response = api_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={}
        )
        assert response.status_code in [401, 403]
        
    def test_free_user_gets_403(self, authenticated_free_client):
        """Test that FREE users get 403 for tax calculation"""
        client, email = authenticated_free_client
        
        response = client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={}
        )
        
        assert response.status_code == 403
        assert "Unlimited" in response.json().get("detail", "")
        
    def test_unlimited_user_can_calculate(self, authenticated_premium_client):
        """Test that Unlimited users can access tax calculation"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "tax_data" in data
        assert "has_data" in data
        
    def test_calculate_returns_correct_structure(self, authenticated_premium_client):
        """Test that tax calculation returns expected structure"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check top level structure
        assert "message" in data
        assert "has_data" in data
        assert "tax_data" in data
        
        # Check tax_data structure
        tax_data = data["tax_data"]
        assert "method" in tax_data
        assert tax_data["method"] == "FIFO"
        assert "exchanges" in tax_data
        assert "total_transactions" in tax_data
        assert "realized_gains" in tax_data
        assert "unrealized" in tax_data
        assert "summary" in tax_data
        
    def test_calculate_with_year_filter(self, authenticated_premium_client):
        """Test that year filter is accepted"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={"tax_year": 2024}
        )
        
        assert response.status_code == 200
        
    def test_calculate_with_asset_filter(self, authenticated_premium_client):
        """Test that asset filter is accepted"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={"asset_filter": "BTC"}
        )
        
        assert response.status_code == 200
        
    def test_calculate_with_both_filters(self, authenticated_premium_client):
        """Test that both filters can be used together"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={"tax_year": 2024, "asset_filter": "ETH"}
        )
        
        assert response.status_code == 200
        
    def test_summary_has_expected_fields(self, authenticated_premium_client):
        """Test that summary contains all expected fields"""
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={}
        )
        
        assert response.status_code == 200
        summary = response.json()["tax_data"]["summary"]
        
        expected_fields = [
            "total_realized_gain",
            "short_term_gains",
            "long_term_gains",
            "total_unrealized_gain",
            "total_cost_basis",
            "total_current_value",
            "dispositions_count",
            "open_positions"
        ]
        
        for field in expected_fields:
            assert field in summary, f"Missing field: {field}"


class TestExchangeForm8949Endpoint:
    """Tests for GET /api/exchanges/tax/form-8949"""
    
    def test_form8949_requires_authentication(self, api_client):
        """Test that Form 8949 endpoint requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/tax/form-8949")
        assert response.status_code in [401, 403]
        
    def test_free_user_gets_403(self, authenticated_free_client):
        """Test that FREE users get 403 for Form 8949"""
        client, email = authenticated_free_client
        
        response = client.get(f"{BASE_URL}/api/exchanges/tax/form-8949")
        
        assert response.status_code == 403
        assert "Unlimited" in response.json().get("detail", "")
        
    def test_unlimited_user_can_access(self, authenticated_premium_client):
        """Test that Unlimited users can access Form 8949"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "line_items" in data
        
    def test_returns_correct_structure(self, authenticated_premium_client):
        """Test that Form 8949 returns expected structure"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have line_items and totals (or message for no data)
        assert "line_items" in data or "message" in data
        
    def test_with_year_filter(self, authenticated_premium_client):
        """Test Form 8949 with tax year filter"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949",
            params={"tax_year": 2024}
        )
        
        assert response.status_code == 200
        
    def test_with_holding_period_filter_short(self, authenticated_premium_client):
        """Test Form 8949 with short-term holding period filter"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949",
            params={"holding_period": "short-term"}
        )
        
        assert response.status_code == 200
        
    def test_with_holding_period_filter_long(self, authenticated_premium_client):
        """Test Form 8949 with long-term holding period filter"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949",
            params={"holding_period": "long-term"}
        )
        
        assert response.status_code == 200
        
    def test_with_all_filters(self, authenticated_premium_client):
        """Test Form 8949 with all filters"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949",
            params={"tax_year": 2024, "holding_period": "short-term"}
        )
        
        assert response.status_code == 200


class TestExchangeForm8949CSVEndpoint:
    """Tests for GET /api/exchanges/tax/form-8949/csv"""
    
    def test_csv_requires_authentication(self, api_client):
        """Test that CSV export requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/exchanges/tax/form-8949/csv")
        assert response.status_code in [401, 403]
        
    def test_free_user_gets_403(self, authenticated_free_client):
        """Test that FREE users get 403 for CSV export"""
        client, email = authenticated_free_client
        
        response = client.get(f"{BASE_URL}/api/exchanges/tax/form-8949/csv")
        
        assert response.status_code == 403
        assert "Unlimited" in response.json().get("detail", "")
        
    def test_unlimited_user_access(self, authenticated_premium_client):
        """Test that Unlimited users can access CSV export (may return 404 if no data)"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949/csv"
        )
        
        # Should be 200 with data or 404 if no exchange data
        assert response.status_code in [200, 404]
        
    def test_csv_with_year_filter(self, authenticated_premium_client):
        """Test CSV export with tax year filter"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949/csv",
            params={"tax_year": 2024}
        )
        
        # Should be 200 with data or 404 if no exchange data
        assert response.status_code in [200, 404]
        
    def test_csv_with_holding_period_filter(self, authenticated_premium_client):
        """Test CSV export with holding period filter"""
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949/csv",
            params={"holding_period": "short-term"}
        )
        
        # Should be 200 with data or 404 if no exchange data
        assert response.status_code in [200, 404]


class TestExchangeTaxIntegration:
    """Integration tests for the exchange tax calculator flow"""
    
    def test_free_user_blocked_all_tax_endpoints(self, authenticated_free_client):
        """Test that free users are blocked from all tax endpoints"""
        client, email = authenticated_free_client
        
        # Test calculate
        response = client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={}
        )
        assert response.status_code == 403
        
        # Test form-8949
        response = client.get(f"{BASE_URL}/api/exchanges/tax/form-8949")
        assert response.status_code == 403
        
        # Test form-8949/csv
        response = client.get(f"{BASE_URL}/api/exchanges/tax/form-8949/csv")
        assert response.status_code == 403
        
    def test_unlimited_user_full_flow(self, authenticated_premium_client):
        """Test the full tax calculator flow for Unlimited user"""
        # Calculate tax
        response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={}
        )
        assert response.status_code == 200
        assert "tax_data" in response.json()
        
        # Get Form 8949
        response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949"
        )
        assert response.status_code == 200
        assert "line_items" in response.json()
        
    def test_tax_data_consistent_between_endpoints(self, authenticated_premium_client):
        """Test that tax data is consistent between calculate and form-8949"""
        # Get data from calculate
        calc_response = authenticated_premium_client.post(
            f"{BASE_URL}/api/exchanges/tax/calculate",
            json={}
        )
        
        # Get data from form-8949
        form_response = authenticated_premium_client.get(
            f"{BASE_URL}/api/exchanges/tax/form-8949"
        )
        
        # Both should succeed
        assert calc_response.status_code == 200
        assert form_response.status_code == 200
        
        # Both should return no data (empty) or data (consistent)
        calc_data = calc_response.json()
        form_data = form_response.json()
        
        # If no data, both should indicate this
        if not calc_data.get("has_data"):
            assert len(form_data.get("line_items", [])) == 0
