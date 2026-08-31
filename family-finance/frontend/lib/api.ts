const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type ParsedTransaction = {
  trans_date: string;
  post_date: string | null;
  description: string;
  amount: number;
  foreign_currency_note: string;
  suggested_category: string | null;
};

export type StatementPreview = {
  account_last_four: string;
  transactions: ParsedTransaction[];
  warnings: string[];
  flip_amount_sign_applied: boolean | null;
  // True when the file was parsed as a credit-card PDF statement — lets
  // the upload form warn if the selected account isn't typed as a credit
  // card, the exact mix-up of a card statement landing on the wrong
  // account by accident.
  is_credit_card_statement: boolean;
};

export const ASSET_ACCOUNT_TYPES = [
  "cash",
  "chequing",
  "savings",
  "investment",
  "tfsa",
  "rrsp",
  "resp",
  "real_estate",
  "vehicle",
  "other_asset",
] as const;

export const LIABILITY_ACCOUNT_TYPES = [
  "credit_card",
  "mortgage",
  "car_loan",
  "other_liability",
] as const;

export type AccountType =
  | (typeof ASSET_ACCOUNT_TYPES)[number]
  | (typeof LIABILITY_ACCOUNT_TYPES)[number];

export const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  cash: "Cash",
  chequing: "Chequing",
  savings: "Savings",
  investment: "Investment",
  tfsa: "TFSA",
  rrsp: "RRSP",
  resp: "RESP",
  real_estate: "Real Estate",
  vehicle: "Vehicle",
  other_asset: "Other asset",
  credit_card: "Credit Card",
  mortgage: "Mortgage",
  car_loan: "Car Loan",
  other_liability: "Other liability",
};

// Short answers to "what does this type actually capture?" — shown as a
// caption under the type selector wherever an account gets created or
// edited, so the choice is self-explanatory instead of a guess.
export const ACCOUNT_TYPE_HINTS: Record<AccountType, string> = {
  cash: "Physical cash or anything else you track by hand — no statements to import.",
  chequing: "Your everyday spending account — debit card, e-transfers, bill payments.",
  savings: "A savings account outside any registered plan.",
  investment:
    "A non-registered (taxable) brokerage account — stocks, ETFs, mutual funds. Not a TFSA, RRSP, or RESP — those have their own types below.",
  tfsa: "Tax-Free Savings Account — registered; growth and withdrawals are tax-free.",
  rrsp: "Registered Retirement Savings Plan — registered; contributions are tax-deductible.",
  resp: "Registered Education Savings Plan — registered; for a child's education.",
  real_estate:
    "The current value of a property you own — pairs with a Mortgage liability, since the loan and the home it bought are two separate sides of the same picture.",
  vehicle:
    "The current value of a vehicle you own — pairs with a Car Loan liability the same way.",
  other_asset: "Anything else you own that doesn't fit the types above.",
  credit_card: "A credit card balance — what you currently owe.",
  mortgage: "Your home loan balance.",
  car_loan: "A vehicle loan or lease balance.",
  other_liability: "Anything else you owe that doesn't fit the types above.",
};

export type Account = {
  id: number;
  name: string;
  institution: string;
  account_type: AccountType;
  last_four: string;
  credit_limit: number | null;
  is_liability: boolean;
  sort_order: number | null;
  // Explicit CSV sign-convention override — null means "let the next
  // import's heuristic decide and lock itself in" (see the Statement Log
  // page's convention selector).
  csv_amount_sign_flipped: boolean | null;
};

export type DashboardSummary = {
  month: string;
  total_spending: number;
  total_income: number;
  net_cash_flow: number;
  by_category: Record<string, number>;
  by_group: Record<string, number>;
};

export type Rule = {
  id: number;
  keyword: string;
  category: string;
  category_id: number;
  min_amount: number | null;
  max_amount: number | null;
  account_id: number | null;
  account_name: string;
  priority: number;
  tags: string[];
  match_count: number;
};

export type RuleInput = {
  keyword: string;
  category: string;
  min_amount: number | null;
  max_amount: number | null;
  account_id: number | null;
  priority: number;
  tags: string[];
};

