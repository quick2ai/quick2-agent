"""Spend pattern recognition + annual savings analysis.

Looks at transaction history to find:
  - category spend profile (monthly averages, annualized)
  - recurring merchants (subscriptions and habitual spend)
  - "missed rewards": what each purchase earned vs. what the engine's best
    pick would have earned — annualized into a savings number
  - market recommendations driven by real category spend (see market.py)
"""

import datetime
from collections import defaultdict

from . import engine as eng
from . import market


def category_profile(transactions: list) -> dict:
    """Monthly average + annualized spend per category."""
    if not transactions:
        return {}
    by_cat = defaultdict(float)
    months = set()
    for t in transactions:
        by_cat[t.category] += t.amount
        months.add((t.date.year, t.date.month))
    n_months = max(1, len(months))
    return {
        cat: {
            "total": round(total, 2),
            "monthly_avg": round(total / n_months, 2),
            "annualized": round(total / n_months * 12, 2),
        }
        for cat, total in sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)
    }


def recurring_merchants(transactions: list, min_months: int = 2) -> list[dict]:
    """Merchants charged in >= min_months distinct months (likely recurring)."""
    by_merchant = defaultdict(list)
    for t in transactions:
        if t.merchant:
            by_merchant[t.merchant].append(t)
    out = []
    for merchant, txns in by_merchant.items():
        months = {(t.date.year, t.date.month) for t in txns}
        if len(months) >= min_months:
            avg = sum(t.amount for t in txns) / len(txns)
            out.append({
                "merchant": merchant,
                "category": txns[0].category,
                "months_seen": len(months),
                "charges": len(txns),
                "avg_amount": round(avg, 2),
                "annualized": round(avg * 12, 2) if len(months) >= 2 else round(sum(t.amount for t in txns), 2),
            })
    out.sort(key=lambda m: m["annualized"], reverse=True)
    return out


def missed_rewards(transactions: list, accounts: list) -> dict:
    """Re-run history through the router: what would optimal routing have earned?

    Uses today's account snapshots (balances/caps as they are now) — an
    approximation, but a good directional estimate of leakage.
    """
    snapshots = [eng.snapshot_from_orm(a) for a in accounts]
    total_actual, total_optimal = 0.0, 0.0
    worst = defaultdict(lambda: {"count": 0, "missed": 0.0})
    months = set()

    for t in transactions:
        months.add((t.date.year, t.date.month))
        purchase = eng.Purchase(amount=t.amount, category=t.category,
                                merchant=t.merchant, date=t.date)
        best_rewards = 0.0
        for snap in snapshots:
            if snap.kind != "credit" or not snap.active:
                continue
            value, _ = eng.rewards_for(snap, purchase)
            best_rewards = max(best_rewards, value)
        total_actual += t.reward_earned or 0.0
        total_optimal += best_rewards
        gap = best_rewards - (t.reward_earned or 0.0)
        if gap > 0.005:
            worst[t.category]["count"] += 1
            worst[t.category]["missed"] += gap

    n_months = max(1, len(months))
    missed = max(0.0, total_optimal - total_actual)
    leaks = [
        {"category": cat, "purchases": d["count"], "missed": round(d["missed"], 2)}
        for cat, d in sorted(worst.items(), key=lambda kv: kv[1]["missed"], reverse=True)
    ]
    return {
        "actual_rewards": round(total_actual, 2),
        "optimal_rewards": round(total_optimal, 2),
        "missed": round(missed, 2),
        "missed_annualized": round(missed / n_months * 12, 2),
        "leaks_by_category": leaks[:6],
        "months_analyzed": n_months,
    }


def build_insights(transactions: list, accounts: list) -> dict:
    """Full insight bundle for the dashboard/insights page."""
    profile = category_profile(transactions)
    recurring = recurring_merchants(transactions)
    missed = missed_rewards(transactions, accounts)

    # Market recommendations weighted by real spend
    card_recs = []
    for cat, stats in profile.items():
        card_recs.extend(market.recommend_for_category(accounts, cat, stats["annualized"]))
    card_recs.sort(key=lambda r: r["est_annual_gain"], reverse=True)
    # one recommendation per card — keep its strongest category
    seen_cards: set = set()
    card_recs = [r for r in card_recs
                 if not (r["card"] in seen_cards or seen_cards.add(r["card"]))]
    savings_recs = market.recommend_savings_upgrade(accounts)

    total_opportunity = (missed["missed_annualized"]
                         + sum(r["est_annual_gain"] for r in card_recs[:3])
                         + sum(r["est_annual_gain"] for r in savings_recs))
    return {
        "category_profile": profile,
        "recurring_merchants": recurring[:10],
        "missed_rewards": missed,
        "card_recommendations": card_recs[:5],
        "savings_recommendations": savings_recs,
        "total_annual_opportunity": round(total_opportunity, 2),
        "generated_at": datetime.datetime.utcnow().isoformat(),
    }
