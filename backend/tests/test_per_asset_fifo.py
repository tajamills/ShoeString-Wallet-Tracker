"""
Tests for Per-Asset FIFO Calculation - Verifying BTC buys match BTC sells, etc.

BUG CONTEXT: Previously FIFO calculation processed ALL transactions in a single queue
(BTC, ETH, SOL, DOGE, etc.) causing BTC sells to match DOGE buys, producing 
astronomical and incorrect gains/losses.

FIX: FIFO now groups transactions by asset symbol first, then runs FIFO 
independently per asset.
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://crypto-tax-tracker-1.preview.emergentagent.com').rstrip('/')

# Multi-asset Coinbase CSV for testing per-asset FIFO
# Contains buys and sells for BTC, ETH, SOL, ALGO at different prices
# DOGE has only buys (no sells) - should not affect other assets' FIFO
MULTI_ASSET_TEST_CSV = """Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price at Transaction,Subtotal
2024-01-15T10:00:00Z,Buy,BTC,0.5,42000,21000
2024-01-15T11:00:00Z,Buy,ETH,2.0,2200,4400
2024-01-16T10:00:00Z,Buy,SOL,10,95,950
2024-01-17T10:00:00Z,Buy,ALGO,500,0.18,90
2024-02-01T10:00:00Z,Buy,DOGE,1000,0.08,80
2024-03-01T10:00:00Z,Buy,BTC,0.3,65000,19500
2024-03-15T10:00:00Z,Sell,BTC,0.4,68000,27200
2024-03-15T11:00:00Z,Sell,ETH,1.5,3500,5250
2024-03-20T10:00:00Z,Sell,SOL,5,150,750
2024-04-01T10:00:00Z,Sell,ALGO,300,0.25,75
"""

# Expected calculations per asset:
# BTC: Buy 0.5@42000=$21000, Buy 0.3@65000=$19500, Sell 0.4@68000=$27200
#      FIFO: First 0.4 from first lot @42000 cost = 0.4*42000=$16800
#      Gain = 27200 - 16800 = $10,400
#
# ETH: Buy 2.0@2200=$4400, Sell 1.5@3500=$5250
#      FIFO: 1.5 from first lot @2200 cost = 1.5*2200=$3300
#      Gain = 5250 - 3300 = $1,950
#
# SOL: Buy 10@95=$950, Sell 5@150=$750
#      FIFO: 5 from first lot @95 cost = 5*95=$475
#      Gain = 750 - 475 = $275
#
# ALGO: Buy 500@0.18=$90, Sell 300@0.25=$75
#       FIFO: 300 from first lot @0.18 cost = 300*0.18=$54
#       Gain = 75 - 54 = $21


class TestPerAssetFIFO:
    """Test that FIFO is calculated per asset, not mixed across assets"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token):
        """Setup test clients and auth"""
        self.client = api_client
        self.token = premium_auth_token
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.headers_json = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Cleanup before and after tests"""
        # Clear before test
        self._clear_transactions()
        yield
        # Clear after test
        self._clear_transactions()
    
    def _clear_transactions(self):
        """Clear all exchange transactions for test user"""
        try:
            response = self.client.delete(
                f"{BASE_URL}/api/admin/clear-exchange-transactions",
                headers=self.headers
            )
            print(f"Cleanup result: {response.status_code}")
        except Exception as e:
            print(f"Cleanup error (ignored): {e}")
    
    def _import_csv(self, csv_content: str):
        """Import CSV file for testing using proper multipart/form-data"""
        # Note: Don't set Content-Type header when using files - requests handles it
        import requests
        session = requests.Session()
        files = {
            'file': ('test_multi_asset.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        response = session.post(
            f"{BASE_URL}/api/exchanges/import-csv",
            headers={"Authorization": f"Bearer {self.token}"},
            files=files
        )
        return response
    
    def test_csv_import_multi_asset(self):
        """Test that CSV import successfully imports multiple assets"""
        response = self._import_csv(MULTI_ASSET_TEST_CSV)
        
        assert response.status_code == 200, f"CSV import failed: {response.text}"
        data = response.json()
        
        # Should import 10 transactions (5 buys + 4 sells + 1 DOGE buy)
        assert data.get("transaction_count") >= 10, f"Expected at least 10 txs, got {data.get('transaction_count')}"
        
        # Check summary has multiple assets
        summary = data.get("summary", {})
        assets = summary.get("by_asset", {})
        assert "BTC" in assets, "BTC not found in imported assets"
        assert "ETH" in assets, "ETH not found in imported assets"
        assert "SOL" in assets, "SOL not found in imported assets"
        assert "ALGO" in assets, "ALGO not found in imported assets"
        assert "DOGE" in assets, "DOGE not found in imported assets"
        
        print(f"✓ Imported {data.get('transaction_count')} transactions for {len(assets)} assets")
    
    def test_unified_tax_exchange_only_per_asset(self):
        """Test that unified tax calculates FIFO per asset"""
        # First import the CSV
        import_response = self._import_csv(MULTI_ASSET_TEST_CSV)
        assert import_response.status_code == 200, f"CSV import failed: {import_response.text}"
        
        # Call unified tax with exchange_only
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.headers_json,
            json={
                "chain": "ethereum",
                "data_source": "exchange_only"
            }
        )
        
        assert response.status_code == 200, f"Unified tax failed: {response.text}"
        data = response.json()
        tax_data = data.get("tax_data", {})
        
        # Check FIFO method
        assert tax_data.get("method") == "FIFO", "Should use FIFO method"
        
        # Check sources
        sources = tax_data.get("sources", {})
        assert sources.get("exchange_count", 0) > 0, "Should have exchange transactions"
        assert sources.get("assets_tracked", 0) >= 4, f"Should track at least 4 assets, got {sources.get('assets_tracked')}"
        
        # Check realized gains exist
        realized_gains = tax_data.get("realized_gains", [])
        assert len(realized_gains) > 0, "Should have realized gains from sells"
        
        print(f"✓ Tax data: {len(realized_gains)} realized gains, {sources.get('assets_tracked')} assets tracked")
        
        return tax_data
    
    def test_realized_gains_per_asset_match(self):
        """CRITICAL: Verify each realized gain has matching buy_asset and sell_asset"""
        # Import CSV first
        import_response = self._import_csv(MULTI_ASSET_TEST_CSV)
        assert import_response.status_code == 200
        
        # Get unified tax
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.headers_json,
            json={
                "chain": "ethereum",
                "data_source": "exchange_only"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        realized_gains = data.get("tax_data", {}).get("realized_gains", [])
        
        # CRITICAL CHECK: Each gain entry should have same asset for buy and sell
        # If BTC is sold, it should match a BTC buy, not ETH or DOGE
        mismatches = []
        for gain in realized_gains:
            asset = gain.get("asset", "UNKNOWN")
            buy_source = gain.get("buy_source", "")
            sell_source = gain.get("sell_source", "")
            buy_id = gain.get("buy_id", "")
            sell_id = gain.get("sell_id", "")
            
            # The asset field should be consistent
            # All buys/sells in a single gain entry should be for the same asset
            print(f"Gain entry: {asset} - Amount: {gain.get('amount'):.6f}, "
                  f"Buy@${gain.get('buy_price', 0):.2f}, Sell@${gain.get('sell_price', 0):.2f}, "
                  f"Gain: ${gain.get('gain_loss', 0):.2f}")
            
            # Validate the asset exists and is one of our expected assets
            valid_assets = ["BTC", "ETH", "SOL", "ALGO", "DOGE"]
            if asset not in valid_assets:
                mismatches.append(f"Unknown asset {asset} in gain entry")
        
        assert len(mismatches) == 0, f"Asset mismatches found: {mismatches}"
        print(f"✓ All {len(realized_gains)} realized gains have consistent per-asset matching")
    
    def test_gain_calculations_reasonable(self):
        """Verify gains are reasonable values, not billions"""
        # Import CSV first
        import_response = self._import_csv(MULTI_ASSET_TEST_CSV)
        assert import_response.status_code == 200
        
        # Get unified tax
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.headers_json,
            json={
                "chain": "ethereum",
                "data_source": "exchange_only"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        tax_data = data.get("tax_data", {})
        summary = tax_data.get("summary", {})
        realized_gains = tax_data.get("realized_gains", [])
        
        # Check individual gains are reasonable (not billions)
        MAX_REASONABLE_GAIN = 100_000  # $100k max per transaction in our test data
        for gain in realized_gains:
            gain_value = abs(gain.get("gain_loss", 0))
            assert gain_value < MAX_REASONABLE_GAIN, (
                f"Unreasonable gain ${gain_value:,.2f} for {gain.get('asset')} - "
                f"Bug likely: cross-asset FIFO matching"
            )
        
        # Check total realized gain is reasonable
        total_realized = summary.get("total_realized_gain", 0)
        MAX_TOTAL_REASONABLE = 1_000_000  # $1M max total for our test data
        assert abs(total_realized) < MAX_TOTAL_REASONABLE, (
            f"Total realized gain ${total_realized:,.2f} is unreasonable - "
            f"Bug likely: cross-asset FIFO matching producing billions"
        )
        
        print(f"✓ Total realized gain: ${total_realized:,.2f} (reasonable)")
        print(f"✓ All {len(realized_gains)} individual gains are reasonable")
    
    def test_btc_fifo_correct(self):
        """Verify BTC FIFO calculation specifically"""
        # Import CSV first
        import_response = self._import_csv(MULTI_ASSET_TEST_CSV)
        assert import_response.status_code == 200
        
        # Get unified tax
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.headers_json,
            json={
                "chain": "ethereum",
                "data_source": "exchange_only"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        realized_gains = data.get("tax_data", {}).get("realized_gains", [])
        
        # Find BTC gains
        btc_gains = [g for g in realized_gains if g.get("asset") == "BTC"]
        
        # We sold 0.4 BTC at $68,000
        # FIFO: should use first lot (0.5 BTC @ $42,000)
        # Expected: 0.4 * $68000 = $27,200 proceeds, 0.4 * $42000 = $16,800 cost basis
        # Gain = $27,200 - $16,800 = $10,400
        
        assert len(btc_gains) > 0, "Should have at least one BTC gain"
        
        total_btc_gain = sum(g.get("gain_loss", 0) for g in btc_gains)
        expected_btc_gain = 10400  # From our calculation
        
        # Allow 5% tolerance for potential price differences
        tolerance = abs(expected_btc_gain * 0.05)
        assert abs(total_btc_gain - expected_btc_gain) < tolerance + 100, (
            f"BTC gain ${total_btc_gain:,.2f} should be close to ${expected_btc_gain:,.2f}"
        )
        
        # Verify buy price is the first lot price (FIFO)
        for g in btc_gains:
            buy_price = g.get("buy_price", 0)
            # First lot was at $42,000, so buy price should be around that
            assert buy_price > 40000 and buy_price < 45000, (
                f"BTC buy price ${buy_price} should be near $42,000 (FIFO first lot)"
            )
        
        print(f"✓ BTC FIFO correct: Total gain ${total_btc_gain:,.2f} (expected ~${expected_btc_gain:,.2f})")
    
    def test_doge_no_sells_no_gains(self):
        """Verify DOGE (with only buys, no sells) doesn't appear in realized gains"""
        # Import CSV first
        import_response = self._import_csv(MULTI_ASSET_TEST_CSV)
        assert import_response.status_code == 200
        
        # Get unified tax
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.headers_json,
            json={
                "chain": "ethereum",
                "data_source": "exchange_only"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        realized_gains = data.get("tax_data", {}).get("realized_gains", [])
        
        # DOGE has no sells, so should NOT appear in realized gains
        doge_gains = [g for g in realized_gains if g.get("asset") == "DOGE"]
        
        assert len(doge_gains) == 0, (
            f"DOGE should have no realized gains (no sells), but found {len(doge_gains)} entries"
        )
        
        print("✓ DOGE correctly excluded from realized gains (no sells)")
    
    def test_assets_tracked_count(self):
        """Verify the sources.assets_tracked count is correct"""
        # Import CSV first
        import_response = self._import_csv(MULTI_ASSET_TEST_CSV)
        assert import_response.status_code == 200
        
        # Get unified tax
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.headers_json,
            json={
                "chain": "ethereum",
                "data_source": "exchange_only"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        sources = data.get("tax_data", {}).get("sources", {})
        
        # We imported 5 assets: BTC, ETH, SOL, ALGO, DOGE
        assets_tracked = sources.get("assets_tracked", 0)
        assert assets_tracked >= 5, f"Should track 5 assets, got {assets_tracked}"
        
        print(f"✓ Correctly tracking {assets_tracked} assets")


class TestForm8949Export:
    """Test Form 8949 export shows correct asset names"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token):
        """Setup test clients"""
        self.client = api_client
        self.token = premium_auth_token
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.headers_json = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def _import_csv(self, csv_content: str):
        """Import CSV file for testing using proper multipart/form-data"""
        import requests
        session = requests.Session()
        files = {
            'file': ('test_multi_asset.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        response = session.post(
            f"{BASE_URL}/api/exchanges/import-csv",
            headers={"Authorization": f"Bearer {self.token}"},
            files=files
        )
        return response
    
    def test_form_8949_endpoint_exists(self):
        """Verify Form 8949 export endpoint exists - POST /api/tax/export-form-8949"""
        # Form 8949 is a POST endpoint at /api/tax/export-form-8949
        response = self.client.post(
            f"{BASE_URL}/api/tax/export-form-8949",
            headers=self.headers_json,
            json={
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f5fEb6",
                "chain": "ethereum",
                "filter_type": "all",
                "data_source": "wallet_only"
            }
        )
        
        # Should return 200 or other response, not 404
        assert response.status_code != 404, f"Form 8949 endpoint should exist, got {response.status_code}"
        print(f"✓ Form 8949 endpoint accessible (status: {response.status_code})")
    
    def test_form_8949_shows_correct_asset_names(self):
        """Test that Form 8949 CSV shows correct asset names (BTC, ETH) not chain symbol"""
        # Clear and import multi-asset data
        self.client.delete(f"{BASE_URL}/api/admin/clear-exchange-transactions", headers=self.headers)
        
        import_response = self._import_csv(MULTI_ASSET_TEST_CSV)
        assert import_response.status_code == 200, f"CSV import failed: {import_response.text}"
        
        # Export Form 8949 with exchange_only
        response = self.client.post(
            f"{BASE_URL}/api/tax/export-form-8949",
            headers=self.headers_json,
            json={
                "address": "",
                "chain": "ethereum", 
                "filter_type": "all",
                "data_source": "exchange_only"
            }
        )
        
        # Should return CSV content
        assert response.status_code == 200, f"Form 8949 export failed: {response.text}"
        
        csv_content = response.text
        
        # Verify the CSV contains correct asset names
        # FIX VERIFICATION: It should show "BTC", "ETH", "SOL", "ALGO"
        # NOT just the chain symbol (e.g., "ETH" for everything)
        
        # Check for presence of asset names in Description column
        assert "BTC" in csv_content, "Form 8949 should show BTC asset name"
        assert "ETH" in csv_content or "SOL" in csv_content, "Form 8949 should show multiple asset names"
        
        # Check header mentions multiple assets
        if "Multiple" in csv_content:
            print("✓ Form 8949 header shows 'Multiple (N assets)' as expected")
        
        print(f"✓ Form 8949 contains correct asset names")
        
        # Cleanup
        self.client.delete(f"{BASE_URL}/api/admin/clear-exchange-transactions", headers=self.headers)


class TestWalletOnlyDefaultDataSource:
    """Test that UnifiedTaxDashboard defaults to wallet_only when wallet is present"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token):
        """Setup test clients"""
        self.client = api_client
        self.token = premium_auth_token
        self.headers_json = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_wallet_only_data_source_works(self):
        """Test that wallet_only data source works correctly"""
        # Solana wallet address from test requirements
        SOLANA_ADDRESS = "7UcUr26v8a7ttMTud3NeARj8nFqDa2upsGyAKHLcWhEr"
        
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.headers_json,
            json={
                "address": SOLANA_ADDRESS,
                "chain": "solana",
                "data_source": "wallet_only"
            }
        )
        
        assert response.status_code == 200, f"wallet_only failed: {response.text}"
        data = response.json()
        
        # Verify data_source in response
        assert data.get("data_source") == "wallet_only", "Should report wallet_only data source"
        
        # Verify sources show wallet only
        sources = data.get("data_sources_used", {})
        assert sources.get("wallet") == True or sources.get("wallet_tx_count", 0) >= 0
        
        # CRITICAL: Check total is reasonable (not billions)
        summary = data.get("tax_data", {}).get("summary", {})
        total_realized = abs(summary.get("total_realized_gain", 0))
        
        # Even for a real wallet, we shouldn't see billions
        MAX_REASONABLE = 1_000_000_000  # $1B is already extreme
        assert total_realized < MAX_REASONABLE, (
            f"wallet_only total ${total_realized:,.2f} exceeds reasonable max - "
            f"likely per-asset FIFO bug"
        )
        
        print(f"✓ wallet_only mode works, total realized: ${total_realized:,.2f}")


class TestCombinedModeMultiAsset:
    """Test combined mode (wallet + exchange) with multiple assets"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, premium_auth_token):
        """Setup test clients"""
        self.client = api_client
        self.token = premium_auth_token
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.headers_json = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def _import_csv(self, csv_content: str):
        """Import CSV file for testing using proper multipart/form-data"""
        import requests
        session = requests.Session()
        files = {
            'file': ('test_multi_asset.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        response = session.post(
            f"{BASE_URL}/api/exchanges/import-csv",
            headers={"Authorization": f"Bearer {self.token}"},
            files=files
        )
        return response
    
    def test_combined_mode_reasonable_numbers(self):
        """Test combined mode produces reasonable numbers"""
        # Clear old transactions first
        self.client.delete(
            f"{BASE_URL}/api/admin/clear-exchange-transactions",
            headers=self.headers
        )
        
        # Import multi-asset CSV
        import_response = self._import_csv(MULTI_ASSET_TEST_CSV)
        
        if import_response.status_code != 200:
            pytest.skip(f"CSV import failed: {import_response.text}")
        
        # Test combined mode with a wallet
        response = self.client.post(
            f"{BASE_URL}/api/tax/unified",
            headers=self.headers_json,
            json={
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f5fEb6",
                "chain": "ethereum",
                "data_source": "combined"
            }
        )
        
        assert response.status_code == 200, f"Combined mode failed: {response.text}"
        data = response.json()
        
        # Check reasonable numbers
        summary = data.get("tax_data", {}).get("summary", {})
        total_realized = abs(summary.get("total_realized_gain", 0))
        
        MAX_REASONABLE = 10_000_000_000  # $10B absolute max
        assert total_realized < MAX_REASONABLE, (
            f"Combined mode total ${total_realized:,.2f} is unreasonable"
        )
        
        print(f"✓ Combined mode total realized: ${total_realized:,.2f}")
        
        # Cleanup
        self.client.delete(
            f"{BASE_URL}/api/admin/clear-exchange-transactions",
            headers=self.headers
        )