export type RuleScope = "uncategorized" | "rule" | "all";

export const RULE_SCOPE_LABELS: Record<RuleScope, string> = {
  uncategorized: "Only uncategorized transactions",
  rule: "Also revise ones the rules filed before",
  all: "Everything, including categories I set by hand",
};

export type RuleApplyChange = {
  transaction_id: number;
  trans_date: string;
  description: string;
  amount: number;
  account_name: string;
  from_category: string | null;
  from_source: string | null;
  to_category: string;
  matched_keyword: string;
  tags_added: string[];
};

export type RuleApplyResult = {
  dry_run: boolean;
  scope: RuleScope;
  considered: number;
  changed: number;
  unchanged: number;
  unmatched: number;
  protected_manual: number;
  changes: RuleApplyChange[];
};

export type CategoryMonthPoint = {
  month: string;
  total: number;
  is_current: boolean;
};

export type CategoryDetail = {
  category: string;
  kind: string;
  group_name: string;
  color: string;
  emoji: string;
  month: string;
  total: number;
  transaction_count: number;
  monthly_budget: number | null;
  over_budget: number | null;
  average_of_history: number | null;
  history: CategoryMonthPoint[];
  transactions: Transaction[];
};

export type NextPayday = {
  pay_date: string;
  days_away: number;
  expected_net: number | null;
  employer: string;
  basis: string;
};

export type UpcomingBill = {
  description: string;
  category: string | null;
  account_name: string;
  expected_date: string;
  days_away: number;
  expected_amount: number;
  amount_low: number;
  amount_high: number;
  amount_varies: boolean;
  cadence: string;
  occurrences: number;
  basis: string;
  overdue: boolean;
};

export type UpcomingSummary = {
  as_of: string;
  horizon_days: number;
  next_payday: NextPayday | null;
  payday_hint: string;
  bills: UpcomingBill[];
  bills_total: number;
  bills_hint: string;
};

export type CreditCardSummary = {
  account_id: number;
  name: string;
  current_balance: number | null;
  balance_as_of: string | null;
  balance_is_estimated: boolean;
  credit_limit: number | null;
  available_credit: number | null;
  month_spending: number;
  month_payments: number;
};

export type AccountWithBalance = {
  id: number;
  name: string;
  account_type: AccountType;
  is_liability: boolean;
  credit_limit: number | null;
  current_balance: number | null;
  balance_as_of: string | null;
  balance_is_estimated: boolean;
  csv_amount_sign_flipped: boolean | null;
};

export type NetWorthSummary = {
  assets_total: number;
  liabilities_total: number;
  net_worth: number;
  net_worth_prev_month: number | null;
  delta: number | null;
  accounts_with_history: number;
  accounts_total: number;
  accounts: AccountWithBalance[];
};

export type MonthCoverage = {
  month: string;
  transaction_count: number;
  covered: boolean;
  skipped: boolean;
};

export type AccountCoverage = {
  account_id: number;
  account_name: string;
  months: MonthCoverage[];
  missing_months: string[];
  last_imported_at: string | null;
  days_since_last_import: number | null;
};

export type CoverageSummary = {
  accounts: AccountCoverage[];
  total_missing: number;
};

export type CategoryKind = "expense" | "income" | "transfer";

export type CostType = "fixed" | "recurring" | "variable" | "irregular";
export type Controllability = "low" | "medium" | "high" | "very_high";

export const COST_TYPE_LABELS: Record<CostType, string> = {
  fixed: "Fixed",
  recurring: "Recurring",
  variable: "Variable",
  irregular: "Irregular",
};

export const CONTROL_LABELS: Record<Controllability, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  very_high: "Very high",
};

export type Category = {
  id: number;
  name: string;
  kind: CategoryKind;
  keywords: string[];
  monthly_budget: number | null;
  group_name: string;
  cost_type: CostType;
  controllability: Controllability;
  color: string;
  emoji: string;
};

