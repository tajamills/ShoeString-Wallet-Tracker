# Crypto Bag Tracker - API Documentation

## Base URL

**Production:** `https://api.cryptobagtracker.io`  
**Preview:** `https://portfolio-gains-calc.preview.emergentagent.com`

## Authentication

All authenticated endpoints require a JWT token in the Authorization header:

```
Authorization: Bearer <token>
```

Tokens are obtained via `/api/auth/login` and expire after 24 hours.

---

## Endpoints

### Authentication

#### POST /api/auth/register
Create a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (201):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "subscription_tier": "free",
    "analysis_count": 0
  }
}
```

---

#### POST /api/auth/login
Authenticate an existing user.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "subscription_tier": "unlimited",
    "analysis_count": 15
  }
}
```

---

#### GET /api/auth/me
Get current user information.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "subscription_tier": "unlimited",
  "analysis_count": 15,
  "created_at": "2026-01-15T10:30:00Z"
}
```

---

### Wallet Analysis

#### POST /api/wallet/analyze
Analyze a wallet address on a specific blockchain.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f...",
  "chain": "ethereum"
}
```

**Supported Chains:**
`ethereum`, `bitcoin`, `polygon`, `arbitrum`, `bsc`, `solana`, `algorand`, `avalanche`, `optimism`, `base`, `fantom`, `dogecoin`

**Response (200):**
```json
{
  "address": "0x742d35Cc...",
  "chain": "ethereum",
  "currentBalance": 1.5,
  "totalEthReceived": 10.5,
  "totalEthSent": 9.0,
  "totalGasFees": 0.05,
  "incomingTransactionCount": 25,
  "outgoingTransactionCount": 20,
  "total_value_usd": 4500.00,
  "total_received_usd": 31500.00,
  "total_sent_usd": 27000.00,
  "current_price_usd": 3000.00,
  "recentTransactions": [...],
  "tax_data": {
    "realized_gains": 1500.00,
    "unrealized_gains": 500.00,
    "short_term_gains": 800.00,
    "long_term_gains": 700.00,
    "tax_lots": [...]
  }
}
```

---

#### POST /api/wallet/analyze-all
Analyze a wallet across all supported chains (Unlimited tier only).

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f..."
}
```

**Response (200):**
```json
{
  "results": [
    { "chain": "ethereum", "balance": 1.5, ... },
    { "chain": "polygon", "balance": 0.0, ... },
    ...
  ],
  "total_value_usd": 5000.00
}
```

---

### Tax Reports

#### POST /api/tax/export-form-8949
Generate Form 8949 CSV for capital gains reporting.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "address": "0x742d35Cc...",
  "chain": "ethereum",
  "tax_year": 2025,
  "term_filter": "all"
}
```

**term_filter options:** `all`, `short_term`, `long_term`

**Response (200):** CSV file download

---

#### POST /api/tax/export-schedule-d
Generate Schedule D summary.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "address": "0x742d35Cc...",
  "chain": "ethereum",
  "tax_year": 2025,
  "format": "csv"
}
```

**format options:** `csv`, `text`

**Response (200):** CSV or text file download

---

#### POST /api/tax/save-categories
Save transaction categories for tax purposes.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "address": "0x742d35Cc...",
  "chain": "ethereum",
  "categories": {
    "0xabc123...": "trade",
    "0xdef456...": "income"
  }
}
```

**Category options:** `trade`, `income`, `gift`, `airdrop`, `staking`, `mining`

**Response (200):**
```json
{
  "message": "Categories saved successfully"
}
```

---

### Exchange Integration

#### GET /api/exchanges/supported
List supported exchanges for CSV import.

**Response (200):**
```json
{
  "exchanges": [
    {
      "id": "coinbase",
      "name": "Coinbase",
      "csv_columns": ["Timestamp", "Transaction Type", "Asset", "Quantity Transacted"]
    },
    ...
  ]
}
```

