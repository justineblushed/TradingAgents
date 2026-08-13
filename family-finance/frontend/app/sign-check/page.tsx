"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { SignIssue, fixSignIssues, listSignIssues } from "@/lib/api";
import { formatSignedCurrency } from "@/lib/format";

export default function SignCheckPage() {
  const [issues, setIssues] = useState<SignIssue[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const rows = await listSignIssues();
      setIssues(rows);
      // Income-positive has no legitimate exception, so it's pre-selected
      // for a one-click fix. Expense-negative can be a genuine refund, so
      // it's left for the user to review and check by hand.
      setSelected(
        new Set(rows.filter((r) => r.direction === "income_positive").map((r) => r.id))
      );
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleFix(ids: number[]) {
    if (ids.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const result = await fixSignIssues(ids);
      setMessage(
        result.fixed > 0
          ? `Fixed ${result.fixed} transaction${result.fixed === 1 ? "" : "s"}.${
              result.already_ok > 0
                ? ` ${result.already_ok} were already correct and left alone.`
                : ""
            }`
          : "Nothing to fix — those rows were already correct."
      );
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fix");
    } finally {
      setBusy(false);
    }
  }

  const incomeIssues = issues?.filter((i) => i.direction === "income_positive") ?? [];
  const expenseIssues = issues?.filter((i) => i.direction === "expense_negative") ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-800">Sign Check</h1>
        <p className="mt-1 max-w-2xl text-xs text-slate-500">
          This app treats a negative amount as money in and a positive one
          as money out. A transaction filed under an income category —
          Employment Income, Rental Income, and the like — should always be
          negative, and one filed under an expense category should almost
          always be positive. Either mismatch drags totals the wrong way on
          the Dashboard, Cash Flow, and that category's drill-down, since
          all three flip a category's raw total to show it as a positive
          number. This usually happens with a statement imported before the
          app started reconciling a CSV's own sign convention against its
          own — see the note on the{" "}
          <Link href="/statement-log" className="font-medium text-brand-600 hover:text-brand-700">
            Statement Log page
          </Link>
          , where statements get uploaded.
        </p>
      </div>

      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {message && (
        <p className="rounded-md bg-brand-50 p-3 text-sm text-brand-700">{message}</p>
      )}

      {issues === null && !error && (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      )}

      {issues !== null && issues.length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
          No sign issues found — every income and expense transaction is
          stored the way this app expects.
        </p>
      )}

      {incomeIssues.length > 0 && (
        <IssueSection
          title={`${incomeIssues.length} transaction${incomeIssues.length === 1 ? "" : "s"} stored with the wrong sign`}
          hint="An income row has no legitimate reason to be positive — these span whichever months they were imported into, and fixing one corrects that month's income total wherever it's shown."
          issues={incomeIssues}
          selected={selected}
          toggle={toggle}
          setSelected={setSelected}
          busy={busy}
          onFix={handleFix}
        />
      )}

      {expenseIssues.length > 0 && (
        <IssueSection
          title={`${expenseIssues.length} possible issue${expenseIssues.length === 1 ? "" : "s"} — review before fixing`}
          hint="A negative amount under an expense category is often a genuine refund netted against that category on purpose, not a bug — so none of these are pre-selected. Check the description and amount first; if it's actually a debit that landed with the wrong sign, check it and fix it."
          issues={expenseIssues}
          selected={selected}
          toggle={toggle}
          setSelected={setSelected}
          busy={busy}
          onFix={handleFix}
          tone="amber"
        />
      )}
    </div>
  );
}

function IssueSection({
  title,
  hint,
  issues,
  selected,
  toggle,
  setSelected,
  busy,
  onFix,
  tone = "default",
}: {
  title: string;
  hint: string;
  issues: SignIssue[];
  selected: Set<number>;
  toggle: (id: number) => void;
  setSelected: (updater: (prev: Set<number>) => Set<number>) => void;
  busy: boolean;
  onFix: (ids: number[]) => void;
  tone?: "default" | "amber";
}) {
  const selectedHere = issues.filter((i) => selected.has(i.id));
  const allSelected = issues.length > 0 && selectedHere.length === issues.length;

  function setGroupSelection(checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      issues.forEach((i) => (checked ? next.add(i.id) : next.delete(i.id)));
      return next;
    });
  }

  return (
    <div
      className={`rounded-xl border bg-white p-4 shadow-sm ${
        tone === "amber" ? "border-amber-300" : "border-amber-200"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-slate-600">{title}</h2>
          <p className="text-xs text-amber-700">{hint}</p>
        </div>
        <button
          onClick={() => onFix(selectedHere.map((i) => i.id))}
          disabled={busy || selectedHere.length === 0}
          className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
        >
          Fix {selectedHere.length} selected
        </button>
      </div>

      <table className="mt-4 w-full text-left text-sm">
        <thead className="text-xs uppercase text-slate-400">
          <tr>
            <th className="w-8 py-1">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={(e) => setGroupSelection(e.target.checked)}
              />
            </th>
            <th>Date</th>
            <th>Description</th>
            <th>Category</th>
            <th>Account</th>
            <th className="text-right">Stored as</th>
            <th className="text-right">Should be</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {issues.map((issue) => (
            <tr key={issue.id} className="border-t border-slate-100">
              <td className="py-1.5">
                <input
                  type="checkbox"
                  checked={selected.has(issue.id)}
                  onChange={() => toggle(issue.id)}
                />
              </td>
              <td className="whitespace-nowrap pr-2 text-slate-500">{issue.trans_date}</td>
              <td className="pr-2">{issue.description}</td>
              <td className="pr-2 text-slate-500">{issue.category}</td>
              <td className="pr-2 text-slate-500">{issue.account_name}</td>
              <td
                className={`pr-2 text-right ${
                  issue.amount < 0 ? "text-green-600" : "text-slate-800"
                }`}
              >
                {formatSignedCurrency(issue.amount)}
              </td>
              <td
                className={`pr-2 text-right font-medium ${
                  -issue.amount < 0 ? "text-green-600" : "text-slate-800"
                }`}
              >
                {formatSignedCurrency(-issue.amount)}
              </td>
              <td className="text-right">
                <button
                  onClick={() => onFix([issue.id])}
                  disabled={busy}
                  className="text-xs font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50"
                >
                  Fix this one
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
