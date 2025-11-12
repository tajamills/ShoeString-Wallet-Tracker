# Complete Deployment Instructions

## What You're Seeing vs What You Need

**Current Situation:**
- ✅ All features working on **localhost** (your development environment)
- ❌ Features NOT on **Render** (your live site) - because code hasn't been pushed

**What You Need to Do:**
Push the updated code from localhost to GitHub, then Render will auto-deploy.

---

## Files to Update in GitHub

You need to update these 7 files in your GitHub repository:

### Backend Files (3 files + 1 new):

**1. `backend/.env`** - Add this line:
```
STRIPE_API_KEY=sk_test_emergent
```
(Make sure NOWPAYMENTS_IPN_SECRET and STRIPE_API_KEY are on separate lines)

**2. `backend/server.py`** - Contains multi-chain support, saved wallets, chain requests

**3. `backend/stripe_service.py`** - Stripe payment integration

**4. `backend/multi_chain_service.py`** - **NEW FILE** - Multi-chain wallet analysis

---

### Frontend Files (3 files + 1 new):

**5. `frontend/src/App.js`** - Contains:
- Chain selector dropdown (Ethereum, Bitcoin, Arbitrum, BSC, Solana)
- Saved wallets toggle
- Downgrade "manage" link
- Fixed analyze button
- Better transaction display

**6. `frontend/src/components/UpgradeModal.js`** - Pro upgrade button logic

**7. `frontend/src/components/SavedWallets.js`** - **NEW FILE** - Wallet storage UI

---

## How to Deploy

### Option 1: Use Git Locally (If you have repo cloned)
```bash
cd /path/to/your/repo
git add .
git commit -m "Add multi-chain, wallet storage, stripe, and downgrade"
git push origin main
```

### Option 2: Manual GitHub Update
1. Go to your GitHub repository
2. Navigate to each file
3. Click "Edit" (pencil icon)
4. Copy the content I provide
5. Commit the changes
6. Render will automatically detect and deploy

### Option 3: Contact Support
If you're on the Standard Plan ($20/mo), you should have the "Save to GitHub" button. If it's missing, there may be a technical issue with the platform.

---

## After Deployment

Once code is pushed to GitHub:
1. Render will detect changes automatically
2. Both frontend and backend will redeploy (takes 3-5 minutes)
3. Visit your live Render URLs to test

**Then you'll see:**
- ⟠ Ethereum, ₿ Bitcoin, 🔷 Arbitrum, 🟡 BSC, ◎ Solana in dropdown
- "Show Saved Wallets" button when logged in
- "manage" link next to subscription badge (Premium/Pro only)

---

## Why You're Not Seeing Features Now

**On Render (your live site):**
- Running OLD code (before multi-chain was added)
- No chain selector beyond Ethereum
- No saved wallets
- No downgrade link

**On Localhost (this environment):**
- Running NEW code (with all features)
- All 5 chains working
- Saved wallets working
- Downgrade link working (for Premium/Pro users)

**Solution:** Push the code to GitHub so Render gets the updates!