---

#### POST /api/exchanges/upload-csv
Upload and import exchange CSV.

**Headers:** `Authorization: Bearer <token>`  
**Content-Type:** `multipart/form-data`

**Form Fields:**
- `file`: CSV file
- `exchange`: Exchange identifier (optional, auto-detected)

**Response (200):**
```json
{
  "message": "Successfully imported 150 transactions",
  "exchange": "coinbase",
  "transaction_count": 150
}
```

---

#### POST /api/exchanges/connect-api
Connect exchange via API keys.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "exchange": "binance",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret",
  "passphrase": "optional_passphrase"
}
```

**Supported exchanges:** `binance`, `kraken`, `gemini`, `crypto_com`, `kucoin`, `okx`, `bybit`, `gate_io`

**Response (200):**
```json
{
  "message": "Successfully connected to Binance",
  "exchange": "binance"
}
```

---

### Chain of Custody

#### POST /api/custody/analyze
Run chain of custody analysis on a wallet.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "address": "0x742d35Cc...",
  "chain": "ethereum",
  "max_depth": 5,
  "dormancy_days": 365
}
```

**Response (200):**
```json
{
  "target_address": "0x742d35Cc...",
  "chain": "ethereum",
  "analysis_date": "2026-03-10T15:30:00Z",
  "summary": {
    "total_links_traced": 12,
    "exchange_origins": 3,
    "dex_origins": 2,
    "dormant_origins": 1
  },
  "custody_chain": [
    {
      "from_address": "0xabc...",
      "to_address": "0x742d35Cc...",
      "value": 1.5,
      "tx_hash": "0x123...",
      "origin_type": "exchange",
      "origin_label": "Coinbase",
      "depth": 1
    },
    ...
  ]
}
```

---

#### POST /api/custody/export-pdf-from-result
Generate PDF report from custody analysis result.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "result": { ... }  // Full custody analysis result object
}
```

**Response (200):** PDF file download

---

### Coinbase OAuth

#### GET /api/coinbase/auth-url
Get Coinbase OAuth authorization URL.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "auth_url": "https://www.coinbase.com/oauth/authorize?..."
}
```

---

#### POST /api/coinbase/callback
Handle OAuth callback and exchange code for tokens.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "code": "authorization_code_from_coinbase"
}
```

**Response (200):**
```json
{
  "message": "Successfully connected to Coinbase",
  "accounts_found": 5
}
```

---

#### GET /api/coinbase/addresses-for-custody
Fetch all addresses from connected Coinbase account.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "addresses": [
    {
      "address": "0x742d35Cc...",
      "currency": "ETH",
      "network": "ethereum"
    },
    ...
  ]
}
```

---

### Payments

#### POST /api/payments/create-upgrade
Create Stripe checkout session for subscription upgrade.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "affiliate_code": "ABC123"  // optional
}
```

**Response (200):**
```json
{
  "checkout_url": "https://checkout.stripe.com/...",
  "session_id": "cs_..."
}
```

---

#### POST /api/payments/manage-subscription
Get Stripe billing portal URL.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "portal_url": "https://billing.stripe.com/..."
}
```

---

### Support

#### POST /api/support/ai-chat
Send message to AI support assistant.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "message": "How do I calculate my cost basis?"
}
```

**Response (200):**
```json
{
  "response": "Cost basis is calculated using the FIFO method...",
  "conversation_id": "conv_123"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Status Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient subscription tier |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limited |
| 500 | Internal Server Error |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| /api/wallet/analyze | 10/minute |
| /api/custody/analyze | 5/minute |
| /api/support/ai-chat | 20/minute |
| All other endpoints | 60/minute |

---

## Webhooks

### Stripe Webhook
**Endpoint:** POST /api/payments/webhook/stripe

Handles Stripe events for subscription lifecycle:
- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

---

*Document Version: 2.1*  
*Last Updated: March 10, 2026*
