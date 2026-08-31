"use client";

import { useEffect, useState } from "react";
import {
  ACCOUNT_TYPE_HINTS,
  ACCOUNT_TYPE_LABELS,
  Account,
  AccountType,
  ASSET_ACCOUNT_TYPES,
  Category,
  LIABILITY_ACCOUNT_TYPES,
  ParsedTransaction,
  confirmStatement,
  createAccount,
  listAccounts,
  listCategories,
  previewStatement,
  updateAccount,
} from "@/lib/api";
import { formatSignedCurrency } from "@/lib/format";
import { CategoryOptions } from "./category-select";

export default function UploadForm({
  initialAccountId,
  onImported,
}: {
  initialAccountId?: number;
  onImported?: () => void;
}) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountId, setAccountId] = useState<number | null>(initialAccountId ?? null);
  const [newAccountName, setNewAccountName] = useState("");
  const [newAccountType, setNewAccountType] = useState<AccountType | "">("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [statementYear, setStatementYear] = useState(new Date().getFullYear());
  const [periodLabel, setPeriodLabel] = useState("");
  // The file itself is kept (not just its parsed result) so choosing or
  // adding an account after the fact — or correcting the statement year —
  // can re-parse it instead of leaving a stale preview in place.
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [transactions, setTransactions] = useState<ParsedTransaction[] | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  // Whether this file's single-Amount-column CSV had its signs flipped —
  // null when there was no such decision (a PDF, or separate debit/credit
  // columns). Carried into confirmStatement so a first-ever decision for
  // this account gets locked in, instead of re-guessed on every import.
  const [signFlipApplied, setSignFlipApplied] = useState<boolean | null>(null);
  // True when this file parsed as a credit-card PDF statement — used to
  // warn if the selected account isn't typed as a credit card, the exact
  // mix-up of a card statement landing on the wrong account by accident.
  const [isCreditCardStatement, setIsCreditCardStatement] = useState(false);
  const [mismatchAcknowledged, setMismatchAcknowledged] = useState(false);
  // The account number the statement itself reports, when it does (credit
  // card statements usually carry one). Used to auto-pick a matching
  // account, and remembered on that account after a successful import so
  // the next statement from it can be matched the same way.
  const [accountLastFour, setAccountLastFour] = useState("");
  const [phase, setPhase] = useState<"idle" | "parsing" | "importing">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [duplicateInfo, setDuplicateInfo] = useState<{
    duplicates: number;
    total: number;
  } | null>(null);
  const [showAddAccount, setShowAddAccount] = useState(false);
  const busy = phase !== "idle";
  const selectedAccount = accounts.find((a) => a.id === accountId) ?? null;
  const showMismatchWarning =
    isCreditCardStatement &&
    !!selectedAccount &&
    selectedAccount.account_type !== "credit_card";
  // With zero accounts there's nothing to pick from, so skip the dropdown
  // entirely and go straight to the add-account form instead of showing it
  // empty and making the user find a toggle to reveal the only usable path.
  const addAccountVisible = accounts.length === 0 || showAddAccount;

  useEffect(() => {
    listAccounts()
      .then((accts) => {
        setAccounts(accts);
        if (initialAccountId && accts.some((a) => a.id === initialAccountId)) {
          setAccountId(initialAccountId);
        }
      })
      .catch((err) =>
        setMessage(err instanceof Error ? err.message : "Failed to load accounts")
      );
    listCategories()
      .then(setCategories)
      .catch((err) =>
        setMessage(err instanceof Error ? err.message : "Failed to load categories")
      );
  }, [initialAccountId]);

  // Runs (or re-runs) the preview for whatever file is currently selected.
  // accId is passed explicitly rather than read from state so a caller can
  // preview with an account that was *just* chosen or created, before the
  // state update has necessarily settled.
  async function runPreview(file: File, accId: number | null, year: number) {
    setPhase("parsing");
    setMessage(null);
    setDuplicateInfo(null);
    try {
      const preview = await previewStatement(file, year, accId ?? undefined);
      setTransactions(preview.transactions);
      setWarnings(preview.warnings);
      setSignFlipApplied(preview.flip_amount_sign_applied);
      setIsCreditCardStatement(preview.is_credit_card_statement);
      setAccountLastFour(preview.account_last_four);
      setMismatchAcknowledged(false);

      // No account was chosen for this parse — if the statement itself
      // names an account number that matches one already on file, pick it
      // automatically instead of leaving the user to find it by hand.
      if (accId === null && preview.account_last_four) {
        const matched = accounts.find((a) => a.last_four === preview.account_last_four);
        if (matched) {
          setAccountId(matched.id);
          await runPreview(file, matched.id, year);
          return;
        }
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to parse statement");
    } finally {
      setPhase("idle");
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Reset the input so picking the same file again still fires onChange
    // (browsers suppress it when the value hasn't changed — without this,
    // re-uploading the same statement after an import does nothing).
    e.target.value = "";
    if (!file) return;
    setSelectedFile(file);
    await runPreview(file, accountId, statementYear);
  }

  async function handleAccountChange(newId: number) {
    setAccountId(newId);
    setMismatchAcknowledged(false);
    if (selectedFile) {
      await runPreview(selectedFile, newId, statementYear);
    }
  }

  async function handleYearChange(newYear: number) {
    setStatementYear(newYear);
    if (selectedFile) {
      await runPreview(selectedFile, accountId, newYear);
    }
  }

  async function handleCreateAccount() {
    if (!newAccountName.trim() || !newAccountType) return;
    setMessage(null);
    try {
      const account = await createAccount({
        name: newAccountName,
        account_type: newAccountType,
      });
      setAccounts((prev) => [...prev, account]);
      setNewAccountName("");
      setNewAccountType("");
      setShowAddAccount(false);
      await handleAccountChange(account.id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to create account");
    }
  }

  function updateCategory(index: number, category: string) {
    setTransactions((prev) =>
      prev
        ? prev.map((t, i) => (i === index ? { ...t, suggested_category: category } : t))
        : prev
    );
  }

  async function handleConfirm(onDuplicate: "block" | "skip" | "import" = "block") {
    if (!accountId || !transactions) return;
    setPhase("importing");
    setMessage(null);
    if (onDuplicate !== "block") setDuplicateInfo(null);
    try {
      const result = await confirmStatement(
        accountId,
        periodLabel,
        transactions,
        onDuplicate,
        signFlipApplied
      );
      if (result.status === "duplicates") {
        setDuplicateInfo({ duplicates: result.duplicates, total: result.total });
      } else {
        setDuplicateInfo(null);
        setMessage(
          result.skipped_duplicates > 0
            ? `Imported ${result.imported} new transactions (skipped ${result.skipped_duplicates} duplicates).`
            : `Imported ${result.imported} transactions.`
        );
        // Remember this account's number for next time, so a future
        // statement from it can be matched automatically instead of
        // picked by hand again.
        if (accountLastFour && selectedAccount && !selectedAccount.last_four) {
          try {
            const updated = await updateAccount(accountId, { last_four: accountLastFour });
            setAccounts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
          } catch {
            // Non-critical — the import itself already succeeded.
          }
        }
        setTransactions(null);
        setSelectedFile(null);
        onImported?.();
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to import");
    } finally {
      setPhase("idle");
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-medium text-slate-600">1. Statement file</h2>

        <label
          className={`inline-block rounded-md px-4 py-2 text-sm font-medium text-white ${
            busy
              ? "cursor-not-allowed bg-slate-300"
              : "cursor-pointer bg-brand-500 hover:bg-brand-600"
          }`}
        >
          Choose PDF or CSV
          <input
            type="file"
            accept="application/pdf,.pdf,text/csv,.csv"
            onChange={handleFileChange}
            className="hidden"
            disabled={busy}
          />
        </label>
        {phase === "parsing" && (
          <p className="mt-2 flex items-center gap-2 text-xs font-medium text-brand-700">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-brand-300 border-t-brand-700" />
            Parsing statement…
          </p>
        )}
        <p className="mt-3 text-xs text-slate-400">
          Files are parsed locally by your own backend and never saved to disk —
          only the transactions you confirm below get stored. CSVs need a date
          column, a description/details column, and either an amount column or
          funds out / funds in columns; a category column is used for
          suggestions when present. You'll pick the account next, once
          there's something to preview.
        </p>
      </div>

      {message && (
        <p className="rounded-md bg-brand-50 p-3 text-sm text-brand-700">{message}</p>
      )}

      {transactions !== null && (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-medium text-slate-600">2. Account</h2>

            {accounts.length > 0 && (
              <div className="flex flex-wrap items-end gap-4">
                <div>
                  <label className="block text-xs text-slate-500">
                    Which account is this statement for?
                  </label>
                  <select
                    value={accountId ?? ""}
                    onChange={(e) => handleAccountChange(Number(e.target.value))}
                    className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                  >
                    {!accountId && <option value="">Choose an account…</option>}
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </div>
                {!addAccountVisible && (
                  <button
                    onClick={() => setShowAddAccount(true)}
                    className="text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    + Add a new account
                  </button>
                )}
              </div>
            )}

            {accountId && accountLastFour && selectedAccount?.last_four === accountLastFour && (
              <p className="mt-1 text-xs text-green-700">
                Matched by account number ({accountLastFour}) to a statement you've
                imported here before.
              </p>
            )}

            {addAccountVisible && (
              <div className={accounts.length > 0 ? "mt-4 border-t border-slate-100 pt-4" : ""}>
                <label className="block text-xs text-slate-500">
                  {accounts.length === 0
                    ? "You don't have any accounts yet — add your first one:"
                    : "New account name"}
                </label>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <input
                    placeholder="e.g. Rogers Mastercard"
                    value={newAccountName}
                    onChange={(e) => setNewAccountName(e.target.value)}
                    className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                    autoFocus={accounts.length === 0}
                  />
                  <select
                    value={newAccountType}
                    onChange={(e) => setNewAccountType(e.target.value as AccountType)}
                    className={`rounded-md border px-2 py-1 text-sm ${
                      newAccountType ? "border-slate-300" : "border-amber-300 bg-amber-50"
                    }`}
                  >
                    <option value="">Choose a type…</option>
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
                    onClick={handleCreateAccount}
                    disabled={!newAccountName.trim() || !newAccountType}
                    className="rounded-md bg-brand-500 px-3 py-1 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    Add
                  </button>
                  {accounts.length > 0 && (
                    <button
                      onClick={() => {
                        setShowAddAccount(false);
                        setNewAccountName("");
                        setNewAccountType("");
                      }}
                      className="text-sm text-slate-400 hover:text-slate-600"
                    >
                      Cancel
                    </button>
                  )}
                </div>
                {newAccountType ? (
                  <p className="mt-1 text-xs text-slate-400">{ACCOUNT_TYPE_HINTS[newAccountType]}</p>
                ) : (
                  <p className="mt-1 text-xs font-medium text-amber-700">
                    Pick the type that matches this account — it decides whether it
                    shows up as an asset or a liability on Net Worth, and it can't
                    be guessed correctly for you.
                  </p>
                )}
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-end gap-4 border-t border-slate-100 pt-4">
              <div>
                <label
                  className="block text-xs text-slate-500"
                  title="PDF only — CSV files carry their own dates"
                >
                  Statement year (PDF only)
                </label>
                <input
                  type="number"
                  value={statementYear}
                  onChange={(e) => handleYearChange(Number(e.target.value))}
                  className="mt-1 w-24 rounded-md border border-slate-300 px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500">Period label</label>
                <input
                  placeholder="e.g. Aug 2026"
                  value={periodLabel}
                  onChange={(e) => setPeriodLabel(e.target.value)}
                  className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                />
              </div>
            </div>
          </div>

          {warnings.length > 0 && (
            <div className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
              <p className="font-medium">Some lines were not recognized:</p>
              <ul className="mt-1 list-inside list-disc">
                {warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {showMismatchWarning && selectedAccount && (
            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">
              <p className="font-medium">
                This looks like a credit card statement, but "{selectedAccount.name}" is
                typed as {ACCOUNT_TYPE_LABELS[selectedAccount.account_type]}.
              </p>
              <p className="mt-1 text-xs text-red-700">
                Double-check the account dropdown above before importing — this is the
                exact mistake that lands a card statement on the wrong account. If a
                transaction ends up on the wrong account, undo just that import from
                its "Import history" on the Statement Log page.
              </p>
              <label className="mt-2 flex items-center gap-2 text-xs font-medium text-red-800">
                <input
                  type="checkbox"
                  checked={mismatchAcknowledged}
                  onChange={(e) => setMismatchAcknowledged(e.target.checked)}
                />
                I checked the account and want to import anyway
              </label>
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-medium text-slate-600">
              3. Review before importing ({transactions.length} transactions)
            </h2>
            <div className="max-h-[480px] overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white text-xs uppercase text-slate-400">
                  <tr>
                    <th className="py-1">Date</th>
                    <th>Description</th>
                    <th className="text-right">Amount</th>
                    <th>Category</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((t, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="py-1 pr-2 text-slate-500">{t.trans_date}</td>
                      <td className="pr-2">
                        {t.description}
                        {t.foreign_currency_note && (
                          <span className="ml-2 text-xs text-slate-400">
                            ({t.foreign_currency_note})
                          </span>
                        )}
                      </td>
                      <td
                        className={`pr-2 text-right ${
                          t.amount < 0 ? "text-green-600" : "text-slate-800"
                        }`}
                      >
                        {formatSignedCurrency(t.amount)}
                      </td>
                      <td>
                        <select
                          value={t.suggested_category ?? ""}
                          onChange={(e) => updateCategory(i, e.target.value)}
                          className={`rounded-md border px-1 py-0.5 text-xs ${
                            t.suggested_category
                              ? "border-slate-300"
                              : "border-amber-300 bg-amber-50"
                          }`}
                        >
                          {!t.suggested_category && (
                            <option value="">Uncategorized</option>
                          )}
                          <CategoryOptions categories={categories} />
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {!accountId && (
              <p className="mt-3 text-xs font-medium text-amber-700">
                Choose or add an account above before importing.
              </p>
            )}

            {duplicateInfo ? (
              <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                <p className="font-medium">
                  {duplicateInfo.duplicates} of {duplicateInfo.total} transactions
                  already exist for this account (same date, description, and
                  amount) — this looks like a re-uploaded statement.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    onClick={() => handleConfirm("skip")}
                    disabled={busy || !accountId || (showMismatchWarning && !mismatchAcknowledged)}
                    className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
                  >
                    Skip duplicates, import the rest
                  </button>
                  <button
                    onClick={() => handleConfirm("import")}
                    disabled={busy || !accountId || (showMismatchWarning && !mismatchAcknowledged)}
                    className="rounded-md border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50"
                  >
                    Import anyway (keep duplicates)
                  </button>
                  <button
                    onClick={() => setDuplicateInfo(null)}
                    disabled={busy}
                    className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => handleConfirm()}
                disabled={busy || !accountId || (showMismatchWarning && !mismatchAcknowledged)}
                className="mt-4 rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
              >
                Confirm &amp; Import
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
