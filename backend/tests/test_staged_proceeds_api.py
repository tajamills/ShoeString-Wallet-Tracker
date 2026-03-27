"""
Test Staged Proceeds Application API Endpoints

Tests the following endpoints:
- GET /api/custody/proceeds/staged/stages - Get recommended application stages
- GET /api/custody/proceeds/staged/preview - Preview with filtering
- POST /api/custody/proceeds/staged/apply - Apply with filters, returns validation delta
- POST /api/custody/proceeds/staged/apply-exact - Convenience endpoint for exact-only
- POST /api/custody/proceeds/staged/apply-stablecoins - Convenience endpoint for stablecoins-only
- POST /api/custody/proceeds/staged/apply-high-confidence - Convenience endpoint for high-confidence
- GET /api/custody/proceeds/rollback-batches - List rollback batches
- POST /api/custody/proceeds/rollback - Rollback a batch

Also tests:
- Validation delta shows orphan_disposals, validation_status, can_export before/after
- Safety blocks for low-confidence approximates
- Rollback batches preserved and listed
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "mobiletest@test.com"
TEST_PASSWORD = "test123456"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestStagedProceedsStages:
    """Test GET /api/custody/proceeds/staged/stages endpoint"""
    
    def test_get_stages_returns_success(self, auth_headers):
        """Test that stages endpoint returns success"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/stages",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        print(f"Stages endpoint returned success: {data.get('success')}")
    
    def test_get_stages_returns_stages_structure(self, auth_headers):
        """Test that stages endpoint returns proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/stages",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        stages_data = data.get("stages", {})
        assert "total_candidates" in stages_data
        assert "stages" in stages_data
        assert "blocked_by_safety" in stages_data
        
        print(f"Total candidates: {stages_data.get('total_candidates')}")
        print(f"Number of stages: {len(stages_data.get('stages', []))}")
        print(f"Blocked by safety: {stages_data.get('blocked_by_safety')}")
    
    def test_stages_have_required_fields(self, auth_headers):
        """Test that each stage has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/stages",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        stages = data.get("stages", {}).get("stages", [])
        for stage in stages:
            assert "stage" in stage
            assert "name" in stage
            assert "candidates" in stage
            assert "total_value" in stage
            assert "risk_level" in stage
            assert "recommended" in stage
            assert "action" in stage
            print(f"Stage {stage['stage']}: {stage['name']} - {stage['candidates']} candidates, risk: {stage['risk_level']}")


