"""
Tax Validation API Endpoint Tests

Tests for the Tax Validation and Invariant Enforcement Layer API endpoints.
Covers all endpoints defined in /api/custody/validate/* routes.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "mobiletest@test.com"
TEST_PASSWORD = "test123456"


class TestTaxValidationAPI:
    """Test Tax Validation API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("access_token") or data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                self.token = token
            else:
                pytest.skip("No token in login response")
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
    
    # ========================================
    # POST /api/custody/validate/transactions
    # ========================================
    
    def test_validate_transactions_buy_acquisition(self):
        """Test that buy transactions are classified as acquisition"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/transactions",
            json={
                "transactions": [
                    {"tx_id": "test1", "tx_type": "buy", "asset": "BTC", "amount": 1.0}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True
        assert data["total_transactions"] == 1
        assert len(data["validated_transactions"]) == 1
        
        tx = data["validated_transactions"][0]
        assert tx["classification"] == "acquisition"
        assert tx["classification_confidence"] == 1.0
        assert tx["needs_review"] == False
    
    def test_validate_transactions_sell_disposal(self):
        """Test that sell transactions are classified as disposal"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/transactions",
            json={
                "transactions": [
                    {"tx_id": "test2", "tx_type": "sell", "asset": "BTC", "amount": 0.5}
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        tx = data["validated_transactions"][0]
        assert tx["classification"] == "disposal"
        assert tx["classification_confidence"] == 1.0
    
    def test_validate_transactions_staking_income(self):
        """Test that staking rewards are classified as income"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/transactions",
            json={
                "transactions": [
                    {"tx_id": "test3", "tx_type": "staking", "asset": "ETH", "amount": 0.1}
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        tx = data["validated_transactions"][0]
        assert tx["classification"] == "income"
        assert tx["classification_confidence"] == 1.0
    
    def test_validate_transactions_unlinked_send_unknown(self):
        """Test that unlinked sends are classified as unknown and need review"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/transactions",
            json={
                "transactions": [
                    {"tx_id": "test4", "tx_type": "send", "asset": "ETH", "amount": 1.0, "chain_status": "unlinked"}
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        tx = data["validated_transactions"][0]
        assert tx["classification"] == "unknown"
        assert tx["needs_review"] == True
        assert data["needs_review_count"] == 1
    
    def test_validate_transactions_linked_send_internal(self):
        """Test that linked sends are classified as internal transfer"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/transactions",
            json={
                "transactions": [
                    {"tx_id": "test5", "tx_type": "send", "asset": "ETH", "amount": 1.0, "chain_status": "linked"}
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        tx = data["validated_transactions"][0]
        assert tx["classification"] == "internal_transfer"
        assert tx["classification_confidence"] >= 0.9
    
    def test_validate_transactions_batch(self):
        """Test batch transaction validation"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/transactions",
            json={
                "transactions": [
                    {"tx_id": "batch1", "tx_type": "buy", "asset": "BTC", "amount": 1.0},
                    {"tx_id": "batch2", "tx_type": "sell", "asset": "BTC", "amount": 0.5},
                    {"tx_id": "batch3", "tx_type": "staking", "asset": "ETH", "amount": 0.1},
                    {"tx_id": "batch4", "tx_type": "airdrop", "asset": "UNI", "amount": 100},
                    {"tx_id": "batch5", "tx_type": "unknown_type", "asset": "SOL", "amount": 1.0}
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_transactions"] == 5
        assert data["needs_review_count"] == 1  # Only unknown_type needs review
    
    # ========================================
    # POST /api/custody/validate/invariants
    # ========================================
    
    def test_validate_invariants_basic(self):
        """Test running invariant checks"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/invariants",
            json={}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert "status" in data
        assert "can_export_taxes" in data
        assert "violations_count" in data
        assert "violations" in data
        assert "warnings" in data
    
    def test_validate_invariants_with_balances(self):
        """Test invariant checks with balance data"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/invariants",
            json={
                "balances": {
                    "BTC": {"starting": 0, "ending": 0},
                    "ETH": {"starting": 0, "ending": 0}
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # With empty balances and no lots, should be valid
        assert data["success"] == True
        assert data["status"] == "valid"
    
    # ========================================
    # GET /api/custody/validate/account-status
    # ========================================
    
    def test_get_account_status(self):
        """Test getting account tax status"""
        response = self.session.get(f"{BASE_URL}/api/custody/validate/account-status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "account_tax_state_valid" in data
        assert "can_export_form_8949" in data
        assert "active_violations" in data
        assert "violations" in data
        assert "recent_audit_entries" in data
        
        # Verify types
        assert isinstance(data["account_tax_state_valid"], bool)
        assert isinstance(data["can_export_form_8949"], bool)
        assert isinstance(data["active_violations"], int)
        assert isinstance(data["violations"], list)
        assert isinstance(data["recent_audit_entries"], list)
    
    # ========================================
    # GET /api/custody/validate/lot-status/{asset}
    # ========================================
    
    def test_get_lot_status_btc(self):
        """Test getting lot status for BTC"""
        response = self.session.get(f"{BASE_URL}/api/custody/validate/lot-status/BTC")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True
        assert data["asset"] == "BTC"
        assert "lot_status" in data
        
        lot_status = data["lot_status"]
        assert "asset" in lot_status
        assert "lots" in lot_status
        assert "total_quantity" in lot_status
        assert "total_cost_basis" in lot_status
    
    def test_get_lot_status_eth(self):
        """Test getting lot status for ETH"""
        response = self.session.get(f"{BASE_URL}/api/custody/validate/lot-status/ETH")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["asset"] == "ETH"
    
    def test_get_lot_status_nonexistent_asset(self):
        """Test getting lot status for asset with no lots"""
        response = self.session.get(f"{BASE_URL}/api/custody/validate/lot-status/NONEXISTENT")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return empty lot status, not error
        assert data["success"] == True
        assert data["lot_status"]["total_quantity"] == 0
        assert data["lot_status"]["total_cost_basis"] == 0
    
    # ========================================
    # GET /api/custody/validate/audit-trail
    # ========================================
    
    def test_get_audit_trail(self):
        """Test getting audit trail"""
        response = self.session.get(f"{BASE_URL}/api/custody/validate/audit-trail")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True
        assert "entries_count" in data
        assert "audit_trail" in data
        assert isinstance(data["audit_trail"], list)
    
    def test_get_audit_trail_with_limit(self):
        """Test getting audit trail with custom limit"""
        response = self.session.get(f"{BASE_URL}/api/custody/validate/audit-trail?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["entries_count"] <= 10
    
    # ========================================
    # POST /api/custody/validate/recompute
    # ========================================
    
    def test_trigger_recompute(self):
        """Test triggering full recomputation"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/recompute?reason=test_recompute"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True
        assert data["message"] == "Tax data recomputation triggered"
        assert "result" in data
        
        result = data["result"]
        assert result["recompute_triggered"] == True
        assert "reason" in result
        assert "cleared_lots" in result
        assert "cleared_disposals" in result
        assert "timestamp" in result
    
    def test_trigger_recompute_default_reason(self):
        """Test triggering recompute with default reason"""
        response = self.session.post(f"{BASE_URL}/api/custody/validate/recompute")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["result"]["reason"] == "user_requested"
    
    # ========================================
    # GET /api/custody/export-form-8949 with validation
    # ========================================
    
    def test_export_form_8949_with_validation(self):
        """Test Form 8949 export with validation enabled"""
        response = self.session.get(
            f"{BASE_URL}/api/custody/export-form-8949?tax_year=2024&validate=true"
        )
        
        # Should return either CSV or validation errors
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        content_type = response.headers.get("Content-Type", "")
        
        if "text/csv" in content_type:
            # CSV export successful
            assert "Content-Disposition" in response.headers
            assert "form_8949" in response.headers["Content-Disposition"]
        else:
            # Validation errors returned as JSON
            data = response.json()
            if "error" in data:
                assert data["can_export"] == False
                assert "validation_result" in data
    
    def test_export_form_8949_without_validation(self):
        """Test Form 8949 export with validation disabled"""
        response = self.session.get(
            f"{BASE_URL}/api/custody/export-form-8949?tax_year=2024&validate=false"
        )
        
        assert response.status_code == 200
        
        # Should always return CSV when validation is disabled
        content_type = response.headers.get("Content-Type", "")
        # Either CSV or JSON (if no events)
        assert "text/csv" in content_type or "application/json" in content_type


class TestTaxValidationAPIEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("access_token") or data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Login failed")
    
    def test_validate_transactions_empty_list(self):
        """Test validating empty transaction list"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/transactions",
            json={"transactions": []}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_transactions"] == 0
        assert data["needs_review_count"] == 0
    
    def test_validate_transactions_all_types(self):
        """Test all transaction type classifications"""
        tx_types = [
            ("buy", "acquisition"),
            ("trade", "acquisition"),
            ("sell", "disposal"),
            ("reward", "income"),
            ("staking", "income"),
            ("airdrop", "income"),
            ("mining", "income"),
            ("interest", "income"),
        ]
        
        transactions = [
            {"tx_id": f"type_{i}", "tx_type": tx_type, "asset": "BTC", "amount": 1.0}
            for i, (tx_type, _) in enumerate(tx_types)
        ]
        
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/transactions",
            json={"transactions": transactions}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for i, (tx_type, expected_class) in enumerate(tx_types):
            tx = data["validated_transactions"][i]
            assert tx["classification"] == expected_class, f"Expected {expected_class} for {tx_type}, got {tx['classification']}"
    
    def test_validate_transactions_external_send(self):
        """Test external send classification"""
        response = self.session.post(
            f"{BASE_URL}/api/custody/validate/transactions",
            json={
                "transactions": [
                    {"tx_id": "ext1", "tx_type": "send", "asset": "ETH", "amount": 1.0, "chain_status": "external"}
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        tx = data["validated_transactions"][0]
        assert tx["classification"] == "disposal"
        assert tx["classification_confidence"] >= 0.9


class TestTaxValidationAPIAuth:
    """Test authentication requirements"""
    
    def test_validate_transactions_requires_auth(self):
        """Test that validate/transactions requires authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(
            f"{BASE_URL}/api/custody/validate/transactions",
            json={"transactions": []}
        )
        
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403]
    
    def test_account_status_requires_auth(self):
        """Test that account-status requires authentication"""
        session = requests.Session()
        
        response = session.get(f"{BASE_URL}/api/custody/validate/account-status")
        
        assert response.status_code in [401, 403]
    
    def test_lot_status_requires_auth(self):
        """Test that lot-status requires authentication"""
        session = requests.Session()
        
        response = session.get(f"{BASE_URL}/api/custody/validate/lot-status/BTC")
        
        assert response.status_code in [401, 403]


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
