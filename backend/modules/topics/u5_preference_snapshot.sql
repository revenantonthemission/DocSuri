-- NULL marks preserved pre-repair evidence, never an invented historical setting.
ALTER TABLE topics.digest_run ADD COLUMN preference_snapshot jsonb;
ALTER TABLE topics.digest_run ADD COLUMN presentation jsonb;
ALTER TABLE topics.digest_run ADD COLUMN request_key uuid NOT NULL DEFAULT gen_random_uuid();
CREATE UNIQUE INDEX digest_request_identity ON topics.digest_run(request_key);
CREATE FUNCTION topics.guard_preparation_snapshot() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
  IF (NEW.preference_snapshot,NEW.presentation,NEW.request_key) IS DISTINCT FROM
     (OLD.preference_snapshot,OLD.presentation,OLD.request_key) THEN
    RAISE EXCEPTION 'preparation snapshot is immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER preparation_snapshot BEFORE UPDATE ON topics.digest_run
FOR EACH ROW EXECUTE FUNCTION topics.guard_preparation_snapshot();
REVOKE ALL ON FUNCTION topics.guard_preparation_snapshot() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION topics.guard_preparation_snapshot() TO docsuri_topics;