// The same order the Categories page itself renders in, top to bottom:
// expense categories grouped by GROUP_ORDER (plus an "Other" bucket for any
// ungrouped/unrecognized group), then Income categories, then Transfer
// categories. Any category picker elsewhere in the app should read in this
// order instead of the flat alphabetical list /categories returns — this is
// the single place that ordering is defined so every picker stays in sync
// with the Categories page instead of drifting into its own A-Z list.
export function groupedCategorySections(
  categories: Category[]
): { label: string; categories: Category[] }[] {
  const expense = categories.filter((c) => c.kind === "expense");
  const income = categories.filter((c) => c.kind === "income");
  const transfer = categories.filter((c) => c.kind === "transfer");

  const sections: { label: string; categories: Category[] }[] = GROUP_ORDER.filter(
    (g) => expense.some((c) => c.group_name === g)
  ).map((group) => ({
    label: group,
    categories: expense.filter((c) => c.group_name === group),
  }));

  const other = expense.filter(
    (c) => !c.group_name || !(GROUP_ORDER as readonly string[]).includes(c.group_name)
  );
  if (other.length > 0) sections.push({ label: "Other", categories: other });

  if (income.length > 0) sections.push({ label: "Income", categories: income });
  if (transfer.length > 0) sections.push({ label: "Transfer", categories: transfer });

  return sections;
}

export type CostTypeSlice = {
  cost_type: CostType;
  label: string;
  amount: number;
  percent: number;
};

export type BudgetVariance = {
  category: string;
  budget: number;
  spent: number;
  over: number;
};

export type AreaToWatch = {
  category: string;
  group_name: string;
  cost_type: CostType;
  controllability: Controllability;
  spent: number;
  typical: number;
  above_typical: number;
  percent_above: number;
  months_of_history: number;
  highlight: boolean;
};

export type SpendingControl = {
  month: string;
  total_spending: number;
  by_cost_type: CostTypeSlice[];
  locked_amount: number;
  over_budget_total: number;
  budget_variances: BudgetVariance[];
  areas_to_watch: AreaToWatch[];
  adjustable_low: number | null;
  adjustable_high: number | null;
  adjustable_months_of_history: number;
};

export type Tag = {
  id: number;
  name: string;
  transaction_count: number;
  total_spent: number;
};

export const GROUP_ORDER = [
  "Housing",
  "Transportation",
  "Food",
  "Family",
  "Lifestyle",
  "Travel",
  "Financial",
] as const;

export type HealthMetric = {
  key: string;
  label: string;
  status: "good" | "warn" | "bad" | "none";
  display_value: string;
  detail: string;
};

export type HealthOpportunity = {
  category: string;
  over_amount: number;
  annual_saving: number;
  basis: string;
  month: string;
};

export type HealthScore = {
  score: number | null;
  band: string;
  reference_month: string | null;
  metrics: HealthMetric[];
  opportunity: HealthOpportunity | null;
};

export type Transaction = {
  id: number;
  trans_date: string;
  post_date: string | null;
  description: string;
  amount: number;
  category: string | null;
  tags: string[];
};

export type TransactionKind = "expense" | "income";

export type PayStubFields = {
  employer: string;
  earner: string;
  pay_date: string;
  period_start: string | null;
  period_end: string | null;
  gross_pay: number;
  income_tax: number;
  cpp: number;
  ei: number;
  rrsp_employee: number;
  pension_employee: number;
  union_dues: number;
  other_deductions: number;
  net_pay: number;
  employer_rrsp: number;
  employer_pension: number;
  notes: string;
};

export type PayStub = PayStubFields & {
  id: number;
  total_deductions: number;
};

export type PayStubDraft = Omit<PayStubFields, "pay_date" | "earner" | "notes"> & {
  pay_date: string | null;
  warnings: string[];
  matched_fields: string[];
};

/** Money amounts the user reviews and edits before a stub is saved. The
 *  order here drives the review form and the YTD table, so the two always
 *  agree on what a "deduction" is. */
