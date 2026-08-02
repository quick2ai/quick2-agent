import datetime
from types import SimpleNamespace

from app.patterns import missed_rewards, recurring_merchants


def txn(merchant, amount, year, month, day=5, category="streaming"):
    return SimpleNamespace(merchant=merchant, amount=amount, category=category,
                           date=datetime.date(year, month, day), reward_earned=0.0)


def test_annualized_uses_total_per_month_not_per_charge():
    # Two $10 charges every month for 3 months = $20/month -> $240/yr
    txns = []
    for month in (5, 6, 7):
        txns.append(txn("Gym", 10.0, 2026, month, day=3))
        txns.append(txn("Gym", 10.0, 2026, month, day=20))
    result = recurring_merchants(txns)
    assert len(result) == 1
    gym = result[0]
    assert gym["charges"] == 6
    assert gym["months_seen"] == 3
    assert gym["avg_amount"] == 10.0
    assert gym["annualized"] == 240.0


def test_single_month_merchants_excluded():
    txns = [txn("One-off", 50.0, 2026, 7), txn("One-off", 50.0, 2026, 7, day=8)]
    assert recurring_merchants(txns) == []


def capped_card_account():
    """ORM-shaped account: 5% groceries capped at $100/quarter, 1% base."""
    return SimpleNamespace(
        id=1, name="Capped 5%", kind="credit", can_pay=True, active=True,
        current_balance=0.0, credit_limit=10000, apr=0.25,
        statement_close_day=15, payment_due_day=12, carries_balance=False,
        reports_to_bureaus=True, apy=0.0, deposit_day=None, deposit_day_2=None,
        safety_buffer=0.0, base_rate=0.01,
        reward_rules=[{"category": "groceries", "rate": 0.05,
                       "cap": 100.0, "cap_period": "quarter"}],
        bonus_value=0.0, bonus_spend_required=0.0, bonus_spend_progress=0.0,
        bonus_deadline=None,
    )


def test_missed_rewards_replay_respects_caps():
    # Two $100 grocery purchases in the same quarter on a card whose 5% rate
    # caps at $100/quarter: optimal = $5.00 (first) + $1.00 (base, second).
    txns = [
        txn("Kroger", 100.0, 2026, 7, day=3, category="groceries"),
        txn("Kroger", 100.0, 2026, 7, day=20, category="groceries"),
    ]
    result = missed_rewards(txns, [capped_card_account()])
    assert result["optimal_rewards"] == 6.0  # not 10.0 — cap exhausted mid-replay
