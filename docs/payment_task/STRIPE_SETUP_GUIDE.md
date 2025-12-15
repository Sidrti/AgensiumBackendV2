# Stripe Setup Guide

## Overview

This guide explains how to configure Stripe for the Agensium prepaid credit billing system.

## Prerequisites

1. A Stripe account (create one at https://stripe.com)
2. Access to the Stripe Dashboard
3. Access to your backend `.env` file

---

## Step 1: Get API Keys

### Development (Test Mode)

1. Go to https://dashboard.stripe.com/test/apikeys
2. Copy the **Secret key** (starts with `sk_test_`)
3. Add to `.env`:
   ```
   STRIPE_API_KEY=sk_test_your_secret_key_here
   ```

### Production (Live Mode)

1. Go to https://dashboard.stripe.com/apikeys
2. Copy the **Secret key** (starts with `sk_live_`)
3. Add to production `.env`:
   ```
   STRIPE_API_KEY=sk_live_your_secret_key_here
   ```

> ⚠️ **NEVER** commit API keys to version control!

---

## Step 2: Create Products & Prices

### Create Credit Products

1. Go to https://dashboard.stripe.com/products
2. Click **Add product**
3. Create products for each credit package:

#### 1,000 Credits - Starter Pack

- Name: `Agensium Credits - 1K Pack`
- Description: `1,000 credits for data processing`
- Price: `$9.99` (one-time)
- Copy the **Price ID** (starts with `price_`)

#### 5,000 Credits - Standard Pack

- Name: `Agensium Credits - 5K Pack`
- Description: `5,000 credits for data processing`
- Price: `$44.99` (one-time)
- Copy the **Price ID**

#### 10,000 Credits - Professional Pack

- Name: `Agensium Credits - 10K Pack`
- Description: `10,000 credits for data processing`
- Price: `$89.99` (one-time)
- Copy the **Price ID**

### Update credit_packages.json

Update `backend/billing/credit_packages.json` with your Price IDs:

```json
{
  "packages": [
    {
      "package_id": "pack_1k",
      "credits": 1000,
      "stripe_price_id": "price_YOUR_ACTUAL_PRICE_ID_1K",
      "amount_cents": 999,
      "currency": "usd"
    },
    {
      "package_id": "pack_5k",
      "credits": 5000,
      "stripe_price_id": "price_YOUR_ACTUAL_PRICE_ID_5K",
      "amount_cents": 4499,
      "currency": "usd"
    },
    {
      "package_id": "pack_10k",
      "credits": 10000,
      "stripe_price_id": "price_YOUR_ACTUAL_PRICE_ID_10K",
      "amount_cents": 8999,
      "currency": "usd"
    }
  ]
}
```

---

## Step 3: Configure Webhooks

### Development (Local Testing)

For local development, use Stripe CLI:

1. Install Stripe CLI: https://stripe.com/docs/stripe-cli
2. Login: `stripe login`
3. Forward webhooks:
   ```bash
   stripe listen --forward-to localhost:8000/billing/webhook
   ```
4. Copy the webhook signing secret (starts with `whsec_`)
5. Add to `.env`:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_your_local_secret
   ```

### Production

1. Go to https://dashboard.stripe.com/webhooks
2. Click **Add endpoint**
3. Enter your endpoint URL:
   ```
   https://your-api-domain.com/billing/webhook
   ```
4. Select events to listen to:
   - `checkout.session.completed` (required)
   - `payment_intent.succeeded` (optional)
   - `charge.refunded` (optional for future refund handling)
5. Click **Add endpoint**
6. Copy the **Signing secret** (starts with `whsec_`)
7. Add to production `.env`:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_your_production_secret
   ```

---

## Step 3.5: Verify Database Migration ✅

Before testing Stripe integration, ensure the database is properly set up:

```bash
# The migration was executed on 2025-12-13
# Verify tables exist:
python -c "
from billing.migrations.create_billing_tables import verify_stripe_columns
verify_stripe_columns()
"
```

You should see:

```
✓ stripe_customer_id column exists in users table
✓ Table 'credit_wallets' exists
✓ Table 'credit_transactions' exists
✓ Table 'stripe_webhook_events' exists
✓ Table 'agent_costs' exists
✓ Default agent costs seeded (22 agents)
```

If tables are missing, run the migration:

```bash
python -m billing.migrations.create_billing_tables
```

---

## Step 4: Test the Integration

### 1. Test Checkout Flow

```bash
# Get available packages
curl -X GET "http://localhost:8000/billing/packages" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Create checkout session
curl -X POST "http://localhost:8000/billing/checkout-session" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"package_id": "pack_5k"}'
```

### 2. Test with Stripe Test Cards

Use these test card numbers:

- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **3D Secure**: `4000 0000 0000 3220`

Use any future expiry date and any CVC.

### 3. Verify Webhook

When using Stripe CLI for local testing:

```bash
# Trigger a test webhook
stripe trigger checkout.session.completed
```

Check your server logs for:

```
[Billing] Granted X credits to user Y
```

---

## Troubleshooting

### "Invalid API Key"

- Verify `STRIPE_API_KEY` in `.env`
- Ensure no extra whitespace
- Check you're using the correct mode (test vs live)

### "Invalid Signature"

- Verify `STRIPE_WEBHOOK_SECRET` in `.env`
- Ensure you're using the correct secret for your environment
- Check webhook endpoint URL matches exactly

### "Price not found"

- Verify Price IDs in `credit_packages.json`
- Ensure products exist in your Stripe Dashboard
- Check you're using Price IDs (not Product IDs)

### Webhook not receiving events

- Verify endpoint URL is publicly accessible (for production)
- Check Stripe Dashboard > Webhooks > Events for errors
- Ensure SSL certificate is valid (for production)

---

## Security Best Practices

1. **Never log full webhook payloads** - they may contain sensitive data
2. **Always verify webhook signatures** - protects against replay attacks
3. **Use environment variables** - never hardcode API keys
4. **Separate test and live keys** - use different `.env` files
5. **Monitor webhook failures** - set up alerts in Stripe Dashboard
6. **Implement idempotency** - prevent double-charging (already handled)

---

## Quick Reference

### API Endpoints

| Endpoint                    | Method | Description                |
| --------------------------- | ------ | -------------------------- |
| `/billing/wallet`           | GET    | Get balance & transactions |
| `/billing/packages`         | GET    | List available packages    |
| `/billing/checkout-session` | POST   | Create checkout session    |
| `/billing/webhook`          | POST   | Stripe webhook handler     |
| `/billing/agent-costs`      | GET    | List agent costs           |

### Error Codes

| Code                           | HTTP | Meaning                  |
| ------------------------------ | ---- | ------------------------ |
| `BILLING_INSUFFICIENT_CREDITS` | 402  | Not enough credits       |
| `BILLING_WALLET_NOT_FOUND`     | 404  | No wallet exists         |
| `BILLING_INVALID_PACKAGE`      | 400  | Invalid package ID       |
| `BILLING_INVALID_SIGNATURE`    | 400  | Webhook signature failed |

---

## Support

- Stripe Documentation: https://stripe.com/docs
- Stripe API Reference: https://stripe.com/docs/api
- Stripe Support: https://support.stripe.com/
