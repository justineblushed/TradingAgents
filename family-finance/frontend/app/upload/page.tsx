"use client";

import { useEffect, useState } from "react";
import {
  Account,
  ParsedTransaction,
  confirmStatement,
  createAccount,
  listAccounts,
  previewStatement,
} from "@/lib/api";

const CATEGORY_OPTIONS = [
  "Groceries",
  "Dining",
  "Travel & Lodging",
  "Fuel & Parking",
  "Telecom & Utilities",
  "Health",
  "Payments & Credits",
  "Interest & Fees",
  "Uncategorized",
];

export default function UploadPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [newAccountName, setNewAccountName] = useState("");
  const [statementYear, setStatementYear] = useState(new Date().getFullYear());
  const [periodLabel, setPeriodLabel] = useState("");
  const [transactions, setTransactions] = useState<ParsedTransaction[] | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    listAccounts()
      .then((accts) => {
        setAccounts(accts);
        if (accts.length > 0) setAccountId(accts[0].id);
      })
      .catch((err) =>
        setMessage(err instanceof Error ? err.message : "Failed to load accounts")
      );
  }, []);

  async function handleCreateAccount() {
    if (!newAccountName.trim()) return;
    setMessage(null);
    try {
      const account = await createAccount({
        name: newAccountName,
        account_type: "credit_card",
      });
      setAccounts((prev) => [...prev, account]);
      setAccountId(account.id);
      setNewAccountName("");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to create account");
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setMessage(null);
    try {
      const preview = await previewStatement(file, statementYear);
      setTransactions(preview.transactions);
      setWarnings(preview.warnings);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to parse statement");
    } finally {
      setBusy(false);
    }
  }

  function updateCategory(index: number, category: string) {
    setTransactions((prev) =>
      prev
        ? prev.map((t, i) => (i === index ? { ...t, suggested_category: category } : t))
        : prev
    );
  }

  async function handleConfirm() {
    if (!accountId || !transactions) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await confirmStatement(accountId, periodLabel, transactions);
      setMessage(`Imported ${result.imported} transactions.`);
      setTransactions(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to import");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-medium text-slate-600">
          1. Choose account &amp; statement PDF
        </h2>

        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs text-slate-500">Account</label>
            <select
              value={accountId ?? ""}
              onChange={(e) => setAccountId(Number(e.target.value))}
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
            >
              {accounts.length === 0 && (
                <option value="" disabled>
                  No accounts yet — add one below
                </option>
              )}
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end gap-2">
            <input
              placeholder="New account name (e.g. Rogers Mastercard)"
              value={newAccountName}
              onChange={(e) => setNewAccountName(e.target.value)}
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            />
            <button
              onClick={handleCreateAccount}
              className="rounded-md bg-slate-100 px-3 py-1 text-sm hover:bg-slate-200"
            >
              Add
            </button>
          </div>

          <div>
            <label className="block text-xs text-slate-500">Statement year</label>
            <input
              type="number"
              value={statementYear}
              onChange={(e) => setStatementYear(Number(e.target.value))}
              className="mt-1 w-24 rounded-md border border-slate-300 px-2 py-1 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-500">Period label</label>
            <input
              placeholder="e.g. Aug 2026"
              value={periodLabel}
              onChange={(e) => setPeriodLabel(e.target.value)}
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
            />
          </div>

          <label
            className={`rounded-md px-4 py-2 text-sm font-medium text-white ${
              !accountId || busy
                ? "cursor-not-allowed bg-slate-300"
                : "cursor-pointer bg-brand-500 hover:bg-brand-600"
            }`}
          >
            Choose PDF
            <input
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              className="hidden"
              disabled={!accountId || busy}
            />
          </label>
        </div>
        {!accountId && (
          <p className="mt-2 text-xs font-medium text-amber-700">
            Add an account above first — "Choose PDF" stays disabled until one is
            selected.
          </p>
        )}
        <p className="mt-3 text-xs text-slate-400">
          The PDF is parsed locally by your own backend and never saved to disk —
          only the transactions you confirm below get stored.
        </p>
      </div>

      {message && (
        <p className="rounded-md bg-brand-50 p-3 text-sm text-brand-700">{message}</p>
      )}

      {warnings.length > 0 && (
        <div className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          <p className="font-medium">Some lines were not recognized:</p>
          <ul className="mt-1 list-inside list-disc">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {transactions && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-medium text-slate-600">
            2. Review before importing ({transactions.length} transactions)
          </h2>
          <div className="max-h-[480px] overflow-auto">
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
                {transactions.map((t, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="py-1 pr-2 text-slate-500">{t.trans_date}</td>
                    <td className="pr-2">
                      {t.description}
                      {t.foreign_currency_note && (
                        <span className="ml-2 text-xs text-slate-400">
                          ({t.foreign_currency_note})
                        </span>
                      )}
                    </td>
                    <td
                      className={`pr-2 text-right ${
                        t.amount < 0 ? "text-green-600" : "text-slate-800"
                      }`}
                    >
                      ${t.amount.toFixed(2)}
                    </td>
                    <td>
                      <select
                        value={t.suggested_category ?? "Uncategorized"}
                        onChange={(e) => updateCategory(i, e.target.value)}
                        className="rounded-md border border-slate-300 px-1 py-0.5 text-xs"
                      >
                        {CATEGORY_OPTIONS.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button
            onClick={handleConfirm}
            disabled={busy}
            className="mt-4 rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
          >
            Confirm &amp; Import
          </button>
        </div>
      )}
    </div>
  );
}
