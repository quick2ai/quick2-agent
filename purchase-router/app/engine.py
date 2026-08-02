"""Smart purchase routing engine.

Given a purchase (amount, category, date) and a snapshot of every connected
account, score each eligible account in *dollars of net benefit* and rank them.

Factors modeled per account:
  + rewards value          earn rate for the category (rotating categories,
                           caps, point valuations)
  + sign-up bonus progress amortized value of an unfinished welcome bonus
  + float value            grace period = your cash keeps earning HYSA interest
                           until the payment due date
  - interest cost          revolving cards accrue interest immediately (no grace)
  - utilization penalty    projected balance at statement close vs. the 10% /
                           30% / 50% / 90% credit-report thresholds
  - cash buffer penalty    checking accounts must not dip below the safety
                           buffer before the next paycheck deposit

The engine is pure (no DB, no clock reads) so it can answer a tap-to-pay
request in microseconds and is fully unit-testable.
"""

import calendar
import datetime
from dataclasses import dataclass, field
from typing import Optional

# ── Tunable weights ──────────────────────────────────────────────────────────

# Dollar-equivalent penalties for the reported utilization band a purchase
# would push a card into at its next statement close. Crossing 30% is what
# most scoring models care about; 90%+ reads as maxed out.
UTILIZATION_PENALTIES = [
    (0.90, 60.0),
    (0.50, 25.0),
    (0.30, 12.0),
    (0.10, 2.0),
]
# Penalty applied when a purchase pushes AGGREGATE utilization across bands.
AGGREGATE_UTILIZATION_PENALTY = 20.0
AGGREGATE_UTILIZATION_THRESHOLD = 0.30

# A balance only reports to the bureaus if it's still there at statement
# close. The further away the close, the more room to pay the purchase down
# before it ever reports — the penalty scales smoothly from full (closes
# today) to this floor (statement just closed, a full cycle away).
POST_CLOSE_UTILIZATION_DISCOUNT = 0.25
STATEMENT_CYCLE_DAYS = 28.0

# Assumed number of days a revolving balance carries before payoff.
ASSUMED_CARRY_DAYS = 30

# Penalty for drawing a checking account below its safety buffer.
BUFFER_BREACH_PENALTY = 40.0

DAYS_IN_YEAR = 365.0


# ── Snapshot dataclasses (decoupled from the ORM) ────────────────────────────

@dataclass
class RewardRule:
    category: str
    rate: float  # $-value fraction earned per $ spent
    cap: Optional[float] = None  # spend cap for this rate
    cap_period: str = "quarter"  # month | quarter | year
    note: str = ""


@dataclass
class AccountSnapshot:
    id: int
    name: str
    kind: str  # credit | checking | savings | investment
    can_pay: bool = True
    active: bool = True
    current_balance: float = 0.0

    # credit
    credit_limit: Optional[float] = None
    apr: float = 0.0
    statement_close_day: Optional[int] = None
    payment_due_day: Optional[int] = None
    carries_balance: bool = False
    reports_to_bureaus: bool = True

    # bank
    apy: float = 0.0
    deposit_day: Optional[int] = None
    deposit_day_2: Optional[int] = None
    safety_buffer: float = 0.0

    # rewards
    base_rate: float = 0.0
    reward_rules: list = field(default_factory=list)  # list[RewardRule]

    # bonus
    bonus_value: float = 0.0
    bonus_spend_required: float = 0.0
    bonus_spend_progress: float = 0.0
    bonus_deadline: Optional[datetime.date] = None

    # {(category, period_key): spend_so_far} used for reward caps
    category_spend: dict = field(default_factory=dict)


@dataclass
class Purchase:
    amount: float
    category: str = "other"
    merchant: str = ""
    date: datetime.date = field(default_factory=datetime.date.today)


@dataclass
class ScoredAccount:
    account_id: int
    name: str
    kind: str
    eligible: bool
    net_benefit: float = 0.0
    rewards_value: float = 0.0
    bonus_value: float = 0.0
    float_value: float = 0.0
    interest_cost: float = 0.0
    utilization_penalty: float = 0.0
    buffer_penalty: float = 0.0
    effective_rate: float = 0.0  # net benefit / amount
    reasons: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "name": self.name,
            "kind": self.kind,
            "eligible": self.eligible,
            "net_benefit": round(self.net_benefit, 2),
            "effective_rate": round(self.effective_rate, 4),
            "breakdown": {
                "rewards_value": round(self.rewards_value, 2),
                "signup_bonus_value": round(self.bonus_value, 2),
                "float_value": round(self.float_value, 2),
                "interest_cost": round(-self.interest_cost, 2),
                "utilization_penalty": round(-self.utilization_penalty, 2),
                "cash_buffer_penalty": round(-self.buffer_penalty, 2),
            },
            "reasons": self.reasons,
        }


