import enum
from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
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


class AccountType(str, enum.Enum):
    # Assets
    cash = "cash"
    chequing = "chequing"
    savings = "savings"
    investment = "investment"
    tfsa = "tfsa"
    rrsp = "rrsp"
    resp = "resp"
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

    rules: Mapped[list["CategoryRule"]] = relationship(back_populates="category")


class CategoryRule(Base):
    """Keyword -> category mapping used by the auto-categorizer."""

    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    category: Mapped["Category"] = relationship(back_populates="rules")


class Tag(Base):
    """A free-form label across transactions — a trip, a project, a renovation."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        secondary=transaction_tags, back_populates="tags"
    )


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
