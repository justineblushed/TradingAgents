"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AccountCoverage,
  CoverageSummary,
  MonthCoverage,
  getStatementCoverage,
  skipCoverageMonth,
  unskipCoverageMonth,
} from "@/lib/api";

// After this many days without a new statement import, an account is
// highlighted as probably due for one (monthly statements + buffer).
const STALE_AFTER_DAYS = 35;

function monthLabel(month: string): string {
  const [year, mon] = month.split("-").map(Number);
  return new Date(year, mon - 1, 1).toLocaleDateString("en-CA", {
    month: "short",
    year: "numeric",
  });
}

function daysAgoLabel(days: number): string {
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  return `${days} days ago`;
}

type SortOrder = "newest" | "oldest";

export default function StatementLogPage() {
  const [coverage, setCoverage] = useState<CoverageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");

  function load() {
    getStatementCoverage()
      .then(setCoverage)
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Statement Log</h1>
          <p className="mt-1 text-sm text-slate-500">
            A checklist of which months have statement data for each account,
            so you can spot gaps before they skew the numbers. Click a covered
            month to see its transactions; click a missing month to mark it
            N/A (no statement exists for it).
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
          No accounts with statements yet —{" "}
          <Link href="/upload" className="font-medium text-brand-600 hover:text-brand-700">
            upload your first statement
          </Link>{" "}
          to start the log.
        </p>
      )}

      {coverage &&
        coverage.accounts.map((account) => (
          <AccountCard
            key={account.account_id}
            account={account}
            sortOrder={sortOrder}
            onChanged={load}
          />
        ))}
    </div>
  );
}

function AccountCard({
  account,
  sortOrder,
  onChanged,
}: {
  account: AccountCoverage;
  sortOrder: SortOrder;
  onChanged: () => void;
}) {
  const stale =
    account.days_since_last_import !== null &&
    account.days_since_last_import > STALE_AFTER_DAYS;

  const months =
    sortOrder === "newest" ? [...account.months].reverse() : account.months;
  const missing =
    sortOrder === "newest"
      ? [...account.missing_months].reverse()
      : account.missing_months;

  return (
    <div
      className={`rounded-xl border bg-white p-4 shadow-sm ${
        stale ? "border-amber-300" : "border-slate-200"
      }`}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-medium text-slate-700">
            {account.account_name}
          </h2>
          <p className={`text-xs ${stale ? "font-medium text-amber-700" : "text-slate-400"}`}>
            {account.days_since_last_import === null
              ? "No statements imported yet"
              : `Last upload: ${daysAgoLabel(account.days_since_last_import)}`}
            {stale && " — probably due for a new statement"}
          </p>
        </div>
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
          {months.map((m) => (
            <MonthChip
              key={m.month}
              accountId={account.account_id}
              month={m}
              onChanged={onChanged}
            />
          ))}
        </div>
      )}

      {account.missing_months.length > 0 && (
        <p className="mt-3 text-xs text-slate-500">
          Missing: {missing.map(monthLabel).join(", ")} —{" "}
          <Link
            href="/upload"
            className="font-medium text-brand-600 hover:text-brand-700"
          >
            upload now
          </Link>
        </p>
      )}
    </div>
  );
}

function MonthChip({
  accountId,
  month,
  onChanged,
}: {
  accountId: number;
  month: MonthCoverage;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);

  async function toggleSkip() {
    const label = monthLabel(month.month);
    const confirmed = month.skipped
      ? window.confirm(`Un-mark ${label} as N/A? It will count as missing again.`)
      : window.confirm(
          `Mark ${label} as N/A (no statement exists for this month)? It will stop counting as missing.`
        );
    if (!confirmed) return;
    setBusy(true);
    try {
      if (month.skipped) {
        await unskipCoverageMonth(accountId, month.month);
      } else {
        await skipCoverageMonth(accountId, month.month);
      }
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  if (month.covered) {
    return (
      <Link
        href={`/transactions?month=${month.month}`}
        title={`${month.transaction_count} transaction${month.transaction_count === 1 ? "" : "s"} — click to view`}
        className="rounded-md border border-green-200 bg-green-50 px-2.5 py-1.5 text-xs font-medium text-green-800 hover:border-green-400 hover:bg-green-100"
      >
        ✓ {monthLabel(month.month)}
        <span className="ml-1 text-green-600/70">({month.transaction_count})</span>
      </Link>
    );
  }

  if (month.skipped) {
    return (
      <button
        onClick={toggleSkip}
        disabled={busy}
        title="Marked N/A (no statement exists) — click to undo"
        className="rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 text-xs font-medium text-slate-500 hover:border-slate-400 disabled:opacity-50"
      >
        – {monthLabel(month.month)} <span className="text-slate-400">N/A</span>
      </button>
    );
  }

  return (
    <button
      onClick={toggleSkip}
      disabled={busy}
      title="No statement uploaded — click to mark N/A if none exists"
      className="rounded-md border border-red-200 bg-red-50 px-2.5 py-1.5 text-xs font-medium text-red-700 hover:border-red-400 hover:bg-red-100 disabled:opacity-50"
    >
      ✗ {monthLabel(month.month)}
    </button>
  );
}
