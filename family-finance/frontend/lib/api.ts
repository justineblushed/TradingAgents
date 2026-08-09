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

export type Account = {
  id: number;
  name: string;
  institution: string;
  account_type: string;
  last_four: string;
};

export type DashboardSummary = {
  month: string;
  total_charges: number;
  total_credits: number;
  net_change: number;
  by_category: Record<string, number>;
};

export type Category = {
  id: number;
  name: string;
  is_income: boolean;
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

export async function createAccount(payload: Partial<Account>): Promise<Account> {
  return asJson(
    await fetch(`${API_BASE}/accounts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
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

export async function listCategories(): Promise<Category[]> {
  return asJson(await fetch(`${API_BASE}/categories`));
}

export async function createCategory(
  name: string,
  isIncome = false
): Promise<Category> {
  return asJson(
    await fetch(`${API_BASE}/categories`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, is_income: isIncome }),
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
