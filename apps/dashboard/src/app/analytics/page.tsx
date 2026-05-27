"use client";

// /analytics — the dashboard's cost + quality overview.
//
// Three panels:
//   1. Daily LLM cost (USD) — bar chart over the last 14 days.
//   2. Daily run volume by status — stacked bar (completed/failed/other)
//      over the same window.
//   3. Eval overall_score over time — one line per workflow, ordered by
//      eval-run created_at.
//
// Aggregation runs client-side off `RunService.ListRuns({pageSize: 500})`
// and `EvalService.ListEvalRuns({pageSize: 200})`. The pattern matches
// how `/evals` and `/runs` already work — at portfolio scale (~10–100
// runs) it's fast and avoids adding an `AnalyticsService` RPC. When run
// volume passes ~10k we'd swap this for a server-side aggregation; the
// page surface stays the same.

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Timestamp } from "@bufbuild/protobuf/wkt";

import {
  BarChart,
  ChartLegend,
  LineChart,
  type BarSeries,
  type LineSeries,
} from "@/components/charts/BarChart";
import { ErrorState, LoadingState } from "@/components/StateMessage";
import { evalClient, runClient } from "@/lib/rpc";

// Mirrors of RunStatus / EvalStatus enum values; protobuf-es decodes wire
// strings into these numbers on the client.
const RUN_STATUS_COMPLETED = 3;
const RUN_STATUS_FAILED = 4;

// Window the trends panels look back over. Two weeks is enough to see a
// trend without making the bars too thin to read.
const WINDOW_DAYS = 14;

function tsToMs(t: Timestamp | undefined): number | null {
  if (!t) return null;
  return Number(t.seconds) * 1000 + Math.floor(t.nanos / 1_000_000);
}

// dayKey returns a 'YYYY-MM-DD' bucket key in the viewer's local
// timezone. We use local time so the bars line up with what the user
// expects when they look at clock-on-the-wall time.
function dayKey(ms: number): string {
  const d = new Date(ms);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function shortDayLabel(key: string): string {
  // 'YYYY-MM-DD' → 'M/D' for the bar tick label.
  const [, m, d] = key.split("-");
  return `${Number(m)}/${Number(d)}`;
}

function lastNDays(n: number, anchorMs: number): string[] {
  const out: string[] = [];
  const anchor = new Date(anchorMs);
  anchor.setHours(0, 0, 0, 0);
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(anchor);
    d.setDate(d.getDate() - i);
    out.push(dayKey(d.getTime()));
  }
  return out;
}

