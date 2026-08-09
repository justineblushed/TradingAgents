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

export type CategoryKind = "expense" | "income" | "transfer";

export type Category = {
  id: number;
  name: string;
  kind: CategoryKind;
  keywords: string[];
};

export type Transaction = {
  id: number;
  trans_date: string;
  post_date: string | null;
  description: string;
  amount: number;
  category: string | null;
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

export async function confirmStatement(
  accountId: number,
  periodLabel: string,
  transactions: ParsedTransaction[]
): Promise<{ statement_id: number; imported: number }> {
  return asJson(
    await fetch(`${API_BASE}/statements/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: accountId,
        period_label: periodLabel,
        transactions,
      }),
    })
  );
}

export async function getDashboardSummary(month?: string): Promise<DashboardSummary> {
  const qs = month ? `?month=${month}` : "";
  return asJson(await fetch(`${API_BASE}/dashboard/summary${qs}`));
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
  kind: CategoryKind = "expense"
): Promise<Category> {
  return asJson(
    await fetch(`${API_BASE}/categories`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, kind }),
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

export async function listTransactions(month?: string): Promise<Transaction[]> {
  const qs = month ? `?month=${month}` : "";
  return asJson(await fetch(`${API_BASE}/transactions${qs}`));
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
