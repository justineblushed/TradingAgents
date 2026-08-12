"use client";

import { useEffect, useState } from "react";
import {
  ACCOUNT_TYPE_HINTS,
  ACCOUNT_TYPE_LABELS,
  AccountType,
  AccountWithBalance,
  ASSET_ACCOUNT_TYPES,
  LIABILITY_ACCOUNT_TYPES,
  NetWorthSummary,
  createAccount,
  deleteAccount,
  getNetWorthSummary,
  moveAccount,
  recordAccountBalance,
  updateAccount,
} from "@/lib/api";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";

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
        <AccountGroup title="Assets" accounts={assets} onSaved={load} onError={setMessage} />
        <AccountGroup
          title="Liabilities"
          accounts={liabilities}
          onSaved={load}
          onError={setMessage}
        />
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
                  {ACCOUNT_TYPE_LABELS[t]}
                </option>
              ))}
            </optgroup>
            <optgroup label="Liabilities">
              {LIABILITY_ACCOUNT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {ACCOUNT_TYPE_LABELS[t]}
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
        <p className="mt-2 text-xs text-slate-400">{ACCOUNT_TYPE_HINTS[newType]}</p>
      </div>
    </div>
  );
}

function NetWorthHeader({ summary }: { summary: NetWorthSummary }) {
  const deltaKnown = summary.delta !== null;
  const deltaUp = deltaKnown && (summary.delta ?? 0) >= 0;
  const partialCoverage =
    deltaKnown && summary.accounts_with_history < summary.accounts_total;
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
      {partialCoverage && (
        <p className="mt-1 text-xs text-slate-400">
          Based on the {summary.accounts_with_history} of {summary.accounts_total}{" "}
          account(s) with a balance recorded before this month — an account
          getting its first-ever balance this month (like a mortgage entered
          for the first time) has no fair "last month" to compare against, so
          it's left out of this figure rather than counted as a swing.
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
  onError,
}: {
  title: string;
  accounts: AccountWithBalance[];
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-medium text-slate-600">{title}</h2>
      {accounts.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-400">No accounts yet.</p>
      ) : (
        <div className="space-y-3">
          {accounts.map((a, i) => (
            <AccountRow
              key={a.id}
              account={a}
              isFirst={i === 0}
              isLast={i === accounts.length - 1}
              onSaved={onSaved}
              onError={onError}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function AccountRow({
  account,
  isFirst,
  isLast,
  onSaved,
  onError,
}: {
  account: AccountWithBalance;
  isFirst: boolean;
  isLast: boolean;
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const [editingBalance, setEditingBalance] = useState(false);
  const [asOfDate, setAsOfDate] = useState(todayIso());
  const [balance, setBalance] = useState(
    account.current_balance !== null ? String(account.current_balance) : ""
  );
  const [savingBalance, setSavingBalance] = useState(false);
  const [balanceError, setBalanceError] = useState<string | null>(null);

  const [editingInfo, setEditingInfo] = useState(false);
  const [editName, setEditName] = useState(account.name);
  const [editType, setEditType] = useState<AccountType>(account.account_type);
  const [savingInfo, setSavingInfo] = useState(false);
  const [infoError, setInfoError] = useState<string | null>(null);

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [moving, setMoving] = useState(false);

  async function handleSaveBalance() {
    if (balance === "") return;
    setSavingBalance(true);
    setBalanceError(null);
    try {
      await recordAccountBalance(account.id, asOfDate, Number(balance));
      setEditingBalance(false);
      onSaved();
    } catch (err) {
      setBalanceError(err instanceof Error ? err.message : "Failed to save balance");
    } finally {
      setSavingBalance(false);
    }
  }

  async function handleSaveInfo() {
    if (!editName.trim()) return;
    setSavingInfo(true);
    setInfoError(null);
    try {
      await updateAccount(account.id, { name: editName.trim(), account_type: editType });
      setEditingInfo(false);
      onSaved();
    } catch (err) {
      setInfoError(err instanceof Error ? err.message : "Failed to save changes");
    } finally {
      setSavingInfo(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteAccount(account.id);
      onSaved();
    } catch (err) {
      setConfirmingDelete(false);
      onError(err instanceof Error ? err.message : "Failed to delete account");
    } finally {
      setDeleting(false);
    }
  }

  async function handleMove(direction: "up" | "down") {
    setMoving(true);
    try {
      await moveAccount(account.id, direction);
      onSaved();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to reorder account");
    } finally {
      setMoving(false);
    }
  }

  return (
    <div className="border-t border-slate-100 pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <div className="flex flex-col">
            <button
              onClick={() => handleMove("up")}
              disabled={isFirst || moving}
              aria-label={`Move ${account.name} up`}
              className="text-slate-300 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-30"
            >
              ▲
            </button>
            <button
              onClick={() => handleMove("down")}
              disabled={isLast || moving}
              aria-label={`Move ${account.name} down`}
              className="text-slate-300 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-30"
            >
              ▼
            </button>
          </div>
          <div>
            <p className="text-sm font-medium text-slate-700">{account.name}</p>
            <p className="text-xs text-slate-400">{ACCOUNT_TYPE_LABELS[account.account_type]}</p>
          </div>
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

      {editingBalance ? (
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
            onClick={handleSaveBalance}
            disabled={savingBalance || balance === ""}
            className="rounded-md bg-brand-500 px-2 py-1 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50"
          >
            {savingBalance ? "Saving…" : "Save"}
          </button>
          <button
            onClick={() => setEditingBalance(false)}
            className="text-xs text-slate-400 hover:text-slate-600"
          >
            Cancel
          </button>
          {balanceError && <span className="text-xs text-red-600">{balanceError}</span>}
        </div>
      ) : editingInfo ? (
        <div className="mt-2 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs"
            />
            <select
              value={editType}
              onChange={(e) => setEditType(e.target.value as AccountType)}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs"
            >
              {/* Deliberately offers both groups, not just the account's
                  current side — otherwise there'd be no way to fix exactly
                  the kind of mistake this form exists for: an account stuck
                  under the wrong side because it was mis-typed at creation. */}
              <optgroup label="Assets">
                {ASSET_ACCOUNT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {ACCOUNT_TYPE_LABELS[t]}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Liabilities">
                {LIABILITY_ACCOUNT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {ACCOUNT_TYPE_LABELS[t]}
                  </option>
                ))}
              </optgroup>
            </select>
            <button
              onClick={handleSaveInfo}
              disabled={savingInfo || !editName.trim()}
              className="rounded-md bg-brand-500 px-2 py-1 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50"
            >
              {savingInfo ? "Saving…" : "Save"}
            </button>
            <button
              onClick={() => {
                setEditingInfo(false);
                setEditName(account.name);
                setEditType(account.account_type);
              }}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              Cancel
            </button>
          </div>
          <p className="text-xs text-slate-400">{ACCOUNT_TYPE_HINTS[editType]}</p>
          {infoError && <p className="text-xs text-red-600">{infoError}</p>}
        </div>
      ) : confirmingDelete ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-600">Delete this account?</span>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Yes, delete"}
          </button>
          <button
            onClick={() => setConfirmingDelete(false)}
            className="text-xs text-slate-400 hover:text-slate-600"
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="mt-1 flex items-center gap-3">
          <button
            onClick={() => setEditingBalance(true)}
            className="text-xs font-medium text-brand-600 hover:text-brand-700"
          >
            Update balance
          </button>
          <button
            onClick={() => setEditingInfo(true)}
            className="text-xs font-medium text-slate-500 hover:text-slate-700"
          >
            Edit
          </button>
          <button
            onClick={() => setConfirmingDelete(true)}
            className="text-xs font-medium text-slate-400 hover:text-red-600"
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
