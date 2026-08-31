import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from . import engine as eng
from . import patterns
from .models import (
    init_db, get_db, Account, Transaction, RoutingDecision, CATEGORIES,
)
from .seed import seed_if_empty

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_if_empty()
    yield

app = FastAPI(title="Quick2 Purchase Router", lifespan=lifespan)

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["categories"] = CATEGORIES


# ── Data helpers ─────────────────────────────────────────────────────────────

async def _load_accounts(db: AsyncSession) -> list[Account]:
    result = await db.execute(select(Account).order_by(Account.kind, Account.name))
    return list(result.scalars().all())


async def _category_spend_map(db: AsyncSession, account_ids: list[int]) -> dict:
    """Per-account {(category, period_key): spend} for reward-cap tracking."""
    if not account_ids:
        return {}
    since = datetime.date.today() - datetime.timedelta(days=370)
    result = await db.execute(
        select(Transaction).where(Transaction.account_id.in_(account_ids),
                                  Transaction.date >= since)
    )
    spend: dict = {aid: {} for aid in account_ids}
    for t in result.scalars().all():
        for period in ("month", "quarter", "year"):
            key = (t.category, eng.period_key(t.date, period))
            acct_map = spend.setdefault(t.account_id, {})
            acct_map[key] = acct_map.get(key, 0.0) + t.amount
    return spend


async def _snapshots(db: AsyncSession) -> tuple[list[Account], list[eng.AccountSnapshot]]:
    accounts = await _load_accounts(db)
    spend = await _category_spend_map(db, [a.id for a in accounts])
    snaps = [eng.snapshot_from_orm(a, spend.get(a.id, {})) for a in accounts]
    return accounts, snaps


def _routing_result(snaps: list[eng.AccountSnapshot], amount: float,
                    category: str, merchant: str) -> dict:
    purchase = eng.Purchase(amount=amount, category=category, merchant=merchant)
    return eng.route(purchase, snaps)


# ── Tap-to-pay routing API ───────────────────────────────────────────────────

class RouteRequest(BaseModel):
    amount: float = Field(gt=0)
    category: str = "other"
    merchant: str = ""
    execute: bool = False  # True = record the charge on the winning account


@app.post("/api/route")
async def api_route(req: RouteRequest, db: AsyncSession = Depends(get_db)):
    """The tap-to-pay decision endpoint.

    In a production deployment this sits behind a virtual card (BIN sponsor /
    issuer-processor): the tap authorizes against the virtual card, this
    endpoint picks the funding account in-flight, and the charge is settled
    against the winner. Here, `execute=true` simulates that settlement.
    """
    if req.category not in CATEGORIES:
        raise HTTPException(400, f"unknown category '{req.category}' — one of {CATEGORIES}")
    accounts, snaps = await _snapshots(db)
    result = _routing_result(snaps, req.amount, req.category, req.merchant)

    executed = False
    if req.execute and result["best"]:
        executed = await _settle_charge(db, accounts, result["best"], req)

    decision = RoutingDecision(
        amount=req.amount, category=req.category, merchant=req.merchant,
        chosen_account_id=result["best"]["account_id"] if result["best"] else None,
        chosen_account_name=result["best"]["name"] if result["best"] else "",
        net_benefit=result["best"]["net_benefit"] if result["best"] else 0.0,
        ranking=result["ranking"],
        executed=executed,
    )
    db.add(decision)
    await db.commit()
    result["decision_id"] = decision.id
    result["executed"] = decision.executed
    return JSONResponse(result)


async def _settle_charge(db: AsyncSession, accounts: list[Account],
                         best: dict, req: RouteRequest) -> bool:
    """Apply the charge to the winning account.

    Re-checks availability against the account's current row before mutating,
    so a stale routing snapshot can't push a card over limit or a bank account
    negative — returns False and settles nothing in that case. (In production
    the issuer-processor's auth stream serializes authorizations per account.)
    """
    account = next(a for a in accounts if a.id == best["account_id"])
    if account.kind == "credit":
        if req.amount > (account.credit_limit or 0) - account.current_balance:
            return False
        account.current_balance += req.amount
        bonus_active = (
            (account.bonus_spend_required or 0) > (account.bonus_spend_progress or 0)
            and (account.bonus_deadline is None
                 or datetime.date.today() <= account.bonus_deadline)
        )
        if bonus_active:
            account.bonus_spend_progress = min(
                account.bonus_spend_required,
                (account.bonus_spend_progress or 0) + req.amount,
            )
    else:
        if req.amount > account.current_balance:
            return False
        account.current_balance -= req.amount
    db.add(Transaction(
        account_id=account.id, amount=req.amount, category=req.category,
        merchant=req.merchant, routed=True,
        reward_earned=best["breakdown"]["rewards_value"],
    ))
    return True


@app.get("/api/accounts")
async def api_accounts(db: AsyncSession = Depends(get_db)):
    accounts = await _load_accounts(db)
    return [
        {
            "id": a.id, "name": a.name, "issuer": a.issuer, "kind": a.kind,
            "last4": a.last4, "balance": a.current_balance,
            "credit_limit": a.credit_limit,
            "utilization": round(a.current_balance / a.credit_limit, 4)
            if a.kind == "credit" and a.credit_limit else None,
            "apr": a.apr, "apy": a.apy,
            "statement_close_day": a.statement_close_day,
            "payment_due_day": a.payment_due_day,
            "carries_balance": a.carries_balance,
        }
        for a in accounts
    ]


