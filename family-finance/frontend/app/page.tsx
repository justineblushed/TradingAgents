"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import Link from "next/link";
import {
  AreaToWatch,
  CONTROL_LABELS,
  Controllability,
  CoverageSummary,
  CreditCardSummary,
  DashboardSummary,
  SpendingControl,
  getCreditCardSummaries,
  getDashboardSummary,
  getSpendingControl,
  getStatementCoverage,
} from "@/lib/api";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";

const COLORS = ["#2f6fed", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#0ea5e9", "#64748b"];

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function DashboardPage() {
  const [month, setMonth] = useState(currentMonth());
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cards, setCards] = useState<CreditCardSummary[] | null>(null);
  const [control, setControl] = useState<SpendingControl | null>(null);
  const [coverage, setCoverage] = useState<CoverageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Missing-statement check is independent of the selected month.
    getStatementCoverage()
      .then(setCoverage)
      .catch(() => {});
  }, []);

  useEffect(() => {
    setSummary(null);
    setCards(null);
    setControl(null);
    getDashboardSummary(month)
      .then(setSummary)
      .catch((e) => setError(e.message));
    getCreditCardSummaries(month)
      .then(setCards)
      .catch((e) => setError(e.message));
    getSpendingControl(month)
      .then(setControl)
      .catch((e) => setError(e.message));
  }, [month]);

  const categoryData = useMemo(
    () =>
      Object.entries(summary?.by_category ?? {}).map(([name, value]) => ({
        name,
        value,
      })),
    [summary]
  );

  const groupData = useMemo(
    () =>
      Object.entries(summary?.by_group ?? {})
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value),
    [summary]
  );

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-slate-600">Month</label>
        <input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
        />
      </div>

      {error && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          Could not reach the backend — is it running? ({error})
        </p>
      )}

      {coverage && coverage.total_missing > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <span>
            ⚠ {coverage.total_missing} month
            {coverage.total_missing === 1 ? "" : "s"} of statements missing
            across your accounts — totals for those months are incomplete.
          </span>
          <Link
            href="/statement-log"
            className="shrink-0 font-medium text-amber-900 underline hover:text-amber-700"
          >
            View checklist
          </Link>
        </div>
      )}

      {!summary && !error && (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      )}

      {summary && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard label="Spending" value={summary.total_spending} tone="expense" />
            <StatCard label="Income" value={summary.total_income} tone="income" />
            <StatCard label="Net Cash Flow" value={summary.net_cash_flow} tone="neutral" />
          </div>
          <p className="text-xs text-slate-400">
            Credit card payments aren't counted here — paying off your own card
            is a transfer between your own accounts, not spending or income.
          </p>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ChartCard title="Spending by Group">
              {groupData.length === 0 ? (
                <EmptyState />
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={groupData}
                      dataKey="value"
                      nameKey="name"
                      outerRadius={90}
                      isAnimationActive={false}
                    >
                      {groupData.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => formatCurrency(v)} />
                    <Legend
                      layout="vertical"
                      align="right"
                      verticalAlign="middle"
                      wrapperStyle={{ fontSize: 12 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </ChartCard>

            <ChartCard title="Category Breakdown">
              {categoryData.length === 0 ? (
                <EmptyState />
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={categoryData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" width={140} />
                    <Tooltip formatter={(v: number) => formatCurrency(v)} />
                    <Bar
                      dataKey="value"
                      fill="#2f6fed"
                      radius={[0, 4, 4, 0]}
                      isAnimationActive={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          </div>
        </>
      )}

      {control && control.total_spending > 0 && (
        <SpendingControlPanel control={control} />
      )}

      {cards && cards.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-medium text-slate-600">Credit Cards</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {cards.map((c) => (
              <CreditCardCard key={c.account_id} card={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const COST_TYPE_BAR: Record<string, string> = {
  fixed: "bg-slate-500",
  recurring: "bg-brand-400",
  variable: "bg-green-500",
  irregular: "bg-amber-500",
};

const CONTROL_BADGE: Record<Controllability, string> = {
  very_high: "bg-green-100 text-green-800",
  high: "bg-green-50 text-green-700",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-slate-100 text-slate-500",
};

const CONTROL_DOT: Record<Controllability, string> = {
  very_high: "🟢",
  high: "🟢",
  medium: "🟡",
  low: "🔴",
};

function SpendingControlPanel({ control }: { control: SpendingControl }) {
  const lockedPct = control.total_spending
    ? Math.round((control.locked_amount / control.total_spending) * 100)
    : 0;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-medium text-slate-600">
          Fixed vs. adjustable spending
        </h2>

        <div className="mb-3 flex h-3 w-full overflow-hidden rounded-full bg-slate-100">
          {control.by_cost_type.map((s) => (
            <div
              key={s.cost_type}
              className={COST_TYPE_BAR[s.cost_type] ?? "bg-slate-300"}
              style={{ width: `${s.percent}%` }}
              title={`${s.label}: ${formatCurrency(s.amount)} (${s.percent}%)`}
            />
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {control.by_cost_type.map((s) => (
            <div key={s.cost_type}>
              <div className="flex items-center gap-1.5">
                <span
                  className={`h-2 w-2 rounded-full ${COST_TYPE_BAR[s.cost_type] ?? "bg-slate-300"}`}
                />
                <span className="text-xs text-slate-500">{s.label}</span>
              </div>
              <p className="mt-0.5 text-sm font-semibold text-slate-800">
                {formatCurrency(s.amount)}
              </p>
              <p className="text-xs text-slate-400">{s.percent}%</p>
            </div>
          ))}
        </div>

        <p className="mt-3 text-xs text-slate-400">
          {formatCurrency(control.locked_amount)} ({lockedPct}%) is fixed or
          irregular — little room to adjust this month.
        </p>
      </div>

      {control.budget_variances.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-medium text-slate-600">Over budget</h2>
            <p className="text-sm font-semibold text-red-600">
              {formatCurrency(control.over_budget_total)} over budget
            </p>
          </div>
          <div className="divide-y divide-slate-100">
            {control.budget_variances.map((b) => (
              <div
                key={b.category}
                className="flex items-center justify-between py-2 text-sm first:pt-0 last:pb-0"
              >
                <span className="text-slate-700">{b.category}</span>
                <span className="text-slate-400">
                  {formatCurrency(b.spent)} vs {formatCurrency(b.budget)}{" "}
                  <span className="font-medium text-red-600">
                    +{formatCurrency(b.over)}
                  </span>
                </span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-400">
            This is budget variance — what already happened. It is not money
            that reappears next month.
          </p>
        </div>
      )}

      {control.areas_to_watch.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-medium text-slate-600">Areas to watch</h2>
          <div className="divide-y divide-slate-100">
            {control.areas_to_watch.map((a) => (
              <WatchRow key={a.category} area={a} />
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-400">
            Compared against each category&apos;s own recent months, not a
            target — this is what flags something genuinely unusual.
          </p>
        </div>
      )}

      {control.adjustable_low !== null && control.adjustable_high !== null && (
        <div className="rounded-xl border border-brand-100 bg-brand-50 p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-widest text-brand-700">
            Adjustable spending
          </p>
          <p className="mt-1 text-2xl font-bold text-brand-700">
            ~{formatCurrency(control.adjustable_low)} –{" "}
            {formatCurrency(control.adjustable_high)}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            An estimate, not a promise. The lower bound is what returning to
            your own typical spending would free up; the upper bound is
            matching your best month in the last{" "}
            {control.adjustable_months_of_history} — both are levels this
            household has actually hit before. Only variable and recurring
            categories you rated high-control are counted.
          </p>
        </div>
      )}
    </div>
  );
}

function WatchRow({ area }: { area: AreaToWatch }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 py-2 first:pt-0 last:pb-0">
      <div className="flex items-center gap-2">
        <span>{CONTROL_DOT[area.controllability]}</span>
        <div>
          <p className="text-sm font-medium text-slate-700">{area.category}</p>
          <p className="text-xs text-slate-400">
            {formatCurrency(area.spent)} this month · typical ~
            {formatCurrency(area.typical)}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {area.highlight && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              CONTROL_BADGE[area.controllability]
            }`}
          >
            {CONTROL_LABELS[area.controllability]} control
          </span>
        )}
        <span className="w-24 text-right text-sm font-semibold text-amber-700">
          ↑ {area.percent_above}% above
        </span>
      </div>
    </div>
  );
}

function CreditCardCard({ card }: { card: CreditCardSummary }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="mb-2 text-sm font-medium text-slate-700">{card.name}</p>
      <dl className="space-y-1.5 text-sm">
        <Row
          label="Current balance"
          value={
            card.current_balance !== null
              ? `${formatSignedCurrency(card.current_balance)}${
                  card.balance_is_estimated ? " (estimated)" : ""
                }`
              : "—"
          }
        />
        <Row
          label="Available credit"
          value={card.available_credit !== null ? formatCurrency(card.available_credit) : "—"}
        />
        <Row label="This month's spending" value={formatCurrency(card.month_spending)} />
        <Row
          label="Payments made"
          value={formatCurrency(card.month_payments)}
          muted
        />
      </dl>
      {card.balance_is_estimated && card.current_balance !== null && (
        <p className="mt-2 text-xs text-slate-400">
          No balance recorded yet — estimated from imported transactions. Add a
          real balance on the Net Worth page for accuracy.
        </p>
      )}
    </div>
  );
}

function Row({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <dt className={muted ? "text-slate-400" : "text-slate-500"}>{label}</dt>
      <dd className={muted ? "text-slate-400" : "font-medium text-slate-800"}>{value}</dd>
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "expense" | "income" | "neutral";
}) {
  const color =
    tone === "expense"
      ? "text-red-600"
      : tone === "income"
      ? "text-green-600"
      : "text-slate-800";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${color}`}>
        {formatSignedCurrency(value)}
      </p>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="mb-2 text-sm font-medium text-slate-600">{title}</h2>
      {children}
    </div>
  );
}

function EmptyState() {
  return (
    <p className="py-16 text-center text-sm text-slate-400">
      No transactions for this month yet — upload a statement to get started.
    </p>
  );
}
