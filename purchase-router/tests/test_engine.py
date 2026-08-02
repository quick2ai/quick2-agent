import datetime

import pytest

from app.engine import (
    AccountSnapshot, Purchase, RewardRule,
    route, score_account, rewards_for, signup_bonus_value,
    days_until_due, next_occurrence, period_key,
)

TODAY = datetime.date(2026, 8, 2)


def make_card(**kw) -> AccountSnapshot:
    defaults = dict(
        id=1, name="Test Card", kind="credit", credit_limit=10000,
        current_balance=500, apr=0.25, statement_close_day=15,
        payment_due_day=12, base_rate=0.01,
    )
    defaults.update(kw)
    return AccountSnapshot(**defaults)


def make_checking(**kw) -> AccountSnapshot:
    defaults = dict(
        id=2, name="Checking", kind="checking", current_balance=3000,
        apy=0.0001, deposit_day=1, deposit_day_2=15, safety_buffer=1000,
    )
    defaults.update(kw)
    return AccountSnapshot(**defaults)


def hysa() -> AccountSnapshot:
    return AccountSnapshot(id=3, name="HYSA", kind="savings",
                           current_balance=20000, apy=0.04, can_pay=False)


# ── date helpers ─────────────────────────────────────────────────────────────

def test_next_occurrence_same_month():
    assert next_occurrence(datetime.date(2026, 8, 2), 15) == datetime.date(2026, 8, 15)


def test_next_occurrence_rolls_over():
    assert next_occurrence(datetime.date(2026, 8, 20), 15) == datetime.date(2026, 9, 15)


def test_next_occurrence_clamps_short_month():
    assert next_occurrence(datetime.date(2026, 2, 1), 31) == datetime.date(2026, 2, 28)


def test_days_until_due_spans_close_then_due():
    # purchase Aug 2, closes Aug 15, due Sep 12
    assert days_until_due(datetime.date(2026, 8, 2), 15, 12) == 41


def test_period_key():
    d = datetime.date(2026, 8, 2)
    assert period_key(d, "month") == "2026-08"
    assert period_key(d, "quarter") == "2026-Q3"
    assert period_key(d, "year") == "2026"


# ── rewards ──────────────────────────────────────────────────────────────────

def test_category_rule_beats_base_rate():
    card = make_card(reward_rules=[RewardRule("dining", 0.04)])
    value, note = rewards_for(card, Purchase(100, "dining", date=TODAY))
    assert value == pytest.approx(4.0)
    assert "dining" in note


def test_base_rate_used_for_unmatched_category():
    card = make_card(base_rate=0.02, reward_rules=[RewardRule("dining", 0.04)])
    value, _ = rewards_for(card, Purchase(100, "gas", date=TODAY))
    assert value == pytest.approx(2.0)


def test_reward_cap_exhausted_falls_back_to_base():
    card = make_card(
        reward_rules=[RewardRule("gas", 0.05, cap=1500, cap_period="quarter")],
        category_spend={("gas", "2026-Q3"): 1500.0},
    )
    value, _ = rewards_for(card, Purchase(100, "gas", date=TODAY))
    assert value == pytest.approx(1.0)  # base 1%


def test_reward_cap_blends_partial():
    card = make_card(
        reward_rules=[RewardRule("gas", 0.05, cap=1500, cap_period="quarter")],
        category_spend={("gas", "2026-Q3"): 1450.0},
    )
    # $50 at 5% + $50 at 1% = $3.00
    value, _ = rewards_for(card, Purchase(100, "gas", date=TODAY))
    assert value == pytest.approx(3.0)


# ── sign-up bonus ────────────────────────────────────────────────────────────

def test_bonus_amortized_per_dollar():
    card = make_card(bonus_value=900, bonus_spend_required=6000,
                     bonus_spend_progress=1000,
                     bonus_deadline=TODAY + datetime.timedelta(days=30))
    # $900 / $6000 = 15 cents per dollar
    assert signup_bonus_value(card, Purchase(100, date=TODAY)) == pytest.approx(15.0)


def test_bonus_expired_is_worthless():
    card = make_card(bonus_value=900, bonus_spend_required=6000,
                     bonus_deadline=TODAY - datetime.timedelta(days=1))
    assert signup_bonus_value(card, Purchase(100, date=TODAY)) == 0.0


def test_bonus_completed_is_worthless():
    card = make_card(bonus_value=900, bonus_spend_required=6000,
                     bonus_spend_progress=6000)
    assert signup_bonus_value(card, Purchase(100, date=TODAY)) == 0.0


