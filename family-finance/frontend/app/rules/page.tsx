"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Account,
  Category,
  RULE_SCOPE_LABELS,
  Rule,
  RuleApplyResult,
  RuleInput,
  RuleScope,
  applyRules,
  createRule,
  deleteRule,
  listAccounts,
  listCategories,
  listRules,
  updateRule,
} from "@/lib/api";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";
import { CategoryOptions } from "../category-select";

function emptyRule(): RuleInput {
  return {
    keyword: "",
    category: "",
    min_amount: null,
    max_amount: null,
    account_id: null,
    priority: 0,
    tags: [],
  };
}

function conditionSummary(rule: Rule): string {
  const parts: string[] = [];
  if (rule.min_amount !== null && rule.max_amount !== null) {
    parts.push(
      `${formatCurrency(rule.min_amount)}–${formatCurrency(rule.max_amount)}`
    );
  } else if (rule.min_amount !== null) {
    parts.push(`≥ ${formatCurrency(rule.min_amount)}`);
  } else if (rule.max_amount !== null) {
    parts.push(`≤ ${formatCurrency(rule.max_amount)}`);
  }
  if (rule.account_name) parts.push(`on ${rule.account_name}`);
  if (rule.priority) parts.push(`priority ${rule.priority}`);
  return parts.join(" · ");
}