export const PAY_STUB_DEDUCTIONS: { key: keyof PayStubFields; label: string }[] = [
  { key: "income_tax", label: "Income tax" },
  { key: "cpp", label: "CPP / QPP" },
  { key: "ei", label: "EI" },
  { key: "rrsp_employee", label: "RRSP (yours)" },
  { key: "pension_employee", label: "Pension (yours)" },
  { key: "union_dues", label: "Union dues" },
  { key: "other_deductions", label: "Other deductions" },
];

export const PAY_STUB_EMPLOYER_FIELDS: { key: keyof PayStubFields; label: string }[] = [
  { key: "employer_rrsp", label: "Employer RRSP match" },
  { key: "employer_pension", label: "Employer pension" },
];

export type TaxBracketHit = {
  jurisdiction: string;
  rate: number;
  lower_bound: number;
  upper_bound: number | null;
};

export type TaxEstimate = {
  available: boolean;
  tax_year?: number;
  province?: string;
  annual_gross?: number;
  rrsp_deduction?: number;
  taxable_income?: number;
  federal_tax?: number;
  provincial_tax?: number;
  total_tax?: number;
  marginal_rate?: number;
  average_rate?: number;
  federal_bracket?: TaxBracketHit | null;
  provincial_bracket?: TaxBracketHit | null;
  additional_contribution?: number;
  tax_saving?: number;
};

export type RrspRoom = {
  available: boolean;
  tax_year?: number;
  rate?: number;
  dollar_limit?: number;
  earned_income?: number;
  generated?: number;
  pension_adjustment?: number;
  carry_forward?: number;
  room?: number;
  capped_by_limit?: boolean;
};

export type PayrollSummary = {
  tax_year: number;
  stub_count: number;
  ytd_gross: number;
  ytd_income_tax: number;
  ytd_cpp: number;
  ytd_ei: number;
  ytd_rrsp: number;
  ytd_employer_rrsp: number;
  ytd_rrsp_contributed: number;
  ytd_pension: number;
  ytd_other_deductions: number;
  ytd_net: number;
  annualized_gross: number;
  projection_basis: string;
  tax: TaxEstimate;
  tax_if_rrsp_maxed: TaxEstimate | null;
  rrsp: RrspRoom;
  withholding_delta: number | null;
  rates_verified_note: string;
};

export type TaxBracket = {
  id: number;
  tax_year: number;
  jurisdiction: string;
  lower_bound: number;
  upper_bound: number | null;
  rate: number;
};

export type TaxSetting = {
  tax_year: number;
  rrsp_rate: number;
  rrsp_dollar_limit: number;
  federal_basic_personal_amount: number;
  provincial_basic_personal_amount: number;
  province: string;
};

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function listAccounts(): Promise<Account[]> {
  return asJson(await fetch(`${API_BASE}/accounts`));
}

export async function createAccount(payload: {
  name: string;
  account_type: AccountType;
  credit_limit?: number | null;
}): Promise<Account> {
  return asJson(
    await fetch(`${API_BASE}/accounts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

export async function updateAccount(
  accountId: number,
  payload: Partial<{
    name: string;
    institution: string;
    account_type: AccountType;
    last_four: string;
    credit_limit: number | null;
    csv_amount_sign_flipped: boolean | null;
  }>
): Promise<Account> {
  return asJson(
    await fetch(`${API_BASE}/accounts/${accountId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

export async function deleteAccount(accountId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/accounts/${accountId}`, { method: "DELETE" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
}

export async function moveAccount(
  accountId: number,
  direction: "up" | "down"
): Promise<Account[]> {
  return asJson(
    await fetch(`${API_BASE}/accounts/${accountId}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction }),
    })
  );
}

export async function recordAccountBalance(
  accountId: number,
  asOfDate: string,
  balance: number
): Promise<void> {
  await asJson(
    await fetch(`${API_BASE}/accounts/${accountId}/balances`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ as_of_date: asOfDate, balance }),
    })
  );
}

export async function getNetWorthSummary(): Promise<NetWorthSummary> {
  return asJson(await fetch(`${API_BASE}/net-worth/summary`));
}

