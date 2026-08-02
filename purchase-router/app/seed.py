"""Demo wallet: 13 realistic accounts + ~4 months of transaction history.

Replace with real connections (Plaid/Teller/issuer APIs) in production —
see connections.py for the integration seam.
"""

import datetime
import random

from sqlalchemy import select, func

from .models import Account, Transaction, async_session

TODAY = datetime.date.today


def _demo_accounts() -> list[Account]:
    today = TODAY()
    return [
        # ── Credit cards ──
        Account(
            name="Chase Sapphire Preferred", issuer="Chase", kind="credit",
            network="visa", last4="4421", current_balance=842.17,
            credit_limit=15000, apr=0.2249, statement_close_day=17, payment_due_day=14,
            base_rate=0.01, point_value=0.0125, reward_unit="points",
            reward_rules=[
                {"category": "travel", "rate": 0.025, "note": "2x points"},
                {"category": "dining", "rate": 0.0375, "note": "3x points"},
                {"category": "streaming", "rate": 0.0375, "note": "3x points"},
            ],
            annual_fee=95,
        ),
        Account(
            name="Chase Freedom Flex", issuer="Chase", kind="credit",
            network="mastercard", last4="7710", current_balance=310.55,
            credit_limit=8000, apr=0.2699, statement_close_day=3, payment_due_day=28,
            base_rate=0.01,
            reward_rules=[
                {"category": "gas", "rate": 0.05, "cap": 1500.0, "cap_period": "quarter",
                 "note": "Q3 rotating category"},
                {"category": "drugstores", "rate": 0.03},
                {"category": "dining", "rate": 0.03},
            ],
        ),
        Account(
            name="Amex Gold", issuer="American Express", kind="credit",
            network="amex", last4="1005", current_balance=1210.90,
            credit_limit=20000, apr=0.2399, statement_close_day=25, payment_due_day=20,
            base_rate=0.01, point_value=0.014, reward_unit="points",
            reward_rules=[
                {"category": "dining", "rate": 0.056, "note": "4x MR points"},
                {"category": "groceries", "rate": 0.056, "cap": 25000.0, "cap_period": "year",
                 "note": "4x at U.S. supermarkets"},
            ],
            bonus_value=900.0, bonus_spend_required=6000.0, bonus_spend_progress=3850.0,
            bonus_deadline=today + datetime.timedelta(days=52),
            annual_fee=325,
        ),
        Account(
            name="Citi Double Cash", issuer="Citi", kind="credit",
            network="mastercard", last4="3388", current_balance=95.20,
            credit_limit=12000, apr=0.2874, statement_close_day=9, payment_due_day=6,
            base_rate=0.02,
        ),
        Account(
            name="Discover it", issuer="Discover", kind="credit",
            network="discover", last4="6002", current_balance=45.00,
            credit_limit=6500, apr=0.2649, statement_close_day=21, payment_due_day=18,
            base_rate=0.01,
            reward_rules=[
                {"category": "groceries", "rate": 0.05, "cap": 1500.0, "cap_period": "quarter",
                 "note": "Q3 rotating category"},
            ],
        ),
        Account(
            name="Capital One Venture", issuer="Capital One", kind="credit",
            network="visa", last4="9954", current_balance=4680.00,
            credit_limit=10000, apr=0.2949, statement_close_day=12, payment_due_day=9,
            carries_balance=True,  # revolving — grace period lost
            base_rate=0.02, reward_unit="miles",
            reward_rules=[{"category": "travel", "rate": 0.05, "note": "5x via portal"}],
            annual_fee=95,
            notes="Carrying a balance — router avoids this card until paid off.",
        ),
        Account(
            name="Amazon Prime Visa", issuer="Chase", kind="credit",
            network="visa", last4="0071", current_balance=188.34,
            credit_limit=9000, apr=0.2699, statement_close_day=27, payment_due_day=24,
            base_rate=0.01,
            reward_rules=[
                {"category": "online_shopping", "rate": 0.05, "note": "5% at Amazon/Whole Foods"},
                {"category": "gas", "rate": 0.02},
                {"category": "dining", "rate": 0.02},
            ],
        ),
        Account(
            name="Wells Fargo Active Cash", issuer="Wells Fargo", kind="credit",
            network="visa", last4="5512", current_balance=1420.00,
            credit_limit=5000, apr=0.2924, statement_close_day=6, payment_due_day=3,
            base_rate=0.02,
            notes="High utilization (28%) — router steers spend away near statement close.",
        ),
        Account(
            name="US Bank Cash+", issuer="U.S. Bank", kind="credit",
            network="visa", last4="8823", current_balance=62.75,
            credit_limit=7500, apr=0.2799, statement_close_day=14, payment_due_day=11,
            base_rate=0.01,
            reward_rules=[
                {"category": "utilities", "rate": 0.05, "cap": 2000.0, "cap_period": "quarter",
                 "note": "chosen 5% category"},
                {"category": "streaming", "rate": 0.05, "cap": 2000.0, "cap_period": "quarter",
                 "note": "chosen 5% category"},
            ],
        ),
        # ── Bank accounts ──
        Account(
            name="Chase Total Checking", issuer="Chase", kind="checking",
            network="visa", last4="2201", current_balance=3240.88,
            apy=0.0001, deposit_day=1, deposit_day_2=15, deposit_amount=4200.0,
            safety_buffer=1500.0,
            notes="Primary paycheck account — debit card attached.",
        ),
        Account(
            name="Ally Spending", issuer="Ally", kind="checking",
            network="mastercard", last4="4477", current_balance=980.40,
            apy=0.0025, deposit_day=15, deposit_amount=600.0, safety_buffer=400.0,
        ),
        Account(
            name="Ally High-Yield Savings", issuer="Ally", kind="savings",
            last4="9931", current_balance=18500.00, apy=0.0410,
            can_pay=False, safety_buffer=10000.0,
            notes="Emergency fund + float parking. Sets the opportunity value of float.",
        ),
        Account(
            name="Fidelity Brokerage (cash)", issuer="Fidelity", kind="investment",
            last4="7301", current_balance=6200.00, apy=0.0395,
            can_pay=False,
            notes="SPAXX core position.",
        ),
    ]


