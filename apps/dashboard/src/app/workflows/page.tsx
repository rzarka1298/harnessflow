"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { workflowClient } from "@/lib/rpc";

const SAMPLE_YAML = `name: research-assistant
version: 1
steps:
  planner:
    type: llm_call
    model: gpt-4o
    prompt: "Break the question into sub-queries."
  retriever:
    type: retrieve
    source: vector-db
    top_k: 5
    after: [planner]
  executor:
    type: llm_call
    model: gpt-4o
    prompt: "Answer using context: {{steps.retriever.output}}"
    after: [retriever]
  verifier:
    type: verify
    after: [executor]
`;

export default function WorkflowsPage() {
  const qc = useQueryClient();
  const [yaml, setYaml] = useState(SAMPLE_YAML);
  const [creating, setCreating] = useState(false);

  const list = useQuery({
    queryKey: ["workflows"],
    queryFn: () => workflowClient.listWorkflows({ pageSize: 50 }),
  });

  const create = useMutation({
    mutationFn: () => workflowClient.createWorkflow({ yamlSource: yaml }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["workflows"] });
      setCreating(false);
    },
  });

  return (
    <main className="space-y-8">
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Workflows</h1>
          <button
            onClick={() => setCreating((v) => !v)}
            className="rounded-md bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
          >
            {creating ? "Cancel" : "New workflow"}
          </button>
        </div>

        {creating && (
          <div className="space-y-3 rounded-md border border-gray-200 p-4 dark:border-gray-800">
            <textarea
              value={yaml}
              onChange={(e) => setYaml(e.target.value)}
              className="h-72 w-full rounded border border-gray-200 bg-gray-50 p-3 font-mono text-xs dark:border-gray-700 dark:bg-gray-900"
            />
            <div className="flex items-center gap-3">
              <button
                onClick={() => create.mutate()}
                disabled={create.isPending}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {create.isPending ? "Creating…" : "Create"}
              </button>
              {create.isError && (
                <span className="text-sm text-red-600">{String(create.error)}</span>
              )}
            </div>
          </div>
        )}
      </section>

      <section>
        {list.isLoading && <p className="text-sm text-gray-500">Loading…</p>}
        {list.isError && (
          <p className="text-sm text-red-600">Failed to load: {String(list.error)}</p>
        )}
        {list.data?.workflows?.length === 0 && (
          <p className="text-sm text-gray-500">
            No workflows yet. Click <strong>New workflow</strong> above to create one.
          </p>
        )}
        <ul className="divide-y divide-gray-200 dark:divide-gray-800">
          {list.data?.workflows?.map((wf) => (
            <li key={wf.id} className="py-3">
              <Link
                href={`/workflows/${wf.id}`}
                className="flex items-center justify-between hover:opacity-80"
              >
                <div>
                  <div className="font-medium">{wf.name}</div>
                  <div className="font-mono text-xs text-gray-500">{wf.id}</div>
                </div>
                <div className="text-right text-sm">
                  <div>v{wf.version}</div>
                  <div className="text-xs text-gray-500">{wf.status}</div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
