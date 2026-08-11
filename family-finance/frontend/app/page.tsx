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
import { useRouter } from "next/navigation";
import SignIssueBanner from "./sign-issue-banner";
import {
  AreaToWatch,
  CONTROL_LABELS,
  Controllability,
  Category,
  CoverageSummary,
  CreditCardSummary,
  DashboardSummary,
  SpendingControl,
  UpcomingSummary,
  getCreditCardSummaries,
  getDashboardSummary,
  getSpendingControl,
  getStatementCoverage,
  getUpcoming,
  listCategories,
} from "@/lib/api";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

/** Y-axis label for the category bar chart, rendered as a real button so the
 *  category name itself is keyboard-reachable — clicking a bar works with a
 *  mouse but leaves the chart unusable without one. */
function CategoryTick(props: {
  x?: number;
  y?: number;
  payload?: { value: string };
  onSelect: (name: string) => void;
}) {
  const { x = 0, y = 0, payload, onSelect } = props;
  const name = payload?.value ?? "";
  return (
    <foreignObject x={x - 150} y={y - 11} width={146} height={22}>
      <button
        onClick={() => onSelect(name)}
        title={`See every ${name} transaction`}
        className="w-full truncate pr-1 text-right text-xs text-slate-600 hover:text-brand-700 hover:underline"
      >
        {name}
      </button>
    </foreignObject>
  );
}

