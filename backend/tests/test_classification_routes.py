"""
Test Unknown Transaction Classification Routes

Tests for the Unknown Transaction Reduction System:
- Pattern Detection Engine
- Auto-Suggestion Engine
- Bulk Classification
- Auto-Apply Threshold
- Feedback Loop
- Metrics Dashboard
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


class TestClassificationRoutes:
    """Test classification API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        # API returns access_token, not token
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
    
    # === GET /api/custody/classify/analyze ===
    def test_analyze_unknown_transactions_success(self, auth_headers):
        """Test analyze endpoint returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/analyze",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Analyze failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert data["success"] == True
        assert "analysis" in data
        
        analysis = data["analysis"]
        assert "unknown_count" in analysis
        assert "patterns" in analysis
        assert "by_confidence" in analysis
        assert "metrics" in analysis
        
        # Verify by_confidence structure
        by_confidence = analysis["by_confidence"]
        assert "auto_apply" in by_confidence
        assert "suggest" in by_confidence
        assert "unresolved" in by_confidence
        
        # Verify metrics structure
        metrics = analysis["metrics"]
        assert "total_unknown" in metrics
        assert "auto_classified" in metrics
        assert "suggested_count" in metrics
        assert "unresolved_count" in metrics
        
        print(f"Analyze: unknown_count={analysis['unknown_count']}, patterns={len(analysis['patterns'])}")
    
    def test_analyze_with_limit_parameter(self, auth_headers):
        """Test analyze endpoint with limit parameter"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/analyze?limit=100",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_analyze_unauthorized(self):
        """Test analyze endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/custody/classify/analyze")
        assert response.status_code in [401, 403], "Should require auth"
    
    # === POST /api/custody/classify/auto-apply ===
    def test_auto_apply_dry_run(self, auth_headers):
        """Test auto-apply with dry_run=true"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/auto-apply?dry_run=true",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Auto-apply failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "result" in data
        
        result = data["result"]
        assert "dry_run" in result
        assert result["dry_run"] == True
        assert "classified_count" in result
        
        print(f"Auto-apply dry run: would classify {result['classified_count']} transactions")
    
    def test_auto_apply_actual(self, auth_headers):
        """Test auto-apply with dry_run=false (actual classification)"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/auto-apply?dry_run=false",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Auto-apply actual failed: {response.text}"
        data = response.json()
        
        assert data["success"] == True
        result = data["result"]
        assert "dry_run" in result
        assert result["dry_run"] == False
        assert "classified_count" in result
        
        # If no transactions to classify, should have appropriate message
        if result["classified_count"] == 0:
            assert "message" in result or "batch_id" not in result
        
        print(f"Auto-apply actual: classified {result['classified_count']} transactions")
    
    def test_auto_apply_unauthorized(self):
        """Test auto-apply requires authentication"""
        response = requests.post(f"{BASE_URL}/api/custody/classify/auto-apply")
        assert response.status_code in [401, 403]
    
    # === GET /api/custody/classify/metrics ===
    def test_get_metrics_success(self, auth_headers):
        """Test metrics endpoint returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/metrics",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Metrics failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "metrics" in data
        
        metrics = data["metrics"]
        assert "current_unknown" in metrics
        assert "period_days" in metrics
        assert "auto_classification_rate" in metrics
        assert "suggestion_accuracy" in metrics
        assert "total_feedback" in metrics
        assert "accepted" in metrics
        assert "rejected" in metrics
        assert "daily_stats" in metrics
        
        print(f"Metrics: current_unknown={metrics['current_unknown']}, accuracy={metrics['suggestion_accuracy']}")
    
    def test_get_metrics_with_days_parameter(self, auth_headers):
        """Test metrics endpoint with custom days parameter"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/metrics?days=7",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["metrics"]["period_days"] == 7
    
    def test_get_metrics_unauthorized(self):
        """Test metrics requires authentication"""
        response = requests.get(f"{BASE_URL}/api/custody/classify/metrics")
        assert response.status_code in [401, 403]
    
    # === GET /api/custody/classify/patterns ===
    def test_get_patterns_success(self, auth_headers):
        """Test patterns endpoint returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/patterns",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Patterns failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "patterns" in data
        assert isinstance(data["patterns"], list)
        
        # If patterns exist, verify structure
        if data["patterns"]:
            pattern = data["patterns"][0]
            assert "pattern_id" in pattern
            assert "pattern_type" in pattern
            assert "confidence" in pattern
        
        print(f"Patterns: found {len(data['patterns'])} patterns")
    
    def test_get_patterns_unauthorized(self):
        """Test patterns requires authentication"""
        response = requests.get(f"{BASE_URL}/api/custody/classify/patterns")
        assert response.status_code in [401, 403]
    
    # === POST /api/custody/classify/by-pattern ===
    def test_classify_by_pattern_dry_run(self, auth_headers):
        """Test bulk classify by pattern with dry_run=true"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/by-pattern",
            headers=auth_headers,
            json={
                "pattern_id": "test_pattern_123",
                "classification": "internal_transfer",
                "dry_run": True
            }
        )
        
        assert response.status_code == 200, f"By-pattern failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert "result" in data
        
        result = data["result"]
        # Pattern may not exist, so check for error or success
        if result.get("success") == False:
            assert "error" in result
            print(f"By-pattern: pattern not found (expected for test)")
        else:
            assert "dry_run" in result
            print(f"By-pattern: would classify {result.get('would_classify', 0)} transactions")
    
    def test_classify_by_pattern_missing_fields(self, auth_headers):
        """Test by-pattern with missing required fields"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/by-pattern",
            headers=auth_headers,
            json={"pattern_id": "test"}  # Missing classification
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422, f"Expected validation error: {response.text}"
    
    def test_classify_by_pattern_unauthorized(self):
        """Test by-pattern requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/by-pattern",
            json={"pattern_id": "test", "classification": "internal_transfer"}
        )
        assert response.status_code in [401, 403]
    
    # === POST /api/custody/classify/by-destination ===
    def test_classify_by_destination_dry_run(self, auth_headers):
        """Test bulk classify by destination with dry_run=true"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/by-destination",
            headers=auth_headers,
            json={
                "destination_wallet": "0x1234567890abcdef1234567890abcdef12345678",
                "classification": "deposit",
                "dry_run": True
            }
        )
        
        assert response.status_code == 200, f"By-destination failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "result" in data
        
        result = data["result"]
        # May have 0 transactions to classify
        if "classified_count" in result:
            print(f"By-destination: {result['classified_count']} transactions")
        elif "would_classify" in result:
            print(f"By-destination: would classify {result['would_classify']} transactions")
        else:
            print(f"By-destination: {result.get('message', 'no transactions')}")
    
    def test_classify_by_destination_actual(self, auth_headers):
        """Test bulk classify by destination with dry_run=false"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/by-destination",
            headers=auth_headers,
            json={
                "destination_wallet": "0xnonexistent1234567890abcdef12345678",
                "classification": "external_transfer",
                "dry_run": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_classify_by_destination_missing_fields(self, auth_headers):
        """Test by-destination with missing required fields"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/by-destination",
            headers=auth_headers,
            json={"destination_wallet": "0x123"}  # Missing classification
        )
        
        assert response.status_code == 422
    
    def test_classify_by_destination_unauthorized(self):
        """Test by-destination requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/by-destination",
            json={"destination_wallet": "0x123", "classification": "deposit"}
        )
        assert response.status_code in [401, 403]
    
    # === POST /api/custody/classify/decide ===
    def test_decide_accept_suggestion(self, auth_headers):
        """Test accepting a classification suggestion (feedback loop)"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/decide",
            headers=auth_headers,
            json={
                "tx_id": "test_tx_nonexistent_123",
                "accept": True,
                "override_type": None
            }
        )
        
        assert response.status_code == 200, f"Decide failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert "result" in data
        
        result = data["result"]
        # Transaction may not exist
        if result.get("success") == False:
            assert "error" in result
            print(f"Decide: transaction not found (expected for test)")
        else:
            print(f"Decide: accepted suggestion for {result.get('tx_id')}")
    
    def test_decide_reject_suggestion(self, auth_headers):
        """Test rejecting a classification suggestion"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/decide",
            headers=auth_headers,
            json={
                "tx_id": "test_tx_nonexistent_456",
                "accept": False,
                "override_type": "unknown"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
    
    def test_decide_with_override(self, auth_headers):
        """Test decision with override type"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/decide",
            headers=auth_headers,
            json={
                "tx_id": "test_tx_nonexistent_789",
                "accept": True,
                "override_type": "internal_transfer"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
    
    def test_decide_missing_fields(self, auth_headers):
        """Test decide with missing required fields"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/decide",
            headers=auth_headers,
            json={"tx_id": "test"}  # Missing accept
        )
        
        assert response.status_code == 422
    
    def test_decide_unauthorized(self):
        """Test decide requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/decide",
            json={"tx_id": "test", "accept": True}
        )
        assert response.status_code in [401, 403]
    
    # === GET /api/custody/classify/batches ===
    def test_get_batches_success(self, auth_headers):
        """Test get classification batches for rollback"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/batches",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Batches failed: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert data["success"] == True
        assert "batches" in data
        assert isinstance(data["batches"], list)
        
        # If batches exist, verify structure
        if data["batches"]:
            batch = data["batches"][0]
            assert "batch_id" in batch
            assert "user_id" in batch
            assert "count" in batch
            assert "created_at" in batch
        
        print(f"Batches: found {len(data['batches'])} batches")
    
    def test_get_batches_unauthorized(self):
        """Test batches requires authentication"""
        response = requests.get(f"{BASE_URL}/api/custody/classify/batches")
        assert response.status_code in [401, 403]
    
    # === POST /api/custody/classify/rollback/{batch_id} ===
    def test_rollback_nonexistent_batch(self, auth_headers):
        """Test rollback with nonexistent batch_id"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/rollback/nonexistent_batch_123",
            headers=auth_headers
        )
        
        # Should return 404 for batch not found
        assert response.status_code == 404, f"Expected 404: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"Rollback nonexistent: {data['detail']}")
    
    def test_rollback_unauthorized(self):
        """Test rollback requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/custody/classify/rollback/test_batch"
        )
        assert response.status_code in [401, 403]
    
    # === GET /api/custody/classify/suggestions/{tx_id} ===
    def test_get_suggestion_nonexistent_tx(self, auth_headers):
        """Test get suggestion for nonexistent transaction"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/suggestions/nonexistent_tx_123",
            headers=auth_headers
        )
        
        # Should return 404 for transaction not found
        assert response.status_code == 404, f"Expected 404: {response.text}"
        data = response.json()
        assert "detail" in data
        print(f"Suggestion nonexistent: {data['detail']}")
    
    def test_get_suggestion_unauthorized(self):
        """Test suggestions requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/suggestions/test_tx"
        )
        assert response.status_code in [401, 403]


class TestClassificationIntegration:
    """Integration tests for classification workflow"""
    
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
    
    def test_full_classification_workflow(self, auth_headers):
        """Test complete classification workflow: analyze -> auto-apply -> metrics"""
        # Step 1: Analyze unknown transactions
        analyze_response = requests.get(
            f"{BASE_URL}/api/custody/classify/analyze",
            headers=auth_headers
        )
        assert analyze_response.status_code == 200
        analysis = analyze_response.json()["analysis"]
        
        initial_unknown = analysis["unknown_count"]
        print(f"Step 1 - Analyze: {initial_unknown} unknown transactions")
        
        # Step 2: Check patterns
        patterns_response = requests.get(
            f"{BASE_URL}/api/custody/classify/patterns",
            headers=auth_headers
        )
        assert patterns_response.status_code == 200
        patterns = patterns_response.json()["patterns"]
        print(f"Step 2 - Patterns: {len(patterns)} patterns detected")
        
        # Step 3: Auto-apply (dry run first)
        auto_dry_response = requests.post(
            f"{BASE_URL}/api/custody/classify/auto-apply?dry_run=true",
            headers=auth_headers
        )
        assert auto_dry_response.status_code == 200
        dry_result = auto_dry_response.json()["result"]
        print(f"Step 3 - Auto-apply dry run: would classify {dry_result['classified_count']}")
        
        # Step 4: Get metrics
        metrics_response = requests.get(
            f"{BASE_URL}/api/custody/classify/metrics",
            headers=auth_headers
        )
        assert metrics_response.status_code == 200
        metrics = metrics_response.json()["metrics"]
        print(f"Step 4 - Metrics: current_unknown={metrics['current_unknown']}, accuracy={metrics['suggestion_accuracy']}")
        
        # Step 5: Check batches
        batches_response = requests.get(
            f"{BASE_URL}/api/custody/classify/batches",
            headers=auth_headers
        )
        assert batches_response.status_code == 200
        batches = batches_response.json()["batches"]
        print(f"Step 5 - Batches: {len(batches)} batches available for rollback")
        
        print("Full classification workflow completed successfully!")
    
    def test_confidence_levels_structure(self, auth_headers):
        """Test that confidence levels are properly structured"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/analyze",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        by_confidence = response.json()["analysis"]["by_confidence"]
        
        # Verify all confidence levels exist
        assert "auto_apply" in by_confidence, "Missing auto_apply level"
        assert "suggest" in by_confidence, "Missing suggest level"
        assert "unresolved" in by_confidence, "Missing unresolved level"
        
        # All should be lists
        assert isinstance(by_confidence["auto_apply"], list)
        assert isinstance(by_confidence["suggest"], list)
        assert isinstance(by_confidence["unresolved"], list)
        
        # If any suggestions exist, verify structure
        for level in ["auto_apply", "suggest", "unresolved"]:
            if by_confidence[level]:
                suggestion = by_confidence[level][0]
                assert "tx_id" in suggestion
                assert "suggested_type" in suggestion
                assert "confidence" in suggestion
                assert "confidence_level" in suggestion
                assert "reasoning" in suggestion
                break
        
        print("Confidence levels structure verified!")
    
    def test_metrics_accuracy_calculation(self, auth_headers):
        """Test that metrics accuracy is calculated correctly"""
        response = requests.get(
            f"{BASE_URL}/api/custody/classify/metrics",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        metrics = response.json()["metrics"]
        
        # Verify accuracy is between 0 and 1
        accuracy = metrics["suggestion_accuracy"]
        assert 0 <= accuracy <= 1, f"Accuracy {accuracy} out of range"
        
        # Verify accepted + rejected = total
        total = metrics["total_feedback"]
        accepted = metrics["accepted"]
        rejected = metrics["rejected"]
        
        if total > 0:
            assert accepted + rejected == total, "Feedback counts don't add up"
            calculated_accuracy = accepted / total
            # Allow small floating point difference
            assert abs(accuracy - calculated_accuracy) < 0.01, "Accuracy calculation mismatch"
        
        print(f"Metrics accuracy verified: {accuracy}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
