"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ResponsiveContainer, Sankey, Tooltip } from "recharts";
import { SankeySummary, getSankey } from "@/lib/api";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";
import SignIssueBanner from "../sign-issue-banner";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

const NODE_WIDTH = 14;

/** A node's own colour, tinted for its outgoing flows. Recharts hands the
 *  raw node/link objects straight through as `payload`, so this reads the
 *  colour our backend already assigned — the diagram never invents its own
 *  palette, it just draws the one the dashboard and drill-down already use. */
function CashFlowNode(props: any) {
  const { x, y, width, height, payload } = props;
  const isRightEdge = payload.kind === "category" || payload.kind === "savings";
  return (
    <g
      style={{ cursor: payload.kind === "category" ? "pointer" : "default" }}
      onClick={payload.onSelect}
    >
      <rect
        x={x}
        y={y}
        width={width}
        height={Math.max(height, 1)}
        fill={payload.color}
        rx={2}
      />
      <text
        x={isRightEdge ? x + width + 8 : x - 8}
        y={y + height / 2}
        textAnchor={isRightEdge ? "start" : "end"}
        dominantBaseline="middle"
        className="fill-slate-700"
        style={{ fontSize: 12, fontWeight: payload.kind === "hub" ? 600 : 400 }}
      >
        {payload.name}
      </text>
      <text
        x={isRightEdge ? x + width + 8 : x - 8}
        y={y + height / 2 + 14}
        textAnchor={isRightEdge ? "start" : "end"}
        className="fill-slate-400"
        style={{ fontSize: 11 }}
      >
        {formatCurrency(payload.value ?? 0)}
      </text>
    </g>
  );
}

function CashFlowLink(props: any) {
  const {
    sourceX,
    sourceY,
    sourceControlX,
    targetX,
    targetY,
    targetControlX,
    linkWidth,
    payload,
  } = props;
  return (
    <path
      d={`M${sourceX},${sourceY} C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}`}
      fill="none"
      stroke={payload.source.color}
      strokeOpacity={0.35}
      strokeWidth={Math.max(linkWidth, 1)}
    />
  );
}

export default function CashFlowPage() {
  const router = useRouter();
  const [month, setMonth] = useState(currentMonth());
  const [data, setData] = useState<SankeySummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    getSankey(month)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [month]);

  // Attach each node's own flow total and a click handler before handing the
  // data to Recharts — it passes both straight back through `payload`.
  const chartData = useMemo(() => {
    if (!data) return null;
    const incoming = data.nodes.map(() => 0);
    const outgoing = data.nodes.map(() => 0);
    for (const link of data.links) {
      outgoing[link.source] += link.value;
      incoming[link.target] += link.value;
    }
    return {
      nodes: data.nodes.map((n, i) => ({
        ...n,
        value: Math.max(incoming[i], outgoing[i]),
        onSelect:
          n.kind === "category"
            ? () => router.push(`/categories/${encodeURIComponent(n.name)}?month=${month}`)
            : undefined,
      })),
      links: data.links,
    };
  }, [data, month, router]);

  const hasFlow = (data?.nodes.length ?? 0) > 0 && (data?.links.length ?? 0) > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Cash Flow</h1>
          <p className="mt-1 max-w-2xl text-xs text-slate-500">
            Where this month's money came from and where it went — income on
            the left, spending grouped and then broken into categories on the
            right. Colours match the dashboard and drill-down: click a
            category to see its transactions.
          </p>
        </div>
        <div>
          <label className="block text-xs text-slate-500">Month</label>
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
      </div>

      {error && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}
      {!data && !error && (
        <p className="py-16 text-center text-sm text-slate-400">Loading…</p>
      )}

      {data && (
        <>
          {data.total_income < 0 && <SignIssueBanner />}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-slate-500">Income</p>
              <p className="text-xl font-bold text-green-600">
                {formatSignedCurrency(data.total_income)}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-slate-500">Spending</p>
              <p className="text-xl font-bold text-red-600">
                {formatSignedCurrency(data.total_spending)}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-slate-500">
                {data.net_cash_flow >= 0 ? "To savings" : "Shortfall"}
              </p>
              <p
                className={`text-xl font-bold ${
                  data.net_cash_flow >= 0 ? "text-brand-700" : "text-amber-700"
                }`}
              >
                {formatCurrency(Math.abs(data.net_cash_flow))}
              </p>
            </div>
          </div>

          {data.shortfall !== null && (
            <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              Spending was {formatCurrency(data.shortfall)} more than income
              this month, so there's no leftover to draw as a flow into
              savings — that gap came from savings or credit instead, which
              this diagram can't show as a line since there's nothing
              flowing that direction to draw.
            </p>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            {!hasFlow ? (
              <p className="py-16 text-center text-sm text-slate-400">
                No income or spending recorded for this month yet.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(360, data.nodes.length * 22)}>
                <Sankey
                  data={chartData!}
                  nodeWidth={NODE_WIDTH}
                  nodePadding={28}
                  margin={{ top: 10, right: 160, bottom: 10, left: 160 }}
                  link={<CashFlowLink />}
                  node={<CashFlowNode />}
                >
                  <Tooltip
                    formatter={(value: number) => formatCurrency(value)}
                    labelFormatter={() => ""}
                  />
                </Sankey>
              </ResponsiveContainer>
            )}
          </div>

          <p className="text-xs text-slate-400">
            Transfers between your own accounts (like a credit card payment)
            aren't shown here — they're not income or spending. A category
            that's the only one in its group is folded into the group node
            rather than drawn twice.
          </p>
        </>
      )}
    </div>
  );
}
