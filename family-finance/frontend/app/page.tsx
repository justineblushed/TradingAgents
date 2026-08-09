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
import {
  CreditCardSummary,
  DashboardSummary,
  getCreditCardSummaries,
  getDashboardSummary,
} from "@/lib/api";

const COLORS = ["#2f6fed", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#0ea5e9", "#64748b"];

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function DashboardPage() {
  const [month, setMonth] = useState(currentMonth());
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cards, setCards] = useState<CreditCardSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSummary(null);
    setCards(null);
    getDashboardSummary(month)
      .then(setSummary)
      .catch((e) => setError(e.message));
    getCreditCardSummaries(month)
      .then(setCards)
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
            <ChartCard title="Spending by Category">
              {categoryData.length === 0 ? (
                <EmptyState />
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={categoryData}
                      dataKey="value"
                      nameKey="name"
                      outerRadius={90}
                      isAnimationActive={false}
                    >
                      {categoryData.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
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
                    <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
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

function CreditCardCard({ card }: { card: CreditCardSummary }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="mb-2 text-sm font-medium text-slate-700">{card.name}</p>
      <dl className="space-y-1.5 text-sm">
        <Row
          label="Current balance"
          value={
            card.current_balance !== null
              ? `$${card.current_balance.toFixed(2)}${
                  card.balance_is_estimated ? " (estimated)" : ""
                }`
              : "—"
          }
        />
        <Row
          label="Available credit"
          value={card.available_credit !== null ? `$${card.available_credit.toFixed(2)}` : "—"}
        />
        <Row label="This month's spending" value={`$${card.month_spending.toFixed(2)}`} />
        <Row
          label="Payments made"
          value={`$${card.month_payments.toFixed(2)}`}
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
        ${value.toFixed(2)}
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
