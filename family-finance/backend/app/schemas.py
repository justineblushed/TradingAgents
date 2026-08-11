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
    tags: list[str] = []

    class Config:
        from_attributes = True


class PayStubBase(BaseModel):
    employer: str = ""
    earner: str = ""
    pay_date: date
    period_start: date | None = None
    period_end: date | None = None
    gross_pay: float = 0
    income_tax: float = 0
    cpp: float = 0
    ei: float = 0
    rrsp_employee: float = 0
    pension_employee: float = 0
    union_dues: float = 0
    other_deductions: float = 0
    net_pay: float = 0
    employer_rrsp: float = 0
    employer_pension: float = 0
    notes: str = ""


class PayStubCreate(PayStubBase):
    pass


class PayStubOut(PayStubBase):
    id: int
    total_deductions: float = 0

    class Config:
        from_attributes = True


class PayStubDraftOut(BaseModel):
    """Parsed pre-fill — always reviewed by the user before saving."""

    employer: str = ""
    pay_date: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    gross_pay: float = 0
    income_tax: float = 0
    cpp: float = 0
    ei: float = 0
    rrsp_employee: float = 0
    pension_employee: float = 0
    union_dues: float = 0
    other_deductions: float = 0
    net_pay: float = 0
    employer_rrsp: float = 0
    employer_pension: float = 0
    warnings: list[str] = []
    matched_fields: list[str] = []


class TaxBracketOut(BaseModel):
    id: int
    tax_year: int
    jurisdiction: str
    lower_bound: float
    upper_bound: float | None
    rate: float

    class Config:
        from_attributes = True


class TaxBracketInput(BaseModel):
    lower_bound: float
    upper_bound: float | None = None
    rate: float


class TaxBracketsReplace(BaseModel):
    tax_year: int
    jurisdiction: str
    brackets: list[TaxBracketInput]


class TaxSettingOut(BaseModel):
    tax_year: int
    rrsp_rate: float
    rrsp_dollar_limit: float
    federal_basic_personal_amount: float
    provincial_basic_personal_amount: float
    province: str

    class Config:
        from_attributes = True


class PayrollSummary(BaseModel):
    """Year-to-date payroll picture plus estimated tax and RRSP position.

    Everything derived here is an estimate from the stubs entered: it
    knows nothing about other income, credits beyond the basic personal
    amount, spousal transfers, or your CRA carry-forward unless supplied.
    """

    tax_year: int
    stub_count: int
    ytd_gross: float
    ytd_income_tax: float
    ytd_cpp: float
    ytd_ei: float
    ytd_rrsp: float  # withheld from pay
    ytd_employer_rrsp: float = 0.0
    ytd_rrsp_contributed: float = 0.0  # yours + employer match; uses up room
    ytd_pension: float
    ytd_other_deductions: float
    ytd_net: float

    annualized_gross: float
    projection_basis: str  # how the annualization was derived

    tax: dict
    tax_if_rrsp_maxed: dict | None = None
    rrsp: dict
    withholding_delta: float | None = None  # + = over-withheld so far

    rates_verified_note: str


class TagOut(BaseModel):
    id: int
    name: str
    transaction_count: int = 0
    total_spent: float = 0.0

    class Config:
        from_attributes = True


class TagCreate(BaseModel):
    name: str


class TransactionTagsUpdate(BaseModel):
    tags: list[str]


class CategoryOut(BaseModel):
    id: int
    name: str
    kind: str = "expense"
    keywords: list[str] = []
    monthly_budget: float | None = None
    group_name: str = ""
    cost_type: str = "variable"
    controllability: str = "medium"
    color: str = ""
    emoji: str = ""

    class Config:
        from_attributes = True


class CategoryAppearanceUpdate(BaseModel):
    color: str
    emoji: str = ""


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


class BudgetVariance(BaseModel):
    """Pure fact: spent vs. the budget the user set. Not a saving."""

    category: str
    budget: float
    spent: float
    over: float


class AreaToWatch(BaseModel):
    """Spending unusually high against this category's own recent history."""

    category: str
    group_name: str
    cost_type: str
    controllability: str
    spent: float
    typical: float
    above_typical: float
    percent_above: float
    months_of_history: int
    # variable/recurring AND high control — the ones actually worth acting on
    highlight: bool


