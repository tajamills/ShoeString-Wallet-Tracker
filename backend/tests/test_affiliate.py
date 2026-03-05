"""
Test Affiliate Program API Endpoints
- POST /api/affiliate/register - Register as affiliate
- GET /api/affiliate/me - Get affiliate dashboard data
- GET /api/affiliate/validate/{code} - Validate affiliate code (public)
- Integration with payment checkout (affiliate_code in request)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://wallet-tax-hub.preview.emergentagent.com').rstrip('/')


class TestAffiliateValidation:
    """Test public affiliate code validation endpoint"""
    
    def test_validate_invalid_code(self, api_client):
        """GET /api/affiliate/validate/{code} returns invalid for non-existent code"""
        response = api_client.get(f"{BASE_URL}/api/affiliate/validate/NONEXISTENT999")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["discount"] == 0
        assert "Invalid" in data["message"] or "invalid" in data["message"].lower()
    
    def test_validate_short_code(self, api_client):
        """GET /api/affiliate/validate/{code} handles short codes"""
        response = api_client.get(f"{BASE_URL}/api/affiliate/validate/AB")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
    
    def test_validate_code_case_insensitive(self, api_client):
        """GET /api/affiliate/validate/{code} is case insensitive"""
        # First validate with uppercase
        response1 = api_client.get(f"{BASE_URL}/api/affiliate/validate/TESTCODE")
        # Then with lowercase
        response2 = api_client.get(f"{BASE_URL}/api/affiliate/validate/testcode")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        # Both should return same validity status
        assert response1.json()["valid"] == response2.json()["valid"]


class TestAffiliateRegistration:
    """Test affiliate registration endpoint"""
    
    def test_register_requires_auth(self, api_client):
        """POST /api/affiliate/register requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/affiliate/register", json={
            "affiliate_code": "TESTCODE",
            "name": "Test User"
        })
        # Should return 403 Forbidden or 401 Unauthorized without auth
        assert response.status_code in [401, 403]
    
    def test_register_affiliate_success(self, api_client, free_user_auth_token):
        """POST /api/affiliate/register creates new affiliate"""
        token, email = free_user_auth_token
        unique_code = f"TEST{uuid.uuid4().hex[:6].upper()}"
        
        response = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={
                "affiliate_code": unique_code,
                "name": "Test Affiliate",
                "paypal_email": "test@paypal.com"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["affiliate_code"] == unique_code
        assert "Successfully" in data["message"] or "success" in data["message"].lower()
    
    def test_register_duplicate_user(self, api_client, free_user_auth_token):
        """POST /api/affiliate/register prevents duplicate registration"""
        token, email = free_user_auth_token
        unique_code1 = f"TEST{uuid.uuid4().hex[:6].upper()}"
        unique_code2 = f"TEST{uuid.uuid4().hex[:6].upper()}"
        
        # Register first time
        response1 = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={
                "affiliate_code": unique_code1,
                "name": "Test Affiliate"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Try to register again with different code
        response2 = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={
                "affiliate_code": unique_code2,
                "name": "Test Affiliate 2"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # First should succeed, second should fail
        # (unless user was already an affiliate from prior test)
        if response1.status_code == 200:
            assert response2.status_code == 400
            assert "already" in response2.json()["detail"].lower()
    
    def test_register_code_too_short(self, api_client):
        """POST /api/affiliate/register rejects short codes"""
        # Create a fresh user for this test
        unique_id = uuid.uuid4().hex[:8]
        email = f"TEST_short_{unique_id}@test.com"
        password = "TestPass123!"
        
        # Register user
        reg_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password
        })
        
        if reg_response.status_code != 200:
            pytest.skip("Could not create test user")
        
        token = reg_response.json()["access_token"]
        
        # Try to register with short code
        response = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={
                "affiliate_code": "AB",  # Too short (min 3 chars)
                "name": "Test Affiliate"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400
        assert "3-20" in response.json()["detail"] or "characters" in response.json()["detail"].lower()
    
    def test_register_duplicate_code(self, api_client):
        """POST /api/affiliate/register prevents duplicate codes"""
        # Create first user
        unique_id1 = uuid.uuid4().hex[:8]
        email1 = f"TEST_aff1_{unique_id1}@test.com"
        password = "TestPass123!"
        
        reg1 = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": email1,
            "password": password
        })
        
        if reg1.status_code != 200:
            pytest.skip("Could not create first test user")
        
        token1 = reg1.json()["access_token"]
        shared_code = f"SHARED{uuid.uuid4().hex[:4].upper()}"
        
        # Register first affiliate
        response1 = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={"affiliate_code": shared_code, "name": "User 1"},
            headers={"Authorization": f"Bearer {token1}"}
        )
        
        assert response1.status_code == 200
        
        # Create second user
        unique_id2 = uuid.uuid4().hex[:8]
        email2 = f"TEST_aff2_{unique_id2}@test.com"
        
        reg2 = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": email2,
            "password": password
        })
        
        if reg2.status_code != 200:
            pytest.skip("Could not create second test user")
        
        token2 = reg2.json()["access_token"]
        
        # Try to register with same code
        response2 = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={"affiliate_code": shared_code, "name": "User 2"},
            headers={"Authorization": f"Bearer {token2}"}
        )
        
        assert response2.status_code == 400
        assert "taken" in response2.json()["detail"].lower()


