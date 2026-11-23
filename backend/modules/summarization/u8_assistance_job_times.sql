-- U8 (NFR9.7, Build and Test loop-back 1, Step 47(a)): PaperAssistance's job times, a
-- correction added after u8_assistance.sql; it replaces no file. ServiceOperations counts
-- the failed jobs of the last 24 hours by the time each job last changed in a way its
-- owner sees: its state or its failure code. Lease and fence bookkeeping, a phase change
-- or a direct write to the column never move it. Existing rows start at their
-- accepted_at. A new row takes its own accepted_at through job_created: a second
-- clock_timestamp() default would read a slightly different time.
ALTER TABLE assistance.job ADD COLUMN updated_at timestamptz;
UPDATE assistance.job SET updated_at = accepted_at;
ALTER TABLE assistance.job
    ALTER COLUMN updated_at SET NOT NULL,
    ADD CONSTRAINT job_updated_after_accepted CHECK (updated_at >= accepted_at);

CREATE FUNCTION assistance.job_touch() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    NEW.updated_at := NEW.accepted_at;
  ELSIF ROW(NEW.state, NEW.failure_code) IS DISTINCT FROM ROW(OLD.state, OLD.failure_code) THEN
    NEW.updated_at := greatest(clock_timestamp(), OLD.updated_at);
  ELSE
    NEW.updated_at := OLD.updated_at;
  END IF;
  RETURN NEW;
END $$;
-- Row triggers of one kind fire in name order: U1's bound_execution_deadline first, then
-- these two, then U1's preserve_job_binding; none of U1's reads updated_at.
CREATE TRIGGER job_created BEFORE INSERT ON assistance.job
  FOR EACH ROW EXECUTE FUNCTION assistance.job_touch();
CREATE TRIGGER job_touch BEFORE UPDATE ON assistance.job
  FOR EACH ROW EXECUTE FUNCTION assistance.job_touch();
REVOKE ALL ON FUNCTION assistance.job_touch() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION assistance.job_touch() TO docsuri_assistance;
