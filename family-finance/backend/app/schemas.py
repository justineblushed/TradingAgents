from datetime import date, datetime

from pydantic import BaseModel


class ParsedTransaction(BaseModel):
    trans_date: date
    post_date: date | None = None
    description: str
    amount: float
    foreign_currency_note: str = ""
    suggested_category: str | None = None


class StatementPreview(BaseModel):
    account_last_four: str = ""
    transactions: list[ParsedTransaction]
    warnings: list[str] = []


class ImportRequest(BaseModel):
    account_id: int
    period_label: str = ""
    transactions: list[ParsedTransaction]
    # "block": refuse with a 409 if any transaction already exists (default);
    # "skip": import only the new ones; "import": import everything anyway.
    on_duplicate: str = "block"


class TransactionOut(BaseModel):
    id: int
    trans_date: date
    post_date: date | None
    description: str
    amount: float
    category: str | None = None

    class Config:
        from_attributes = True


class CategoryOut(BaseModel):
    id: int
    name: str
    kind: str = "expense"
    keywords: list[str] = []
    monthly_budget: float | None = None
    group_name: str = ""
    cost_type: str = "variable"
    controllability: str = "medium"

    class Config:
        from_attributes = True


class CategoryBudgetUpdate(BaseModel):
    monthly_budget: float | None = None


class CategoryClassificationUpdate(BaseModel):
    cost_type: str
    controllability: str


class CostTypeSlice(BaseModel):
    cost_type: str
    label: str
    amount: float
    percent: float


class CutCandidate(BaseModel):
    category: str
    group_name: str
    cost_type: str
    controllability: str
    spent: float
    reference: float  # budget, or typical spending when no budget is set
    over: float
    basis: str  # "budget" | "typical spending"


class SpendingControl(BaseModel):
    """How much of the month's spending is actually adjustable.

    Splits spending by cost type, then ranks the categories that are both
    over their reference AND realistically controllable. Potential savings
    counts only high/very-high controllability overages — an $800 car
    repair is variable but not a choice, and promising it as "savings"
    would make the number a lie.
    """

    month: str
    total_spending: float
    by_cost_type: list[CostTypeSlice]
    locked_amount: float  # fixed + irregular: little room to adjust
    cut_candidates: list[CutCandidate]
    potential_savings: float


class CategoryCreate(BaseModel):
    name: str
    kind: str = "expense"
    group_name: str = ""


class CategoryKeywordsUpdate(BaseModel):
    keywords: list[str]


class AccountCreate(BaseModel):
    name: str
    institution: str = ""
    account_type: str = "other_asset"
    last_four: str = ""
    credit_limit: float | None = None


class AccountOut(AccountCreate):
    id: int
    is_liability: bool = False

    class Config:
        from_attributes = True


class AccountBalanceCreate(BaseModel):
    as_of_date: date
    balance: float


class AccountBalanceOut(BaseModel):
    id: int
    account_id: int
    as_of_date: date
    balance: float

    class Config:
        from_attributes = True


class AccountWithBalance(BaseModel):
    id: int
    name: str
    account_type: str
    is_liability: bool
    credit_limit: float | None = None
    current_balance: float | None = None
    balance_as_of: date | None = None
    balance_is_estimated: bool = False


class NetWorthSummary(BaseModel):
    assets_total: float
    liabilities_total: float
    net_worth: float
    net_worth_prev_month: float | None = None
    delta: float | None = None
    accounts: list[AccountWithBalance]


class CreditCardSummary(BaseModel):
    account_id: int
    name: str
    current_balance: float | None = None
    balance_as_of: date | None = None
    balance_is_estimated: bool = False
    credit_limit: float | None = None
    available_credit: float | None = None
    month_spending: float
    month_payments: float


class MonthCoverage(BaseModel):
    month: str  # "2026-07"
    transaction_count: int
    covered: bool
    skipped: bool = False


class AccountCoverage(BaseModel):
    account_id: int
    account_name: str
    months: list[MonthCoverage]
    missing_months: list[str]
    last_imported_at: datetime | None = None
    days_since_last_import: int | None = None


class CoverageSummary(BaseModel):
    accounts: list[AccountCoverage]
    total_missing: int


class DashboardSummary(BaseModel):
    """Household cash flow for the month. Transfers between the family's own
    accounts (e.g. paying off a credit card from chequing) are excluded from
    both totals — see CategoryKind.transfer. Merchant refunds in an expense
    category offset that category (net), they are not income."""

    month: str
    total_spending: float
    total_income: float
    net_cash_flow: float
    by_category: dict[str, float]
    by_group: dict[str, float]
