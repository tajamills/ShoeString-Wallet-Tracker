# Crypto Bag Tracker - Product Requirements Document

## Overview
Crypto Bag Tracker is a dual-feature cryptocurrency platform:
1. **Price Alerts** (Primary) - Set price alerts for crypto and get notified via email/SMS
2. **Bag Tracker Beta** (Secondary) - Track wallet transactions across multiple blockchains and generate tax reports

## Original Problem Statement
Build a cryptocurrency wallet analyzer with a **PIVOT to Price Alerts** as the primary feature:
- Price alerts for crypto (stocks coming later)
- Alert triggers: Price thresholds AND percentage changes
- Notifications: Email + SMS
- Pricing: Single tier $18.88/month unlimited alerts with 7-day free trial
- Keep existing tax tracker as "Bag Tracker Beta" tab (free for beta testers)

## Tech Stack
- **Frontend**: React with Tailwind CSS, shadcn/ui components
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Price APIs**: CoinGecko (primary), Coinbase (fallback), KuCoin (secondary fallback)
- **Payments**: Stripe ($18.88/month with 7-day trial)
- **Notifications**: SendGrid (email), Twilio (SMS) - API keys required
- **Authentication**: Custom JWT-based auth

## Subscription Model (Alerts)
| Feature | Free Trial (7 days) | Unlimited ($18.88/mo) |
|---------|---------------------|----------------------|
| Duration | 7 days | Ongoing |
| Max Alerts | Unlimited | Unlimited |
| Email Notifications | Yes | Yes |
| SMS Notifications | Yes | Yes |
| Price Thresholds | Yes | Yes |
| Percentage Alerts | Yes | Yes |

## App Navigation
- **Tab 1: Price Alerts** (Default/Primary)
  - Subscription banner with trial status
  - Create/manage alerts
  - View triggered alerts history
  
- **Tab 2: Bag Tracker Beta**
  - Tax tracking features (free for beta testers)
  - Wallet analysis across 6 chains
  - Tax calculations and reporting

## Completed Features

### June 6, 2026 - Price Alerts Pivot
- [x] Tab navigation (Price Alerts vs Bag Tracker Beta)
- [x] Alert subscription model with 7-day free trial
- [x] Backend CRUD for alerts (/api/alerts/*)
- [x] Start trial endpoint (/api/alerts/start-trial)
- [x] Stripe checkout integration (/api/alerts/create-checkout)
- [x] AlertDashboard.js frontend component
- [x] Price fetching with CoinGecko + Coinbase/KuCoin fallback
- [x] Asset search functionality
- [x] Alert type selection (price_above, price_below, percent_change_up, percent_change_down)
- [x] Notification service structure (SendGrid + Twilio - keys not configured)

### Previous - Tax Tracker Features (Now in Bag Tracker Beta tab)
- [x] Multi-chain wallet analysis (ETH, BTC, POLY, ARB, BSC, SOL)
- [x] Exchange CSV parsing (Coinbase, Kraken, Binance, etc.)
- [x] Tax calculations with FIFO method
- [x] Cost basis tracking with manual acquisition entry
- [x] Internal transfer auto-detection
- [x] Review queue for orphan transactions
- [x] Detailed tax report table (brokerage-style)
- [x] Form 8949 / Schedule D export ready

## API Endpoints

### Alert System
- `GET /api/alerts` - List user's alerts with subscription info
- `POST /api/alerts` - Create new alert (requires active trial/subscription)
- `PUT /api/alerts/{id}` - Update alert
- `DELETE /api/alerts/{id}` - Delete alert
- `POST /api/alerts/{id}/toggle` - Pause/resume alert
- `GET /api/alerts/subscription` - Get subscription status
- `POST /api/alerts/start-trial` - Start 7-day free trial
- `POST /api/alerts/create-checkout` - Create Stripe checkout session
- `GET /api/alerts/tiers` - Get pricing tiers
- `GET /api/alerts/price/{type}/{symbol}` - Get current price
- `GET /api/alerts/search` - Search for assets

### Stripe Integration
- Product ID: prod_UecNCOQUgkIyrk
- Price ID: price_1TfJ8WAXuTzNcQX7GPkmVilU
- Webhook: `/api/alerts/webhook/stripe`

## Pending/Backlog

### P1 - Notification Setup (Requires API Keys)
- [ ] Configure SendGrid API key in backend/.env
- [ ] Configure Twilio credentials in backend/.env
- [ ] Test email delivery
- [ ] Test SMS delivery

### P2 - Stock Alerts (Requires API Key)
- [ ] Add Alpha Vantage or Yahoo Finance integration
- [ ] Enable stock price fetching
- [ ] Update AssetType enum to include stocks

### P3 - Enhancements
- [ ] Alert history/triggered alerts log
- [ ] Price polling background task for auto-triggering
- [ ] Dashboard analytics (alert performance)
- [ ] Batch price fetching for multiple alerts

## Database Collections

### alerts
```javascript
{
  alert_id: string,
  user_id: string,
  asset_symbol: string,      // e.g., "BTC", "ETH"
  asset_type: string,        // "crypto" (stocks later)
  alert_type: string,        // price_above, price_below, percent_change_up, percent_change_down
  target_value: float,       // price or percentage
  current_price: float,
  notification_method: string, // email, sms, both
  phone_number: string,
  email: string,
  note: string,
  status: string,            // active, paused, triggered, expired
  created_at: datetime,
  updated_at: datetime,
  last_triggered_at: datetime
}
```

### alert_subscriptions
```javascript
{
  user_id: string,
  status: string,            // none, trialing, active, canceled, past_due, expired
  tier: string,              // free, unlimited
  trial_used: boolean,
  trial_started_at: datetime,
  trial_ends_at: datetime,
  stripe_subscription_id: string,
  stripe_customer_id: string,
  created_at: datetime,
  updated_at: datetime
}
```

## Test Credentials
See `/app/memory/test_credentials.md`
