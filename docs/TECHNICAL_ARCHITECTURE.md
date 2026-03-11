# Crypto Bag Tracker - Technical Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM ARCHITECTURE                                │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────┐
                    │           USER DEVICES              │
                    │     (Browser / Mobile / Tablet)     │
                    └──────────────────┬──────────────────┘
                                       │
                                       │ HTTPS
                                       ▼
                    ┌─────────────────────────────────────┐
                    │          RENDER PLATFORM            │
                    │  ┌─────────────┐ ┌─────────────┐   │
                    │  │  Frontend   │ │   Backend   │   │
                    │  │ Static Site │ │ Web Service │   │
                    │  │   (React)   │ │  (FastAPI)  │   │
                    │  │             │ │             │   │
                    │  │cryptobag    │ │api.cryptobag│   │
                    │  │tracker.io   │ │tracker.io   │   │
                    │  └─────────────┘ └──────┬──────┘   │
                    └─────────────────────────┼──────────┘
                                              │
                    ┌─────────────────────────┼──────────────────────────┐
                    │                         │                          │
                    ▼                         ▼                          ▼
          ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
          │  MongoDB Atlas  │    │  External APIs  │    │    Services     │
          │                 │    │                 │    │                 │
          │  - users        │    │  - Alchemy      │    │  - Stripe       │
          │  - wallets      │    │  - Blockstream  │    │  - CoinGecko    │
          │  - transactions │    │  - BlockCypher  │    │  - Coinbase     │
          │  - custody      │    │  - Algonode     │    │                 │
          └─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## Frontend Architecture

### Technology Stack
- **Framework:** React 18.x
- **Build Tool:** Create React App
- **Styling:** Tailwind CSS 3.x
- **UI Components:** shadcn/ui
- **State Management:** React hooks (useState, useEffect, useContext)
- **HTTP Client:** Fetch API
- **Visualization:** React Flow (custody graphs)

### Directory Structure
```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── ui/                    # shadcn/ui components
│   │   │   ├── button.jsx
│   │   │   ├── card.jsx
│   │   │   ├── dialog.jsx
│   │   │   └── ...
│   │   ├── AffiliateModal.js
│   │   ├── AuthModal.js
│   │   ├── ChainOfCustodyModal.js
│   │   ├── CustodyFlowGraph.js
│   │   ├── DowngradeModal.js
│   │   ├── ExchangeModal.js
│   │   ├── ExportModal.js
│   │   ├── SupportModal.js
│   │   ├── TaxDashboard.js
│   │   ├── UpgradeModal.js
│   │   └── ...
│   ├── hooks/
│   │   ├── useAnalysis.js
│   │   └── usePayment.js
│   ├── lib/
│   │   └── utils.js
│   ├── App.js                     # Main application component
│   ├── App.css
│   └── index.js
├── package.json
└── tailwind.config.js
```

### Component Hierarchy
```
App.js
├── Header
├── UserInfoBar (logged in state)
│   ├── UserBadge
│   ├── ActionButtons (Exchange, Custody, Affiliate, Help)
│   └── LogoutButton
├── WalletInputSection
│   ├── ChainSelector
│   ├── AddressInput
│   └── AnalyzeButton
├── AnalysisResults (when data available)
│   ├── PortfolioValueCard
│   ├── StatisticsGrid (4 cards)
│   ├── TaxSummary (unlimited tier)
│   └── TransactionsTable
├── Modals
│   ├── AuthModal
│   ├── UpgradeModal
│   ├── ExchangeModal
│   ├── ChainOfCustodyModal
│   ├── AffiliateModal
│   └── SupportModal
└── Footer
```

---

## Backend Architecture

### Technology Stack
- **Framework:** FastAPI 0.100+
- **Python Version:** 3.11
- **Database ODM:** PyMongo
- **Authentication:** python-jose (JWT)
- **Password Hashing:** passlib + bcrypt
- **PDF Generation:** ReportLab
- **Encryption:** cryptography (Fernet)

