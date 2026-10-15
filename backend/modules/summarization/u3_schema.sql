-- U3 PaperAssistance: owner glossary compare-and-swap support and bounded
-- progress evidence. The immutable acceptance binding, claim/fence and ordered
-- progress already live in the U1 assistance schema; these additions complete
-- the U3 obligations without introducing a parallel job store.

-- The glossary already carries (account_id, revision, snapshot). Bind the
-- normalization policy identity so a stale-policy write can be refused and the
-- virtual-empty revision is policy-bound.
ALTER TABLE assistance.glossary
    ADD COLUMN normalization_policy jsonb NOT NULL
        DEFAULT '{"policyId":"u3-owner-glossary","revision":"1"}'::jsonb;

-- Ordered progress evidence is bounded per job; the oldest non-terminal
-- progress window is retained for reconnect reconstruction.
CREATE FUNCTION assistance.progress_bound() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE count bigint; oldest bigint;
BEGIN
    SELECT count(*), min(sequence) INTO count, oldest
      FROM assistance.event WHERE job_id = NEW.job_id;
    IF count > 256 THEN
        DELETE FROM assistance.event
         WHERE job_id = NEW.job_id AND sequence = oldest AND oldest < NEW.sequence - 128;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER progress_bound AFTER INSERT ON assistance.event
FOR EACH ROW EXECUTE FUNCTION assistance.progress_bound();
REVOKE ALL ON FUNCTION assistance.progress_bound() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION assistance.progress_bound() TO docsuri_assistance;