@app.get("/api/insights")
async def api_insights(db: AsyncSession = Depends(get_db)):
    accounts = await _load_accounts(db)
    result = await db.execute(select(Transaction))
    txns = list(result.scalars().all())
    return patterns.build_insights(txns, accounts)


# ── UI pages ─────────────────────────────────────────────────────────────────

def _upcoming_dates(accounts: list[Account]) -> list[dict]:
    today = datetime.date.today()
    events = []
    for a in accounts:
        if a.kind == "credit":
            if a.payment_due_day:
                d = eng.next_occurrence(today, a.payment_due_day)
                events.append({"date": d, "days": (d - today).days,
                               "label": f"{a.name} payment due",
                               "type": "due", "account": a})
            if a.statement_close_day:
                d = eng.next_occurrence(today, a.statement_close_day)
                events.append({"date": d, "days": (d - today).days,
                               "label": f"{a.name} statement closes (reports to bureaus)",
                               "type": "close", "account": a})
        elif a.kind == "checking":
            for dd in (a.deposit_day, a.deposit_day_2):
                if dd:
                    d = eng.next_occurrence(today, dd)
                    events.append({"date": d, "days": (d - today).days,
                                   "label": f"{a.name} paycheck deposit",
                                   "type": "deposit", "account": a})
    events.sort(key=lambda e: e["date"])
    return events[:8]


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    accounts = await _load_accounts(db)
    credit = [a for a in accounts if a.kind == "credit"]
    banks = [a for a in accounts if a.kind in ("checking", "savings", "investment")]
    total_limit = sum(a.credit_limit or 0 for a in credit)
    total_owed = sum(a.current_balance for a in credit)

    result = await db.execute(
        select(RoutingDecision).order_by(desc(RoutingDecision.id)).limit(8))
    recent = list(result.scalars().all())

    return templates.TemplateResponse(request, "dashboard.html", {
        "request": request,
        "credit_accounts": credit,
        "bank_accounts": banks,
        "total_limit": total_limit,
        "total_owed": total_owed,
        "aggregate_util": total_owed / total_limit if total_limit else 0,
        "total_cash": sum(a.current_balance for a in banks),
        "upcoming": _upcoming_dates(accounts),
        "recent_decisions": recent,
        "today": datetime.date.today(),
    })


@app.get("/tap", response_class=HTMLResponse)
async def tap_page(request: Request):
    return templates.TemplateResponse(request, "tap.html", {})


@app.post("/tap/route", response_class=HTMLResponse)
async def tap_route(request: Request,
                    amount: float = Form(...),
                    category: str = Form("other"),
                    merchant: str = Form(""),
                    execute: Optional[str] = Form(None),
                    db: AsyncSession = Depends(get_db)):
    """HTMX endpoint backing the tap-to-pay simulator."""
    if amount <= 0:
        return HTMLResponse("<p class='text-red-400'>Amount must be positive.</p>")
    if category not in CATEGORIES:
        return HTMLResponse("<p class='text-red-400'>Unknown category.</p>")
    accounts, snaps = await _snapshots(db)
    result = _routing_result(snaps, amount, category, merchant)

    executed = False
    if execute and result["best"]:
        executed = await _settle_charge(db, accounts, result["best"],
                                        RouteRequest(amount=amount, category=category,
                                                     merchant=merchant, execute=True))
    decision = RoutingDecision(
        amount=amount, category=category, merchant=merchant,
        chosen_account_id=result["best"]["account_id"] if result["best"] else None,
        chosen_account_name=result["best"]["name"] if result["best"] else "",
        net_benefit=result["best"]["net_benefit"] if result["best"] else 0.0,
        ranking=result["ranking"],
        executed=executed,
    )
    db.add(decision)
    await db.commit()

    return templates.TemplateResponse(request, "_decision.html", {
        "request": request, "result": result, "executed": decision.executed,
    })


@app.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, db: AsyncSession = Depends(get_db)):
    accounts = await _load_accounts(db)
    today = datetime.date.today()
    rows = []
    for a in accounts:
        row = {"a": a, "util": None, "close_in": None, "due_in": None, "deposit_in": None}
        if a.kind == "credit" and a.credit_limit:
            row["util"] = a.current_balance / a.credit_limit
            if a.statement_close_day:
                row["close_in"] = (eng.next_occurrence(today, a.statement_close_day) - today).days
            if a.payment_due_day:
                row["due_in"] = (eng.next_occurrence(today, a.payment_due_day) - today).days
        elif a.kind == "checking" and a.deposit_day:
            days = [(eng.next_occurrence(today, d) - today).days
                    for d in (a.deposit_day, a.deposit_day_2) if d]
            row["deposit_in"] = min(days) if days else None
        rows.append(row)
    return templates.TemplateResponse(request, "accounts.html", {"rows": rows})


@app.get("/insights", response_class=HTMLResponse)
async def insights_page(request: Request, db: AsyncSession = Depends(get_db)):
    accounts = await _load_accounts(db)
    result = await db.execute(select(Transaction))
    txns = list(result.scalars().all())
    insights = patterns.build_insights(txns, accounts)
    return templates.TemplateResponse(request, "insights.html", {
        "request": request, "insights": insights, "txn_count": len(txns),
    })


@app.get("/health")
async def health():
    return {"status": "ok"}