class SpendingControl(BaseModel):
    """How much of the month's spending is actually adjustable.

    Deliberately keeps three ideas separate rather than collapsing them
    into one headline "savings" number:

    1. budget variance — how far over the set budget, a fact about the
       past, not money that will reappear next month;
    2. areas to watch — spending high against the category's OWN recent
       typical, which is what actually signals something unusual;
    3. adjustable range — a bounded estimate, low = getting back to
       typical, high = matching the best recent month. Both bounds come
       from months the household actually achieved, and only
       variable/recurring + high-control categories count. Suppressed
       entirely with under two months of history rather than guessing.
    """

    month: str
    total_spending: float
    by_cost_type: list[CostTypeSlice]
    locked_amount: float  # fixed + irregular: little room to adjust

    over_budget_total: float
    budget_variances: list[BudgetVariance]

    areas_to_watch: list[AreaToWatch]

    adjustable_low: float | None = None
    adjustable_high: float | None = None
    adjustable_months_of_history: int = 0


class RuleOut(BaseModel):
    id: int
    keyword: str
    category: str
    category_id: int
    min_amount: float | None = None
    max_amount: float | None = None
    account_id: int | None = None
    account_name: str = ""
    priority: int = 0
    tags: list[str] = []
    # How many transactions this rule currently matches — the fastest way to
    # tell a useful rule from one that never fires or one that's far too broad.
    match_count: int = 0


class RuleInput(BaseModel):
    keyword: str
    category: str
    min_amount: float | None = None
    max_amount: float | None = None
    account_id: int | None = None
    priority: int = 0
    tags: list[str] = []


class RuleApplyRequest(BaseModel):
    """Re-run the rules over transactions already imported.

    `scope` decides what may be touched, in ascending order of risk:
      - "uncategorized": only rows with no category at all (the default);
      - "rule": also revise rows a previous rule run assigned;
      - "all": also overwrite categories the user set by hand.
    Manual choices are protected by default because silently undoing a
    correction is worse than leaving a row mis-filed.
    """

    scope: str = "uncategorized"
    dry_run: bool = True


class RuleApplyChange(BaseModel):
    transaction_id: int
    trans_date: date
    description: str
    amount: float
    account_name: str = ""
    from_category: str | None = None
    from_source: str | None = None
    to_category: str
    matched_keyword: str
    tags_added: list[str] = []


class RuleApplyResult(BaseModel):
    dry_run: bool
    scope: str
    considered: int  # transactions the scope allowed us to look at
    changed: int
    unchanged: int  # in scope, matched a rule, already filed there
    unmatched: int  # in scope, no rule matched
    protected_manual: int  # skipped because the user set them by hand
    changes: list[RuleApplyChange] = []


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


class CategoryMonthPoint(BaseModel):
    month: str
    total: float
    is_current: bool = False


class CategoryDetail(BaseModel):
    """One category, one month, plus enough history to judge whether that
    month was unusual. Totals net refunds against the category the same way
    the dashboard does, so drilling in never contradicts the chart you
    clicked from."""

    category: str
    kind: str
    group_name: str
    color: str = ""
    emoji: str = ""
    month: str
    total: float
    transaction_count: int
    monthly_budget: float | None = None
    over_budget: float | None = None
    average_of_history: float | None = None  # other months shown, excluding this one
    history: list[CategoryMonthPoint] = []
    transactions: list[TransactionOut] = []


class NextPayday(BaseModel):
    pay_date: date
    days_away: int
    expected_net: float | None = None
    employer: str = ""
    basis: str  # how the date was projected, so it can be sanity-checked


class UpcomingBill(BaseModel):
    """A charge the history says is due soon. An expectation, not an invoice."""

    description: str
    category: str | None = None
    account_name: str = ""
    expected_date: date
    days_away: int
    expected_amount: float
    amount_low: float
    amount_high: float
    amount_varies: bool
    cadence: str
    occurrences: int
    basis: str
    overdue: bool = False  # due date has passed with no matching charge yet


class UpcomingSummary(BaseModel):
    """Next payday and the bills the transaction history says are due.

    Both are inferred, not scheduled: nothing here was entered as a bill.
    A charge is only reported once it has repeated on a steady enough
    rhythm to be worth trusting, and each one carries the evidence behind
    it. Anything already paid this cycle is excluded rather than shown as
    still due.
    """

    as_of: date
    horizon_days: int
    next_payday: NextPayday | None = None
    payday_hint: str = ""  # why there is no payday, when there isn't one
    bills: list[UpcomingBill] = []
    bills_total: float = 0.0
    bills_hint: str = ""


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
