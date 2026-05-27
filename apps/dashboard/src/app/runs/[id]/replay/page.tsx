"use client";

// Run replay — a Gantt-style timeline of step execution plus a scrubber that
// time-travels through the run. The point isn't to be a Temporal-events
// replay (we have Temporal UI + Jaeger for that); it's to give a recruiter
// or a triager a single screen that answers "what was happening at second
// T of this run, and what did each step look like at that moment?"
//
// Everything is computed client-side from `RunService.GetRun(id)` — the
// proto already exposes per-step `started_at` / `ended_at`, so no API
// changes were needed for this view.

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import type { Timestamp } from "@bufbuild/protobuf/wkt";

import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "@/components/StateMessage";
import { runClient } from "@/lib/rpc";
import type { Step } from "@/gen/run/v1/run_pb";

// Protobuf Timestamp → epoch milliseconds. Returns null when the field is
// absent (e.g. a step that hasn't started yet).
function tsToMs(t: Timestamp | undefined): number | null {
  if (!t) return null;
  return Number(t.seconds) * 1000 + Math.floor(t.nanos / 1_000_000);
}

// Mirrors of harnessflow.run.v1.StepStatus enum values; protobuf-es decodes
// the wire-format enum strings into these numbers on the client.
const STATUS_RUNNING = 2;
const STATUS_FAILED = 4;
const STATUS_SKIPPED = 5;

type StepWindow = {
  step: Step;
  startMs: number;
  endMs: number;
  leftPct: number;
  widthPct: number;
};

