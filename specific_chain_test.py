#!/usr/bin/env python3
"""
Specific Chain Analysis Test for ShoeString Wallet Tracker
Tests the specific wallet addresses and chains mentioned in the review request
"""

import requests
import json
import time
from datetime import datetime
import sys

# Configuration
BASE_URL = "https://tax-analysis-phase2.preview.emergentagent.com/api"
TIMEOUT = 30

class SpecificChainTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = TIMEOUT
        self.access_token = None
        self.user_data = None
        self.test_results = []
        
        # Generate unique test email with timestamp
        timestamp = int(time.time())
        self.test_email = f"chain_test_{timestamp}@example.com"
        self.test_password = "ChainTest123!"
        
    def log_result(self, test_name, success, details, response_data=None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "response_data": response_data
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        if response_data and not success:
            print(f"   Response: {json.dumps(response_data, indent=2)}")
    
    def setup_user(self):
        """Register and login user"""
        try:
            # Register
            payload = {
                "email": self.test_email,
                "password": self.test_password
            }
            
            response = self.session.post(f"{BASE_URL}/auth/register", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.user_data = data.get("user")
                
                self.log_result("User Setup", True, 
                              f"User registered successfully. ID: {self.user_data['id']}, Tier: {self.user_data['subscription_tier']}")
                return True
            else:
                self.log_result("User Setup", False, f"HTTP {response.status_code}", response.json())
                return False
                
        except Exception as e:
            self.log_result("User Setup", False, f"Error: {str(e)}")
            return False
    
    def test_ethereum_wallet(self):
        """Test Ethereum wallet: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"""
        if not self.access_token:
            self.log_result("Ethereum Wallet Test", False, "No access token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            payload = {
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
                "chain": "ethereum"
            }
            
            response = self.session.post(f"{BASE_URL}/wallet/analyze", json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.log_result("Ethereum Wallet Test", True, 
                              f"✅ SUCCESS - ETH analysis working. Received: {data['totalEthReceived']} ETH, Sent: {data['totalEthSent']} ETH, Net: {data['netEth']} ETH, Transactions: {data['incomingTransactionCount']} in, {data['outgoingTransactionCount']} out")
                return True
            else:
                self.log_result("Ethereum Wallet Test", False, 
                              f"❌ FAILED - HTTP {response.status_code}", response.json())
                return False
                
        except Exception as e:
            self.log_result("Ethereum Wallet Test", False, f"❌ ERROR - {str(e)}")
            return False
    
    def test_bitcoin_wallet_free_tier(self):
        """Test Bitcoin wallet with free tier (should be restricted)"""
        if not self.access_token:
            self.log_result("Bitcoin Wallet Test (Free Tier)", False, "No access token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            payload = {
                "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "chain": "bitcoin"
            }
            
            response = self.session.post(f"{BASE_URL}/wallet/analyze", json=payload, headers=headers)
            
            if response.status_code == 403:
                error_data = response.json()
                if "Multi-chain analysis is a Premium feature" in error_data.get("detail", ""):
                    self.log_result("Bitcoin Wallet Test (Free Tier)", True, 
                                  "✅ CORRECT - Bitcoin analysis properly restricted for free tier")
                    return True
                else:
                    self.log_result("Bitcoin Wallet Test (Free Tier)", False, 
                                  f"❌ WRONG ERROR - Unexpected 403 message: {error_data}")
                    return False
            elif response.status_code == 429:
                # Daily limit reached
                self.log_result("Bitcoin Wallet Test (Free Tier)", True, 
                              "✅ CORRECT - Bitcoin analysis blocked by daily limit (expected)")
                return True
            elif response.status_code == 200:
                self.log_result("Bitcoin Wallet Test (Free Tier)", False, 
                              "❌ SECURITY ISSUE - Bitcoin analysis should be restricted for free tier")
                return False
            else:
                self.log_result("Bitcoin Wallet Test (Free Tier)", False, 
                              f"❌ UNEXPECTED - HTTP {response.status_code}", response.json())
                return False
                
        except Exception as e:
            self.log_result("Bitcoin Wallet Test (Free Tier)", False, f"❌ ERROR - {str(e)}")
            return False
    
    def test_polygon_wallet_free_tier(self):
        """Test Polygon wallet with free tier (should be restricted)"""
        if not self.access_token:
            self.log_result("Polygon Wallet Test (Free Tier)", False, "No access token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            payload = {
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
                "chain": "polygon"
            }
            
            response = self.session.post(f"{BASE_URL}/wallet/analyze", json=payload, headers=headers)
            
            if response.status_code == 403:
                error_data = response.json()
                if "Multi-chain analysis is a Premium feature" in error_data.get("detail", ""):
                    self.log_result("Polygon Wallet Test (Free Tier)", True, 
                                  "✅ CORRECT - Polygon analysis properly restricted for free tier")
                    return True
                else:
                    self.log_result("Polygon Wallet Test (Free Tier)", False, 
                                  f"❌ WRONG ERROR - Unexpected 403 message: {error_data}")
                    return False
            elif response.status_code == 429:
                # Daily limit reached
                self.log_result("Polygon Wallet Test (Free Tier)", True, 
                              "✅ CORRECT - Polygon analysis blocked by daily limit (expected)")
                return True
            elif response.status_code == 200:
                self.log_result("Polygon Wallet Test (Free Tier)", False, 
                              "❌ SECURITY ISSUE - Polygon analysis should be restricted for free tier")
                return False
            else:
                self.log_result("Polygon Wallet Test (Free Tier)", False, 
                              f"❌ UNEXPECTED - HTTP {response.status_code}", response.json())
                return False
                
        except Exception as e:
            self.log_result("Polygon Wallet Test (Free Tier)", False, f"❌ ERROR - {str(e)}")
            return False
    
    def test_chain_request_endpoint(self):
        """Test chain request endpoint for Pro users"""
        if not self.access_token:
            self.log_result("Chain Request Endpoint Test", False, "No access token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            payload = {
                "chain_name": "Avalanche",
                "reason": "Testing chain request functionality"
            }
            
            response = self.session.post(f"{BASE_URL}/chain-request", json=payload, headers=headers)
            
            if response.status_code == 403:
                error_data = response.json()
                if "Chain requests are only available for premium subscribers" in error_data.get("detail", ""):
                    self.log_result("Chain Request Endpoint Test", True, 
                                  "✅ CORRECT - Chain request properly restricted for free tier")
                    return True
                else:
                    self.log_result("Chain Request Endpoint Test", False, 
                                  f"❌ WRONG ERROR - Unexpected 403 message: {error_data}")
                    return False
            elif response.status_code == 200:
                data = response.json()
                if "request_id" in data:
                    self.log_result("Chain Request Endpoint Test", True, 
                                  f"✅ SUCCESS - Chain request created with ID: {data['request_id']}")
                    return True
                else:
                    self.log_result("Chain Request Endpoint Test", False, 
                                  f"❌ INVALID RESPONSE - Missing request_id: {data}")
                    return False
            else:
                self.log_result("Chain Request Endpoint Test", False, 
                              f"❌ UNEXPECTED - HTTP {response.status_code}", response.json())
                return False
                
        except Exception as e:
            self.log_result("Chain Request Endpoint Test", False, f"❌ ERROR - {str(e)}")
            return False
    
    def test_downgrade_endpoint(self):
        """Test downgrade endpoint"""
        if not self.access_token:
            self.log_result("Downgrade Endpoint Test", False, "No access token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # First check current tier
            user_response = self.session.get(f"{BASE_URL}/auth/me", headers=headers)
            if user_response.status_code != 200:
                self.log_result("Downgrade Endpoint Test", False, "Failed to get user info")
                return False
            
            user_data = user_response.json()
            current_tier = user_data.get('subscription_tier', 'free')
            
            # Test downgrade from free tier (should fail)
            payload = {"new_tier": "free"}
            response = self.session.post(f"{BASE_URL}/auth/downgrade", json=payload, headers=headers)
            
            if response.status_code == 400:
                error_data = response.json()
                if "Cannot downgrade from current tier" in error_data.get("detail", ""):
                    self.log_result("Downgrade Endpoint Test", True, 
                                  f"✅ CORRECT - Downgrade properly prevented for {current_tier} tier")
                    return True
                else:
                    self.log_result("Downgrade Endpoint Test", False, 
                                  f"❌ WRONG ERROR - Unexpected error message: {error_data}")
                    return False
            else:
                self.log_result("Downgrade Endpoint Test", False, 
                              f"❌ UNEXPECTED - Expected 400, got HTTP {response.status_code}", response.json())
                return False
                
        except Exception as e:
            self.log_result("Downgrade Endpoint Test", False, f"❌ ERROR - {str(e)}")
            return False
    
    def run_specific_tests(self):
        """Run the specific tests requested in the review"""
        print(f"🔍 Running Specific Chain Tests for ShoeString Wallet Tracker")
        print(f"📍 Testing URL: {BASE_URL}")
        print(f"📧 Test Email: {self.test_email}")
        print("=" * 80)
        
        # Setup user first
        if not self.setup_user():
            print("❌ Failed to setup user, aborting tests")
            return 0, 6, self.test_results
        
        # Test sequence based on review request
        tests = [
            ("Ethereum Wallet Analysis", self.test_ethereum_wallet),
            ("Bitcoin Wallet (Free Tier)", self.test_bitcoin_wallet_free_tier),
            ("Polygon Wallet (Free Tier)", self.test_polygon_wallet_free_tier),
            ("Chain Request Endpoint", self.test_chain_request_endpoint),
            ("Downgrade Endpoint", self.test_downgrade_endpoint),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n🧪 Running: {test_name}")
            try:
                if test_func():
                    passed += 1
            except Exception as e:
                self.log_result(test_name, False, f"Test execution error: {str(e)}")
        
        print("\n" + "=" * 80)
        print(f"📊 Specific Test Results: {passed}/{total} tests passed")
        
        # Summary of critical issues
        failed_tests = [result for result in self.test_results if not result["success"]]
        if failed_tests:
            print("\n❌ Failed Tests:")
            for result in failed_tests:
                print(f"   • {result['test']}: {result['details']}")
        
        print(f"\n✅ Successful Tests: {passed}")
        print(f"❌ Failed Tests: {len(failed_tests)}")
        
        return passed, total, self.test_results

def main():
    """Main test execution"""
    tester = SpecificChainTester()
    passed, total, results = tester.run_specific_tests()
    
    # Return exit code based on results
    if passed == total:
        print("\n🎉 All specific tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} specific tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())