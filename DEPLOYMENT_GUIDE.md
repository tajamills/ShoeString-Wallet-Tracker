# ShoeString Wallet Tracker - Deployment Guide

## Option 1: Vercel (Easiest - Recommended for Frontend)

### Why Vercel?
- ✅ Free tier available
- ✅ Automatic deployments from Git
- ✅ Built-in CI/CD
- ✅ Best for React apps
- ❌ Backend requires serverless functions (not ideal for FastAPI)

### Steps:
1. **Push to GitHub**
   ```bash
   cd /app
   git init
   git add .
   git commit -m "Initial commit - ShoeString Wallet Tracker"
   gh repo create shoestring-wallet-tracker --public --source=. --push
   ```

2. **Deploy Frontend to Vercel**
   - Go to https://vercel.com
   - Click "New Project"
   - Import your GitHub repo
   - Set Root Directory: `frontend`
   - Environment Variables:
     - `REACT_APP_BACKEND_URL` = (your backend URL - see Option 2/3)
   - Click Deploy

3. **Backend**: Deploy separately (see Option 2 or 3 below)

---

## Option 2: Railway (Best All-in-One Solution) ⭐ RECOMMENDED

### Why Railway?
- ✅ Free $5/month credit
- ✅ Supports FastAPI + React + MongoDB
- ✅ One-click deployment
- ✅ Automatic HTTPS
- ✅ Built-in database hosting

### Steps:

1. **Create Railway Account**
   - Go to https://railway.app
   - Sign up with GitHub

2. **Push Code to GitHub First**
   ```bash
   cd /app
   git init
   git add .
   git commit -m "Initial commit"
   gh repo create shoestring-wallet-tracker --public --source=. --push
   ```

3. **Deploy Backend on Railway**
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repo
   - Railway auto-detects Python/FastAPI
   - Add Environment Variables:
     ```
     MONGO_URL=<Railway will provide this>
     DB_NAME=shoestring_db
     CORS_ORIGINS=*
     ALCHEMY_API_KEY=U2_F7nkCGFY73wbiIFpum
     JWT_SECRET_KEY=crypto-wallet-tracker-secret-key-2025-change-in-production
     NOWPAYMENTS_API_KEY=AG6C7RA-51J4B4Y-QNY2906-WNRWA80
     NOWPAYMENTS_IPN_SECRET=your-ipn-secret-key-here
     PORT=8001
     ```
   - Set Start Command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - Set Root Directory: `backend`

4. **Add MongoDB on Railway**
   - In same project, click "New" → "Database" → "MongoDB"
   - Railway auto-generates MONGO_URL
   - Copy MONGO_URL to backend environment variables

5. **Deploy Frontend on Railway**
   - Click "New Service" → "GitHub Repo"
   - Select same repo
   - Set Root Directory: `frontend`
   - Add Environment Variables:
     ```
     REACT_APP_BACKEND_URL=https://your-backend-url.railway.app
     ```
   - Railway auto-deploys React app

6. **Get URLs**
   - Backend: `https://shoestring-backend-xxx.railway.app`
   - Frontend: `https://shoestring-frontend-xxx.railway.app`

---

## Option 3: Render (Good Free Tier)

### Why Render?
- ✅ Free tier with 750 hours/month
- ✅ Supports FastAPI + React
- ✅ Auto-deploy from Git
- ✅ Free PostgreSQL (but you use MongoDB)

### Steps:

1. **Push to GitHub** (same as above)

2. **Deploy Backend**
   - Go to https://render.com
   - Click "New" → "Web Service"
   - Connect GitHub repo
   - Settings:
     - Name: `shoestring-backend`
     - Root Directory: `backend`
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
     - Environment: Python 3
   - Add Environment Variables (same as Railway)

3. **Add MongoDB**
   - Use MongoDB Atlas (free tier): https://www.mongodb.com/cloud/atlas
   - Create cluster → Get connection string
   - Add to Render environment variables

4. **Deploy Frontend**
   - Click "New" → "Static Site"
   - Connect GitHub repo
   - Settings:
     - Root Directory: `frontend`
     - Build Command: `yarn install && yarn build`
     - Publish Directory: `build`
   - Add Environment Variable:
     ```
     REACT_APP_BACKEND_URL=https://shoestring-backend.onrender.com
     ```

---

## Option 4: DigitalOcean App Platform

### Why DigitalOcean?
- ✅ $5/month for basic apps
- ✅ Full control
- ✅ Managed MongoDB available

### Steps:
1. Sign up at https://www.digitalocean.com
2. Create new app from GitHub repo
3. Configure components:
   - Backend (Python)
   - Frontend (Node.js)
   - MongoDB database
4. Set environment variables
5. Deploy

---

## Recommended Approach: Railway 🚀

**Railway is the best choice because:**
1. Easiest setup (one platform for everything)
2. Free $5/month credit
3. Auto-detects FastAPI and React
4. Built-in MongoDB hosting
5. Automatic HTTPS
6. Easy environment variable management

### Quick Railway Deployment (5 minutes):

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Initialize project
cd /app
railway init

# 4. Deploy backend
cd backend
railway up

# 5. Add MongoDB
railway add --plugin mongodb

# 6. Deploy frontend
cd ../frontend
railway up

# 7. Link services
railway link
```

---

## After Deployment Checklist

✅ Backend is accessible (test: `curl https://your-backend.com/api/`)
✅ Frontend loads correctly
✅ Database connection works
✅ User registration/login works
✅ Wallet analysis works
✅ Payment flow works
✅ Environment variables are set
✅ CORS allows your frontend domain

---

## Cost Comparison

| Platform | Free Tier | Paid Plans |
|----------|-----------|------------|
| **Railway** | $5/month credit | $5/month then usage-based |
| **Vercel** | Free for frontend | $20/month Pro |
| **Render** | 750 hours/month free | $7/month |
| **DigitalOcean** | No free tier | $5/month minimum |

---

## Troubleshooting

### CORS Errors
- Update `CORS_ORIGINS` in backend .env to include your frontend URL
- Example: `CORS_ORIGINS=https://your-frontend.railway.app,https://your-domain.com`

### Database Connection Issues
- Check MONGO_URL is correct
- Verify MongoDB allows connections from your hosting IP
- For Railway/Render: They handle this automatically

### Environment Variables Not Loading
- Make sure variables are set in hosting platform dashboard
- Restart services after adding variables
- Check variable names match exactly (case-sensitive)

### Payment Webhook Not Working
- Update NOWPayments IPN callback URL to your production backend
- Format: `https://your-backend.railway.app/api/payments/webhook`

---

## Domain Setup (Optional)

Once deployed, you can add a custom domain:

1. **Buy domain** (Namecheap, Google Domains, etc.)
2. **Add to Railway/Vercel/Render**:
   - Go to project settings → Domains
   - Add your domain (e.g., shoestringwallet.com)
3. **Update DNS**:
   - Add CNAME record pointing to your Railway/Vercel URL
4. **Update environment variables**:
   - `REACT_APP_BACKEND_URL=https://api.shoestringwallet.com`
   - `CORS_ORIGINS=https://shoestringwallet.com`

---

## Need Help?

1. **Railway Discord**: https://discord.gg/railway
2. **Vercel Support**: https://vercel.com/support
3. **Render Community**: https://community.render.com

Good luck with deployment! 🚀
