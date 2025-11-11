# Where to Find the Downgrade Option

## Location: User Info Bar

When you're logged in as a **Premium** or **Pro** user, you'll see a small **"manage"** link next to your subscription information.

### Visual Location:

```
┌─────────────────────────────────────────────────┐
│  👤 [User Icon]  your@email.com                │
│     [PREMIUM Badge] 0 analyses today manage ← HERE │
│                                    [Upgrade] [Logout] │
└─────────────────────────────────────────────────┘
```

### What It Looks Like:
- **Text**: "manage"
- **Style**: Small, gray, underlined
- **Location**: Right after "X analyses today"
- **Only visible**: For Premium and Pro users (NOT Free tier)

### What It Does:
- Clicking it opens your email client
- Pre-fills email to: `support@shoestringwallet.com`
- Pre-fills subject: "Downgrade Request"
- You can then send your downgrade request

### Why It's Subtle:
- Intentionally not prominent (per your request)
- Doesn't encourage downgrades
- Available when needed but not in your face

---

## If You Don't See It:

**Possible reasons:**
1. You're logged in as a **Free** user (downgrade option only for paid tiers)
2. The frontend hasn't been updated on Render yet (still needs deployment)
3. You need to refresh the page after login

**To test locally:**
1. Login with a test account
2. Upgrade that account to Premium (via database or payment)
3. The "manage" link should appear next to your subscription badge

---

## Alternative: Manual Downgrade Process

If the link isn't working or visible, users can always:
1. Email directly: support@shoestringwallet.com
2. Use the subject: "Downgrade Request"
3. Include their account email