_MERCHANTS = {
    "dining": ["Chipotle", "Olive Garden", "Local Thai", "Starbucks", "DoorDash"],
    "groceries": ["Kroger", "Whole Foods", "Trader Joe's", "Costco"],
    "gas": ["Shell", "QuikTrip", "Costco Gas"],
    "travel": ["Delta", "Marriott", "Uber"],
    "online_shopping": ["Amazon", "Best Buy", "Target.com"],
    "streaming": ["Netflix", "Spotify", "Hulu", "YouTube Premium"],
    "drugstores": ["CVS", "Walgreens"],
    "entertainment": ["AMC Theatres", "Topgolf"],
    "transit": ["Metro", "Lyft"],
    "utilities": ["Georgia Power", "Comcast", "T-Mobile"],
    "home_improvement": ["Home Depot", "Lowe's"],
    "other": ["USPS", "Vet Clinic", "Barber"],
}

_AMOUNTS = {
    "dining": (12, 85), "groceries": (40, 220), "gas": (30, 65),
    "travel": (90, 600), "online_shopping": (15, 180), "streaming": (9, 23),
    "drugstores": (8, 45), "entertainment": (25, 120), "transit": (10, 40),
    "utilities": (60, 210), "home_improvement": (20, 350), "other": (10, 90),
}

# Weighted mix of monthly purchases per category
_MONTHLY_MIX = {
    "dining": 9, "groceries": 6, "gas": 4, "online_shopping": 5,
    "streaming": 4, "drugstores": 2, "travel": 1, "entertainment": 2,
    "transit": 3, "utilities": 3, "home_improvement": 1, "other": 2,
}


def _demo_transactions(accounts: list[Account]) -> list[Transaction]:
    """~4 months of history, deliberately routed sub-optimally at times so
    the pattern-recognition insights have real leakage to find."""
    rng = random.Random(42)
    today = TODAY()
    cards = [a for a in accounts if a.kind == "credit"]
    checking = next(a for a in accounts if a.name == "Chase Total Checking")

    def best_card_for(category: str) -> Account:
        best, best_rate = cards[0], -1.0
        for c in cards:
            rate = c.base_rate or 0.0
            for r in (c.reward_rules or []):
                if r.get("category") == category:
                    rate = max(rate, r["rate"])
            if rate > best_rate:
                best, best_rate = c, rate
        return best

    txns = []
    for months_back in range(4, 0, -1):
        month_start = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        for _ in range(months_back - 1):
            month_start = (month_start - datetime.timedelta(days=1)).replace(day=1)
        for category, count in _MONTHLY_MIX.items():
            for _ in range(count):
                day = rng.randint(1, 28)
                date = month_start.replace(day=day)
                if date >= today:
                    continue
                lo, hi = _AMOUNTS[category]
                amount = round(rng.uniform(lo, hi), 2)
                merchant = rng.choice(_MERCHANTS[category])
                # 55% optimal, 35% habit card (Sapphire), 10% debit — realistic leakage
                roll = rng.random()
                if roll < 0.55:
                    acct = best_card_for(category)
                elif roll < 0.90:
                    acct = cards[0]
                else:
                    acct = checking
                rate = acct.base_rate or 0.0
                for r in (acct.reward_rules or []):
                    if r.get("category") == category:
                        rate = max(rate, r["rate"])
                txns.append(Transaction(
                    account=acct, date=date, amount=amount, category=category,
                    merchant=merchant, reward_earned=round(amount * rate, 2),
                ))
    # Pin recurring subscriptions to exact merchants monthly
    for months_back in range(4, 0, -1):
        d = today - datetime.timedelta(days=30 * months_back - 3)
        for merchant, cat, amt in [("Netflix", "streaming", 15.49),
                                   ("Spotify", "streaming", 11.99),
                                   ("Comcast", "utilities", 89.99),
                                   ("T-Mobile", "utilities", 105.00)]:
            acct = cards[0]
            rate = acct.base_rate or 0.0
            for r in (acct.reward_rules or []):
                if r.get("category") == cat:
                    rate = max(rate, r["rate"])
            txns.append(Transaction(
                account=acct, date=d, amount=amt, category=cat,
                merchant=merchant, reward_earned=round(amt * rate, 2),
            ))
    return txns


async def seed_if_empty() -> bool:
    """Populate the demo wallet on first boot. Returns True if seeded."""
    async with async_session() as session:
        count = (await session.execute(select(func.count(Account.id)))).scalar()
        if count:
            return False
        accounts = _demo_accounts()
        session.add_all(accounts)
        await session.flush()
        session.add_all(_demo_transactions(accounts))
        await session.commit()
        return True
