"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  DuplicateGroup,
  fixDuplicateTransactions,
  listDuplicateTransactions,
} from "@/lib/api";
import { formatSignedCurrency } from "@/lib/format";

export default function DuplicatesPage() {
  const [groups, setGroups] = useState<DuplicateGroup[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const rows = await listDuplicateTransactions();
      setGroups(rows);
      // Pre-select every copy except the first (lowest id, i.e. whichever
      // was imported first) in each group — a sensible default of "keep
      // one, remove the rest" that the user can still adjust before fixing.
      const toDelete = new Set<number>();
      rows.forEach((g) => g.transaction_ids.slice(1).forEach((id) => toDelete.add(id)));
      setSelected(toDelete);
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
      const result = await fixDuplicateTransactions(ids);
      setMessage(
        result.deleted > 0
          ? `Removed ${result.deleted} duplicate transaction${result.deleted === 1 ? "" : "s"}.`
          : "Nothing removed — those rows were already gone."
      );
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove");
    } finally {
      setBusy(false);
    }
  }

  const totalExtraCopies = groups?.reduce((sum, g) => sum + g.transaction_ids.length - 1, 0) ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-800">Duplicate Transactions</h1>
        <p className="mt-1 max-w-2xl text-xs text-slate-500">
          A duplicate here means the same account, date, description, and
          amount showing up more than once — usually a re-uploaded statement
          imported with "keep duplicates," or two files that covered an
          overlapping period. One copy of each group is kept selected as
          "keep" by default; the rest are pre-checked for removal, but check
          the description and amount first — a genuine same-day repeat
          purchase (two identical parking charges, say) looks identical from
          the data alone and isn't actually a duplicate.
        </p>
      </div>

      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {message && (
        <p className="rounded-md bg-brand-50 p-3 text-sm text-brand-700">{message}</p>
      )}

      {groups === null && !error && (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      )}

      {groups !== null && groups.length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
          No duplicate transactions found.
        </p>
      )}

      {groups !== null && groups.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-medium text-slate-600">
                {groups.length} duplicate group{groups.length === 1 ? "" : "s"} —{" "}
                {totalExtraCopies} extra cop{totalExtraCopies === 1 ? "y" : "ies"} total
              </h2>
              <p className="text-xs text-amber-700">
                Uncheck anything you want to keep before removing.
              </p>
            </div>
            <button
              onClick={() => handleFix(Array.from(selected))}
              disabled={busy || selected.size === 0}
              className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
            >
              Remove {selected.size} selected
            </button>
          </div>

          <div className="mt-4 space-y-4">
            {groups.map((group, i) => (
              <div
                key={`${group.trans_date}-${group.description}-${group.amount}-${i}`}
                className="rounded-md border border-slate-200 p-3"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium text-slate-700">{group.description}</p>
                    <p className="text-xs text-slate-400">
                      {group.trans_date} · {group.account_name}
                      {group.category ? ` · ${group.category}` : " · Uncategorized"}
                    </p>
                  </div>
                  <p className="text-sm font-semibold text-slate-800">
                    {formatSignedCurrency(group.amount)} × {group.transaction_ids.length}
                  </p>
                </div>
                <div className="mt-2 flex flex-wrap gap-4">
                  {group.transaction_ids.map((id, idx) => (
                    <div key={id} className="flex items-center gap-1.5 text-xs text-slate-600">
                      <label className="flex items-center gap-1.5">
                        <input
                          type="checkbox"
                          checked={selected.has(id)}
                          onChange={() => toggle(id)}
                        />
                        Copy {idx + 1} (id {id}){idx === 0 ? " — kept by default" : ""}
                      </label>
                      <Link
                        href={`/transactions?month=${group.trans_date.slice(0, 7)}&highlight=${id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-brand-600 underline hover:text-brand-700"
                        title="Open this transaction on the Transactions page in a new tab"
                      >
                        View →
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
