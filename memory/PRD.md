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

### Phase 9: Chain of Custody Analysis (Completed - Mar 8, 2026)
- [x] Chain of Custody service (`custody_service.py`)
- [x] Traces transactions backwards to find asset origins
- [x] Stop conditions:
  - Exchange detection (Binance, Coinbase, Kraken, Gemini, etc.)
  - DEX detection (Uniswap, SushiSwap, 1inch)
  - Dormancy threshold (configurable, default 365 days)
- [x] Known exchange addresses database (24+ exchange addresses)
- [x] Known DEX router addresses (6 major DEXs)
- [x] API endpoints:
  - POST `/api/custody/analyze` - Run chain of custody analysis
  - GET `/api/custody/history` - Get user's analysis history
  - GET `/api/custody/known-addresses` - List known exchange/DEX addresses
- [x] Frontend modal (`ChainOfCustodyModal.js`)
- [x] **Interactive Flow Graph visualization** (`CustodyFlowGraph.js`) - Mar 9, 2026:
  - Tree diagram showing asset flow through wallets
  - Color-coded nodes (Exchange=green, DEX=blue, Dormant=orange, Target=purple)
  - Interactive zoom, pan, and drag
  - MiniMap for navigation
  - Legend explaining node types
  - Toggle between Graph View and Table View
- [x] Support for 6 EVM chains (Ethereum, Polygon, Arbitrum, BSC, Base, Optimism)
- [x] Advanced options (max depth, dormancy threshold)
- [x] CSV export of results
- [x] Unlimited tier only feature
- [x] Designed for easy extraction/licensing to government entities

### Phase 10: Coinbase OAuth Integration (Completed - Mar 10, 2026)
- [x] Coinbase OAuth service (`coinbase_oauth_service.py`)
- [x] READ-ONLY access only (cannot move, send, or withdraw funds)
- [x] OAuth scopes: wallet:accounts:read, wallet:transactions:read, wallet:addresses:read
- [x] API endpoints:
  - GET `/api/coinbase/auth-url` - Get OAuth authorization URL
  - POST `/api/coinbase/callback` - Handle OAuth callback
  - GET `/api/coinbase/status` - Check connection status
  - DELETE `/api/coinbase/disconnect` - Disconnect Coinbase account
  - GET `/api/coinbase/addresses-for-custody` - Fetch addresses for custody analysis
- [x] Frontend updated with two input methods:
  - **Connect Coinbase** - Automatically import addresses from Coinbase
  - **Manual Entry** - Enter wallet addresses one by one
- [x] Security notice explaining READ-ONLY access
- [x] Token refresh handling for expired access tokens

### Phase 11: Multi-Exchange & PDF Reports (Completed - Mar 10, 2026)
- [x] Multi-Exchange service (`multi_exchange_service.py`)
  - Binance API integration (READ-ONLY)
  - Kraken API integration (READ-ONLY)
  - Gemini API integration (READ-ONLY)
  - **Crypto.com API integration (READ-ONLY)** - NEW
  - **KuCoin API integration (READ-ONLY)** - NEW
  - **OKX API integration (READ-ONLY)** - NEW
- [x] **Encryption Service** (`encryption_service.py`) - NEW
  - Fernet symmetric encryption for API keys
  - Keys encrypted before database storage
  - Automatic decryption on retrieval
  - ENCRYPTION_KEY environment variable required for production
- [x] API endpoints for exchange connections:
  - POST `/api/exchanges/connect-api` - Connect exchange with API keys (now with passphrase support)
  - GET `/api/exchanges/api-connections` - List connected exchanges
  - DELETE `/api/exchanges/disconnect-api/{exchange}` - Disconnect exchange
  - GET `/api/exchanges/addresses-for-custody/{exchange}` - Fetch addresses
- [x] PDF Report Generator (`custody_report_generator.py`)
  - Professional reports for auditors/government
  - Title page with analysis metadata
  - Executive summary with statistics
  - Exchange origins table
  - DEX origins table
  - Dormant wallet origins
  - Full transaction chain detail
  - Disclaimer and footer
- [x] API endpoints for PDF export:
  - POST `/api/custody/export-pdf` - Generate PDF from new analysis
  - POST `/api/custody/export-pdf-from-result` - Generate PDF from existing result
- [x] Frontend "PDF Report" button added to results view
- [x] **Coinbase OAuth Setup Guide** (`/app/COINBASE_OAUTH_SETUP.md`) - NEW

### Phase 12: Support & Help System (Completed - Mar 10, 2026)
- [x] AI Support Agent (`support_agent_service.py`)
  - GPT-4o powered help assistant
  - Answers crypto tax questions
  - Trained on app features and tax basics
  - Conversation history tracking
- [x] Support Modal (`SupportModal.js`)
  - **AI Assistant tab** - Chat with AI for instant help
  - **Contact Us tab** - Email form for human support
  - Suggested questions for quick help
  - Conversation history persistence
- [x] API endpoints:
  - POST `/api/support/ai-chat` - Send message to AI
  - GET `/api/support/suggested-questions` - Get suggested questions
  - POST `/api/support/contact` - Submit contact form
  - GET `/api/support/conversation-history` - Get chat history
- [x] Help button added to navigation bar

### Phase 13: Additional Exchanges (Completed - Mar 10, 2026)
- [x] **Bybit** API integration (READ-ONLY)
- [x] **Gate.io** API integration (READ-ONLY)
- Total supported exchanges: **8**
  - Binance, Kraken, Gemini, Crypto.com, KuCoin, OKX, Bybit, Gate.io

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

### Chain of Custody (Unlimited tier)
- POST `/api/custody/analyze` - Run chain of custody analysis
- GET `/api/custody/history` - Get user's analysis history
- GET `/api/custody/known-addresses` - List known exchange/DEX addresses

