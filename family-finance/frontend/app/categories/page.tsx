"use client";

import { useEffect, useState } from "react";
import {
  Category,
  CategoryKind,
  GROUP_ORDER,
  createCategory,
  deleteCategory,
  listCategories,
  updateCategoryBudget,
  updateCategoryKeywords,
} from "@/lib/api";

const KIND_LABELS: Record<CategoryKind, string> = {
  expense: "Expense",
  income: "Income",
  transfer: "Transfer (excluded from spending/income)",
};

export default function CategoriesPage() {
  const [categories, setCategories] = useState<Category[] | null>(null);
  const [keywordDrafts, setKeywordDrafts] = useState<Record<number, string>>({});
  const [savingId, setSavingId] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState<CategoryKind>("expense");
  const [newGroup, setNewGroup] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  function load() {
    listCategories()
      .then((cats) => {
        setCategories(cats);
        setKeywordDrafts(
          Object.fromEntries(cats.map((c) => [c.id, c.keywords.join(", ")]))
        );
      })
      .catch((err) =>
        setMessage(err instanceof Error ? err.message : "Failed to load categories")
      );
  }

  useEffect(load, []);

  async function handleAddCategory() {
    if (!newName.trim()) return;
    setMessage(null);
    try {
      await createCategory(newName.trim(), newKind, newKind === "expense" ? newGroup : "");
      setNewName("");
      setNewKind("expense");
      setNewGroup("");
      load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to add category");
    }
  }

  async function handleSaveKeywords(category: Category) {
    const keywords = keywordDrafts[category.id]
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    setSavingId(category.id);
    setMessage(null);
    try {
      const updated = await updateCategoryKeywords(category.id, keywords);
      setCategories((prev) =>
        prev ? prev.map((c) => (c.id === category.id ? updated : c)) : prev
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save keywords");
    } finally {
      setSavingId(null);
    }
  }

  async function handleSaveBudget(category: Category, budget: number | null) {
    setMessage(null);
    try {
      const updated = await updateCategoryBudget(category.id, budget);
      setCategories((prev) =>
        prev ? prev.map((c) => (c.id === category.id ? updated : c)) : prev
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save budget");
    }
  }

  async function handleDelete(category: Category) {
    if (
      !window.confirm(
        `Delete "${category.name}"? Transactions using it will become Uncategorized instead of being deleted.`
      )
    ) {
      return;
    }
    setMessage(null);
    try {
      await deleteCategory(category.id);
      setCategories((prev) => (prev ? prev.filter((c) => c.id !== category.id) : prev));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to delete category");
    }
  }

  const expense = categories?.filter((c) => c.kind === "expense") ?? [];
  const income = categories?.filter((c) => c.kind === "income") ?? [];
  const transfer = categories?.filter((c) => c.kind === "transfer") ?? [];

  const groupNames: string[] = [
    ...GROUP_ORDER.filter((g) => expense.some((c) => c.group_name === g)),
    ...(expense.some((c) => !c.group_name || !GROUP_ORDER.includes(c.group_name as any))
      ? ["Other"]
      : []),
  ];
  const expenseByGroup = (group: string) =>
    group === "Other"
      ? expense.filter(
          (c) => !c.group_name || !GROUP_ORDER.includes(c.group_name as any)
        )
      : expense.filter((c) => c.group_name === group);

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-medium text-slate-600">Add a category</h2>
        <div className="flex flex-wrap items-end gap-3">
          <input
            placeholder="e.g. Pet care"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddCategory()}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
          <select
            value={newKind}
            onChange={(e) => setNewKind(e.target.value as CategoryKind)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          >
            {Object.entries(KIND_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          {newKind === "expense" && (
            <select
              value={newGroup}
              onChange={(e) => setNewGroup(e.target.value)}
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="">No group</option>
              {GROUP_ORDER.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={handleAddCategory}
            disabled={!newName.trim()}
            className="rounded-md bg-brand-500 px-3 py-1 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            Add
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          "Transfer" is for money moving between your own accounts — like
          paying off a credit card — never counted as spending or income.
        </p>
      </div>

      {message && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{message}</p>
      )}

      {categories === null ? (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      ) : (
        <>
          {groupNames.map((group) => (
            <CategoryGroup
              key={group}
              title={`${group} — expenses`}
              categories={expenseByGroup(group)}
              keywordDrafts={keywordDrafts}
              setKeywordDrafts={setKeywordDrafts}
              savingId={savingId}
              onSave={handleSaveKeywords}
              onDelete={handleDelete}
              showBudget
              onSaveBudget={handleSaveBudget}
            />
          ))}
          <CategoryGroup
            title="Income categories"
            categories={income}
            keywordDrafts={keywordDrafts}
            setKeywordDrafts={setKeywordDrafts}
            savingId={savingId}
            onSave={handleSaveKeywords}
            onDelete={handleDelete}
          />
          <CategoryGroup
            title="Transfer categories (excluded from spending/income)"
            categories={transfer}
            keywordDrafts={keywordDrafts}
            setKeywordDrafts={setKeywordDrafts}
            savingId={savingId}
            onSave={handleSaveKeywords}
            onDelete={handleDelete}
          />
        </>
      )}
    </div>
  );
}

function CategoryGroup({
  title,
  categories,
  keywordDrafts,
  setKeywordDrafts,
  savingId,
  onSave,
  onDelete,
  showBudget,
  onSaveBudget,
}: {
  title: string;
  categories: Category[];
  keywordDrafts: Record<number, string>;
  setKeywordDrafts: React.Dispatch<React.SetStateAction<Record<number, string>>>;
  savingId: number | null;
  onSave: (c: Category) => void;
  onDelete: (c: Category) => void;
  showBudget?: boolean;
  onSaveBudget?: (c: Category, budget: number | null) => void;
}) {
  if (categories.length === 0) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-medium text-slate-600">{title}</h2>
      <div className="space-y-3">
        {categories.map((c) => {
          const draft = keywordDrafts[c.id] ?? "";
          const dirty = draft !== c.keywords.join(", ");
          return (
            <div key={c.id} className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 first:border-t-0 first:pt-0">
              <span className="w-40 shrink-0 text-sm font-medium text-slate-700">
                {c.name}
              </span>
              <input
                value={draft}
                onChange={(e) =>
                  setKeywordDrafts((prev) => ({ ...prev, [c.id]: e.target.value }))
                }
                placeholder="keywords, comma-separated (matches transaction description)"
                className="min-w-[240px] flex-1 rounded-md border border-slate-300 px-2 py-1 text-xs"
              />
              {showBudget && onSaveBudget && (
                <BudgetInput category={c} onSave={onSaveBudget} />
              )}
              {dirty && (
                <button
                  onClick={() => onSave(c)}
                  disabled={savingId === c.id}
                  className="rounded-md bg-brand-500 px-2 py-1 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50"
                >
                  {savingId === c.id ? "Saving…" : "Save"}
                </button>
              )}
              <button
                onClick={() => onDelete(c)}
                className="text-xs text-slate-400 hover:text-red-600"
              >
                Delete
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function BudgetInput({
  category,
  onSave,
}: {
  category: Category;
  onSave: (c: Category, budget: number | null) => void;
}) {
  const [draft, setDraft] = useState(
    category.monthly_budget !== null ? String(category.monthly_budget) : ""
  );
  const saved = category.monthly_budget !== null ? String(category.monthly_budget) : "";
  const dirty = draft !== saved;

  return (
    <span className="flex items-center gap-1 text-xs text-slate-500">
      <label title="Monthly spending target — drives the health score's budget metric">
        Target $
      </label>
      <input
        type="number"
        min="0"
        step="10"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="—"
        className="w-20 rounded-md border border-slate-300 px-1.5 py-1 text-xs"
      />
      {dirty && (
        <button
          onClick={() => onSave(category, draft === "" ? null : Number(draft))}
          className="rounded-md bg-brand-500 px-2 py-1 text-xs font-medium text-white hover:bg-brand-600"
        >
          Set
        </button>
      )}
    </span>
  );
}
