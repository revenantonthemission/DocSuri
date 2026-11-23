-- U8 (the research executor; your decision of 2026-10-24): ResearchWorkspace's wait
-- reason, added after u8_research_erasure.sql; it replaces no file. A job whose model
-- runtime did not answer records why it waits: DEADLINE_EXCEEDED or
-- DEPENDENCY_UNAVAILABLE, and null for every other job. When its attempts are spent it
-- closes with that reason. `research.job_touch` does not watch this column, so setting
-- it leaves the job's owner time (`updated_at`) where it was.
ALTER TABLE research.job ADD COLUMN wait_reason text
    CONSTRAINT job_wait_reason CHECK (
        wait_reason IS NULL OR wait_reason IN ('DEADLINE_EXCEEDED', 'DEPENDENCY_UNAVAILABLE')
    );
