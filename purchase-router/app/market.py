"""Market card catalog + recommendation engine.

Compares the user's best owned earn rate per category against the best cards
on the market. When a market card would out-earn the wallet on a category the
user actually spends in, we surface it with a referral link — this is the
monetization surface (referral/affiliate revenue).

Catalog rates are $-value earn fractions (points already valued).
"""

import re
from dataclasses import dataclass, field


def _norm(name: str) -> str:
    """Normalize card names for ownership matching ('U.S. Bank' == 'US Bank')."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


@dataclass
class MarketCard:
    name: str
    issuer: str
    headline: str
    annual_fee: float
    category_rates: dict  # {category: rate}
    base_rate: float
    signup_bonus: str
    referral_url: str  # affiliate/referral placeholder
    tags: list = field(default_factory=list)


MARKET_CATALOG = [
    MarketCard(
        name="Amex Gold",
        issuer="American Express",
        headline="4X points at restaurants and U.S. supermarkets",
        annual_fee=325.0,
        category_rates={"dining": 0.04, "groceries": 0.04},
        base_rate=0.01,
        signup_bonus="60,000 points after $6,000 spend in 6 months",
        referral_url="https://example.com/ref/amex-gold?aff=quick2",
        tags=["dining", "groceries"],
    ),
    MarketCard(
        name="Citi Custom Cash",
        issuer="Citi",
        headline="5% back on your top eligible category each cycle (up to $500)",
        annual_fee=0.0,
        category_rates={"dining": 0.05, "groceries": 0.05, "gas": 0.05,
                        "travel": 0.05, "drugstores": 0.05, "streaming": 0.05,
                        "transit": 0.05},
        base_rate=0.01,
        signup_bonus="$200 after $1,500 spend in 6 months",
        referral_url="https://example.com/ref/citi-custom-cash?aff=quick2",
        tags=["flexible 5%"],
    ),
    MarketCard(
        name="Wells Fargo Autograph",
        issuer="Wells Fargo",
        headline="3X on dining, travel, gas, transit, streaming",
        annual_fee=0.0,
        category_rates={"dining": 0.03, "travel": 0.03, "gas": 0.03,
                        "transit": 0.03, "streaming": 0.03},
        base_rate=0.01,
        signup_bonus="20,000 points after $1,000 spend in 3 months",
        referral_url="https://example.com/ref/wf-autograph?aff=quick2",
        tags=["no annual fee"],
    ),
    MarketCard(
        name="Capital One Savor",
        issuer="Capital One",
        headline="4% on dining and entertainment, 3% groceries",
        annual_fee=95.0,
        category_rates={"dining": 0.04, "entertainment": 0.04, "groceries": 0.03,
                        "streaming": 0.04},
        base_rate=0.01,
        signup_bonus="$300 after $3,000 spend in 3 months",
        referral_url="https://example.com/ref/c1-savor?aff=quick2",
        tags=["dining", "entertainment"],
    ),
    MarketCard(
        name="U.S. Bank Cash+",
        issuer="U.S. Bank",
        headline="5% on two categories you choose (up to $2,000/quarter)",
        annual_fee=0.0,
        category_rates={"utilities": 0.05, "streaming": 0.05, "home_improvement": 0.05,
                        "entertainment": 0.05},
        base_rate=0.01,
        signup_bonus="$200 after $1,000 spend in 120 days",
        referral_url="https://example.com/ref/usb-cashplus?aff=quick2",
        tags=["utilities", "choose-your-own 5%"],
    ),
    MarketCard(
        name="Chase Sapphire Reserve",
        issuer="Chase",
        headline="High-value travel earning with lounge access",
        annual_fee=550.0,
        category_rates={"travel": 0.045, "dining": 0.045},
        base_rate=0.015,
        signup_bonus="60,000 points after $5,000 spend in 3 months",
        referral_url="https://example.com/ref/csr?aff=quick2",
        tags=["premium travel"],
    ),
    MarketCard(
        name="Amazon Prime Visa",
        issuer="Chase",
        headline="5% at Amazon and Whole Foods for Prime members",
        annual_fee=0.0,
        category_rates={"online_shopping": 0.05},
        base_rate=0.01,
        signup_bonus="$100 gift card on approval",
        referral_url="https://example.com/ref/amazon-prime-visa?aff=quick2",
        tags=["online shopping"],
    ),
    MarketCard(
        name="Costco Anywhere Visa",
        issuer="Citi",
        headline="4% on gas and EV charging (up to $7,000/yr)",
        annual_fee=0.0,
        category_rates={"gas": 0.04, "travel": 0.03, "dining": 0.03},
        base_rate=0.01,
        signup_bonus="None",
        referral_url="https://example.com/ref/costco-visa?aff=quick2",
        tags=["gas"],
    ),
]

HIGH_YIELD_OFFERS = [
    {
        "name": "Marcus High-Yield Savings",
        "apy": 0.0440,
        "headline": "4.40% APY, no minimums",
        "referral_url": "https://example.com/ref/marcus?aff=quick2",
    },
    {
        "name": "Wealthfront Cash",
        "apy": 0.0450,
        "headline": "4.50% APY with instant transfers",
        "referral_url": "https://example.com/ref/wealthfront?aff=quick2",
    },
]


def best_owned_rate(accounts: list, category: str) -> tuple[float, str]:
    """Best earn rate the wallet already has for a category (credit cards only)."""
    best, name = 0.0, ""
    for a in accounts:
        if a.kind != "credit" or not a.active:
            continue
        rate = a.base_rate or 0.0
        for rule in (a.reward_rules or []):
            if rule.get("category") in (category, "all"):
                rate = max(rate, float(rule.get("rate", 0.0)))
        if rate > best:
            best, name = rate, a.name
    return best, name


def recommend_for_category(accounts: list, category: str,
                           annual_spend: float) -> list[dict]:
    """Market cards that would out-earn the wallet on this category.

    Only recommends when the incremental earnings clear the annual fee
    (fee is attributed entirely to this category — conservative).
    """
    owned_rate, owned_name = best_owned_rate(accounts, category)
    owned_names = {_norm(a.name) for a in accounts}
    recs = []
    for card in MARKET_CATALOG:
        if _norm(card.name) in owned_names:
            continue
        market_rate = card.category_rates.get(category, 0.0)
        if market_rate <= owned_rate:
            continue
        gross_gain = (market_rate - owned_rate) * annual_spend
        net_gain = gross_gain - card.annual_fee
        if net_gain <= 0:
            continue
        recs.append({
            "card": card.name,
            "issuer": card.issuer,
            "headline": card.headline,
            "category": category,
            "market_rate": market_rate,
            "owned_rate": owned_rate,
            "owned_best_card": owned_name,
            "annual_fee": card.annual_fee,
            "annual_spend": round(annual_spend, 2),
            "est_annual_gain": round(net_gain, 2),
            "signup_bonus": card.signup_bonus,
            "referral_url": card.referral_url,
        })
    recs.sort(key=lambda r: r["est_annual_gain"], reverse=True)
    return recs


def recommend_savings_upgrade(accounts: list) -> list[dict]:
    """Higher-APY homes for idle cash across connected bank accounts."""
    cash_accounts = [a for a in accounts
                     if a.kind in ("checking", "savings", "investment") and a.active]
    recs = []
    for offer in HIGH_YIELD_OFFERS:
        for a in cash_accounts:
            delta = offer["apy"] - (a.apy or 0.0)
            movable = max(0.0, (a.current_balance or 0.0) - (a.safety_buffer or 0.0))
            gain = delta * movable
            if gain > 25.0:  # only surface meaningful wins
                recs.append({
                    "offer": offer["name"],
                    "headline": offer["headline"],
                    "from_account": a.name,
                    "current_apy": a.apy or 0.0,
                    "offer_apy": offer["apy"],
                    "movable_balance": round(movable, 2),
                    "est_annual_gain": round(gain, 2),
                    "referral_url": offer["referral_url"],
                })
    recs.sort(key=lambda r: r["est_annual_gain"], reverse=True)
    # de-dupe: keep the best offer per source account
    seen, out = set(), []
    for r in recs:
        if r["from_account"] in seen:
            continue
        seen.add(r["from_account"])
        out.append(r)
    return out
