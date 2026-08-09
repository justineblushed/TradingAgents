"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Category,
  Transaction,
  listCategories,
  listTransactions,
  setTransactionCategory,
} from "@/lib/api";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function TransactionsPage() {
  const [month, setMonth] = useState(currentMonth());
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    setTransactions(null);
    listTransactions(month)
      .then(setTransactions)
      .catch((e) => setError(e.message));
  }, [month]);

  const uncategorizedCount = useMemo(
    () => (transactions ?? []).filter((t) => !t.category).length,
    [transactions]
  );

  async function handleCategoryChange(transactionId: number, categoryName: string) {
    if (!transactions) return;
    const previous = transactions;
    // Optimistic update so the dropdown feels instant; rolled back on failure.
    setTransactions(
      transactions.map((t) =>
        t.id === transactionId ? { ...t, category: categoryName } : t
      )
    );
    setSavingId(transactionId);
    setError(null);
    try {
      await setTransactionCategory(transactionId, categoryName);
    } catch (err) {
      setTransactions(previous);
      setError(
        err instanceof Error ? err.message : "Failed to save category change"
      );
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-slate-600">Month</label>
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
        {transactions && transactions.length > 0 && (
          <p className="text-sm text-slate-500">
            {transactions.length} transaction{transactions.length === 1 ? "" : "s"}
            {uncategorizedCount > 0 && (
              <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                {uncategorizedCount} uncategorized
              </span>
            )}
          </p>
        )}
      </div>

      {error && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        {transactions === null ? (
          <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
        ) : transactions.length === 0 ? (
          <p className="py-16 text-center text-sm text-slate-400">
            No transactions for this month — upload a statement to get started.
          </p>
        ) : (
          <div className="max-h-[600px] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-white text-xs uppercase text-slate-400">
                <tr>
                  <th className="py-1">Date</th>
                  <th>Description</th>
                  <th className="text-right">Amount</th>
                  <th>Category</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr key={t.id} className="border-t border-slate-100">
                    <td className="py-1.5 pr-2 text-slate-500">{t.trans_date}</td>
                    <td className="pr-2">{t.description}</td>
                    <td
                      className={`pr-2 text-right ${
                        t.amount < 0 ? "text-green-600" : "text-slate-800"
                      }`}
                    >
                      ${t.amount.toFixed(2)}
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <select
                          value={t.category ?? ""}
                          onChange={(e) => handleCategoryChange(t.id, e.target.value)}
                          className={`rounded-md border px-1 py-0.5 text-xs ${
                            t.category
                              ? "border-slate-300"
                              : "border-amber-300 bg-amber-50"
                          }`}
                        >
                          {!t.category && <option value="">Uncategorized</option>}
                          {categories.map((c) => (
                            <option key={c.id} value={c.name}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                        {savingId === t.id && (
                          <span className="text-xs text-slate-400">Saving…</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
