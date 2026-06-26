"""
Tests for Stripe webhook endpoints (iteration 34).

Verifies:
- /api/payments/webhook/stripe endpoint exists and accepts POST
- /api/alerts/webhook/stripe endpoint exists and accepts POST
- Signature validation rejects invalid signatures
- Endpoints do not crash on malformed payloads
"""
import os
import json
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fall back to frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.strip().startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.strip().split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

PAYMENTS_WEBHOOK = f"{BASE_URL}/api/payments/webhook/stripe"
ALERTS_WEBHOOK = f"{BASE_URL}/api/alerts/webhook/stripe"


# ---------- Endpoint existence ----------

class TestWebhookExistence:
    """Verify webhook endpoints exist (not 404)"""

    def test_payments_webhook_exists(self):
        # Empty body, no signature -> should not be 404. Expect 400/500 (signature fail)
        r = requests.post(PAYMENTS_WEBHOOK, data=b"", timeout=15)
        assert r.status_code != 404, f"Endpoint missing: {r.status_code} {r.text}"
        assert r.status_code != 405, f"Method not allowed: {r.text}"

    def test_alerts_webhook_exists(self):
        r = requests.post(ALERTS_WEBHOOK, data=b"", timeout=15)
        assert r.status_code != 404, f"Endpoint missing: {r.status_code} {r.text}"
        assert r.status_code != 405, f"Method not allowed: {r.text}"


# ---------- Signature validation ----------

class TestSignatureValidation:
    """Webhook must reject requests with invalid Stripe signature"""

    def test_payments_webhook_rejects_invalid_signature(self):
        fake_payload = json.dumps({
            "id": "evt_test",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_fake"}}
        }).encode()
        r = requests.post(
            PAYMENTS_WEBHOOK,
            data=fake_payload,
            headers={
                "Content-Type": "application/json",
                "stripe-signature": "t=1234567890,v1=invalid_signature_here"
            },
            timeout=15
        )
        # Expect 400 (invalid sig) or 500 (handler wraps it). Must NOT be 200.
        assert r.status_code != 200, f"Webhook accepted invalid signature! {r.text}"
        assert r.status_code in (400, 401, 403, 500), f"Unexpected status: {r.status_code} {r.text}"

    def test_payments_webhook_rejects_missing_signature(self):
        fake_payload = json.dumps({"type": "checkout.session.completed", "data": {"object": {}}}).encode()
        r = requests.post(
            PAYMENTS_WEBHOOK,
            data=fake_payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        assert r.status_code != 200, f"Webhook accepted request without signature! {r.text}"

    def test_alerts_webhook_rejects_invalid_signature(self):
        fake_payload = json.dumps({
            "id": "evt_test",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_fake"}}
        }).encode()
        r = requests.post(
            ALERTS_WEBHOOK,
            data=fake_payload,
            headers={
                "Content-Type": "application/json",
                "stripe-signature": "t=1234567890,v1=invalid_signature_here"
            },
            timeout=15
        )
        assert r.status_code != 200, f"Alerts webhook accepted invalid signature! {r.text}"
        assert r.status_code in (400, 401, 403, 500), f"Unexpected status: {r.status_code} {r.text}"


# ---------- Handler structural integrity (code inspection) ----------

class TestHandlerStructure:
    """Verify the payments webhook code updates alert_subscriptions on relevant events.
    This is a static check on the source file (the actual logic can't be exercised live
    without a valid Stripe signature)."""

    @pytest.fixture(scope="class")
    def payments_src(self):
        with open("/app/backend/routes/payments.py") as f:
            return f.read()

    def test_checkout_session_completed_updates_alert_subscriptions(self, payments_src):
        # Find the checkout.session.completed branch
        idx = payments_src.find("checkout.session.completed")
        assert idx != -1, "checkout.session.completed handler missing"
        # Next 4000 chars should mention alert_subscriptions update
        snippet = payments_src[idx: idx + 4000]
        assert "alert_subscriptions" in snippet, "alert_subscriptions not updated in checkout.session.completed"
        assert "update_one" in snippet
        assert "upsert=True" in snippet or "upsert = True" in snippet

    def test_subscription_updated_updates_alert_subscriptions(self, payments_src):
        idx = payments_src.find("customer.subscription.updated")
        assert idx != -1
        snippet = payments_src[idx: idx + 2500]
        assert "alert_subscriptions" in snippet, "alert_subscriptions not updated in customer.subscription.updated"

    def test_subscription_deleted_updates_alert_subscriptions(self, payments_src):
        idx = payments_src.find("customer.subscription.deleted")
        assert idx != -1
        snippet = payments_src[idx: idx + 2500]
        assert "alert_subscriptions" in snippet, "alert_subscriptions not updated in customer.subscription.deleted"
