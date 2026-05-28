-- 0001_init: workflows, workflow_runs, workflow_steps.
--
-- IDs are UUIDs (we use v7 in the app so they sort by creation time).
-- Statuses, step types, and other enum-shaped fields are TEXT for forward
-- compatibility with the DSL — adding a step type or status does not require
-- a migration.

CREATE TABLE workflows (
    id              UUID PRIMARY KEY,
    name            TEXT NOT NULL,
    version         INTEGER NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    yaml_source     TEXT NOT NULL,
    -- draft | active | archived (see WorkflowStatus in workflow.proto)
    status          TEXT NOT NULL DEFAULT 'draft',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, version)
);
CREATE INDEX workflows_name_idx ON workflows (name);
CREATE INDEX workflows_status_idx ON workflows (status);

CREATE TABLE workflow_runs (
    id                      UUID PRIMARY KEY,
    workflow_id             UUID NOT NULL REFERENCES workflows(id),
    -- Temporal workflow id (string). Used to query the Temporal cluster for
    -- live state and history.
    temporal_workflow_id    TEXT NOT NULL,
    -- pending | running | completed | failed | waiting_approval | canceled
    status                  TEXT NOT NULL DEFAULT 'pending',
    started_at              TIMESTAMPTZ,
    ended_at                TIMESTAMPTZ,
    -- Single OpenTelemetry trace id covering the whole run, populated when
    -- the run is started. Empty string before that.
    trace_id                TEXT NOT NULL DEFAULT '',
    total_cost_usd_cents    BIGINT NOT NULL DEFAULT 0,
    total_tokens            BIGINT NOT NULL DEFAULT 0,
    error                   TEXT NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX workflow_runs_workflow_idx ON workflow_runs (workflow_id);
CREATE INDEX workflow_runs_status_idx ON workflow_runs (status);
CREATE INDEX workflow_runs_temporal_idx ON workflow_runs (temporal_workflow_id);
CREATE INDEX workflow_runs_created_at_idx ON workflow_runs (created_at DESC);

CREATE TABLE workflow_steps (
    id                  UUID PRIMARY KEY,
    run_id              UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    -- llm_call | retrieve | tool_call | verify (workflow DSL step type)
    type                TEXT NOT NULL,
    -- pending | running | completed | failed | skipped
    status              TEXT NOT NULL DEFAULT 'pending',
    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    latency_ms          BIGINT NOT NULL DEFAULT 0,
    input_tokens        BIGINT NOT NULL DEFAULT 0,
    output_tokens       BIGINT NOT NULL DEFAULT 0,
    cost_usd_cents      BIGINT NOT NULL DEFAULT 0,
    attempt             INTEGER NOT NULL DEFAULT 1,
    error               TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX workflow_steps_run_idx ON workflow_steps (run_id);
CREATE INDEX workflow_steps_status_idx ON workflow_steps (status);
