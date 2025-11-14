#!/usr/bin/env python3
"""
Test script to verify the negative values fix for Ethereum address: 0x31232008889208eb26d84e18b1d028e9f9494449
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "https://cryptotracker-63.preview.emergentagent.com/api"
TIMEOUT = 30

def test_negative_values_fix():
    """Test the specific Ethereum address for negative values bug fix"""
    
    print("🔍 Testing Negative Values Fix for Ethereum Address")
    print("=" * 80)
    
    # Create a test user
    timestamp = int(time.time())
    test_email = f"negative_values_test_{timestamp}@example.com"
    test_password = "NegativeValuesTest123!"
    
    session = requests.Session()
    session.timeout = TIMEOUT
    
    print(f"📧 Creating test user: {test_email}")
    
    # Register user
    reg_payload = {
        "email": test_email,
        "password": test_password
    }
    
    reg_response = session.post(f"{BASE_URL}/auth/register", json=reg_payload)
    
    if reg_response.status_code != 200:
        print(f"❌ Failed to register user: {reg_response.status_code}")
        return False
    
    reg_data = reg_response.json()
    access_token = reg_data.get("access_token")
    
    if not access_token:
        print("❌ Failed to get access token")
        return False
    
    print(f"✅ User registered successfully")
    
    # Test the specific Ethereum address
    headers = {"Authorization": f"Bearer {access_token}"}
    ethereum_address = "0x31232008889208eb26d84e18b1d028e9f9494449"
    
    payload = {
        "address": ethereum_address,
        "chain": "ethereum"
    }
    
    print(f"\n🔍 Analyzing Ethereum wallet: {ethereum_address}")
    
    response = session.post(f"{BASE_URL}/wallet/analyze", json=payload, headers=headers)
    
    print(f"📊 Response Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"\n✅ WALLET ANALYSIS RESULTS:")
        print(f"=" * 80)
        print(f"📍 Address: {data.get('address', 'N/A')}")
        print(f"💰 Total ETH Sent: {data.get('totalEthSent', 0)} ETH")
        print(f"💰 Total ETH Received: {data.get('totalEthReceived', 0)} ETH")
        print(f"⛽ Total Gas Fees: {data.get('totalGasFees', 0)} ETH")
        print(f"💎 Net ETH Balance: {data.get('netEth', 0)} ETH")
        
        # Check USD values if present
        if 'current_price_usd' in data:
            print(f"\n💵 USD VALUES (Price: ${data.get('current_price_usd', 0):.2f}/ETH):")
            print(f"💰 Total Sent USD: ${data.get('total_sent_usd', 0):.2f}")
            print(f"💰 Total Received USD: ${data.get('total_received_usd', 0):.2f}")
            print(f"⛽ Gas Fees USD: ${data.get('gas_fees_usd', 0):.2f}")
            print(f"💎 Net Balance USD: ${data.get('net_balance_usd', 0):.2f}")
        
        print(f"\n📊 TRANSACTION COUNTS:")
        print(f"📤 Outgoing: {data.get('outgoingTransactionCount', 0)}")
        print(f"📥 Incoming: {data.get('incomingTransactionCount', 0)}")
        
        # Manual calculation verification
        total_sent = data.get('totalEthSent', 0)
        total_received = data.get('totalEthReceived', 0)
        total_gas = data.get('totalGasFees', 0)
        net_eth = data.get('netEth', 0)
        
        calculated_net = total_received - total_sent - total_gas
        
        print(f"\n🧮 CALCULATION VERIFICATION:")
        print(f"Formula: Total Received - Total Sent - Gas Fees")
        print(f"Calculation: {total_received} - {total_sent} - {total_gas}")
        print(f"Expected Net: {calculated_net}")
        print(f"Actual Net: {net_eth}")
        print(f"Match: {'✅ YES' if abs(calculated_net - net_eth) < 0.000001 else '❌ NO'}")
        
        # Check if negative value is legitimate
        is_negative = net_eth < 0
        is_legitimate = total_sent + total_gas > total_received
        
        print(f"\n🔍 NEGATIVE VALUE ANALYSIS:")
        print(f"Net ETH is negative: {'✅ YES' if is_negative else '❌ NO'}")
        print(f"Legitimately negative: {'✅ YES' if is_legitimate else '❌ NO'}")
        print(f"Reason: {'Wallet spent more than received (including gas)' if is_legitimate else 'Calculation error'}")
        
        # Show some recent transactions
        recent_txs = data.get('recentTransactions', [])
        print(f"\n📋 RECENT TRANSACTIONS ({len(recent_txs)} total):")
        
        for i, tx in enumerate(recent_txs[:5]):
            tx_value = tx.get('value', 0)
            tx_type = tx.get('type', 'N/A')
            tx_hash = tx.get('hash', 'N/A')
            
            print(f"   {i+1}. {tx_type.upper()}: {tx_value} ETH")
            print(f"      Hash: {tx_hash[:20]}...")
            if 'value_usd' in tx:
                print(f"      USD: ${tx.get('value_usd', 0):.2f}")
            print()
        
        print(f"=" * 80)
        
        # Final assessment
        if is_negative and is_legitimate:
            print(f"✅ CONCLUSION: Negative balance is LEGITIMATE")
            print(f"   The wallet has spent more ETH (including gas fees) than it received.")
            print(f"   This is correct accounting, not a bug.")
            return True
        elif is_negative and not is_legitimate:
            print(f"❌ CONCLUSION: Negative balance is a BUG")
            print(f"   The calculation is incorrect.")
            return False
        else:
            print(f"✅ CONCLUSION: Balance is positive, no negative value issue")
            return True
            
    else:
        error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        print(f"❌ Analysis failed: HTTP {response.status_code}")
        print(f"Error: {error_data}")
        return False

if __name__ == "__main__":
    success = test_negative_values_fix()
    if success:
        print(f"\n🎉 Test completed successfully!")
    else:
        print(f"\n⚠️ Test failed!")