"use client";

// Eval run detail. Top-of-page stat strip mirrors /runs (status, overall
// score, p50/p95 latency, total cost). Below that, the per-case table from
// GetEvalRun.case_results — each row is one dataset case with its per-scorer
// scores, output preview, and latency/cost. This is the page a reviewer
// lands on when triaging an eval regression in a PR comment.

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { evalClient } from "@/lib/rpc";
import type { EvalCaseResult, ScorerScore } from "@/gen/eval/v1/eval_pb";

export default function EvalDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const detail = useQuery({
    queryKey: ["eval", id],
    queryFn: () => evalClient.getEvalRun({ id }),
    refetchInterval: (q) => {
      const status = q.state.data?.evalRun?.status;
      // Stop polling once the run has reached a terminal state.
      const terminal = status === 3 || status === 4;
      return terminal ? false : 5000;
    },
  });

  if (detail.isLoading)
    return <p className="text-sm text-gray-500">Loading…</p>;
  if (detail.isError)
    return <p className="text-sm text-red-600">{String(detail.error)}</p>;

  const run = detail.data?.evalRun;
  const cases = detail.data?.caseResults ?? [];
  if (!run) return <p className="text-sm text-gray-500">Not found.</p>;

  const totalCostUsd = Number(run.costTotalUsdCents) / 100;

  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">Eval</h1>
          <EvalStatusBadge status={run.status} />
        </div>
        <div className="font-mono text-xs text-gray-500">{run.id}</div>
        <div className="text-sm text-gray-600 dark:text-gray-400">
          <Link
            href={`/workflows/${run.workflowId}`}
            className="text-blue-600 hover:underline"
          >
            workflow {run.workflowId.slice(0, 8)}…
          </Link>
          {" · "}dataset <code>{run.dataset}</code>
          {run.seedsPerCase > 0 && (
            <>
              {" · "}
              {run.seedsPerCase} seed{run.seedsPerCase === 1 ? "" : "s"}/case
            </>
          )}
          {run.createdAt && (
            <>
              {" · "}
              {new Date(Number(run.createdAt.seconds) * 1000).toLocaleString()}
            </>
          )}
        </div>
      </header>

      <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Overall" value={run.overallScore.toFixed(3)} />
        <Stat label="Latency p50" value={`${Number(run.latencyP50Ms)} ms`} />
        <Stat label="Latency p95" value={`${Number(run.latencyP95Ms)} ms`} />
        <Stat label="Total cost" value={`$${totalCostUsd.toFixed(4)}`} />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Aggregate scores
        </h2>
        <div className="flex flex-wrap gap-2">
          {run.aggregateScores.length === 0 && (
            <p className="text-sm text-gray-500">No scorers reported.</p>
          )}
          {run.aggregateScores.map((s) => (
            <ScorerChip key={s.scorer} score={s} size="lg" />
          ))}
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Cases
        </h2>
        <p className="text-xs text-gray-500">
          Click a case to inspect its output preview.
        </p>
        <div className="divide-y divide-gray-100 rounded-md border border-gray-200 dark:divide-gray-900 dark:border-gray-800">
          {cases.map((c) => (
            <CaseRow key={`${c.caseId}-${c.runId}`} c={c} />
          ))}
          {cases.length === 0 && (
            <p className="px-4 py-3 text-sm text-gray-500">
              No case results yet.
            </p>
          )}
        </div>
      </section>
    </main>
  );
}

function CaseRow({ c }: { c: EvalCaseResult }) {
  const costUsd = Number(c.costUsdCents) / 100;
  return (
    <details className="group">
      <summary className="flex cursor-pointer items-center gap-4 px-4 py-3 text-sm hover:bg-gray-50 dark:hover:bg-gray-900">
        <span className="font-mono text-xs">{c.caseId}</span>
        <span className="flex flex-wrap gap-1">
          {c.scores.map((s) => (
            <ScorerChip key={s.scorer} score={s} />
          ))}
        </span>
        <span className="ml-auto text-xs text-gray-500 tabular-nums">
          {Number(c.latencyMs)} ms · ${costUsd.toFixed(4)}
        </span>
      </summary>
      <div className="space-y-3 px-4 pb-4 text-sm">
        <Field label="Output preview" value={c.outputPreview || "—"} />
      </div>
    </details>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
        {label}
      </div>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded border border-gray-200 bg-gray-50 p-3 font-mono text-xs dark:border-gray-800 dark:bg-gray-900">
        {value}
      </pre>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded border border-gray-200 p-3 dark:border-gray-800">
      <div className="text-xs uppercase tracking-wide text-gray-500">
        {label}
      </div>
      <div className="mt-1 text-sm font-medium tabular-nums">{value}</div>
    </div>
  );
}

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

function ScorerChip({
  score,
  size = "sm",
}: {
  score: ScorerScore;
  size?: "sm" | "lg";
}) {
  const v = score.score;
  const tone =
    v >= 0.8
      ? "border-green-300 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
      : v >= 0.5
        ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200"
        : "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200";
  const sizing =
    size === "lg"
      ? "px-2.5 py-1 text-xs"
      : "px-1.5 py-0.5 text-[10px]";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border font-medium tabular-nums ${sizing} ${tone}`}
    >
      <span className="opacity-70">{score.scorer}</span>
      <span>{v.toFixed(3)}</span>
    </span>
  );
}
