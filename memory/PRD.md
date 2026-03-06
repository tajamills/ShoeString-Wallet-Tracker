# Crypto Bag Tracker - Product Requirements Document

## Overview
Crypto Bag Tracker is a cryptocurrency wallet analysis platform that helps users track their holdings across multiple blockchains, calculate tax obligations, and generate IRS-compatible tax reports.

## Original Problem Statement
Build a cryptocurrency wallet analyzer that:
- Analyzes wallets across multiple blockchains (ETH, BTC, POLY, ARB, BSC, SOL)
- Supports tiered subscription model (Free, Premium, Pro)
- Provides accurate data for tax reporting including cost basis and capital gains
- Exports IRS Form 8949 for tax filing
- Supports Bitcoin HD wallets (xPub)
- "Analyze All Chains" feature for Pro users

## Tech Stack
- **Frontend**: React with Tailwind CSS, shadcn/ui components
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Blockchain APIs**: Alchemy (EVM/Solana), Blockstream/Blockcypher (Bitcoin)
- **Price Data**: CoinGecko API (with fallback prices for rate limiting)
- **Payments**: Stripe (recurring subscriptions)
- **Authentication**: Custom JWT-based auth

## Subscription Tiers
| Feature | Free | Unlimited ($100.88/year) |
|---------|------|----------------------|
| Wallet Analyses | 1 total | Unlimited |
| All 6 Blockchains | - | ✓ |
| CSV Export | - | ✓ |
| USD Valuation | - | ✓ |
| Tax Calculation (FIFO) | - | ✓ |
| Form 8949 & Schedule D Export | - | ✓ |
| Transaction Categorization | - | ✓ |
| Analyze All Chains | - | ✓ |
| Bitcoin xPub Support | - | ✓ |
| Exchange API Integration | - | ✓ |

## Terms of Service
All users must accept Terms of Service before using the platform. The TOS modal appears after login for new users and cannot be dismissed without accepting.

## Completed Features

### Phase 1: USD Valuation (Completed)
- [x] CoinGecko API integration for real-time prices
- [x] Fallback prices for rate limiting scenarios
- [x] Portfolio value in USD
- [x] Transaction values in USD
- [x] Running balance column in transaction history
- [x] Clear labeling (Current Balance vs Lifetime Totals)

### Phase 2: Cost Basis & Capital Gains (Completed - Feb 28, 2026)
- [x] FIFO (First-In, First-Out) cost basis calculation
- [x] Realized gains/losses tracking
- [x] Unrealized gains calculation
- [x] Short-term vs Long-term classification
- [x] Tax lots tracking
- [x] Tax Summary UI with 4 key metrics
- [x] Form 8949 CSV export (all/short-term/long-term filters)
- [x] Transaction categorization (trade, income, gift, etc.)
- [x] Categories persistence in database
- [x] Premium/Pro tier restrictions

### Phase 3: Tax Reports Enhancements (Completed - Feb 28, 2026)
- [x] Schedule D summary generation (text and CSV formats)
- [x] Tax year filtering (2020-current year)
- [x] Batch categorization with custom rules
- [x] Auto-categorization with smart detection
- [x] Schedule D export modal with year/format selection
- [x] Batch categorization modal with rule builder
- [x] Enhanced category options (staking, airdrop, mining)

### Phase 4: Affiliate Program (Completed - Mar 5, 2026)
- [x] Affiliate registration endpoint
- [x] Unique affiliate codes generation
- [x] Referral tracking system
- [x] Commission calculation ($10 per referral)
- [x] Affiliate dashboard modal
- [x] Affiliate code validation endpoint
- [x] Discount application during checkout ($10 off)
- [x] Admin reporting endpoints

### Phase 5: Exchange Integration - CSV Import (Completed - Mar 5, 2026)
- [x] CSV parser service with auto-detection for 6 exchanges
- [x] Support for: Coinbase, Binance, Kraken, Gemini, Crypto.com, KuCoin
- [x] File upload endpoint with auto-format detection
- [x] Step-by-step export instructions for each exchange
- [x] ExchangeModal with drag-and-drop CSV upload UI
- [x] Transaction storage and filtering
- [x] Privacy-first approach - no API keys stored
- [x] Free user restriction (Unlimited only)
- [x] **Multi-format Coinbase CSV support** (Mar 6, 2026):
  - Classic format: Timestamp, Transaction Type, Asset, Quantity Transacted
  - Modern format: Transaction ID, Date & time, Asset Acquired/Sold, Quantity Acquired/Sold, USD Value
  - Smart buy/sell detection based on crypto vs stablecoin assets
  - Heuristic detection for non-standard formats
