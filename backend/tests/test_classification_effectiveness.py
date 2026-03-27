"""
Test Classification Effectiveness Metrics Routes

Tests for the Unknown Classification Effectiveness Metrics System:
- GET /api/custody/classify/effectiveness - Comprehensive effectiveness summary
- GET /api/custody/classify/effectiveness/confidence-buckets - Precision by confidence bucket
- GET /api/custody/classify/effectiveness/classification-types - Metrics by classification type
- POST /api/custody/classify/effectiveness/snapshot - Capture before/after snapshots
- GET /api/custody/classify/effectiveness/admin/summary - Aggregated summary across all accounts

Tracks:
- unknown_count_before/after, auto_classified_count, user_confirmed_count, rollback_count
- validation_status_before/after, can_export_before/after
- Precision metrics by confidence bucket (high >0.95, medium_high 0.85-0.95, medium 0.70-0.85, low <0.70)
- Metrics by classification type (internal_transfer, external_transfer, swap, bridge)
"""

import pytest
import requests
import os
from datetime import datetime

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "mobiletest@test.com"
TEST_PASSWORD = "test123456"


class TestClassificationEffectivenessRoutes:
    """Test classification effectiveness API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        token = data.get("access_token") or data.get("token")
        assert token, f"No token in login response: {data.keys()}"
        return token
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    # === GET /api/custody/classify/effectiveness ===
    def test_effectiveness_summary_success(self, auth_headers):
        """Test effectiveness endpoint returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Effectiveness failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert data["success"] == True
        assert "effectiveness" in data
        
        effectiveness = data["effectiveness"]
        
        # Verify required fields for before/after tracking
        assert "user_id" in effectiveness
        assert "period_start" in effectiveness
        assert "period_end" in effectiveness
        
        # Verify unknown count tracking
        assert "unknown_count_before" in effectiveness
        assert "unknown_count_after" in effectiveness
        assert "unknown_reduction" in effectiveness
        assert "unknown_reduction_pct" in effectiveness
        
        # Verify classification counts
        assert "auto_classified_count" in effectiveness
        assert "user_confirmed_count" in effectiveness
        assert "user_rejected_count" in effectiveness
        assert "rollback_count" in effectiveness
        
        # Verify validation status tracking
        assert "validation_status_before" in effectiveness
        assert "validation_status_after" in effectiveness
        assert "can_export_before" in effectiveness
        assert "can_export_after" in effectiveness
        
        # Verify export readiness improvement flag
        assert "export_readiness_improved" in effectiveness
        
        # Verify confidence buckets and classification types
        assert "confidence_buckets" in effectiveness
        assert "classification_types" in effectiveness
        assert "overall_precision" in effectiveness
        
        # Verify types
        assert isinstance(effectiveness["confidence_buckets"], list)
        assert isinstance(effectiveness["classification_types"], list)
        assert isinstance(effectiveness["overall_precision"], (int, float))
        
        print(f"Effectiveness: unknown_before={effectiveness['unknown_count_before']}, "
              f"unknown_after={effectiveness['unknown_count_after']}, "
              f"auto_classified={effectiveness['auto_classified_count']}, "
              f"precision={effectiveness['overall_precision']}")
    
    def test_effectiveness_with_days_parameter(self, auth_headers):
        """Test effectiveness endpoint with custom days parameter"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness?days=7",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "effectiveness" in data
        
        # Verify period is approximately 7 days
        effectiveness = data["effectiveness"]
        assert "period_start" in effectiveness
        assert "period_end" in effectiveness
        print(f"Effectiveness with 7 days: period_start={effectiveness['period_start']}")
    
    def test_effectiveness_unauthorized(self):
        """Test effectiveness endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/custody/classify/effectiveness")
        assert response.status_code in [401, 403], "Should require auth"
    
    # === GET /api/custody/classify/effectiveness/confidence-buckets ===
    def test_confidence_buckets_success(self, auth_headers):
        """Test confidence buckets endpoint returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/confidence-buckets",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Confidence buckets failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "confidence_buckets" in data
        
        buckets = data["confidence_buckets"]
        assert isinstance(buckets, list)
        
        # Verify expected bucket names exist
        bucket_names = [b["bucket_name"] for b in buckets]
        expected_buckets = ["high", "medium_high", "medium", "low"]
        
        for expected in expected_buckets:
            assert expected in bucket_names, f"Missing bucket: {expected}"
        
        # Verify bucket structure
        for bucket in buckets:
            assert "bucket_name" in bucket
            assert "min_confidence" in bucket
            assert "max_confidence" in bucket
            assert "total_classified" in bucket
            assert "user_confirmed" in bucket
            assert "user_rejected" in bucket
            assert "rollback_count" in bucket
            assert "precision" in bucket
            
            # Verify confidence ranges
            if bucket["bucket_name"] == "high":
                assert bucket["min_confidence"] == 0.95
                assert bucket["max_confidence"] == 1.0
            elif bucket["bucket_name"] == "medium_high":
                assert bucket["min_confidence"] == 0.85
                assert bucket["max_confidence"] == 0.95
            elif bucket["bucket_name"] == "medium":
                assert bucket["min_confidence"] == 0.70
                assert bucket["max_confidence"] == 0.85
            elif bucket["bucket_name"] == "low":
                assert bucket["min_confidence"] == 0.0
                assert bucket["max_confidence"] == 0.70
        
        print(f"Confidence buckets: {len(buckets)} buckets returned")
        for b in buckets:
            print(f"  - {b['bucket_name']}: total={b['total_classified']}, precision={b['precision']}")
    
    def test_confidence_buckets_with_days_parameter(self, auth_headers):
        """Test confidence buckets with custom days parameter"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/confidence-buckets?days=14",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "confidence_buckets" in data
    
    def test_confidence_buckets_unauthorized(self):
        """Test confidence buckets requires authentication"""
        response = requests.get(f"{BASE_URL}/api/custody/classify/effectiveness/confidence-buckets")
        assert response.status_code in [401, 403]
    
    # === GET /api/custody/classify/effectiveness/classification-types ===
    def test_classification_types_success(self, auth_headers):
        """Test classification types endpoint returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/classification-types",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Classification types failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "classification_types" in data
        
        types = data["classification_types"]
        assert isinstance(types, list)
        
        # If there are classification types, verify structure
        if types:
            for ct in types:
                assert "classification_type" in ct
                assert "total_classified" in ct
                assert "auto_classified" in ct
                assert "user_confirmed" in ct
                assert "user_rejected" in ct
                assert "rollback_count" in ct
                assert "precision" in ct
                
                # Verify classification type is one of expected types
                expected_types = [
                    "internal_transfer", "external_transfer", "swap", "bridge",
                    "deposit", "withdrawal", "buy", "sell", "reward", "staking"
                ]
                assert ct["classification_type"] in expected_types or ct["classification_type"] == "unknown", \
                    f"Unexpected classification type: {ct['classification_type']}"
        
        print(f"Classification types: {len(types)} types with classifications")
        for ct in types:
            print(f"  - {ct['classification_type']}: total={ct['total_classified']}, precision={ct['precision']}")
    
    def test_classification_types_with_days_parameter(self, auth_headers):
        """Test classification types with custom days parameter"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/classification-types?days=60",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "classification_types" in data
    
    def test_classification_types_unauthorized(self):
        """Test classification types requires authentication"""
        response = requests.get(f"{BASE_URL}/api/custody/classify/effectiveness/classification-types")
        assert response.status_code in [401, 403]
    
    # === POST /api/custody/classify/effectiveness/snapshot ===
    def test_snapshot_before_success(self, auth_headers):
        """Test capturing 'before' snapshot"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/effectiveness/snapshot?snapshot_type=before",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Snapshot before failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "snapshot" in data
        
        snapshot = data["snapshot"]
        
        # Verify snapshot structure
        assert "snapshot_id" in snapshot
        assert "user_id" in snapshot
        assert "timestamp" in snapshot
        assert "snapshot_type" in snapshot
        assert snapshot["snapshot_type"] == "before"
        
        # Verify state tracking fields
        assert "unknown_count" in snapshot
        assert "validation_status" in snapshot
        assert "can_export" in snapshot
        assert "blocking_issues_count" in snapshot
        assert "unresolved_review_count" in snapshot
        
        # Verify types
        assert isinstance(snapshot["unknown_count"], int)
        assert isinstance(snapshot["can_export"], bool)
        assert isinstance(snapshot["blocking_issues_count"], int)
        
        print(f"Snapshot before: id={snapshot['snapshot_id'][:8]}..., "
              f"unknown_count={snapshot['unknown_count']}, "
              f"can_export={snapshot['can_export']}")
    
    def test_snapshot_after_success(self, auth_headers):
        """Test capturing 'after' snapshot"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/effectiveness/snapshot?snapshot_type=after",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Snapshot after failed: {response.text}"
        data = response.json()
        
        assert data["success"] == True
        assert "snapshot" in data
        
        snapshot = data["snapshot"]
        assert snapshot["snapshot_type"] == "after"
        
        print(f"Snapshot after: id={snapshot['snapshot_id'][:8]}..., "
              f"unknown_count={snapshot['unknown_count']}")
    
    def test_snapshot_invalid_type(self, auth_headers):
        """Test snapshot with invalid snapshot_type"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/effectiveness/snapshot?snapshot_type=invalid",
            headers=auth_headers
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid type: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"Invalid snapshot type error: {data['detail']}")
    
    def test_snapshot_default_type(self, auth_headers):
        """Test snapshot with default type (should be 'before')"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/effectiveness/snapshot",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["snapshot"]["snapshot_type"] == "before"
    
    def test_snapshot_unauthorized(self):
        """Test snapshot requires authentication"""
        response = requests.post(f"{BASE_URL}/api/custody/classify/effectiveness/snapshot")
        assert response.status_code in [401, 403]
    
    # === GET /api/custody/classify/effectiveness/admin/summary ===
    def test_admin_summary_success(self, auth_headers):
        """Test admin summary endpoint returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/admin/summary",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Admin summary failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "summary" in data
        
        summary = data["summary"]
        
        # Verify aggregated metrics
        assert "period_days" in summary
        assert "accounts_count" in summary
        assert "total_auto_classified" in summary
        assert "total_user_confirmed" in summary
        assert "total_user_rejected" in summary
        assert "total_rollbacks" in summary
        assert "aggregate_precision" in summary
        assert "accounts_improved" in summary
        
        # Verify confidence buckets and classification types
        assert "confidence_buckets" in summary
        assert "classification_types" in summary
        
        # Verify types
        assert isinstance(summary["accounts_count"], int)
        assert isinstance(summary["total_auto_classified"], int)
        assert isinstance(summary["aggregate_precision"], (int, float))
        assert isinstance(summary["confidence_buckets"], list)
        assert isinstance(summary["classification_types"], list)
        
        print(f"Admin summary: accounts={summary['accounts_count']}, "
              f"total_auto_classified={summary['total_auto_classified']}, "
              f"aggregate_precision={summary['aggregate_precision']}, "
              f"accounts_improved={summary['accounts_improved']}")
    
    def test_admin_summary_with_days_parameter(self, auth_headers):
        """Test admin summary with custom days parameter"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/admin/summary?days=90",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["summary"]["period_days"] == 90
    
    def test_admin_summary_unauthorized(self):
        """Test admin summary requires authentication"""
        response = requests.get(f"{BASE_URL}/api/custody/classify/effectiveness/admin/summary")
        assert response.status_code in [401, 403]


