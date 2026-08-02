import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


class Base(DeclarativeBase):
    pass


# Account kinds
CREDIT = "credit"
CHECKING = "checking"
SAVINGS = "savings"
INVESTMENT = "investment"

# Purchase categories the engine understands
CATEGORIES = [
    "dining",
    "groceries",
    "gas",
    "travel",
    "online_shopping",
    "streaming",
    "drugstores",
    "entertainment",
    "transit",
    "utilities",
    "home_improvement",
    "other",
]


class Account(Base):
    """A payment or deposit account connected to the routing agent.

    Credit accounts use: credit_limit, current_balance, apr, statement_close_day,
    payment_due_day, carries_balance, reports_to_bureaus.
    Bank accounts (checking/savings/investment) use: current_balance, apy,
    deposit_day / deposit_day_2, safety_buffer.
    """

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    issuer = Column(String, default="")
    kind = Column(String, nullable=False)  # credit | checking | savings | investment
    network = Column(String, default="")  # visa, mastercard, amex, discover, ach
    last4 = Column(String, default="0000")
    active = Column(Boolean, default=True)
    can_pay = Column(Boolean, default=True)  # savings/investment usually can't tap-to-pay

    current_balance = Column(Float, default=0.0)  # credit: amount owed; bank: cash held

    # Credit-specific
    credit_limit = Column(Float, nullable=True)
    apr = Column(Float, default=0.0)  # annual rate, e.g. 0.2499
    statement_close_day = Column(Integer, nullable=True)  # day of month balance reports to bureaus
    payment_due_day = Column(Integer, nullable=True)  # day of month payment is due
    carries_balance = Column(Boolean, default=False)  # revolving => grace period lost
    reports_to_bureaus = Column(Boolean, default=True)

    # Bank-specific
    apy = Column(Float, default=0.0)  # interest earned on deposits
    deposit_day = Column(Integer, nullable=True)  # paycheck deposit day of month
    deposit_day_2 = Column(Integer, nullable=True)  # second deposit day (semi-monthly pay)
    deposit_amount = Column(Float, default=0.0)
    safety_buffer = Column(Float, default=0.0)  # min cash to keep before next deposit

    # Rewards
    base_rate = Column(Float, default=0.0)  # catch-all earn rate (fraction of $)
    point_value = Column(Float, default=0.01)  # $ value per point/mile (cashback = 0.01/1%)
    reward_unit = Column(String, default="cashback")  # cashback | points | miles
    reward_rules = Column(JSON, default=list)
    # reward_rules: [{"category": "dining", "rate": 0.04,
    #                 "cap": 1500.0, "cap_period": "quarter"|"month"|"year",
    #                 "note": "Q3 rotating category"}]
    # rate is the $-value earn fraction already multiplied by point_value where relevant.

    # Sign-up bonus in progress
    bonus_value = Column(Float, default=0.0)  # $ value of the bonus
    bonus_spend_required = Column(Float, default=0.0)
    bonus_spend_progress = Column(Float, default=0.0)
    bonus_deadline = Column(Date, nullable=True)

    annual_fee = Column(Float, default=0.0)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    transactions = relationship("Transaction", back_populates="account")


class Transaction(Base):
    """A purchase routed (or manually made) on an account."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    date = Column(Date, nullable=False, default=datetime.date.today)
    amount = Column(Float, nullable=False)
    category = Column(String, default="other")
    merchant = Column(String, default="")
    reward_earned = Column(Float, default=0.0)  # $ value earned on this txn
    routed = Column(Boolean, default=False)  # True if the agent picked the account
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    account = relationship("Account", back_populates="transactions")


class RoutingDecision(Base):
    """Audit log of every routing decision the agent made."""

    __tablename__ = "routing_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, default=datetime.date.today)
    amount = Column(Float, nullable=False)
    category = Column(String, default="other")
    merchant = Column(String, default="")
    chosen_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    chosen_account_name = Column(String, default="")
    net_benefit = Column(Float, default=0.0)
    ranking = Column(JSON, default=list)  # full scored ranking snapshot
    executed = Column(Boolean, default=False)  # charge actually recorded
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# Database setup
DATABASE_URL = "sqlite+aiosqlite:///./purchase_router.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        yield session
