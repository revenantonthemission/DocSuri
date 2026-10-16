-- Prepared work has a finite acceptance window, never extended by retries.
-- Existing rows receive a window at migration; accepted work is unaffected.
ALTER TABLE research.admission ADD COLUMN accept_before timestamptz NOT NULL
    DEFAULT (clock_timestamp() + interval '30 seconds');
CREATE INDEX research_prepared_recovery ON research.admission(accept_before,operation_id)
    WHERE state='prepared';
CREATE FUNCTION research.keep_admission_deadline() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.accept_before IS DISTINCT FROM OLD.accept_before THEN
        RAISE EXCEPTION 'admission deadline is immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION research.keep_admission_deadline() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION research.keep_admission_deadline() TO docsuri_research;
CREATE TRIGGER keep_admission_deadline BEFORE UPDATE ON research.admission
    FOR EACH ROW EXECUTE FUNCTION research.keep_admission_deadline();
