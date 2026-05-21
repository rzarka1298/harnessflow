"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { DagViewer } from "@/components/DagViewer";
import { workflowClient } from "@/lib/rpc";
import { parseWorkflowGraph } from "@/lib/yaml-graph";

export default function WorkflowDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [query, setQuery] = useState(
    "How does Temporal handle workflow retries vs activity retries?",
  );

  const wf = useQuery({
    queryKey: ["workflow", id],
    queryFn: () => workflowClient.getWorkflow({ id }),
  });

  const run = useMutation({
    mutationFn: () =>
      workflowClient.runWorkflow({
        workflowId: id,
        inputs: { query },
      }),
    onSuccess: (resp) => {
      router.push(`/runs/${resp.runId}`);
    },
  });

  if (wf.isLoading) return <p className="text-sm text-gray-500">Loading…</p>;
  if (wf.isError) return <p className="text-sm text-red-600">{String(wf.error)}</p>;

  const workflow = wf.data?.workflow;
  if (!workflow) return <p className="text-sm text-gray-500">Not found.</p>;

  const steps = parseWorkflowGraph(workflow.yamlSource);

  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{workflow.name}</h1>
        <div className="font-mono text-xs text-gray-500">{workflow.id}</div>
        <div className="text-sm text-gray-500">
          v{workflow.version} · {workflow.status}
        </div>
        {workflow.description && (
          <p className="text-sm text-gray-600 dark:text-gray-300">{workflow.description}</p>
        )}
      </header>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">DAG</h2>
        <DagViewer steps={steps} />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Run</h2>
        <div className="rounded-md border border-gray-200 p-4 dark:border-gray-800">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Input: query</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full rounded border border-gray-200 bg-gray-50 p-2 text-sm dark:border-gray-700 dark:bg-gray-900"
            />
          </label>
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={() => run.mutate()}
              disabled={run.isPending}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {run.isPending ? "Starting…" : "Run workflow"}
            </button>
            {run.isError && (
              <span className="text-sm text-red-600">{String(run.error)}</span>
            )}
          </div>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">YAML</h2>
        <pre className="overflow-auto rounded-md border border-gray-200 bg-gray-50 p-4 font-mono text-xs leading-relaxed dark:border-gray-800 dark:bg-gray-900">
          {workflow.yamlSource}
        </pre>
      </section>
    </main>
  );
}
