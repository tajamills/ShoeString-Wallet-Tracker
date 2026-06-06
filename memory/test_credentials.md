# Test Credentials for Crypto Bag Tracker

## Primary Test User
- **Email**: mobiletest@test.com
- **Password**: test123456
- **User ID**: 6f9b5c58-a65b-42c4-afa6-f206bbb4876c
- **Subscription**: Free Trial (7 days from 2026-06-06)
- **Features**: Unlimited alerts during trial

## Notes
- This user has an active free trial for the Price Alerts feature
- One BTC price alert exists ($100,000 price_above threshold)
- Trial expires 2026-06-13

## Stripe Test Keys
- Test keys available in pod environment at `/app/.stripe/`
- Product ID: prod_UecNCOQUgkIyrk
- Price ID: price_1TfJ8WAXuTzNcQX7GPkmVilU
- Subscription: $18.88/month unlimited alerts with 7-day free trial

## Notification APIs (Not Yet Configured)
- SendGrid: Requires SENDGRID_API_KEY and SENDER_EMAIL in backend/.env
- Twilio: Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER in backend/.env
