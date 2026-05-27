"use client";

import { use, useMemo } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DagViewer } from "@/components/DagViewer";
import { runClient, workflowClient } from "@/lib/rpc";
import { parseWorkflowGraph } from "@/lib/yaml-graph";

// Mirror of runv1.RunStatus enum values.
const STATUS_WAITING_APPROVAL = 5;

export default function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const qc = useQueryClient();

  const detail = useQuery({
    queryKey: ["run", id],
    queryFn: () => runClient.getRun({ id }),
    refetchInterval: (q) => {
      const status = q.state.data?.run?.status;
      // Stop polling once the run has reached a terminal state.
      const terminal = status === 3 || status === 4 || status === 6;
      return terminal ? false : 2000;
    },
  });

  const approve = useMutation({
    mutationFn: () => runClient.approveRun({ runId: id }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["run", id] }),
  });

  // The DAG needs the workflow YAML to know the graph shape; the run only
  // carries `workflow_id`. The query stays disabled until we know which
  // workflow to ask for.
  const workflowId = detail.data?.run?.workflowId;
  const wf = useQuery({
    queryKey: ["workflow", workflowId],
    queryFn: () => workflowClient.getWorkflow({ id: workflowId! }),
    enabled: Boolean(workflowId),
    staleTime: 5 * 60_000, // YAML doesn't change mid-run
  });

  // Use the broader `wf.data` reference so React Compiler's inferred deps
  // line up with what we declare; YAML doesn't change mid-run and the
  // useQuery has a 5-min staleTime, so the extra invalidations are rare.
  const dagSteps = useMemo(
    () =>
      wf.data?.workflow?.yamlSource
        ? parseWorkflowGraph(wf.data.workflow.yamlSource)
        : [],
    [wf.data],
  );
  const stepStatuses = useMemo(() => {
    const m: Record<string, number> = {};
    for (const s of detail.data?.steps ?? []) m[s.name] = s.status;
    return m;
  }, [detail.data?.steps]);

  if (detail.isLoading) return <p className="text-sm text-gray-500">Loading…</p>;
  if (detail.isError) return <p className="text-sm text-red-600">{String(detail.error)}</p>;

  const run = detail.data?.run;
  const steps = detail.data?.steps ?? [];
  if (!run) return <p className="text-sm text-gray-500">Not found.</p>;

  const awaitingApproval = run.status === STATUS_WAITING_APPROVAL;

  const totalCostUsd = Number(run.totalCostUsdCents) / 100;
  const jaegerUrl = run.traceId
    ? `http://localhost:16686/trace/${run.traceId}`
    : "http://localhost:16686/";

  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Run</h1>
          <Link
            href={`/runs/${id}/replay`}
            className="text-sm text-blue-600 hover:underline"
          >
            ▶ Replay timeline
          </Link>
        </div>
        <div className="font-mono text-xs text-gray-500">{run.id}</div>
        <div className="text-sm">
          <Link
            href={`/workflows/${run.workflowId}`}
            className="text-blue-600 hover:underline"
          >
            workflow {run.workflowId.slice(0, 8)}…
          </Link>
        </div>
      </header>

      {awaitingApproval && (
        <div className="flex items-center justify-between rounded-md border border-amber-300 bg-amber-50 p-4 dark:border-amber-700 dark:bg-amber-950">
          <div className="text-sm">
            <div className="font-medium text-amber-900 dark:text-amber-200">
              Waiting for approval
            </div>
            <div className="text-amber-700 dark:text-amber-300">
              This run is paused on an approval gate.
            </div>
          </div>
          <button
            onClick={() => approve.mutate()}
            disabled={approve.isPending}
            className="rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {approve.isPending ? "Approving…" : "Approve"}
          </button>
        </div>
      )}

      {dagSteps.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            DAG
          </h2>
          <DagViewer steps={dagSteps} stepStatuses={stepStatuses} />
        </section>
      )}

      <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Status" value={statusLabel(run.status)} />
        <Stat label="Total tokens" value={String(run.totalTokens)} />
        <Stat label="Total cost" value={`$${totalCostUsd.toFixed(4)}`} />
        <Stat
          label="Trace"
          value={
            run.traceId ? (
              <a className="text-blue-600 hover:underline" href={jaegerUrl} target="_blank" rel="noreferrer">
                {run.traceId.slice(0, 12)}… ↗
              </a>
            ) : (
              "—"
            )
          }
        />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Steps</h2>
        <p className="text-xs text-gray-500">Click a step to inspect its prompt, response, and any error.</p>
        <div className="divide-y divide-gray-100 rounded-md border border-gray-200 dark:divide-gray-900 dark:border-gray-800">
          {steps.map((s) => (
            <details key={s.id} className="group">
              <summary className="flex cursor-pointer items-center gap-4 px-4 py-3 text-sm hover:bg-gray-50 dark:hover:bg-gray-900">
                <span className="font-medium">{s.name}</span>
                <span className="text-gray-500">{s.type}</span>
                <span>{stepStatusLabel(s.status)}</span>
                <span className="ml-auto text-xs text-gray-500">
                  {Number(s.latencyMs)} ms · {Number(s.inputTokens)}/{Number(s.outputTokens)} tok · $
                  {(Number(s.costUsdCents) / 100).toFixed(4)}
                </span>
              </summary>
              <div className="space-y-3 px-4 pb-4 text-sm">
                {s.error && (
                  <Field label="Error" tone="error" value={s.error} />
                )}
                <Field label="Input (prompt)" value={s.inputPreview || "—"} />
                <Field label="Output (response)" value={s.outputPreview || "—"} />
              </div>
            </details>
          ))}
          {steps.length === 0 && (
            <p className="px-4 py-3 text-sm text-gray-500">No steps yet.</p>
          )}
        </div>
      </section>
    </main>
  );
}

function Field({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "error";
}) {
  return (
    <div>
      <div
        className={`mb-1 text-xs font-semibold uppercase tracking-wide ${
          tone === "error" ? "text-red-600" : "text-gray-500"
        }`}
      >
        {label}
      </div>
      <pre
        className={`max-h-64 overflow-auto whitespace-pre-wrap rounded border p-3 font-mono text-xs ${
          tone === "error"
            ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
            : "border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900"
        }`}
      >
        {value}
      </pre>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded border border-gray-200 p-3 dark:border-gray-800">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}

function statusLabel(status: number): string {
  return ({
    0: "UNSPECIFIED",
    1: "PENDING",
    2: "RUNNING",
    3: "COMPLETED",
    4: "FAILED",
    5: "WAITING_APPROVAL",
    6: "CANCELED",
  } as Record<number, string>)[status] ?? "UNSPECIFIED";
}

function stepStatusLabel(status: number): string {
  return ({
    0: "UNSPECIFIED",
    1: "PENDING",
    2: "RUNNING",
    3: "COMPLETED",
    4: "FAILED",
    5: "SKIPPED",
  } as Record<number, string>)[status] ?? "UNSPECIFIED";
}
