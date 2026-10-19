-- Appended correction: the chronological gate blocks only strictly earlier
-- non-terminal windows. Same-window duplicates belong to the digest_run_window
-- unique index (UniqueViolation), not to this guard.
CREATE OR REPLACE FUNCTION topics.guard_run_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE current_settings integer;
BEGIN
    IF NEW.state <> 'prepared' THEN
        RAISE EXCEPTION 'a digest run starts prepared' USING ERRCODE = '23514';
    END IF;
    SELECT revision INTO current_settings FROM topics.digest_settings WHERE topic_id = NEW.topic_id;
    IF NOT FOUND OR NEW.settings_revision <> current_settings THEN
        RAISE EXCEPTION 'run must stamp the current settings revision' USING ERRCODE = '23514';
    END IF;
    IF EXISTS (SELECT 1 FROM topics.digest_run r WHERE r.topic_id = NEW.topic_id
               AND r.window_start < NEW.window_start
               AND r.state IN ('prepared','sending','unknown')) THEN
        RAISE EXCEPTION 'an earlier window is not terminal' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
