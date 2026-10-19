-- Provider refusal detail (appended; applied U5 migrations stay byte-identical).
-- A definite provider refusal records the provider's HTTP status and its short
-- machine-readable error name (e.g. `validation_error`), or the fixed
-- placeholder `name-unavailable` when the body did not carry a valid name. No
-- free-text provider message, request header, body or recipient is stored.
-- Refusals decided on this host before any network call use their own
-- failure_reason values and never carry a provider status.
ALTER TABLE topics.delivery_outcome
    ADD COLUMN provider_status smallint,
    ADD COLUMN provider_error text;
ALTER TABLE topics.delivery_outcome
    ADD CONSTRAINT delivery_outcome_provider_refusal CHECK (
        (provider_status IS NULL AND provider_error IS NULL)
        OR (observed_state = 'failed'
            AND failure_reason = 'delivery-path-refused'
            AND provider_status IN (400, 401, 403, 404, 413, 422, 429)
            AND provider_error IS NOT NULL
            AND (provider_error ~ '^[a-z][a-z0-9_]{0,63}$'
                 OR provider_error = 'name-unavailable'))
    );

-- Replaces the update guard from u5_schema.sql with the same rules, plus the
-- refusal detail joining the immutable observed facts.
CREATE OR REPLACE FUNCTION topics.guard_outcome_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE run_state text;
BEGIN
    IF (NEW.id,NEW.run_id,NEW.observed_state,NEW.observed_at,NEW.provider_status,NEW.provider_error)
       IS DISTINCT FROM (OLD.id,OLD.run_id,OLD.observed_state,OLD.observed_at,OLD.provider_status,OLD.provider_error) THEN
        RAISE EXCEPTION 'observed outcome is immutable' USING ERRCODE = '23514';
    END IF;
    IF (OLD.reconciled_state IS NOT NULL AND (NEW.reconciled_state,NEW.reconciled_at)
        IS DISTINCT FROM (OLD.reconciled_state,OLD.reconciled_at))
       OR (OLD.failure_reason IS NOT NULL AND NEW.failure_reason IS DISTINCT FROM OLD.failure_reason) THEN
        RAISE EXCEPTION 'recorded reconciliation is immutable' USING ERRCODE = '23514';
    END IF;
    IF OLD.reconciled_state IS NULL AND NEW.reconciled_state IS NOT NULL THEN
        SELECT state INTO run_state FROM topics.digest_run WHERE id = NEW.run_id;
        IF NOT FOUND OR run_state IS DISTINCT FROM NEW.reconciled_state THEN
            RAISE EXCEPTION 'reconciliation must match the run state' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION topics.guard_outcome_update() FROM PUBLIC;