### Directory Structure
```
backend/
├── chains/                        # Modular blockchain analyzers
│   ├── __init__.py
│   ├── base.py                    # BaseChainAnalyzer (abstract)
│   ├── evm.py                     # EVMChainAnalyzer
│   ├── bitcoin.py                 # BitcoinAnalyzer
│   └── solana.py                  # SolanaAnalyzer
├── auth_service.py                # JWT authentication
├── custody_service.py             # Chain of custody logic
├── custody_report_generator.py    # PDF report generation
├── encryption_service.py          # API key encryption
├── multi_chain_service.py         # Legacy chain analyzer
├── multi_chain_service_v2.py      # New modular chain analyzer
├── multi_exchange_service.py      # Exchange API connections
├── coinbase_oauth_service.py      # Coinbase OAuth2
├── csv_parser_service.py          # Exchange CSV parsing
├── unified_tax_service.py         # Tax calculations
├── ai_support_service.py          # AI chatbot
├── server.py                      # Main FastAPI application
├── requirements.txt
└── .env
```

### Service Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND SERVICES                                   │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   server.py     │
                              │  (FastAPI App)  │
                              └────────┬────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │              │               │               │              │
        ▼              ▼               ▼               ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│    Auth     │ │   Wallet    │ │     Tax     │ │  Exchange   │ │   Custody   │
│   Service   │ │   Service   │ │   Service   │ │   Service   │ │   Service   │
│             │ │             │ │             │ │             │ │             │
│ - register  │ │ - analyze   │ │ - FIFO      │ │ - CSV parse │ │ - trace     │
│ - login     │ │ - multi-ch  │ │ - Form 8949 │ │ - API conn  │ │ - PDF gen   │
│ - JWT       │ │ - balance   │ │ - Sched D   │ │ - OAuth     │ │ - graph     │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │               │               │
       └───────────────┴───────────────┴───────────────┴───────────────┘
                                       │
                              ┌────────┴────────┐
                              │    MongoDB      │
                              └─────────────────┘
```

---

## Database Schema

### Collections

#### users
```javascript
{
  _id: ObjectId,
  id: String (UUID),
  email: String (unique),
  password_hash: String,
  subscription_tier: "free" | "unlimited",
  stripe_customer_id: String,
  stripe_subscription_id: String,
  subscription_status: String,
  current_period_end: DateTime,
  cancel_at_period_end: Boolean,
  analysis_count: Number,
  daily_usage_count: Number,
  last_usage_reset: DateTime,
  created_at: DateTime,
  terms_accepted: Boolean,
  terms_accepted_at: DateTime,
  coinbase_tokens: {
    access_token: String (encrypted),
    refresh_token: String (encrypted),
    expires_at: DateTime
  },
  exchange_credentials: {
    binance: {
      api_key: String (encrypted),
      api_secret: String (encrypted)
    },
    ...
  }
}
```

#### saved_wallets
```javascript
{
  _id: ObjectId,
  user_id: String,
  wallet_address: String,
  name: String,
  chain: String,
  created_at: DateTime
}
```

#### exchange_transactions
```javascript
{
  _id: ObjectId,
  user_id: String,
  exchange: String,
  tx_type: "buy" | "sell" | "transfer",
  asset: String,
  quantity: Number,
  price: Number,
  total_value: Number,
  fee: Number,
  timestamp: DateTime,
  original_row: Object
}
```

#### transaction_categories
```javascript
{
  _id: ObjectId,
  user_id: String,
  address: String,
  chain: String,
  categories: {
    "tx_hash": "trade" | "income" | "gift" | "airdrop" | "staking" | "mining"
  },
  updated_at: DateTime
}
```

#### custody_analyses
```javascript
{
  _id: ObjectId,
  user_id: String,
  target_address: String,
  chain: String,
  analysis_date: DateTime,
  summary: {
    total_links_traced: Number,
    exchange_origins: Number,
    dex_origins: Number,
    dormant_origins: Number
  },
  custody_chain: Array
}
```

#### affiliates
```javascript
{
  _id: ObjectId,
  user_id: String,
  affiliate_code: String (unique),
  referral_count: Number,
  total_earnings: Number,
  created_at: DateTime
}
```

#### chain_requests
```javascript
{
  _id: ObjectId,
  user_id: String,
  chain_name: String,
  status: "pending" | "approved" | "rejected",
  created_at: DateTime,
  updated_at: DateTime
}
```

### Indexes
```javascript
// users
db.users.createIndex({ "email": 1 }, { unique: true })
db.users.createIndex({ "id": 1 })

// exchange_transactions
db.exchange_transactions.createIndex({ "user_id": 1 })
db.exchange_transactions.createIndex({ "user_id": 1, "timestamp": -1 })

// custody_analyses
db.custody_analyses.createIndex({ "user_id": 1 })
db.custody_analyses.createIndex({ "target_address": 1 })

