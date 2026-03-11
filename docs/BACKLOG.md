# Crypto Bag Tracker - Product Backlog

## Overview

This document contains the prioritized product backlog for future development. Items are organized by priority (P0-P3) and estimated effort.

**Effort Scale:**
- XS: < 1 day
- S: 1-2 days
- M: 3-5 days
- L: 1-2 weeks
- XL: 2+ weeks

---

## P0 - Critical (Next Sprint)

### BL-001: Password Reset Flow
**Effort:** S | **Type:** Feature | **Epic:** Authentication

**Description:**  
Implement email-based password reset functionality.

**Requirements:**
- Send reset link via email (SendGrid/SES)
- Token expires after 24 hours
- New password validation
- Confirmation email after reset

**Technical Notes:**
- Add `password_reset_tokens` collection in MongoDB
- Create `/api/auth/forgot-password` and `/api/auth/reset-password` endpoints
- Use secure random tokens

---

### BL-002: Email Notifications
**Effort:** M | **Type:** Feature | **Epic:** User Experience

**Description:**  
Send transactional emails for key events.

**Requirements:**
- Welcome email on registration
- Subscription confirmation
- Subscription renewal reminder (7 days before)
- Password reset emails
- Support ticket confirmation

**Technical Notes:**
- Integrate SendGrid or AWS SES
- Create email templates
- Add email preferences to user settings

---

### BL-003: Error Monitoring & Logging
**Effort:** S | **Type:** Infrastructure | **Epic:** Operations

**Description:**  
Implement proper error tracking and monitoring.

**Requirements:**
- Integrate Sentry for error tracking
- Structured logging for backend
- Alert on critical errors
- Performance monitoring

**Technical Notes:**
- Add Sentry SDK to backend and frontend
- Configure log levels
- Set up Slack/email alerts

---

## P1 - High Priority (This Quarter)

### BL-004: Portfolio History Charts
**Effort:** L | **Type:** Feature | **Epic:** Analytics

**Description:**  
Show portfolio value over time with interactive charts.

**Requirements:**
- Daily portfolio snapshots
- Line chart visualization
- Time range selector (1W, 1M, 3M, 1Y, All)
- Compare against BTC/ETH performance
- Export chart as image

**Technical Notes:**
- Store daily snapshots in MongoDB
- Use Recharts or Chart.js
- Background job for daily calculations

---

### BL-005: DeFi Position Tracking
**Effort:** XL | **Type:** Feature | **Epic:** Portfolio

**Description:**  
Track and value DeFi positions (liquidity pools, staking).

**Requirements:**
- Detect LP tokens in wallets
- Fetch underlying token values
- Track staking positions
- Include in portfolio total
- Show APY where available

**Technical Notes:**
- Integrate DeFiLlama API
- Support major protocols (Uniswap, Aave, Curve)
- Complex position valuation logic

---

### BL-006: NFT Portfolio
**Effort:** L | **Type:** Feature | **Epic:** Portfolio

**Description:**  
Display NFT holdings with valuations.

**Requirements:**
- Detect NFTs in EVM wallets
- Show NFT images and metadata
- Estimate floor price value
- Include in portfolio total
- Collection grouping

**Technical Notes:**
- Integrate OpenSea/Reservoir API
- Image caching/CDN
- Floor price as default valuation

---

### BL-007: Tax Loss Harvesting Suggestions
**Effort:** M | **Type:** Feature | **Epic:** Tax

**Description:**  
Suggest assets to sell for tax loss harvesting.

**Requirements:**
- Identify assets with unrealized losses
- Calculate potential tax savings
- Warn about wash sale rules
- Sort by largest loss opportunity

**Technical Notes:**
- Use existing tax lot data
- Calculate at current prices
- 30-day wash sale window check

---

### BL-008: Unified Tax Report (Wallet + Exchange)
**Effort:** M | **Type:** Feature | **Epic:** Tax

**Description:**  
Generate Form 8949 combining wallet and exchange data.

**Requirements:**
- Merge all data sources
- Deduplicate transfers
- Single unified export
- Source labeling in report

**Technical Notes:**
- Extend existing tax service
- Transfer detection between sources
- Data source column in export

---

### BL-009: Auto-Import Transaction History
**Effort:** M | **Type:** Feature | **Epic:** Exchange

**Description:**  
Automatically fetch transaction history via exchange APIs.

**Requirements:**
- Fetch historical trades
- Fetch deposits/withdrawals
- Sync on schedule (daily)
- Manual sync button

**Technical Notes:**
- Extend multi_exchange_service.py
- Handle API pagination
- Rate limiting per exchange

---

### BL-010: Two-Factor Authentication
**Effort:** M | **Type:** Feature | **Epic:** Security

**Description:**  
Add optional 2FA for account security.

**Requirements:**
- TOTP (Google Authenticator compatible)
- Setup flow with QR code
- Backup codes
- Remember device option

**Technical Notes:**
- Use pyotp library
- Store encrypted secret
- Add 2FA check to login flow

---

## P2 - Medium Priority (Next Quarter)

### BL-011: Bulk Wallet Import
**Effort:** S | **Type:** Feature | **Epic:** Wallet

**Description:**  
Import multiple wallet addresses at once.

**Requirements:**
- CSV upload with addresses
- Optional chain and nickname columns
- Batch analysis with progress
- Error report for invalid addresses

---

### BL-012: Custom Tax Rules
**Effort:** M | **Type:** Feature | **Epic:** Tax

**Description:**  
Allow users to define custom categorization rules.

**Requirements:**
- Rule builder UI
- Conditions: address, amount, date range
- Actions: categorize, exclude
- Apply to future imports