# ── scoring ──────────────────────────────────────────────────────────────────

def test_revolving_card_penalized_for_interest():
    clean = make_card(id=1, name="Clean")
    revolving = make_card(id=2, name="Revolving", carries_balance=True, apr=0.30)
    p = Purchase(200, "other", date=TODAY)
    s_clean = score_account(clean, p, cash_apy=0.04)
    s_rev = score_account(revolving, p, cash_apy=0.04)
    assert s_rev.interest_cost > 0
    assert s_clean.net_benefit > s_rev.net_benefit


def test_utilization_threshold_penalty():
    # 28% -> crossing 30% with this purchase
    card = make_card(current_balance=2800, credit_limit=10000,
                     statement_close_day=(TODAY + datetime.timedelta(days=5)).day)
    s = score_account(card, Purchase(400, date=TODAY), cash_apy=0.0)
    assert s.utilization_penalty > 0
    assert any("30%" in r for r in s.reasons)


def test_post_close_purchase_discounts_utilization_penalty():
    close_soon = make_card(id=1, current_balance=2800, credit_limit=10000,
                           statement_close_day=(TODAY + datetime.timedelta(days=3)).day)
    just_closed = make_card(id=2, current_balance=2800, credit_limit=10000,
                            statement_close_day=(TODAY - datetime.timedelta(days=2)).day)
    p = Purchase(400, date=TODAY)
    s_soon = score_account(close_soon, p, cash_apy=0.0)
    s_closed = score_account(just_closed, p, cash_apy=0.0)
    assert s_closed.utilization_penalty < s_soon.utilization_penalty


def test_insufficient_credit_is_ineligible():
    card = make_card(current_balance=9900, credit_limit=10000)
    s = score_account(card, Purchase(500, date=TODAY), cash_apy=0.0)
    assert not s.eligible


def test_checking_buffer_breach_penalized():
    acct = make_checking(current_balance=1200, safety_buffer=1000)
    s = score_account(acct, Purchase(400, date=TODAY), cash_apy=0.0)
    assert s.buffer_penalty > 0


def test_checking_insufficient_balance_ineligible():
    acct = make_checking(current_balance=100)
    s = score_account(acct, Purchase(400, date=TODAY), cash_apy=0.0)
    assert not s.eligible


def test_float_value_earned_with_grace_period():
    card = make_card()
    s = score_account(card, Purchase(1000, date=TODAY), cash_apy=0.04)
    assert s.float_value > 0


# ── end-to-end routing ───────────────────────────────────────────────────────

def test_route_picks_best_category_card():
    dining_card = make_card(id=1, name="Dining 4%",
                            reward_rules=[RewardRule("dining", 0.04)])
    flat_card = make_card(id=2, name="Flat 2%", base_rate=0.02)
    checking = make_checking()
    result = route(Purchase(100, "dining", date=TODAY),
                   [dining_card, flat_card, checking, hysa()])
    assert result["best"]["name"] == "Dining 4%"
    assert result["best"]["net_benefit"] > 0
    names = [r["name"] for r in result["ranking"]]
    assert names.index("Dining 4%") < names.index("Flat 2%")


def test_route_avoids_revolving_card_despite_rewards():
    revolving = make_card(id=1, name="Revolving 3%", carries_balance=True,
                          apr=0.29, reward_rules=[RewardRule("dining", 0.03)])
    flat = make_card(id=2, name="Flat 2%", base_rate=0.02)
    result = route(Purchase(100, "dining", date=TODAY), [revolving, flat, hysa()])
    assert result["best"]["name"] == "Flat 2%"


def test_route_bonus_chase_dominates():
    bonus_card = make_card(id=1, name="Bonus Card", base_rate=0.01,
                           bonus_value=900, bonus_spend_required=6000,
                           bonus_spend_progress=100,
                           bonus_deadline=TODAY + datetime.timedelta(days=60))
    flat = make_card(id=2, name="Flat 2%", base_rate=0.02)
    result = route(Purchase(100, "other", date=TODAY), [bonus_card, flat, hysa()])
    assert result["best"]["name"] == "Bonus Card"


def test_route_no_eligible_accounts():
    tiny = make_card(current_balance=9990, credit_limit=10000)
    result = route(Purchase(5000, date=TODAY), [tiny])
    assert result["best"] is None
    assert len(result["ineligible"]) == 1


def test_savings_cannot_pay():
    result = route(Purchase(50, date=TODAY), [hysa(), make_checking()])
    assert result["best"]["name"] == "Checking"
    assert any(s["name"] == "HYSA" for s in result["ineligible"])
