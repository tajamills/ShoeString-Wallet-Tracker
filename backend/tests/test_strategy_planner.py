"""
Tests for Strategy Planner (Entry/Exit Strategy) with auto-alert creation.
- POST /api/exit-strategy/strategies (creates strategy + auto-creates alerts)
- PUT /api/exit-strategy/strategies/{id} (updates + creates/deletes alerts)
- GET /api/exit-strategy/strategies
- DELETE /api/exit-strategy/strategies/{id}
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://proceeds-validator.preview.emergentagent.com').rstrip('/')
TEST_EMAIL = "mobiletest@test.com"
TEST_PASSWORD = "test123456"


@pytest.fixture(scope="module")
def auth_token():
    """Authenticate and return token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }, timeout=30)
    if resp.status_code != 200:
        pytest.skip(f"Auth failed: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip(f"No token in response: {data}")
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_strategy(headers):
    """Delete any existing TESTCOIN strategy before/after."""
    yield
    try:
        resp = requests.get(f"{BASE_URL}/api/exit-strategy/strategies", headers=headers, timeout=10)
        if resp.status_code == 200:
            for s in resp.json().get("strategies", []):
                if s.get("asset_symbol") in ("TESTCOIN", "TESTBTC", "TESTETH"):
                    requests.delete(f"{BASE_URL}/api/exit-strategy/strategies/{s['strategy_id']}",
                                    headers=headers, timeout=10)
    except Exception:
        pass


def _delete_strategy_if_exists(headers, symbol):
    resp = requests.get(f"{BASE_URL}/api/exit-strategy/strategies", headers=headers, timeout=10)
    if resp.status_code == 200:
        for s in resp.json().get("strategies", []):
            if s.get("asset_symbol") == symbol:
                requests.delete(f"{BASE_URL}/api/exit-strategy/strategies/{s['strategy_id']}",
                                headers=headers, timeout=10)


class TestStrategyPlanner:
    """End-to-end strategy + auto-alert tests."""

    def test_list_strategies(self, headers):
        resp = requests.get(f"{BASE_URL}/api/exit-strategy/strategies", headers=headers, timeout=15)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "strategies" in data
        assert "count" in data
        assert isinstance(data["strategies"], list)

    def test_create_strategy_with_entry_tiers_creates_price_below_alerts(self, headers):
        _delete_strategy_if_exists(headers, "TESTCOIN")
        payload = {
            "asset_symbol": "TESTCOIN",
            "quantity": 10.0,
            "average_cost_basis": 100.0,
            "tax_rate": 15.0,
            "tiers": [
                {"name": "Entry 1", "tier_type": "entry", "sell_percentage": 30, "target_price": 80.0},
                {"name": "Entry 2", "tier_type": "entry", "sell_percentage": 30, "target_price": 60.0},
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/exit-strategy/strategies", json=payload, headers=headers, timeout=20)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["alerts_created"] == 2
        strategy_id = data["strategy_id"]
        assert strategy_id

        # Verify strategy exists with tiers
        get_resp = requests.get(f"{BASE_URL}/api/exit-strategy/strategies/{strategy_id}",
                                headers=headers, timeout=10)
        assert get_resp.status_code == 200
        strategy = get_resp.json()
        assert strategy["asset_symbol"] == "TESTCOIN"
        assert len(strategy["tiers"]) == 2
        for tier in strategy["tiers"]:
            assert tier["tier_type"] == "entry"
            assert tier["alert_created"] is True
            assert tier["alert_id"]

        # Verify alerts in alerts collection match strategy alert_ids and are price_below
        tier_alert_ids = {t["alert_id"] for t in strategy["tiers"]}
        alerts_resp = requests.get(f"{BASE_URL}/api/alerts", headers=headers, timeout=15)
        assert alerts_resp.status_code == 200
        alerts_data = alerts_resp.json()
        alerts = alerts_data if isinstance(alerts_data, list) else alerts_data.get("alerts", [])
        matched = [a for a in alerts if a.get("alert_id") in tier_alert_ids]
        assert len(matched) == 2, f"Expected 2 alerts matching tier IDs, got {len(matched)}"
        for a in matched:
            assert a["alert_type"] == "price_below", f"Expected price_below, got {a['alert_type']}"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/exit-strategy/strategies/{strategy_id}",
                        headers=headers, timeout=10)

    def test_create_strategy_with_exit_tiers_creates_price_above_alerts(self, headers):
        _delete_strategy_if_exists(headers, "TESTCOIN")
        payload = {
            "asset_symbol": "TESTCOIN",
            "quantity": 5.0,
            "average_cost_basis": 100.0,
            "tax_rate": 20.0,
            "tiers": [
                {"name": "Exit 1", "tier_type": "exit", "sell_percentage": 25, "target_price": 200.0},
                {"name": "Exit 2", "tier_type": "exit", "sell_percentage": 50, "target_price": 300.0},
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/exit-strategy/strategies", json=payload, headers=headers, timeout=20)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["alerts_created"] == 2
        strategy_id = data["strategy_id"]

        # Get the alert_ids from the created strategy
        get_resp = requests.get(f"{BASE_URL}/api/exit-strategy/strategies/{strategy_id}",
                                headers=headers, timeout=10)
        tier_alert_ids = {t["alert_id"] for t in get_resp.json()["tiers"]}

        # Verify those specific alerts are price_above
        alerts_resp = requests.get(f"{BASE_URL}/api/alerts", headers=headers, timeout=15)
        assert alerts_resp.status_code == 200
        alerts_data = alerts_resp.json()
        alerts = alerts_data if isinstance(alerts_data, list) else alerts_data.get("alerts", [])
        matched = [a for a in alerts if a.get("alert_id") in tier_alert_ids]
        assert len(matched) == 2, f"Expected 2 alerts matching tier IDs, got {len(matched)}"
        for a in matched:
            assert a["alert_type"] == "price_above", f"Expected price_above, got {a['alert_type']}"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/exit-strategy/strategies/{strategy_id}",
                        headers=headers, timeout=10)

    def test_create_strategy_with_mixed_tiers(self, headers):
        _delete_strategy_if_exists(headers, "TESTCOIN")
        payload = {
            "asset_symbol": "TESTCOIN",
            "quantity": 2.0,
            "average_cost_basis": 50000.0,
            "tax_rate": 15.0,
            "tiers": [
                {"name": "Dip Buy", "tier_type": "entry", "sell_percentage": 50, "target_price": 40000.0},
                {"name": "Take Profit", "tier_type": "exit", "sell_percentage": 50, "target_price": 80000.0},
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/exit-strategy/strategies", json=payload, headers=headers, timeout=20)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["alerts_created"] == 2
        strategy_id = data["strategy_id"]

        alerts_resp = requests.get(f"{BASE_URL}/api/alerts", headers=headers, timeout=15)
        alerts_data = alerts_resp.json()
        alerts = alerts_data if isinstance(alerts_data, list) else alerts_data.get("alerts", [])
        below = [a for a in alerts if a.get("asset_symbol") == "TESTCOIN" and a["alert_type"] == "price_below"]
        above = [a for a in alerts if a.get("asset_symbol") == "TESTCOIN" and a["alert_type"] == "price_above"]
        assert len(below) >= 1, "Entry tier should produce price_below alert"
        assert len(above) >= 1, "Exit tier should produce price_above alert"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/exit-strategy/strategies/{strategy_id}",
                        headers=headers, timeout=10)

    def test_duplicate_strategy_for_same_asset_returns_400(self, headers):
        _delete_strategy_if_exists(headers, "TESTCOIN")
        payload = {
            "asset_symbol": "TESTCOIN",
            "quantity": 1.0,
            "average_cost_basis": 100.0,
            "tax_rate": 15.0,
            "tiers": []
        }
        r1 = requests.post(f"{BASE_URL}/api/exit-strategy/strategies", json=payload, headers=headers, timeout=15)
        assert r1.status_code == 200
        sid = r1.json()["strategy_id"]

        r2 = requests.post(f"{BASE_URL}/api/exit-strategy/strategies", json=payload, headers=headers, timeout=15)
        assert r2.status_code == 400

        requests.delete(f"{BASE_URL}/api/exit-strategy/strategies/{sid}", headers=headers, timeout=10)

    def test_update_strategy_adds_new_alerts(self, headers):
        _delete_strategy_if_exists(headers, "TESTCOIN")
        # Create initial with no tiers
        r1 = requests.post(f"{BASE_URL}/api/exit-strategy/strategies", json={
            "asset_symbol": "TESTCOIN",
            "quantity": 1.0,
            "average_cost_basis": 100.0,
            "tax_rate": 15.0,
            "tiers": []
        }, headers=headers, timeout=15)
        assert r1.status_code == 200
        sid = r1.json()["strategy_id"]

        # Update: add 2 tiers (1 entry, 1 exit)
        update_payload = {
            "tiers": [
                {"name": "Entry", "tier_type": "entry", "sell_percentage": 25, "target_price": 50.0},
                {"name": "Exit", "tier_type": "exit", "sell_percentage": 25, "target_price": 200.0},
            ]
        }
        r2 = requests.put(f"{BASE_URL}/api/exit-strategy/strategies/{sid}",
                          json=update_payload, headers=headers, timeout=15)
        assert r2.status_code == 200, r2.text
        data = r2.json()
        assert data["alerts_created"] == 2

        # Cleanup
        requests.delete(f"{BASE_URL}/api/exit-strategy/strategies/{sid}", headers=headers, timeout=10)

    def test_delete_strategy(self, headers):
        _delete_strategy_if_exists(headers, "TESTCOIN")
        r1 = requests.post(f"{BASE_URL}/api/exit-strategy/strategies", json={
            "asset_symbol": "TESTCOIN",
            "quantity": 1.0,
            "average_cost_basis": 100.0,
            "tax_rate": 15.0,
            "tiers": []
        }, headers=headers, timeout=15)
        sid = r1.json()["strategy_id"]
        rd = requests.delete(f"{BASE_URL}/api/exit-strategy/strategies/{sid}", headers=headers, timeout=10)
        assert rd.status_code == 200
        # Verify it's gone
        rg = requests.get(f"{BASE_URL}/api/exit-strategy/strategies/{sid}", headers=headers, timeout=10)
        assert rg.status_code == 404
