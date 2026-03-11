# Crypto Bag Tracker - Product Specification

## Executive Summary

**Product Name:** Crypto Bag Tracker  
**Domain:** cryptobagtracker.io  
**Category:** Cryptocurrency Tax & Portfolio Management SaaS  
**Target Market:** US cryptocurrency holders needing tax compliance tools  
**Pricing:** Freemium with $100.88/year Unlimited tier

---

## Problem Statement

Cryptocurrency users face significant challenges with tax compliance:

1. **Fragmented Data** - Holdings spread across multiple wallets and exchanges
2. **Complex Calculations** - FIFO cost basis requires tracking every transaction
3. **IRS Requirements** - Form 8949 and Schedule D require detailed records
4. **Multi-Chain Complexity** - Users hold assets across 10+ blockchains
5. **Exchange Diversity** - Data in different formats across platforms
6. **Audit Risk** - Government agencies increasingly scrutinizing crypto holdings

---

## Solution

Crypto Bag Tracker provides a comprehensive platform that:

- **Aggregates** wallet data from 12 blockchains automatically
- **Imports** transaction history from 9+ major exchanges
- **Calculates** FIFO cost basis and capital gains/losses
- **Generates** IRS-ready Form 8949 and Schedule D reports
- **Traces** asset origins with Chain of Custody analysis
- **Secures** user data with encryption and read-only access

---

## Target Users

### Primary Persona: "Tax-Conscious Trader"
- **Demographics:** 25-45 years old, US-based
- **Holdings:** $10K - $500K in cryptocurrency
- **Behavior:** Trades across multiple exchanges, uses DeFi
- **Pain Point:** Dreads tax season, unsure of cost basis
- **Goal:** File accurate taxes without expensive accountants

### Secondary Persona: "Compliance Professional"
- **Demographics:** Government auditor, forensic accountant
- **Use Case:** Investigating cryptocurrency holdings
- **Pain Point:** Tracing asset origins across wallets
- **Goal:** Generate audit-ready documentation

### Tertiary Persona: "Crypto Holder"
- **Demographics:** Any age, holds crypto long-term
- **Holdings:** Any amount
- **Behavior:** Minimal trading, HODLing
- **Pain Point:** Needs to track portfolio value
- **Goal:** Know their current holdings and unrealized gains

---

## Feature Set

### Tier Comparison

| Feature | Free | Unlimited ($100.88/yr) |
|---------|------|------------------------|
| Wallet Analysis | 1 total | Unlimited |
| Blockchains | ETH, BTC only | All 12 chains |
| Portfolio Value (USD) | No | Yes |
| CSV Export | No | Yes |
| Tax Calculations (FIFO) | No | Yes |
| Form 8949 Export | No | Yes |
| Schedule D Export | No | Yes |
| Exchange CSV Import | No | Yes |
| Exchange API Connect | No | Yes |
| Chain of Custody | No | Yes |
| AI Support Assistant | No | Yes |
| Bitcoin xPub Support | No | Yes |

### Core Features (Detailed)

#### 1. Multi-Chain Wallet Analysis
- **Supported Chains:** Ethereum, Bitcoin, Polygon, Arbitrum, BSC, Solana, Algorand, Avalanche, Optimism, Base, Fantom, Dogecoin
- **Data Retrieved:** Balance, all transactions, gas fees
- **Output:** USD-valued portfolio summary

#### 2. Tax Calculation Engine
- **Method:** FIFO (First-In, First-Out)
- **Outputs:** 
  - Realized gains/losses
  - Unrealized gains/losses
  - Short-term vs Long-term classification
  - Tax lots inventory
- **Exports:** Form 8949 CSV, Schedule D summary

#### 3. Exchange Integration
- **CSV Import:** Coinbase, Binance, Kraken, Gemini, Crypto.com, KuCoin
- **API Connect:** Binance, Kraken, Gemini, Crypto.com, KuCoin, OKX, Bybit, Gate.io
- **OAuth:** Coinbase (read-only)

#### 4. Chain of Custody Analysis
- **Purpose:** Trace asset origins for audit/compliance
- **Detection:** Exchange wallets, DEX routers, dormant wallets
- **Outputs:** Interactive flow graph, table view, PDF report
- **Use Case:** Government agencies, auditors, self-audit

