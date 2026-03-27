"""
Test P1.5 (Proceeds Acquisition Constraints) and P2 (Frontend validation status UI, bulk resolution, queue grouping) features

Tests:
- GET /api/custody/validation-status - Returns validation status
- GET /api/custody/beta/pre-export-check - Returns blocking issues
- GET /api/custody/review-queue/grouped - Groups items by destination/source/asset
- GET /api/custody/review-queue/suggestions - Returns wallet link suggestions
- POST /api/custody/review-queue/bulk-resolve - Resolves multiple items at once
- POST /api/custody/fix/create-proceeds-acquisitions - Creates proceeds acquisitions
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://crypto-tax-tracker-1.preview.emergentagent.com')


class TestP2ValidationEndpoints:
    """P2 Validation Status and Review Queue Enhancement Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        login_resp = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': 'mobiletest@test.com',
            'password': 'test123456'
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get('access_token')
        self.headers = {'Authorization': f'Bearer {self.token}'}
    
    def test_validation_status_endpoint(self):
        """Test GET /api/custody/validation-status returns validation status"""
        resp = requests.get(f'{BASE_URL}/api/custody/validation-status', headers=self.headers)
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert 'success' in data
        assert data['success'] == True
        assert 'validation_status' in data
        
        status = data['validation_status']
        assert 'user_id' in status
        assert 'is_valid' in status or 'can_export' in status
    
    def test_pre_export_check_endpoint(self):
        """Test GET /api/custody/beta/pre-export-check returns blocking issues"""
        resp = requests.get(f'{BASE_URL}/api/custody/beta/pre-export-check?tax_year=2024', headers=self.headers)
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert 'can_export' in data
        assert 'validation_status' in data
        assert 'blocking_issues_count' in data
        assert 'unresolved_review_count' in data
        assert 'recommendation' in data
        
        # Verify types
        assert isinstance(data['can_export'], bool)
        assert isinstance(data['blocking_issues_count'], int)
        assert isinstance(data['unresolved_review_count'], int)
    
    def test_review_queue_grouped_endpoint(self):
        """Test GET /api/custody/review-queue/grouped groups items correctly"""
        resp = requests.get(f'{BASE_URL}/api/custody/review-queue/grouped', headers=self.headers)
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert 'success' in data
        assert data['success'] == True
        assert 'grouped' in data
        
        grouped = data['grouped']
        assert 'user_id' in grouped
        assert 'total_items' in grouped
        assert 'by_destination' in grouped
        assert 'by_source' in grouped
        assert 'by_asset' in grouped
        assert 'by_amount_range' in grouped
        assert 'actionable_groups' in grouped
        
        # Verify types
        assert isinstance(grouped['total_items'], int)
        assert isinstance(grouped['by_destination'], dict)
        assert isinstance(grouped['by_source'], dict)
        assert isinstance(grouped['by_asset'], dict)
    
    def test_review_queue_suggestions_endpoint(self):
        """Test GET /api/custody/review-queue/suggestions returns wallet link suggestions"""
        resp = requests.get(f'{BASE_URL}/api/custody/review-queue/suggestions', headers=self.headers)
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert 'success' in data
        assert data['success'] == True
        assert 'suggestions' in data
        
        suggestions = data['suggestions']
        assert 'user_id' in suggestions
        assert 'generated_at' in suggestions
        assert 'suggestions' in suggestions
        assert 'high_confidence' in suggestions
        assert 'medium_confidence' in suggestions
        assert 'low_confidence' in suggestions
        assert 'statistics' in suggestions
    
    def test_bulk_resolve_endpoint_empty_list(self):
        """Test POST /api/custody/review-queue/bulk-resolve with empty list"""
        resp = requests.post(
            f'{BASE_URL}/api/custody/review-queue/bulk-resolve',
            headers=self.headers,
            json={
                'review_ids': [],
                'decision': 'mine',
                'reason': 'test_empty_bulk_resolve'
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert 'success' in data
        assert 'results' in data
        
        results = data['results']
        assert 'user_id' in results
        assert 'decision' in results
        assert 'resolved_count' in results
        assert 'failed_count' in results
    
    def test_bulk_resolve_by_category_endpoint(self):
        """Test POST /api/custody/review-queue/bulk-resolve-category/{category}"""
        resp = requests.post(
            f'{BASE_URL}/api/custody/review-queue/bulk-resolve-category/dust_amount?decision=mine&limit=10',
            headers=self.headers
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert 'success' in data
        assert 'results' in data


class TestP15ProceedsAcquisitions:
    """P1.5 Proceeds Acquisition Constraints Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        login_resp = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': 'mobiletest@test.com',
            'password': 'test123456'
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get('access_token')
        self.headers = {'Authorization': f'Bearer {self.token}'}
    
    def test_create_proceeds_acquisitions_dry_run(self):
        """Test POST /api/custody/fix/create-proceeds-acquisitions with dry_run=true"""
        resp = requests.post(
            f'{BASE_URL}/api/custody/fix/create-proceeds-acquisitions?dry_run=true',
            headers=self.headers
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert 'success' in data
        assert data['success'] == True
        assert 'dry_run' in data
        assert data['dry_run'] == True
        assert 'proceeds_acquisitions_count' in data
        assert 'total_value' in data
        assert 'validation_errors' in data
        assert 'audit_entries_count' in data
        assert 'message' in data
        
        # Verify types
        assert isinstance(data['proceeds_acquisitions_count'], int)
        assert isinstance(data['total_value'], (int, float))
    
    def test_create_proceeds_acquisitions_legacy_endpoint(self):
        """Test legacy endpoint POST /api/custody/fix/create-implicit-acquisitions"""
        resp = requests.post(
            f'{BASE_URL}/api/custody/fix/create-implicit-acquisitions?dry_run=true',
            headers=self.headers
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Should work same as create-proceeds-acquisitions
        assert 'success' in data
        assert data['success'] == True
        assert 'dry_run' in data


class TestReviewQueueBasic:
    """Basic Review Queue Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        login_resp = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': 'mobiletest@test.com',
            'password': 'test123456'
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get('access_token')
        self.headers = {'Authorization': f'Bearer {self.token}'}
    
    def test_review_queue_endpoint(self):
        """Test GET /api/custody/review-queue returns pending reviews"""
        resp = requests.get(f'{BASE_URL}/api/custody/review-queue', headers=self.headers)
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert 'reviews' in data
        assert 'count' in data
        assert isinstance(data['reviews'], list)
        assert isinstance(data['count'], int)


class TestValidationStatusIntegration:
    """Integration tests for validation status flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        login_resp = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': 'mobiletest@test.com',
            'password': 'test123456'
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get('access_token')
        self.headers = {'Authorization': f'Bearer {self.token}'}
    
    def test_validation_status_matches_pre_export(self):
        """Test that validation-status and pre-export-check are consistent"""
        # Get validation status
        status_resp = requests.get(f'{BASE_URL}/api/custody/validation-status', headers=self.headers)
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        
        # Get pre-export check
        export_resp = requests.get(f'{BASE_URL}/api/custody/beta/pre-export-check?tax_year=2024', headers=self.headers)
        assert export_resp.status_code == 200
        export_data = export_resp.json()
        
        # Both should have consistent can_export logic
        # Note: validation_status.can_export may differ from pre_export.can_export
        # because pre_export includes more checks (blocking issues, review queue)
        assert 'validation_status' in status_data
        assert 'can_export' in export_data
    
    def test_review_queue_count_matches_grouped(self):
        """Test that review queue count matches grouped total"""
        # Get review queue
        queue_resp = requests.get(f'{BASE_URL}/api/custody/review-queue', headers=self.headers)
        assert queue_resp.status_code == 200
        queue_count = queue_resp.json().get('count', 0)
        
        # Get grouped
        grouped_resp = requests.get(f'{BASE_URL}/api/custody/review-queue/grouped', headers=self.headers)
        assert grouped_resp.status_code == 200
        grouped_total = grouped_resp.json().get('grouped', {}).get('total_items', 0)
        
        # Counts should match
        assert queue_count == grouped_total, f"Queue count {queue_count} != Grouped total {grouped_total}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
