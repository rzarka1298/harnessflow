"use client";

import Link from "next/link";
import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projectClient } from "@/lib/rpc";
import { parseSnapshot, safeExternalUrl } from "@/lib/project-snapshot";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingState,
} from "@/components/StateMessage";
import {
  readableDate,
  Section,
  StatusBadge,
  TERMINAL_STATUSES,
} from "@/components/projects/ProjectUI";

const PHASES = [
  "prepare",
  "plan",
  "plan_review",
  "implement",
  "verify",
  "review",
  "repair",
  "deliver",
];
const PAUSED_STATUSES = new Set(["paused", "blocked", "exhausted"]);

export default function ProjectRunPage({
  params,
}: {
  params: Promise<{ id: string; runId: string }>;
}) {
  const { id, runId } = use(params);
  const qc = useQueryClient();
  const [clarification, setClarification] = useState("");
  const [additionalAttempts, setAdditionalAttempts] = useState(0);
  const [additionalMinutes, setAdditionalMinutes] = useState(0);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [requestedControl, setRequestedControl] = useState<{
    action: string;
    savedAt: number;
  } | null>(null);
  const detail = useQuery({
    queryKey: ["project-run", runId],
    queryFn: () => projectClient.getRun({ id: runId }),
    refetchInterval: (query) =>
      TERMINAL_STATUSES.has(query.state.data?.run?.status ?? "") ? false : 2000,
  });
  const project = useQuery({
    queryKey: ["project", id],
    queryFn: () => projectClient.getProject({ id }),
  });
  const control = useMutation({
    mutationFn: (action: string) =>
      projectClient.controlRun({
        runId,
        action,
        clarification: action === "resume" ? clarification : "",
        additionalAttempts: action === "resume" ? additionalAttempts : 0,
        additionalSeconds: action === "resume" ? additionalMinutes * 60 : 0,
      }),
    onSuccess: (response, action) => {
      qc.setQueryData(["project-run", runId], { run: response.run });
      void qc.invalidateQueries({ queryKey: ["project-runs", id] });
      setConfirmCancel(false);
      setClarification("");
      setAdditionalAttempts(0);
      setAdditionalMinutes(0);
      setRequestedControl({
        action,
        savedAt:
          Number(response.run?.updatedAt?.seconds ?? 0) * 1000 +
          (response.run?.updatedAt?.nanos ?? 0) / 1_000_000,
      });
    },
  });
  if (detail.isLoading) return <LoadingState label="Loading run…" />;
  if (detail.isError)
    return (
      <ErrorState error={detail.error} retry={() => void detail.refetch()} />
    );
  const run = detail.data?.run;
  if (!run) return <EmptyState title="Run not found." />;
  if (run.projectId !== id)
    return <EmptyState title="This run belongs to a different project." />;
  const { snapshot, error: snapshotError } = parseSnapshot(run.snapshotJson);
  const terminal = TERMINAL_STATUSES.has(run.status);
  const paused = PAUSED_STATUSES.has(run.status);
  const checkpointAt =
    Number(run.updatedAt?.seconds ?? 0) * 1000 +
    (run.updatedAt?.nanos ?? 0) / 1_000_000;
  const controlAcknowledged =
    terminal ||
    (requestedControl?.action === "resume"
      ? !paused || checkpointAt > requestedControl.savedAt
      : requestedControl?.action === "pause" && paused);
  // Adjust local command state when a polled checkpoint acknowledges it. The
  // API saves commands before the worker applies them, so mutation success
  // alone is not an acknowledgment and must not enable duplicate extensions.
  if (requestedControl && controlAcknowledged) setRequestedControl(null);
  const awaitingControl = requestedControl !== null && !controlAcknowledged;
  const tasks = snapshot.plan?.tasks ?? [];
  const done = new Set(snapshot.completed_task_ids ?? []);
  const evidence = snapshot.evidence ?? [];
  const prUrl = safeExternalUrl(snapshot.pr_url);
  const phaseIndex = PHASES.indexOf(snapshot.phase ?? "");

  return (
    <main className="project-space space-y-6">
      <header className="space-y-4">
        <Link
          className="text-xs text-teal-700 dark:text-teal-300"
          href={`/projects/${id}`}
        >
          ← {project.data?.project?.name ?? "Back to project"}
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="project-eyebrow mb-2">PROJECT RUN</div>
            <h1 className="text-3xl font-semibold tracking-tight">
              {project.data?.project?.name ?? "Build progress"}
            </h1>
            <p className="mt-2 font-mono text-xs text-gray-500">
              {run.id} · {readableDate(run.createdAt)}
            </p>
          </div>
          <StatusBadge status={run.status} />
        </div>
        <div
          className="flex flex-wrap items-center gap-2"
          aria-label="Run phases"
        >
          {PHASES.map((phase, index) => (
            <span
              key={phase}
              className={`rounded-full border px-3 py-1 text-xs capitalize ${phase === snapshot.phase ? "border-teal-500 bg-teal-50 text-teal-800 dark:bg-teal-950 dark:text-teal-200" : "border-gray-200 text-gray-500 dark:border-gray-800"}`}
            >
              {index < phaseIndex || run.status === "completed"
                ? "✓ "
                : `${index + 1} · `}
              {phase.replaceAll("_", " ")}
            </span>
          ))}
        </div>
      </header>
      {snapshotError ? (
        <ErrorState error={snapshotError} retry={() => void detail.refetch()} />
      ) : null}
      {run.reason ? (
        <div
          role="status"
          className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
        >
          {run.reason}
        </div>
      ) : null}
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="project-metric">
          <dt>Tasks completed</dt>
          <dd>
            {done.size} / {tasks.length || "—"}
          </dd>
        </div>
        <div className="project-metric">
          <dt>Coding attempts</dt>
          <dd>
            {snapshot.attempts ?? 0}
            {snapshot.max_attempts ? ` / ${snapshot.max_attempts}` : ""}
          </dd>
        </div>
        <div className="project-metric">
          <dt>Active time</dt>
          <dd>
            {Math.floor((snapshot.active_seconds ?? 0) / 60)}
            {snapshot.max_duration_seconds
              ? ` / ${Math.floor(snapshot.max_duration_seconds / 60)}`
              : ""}{" "}
            min
          </dd>
        </div>
        <div className="project-metric">
          <dt>Reported tokens</dt>
          <dd>
            {(
              (snapshot.tokens?.input ?? 0) + (snapshot.tokens?.output ?? 0)
            ).toLocaleString()}
          </dd>
        </div>
      </dl>
      {!terminal ? (
        <Section
          title="Run controls"
          hint={
            paused
              ? "Address the blocker or extend the limits, then resume the same run."
              : "Pause at the next checkpoint to provide context or change the limits."
          }
        >
          {paused ? (
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (!awaitingControl) control.mutate("resume");
              }}
            >
              <label className="project-field">
                <span>Clarification or additional context</span>
                <textarea
                  rows={3}
                  value={clarification}
                  onChange={(e) => setClarification(e.target.value)}
                  placeholder="Answer the question above or describe how to continue."
                />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="project-field">
                  <span>Additional coding attempts</span>
                  <input
                    type="number"
                    min={0}
                    max={1000}
                    value={additionalAttempts}
                    onChange={(e) =>
                      setAdditionalAttempts(Number(e.target.value))
                    }
                  />
                </label>
                <label className="project-field">
                  <span>Additional active minutes</span>
                  <input
                    type="number"
                    min={0}
                    max={10080}
                    value={additionalMinutes}
                    onChange={(e) =>
                      setAdditionalMinutes(Number(e.target.value))
                    }
                  />
                </label>
              </div>
              <button
                className="project-button"
                disabled={control.isPending || awaitingControl}
              >
                Resume run
              </button>
            </form>
          ) : (
            <button
              className="project-button-secondary"
              disabled={control.isPending || awaitingControl}
              onClick={() => control.mutate("pause")}
            >
              Pause run
            </button>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {confirmCancel ? (
              <>
                <span className="text-xs text-gray-500">
                  Stop this run? Saved work and evidence remain available.
                </span>
                <button
                  className="project-button-danger"
                  disabled={control.isPending}
                  onClick={() => control.mutate("cancel")}
                >
                  Confirm cancel
                </button>
                <button
                  className="project-button-secondary"
                  onClick={() => setConfirmCancel(false)}
                >
                  Keep running
                </button>
              </>
            ) : (
              <button
                className="text-xs text-red-700 underline underline-offset-4 dark:text-red-300"
                onClick={() => setConfirmCancel(true)}
              >
                Cancel run
              </button>
            )}
          </div>
          {awaitingControl ? (
            <p
              className="mt-3 text-xs leading-relaxed text-teal-700 dark:text-teal-300"
              role="status"
            >
              {requestedControl?.action === "resume"
                ? "Resume"
                : requestedControl?.action === "pause"
                  ? "Pause"
                  : "Cancel"}{" "}
              request saved. Waiting for the runner to reach a checkpoint. You
              can leave this page; the request is stored.
            </p>
          ) : null}
          {control.isError ? (
            <div className="mt-3">
              <InlineError error={control.error} />
            </div>
          ) : null}
        </Section>
      ) : null}
      {snapshot.summary || prUrl || snapshot.branch ? (
        <Section title={run.status === "completed" ? "Delivery" : "Workspace"}>
          {snapshot.summary ? (
            <p className="mb-4 whitespace-pre-wrap text-sm leading-relaxed">
              {snapshot.summary}
            </p>
          ) : null}
          <dl className="space-y-2 text-xs">
            {snapshot.branch ? (
              <div>
                <dt className="inline text-gray-500">Branch </dt>
                <dd className="inline break-all font-mono">
                  {snapshot.branch}
                </dd>
              </div>
            ) : null}
            {snapshot.workspace_path ? (
              <div>
                <dt className="inline text-gray-500">Worktree </dt>
                <dd className="inline break-all font-mono">
                  {snapshot.workspace_path}
                </dd>
              </div>
            ) : null}
            {snapshot.head_commit ? (
              <div>
                <dt className="inline text-gray-500">Commit </dt>
                <dd className="inline break-all font-mono">
                  {snapshot.head_commit}
                </dd>
              </div>
            ) : null}
          </dl>
          {prUrl ? (
            <a
              className="project-button mt-4"
              href={prUrl}
              target="_blank"
              rel="noreferrer"
            >
              Review pull request ↗
            </a>
          ) : null}
        </Section>
      ) : null}
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Section title="Plan & tasks" hint={snapshot.plan?.summary}>
            {tasks.length ? (
              <ol className="space-y-3">
                {tasks.map((task) => (
                  <li
                    key={task.id}
                    className="rounded-lg border border-gray-200 p-3 dark:border-gray-800"
                  >
                    <div className="flex items-start gap-2">
                      <span
                        className={
                          done.has(task.id) ? "text-teal-600" : "text-gray-400"
                        }
                        aria-label={done.has(task.id) ? "Completed" : "Pending"}
                      >
                        {done.has(task.id) ? "✓" : "○"}
                      </span>
                      <div>
                        <h3 className="text-sm font-medium">{task.title}</h3>
                        <p className="mt-1 text-xs text-gray-500">
                          {task.id} · {(task.requirement_ids ?? []).join(", ")}
                        </p>
                        {task.instructions ? (
                          <details className="mt-2 text-xs">
                            <summary className="cursor-pointer text-gray-500">
                              Instructions
                            </summary>
                            <p className="mt-2 whitespace-pre-wrap leading-relaxed">
                              {task.instructions}
                            </p>
                          </details>
                        ) : null}
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-gray-500">
                The plan will appear after the agent inspects your repository
                and brief.
              </p>
            )}
            {snapshot.plan?.assumptions?.length ? (
              <details className="mt-4 text-xs">
                <summary className="cursor-pointer font-medium">
                  Planning assumptions
                </summary>
                <ul className="mt-2 list-disc space-y-2 pl-5">
                  {snapshot.plan.assumptions.map((assumption, i) => (
                    <li key={i}>{assumption}</li>
                  ))}
                </ul>
              </details>
            ) : null}
          </Section>
          <Section
            title="Acceptance criteria"
            hint="Requirements are connected to checks and their recorded results."
          >
            {(snapshot.plan?.requirements ?? []).length ? (
              <ul className="space-y-4">
                {snapshot.plan!.requirements!.map((requirement) => {
                  const checks = (snapshot.plan?.checks ?? []).filter((check) =>
                    check.requirement_ids?.includes(requirement.id),
                  );
                  return (
                    <li key={requirement.id}>
                      <p className="text-sm">
                        <span className="mr-2 font-mono text-xs text-gray-500">
                          {requirement.id}
                        </span>
                        {requirement.description}
                      </p>
                      <p className="mt-1 text-xs text-gray-500">
                        {checks.length
                          ? `Checks: ${checks.map((check) => check.id).join(", ")}`
                          : "No checks assigned yet"}
                      </p>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-gray-500">
                Acceptance criteria will appear with the plan.
              </p>
            )}
          </Section>
          <Section title="Activity" hint="Persistent events from the runner.">
            {snapshot.events?.length ? (
              <ol className="max-h-96 space-y-4 overflow-auto">
                {snapshot.events.map((event, index) => (
                  <li
                    key={`${event.at}-${index}`}
                    className="border-l-2 border-teal-100 pl-3 dark:border-teal-900"
                  >
                    <p className="whitespace-pre-wrap text-xs leading-relaxed">
                      {event.message}
                    </p>
                    <time className="mt-1 block text-[10px] text-gray-500">
                      {event.at}
                    </time>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-gray-500">
                Waiting for the first runner event…
              </p>
            )}
          </Section>
          {snapshot.agent_attempts?.length ? (
            <Section
              title="Agent attempts"
              hint="Each attempt is a separate agent session."
            >
              <ul className="space-y-3">
                {snapshot.agent_attempts.map((attempt) => (
                  <li
                    key={attempt.id}
                    className="flex items-start justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm capitalize">
                        {attempt.phase.replaceAll("_", " ")}
                      </p>
                      <p className="mt-1 break-all font-mono text-[10px] text-gray-500">
                        {attempt.id}
                      </p>
                      <p className="mt-1 text-[10px] text-gray-500">
                        {attempt.started_at}
                        {attempt.ended_at ? ` → ${attempt.ended_at}` : ""}
                      </p>
                    </div>
                    <StatusBadge status={attempt.status} />
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}
        </div>
        <div className="space-y-6">
          <Section
            title="Verification evidence"
            hint="Command results are tied to the commit that was checked."
          >
            {evidence.length ? (
              <div className="space-y-3">
                {evidence.map((result, index) => (
                  <details
                    key={`${result.check_id}-${index}`}
                    className="rounded-lg border border-gray-200 p-3 dark:border-gray-800"
                  >
                    <summary className="flex cursor-pointer items-center justify-between gap-2 text-sm">
                      <span>{result.check_id}</span>
                      <StatusBadge
                        status={result.passed ? "completed" : "failed"}
                      />
                    </summary>
                    <p className="my-2 font-mono text-[11px] text-gray-500">
                      exit {result.exit_code} · commit{" "}
                      {result.commit?.slice(0, 12) ?? "unknown"}
                    </p>
                    <pre className="project-code">
                      $ {(result.argv ?? []).join(" ")}
                      {"\n\n"}
                      {result.output || "No output recorded."}
                    </pre>
                  </details>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                No checks have finished yet. A completed run must include
                verification evidence.
              </p>
            )}
          </Section>
          {snapshot.review ? (
            <Section title="Independent review">
              <StatusBadge
                status={snapshot.review.passed ? "completed" : "failed"}
              />
              <ul className="mt-3 space-y-2 text-sm">
                {snapshot.review.findings.map((finding, index) => (
                  <li key={index}>{finding}</li>
                ))}
              </ul>
              {!snapshot.review.findings.length ? (
                <p className="mt-3 text-sm text-gray-500">
                  No findings reported.
                </p>
              ) : null}
            </Section>
          ) : null}
          <Section
            title="Artifacts & changes"
            hint="Inspect the recorded output, diff, and handoff notes."
          >
            {snapshot.artifacts?.length ? (
              <div className="space-y-3">
                {snapshot.artifacts.map((artifact, index) => (
                  <details
                    key={`${artifact.name}-${index}`}
                    className="rounded-lg border border-gray-200 p-3 dark:border-gray-800"
                  >
                    <summary className="cursor-pointer break-all text-sm font-medium">
                      {artifact.name}
                    </summary>
                    <pre className="project-code mt-3">{artifact.content}</pre>
                    <a
                      className="mt-3 inline-block text-xs text-teal-700 underline underline-offset-4 dark:text-teal-300"
                      download={artifact.name.split("/").pop()}
                      href={`data:text/plain;charset=utf-8,${encodeURIComponent(artifact.content)}`}
                    >
                      Download artifact
                    </a>
                  </details>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                Artifacts will appear as work is saved.
              </p>
            )}
          </Section>
        </div>
      </div>
    </main>
  );
}
