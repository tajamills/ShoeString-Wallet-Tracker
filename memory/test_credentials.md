# Test Credentials for Crypto Bag Tracker

## Primary Test User
- **Email**: mobiletest@test.com
- **Password**: test123456
- **User ID**: 6f9b5c58-a65b-42c4-afa6-f206bbb4876c
- **Subscription**: Free Trial (6 days remaining as of Jun 6, 2026)
- **Features**: Unlimited alerts during trial

## Notes
- This user has an active free trial for the Price Alerts feature
- One BTC price alert exists ($100,000 price_above threshold)
- Trial expires 2026-06-13

## Stripe Configuration (Live)
- API Key: sk_live_51SS4RvAXuTzNcQX7... (in backend/.env)
- Product ID: prod_UecNCOQUgkIyrk
- Price ID: price_1TfJ8WAXuTzNcQX7GPkmVilU
- Subscription: $18.88/month unlimited alerts with 7-day free trial

## Telegram Bot
- Bot Username: @cryptobagtrackerbot
- Bot Token: 8248830850:AAGJerBuuF8JfyAZy9i5BoTLMQDTDDDZzdo (in backend/.env)
- Webhook URL: https://proceeds-validator.preview.emergentagent.com/api/alerts/telegram/webhook

## Zapier Webhook (SMS)
- URL: https://hooks.zapier.com/hooks/catch/27857399/4bx050v/
- Used for SMS notifications

## Notification Methods
- **Telegram**: Primary - unlimited, instant (requires user to connect via @cryptobagtrackerbot)
- **SMS**: Secondary - via Zapier webhook (no email due to rate limits)
