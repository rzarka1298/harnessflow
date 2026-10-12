"use client";

import Link from "next/link";
import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { projectClient } from "@/lib/rpc";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingState,
} from "@/components/StateMessage";
import {
  readableDate,
  RunOptions,
  Section,
  StatusBadge,
} from "@/components/projects/ProjectUI";

export default function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [attempts, setAttempts] = useState(30);
  const [minutes, setMinutes] = useState(240);
  const [model, setModel] = useState("");
  const [requestPr, setRequestPr] = useState(false);
  const detail = useQuery({
    queryKey: ["project", id],
    queryFn: () => projectClient.getProject({ id }),
  });
  const runs = useInfiniteQuery({
    queryKey: ["project-runs", id],
    initialPageParam: "",
    queryFn: ({ pageParam }) =>
      projectClient.listRuns({
        projectId: id,
        pageSize: 30,
        pageToken: pageParam,
      }),
    getNextPageParam: (page) => page.nextPageToken || undefined,
    refetchInterval: 5000,
  });
  const start = useMutation({
    mutationFn: () =>
      projectClient.startRun({
        projectId: id,
        maxAttempts: attempts,
        maxDurationSeconds: minutes * 60,
        model: model.trim(),
        requestPr,
      }),
    onSuccess: (response) => {
      if (response.run) router.push(`/projects/${id}/runs/${response.run.id}`);
    },
  });
  if (detail.isLoading) return <LoadingState label="Loading project…" />;
  if (detail.isError)
    return (
      <ErrorState error={detail.error} retry={() => void detail.refetch()} />
    );
  const project = detail.data?.project;
  if (!project) return <EmptyState title="Project not found." />;
  const rows = runs.data?.pages.flatMap((page) => page.runs) ?? [];
  return (
    <main className="project-space space-y-7">
      <header className="space-y-3">
        <Link
          className="text-xs text-teal-700 dark:text-teal-300"
          href="/projects"
        >
          ← All projects
        </Link>
        <h1 className="text-3xl font-semibold tracking-tight">
          {project.name}
        </h1>
        <p className="break-all font-mono text-xs text-gray-500">
          {project.repositoryPath}
        </p>
      </header>
      <div className="grid items-start gap-6 lg:grid-cols-[1.2fr_1fr]">
        <div className="space-y-6">
          <Section
            title="Runs"
            hint="Each run keeps its own branch, progress, and verification evidence."
          >
            {runs.isLoading ? <LoadingState label="Loading runs…" /> : null}
            {runs.isError ? (
              <ErrorState
                error={runs.error}
                retry={() => void runs.refetch()}
              />
            ) : null}
            {!runs.isLoading && !runs.isError && !rows.length ? (
              <EmptyState
                title="Ready for the first run."
                body="Set your limits and start. You can pause, clarify, and resume from the run page."
              />
            ) : null}
            <ul className="divide-y divide-gray-100 dark:divide-gray-800">
              {rows.map((run) => (
                <li key={run.id}>
                  <Link
                    className="project-list-item"
                    href={`/projects/${id}/runs/${run.id}`}
                  >
                    <div className="min-w-0">
                      <h3>Run {run.id.slice(0, 8)}</h3>
                      <small>{readableDate(run.createdAt)}</small>
                      {run.reason ? (
                        <p className="mt-1 text-xs">{run.reason}</p>
                      ) : null}
                    </div>
                    <StatusBadge status={run.status} />
                  </Link>
                </li>
              ))}
            </ul>
            {runs.hasNextPage ? (
              <button
                className="project-button-secondary mt-4"
                disabled={runs.isFetchingNextPage}
                onClick={() => void runs.fetchNextPage()}
              >
                Load more runs
              </button>
            ) : null}
          </Section>
          <Section title="Product brief">
            <pre className="project-code">{project.prd}</pre>
          </Section>
        </div>
        <Section
          title="Start a run"
          hint="The harness works toward your acceptance criteria and pauses if it needs input or reaches a limit."
        >
          <form
            className="space-y-5"
            onSubmit={(e) => {
              e.preventDefault();
              start.mutate();
            }}
          >
            <RunOptions
              attempts={attempts}
              minutes={minutes}
              model={model}
              requestPr={requestPr}
              onAttempts={setAttempts}
              onMinutes={setMinutes}
              onModel={setModel}
              onRequestPr={setRequestPr}
            />
            {start.isError ? <InlineError error={start.error} /> : null}
            <button
              className="project-button w-full"
              disabled={start.isPending}
            >
              {start.isPending ? "Starting run…" : "Start building →"}
            </button>
          </form>
        </Section>
      </div>
    </main>
  );
}
