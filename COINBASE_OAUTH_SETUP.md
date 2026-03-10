# Coinbase OAuth App Registration Guide

## Step-by-Step Instructions

### 1. Create a Coinbase Developer Account

1. Go to **https://www.coinbase.com/developers**
2. Click "Get started" or sign in with your existing Coinbase account
3. Accept the developer terms of service

### 2. Create a New OAuth Application

1. Navigate to **https://portal.cloud.coinbase.com/**
2. Click **"Create new project"** or go to an existing project
3. In your project, go to **"API Keys"** → **"Create API Key"**
4. Select **"OAuth"** as the authentication type

### 3. Configure Your OAuth Application

Fill in the following details:

| Field | Value |
|-------|-------|
| **App Name** | Crypto Bag Tracker |
| **App Description** | Tax tracking and chain of custody analysis for cryptocurrency |
| **App Logo** | Upload your logo (optional) |
| **Homepage URL** | https://cryptobagtracker.io |
| **Redirect URI** | https://cryptobagtracker.io/api/coinbase/callback |

### 4. Set OAuth Scopes (READ-ONLY)

Request ONLY these scopes:
- ✅ `wallet:accounts:read` - View account balances
- ✅ `wallet:transactions:read` - View transaction history  
- ✅ `wallet:addresses:read` - View wallet addresses

**DO NOT** request:
- ❌ `wallet:transactions:send`
- ❌ `wallet:withdrawals:create`
- ❌ Any write/trade permissions

### 5. Get Your Credentials

After creating the app, you'll receive:
- **Client ID** (public) - e.g., `abc123def456`
- **Client Secret** (private) - e.g., `sk_live_xxxxx`

### 6. Configure Environment Variables

Add these to your production environment (Render dashboard):

```
COINBASE_CLIENT_ID=your_client_id_here
COINBASE_CLIENT_SECRET=your_client_secret_here
COINBASE_REDIRECT_URI=https://cryptobagtracker.io/api/coinbase/callback
```

### 7. Submit for Review (Production)

For production use with unlimited users:
1. Go to your app settings
2. Click "Submit for Review"
3. Provide description of how you use the data
4. Wait for Coinbase approval (usually 1-5 business days)

**Note:** During development/testing, you can use the app with your own Coinbase account without review.

---

## Security Checklist

- [ ] Client Secret stored in environment variables only (never in code)
- [ ] HTTPS enabled for all OAuth endpoints
- [ ] State parameter validated to prevent CSRF
- [ ] Tokens stored encrypted in database
- [ ] Token refresh implemented for expired access tokens
- [ ] Users can disconnect their account anytime

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Invalid redirect URI" | Ensure the redirect URI in Coinbase exactly matches your app |
| "Scope not allowed" | Re-check you only requested read-only scopes |
| "App not approved" | Submit for review or test with your own account |
| "Token expired" | Implement token refresh using refresh_token |