- [x] Accepted CSV columns displayed in UI for each exchange
- [x] Detailed export instructions endpoint with format documentation

### Phase 5b: Exchange-Only Tax Calculator (Completed - Mar 5, 2026)
- [x] Standalone tax calculator from exchange CSVs (no wallet needed)
- [x] FIFO cost basis calculation across all imported exchanges
- [x] Realized/unrealized capital gains calculation
- [x] Form 8949 generation with short-term/long-term split
- [x] CSV export for Form 8949
- [x] Tax year filtering
- [x] Asset filtering
- [x] ExchangeModal tabs: Import CSVs / Tax Calculator
- [x] **Stablecoin exclusion** (Mar 6, 2026): USDC, USDT, BUSD, DAI, etc. excluded from cost basis (not taxable events)
- [x] **CPA Disclaimer** (Mar 6, 2026): Prominent warning that calculations are estimates and should be verified by a tax professional
- [x] **Calculation Transparency** (Mar 6, 2026): Clear documentation of what's included/excluded in calculations

### Phase 6: Code Refactoring (Completed - Mar 5, 2026)
- [x] Created useAnalysis hook for wallet analysis logic
- [x] Created usePayment hook for payment/subscription logic
- [x] Refactored App.js to use custom hooks (reduced complexity)
- [x] Created chains/ package with modular analyzers:
  - [x] base.py - BaseChainAnalyzer abstract class
  - [x] evm.py - EVMChainAnalyzer for Ethereum, Polygon, Arbitrum, BSC
  - [x] bitcoin.py - BitcoinAnalyzer with xPub support
  - [x] solana.py - SolanaAnalyzer
- [x] Created multi_chain_service_v2.py using modular analyzers
- [x] Verified backward compatibility with original multi_chain_service.py

### Core Features (Completed)
- [x] User authentication (JWT)
- [x] Stripe subscription management
- [x] Multi-chain wallet analysis
- [x] Bitcoin xPub HD wallet support (Pro)
- [x] Analyze All Chains (Pro)
- [x] Paginated CSV export
- [x] Saved wallets
- [x] Coupon code support
- [x] Branding updates (Crypto Bag Tracker)

## API Endpoints

### Authentication
- POST `/api/auth/register` - User registration
- POST `/api/auth/login` - User login
- GET `/api/auth/me` - Get current user

### Wallet Analysis
- POST `/api/wallet/analyze` - Analyze single wallet (returns tax_data for premium+)
- POST `/api/wallet/analyze-all` - Analyze all chains (Pro only)
- POST `/api/wallet/export-transactions` - Paginated CSV export

### Tax Reports
- POST `/api/tax/export-form-8949` - Generate Form 8949 CSV (Premium+)
- POST `/api/tax/export-summary` - Generate tax summary CSV (Premium+)
- POST `/api/tax/export-schedule-d` - Generate Schedule D summary (Premium+)
- POST `/api/tax/save-categories` - Save transaction categories (Premium+)
- GET `/api/tax/categories/{address}` - Get saved categories (Premium+)
- POST `/api/tax/batch-categorize` - Batch categorize with rules (Premium+)
- POST `/api/tax/auto-categorize` - Auto-categorize transactions (Premium+)
- GET `/api/tax/supported-years` - Get supported tax years (Public)

### Exchange Integration
- GET `/api/exchanges/supported` - List supported exchanges (public)
- POST `/api/exchanges/connect` - Connect an exchange (Unlimited only)
- GET `/api/exchanges/connected` - List connected exchanges
- DELETE `/api/exchanges/{exchange_id}` - Disconnect an exchange
- POST `/api/exchanges/{exchange_id}/sync` - Sync exchange data (Unlimited only)
- GET `/api/exchanges/transactions` - Get synced transactions (Unlimited only)

