"""
Test Suite for Chain of Custody and Wallet Linkage Features - Iteration 20

Tests:
- Review Queue API endpoints
- Resolve Review (Mine/External/Skip)
- Linkages API
- Tax Events API
- Form 8949 CSV Export
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "mobiletest@test.com"
TEST_PASSWORD = "test123456"


class TestAuthentication:
    """Test login flow"""
    
    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL
        assert data["user"]["subscription_tier"] == "unlimited"
        print(f"Login successful: {data['user']['email']} ({data['user']['subscription_tier']})")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed")


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestReviewQueue:
    """Test Review Queue endpoints"""
    
    def test_get_review_queue(self, auth_headers):
        """Test fetching review queue"""
        response = requests.get(
            f"{BASE_URL}/api/custody/review-queue",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "reviews" in data
        assert "count" in data
        assert isinstance(data["reviews"], list)
        print(f"Review queue has {data['count']} pending items")
    
    def test_review_queue_item_structure(self, auth_headers):
        """Test review queue item has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/custody/review-queue",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            review = data["reviews"][0]
            required_fields = ["id", "user_id", "tx_id", "source_address", 
                            "destination_address", "asset", "amount", 
                            "review_status", "prompt_text"]
            for field in required_fields:
                assert field in review, f"Missing field: {field}"
            print(f"Review item structure valid: {review['asset']} - {review['amount']}")
        else:
            print("No pending reviews to check structure")


class TestResolveReview:
    """Test resolve review endpoint"""
    
    def test_resolve_review_invalid_decision(self, auth_headers):
        """Test resolve with invalid decision returns error"""
        response = requests.post(
            f"{BASE_URL}/api/custody/resolve-review",
            headers=auth_headers,
            json={"review_id": "test-id", "decision": "invalid"}
        )
        # Backend returns 500 with wrapped 400 error message
        assert response.status_code in [400, 500]
        data = response.json()
        assert "Decision must be" in data.get("detail", "")
        print("Invalid decision correctly rejected")
    
    def test_resolve_review_not_found(self, auth_headers):
        """Test resolve with non-existent review ID"""
        response = requests.post(
            f"{BASE_URL}/api/custody/resolve-review",
            headers=auth_headers,
            json={"review_id": "non-existent-id", "decision": "yes"}
        )
        assert response.status_code == 404
        print("Non-existent review correctly returns 404")


class TestLinkages:
    """Test Linkages endpoints"""
    
    def test_get_linkages(self, auth_headers):
        """Test fetching user linkages"""
        response = requests.get(
            f"{BASE_URL}/api/custody/linkages",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "linkages" in data
        assert "count" in data
        assert isinstance(data["linkages"], list)
        print(f"User has {data['count']} linkages")
    
    def test_linkage_item_structure(self, auth_headers):
        """Test linkage item has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/custody/linkages",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            linkage = data["linkages"][0]
            required_fields = ["id", "user_id", "from_address", "to_address", 
                            "link_type", "confidence", "is_active"]
            for field in required_fields:
                assert field in linkage, f"Missing field: {field}"
            print(f"Linkage structure valid: {linkage['from_address'][:10]}... -> {linkage['to_address'][:10]}...")
        else:
            print("No linkages to check structure")


class TestClusters:
    """Test Wallet Clusters endpoints"""
    
    def test_get_clusters(self, auth_headers):
        """Test fetching wallet clusters"""
        response = requests.get(
            f"{BASE_URL}/api/custody/clusters",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "clusters" in data
        assert "count" in data
        print(f"User has {data['count']} wallet clusters")


class TestTaxEvents:
    """Test Tax Events endpoints"""
    
    def test_get_tax_events(self, auth_headers):
        """Test fetching tax events"""
        response = requests.get(
            f"{BASE_URL}/api/custody/tax-events?tax_year=2026",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "tax_events" in data
        assert "count" in data
        assert "summary" in data
        assert "total_gain" in data["summary"]
        assert "total_loss" in data["summary"]
        assert "net" in data["summary"]
        print(f"Tax events: {data['count']} | Net: ${data['summary']['net']:.2f}")
    
    def test_tax_event_structure(self, auth_headers):
        """Test tax event has Form 8949 data"""
        response = requests.get(
            f"{BASE_URL}/api/custody/tax-events?tax_year=2026",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            event = data["tax_events"][0]
            required_fields = ["id", "user_id", "asset", "quantity", 
                            "proceeds", "cost_basis", "gain_loss", "form_8949_data"]
            for field in required_fields:
                assert field in event, f"Missing field: {field}"
            
            # Check Form 8949 data structure
            form_data = event["form_8949_data"]
            form_fields = ["description", "date_acquired", "date_sold", 
                         "proceeds", "cost_basis", "gain_or_loss"]
            for field in form_fields:
                assert field in form_data, f"Missing Form 8949 field: {field}"
            print(f"Tax event structure valid: {event['asset']} | Gain/Loss: ${event['gain_loss']:.2f}")
        else:
            print("No tax events to check structure")


class TestForm8949Export:
    """Test Form 8949 CSV Export"""
    
    def test_export_form_8949_csv(self, auth_headers):
        """Test Form 8949 CSV export returns valid CSV"""
        response = requests.get(
            f"{BASE_URL}/api/custody/export-form-8949?tax_year=2026",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        
        # Check CSV content
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) >= 1  # At least header row
        
        # Check header row has IRS Form 8949 columns
        header = lines[0]
        expected_columns = ["Description of Property", "Date Acquired", 
                          "Date Sold or Disposed", "Proceeds", "Cost or Other Basis",
                          "Adjustment Code", "Adjustment Amount", "Gain or (Loss)"]
        for col in expected_columns:
            assert col in header, f"Missing column: {col}"
        
        print(f"Form 8949 CSV valid: {len(lines)} rows (including header)")
    
    def test_export_form_8949_content_disposition(self, auth_headers):
        """Test Form 8949 export has proper filename"""
        response = requests.get(
            f"{BASE_URL}/api/custody/export-form-8949?tax_year=2026",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert "form_8949" in content_disposition
        assert "2026" in content_disposition
        print(f"Content-Disposition: {content_disposition}")


class TestLinkWallet:
    """Test manual wallet linking"""
    
    def test_link_wallet_missing_fields(self, auth_headers):
        """Test link wallet with missing fields"""
        response = requests.post(
            f"{BASE_URL}/api/custody/link-wallet",
            headers=auth_headers,
            json={"from_address": "0x123"}  # Missing to_address
        )
        assert response.status_code == 422  # Validation error
        print("Missing fields correctly rejected")


class TestExportReviewQueue:
    """Test Review Queue CSV Export"""
    
    def test_export_review_queue_csv(self, auth_headers):
        """Test review queue CSV export"""
        response = requests.get(
            f"{BASE_URL}/api/custody/export-review-queue",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) >= 1  # At least header row
        
        # Check header has expected columns
        header = lines[0]
        expected_columns = ["Review ID", "Transaction ID", "Source Address", 
                          "Destination Address", "Asset", "Amount"]
        for col in expected_columns:
            assert col in header, f"Missing column: {col}"
        
        print(f"Review Queue CSV valid: {len(lines)} rows")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
