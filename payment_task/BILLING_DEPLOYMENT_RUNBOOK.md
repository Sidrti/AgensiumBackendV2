# Billing System Deployment Runbook

## Quick Start Checklist

### 1. Environment Setup (5 minutes)

```bash
# Copy example environment file
cp .env.example .env

# Edit with your values
# Required variables:
# - DATABASE_URL (already configured)
# - STRIPE_API_KEY (from Stripe Dashboard)
# - STRIPE_WEBHOOK_SECRET (from Stripe webhook setup)
```

### 2. Install Dependencies (2 minutes)

```bash
pip install -r requirements.txt
```

New dependencies added:

- `stripe>=10.0.0` - Stripe SDK
- `alembic>=1.13.0` - Database migrations

### 3. Run Database Migration (1 minute) ✅ COMPLETED

```bash
# From the backend directory
python -m billing.migrations.create_billing_tables
```

This will:

- ✅ Add `stripe_customer_id` column to users table
- ✅ Create `credit_wallets` table
- ✅ Create `credit_transactions` table
- ✅ Create `stripe_webhook_events` table
- ✅ Create `agent_costs` table
- ✅ Seed default agent costs (22 agents with pricing)

**Status:** Migration completed successfully on 2025-12-13

- All tables created
- All indexes created
- Default agent costs seeded with values ranging from 20-150 credits

### 4. Update Stripe Price IDs (5 minutes)

1. Create products in Stripe Dashboard
2. Copy Price IDs
3. Update `billing/credit_packages.json`:

```json
{
  "packages": [
    {
      "package_id": "pack_1k",
      "stripe_price_id": "price_REAL_ID_HERE",
      ...
    }
  ]
}
```

### 5. Verify Installation

```bash
# Start the server
uvicorn main:app --reload

# Test health check
curl http://localhost:8000/health

# Test billing packages endpoint
curl http://localhost:8000/billing/packages
```

---

## Verification Tests

### Test 1: Check Agent Costs Loaded

```bash
curl http://localhost:8000/billing/agent-costs
```

Expected: JSON with 22 agent costs (20-150 credits each)

### Test 2: Wallet Auto-Creation

When a user first accesses their wallet, it's auto-created with 0 balance:

```bash
curl -X GET http://localhost:8000/billing/wallet \
  -H "Authorization: Bearer JWT_TOKEN"
```

Expected: `{"balance_credits": 0, "transactions": []}`

### Test 3: Insufficient Credits Error

```bash
# Try to run an agent without credits
curl -X POST http://localhost:8000/api/profile-my-data \
  -H "Authorization: Bearer JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tool_configuration": {...}}'
```

Expected: 402 error with `"error_code": "BILLING_INSUFFICIENT_CREDITS"`

### Test 4: Admin Grant Credits

```bash
curl -X POST http://localhost:8000/billing/admin/grant \
  -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "credits": 1000, "reason": "Testing"}'
```

Expected: `{"success": true, "new_balance": 1000}`

---

## Production Deployment

### Environment Variables Required

```bash
# Database
DATABASE_URL=mysql+pymysql://user:pass@host:port/db

# Stripe (LIVE keys)
STRIPE_API_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Frontend URL for redirects
FRONTEND_URL=https://your-app.com

# AI (existing)
OPENAI_API_KEY=sk-xxx
```

### Stripe Webhook Configuration

1. Go to Stripe Dashboard > Webhooks
2. Add endpoint: `https://your-api.com/billing/webhook`
3. Select event: `checkout.session.completed`
4. Copy signing secret to `STRIPE_WEBHOOK_SECRET`

### Database Migration (Production)

Option A: Run migration script

```bash
python -m billing.migrations.create_billing_tables
```

Option B: Manual SQL (see output of):

```python
from billing.migrations.create_billing_tables import show_migration_sql
show_migration_sql()
```

---

## Rollback Procedure

If issues occur, rollback in reverse order:

1. **Disable billing router** in `main.py`:

   ```python
   # Comment out:
   # app.include_router(billing_router)
   ```

2. **Disable billing enforcement** in transformers:

   ```python
   # Comment out billing blocks in:
   # - clean_my_data_transformer.py
   # - master_my_data_transformer.py
   # - profile_my_data_transformer.py
   ```

3. **Keep database tables** - no data loss needed for rollback

---

## Monitoring

### Key Metrics to Watch

1. **Webhook success rate** - Stripe Dashboard > Webhooks > Events
2. **Transaction volume** - Query `credit_transactions` table
3. **Failed payments** - Filter transactions with `stripe_payment_intent_id IS NULL`
4. **Agent usage** - Group transactions by `agent_id`

### Log Messages to Monitor

```
[Billing] Charged X credits from user Y for agent Z
[Billing] Granted X credits to user Y
[Billing] Webhook processed: checkout_session_xxx
[Billing] Error: Insufficient credits for user X
```

---

## Troubleshooting

### Problem: Migration fails

**Solution**: Check database connection and permissions

```bash
# Test connection
python -c "from db.database import engine; print(engine.connect())"
```

### Problem: Webhook signature invalid

**Solution**: Verify webhook secret matches environment

- Check Stripe Dashboard webhook settings
- Ensure no extra whitespace in `.env`
- Use correct secret (test vs live)

### Problem: Credits not granted after payment

**Solution**: Check webhook events

1. Stripe Dashboard > Webhooks > Events
2. Look for `checkout.session.completed`
3. Check event payload has correct metadata
4. Check `stripe_webhook_events` table for duplicates

### Problem: Agent cost not found

**Solution**: Seed costs or add manually

```bash
curl -X POST http://localhost:8000/billing/admin/seed-costs \
  -H "Authorization: Bearer ADMIN_JWT_TOKEN"
```

---

## Support Contacts

- Stripe Support: https://support.stripe.com/
- Database Issues: Check Aiven console
- Application Errors: Check server logs