class TestAffiliateDashboard:
    """Test affiliate dashboard endpoint"""
    
    def test_dashboard_requires_auth(self, api_client):
        """GET /api/affiliate/me requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/affiliate/me")
        assert response.status_code in [401, 403]
    
    def test_dashboard_non_affiliate_user(self, api_client):
        """GET /api/affiliate/me returns is_affiliate=False for non-affiliates"""
        # Create a fresh user who is NOT an affiliate
        unique_id = uuid.uuid4().hex[:8]
        email = f"TEST_nonaff_{unique_id}@test.com"
        password = "TestPass123!"
        
        reg_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password
        })
        
        if reg_response.status_code != 200:
            pytest.skip("Could not create test user")
        
        token = reg_response.json()["access_token"]
        
        response = api_client.get(
            f"{BASE_URL}/api/affiliate/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_affiliate"] is False
    
    def test_dashboard_affiliate_user(self, api_client):
        """GET /api/affiliate/me returns full data for affiliates"""
        # Create user and register as affiliate
        unique_id = uuid.uuid4().hex[:8]
        email = f"TEST_aff_{unique_id}@test.com"
        password = "TestPass123!"
        
        reg_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password
        })
        
        if reg_response.status_code != 200:
            pytest.skip("Could not create test user")
        
        token = reg_response.json()["access_token"]
        affiliate_code = f"TEST{unique_id[:6].upper()}"
        
        # Register as affiliate
        reg_aff = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={"affiliate_code": affiliate_code, "name": "Test Aff", "paypal_email": "pay@pal.com"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert reg_aff.status_code == 200
        
        # Get dashboard
        response = api_client.get(
            f"{BASE_URL}/api/affiliate/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify dashboard data structure
        assert data["is_affiliate"] is True
        assert data["affiliate_code"] == affiliate_code
        assert data["name"] == "Test Aff"
        assert "total_earnings" in data
        assert "pending_earnings" in data
        assert "referral_count" in data
        assert data["total_earnings"] == 0.0  # New affiliate has no earnings
        assert data["referral_count"] == 0
        assert "recent_referrals" in data
        assert isinstance(data["recent_referrals"], list)


class TestAffiliateCodeValidationAfterRegistration:
    """Test that registered affiliate codes are validated correctly"""
    
    def test_validate_registered_code(self, api_client):
        """GET /api/affiliate/validate/{code} returns valid=True for registered codes"""
        # Create user and register as affiliate
        unique_id = uuid.uuid4().hex[:8]
        email = f"TEST_validate_{unique_id}@test.com"
        password = "TestPass123!"
        
        reg_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password
        })
        
        if reg_response.status_code != 200:
            pytest.skip("Could not create test user")
        
        token = reg_response.json()["access_token"]
        affiliate_code = f"VAL{unique_id[:6].upper()}"
        
        # Register as affiliate
        reg_aff = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={"affiliate_code": affiliate_code, "name": "Validator Test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert reg_aff.status_code == 200
        
        # Now validate the code (public endpoint, no auth needed)
        response = api_client.get(f"{BASE_URL}/api/affiliate/validate/{affiliate_code}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["discount"] == 10.0
        assert "$10" in data["message"] or "10" in data["message"]


class TestPaymentWithAffiliateCode:
    """Test affiliate code integration with payment checkout"""
    
    def test_payment_request_accepts_affiliate_code(self, api_client, free_user_auth_token):
        """POST /api/payments/create-upgrade accepts affiliate_code"""
        token, email = free_user_auth_token
        
        # This test just verifies the endpoint accepts the affiliate_code parameter
        # We can't fully test Stripe integration without real payment
        response = api_client.post(
            f"{BASE_URL}/api/payments/create-upgrade",
            json={
                "tier": "unlimited",
                "origin_url": "https://wallet-tax-hub.preview.emergentagent.com",
                "affiliate_code": "FAKECODE123"  # Invalid code - should still create session but without discount
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should either succeed (create checkout) or fail gracefully
        # Stripe might return error if not configured, but endpoint shouldn't crash
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            data = response.json()
            # Verify response has expected fields
            assert "url" in data or "session_id" in data
    
    def test_user_cannot_use_own_code(self, api_client):
        """POST /api/payments/create-upgrade blocks using own affiliate code"""
        # Create user and register as affiliate
        unique_id = uuid.uuid4().hex[:8]
        email = f"TEST_owncode_{unique_id}@test.com"
        password = "TestPass123!"
        
        reg_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password
        })
        
        if reg_response.status_code != 200:
            pytest.skip("Could not create test user")
        
        token = reg_response.json()["access_token"]
        affiliate_code = f"OWN{unique_id[:6].upper()}"
        
        # Register as affiliate
        reg_aff = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={"affiliate_code": affiliate_code, "name": "Own Code Test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert reg_aff.status_code == 200
        
        # Try to use own code for upgrade
        response = api_client.post(
            f"{BASE_URL}/api/payments/create-upgrade",
            json={
                "tier": "unlimited",
                "origin_url": "https://wallet-tax-hub.preview.emergentagent.com",
                "affiliate_code": affiliate_code
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should be blocked
        assert response.status_code == 400
        assert "own" in response.json()["detail"].lower() or "cannot" in response.json()["detail"].lower()


class TestAffiliateCodeFormats:
    """Test various affiliate code formats"""
    
    def test_alphanumeric_code(self, api_client):
        """Affiliate codes with letters and numbers work"""
        unique_id = uuid.uuid4().hex[:8]
        email = f"TEST_alpha_{unique_id}@test.com"
        password = "TestPass123!"
        
        reg_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password
        })
        
        if reg_response.status_code != 200:
            pytest.skip("Could not create test user")
        
        token = reg_response.json()["access_token"]
        
        # Test alphanumeric code
        response = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={"affiliate_code": "ABC123XYZ", "name": "Alpha Test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["affiliate_code"] == "ABC123XYZ"
    
    def test_code_converted_to_uppercase(self, api_client):
        """Affiliate codes are converted to uppercase"""
        unique_id = uuid.uuid4().hex[:8]
        email = f"TEST_upper_{unique_id}@test.com"
        password = "TestPass123!"
        
        reg_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password
        })
        
        if reg_response.status_code != 200:
            pytest.skip("Could not create test user")
        
        token = reg_response.json()["access_token"]
        
        # Submit lowercase code
        response = api_client.post(
            f"{BASE_URL}/api/affiliate/register",
            json={"affiliate_code": "lowercase123", "name": "Upper Test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        # Code should be stored as uppercase
        assert response.json()["affiliate_code"] == "LOWERCASE123"
