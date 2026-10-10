CREATE TABLE projects (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    repository_path TEXT NOT NULL,
    prd TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE project_runs (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    repository_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    reason TEXT NOT NULL DEFAULT '',
    state JSONB NOT NULL DEFAULT '{}',
    control TEXT NOT NULL DEFAULT '',
    clarification TEXT NOT NULL DEFAULT '',
    max_attempts INTEGER NOT NULL CHECK (max_attempts > 0),
    max_duration_seconds INTEGER NOT NULL CHECK (max_duration_seconds > 0),
    model TEXT NOT NULL DEFAULT '',
    request_pr BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX project_runs_repository_active ON project_runs(repository_path)
    WHERE status NOT IN ('completed', 'failed', 'canceled');
CREATE INDEX project_runs_project_created ON project_runs(project_id, created_at DESC);
