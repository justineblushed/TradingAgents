"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { SignIssue, fixSignIssues, listSignIssues } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

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
      setSelected(new Set(rows.map((r) => r.id)));
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-800">Sign Check</h1>
        <p className="mt-1 max-w-2xl text-xs text-slate-500">
          This app treats a negative amount as money in and a positive one
          as money out. A transaction filed under an income category —
          Employment Income, Rental Income, and the like — should always be
          negative. One stored the other way round doesn't just look odd on
          its own: it drags the income total on the Dashboard, Cash Flow,
          and that category's drill-down toward zero or negative, since all
          three flip a category's raw total to show it as a positive
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
          No sign issues found — every income transaction is stored the way
          this app expects.
        </p>
      )}

      {issues !== null && issues.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-medium text-slate-600">
                {issues.length} transaction{issues.length === 1 ? "" : "s"} stored with
                the wrong sign
              </h2>
              <p className="text-xs text-amber-700">
                These span whichever months they were imported into —
                fixing one corrects that month's income total wherever
                it's shown (Dashboard, Cash Flow, and that category's
                drill-down).
              </p>
            </div>
            <button
              onClick={() => handleFix(Array.from(selected))}
              disabled={busy || selected.size === 0}
              className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
            >
              Fix {selected.size} selected
            </button>
          </div>

          <table className="mt-4 w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="w-8 py-1">
                  <input
                    type="checkbox"
                    checked={selected.size === issues.length}
                    onChange={(e) =>
                      setSelected(
                        e.target.checked ? new Set(issues.map((i) => i.id)) : new Set()
                      )
                    }
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
                  <td className="whitespace-nowrap pr-2 text-slate-500">
                    {issue.trans_date}
                  </td>
                  <td className="pr-2">{issue.description}</td>
                  <td className="pr-2 text-slate-500">{issue.category}</td>
                  <td className="pr-2 text-slate-500">{issue.account_name}</td>
                  <td className="pr-2 text-right text-slate-800">
                    {formatCurrency(issue.amount)}
                  </td>
                  <td className="pr-2 text-right font-medium text-green-600">
                    -{formatCurrency(issue.amount)}
                  </td>
                  <td className="text-right">
                    <button
                      onClick={() => handleFix([issue.id])}
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
      )}
    </div>
  );
}
