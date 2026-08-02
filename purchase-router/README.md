# Quick2 Purchase Router

A smart purchase-routing agent: connect every card and bank account, and on each
"tap to pay" the agent scores all of them in real time and routes the charge to
the account that nets you the most money — maximizing rewards and interest
earned while minimizing interest paid and credit-report impact.

Built with FastAPI + HTMX + Tailwind + SQLite, following the same conventions
as the other Quick2Labs apps in this repo.

## Quick start

```bash
cd purchase-router
chmod +x run.sh
./run.sh
# open http://localhost:5000
```

First boot seeds a realistic demo wallet: 9 credit cards, 2 checking accounts,
a high-yield savings account, and a brokerage — plus 4 months of transaction
history so the insights page has real patterns to analyze.

Run the tests:

```bash
.venv/bin/pytest tests/ -q
```

## What it does

### 1. Tap-to-pay routing (`/tap`, `POST /api/route`)

Every purchase request is scored against every connected account **in dollars
of net benefit**:

| Factor | Direction | How it's modeled |
|---|---|---|
| Rewards & cash back | + | Best applicable earn rate for the purchase category, including rotating quarterly categories, spend caps (with blended partial-cap math), and point valuations |
| Sign-up bonus progress | + | Unfinished welcome bonuses are amortized per dollar of required spend — a $900 bonus on $6k spend adds 15¢/$ until earned |
| Float value | + | Cards with an intact grace period let your cash keep earning HYSA APY until the payment due date (purchase → statement close → due date) |
| Interest cost | − | Cards carrying a revolving balance accrue APR on new purchases immediately (grace period lost) — the router steers away from them |
| Credit-report impact | − | Projected utilization at the next statement close vs. the 10% / 30% / 50% / 90% reporting thresholds, per card and aggregate. Purchases that post right after a close are discounted — they won't report for a month |
| Cash-flow safety | − | Checking accounts are penalized for dipping below their safety buffer, scaled by days until the next paycheck deposit |

The decision comes back with the full ranking, a per-factor dollar breakdown,
and plain-English reasons — and is logged to an audit trail.

```bash
curl -X POST http://localhost:5000/api/route \
  -H "Content-Type: application/json" \
  -d '{"amount": 64.20, "category": "dining", "merchant": "Chipotle", "execute": false}'
```

Set `"execute": true` to settle the charge: balance and sign-up-bonus progress
update on the winning account and the transaction is recorded.

### 2. Dashboard (`/`)

All accounts at a glance: per-card utilization bars against the reporting
thresholds, aggregate utilization, cash position, and a unified calendar of
upcoming payment due dates, statement close dates (when balances report to the
bureaus), and paycheck deposit dates.

### 3. Insights & annual savings (`/insights`, `GET /api/insights`)

Pattern recognition over transaction history:

- **Rewards leakage** — replays every historical purchase against the
  wallet's reward structures (honoring category caps as they exhaust, and
  excluding revolving cards the router avoids) and quantifies what the best
  card choice would have earned vs. what you actually earned, annualized,
  broken down by category. Rewards-domain only: float and utilization
  effects depend on balances at purchase time, which history can't
  reconstruct.
- **Spending profile** — monthly/annualized spend per category.
- **Recurring charge detection** — subscriptions and habitual merchants.
- **Market recommendations** — compares your wallet's best earn rate per
  category against a market catalog of cards; recommends upgrades only when
  the incremental earnings clear the annual fee, sized by your real spend.
  Each recommendation carries a referral URL — this is the monetization
  surface (affiliate/referral revenue), alongside high-yield savings offers
  for idle cash.

## Architecture

```
app/
  engine.py    Pure routing engine — no I/O, microsecond scoring, fully unit-tested
  models.py    SQLAlchemy models: Account, Transaction, RoutingDecision (audit log)
  market.py    Market card catalog + referral-driven recommendations
  patterns.py  Spend-pattern recognition and annual-savings analysis
  seed.py      Demo wallet (13 accounts) + 4 months of history
  main.py      FastAPI app: routing API + HTMX UI
tests/
  test_engine.py
```

The engine is deliberately pure (accounts in → ranked decision out) so it can
sit on the hot path of a real payment authorization.

## Path to production

Real single-tap routing requires a **virtual card in front of your accounts**
(the Curve model): you add one card to Apple/Google Pay, issued via a BIN
sponsor / issuer-processor (Lithic, Marqeta, Stripe Issuing). The tap
authorizes against the virtual card, the processor's auth webhook calls
`POST /api/route` with the merchant category code and amount, and the charge
is funded from the winning account (JIT funding). The pieces to swap in:

1. **Account sync** — replace `seed.py` with Plaid/Teller connections for
   balances, statement dates, and transactions (`liabilities` endpoints expose
   APRs, due dates, and last statement balances).
2. **Card issuing** — Lithic/Marqeta virtual card with an auth-stream webhook;
   the router already answers in well under the ~2s auth window.
3. **MCC mapping** — map ISO merchant category codes to the engine's
   categories (the `category` field on `/api/route`).
4. **Rewards calendars** — issuer rotating-category schedules are published
   quarterly; sync them into `reward_rules`.

Everything above the payment rails — the scoring engine, audit trail, insights,
and monetization — is what this app implements and is rail-agnostic.
