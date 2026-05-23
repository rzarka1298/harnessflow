-- 0002_step_previews: capture truncated step input/output for failure analysis.
-- The `error` column already exists from 0001; these add the prompt/response
-- context the dashboard shows when inspecting a (failed or completed) step.

ALTER TABLE workflow_steps
    ADD COLUMN input_preview  TEXT NOT NULL DEFAULT '',
    ADD COLUMN output_preview TEXT NOT NULL DEFAULT '';
