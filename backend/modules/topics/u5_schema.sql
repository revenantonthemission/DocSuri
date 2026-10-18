-- TopicsDigests owns these records (U5); account and corpus identity is
-- referenced by stable ID only and never written here. One writer per table;
-- the digest rules are enforced in place: identity immutability, monotonic
-- settings revisions (BR1.3), chronological window ordering (BR2.4),
-- the DigestRun state machine (BR3.1), outcome/reconciliation facts and the
-- per-topic delivery watermark (BR2.2).
CREATE TABLE topics.followed_topic (
    id uuid PRIMARY KEY,
    account_id uuid NOT NULL,
    topic_key text NOT NULL CHECK (octet_length(topic_key) BETWEEN 1 AND 160),
    display_name text NOT NULL CHECK (octet_length(display_name) BETWEEN 1 AND 160),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','unsubscribed')),
    followed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (account_id, topic_key)
);
CREATE INDEX followed_topic_status ON topics.followed_topic(status,account_id);
CREATE TABLE topics.digest_settings (
    id uuid PRIMARY KEY,
    topic_id uuid NOT NULL UNIQUE REFERENCES topics.followed_topic(id) ON DELETE CASCADE,
    cadence text NOT NULL CHECK (cadence IN ('daily','weekly')),
    delivery_time_local time NOT NULL,
    delivery_day text CHECK (delivery_day IN ('mon','tue','wed','thu','fri','sat','sun')),
    content_window_days integer NOT NULL CHECK (content_window_days IN (7,30)),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((cadence = 'weekly') = (delivery_day IS NOT NULL))
);
CREATE TABLE topics.digest_run (
    id uuid PRIMARY KEY,
    topic_id uuid NOT NULL REFERENCES topics.followed_topic(id) ON DELETE CASCADE,
    window_start date NOT NULL,
    window_end date NOT NULL,
    state text NOT NULL DEFAULT 'prepared'
        CHECK (state IN ('prepared','sending','sent','failed','unknown','empty','discarded')),
    digest_content jsonb NOT NULL,
    settings_revision integer NOT NULL CHECK (settings_revision > 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (window_end >= window_start),
    CHECK (CASE jsonb_typeof(digest_content) WHEN 'array'
        THEN state <> 'empty' OR jsonb_array_length(digest_content) = 0 ELSE false END)
);
-- At most one non-discarded run per (topic, window): scheduler re-fires and
-- crash re-checks adopt the existing run (BR2.4); a revision-discard re-prepares
-- the SAME window as a new row, which only the discarded exclusion allows.
CREATE UNIQUE INDEX digest_run_window ON topics.digest_run(topic_id,window_start,window_end)
    WHERE state <> 'discarded';
-- At most one send attempt in flight per topic (BR3.1).
CREATE UNIQUE INDEX digest_run_single_flight ON topics.digest_run(topic_id) WHERE state = 'sending';
-- Unreconciled unknowns pause the topic's sends (BR3.2).
CREATE INDEX digest_run_unknown_pause ON topics.digest_run(topic_id) WHERE state = 'unknown';
-- Bounded restart/recovery sweep for orphaned attempts (BR3.4).
CREATE INDEX digest_run_sending_age ON topics.digest_run(updated_at,id) WHERE state = 'sending';
CREATE TABLE topics.delivery_outcome (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL UNIQUE REFERENCES topics.digest_run(id) ON DELETE CASCADE,
    observed_state text NOT NULL CHECK (observed_state IN ('sent','failed','unknown','empty')),
    observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    reconciled_state text CHECK (reconciled_state IN ('sent','failed')),
    reconciled_at timestamptz,
    failure_reason text CHECK (failure_reason IS NULL OR octet_length(failure_reason) BETWEEN 1 AND 160),
    CHECK ((reconciled_state IS NULL) = (reconciled_at IS NULL))
);
CREATE TABLE topics.send_log_entry (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL UNIQUE REFERENCES topics.digest_run(id) ON DELETE CASCADE,
    attempted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    transport_receipt text CHECK (transport_receipt IS NULL OR octet_length(transport_receipt) BETWEEN 1 AND 160),
    acknowledged_at timestamptz,
    path_kind text NOT NULL CHECK (path_kind IN ('real','local-sink'))
);
CREATE TABLE topics.topic_delivery_watermark (
    id uuid PRIMARY KEY,
    topic_id uuid NOT NULL REFERENCES topics.followed_topic(id) ON DELETE CASCADE,
    content_id text NOT NULL CHECK (octet_length(content_id) BETWEEN 1 AND 160),
    included_in_run_id uuid NOT NULL REFERENCES topics.digest_run(id) ON DELETE CASCADE,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (topic_id, content_id)
);
CREATE TABLE topics.lifecycle_evidence (
    request_id uuid NOT NULL, scope text NOT NULL, generation bigint NOT NULL,
    policy_ref jsonb NOT NULL, manifest_revision text NOT NULL, evidence_ref uuid NOT NULL,
    PRIMARY KEY (request_id, scope)
);

CREATE FUNCTION topics.guard_topic_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.id,NEW.account_id,NEW.topic_key,NEW.followed_at)
       IS DISTINCT FROM (OLD.id,OLD.account_id,OLD.topic_key,OLD.followed_at) THEN
        RAISE EXCEPTION 'topic identity is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER topic_update BEFORE UPDATE ON topics.followed_topic FOR EACH ROW EXECUTE FUNCTION topics.guard_topic_update();

