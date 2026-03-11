# Crypto Bag Tracker - Release Notes

## Version History

---

## v2.1.0 (March 10, 2026)

### New Features
- **Mobile Responsive UI** - Complete redesign for mobile devices
  - Responsive navigation and button layouts
  - Touch-friendly modals and forms
  - Optimized tables with hidden columns on mobile
  - Tablet breakpoint support (768px)

### Improvements
- Chain of Custody modal mobile optimization
- Support modal mobile optimization
- Better button wrapping on small screens

### Bug Fixes
- Fixed buttons overflowing on mobile viewports
- Fixed modal padding on small screens

---

## v2.0.0 (March 10, 2026)

### New Features
- **Multi-Exchange API Integration**
  - Connect to 8 exchanges via API keys
  - Binance, Kraken, Gemini, Crypto.com, KuCoin, OKX, Bybit, Gate.io
  - Read-only access only
  - API keys encrypted at rest

- **Coinbase OAuth Integration**
  - Connect Coinbase with one click
  - Auto-import wallet addresses
  - Read-only access (cannot move funds)

- **Chain of Custody Analysis**
  - Trace asset origins across wallets
  - Detect exchange, DEX, and dormant wallet origins
  - Interactive flow graph visualization
  - PDF report export for auditors

- **AI Support Assistant**
  - In-app chat with AI
  - Tax and crypto questions
  - Suggested questions for quick help

- **PDF Report Generation**
  - Professional custody reports
  - Executive summary
  - Full transaction chain detail

### Improvements
- Added encryption service for sensitive data
- Coinbase OAuth setup guide

---

## v1.9.0 (March 8, 2026)

### New Features
- **Chain of Custody (Initial)**
  - Backend service for tracing transactions
  - Stop conditions: exchanges, DEXs, dormancy
  - Table view of results

- **CustodyFlowGraph Component**
  - Interactive React Flow visualization
  - Color-coded nodes by origin type
  - Zoom, pan, and drag controls
  - Mini-map navigation

---

## v1.8.0 (March 6, 2026)

### New Features
- **Expanded Blockchain Support**
  - Algorand (ALGO)
  - Avalanche (AVAX)
  - Optimism (ETH)
  - Base (ETH)
  - Fantom (FTM)
  - Dogecoin (DOGE)
  - Total: 12 supported chains

- **Request a Chain Feature**
  - Unlimited users can request new blockchains
  - 48-hour turnaround promise
  - Status tracking

### Improvements
- Auto-detect wallet-to-exchange transfers
- Transfer cost basis linking

---

## v1.7.0 (March 6, 2026)

### New Features
- **Cost Basis Adjustment for Transfers**
  - Edit cost basis on exchange transactions
  - Override acquisition dates
  - Correctly calculate holding period

- **Multi-Format Coinbase CSV**
  - Support for classic and modern formats
  - Smart buy/sell detection
  - Heuristic fallback detection

### Improvements
- Stablecoin exclusion from cost basis
- CPA disclaimer on all tax calculations
- Calculation transparency documentation

---

## v1.6.0 (March 5, 2026)

### New Features
- **Exchange-Only Tax Calculator**
  - Calculate taxes from CSVs alone
  - No wallet analysis required
  - FIFO cost basis
  - Form 8949 export

- **Code Refactoring**
  - Custom React hooks (useAnalysis, usePayment)
  - Modular chain analyzers
  - multi_chain_service_v2

---

## v1.5.0 (March 5, 2026)

### New Features
- **Affiliate Program**
  - Unique affiliate codes
  - $10 commission per referral
  - $10 discount for referred users
  - Affiliate dashboard

- **Exchange CSV Import**
  - Support for 6 exchanges
  - Coinbase, Binance, Kraken, Gemini, Crypto.com, KuCoin
  - Auto-format detection
  - Drag-and-drop upload

---

## v1.4.0 (February 28, 2026)

### New Features
- **Tax Reports Enhancements**
  - Schedule D summary generation
  - Tax year filtering (2020-current)
  - Batch categorization with rules
  - Auto-categorization detection

---

## v1.3.0 (February 28, 2026)

### New Features
- **Cost Basis & Capital Gains**
  - FIFO cost basis calculation
  - Realized/unrealized gains
  - Short-term vs long-term classification
  - Tax lots tracking
  - Form 8949 CSV export
  - Transaction categorization

---

## v1.2.0 (February 2026)

### New Features
- **USD Valuation**
  - CoinGecko API integration
  - Real-time portfolio value
  - Transaction values in USD
  - Fallback prices for rate limiting

---

## v1.1.0 (November 2025)

### New Features
- **Stripe Subscription**
  - Unlimited tier ($100.88/year)
  - Stripe checkout integration
  - Billing portal access

- **Bitcoin xPub Support**
  - HD wallet support
  - Derive all addresses from xPub/yPub/zPub

---

## v1.0.0 (November 2025)

### Initial Release
- User authentication (JWT)
- Multi-chain wallet analysis
- Ethereum, Bitcoin, Polygon, Arbitrum, BSC, Solana
- Basic transaction history
- CSV export
- Terms of Service acceptance
- Saved wallets feature

---

## Upgrade Path

### Free → Unlimited
All features are immediately available after upgrade:
- All 12 blockchains unlocked
- Unlimited wallet analyses
- Tax calculation features
- Exchange integrations
- Chain of Custody
- Export features

### Downgrade (Unlimited → Free)
- Access continues until period end
- After period end:
  - Reduced to 1 total analysis
  - Only ETH/BTC chains
  - No export features
  - No tax calculations

---

## Known Issues

### Current
- CoinGecko API rate limits may cause fallback prices
- Large wallets (10,000+ txns) may timeout

### Resolved
- v2.1.0: Fixed mobile responsiveness issues
- v2.0.0: Fixed Coinbase token refresh
- v1.8.0: Fixed negative balance calculations

---

## Deprecation Notices

### Upcoming
- `multi_chain_service.py` (v1) will be deprecated in v3.0.0
  - Use `multi_chain_service_v2.py` instead

---

*Document Version: 2.1*  
*Last Updated: March 10, 2026*
