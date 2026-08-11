"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { CategoryDetail, getCategoryDetail } from "@/lib/api";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function shiftMonth(month: string, delta: number): string {
  const [year, mon] = month.split("-").map(Number);
  const index = year * 12 + (mon - 1) + delta;
  return `${String(Math.floor(index / 12)).padStart(4, "0")}-${String(
    (index % 12) + 1
  ).padStart(2, "0")}`;
}

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function monthLabel(month: string): string {
  const [year, mon] = month.split("-").map(Number);
  return `${MONTH_NAMES[mon - 1]} ${year}`;
}

export default function CategoryDetailPage() {
  return (
    <Suspense
      fallback={<p className="py-16 text-center text-sm text-slate-400">Loading…</p>}
    >
      <CategoryDetailInner />
    </Suspense>
  );
}

function CategoryDetailInner() {
  const params = useParams<{ name: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const name = decodeURIComponent(params.name);

  const monthParam = searchParams.get("month");
  const month = /^\d{4}-\d{2}$/.test(monthParam ?? "")
    ? (monthParam as string)
    : currentMonth();

  const [detail, setDetail] = useState<CategoryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDetail(null);
    setError(null);
    getCategoryDetail(name, month)
      .then(setDetail)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [name, month]);

  function goToMonth(next: string) {
    router.replace(
      `/categories/${encodeURIComponent(name)}?month=${next}`,
      { scroll: false }
    );
  }

  const peak = Math.max(1, ...(detail?.history ?? []).map((p) => Math.abs(p.total)));
  const isIncome = detail?.kind === "income";
  const accent = detail?.color || "#64748b";

  return (
    <div className="space-y-6">
      <Link
        href="/"
        className="inline-block text-sm text-slate-500 hover:text-slate-700"
      >
        ← Back to dashboard
      </Link>

      {error && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}
      {!detail && !error && (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      )}

      {detail && (
        <>
          {/* Header + month stepper */}
          <div
            className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
            style={{ borderTopColor: accent, borderTopWidth: 3 }}
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span
                  className="flex h-11 w-11 items-center justify-center rounded-lg text-xl"
                  style={{ backgroundColor: `${accent}1a` }}
                  aria-hidden
                >
                  {detail.emoji || "•"}
                </span>
                <div>
                  <h1 className="text-lg font-semibold text-slate-800">
                    {detail.category}
                  </h1>
                  <p className="text-xs text-slate-400">
                    {detail.group_name || "Ungrouped"} · {detail.kind}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1">
                <button
                  onClick={() => goToMonth(shiftMonth(month, -1))}
                  aria-label="Previous month"
                  className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
                >
                  ←
                </button>
                <input
                  type="month"
                  value={month}
                  onChange={(e) => e.target.value && goToMonth(e.target.value)}
                  className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                />
                <button
                  onClick={() => goToMonth(shiftMonth(month, 1))}
                  aria-label="Next month"
                  className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
                >
                  →
                </button>
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div>
                <p className="text-xs text-slate-500">
                  {isIncome ? "Received" : "Spent"} in {monthLabel(month)}
                </p>
                <p className="text-2xl font-bold" style={{ color: accent }}>
                  {formatCurrency(detail.total)}
                </p>
                <p className="text-xs text-slate-400">
                  {detail.transaction_count} transaction
                  {detail.transaction_count === 1 ? "" : "s"}
                </p>
              </div>

              <div>
                <p className="text-xs text-slate-500">
                  Typical month{" "}
                  <span className="text-slate-400">(last 12, excluding this one)</span>
                </p>
                {detail.average_of_history !== null ? (
                  <>
                    <p className="text-2xl font-bold text-slate-700">
                      {formatCurrency(detail.average_of_history)}
                    </p>
                    <p
                      className={`text-xs ${
                        detail.total > detail.average_of_history
                          ? "text-amber-700"
                          : "text-green-700"
                      }`}
                    >
                      {detail.total >= detail.average_of_history ? "↑ " : "↓ "}
                      {formatCurrency(
                        Math.abs(detail.total - detail.average_of_history)
                      )}{" "}
                      vs typical
                    </p>
                  </>
                ) : (
                  <p className="mt-1 text-sm text-slate-400">
                    No other month has activity here yet.
                  </p>
                )}
              </div>

              <div>
                <p className="text-xs text-slate-500">Monthly budget</p>
                {detail.monthly_budget !== null ? (
                  <>
                    <p className="text-2xl font-bold text-slate-700">
                      {formatCurrency(detail.monthly_budget)}
                    </p>
                    <p
                      className={`text-xs ${
                        detail.over_budget ? "text-red-700" : "text-green-700"
                      }`}
                    >
                      {detail.over_budget
                        ? `${formatCurrency(detail.over_budget)} over`
                        : `${formatCurrency(
                            detail.monthly_budget - detail.total
                          )} left`}
                    </p>
                  </>
                ) : (
                  <p className="mt-1 text-sm text-slate-400">
                    None set —{" "}
                    <Link
                      href="/categories"
                      className="font-medium text-brand-600 hover:text-brand-700"
                    >
                      add one
                    </Link>
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* 12-month trend — the reason to drill in is to see whether this
              month is normal, which one number can't tell you. */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-medium text-slate-600">
              Last 12 months
            </h2>
            <div className="flex items-end gap-1.5" style={{ height: 140 }}>
              {detail.history.map((point) => (
                <button
                  key={point.month}
                  onClick={() => goToMonth(point.month)}
                  title={`${monthLabel(point.month)} · ${formatCurrency(point.total)}`}
                  className="group flex flex-1 flex-col items-center justify-end gap-1"
                  style={{ height: "100%" }}
                >
                  <span className="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100">
                    {point.total ? formatCurrency(point.total) : ""}
                  </span>
                  <span
                    className="w-full rounded-t transition-opacity group-hover:opacity-80"
                    style={{
                      height: `${Math.max(
                        2,
                        (Math.abs(point.total) / peak) * 100
                      )}%`,
                      backgroundColor: point.is_current ? accent : `${accent}59`,
                    }}
                  />
                  <span
                    className={`text-[10px] ${
                      point.is_current
                        ? "font-semibold text-slate-700"
                        : "text-slate-400"
                    }`}
                  >
                    {point.month.slice(5)}
                  </span>
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Click a bar to jump to that month. Months with no imported
              statement show as empty, which is not the same as spending
              nothing — check the{" "}
              <Link
                href="/statement-log"
                className="font-medium text-brand-600 hover:text-brand-700"
              >
                statement log
              </Link>
              .
            </p>
          </div>

          {/* Transactions */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-medium text-slate-600">
                Transactions in {monthLabel(month)}
              </h2>
              <Link
                href={`/transactions?month=${month}`}
                className="text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                Open in Transactions →
              </Link>
            </div>

            {detail.transactions.length === 0 ? (
              <p className="py-10 text-center text-sm text-slate-400">
                Nothing in this category for {monthLabel(month)}.
              </p>
            ) : (
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-400">
                  <tr>
                    <th className="py-1 pr-3">Date</th>
                    <th className="pr-3">Description</th>
                    <th className="pr-3">Tags</th>
                    <th className="text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.transactions.map((t) => (
                    <tr key={t.id} className="border-t border-slate-100">
                      <td className="whitespace-nowrap py-1.5 pr-3 text-slate-500">
                        {t.trans_date}
                      </td>
                      <td className="pr-3">{t.description}</td>
                      <td className="pr-3">
                        {t.tags.map((tag) => (
                          <span
                            key={tag}
                            className="mr-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                          >
                            {tag}
                          </span>
                        ))}
                      </td>
                      <td
                        className={`text-right ${
                          t.amount < 0 ? "text-green-600" : "text-slate-800"
                        }`}
                      >
                        {formatSignedCurrency(t.amount)}
                      </td>
                    </tr>
                  ))}
                  <tr className="border-t-2 border-slate-200 font-semibold">
                    <td className="py-2" colSpan={3}>
                      Total
                    </td>
                    <td className="text-right">{formatCurrency(detail.total)}</td>
                  </tr>
                </tbody>
              </table>
            )}
            {detail.transactions.some((t) => t.amount < 0) && (
              <p className="mt-2 text-xs text-slate-400">
                Refunds (shown in green) are netted off the total rather than
                counted as income — the same way the dashboard reports this
                category.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
