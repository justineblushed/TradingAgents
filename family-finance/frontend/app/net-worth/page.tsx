"use client";

import { useEffect, useState } from "react";
import {
  AccountType,
  AccountWithBalance,
  ASSET_ACCOUNT_TYPES,
  LIABILITY_ACCOUNT_TYPES,
  NetWorthSummary,
  createAccount,
  getNetWorthSummary,
  recordAccountBalance,
} from "@/lib/api";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";

const TYPE_LABELS: Record<AccountType, string> = {
  cash: "Cash",
  chequing: "Chequing",
  savings: "Savings",
  investment: "Investment",
  tfsa: "TFSA",
  rrsp: "RRSP",
  resp: "RESP",
  other_asset: "Other asset",
  credit_card: "Credit Card",
  mortgage: "Mortgage",
  car_loan: "Car Loan",
  other_liability: "Other liability",
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function NetWorthPage() {
  const [summary, setSummary] = useState<NetWorthSummary | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<AccountType>("chequing");
  const [newCreditLimit, setNewCreditLimit] = useState("");

  function load() {
    getNetWorthSummary()
      .then(setSummary)
      .catch((err) =>
        setMessage(err instanceof Error ? err.message : "Failed to load net worth")
      );
  }

  useEffect(load, []);

  async function handleAddAccount() {
    if (!newName.trim()) return;
    setMessage(null);
    try {
      await createAccount({
        name: newName.trim(),
        account_type: newType,
        credit_limit: newType === "credit_card" && newCreditLimit ? Number(newCreditLimit) : null,
      });
      setNewName("");
      setNewCreditLimit("");
      load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to add account");
    }
  }

  const assets = summary?.accounts.filter((a) => !a.is_liability) ?? [];
  const liabilities = summary?.accounts.filter((a) => a.is_liability) ?? [];

  return (
    <div className="space-y-6">
      {message && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{message}</p>
      )}

      {summary === null && !message ? (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      ) : summary ? (
        <NetWorthHeader summary={summary} />
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <AccountGroup title="Assets" accounts={assets} onSaved={load} />
        <AccountGroup title="Liabilities" accounts={liabilities} onSaved={load} />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-medium text-slate-600">Add an account</h2>
        <div className="flex flex-wrap items-end gap-3">
          <input
            placeholder="e.g. RBC Savings"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as AccountType)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          >
            <optgroup label="Assets">
              {ASSET_ACCOUNT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABELS[t]}
                </option>
              ))}
            </optgroup>
            <optgroup label="Liabilities">
              {LIABILITY_ACCOUNT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABELS[t]}
                </option>
              ))}
            </optgroup>
          </select>
          {newType === "credit_card" && (
            <input
              type="number"
              placeholder="Credit limit (optional)"
              value={newCreditLimit}
              onChange={(e) => setNewCreditLimit(e.target.value)}
              className="w-40 rounded-md border border-slate-300 px-2 py-1 text-sm"
            />
          )}
          <button
            onClick={handleAddAccount}
            disabled={!newName.trim()}
            className="rounded-md bg-brand-500 px-3 py-1 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}

function NetWorthHeader({ summary }: { summary: NetWorthSummary }) {
  const deltaKnown = summary.delta !== null;
  const deltaUp = deltaKnown && (summary.delta ?? 0) >= 0;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <p className="text-sm text-slate-500">Assets</p>
          <p className="mt-1 text-2xl font-semibold text-green-600">
            {formatCurrency(summary.assets_total)}
          </p>
        </div>
        <div>
          <p className="text-sm text-slate-500">Liabilities</p>
          <p className="mt-1 text-2xl font-semibold text-red-600">
            -{formatCurrency(summary.liabilities_total)}
          </p>
        </div>
        <div>
          <p className="text-sm text-slate-500">Net Worth</p>
          <p className="mt-1 text-3xl font-bold text-brand-700">
            {formatSignedCurrency(summary.net_worth)}
          </p>
        </div>
      </div>
      {deltaKnown && (
        <p className={`mt-4 text-sm font-medium ${deltaUp ? "text-green-600" : "text-red-600"}`}>
          {deltaUp ? "↑" : "↓"} {formatCurrency(Math.abs(summary.delta as number))} vs last month
        </p>
      )}
      {!deltaKnown && (
        <p className="mt-4 text-xs text-slate-400">
          Record a balance before this month for at least one account to see
          month-over-month change.
        </p>
      )}
    </div>
  );
}

function AccountGroup({
  title,
  accounts,
  onSaved,
}: {
  title: string;
  accounts: AccountWithBalance[];
  onSaved: () => void;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-medium text-slate-600">{title}</h2>
      {accounts.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-400">No accounts yet.</p>
      ) : (
        <div className="space-y-3">
          {accounts.map((a) => (
            <AccountRow key={a.id} account={a} onSaved={onSaved} />
          ))}
        </div>
      )}
    </div>
  );
}

function AccountRow({
  account,
  onSaved,
}: {
  account: AccountWithBalance;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [asOfDate, setAsOfDate] = useState(todayIso());
  const [balance, setBalance] = useState(
    account.current_balance !== null ? String(account.current_balance) : ""
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (balance === "") return;
    setSaving(true);
    setError(null);
    try {
      await recordAccountBalance(account.id, asOfDate, Number(balance));
      setEditing(false);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save balance");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="border-t border-slate-100 pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-slate-700">{account.name}</p>
          <p className="text-xs text-slate-400">{TYPE_LABELS[account.account_type]}</p>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold text-slate-800">
            {account.current_balance !== null ? formatSignedCurrency(account.current_balance) : "—"}
          </p>
          <p className="text-xs text-slate-400">
            {account.balance_is_estimated
              ? "estimated from transactions"
              : account.balance_as_of
              ? `as of ${account.balance_as_of}`
              : "no balance recorded"}
          </p>
        </div>
      </div>

      {editing ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-xs"
          />
          <input
            type="number"
            step="0.01"
            placeholder="Balance"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
            className="w-32 rounded-md border border-slate-300 px-2 py-1 text-xs"
          />
          <button
            onClick={handleSave}
            disabled={saving || balance === ""}
            className="rounded-md bg-brand-500 px-2 py-1 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
          <button
            onClick={() => setEditing(false)}
            className="text-xs text-slate-400 hover:text-slate-600"
          >
            Cancel
          </button>
          {error && <span className="text-xs text-red-600">{error}</span>}
        </div>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="mt-1 text-xs font-medium text-brand-600 hover:text-brand-700"
        >
          Update balance
        </button>
      )}
    </div>
  );
}
