"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Category,
  Tag,
  Transaction,
  TransactionKind,
  deleteTransaction,
  listCategories,
  listTags,
  listTransactions,
  setTransactionCategory,
  setTransactionTags,
} from "@/lib/api";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";
import { CategoryOptions } from "../category-select";

const KIND_LABELS: Record<"" | TransactionKind, string> = {
  "": "All",
  expense: "Spending",
  income: "Income",
};

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function TransactionsPage() {
  // useSearchParams needs a Suspense boundary for static prerendering.
  return (
    <Suspense fallback={<p className="py-16 text-center text-sm text-slate-400">Loading…</p>}>
      <TransactionsInner />
    </Suspense>
  );
}

function TransactionsInner() {
  const searchParams = useSearchParams();
  const initialMonth = /^\d{4}-\d{2}$/.test(searchParams.get("month") ?? "")
    ? (searchParams.get("month") as string)
    : currentMonth();
  const [month, setMonth] = useState(initialMonth);
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagFilter, setTagFilter] = useState("");
  const initialKind = searchParams.get("kind");
  const [kindFilter, setKindFilter] = useState<"" | TransactionKind>(
    initialKind === "expense" || initialKind === "income" ? initialKind : ""
  );
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  // A transaction landed on from elsewhere (the Duplicates page, say) that
  // should be scrolled to and visually picked out of the list.
  const highlightId = Number(searchParams.get("highlight")) || null;
  const rowRefs = useRef<Map<number, HTMLTableRowElement>>(new Map());

  function loadTags() {
    listTags()
      .then(setTags)
      .catch((e) => setError(e.message));
  }

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch((e) => setError(e.message));
    loadTags();
  }, []);

  useEffect(() => {
    setTransactions(null);
    // A tag spans months (a trip crosses month boundaries), so filtering by
    // one drops the month filter rather than intersecting the two.
    listTransactions(
      tagFilter ? undefined : month,
      tagFilter || undefined,
      kindFilter || undefined
    )
      .then(setTransactions)
      .catch((e) => setError(e.message));
  }, [month, tagFilter, kindFilter]);

  useEffect(() => {
    if (!highlightId || !transactions) return;
    const row = rowRefs.current.get(highlightId);
    row?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightId, transactions]);

  const activeTag = tags.find((t) => t.name === tagFilter) ?? null;

  const uncategorizedCount = useMemo(
    () => (transactions ?? []).filter((t) => !t.category).length,
    [transactions]
  );

  async function handleCategoryChange(transactionId: number, categoryName: string) {
    if (!transactions) return;
    const previous = transactions;
    // Optimistic update so the dropdown feels instant; rolled back on failure.
    setTransactions(
      transactions.map((t) =>
        t.id === transactionId ? { ...t, category: categoryName } : t
      )
    );
    setSavingId(transactionId);
    setError(null);
    try {
      await setTransactionCategory(transactionId, categoryName);
    } catch (err) {
      setTransactions(previous);
      setError(
        err instanceof Error ? err.message : "Failed to save category change"
      );
    } finally {
      setSavingId(null);
    }
  }

  async function handleDelete(transaction: Transaction) {
    const confirmed = window.confirm(
      `Delete this transaction?\n\n${transaction.trans_date} · ${transaction.description} · ${formatSignedCurrency(
        transaction.amount
      )}\n\nThis can't be undone.`
    );
    if (!confirmed) return;
    setDeletingId(transaction.id);
    setError(null);
    try {
      await deleteTransaction(transaction.id);
      setTransactions((prev) => (prev ? prev.filter((t) => t.id !== transaction.id) : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete transaction");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleTagsChange(transactionId: number, nextTags: string[]) {
    setSavingId(transactionId);
    setError(null);
    try {
      const updated = await setTransactionTags(transactionId, nextTags);
      setTransactions((prev) =>
        prev ? prev.map((t) => (t.id === transactionId ? updated : t)) : prev
      );
      loadTags();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save tags");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm font-medium text-slate-600">Month</label>
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            disabled={!!tagFilter}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm disabled:bg-slate-100 disabled:text-slate-400"
          />
          <label className="text-sm font-medium text-slate-600">Tag</label>
          <select
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="">All (by month)</option>
            {tags.map((t) => (
              <option key={t.id} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
          <label className="text-sm font-medium text-slate-600">Kind</label>
          <select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value as "" | TransactionKind)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          >
            {(Object.keys(KIND_LABELS) as ("" | TransactionKind)[]).map((k) => (
              <option key={k} value={k}>
                {KIND_LABELS[k]}
              </option>
            ))}
          </select>
        </div>
        {transactions && transactions.length > 0 && (
          <p className="text-sm text-slate-500">
            {transactions.length} transaction{transactions.length === 1 ? "" : "s"}
            {uncategorizedCount > 0 && (
              <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                {uncategorizedCount} uncategorized
              </span>
            )}
          </p>
        )}
      </div>

      {error && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}

      {activeTag && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-brand-100 bg-brand-50 p-3 text-sm">
          <span className="text-slate-700">
            <span className="font-semibold">{activeTag.name}</span> across all
            months — {activeTag.transaction_count} transaction
            {activeTag.transaction_count === 1 ? "" : "s"}
          </span>
          <span className="font-semibold text-brand-700">
            {formatCurrency(activeTag.total_spent)} spent
          </span>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        {transactions === null ? (
          <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
        ) : transactions.length === 0 ? (
          <p className="py-16 text-center text-sm text-slate-400">
            No transactions for this month — upload a statement to get started.
          </p>
        ) : (
          <div className="max-h-[600px] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-white text-xs uppercase text-slate-400">
                <tr>
                  <th className="py-1">Date</th>
                  <th>Description</th>
                  <th className="text-right">Amount</th>
                  <th>Category</th>
                  <th>Tags</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr
                    key={t.id}
                    ref={(el) => {
                      if (el) rowRefs.current.set(t.id, el);
                      else rowRefs.current.delete(t.id);
                    }}
                    className={`border-t border-slate-100 ${
                      t.id === highlightId ? "bg-amber-50 ring-2 ring-inset ring-amber-300" : ""
                    }`}
                  >
                    <td className="py-1.5 pr-2 text-slate-500">{t.trans_date}</td>
                    <td className="pr-2">{t.description}</td>
                    <td
                      className={`pr-2 text-right ${
                        t.amount < 0 ? "text-green-600" : "text-slate-800"
                      }`}
                    >
                      {formatSignedCurrency(t.amount)}
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <span
                          aria-hidden
                          title={t.category ?? "Uncategorized"}
                          className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                          style={{
                            backgroundColor:
                              categories.find((c) => c.name === t.category)?.color ||
                              "#cbd5e1",
                          }}
                        />
                        <select
                          value={t.category ?? ""}
                          onChange={(e) => handleCategoryChange(t.id, e.target.value)}
                          className={`rounded-md border px-1 py-0.5 text-xs ${
                            t.category
                              ? "border-slate-300"
                              : "border-amber-300 bg-amber-50"
                          }`}
                        >
                          {!t.category && <option value="">Uncategorized</option>}
                          <CategoryOptions categories={categories} />
                        </select>
                        {savingId === t.id && (
                          <span className="text-xs text-slate-400">Saving…</span>
                        )}
                      </div>
                    </td>
                    <td className="pl-2">
                      <TagCell
                        transaction={t}
                        allTags={tags}
                        onChange={(next) => handleTagsChange(t.id, next)}
                      />
                    </td>
                    <td className="pl-2 text-right">
                      <button
                        onClick={() => handleDelete(t)}
                        disabled={deletingId === t.id}
                        title="Delete this transaction"
                        className="text-xs font-medium text-slate-400 hover:text-red-600 disabled:opacity-50"
                      >
                        {deletingId === t.id ? "Deleting…" : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function TagCell({
  transaction,
  allTags,
  onChange,
}: {
  transaction: Transaction;
  allTags: Tag[];
  onChange: (tags: string[]) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");

  function commit() {
    const name = draft.trim();
    setDraft("");
    setAdding(false);
    if (!name || transaction.tags.includes(name)) return;
    onChange([...transaction.tags, name]);
  }

  return (
    <div className="flex flex-wrap items-center gap-1">
      {transaction.tags.map((name) => (
        <span
          key={name}
          className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
        >
          {name}
          <button
            onClick={() => onChange(transaction.tags.filter((t) => t !== name))}
            title={`Remove ${name}`}
            className="text-slate-400 hover:text-red-600"
          >
            ×
          </button>
        </span>
      ))}
      {adding ? (
        <input
          autoFocus
          list="tag-options"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setDraft("");
              setAdding(false);
            }
          }}
          placeholder="e.g. Chicago Trip"
          className="w-32 rounded-md border border-slate-300 px-1.5 py-0.5 text-xs"
        />
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="rounded-full border border-dashed border-slate-300 px-2 py-0.5 text-xs text-slate-400 hover:border-brand-400 hover:text-brand-600"
        >
          + tag
        </button>
      )}
      <datalist id="tag-options">
        {allTags.map((t) => (
          <option key={t.id} value={t.name} />
        ))}
      </datalist>
    </div>
  );
}
