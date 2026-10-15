-- U3 amendment 2: a watermark (or completion) requires at least one committed
-- publication effect and no non-committed effect. An accepted run with pending
-- work can never advance a boundary.
CREATE OR REPLACE FUNCTION corpus.guard_run_state() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF OLD.state IN ('completed','failed') AND NEW.state IS DISTINCT FROM OLD.state THEN
        RAISE EXCEPTION 'terminal run state cannot regress' USING ERRCODE = '23514';
    END IF;
    IF NEW.watermark IS DISTINCT FROM OLD.watermark AND NEW.watermark IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM corpus.run_effect
                       WHERE run_id = NEW.id AND stage = 'publication' AND state = 'committed')
           OR EXISTS (SELECT 1 FROM corpus.run_effect
                      WHERE run_id = NEW.id AND state <> 'committed') THEN
            RAISE EXCEPTION 'watermark cannot advance past unverified work' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.state = 'completed' THEN
        IF NOT EXISTS (SELECT 1 FROM corpus.run_effect
                       WHERE run_id = NEW.id AND stage = 'publication' AND state = 'committed')
           OR EXISTS (SELECT 1 FROM corpus.run_effect
                      WHERE run_id = NEW.id AND state <> 'committed') THEN
            RAISE EXCEPTION 'run cannot complete with outstanding effects' USING ERRCODE = '23514';
        END IF;
        NEW.completed_at := coalesce(NEW.completed_at, clock_timestamp());
        NEW.dispatch_pending := false;
    END IF;
    IF NEW.state = 'failed' THEN
        NEW.completed_at := coalesce(NEW.completed_at, clock_timestamp());
        NEW.dispatch_pending := false;
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION corpus.guard_run_state() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.guard_run_state() TO docsuri_corpus;