export default function AnalyticsPage() {
  const runs = useQuery({
    queryKey: ["analytics", "runs"],
    queryFn: () => runClient.listRuns({ pageSize: 500 }),
    refetchInterval: 5000,
  });

  const evals = useQuery({
    queryKey: ["analytics", "evals"],
    queryFn: () => evalClient.listEvalRuns({ pageSize: 200 }),
    refetchInterval: 10_000,
  });

  // Use the latest query refetch timestamp as the "now" reference, same
  // pattern as the replay page — keeps Date.now() out of render to
  // satisfy the react-hooks/purity rule.
  const refMs = Math.max(runs.dataUpdatedAt, evals.dataUpdatedAt, 1);

  const days = useMemo(() => lastNDays(WINDOW_DAYS, refMs), [refMs]);

  const { costSeries, volumeSeries, summary } = useMemo(() => {
    const cost: Record<string, number> = {};
    const tokens: Record<string, number> = {};
    const completed: Record<string, number> = {};
    const failed: Record<string, number> = {};
    const other: Record<string, number> = {};
    let totalCostCents = 0;
    let totalTokens = 0;
    let totalRuns = 0;
    for (const r of runs.data?.runs ?? []) {
      const t = tsToMs(r.startedAt);
      if (t === null) continue;
      const key = dayKey(t);
      const cents = Number(r.totalCostUsdCents);
      const toks = Number(r.totalTokens);
      cost[key] = (cost[key] ?? 0) + cents;
      tokens[key] = (tokens[key] ?? 0) + toks;
      if (r.status === RUN_STATUS_COMPLETED) {
        completed[key] = (completed[key] ?? 0) + 1;
      } else if (r.status === RUN_STATUS_FAILED) {
        failed[key] = (failed[key] ?? 0) + 1;
      } else {
        other[key] = (other[key] ?? 0) + 1;
      }
      totalCostCents += cents;
      totalTokens += toks;
      totalRuns += 1;
    }

    return {
      costSeries: {
        cost: days.map((k) => (cost[k] ?? 0) / 100), // cents → USD
        tokens: days.map((k) => tokens[k] ?? 0),
      },
      volumeSeries: [
        {
          name: "completed",
          color: "#10b981",
          values: days.map((k) => completed[k] ?? 0),
        },
        {
          name: "failed",
          color: "#ef4444",
          values: days.map((k) => failed[k] ?? 0),
        },
        {
          name: "other",
          color: "#9ca3af",
          values: days.map((k) => other[k] ?? 0),
        },
      ] satisfies BarSeries[],
      summary: {
        totalRuns,
        totalCostUsd: totalCostCents / 100,
        totalTokens,
      },
    };
  }, [runs.data?.runs, days]);

  // Score-over-time chart: one line per workflow. Each eval contributes
  // a point at its created_at; gaps stay null so the line breaks instead
  // of straight-lining through missing days.
  const { scoreLines, scoreLabels, evalSummary } = useMemo(() => {
    const byWorkflow = new Map<string, { x: number; y: number }[]>();
    for (const e of evals.data?.evalRuns ?? []) {
      const t = tsToMs(e.createdAt);
      if (t === null) continue;
      const arr = byWorkflow.get(e.workflowId) ?? [];
      arr.push({ x: t, y: e.overallScore });
      byWorkflow.set(e.workflowId, arr);
    }

    if (byWorkflow.size === 0) {
      return {
        scoreLines: [],
        scoreLabels: [],
        evalSummary: { evalCount: 0, mean: 0 },
      };
    }

    const allPoints = Array.from(byWorkflow.values()).flat();
    allPoints.sort((a, b) => a.x - b.x);
    const labels = allPoints.map((p) => shortDayLabel(dayKey(p.x)));
    // Position by index across the global timeline. Each workflow's line
    // hits a value at its own sample positions, null everywhere else.
    const xIndex = new Map<number, number>();
    allPoints.forEach((p, i) => xIndex.set(p.x, i));

    const palette = ["#3b82f6", "#a855f7", "#f59e0b", "#10b981", "#ef4444"];
    const lines: LineSeries[] = [];
    let idx = 0;
    for (const [workflowId, points] of byWorkflow) {
      const values: (number | null)[] = labels.map(() => null);
      for (const p of points) {
        const i = xIndex.get(p.x);
        if (i !== undefined) values[i] = p.y;
      }
      lines.push({
        name: workflowId.slice(0, 8),
        color: palette[idx % palette.length],
        values,
      });
      idx += 1;
    }

    return {
      scoreLines: lines,
      scoreLabels: labels,
      evalSummary: {
        evalCount: allPoints.length,
        mean:
          allPoints.reduce((s, p) => s + p.y, 0) / allPoints.length,
      },
    };
  }, [evals.data?.evalRuns]);

  const dayLabels = days.map(shortDayLabel);
  const loading = runs.isLoading || evals.isLoading;
  const err = runs.error ?? evals.error;

  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <p className="text-xs text-gray-500">
          Cost, run volume, and eval-score trends — aggregated client-side
          from <code>RunService.ListRuns</code> and{" "}
          <code>EvalService.ListEvalRuns</code>. Last {WINDOW_DAYS} days.
        </p>
      </header>

      {loading && <LoadingState label="Loading analytics…" />}
      {err && (
        <ErrorState
          title="Failed to load analytics."
          error={err}
          retry={() => {
            void runs.refetch();
            void evals.refetch();
          }}
        />
      )}

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Runs" value={String(summary.totalRuns)} />
        <Stat
          label="Total cost"
          value={`$${summary.totalCostUsd.toFixed(4)}`}
        />
        <Stat
          label="Total tokens"
          value={summary.totalTokens.toLocaleString()}
        />
        <Stat
          label="Mean eval score"
          value={
            evalSummary.evalCount > 0
              ? evalSummary.mean.toFixed(3)
              : "—"
          }
        />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Daily LLM cost
        </h2>
        <div className="rounded-md border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-950">
          <BarChart
            labels={dayLabels}
            series={[
              {
                name: "USD",
                color: "#3b82f6",
                values: costSeries.cost,
              },
            ]}
            yFormat={(v) => `$${v.toFixed(2)}`}
            ariaLabel="Daily LLM cost in USD"
          />
        </div>
        <p className="text-xs text-gray-500">
          MockProvider runs ($0.0000/call) show as flat — set real
          OPENAI/ANTHROPIC keys to see live spend.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Daily run volume
        </h2>
        <div className="space-y-2 rounded-md border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-950">
          <BarChart
            labels={dayLabels}
            series={volumeSeries}
            ariaLabel="Daily run count by status"
          />
          <ChartLegend
            items={volumeSeries.map((s) => ({ name: s.name, color: s.color }))}
          />
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Eval overall score over time
        </h2>
        <div className="space-y-2 rounded-md border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-950">
          <LineChart
            labels={scoreLabels}
            series={scoreLines}
            yMin={0}
            yMax={1}
            yFormat={(v) => v.toFixed(2)}
            ariaLabel="Eval overall score per workflow over time"
          />
          {scoreLines.length > 0 && (
            <ChartLegend
              items={scoreLines.map((s) => ({
                name: `workflow ${s.name}…`,
                color: s.color,
              }))}
            />
          )}
        </div>
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-gray-200 p-3 dark:border-gray-800">
      <div className="text-xs uppercase tracking-wide text-gray-500">
        {label}
      </div>
      <div className="mt-1 text-sm font-medium tabular-nums">{value}</div>
    </div>
  );
}