#### 5. Security Features
- **API Key Encryption:** Fernet symmetric encryption at rest
- **Read-Only Access:** All exchange connections are read-only
- **No Fund Movement:** Application cannot move/send/withdraw funds
- **JWT Authentication:** Secure token-based auth

---

## Technical Architecture

### Frontend
- **Framework:** React 18
- **Styling:** Tailwind CSS + shadcn/ui components
- **State:** React hooks (useState, useEffect)
- **Visualization:** React Flow (for custody graphs)

### Backend
- **Framework:** FastAPI (Python 3.11)
- **Database:** MongoDB
- **Authentication:** JWT with bcrypt password hashing
- **Encryption:** cryptography (Fernet)

### External Services
- **Blockchain Data:** Alchemy, Blockstream, BlockCypher, Algonode
- **Price Data:** CoinGecko API
- **Payments:** Stripe (subscriptions)
- **OAuth:** Coinbase

### Deployment
- **Platform:** Render
- **Frontend:** Static Site
- **Backend:** Python Web Service
- **Database:** MongoDB Atlas

---

## Business Model

### Revenue Streams

1. **Subscriptions:** $100.88/year Unlimited tier
2. **Affiliate Program:** 10% commission ($10 per referral)

### Unit Economics

| Metric | Value |
|--------|-------|
| Price | $100.88/year |
| Affiliate Payout | $10/referral |
| Net Revenue/User | $90.88/year |
| Target Users Y1 | 1,000 |
| ARR Target Y1 | $90,880 |

### Competitive Positioning

| Competitor | Price | Chains | Custody | Our Advantage |
|------------|-------|--------|---------|---------------|
| Koinly | $99-399/yr | 50+ | No | Chain of Custody |
| CoinTracker | $59-199/yr | 300+ | No | Simpler pricing |
| TokenTax | $65-3500/yr | 80+ | No | Lower cost |
| **Crypto Bag Tracker** | $100.88/yr | 12 | Yes | Custody Analysis |

---

## Success Metrics

### North Star Metric
**Tax Reports Generated** - Number of Form 8949 exports

### Key Performance Indicators

| Metric | Target | Measurement |
|--------|--------|-------------|
| Monthly Active Users | 500 | Unique logins |
| Free-to-Paid Conversion | 5% | Upgrades / Registrations |
| Churn Rate | < 10% | Monthly cancellations |
| NPS Score | > 50 | Quarterly survey |
| Support Response Time | < 4 hours | AI + Human combined |

### Feature Adoption

| Feature | Target Adoption |
|---------|-----------------|
| Wallet Analysis | 100% of users |
| Tax Report Export | 80% of paid users |
| Exchange Import | 60% of paid users |
| Chain of Custody | 20% of paid users |

---

## Roadmap Overview

### Current State (v2.1 - March 2026)
- 12 blockchain support
- Full tax calculation suite
- 9 exchange integrations
- Chain of Custody with PDF export
- Mobile responsive UI
- AI support assistant

### Next Quarter (Q2 2026)
- DeFi position tracking
- NFT valuations
- Portfolio history charts
- Tax loss harvesting suggestions

### Future (Q3-Q4 2026)
- International tax support (UK, EU)
- CPA marketplace integration
- White-label for accountants
- API for third-party integration

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| API rate limiting | Medium | High | Fallback prices, caching |
| Blockchain API changes | High | Medium | Modular chain adapters |
| Regulatory changes | High | Medium | Flexible tax engine |
| Security breach | Critical | Low | Encryption, read-only access |
| Competitor feature parity | Medium | High | Focus on Custody differentiator |

---

## Appendix

### Glossary

- **FIFO:** First-In, First-Out - Tax lot matching method
- **Cost Basis:** Original purchase price of an asset
- **Realized Gain:** Profit from selling an asset
- **Unrealized Gain:** Paper profit on unsold assets
- **Form 8949:** IRS form for reporting capital gains
- **Schedule D:** IRS form summarizing capital gains/losses
- **Chain of Custody:** Tracing asset movement through wallets

### Regulatory References

- IRS Notice 2014-21: Virtual currency tax guidance
- Form 8949: Sales and Other Dispositions of Capital Assets
- Schedule D: Capital Gains and Losses

---

*Document Version: 2.1*  
*Last Updated: March 10, 2026*  
*Owner: Product Team*
