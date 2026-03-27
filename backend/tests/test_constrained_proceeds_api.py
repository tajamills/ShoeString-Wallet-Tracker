"""
API Tests for Constrained Proceeds Acquisition Remediation Endpoints

Tests the following endpoints:
- GET /api/custody/proceeds/preview - Preview fixable/non-fixable counts with reasons
- POST /api/custody/proceeds/apply - Apply fixes with dry_run option
- POST /api/custody/proceeds/rollback - Rollback a batch of created records
- GET /api/custody/proceeds/rollback-batches - List all rollback batches

Verifies:
- Exclusions work correctly (stablecoin, missing USD, missing timestamp, etc.)
- Created records have source_disposal linkage
- Created records have rollback_batch_id for reversibility
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "mobiletest@test.com"
TEST_PASSWORD = "test123456"


class TestConstrainedProceedsAPI:
    """Test the constrained proceeds acquisition remediation API endpoints"""
    
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
                self.authenticated = True
            else:
                self.authenticated = False
        else:
            self.authenticated = False
    
    # ========================================
    # GET /api/custody/proceeds/preview
    # ========================================
    
    def test_preview_endpoint_returns_200(self):
        """Test that preview endpoint returns 200 OK"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.get(f"{BASE_URL}/api/custody/proceeds/preview")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
    
    def test_preview_returns_summary_structure(self):
        """Test that preview returns proper summary structure"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.get(f"{BASE_URL}/api/custody/proceeds/preview")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check summary structure
        assert "summary" in data
        summary = data["summary"]
        assert "fixable_count" in summary
        assert "fixable_total_value" in summary
        assert "non_fixable_count" in summary
        assert "non_fixable_reasons" in summary
        
        # Check preview structure
        assert "preview" in data
        preview = data["preview"]
        assert "candidates" in preview
        assert "skipped" in preview
    
    def test_preview_shows_exclusion_reasons(self):
        """Test that preview shows reasons for non-fixable disposals"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.get(f"{BASE_URL}/api/custody/proceeds/preview")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check non_fixable_reasons contains expected exclusion types
        non_fixable_reasons = data["summary"]["non_fixable_reasons"]
        
        # At least some exclusion reasons should be present
        # Based on main agent context: 121 missing USD value, 22 stablecoin source
        valid_reasons = [
            "missing_proceeds_value",
            "stablecoin_source",
            "missing_timestamp",
            "unresolved_wallet_ownership",
            "missing_acquisition_history",
            "inferred_internal_transfer",
            "bridge_ambiguity",
            "dex_ambiguity",
            "already_has_proceeds",
            "zero_proceeds",
            "negative_proceeds",
            "exchange_internal"
        ]
        
        for reason in non_fixable_reasons.keys():
            assert reason in valid_reasons, f"Unknown exclusion reason: {reason}"
    
    def test_preview_skipped_items_have_details(self):
        """Test that skipped items have proper details"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.get(f"{BASE_URL}/api/custody/proceeds/preview")
        
        assert response.status_code == 200
        data = response.json()
        
        skipped = data["preview"]["skipped"]
        
        # If there are skipped items, verify structure
        if len(skipped) > 0:
            item = skipped[0]
            assert "tx_id" in item
            assert "asset" in item
            assert "skip_reason" in item
            assert "details" in item
    
    # ========================================
    # POST /api/custody/proceeds/apply
    # ========================================
    
    def test_apply_dry_run_returns_200(self):
        """Test that apply with dry_run=true returns 200"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.post(
            f"{BASE_URL}/api/custody/proceeds/apply",
            json={"dry_run": True}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert data.get("dry_run") == True
    
    def test_apply_dry_run_does_not_create_records(self):
        """Test that dry_run mode does not create records"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.post(
            f"{BASE_URL}/api/custody/proceeds/apply",
            json={"dry_run": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Dry run should not have rollback_batch_id
        assert data.get("rollback_batch_id") is None
        # Should have preview data instead
        assert "preview" in data or data.get("created_count") == 0
    
    def test_apply_dry_run_shows_preview(self):
        """Test that dry_run shows what would be created"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.post(
            f"{BASE_URL}/api/custody/proceeds/apply",
            json={"dry_run": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should show total value
        assert "total_value" in data
        assert isinstance(data["total_value"], (int, float))
    
    def test_apply_with_specific_tx_ids(self):
        """Test that apply can target specific transaction IDs"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        # First get preview to find candidates
        preview_response = self.session.get(f"{BASE_URL}/api/custody/proceeds/preview")
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        
        candidates = preview_data["preview"]["candidates"]
        
        if len(candidates) == 0:
            # No candidates to test with - this is expected per main agent context
            pytest.skip("No fixable candidates available")
        
        # Try to apply with specific tx_ids (dry run)
        tx_ids = [c["source_disposal_tx_id"] for c in candidates[:2]]
        
        response = self.session.post(
            f"{BASE_URL}/api/custody/proceeds/apply",
            json={"candidate_tx_ids": tx_ids, "dry_run": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
    
    # ========================================
    # POST /api/custody/proceeds/rollback
    # ========================================
    
    def test_rollback_invalid_batch_returns_404(self):
        """Test that rollback with invalid batch_id returns 404"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.post(
            f"{BASE_URL}/api/custody/proceeds/rollback",
            json={"batch_id": "non-existent-batch-id-12345"}
        )
        
        # Should return 404 for non-existent batch
        assert response.status_code == 404
    
    def test_rollback_requires_batch_id(self):
        """Test that rollback requires batch_id parameter"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.post(
            f"{BASE_URL}/api/custody/proceeds/rollback",
            json={}
        )
        
        # Should return 422 for missing required field
        assert response.status_code == 422
    
    # ========================================
    # GET /api/custody/proceeds/rollback-batches
    # ========================================
    
    def test_rollback_batches_returns_200(self):
        """Test that rollback-batches endpoint returns 200"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.get(f"{BASE_URL}/api/custody/proceeds/rollback-batches")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
    
    def test_rollback_batches_returns_list(self):
        """Test that rollback-batches returns a list of batches"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.get(f"{BASE_URL}/api/custody/proceeds/rollback-batches")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "batches" in data
        assert isinstance(data["batches"], list)
    
    def test_rollback_batches_structure(self):
        """Test that rollback batches have proper structure"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.get(f"{BASE_URL}/api/custody/proceeds/rollback-batches")
        
        assert response.status_code == 200
        data = response.json()
        
        batches = data["batches"]
        
        # If there are batches, verify structure
        if len(batches) > 0:
            batch = batches[0]
            assert "batch_id" in batch
            assert "record_count" in batch
            assert "total_value" in batch
    
    # ========================================
    # Integration Tests - Full Flow
    # ========================================
    
    def test_full_flow_preview_to_apply_to_rollback(self):
        """Test the full flow: preview -> apply -> verify -> rollback"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        # Step 1: Preview
        preview_response = self.session.get(f"{BASE_URL}/api/custody/proceeds/preview")
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        
        fixable_count = preview_data["summary"]["fixable_count"]
        
        if fixable_count == 0:
            # No candidates - this is expected per main agent context
            # Verify the exclusion reasons are correct
            non_fixable_reasons = preview_data["summary"]["non_fixable_reasons"]
            print(f"No fixable candidates. Non-fixable reasons: {non_fixable_reasons}")
            
            # Verify we have expected exclusion reasons
            assert preview_data["summary"]["non_fixable_count"] > 0
            return
        
        # Step 2: Apply (not dry run) - only if we have candidates
        apply_response = self.session.post(
            f"{BASE_URL}/api/custody/proceeds/apply",
            json={"dry_run": False}
        )
        assert apply_response.status_code == 200
        apply_data = apply_response.json()
        
        # Verify records were created
        assert apply_data.get("created_count", 0) > 0
        rollback_batch_id = apply_data.get("rollback_batch_id")
        assert rollback_batch_id is not None
        
        # Verify created records have source_disposal linkage
        created_records = apply_data.get("created_records", [])
        for record in created_records:
            assert "source_disposal" in record
        
        # Step 3: Verify batch appears in rollback-batches
        batches_response = self.session.get(f"{BASE_URL}/api/custody/proceeds/rollback-batches")
        assert batches_response.status_code == 200
        batches_data = batches_response.json()
        
        batch_ids = [b["batch_id"] for b in batches_data["batches"]]
        assert rollback_batch_id in batch_ids
        
        # Step 4: Rollback
        rollback_response = self.session.post(
            f"{BASE_URL}/api/custody/proceeds/rollback",
            json={"batch_id": rollback_batch_id}
        )
        assert rollback_response.status_code == 200
        rollback_data = rollback_response.json()
        
        assert rollback_data.get("success") == True
        assert rollback_data.get("deleted_count", 0) > 0
    
    # ========================================
    # Exclusion Verification Tests
    # ========================================
    
    def test_exclusions_are_properly_categorized(self):
        """Test that exclusions are properly categorized with reasons"""
        if not self.authenticated:
            pytest.skip("Authentication failed")
        
        response = self.session.get(f"{BASE_URL}/api/custody/proceeds/preview")
        
        assert response.status_code == 200
        data = response.json()
        
        skipped = data["preview"]["skipped"]
        non_fixable_reasons = data["summary"]["non_fixable_reasons"]
        
        # Count skipped items by reason
        reason_counts = {}
        for item in skipped:
            reason = item["skip_reason"]
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        # Verify counts match summary
        for reason, count in reason_counts.items():
            assert non_fixable_reasons.get(reason, 0) == count, \
                f"Mismatch for {reason}: skipped={count}, summary={non_fixable_reasons.get(reason, 0)}"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
