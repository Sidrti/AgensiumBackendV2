# Prepaid Billing System — Complete Flow Example

**A step-by-step walkthrough of how the entire billing system works with real data**

---

## Table of Contents

1. [User Registration](#1-user-registration)
2. [Viewing Available Credit Packages](#2-viewing-available-credit-packages)
3. [Purchasing Credits via Stripe](#3-purchasing-credits-via-stripe)
4. [Credits Received in Wallet](#4-credits-received-in-wallet)
5. [Executing an Agent](#5-executing-an-agent)
6. [Credit Deduction](#6-credit-deduction)
7. [Viewing Wallet & Transaction History](#7-viewing-wallet--transaction-history)
8. [Running Out of Credits](#8-running-out-of-credits)
9. [Database State at Each Step](#9-database-state-at-each-step)

---

## 1. User Registration

### What Happens

User signs up on the frontend with email and password.

### Backend Process

```
POST /auth/signup
├── Input: { "email": "john@example.com", "password": "secure123" }
├── Backend creates new User record
└── User stored in database
```

### Database: `users` table

```
id  | email               | stripe_customer_id | created_at
----|---------------------|-------------------|------------------
1   | john@example.com    | NULL              | 2025-01-10 10:00:00
```

**Status:** User created but has **NO wallet yet** (wallet is created on first billing action)

---

## 2. Viewing Available Credit Packages

### What Happens

User visits the "Buy Credits" page on frontend. Frontend calls the packages endpoint.

### API Request

```
GET /billing/packages
Authorization: Bearer <jwt_token_for_john>
```

### Backend Process

Packages are loaded from `billing/credit_packages.json`:

```python
# stripe_service.py - Load packages from JSON
import json
import os

def load_credit_packages():
    """Load credit packages configuration from JSON file."""
    json_path = os.path.join(
        os.path.dirname(__file__),
        "credit_packages.json"
    )
    with open(json_path, "r") as f:
        config = json.load(f)
    return config["packages"]

CREDIT_PACKAGES = load_credit_packages()
```

The `billing/credit_packages.json` file contains:

```json
{
  "packages": [
    {
      "package_id": "pack_1k",
      "credits": 1000,
      "stripe_price_id": "price_1IqkLmAxxx",
      "amount_cents": 999,
      "currency": "usd"
    },
    {
      "package_id": "pack_5k",
      "credits": 5000,
      "stripe_price_id": "price_2JpkMnByyy",
      "amount_cents": 4499,
      "currency": "usd"
    },
    {
      "package_id": "pack_10k",
      "credits": 10000,
      "stripe_price_id": "price_3KqlNoZzzz",
      "amount_cents": 8999,
      "currency": "usd"
    }
  ]
}
```

### API Response

```json
{
  "packages": [
    {
      "package_id": "pack_1k",
      "credits": 1000,
      "stripe_price_id": "price_1IqkLmAxxx",
      "amount_cents": 999,
      "currency": "usd"
    },
    {
      "package_id": "pack_5k",
      "credits": 5000,
      "stripe_price_id": "price_2JpkMnByyy",
      "amount_cents": 4499,
      "currency": "usd"
    },
    {
      "package_id": "pack_10k",
      "credits": 10000,
      "stripe_price_id": "price_3KqlNoZzzz",
      "amount_cents": 8999,
      "currency": "usd"
    }
  ]
}
```

**Frontend displays:** "Get 5,000 credits for $44.99"

---

## 3. Purchasing Credits via Stripe

### What Happens

User clicks "Buy 5,000 credits" button. Frontend initiates checkout.

### API Request

```
POST /billing/checkout-session
Authorization: Bearer <jwt_token_for_john>
Content-Type: application/json

{
  "package_id": "pack_5k"
}
```

### Backend Process

```python
# router.py - Checkout endpoint
@router.post("/billing/checkout-session")
async def create_checkout_session(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user)
):
    package = PACKAGES[request.package_id]  # pack_5k

    # Create Stripe customer if doesn't exist
    if not current_user.stripe_customer_id:
        stripe_customer = stripe.Customer.create(
            email=current_user.email  # john@example.com
        )
        current_user.stripe_customer_id = stripe_customer.id
        db.commit()

    # Create Stripe checkout session
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=current_user.stripe_customer_id,
        line_items=[{
            "price": package["stripe_price_id"],  # price_2JpkMnByyy
            "quantity": 1
        }],
        success_url="https://app.agensium.com/billing/success",
        cancel_url="https://app.agensium.com/billing/cancel",
        metadata={
            "user_id": current_user.id,  # 1
            "package_id": request.package_id  # pack_5k
        }
    )

    return {
        "checkout_url": session.url,
        "session_id": session.id
    }
```

### API Response

```json
{
  "checkout_url": "https://checkout.stripe.com/pay/cs_test_xyz123",
  "session_id": "cs_test_xyz123"
}
```

### What User Sees

- Browser redirects to Stripe checkout page
- User enters card details
- User clicks "Pay $44.99"
- Stripe processes payment
- Browser redirects to success URL

### Database Update: `users` table

```
id  | email               | stripe_customer_id | created_at
----|---------------------|-------------------|------------------
1   | john@example.com    | cus_abc123def    | 2025-01-10 10:00:00
```

**Status:** Stripe customer created, but credits **NOT YET RECEIVED**

---

## 4. Credits Received in Wallet

### What Happens

After user completes Stripe payment, Stripe sends a webhook to our backend.

### Stripe Webhook Event

```
Event Type: checkout.session.completed
Event ID: evt_stripe_12345
Payload:
{
  "id": "evt_stripe_12345",
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "id": "cs_test_xyz123",
      "payment_status": "paid",
      "customer": "cus_abc123def",
      "metadata": {
        "user_id": "1",
        "package_id": "pack_5k"
      }
    }
  }
}
```

### Backend Webhook Handler

```python
# router.py - Webhook endpoint
@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # Verify signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return {"status": "invalid_signature"}

    # Check if event already processed (idempotency)
    existing_event = db.query(StripeWebhookEvent).filter(
        StripeWebhookEvent.stripe_event_id == event['id']
    ).first()

    if existing_event:
        return {"status": "already_processed"}  # Prevent double-crediting

    # Process new event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])  # 1
        package_id = session['metadata']['package_id']  # pack_5k

        # Get package details
        package = PACKAGES[package_id]
        credits_to_grant = package['credits']  # 5000

        # Get or create wallet for user
        wallet = db.query(CreditWallet).filter(
            CreditWallet.user_id == user_id
        ).first()

        if not wallet:
            wallet = CreditWallet(user_id=user_id, balance_credits=0)
            db.add(wallet)
            db.flush()  # Get wallet.id

        # ADD CREDITS
        wallet.balance_credits += credits_to_grant  # 0 + 5000 = 5000

        # Record transaction for audit trail
        transaction = CreditTransaction(
            user_id=user_id,
            delta_credits=credits_to_grant,  # 5000
            type="PURCHASE",
            reason="Stripe payment for pack_5k",
            stripe_checkout_session_id=session['id'],  # cs_test_xyz123
            stripe_event_id=event['id']  # evt_stripe_12345
        )
        db.add(transaction)

        # Mark webhook as processed
        webhook_event = StripeWebhookEvent(
            stripe_event_id=event['id'],
            event_type=event['type'],
            processed_at=func.now()
        )
        db.add(webhook_event)

        db.commit()

    return {"status": "success"}
```

### Database Updates

#### Table: `credit_wallets` (NEW)

```
id  | user_id | balance_credits | created_at           | updated_at
----|---------|-----------------|----------------------|-----------------------
1   | 1       | 5000            | 2025-01-10 10:05:00 | 2025-01-10 10:05:00
```

#### Table: `credit_transactions` (NEW)

```
id  | user_id | delta_credits | type     | reason                    | stripe_event_id
----|---------|---------------|----------|---------------------------|---------------
1   | 1       | 5000          | PURCHASE | Stripe payment for pack_5k| evt_stripe_12345
```

#### Table: `stripe_webhook_events` (NEW)

```
id  | stripe_event_id  | event_type                  | processed_at
----|------------------|-----------------------------|------------------
1   | evt_stripe_12345 | checkout.session.completed  | 2025-01-10 10:05:01
```

**Status:** ✅ John now has **5,000 credits in his wallet**

---

## 5. Executing Agents (Upfront Billing)

### What Happens

John is ready to clean his data. He uploads a CSV file and clicks "Clean My Data".

### API Request

```
POST /analyze
Authorization: Bearer <jwt_token_for_john>
Content-Type: application/json

{
  "tool_id": "clean-my-data",
  "file_path": "/uploads/john_data.csv",
  "agents_to_run": [
    "semantic-mapper",
    "null-handler",
    "contract-enforcer"
  ]
}
```

### Agent Cost Lookup

Backend checks the `agent_costs` table to see how much each agent costs:

```
agent_id               | cost (credits)
-----------------------|---------
semantic-mapper        | 50
null-handler           | 30
contract-enforcer      | 75
duplicate-resolver     | 100
golden-record-builder  | 150
... (other agents)
```

### Upfront Billing Check (Before ANY Agent Executes)

The transformer validates and consumes ALL credits **BEFORE** any agent executes. This is an all-or-nothing approach:

````python
# clean_my_data_transformer.py
from billing import BillingContext, InsufficientCreditsError

async def run_clean_my_data_analysis(...):
    current_user = get_current_user()
    tool_id = "clean-my-data"
    agents_to_run = ["semantic-mapper", "null-handler", "contract-enforcer"]

    # ========== UPFRONT BILLING (BEFORE ANY AGENT) ==========
    with BillingContext(current_user) as billing:
        try:
            # Calculate total: 50 + 30 + 75 = 155 credits
            # Check if user can afford ALL agents
            # If YES: Consume ALL credits upfront
            billing.validate_and_consume_all(
                agents=agents_to_run,
                tool_id=tool_id,
                task_id=task_id
            )
        except InsufficientCreditsError as e:
            # ❌ Not enough credits - NO agents run
            return billing.get_billing_error_response(
                error=e,
                task_id=task_id,
                tool_id=tool_id,
                start_time=start_time
            )
    # ========== END UPFRONT BILLING ==========

    # ✅ All credits consumed - now execute agents
    for agent_id in agents_to_run:
        # No billing check here - already paid upfront
        result = _execute_agent(agent_id, agent_input)
        print(f"Agent {agent_id} completed successfully")

---

## 6. Credit Deduction (Upfront - All at Once)

### Zoom In: `validate_and_consume_all()` Function

This is the **critical billing function** that guarantees:
- No partial execution (all-or-nothing)
- No negative balances
- Predictable behavior for users

```python
# billing/billing_context.py

class BillingContext:
    def validate_and_consume_all(
        self,
        agents: List[str],
        tool_id: str,
        task_id: str = None
    ):
        """
        Check affordability for ALL agents, then consume ALL credits upfront.
        If user can't afford ALL agents, raises InsufficientCreditsError.
        """

        # STEP 1: Check if user can afford ALL agents
        affordability = self.wallet_service.can_afford_agents(
            self.user.id,
            agents
        )

        if not affordability["can_afford"]:
            raise InsufficientCreditsError(
                available=affordability["available"],
                required=affordability["total_cost"],
                shortfall=affordability["shortfall"],
                breakdown=affordability["breakdown"]
            )

        # STEP 2: Consume credits for ALL agents (in single loop)
        for agent_id in agents:
            cost = affordability["breakdown"][agent_id]
            self.wallet_service.consume_for_agent(
                user_id=self.user.id,
                agent_id=agent_id,
                cost=cost,
                tool_id=tool_id,
                task_id=task_id
            )
````

### Step-by-Step Upfront Debit Example

**Initial State:** John's wallet has **5,000 credits**

**Agents to run:** semantic-mapper (50) + null-handler (30) + contract-enforcer (75) = **155 total**

#### Step 1: Affordability Check

```
can_afford_agents(["semantic-mapper", "null-handler", "contract-enforcer"])

Result:
{
    "can_afford": true,
    "available": 5000,
    "total_cost": 155,
    "shortfall": 0,
    "breakdown": {
        "semantic-mapper": 50,
        "null-handler": 30,
        "contract-enforcer": 75
    }
}
```

#### Step 2: Consume All Credits (Single Transaction Loop)

```
UPFRONT CONSUMPTION:
1. Lock wallet row
2. Check: 5000 >= 155? ✅ YES
3. Debit semantic-mapper: 5000 - 50 = 4950
   Record: CreditTransaction(delta=-50, agent_id="semantic-mapper")
4. Debit null-handler: 4950 - 30 = 4920
   Record: CreditTransaction(delta=-30, agent_id="null-handler")
5. Debit contract-enforcer: 4920 - 75 = 4845
   Record: CreditTransaction(delta=-75, agent_id="contract-enforcer")
6. Commit all

AFTER:
wallet.balance_credits = 4845
```

#### Step 3: Execute Agents (No Billing Checks)

```
# All credits already consumed - just execute
for agent_id in agents:
    result = _execute_agent(agent_id)  # No billing check here
```

**Final Result:** All 3 agents executed successfully. John now has **4,845 credits remaining**.

**Key Difference from Per-Agent Billing:** If John only had 100 credits (not enough for all 3 agents), NO agents would run at all. He would get an error immediately showing he needs 155 credits but only has 100.

---

## 7. Viewing Wallet & Transaction History

### What Happens

John visits the billing page to see his balance and transaction history.

### API Request

```
GET /billing/wallet
Authorization: Bearer <jwt_token_for_john>
```

### Backend Process

```python
# router.py - Wallet endpoint
@router.get("/billing/wallet")
async def get_wallet(current_user: User = Depends(get_current_user)):
    wallet = db.query(CreditWallet).filter(
        CreditWallet.user_id == current_user.id
    ).first()

    transactions = db.query(CreditTransaction).filter(
        CreditTransaction.user_id == current_user.id
    ).order_by(CreditTransaction.created_at.desc()).limit(20).all()

    return {
        "balance_credits": wallet.balance_credits,
        "status": "active",
        "recent_transactions": [
            {
                "id": t.id,
                "delta_credits": t.delta_credits,
                "type": t.type,
                "agent_id": t.agent_id,
                "tool_id": t.tool_id,
                "reason": t.reason,
                "created_at": t.created_at
            }
            for t in transactions
        ]
    }
```

### API Response

```json
{
  "balance_credits": 4845,
  "status": "active",
  "recent_transactions": [
    {
      "id": 4,
      "delta_credits": -75,
      "type": "CONSUME",
      "agent_id": "contract-enforcer",
      "tool_id": "clean-my-data",
      "reason": "Agent execution: contract-enforcer",
      "created_at": "2025-01-10T10:15:30Z"
    },
    {
      "id": 3,
      "delta_credits": -30,
      "type": "CONSUME",
      "agent_id": "null-handler",
      "tool_id": "clean-my-data",
      "reason": "Agent execution: null-handler",
      "created_at": "2025-01-10T10:15:15Z"
    },
    {
      "id": 2,
      "delta_credits": -50,
      "type": "CONSUME",
      "agent_id": "semantic-mapper",
      "tool_id": "clean-my-data",
      "reason": "Agent execution: semantic-mapper",
      "created_at": "2025-01-10T10:15:05Z"
    },
    {
      "id": 1,
      "delta_credits": 5000,
      "type": "PURCHASE",
      "agent_id": null,
      "tool_id": null,
      "reason": "Stripe payment for pack_5k",
      "created_at": "2025-01-10T10:05:00Z"
    }
  ]
}
```

### What John Sees on Frontend

```
┌─────────────────────────────────────┐
│  Your Credit Wallet                 │
├─────────────────────────────────────┤
│  Current Balance: 4,845 credits      │
├─────────────────────────────────────┤
│  Recent Transactions:                │
│                                     │
│  1. [TODAY 10:15] -75 credits       │
│     Used by: contract-enforcer      │
│     Tool: clean-my-data             │
│                                     │
│  2. [TODAY 10:15] -30 credits       │
│     Used by: null-handler           │
│     Tool: clean-my-data             │
│                                     │
│  3. [TODAY 10:15] -50 credits       │
│     Used by: semantic-mapper        │
│     Tool: clean-my-data             │
│                                     │
│  4. [TODAY 10:05] +5,000 credits    │
│     Purchase: 5,000 credit pack     │
│                                     │
└─────────────────────────────────────┘
```

---

## 8. Running Out of Credits (Upfront Check)

### What Happens

John wants to run more agents, but has only 4,845 credits. He wants to run:

- `golden-record-builder` (costs 150 credits)
- `duplicate-resolver` (costs 100 credits)

**Total needed:** 250 credits  
**Available:** 4,845 credits  
✅ **Can execute (all agents)**

But let's imagine after running more agents, John only has **40 credits left**.

Now he tries to run `golden-record-builder` AND `duplicate-resolver`:

### API Request

```
POST /analyze
Authorization: Bearer <jwt_token_for_john>
Content-Type: application/json

{
  "tool_id": "master-my-data",
  "file_path": "/uploads/john_data.csv",
  "agents_to_run": ["golden-record-builder", "duplicate-resolver"]
}
```

### Backend Process (Upfront Check)

```python
# BEFORE any agent runs - upfront billing check
from billing import BillingContext, InsufficientCreditsError

with BillingContext(current_user) as billing:
    try:
        # Check ALL agents upfront: 150 + 100 = 250 credits needed
        # User only has 40 credits
        billing.validate_and_consume_all(
            agents=["golden-record-builder", "duplicate-resolver"],
            tool_id="master-my-data",
            task_id=task_id
        )
    except InsufficientCreditsError as e:
        # ❌ IMMEDIATE REJECTION - NO agents run
        return billing.get_billing_error_response(
            error=e,
            task_id=task_id,
            tool_id="master-my-data",
            start_time=start_time
        )

# This code NEVER executes if insufficient credits
for agent_id in agents:
    result = _execute_agent(agent_id)
```

### API Response (Error - V2.1 Format)

```json
{
  "status": "error",
  "error_code": "BILLING_INSUFFICIENT_CREDITS",
  "error_message": "Insufficient credits for agent execution. Required: 250, Available: 40",
  "context": {
    "available": 40,
    "required": 250,
    "shortfall": 210,
    "breakdown": {
      "golden-record-builder": 150,
      "duplicate-resolver": 100
    }
  },
  "execution_time_ms": 45
}
```

### HTTP Status

```
HTTP/1.1 402 Payment Required
Content-Type: application/json

{
  "status": "error",
  "error_code": "BILLING_INSUFFICIENT_CREDITS",
  "error_message": "Insufficient credits for agent execution. Required: 250, Available: 40",
  "context": {
    "available": 40,
    "required": 250,
    "shortfall": 210,
    "breakdown": {
      "golden-record-builder": 150,
      "duplicate-resolver": 100
    }
  }
}
```

### What John Sees

Frontend detects `402 Payment Required` and displays the full breakdown:

```
┌──────────────────────────────────────────┐
│  ❌ Insufficient Credits                 │
├──────────────────────────────────────────┤
│                                          │
│  You don't have enough credits           │
│  to run ALL selected agents.             │
│                                          │
│  Agents Selected:                        │
│  • golden-record-builder: 150 credits    │
│  • duplicate-resolver: 100 credits       │
│  ─────────────────────────────────       │
│  Total Required: 250 credits             │
│  You Have: 40 credits                    │
│  Shortfall: 210 credits                  │
│                                          │
│  [ Buy More Credits ] [ Select Fewer ]   │
│                                          │
└──────────────────────────────────────────┘
```

**Key Point:** With upfront billing, John sees the TOTAL cost for ALL agents before any run. He can either buy more credits or select fewer agents.

John clicks "Buy More Credits" and repeats the flow from **Section 3**.

---

## 9. Database State at Each Step

### Timeline View

Here's what the database looks like at each critical point:

### Step 0: Initial Signup

```
users:
┌─────┬─────────────────┬────────────────────┐
│ id  │ email           │ stripe_customer_id │
├─────┼─────────────────┼────────────────────┤
│ 1   │ john@example.com│ NULL               │
└─────┴─────────────────┴────────────────────┘

credit_wallets: [EMPTY]
credit_transactions: [EMPTY]
```

---

### Step 1: After Stripe Payment

```
users:
┌─────┬─────────────────┬────────────────────┐
│ id  │ email           │ stripe_customer_id │
├─────┼─────────────────┼────────────────────┤
│ 1   │ john@example.com│ cus_abc123def      │
└─────┴─────────────────┴────────────────────┘

credit_wallets:
┌────┬─────────┬──────────────────┐
│ id │ user_id │ balance_credits  │
├────┼─────────┼──────────────────┤
│ 1  │ 1       │ 5000             │
└────┴─────────┴──────────────────┘

credit_transactions:
┌────┬─────────┬────────────────┬──────────┬─────────────┐
│ id │ user_id │ delta_credits  │ type     │ agent_id    │
├────┼─────────┼────────────────┼──────────┼─────────────┤
│ 1  │ 1       │ 5000           │ PURCHASE │ NULL        │
└────┴─────────┴────────────────┴──────────┴─────────────┘
```

---

### Step 2: After Executing 3 Agents

```
credit_wallets:
┌────┬─────────┬──────────────────┐
│ id │ user_id │ balance_credits  │
├────┼─────────┼──────────────────┤
│ 1  │ 1       │ 4845             │ ← Changed: 5000 - 50 - 30 - 75
└────┴─────────┴──────────────────┘

credit_transactions:
┌────┬─────────┬────────────────┬─────────────┬──────────────────────┐
│ id │ user_id │ delta_credits  │ type        │ agent_id             │
├────┼─────────┼────────────────┼─────────────┼──────────────────────┤
│ 1  │ 1       │ 5000           │ PURCHASE    │ NULL                 │
│ 2  │ 1       │ -50            │ CONSUME     │ semantic-mapper      │
│ 3  │ 1       │ -30            │ CONSUME     │ null-handler         │
│ 4  │ 1       │ -75            │ CONSUME     │ contract-enforcer    │
└────┴─────────┴────────────────┴─────────────┴──────────────────────┘
```

---

### Step 3: After Attempting Agent with Insufficient Credits

```
credit_wallets:
┌────┬─────────┬──────────────────┐
│ id │ user_id │ balance_credits  │
├────┼─────────┼──────────────────┤
│ 1  │ 1       │ 40               │ ← Still 40 (agent was NOT executed)
└────┴─────────┴──────────────────┘

credit_transactions:
┌────┬─────────┬────────────────┬─────────────┬──────────────────────┐
│ id │ user_id │ delta_credits  │ type        │ agent_id             │
├────┼─────────┼────────────────┼─────────────┼──────────────────────┤
│ 1  │ 1       │ 5000           │ PURCHASE    │ NULL                 │
│ 2  │ 1       │ -50            │ CONSUME     │ semantic-mapper      │
│ 3  │ 1       │ -30            │ CONSUME     │ null-handler         │
│ 4  │ 1       │ -75            │ CONSUME     │ contract-enforcer    │
│ .. │ ...     │ ...            │ ...         │ ...                  │
│ N  │ 1       │ 40             │ CONSUME     │ <last agent that fit> │
└────┴─────────┴────────────────┴─────────────┴──────────────────────┘

❌ NO NEW TRANSACTION for golden-record-builder
   (it was rejected before execution, so NO debit occurred)
```

**Key Point:** The `golden-record-builder` agent **never appears** in the transaction log because it was rejected before the debit was attempted.

---

## Complete Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│ 1. USER SIGNS UP                                             │
├──────────────────────────────────────────────────────────────┤
│ POST /auth/signup                                            │
│ → Create User record (no wallet yet)                         │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. USER WANTS TO BUY CREDITS                                 │
├──────────────────────────────────────────────────────────────┤
│ GET /billing/packages                                        │
│ → Return list of credit packs (1K, 5K, 10K)                 │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. USER INITIATES STRIPE CHECKOUT                            │
├──────────────────────────────────────────────────────────────┤
│ POST /billing/checkout-session                               │
│ → Create Stripe checkout session                             │
│ → Return checkout URL                                        │
│ → User pays on Stripe                                        │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. STRIPE WEBHOOK RECEIVED                                   │
├──────────────────────────────────────────────────────────────┤
│ POST /billing/webhook (from Stripe)                          │
│ → Verify webhook signature                                   │
│ → Check if already processed (idempotency)                   │
│ → Grant credits to wallet                                    │
│ → Record PURCHASE transaction                                │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. USER EXECUTES AN AGENT (e.g., clean-my-data)              │
├──────────────────────────────────────────────────────────────┤
│ POST /analyze                                                │
│ → For each agent_id in agents_to_run:                        │
│                                                              │
│   a) Lookup cost in agent_costs table                        │
│   b) Debit wallet (atomic transaction with lock)             │
│      - Check balance >= cost                                 │
│      - If YES: debit, record CONSUME transaction, execute    │
│      - If NO: return 402 Payment Required, stop              │
│                                                              │
│   c) Execute agent                                           │
│   d) Repeat for next agent                                   │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. USER VIEWS WALLET & HISTORY                               │
├──────────────────────────────────────────────────────────────┤
│ GET /billing/wallet                                          │
│ → Return current balance + recent transactions               │
└──────────────────────────────────────────────────────────────┘
```

---

## Summary: Key Principles

| Principle                | How It Works                                                                     |
| ------------------------ | -------------------------------------------------------------------------------- |
| **Prepaid**              | Credits must be purchased before agents run                                      |
| **Upfront Billing**      | ALL credits are checked and consumed BEFORE any agent executes                   |
| **All-or-Nothing**       | Either ALL agents run or NONE run (no partial execution)                         |
| **Atomic Debits**        | Credits are deducted inside a database transaction with row-level locking        |
| **No Negative Balance**  | If balance < total cost, ALL agents are rejected with 402 status                 |
| **Full Cost Visibility** | Error response includes breakdown of cost per agent                              |
| **Audit Trail**          | Every credit change is logged in `credit_transactions` table                     |
| **Stripe Idempotency**   | Webhooks are checked against `stripe_webhook_events` to prevent double-crediting |

---

## Quick Reference: Key Numbers (Example)

```
Credit Packs Available:
├── pack_1k:  1,000 credits = $9.99
├── pack_5k:  5,000 credits = $44.99
└── pack_10k: 10,000 credits = $89.99

Agent Costs (from agent_costs table):
├── semantic-mapper:        50 credits
├── null-handler:           30 credits
├── contract-enforcer:      75 credits
├── duplicate-resolver:     100 credits
└── golden-record-builder:  150 credits

John's Journey (with Upfront Billing):
1. Buys pack_5k → Gets 5,000 credits
2. Selects 3 agents: semantic-mapper + null-handler + contract-enforcer
3. Upfront check: 50 + 30 + 75 = 155 total → Has 5,000 ✅
4. ALL credits consumed upfront → Balance: 4,845
5. Agents execute (billing already done)
6. Later: Tries 2 agents needing 250 credits but only has 40
7. IMMEDIATE rejection (before any agent runs) with full breakdown
8. Buys more credits to continue
```

**Key Difference:** With upfront billing, John knows the TOTAL cost before ANY agent runs. No partial results, no surprises mid-execution.

---

**This walkthrough shows the complete user journey from signup through agent execution with upfront billing!**
