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

### Phase 5: Exchange API Integration (Completed - Mar 5, 2026)
- [x] Coinbase OAuth2 integration framework
- [x] Binance API key authentication
- [x] Exchange connection management (connect/disconnect)
- [x] Transaction sync from exchanges
- [x] Unified transaction format across exchanges
- [x] Exchange transactions listing with filters
- [x] Transaction summary calculation
- [x] ExchangeModal UI for managing connections
- [x] Free user restriction (Unlimited only)

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

### Future Features (P2-P5)
- [ ] DeFi & NFT Integration (liquidity pools, staking, NFT valuations)
- [ ] Additional blockchains (Avalanche, Optimism, Base)
- [ ] Data visualizations (charts, graphs)
- [ ] Mobile responsiveness improvements
- [ ] Tax loss harvesting suggestions
- [ ] Refactor App.js into smaller components (useAnalysis hook created)
- [ ] Refactor multi_chain_service.py into separate chain modules

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
