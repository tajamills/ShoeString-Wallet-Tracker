# Crypto Bag Tracker - User Stories

## Overview

This document contains user stories organized by epic/feature area. Each story follows the format:
> As a [user type], I want to [action], so that [benefit].

Stories include acceptance criteria and are tagged with priority (P0-P3) and status.

---

## Epic 1: User Authentication & Onboarding

### US-1.1: User Registration
**Priority:** P0 | **Status:** Complete

> As a new user, I want to create an account with email and password, so that I can access the platform.

**Acceptance Criteria:**
- [x] Email validation (valid format, unique)
- [x] Password requirements (6+ characters)
- [x] Success redirects to dashboard
- [x] Error messages for invalid input

---

### US-1.2: User Login
**Priority:** P0 | **Status:** Complete

> As a returning user, I want to log in with my credentials, so that I can access my saved data.

**Acceptance Criteria:**
- [x] Email/password authentication
- [x] JWT token generation
- [x] Remember me functionality
- [x] Error messages for invalid credentials

---

### US-1.3: Terms of Service
**Priority:** P0 | **Status:** Complete

> As a new user, I want to review and accept terms of service, so that I understand my obligations.

**Acceptance Criteria:**
- [x] TOS modal appears after first login
- [x] Cannot dismiss without accepting
- [x] TOS acceptance saved to database
- [x] Timestamp recorded

---

### US-1.4: Password Reset
**Priority:** P1 | **Status:** Backlog

> As a user who forgot my password, I want to reset it via email, so that I can regain access.

**Acceptance Criteria:**
- [ ] Send reset link to email
- [ ] Token expires after 24 hours
- [ ] New password validation
- [ ] Confirmation email sent

---

## Epic 2: Wallet Analysis

### US-2.1: Analyze Single Wallet
**Priority:** P0 | **Status:** Complete

> As a user, I want to analyze a wallet address, so that I can see my transaction history and balance.

**Acceptance Criteria:**
- [x] Input field for wallet address
- [x] Chain selection dropdown
- [x] Address validation
- [x] Display balance, transactions, totals
- [x] Loading state during analysis

---

### US-2.2: Multi-Chain Support
**Priority:** P0 | **Status:** Complete

> As an Unlimited user, I want to analyze wallets on multiple blockchains, so that I can track all my holdings.

**Acceptance Criteria:**
- [x] Support 12 blockchains
- [x] Chain-specific address validation
- [x] Unified transaction format
- [x] Chain icons in UI

---

### US-2.3: USD Valuation
**Priority:** P0 | **Status:** Complete

> As an Unlimited user, I want to see my holdings valued in USD, so that I understand my portfolio worth.

**Acceptance Criteria:**
- [x] Current price fetched from CoinGecko
- [x] Portfolio total in USD
- [x] Transaction values in USD
- [x] Fallback prices when rate limited

---

### US-2.4: Save Favorite Wallets
**Priority:** P1 | **Status:** Complete

> As a user, I want to save wallet addresses with nicknames, so that I can quickly re-analyze them.

**Acceptance Criteria:**
- [x] Save button on analysis results
- [x] Custom nickname field
- [x] Saved wallets list in sidebar
- [x] One-click re-analysis

---

### US-2.5: Bitcoin xPub Support
**Priority:** P1 | **Status:** Complete

> As an Unlimited user with a hardware wallet, I want to enter my xPub key, so that all my Bitcoin addresses are analyzed together.

**Acceptance Criteria:**
- [x] Accept xPub/yPub/zPub format
- [x] Derive all used addresses
- [x] Aggregate balance and transactions
- [x] Clear labeling in results

---

## Epic 3: Tax Calculations

### US-3.1: FIFO Cost Basis
**Priority:** P0 | **Status:** Complete

> As an Unlimited user, I want my cost basis calculated using FIFO, so that I can determine my capital gains.

**Acceptance Criteria:**
- [x] Track all buy transactions as tax lots
- [x] Match sells to oldest lots first
- [x] Calculate gain/loss per sale
- [x] Display tax summary

---

### US-3.2: Realized vs Unrealized Gains
**Priority:** P0 | **Status:** Complete

> As a user, I want to see both realized and unrealized gains, so that I understand my tax liability.

**Acceptance Criteria:**
- [x] Realized gains = sold assets
- [x] Unrealized gains = current holdings
- [x] Separate displays for each
- [x] USD values for both

---

### US-3.3: Short-term vs Long-term
**Priority:** P0 | **Status:** Complete

> As a user, I want gains classified by holding period, so that I know which tax rate applies.

