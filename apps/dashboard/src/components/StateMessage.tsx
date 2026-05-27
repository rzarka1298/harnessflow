// Shared presentation for the three "data isn't here yet" states the
// dashboard pages keep redoing inline: loading, empty, error.
//
// Kept tiny on purpose — Unicode glyphs over an icon library, hand-rolled
// Tailwind classes rather than pulling in shadcn. The variants share the
// same dashed-border + centered-stack layout so the dashboard reads
// consistently as you click between pages.

import type { ReactNode } from "react";

type ToneClasses = {
  border: string;
  iconBg: string;
  iconFg: string;
};

const TONES: Record<"neutral" | "info" | "error", ToneClasses> = {
  neutral: {
    border:
      "border-gray-200 bg-gray-50/40 dark:border-gray-800 dark:bg-gray-900/40",
    iconBg: "bg-gray-100 dark:bg-gray-800",
    iconFg: "text-gray-500 dark:text-gray-400",
  },
  info: {
    border:
      "border-blue-200 bg-blue-50/40 dark:border-blue-900 dark:bg-blue-950/30",
    iconBg: "bg-blue-100 dark:bg-blue-900/40",
    iconFg: "text-blue-600 dark:text-blue-300",
  },
  error: {
    border:
      "border-red-200 bg-red-50/40 dark:border-red-900 dark:bg-red-950/30",
    iconBg: "bg-red-100 dark:bg-red-900/40",
    iconFg: "text-red-600 dark:text-red-300",
  },
};

function Panel({
  tone,
  icon,
  title,
  body,
  cta,
  compact,
}: {
  tone: keyof typeof TONES;
  icon: string;
  title: string;
  body?: ReactNode;
  cta?: ReactNode;
  compact?: boolean;
}) {
  const t = TONES[tone];
  return (
    <div
      className={`flex flex-col items-center gap-2 rounded-md border border-dashed text-center ${t.border} ${
        compact ? "px-4 py-4" : "px-6 py-8"
      }`}
      role={tone === "error" ? "alert" : undefined}
    >
      <div
        aria-hidden
        className={`flex h-10 w-10 items-center justify-center rounded-full text-lg ${t.iconBg} ${t.iconFg}`}
      >
        {icon}
      </div>
      <div className="text-sm font-medium text-gray-800 dark:text-gray-100">
        {title}
      </div>
      {body && (
        <div className="max-w-md text-xs text-gray-600 dark:text-gray-400">
          {body}
        </div>
      )}
      {cta && <div className="mt-1">{cta}</div>}
    </div>
  );
}

// LoadingState — shown while the initial fetch is in flight. Uses a
// pulsing dot rather than a spinner so it animates without needing a
// keyframe in globals.css.
export function LoadingState({
  label = "Loading…",
  compact,
}: {
  label?: string;
  compact?: boolean;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center gap-3 rounded-md border border-dashed border-gray-200 px-4 text-sm text-gray-500 dark:border-gray-800 dark:text-gray-400 ${
        compact ? "py-2" : "py-4"
      }`}
    >
      <span
        aria-hidden
        className="inline-block h-2 w-2 animate-pulse rounded-full bg-gray-400 dark:bg-gray-500"
      />
      <span>{label}</span>
    </div>
  );
}

// EmptyState — no data yet. The CTA slot is for the "do X to get data"
// hint (e.g., "Run one with `harnessflow-eval`").
export function EmptyState({
  title,
  body,
  cta,
  compact,
  icon = "📭",
}: {
  title: string;
  body?: ReactNode;
  cta?: ReactNode;
  compact?: boolean;
  icon?: string;
}) {
  return (
    <Panel
      tone="neutral"
      icon={icon}
      title={title}
      body={body}
      cta={cta}
      compact={compact}
    />
  );
}

// ErrorState — the fetch came back non-OK. `error` accepts any thrown
// value; we coerce via String() so a `connect` error message still reads
// reasonably.
export function ErrorState({
  title = "Couldn't load.",
  error,
  retry,
  compact,
}: {
  title?: string;
  error: unknown;
  retry?: () => void;
  compact?: boolean;
}) {
  return (
    <Panel
      tone="error"
      icon="⚠"
      title={title}
      body={
        <code className="break-all font-mono text-[11px] text-red-700 dark:text-red-300">
          {String(error)}
        </code>
      }
      cta={
        retry && (
          <button
            onClick={retry}
            className="rounded border border-red-300 bg-white px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50 dark:border-red-800 dark:bg-red-950 dark:text-red-200 dark:hover:bg-red-900"
          >
            Retry
          </button>
        )
      }
      compact={compact}
    />
  );
}

// InlineError — for places where a full panel is too heavy (e.g., a
// mutation failure next to a button). Keeps the red-text affordance
// without the dashed-border container.
export function InlineError({ error }: { error: unknown }) {
  return (
    <span className="text-sm text-red-600 dark:text-red-400" role="alert">
      ⚠ {String(error)}
    </span>
  );
}
