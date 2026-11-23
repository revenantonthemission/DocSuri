-- U8 (A2): ResearchWorkspace's job times for the owner job list, a correction added
-- after u8_research.sql; it replaces no file. A2's items carry updatedAt, and
-- research.job held only accepted_at, so each job gains the time it last changed in a
-- way its owner sees: its state, its result or its error. Lease and fence bookkeeping
-- do not move it. Existing rows start at their accepted_at.
ALTER TABLE research.job ADD COLUMN updated_at timestamptz;
UPDATE research.job SET updated_at = accepted_at;
ALTER TABLE research.job
    ALTER COLUMN updated_at SET DEFAULT clock_timestamp(),
    ALTER COLUMN updated_at SET NOT NULL,
    ADD CONSTRAINT job_updated_after_accepted CHECK (updated_at >= accepted_at);

CREATE FUNCTION research.job_touch() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
  IF ROW(NEW.state, NEW.artifact_id, NEW.error_code)
     IS DISTINCT FROM ROW(OLD.state, OLD.artifact_id, OLD.error_code) THEN
    NEW.updated_at := greatest(clock_timestamp(), OLD.updated_at);
  ELSE
    NEW.updated_at := OLD.updated_at;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER job_touch BEFORE UPDATE ON research.job
  FOR EACH ROW EXECUTE FUNCTION research.job_touch();
REVOKE ALL ON FUNCTION research.job_touch() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION research.job_touch() TO docsuri_research;
