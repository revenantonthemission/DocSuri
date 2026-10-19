-- Real-send evidence retention (appended; applied U5 migrations stay byte-identical).
-- A real attempt records when its provider receipt must stop being kept: at
-- most 30 days after the attempt (the approved bound). Expiry clears only the
-- receipt and stamps evidence_expired_at; the row, its path and its attempt and
-- acknowledgement times stay, so the durable real-send allocation that counts
-- these rows is never replenished. Local-sink rows carry no retention bound.
-- The recipient address is never stored here: it stays in accounts.account.
ALTER TABLE topics.send_log_entry
    ADD COLUMN evidence_retain_until timestamptz,
    ADD COLUMN evidence_expired_at timestamptz;
ALTER TABLE topics.send_log_entry
    ADD CONSTRAINT send_log_real_retention CHECK (
        (path_kind = 'real') = (evidence_retain_until IS NOT NULL)
        AND (evidence_retain_until IS NULL
             OR evidence_retain_until BETWEEN attempted_at AND attempted_at + interval '30 days')
        AND (evidence_expired_at IS NULL
             OR (evidence_retain_until IS NOT NULL AND transport_receipt IS NULL))
    );

-- Replaces the update guard from u5_schema.sql with the same identity and
-- set-once rules plus one narrow exception: a receipt may be cleared exactly
-- once, together with evidence_expired_at, after its retention bound.
CREATE OR REPLACE FUNCTION topics.guard_send_log_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE expiring boolean;
BEGIN
    IF (NEW.id,NEW.run_id,NEW.attempted_at,NEW.path_kind,NEW.evidence_retain_until)
       IS DISTINCT FROM (OLD.id,OLD.run_id,OLD.attempted_at,OLD.path_kind,OLD.evidence_retain_until) THEN
        RAISE EXCEPTION 'send log identity is immutable' USING ERRCODE = '23514';
    END IF;
    IF OLD.evidence_expired_at IS NOT NULL
       AND (NEW.evidence_expired_at IS DISTINCT FROM OLD.evidence_expired_at
            OR NEW.transport_receipt IS NOT NULL) THEN
        RAISE EXCEPTION 'expired evidence stays expired' USING ERRCODE = '23514';
    END IF;
    expiring := OLD.evidence_expired_at IS NULL AND NEW.evidence_expired_at IS NOT NULL;
    IF expiring AND (OLD.path_kind <> 'real' OR NEW.transport_receipt IS NOT NULL
                     OR OLD.evidence_retain_until > clock_timestamp()) THEN
        RAISE EXCEPTION 'evidence retention bound not reached' USING ERRCODE = '23514';
    END IF;
    IF (NOT expiring AND OLD.transport_receipt IS NOT NULL
        AND NEW.transport_receipt IS DISTINCT FROM OLD.transport_receipt)
       OR (OLD.acknowledged_at IS NOT NULL AND NEW.acknowledged_at IS DISTINCT FROM OLD.acknowledged_at) THEN
        RAISE EXCEPTION 'transport receipt and acknowledgment are set once' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION topics.guard_send_log_update() FROM PUBLIC;

CREATE INDEX send_log_real_retention_due ON topics.send_log_entry (evidence_retain_until, id)
    WHERE path_kind = 'real' AND evidence_expired_at IS NULL;
