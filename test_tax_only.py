#!/usr/bin/env python3
"""
Test only the Tax Calculations Phase 2 functionality
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "https://tax-analysis-phase2.preview.emergentagent.com/api"
TIMEOUT = 30

def test_tax_calculations_phase2():
    """Test Phase 2 Tax Calculations with address: 0x31232008889208eb26d84e18b1d028e9f9494449"""
    session = requests.Session()
    session.timeout = TIMEOUT
    
    try:
        # Create a new premium user for testing tax calculations
        timestamp = int(time.time())
        premium_email = f"tax_premium_test_{timestamp}@example.com"
        premium_password = "TaxPremiumTest123!"
        
        print(f"🔑 Creating Premium User for Tax Calculations Testing:")
        print(f"   Email: {premium_email}")
        print(f"   Password: {premium_password}")
        
        # Register premium user
        payload = {
            "email": premium_email,
            "password": premium_password
        }
        
        response = session.post(f"{BASE_URL}/auth/register", json=payload)
        if response.status_code != 200:
            print(f"❌ Failed to register premium user: {response.status_code}")
            return False
        
        premium_data = response.json()
        premium_token = premium_data.get("access_token")
        premium_user_id = premium_data.get("user", {}).get("id")
        
        if not premium_token or not premium_user_id:
            print(f"❌ Failed to get premium user token or ID")
            return False
        
        print(f"✅ Premium User Created Successfully:")
        print(f"   User ID: {premium_user_id}")
        print(f"   Token: {premium_token[:20]}...")
        
        headers = {"Authorization": f"Bearer {premium_token}"}
        
        # Test the specific Ethereum address for tax calculations
        ethereum_address = "0x31232008889208eb26d84e18b1d028e9f9494449"
        ethereum_payload = {
            "address": ethereum_address,
            "chain": "ethereum"
        }
        
        print(f"\n🧮 Analyzing Ethereum Wallet for Tax Calculations:")
        print(f"   Address: {ethereum_address}")
        print(f"   Chain: ethereum")
        
        ethereum_response = session.post(f"{BASE_URL}/wallet/analyze", json=ethereum_payload, headers=headers)
        
        print(f"\n📊 Analysis Response:")
        print(f"   Status Code: {ethereum_response.status_code}")
        
        if ethereum_response.status_code == 200:
            data = ethereum_response.json()
            
            print(f"\n✅ ETHEREUM WALLET ANALYSIS SUCCESSFUL!")
            print(f"=" * 80)
            print(f"📍 Wallet Address: {data.get('address', 'N/A')}")
            print(f"💰 Total ETH Sent: {data.get('totalEthSent', 0)} ETH")
            print(f"💰 Total ETH Received: {data.get('totalEthReceived', 0)} ETH")
            print(f"⛽ Total Gas Fees: {data.get('totalGasFees', 0)} ETH")
            print(f"💎 Net ETH Balance: {data.get('netEth', 0)} ETH")
            print(f"📤 Outgoing Transactions: {data.get('outgoingTransactionCount', 0)}")
            print(f"📥 Incoming Transactions: {data.get('incomingTransactionCount', 0)}")
            
            # TAX CALCULATIONS VERIFICATION - THIS IS THE KEY PART
            print(f"\n🧮 TAX CALCULATIONS PHASE 2 VERIFICATION:")
            print(f"=" * 80)
            
            # Check for tax_data object
            tax_data = data.get('tax_data')
            
            if tax_data is None:
                print(f"❌ tax_data object missing from response")
                print(f"   This could mean:")
                print(f"   1. User tier is not Premium/Pro (current tier: {data.get('subscription_tier', 'unknown')})")
                print(f"   2. Tax calculations not implemented")
                print(f"   3. Tax calculations failed silently")
                return False
            
            print(f"✅ tax_data object found in response")
            
            # Show tax data structure
            print(f"\n📊 TAX DATA STRUCTURE:")
            print(f"   Method: {tax_data.get('method', 'N/A')}")
            
            # Check realized gains
            realized_gains = tax_data.get('realized_gains', [])
            print(f"   Realized Gains: {len(realized_gains)} transactions")
            
            # Check unrealized gains
            unrealized_gains = tax_data.get('unrealized_gains', {})
            print(f"   Unrealized Gains Lots: {len(unrealized_gains.get('lots', []))}")
            print(f"   Total Unrealized Gain: ${unrealized_gains.get('total_gain', 0)}")
            
            # Check summary
            summary = tax_data.get('summary', {})
            print(f"   Total Realized Gain: ${summary.get('total_realized_gain', 0)}")
            print(f"   Total Unrealized Gain: ${summary.get('total_unrealized_gain', 0)}")
            print(f"   Total Gain: ${summary.get('total_gain', 0)}")
            print(f"   Short-term Gains: ${summary.get('short_term_gains', 0)}")
            print(f"   Long-term Gains: ${summary.get('long_term_gains', 0)}")
            
            # Verification checks
            all_checks_passed = True
            
            # 1. Check for realized_gains array
            if not isinstance(realized_gains, list):
                print(f"❌ realized_gains is not an array")
                all_checks_passed = False
            else:
                print(f"✅ realized_gains array present ({len(realized_gains)} items)")
            
            # 2. Check for unrealized_gains object
            if not isinstance(unrealized_gains, dict):
                print(f"❌ unrealized_gains is not an object")
                all_checks_passed = False
            else:
                print(f"✅ unrealized_gains object present")
            
            # 3. Check for summary with total gains
            if not isinstance(summary, dict) or 'total_gain' not in summary:
                print(f"❌ summary missing or no total_gain")
                all_checks_passed = False
            else:
                print(f"✅ summary with total gains present")
            
            # 4. Check for short_term vs long_term gains
            if 'short_term_gains' not in summary or 'long_term_gains' not in summary:
                print(f"❌ short_term vs long_term gains missing")
                all_checks_passed = False
            else:
                print(f"✅ short_term vs long_term gains present")
            
            # 5. Check for cost basis calculations
            cost_basis_found = False
            if realized_gains:
                for gain in realized_gains:
                    if 'cost_basis' in gain:
                        cost_basis_found = True
                        break
            
            if unrealized_gains and 'total_cost_basis' in unrealized_gains:
                cost_basis_found = True
            
            if cost_basis_found:
                print(f"✅ cost basis calculations present")
            else:
                print(f"❌ cost basis calculations missing")
                all_checks_passed = False
            
            print(f"\n🎯 FINAL ASSESSMENT:")
            print(f"=" * 80)
            
            if all_checks_passed:
                print(f"✅ TAX CALCULATIONS PHASE 2 WORKING CORRECTLY!")
                print(f"   All required fields present and properly structured")
                return True
            else:
                print(f"❌ TAX CALCULATIONS PHASE 2 HAS ISSUES!")
                print(f"   Some required fields missing or improperly structured")
                return False
                
        else:
            error_data = ethereum_response.json() if ethereum_response.headers.get('content-type', '').startswith('application/json') else ethereum_response.text
            print(f"\n❌ Analysis failed: HTTP {ethereum_response.status_code}")
            print(f"   Error: {error_data}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        return False

if __name__ == "__main__":
    print(f"🧮 Testing Tax Calculations Phase 2")
    print(f"📍 Testing URL: {BASE_URL}")
    print("=" * 80)
    
    success = test_tax_calculations_phase2()
    
    if success:
        print(f"\n✅ TAX CALCULATIONS PHASE 2 TEST PASSED!")
    else:
        print(f"\n❌ TAX CALCULATIONS PHASE 2 TEST FAILED!")