# ── Date helpers ─────────────────────────────────────────────────────────────

def _clamp_day(year: int, month: int, day: int) -> datetime.date:
    last = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, min(day, last))


def next_occurrence(from_date: datetime.date, day_of_month: int,
                    inclusive: bool = True) -> datetime.date:
    """Next date on day_of_month. Inclusive by default: a statement that
    closes (or payment due) TODAY is today's event, not next month's."""
    candidate = _clamp_day(from_date.year, from_date.month, day_of_month)
    if candidate > from_date or (inclusive and candidate == from_date):
        return candidate
    year, month = (from_date.year + 1, 1) if from_date.month == 12 else (from_date.year, from_date.month + 1)
    return _clamp_day(year, month, day_of_month)


def days_until_due(purchase_date: datetime.date, close_day: int, due_day: int) -> int:
    """Days of float: purchase -> statement close -> the due date after it.

    A purchase on the close day posts to today's statement; the due date is
    always strictly after the close.
    """
    close = next_occurrence(purchase_date, close_day)
    due = next_occurrence(close, due_day, inclusive=False)
    return (due - purchase_date).days


def period_key(date: datetime.date, period: str) -> str:
    if period == "month":
        return f"{date.year}-{date.month:02d}"
    if period == "year":
        return str(date.year)
    return f"{date.year}-Q{(date.month - 1) // 3 + 1}"


# ── Scoring components ───────────────────────────────────────────────────────

def rewards_for(account: AccountSnapshot, purchase: Purchase) -> tuple[float, str]:
    """Best applicable earn value in dollars, honoring category caps."""
    best_rate = account.base_rate
    note = f"base {account.base_rate:.1%}" if account.base_rate else ""
    for rule in account.reward_rules:
        if rule.category not in (purchase.category, "all"):
            continue
        rate = rule.rate
        if rule.cap is not None:
            pk = period_key(purchase.date, rule.cap_period)
            if rule.category == "all":
                # an "all" cap covers spend in every category this period
                spent = sum(v for (_, p), v in account.category_spend.items() if p == pk)
            else:
                spent = account.category_spend.get((rule.category, pk), 0.0)
            if spent >= rule.cap:
                continue  # cap exhausted — rule no longer applies
            if spent + purchase.amount > rule.cap:
                # blended: part of the purchase earns at the boosted rate
                boosted_portion = rule.cap - spent
                rate = (boosted_portion * rule.rate
                        + (purchase.amount - boosted_portion) * account.base_rate) / purchase.amount
        if rate > best_rate:
            best_rate = rate
            note = f"{rule.rate:.1%} on {rule.category}" + (f" ({rule.note})" if rule.note else "")
    return best_rate * purchase.amount, note


def signup_bonus_value(account: AccountSnapshot, purchase: Purchase) -> float:
    """Amortized value of progress toward an unfinished welcome bonus."""
    if account.bonus_value <= 0 or account.bonus_spend_required <= 0:
        return 0.0
    if account.bonus_spend_progress >= account.bonus_spend_required:
        return 0.0
    if account.bonus_deadline and purchase.date > account.bonus_deadline:
        return 0.0
    remaining = account.bonus_spend_required - account.bonus_spend_progress
    counted = min(purchase.amount, remaining)
    return counted * (account.bonus_value / account.bonus_spend_required)