export async function getStatementCoverage(): Promise<CoverageSummary> {
  return asJson(await fetch(`${API_BASE}/coverage/statements`));
}

export async function skipCoverageMonth(accountId: number, month: string): Promise<void> {
  await asJson(
    await fetch(`${API_BASE}/coverage/skip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account_id: accountId, month }),
    })
  );
}

export async function unskipCoverageMonth(accountId: number, month: string): Promise<void> {
  await asJson(
    await fetch(
      `${API_BASE}/coverage/skip?account_id=${accountId}&month=${encodeURIComponent(month)}`,
      { method: "DELETE" }
    )
  );
}

export async function previewStatement(
  file: File,
  statementYear: number,
  accountId?: number | null
): Promise<StatementPreview> {
  const form = new FormData();
  form.append("file", file);
  form.append("statement_year", String(statementYear));
  if (accountId) form.append("account_id", String(accountId));
  return asJson(
    await fetch(`${API_BASE}/statements/preview`, {
      method: "POST",
      body: form,
    })
  );
}

export type ConfirmResult =
  | { status: "ok"; imported: number; skipped_duplicates: number }
  | { status: "duplicates"; duplicates: number; total: number };

export async function confirmStatement(
  accountId: number,
  periodLabel: string,
  transactions: ParsedTransaction[],
  onDuplicate: "block" | "skip" | "import" = "block",
  amountSignFlipped?: boolean | null
): Promise<ConfirmResult> {
  const res = await fetch(`${API_BASE}/statements/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      account_id: accountId,
      period_label: periodLabel,
      transactions,
      on_duplicate: onDuplicate,
      amount_sign_flipped: amountSignFlipped ?? null,
    }),
  });
  if (res.status === 409) {
    const body = await res.json();
    return {
      status: "duplicates",
      duplicates: body.detail.duplicates,
      total: body.detail.total,
    };
  }
  const body = await asJson<{ imported: number; skipped_duplicates: number }>(res);
  return { status: "ok", ...body };
}

export type ResetAllResult = {
  deleted_transactions: number;
  deleted_statements: number;
  deleted_coverage_skips: number;
  accounts_reset: number;
};

export async function resetAllTransactions(): Promise<ResetAllResult> {
  return asJson(
    await fetch(`${API_BASE}/statements/reset-all`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    })
  );
}

export type StatementSummary = {
  id: number;
  account_id: number;
  account_name: string;
  period_label: string;
  imported_at: string;
  transaction_count: number;
};

export async function listStatements(accountId?: number): Promise<StatementSummary[]> {
  const qs = accountId ? `?account_id=${accountId}` : "";
  return asJson(await fetch(`${API_BASE}/statements${qs}`));
}

export type StatementDeleteResult = {
  deleted_transactions: number;
};

export async function deleteStatement(statementId: number): Promise<StatementDeleteResult> {
  return asJson(
    await fetch(`${API_BASE}/statements/${statementId}`, { method: "DELETE" })
  );
}

export async function getDashboardSummary(month?: string): Promise<DashboardSummary> {
  const qs = month ? `?month=${month}` : "";
  return asJson(await fetch(`${API_BASE}/dashboard/summary${qs}`));
}

export async function getSpendingControl(month?: string): Promise<SpendingControl> {
  const qs = month ? `?month=${month}` : "";
  return asJson(await fetch(`${API_BASE}/dashboard/spending-control${qs}`));
}

export async function listRules(): Promise<Rule[]> {
  return asJson(await fetch(`${API_BASE}/rules`));
}

