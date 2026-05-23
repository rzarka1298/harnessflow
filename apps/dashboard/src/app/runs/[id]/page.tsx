"use client";

import { use } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { runClient } from "@/lib/rpc";

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
        <h1 className="text-2xl font-semibold">Run</h1>
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
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500 dark:border-gray-800">
              <th className="py-2">Step</th>
              <th className="py-2">Type</th>
              <th className="py-2">Status</th>
              <th className="py-2 text-right">Latency</th>
              <th className="py-2 text-right">Tokens (in/out)</th>
              <th className="py-2 text-right">Cost</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((s) => (
              <tr key={s.id} className="border-b border-gray-100 dark:border-gray-900">
                <td className="py-2 font-medium">{s.name}</td>
                <td className="py-2 text-gray-500">{s.type}</td>
                <td className="py-2">{stepStatusLabel(s.status)}</td>
                <td className="py-2 text-right">{Number(s.latencyMs)} ms</td>
                <td className="py-2 text-right text-gray-500">
                  {Number(s.inputTokens)} / {Number(s.outputTokens)}
                </td>
                <td className="py-2 text-right">${(Number(s.costUsdCents) / 100).toFixed(4)}</td>
              </tr>
            ))}
            {steps.length === 0 && (
              <tr>
                <td colSpan={6} className="py-3 text-sm text-gray-500">
                  No steps yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
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
