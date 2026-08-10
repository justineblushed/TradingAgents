"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CoverageSummary, getStatementCoverage } from "@/lib/api";

function monthLabel(month: string): string {
  const [year, mon] = month.split("-").map(Number);
  return new Date(year, mon - 1, 1).toLocaleDateString("en-CA", {
    month: "short",
    year: "numeric",
  });
}

type SortOrder = "newest" | "oldest";

export default function StatementLogPage() {
  const [coverage, setCoverage] = useState<CoverageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");

  useEffect(() => {
    getStatementCoverage()
      .then(setCoverage)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Statement Log</h1>
          <p className="mt-1 text-sm text-slate-500">
            A checklist of which months have statement data for each credit card,
            so you can spot gaps before they skew the numbers. A month counts as
            covered once it has at least one imported transaction.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <label className="text-slate-500">Sort</label>
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as SortOrder)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="newest">Newest month first</option>
            <option value="oldest">Oldest month first</option>
          </select>
        </div>
      </div>

      {error && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}

      {coverage === null && !error && (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      )}

      {coverage && coverage.accounts.length === 0 && (
        <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-400 shadow-sm">
          No credit card accounts yet —{" "}
          <Link href="/upload" className="font-medium text-brand-600 hover:text-brand-700">
            upload your first statement
          </Link>{" "}
          to start the log.
        </p>
      )}

      {coverage &&
        coverage.accounts.map((account) => (
          <div
            key={account.account_id}
            className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-medium text-slate-700">
                {account.account_name}
              </h2>
              {account.missing_months.length > 0 ? (
                <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                  {account.missing_months.length} month
                  {account.missing_months.length === 1 ? "" : "s"} missing
                </span>
              ) : account.months.length > 0 ? (
                <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                  All caught up
                </span>
              ) : null}
            </div>

            {account.months.length === 0 ? (
              <p className="py-4 text-center text-sm text-slate-400">
                No statements imported for this account yet.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {(sortOrder === "newest"
                  ? [...account.months].reverse()
                  : account.months
                ).map((m) => (
                  <div
                    key={m.month}
                    title={
                      m.covered
                        ? `${m.transaction_count} transaction${m.transaction_count === 1 ? "" : "s"}`
                        : "No statement uploaded for this month"
                    }
                    className={`rounded-md border px-2.5 py-1.5 text-xs font-medium ${
                      m.covered
                        ? "border-green-200 bg-green-50 text-green-800"
                        : "border-red-200 bg-red-50 text-red-700"
                    }`}
                  >
                    {m.covered ? "✓" : "✗"} {monthLabel(m.month)}
                    {m.covered && (
                      <span className="ml-1 text-green-600/70">
                        ({m.transaction_count})
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {account.missing_months.length > 0 && (
              <p className="mt-3 text-xs text-slate-500">
                Missing:{" "}
                {(sortOrder === "newest"
                  ? [...account.missing_months].reverse()
                  : account.missing_months
                )
                  .map(monthLabel)
                  .join(", ")}{" "}
                —{" "}
                <Link
                  href="/upload"
                  className="font-medium text-brand-600 hover:text-brand-700"
                >
                  upload now
                </Link>
              </p>
            )}
          </div>
        ))}
    </div>
  );
}
