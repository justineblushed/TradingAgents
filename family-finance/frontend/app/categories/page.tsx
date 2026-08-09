"use client";

import { useEffect, useState } from "react";
import {
  Category,
  createCategory,
  deleteCategory,
  listCategories,
  updateCategoryKeywords,
} from "@/lib/api";

export default function CategoriesPage() {
  const [categories, setCategories] = useState<Category[] | null>(null);
  const [keywordDrafts, setKeywordDrafts] = useState<Record<number, string>>({});
  const [savingId, setSavingId] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [newIsIncome, setNewIsIncome] = useState(false);
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
      await createCategory(newName.trim(), newIsIncome);
      setNewName("");
      setNewIsIncome(false);
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

  const expense = categories?.filter((c) => !c.is_income) ?? [];
  const income = categories?.filter((c) => c.is_income) ?? [];

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
          <label className="flex items-center gap-1.5 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={newIsIncome}
              onChange={(e) => setNewIsIncome(e.target.checked)}
            />
            Income category
          </label>
          <button
            onClick={handleAddCategory}
            disabled={!newName.trim()}
            className="rounded-md bg-brand-500 px-3 py-1 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            Add
          </button>
        </div>
      </div>

      {message && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{message}</p>
      )}

      {categories === null ? (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      ) : (
        <>
          <CategoryGroup
            title="Expense categories"
            categories={expense}
            keywordDrafts={keywordDrafts}
            setKeywordDrafts={setKeywordDrafts}
            savingId={savingId}
            onSave={handleSaveKeywords}
            onDelete={handleDelete}
          />
          <CategoryGroup
            title="Income categories"
            categories={income}
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
}: {
  title: string;
  categories: Category[];
  keywordDrafts: Record<number, string>;
  setKeywordDrafts: React.Dispatch<React.SetStateAction<Record<number, string>>>;
  savingId: number | null;
  onSave: (c: Category) => void;
  onDelete: (c: Category) => void;
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
