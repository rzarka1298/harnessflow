export interface ProjectSnapshot {
  phase?: string;
  branch?: string;
  workspace_path?: string;
  base_commit?: string;
  head_commit?: string;
  plan?: {
    summary?: string;
    assumptions?: string[];
    requirements?: { id: string; description: string }[];
    tasks?: {
      id: string;
      title: string;
      instructions?: string;
      requirement_ids?: string[];
      depends_on?: string[];
    }[];
    checks?: {
      id: string;
      description: string;
      requirement_ids?: string[];
      argv?: string[];
      timeout_seconds?: number;
    }[];
  };
  completed_task_ids?: string[];
  attempts?: number;
  max_attempts?: number;
  max_duration_seconds?: number;
  active_seconds?: number;
  evidence?: {
    check_id: string;
    requirement_ids?: string[];
    argv?: string[];
    exit_code: number;
    output?: string;
    commit?: string;
    passed: boolean;
  }[];
  events?: { at: string; message: string }[];
  artifacts?: { name: string; content: string; media_type?: string }[];
  summary?: string;
  pr_url?: string;
  tokens?: { input: number; output: number };
  cost_usd?: number | null;
  review?: { passed: boolean; findings: string[] };
  failure_count?: number;
  agent_attempts?: {
    id: string;
    phase: string;
    status: string;
    started_at: string;
    ended_at?: string;
  }[];
}

// Snapshots are versioned server-owned JSON; keep parse failure visible instead
// of turning a corrupt snapshot into a misleading empty/completed run.
export function parseSnapshot(raw: string | undefined): {
  snapshot: ProjectSnapshot;
  error?: string;
} {
  if (!raw) return { snapshot: {} };
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value))
      throw new Error("Expected a snapshot object.");
    return { snapshot: value as ProjectSnapshot };
  } catch {
    return {
      snapshot: {},
      error:
        "Run details could not be read. Refresh to try again; the run status remains available.",
    };
  }
}

export function safeExternalUrl(value: string | undefined): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:"
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}
