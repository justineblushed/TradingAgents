"use client";

import { useEffect, useState } from "react";
import {
  Account,
  Category,
  ParsedTransaction,
  confirmStatement,
  createAccount,
  listAccounts,
  listCategories,
  previewStatement,
} from "@/lib/api";
import { formatSignedCurrency } from "@/lib/format";

export default function UploadPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [newAccountName, setNewAccountName] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [statementYear, setStatementYear] = useState(new Date().getFullYear());
  const [periodLabel, setPeriodLabel] = useState("");
  const [transactions, setTransactions] = useState<ParsedTransaction[] | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [phase, setPhase] = useState<"idle" | "parsing" | "importing">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [duplicateInfo, setDuplicateInfo] = useState<{
    duplicates: number;
    total: number;
  } | null>(null);
  const [showAddAccount, setShowAddAccount] = useState(false);
  const busy = phase !== "idle";
  // With zero accounts there's nothing to pick from, so skip the dropdown
  // entirely and go straight to the add-account form instead of showing it
  // empty and making the user find a toggle to reveal the only usable path.
  const addAccountVisible = accounts.length === 0 || showAddAccount;

  useEffect(() => {
    listAccounts()
      .then((accts) => {
        setAccounts(accts);
        if (accts.length > 0) setAccountId(accts[0].id);
      })
      .catch((err) =>
        setMessage(err instanceof Error ? err.message : "Failed to load accounts")
      );
    listCategories()
      .then(setCategories)
      .catch((err) =>
        setMessage(err instanceof Error ? err.message : "Failed to load categories")
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
      setShowAddAccount(false);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to create account");
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Reset the input so picking the same file again still fires onChange
    // (browsers suppress it when the value hasn't changed — without this,
    // re-uploading the same statement after an import does nothing).
    e.target.value = "";
    if (!file) return;
    setPhase("parsing");
    setMessage(null);
    setDuplicateInfo(null);
    try {
      const preview = await previewStatement(file, statementYear);
      setTransactions(preview.transactions);
      setWarnings(preview.warnings);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to parse statement");
    } finally {
      setPhase("idle");
    }
  }

  function updateCategory(index: number, category: string) {
    setTransactions((prev) =>
      prev
        ? prev.map((t, i) => (i === index ? { ...t, suggested_category: category } : t))
        : prev
    );
  }

  async function handleConfirm(onDuplicate: "block" | "skip" | "import" = "block") {
    if (!accountId || !transactions) return;
    setPhase("importing");
    setMessage(null);
    if (onDuplicate !== "block") setDuplicateInfo(null);
    try {
      const result = await confirmStatement(
        accountId,
        periodLabel,
        transactions,
        onDuplicate
      );
      if (result.status === "duplicates") {
        setDuplicateInfo({ duplicates: result.duplicates, total: result.total });
      } else {
        setDuplicateInfo(null);
        setMessage(
          result.skipped_duplicates > 0
            ? `Imported ${result.imported} new transactions (skipped ${result.skipped_duplicates} duplicates).`
            : `Imported ${result.imported} transactions.`
        );
        setTransactions(null);
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to import");
    } finally {
      setPhase("idle");
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-medium text-slate-600">1. Account</h2>

        {accounts.length > 0 && (
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-xs text-slate-500">
                Which account is this statement for?
              </label>
              <select
                value={accountId ?? ""}
                onChange={(e) => setAccountId(Number(e.target.value))}
                className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
            {!addAccountVisible && (
              <button
                onClick={() => setShowAddAccount(true)}
                className="text-sm font-medium text-brand-600 hover:text-brand-700"
              >
                + Add a new account
              </button>
            )}
          </div>
        )}

        {addAccountVisible && (
          <div className={accounts.length > 0 ? "mt-4 border-t border-slate-100 pt-4" : ""}>
            <label className="block text-xs text-slate-500">
              {accounts.length === 0
                ? "You don't have any accounts yet — add your first one:"
                : "New account name"}
            </label>
            <div className="mt-1 flex items-center gap-2">
              <input
                placeholder="e.g. Rogers Mastercard"
                value={newAccountName}
                onChange={(e) => setNewAccountName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateAccount()}
                className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                autoFocus={accounts.length === 0}
              />
              <button
                onClick={handleCreateAccount}
                disabled={!newAccountName.trim()}
                className="rounded-md bg-brand-500 px-3 py-1 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                Add
              </button>
              {accounts.length > 0 && (
                <button
                  onClick={() => {
                    setShowAddAccount(false);
                    setNewAccountName("");
                  }}
                  className="text-sm text-slate-400 hover:text-slate-600"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-medium text-slate-600">2. Statement file</h2>

        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs text-slate-500" title="PDF only — CSV files carry their own dates">
              Statement year (PDF only)
            </label>
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
            Choose PDF or CSV
            <input
              type="file"
              accept="application/pdf,.pdf,text/csv,.csv"
              onChange={handleFileChange}
              className="hidden"
              disabled={!accountId || busy}
            />
          </label>
        </div>
        {!accountId && (
          <p className="mt-2 text-xs font-medium text-amber-700">
            Choose or add an account above first — the file picker stays
            disabled until one is selected.
          </p>
        )}
        {phase === "parsing" && (
          <p className="mt-2 flex items-center gap-2 text-xs font-medium text-brand-700">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-brand-300 border-t-brand-700" />
            Parsing statement…
          </p>
        )}
        <p className="mt-3 text-xs text-slate-400">
          Files are parsed locally by your own backend and never saved to disk —
          only the transactions you confirm below get stored. CSVs need a date
          column, a description/details column, and either an amount column or
          funds out / funds in columns; a category column is used for
          suggestions when present.
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
                      {formatSignedCurrency(t.amount)}
                    </td>
                    <td>
                      <select
                        value={t.suggested_category ?? ""}
                        onChange={(e) => updateCategory(i, e.target.value)}
                        className={`rounded-md border px-1 py-0.5 text-xs ${
                          t.suggested_category
                            ? "border-slate-300"
                            : "border-amber-300 bg-amber-50"
                        }`}
                      >
                        {!t.suggested_category && (
                          <option value="">Uncategorized</option>
                        )}
                        {categories.map((c) => (
                          <option key={c.id} value={c.name}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {duplicateInfo ? (
            <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              <p className="font-medium">
                {duplicateInfo.duplicates} of {duplicateInfo.total} transactions
                already exist for this account (same date, description, and
                amount) — this looks like a re-uploaded statement.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() => handleConfirm("skip")}
                  disabled={busy}
                  className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
                >
                  Skip duplicates, import the rest
                </button>
                <button
                  onClick={() => handleConfirm("import")}
                  disabled={busy}
                  className="rounded-md border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50"
                >
                  Import anyway (keep duplicates)
                </button>
                <button
                  onClick={() => setDuplicateInfo(null)}
                  disabled={busy}
                  className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => handleConfirm()}
              disabled={busy}
              className="mt-4 rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
            >
              Confirm &amp; Import
            </button>
          )}
        </div>
      )}
    </div>
  );
}