### Coinbase OAuth (Unlimited tier)
- GET `/api/coinbase/auth-url` - Get OAuth authorization URL
- POST `/api/coinbase/callback` - Handle OAuth callback and exchange tokens
- GET `/api/coinbase/status` - Check Coinbase connection status
- DELETE `/api/coinbase/disconnect` - Disconnect Coinbase account
- GET `/api/coinbase/addresses-for-custody` - Fetch all addresses for custody analysis

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

### Phase 8: Expanded Chain Support (Completed - Mar 6, 2026)
- [x] **Algorand (ALGO)** - Algonode indexer API
- [x] **Avalanche (AVAX)** - Alchemy EVM
- [x] **Optimism (ETH)** - Alchemy EVM  
- [x] **Base (ETH)** - Alchemy EVM
- [x] **Fantom (FTM)** - Alchemy EVM
- [x] **Dogecoin (DOGE)** - BlockCypher + Dogechain API
- [x] **Request a Chain** feature for Unlimited users (48hr turnaround)
- [x] Chain request stored in MongoDB, status tracking
- [x] Quick-select popular chains (Cardano, XRP, Tron, etc.)
- [x] Total: 12 supported blockchains

**Currently Supported Chains:**
1. Ethereum (ETH) - Free tier
2. Bitcoin (BTC) - Free tier  
3. Polygon (MATIC)
4. Arbitrum (ETH)
5. BNB Smart Chain (BNB)
6. Solana (SOL)
7. Algorand (ALGO)
8. Avalanche (AVAX)
9. Optimism (ETH)
10. Base (ETH)
11. Fantom (FTM)
12. Dogecoin (DOGE)

### Future Features (P2-P5)
- [ ] DeFi & NFT Integration (liquidity pools, staking, NFT valuations)
- [ ] Additional blockchains (Avalanche, Optimism, Base)
- [ ] Data visualizations (charts, graphs for portfolio history)
- [x] **Mobile responsiveness improvements** (Completed - Mar 10, 2026)
- [ ] Tax loss harvesting suggestions
- [ ] Further component extraction from App.js (WalletInputCard, AnalysisResults)
- [ ] Use multi_chain_service_v2 as the primary service (deprecate v1)

### Phase 14: Mobile Responsiveness (Completed - Mar 10, 2026)
- [x] Responsive header - scales title and icons for mobile
- [x] Responsive user info bar - buttons wrap on mobile instead of overflowing
- [x] Responsive wallet input - input and buttons stack on small screens
- [x] Responsive statistics grid - 2 columns on mobile, 4 on desktop
- [x] Responsive transactions table - hidden columns on mobile, scrollable
- [x] Responsive modals - full width on mobile with adjusted padding
- [x] Chain of Custody modal mobile fixes
- [x] Support modal mobile fixes
- [x] Tablet breakpoint support (768px)
- [x] Mobile breakpoint support (375px and below)

### Phase 15: User Credentials & Documentation (Completed - Mar 11, 2026)
- [x] Changed Coinbase integration from OAuth to user API keys
- [x] Users now enter THEIR OWN Coinbase API credentials
- [x] Each user's data accessed using their own credentials only
- [x] Added Coinbase to multi_exchange_service.py with API key support
- [x] Chain of Custody now supports all 12 blockchains (added BTC, SOL, ALGO, AVAX, FTM, DOGE)
- [x] Created comprehensive product documentation:
  - PROCESS_FLOW.md - Visual flow diagrams
  - PRODUCT_SPEC.md - Product requirements & business model
  - USER_STORIES.md - 35 user stories with acceptance criteria
  - BACKLOG.md - Prioritized feature backlog
  - API_DOCUMENTATION.md - API endpoint reference
  - TECHNICAL_ARCHITECTURE.md - System architecture
  - RELEASE_NOTES.md - Version history
  - EXECUTIVE_SUMMARY.md - One-pager for stakeholders
  - SECURITY_COMPLIANCE.md - Security controls for insurance
  - PRIVACY_POLICY.md - User privacy policy
  - TERMS_OF_SERVICE.md - Legal terms
  - RISK_ASSESSMENT.md - Risk analysis for insurance
- [x] Updated all docs with contact info: support@cryptobagtracker.com, (404) 954-1182, 1557 Buford Dr #492773, Lawrenceville, GA 30043

### Phase 16: MVP Finalization (Completed - Mar 2026)
- [x] **Password Reset Flow** (email via Resend)
  - Added `/api/auth/forgot-password` endpoint
  - Added `/api/auth/reset-password` endpoint
  - Token-based reset with 24-hour expiration
  - Integrated Resend for transactional emails
  - Frontend "Forgot your password?" link in AuthModal
  - Success/error message handling
- [x] **Welcome Email** sent on new user registration (via Resend)
- [x] **Sentry Integration** for error monitoring (backend)
- [x] **UI Simplification** (hiding non-MVP features)
  - Removed Help/Support button (AI chatbot) from main UI
  - Simplified TaxDashboard to show only Form 8949 CSV export
  - Hidden Schedule D export button
  - Hidden Batch Categorize button  
  - Hidden "Categorize Transactions for Tax" button
  - Kept backend logic intact for future use
- [x] **Critical Bug Fix**: DateTime comparison in check_usage_limit()
  - Fixed timezone-naive vs timezone-aware datetime comparison
  - Wallet analysis now works correctly
- [x] **Deployment Fix**: Removed emergentintegrations from requirements.txt (not available on standard PyPI)
- [x] **Test Coverage**: Backend 100%, Frontend 70% (3 flaky due to timing)

