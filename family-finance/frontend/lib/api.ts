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
};

export const ASSET_ACCOUNT_TYPES = [
  "cash",
  "chequing",
  "savings",
  "investment",
  "tfsa",
  "rrsp",
  "resp",
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

export type Account = {
  id: number;
  name: string;
  institution: string;
  account_type: AccountType;
  last_four: string;
  credit_limit: number | null;
  is_liability: boolean;
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
};

export type NetWorthSummary = {
  assets_total: number;
  liabilities_total: number;
  net_worth: number;
  net_worth_prev_month: number | null;
  delta: number | null;
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
};

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
  statementYear: number
): Promise<StatementPreview> {
  const form = new FormData();
  form.append("file", file);
  form.append("statement_year", String(statementYear));
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
  onDuplicate: "block" | "skip" | "import" = "block"
): Promise<ConfirmResult> {
  const res = await fetch(`${API_BASE}/statements/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      account_id: accountId,
      period_label: periodLabel,
      transactions,
      on_duplicate: onDuplicate,
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

export async function getUpcoming(horizonDays?: number): Promise<UpcomingSummary> {
  const qs = horizonDays ? `?horizon_days=${horizonDays}` : "";
  return asJson(await fetch(`${API_BASE}/dashboard/upcoming${qs}`));
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
  tag?: string
): Promise<Transaction[]> {
  const params = new URLSearchParams();
  if (month) params.set("month", month);
  if (tag) params.set("tag", tag);
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
