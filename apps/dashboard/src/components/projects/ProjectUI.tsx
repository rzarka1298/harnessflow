import type { ReactNode } from "react";

export const TERMINAL_STATUSES = new Set(["completed", "failed", "canceled"]);
export const ACTIVE_STATUSES = new Set([
  "queued",
  "running",
  "planning",
  "executing",
  "verifying",
]);

export function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "completed"
      ? "success"
      : status === "failed"
        ? "danger"
        : ACTIVE_STATUSES.has(status)
          ? "active"
          : "neutral";
  return (
    <span className={`project-status project-status-${tone}`}>
      <span aria-hidden className="project-status-dot" />
      {status.replaceAll("_", " ") || "pending"}
    </span>
  );
}

export function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <section className="project-panel">
      <header className="project-panel-heading">
        <h2>{title}</h2>
        {hint ? <p>{hint}</p> : null}
      </header>
      {children}
    </section>
  );
}

export function RunOptions({
  attempts,
  minutes,
  model,
  requestPr,
  onAttempts,
  onMinutes,
  onModel,
  onRequestPr,
}: {
  attempts: number;
  minutes: number;
  model: string;
  requestPr: boolean;
  onAttempts: (value: number) => void;
  onMinutes: (value: number) => void;
  onModel: (value: string) => void;
  onRequestPr: (value: boolean) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="project-field">
          <span>Coding attempts</span>
          <input
            required
            type="number"
            min={1}
            max={1000}
            value={attempts}
            onChange={(e) => onAttempts(Number(e.target.value))}
          />
          <small>Pauses when this limit is reached.</small>
        </label>
        <label className="project-field">
          <span>Active time limit (minutes)</span>
          <input
            required
            type="number"
            min={1}
            max={10080}
            value={minutes}
            onChange={(e) => onMinutes(Number(e.target.value))}
          />
          <small>Paused time does not count.</small>
        </label>
      </div>
      <label className="project-field">
        <span>
          Model <span className="font-normal text-gray-500">· optional</span>
        </span>
        <input
          value={model}
          onChange={(e) => onModel(e.target.value)}
          placeholder="Use the configured Codex model"
          autoComplete="off"
        />
      </label>
      <label className="flex items-start gap-3 text-sm">
        <input
          className="mt-1 accent-teal-700"
          type="checkbox"
          checked={requestPr}
          onChange={(e) => onRequestPr(e.target.checked)}
        />
        <span>
          Open a pull request when complete
          <small className="mt-1 block text-gray-500">
            Requires an authenticated GitHub CLI and a repository remote.
            Otherwise, the result stays on a local branch.
          </small>
        </span>
      </label>
    </div>
  );
}

export function readableDate(value: { seconds: bigint } | undefined): string {
  return value
    ? new Date(Number(value.seconds) * 1000).toLocaleString()
    : "Just created";
}
