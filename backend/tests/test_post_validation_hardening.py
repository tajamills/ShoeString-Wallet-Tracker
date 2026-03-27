"""
Post-Validation Hardening Features Test Suite

Tests for:
1. Regression fixture system for validated accounts
2. Pre-export summary metadata
3. Modular refactor of custody.py into separate route files
4. Recompute integrity enforcement
5. Export safety guard
6. Audit trail completeness
"""

import pytest
import requests
import os
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "mobiletest@test.com"
TEST_PASSWORD = "test123456"

# Known fixture ID from main agent
KNOWN_FIXTURE_ID = "d878078e-1101-4f32-bbbf-cff04f2b1a28"


class TestAuthentication:
    """Authentication tests - run first to get token"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    def test_login_success(self, auth_token):
        """Test login returns valid token"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✓ Login successful, token length: {len(auth_token)}")


class TestRegressionFixtureSystem:
    """Tests for regression fixture creation and testing"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_list_regression_fixtures(self, headers):
        """Test GET /api/custody/regression/fixtures - lists all fixtures"""
        response = requests.get(
            f"{BASE_URL}/api/custody/regression/fixtures",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "fixtures" in data
        print(f"✓ Listed {len(data['fixtures'])} fixtures")
        
        # Check if known fixture exists
        fixture_ids = [f.get("fixture_id") for f in data["fixtures"]]
        if KNOWN_FIXTURE_ID in fixture_ids:
            print(f"✓ Known fixture {KNOWN_FIXTURE_ID} found")
    
    def test_create_regression_fixture(self, headers):
        """Test POST /api/custody/regression/create-fixture - creates snapshot with version tag"""
        response = requests.post(
            f"{BASE_URL}/api/custody/regression/create-fixture",
            headers=headers,
            json={
                "version_tag": f"test_fixture_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "description": "Test fixture created by automated testing"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "fixture" in data
        
        fixture = data["fixture"]
        assert "fixture_id" in fixture
        assert "version_tag" in fixture
        assert "user_id" in fixture
        assert "created_at" in fixture
        assert "disposal_count" in fixture
        assert "total_proceeds" in fixture
        assert "total_cost_basis" in fixture
        assert "total_gain_loss" in fixture
        assert "validation_status" in fixture
        assert "can_export" in fixture
        
        print(f"✓ Created fixture: {fixture['fixture_id']}")
        print(f"  - Version tag: {fixture['version_tag']}")
        print(f"  - Disposal count: {fixture['disposal_count']}")
        print(f"  - Total proceeds: ${fixture['total_proceeds']:.2f}")
        print(f"  - Validation status: {fixture['validation_status']}")
        print(f"  - Can export: {fixture['can_export']}")
    
    def test_run_regression_test_with_known_fixture(self, headers):
        """Test POST /api/custody/regression/run-test/{fixture_id} - runs regression test"""
        response = requests.post(
            f"{BASE_URL}/api/custody/regression/run-test/{KNOWN_FIXTURE_ID}",
            headers=headers,
            params={"recompute": "false"}  # Skip recompute for faster test
        )
        
        if response.status_code == 404:
            pytest.skip(f"Known fixture {KNOWN_FIXTURE_ID} not found - may have been deleted")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "passed" in data
        assert "result" in data
        
        result = data["result"]
        assert "fixture_id" in result
        assert "version_tag" in result
        assert "test_timestamp" in result
        assert "disposal_count_match" in result
        assert "proceeds_match" in result
        assert "cost_basis_match" in result
        assert "gain_loss_match" in result
        assert "validation_status_match" in result
        assert "can_export_match" in result
        
        print(f"✓ Regression test result: {'PASSED' if data['passed'] else 'FAILED'}")
        print(f"  - Disposal count match: {result['disposal_count_match']}")
        print(f"  - Proceeds match: {result['proceeds_match']}")
        print(f"  - Cost basis match: {result['cost_basis_match']}")
        print(f"  - Gain/loss match: {result['gain_loss_match']}")
        print(f"  - Validation status match: {result['validation_status_match']}")
        print(f"  - Can export match: {result['can_export_match']}")
        
        if result.get("mismatches"):
            print(f"  - Mismatches: {result['mismatches']}")
    
    def test_run_regression_test_invalid_fixture(self, headers):
        """Test regression test with invalid fixture ID returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/custody/regression/run-test/invalid-fixture-id-12345",
            headers=headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid fixture ID correctly returns 404")


