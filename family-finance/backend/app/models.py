import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AccountType(str, enum.Enum):
    credit_card = "credit_card"
    chequing = "chequing"
    savings = "savings"
    investment = "investment"
    other = "other"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    institution: Mapped[str] = mapped_column(String(120), default="")
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType), default=AccountType.other
    )
    last_four: Mapped[str] = mapped_column(String(4), default="")

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    is_income: Mapped[bool] = mapped_column(default=False)

    rules: Mapped[list["CategoryRule"]] = relationship(back_populates="category")


class CategoryRule(Base):
    """Keyword -> category mapping used by the auto-categorizer."""

    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    category: Mapped["Category"] = relationship(back_populates="rules")


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