def utilization_penalty_for(account: AccountSnapshot, purchase: Purchase,
                            aggregate_util_before: float,
                            aggregate_limit: float) -> tuple[float, list]:
    """Dollar-equivalent penalty for the utilization the purchase would report."""
    if account.kind != "credit" or not account.credit_limit or not account.reports_to_bureaus:
        return 0.0, []
    reasons = []
    limit = account.credit_limit
    util_before = account.current_balance / limit
    util_after = (account.current_balance + purchase.amount) / limit

    penalty = 0.0
    for threshold, cost in UTILIZATION_PENALTIES:
        if util_after > threshold >= util_before:
            penalty += cost
            reasons.append(
                f"pushes reported utilization past {threshold:.0%} "
                f"({util_before:.0%} → {util_after:.0%})"
            )

    if aggregate_limit > 0:
        agg_after = aggregate_util_before + purchase.amount / aggregate_limit
        if agg_after > AGGREGATE_UTILIZATION_THRESHOLD >= aggregate_util_before:
            penalty += AGGREGATE_UTILIZATION_PENALTY
            reasons.append("pushes overall utilization across all cards past 30%")

    # Scale by time to act: more days before the close = more room to pay
    # the purchase down before it reports. Continuous — no threshold cliff.
    if account.statement_close_day is not None and penalty > 0:
        close = next_occurrence(purchase.date, account.statement_close_day)
        days_to_close = (close - purchase.date).days
        urgency = max(0.0, 1.0 - days_to_close / STATEMENT_CYCLE_DAYS)
        penalty *= POST_CLOSE_UTILIZATION_DISCOUNT + (1.0 - POST_CLOSE_UTILIZATION_DISCOUNT) * urgency
        if days_to_close >= 21:
            reasons.append(
                f"{days_to_close} days until this card's statement closes — "
                f"time to pay it down before the balance reports"
            )
    return penalty, reasons


def score_account(account: AccountSnapshot, purchase: Purchase,
                  cash_apy: float,
                  aggregate_util_before: float = 0.0,
                  aggregate_limit: float = 0.0) -> ScoredAccount:
    s = ScoredAccount(account_id=account.id, name=account.name,
                      kind=account.kind, eligible=True)

    # ── Eligibility ──
    if not account.active or not account.can_pay:
        s.eligible = False
        s.reasons.append("account can't be used for payments")
        return s
    if account.kind == "credit":
        available = (account.credit_limit or 0) - account.current_balance
        if purchase.amount > available:
            s.eligible = False
            s.reasons.append(f"insufficient available credit (${available:,.0f})")
            return s
    elif account.kind in ("checking", "savings", "investment"):
        if purchase.amount > account.current_balance:
            s.eligible = False
            s.reasons.append(f"insufficient balance (${account.current_balance:,.0f})")
            return s

    # ── Rewards ──
    s.rewards_value, reward_note = rewards_for(account, purchase)
    if s.rewards_value > 0 and reward_note:
        s.reasons.append(f"earns {reward_note} → ${s.rewards_value:.2f}")

    # ── Sign-up bonus ──
    s.bonus_value = signup_bonus_value(account, purchase)
    if s.bonus_value > 0:
        remaining = account.bonus_spend_required - account.bonus_spend_progress
        s.reasons.append(
            f"counts toward ${account.bonus_value:,.0f} welcome bonus "
            f"(${remaining:,.0f} to go) → +${s.bonus_value:.2f}"
        )

    if account.kind == "credit":
        if account.carries_balance:
            # Grace period lost: new purchases accrue interest from day one.
            s.interest_cost = purchase.amount * account.apr * ASSUMED_CARRY_DAYS / DAYS_IN_YEAR
            s.reasons.append(
                f"carrying a balance — new purchases accrue {account.apr:.1%} APR "
                f"immediately → -${s.interest_cost:.2f}"
            )
        elif account.statement_close_day and account.payment_due_day:
            # Grace period intact: cash stays in the HYSA until the due date.
            float_days = days_until_due(purchase.date, account.statement_close_day,
                                        account.payment_due_day)
            s.float_value = purchase.amount * cash_apy * float_days / DAYS_IN_YEAR
            if s.float_value >= 0.01:
                s.reasons.append(
                    f"{float_days} days of float — cash earns {cash_apy:.2%} "
                    f"until due → +${s.float_value:.2f}"
                )

        s.utilization_penalty, util_reasons = utilization_penalty_for(
            account, purchase, aggregate_util_before, aggregate_limit)
        s.reasons.extend(util_reasons)

    elif account.kind in ("checking", "savings", "investment"):
        # Paying cash forfeits interest the money would have kept earning.
        lost = purchase.amount * account.apy * ASSUMED_CARRY_DAYS / DAYS_IN_YEAR
        if lost >= 0.01:
            s.interest_cost = lost
            s.reasons.append(f"cash leaves a {account.apy:.2%} APY account → -${lost:.2f}")

        # Don't dip below the safety buffer before the next paycheck lands.
        if account.kind == "checking" and account.safety_buffer > 0:
            after = account.current_balance - purchase.amount
            if after < account.safety_buffer:
                deposit_days = []
                for d in (account.deposit_day, account.deposit_day_2):
                    if d:
                        deposit_days.append((next_occurrence(purchase.date, d) - purchase.date).days)
                days_to_deposit = min(deposit_days) if deposit_days else 30
                s.buffer_penalty = BUFFER_BREACH_PENALTY * min(1.0, days_to_deposit / 15.0)
                s.reasons.append(
                    f"would dip below ${account.safety_buffer:,.0f} buffer with "
                    f"{days_to_deposit} days until next deposit"
                )

    s.net_benefit = (s.rewards_value + s.bonus_value + s.float_value
                     - s.interest_cost - s.utilization_penalty - s.buffer_penalty)
    s.effective_rate = s.net_benefit / purchase.amount if purchase.amount else 0.0
    return s


