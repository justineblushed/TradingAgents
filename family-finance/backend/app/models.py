import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


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

    rules: Mapped[list["CategoryRule"]] = relationship(back_populates="category")


class CategoryRule(Base):
    """Keyword -> category mapping used by the auto-categorizer."""

    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    category: Mapped["Category"] = relationship(back_populates="rules")


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
