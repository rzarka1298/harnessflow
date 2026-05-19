-- name: CreateWorkflow :one
INSERT INTO workflows (id, name, version, description, yaml_source, status)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING *;

-- name: GetWorkflow :one
SELECT * FROM workflows WHERE id = $1;

-- name: ListWorkflows :many
SELECT * FROM workflows
ORDER BY created_at DESC, id DESC
LIMIT $1 OFFSET $2;

-- name: CountWorkflows :one
SELECT COUNT(*) FROM workflows;

-- name: GetLatestWorkflowVersion :one
SELECT * FROM workflows
WHERE name = $1
ORDER BY version DESC
LIMIT 1;

-- name: UpdateWorkflowStatus :exec
UPDATE workflows
SET status = $2, updated_at = NOW()
WHERE id = $1;