export default function RunReplayPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const detail = useQuery({
    queryKey: ["run", id],
    queryFn: () => runClient.getRun({ id }),
    refetchInterval: (q) => {
      const status = q.state.data?.run?.status;
      // Match /runs/[id]: poll until a terminal state, then stop.
      const terminal = status === 3 || status === 4 || status === 6;
      return terminal ? false : 2000;
    },
  });

  // Cursor position is a percentage 0–100 along the run's time window. We
  // store it as a number, default 100 (= "show the end state"); changing
  // the slider sets it; replaying via the play button steps it forward.
  const [cursorPct, setCursorPct] = useState(100);
  const [isPlaying, setIsPlaying] = useState(false);

  const run = detail.data?.run;
  // Stabilize the steps reference so the downstream useMemos don't refire
  // on every render — TanStack Query already memoizes the response object.
  const steps = useMemo(() => detail.data?.steps ?? [], [detail.data?.steps]);
  // `dataUpdatedAt` is the ms timestamp of the last query refetch. We use
  // it as our "now" reference: it's stable per render, refreshes with the
  // 2s poll on in-progress runs, and dodges the React-hooks-purity rule
  // that bans Date.now() during render.
  const refMs = detail.dataUpdatedAt;

  // Compute the bounds for the timeline. We prefer the run's own
  // started_at/ended_at; fall back to the min/max across steps if the run
  // didn't get those stamped (shouldn't happen post-Week-5, but defensive).
  const { runStart, runEnd } = useMemo(() => {
    let start = tsToMs(run?.startedAt) ?? Infinity;
    let end = tsToMs(run?.endedAt) ?? -Infinity;
    for (const s of steps) {
      const a = tsToMs(s.startedAt);
      const b = tsToMs(s.endedAt);
      if (a !== null) start = Math.min(start, a);
      if (b !== null) end = Math.max(end, b);
    }
    if (start === Infinity) start = refMs;
    if (end === -Infinity || end < start) end = start + 1; // avoid divide-by-zero
    return { runStart: start, runEnd: end };
  }, [run, steps, refMs]);

  const totalMs = runEnd - runStart;

  // Per-step screen coordinates, ordered by start time so the rows read
  // top-to-bottom like a Gantt chart.
  const windows = useMemo<StepWindow[]>(() => {
    const out: StepWindow[] = [];
    for (const s of steps) {
      const startMs = tsToMs(s.startedAt);
      if (startMs === null) continue; // step never ran; skip the bar
      // For an in-progress step, draw up to the run's end (or "now"-clamp).
      const endMs = tsToMs(s.endedAt) ?? Math.min(refMs, runEnd);
      const leftPct = ((startMs - runStart) / totalMs) * 100;
      const widthPct = Math.max(0.5, ((endMs - startMs) / totalMs) * 100);
      out.push({ step: s, startMs, endMs, leftPct, widthPct });
    }
    out.sort((a, b) => a.startMs - b.startMs);
    return out;
  }, [steps, runStart, runEnd, totalMs, refMs]);

  // Cursor time in absolute ms — used to decide each step's state at this
  // moment and to select the "focused" step for the detail panel.
  const cursorMs = runStart + (cursorPct / 100) * totalMs;

  // The currently-focused step is the one whose window contains the
  // cursor; if none, the latest step that's already started. This is what
  // populates the prompt/response panel below the timeline.
  const focused = useMemo<StepWindow | null>(() => {
    if (windows.length === 0) return null;
    const containing = windows.find(
      (w) => cursorMs >= w.startMs && cursorMs <= w.endMs,
    );
    if (containing) return containing;
    const before = windows.filter((w) => w.startMs <= cursorMs);
    return before[before.length - 1] ?? windows[0];
  }, [windows, cursorMs]);

  if (detail.isLoading) return <LoadingState label="Loading run…" />;
  if (detail.isError)
    return (
      <ErrorState
        title="Failed to load run."
        error={detail.error}
        retry={() => void detail.refetch()}
      />
    );
  if (!run)
    return (
      <EmptyState
        title="Run not found."
        body="The URL may be wrong, or the run was deleted."
      />
    );

  // Format helpers — keep numbers short so the timeline doesn't overflow.
  const fmtElapsed = (ms: number) => {
    const s = ms / 1000;
    if (s < 10) return `${s.toFixed(2)}s`;
    return `${s.toFixed(1)}s`;
  };

  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Run replay</h1>
          <Link
            href={`/runs/${id}`}
            className="text-sm text-blue-600 hover:underline"
          >
            ← back to run
          </Link>
        </div>
        <div className="font-mono text-xs text-gray-500">{run.id}</div>
        <div className="text-sm text-gray-600 dark:text-gray-400">
          {windows.length} step{windows.length === 1 ? "" : "s"} over{" "}
          {fmtElapsed(totalMs)}
          {" · "}
          <span className="font-mono">{statusLabel(run.status)}</span>
        </div>
      </header>

      <section className="space-y-2">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Timeline
          </h2>
          <span className="font-mono text-xs text-gray-500">
            t = {fmtElapsed(cursorMs - runStart)}
          </span>
        </div>

        {/* Gantt rows. Each row has a faint full-width track and a colored
            bar positioned by leftPct/widthPct. A red cursor line is
            overlaid across all rows. */}
        <div className="relative space-y-1.5 rounded-md border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900">
          {windows.length === 0 && (
            <EmptyState
              compact
              icon="⏱"
              title="No step events recorded."
              body="The worker hasn't persisted any started/ended timestamps yet. If this run is in-flight, bars will appear as steps fire."
            />
          )}
          {windows.map((w) => {
            const stateNow = stepStateAt(w, cursorMs);
            return (
              <div key={w.step.id} className="grid grid-cols-[8rem_1fr] items-center gap-2">
                <div className="truncate text-xs">
                  <span className="font-medium">{w.step.name}</span>
                  <span className="ml-1 text-gray-500">{w.step.type}</span>
                </div>
                <div className="relative h-5 rounded bg-gray-200 dark:bg-gray-800">
                  <div
                    title={`${w.step.name}: ${fmtElapsed(w.startMs - runStart)} → ${fmtElapsed(w.endMs - runStart)} (${Number(w.step.latencyMs)} ms)`}
                    className={`absolute top-0 h-5 rounded ${barColor(w.step.status, stateNow)}`}
                    style={{ left: `${w.leftPct}%`, width: `${w.widthPct}%` }}
                  />
                </div>
              </div>
            );
          })}
          {/* Cursor line. The 8rem gutter at the left holds the step
              labels, so the cursor track is offset by that amount. */}
          {windows.length > 0 && (
            <div
              className="pointer-events-none absolute inset-y-3 w-px bg-red-500"
              style={{
                left: `calc(0.75rem + 8rem + 0.5rem + (100% - 0.75rem - 0.75rem - 8rem - 0.5rem) * ${cursorPct / 100})`,
              }}
            />
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              if (isPlaying) {
                setIsPlaying(false);
                return;
              }
              setIsPlaying(true);
              setCursorPct(0);
              const start = Date.now();
              const playMs = Math.min(8000, Math.max(2000, totalMs)); // 2–8s sweep
              const tick = () => {
                const elapsed = Date.now() - start;
                const pct = Math.min(100, (elapsed / playMs) * 100);
                setCursorPct(pct);
                if (pct < 100 && isPlaying !== false) {
                  requestAnimationFrame(tick);
                } else {
                  setIsPlaying(false);
                }
              };
              requestAnimationFrame(tick);
            }}
            className="rounded-md border border-gray-300 bg-white px-3 py-1 text-xs font-medium hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:hover:bg-gray-800"
          >
            {isPlaying ? "Pause" : "▶ Replay"}
          </button>
          <input
            type="range"
            min={0}
            max={100}
            step={0.1}
            value={cursorPct}
            onChange={(e) => {
              setIsPlaying(false);
              setCursorPct(Number(e.target.value));
            }}
            className="flex-1 accent-red-500"
          />
          <span className="w-20 text-right font-mono text-xs text-gray-500">
            {cursorPct.toFixed(0)}%
          </span>
        </div>
      </section>

      {focused && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Focused step
          </h2>
          <div className="rounded-md border border-gray-200 p-4 dark:border-gray-800">
            <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
              <span className="font-medium">{focused.step.name}</span>
              <span className="text-gray-500">{focused.step.type}</span>
              <span className="font-mono text-xs">
                {stepStatusLabel(stepStateAt(focused, cursorMs))}
              </span>
              <span className="ml-auto font-mono text-xs text-gray-500">
                {fmtElapsed(focused.startMs - runStart)} →{" "}
                {fmtElapsed(focused.endMs - runStart)} ·{" "}
                {Number(focused.step.latencyMs)} ms ·{" "}
                {Number(focused.step.inputTokens)}/
                {Number(focused.step.outputTokens)} tok · $
                {(Number(focused.step.costUsdCents) / 100).toFixed(4)}
              </span>
            </div>
            <Field
              label="Input (prompt)"
              value={focused.step.inputPreview || "—"}
            />
            <Field
              label="Output (response)"
              value={focused.step.outputPreview || "—"}
            />
            {focused.step.error && (
              <Field label="Error" value={focused.step.error} tone="error" />
            )}
          </div>
        </section>
      )}
    </main>
  );
}

// stepStateAt returns the *effective* status of a step at the cursor time
// — even when the underlying row is `COMPLETED`, replaying through its
// window should show RUNNING for that moment.
function stepStateAt(w: StepWindow, cursorMs: number): number {
  if (cursorMs < w.startMs) return 1; // pending (proto: STEP_STATUS_PENDING)
  if (cursorMs >= w.endMs) return w.step.status;
  return STATUS_RUNNING;
}

function barColor(actualStatus: number, replayStatus: number): string {
  // The bar is colored by the step's *final* status, but pulses while the
  // cursor is inside its window. A faded color before the cursor reaches
  // it is what conveys the "not yet" idea.
  if (replayStatus === 1) {
    return "bg-gray-300 dark:bg-gray-700 opacity-50";
  }
  if (actualStatus === STATUS_FAILED) {
    return replayStatus === STATUS_RUNNING ? "bg-red-400 animate-pulse" : "bg-red-500";
  }
  if (actualStatus === STATUS_SKIPPED) {
    return "bg-gray-400 dark:bg-gray-600";
  }
  if (replayStatus === STATUS_RUNNING) {
    return "bg-blue-400 animate-pulse";
  }
  return "bg-green-500";
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
    <div className="mt-3">
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