def route(purchase: Purchase, accounts: list[AccountSnapshot]) -> dict:
    """Rank all accounts for a purchase. Returns {best, ranking, summary}."""
    # Best APY across connected cash accounts = opportunity value of float.
    cash_apy = max((a.apy for a in accounts if a.kind in ("savings", "investment", "checking")),
                   default=0.0)

    credit_accounts = [a for a in accounts if a.kind == "credit" and a.credit_limit]
    aggregate_limit = sum(a.credit_limit for a in credit_accounts)
    aggregate_balance = sum(a.current_balance for a in credit_accounts)
    aggregate_util = aggregate_balance / aggregate_limit if aggregate_limit else 0.0

    scored = [score_account(a, purchase, cash_apy, aggregate_util, aggregate_limit)
              for a in accounts]
    eligible = sorted([s for s in scored if s.eligible],
                      key=lambda s: s.net_benefit, reverse=True)
    ineligible = [s for s in scored if not s.eligible]

    best = eligible[0] if eligible else None
    runner_up = eligible[1] if len(eligible) > 1 else None

    summary = ""
    if best:
        summary = (f"Route to {best.name}: ${best.net_benefit:.2f} net benefit "
                   f"({best.effective_rate:.1%} effective)")
        if runner_up:
            summary += f" — beats {runner_up.name} by ${best.net_benefit - runner_up.net_benefit:.2f}"

    return {
        "purchase": {
            "amount": purchase.amount,
            "category": purchase.category,
            "merchant": purchase.merchant,
            "date": purchase.date.isoformat(),
        },
        "best": best.as_dict() if best else None,
        "ranking": [s.as_dict() for s in eligible],
        "ineligible": [s.as_dict() for s in ineligible],
        "summary": summary,
    }


# ── ORM adapter ──────────────────────────────────────────────────────────────

def snapshot_from_orm(account, category_spend: Optional[dict] = None) -> AccountSnapshot:
    """Build an engine snapshot from a models.Account row."""
    rules = [
        RewardRule(
            category=r.get("category", "other"),
            rate=float(r.get("rate", 0.0)),
            cap=r.get("cap"),
            cap_period=r.get("cap_period", "quarter"),
            note=r.get("note", ""),
        )
        for r in (account.reward_rules or [])
    ]
    return AccountSnapshot(
        id=account.id,
        name=account.name,
        kind=account.kind,
        can_pay=account.can_pay,
        active=account.active,
        current_balance=account.current_balance or 0.0,
        credit_limit=account.credit_limit,
        apr=account.apr or 0.0,
        statement_close_day=account.statement_close_day,
        payment_due_day=account.payment_due_day,
        carries_balance=bool(account.carries_balance),
        reports_to_bureaus=bool(account.reports_to_bureaus),
        apy=account.apy or 0.0,
        deposit_day=account.deposit_day,
        deposit_day_2=account.deposit_day_2,
        safety_buffer=account.safety_buffer or 0.0,
        base_rate=account.base_rate or 0.0,
        reward_rules=rules,
        bonus_value=account.bonus_value or 0.0,
        bonus_spend_required=account.bonus_spend_required or 0.0,
        bonus_spend_progress=account.bonus_spend_progress or 0.0,
        bonus_deadline=account.bonus_deadline,
        category_spend=category_spend or {},
    )