export default function DashboardPage() {
  const [month, setMonth] = useState(currentMonth());
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cards, setCards] = useState<CreditCardSummary[] | null>(null);
  const [control, setControl] = useState<SpendingControl | null>(null);
  const [coverage, setCoverage] = useState<CoverageSummary | null>(null);
  const [upcoming, setUpcoming] = useState<UpcomingSummary | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    // Both of these are about today, not the month being browsed.
    getStatementCoverage()
      .then(setCoverage)
      .catch(() => {});
    getUpcoming()
      .then(setUpcoming)
      .catch(() => {});
    listCategories()
      .then(setCategories)
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

  // A category keeps its own colour in every chart, so a colour means the
  // same thing wherever you see it. Uncategorized is deliberately grey —
  // it's a gap in the data, not a kind of spending.
  const colorOf = useMemo(() => {
    const map = new Map(categories.map((c) => [c.name, c.color]));
    return (name: string) => map.get(name) || "#94a3b8";
  }, [categories]);

  const emojiOf = useMemo(() => {
    const map = new Map(categories.map((c) => [c.name, c.emoji]));
    return (name: string) => map.get(name) || "";
  }, [categories]);

  const categoryData = useMemo(
    () =>
      Object.entries(summary?.by_category ?? {})
        .map(([name, value]) => ({
          name,
          value,
          color: colorOf(name),
          label: `${emojiOf(name)} ${name}`.trim(),
        }))
        .sort((a, b) => b.value - a.value),
    [summary, colorOf, emojiOf]
  );

  // A group's colour is borrowed from its largest category so the pie and
  // the bar chart visibly belong to the same palette.
  const groupData = useMemo(() => {
    const dominant = new Map<string, { name: string; value: number }>();
    for (const c of categories) {
      const spent = summary?.by_category?.[c.name] ?? 0;
      const group = c.group_name || "Other";
      const best = dominant.get(group);
      if (spent > 0 && (!best || spent > best.value)) {
        dominant.set(group, { name: c.name, value: spent });
      }
    }
    return Object.entries(summary?.by_group ?? {})
      .map(([name, value]) => ({
        name,
        value,
        color: dominant.has(name) ? colorOf(dominant.get(name)!.name) : "#94a3b8",
      }))
      .sort((a, b) => b.value - a.value);
  }, [summary, categories, colorOf]);

  function openCategory(name: string) {
    router.push(`/categories/${encodeURIComponent(name)}?month=${month}`);
  }

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

      {summary && summary.total_income < 0 && <SignIssueBanner />}

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

          {upcoming && <ComingUpCard upcoming={upcoming} />}

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
                      {groupData.map((slice) => (
                        <Cell key={slice.name} fill={slice.color} />
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
                <>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart
                      data={categoryData}
                      layout="vertical"
                      onClick={(state) => {
                        const name = state?.activePayload?.[0]?.payload?.name;
                        if (name) openCategory(name);
                      }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={150}
                        tick={<CategoryTick onSelect={openCategory} />}
                      />
                      <Tooltip
                        cursor={{ fill: "#f1f5f9" }}
                        formatter={(v: number) => formatCurrency(v)}
                      />
                      <Bar
                        dataKey="value"
                        radius={[0, 4, 4, 0]}
                        isAnimationActive={false}
                        className="cursor-pointer"
                      >
                        {categoryData.map((row) => (
                          <Cell key={row.name} fill={row.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <p className="mt-1 text-xs text-slate-400">
                    Click a bar to see every transaction behind it, and step
                    through other months.
                  </p>
                </>
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

function relativeDay(days: number): string {
  if (days < 0) return `${-days} day${days === -1 ? "" : "s"} ago`;
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  return `in ${days} days`;
}

/** Forward-looking card: the next paycheque and the bills history says are
 *  coming. Both are inferred rather than scheduled, so each row carries the
 *  evidence behind it — a projection presented as a certainty would be worse
 *  than no projection at all. */
function ComingUpCard({ upcoming }: { upcoming: UpcomingSummary }) {
  const { next_payday: payday, bills } = upcoming;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-medium text-slate-600">Coming up</h2>
        <span className="text-xs text-slate-400">
          next {upcoming.horizon_days} days
        </span>
      </div>

      <div className="mt-3 grid gap-4 md:grid-cols-2">
        {/* Next payday */}
        <div className="rounded-lg bg-green-50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-green-700">
            Next payday
          </p>
          {payday ? (
            <>
              <p className="mt-1 text-xl font-semibold text-slate-800">
                {payday.pay_date}{" "}
                <span className="text-sm font-normal text-slate-500">
                  · {relativeDay(payday.days_away)}
                </span>
              </p>
              {payday.expected_net !== null && (
                <p className="text-sm text-slate-600">
                  expecting ~{formatCurrency(payday.expected_net)} net
                  {payday.employer && ` from ${payday.employer}`}
                </p>
              )}
              <p className="mt-1 text-xs text-slate-400">
                Projected from your pay stubs ({payday.basis}) — not a
                confirmed deposit date.
              </p>
            </>
          ) : (
            <p className="mt-1 text-sm text-slate-500">
              {upcoming.payday_hint}{" "}
              <Link
                href="/payroll"
                className="font-medium text-brand-600 hover:text-brand-700"
              >
                Payroll →
              </Link>
            </p>
          )}
        </div>

        {/* Bills total */}
        <div className="rounded-lg bg-slate-50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Bills due
          </p>
          {bills.length > 0 ? (
            <>
              <p className="mt-1 text-xl font-semibold text-slate-800">
                {formatCurrency(upcoming.bills_total)}
              </p>
              <p className="text-sm text-slate-600">
                across {bills.length} recurring charge
                {bills.length === 1 ? "" : "s"}
              </p>
              {payday?.expected_net != null && (
                <p className="mt-1 text-xs text-slate-400">
                  {upcoming.bills_total <= payday.expected_net
                    ? "Covered by the next paycheque on its own."
                    : `${formatCurrency(
                        upcoming.bills_total - payday.expected_net
                      )} more than the next paycheque — the rest comes from your balances.`}
                </p>
              )}
            </>
          ) : (
            <p className="mt-1 text-sm text-slate-500">{upcoming.bills_hint}</p>
          )}
        </div>
      </div>

      {bills.length > 0 && (
        <div className="mt-4 divide-y divide-slate-100 border-t border-slate-100 pt-1">
          {bills.map((bill) => (
            <div
              key={`${bill.description}-${bill.expected_date}`}
              className="flex flex-wrap items-center justify-between gap-2 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-700">
                  {bill.description}
                  {bill.overdue && (
                    <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                      expected {relativeDay(bill.days_away)}
                    </span>
                  )}
                </p>
                <p className="text-xs text-slate-400">
                  {bill.category ?? "Uncategorized"} · {bill.account_name} ·{" "}
                  {bill.basis}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold text-slate-800">
                  {bill.amount_varies ? "~" : ""}
                  {formatCurrency(bill.expected_amount)}
                </p>
                <p className="text-xs text-slate-400">
                  {bill.overdue ? "was due" : relativeDay(bill.days_away)}
                  {bill.amount_varies &&
                    ` · ranges ${formatCurrency(
                      bill.amount_low
                    )}–${formatCurrency(bill.amount_high)}`}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="mt-3 text-xs text-slate-400">
        Nothing here was entered as a bill — these are charges spotted
        repeating in your imported transactions, so the amounts are
        expectations from history rather than invoices.
      </p>
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
