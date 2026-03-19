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

## Backlog
- [ ] **CoinGecko Rate Limit Improvement** - Add paid API key support, better caching, or alternative price provider to ensure historical prices are always fetched accurately
