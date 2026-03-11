# Crypto Bag Tracker - Process Flow Document

## Table of Contents
1. [User Journey Overview](#user-journey-overview)
2. [Authentication Flow](#authentication-flow)
3. [Wallet Analysis Flow](#wallet-analysis-flow)
4. [Tax Calculation Flow](#tax-calculation-flow)
5. [Exchange Integration Flow](#exchange-integration-flow)
6. [Chain of Custody Flow](#chain-of-custody-flow)
7. [Payment/Subscription Flow](#paymentsubscription-flow)
8. [Data Flow Architecture](#data-flow-architecture)

---

## User Journey Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER JOURNEY MAP                                   │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │  Visit   │────▶│  Sign Up │────▶│  Accept  │────▶│  Free    │
    │  Site    │     │  /Login  │     │   TOS    │     │  Tier    │
    └──────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                            │
                          ┌─────────────────────────────────┤
                          │                                 │
                          ▼                                 ▼
                    ┌──────────┐                      ┌──────────┐
                    │ Analyze  │                      │  Upgrade │
                    │ 1 Wallet │                      │ Unlimited│
                    │ (ETH/BTC)│                      │  $100/yr │
                    └──────────┘                      └────┬─────┘
                                                          │
         ┌────────────────────────────────────────────────┤
         │                    │                           │
         ▼                    ▼                           ▼
   ┌──────────┐        ┌──────────┐               ┌──────────┐
   │ Unlimited│        │ Exchange │               │ Chain of │
   │ Analyses │        │  Import  │               │ Custody  │
   │ 12 Chains│        │ CSV/API  │               │ Analysis │
   └────┬─────┘        └────┬─────┘               └────┬─────┘
        │                   │                          │
        └───────────────────┼──────────────────────────┘
                            │
                            ▼
                     ┌──────────┐
                     │   Tax    │
                     │ Reports  │
                     │ Form 8949│
                     └──────────┘
```

---

## Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

NEW USER REGISTRATION:
┌──────┐    ┌───────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
│ User │───▶│ Enter     │───▶│ Validate │───▶│ Hash    │───▶│ Store in │
│      │    │ Email/Pwd │    │ Format   │    │ Password│    │ MongoDB  │
└──────┘    └───────────┘    └──────────┘    └─────────┘    └────┬─────┘
                                                                  │
                                                                  ▼
                                                            ┌──────────┐
                                                            │ Generate │
                                                            │   JWT    │
                                                            └────┬─────┘
                                                                 │
                              ┌───────────────────────────────────┘
                              │
                              ▼
┌──────────┐    ┌───────────────┐    ┌──────────┐
│ Show TOS │───▶│ User Accepts  │───▶│ Dashboard│
│  Modal   │    │    Terms      │    │  Ready   │
└──────────┘    └───────────────┘    └──────────┘


RETURNING USER LOGIN:
┌──────┐    ┌───────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
│ User │───▶│ Enter     │───▶│ Find in  │───▶│ Verify  │───▶│ Generate │
│      │    │ Email/Pwd │    │ MongoDB  │    │ Password│    │   JWT    │
└──────┘    └───────────┘    └──────────┘    └─────────┘    └────┬─────┘
                                                                  │
                                                                  ▼
                                                            ┌──────────┐
                                                            │ Return   │
                                                            │ User Data│
                                                            └──────────┘
```

---

## Wallet Analysis Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WALLET ANALYSIS FLOW                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌───────────┐    ┌──────────┐    ┌─────────────┐
│ Enter    │───▶│ Select    │───▶│ Validate │───▶│ Check User  │
│ Address  │    │ Blockchain│    │ Address  │    │ Tier/Limits │
└──────────┘    └───────────┘    └──────────┘    └──────┬──────┘
                                                        │
                        ┌───────────────────────────────┤
                        │                               │
                        ▼                               ▼
                  [FREE TIER]                    [UNLIMITED TIER]
                  ┌─────────┐                    ┌─────────────┐
                  │ 1 Total │                    │  Unlimited  │
                  │ Analysis│                    │  Analyses   │
                  │ ETH/BTC │                    │  12 Chains  │
                  └────┬────┘                    └──────┬──────┘
                       │                                │
                       └────────────────┬───────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │ BLOCKCHAIN API  │
                               │    REQUESTS     │
                               └────────┬────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
        ▼                               ▼                               ▼
┌───────────────┐              ┌───────────────┐              ┌───────────────┐
│   EVM CHAINS  │              │    BITCOIN    │              │    SOLANA     │
│ Alchemy API   │              │  Blockstream  │              │  Alchemy API  │
│ ETH,POLY,ARB  │              │  BlockCypher  │              │               │
│ BSC,BASE,OPT  │              │  xPub Support │              │               │
└───────┬───────┘              └───────┬───────┘              └───────┬───────┘
        │                               │                               │
        └───────────────────────────────┼───────────────────────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │  PRICE LOOKUP   │
                               │  CoinGecko API  │
                               │  (w/ fallback)  │
                               └────────┬────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │ CALCULATE:      │
                               │ - Balance       │
                               │ - Flow In/Out   │
                               │ - USD Values    │
                               │ - Gas Fees      │
                               └────────┬────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │ RETURN RESULTS  │
                               │ to Frontend     │
                               └─────────────────┘
```

---

## Tax Calculation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TAX CALCULATION FLOW (FIFO)                          │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT SOURCES:
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Wallet    │    │  Exchange   │    │  Combined   │
│Transactions │    │CSV Imports  │    │   (Both)    │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                   │                  │
       └───────────────────┼──────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ SORT BY DATE    │
                  │ (Oldest First)  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ IDENTIFY TYPE:  │
                  │ BUY/SELL/OTHER  │
                  └────────┬────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
     ┌──────────┐    ┌──────────┐    ┌──────────┐
     │   BUY    │    │   SELL   │    │  OTHER   │
     │ Create   │    │ Match to │    │ Income/  │
     │ Tax Lot  │    │ Tax Lots │    │ Gift/etc │
     └────┬─────┘    └────┬─────┘    └────┬─────┘
          │               │               │
          │               ▼               │
          │    ┌─────────────────────┐    │
          │    │ FIFO MATCHING:      │    │
          │    │ 1. Find oldest lot  │    │
          │    │ 2. Calculate gain   │    │
          │    │ 3. Determine term   │    │
          │    │    (ST < 1yr, LT)   │    │
          │    └──────────┬──────────┘    │
          │               │               │
          └───────────────┼───────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ TAX SUMMARY:    │
                 │ - Realized Gain │
                 │ - Unrealized    │
                 │ - Short-term    │
                 │ - Long-term     │
                 └────────┬────────┘
                          │
           ┌──────────────┼──────────────┐
           │              │              │
           ▼              ▼              ▼
    ┌───────────┐  ┌───────────┐  ┌───────────┐
    │ Form 8949 │  │Schedule D │  │    CSV    │
    │   Export  │  │  Summary  │  │  Export   │
    └───────────┘  └───────────┘  └───────────┘
```

---

## Exchange Integration Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       EXCHANGE INTEGRATION FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

METHOD 1: CSV IMPORT
┌──────────┐    ┌───────────┐    ┌──────────┐    ┌─────────────┐
│ Upload   │───▶│ Auto-     │───▶│ Parse    │───▶│ Normalize   │
│ CSV File │    │ Detect    │    │ Headers  │    │ Transactions│
└──────────┘    │ Exchange  │    └──────────┘    └──────┬──────┘
                └───────────┘                           │
                                                        ▼
                                               ┌─────────────────┐
                                               │ Store in MongoDB│
                                               │ exchange_txns   │
                                               └─────────────────┘

SUPPORTED CSV FORMATS:
┌────────────┬────────────────────────────────────────────────────┐
│ Exchange   │ Detected Columns                                   │
├────────────┼────────────────────────────────────────────────────┤
│ Coinbase   │ Timestamp, Transaction Type, Asset, Quantity       │
│ Binance    │ Date(UTC), Pair, Side, Price, Executed             │
│ Kraken     │ time, type, pair, price, vol                       │
│ Gemini     │ Date, Type, Symbol, Amount, Price                  │
│ Crypto.com │ Timestamp (UTC), Transaction Kind, Currency        │
│ KuCoin     │ Time, Side, Symbol, Filled Price                   │
└────────────┴────────────────────────────────────────────────────┘


METHOD 2: API CONNECTION (READ-ONLY)
┌──────────┐    ┌───────────┐    ┌──────────┐    ┌─────────────┐
│ Enter    │───▶│ Encrypt   │───▶│ Store    │───▶│ Fetch       │
│ API Keys │    │ Keys      │    │ Encrypted│    │ Addresses   │
└──────────┘    │ (Fernet)  │    │ in MongoDB│   └──────┬──────┘
                └───────────┘    └──────────┘           │
                                                        ▼
                                               ┌─────────────────┐
                                               │ Use for Chain   │
                                               │ of Custody      │
                                               └─────────────────┘

SUPPORTED API EXCHANGES:
┌─────────────────────────────────────────────────────────────────┐
│ Coinbase (OAuth) │ Binance │ Kraken │ Gemini │ Crypto.com      │
│ KuCoin │ OKX │ Bybit │ Gate.io                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Chain of Custody Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CHAIN OF CUSTODY FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT METHODS:
┌─────────────────┐         ┌─────────────────┐
│ COINBASE OAUTH  │         │  MANUAL ENTRY   │
│ Auto-import     │         │ Enter addresses │
│ addresses       │         │ one by one      │
└────────┬────────┘         └────────┬────────┘
         │                           │
         └─────────────┬─────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ TARGET WALLET   │
              │ ADDRESS         │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ FETCH INCOMING  │◀──────────────────────┐
              │ TRANSACTIONS    │                       │
              └────────┬────────┘                       │
                       │                                │
                       ▼                                │
              ┌─────────────────┐                       │
              │ FOR EACH TX:    │                       │
              │ Check sender    │                       │
              └────────┬────────┘                       │
                       │                                │
       ┌───────────────┼───────────────┐               │
       │               │               │               │
       ▼               ▼               ▼               │
┌───────────┐   ┌───────────┐   ┌───────────┐         │
│ EXCHANGE  │   │    DEX    │   │  DORMANT  │         │
│ DETECTED  │   │ DETECTED  │   │  WALLET   │         │
│           │   │           │   │ (>365 days│         │
│ Coinbase  │   │ Uniswap   │   │ inactive) │         │
│ Binance   │   │ SushiSwap │   │           │         │
│ Kraken    │   │ 1inch     │   │           │         │
│ etc.      │   │ etc.      │   │           │         │
└─────┬─────┘   └─────┬─────┘   └─────┬─────┘         │
      │               │               │               │
      │   STOP        │   STOP        │   STOP        │
      │   TRACING     │   TRACING     │   TRACING     │
      │               │               │               │
      └───────────────┼───────────────┘               │
                      │                               │
                      │ NOT FOUND? ───────────────────┘
                      │ Recurse to sender's
                      │ incoming transactions
                      │ (up to max_depth)
                      │
                      ▼
              ┌─────────────────┐
              │ BUILD RESULTS:  │
              │ - Transaction   │
              │   Chain         │
              │ - Origin Type   │
              │ - Flow Graph    │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
 ┌───────────┐  ┌───────────┐  ┌───────────┐
 │   TABLE   │  │   GRAPH   │  │    PDF    │
 │   VIEW    │  │   VIEW    │  │  REPORT   │
 └───────────┘  └───────────┘  └───────────┘
```

---

## Payment/Subscription Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PAYMENT/SUBSCRIPTION FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

UPGRADE FLOW:
┌──────────┐    ┌───────────┐    ┌──────────┐    ┌─────────────┐
│ Click    │───▶│ Apply     │───▶│ Create   │───▶│ Redirect to │
│ Upgrade  │    │ Affiliate │    │ Stripe   │    │ Stripe      │
└──────────┘    │ Code      │    │ Session  │    │ Checkout    │
                │ (-$10)    │    └──────────┘    └──────┬──────┘
                └───────────┘                           │
                                                        ▼
                                               ┌─────────────────┐
                                               │ STRIPE CHECKOUT │
                                               │ - Card Details  │
                                               │ - Billing Info  │
                                               └────────┬────────┘
                                                        │
                           ┌────────────────────────────┼────────────────┐
                           │                            │                │
                           ▼                            ▼                ▼
                    ┌───────────┐              ┌───────────┐     ┌───────────┐
                    │  SUCCESS  │              │  CANCEL   │     │  FAILURE  │
                    └─────┬─────┘              └───────────┘     └───────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ STRIPE WEBHOOK  │
                 │ checkout.       │
                 │ session.        │
                 │ completed       │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ UPDATE USER:    │
                 │ - tier=unlimited│
                 │ - stripe_ids    │
                 │ - period_end    │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ AFFILIATE       │
                 │ COMMISSION      │
                 │ +$10 credited   │
                 └─────────────────┘


SUBSCRIPTION LIFECYCLE:
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  ACTIVE       │───▶│  RENEWAL      │───▶│  RENEWED      │
│  Subscription │    │  (Annual)     │    │  for 1 year   │
└───────────────┘    └───────────────┘    └───────────────┘
        │
        │ User cancels
        ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ CANCEL AT     │───▶│  PERIOD END   │───▶│  DOWNGRADE    │
│ PERIOD END    │    │  REACHED      │    │  to FREE      │
└───────────────┘    └───────────────┘    └───────────────┘
```

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW ARCHITECTURE                               │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │    FRONTEND     │
                              │    (React)      │
                              │  Port 3000      │
                              └────────┬────────┘
                                       │
                                       │ HTTPS
                                       │ /api/*
                                       ▼
                              ┌─────────────────┐
                              │    BACKEND      │
                              │   (FastAPI)     │
                              │   Port 8001     │
                              └────────┬────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────┐            ┌───────────────┐            ┌───────────────┐
│   MONGODB     │            │  BLOCKCHAIN   │            │   EXTERNAL    │
│               │            │     APIs      │            │    SERVICES   │
│ - users       │            │               │            │               │
│ - wallets     │            │ - Alchemy     │            │ - Stripe      │
│ - exchange_tx │            │ - Blockstream │            │ - CoinGecko   │
│ - categories  │            │ - BlockCypher │            │ - Coinbase    │
│ - custody     │            │ - Algonode    │            │   OAuth       │
│ - affiliates  │            │               │            │               │
└───────────────┘            └───────────────┘            └───────────────┘


ENVIRONMENT VARIABLES:
┌─────────────────────────────────────────────────────────────────────────────┐
│ FRONTEND                          │ BACKEND                                 │
├───────────────────────────────────┼─────────────────────────────────────────┤
│ REACT_APP_BACKEND_URL             │ MONGO_URL                               │
│                                   │ DB_NAME                                 │
│                                   │ STRIPE_API_KEY                          │
│                                   │ STRIPE_WEBHOOK_SECRET                   │
│                                   │ STRIPE_PRICE_ID_PREMIUM                 │
│                                   │ ALCHEMY_API_KEY                         │
│                                   │ ENCRYPTION_KEY                          │
│                                   │ COINBASE_CLIENT_ID                      │
│                                   │ COINBASE_CLIENT_SECRET                  │
│                                   │ COINBASE_REDIRECT_URI                   │
│                                   │ CORS_ORIGINS                            │
└───────────────────────────────────┴─────────────────────────────────────────┘
```

---

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ERROR HANDLING FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   USER ACTION   │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │   API REQUEST   │
                              └────────┬────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
             ┌───────────┐      ┌───────────┐      ┌───────────┐
             │  SUCCESS  │      │   AUTH    │      │  SERVER   │
             │   200     │      │  ERROR    │      │   ERROR   │
             └─────┬─────┘      │  401/403  │      │   500     │
                   │            └─────┬─────┘      └─────┬─────┘
                   │                  │                  │
                   ▼                  ▼                  ▼
             ┌───────────┐      ┌───────────┐      ┌───────────┐
             │  Update   │      │  Redirect │      │   Toast   │
             │    UI     │      │  to Login │      │   Error   │
             └───────────┘      └───────────┘      │  Message  │
                                                   └───────────┘

RATE LIMITING FALLBACKS:
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ CoinGecko       │─────▶│ Rate Limited    │─────▶│ Use Fallback    │
│ API Call        │      │ (429)           │      │ Prices          │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

---

*Document Version: 2.1*  
*Last Updated: March 10, 2026*