CREATE FUNCTION topics.guard_settings_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.id,NEW.topic_id) IS DISTINCT FROM (OLD.id,OLD.topic_id) THEN
        RAISE EXCEPTION 'settings identity is immutable' USING ERRCODE = '23514';
    END IF;
    IF (NEW.cadence,NEW.delivery_time_local,NEW.delivery_day,NEW.content_window_days)
       IS DISTINCT FROM (OLD.cadence,OLD.delivery_time_local,OLD.delivery_day,OLD.content_window_days)
       AND NEW.revision <= OLD.revision THEN
        RAISE EXCEPTION 'settings revision must advance with every change' USING ERRCODE = '23514';
    END IF;
    IF NEW.revision < OLD.revision THEN
        RAISE EXCEPTION 'settings revision cannot regress' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER settings_update BEFORE UPDATE ON topics.digest_settings FOR EACH ROW EXECUTE FUNCTION topics.guard_settings_update();

CREATE FUNCTION topics.guard_run_insert() RETURNS trigger
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
               AND r.window_start <= NEW.window_start
               AND r.state IN ('prepared','sending','unknown')) THEN
        RAISE EXCEPTION 'an earlier window is not terminal' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER run_insert BEFORE INSERT ON topics.digest_run FOR EACH ROW EXECUTE FUNCTION topics.guard_run_insert();

CREATE FUNCTION topics.guard_run_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.id,NEW.topic_id,NEW.window_start,NEW.window_end,NEW.digest_content,
        NEW.settings_revision,NEW.created_at)
       IS DISTINCT FROM
       (OLD.id,OLD.topic_id,OLD.window_start,OLD.window_end,OLD.digest_content,
        OLD.settings_revision,OLD.created_at) THEN
        RAISE EXCEPTION 'prepared window and content are immutable' USING ERRCODE = '23514';
    END IF;
    IF NEW.state IS DISTINCT FROM OLD.state AND NOT (
        (OLD.state = 'prepared' AND NEW.state IN ('sending','empty','discarded')) OR
        (OLD.state = 'sending' AND NEW.state IN ('sent','failed','unknown')) OR
        (OLD.state = 'unknown' AND NEW.state IN ('sent','failed'))) THEN
        RAISE EXCEPTION 'invalid digest run transition' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER run_update BEFORE UPDATE ON topics.digest_run FOR EACH ROW EXECUTE FUNCTION topics.guard_run_update();

CREATE FUNCTION topics.guard_outcome_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE run_state text;
BEGIN
    SELECT state INTO run_state FROM topics.digest_run WHERE id = NEW.run_id;
    IF NOT FOUND OR run_state IS DISTINCT FROM NEW.observed_state THEN
        RAISE EXCEPTION 'outcome must record the run state' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER outcome_insert BEFORE INSERT ON topics.delivery_outcome FOR EACH ROW EXECUTE FUNCTION topics.guard_outcome_insert();

CREATE FUNCTION topics.guard_outcome_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE run_state text;
BEGIN
    IF (NEW.id,NEW.run_id,NEW.observed_state,NEW.observed_at)
       IS DISTINCT FROM (OLD.id,OLD.run_id,OLD.observed_state,OLD.observed_at) THEN
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
CREATE TRIGGER outcome_update BEFORE UPDATE ON topics.delivery_outcome FOR EACH ROW EXECUTE FUNCTION topics.guard_outcome_update();

CREATE FUNCTION topics.guard_send_log_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE run_state text;
BEGIN
    SELECT state INTO run_state FROM topics.digest_run WHERE id = NEW.run_id;
    IF NOT FOUND OR run_state IS DISTINCT FROM 'sending' THEN
        RAISE EXCEPTION 'send log starts only with a sending run' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER send_log_insert BEFORE INSERT ON topics.send_log_entry FOR EACH ROW EXECUTE FUNCTION topics.guard_send_log_insert();

CREATE FUNCTION topics.guard_send_log_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.id,NEW.run_id,NEW.attempted_at,NEW.path_kind)
       IS DISTINCT FROM (OLD.id,OLD.run_id,OLD.attempted_at,OLD.path_kind) THEN
        RAISE EXCEPTION 'send log identity is immutable' USING ERRCODE = '23514';
    END IF;
    IF (OLD.transport_receipt IS NOT NULL AND NEW.transport_receipt IS DISTINCT FROM OLD.transport_receipt)
       OR (OLD.acknowledged_at IS NOT NULL AND NEW.acknowledged_at IS DISTINCT FROM OLD.acknowledged_at) THEN
        RAISE EXCEPTION 'transport receipt and acknowledgment are set once' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER send_log_update BEFORE UPDATE ON topics.send_log_entry FOR EACH ROW EXECUTE FUNCTION topics.guard_send_log_update();

CREATE FUNCTION topics.guard_watermark_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE run_state text; run_topic uuid;
BEGIN
    SELECT state,topic_id INTO run_state,run_topic FROM topics.digest_run WHERE id = NEW.included_in_run_id;
    IF NOT FOUND OR run_state IS DISTINCT FROM 'sent' OR run_topic IS DISTINCT FROM NEW.topic_id THEN
        RAISE EXCEPTION 'watermark requires this topic sent run' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER watermark_insert BEFORE INSERT ON topics.topic_delivery_watermark FOR EACH ROW EXECUTE FUNCTION topics.guard_watermark_insert();

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA topics FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA topics TO docsuri_topics;
GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA topics TO docsuri_topics;
