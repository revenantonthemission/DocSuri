-- NULL marks a run no schedule prepared, never an invented instant.
-- The scheduled instant is the due instant of the occurrence the run was prepared
-- for, set once at insert (appended; applied U5 migrations stay byte-identical).
ALTER TABLE topics.digest_run ADD COLUMN scheduled_at timestamptz;

-- Replaces the update guard from u5_preference_snapshot.sql with the same rule,
-- plus the scheduled instant joining the immutable preparation facts.
CREATE OR REPLACE FUNCTION topics.guard_preparation_snapshot() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
  IF (NEW.preference_snapshot,NEW.presentation,NEW.request_key,NEW.scheduled_at) IS DISTINCT FROM
     (OLD.preference_snapshot,OLD.presentation,OLD.request_key,OLD.scheduled_at) THEN
    RAISE EXCEPTION 'preparation snapshot is immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION topics.guard_preparation_snapshot() FROM PUBLIC;
