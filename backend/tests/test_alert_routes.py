"""
Backend tests for Price Alerts API (Crypto Bag Tracker pivot to Price Alerts).
Covers:
- Auth required endpoints
- Subscription status
- Alert CRUD (create / list / toggle / delete)
- Validation
"""
import os
import pytest
import requests
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://proceeds-validator.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

TEST_EMAIL = "mobiletest@test.com"
TEST_PASSWORD = "test123456"


@pytest.fixture(scope="session")
def auth_token():
    """Login with test credentials and return JWT token."""
    r = requests.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login failed ({r.status_code}): {r.text}")
    data = r.json()
    token = data.get("access_token") or data.get("token") or data.get("jwt")
    if not token:
        pytest.skip(f"No token returned: {data}")
    return token


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# --- Auth gating ---
class TestAlertsAuth:
    def test_get_alerts_requires_auth(self):
        r = requests.get(f"{API}/alerts", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_subscription_requires_auth(self):
        r = requests.get(f"{API}/alerts/subscription", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_create_alert_requires_auth(self):
        r = requests.post(f"{API}/alerts", json={
            "asset_symbol": "BTC", "asset_type": "crypto",
            "alert_type": "price_above", "target_value": 100000
        }, timeout=15)
        assert r.status_code in (401, 403), r.text


# --- Subscription ---
class TestAlertSubscription:
    def test_get_subscription(self, auth_headers):
        r = requests.get(f"{API}/alerts/subscription", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("status", "tier", "trial_used", "can_create_alerts"):
            assert key in data, f"Missing key '{key}' in {data}"
        # Per agent note: user already on trial with ~6 days
        assert data["status"] in ("trialing", "active", "none", "expired")

    def test_get_tiers(self, auth_headers):
        r = requests.get(f"{API}/alerts/tiers", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "tiers" in data
        assert "unlimited" in data["tiers"]
        assert data["tiers"]["unlimited"]["price_monthly"] == 18.88


# --- Asset Search & Price ---
class TestAlertSearch:
    def test_search_btc(self, auth_headers):
        r = requests.get(f"{API}/alerts/search", params={"q": "BTC"}, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "results" in data
        syms = [x["symbol"] for x in data["results"]]
        assert "BTC" in syms

    def test_get_btc_price(self, auth_headers):
        r = requests.get(f"{API}/alerts/price/crypto/BTC", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["symbol"] == "BTC"
        assert data["price"] > 0


# --- Alert CRUD ---
class TestAlertsCRUD:
    created_alert_id = None

    def test_list_alerts(self, auth_headers):
        r = requests.get(f"{API}/alerts", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "alerts" in data and "subscription" in data
        assert isinstance(data["alerts"], list)

    def test_create_alert(self, auth_headers):
        payload = {
            "asset_symbol": "ETH",
            "asset_type": "crypto",
            "alert_type": "price_above",
            "target_value": 99999.99,
            "notification_method": "email",
            "note": "TEST_alert_pytest"
        }
        r = requests.post(f"{API}/alerts", json=payload, headers=auth_headers, timeout=30)
        # If user has no subscription, will 403; per agent note user is on trial.
        assert r.status_code == 200, f"Expected 200; got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("success") is True
        assert data["alert"]["asset_symbol"] == "ETH"
        assert data["alert"]["alert_type"] == "price_above"
        TestAlertsCRUD.created_alert_id = data["alert"]["id"]

    def test_get_alerts_includes_new(self, auth_headers):
        assert TestAlertsCRUD.created_alert_id, "Alert was not created"
        r = requests.get(f"{API}/alerts", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        ids = [a.get("alert_id") for a in r.json()["alerts"]]
        assert TestAlertsCRUD.created_alert_id in ids

    def test_toggle_alert(self, auth_headers):
        aid = TestAlertsCRUD.created_alert_id
        assert aid
        r = requests.post(f"{API}/alerts/{aid}/toggle", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["new_status"] in ("active", "paused")
        assert d["previous_status"] != d["new_status"]

    def test_delete_alert(self, auth_headers):
        aid = TestAlertsCRUD.created_alert_id
        assert aid
        r = requests.delete(f"{API}/alerts/{aid}", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        # Verify gone
        r2 = requests.get(f"{API}/alerts/{aid}", headers=auth_headers, timeout=15)
        assert r2.status_code == 404


# --- Validation ---
class TestAlertValidation:
    def test_invalid_asset_type(self, auth_headers):
        r = requests.post(f"{API}/alerts", json={
            "asset_symbol": "BTC", "asset_type": "invalid",
            "alert_type": "price_above", "target_value": 100
        }, headers=auth_headers, timeout=15)
        assert r.status_code in (400, 422)

    def test_invalid_price_asset_type(self, auth_headers):
        r = requests.get(f"{API}/alerts/price/invalid/BTC", headers=auth_headers, timeout=15)
        assert r.status_code == 400