class TestPreExportSummary:
    """Tests for pre-export summary metadata"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_pre_export_check(self, headers):
        """Test GET /api/custody/beta/pre-export-check - returns comprehensive summary"""
        response = requests.get(
            f"{BASE_URL}/api/custody/beta/pre-export-check",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check required fields - the response structure is different from modular routes
        assert "can_export" in data
        assert "validation_status" in data
        assert "blocking_issues_count" in data
        
        print(f"✓ Pre-export check completed")
        print(f"  - Validation status: {data['validation_status']}")
        print(f"  - Can export: {data['can_export']}")
        print(f"  - Blocking issues count: {data['blocking_issues_count']}")
        
        if "unresolved_review_count" in data:
            print(f"  - Unresolved review count: {data['unresolved_review_count']}")
        
        if "export_blocked_reason" in data:
            print(f"  - Export blocked reason: {data['export_blocked_reason']}")
    
    def test_validation_status_endpoint(self, headers):
        """Test GET /api/custody/validation-status - lightweight check"""
        response = requests.get(
            f"{BASE_URL}/api/custody/validation-status",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        # Check for validation_status in nested structure
        assert "validation_status" in data
        
        # The validation_status might be nested
        if isinstance(data["validation_status"], dict):
            vs = data["validation_status"]
            print(f"✓ Validation status: is_valid={vs.get('is_valid')}, can_export={vs.get('can_export')}")
        else:
            print(f"✓ Validation status: {data['validation_status']}")


class TestExportSafetyGuard:
    """Tests for export safety guard - blocks export if validation fails"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_export_form_8949_json(self, headers):
        """Test GET /api/custody/export-form-8949 - returns JSON with safety guard"""
        # Use tax_year parameter as it's required
        response = requests.get(
            f"{BASE_URL}/api/custody/export-form-8949",
            headers=headers,
            params={"format": "json", "tax_year": 2024}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check if export was blocked or allowed
        # The response has "can_export" field to indicate if export is allowed
        if data.get("can_export") == False:
            # Export blocked - check error structure
            assert "error" in data or "blocked_reason" in data
            print(f"✓ Export blocked (as expected if validation fails)")
            print(f"  - Validation status: {data.get('validation_status', 'N/A')}")
            print(f"  - Blocked reason: {data.get('blocked_reason', 'N/A')}")
            print(f"  - Critical issues: {data.get('critical_issues', 0)}")
            print(f"  - High issues: {data.get('high_issues', 0)}")
        else:
            # Export allowed
            assert data.get("success") == True
            print(f"✓ Export allowed")
            if "data" in data:
                print(f"  - Data rows: {len(data.get('data', []))}")
    
    def test_export_form_8949_with_force(self, headers):
        """Test export with force=true bypasses validation"""
        response = requests.get(
            f"{BASE_URL}/api/custody/export-form-8949",
            headers=headers,
            params={"format": "csv", "force": "true", "tax_year": 2024}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # With force=true, it returns CSV format
        content_type = response.headers.get("content-type", "")
        
        # Check if it's CSV or JSON
        if "text/csv" in content_type or response.text.startswith("Description"):
            # CSV response - export succeeded
            print(f"✓ Forced export successful (CSV format)")
            lines = response.text.strip().split('\n')
            print(f"  - CSV rows: {len(lines)}")
        else:
            # JSON response
            data = response.json()
            assert data.get("success") == True
            print(f"✓ Forced export successful (JSON format)")
            if "data" in data:
                print(f"  - Data rows: {len(data.get('data', []))}")


class TestRecomputeIntegrity:
    """Tests for recompute integrity enforcement"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_trigger_recompute(self, headers):
        """Test POST /api/custody/validate/recompute - triggers full recompute"""
        response = requests.post(
            f"{BASE_URL}/api/custody/validate/recompute",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        # Check for result field (legacy format) or recompute field (new format)
        if "recompute" in data:
            recompute = data["recompute"]
            print(f"✓ Recompute triggered successfully (new format)")
            print(f"  - Recompute ID: {recompute.get('recompute_id', 'N/A')}")
            print(f"  - Trigger: {recompute.get('trigger', 'N/A')}")
            print(f"  - Status: {recompute.get('status', 'N/A')}")
            print(f"  - Lots created: {recompute.get('lots_created', 'N/A')}")
            print(f"  - Disposals created: {recompute.get('disposals_created', 'N/A')}")
        elif "result" in data:
            result = data["result"]
            print(f"✓ Recompute triggered successfully (legacy format)")
            print(f"  - Recompute triggered: {result.get('recompute_triggered', 'N/A')}")
            print(f"  - Reason: {result.get('reason', 'N/A')}")
            print(f"  - Cleared lots: {result.get('cleared_lots', 'N/A')}")
            print(f"  - Cleared disposals: {result.get('cleared_disposals', 'N/A')}")
        else:
            print(f"✓ Recompute triggered: {data.get('message', 'N/A')}")


class TestAuditTrail:
    """Tests for audit trail completeness"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_get_audit_trail(self, headers):
        """Test GET /api/custody/validate/audit-trail - returns audit entries"""
        response = requests.get(
            f"{BASE_URL}/api/custody/validate/audit-trail",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        # Check for entries in different formats
        entries_count = data.get("count") or data.get("entries_count", 0)
        entries = data.get("entries") or data.get("audit_trail", [])
        
        print(f"✓ Audit trail retrieved: {entries_count} entries")
        
        # Check entry structure if entries exist
        if entries:
            entry = entries[0]
            assert "action" in entry or "audit_id" in entry
            assert "timestamp" in entry
            
            # Print recent entries
            for i, e in enumerate(entries[:5]):
                print(f"  - [{e.get('timestamp', 'N/A')}] {e.get('action', 'N/A')}")
    
    def test_get_audit_trail_filtered(self, headers):
        """Test audit trail with action filter"""
        response = requests.get(
            f"{BASE_URL}/api/custody/validate/audit-trail",
            headers=headers,
            params={"action": "full_recompute", "limit": 10}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        entries_count = data.get("count") or data.get("entries_count", 0)
        print(f"✓ Filtered audit trail (full_recompute): {entries_count} entries")


class TestModularRoutes:
    """Tests for modular route files - ensure all routes work correctly"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    # === Review Queue Routes ===
    def test_review_queue_routes_get_queue(self, headers):
        """Test review_queue_routes: GET /api/custody/review-queue"""
        response = requests.get(
            f"{BASE_URL}/api/custody/review-queue",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Check for items or reviews field
        assert "items" in data or "reviews" in data or "count" in data
        count = data.get("count", len(data.get("items", data.get("reviews", []))))
        print(f"✓ Review queue: {count} items")
    
    def test_review_queue_routes_grouped(self, headers):
        """Test review_queue_routes: GET /api/custody/review-queue/grouped"""
        response = requests.get(
            f"{BASE_URL}/api/custody/review-queue/grouped",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Grouped review queue retrieved")
    
    # === Validation Routes ===
    def test_validation_routes_account_status(self, headers):
        """Test validation_routes: GET /api/custody/validate/account-status"""
        response = requests.get(
            f"{BASE_URL}/api/custody/validate/account-status",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Check for status or account_tax_state_valid
        assert "status" in data or "account_tax_state_valid" in data or "success" in data
        print(f"✓ Account validation status retrieved")
    
    def test_validation_routes_beta_validate(self, headers):
        """Test validation_routes: POST /api/custody/beta/validate"""
        response = requests.post(
            f"{BASE_URL}/api/custody/beta/validate",
            headers=headers,
            json={}  # Empty body
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "report" in data
        print(f"✓ Beta validation completed")
    
    # === Proceeds Routes ===
    def test_proceeds_routes_preview(self, headers):
        """Test proceeds_routes: GET /api/custody/proceeds/preview"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/preview",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Proceeds preview retrieved")
    
    def test_proceeds_routes_staged_stages(self, headers):
        """Test proceeds_routes: GET /api/custody/proceeds/staged/stages"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/staged/stages",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "stages" in data
        print(f"✓ Staged application stages retrieved")
    
    def test_proceeds_routes_rollback_batches(self, headers):
        """Test proceeds_routes: GET /api/custody/proceeds/rollback-batches"""
        response = requests.get(
            f"{BASE_URL}/api/custody/proceeds/rollback-batches",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "batches" in data
        print(f"✓ Rollback batches: {len(data['batches'])} batches")
    
    # === Price Backfill Routes ===
    def test_price_backfill_routes_preview(self, headers):
        """Test price_backfill_routes: GET /api/custody/price-backfill/preview"""
        response = requests.get(
            f"{BASE_URL}/api/custody/price-backfill/preview",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Price backfill preview retrieved")
    
    def test_price_backfill_routes_batches(self, headers):
        """Test price_backfill_routes: GET /api/custody/price-backfill/batches"""
        response = requests.get(
            f"{BASE_URL}/api/custody/price-backfill/batches",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "batches" in data
        print(f"✓ Price backfill batches: {len(data['batches'])} batches")
    
    # === Custody Core Routes ===
    def test_custody_core_routes_linkages(self, headers):
        """Test custody_core_routes: GET /api/custody/linkages"""
        response = requests.get(
            f"{BASE_URL}/api/custody/linkages",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Check for linkages field
        assert "linkages" in data
        count = data.get("count", len(data.get("linkages", [])))
        print(f"✓ Wallet linkages: {count} linkages")
    
    def test_custody_core_routes_clusters(self, headers):
        """Test custody_core_routes: GET /api/custody/clusters"""
        response = requests.get(
            f"{BASE_URL}/api/custody/clusters",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Check for clusters field
        assert "clusters" in data
        count = data.get("count", len(data.get("clusters", [])))
        print(f"✓ Wallet clusters: {count} clusters")
    
    def test_custody_core_routes_tax_lots(self, headers):
        """Test custody_core_routes: GET /api/custody/tax-lots"""
        response = requests.get(
            f"{BASE_URL}/api/custody/tax-lots",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "lots" in data
        print(f"✓ Tax lots: {data.get('count', 0)} lots")
    
    def test_custody_core_routes_tax_lot_balances(self, headers):
        """Test custody_core_routes: GET /api/custody/tax-lots/balances"""
        response = requests.get(
            f"{BASE_URL}/api/custody/tax-lots/balances",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "balances" in data
        print(f"✓ Tax lot balances: {len(data['balances'])} assets")
    
    def test_custody_core_routes_tax_events(self, headers):
        """Test custody_core_routes: GET /api/custody/tax-events"""
        response = requests.get(
            f"{BASE_URL}/api/custody/tax-events",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Check for tax_events field
        assert "tax_events" in data or "events" in data
        count = data.get("count", len(data.get("tax_events", data.get("events", []))))
        print(f"✓ Tax events: {count} events")
    
    def test_custody_core_routes_known_addresses(self, headers):
        """Test custody_core_routes: GET /api/custody/known-addresses"""
        response = requests.get(
            f"{BASE_URL}/api/custody/known-addresses",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Check for exchanges and dexes fields
        assert "exchanges" in data
        assert "dexes" in data
        print(f"✓ Known addresses retrieved")


class TestValidationInvariants:
    """Tests for validation invariants and lot status"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_validate_invariants(self, headers):
        """Test POST /api/custody/validate/invariants"""
        response = requests.post(
            f"{BASE_URL}/api/custody/validate/invariants",
            headers=headers,
            json={}  # Empty body
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        # Check for status field (legacy format) or invariants field (new format)
        if "invariants" in data:
            print(f"✓ Invariant check completed (new format)")
        else:
            print(f"✓ Invariant check completed")
            print(f"  - Status: {data.get('status', 'N/A')}")
            print(f"  - Can export taxes: {data.get('can_export_taxes', 'N/A')}")
            print(f"  - Violations count: {data.get('violations_count', 0)}")
    
    def test_lot_status_for_asset(self, headers):
        """Test GET /api/custody/validate/lot-status/{asset}"""
        # Test with USDC which should have lots
        response = requests.get(
            f"{BASE_URL}/api/custody/validate/lot-status/USDC",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "asset" in data
        
        # Check for lot_status nested structure or direct fields
        if "lot_status" in data:
            lot_status = data["lot_status"]
            print(f"✓ Lot status for USDC:")
            print(f"  - Total quantity: {lot_status.get('total_quantity', 0)}")
            print(f"  - Total cost basis: ${lot_status.get('total_cost_basis', 0):.2f}")
        else:
            print(f"✓ Lot status for USDC:")
            print(f"  - Lot count: {data.get('lot_count', 0)}")
            print(f"  - Total remaining: {data.get('total_remaining', 0)}")
            print(f"  - Total cost basis: ${data.get('total_cost_basis', 0):.2f}")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
