-- U8 (your decision of 2026-10-24, "Until deleted or erased"): how long production's
-- research results are kept, added right after u8_research_waits.sql; it replaces no
-- file. In production, research answers and novelty results are kept until their owner
-- deletes them or the account is erased, never ended by time.
--
-- `research.artifact.expires_at` is NOT NULL and fixed after insert (u4_schema.sql), and
-- no U4 file changes. So for an artifact whose policy names
-- `docsuri-production-research`, this trigger stores the fixed mark
-- 9999-12-31 00:00:00+00 in place of the time the insert gave: U4's expiry sweep, its
-- result read, the discussion read and the job list compare the mark with the
-- database's clock and never reach it. A null would read as gone, and PostgreSQL's
-- `infinity` cannot be loaded into a Python date by psycopg; the mark loads in every
-- time zone. Every other policy keeps the value it was given.
CREATE FUNCTION research.artifact_retention() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.policy ->> 'policyId' = 'docsuri-production-research' THEN
        NEW.expires_at := timestamptz '9999-12-31 00:00:00+00';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER artifact_retention BEFORE INSERT ON research.artifact
    FOR EACH ROW EXECUTE FUNCTION research.artifact_retention();
REVOKE ALL ON FUNCTION research.artifact_retention() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION research.artifact_retention() TO docsuri_research;
