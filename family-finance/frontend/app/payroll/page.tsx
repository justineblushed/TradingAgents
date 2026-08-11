"use client";

import { useCallback, useEffect, useState } from "react";
import {
  PAY_STUB_DEDUCTIONS,
  PAY_STUB_EMPLOYER_FIELDS,
  PayStub,
  PayStubFields,
  PayrollSummary,
  TaxBracket,
  createPayStub,
  deletePayStub,
  getPayrollSummary,
  listPayStubs,
  listTaxBrackets,
  previewPayStub,
  replaceTaxBrackets,
} from "@/lib/api";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";

function formatPercent(rate: number | undefined): string {
  if (rate === undefined) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

function emptyStub(): PayStubFields {
  return {
    employer: "",
    earner: "",
    pay_date: "",
    period_start: null,
    period_end: null,
    gross_pay: 0,
    income_tax: 0,
    cpp: 0,
    ei: 0,
    rrsp_employee: 0,
    pension_employee: 0,
    union_dues: 0,
    other_deductions: 0,
    net_pay: 0,
    employer_rrsp: 0,
    employer_pension: 0,
    notes: "",
  };
}

const JURISDICTION_LABELS: Record<string, string> = {
  federal: "Federal",
  MB: "Manitoba",
  ON: "Ontario",
  BC: "British Columbia",
  AB: "Alberta",
  SK: "Saskatchewan",
  QC: "Quebec",
};

function jurisdictionLabel(code: string): string {
  return JURISDICTION_LABELS[code] ?? code;
}

/** A single dollar input. Kept as a string while focused so a field can be
 *  cleared and retyped without a stray 0 fighting the cursor. */
function MoneyInput({
  value,
  onChange,
  highlight = false,
}: {
  value: number;
  onChange: (v: number) => void;
  highlight?: boolean;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <input
      type="number"
      step="0.01"
      inputMode="decimal"
      value={draft ?? (value === 0 ? "" : String(value))}
      placeholder="0.00"
      onChange={(e) => {
        setDraft(e.target.value);
        onChange(Number(e.target.value) || 0);
      }}
      onBlur={() => setDraft(null)}
      className={`w-28 rounded-md border px-2 py-1 text-right text-sm ${
        highlight ? "border-amber-300 bg-amber-50" : "border-slate-300"
      }`}
    />
  );
}

export default function PayrollPage() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [carryForward, setCarryForward] = useState(0);
  const [carryForwardInput, setCarryForwardInput] = useState("");

  const [summary, setSummary] = useState<PayrollSummary | null>(null);
  const [stubs, setStubs] = useState<PayStub[]>([]);
  const [brackets, setBrackets] = useState<TaxBracket[]>([]);

  const [draft, setDraft] = useState<PayStubFields | null>(null);
  const [draftWarnings, setDraftWarnings] = useState<string[]>([]);
  const [matched, setMatched] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showBrackets, setShowBrackets] = useState(false);
  const [editedBrackets, setEditedBrackets] = useState<TaxBracket[] | null>(null);

  const reload = useCallback(async () => {
    try {
      const [s, list, br] = await Promise.all([
        getPayrollSummary(year, carryForward),
        listPayStubs(year),
        listTaxBrackets(year),
      ]);
      setSummary(s);
      setStubs(list);
      setBrackets(br);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load payroll data");
    }
  }, [year, carryForward]);

  useEffect(() => {
    reload();
  }, [reload]);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Reset so re-picking the same file still fires onChange.
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const parsed = await previewPayStub(file);
      setDraft({
        ...emptyStub(),
        employer: parsed.employer,
        pay_date: parsed.pay_date ?? "",
        period_start: parsed.period_start,
        period_end: parsed.period_end,
        gross_pay: parsed.gross_pay,
        income_tax: parsed.income_tax,
        cpp: parsed.cpp,
        ei: parsed.ei,
        rrsp_employee: parsed.rrsp_employee,
        pension_employee: parsed.pension_employee,
        union_dues: parsed.union_dues,
        other_deductions: parsed.other_deductions,
        net_pay: parsed.net_pay,
        employer_rrsp: parsed.employer_rrsp,
        employer_pension: parsed.employer_pension,
      });
      setDraftWarnings(parsed.warnings);
      setMatched(parsed.matched_fields);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to read pay stub");
    } finally {
      setBusy(false);
    }
  }

  function setField<K extends keyof PayStubFields>(key: K, value: PayStubFields[K]) {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  const draftDeductions = draft
    ? PAY_STUB_DEDUCTIONS.reduce((sum, f) => sum + Number(draft[f.key] ?? 0), 0)
    : 0;
  const draftResidual = draft
    ? Number((draft.gross_pay - draftDeductions - draft.net_pay).toFixed(2))
    : 0;

  async function handleSave() {
    if (!draft) return;
    if (!draft.pay_date) {
      setError("Pick a pay date before saving.");
      return;
    }
    if (draft.gross_pay <= 0) {
      setError("Gross pay is required — that's the number the bank deposit hides.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await createPayStub(draft);
      const stubYear = Number(draft.pay_date.slice(0, 4));
      setDraft(null);
      setDraftWarnings([]);
      setMatched([]);
      if (stubYear && stubYear !== year) {
        // The stub belongs to another tax year — follow it there rather than
        // leaving the user staring at a page that looks like nothing saved.
        // Changing the year re-runs the load effect, so no reload() here.
        setMessage(`Pay stub saved — switched to ${stubYear}.`);
        setYear(stubYear);
      } else {
        // Refresh first: confirming the save while the totals below still
        // show the previous numbers reads as if nothing was counted.
        await reload();
        setMessage("Pay stub saved.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save pay stub");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: number) {
    setBusy(true);
    try {
      await deletePayStub(id);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete pay stub");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveBrackets(jurisdiction: string) {
    if (!editedBrackets) return;
    setBusy(true);
    setError(null);
    try {
      const rows = editedBrackets.filter((b) => b.jurisdiction === jurisdiction);
      await replaceTaxBrackets(
        year,
        jurisdiction,
        rows.map((b) => ({
          lower_bound: b.lower_bound,
          upper_bound: b.upper_bound,
          rate: b.rate,
        }))
      );
      setEditedBrackets(null);
      setMessage(`${jurisdictionLabel(jurisdiction)} rates updated for ${year}.`);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save tax brackets");
    } finally {
      setBusy(false);
    }
  }

  const workingBrackets = editedBrackets ?? brackets;
  // Federal first, then provinces alphabetically — matches how a return reads.
  const jurisdictions = Array.from(
    new Set(workingBrackets.map((b) => b.jurisdiction))
  ).sort((a, b) =>
    a === "federal" ? -1 : b === "federal" ? 1 : a.localeCompare(b)
  );
  const hasStubs = (summary?.stub_count ?? 0) > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Payroll &amp; Tax</h1>
          <p className="mt-1 max-w-2xl text-xs text-slate-500">
            Your bank only shows the net deposit. Adding pay stubs here captures
            the gross pay and everything withheld from it, so RRSP room and your
            tax bracket are worked out from the real numbers instead of the
            take-home amount.
          </p>
        </div>
        <div>
          <label className="block text-xs text-slate-500">Tax year</label>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
          >
            {Array.from(
              // Always include the selected year, so following a stub into an
              // older tax year never leaves the dropdown blank.
              new Set([currentYear + 1, currentYear, currentYear - 1, currentYear - 2, year])
            )
              .sort((a, b) => b - a)
              .map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
          </select>
        </div>
      </div>

      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {message && (
        <p className="rounded-md bg-brand-50 p-3 text-sm text-brand-700">{message}</p>
      )}

      {/* Add a stub */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-medium text-slate-600">Add a pay stub</h2>
        <div className="flex flex-wrap items-center gap-3">
          <label
            className={`rounded-md px-4 py-2 text-sm font-medium text-white ${
              busy
                ? "cursor-not-allowed bg-slate-300"
                : "cursor-pointer bg-brand-500 hover:bg-brand-600"
            }`}
          >
            Choose pay stub PDF
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={handleFile}
              className="hidden"
              disabled={busy}
            />
          </label>
          <button
            onClick={() => {
              setDraft(emptyStub());
              setDraftWarnings([]);
              setMatched([]);
              setMessage(null);
              setError(null);
            }}
            disabled={busy}
            className="text-sm font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50"
          >
            or enter it manually
          </button>
        </div>
        <p className="mt-3 text-xs text-slate-400">
          Stub layouts differ between employers, so the PDF is read on a
          best-effort basis and every field is yours to correct below before
          anything is saved. The file is parsed in memory by your own backend and
          never written to disk.
        </p>
      </div>

      {/* Review form */}
      {draft && (
        <div className="rounded-xl border border-brand-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-medium text-slate-600">
            Review before saving
          </h2>

          {draftWarnings.length > 0 && (
            <div className="mb-4 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
              <ul className="list-inside list-disc">
                {draftWarnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="block text-xs text-slate-500">Employer</label>
              <input
                value={draft.employer}
                onChange={(e) => setField("employer", e.target.value)}
                placeholder="e.g. City of Winnipeg"
                className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500">
                Who earned it (optional)
              </label>
              <input
                value={draft.earner}
                onChange={(e) => setField("earner", e.target.value)}
                placeholder="e.g. Me / Partner"
                className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500">Pay date</label>
              <input
                type="date"
                value={draft.pay_date}
                onChange={(e) => setField("pay_date", e.target.value)}
                className={`mt-1 w-full rounded-md border px-2 py-1 text-sm ${
                  draft.pay_date ? "border-slate-300" : "border-amber-300 bg-amber-50"
                }`}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500">
                Period ending (optional)
              </label>
              <input
                type="date"
                value={draft.period_end ?? ""}
                onChange={(e) => setField("period_end", e.target.value || null)}
                className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
          </div>

          <div className="mt-5 grid gap-6 md:grid-cols-2">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                Earnings &amp; deductions
              </p>
              <div className="mt-2 space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium text-slate-700">Gross pay</span>
                  <MoneyInput
                    value={draft.gross_pay}
                    onChange={(v) => setField("gross_pay", v)}
                    highlight={draft.gross_pay <= 0}
                  />
                </div>
                {PAY_STUB_DEDUCTIONS.map((f) => (
                  <div key={f.key} className="flex items-center justify-between gap-3">
                    <span className="text-sm text-slate-600">
                      {f.label}
                      {matched.includes(f.key) && (
                        <span className="ml-2 text-xs text-green-600">read from PDF</span>
                      )}
                    </span>
                    <MoneyInput
                      value={Number(draft[f.key])}
                      onChange={(v) => setField(f.key, v as never)}
                    />
                  </div>
                ))}
                <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-2">
                  <span className="text-sm font-medium text-slate-700">Net pay</span>
                  <MoneyInput
                    value={draft.net_pay}
                    onChange={(v) => setField("net_pay", v)}
                    highlight={draft.net_pay <= 0}
                  />
                </div>
                <p
                  className={`text-xs ${
                    Math.abs(draftResidual) < 0.01 ? "text-green-600" : "text-amber-700"
                  }`}
                >
                  {Math.abs(draftResidual) < 0.01
                    ? "✓ Gross − deductions = net pay."
                    : `Gross − deductions − net leaves ${formatSignedCurrency(
                        draftResidual
                      )} unaccounted for. Put it in "Other deductions" or fix a field.`}
                </p>
              </div>
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                Employer contributions
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Not deducted from your pay, but they reduce next year&apos;s RRSP
                room through the pension adjustment.
              </p>
              <div className="mt-2 space-y-2">
                {PAY_STUB_EMPLOYER_FIELDS.map((f) => (
                  <div key={f.key} className="flex items-center justify-between gap-3">
                    <span className="text-sm text-slate-600">{f.label}</span>
                    <MoneyInput
                      value={Number(draft[f.key])}
                      onChange={(v) => setField(f.key, v as never)}
                    />
                  </div>
                ))}
              </div>
              <label className="mt-4 block text-xs text-slate-500">Notes</label>
              <textarea
                value={draft.notes}
                onChange={(e) => setField("notes", e.target.value)}
                rows={3}
                placeholder="e.g. includes retro pay"
                className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={busy}
              className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
            >
              Save pay stub
            </button>
            <button
              onClick={() => {
                setDraft(null);
                setDraftWarnings([]);
              }}
              disabled={busy}
              className="text-sm text-slate-500 hover:text-slate-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {summary && !hasStubs && !draft && (
        <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
          No pay stubs for {year} yet. Add one above and the tax and RRSP picture
          below fills in.
        </p>
      )}

      {summary && hasStubs && (
        <>
          {/* YTD */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-medium text-slate-600">
                Year to date ({summary.stub_count} stub
                {summary.stub_count === 1 ? "" : "s"})
              </h2>
              <span className="text-xs text-slate-400">{summary.projection_basis}</span>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-xs text-slate-500">Gross pay</p>
                <p className="text-xl font-semibold text-slate-800">
                  {formatCurrency(summary.ytd_gross)}
                </p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-xs text-slate-500">Withheld &amp; deducted</p>
                <p className="text-xl font-semibold text-slate-800">
                  {formatCurrency(summary.ytd_gross - summary.ytd_net)}
                </p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-xs text-slate-500">
                  Net deposited{" "}
                  <span className="text-slate-400">(what the bank sees)</span>
                </p>
                <p className="text-xl font-semibold text-slate-800">
                  {formatCurrency(summary.ytd_net)}
                </p>
              </div>
            </div>
            <table className="mt-4 w-full text-left text-sm">
              <tbody className="divide-y divide-slate-100">
                {[
                  ["Income tax", summary.ytd_income_tax],
                  ["CPP", summary.ytd_cpp],
                  ["EI", summary.ytd_ei],
                  ["RRSP (yours)", summary.ytd_rrsp],
                  ["Pension (yours)", summary.ytd_pension],
                  ["Union dues & other", summary.ytd_other_deductions],
                ].map(([label, amount]) => (
                  <tr key={label as string}>
                    <td className="py-1.5 text-slate-600">{label}</td>
                    <td className="py-1.5 text-right text-slate-800">
                      {formatCurrency(amount as number)}
                    </td>
                    <td className="w-16 py-1.5 text-right text-xs text-slate-400">
                      {summary.ytd_gross > 0
                        ? `${(((amount as number) / summary.ytd_gross) * 100).toFixed(1)}%`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Tax position */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-medium text-slate-600">Tax position</h2>
            {summary.tax.available ? (
              <>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  <div>
                    <p className="text-xs text-slate-500">Projected annual gross</p>
                    <p className="text-lg font-semibold text-slate-800">
                      {formatCurrency(summary.annualized_gross)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Marginal rate</p>
                    <p className="text-lg font-semibold text-slate-800">
                      {formatPercent(summary.tax.marginal_rate)}
                    </p>
                    <p className="text-xs text-slate-400">on your next dollar earned</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Average rate</p>
                    <p className="text-lg font-semibold text-slate-800">
                      {formatPercent(summary.tax.average_rate)}
                    </p>
                    <p className="text-xs text-slate-400">
                      {formatCurrency(summary.tax.total_tax ?? 0)} estimated for the year
                    </p>
                  </div>
                </div>

                <div className="mt-4 space-y-1 text-sm text-slate-600">
                  {summary.tax.federal_bracket && (
                    <p>
                      Federal bracket:{" "}
                      <span className="font-medium text-slate-800">
                        {formatPercent(summary.tax.federal_bracket.rate)}
                      </span>{" "}
                      <span className="text-xs text-slate-400">
                        (from {formatCurrency(summary.tax.federal_bracket.lower_bound)}
                        {summary.tax.federal_bracket.upper_bound
                          ? ` to ${formatCurrency(
                              summary.tax.federal_bracket.upper_bound
                            )}`
                          : " and up"}
                        , after the basic personal amount)
                      </span>
                    </p>
                  )}
                  {summary.tax.provincial_bracket && (
                    <p>
                      {jurisdictionLabel(summary.tax.province ?? "")} bracket:{" "}
                      <span className="font-medium text-slate-800">
                        {formatPercent(summary.tax.provincial_bracket.rate)}
                      </span>{" "}
                      <span className="text-xs text-slate-400">
                        (from {formatCurrency(summary.tax.provincial_bracket.lower_bound)}
                        {summary.tax.provincial_bracket.upper_bound
                          ? ` to ${formatCurrency(
                              summary.tax.provincial_bracket.upper_bound
                            )}`
                          : " and up"}
                        )
                      </span>
                    </p>
                  )}
                </div>

                {summary.withholding_delta !== null && (
                  <p className="mt-4 rounded-md bg-slate-50 p-3 text-sm text-slate-600">
                    Tax withheld so far is{" "}
                    <span className="font-semibold text-slate-800">
                      {formatSignedCurrency(summary.withholding_delta)}
                    </span>{" "}
                    versus what this estimate expects at this point in the year
                    {summary.withholding_delta > 0
                      ? " — leaning toward a refund"
                      : summary.withholding_delta < 0
                      ? " — leaning toward a balance owing"
                      : ""}
                    . A rough signal only; it can&apos;t see other income, credits,
                    or your partner&apos;s return.
                  </p>
                )}
              </>
            ) : (
              <p className="mt-3 text-sm text-slate-500">
                No tax rates stored for {year}. Add them in the rates table below
                and this fills in.
              </p>
            )}
          </div>

          {/* RRSP */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-medium text-slate-600">RRSP room</h2>
            {summary.rrsp.available ? (
              <>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  <div>
                    <p className="text-xs text-slate-500">
                      Room generated by {year} income
                    </p>
                    <p className="text-lg font-semibold text-slate-800">
                      {formatCurrency(summary.rrsp.generated ?? 0)}
                    </p>
                    <p className="text-xs text-slate-400">
                      {formatPercent(summary.rrsp.rate)} of{" "}
                      {formatCurrency(summary.rrsp.earned_income ?? 0)}
                      {summary.rrsp.capped_by_limit &&
                        ` — capped at the ${formatCurrency(
                          summary.rrsp.dollar_limit ?? 0
                        )} annual limit`}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Pension adjustment</p>
                    <p className="text-lg font-semibold text-slate-800">
                      −{formatCurrency(summary.rrsp.pension_adjustment ?? 0)}
                    </p>
                    <p className="text-xs text-slate-400">
                      registered pension contributions, projected for the full
                      year. An employer RRSP match isn&apos;t a pension
                      adjustment — it counts as a contribution instead.
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Estimated room</p>
                    <p className="text-lg font-semibold text-brand-700">
                      {formatCurrency(summary.rrsp.room ?? 0)}
                    </p>
                    <p className="text-xs text-slate-400">
                      contributed so far:{" "}
                      {formatCurrency(summary.ytd_rrsp_contributed)}
                      {summary.ytd_employer_rrsp > 0 &&
                        ` (incl. ${formatCurrency(
                          summary.ytd_employer_rrsp
                        )} employer match)`}
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-slate-100 pt-4">
                  <div>
                    <label className="block text-xs text-slate-500">
                      Carry-forward room from your Notice of Assessment
                    </label>
                    <input
                      type="number"
                      value={carryForwardInput}
                      onChange={(e) => setCarryForwardInput(e.target.value)}
                      onBlur={() => setCarryForward(Number(carryForwardInput) || 0)}
                      onKeyDown={(e) =>
                        e.key === "Enter" &&
                        setCarryForward(Number(carryForwardInput) || 0)
                      }
                      placeholder="0.00"
                      className="mt-1 w-40 rounded-md border border-slate-300 px-2 py-1 text-sm"
                    />
                  </div>
                  <p className="pb-1 text-xs text-slate-400">
                    This app can&apos;t see your CRA account — enter the unused
                    room from your NOA to include it.
                  </p>
                </div>

                {summary.tax_if_rrsp_maxed && (
                  <div className="mt-4 rounded-md border border-brand-100 bg-brand-50 p-3 text-sm text-slate-700">
                    Contributing the remaining{" "}
                    <span className="font-semibold">
                      {formatCurrency(
                        summary.tax_if_rrsp_maxed.additional_contribution ?? 0
                      )}
                    </span>{" "}
                    would lower the estimated {year} tax bill by about{" "}
                    <span className="font-semibold text-brand-700">
                      {formatCurrency(summary.tax_if_rrsp_maxed.tax_saving ?? 0)}
                    </span>
                    , dropping the marginal rate from{" "}
                    {formatPercent(summary.tax.marginal_rate)} to{" "}
                    {formatPercent(summary.tax_if_rrsp_maxed.marginal_rate)}. Deferred,
                    not erased — it&apos;s taxed on withdrawal.
                  </div>
                )}
              </>
            ) : (
              <p className="mt-3 text-sm text-slate-500">
                No RRSP settings stored for {year}.
              </p>
            )}
          </div>

          {/* Stub list */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-medium text-slate-600">
              Pay stubs in {year}
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-400">
                  <tr>
                    <th className="py-1 pr-3">Pay date</th>
                    <th className="pr-3">Employer</th>
                    <th className="pr-3">Earner</th>
                    <th className="pr-3 text-right">Gross</th>
                    <th className="pr-3 text-right">Deductions</th>
                    <th className="pr-3 text-right">Net</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {stubs.map((s) => (
                    <tr key={s.id} className="border-t border-slate-100">
                      <td className="py-1.5 pr-3 text-slate-600">{s.pay_date}</td>
                      <td className="pr-3">{s.employer || "—"}</td>
                      <td className="pr-3 text-slate-500">{s.earner || "—"}</td>
                      <td className="pr-3 text-right">{formatCurrency(s.gross_pay)}</td>
                      <td className="pr-3 text-right text-slate-500">
                        {formatCurrency(s.total_deductions)}
                      </td>
                      <td className="pr-3 text-right font-medium">
                        {formatCurrency(s.net_pay)}
                      </td>
                      <td className="text-right">
                        <button
                          onClick={() => handleDelete(s.id)}
                          disabled={busy}
                          className="text-xs text-slate-400 hover:text-red-600 disabled:opacity-50"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Rates */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-medium text-slate-600">
            Tax rates used for {year}
          </h2>
          <button
            onClick={() => setShowBrackets((v) => !v)}
            className="text-sm font-medium text-brand-600 hover:text-brand-700"
          >
            {showBrackets ? "Hide" : "Show / edit"}
          </button>
        </div>
        <p className="mt-2 text-xs text-amber-800">
          {summary?.rates_verified_note ??
            "Rates are indexed every year — verify them against canada.ca before relying on these numbers."}
        </p>

        {showBrackets && (
          <div className="mt-4 space-y-6">
            {jurisdictions.length === 0 && (
              <p className="text-sm text-slate-500">
                No brackets stored for {year}. The estimate falls back to the most
                recent year that has rates.
              </p>
            )}
            {jurisdictions.map((j) => {
              const rows = workingBrackets
                .filter((b) => b.jurisdiction === j)
                .sort((a, b) => a.lower_bound - b.lower_bound);
              return (
                <div key={j}>
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-700">
                      {jurisdictionLabel(j)} — {rows[0]?.tax_year ?? year}
                    </p>
                    {editedBrackets && (
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleSaveBrackets(j)}
                          disabled={busy}
                          className="rounded-md bg-brand-500 px-3 py-1 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50"
                        >
                          Save {jurisdictionLabel(j)}
                        </button>
                        <button
                          onClick={() => setEditedBrackets(null)}
                          className="text-xs text-slate-400 hover:text-slate-600"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                  <table className="mt-2 w-full text-left text-sm">
                    <thead className="text-xs uppercase text-slate-400">
                      <tr>
                        <th className="py-1 pr-3">From</th>
                        <th className="pr-3">To</th>
                        <th className="pr-3">Rate %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((b) => (
                        <tr key={b.id} className="border-t border-slate-100">
                          <td className="py-1 pr-3">
                            <input
                              type="number"
                              value={b.lower_bound}
                              onChange={(e) =>
                                setEditedBrackets(
                                  (workingBrackets ?? []).map((x) =>
                                    x.id === b.id
                                      ? { ...x, lower_bound: Number(e.target.value) }
                                      : x
                                  )
                                )
                              }
                              className="w-32 rounded-md border border-slate-300 px-2 py-1 text-sm"
                            />
                          </td>
                          <td className="pr-3">
                            <input
                              type="number"
                              value={b.upper_bound ?? ""}
                              placeholder="no limit"
                              onChange={(e) =>
                                setEditedBrackets(
                                  (workingBrackets ?? []).map((x) =>
                                    x.id === b.id
                                      ? {
                                          ...x,
                                          upper_bound:
                                            e.target.value === ""
                                              ? null
                                              : Number(e.target.value),
                                        }
                                      : x
                                  )
                                )
                              }
                              className="w-32 rounded-md border border-slate-300 px-2 py-1 text-sm"
                            />
                          </td>
                          <td className="pr-3">
                            <input
                              type="number"
                              step="0.01"
                              value={Number((b.rate * 100).toFixed(4))}
                              onChange={(e) =>
                                setEditedBrackets(
                                  (workingBrackets ?? []).map((x) =>
                                    x.id === b.id
                                      ? { ...x, rate: Number(e.target.value) / 100 }
                                      : x
                                  )
                                )
                              }
                              className="w-24 rounded-md border border-slate-300 px-2 py-1 text-sm"
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
