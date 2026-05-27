"use client";

// List of eval runs across all workflows, newest first. Each row links to
// the per-run detail page and surfaces the headline numbers (overall score,
// per-scorer chips, latency p50/p95, total cost) so it acts as a
// quality-over-time leaderboard at a glance. Backed by
// EvalService.ListEvalRuns; evals are produced by the eval-runner CLI and
// persisted by it directly to Postgres (see ADR-0006).

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "@/components/StateMessage";
import { evalClient } from "@/lib/rpc";
import type { EvalRun, ScorerScore } from "@/gen/eval/v1/eval_pb";

export default function EvalsPage() {
  const list = useQuery({
    queryKey: ["evals"],
    queryFn: () => evalClient.listEvalRuns({ pageSize: 50 }),
    // Eval runs only land after the CLI finishes a full pass, but we still
    // poll so an in-progress run completing while the page is open shows
    // up without a refresh.
    refetchInterval: 5000,
  });

  return (
    <main className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Evals</h1>
        <p className="text-xs text-gray-500">
          Eval runs are produced by the <code>harnessflow-eval</code> CLI in{" "}
          <code>apps/eval-runner/</code> and persisted to Postgres. The
          per-workflow deployment gate compares <em>overall score</em>{" "}
          against the workflow YAML&apos;s <code>requires_eval_pass.min_score</code>.
        </p>
      </header>
      {list.isLoading && <LoadingState label="Loading eval runs…" />}
      {list.isError && (
        <ErrorState error={list.error} retry={() => void list.refetch()} />
      )}
      {list.data?.evalRuns?.length === 0 && (
        <EmptyState
          title="No eval runs yet."
          icon="🧪"
          body={
            <>
              Trigger one with{" "}
              <code className="font-mono text-[11px]">
                uv run --directory apps/eval-runner harnessflow-eval
                --workflow-id &lt;id&gt; --dataset research-assistant
              </code>
              , or open a PR that modifies a workflow YAML — the CI eval-gate
              will run one automatically.
            </>
          }
        />
      )}
      <ul className="divide-y divide-gray-200 dark:divide-gray-800">
        {list.data?.evalRuns?.map((r) => (
          <EvalRunRow key={r.id} run={r} />
        ))}
      </ul>
    </main>
  );
}

function EvalRunRow({ run }: { run: EvalRun }) {
  const totalCostUsd = Number(run.costTotalUsdCents) / 100;
  return (
    <li className="py-3">
      <Link
        href={`/evals/${run.id}`}
        className="flex items-center justify-between gap-4 hover:opacity-80"
      >
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs">{run.id.slice(0, 12)}…</span>
            <EvalStatusBadge status={run.status} />
          </div>
          <div className="text-xs text-gray-500">
            workflow {run.workflowId.slice(0, 8)}… · dataset{" "}
            <code>{run.dataset}</code>
            {run.seedsPerCase > 0 && ` · ${run.seedsPerCase} seed${run.seedsPerCase === 1 ? "" : "s"}/case`}
            {run.createdAt && (
              <> · {new Date(Number(run.createdAt.seconds) * 1000).toLocaleString()}</>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {run.aggregateScores.map((s) => (
              <ScorerChip key={s.scorer} score={s} />
            ))}
          </div>
        </div>
        <div className="shrink-0 text-right text-xs">
          <div className="text-base font-semibold tabular-nums">
            {run.overallScore.toFixed(3)}
          </div>
          <div className="mt-0.5 text-gray-500 tabular-nums">
            p50 {Number(run.latencyP50Ms)}ms · p95 {Number(run.latencyP95Ms)}ms
          </div>
          <div className="text-gray-500 tabular-nums">
            ${totalCostUsd.toFixed(4)}
          </div>
        </div>
      </Link>
    </li>
  );
}

// Connect-Web with protobuf-es decodes enums into their numeric values, so
// we can compare against the EvalStatus enum directly (see /runs page for
// the same pattern).
function EvalStatusBadge({ status }: { status: number }) {
  const label = (
    {
      0: "UNSPECIFIED",
      1: "PENDING",
      2: "RUNNING",
      3: "COMPLETED",
      4: "FAILED",
    } as Record<number, string>
  )[status] ?? "UNSPECIFIED";
  const color =
    label === "COMPLETED"
      ? "bg-green-100 text-green-800"
      : label === "FAILED"
        ? "bg-red-100 text-red-800"
        : label === "RUNNING"
          ? "bg-blue-100 text-blue-800"
          : "bg-gray-100 text-gray-800";
  return (
    <span
      className={`rounded px-2 py-0.5 text-[10px] font-semibold ${color}`}
    >
      {label}
    </span>
  );
}

function ScorerChip({ score }: { score: ScorerScore }) {
  // Scorers all produce a 0–1 score in our framework (latency/cost are
  // surfaced separately on the row). Tint by quality.
  const v = score.score;
  const tone =
    v >= 0.8
      ? "border-green-300 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
      : v >= 0.5
        ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200"
        : "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium tabular-nums ${tone}`}
    >
      <span className="opacity-70">{score.scorer}</span>
      <span>{v.toFixed(2)}</span>
    </span>
  );
}
