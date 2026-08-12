import enum
from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Tags are a dimension orthogonal to categories: a Chicago trip's groceries
# stay Groceries and its gas stays Gas & Parking, while the tag answers
# "what did the whole trip cost?" — no Travel Food / Travel Gas categories.
transaction_tags = Table(
    "transaction_tags",
    Base.metadata,
    Column("transaction_id", ForeignKey("transactions.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)

# Tags a rule applies automatically when it matches.
category_rule_tags = Table(
    "category_rule_tags",
    Base.metadata,
    Column("rule_id", ForeignKey("category_rules.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class AccountType(str, enum.Enum):
    # Assets
    cash = "cash"
    chequing = "chequing"
    savings = "savings"
    investment = "investment"
    tfsa = "tfsa"
    rrsp = "rrsp"
    resp = "resp"
    # Paired conceptually with mortgage/car_loan below: the loan is what
    # you owe, this is what it bought — recording both is what makes net
    # worth reflect reality instead of just the debt side.
    real_estate = "real_estate"
    vehicle = "vehicle"
    other_asset = "other_asset"
    # Liabilities
    credit_card = "credit_card"
    mortgage = "mortgage"
    car_loan = "car_loan"
    other_liability = "other_liability"


LIABILITY_ACCOUNT_TYPES = frozenset(
    {
        AccountType.credit_card,
        AccountType.mortgage,
        AccountType.car_loan,
        AccountType.other_liability,
    }
)


def is_liability_type(account_type: AccountType) -> bool:
    return account_type in LIABILITY_ACCOUNT_TYPES


class CategoryKind(str, enum.Enum):
    expense = "expense"
    income = "income"
    # Money moving between the household's own accounts — e.g. a credit
    # card payment from chequing. Never counted as spending or income.
    transfer = "transfer"


class CostType(str, enum.Enum):
    """How much this spending is locked in month to month."""

    fixed = "fixed"  # contractual, same every month (mortgage, car loan)
    recurring = "recurring"  # regular but cancellable (subscriptions)
    variable = "variable"  # changes with behaviour (groceries, dining)
    irregular = "irregular"  # lumpy and unplanned (car repairs, medical)


class Controllability(str, enum.Enum):
    """How much room there realistically is to cut this month.

    Deliberately separate from CostType: car maintenance is variable but
    an $800 repair isn't a choice, while dining out is variable AND easy
    to cut. Only the controllable part is offered as potential savings.
    """

    low = "low"
    medium = "medium"
    high = "high"
    very_high = "very_high"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    institution: Mapped[str] = mapped_column(String(120), default="")
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType), default=AccountType.other_asset
    )
    last_four: Mapped[str] = mapped_column(String(4), default="")
    # Only meaningful for credit_card accounts; used to compute available credit.
    credit_limit: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Manual display order within its own Assets/Liabilities group on the Net
    # Worth page. Nullable so older rows can be backfilled by migration.
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")
    balances: Mapped[list["AccountBalance"]] = relationship(
        back_populates="account", order_by="AccountBalance.as_of_date"
    )

    @property
    def is_liability(self) -> bool:
        return is_liability_type(self.account_type)


class AccountBalance(Base):
    """A manually-recorded balance snapshot for an account on a given date.

    Net worth has no bank-feed to pull real-time balances from, so the user
    records balances themselves periodically (e.g. once a month) — this
    table holds that history. The latest snapshot per account is what the
    Net Worth page and credit-card "current balance" figures are based on.
    """

    __tablename__ = "account_balances"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    as_of_date: Mapped[date] = mapped_column(Date)
    balance: Mapped[float] = mapped_column(Numeric(12, 2))

    account: Mapped["Account"] = relationship(back_populates="balances")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[CategoryKind] = mapped_column(
        Enum(CategoryKind), default=CategoryKind.expense
    )
    # Optional monthly spending target; drives the "within budget" health
    # metric and the biggest-opportunity insight. Null = no target set.
    monthly_budget: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Roll-up group for dashboard reading ("Housing", "Food", ...). Empty for
    # user-created categories that haven't been grouped.
    group_name: Mapped[str] = mapped_column(String(40), default="")
    # Two independent dimensions used by the "where can I cut?" analysis.
    # Meaningful for expense categories only.
    cost_type: Mapped[CostType] = mapped_column(
        Enum(CostType), default=CostType.variable
    )
    controllability: Mapped[Controllability] = mapped_column(
        Enum(Controllability), default=Controllability.medium
    )
    # Appearance. A category keeps the same colour everywhere it appears, so
    # the pie, the bar chart and the drill-down all agree — a palette that
    # rotates by chart position means "the blue slice" changes meaning
    # whenever spending reorders the chart.
    color: Mapped[str] = mapped_column(String(7), default="")  # "#2f6fed"
    emoji: Mapped[str] = mapped_column(String(8), default="")

    rules: Mapped[list["CategoryRule"]] = relationship(back_populates="category")


class CategoryRule(Base):
    """A condition that files a transaction into a category automatically.

    The keyword is the only required condition; the rest narrow it. That
    matters because one merchant can mean two different things: a $9.99
    charge from a warehouse store is a membership fee, a $240 one is
    groceries. Conditions are ANDed, and the most specific matching rule
    wins (see app.categorize.match_category).
    """

    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    # Optional narrowing conditions. Null means "don't care".
    # Bounds are inclusive and compared against the absolute amount, so a
    # rule reads the same whether it targets a charge or a refund.
    min_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    # Manual tie-breaker for equally specific rules; higher wins.
    priority: Mapped[int] = mapped_column(default=0)

    category: Mapped["Category"] = relationship(back_populates="rules")
    account: Mapped["Account | None"] = relationship()
    # Tags applied alongside the category when this rule matches — lets
    # "every charge at this vet gets tagged #pets" happen without hand-tagging.
    tags: Mapped[list["Tag"]] = relationship(secondary="category_rule_tags")


class Tag(Base):
    """A free-form label across transactions — a trip, a project, a renovation."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        secondary=transaction_tags, back_populates="tags"
    )


class PayStub(Base):
    """One pay period, decomposed.

    A bank statement only shows the net deposit. The stub is what reveals
    gross pay and where the rest went — income tax withheld, CPP, EI,
    RRSP/pension contributions — which is what actual tax-bracket and
    RRSP-room calculations need.
    """

    __tablename__ = "pay_stubs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer: Mapped[str] = mapped_column(String(120), default="")
    earner: Mapped[str] = mapped_column(String(80), default="")  # which family member
    pay_date: Mapped[date] = mapped_column(Date)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    gross_pay: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    income_tax: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    cpp: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    ei: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    rrsp_employee: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    pension_employee: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    union_dues: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    other_deductions: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    net_pay: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Employer-side amounts don't reduce take-home but do affect RRSP room
    # (via the pension adjustment) and total compensation.
    employer_rrsp: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    employer_pension: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    notes: Mapped[str] = mapped_column(Text, default="")


class TaxBracket(Base):
    """A progressive tax bracket, stored as data so rates can be corrected
    without a code change — they are indexed annually and this app should
    never pretend its built-in numbers are authoritative."""

    __tablename__ = "tax_brackets"

    id: Mapped[int] = mapped_column(primary_key=True)
    tax_year: Mapped[int] = mapped_column()
    jurisdiction: Mapped[str] = mapped_column(String(20))  # "federal" | "MB" | ...
    lower_bound: Mapped[float] = mapped_column(Numeric(12, 2))
    upper_bound: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    rate: Mapped[float] = mapped_column(Numeric(6, 4))  # 0.205 = 20.5%


class TaxYearSetting(Base):
    __tablename__ = "tax_year_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    tax_year: Mapped[int] = mapped_column(unique=True)
    rrsp_rate: Mapped[float] = mapped_column(Numeric(6, 4), default=0.18)
    rrsp_dollar_limit: Mapped[float] = mapped_column(Numeric(12, 2))
    federal_basic_personal_amount: Mapped[float] = mapped_column(Numeric(12, 2))
    provincial_basic_personal_amount: Mapped[float] = mapped_column(Numeric(12, 2))
    province: Mapped[str] = mapped_column(String(20), default="MB")


class CoverageSkip(Base):
    """A month the user marked as N/A for an account — no statement exists
    (card unused that month, account opened mid-year, etc.), so the
    statement checklist shouldn't keep flagging it as missing."""

    __tablename__ = "coverage_skips"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    month: Mapped[str] = mapped_column(String(7))  # "2026-05"


class Statement(Base):
    """One imported statement file (metadata only — the source PDF is never stored)."""

    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    period_label: Mapped[str] = mapped_column(String(40), default="")
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    transaction_count: Mapped[int] = mapped_column(default=0)

    account: Mapped["Account"] = relationship()


class CategorySource(str, enum.Enum):
    """Who decided this transaction's category.

    Recorded so a retroactive rule run can leave hand-corrections alone.
    Without it, re-running the rules would silently undo every fix the
    household made by hand — the exact opposite of helpful.
    """

    rule = "rule"  # assigned by the auto-categorizer
    manual = "manual"  # the user chose it


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    statement_id: Mapped[int | None] = mapped_column(
        ForeignKey("statements.id"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    category_source: Mapped[CategorySource | None] = mapped_column(
        Enum(CategorySource), nullable=True
    )

    trans_date: Mapped[date] = mapped_column(Date)
    post_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    foreign_currency_note: Mapped[str] = mapped_column(String(120), default="")

    account: Mapped["Account"] = relationship(back_populates="transactions")
    category: Mapped["Category | None"] = relationship()
    tags: Mapped[list["Tag"]] = relationship(
        secondary=transaction_tags, back_populates="transactions"
    )