export default function RulesPage() {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [draft, setDraft] = useState<RuleInput | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [tagsText, setTagsText] = useState("");

  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const [scope, setScope] = useState<RuleScope>("uncategorized");
  const [preview, setPreview] = useState<RuleApplyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setRules(await listRules());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load rules");
    }
  }, []);

  useEffect(() => {
    reload();
    listCategories().then(setCategories).catch(() => {});
    listAccounts().then(setAccounts).catch(() => {});
  }, [reload]);

  function startNew() {
    const blank = emptyRule();
    blank.category = categories[0]?.name ?? "";
    setDraft(blank);
    setEditingId(null);
    setTagsText("");
    setMessage(null);
    setError(null);
  }

  function startEdit(rule: Rule) {
    setDraft({
      keyword: rule.keyword,
      category: rule.category,
      min_amount: rule.min_amount,
      max_amount: rule.max_amount,
      account_id: rule.account_id,
      priority: rule.priority,
      tags: rule.tags,
    });
    setEditingId(rule.id);
    setTagsText(rule.tags.join(", "));
    setMessage(null);
    setError(null);
  }

  function setField<K extends keyof RuleInput>(key: K, value: RuleInput[K]) {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function handleSave() {
    if (!draft) return;
    if (!draft.keyword.trim()) {
      setError("A keyword is required — that's what the rule matches on.");
      return;
    }
    if (!draft.category) {
      setError("Pick the category this rule should file into.");
      return;
    }
    const payload: RuleInput = {
      ...draft,
      keyword: draft.keyword.trim(),
      tags: tagsText
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    };
    setBusy(true);
    setError(null);
    try {
      if (editingId === null) await createRule(payload);
      else await updateRule(editingId, payload);
      setDraft(null);
      setEditingId(null);
      await reload();
      // A changed rule invalidates any preview taken before it.
      setPreview(null);
      setMessage("Rule saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save rule");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(rule: Rule) {
    setBusy(true);
    try {
      await deleteRule(rule.id);
      if (editingId === rule.id) {
        setDraft(null);
        setEditingId(null);
      }
      setPreview(null);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete rule");
    } finally {
      setBusy(false);
    }
  }

  async function handlePreview() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setPreview(await applyRules(scope, true));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to preview");
    } finally {
      setBusy(false);
    }
  }

  async function handleApply() {
    setBusy(true);
    setError(null);
    try {
      const result = await applyRules(scope, false);
      setPreview(null);
      setMessage(
        `Re-filed ${result.changed} transaction${
          result.changed === 1 ? "" : "s"
        }.${
          result.protected_manual > 0
            ? ` ${result.protected_manual} left alone because you set them by hand.`
            : ""
        }`
      );
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to apply rules");
    } finally {
      setBusy(false);
    }
  }

  // With the default taxonomy seeded there are well over a hundred rules, so
  // the list is searchable and collapsed by category — a flat dump buries
  // everything else on the page.
  const query = search.trim().toLowerCase();
  const visible = (rules ?? []).filter(
    (r) =>
      !query ||
      r.keyword.toLowerCase().includes(query) ||
      r.category.toLowerCase().includes(query)
  );
  const grouped = visible.reduce<Record<string, Rule[]>>((acc, rule) => {
    (acc[rule.category] ??= []).push(rule);
    return acc;
  }, {});

  function sectionOpen(category: string): boolean {
    // Searching implies you want to see what matched.
    return query.length > 0 || expanded.has(category);
  }

  function toggleSection(category: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">
            Auto-categorization rules
          </h1>
          <p className="mt-1 max-w-2xl text-xs text-slate-500">
            A rule files a transaction automatically when its keyword appears
            in the description. The optional amount and account conditions
            narrow it — useful when one merchant means two things, like a
            small annual membership fee versus a big grocery run at the same
            store. When several rules match, the most specific one wins.
          </p>
        </div>
        <button
          onClick={startNew}
          className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
        >
          + New rule
        </button>
      </div>

      {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {message && (
        <p className="rounded-md bg-brand-50 p-3 text-sm text-brand-700">{message}</p>
      )}

      {/* Rule editor */}
      {draft && (
        <div className="rounded-xl border border-brand-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-medium text-slate-600">
            {editingId === null ? "New rule" : "Edit rule"}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label className="block text-xs text-slate-500">
                Description contains
              </label>
              <input
                value={draft.keyword}
                onChange={(e) => setField("keyword", e.target.value)}
                placeholder="e.g. costco"
                className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              />
              <p className="mt-1 text-xs text-slate-400">
                Case doesn&apos;t matter; matched anywhere in the line.
              </p>
            </div>
            <div>
              <label className="block text-xs text-slate-500">File into</label>
              <select
                value={draft.category}
                onChange={(e) => setField("category", e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="">Choose a category…</option>
                <CategoryOptions categories={categories} />
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500">
                Only on this account
              </label>
              <select
                value={draft.account_id ?? ""}
                onChange={(e) =>
                  setField("account_id", e.target.value ? Number(e.target.value) : null)
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="">Any account</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500">
                Amount at least
              </label>
              <input
                type="number"
                step="0.01"
                value={draft.min_amount ?? ""}
                onChange={(e) =>
                  setField("min_amount", e.target.value ? Number(e.target.value) : null)
                }
                placeholder="any"
                className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500">Amount at most</label>
              <input
                type="number"
                step="0.01"
                value={draft.max_amount ?? ""}
                onChange={(e) =>
                  setField("max_amount", e.target.value ? Number(e.target.value) : null)
                }
                placeholder="any"
                className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              />
              <p className="mt-1 text-xs text-slate-400">
                Compared to the size of the charge, so it covers refunds too.
              </p>
            </div>
            <div>
              <label className="block text-xs text-slate-500">
                Also tag with (comma separated)
              </label>
              <input
                value={tagsText}
                onChange={(e) => setTagsText(e.target.value)}
                placeholder="e.g. pets, vet"
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
              Save rule
            </button>
            <button
              onClick={() => {
                setDraft(null);
                setEditingId(null);
              }}
              className="text-sm text-slate-500 hover:text-slate-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Retroactive run */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-medium text-slate-600">
          Run rules on transactions already imported
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Rules normally only run at import time. This applies them backwards
          over what&apos;s already in the database. Always preview first —
          nothing is written until you confirm.
        </p>

        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-slate-500">What to touch</label>
            <select
              value={scope}
              onChange={(e) => {
                setScope(e.target.value as RuleScope);
                setPreview(null);
              }}
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
            >
              {(Object.keys(RULE_SCOPE_LABELS) as RuleScope[]).map((s) => (
                <option key={s} value={s}>
                  {RULE_SCOPE_LABELS[s]}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={handlePreview}
            disabled={busy}
            className="rounded-md border border-brand-300 px-4 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-50"
          >
            Preview changes
          </button>
        </div>

        {scope === "all" && (
          <p className="mt-3 rounded-md bg-amber-50 p-3 text-xs text-amber-800">
            This scope overwrites categories you picked by hand. Every other
            scope leaves those alone.
          </p>
        )}

        {preview && (
          <div className="mt-4">
            <div className="flex flex-wrap gap-4 text-xs text-slate-500">
              <span>
                <span className="font-semibold text-slate-800">
                  {preview.changed}
                </span>{" "}
                would change
              </span>
              <span>{preview.unchanged} already filed correctly</span>
              <span>{preview.unmatched} matched no rule</span>
              {preview.protected_manual > 0 && (
                <span>{preview.protected_manual} protected (set by hand)</span>
              )}
            </div>

            {preview.changed === 0 ? (
              <p className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-500">
                Nothing to change in this scope — your rules already agree with
                how these transactions are filed.
              </p>
            ) : (
              <>
                <div className="mt-3 max-h-96 overflow-auto rounded-md border border-slate-200">
                  <table className="w-full text-left text-sm">
                    <thead className="sticky top-0 bg-slate-50 text-xs uppercase text-slate-400">
                      <tr>
                        <th className="px-2 py-1">Date</th>
                        <th className="px-2">Description</th>
                        <th className="px-2 text-right">Amount</th>
                        <th className="px-2">From</th>
                        <th className="px-2">To</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.changes.map((c) => (
                        <tr key={c.transaction_id} className="border-t border-slate-100">
                          <td className="whitespace-nowrap px-2 py-1 text-slate-500">
                            {c.trans_date}
                          </td>
                          <td className="max-w-xs truncate px-2">{c.description}</td>
                          <td className="px-2 text-right">
                            {formatSignedCurrency(c.amount)}
                          </td>
                          <td className="px-2 text-slate-500">
                            {c.from_category ?? "Uncategorized"}
                            {c.from_source === "manual" && (
                              <span className="ml-1 text-xs text-amber-700">
                                (by hand)
                              </span>
                            )}
                          </td>
                          <td className="px-2 font-medium text-slate-800">
                            {c.to_category}
                            {c.tags_added.length > 0 && (
                              <span className="ml-1 text-xs text-slate-400">
                                +{c.tags_added.join(", ")}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <button
                  onClick={handleApply}
                  disabled={busy}
                  className="mt-3 rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
                >
                  Apply these {preview.changed} change
                  {preview.changed === 1 ? "" : "s"}
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Rule list */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium text-slate-600">
            {rules === null
              ? "Rules"
              : query
              ? `${visible.length} of ${rules.length} rules`
              : `${rules.length} rules`}
          </h2>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search keyword or category…"
            className="w-64 rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
        {rules !== null && rules.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-400">
            No rules yet. Add one above, or add keywords from the Categories
            page — they become rules too.
          </p>
        )}
        {rules !== null && rules.length > 0 && visible.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-400">
            No rule matches “{search}”.
          </p>
        )}
        <div className="divide-y divide-slate-100">
          {Object.entries(grouped).map(([category, categoryRules]) => (
            <div key={category} className="py-1">
              <button
                onClick={() => toggleSection(category)}
                aria-expanded={sectionOpen(category)}
                className="flex w-full items-center justify-between gap-2 py-1.5 text-left"
              >
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {category}
                </span>
                <span className="text-xs text-slate-400">
                  {categoryRules.length} rule
                  {categoryRules.length === 1 ? "" : "s"}{" "}
                  {sectionOpen(category) ? "▾" : "▸"}
                </span>
              </button>
              <div
                className={`mt-1 divide-y divide-slate-100 ${
                  sectionOpen(category) ? "" : "hidden"
                }`}
              >
                {categoryRules.map((rule) => (
                  <div
                    key={rule.id}
                    className="flex flex-wrap items-center justify-between gap-2 py-2"
                  >
                    <div className="min-w-0">
                      <p className="text-sm text-slate-700">
                        <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">
                          {rule.keyword}
                        </code>
                        {conditionSummary(rule) && (
                          <span className="ml-2 text-xs text-slate-500">
                            {conditionSummary(rule)}
                          </span>
                        )}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-400">
                        matches {rule.match_count} imported transaction
                        {rule.match_count === 1 ? "" : "s"}
                        {rule.tags.length > 0 &&
                          ` · tags: ${rule.tags.join(", ")}`}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => startEdit(rule)}
                        className="text-xs font-medium text-brand-600 hover:text-brand-700"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(rule)}
                        disabled={busy}
                        className="text-xs text-slate-400 hover:text-red-600 disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
