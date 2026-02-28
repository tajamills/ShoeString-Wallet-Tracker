import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tax-analysis-phase2.preview.emergentagent.com').rstrip('/')

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture
def premium_auth_token(api_client):
    """Get authentication token for premium user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "taxtest@test.com",
        "password": "TestPass123!"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Premium user authentication failed - skipping authenticated tests")

@pytest.fixture
def free_user_auth_token(api_client):
    """Get authentication token for free user - create one if needed"""
    import uuid
    import time
    
    # Create a unique free user
    unique_id = uuid.uuid4().hex[:8]
    email = f"TEST_free_{unique_id}@test.com"
    password = "TestPass123!"
    
    # Register the user
    response = api_client.post(f"{BASE_URL}/api/auth/register", json={
        "email": email,
        "password": password
    })
    
    if response.status_code == 200:
        return response.json().get("access_token"), email
    elif response.status_code == 400 and "already registered" in response.text.lower():
        # Try login instead
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            return response.json().get("access_token"), email
    
    pytest.skip("Free user creation/authentication failed")

@pytest.fixture
def authenticated_premium_client(api_client, premium_auth_token):
    """Session with premium auth header"""
    api_client.headers.update({"Authorization": f"Bearer {premium_auth_token}"})
    return api_client

@pytest.fixture
def authenticated_free_client(api_client, free_user_auth_token):
    """Session with free user auth header"""
    token, email = free_user_auth_token
    api_client.headers.update({"Authorization": f"Bearer {token}"})
    return api_client, email