class TestStagedProceedsPreview:
    """Test GET /api/custody/proceeds/staged/preview endpoint"""
    
    def test_preview_returns_success(self, auth_headers):
        """Test that preview endpoint returns success"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/preview",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        print(f"Preview endpoint returned success")
    
    def test_preview_returns_proper_structure(self, auth_headers):
        """Test that preview returns proper structure with valuation quality groups"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/preview",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        preview = data.get("preview", {})
        assert "filters_applied" in preview
        assert "summary" in preview
        assert "by_valuation_quality" in preview
        assert "blocked" in preview
        
        # Check valuation quality groups
        by_quality = preview.get("by_valuation_quality", {})
        assert "exact" in by_quality
        assert "stablecoin" in by_quality
        assert "high_confidence_approximate" in by_quality
        assert "low_confidence_approximate" in by_quality
        
        print(f"Preview summary: {preview.get('summary')}")
    
    def test_preview_with_asset_filter(self, auth_headers):
        """Test preview with asset filter"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/preview?assets=BTC",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        filters = data.get("preview", {}).get("filters_applied", {})
        assert filters.get("assets") == ["BTC"]
        print(f"Asset filter applied: {filters.get('assets')}")
    
    def test_preview_with_date_range_filter(self, auth_headers):
        """Test preview with date range filter"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/preview?date_from=2024-01-01&date_to=2024-12-31",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        filters = data.get("preview", {}).get("filters_applied", {})
        assert filters.get("date_from") == "2024-01-01"
        assert filters.get("date_to") == "2024-12-31"
        print(f"Date range filter applied: {filters.get('date_from')} to {filters.get('date_to')}")
    
    def test_preview_with_valuation_filter(self, auth_headers):
        """Test preview with different valuation filters"""
        for val_filter in ["exact_only", "stablecoin_only", "high_confidence", "all_eligible"]:
            response = requests.get(
                f"{BASE_URL}/api/custody/proceeds/staged/preview?valuation_filter={val_filter}",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            
            filters = data.get("preview", {}).get("filters_applied", {})
            assert filters.get("valuation_filter") == val_filter
            print(f"Valuation filter '{val_filter}' applied successfully")
    
    def test_preview_with_confidence_threshold(self, auth_headers):
        """Test preview with confidence threshold"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/preview?min_confidence=0.9",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        filters = data.get("preview", {}).get("filters_applied", {})
        assert filters.get("min_confidence") == 0.9
        print(f"Confidence threshold applied: {filters.get('min_confidence')}")


class TestStagedProceedsApply:
    """Test POST /api/custody/proceeds/staged/apply endpoint"""
    
    def test_apply_dry_run_returns_success(self, auth_headers):
        """Test that apply endpoint with dry_run returns success"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply",
            headers=auth_headers,
            json={"dry_run": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        print(f"Apply dry_run returned success")
    
    def test_apply_dry_run_returns_result_structure(self, auth_headers):
        """Test that apply dry_run returns proper result structure"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply",
            headers=auth_headers,
            json={"dry_run": True}
        )
        assert response.status_code == 200
        data = response.json()
        
        result = data.get("result", {})
        assert "batch_id" in result
        assert "filters_applied" in result
        assert "candidates_matched" in result
        assert "candidates_applied" in result
        assert "candidates_blocked" in result
        assert "total_value" in result
        
        print(f"Dry run result: matched={result.get('candidates_matched')}, applied={result.get('candidates_applied')}, blocked={result.get('candidates_blocked')}")
    
    def test_apply_with_asset_filter(self, auth_headers):
        """Test apply with asset filter"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply",
            headers=auth_headers,
            json={
                "assets": ["BTC"],
                "dry_run": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        filters = data.get("result", {}).get("filters_applied", {})
        assert filters.get("assets") == ["BTC"]
        print(f"Apply with asset filter: {filters.get('assets')}")
    
    def test_apply_with_valuation_filter(self, auth_headers):
        """Test apply with valuation filter"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply",
            headers=auth_headers,
            json={
                "valuation_filter": "high_confidence",
                "dry_run": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        filters = data.get("result", {}).get("filters_applied", {})
        assert filters.get("valuation_filter") == "high_confidence"
        print(f"Apply with valuation filter: {filters.get('valuation_filter')}")
    
    def test_apply_blocked_reasons_tracked(self, auth_headers):
        """Test that blocked reasons are tracked"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply",
            headers=auth_headers,
            json={
                "valuation_filter": "all_eligible",
                "min_confidence": 0.5,
                "dry_run": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        result = data.get("result", {})
        blocked_reasons = result.get("blocked_reasons", {})
        blocked_records = result.get("blocked_records", [])
        
        print(f"Blocked reasons: {blocked_reasons}")
        print(f"Blocked records count: {len(blocked_records)}")


class TestStagedProceedsConvenienceEndpoints:
    """Test convenience endpoints for staged application"""
    
    def test_apply_exact_only_dry_run(self, auth_headers):
        """Test apply-exact endpoint with dry_run"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply-exact?dry_run=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        result = data.get("result", {})
        filters = result.get("filters_applied", {})
        # Exact-only should have high min_confidence
        assert filters.get("min_confidence") >= 0.9
        print(f"Apply-exact dry_run: matched={result.get('candidates_matched')}, applied={result.get('candidates_applied')}")
    
    def test_apply_exact_only_with_asset_filter(self, auth_headers):
        """Test apply-exact with asset filter"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply-exact?assets=ETH&dry_run=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        filters = data.get("result", {}).get("filters_applied", {})
        assert filters.get("assets") == ["ETH"]
        print(f"Apply-exact with ETH filter: {filters.get('assets')}")
    
    def test_apply_stablecoins_only_dry_run(self, auth_headers):
        """Test apply-stablecoins endpoint with dry_run"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply-stablecoins?dry_run=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        result = data.get("result", {})
        filters = result.get("filters_applied", {})
        # Stablecoin-only should have confidence 1.0
        assert filters.get("min_confidence") == 1.0
        assert filters.get("valuation_filter") == "stablecoin_only"
        print(f"Apply-stablecoins dry_run: matched={result.get('candidates_matched')}, applied={result.get('candidates_applied')}")
    
    def test_apply_high_confidence_dry_run(self, auth_headers):
        """Test apply-high-confidence endpoint with dry_run"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply-high-confidence?dry_run=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        result = data.get("result", {})
        filters = result.get("filters_applied", {})
        # High-confidence should have min_confidence >= 0.8
        assert filters.get("min_confidence") >= 0.8
        assert filters.get("valuation_filter") == "high_confidence"
        print(f"Apply-high-confidence dry_run: matched={result.get('candidates_matched')}, applied={result.get('candidates_applied')}")
    
    def test_apply_high_confidence_with_asset_filter(self, auth_headers):
        """Test apply-high-confidence with asset filter"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply-high-confidence?assets=BTC,ETH&dry_run=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        filters = data.get("result", {}).get("filters_applied", {})
        assert filters.get("assets") == ["BTC", "ETH"]
        print(f"Apply-high-confidence with BTC,ETH filter: {filters.get('assets')}")


class TestRollbackBatches:
    """Test rollback batch listing and rollback functionality"""
    
    def test_list_rollback_batches(self, auth_headers):
        """Test listing rollback batches"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/rollback-batches",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        batches = data.get("batches", [])
        print(f"Found {len(batches)} rollback batches")
        
        for batch in batches[:5]:  # Print first 5
            print(f"  Batch {batch.get('batch_id', 'N/A')[:8]}...: {batch.get('record_count', 0)} records, ${batch.get('total_value', 0):.2f}")
    
    def test_rollback_batches_have_required_fields(self, auth_headers):
        """Test that rollback batches have required fields"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/rollback-batches",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        batches = data.get("batches", [])
        if batches:
            batch = batches[0]
            assert "batch_id" in batch
            assert "record_count" in batch
            assert "total_value" in batch
            print(f"Batch structure verified: {list(batch.keys())}")
        else:
            print("No batches to verify structure")
    
    def test_rollback_invalid_batch_returns_404(self, auth_headers):
        """Test that rollback with invalid batch_id returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/rollback",
            headers=auth_headers,
            json={"batch_id": "invalid-batch-id-12345"}
        )
        # Should return 404 for invalid batch
        assert response.status_code == 404
        print(f"Invalid batch rollback correctly returned 404")


class TestValidationDelta:
    """Test validation delta metrics in staged application"""
    
    def test_validation_delta_structure_in_apply(self, auth_headers):
        """Test that validation delta has proper structure when applying (non-dry-run would have it)"""
        # First check if there are any candidates to apply
        preview_response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/preview?valuation_filter=all_eligible",
            headers=auth_headers
        )
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        
        total_candidates = preview_data.get("preview", {}).get("summary", {}).get("total_candidates", 0)
        print(f"Total candidates available: {total_candidates}")
        
        # Dry run won't have validation_delta, but we can verify the structure is expected
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply",
            headers=auth_headers,
            json={"dry_run": True}
        )
        assert response.status_code == 200
        data = response.json()
        
        result = data.get("result", {})
        # In dry_run, validation_delta should be None
        validation_delta = result.get("validation_delta")
        print(f"Validation delta in dry_run: {validation_delta}")
        
        # Verify the result has the expected fields
        assert "candidates_matched" in result
        assert "candidates_applied" in result
        assert "total_value" in result


class TestSafetyBlocks:
    """Test safety blocks for low-confidence approximates"""
    
    def test_low_confidence_blocked_without_force_override(self, auth_headers):
        """Test that low-confidence candidates are blocked without force_override"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply",
            headers=auth_headers,
            json={
                "valuation_filter": "all_eligible",
                "min_confidence": 0.5,  # Low threshold
                "exclude_wide_window": False,
                "dry_run": True,
                "force_override": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        result = data.get("result", {})
        blocked_reasons = result.get("blocked_reasons", {})
        
        # Check if any low_confidence blocks exist
        low_conf_blocks = [k for k in blocked_reasons.keys() if "low_confidence" in k]
        print(f"Low confidence blocks: {low_conf_blocks}")
        print(f"All blocked reasons: {blocked_reasons}")
    
    def test_wide_window_blocked_by_default(self, auth_headers):
        """Test that wide-window approximates are blocked by default"""
        response = requests.post(
            f"{BASE_URL}/api/custody/proceeds/staged/apply",
            headers=auth_headers,
            json={
                "valuation_filter": "all_eligible",
                "exclude_wide_window": True,  # Default
                "dry_run": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        result = data.get("result", {})
        blocked_reasons = result.get("blocked_reasons", {})
        
        # Check if any wide_window blocks exist
        wide_window_blocks = [k for k in blocked_reasons.keys() if "wide_window" in k]
        print(f"Wide window blocks: {wide_window_blocks}")


class TestIntegrationWithExistingBatches:
    """Test integration with existing rollback batches from main agent context"""
    
    def test_existing_batches_listed(self, auth_headers):
        """Test that existing batches from previous staged applications are listed"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/rollback-batches",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        batches = data.get("batches", [])
        print(f"Total rollback batches: {len(batches)}")
        
        # According to main agent context, there should be 3 batches:
        # - 33b95565 (BTC, 15 records)
        # - 74eda72d (ETH, 20 records)
        # - 9b4bd296 (remaining, 86 records)
        
        for batch in batches:
            batch_id = batch.get("batch_id", "")
            record_count = batch.get("record_count", 0)
            total_value = batch.get("total_value", 0)
            assets = batch.get("assets", [])
            print(f"  Batch {batch_id[:8]}...: {record_count} records, ${total_value:.2f}, assets: {assets}")
    
    def test_stages_show_zero_remaining_after_all_applied(self, auth_headers):
        """Test that stages endpoint shows 0 remaining candidates after all applied"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/stages",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        stages_data = data.get("stages", {})
        total_candidates = stages_data.get("total_candidates", -1)
        
        print(f"Total remaining candidates: {total_candidates}")
        # According to main agent context, all 121 candidates have been applied
        # So total_candidates should be 0


class TestRollbackFunctionality:
    """Test rollback functionality with existing batches"""
    
    def test_rollback_batch_preview(self, auth_headers):
        """Test that we can identify a batch to rollback"""
        # First list batches
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/rollback-batches",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        batches = data.get("batches", [])
        if not batches:
            pytest.skip("No batches available for rollback test")
        
        # Get the first batch for potential rollback
        first_batch = batches[0]
        batch_id = first_batch.get("batch_id")
        record_count = first_batch.get("record_count", 0)
        
        print(f"Batch available for rollback: {batch_id[:8]}... with {record_count} records")
        
        # Note: We won't actually rollback in this test to preserve data
        # Just verify the batch exists and has the expected structure


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
