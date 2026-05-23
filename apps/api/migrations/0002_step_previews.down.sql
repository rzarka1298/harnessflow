ALTER TABLE workflow_steps
    DROP COLUMN IF EXISTS input_preview,
    DROP COLUMN IF EXISTS output_preview;