### Phase 17: Chain Analyzer Fixes (Completed - Mar 2026)
- [x] **Solana Analyzer**: Fixed to properly parse transaction values using dedicated analyzer
- [x] **BSC/BNB Analyzer**: Fixed API parameters (BSC doesn't support withMetadata/excludeZeroValue)
- [x] **BSC Metadata Fix**: Fixed NoneType error when metadata is null
- [x] **Algorand Analyzer**: Fixed to use dedicated analyzer format
- [x] **Dogecoin Analyzer**: Fixed to use dedicated analyzer format
- [x] **Address Detection**: Added XRP (r prefix) and XLM/Stellar (G prefix, 56 chars) detection
- [x] **Form 8949 Export**: Updated to use unified tax service (wallet + exchange combined)
- [x] **Schedule D Export**: Updated to use unified tax service (wallet + exchange combined)
- [x] **Password Reset Page**: Created /reset-password route for email links
- [x] **Email Notifications**: Added subscription upgrade, expiring, expired emails
- [x] **Stripe Webhook**: Added invoice.upcoming listener for renewal reminders

### Chain Verification Results (Mar 2026)
| Chain | Status | Notes |
|-------|--------|-------|
| Ethereum | ✅ Working | Full support with historical prices |
| BSC/BNB | ✅ Working | Fixed API params |
| Solana | ✅ Working | Fixed value parsing, historical prices |
| Bitcoin | ✅ Working | Full support |
| Polygon | ✅ Working | Full support |
| Algorand | ✅ Working | Full support |
| Dogecoin | ✅ Working | Full support with historical prices |
| XRP | ✅ Working | Full support with historical prices |
| XLM/Stellar | ✅ Working | Fixed 400 error handling |

### Phase 18: On-Chain Tax Calculation (Completed - Mar 2026)
- [x] **Historical Tax Enrichment Service** (`historical_tax_enrichment.py`)
  - Fetches historical prices from CoinGecko for each transaction timestamp
  - Enriches wallet transactions with accurate cost basis
  - Implements FIFO matching for realized gains calculation
  - Calculates unrealized gains for remaining holdings
  - Validates transactions to catch anomalies (>$100B values)
- [x] **Price Service Updates** (`price_service.py`)
  - Added XRP and XLM to CoinGecko ID mappings
  - Updated fallback prices for new chains
- [x] **Multi-Chain Service Updates** (`multi_chain_service.py`)
  - Now uses historical_tax_enrichment for tax calculations
  - Added timestamp extraction from EVM transaction metadata
  - Fixed tier check to include 'unlimited' for tax data
- [x] **Unified Tax Service Validation** (`unified_tax_service.py`)
  - Added validation logging for suspicious transactions
  - Logs transactions with amounts/prices >$10B
  - Helps identify data bugs like the -$37B issue
- [x] **Stellar Analyzer Fix** (`chains/stellar.py`)
  - Fixed 400 Bad Request error handling
  - Gracefully handles invalid addresses
- [x] **Dead Code Removal**
  - Removed obsolete `/api/admin/check-expiring-subscriptions` endpoint
  - Subscription warnings now handled by Stripe webhooks

### Phase 19: Critical FIFO Bug Fix - Per-Asset Calculation (Completed - Mar 19, 2026)
- [x] **ROOT CAUSE IDENTIFIED**: FIFO calculation was mixing ALL assets (BTC, ETH, SOL, DOGE, etc.) into a single queue, causing cross-asset matching (e.g., BTC sells matched against DOGE buys) which produced astronomical and incorrect gains/losses
- [x] **Fix in `unified_tax_service.py`**: `calculate_unified_tax_data()` now groups transactions by asset symbol, runs FIFO independently per asset, then aggregates results
- [x] **Fix in `historical_tax_enrichment.py`**: `calculate_on_chain_tax_data()` same per-asset FIFO fix applied
- [x] **Form 8949 Export Fix** (`tax_report_service.py`): Now shows correct asset names (BTC, ETH, SOL) in description column instead of chain symbol; header shows "Multiple (N assets)" for multi-asset reports
- [x] **Frontend Default Data Source**: Changed from "combined" to "wallet_only" when a wallet address is active in `UnifiedTaxDashboard.js`
- [x] **Test Coverage**: 11/11 backend tests passed, frontend verified via Playwright

### Phase 20: Exchange Deposit Address Detection (Completed - Mar 19, 2026)
- [x] **Detection Logic** in `multi_chain_service.py`: Detects exchange deposit address pattern (receive then immediate sweep to exchange main wallet) based on balance ~0, total_in ≈ total_out, and sweep timing
- [x] **Backend Response Model**: Added `exchange_deposit_warning` field to `WalletAnalysisResponse` Pydantic model in `server.py`
- [x] **Frontend Alert** in `App.js`: Shows prominent amber warning when exchange deposit address is detected, with "Import Exchange CSV" and "Connect Exchange API" action buttons
- [x] **Coinbase Transaction Sync**: New endpoint `POST /api/exchanges/sync-coinbase` fetches all buys/sells/trades from connected Coinbase API and stores as exchange_transactions
- [x] **Sync UI Button**: Added "Sync All Transactions from Coinbase" button in Chain of Custody modal
- [x] **Test Coverage**: 11/11 tests passed (iteration 15)

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
- `mobiletest@test.com` / `test123456` - Unlimited tier

## Known Limitations
- CoinGecko API rate limits (fallback prices used when rate-limited)
- Form 8949 export requires realized gains (sell transactions)
- Historical prices for past transactions use current prices as fallback

### Phase 21: Chain of Custody & Wallet Linkage Verification (Completed - Mar 26, 2026)
- [x] **3-Layer Linkage Architecture** verified working:
  - Layer 1: Canonical Ledger (immutable transaction data)
  - Layer 2: Linkage Engine (`linkage_engine_service.py`) - identity/ownership matching
  - Layer 3: Chain of Custody UI (user-facing custody trails)
- [x] **Review Queue System** fully functional:
  - Detects cross-exchange transfers
  - Shows pending chain breaks for user decision
  - Supports "Mine" (creates linkage), "External" (creates tax event), "Skip" (ignore)
- [x] **Form 8949 CSV Export** verified:
  - IRS-compliant format with proper columns
  - Uses FIFO cost basis from original acquisition date
  - Tax events generated from "External" resolutions
- [x] **API Endpoints Tested**:
  - GET `/api/custody/review-queue` - 328 pending items
  - POST `/api/custody/resolve-review` - Mine/External decisions work
  - GET `/api/custody/linkages` - 37 active linkages
  - GET `/api/custody/clusters` - Wallet grouping
  - GET `/api/custody/tax-events` - Tax event retrieval
  - GET `/api/custody/export-form-8949` - CSV download
  - GET `/api/custody/export-review-queue` - CSV export for offline review
- [x] **Bug Fix**: Error handling in resolve-review now returns proper 400 status for invalid decisions

## Backlog
- [ ] DeFi/NFT Position Tracking
- [ ] Refactor monolithic files (`ChainOfCustodyModal.js`, `App.js`)
- [ ] Import missing USDC/XLM acquisitions to resolve remaining 3 critical orphan disposal issues (P1)
- [ ] Frontend UI for Regression Fixture Management (P2)

## Completed

**P0 - Critical (Blocking Export)** ✅
- [x] Root-cause and fix orphan disposals for XLM and USDC
- [x] Categorize unresolved review queue items by cause and frequency
- [x] Confirm `can_export: false` is enforced everywhere export can happen

**P1 - High Priority** ✅
- [x] Persist validation state to MongoDB (`tax_lots`, `tax_disposals`, `tax_audit_trail`)
- [x] Integrate validation into CSV import flow (auto-classify on import)
- [x] Hook validation into existing tax services
- [x] Auto-trigger recompute on linkage/classification changes
- [x] Add validation status to API responses

**P1.5 - Proceeds Acquisition Constraints** ✅ (Completed - Mar 27, 2026)
- [x] Renamed "implicit acquisitions" to "proceeds acquisitions"
- [x] Require linked source disposal (must reference the sell tx that generated proceeds)
- [x] Require exact amount match (proceeds amount = acquisition amount)
- [x] Require timestamp (must match source disposal timestamp)
- [x] Require price source (e.g., "proceeds_from_BTC_sell")
- [x] Require audit trail entry linking disposal → proceeds acquisition
- [x] Added POST `/api/custody/fix/create-proceeds-acquisitions` endpoint with dry_run support
- [x] Legacy endpoint alias `/api/custody/fix/create-implicit-acquisitions` for backwards compatibility

**P1.5.1 - Constrained Proceeds Acquisition Remediation** ✅ (Completed - Mar 27, 2026)
- [x] **ConstrainedProceedsService** (`constrained_proceeds_service.py`) - Strict validation flow
  - Only creates proceeds acquisition when linked to known source disposal
  - Required fields: source_disposal_tx_id, proceeds_asset, exact_amount, timestamp, price_source
  - Tags all records as `derived_proceeds_acquisition`
  - All records are reversible via rollback_batch_id
  
- [x] **Exclusion Rules** - Never creates inventory without proper justification:
  - Unresolved wallet ownership (pending review queue)
  - Missing acquisition history for asset
  - Inferred internal transfers (chain_status=linked)
  - Bridge ambiguity without explicit proceeds leg
  - DEX ambiguity without explicit proceeds leg
  - Missing proceeds value or timestamp
  - Stablecoin source (USDC sells don't generate USDC proceeds)
  - Already has existing proceeds record
  
- [x] **Preview Mode** - Show candidates before applying:
  - GET `/api/custody/proceeds/preview` - Lists all fixable/non-fixable disposals
  - Shows reason, source disposal, derived asset, amount, timestamp for each candidate
  
- [x] **Dry-Run Summary**:
  - Count of fixable orphan disposals
  - Count of non-fixable orphan disposals by reason
  - Detailed breakdown of why each case was skipped
  
- [x] **Reversibility**:
  - POST `/api/custody/proceeds/apply` - Creates records with rollback_batch_id
  - POST `/api/custody/proceeds/rollback` - Reverses a batch of created records
  - GET `/api/custody/proceeds/rollback-batches` - Lists all reversible batches
  
- [x] **Test Suite** (`test_constrained_proceeds.py`) - 16 tests
  - Validates all exclusion cases
  - Ensures NEVER creates inventory without linked disposal
  - Verifies audit trail and source_disposal linkage

**P1.6 - Price Backfill Pipeline** ✅ (Completed - Mar 27, 2026)
- [x] **PriceBackfillService** (`price_backfill_service.py`) - Historical price fetching
  - Fetches USD price at/nearest to transaction timestamp
  - Uses CryptoCompare (primary) and CoinGecko (fallback) APIs
  - Stablecoins (USDC, USDT, etc.) auto-valued at $1
  
- [x] **Valuation Status Tracking**:
  - `exact`: Price from exact transaction date (high confidence 0.95)
  - `approximate`: Price from nearest available date within 24h window
  - `stablecoin`: Fixed 1:1 USD peg (confidence 1.0)
  - `unavailable`: No price data found
  
- [x] **Stored Metadata per Transaction**:
  - `price_backfill.valuation_status`: exact/approximate/stablecoin/unavailable
  - `price_backfill.price_source`: cryptocompare/coingecko/stablecoin_peg
  - `price_backfill.timestamp_used`: Actual timestamp used for price lookup
  - `price_backfill.time_delta_hours`: Difference between tx time and price time
  - `price_backfill.confidence`: 0.0-1.0 confidence score
  - `price_backfill.backfill_batch_id`: For rollback capability
  
- [x] **Eligibility Gate for Proceeds Acquisition**:
  - Only `exact` and `stablecoin` valuations enable proceeds acquisition
  - `approximate` requires confidence >= 0.7
  - `unavailable` blocks proceeds acquisition
  - Constrained proceeds service updated to check `valuation_not_eligible`
  
- [x] **API Endpoints**:
  - GET `/api/custody/price-backfill/preview` - Dry-run showing total/backfillable/missing
  - POST `/api/custody/price-backfill/apply` - Apply backfill with audit trail
  - POST `/api/custody/price-backfill/rollback` - Reverse a batch
  - GET `/api/custody/price-backfill/batches` - List all batches
  
- [x] **Test Suite** (`test_price_backfill.py`) - 14 tests
  - Validates all valuation statuses
  - Verifies eligibility checks for proceeds acquisition
  - Confirms audit trail creation and rollback capability

**P1.7 - Staged Proceeds Application Controls** ✅ (Completed - Mar 27, 2026)
- [x] **StagedProceedsService** (`staged_proceeds_service.py`) - Controlled application flow
  - Apply exact-valuation candidates first (recommended Stage 1)
  - Automatic validation after each batch with delta metrics
  - Full rollback capability by batch_id
  
- [x] **Filtering Support**:
  - Filter by asset(s) (e.g., "BTC,ETH")
  - Filter by date range (date_from, date_to in YYYY-MM-DD)
  - Filter by valuation status (exact_only, stablecoin_only, high_confidence, all_eligible)
  - Filter by confidence threshold (min_confidence 0.0-1.0)
  - Filter by max time delta (max_time_delta_hours)
  
- [x] **Validation Delta Metrics**:
  - `orphan_disposals` before/after/delta
  - `validation_status` before/after
  - `can_export` before/after
  - `blocking_issues` before/after/delta
  - `new_warnings`, `new_errors`, `resolved_issues`
  
- [x] **Safety Blocks**:
  - Low-confidence approximates (<0.7) blocked by default
  - Wide-window approximates (>12h time delta) blocked by default
  - Requires `force_override=True` to bypass safety blocks
  
- [x] **API Endpoints**:
  - GET `/api/custody/proceeds/staged/stages` - Recommended application stages
  - GET `/api/custody/proceeds/staged/preview` - Preview with filters
  - POST `/api/custody/proceeds/staged/apply` - Apply with filters and delta
  - POST `/api/custody/proceeds/staged/apply-exact` - Convenience: exact only
  - POST `/api/custody/proceeds/staged/apply-stablecoins` - Convenience: stablecoins only
  - POST `/api/custody/proceeds/staged/apply-high-confidence` - Convenience: high confidence
  
- [x] **Test Results**:
  - Applied 121 candidates in 3 staged batches (BTC: 15, ETH: 20, remaining: 86)
  - Total value: $72,799.38
  - Final delta: orphan_disposals 1→0, validation_status needs_review→valid, can_export false→true

**P1.8 - Post-Validation Hardening** ✅ (Completed - Mar 27, 2026)

- [x] **1. Regression Fixture System** (`regression_fixture_service.py`)
  - Snapshots validated accounts: raw transactions, transfers, linkages, tax lots, disposals, validation state, Form 8949 dataset
  - Stores fixture with version tag (e.g., "golden_account_v1")
  - Automated regression test: re-runs pipeline and compares disposal_count, total_proceeds, total_cost_basis, total_gain_loss, validation_status, can_export
  - Fails test if any mismatch occurs
  - Endpoints: POST `/regression/create-fixture`, POST `/regression/run-test/{id}`, GET `/regression/fixtures`

- [x] **2. Pre-Export Summary Metadata** (`export_safety_guard.py`)
  - Extended tax API responses with summary block:
    - validation_status (valid/invalid/needs_review)
    - can_export (true/false)
    - proceeds_derived_count
    - unresolved_review_count
    - blocking_issues_count
    - last_recompute_timestamp
  - Always returned before export via GET `/beta/pre-export-check`

- [x] **3. Modular Refactor of custody.py** (~2300 lines → 5 modules)
  - `custody_core_routes.py`: Chain of custody, linkages, Form 8949, tax lots
  - `review_queue_routes.py`: Review queue operations
  - `validation_routes.py`: Validation, invariants, regression fixtures
  - `proceeds_routes.py`: Constrained proceeds, staged application
  - `price_backfill_routes.py`: Price backfill operations
  - No change to logic, all tests pass, routing paths unchanged

- [x] **4. Recompute Integrity Enforcement** (`recompute_service.py`)
  - Triggers full recompute on: linkage changes, classification changes, proceeds application, price backfill
  - No partial updates allowed - rebuilds tax lots, disposals, validation state
  - Stores recompute timestamp via `mark_pending_recompute()`
  - Endpoint: POST `/validate/recompute`

- [x] **5. Export Safety Guard** (`export_safety_guard.py`)
  - Before Form 8949 generation:
    - Re-runs validation
    - Confirms validation_status == "valid" and can_export == true
  - If not: blocks export, returns structured error with blocking issues
  - Force bypass available via `?force=true` parameter

- [x] **6. Audit Trail Completeness**
  - All derived records include:
    - source_tx_id(s), derivation_type, timestamp, price_source, batch_id, reversible flag
  - Endpoint: GET `/validate/audit-trail`

**Testing:** 100% pass rate (29 API tests)

**P2 - Review Queue Enhancements** ✅ (Completed - Mar 27, 2026)
- [x] **Frontend Validation Status UI** (`ValidationStatusPanel.js`)
  - Displays overall validation status (valid/invalid/needs_review)
  - Shows blocking issues count, unresolved reviews count, can_export flag
  - Expandable details with severity-coded issues and recommendations
  - Quick action buttons: "Review Queue" and "Chain of Custody"
  - Integrated into TaxSummaryDashboard.js
- [x] **Bulk Resolution Service** (`review_queue_enhancements.py`)
  - POST `/api/custody/review-queue/bulk-resolve` - Resolve multiple items at once
  - POST `/api/custody/review-queue/bulk-resolve-category/{category}` - Resolve by category
  - Supports decisions: "mine" (creates linkage) or "external" (creates tax event)
- [x] **Wallet Link Suggestion Engine**
  - GET `/api/custody/review-queue/suggestions` - Analyzes patterns
  - Suggests frequent destinations as potential user wallets
  - Detects round-trip patterns and exchange patterns
  - Confidence scoring: high, medium, low
- [x] **Review Queue Grouping Service**
  - GET `/api/custody/review-queue/grouped` - Groups by destination/source/asset/amount
  - Provides actionable groups with bulk action recommendations
- [x] Add validation status to API responses

### Phase 23: Beta Account Validation Harness (Completed - Mar 27, 2026)
- [x] **Beta Validation Harness** (`beta_validation_harness.py`) - ~1000 lines
  - Runs selected beta user accounts through full tax pipeline
  - Generates human-reviewable validation reports before Form 8949 export

- [x] **Report Components**:
  - `ClassificationSummary`: Transaction classification breakdown by type and asset
  - `LotReconciliationSummary`: Lot tracking with FIFO, cost basis by asset
  - `DisposalSummary`: Total proceeds, cost basis, gain/loss (short/long-term)
  - `InvariantCheckResult`: Pass/fail for each invariant with affected assets
  - `ValidationIssue`: Highlighted problems with severity levels

- [x] **Invariant Checks**:
  - Balance Reconciliation (starting + acquisitions - disposals = ending)
  - No Orphan Disposals (disposed qty <= acquired qty per asset)
  - Cost Basis Validity (no negative cost basis)
  - No Double Disposal (no duplicate sell tx_ids)
  - Classification Completeness (no unknown classifications)
  - Review Queue Resolved (no pending review items)

- [x] **Issue Detection & Highlighting**:
  - CRITICAL: Orphan disposals, balance mismatches
  - HIGH: Unresolved chain breaks, unknown classifications
  - MEDIUM: Missing price data (zero cost basis acquisitions)
  - LOW: Minor data quality issues

- [x] **Validation Status Logic**:
  - `invalid` + blocked: Critical issues or failed invariants
  - `needs_review` + blocked: Unresolved review queue items
  - `needs_review` + exportable: High issues (warning only)
  - `valid` + exportable: All checks passed

- [x] **New API Endpoints**:
  - POST `/api/custody/beta/validate` - Full account validation with report generation
  - POST `/api/custody/beta/validate-batch` - Validate multiple accounts
  - GET `/api/custody/beta/validation-report/{user_id}` - Retrieve saved report
  - GET `/api/custody/beta/pre-export-check` - Quick blocking issues check

- [x] **Report Output**:
  - JSON format: Full structured data for programmatic use
  - Human-readable text: Formatted report for manual QA review
  - Files saved to `/app/test_reports/beta_validation_{user_id}_{tax_year}.{json,txt}`

### Phase 22: Tax Validation and Invariant Enforcement Layer (Completed - Mar 27, 2026)
- [x] **New Tax Validation Service** (`tax_validation_service.py`) - 940 lines
  - Comprehensive validation layer ensuring all generated tax records are accurate, internally consistent, and auditable
  - Prevents silent errors by enforcing strict validation rules before any tax output is finalized

- [x] **Transaction Classification System**:
  - Formal enum: `acquisition`, `disposal`, `internal_transfer`, `income`, `unknown`
  - Auto-classification based on transaction type and chain status
  - Confidence scoring (0.0-1.0) for each classification
  - Unknown/low-confidence transactions routed to review queue
  - `validate_classification()` enriches transactions with classification metadata

- [x] **Cost Basis Engine with Strict Lot Tracking**:
  - FIFO lot tracking with: acquisition date, quantity, remaining quantity, cost basis per unit
  - `create_lot()` - Creates tax lots with validation (no negative cost basis, positive quantity required)
  - `dispose_from_lots()` - FIFO matching with lot tracking and double-spend prevention
  - Constraint enforcement: cost basis >= 0, disposed qty <= acquired qty

- [x] **Invariant Checks (Mandatory Before Export)**:
  - **Balance Reconciliation**: `starting_balance + acquisitions - disposals = ending_balance`
  - **Cost Basis Conservation**: Internal transfers cannot change total cost basis
  - **No Double Spend**: Each unit of asset can only be disposed once (unit ID tracking)
  - **No Orphan Disposals**: Every disposal must have acquisition source, cost basis, timestamp, price
  - `run_all_invariant_checks()` runs comprehensive validation suite

- [x] **Form 8949 Pre-Export Validation**:
  - `validate_form_8949_record()` - Validates individual records (required fields, no negatives, gain/loss calc)
  - `validate_form_8949_export()` - Full export validation with totals reconciliation
  - Export blocked if validation fails with detailed error messages
  - Updated `/api/custody/export-form-8949` with `validate=true` parameter (default)

- [x] **Recompute Logic**:
  - `trigger_full_recompute()` - Clears all computed state on data changes
  - Triggered by: wallet linkage changes, classification changes, transaction data changes
  - No partial updates allowed - ensures consistency

- [x] **Full Audit Trail**:
  - Every lot creation, disposal, and validation logged with timestamp
  - `get_audit_trail()` retrieves chronological action history
  - Supports explainability and reproducibility requirements

- [x] **New API Endpoints**:
  - POST `/api/custody/validate/transactions` - Classify and validate transaction batch
  - POST `/api/custody/validate/invariants` - Run all invariant checks
  - GET `/api/custody/validate/account-status` - Check if account can export taxes
  - POST `/api/custody/validate/recompute` - Trigger full tax recalculation
  - GET `/api/custody/validate/lot-status/{asset}` - View lot status for asset
  - GET `/api/custody/validate/audit-trail` - Retrieve audit trail entries

- [x] **Comprehensive Test Suite** - 65 total tests (all passing):
  - **Basic Tests** (`test_tax_validation.py`) - 37 tests
  - **Advanced Test Suite** (`test_tax_validation_comprehensive.py`) - 28 tests:
    - 10 Core Passing Scenarios (buy/sell, internal transfer, bridge, FIFO, partial disposal, fees, CSV import, recompute, export consistency)
    - 10 Failure Scenario Tests (internal as sale, external as internal, duplicate disposal, cost basis change, orphan disposal, wrong quantity, slippage, unknown leaking, no recompute, invalid export)
    - 5 Invariant Checks (balance reconciliation, cost basis conservation, no double disposal, no orphan, deterministic export)
    - 2 Validation Enforcement Tests (invalid blocks, warning allows)
    - 1 QA Summary Generator
  - **QA Summary Output**: `/app/test_reports/tax_validation_qa_summary.json`

### Completed Refactoring (Mar 19, 2026)
- [x] **Server.py Refactoring** - Split 4,375-line server.py into 10 modular route files:
  - `routes/auth.py` (263 lines) - Authentication, login, register, password reset
  - `routes/payments.py` (439 lines) - Stripe checkout, webhooks, status
  - `routes/wallets.py` (438 lines) - Wallet analysis, saved wallets, chains
  - `routes/tax.py` (781 lines) - Form 8949, Schedule D, categories, unified tax
  - `routes/affiliates.py` (262 lines) - Affiliate registration, validation, admin
  - `routes/exchanges.py` (848 lines) - CSV import, API connections, Coinbase sync
  - `routes/custody.py` (199 lines) - Chain of custody analysis, PDF export
  - `routes/support.py` (119 lines) - AI chat, contact form
  - `routes/dependencies.py` (116 lines) - Shared auth, DB, utilities
  - `routes/models.py` (269 lines) - Pydantic models
  - New `server.py` (528 lines) - Main app, router includes, legacy aliases
- [x] Total route code: 3,734 lines across 10 modules (better maintainability)
- [x] All API endpoints verified working after refactoring
- [x] Backwards compatibility maintained via alias routes

### Phase 24: Unknown Transaction Reduction System (Completed - Mar 27, 2026)
- [x] **UnknownTransactionClassifier** (`unknown_transaction_classifier.py`) - ~1000 lines
  - Auto-classifies high-confidence unknown transactions using pattern detection
  - Reduces manual review work by identifying internal vs external transfers
  
- [x] **Pattern Detection Engine**:
  - Groups transactions by destination wallet (detects repeated sends to same address)
  - Groups transactions by source wallet (detects repeated receives from same address)
  - Groups transactions by asset (learns from historical user decisions)
  - Confidence scoring based on pattern strength and known wallet matches
  
- [x] **Auto-Suggestion Engine**:
  - Confidence levels: `auto_apply` (>0.95), `suggest` (0.70-0.95), `unresolved` (<0.70)
  - Classification types: internal_transfer, external_transfer, swap, bridge, deposit, withdrawal, buy, sell, reward, staking
  - Matches against known exchange/DEX/bridge keywords
  - Learns from user's own wallet linkages
  
- [x] **Bulk Classification**:
  - Classify all transactions matching a pattern in one operation
  - Classify all transactions to same destination wallet
  - Batch processing with rollback support
  
- [x] **Auto-Apply Threshold**:
  - Transactions with >95% confidence can be auto-classified
  - Dry-run mode to preview before applying
  - Batch ID tracking for reversal
  
- [x] **Feedback Loop**:
  - User accept/reject decisions recorded in `classification_feedback` collection
  - Historical decisions improve future suggestion accuracy
  - Per-pattern and per-destination learning
  
- [x] **Metrics Dashboard**:
  - Current unknown transaction count
  - Auto-classification rate
  - Suggestion accuracy rate
  - Daily classification stats
  
- [x] **API Endpoints** (`routes/classification_routes.py`):
  - GET `/api/custody/classify/analyze` - Analyze unknowns, detect patterns, generate suggestions
  - POST `/api/custody/classify/auto-apply` - Auto-classify >95% confidence (dry_run support)
  - GET `/api/custody/classify/metrics` - Classification performance over time
  - GET `/api/custody/classify/patterns` - Get detected patterns for bulk actions
  - POST `/api/custody/classify/by-pattern` - Bulk classify by pattern ID
  - POST `/api/custody/classify/by-destination` - Bulk classify by destination wallet
  - POST `/api/custody/classify/decide` - Accept/reject suggestion (feedback loop)
  - GET `/api/custody/classify/batches` - List classification batches for rollback
  - POST `/api/custody/classify/rollback/{batch_id}` - Reverse a classification batch
  - GET `/api/custody/classify/suggestions/{tx_id}` - Get suggestion for specific transaction
  
- [x] **Frontend UI** (`components/UnknownTransactionClassifier.js`):
  - Stats overview: unknown count, auto-classifiable, suggested, unresolved
  - Progress bar showing classification coverage
  - One-click auto-classify all high-confidence transactions
  - Tab navigation: Suggestions, Patterns, Metrics, Batches
  - Confidence filter dropdown
  - Pattern expansion with bulk classify button
  - Rollback functionality for batches
  - Integrated into TaxSummaryDashboard via ValidationStatusPanel
  
- [x] **Test Suite**: 32 tests passing (iteration 27)

### Phase 25: Classification Effectiveness Metrics (Completed - Mar 27, 2026)
- [x] **ClassificationEffectivenessService** (`classification_effectiveness_service.py`) - ~600 lines
  - Measures whether classifier improves tax readiness without bad classifications
  - Tracks before/after account state snapshots
  
- [x] **Account-Level Metrics Tracked**:
  - unknown_count_before / unknown_count_after
  - auto_classified_count
  - user_confirmed_count / user_rejected_count
  - rollback_count
  - validation_status_before / validation_status_after
  - can_export_before / can_export_after
  - export_readiness_improved flag
  
- [x] **Precision Metrics by Confidence Bucket**:
  - High (>0.95): Auto-apply threshold
  - Medium-High (0.85-0.95): Strong suggestion
  - Medium (0.70-0.85): Moderate confidence
  - Low (<0.70): Unresolved
  
- [x] **Metrics by Classification Type**:
  - internal_transfer, external_transfer, swap, bridge
  - deposit, withdrawal, buy, sell, reward, staking
  - Tracks total, auto_classified, confirmed, rejected, precision per type
  
- [x] **API Endpoints**:
  - GET `/api/custody/classify/effectiveness` - Full effectiveness summary
  - GET `/api/custody/classify/effectiveness/confidence-buckets` - Precision by confidence
  - GET `/api/custody/classify/effectiveness/classification-types` - Metrics by type
  - POST `/api/custody/classify/effectiveness/snapshot` - Capture before/after snapshots
  - GET `/api/custody/classify/effectiveness/admin/summary` - Aggregated all-accounts view
  
- [x] **Frontend UI** (`ValidationStatusPanel.js` enhanced):
  - Effectiveness summary panel (expandable)
  - Stats: Unknowns Reduced, Auto-Classified, User Confirmed, Precision %
  - Export Readiness Improvement indicator
  - Precision breakdown by confidence bucket
  - Classification type distribution
  - Rollback warning display
  
- [x] **Integration with Classifier**:
  - Auto-records effectiveness events on classification
  - Records user feedback (accept/reject) for precision tracking
  - Records rollback events
  
- [x] **Test Suite**: 24 new tests + 32 regression = 56 tests passing (iteration 28)


### Phase 26: Tax Summary API Fix & Manual Acquisition Entry (Completed - Mar 29, 2026)

#### P0: 2025 Tax Summary Datetime Fix
- [x] **Root Cause**: `unified_tax_service.py` - String timestamps from `derived_proceeds` transactions were being parsed as timezone-naive datetimes, causing comparison errors with timezone-aware datetimes
- [x] **Fix**: Enhanced timestamp normalization in `normalize_exchange_transaction()` to ensure all parsed datetimes (from strings or datetime objects) are timezone-aware (UTC)
- [x] **Result**: 2025 Tax Summary now returns proper data:
  - 311 realized gains (was 0)
  - $3,259.54 total realized gain
  - $3,113.36 short-term gains
  - $146.18 long-term gains
  - 360 buys, 146 sells processed

#### P1: Manual Acquisition Entry (Orphan Disposal Fix)
- [x] **New API Endpoints** (`/app/backend/routes/exchanges.py`):
  - `POST /api/exchanges/manual-acquisition` - Add manual buy record
    - Required: asset, amount, price_usd, timestamp
    - Optional: source, notes
    - Validates: positive amount, non-negative price, valid timestamp format
  - `GET /api/exchanges/orphan-disposal-summary` - Get assets with orphan disposals
    - Returns shortfall amounts, current prices, recommendations
    - Sorted by USD shortfall (largest first)
  - `GET /api/exchanges/manual-acquisitions` - List all manual entries
  - `DELETE /api/exchanges/manual-acquisition/{tx_id}` - Remove manual entry

- [x] **Frontend UI** (`AddDataModal.js`):
  - New "Manual" tab in Add Data modal
  - `ManualAcquisitionForm` component (~170 lines)
  - Quick-fill buttons for orphan assets (USDC, ALGO, SOL, FLR, AXL, BCH)
  - Auto-populates asset, amount, and date from orphan data
  - Form validation with error messages
  - Success feedback with data refresh

- [x] **Orphan Disposal Summary**: User has 6 assets with orphan disposals:
  - USDC: ~41,253 shortfall
  - ALGO: ~255,828 shortfall
  - SOL: ~6.90 shortfall
  - FLR: ~47,516 shortfall
  - AXL: ~760 shortfall
  - BCH: ~3.17 shortfall

- [x] **Test Suite**: 15 new tests passing (iteration 30)

## Current Validation Status
- **46 Blocking Issues** (orphan disposals)
- **0 Unresolved Reviews**
- **Export Blocked** until orphan disposals resolved via manual acquisition entries

## Upcoming Tasks (P1/P2)
- Import missing USDC/XLM/ALGO acquisitions (user must add via Manual Entry tab)
- Frontend UI for Regression Fixture Management
- DeFi Position Tracking
- NFT Portfolio Tracking
- Refactor `ChainOfCustodyModal.js` and `App.js` into smaller components

## Test Credentials
- Email: `mobiletest@test.com`
- Password: `test123456`
- UUID: `6f9b5c58-a65b-42c4-afa6-f206bbb4876c`

## Test Reports
- Iteration 30: `/app/test_reports/iteration_30.json` (15 tests - Manual Acquisition)
- Iteration 29: `/app/test_reports/iteration_29.json` (21 tests - Tax Regression)
- Iteration 28: `/app/test_reports/iteration_28.json` (56 tests - Classification Effectiveness)

