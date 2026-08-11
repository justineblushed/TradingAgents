"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  CalendarDay,
  CalendarSummary,
  Transaction,
  getCalendar,
  listTransactions,
} from "@/lib/api";
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
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function monthLabel(month: string): string {
  const [year, mon] = month.split("-").map(Number);
  return `${MONTH_NAMES[mon - 1]} ${year}`;
}

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Bucketed rather than a smooth gradient so adjacent days are easy to
 *  tell apart at a glance — a continuous gradient tends to make
 *  medium-spend days blur into their neighbours. */
function intensityClasses(spending: number, max: number, inMonth: boolean): string {
  if (!inMonth) return spending > 0 ? "bg-slate-100" : "bg-slate-50";
  if (spending <= 0 || max <= 0) return "bg-white";
  const ratio = spending / max;
  if (ratio > 0.75) return "bg-red-500 text-white";
  if (ratio > 0.5) return "bg-red-300";
  if (ratio > 0.25) return "bg-red-200";
  return "bg-red-100";
}

export default function CalendarPage() {
  const [month, setMonth] = useState(currentMonth());
  const [data, setData] = useState<CalendarSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selectedDay, setSelectedDay] = useState<CalendarDay | null>(null);
  const [dayTransactions, setDayTransactions] = useState<Transaction[] | null>(null);
  const [dayError, setDayError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    setSelectedDay(null);
    getCalendar(month)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [month]);

  const selectDay = useCallback(async (day: CalendarDay) => {
    setSelectedDay(day);
    setDayTransactions(null);
    setDayError(null);
    try {
      // A padding day may belong to the adjacent month, so fetch whichever
      // month the day itself falls in rather than assuming the one on screen.
      const dayMonth = day.date.slice(0, 7);
      const rows = await listTransactions(dayMonth);
      setDayTransactions(rows.filter((t) => t.trans_date === day.date));
    } catch (e) {
      setDayError(e instanceof Error ? e.message : "Failed to load transactions");
    }
  }, []);

  const weeks = useMemo(() => {
    if (!data) return [];
    const out: CalendarDay[][] = [];
    for (let i = 0; i < data.days.length; i += 7) {
      out.push(data.days.slice(i, i + 7));
    }
    return out;
  }, [data]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Spending Calendar</h1>
          <p className="mt-1 max-w-2xl text-xs text-slate-500">
            Darker means more spent that day, scaled against this month's
            own highest-spending day — not a fixed dollar amount, so a quiet
            month and a big one both use the full range of shading. A green
            dot marks a day money came in. Click any day to see what's
            behind it.
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setMonth(shiftMonth(month, -1))}
            aria-label="Previous month"
            className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
          >
            ←
          </button>
          <input
            type="month"
            value={month}
            onChange={(e) => e.target.value && setMonth(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
          <button
            onClick={() => setMonth(shiftMonth(month, 1))}
            aria-label="Next month"
            className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
          >
            →
          </button>
        </div>
      </div>

      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {!data && !error && (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      )}

      {data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-slate-500">Spending in {monthLabel(month)}</p>
              <p className="text-xl font-bold text-red-600">
                {formatCurrency(data.total_spending)}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-slate-500">Income in {monthLabel(month)}</p>
              <p className="text-xl font-bold text-green-600">
                {formatSignedCurrency(data.total_income)}
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="grid grid-cols-7 gap-1.5 text-center text-xs font-medium text-slate-400">
              {WEEKDAY_LABELS.map((w) => (
                <div key={w} className="pb-1">
                  {w}
                </div>
              ))}
            </div>
            <div className="space-y-1.5">
              {weeks.map((week, i) => (
                <div key={i} className="grid grid-cols-7 gap-1.5">
                  {week.map((day) => {
                    const dayNum = Number(day.date.slice(8, 10));
                    const isSelected = selectedDay?.date === day.date;
                    return (
                      <button
                        key={day.date}
                        onClick={() => selectDay(day)}
                        className={`relative flex aspect-square flex-col items-start justify-between rounded-md p-1.5 text-left transition ${intensityClasses(
                          day.spending,
                          data.max_daily_spending,
                          day.in_month
                        )} ${
                          isSelected
                            ? "ring-2 ring-brand-600"
                            : "hover:ring-1 hover:ring-brand-300"
                        } ${day.in_month ? "" : "text-slate-400"}`}
                      >
                        <span className="text-[11px] font-medium">{dayNum}</span>
                        {day.spending > 0 && (
                          <span className="w-full truncate text-[10px] font-semibold">
                            {formatCurrency(day.spending)}
                          </span>
                        )}
                        {day.income > 0 && (
                          <span
                            className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-green-500"
                            title={`${formatCurrency(day.income)} in`}
                          />
                        )}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>

            <div className="mt-3 flex items-center gap-3 text-xs text-slate-400">
              <span>Less</span>
              <span className="h-3 w-3 rounded bg-white ring-1 ring-slate-200" />
              <span className="h-3 w-3 rounded bg-red-100" />
              <span className="h-3 w-3 rounded bg-red-200" />
              <span className="h-3 w-3 rounded bg-red-300" />
              <span className="h-3 w-3 rounded bg-red-500" />
              <span>More</span>
              <span className="ml-3 flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500" /> money in
              </span>
            </div>
          </div>

          {selectedDay && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-sm font-medium text-slate-600">
                  {selectedDay.date}
                  {!selectedDay.in_month && (
                    <span className="ml-2 text-xs text-slate-400">
                      (outside {monthLabel(month)})
                    </span>
                  )}
                </h2>
                <Link
                  href={`/transactions?month=${selectedDay.date.slice(0, 7)}`}
                  className="text-xs font-medium text-brand-600 hover:text-brand-700"
                >
                  Open in Transactions →
                </Link>
              </div>

              {dayError && (
                <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{dayError}</p>
              )}
              {dayTransactions === null && !dayError && (
                <p className="py-6 text-center text-sm text-slate-400">Loading…</p>
              )}
              {dayTransactions !== null && dayTransactions.length === 0 && (
                <p className="py-6 text-center text-sm text-slate-400">
                  Nothing recorded on this day.
                </p>
              )}
              {dayTransactions !== null && dayTransactions.length > 0 && (
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase text-slate-400">
                    <tr>
                      <th className="py-1">Description</th>
                      <th>Category</th>
                      <th className="text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dayTransactions.map((t) => (
                      <tr key={t.id} className="border-t border-slate-100">
                        <td className="py-1.5 pr-3">{t.description}</td>
                        <td className="pr-3 text-slate-500">
                          {t.category ?? "Uncategorized"}
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
                  </tbody>
                </table>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
