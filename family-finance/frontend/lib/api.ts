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
