-- 0003_eval_results: persistence for the eval framework.
--
-- An eval_runs row is one evaluation of a workflow over a dataset; the
-- per-scorer aggregate scores and per-case scores are stored as JSONB
-- (scorer name -> score) to avoid an extra table while the scorer set is
-- still evolving. The eval-runner (apps/eval-runner) writes these; the Go
-- EvalService reads them.

CREATE TABLE eval_runs (
    id                   UUID PRIMARY KEY,
    workflow_id          UUID NOT NULL REFERENCES workflows(id),
    dataset              TEXT NOT NULL DEFAULT '',
    -- pending | running | completed | failed
    status               TEXT NOT NULL DEFAULT 'completed',
    seeds_per_case       INTEGER NOT NULL DEFAULT 1,
    overall_score        DOUBLE PRECISION NOT NULL DEFAULT 0,
    -- {scorer: mean_score}
    aggregate_scores     JSONB NOT NULL DEFAULT '{}',
    latency_p50_ms       BIGINT NOT NULL DEFAULT 0,
    latency_p95_ms       BIGINT NOT NULL DEFAULT 0,
    cost_total_usd_cents BIGINT NOT NULL DEFAULT 0,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at         TIMESTAMPTZ
);
CREATE INDEX eval_runs_workflow_idx ON eval_runs (workflow_id);
CREATE INDEX eval_runs_created_at_idx ON eval_runs (created_at DESC);

CREATE TABLE eval_result_cases (
    id              UUID PRIMARY KEY,
    eval_run_id     UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    case_id         TEXT NOT NULL,
    -- {scorer: score}
    scores          JSONB NOT NULL DEFAULT '{}',
    output_preview  TEXT NOT NULL DEFAULT '',
    latency_ms      BIGINT NOT NULL DEFAULT 0,
    cost_usd_cents  BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX eval_result_cases_run_idx ON eval_result_cases (eval_run_id);