export async function createRule(payload: RuleInput): Promise<Rule> {
  return asJson(
    await fetch(`${API_BASE}/rules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

export async function updateRule(ruleId: number, payload: RuleInput): Promise<Rule> {
  return asJson(
    await fetch(`${API_BASE}/rules/${ruleId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

export async function deleteRule(ruleId: number): Promise<void> {
  await asJson(await fetch(`${API_BASE}/rules/${ruleId}`, { method: "DELETE" }));
}

export async function applyRules(
  scope: RuleScope,
  dryRun: boolean
): Promise<RuleApplyResult> {
  return asJson(
    await fetch(`${API_BASE}/rules/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope, dry_run: dryRun }),
    })
  );
}

export async function getCategoryDetail(
  category: string,
  month: string
): Promise<CategoryDetail> {
  const qs = `?category=${encodeURIComponent(category)}&month=${month}`;
  return asJson(await fetch(`${API_BASE}/dashboard/category-detail${qs}`));
}

export async function setCategoryAppearance(
  categoryId: number,
  color: string,
  emoji: string
): Promise<Category> {
  return asJson(
    await fetch(`${API_BASE}/categories/${categoryId}/appearance`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ color, emoji }),
    })
  );
}

export async function getUpcoming(horizonDays?: number): Promise<UpcomingSummary> {
  const qs = horizonDays ? `?horizon_days=${horizonDays}` : "";
  return asJson(await fetch(`${API_BASE}/dashboard/upcoming${qs}`));
}

export type SankeyNodeKind = "income" | "hub" | "group" | "category" | "savings";

export type SankeyNode = {
  name: string;
  color: string;
  kind: SankeyNodeKind;
};

export type SankeyLinkData = {
  source: number;
  target: number;
  value: number;
};


export type SankeySummary = {
  month: string;
  total_income: number;
  total_spending: number;
  net_cash_flow: number;
  nodes: SankeyNode[];
  links: SankeyLinkData[];
  shortfall: number | null;
};

export async function getSankey(month?: string): Promise<SankeySummary> {
  const qs = month ? `?month=${month}` : "";
  return asJson(await fetch(`${API_BASE}/dashboard/sankey${qs}`));
}

export type SignIssueDirection = "income_positive" | "expense_negative";

export type SignIssue = {
  id: number;
  trans_date: string;
  description: string;
  amount: number;
  category: string;
  account_name: string;
  direction: SignIssueDirection;
};

export type SignIssueFixResult = {
  fixed: number;
  already_ok: number;
};

export async function listSignIssues(): Promise<SignIssue[]> {
  return asJson(await fetch(`${API_BASE}/transactions/sign-issues`));
}

export async function fixSignIssues(
  transactionIds: number[]
): Promise<SignIssueFixResult> {
  return asJson(
    await fetch(`${API_BASE}/transactions/sign-issues/fix`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_ids: transactionIds }),
    })
  );
}

export type DuplicateTransactionCopy = {
  id: number;
  account_name: string;
};

export type DuplicateGroup = {
  trans_date: string;
  description: string;
  amount: number;
  category: string | null;
  copies: DuplicateTransactionCopy[];
};

export type DuplicateFixResult = {
  deleted: number;
};

export async function listDuplicateTransactions(): Promise<DuplicateGroup[]> {
  return asJson(await fetch(`${API_BASE}/transactions/duplicates`));
}

export async function fixDuplicateTransactions(
  transactionIds: number[]
): Promise<DuplicateFixResult> {
  return asJson(
    await fetch(`${API_BASE}/transactions/duplicates/fix`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_ids: transactionIds }),
    })
  );
}

export async function updateCategoryClassification(
  categoryId: number,
  costType: CostType,
  controllability: Controllability
): Promise<Category> {
  return asJson(
    await fetch(`${API_BASE}/categories/${categoryId}/classification`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cost_type: costType, controllability }),
    })
  );
}

export async function getCreditCardSummaries(month?: string): Promise<CreditCardSummary[]> {
  const qs = month ? `?month=${month}` : "";
  return asJson(await fetch(`${API_BASE}/dashboard/credit-cards${qs}`));
}

export async function listCategories(): Promise<Category[]> {
  return asJson(await fetch(`${API_BASE}/categories`));
}

export async function createCategory(
  name: string,
  kind: CategoryKind = "expense",
  groupName = ""
): Promise<Category> {
  return asJson(
    await fetch(`${API_BASE}/categories`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, kind, group_name: groupName }),
    })
  );
}

export async function updateCategoryKeywords(
  categoryId: number,
  keywords: string[]
): Promise<Category> {
  return asJson(
    await fetch(`${API_BASE}/categories/${categoryId}/keywords`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keywords }),
    })
  );
}

export async function deleteCategory(categoryId: number): Promise<void> {
  await asJson(
    await fetch(`${API_BASE}/categories/${categoryId}`, { method: "DELETE" })
  );
}

export async function updateCategoryBudget(
  categoryId: number,
  monthlyBudget: number | null
): Promise<Category> {
  return asJson(
    await fetch(`${API_BASE}/categories/${categoryId}/budget`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ monthly_budget: monthlyBudget }),
    })
  );
}

export async function getHealthScore(): Promise<HealthScore> {
  return asJson(await fetch(`${API_BASE}/health-score`));
}

export async function listTransactions(
  month?: string,
  tag?: string,
  kind?: TransactionKind
): Promise<Transaction[]> {
  const params = new URLSearchParams();
  if (month) params.set("month", month);
  if (tag) params.set("tag", tag);
  if (kind) params.set("kind", kind);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return asJson(await fetch(`${API_BASE}/transactions${qs}`));
}

export async function listTags(): Promise<Tag[]> {
  return asJson(await fetch(`${API_BASE}/tags`));
}

export async function deleteTag(tagId: number): Promise<void> {
  await asJson(await fetch(`${API_BASE}/tags/${tagId}`, { method: "DELETE" }));
}

export async function setTransactionTags(
  transactionId: number,
  tags: string[]
): Promise<Transaction> {
  return asJson(
    await fetch(`${API_BASE}/transactions/${transactionId}/tags`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags }),
    })
  );
}

export async function previewPayStub(file: File): Promise<PayStubDraft> {
  const form = new FormData();
  form.append("file", file);
  return asJson(
    await fetch(`${API_BASE}/payroll/preview`, { method: "POST", body: form })
  );
}

export async function listPayStubs(year?: number): Promise<PayStub[]> {
  const qs = year ? `?year=${year}` : "";
  return asJson(await fetch(`${API_BASE}/payroll/stubs${qs}`));
}

export async function createPayStub(payload: PayStubFields): Promise<PayStub> {
  return asJson(
    await fetch(`${API_BASE}/payroll/stubs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

export async function deletePayStub(stubId: number): Promise<void> {
  await asJson(
    await fetch(`${API_BASE}/payroll/stubs/${stubId}`, { method: "DELETE" })
  );
}

export async function getPayrollSummary(
  year?: number,
  carryForward = 0
): Promise<PayrollSummary> {
  const params = new URLSearchParams();
  if (year) params.set("year", String(year));
  if (carryForward) params.set("carry_forward", String(carryForward));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return asJson(await fetch(`${API_BASE}/payroll/summary${qs}`));
}

export async function listTaxBrackets(year?: number): Promise<TaxBracket[]> {
  const qs = year ? `?year=${year}` : "";
  return asJson(await fetch(`${API_BASE}/payroll/tax-brackets${qs}`));
}

export async function replaceTaxBrackets(
  taxYear: number,
  jurisdiction: string,
  brackets: { lower_bound: number; upper_bound: number | null; rate: number }[]
): Promise<TaxBracket[]> {
  return asJson(
    await fetch(`${API_BASE}/payroll/tax-brackets`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tax_year: taxYear, jurisdiction, brackets }),
    })
  );
}

export async function getTaxSettings(year?: number): Promise<TaxSetting | null> {
  const qs = year ? `?year=${year}` : "";
  return asJson(await fetch(`${API_BASE}/payroll/tax-settings${qs}`));
}

export async function deleteTransaction(transactionId: number): Promise<void> {
  await asJson(
    await fetch(`${API_BASE}/transactions/${transactionId}`, { method: "DELETE" })
  );
}

export async function setTransactionCategory(
  transactionId: number,
  categoryName: string
): Promise<void> {
  await asJson(
    await fetch(
      `${API_BASE}/transactions/${transactionId}/category?category_name=${encodeURIComponent(
        categoryName
      )}`,
      { method: "PATCH" }
    )
  );
}