**Acceptance Criteria:**
- [x] Short-term = held < 1 year
- [x] Long-term = held >= 1 year
- [x] Separate totals for each
- [x] Classification in export

---

### US-3.4: Form 8949 Export
**Priority:** P0 | **Status:** Complete

> As an Unlimited user, I want to export Form 8949 data, so that I can file my taxes correctly.

**Acceptance Criteria:**
- [x] CSV format matching IRS requirements
- [x] All required columns present
- [x] Filter by tax year
- [x] Filter by short/long-term

---

### US-3.5: Schedule D Summary
**Priority:** P1 | **Status:** Complete

> As an Unlimited user, I want a Schedule D summary, so that I have totals for my tax return.

**Acceptance Criteria:**
- [x] Aggregate short-term gains/losses
- [x] Aggregate long-term gains/losses
- [x] Text and CSV export options
- [x] Tax year selection

---

### US-3.6: Transaction Categorization
**Priority:** P1 | **Status:** Complete

> As a user, I want to categorize transactions, so that non-taxable events are handled correctly.

**Acceptance Criteria:**
- [x] Categories: trade, income, gift, airdrop, staking, mining
- [x] Manual categorization per transaction
- [x] Batch categorization with rules
- [x] Auto-categorization detection

---

### US-3.7: Tax Year Filtering
**Priority:** P1 | **Status:** Complete

> As a user, I want to filter results by tax year, so that I can focus on one filing at a time.

**Acceptance Criteria:**
- [x] Year selector (2020 - current)
- [x] All reports filter by year
- [x] Default to current year
- [x] Year shown in exports

---

## Epic 4: Exchange Integration

### US-4.1: CSV Import
**Priority:** P0 | **Status:** Complete

> As an Unlimited user, I want to import transaction CSVs from exchanges, so that I can include all my trades.

**Acceptance Criteria:**
- [x] Drag-and-drop file upload
- [x] Auto-detect exchange format
- [x] Support 6 major exchanges
- [x] Preview before import
- [x] Error handling for bad files

---

### US-4.2: Multi-Format Coinbase Support
**Priority:** P1 | **Status:** Complete

> As a Coinbase user, I want both old and new CSV formats supported, so that any export works.

**Acceptance Criteria:**
- [x] Classic format detection
- [x] Modern format detection
- [x] Heuristic fallback detection
- [x] Stablecoin handling

---

### US-4.3: Exchange API Connection
**Priority:** P1 | **Status:** Complete

> As an Unlimited user, I want to connect exchanges via API, so that I can auto-import my addresses.

**Acceptance Criteria:**
- [x] Read-only access only
- [x] API key encryption at rest
- [x] Support 8 exchanges
- [x] Disconnect option

---

### US-4.4: Coinbase OAuth
**Priority:** P1 | **Status:** Complete

> As a Coinbase user, I want to connect via OAuth, so that I don't have to manage API keys.

**Acceptance Criteria:**
- [x] OAuth 2.0 flow
- [x] Read-only scopes only
- [x] Token refresh handling
- [x] Disconnect option

---

### US-4.5: Exchange-Only Tax Calculator
**Priority:** P1 | **Status:** Complete

> As a user who only trades on exchanges, I want to calculate taxes without wallet analysis, so that I can get reports faster.

**Acceptance Criteria:**
- [x] Standalone calculator from CSVs
- [x] FIFO calculations
- [x] Form 8949 export
- [x] Stablecoin exclusion

---

## Epic 5: Chain of Custody

### US-5.1: Trace Asset Origins
**Priority:** P0 | **Status:** Complete

> As an Unlimited user, I want to trace where my crypto came from, so that I can prove its source.

**Acceptance Criteria:**
- [x] Input wallet address
- [x] Recursive transaction tracing
- [x] Stop at exchanges, DEXs, dormant wallets
- [x] Display full chain

---

### US-5.2: Flow Graph Visualization
**Priority:** P1 | **Status:** Complete

> As a user, I want to see asset flow as a visual graph, so that I can understand the path easily.

**Acceptance Criteria:**
- [x] Interactive node graph
- [x] Color-coded by type
- [x] Zoom and pan controls
- [x] Legend explaining colors

---

### US-5.3: PDF Export
**Priority:** P1 | **Status:** Complete

> As a user, I want to export custody analysis as PDF, so that I can share it with auditors.

**Acceptance Criteria:**
- [x] Professional formatting
- [x] Title page with metadata
- [x] Executive summary
- [x] Full transaction chain
- [x] Disclaimer included

---

### US-5.4: Coinbase Auto-Import for Custody
**Priority:** P2 | **Status:** Complete

> As a Coinbase user, I want to auto-import my addresses for custody analysis, so that I don't have to enter them manually.

