"""
MVP Backend Tests
Tests for MVP finalization features:
1. Auth: Login endpoint
2. Auth: Password reset endpoint
3. Wallet analysis: Basic wallet analysis endpoint
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://chain-custody-tool.preview.emergentagent.com').rstrip('/')

# Test credentials from problem statement
TEST_EMAIL = "mobiletest@test.com"
TEST_PASSWORD = "test123456"
TEST_WALLET_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


class TestAuthLogin:
    """Test auth login endpoint"""
    
    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "access_token" in data
        assert "token_type" in data
        assert "user" in data
        
        # Verify user data
        user = data["user"]
        assert user["email"] == TEST_EMAIL
        assert "subscription_tier" in user
        assert "id" in user
    
    def test_login_invalid_password(self):
        """Test login fails with invalid password"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": "wrongpassword"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
    
    def test_login_nonexistent_user(self):
        """Test login fails with non-existent email"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "nonexistent@test.com", "password": "anypassword"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
    
    def test_login_invalid_email_format(self):
        """Test login fails with invalid email format"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "notanemail", "password": "somepassword"}
        )
        
        # Should fail with 422 (validation error) or 401
        assert response.status_code in [401, 422], f"Expected 401 or 422, got {response.status_code}: {response.text}"


class TestPasswordReset:
    """Test password reset endpoint"""
    
    def test_forgot_password_success(self):
        """Test password reset request returns success message"""
        response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": TEST_EMAIL}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response contains message
        assert "message" in data
        # Message should be generic to prevent email enumeration
        assert "If this email exists" in data["message"] or "reset link" in data["message"].lower()
    
    def test_forgot_password_nonexistent_email(self):
        """Test password reset request for non-existent email still returns success (security)"""
        response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": f"nonexistent_{uuid.uuid4().hex[:8]}@test.com"}
        )
        
        # Should return 200 to prevent email enumeration
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "message" in data
    
    def test_reset_password_invalid_token(self):
        """Test reset password with invalid token returns error"""
        response = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={"token": "invalid_token_123", "new_password": "NewPass123!"}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"


class TestAuthenticatedEndpoints:
    """Test authenticated endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for test user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_get_current_user(self, auth_token):
        """Test getting current user info with valid token"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["email"] == TEST_EMAIL
        assert "subscription_tier" in data
        assert "terms_accepted" in data
    
    def test_get_current_user_without_token(self):
        """Test getting current user fails without token"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}: {response.text}"


class TestWalletAnalysis:
    """Test wallet analysis endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for test user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_analyze_wallet_success(self, auth_token):
        """Test wallet analysis with valid address
        
        BUG: Currently returns 500 due to datetime comparison issue in check_usage_limit().
        The issue is that datetime.fromisoformat() may return a naive datetime,
        but datetime.now(timezone.utc) returns an aware datetime.
        See server.py line 244-247.
        """
        response = requests.post(
            f"{BASE_URL}/api/wallet/analyze",
            json={"address": TEST_WALLET_ADDRESS, "chain": "ethereum"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Expected behavior: 200 with analysis data
        # Actual behavior: 500 Internal Server Error due to datetime bug
        # This test will FAIL to report the bug to main agent
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}. BUG: datetime comparison error in check_usage_limit()"
        data = response.json()
        
        # Verify response structure
        assert "address" in data
        assert data["address"].lower() == TEST_WALLET_ADDRESS.lower()
        assert "totalEthSent" in data or "total_sent" in data
        assert "totalEthReceived" in data or "total_received" in data
        assert "currentBalance" in data or "current_balance" in data
    
    def test_analyze_wallet_invalid_address(self, auth_token):
        """Test wallet analysis with invalid address
        
        BUG: Currently returns 500 due to same datetime issue.
        """
        response = requests.post(
            f"{BASE_URL}/api/wallet/analyze",
            json={"address": "invalid-address", "chain": "ethereum"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Should return error for invalid address (400/422)
        # But currently returns 500 due to datetime bug
        assert response.status_code in [400, 422], f"Expected 400 or 422, got {response.status_code}: {response.text}. BUG: datetime comparison error in check_usage_limit()"
    
    def test_analyze_wallet_without_auth(self):
        """Test wallet analysis fails without authentication"""
        response = requests.post(
            f"{BASE_URL}/api/wallet/analyze",
            json={"address": TEST_WALLET_ADDRESS, "chain": "ethereum"}
        )
        
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}: {response.text}"


class TestTaxExport:
    """Test tax export endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for test user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_export_form_8949_endpoint_exists(self, auth_token):
        """Test Form 8949 export endpoint exists and responds"""
        # This tests that the endpoint exists - actual export requires wallet analysis first
        response = requests.post(
            f"{BASE_URL}/api/tax/export-form-8949",
            json={"address": TEST_WALLET_ADDRESS, "chain": "ethereum", "filter_type": "all"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Should return either success (200) or error about no data (400/404)
        # Not 403 (forbidden) or 500 (server error)
        assert response.status_code in [200, 400, 404], f"Expected 200/400/404, got {response.status_code}: {response.text}"
    
    def test_export_form_8949_without_auth(self):
        """Test Form 8949 export fails without authentication"""
        response = requests.post(
            f"{BASE_URL}/api/tax/export-form-8949",
            json={"address": TEST_WALLET_ADDRESS, "chain": "ethereum", "filter_type": "all"}
        )
        
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}: {response.text}"


class TestUserRegistration:
    """Test user registration endpoint"""
    
    def test_register_new_user(self):
        """Test registering a new user"""
        unique_email = f"test_mvp_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": unique_email, "password": "TestPass123!"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == unique_email
        assert data["user"]["subscription_tier"] == "free"  # New users are free tier
    
    def test_register_duplicate_email(self):
        """Test registering with existing email fails"""
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": TEST_EMAIL, "password": "SomePass123!"}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    
    def test_register_weak_password(self):
        """Test registering with weak password fails"""
        unique_email = f"test_weak_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": unique_email, "password": "123"}  # Too short
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
