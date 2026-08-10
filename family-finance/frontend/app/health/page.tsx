"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { HealthMetric, HealthScore, getHealthScore } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

const STATUS_ICON: Record<HealthMetric["status"], string> = {
  good: "✓",
  warn: "⚠",
  bad: "✗",
  none: "·",
};

const STATUS_COLOR: Record<HealthMetric["status"], string> = {
  good: "text-green-600",
  warn: "text-amber-600",
  bad: "text-red-600",
  none: "text-slate-400",
};

const BAND_COLOR: Record<string, string> = {
  EXCELLENT: "text-green-600",
  GOOD: "text-green-600",
  FAIR: "text-amber-600",
  "NEEDS ATTENTION": "text-red-600",
  "NOT ENOUGH DATA": "text-slate-400",
};

export default function HealthPage() {
  const [health, setHealth] = useState<HealthScore | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealthScore()
      .then(setHealth)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {error && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}
      {health === null && !error && (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      )}

      {health && (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
            <p className="text-xs font-medium uppercase tracking-widest text-slate-400">
              Financial Health
            </p>
            {health.score !== null ? (
              <>
                <p className="mt-2 text-6xl font-bold text-slate-800">
                  {health.score}
                </p>
                <div className="mx-auto mt-3 h-1.5 w-48 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full ${
                      health.score >= 70
                        ? "bg-green-500"
                        : health.score >= 50
                        ? "bg-amber-500"
                        : "bg-red-500"
                    }`}
                    style={{ width: `${health.score}%` }}
                  />
                </div>
                <p
                  className={`mt-2 text-sm font-semibold tracking-widest ${
                    BAND_COLOR[health.band] ?? "text-slate-500"
                  }`}
                >
                  {health.band}
                </p>
                <p className="mt-3 text-xs text-slate-400">
                  The score is just a summary — the metrics below are what
                  matter.
                  {health.reference_month &&
                    ` Based on ${health.reference_month} (last complete month).`}
                </p>
              </>
            ) : (
              <>
                <p className="mt-2 text-3xl font-bold text-slate-400">—</p>
                <p className="mt-2 text-sm font-semibold tracking-widest text-slate-400">
                  {health.band}
                </p>
                <p className="mt-3 text-xs text-slate-400">
                  Import statements and record account balances to build up the
                  data behind each metric.
                </p>
              </>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="divide-y divide-slate-100">
              {health.metrics.map((m) => (
                <div key={m.key} className="py-3 first:pt-1 last:pb-1">
                  <div className="flex items-center justify-between gap-3">
                    <span className="flex items-center gap-2 text-sm text-slate-700">
                      <span className={`w-4 font-bold ${STATUS_COLOR[m.status]}`}>
                        {STATUS_ICON[m.status]}
                      </span>
                      {m.label}
                    </span>
                    <span
                      className={`text-sm font-semibold ${
                        m.status === "none" ? "text-slate-400" : "text-slate-800"
                      }`}
                    >
                      {m.display_value}
                    </span>
                  </div>
                  <p className="ml-6 mt-0.5 text-xs text-slate-400">{m.detail}</p>
                </div>
              ))}
            </div>
          </div>

          {health.opportunity && (
            <div className="rounded-xl border border-brand-100 bg-brand-50 p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-widest text-brand-700">
                Biggest opportunity
              </p>
              <p className="mt-2 text-sm text-slate-700">
                You spent{" "}
                <span className="font-semibold">
                  {formatCurrency(health.opportunity.over_amount)}
                </span>{" "}
                more on{" "}
                <span className="font-semibold">{health.opportunity.category}</span>{" "}
                than your {health.opportunity.basis} in {health.opportunity.month}.
              </p>
              <p className="mt-2 text-sm text-slate-700">
                Potential annual saving:{" "}
                <span className="font-semibold text-brand-700">
                  ~{formatCurrency(health.opportunity.annual_saving)}
                </span>
              </p>
              <p className="mt-3 text-xs text-slate-400">
                Set or adjust monthly targets on the{" "}
                <Link href="/categories" className="font-medium text-brand-600 hover:text-brand-700">
                  Categories page
                </Link>{" "}
                to sharpen this insight.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