**Acceptance Criteria:**
- [x] Connect Coinbase option
- [x] Fetch all addresses
- [x] Select address for analysis
- [x] Manual entry alternative

---

## Epic 6: Payments & Subscriptions

### US-6.1: Upgrade to Unlimited
**Priority:** P0 | **Status:** Complete

> As a free user, I want to upgrade to Unlimited, so that I can access all features.

**Acceptance Criteria:**
- [x] Clear pricing display
- [x] Stripe checkout integration
- [x] Immediate access after payment
- [x] Confirmation email

---

### US-6.2: Apply Affiliate Code
**Priority:** P1 | **Status:** Complete

> As a user with a referral code, I want to apply it at checkout, so that I get a discount.

**Acceptance Criteria:**
- [x] Code input field
- [x] Validation feedback
- [x] $10 discount applied
- [x] Affiliate credited

---

### US-6.3: Cancel Subscription
**Priority:** P1 | **Status:** Complete

> As a paying user, I want to cancel my subscription, so that I'm not charged again.

**Acceptance Criteria:**
- [x] Access to billing portal
- [x] Cancel at period end option
- [x] Confirmation message
- [x] Access until period ends

---

### US-6.4: Affiliate Dashboard
**Priority:** P2 | **Status:** Complete

> As an affiliate, I want to see my referral stats, so that I can track my earnings.

**Acceptance Criteria:**
- [x] Unique affiliate code
- [x] Referral count
- [x] Earnings total
- [x] Shareable link

---

## Epic 7: Support & Help

### US-7.1: AI Support Assistant
**Priority:** P1 | **Status:** Complete

> As a user, I want to chat with an AI assistant, so that I can get instant help.

**Acceptance Criteria:**
- [x] Chat interface in modal
- [x] Suggested questions
- [x] Conversation history
- [x] Tax-specific knowledge

---

### US-7.2: Contact Form
**Priority:** P1 | **Status:** Complete

> As a user, I want to submit a support request, so that I can get human help for complex issues.

**Acceptance Criteria:**
- [x] Name, email, message fields
- [x] Submission confirmation
- [x] Email notification to support

---

### US-7.3: Request New Chain
**Priority:** P2 | **Status:** Complete

> As an Unlimited user, I want to request support for a new blockchain, so that I can analyze all my wallets.

**Acceptance Criteria:**
- [x] Chain request form
- [x] Popular chains quick-select
- [x] 48hr turnaround promise
- [x] Status tracking

---

## Epic 8: Mobile & UX

### US-8.1: Mobile Responsive Layout
**Priority:** P0 | **Status:** Complete

> As a mobile user, I want the app to work on my phone, so that I can check my portfolio anywhere.

**Acceptance Criteria:**
- [x] Responsive navigation
- [x] Stacked layouts on small screens
- [x] Touch-friendly buttons
- [x] Readable text sizes

---

### US-8.2: Modal Responsiveness
**Priority:** P1 | **Status:** Complete

> As a mobile user, I want modals to be usable, so that I can access all features.

**Acceptance Criteria:**
- [x] Full-width on mobile
- [x] Scrollable content
- [x] Appropriate padding
- [x] Close button accessible

---

## Backlog (Future Stories)

### US-B.1: DeFi Position Tracking
**Priority:** P2 | **Status:** Backlog

> As a DeFi user, I want to see my liquidity pool positions, so that I can include them in my portfolio.

---

### US-B.2: NFT Valuations
**Priority:** P2 | **Status:** Backlog

> As an NFT holder, I want to see my NFT values, so that I can track my full portfolio.

---

### US-B.3: Portfolio History Charts
**Priority:** P2 | **Status:** Backlog

> As a user, I want to see my portfolio value over time, so that I can track my performance.

---

### US-B.4: Tax Loss Harvesting
**Priority:** P2 | **Status:** Backlog

> As a tax-conscious user, I want suggestions for tax loss harvesting, so that I can optimize my taxes.

---

### US-B.5: Multi-User Family Plan
**Priority:** P3 | **Status:** Backlog

> As a family, we want a shared subscription, so that we can save money.

---

### US-B.6: CPA Collaboration
**Priority:** P3 | **Status:** Backlog

> As a user working with a CPA, I want to share read-only access, so that my accountant can review my data.

---

### US-B.7: International Tax Support
**Priority:** P3 | **Status:** Backlog

> As a non-US user, I want tax reports for my country, so that I can comply with local regulations.

---

*Document Version: 2.1*  
*Last Updated: March 10, 2026*  
*Total Stories: 35*  
*Complete: 28 | In Progress: 0 | Backlog: 7*
