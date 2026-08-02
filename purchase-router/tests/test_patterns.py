import datetime
from types import SimpleNamespace

from app.patterns import recurring_merchants


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