---

### BL-013: Recurring Analysis
**Effort:** S | **Type:** Feature | **Epic:** Wallet

**Description:**  
Schedule automatic wallet re-analysis.

**Requirements:**
- Set analysis frequency (daily, weekly)
- Email summary of changes
- Highlight new transactions
- Update portfolio snapshots

---

### BL-014: Mobile App (React Native)
**Effort:** XL | **Type:** Feature | **Epic:** Platform

**Description:**  
Native mobile app for iOS and Android.

**Requirements:**
- Portfolio overview
- Push notifications
- Biometric authentication
- Offline mode for viewing

---

### BL-015: API for Third Parties
**Effort:** L | **Type:** Feature | **Epic:** Platform

**Description:**  
Public API for integrations.

**Requirements:**
- API key management
- Rate limiting
- Documentation (OpenAPI)
- Webhook support

---

### BL-016: White-Label for Accountants
**Effort:** XL | **Type:** Feature | **Epic:** Business

**Description:**  
Multi-tenant version for accounting firms.

**Requirements:**
- Custom branding
- Client management
- Bulk operations
- Firm-level reporting

---

### BL-017: CPA Collaboration
**Effort:** M | **Type:** Feature | **Epic:** Tax

**Description:**  
Share read-only access with tax professionals.

**Requirements:**
- Generate share link
- Expiring access
- Activity log
- Revoke access

---

### BL-018: International Tax Support
**Effort:** XL | **Type:** Feature | **Epic:** Tax

**Description:**  
Support tax calculations for other countries.

**Requirements:**
- UK CGT calculations
- EU reporting formats
- Currency conversion
- Country-specific rules

---

## P3 - Low Priority (Future)

### BL-019: Social Login
**Effort:** M | **Type:** Feature | **Epic:** Authentication

**Description:**  
Login with Google, Apple, etc.

---

### BL-020: Dark/Light Theme Toggle
**Effort:** S | **Type:** Feature | **Epic:** UX

**Description:**  
User preference for color scheme.

---

### BL-021: Multi-Language Support
**Effort:** L | **Type:** Feature | **Epic:** Platform

**Description:**  
Translate UI to Spanish, German, etc.

---

### BL-022: Family/Team Plan
**Effort:** M | **Type:** Feature | **Epic:** Business

**Description:**  
Shared subscription for multiple users.

---

### BL-023: Hardware Wallet Direct Connect
**Effort:** L | **Type:** Feature | **Epic:** Wallet

**Description:**  
Connect Ledger/Trezor directly to fetch addresses.

---

### BL-024: Telegram Bot
**Effort:** M | **Type:** Feature | **Epic:** Platform

**Description:**  
Portfolio alerts and quick lookups via Telegram.

---

### BL-025: Browser Extension
**Effort:** L | **Type:** Feature | **Epic:** Platform

**Description:**  
Chrome extension for quick wallet analysis.

---

## Technical Debt

### TD-001: Refactor App.js
**Effort:** L | **Type:** Tech Debt | **Priority:** P1

**Description:**  
Break down App.js (1200+ lines) into smaller components.

**Components to extract:**
- WalletInputCard
- AnalysisResults
- StatisticsGrid
- TransactionTable
- Navigation

---

### TD-002: Refactor server.py
**Effort:** L | **Type:** Tech Debt | **Priority:** P1

**Description:**  
Break down server.py (3700+ lines) into route modules.

**Modules to create:**
- routes/auth.py
- routes/wallet.py
- routes/tax.py
- routes/exchange.py
- routes/custody.py
- routes/payments.py

---

### TD-003: Add Unit Tests
**Effort:** M | **Type:** Tech Debt | **Priority:** P1

**Description:**  
Improve test coverage for backend services.

**Areas to cover:**
- Tax calculations (FIFO)
- Chain analyzers
- CSV parsers
- API endpoints

---

### TD-004: Deprecate multi_chain_service v1
**Effort:** S | **Type:** Tech Debt | **Priority:** P2

**Description:**  
Remove v1 service, use v2 exclusively.

---

### TD-005: Database Indexing
**Effort:** S | **Type:** Tech Debt | **Priority:** P2

**Description:**  
Add indexes for frequently queried fields.

**Indexes needed:**
- users.email
- exchange_transactions.user_id
- custody_analyses.user_id
- transaction_categories.user_id

---

## Bug Fixes

### BF-001: CoinGecko Rate Limiting
**Effort:** S | **Type:** Bug | **Priority:** P1

**Description:**  
Improve handling of CoinGecko rate limits.

**Solution:**
- Implement caching layer
- Use Pro API for production
- Better fallback price handling

---

### BF-002: Large Wallet Performance
**Effort:** M | **Type:** Bug | **Priority:** P2

**Description:**  
Analysis times out for wallets with 10,000+ transactions.

**Solution:**
- Pagination during analysis
- Background job with progress
- Incremental updates

---

## Completed (Archive)

| ID | Title | Completed |
|----|-------|-----------|
| BL-100 | Mobile Responsive UI | Mar 10, 2026 |
| BL-101 | Chain of Custody | Mar 8, 2026 |
| BL-102 | PDF Export | Mar 10, 2026 |
| BL-103 | Exchange API Connect | Mar 10, 2026 |
| BL-104 | AI Support Assistant | Mar 10, 2026 |
| BL-105 | Coinbase OAuth | Mar 10, 2026 |

---

*Document Version: 2.1*  
*Last Updated: March 10, 2026*  
*Total Items: 30*  
*P0: 3 | P1: 7 | P2: 8 | P3: 7 | Tech Debt: 5*