### Affiliate Program
- POST `/api/affiliate/register` - Register as affiliate
- GET `/api/affiliate/me` - Get affiliate dashboard data
- GET `/api/affiliate/validate/{code}` - Validate affiliate code
- GET `/api/affiliate/admin/report` - Admin affiliate report

### Payments
- POST `/api/payments/create-upgrade` - Create Stripe checkout session
- POST `/api/payments/manage-subscription` - Get billing portal URL
- POST `/api/payments/webhook/stripe` - Stripe webhook handler

## Database Schema

### users
```javascript
{
  id: UUID,
  email: String,
  password_hash: String,
  subscription_tier: "free" | "premium" | "pro",
  stripe_customer_id: String,
  stripe_subscription_id: String,
  subscription_status: String,
  current_period_end: DateTime,
  cancel_at_period_end: Boolean,
  analysis_count: Number,
  created_at: DateTime
}
```

### saved_wallets
```javascript
{
  user_id: String,
  wallet_address: String,
  name: String,
  chain: String
}
```

### transaction_categories
```javascript
{
  id: UUID,
  user_id: String,
  address: String,
  chain: String,
  categories: { tx_hash: category_string },
  updated_at: DateTime
}
```

## Upcoming Tasks

### Next Priority: Integrate Exchange CSV with Tax Calculations
- [x] Add data source toggle to Unified Tax Dashboard ("Wallet Only", "Exchange Only", "Combined")
- [x] Backend `/api/tax/unified` endpoint accepts `data_source` parameter
- [x] Response includes `data_sources_used` showing which sources were included
- [x] Merge on-chain wallet transactions + imported CSV data into unified tax report
- [x] Update `UnifiedTaxDashboard` with source selector and transaction count badges
- [x] CPA disclaimer added to all tax-related components
- [ ] Generate Form 8949 with both on-chain and exchange transactions (partially complete - needs unified export)

### Phase 6: Cost Basis Adjustment for Transfers (Completed - Mar 6, 2026)
- [x] Backend endpoint: PUT `/api/exchanges/transactions/{tx_id}/cost-basis`
- [x] Backend endpoint: GET `/api/exchanges/transactions/transfers` (detect potential transfers)
- [x] Support for `acquisition_date_override` and `cost_basis_override` fields
- [x] Tax calculations use overridden dates for holding period (short vs long-term)
- [x] TransactionEditor component to edit transfer details
- [x] "Adjust Cost Basis" tab in ExchangeModal
- [x] Auto-detect receive→sell patterns within 30 days as potential transfers

### Phase 7: Auto-Match Wallet→Exchange Transfers (Completed - Mar 6, 2026)
- [x] `detect_transfers_between_sources()` in unified_tax_service.py
- [x] Matches wallet sends to exchange receives by: same asset, similar amount (±1%), time within 48hrs
- [x] Backend endpoint: POST `/api/tax/detect-transfers` 
- [x] Captures `from_address` and `to_address` from wallet transactions
- [x] Detected transfers shown in UnifiedTaxDashboard with count and assets
- [x] Linked transactions use wallet's original acquisition date for holding period
- [x] Combined data source auto-matches when both wallet + exchange data present

### Future Features (P2-P5)
- [ ] DeFi & NFT Integration (liquidity pools, staking, NFT valuations)
- [ ] Additional blockchains (Avalanche, Optimism, Base)
- [ ] Data visualizations (charts, graphs for portfolio history)
- [ ] Mobile responsiveness improvements
- [ ] Tax loss harvesting suggestions
- [ ] Further component extraction from App.js (WalletInputCard, AnalysisResults)
- [ ] Use multi_chain_service_v2 as the primary service (deprecate v1)

## Deployment
- **Platform**: Render
- **Domain**: cryptobagtracker.io
- **CI/CD**: GitHub auto-deploy

### Required Environment Variables
```
# Backend
MONGO_URL=mongodb://...
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PREMIUM=price_...
STRIPE_PRICE_ID_PRO=price_...
ALCHEMY_API_KEY=...

# Frontend
REACT_APP_BACKEND_URL=https://...
```

## Test Users
- `taxtest@test.com` / `TestPass123!` - Premium tier (for testing tax features)

## Known Limitations
- CoinGecko API rate limits (fallback prices used when rate-limited)
- Form 8949 export requires realized gains (sell transactions)
- Historical prices for past transactions use current prices as fallback