// affiliates
db.affiliates.createIndex({ "affiliate_code": 1 }, { unique: true })
```

---

## API Design

### RESTful Conventions

| Method | Path | Action |
|--------|------|--------|
| GET | /api/resource | List all |
| GET | /api/resource/:id | Get one |
| POST | /api/resource | Create |
| PUT | /api/resource/:id | Update |
| DELETE | /api/resource/:id | Delete |

### Authentication Flow
```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Client  │                    │  Server  │                    │ MongoDB  │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                               │                               │
     │  POST /api/auth/login         │                               │
     │  {email, password}            │                               │
     │──────────────────────────────▶│                               │
     │                               │  Find user by email           │
     │                               │──────────────────────────────▶│
     │                               │◀──────────────────────────────│
     │                               │                               │
     │                               │  Verify password (bcrypt)     │
     │                               │                               │
     │                               │  Generate JWT (24hr expiry)   │
     │                               │                               │
     │  {access_token, user}         │                               │
     │◀──────────────────────────────│                               │
     │                               │                               │
     │  GET /api/auth/me             │                               │
     │  Authorization: Bearer <jwt>  │                               │
     │──────────────────────────────▶│                               │
     │                               │  Decode & verify JWT          │
     │                               │                               │
     │  {user}                       │                               │
     │◀──────────────────────────────│                               │
```

---

## Security Architecture

### Data Protection

| Data Type | Protection Method |
|-----------|-------------------|
| Passwords | bcrypt hash (8 rounds) |
| JWT Tokens | HS256 signing |
| API Keys | Fernet encryption (AES-128) |
| OAuth Tokens | Fernet encryption |
| Database | MongoDB Atlas TLS |
| Transport | HTTPS only |

### Encryption Service
```python
# encryption_service.py
from cryptography.fernet import Fernet

class EncryptionService:
    def __init__(self):
        key = os.environ.get('ENCRYPTION_KEY')
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()
```

### Access Control

| Resource | Free | Unlimited |
|----------|------|-----------|
| Wallet Analysis | 1 total | Unlimited |
| Chains | ETH, BTC | All 12 |
| Tax Reports | No | Yes |
| Exchange Import | No | Yes |
| Chain of Custody | No | Yes |

---

## Deployment Architecture

### Render Configuration

**Frontend (Static Site)**
```yaml
name: cryptobagtracker-frontend
type: static_site
repo: github.com/user/repo
branch: main
buildCommand: cd frontend && yarn install && yarn build
publishDirectory: frontend/build
envVars:
  - REACT_APP_BACKEND_URL: https://api.cryptobagtracker.io
```

**Backend (Web Service)**
```yaml
name: shoestring-backend
type: web_service
runtime: python
repo: github.com/user/repo
branch: main
buildCommand: cd backend && pip install -r requirements.txt
startCommand: cd backend && uvicorn server:app --host 0.0.0.0 --port 10000
envVars:
  - MONGO_URL: mongodb+srv://...
  - STRIPE_API_KEY: sk_live_...
  - ALCHEMY_API_KEY: ...
  - ENCRYPTION_KEY: ...
  - CORS_ORIGINS: https://cryptobagtracker.io
```

### DNS Configuration
```
cryptobagtracker.io      A      216.24.57.1 (Render)
www.cryptobagtracker.io  CNAME  cryptobagtracker-frontend.onrender.com
api.cryptobagtracker.io  CNAME  shoestring-backend.onrender.com
```

---

## Monitoring & Observability

### Logging Strategy
```python
import logging

# Structured logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Log important events
logger.info(f"User {user_id} analyzed wallet {address} on {chain}")
logger.warning(f"CoinGecko rate limited, using fallback prices")
logger.error(f"Failed to connect to Binance API: {error}")
```

### Metrics to Track
- Request latency (p50, p95, p99)
- Error rate by endpoint
- Database query time
- External API response time
- Active users (DAU, MAU)
- Conversion rate (free → paid)

### Health Checks
```python
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "database": await check_mongo(),
        "timestamp": datetime.utcnow()
    }
```

---

## Performance Considerations

### Caching Strategy
- CoinGecko prices: 60 second cache
- User sessions: JWT (no server-side cache)
- Exchange CSV formats: Static memory cache

### Database Optimization
- Indexes on frequently queried fields
- Projection to limit returned fields
- Pagination for large result sets

### API Rate Limiting
- Per-user limits on expensive operations
- Exponential backoff for external APIs
- Graceful degradation with fallbacks

---

*Document Version: 2.1*  
*Last Updated: March 10, 2026*