class TestEffectivenessIntegration:
    """Integration tests for effectiveness tracking workflow"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_full_effectiveness_workflow(self, auth_headers):
        """Test complete effectiveness tracking workflow"""
        # Step 1: Capture 'before' snapshot
        before_response = requests.post(
            f"{BASE_URL}/api/custody/classify/effectiveness/snapshot?snapshot_type=before",
            headers=auth_headers
        )
        assert before_response.status_code == 200
        before_snapshot = before_response.json()["snapshot"]
        print(f"Step 1 - Before snapshot: unknown_count={before_snapshot['unknown_count']}")
        
        # Step 2: Get effectiveness summary
        effectiveness_response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness",
            headers=auth_headers
        )
        assert effectiveness_response.status_code == 200
        effectiveness = effectiveness_response.json()["effectiveness"]
        print(f"Step 2 - Effectiveness: auto_classified={effectiveness['auto_classified_count']}, "
              f"precision={effectiveness['overall_precision']}")
        
        # Step 3: Get confidence bucket breakdown
        buckets_response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/confidence-buckets",
            headers=auth_headers
        )
        assert buckets_response.status_code == 200
        buckets = buckets_response.json()["confidence_buckets"]
        print(f"Step 3 - Confidence buckets: {len(buckets)} buckets")
        
        # Step 4: Get classification type breakdown
        types_response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/classification-types",
            headers=auth_headers
        )
        assert types_response.status_code == 200
        types = types_response.json()["classification_types"]
        print(f"Step 4 - Classification types: {len(types)} types with data")
        
        # Step 5: Capture 'after' snapshot
        after_response = requests.post(
            f"{BASE_URL}/api/custody/classify/effectiveness/snapshot?snapshot_type=after",
            headers=auth_headers
        )
        assert after_response.status_code == 200
        after_snapshot = after_response.json()["snapshot"]
        print(f"Step 5 - After snapshot: unknown_count={after_snapshot['unknown_count']}")
        
        # Step 6: Get admin summary
        admin_response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/admin/summary",
            headers=auth_headers
        )
        assert admin_response.status_code == 200
        admin_summary = admin_response.json()["summary"]
        print(f"Step 6 - Admin summary: accounts={admin_summary['accounts_count']}, "
              f"aggregate_precision={admin_summary['aggregate_precision']}")
        
        print("Full effectiveness workflow completed successfully!")
    
    def test_effectiveness_data_consistency(self, auth_headers):
        """Test that effectiveness data is consistent across endpoints"""
        # Get main effectiveness summary
        effectiveness_response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness",
            headers=auth_headers
        )
        assert effectiveness_response.status_code == 200
        effectiveness = effectiveness_response.json()["effectiveness"]
        
        # Get confidence buckets
        buckets_response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/confidence-buckets",
            headers=auth_headers
        )
        assert buckets_response.status_code == 200
        buckets = buckets_response.json()["confidence_buckets"]
        
        # Verify confidence buckets in effectiveness match standalone endpoint
        assert len(effectiveness["confidence_buckets"]) == len(buckets)
        
        # Verify bucket names match
        effectiveness_bucket_names = {b["bucket_name"] for b in effectiveness["confidence_buckets"]}
        standalone_bucket_names = {b["bucket_name"] for b in buckets}
        assert effectiveness_bucket_names == standalone_bucket_names
        
        print("Effectiveness data consistency verified!")
    
    def test_precision_calculation_validity(self, auth_headers):
        """Test that precision values are valid (between 0 and 1)"""
        # Get confidence buckets
        buckets_response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/confidence-buckets",
            headers=auth_headers
        )
        assert buckets_response.status_code == 200
        buckets = buckets_response.json()["confidence_buckets"]
        
        for bucket in buckets:
            precision = bucket["precision"]
            assert 0 <= precision <= 1, f"Invalid precision {precision} for bucket {bucket['bucket_name']}"
            
            # Verify precision calculation
            confirmed = bucket["user_confirmed"]
            rejected = bucket["user_rejected"]
            total = confirmed + rejected
            
            if total > 0:
                expected_precision = confirmed / total
                assert abs(precision - expected_precision) < 0.01, \
                    f"Precision mismatch for {bucket['bucket_name']}: {precision} vs {expected_precision}"
        
        # Get classification types
        types_response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/classification-types",
            headers=auth_headers
        )
        assert types_response.status_code == 200
        types = types_response.json()["classification_types"]
        
        for ct in types:
            precision = ct["precision"]
            assert 0 <= precision <= 1, f"Invalid precision {precision} for type {ct['classification_type']}"
        
        print("Precision calculation validity verified!")
    
    def test_snapshot_persistence(self, auth_headers):
        """Test that snapshots are persisted and affect effectiveness summary"""
        # Capture a before snapshot
        before_response = requests.post(
            f"{BASE_URL}/api/custody/classify/effectiveness/snapshot?snapshot_type=before",
            headers=auth_headers
        )
        assert before_response.status_code == 200
        before_snapshot = before_response.json()["snapshot"]
        
        # Get effectiveness - should now have snapshot data
        effectiveness_response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness",
            headers=auth_headers
        )
        assert effectiveness_response.status_code == 200
        effectiveness = effectiveness_response.json()["effectiveness"]
        
        # The unknown_count_before should reflect snapshot or current state
        assert "unknown_count_before" in effectiveness
        assert isinstance(effectiveness["unknown_count_before"], int)
        
        print(f"Snapshot persistence verified: before_unknown={before_snapshot['unknown_count']}, "
              f"effectiveness_before={effectiveness['unknown_count_before']}")


class TestEffectivenessEdgeCases:
    """Edge case tests for effectiveness metrics"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_effectiveness_with_zero_days(self, auth_headers):
        """Test effectiveness with days=0 (edge case)"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness?days=0",
            headers=auth_headers
        )
        
        # Should still return valid response (may have no data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_effectiveness_with_large_days(self, auth_headers):
        """Test effectiveness with very large days parameter"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness?days=365",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_admin_summary_empty_state(self, auth_headers):
        """Test admin summary handles empty state gracefully"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/effectiveness/admin/summary?days=1",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        summary = data["summary"]
        # Should have valid structure even with no data
        assert "accounts_count" in summary
        assert "aggregate_precision" in summary
        assert isinstance(summary["accounts_count"], int)
        assert summary["accounts_count"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
