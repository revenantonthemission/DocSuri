-- ApprovedExport owns these records (U6); account and research identity is referenced
-- by stable ID only and never written here. One writer per table. The export rules are
-- enforced in place: the pending first-configure reservation (R-01, R-02), connection
-- revisions (BR1.3-BR1.6), immutable preview revisions with one trim (BR2.3, BR2.6,
-- D12), the approval and effect state machines (BR3.1-BR3.6, BR4.3, BR5.1), consecutive
-- attempts (BR4.2) with NFR4.8's attempt-before-executing rule, and insert-only checks.
-- The runtime role reads no envelope column and deletes nothing (D13).
CREATE TABLE export.connection (
    id uuid PRIMARY KEY,
    account_id uuid NOT NULL UNIQUE,
    revision integer NOT NULL CHECK (revision >= 0),
    provider text NOT NULL DEFAULT 'notion' CHECK (provider IN ('notion')),
    state text NOT NULL
        CHECK (state IN ('pending','connected','disconnected','revoked','unavailable')),
    pending_holder uuid,
    pending_started_at timestamptz,
    sealed_token bytea,
    token_key_version text CHECK (token_key_version ~ '^u6-[0-9a-f]{32}$'),
    validated_at timestamptz,
    workspace_name text CHECK (octet_length(workspace_name) BETWEEN 1 AND 8000),
    workspace_id text CHECK (octet_length(workspace_id) BETWEEN 1 AND 128),
    connection_user_id text CHECK (octet_length(connection_user_id) BETWEEN 1 AND 128),
    creation_capability text NOT NULL DEFAULT 'unknown'
        CHECK (creation_capability IN ('unknown','confirmed','refused')),
    last_destination_id text CHECK (last_destination_id ~ '^[0-9a-f]{32}$'),
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    -- R-01: the internal reservation is exactly revision 0, held by one check.
    CHECK ((state = 'pending') = (revision = 0)),
    CHECK ((state = 'pending') = (pending_holder IS NOT NULL)),
    CHECK ((pending_holder IS NULL) = (pending_started_at IS NULL)),
    -- An envelope exists exactly while the token is in use (NFR3.7); none while pending.
    CHECK ((state IN ('connected','unavailable')) = (sealed_token IS NOT NULL)),
    CHECK ((sealed_token IS NULL) = (token_key_version IS NULL)),
    -- envelope = "DSE1" | len(version) | version | nonce(12) | AES-256-GCM(token)+tag(16),
    -- and the version column equals the envelope's version field (security design §4.1).
    CHECK (CASE WHEN sealed_token IS NULL OR token_key_version IS NULL THEN true
        WHEN octet_length(sealed_token) NOT BETWEEN 69 AND 4096 THEN false
        ELSE substring(sealed_token FROM 1 FOR 4) = '\x44534531'::bytea
            AND get_byte(sealed_token, 4) = octet_length(token_key_version)
            AND substring(sealed_token FROM 6 FOR octet_length(token_key_version))
                = decode(token_key_version, 'escape') END),
    CHECK (CASE jsonb_typeof(limitations) WHEN 'array'
        THEN jsonb_array_length(limitations) <= 16 ELSE false END)
);
CREATE INDEX connection_stale_pending ON export.connection(pending_started_at) WHERE state = 'pending';

-- D6: one pace record per connection, created with it and removed with it.
CREATE TABLE export.connection_pace (
    connection_id uuid PRIMARY KEY REFERENCES export.connection(id) ON DELETE CASCADE,
    next_slot_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- One previewId per export pair (account, source artifact, destination); BR2.3.
CREATE TABLE export.preview_pair (
    preview_id uuid PRIMARY KEY,
    account_id uuid NOT NULL,
    artifact_id uuid NOT NULL,
    destination_id text NOT NULL CHECK (destination_id ~ '^[0-9a-f]{32}$'),
    -- The latest revision number ever prepared; maintained by the revision insert guard.
    current_revision integer NOT NULL DEFAULT 0 CHECK (current_revision >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (account_id, artifact_id, destination_id)
);

CREATE TABLE export.preview_revision (
    preview_id uuid NOT NULL REFERENCES export.preview_pair(preview_id) ON DELETE CASCADE,
    revision integer NOT NULL CHECK (revision > 0),
    source_revision text NOT NULL CHECK (octet_length(source_revision) BETWEEN 1 AND 128),
    source_content_hash text NOT NULL CHECK (source_content_hash ~ '^[0-9a-f]{64}$'),
    source_eligibility_revision text NOT NULL
        CHECK (octet_length(source_eligibility_revision) BETWEEN 1 AND 128),
    source_title text NOT NULL CHECK (octet_length(source_title) BETWEEN 1 AND 8000),
    connection_id uuid NOT NULL REFERENCES export.connection(id),
    connection_revision integer NOT NULL CHECK (connection_revision > 0),
    destination jsonb NOT NULL CHECK (jsonb_typeof(destination) = 'object'),
    render_policy jsonb NOT NULL CHECK (jsonb_typeof(render_policy) = 'object'),
    marker text NOT NULL UNIQUE CHECK (octet_length(marker) BETWEEN 1 AND 200),
    rendered_blocks jsonb CHECK (jsonb_typeof(rendered_blocks) = 'object'),
    rendered_text text CHECK (octet_length(rendered_text) <= 2000000),
    rendered_content_hash text NOT NULL CHECK (rendered_content_hash ~ '^[0-9a-f]{64}$'),
    binding_hash text NOT NULL CHECK (binding_hash ~ '^[0-9a-f]{64}$'),
    earlier_exports jsonb NOT NULL DEFAULT '[]'::jsonb,
    prepared_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    trimmed_at timestamptz,
    PRIMARY KEY (preview_id, revision),
    -- The two rendered columns exist together, exactly until the one trim (BR2.6).
    CHECK ((rendered_blocks IS NULL) = (rendered_text IS NULL)),
    CHECK ((rendered_blocks IS NULL) = (trimmed_at IS NOT NULL)),
    CHECK (CASE jsonb_typeof(earlier_exports) WHEN 'array'
        THEN jsonb_array_length(earlier_exports) <= 20 ELSE false END)
);
CREATE INDEX preview_revision_retention ON export.preview_revision(prepared_at);

CREATE TABLE export.approval (
    id uuid PRIMARY KEY,
    account_id uuid NOT NULL,
    preview_id uuid NOT NULL,
    preview_revision integer NOT NULL,
    binding_hash text NOT NULL CHECK (binding_hash ~ '^[0-9a-f]{64}$'),
    policy jsonb NOT NULL CHECK (jsonb_typeof(policy) = 'object'),
    approved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    -- Validity is the binding, never a clock (BR3.5): the frozen expired is never entered.
    expires_at timestamptz CHECK (expires_at IS NULL),
    state text NOT NULL DEFAULT 'approved'
        CHECK (state IN ('approved','consumed','cancelled','invalidated')),
    invalidation_reason text CHECK (invalidation_reason IN
        ('source-changed','destination-changed','connection-changed','authority-revoked','account-withdrawn')),
    approving_session uuid NOT NULL,
    request_key uuid NOT NULL,
    CHECK ((state = 'invalidated') = (invalidation_reason IS NOT NULL)),
    UNIQUE (account_id, request_key),
    -- One approval per preview revision (BR3.2); deliberately not cascading, so no
    -- approved revision can ever be removed.
    UNIQUE (preview_id, preview_revision),
    FOREIGN KEY (preview_id, preview_revision) REFERENCES export.preview_revision(preview_id, revision)
);
CREATE INDEX approval_history ON export.approval(account_id, approved_at, id);
CREATE INDEX approval_open ON export.approval(account_id) WHERE state = 'approved';

CREATE TABLE export.effect (
    id uuid PRIMARY KEY,
    approval_id uuid NOT NULL UNIQUE REFERENCES export.approval(id) ON DELETE CASCADE,
    account_id uuid NOT NULL,
    artifact_id uuid NOT NULL,
    destination_id text NOT NULL CHECK (destination_id ~ '^[0-9a-f]{32}$'),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    binding_hash text NOT NULL CHECK (binding_hash ~ '^[0-9a-f]{64}$'),
    state text NOT NULL DEFAULT 'accepted' CHECK (state IN
        ('accepted','executing','succeeded','failed','unknown','cancelled','invalidated')),
    marker text NOT NULL UNIQUE CHECK (octet_length(marker) BETWEEN 1 AND 200),
    request_key uuid NOT NULL,
    accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    waiting_since timestamptz,
    next_attempt_at timestamptz,
    rate_limit_started_at timestamptz,
    next_check_at timestamptz,
    scanning_stopped_at timestamptz,
    ended_at timestamptz,
    remote_reference text CHECK (octet_length(remote_reference) BETWEEN 1 AND 128),
    remote_url text CHECK (octet_length(remote_url) BETWEEN 1 AND 2048),
    reconciliation_evidence_hash text CHECK (reconciliation_evidence_hash ~ '^[0-9a-f]{64}$'),
    outcome_reason text CHECK (outcome_reason IN (
        'token-invalid','no-access','destination-missing','content-rejected',
        'workspace-block-limit','provider-blocked','rate-limit-budget-spent',
        'not-found-after-checks','owner-settled-delivered','owner-settled-not-delivered',
        'dependency-unavailable','policy-unresolved','source-changed','destination-changed',
        'connection-changed','authority-revoked','account-withdrawn','owner-cancelled')),
    settled_by text CHECK (settled_by IN ('provider','reconciliation','owner')),
    owner_assumption text CHECK (octet_length(owner_assumption) BETWEEN 1 AND 2000),
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (account_id, request_key),
    CHECK ((state IN ('succeeded','failed','cancelled','invalidated')) = (ended_at IS NOT NULL)),
    CHECK (remote_reference IS NULL OR state = 'succeeded'),
    CHECK (state NOT IN ('failed','invalidated','cancelled') OR outcome_reason IS NOT NULL),
    CHECK (settled_by IS NULL OR state IN ('succeeded','failed')),
    CHECK (CASE jsonb_typeof(limitations) WHEN 'array'
        THEN jsonb_array_length(limitations) <= 16 ELSE false END)
);
-- BR5.1: at most one export in flight per owner.
CREATE UNIQUE INDEX effect_in_flight ON export.effect (account_id) WHERE state IN ('accepted','executing');
CREATE INDEX effect_pair ON export.effect (account_id, artifact_id, destination_id, state);
CREATE INDEX effect_rolling_hour ON export.effect (account_id, accepted_at);
CREATE INDEX effect_due ON export.effect (state, accepted_at) WHERE state IN ('accepted','executing','unknown');

CREATE TABLE export.attempt (
    id uuid PRIMARY KEY,
    effect_id uuid NOT NULL REFERENCES export.effect(id) ON DELETE CASCADE,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    started_at timestamptz NOT NULL,
    deadline_at timestamptz NOT NULL,
    writer_identity text NOT NULL CHECK (octet_length(writer_identity) BETWEEN 1 AND 128),
    connection_revision integer NOT NULL CHECK (connection_revision > 0),
    ended_at timestamptz,
    response_class text CHECK (response_class IN ('created','refused','rate-limited','uncertain')),
    provider_request_id text CHECK (octet_length(provider_request_id) BETWEEN 1 AND 128),
    path_kind text NOT NULL CHECK (path_kind IN ('synthetic','real')),
    creator_confirmed boolean,
    UNIQUE (effect_id, attempt_number),
    CHECK (deadline_at > started_at),
    CHECK ((response_class IS NULL) = (ended_at IS NULL))
);
-- One outstanding attempt per effect.
CREATE UNIQUE INDEX attempt_outstanding ON export.attempt (effect_id) WHERE ended_at IS NULL;

CREATE TABLE export.reconciliation_check (
    id uuid PRIMARY KEY,
    effect_id uuid NOT NULL REFERENCES export.effect(id) ON DELETE CASCADE,
    checked_at timestamptz NOT NULL,
    window_start timestamptz NOT NULL,
    result text NOT NULL
        CHECK (result IN ('marker-found','not-found','listing-unavailable','listing-incomplete')),
    remote_reference text CHECK (octet_length(remote_reference) BETWEEN 1 AND 128),
    other_marked_pages jsonb NOT NULL DEFAULT '[]'::jsonb,
    evidence_hash text NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
    CHECK ((result = 'marker-found') = (remote_reference IS NOT NULL)),
    CHECK (CASE jsonb_typeof(other_marked_pages) WHEN 'array'
        THEN jsonb_array_length(other_marked_pages) <= 10 ELSE false END)
);
CREATE INDEX reconciliation_check_effect ON export.reconciliation_check (effect_id, checked_at);

-- Configure and settle replays; the input hash covers the request without the token,
-- and the response holds only identifiers, state, revision or the refusal code.
CREATE TABLE export.replay_record (
    account_id uuid NOT NULL,
    operation text NOT NULL CHECK (operation IN ('configure','settle')),
    operation_key uuid NOT NULL,
    input_hash text NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    response jsonb NOT NULL CHECK (jsonb_typeof(response) = 'object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (account_id, operation, operation_key)
);

-- Exactly the columns backend.lifecycle_effects.apply_owner_effect writes.
CREATE TABLE export.lifecycle_evidence (
    request_id uuid NOT NULL, scope text NOT NULL, generation bigint NOT NULL,
    policy_ref jsonb NOT NULL, manifest_revision text NOT NULL, evidence_ref uuid NOT NULL,
    PRIMARY KEY (request_id, scope)
);

-- Count-only evidence: no account column, so it survives erasure (BR6.1, BR6.2, BR7.2).
CREATE TABLE export.lifecycle_counts (
    request_id uuid NOT NULL,
    scope text NOT NULL CHECK (scope IN ('live_records','pending_work','external_copies')),
    action text NOT NULL CHECK (action IN ('withdraw','reactivate','erase')),
    reason_key text NOT NULL
        CHECK (reason_key IN ('owner-scope-complete','external-copies-retained-by-owner')),
    approvals_invalidated integer NOT NULL DEFAULT 0 CHECK (approvals_invalidated >= 0),
    effects_invalidated integer NOT NULL DEFAULT 0 CHECK (effects_invalidated >= 0),
    exports_in_flight integer NOT NULL DEFAULT 0 CHECK (exports_in_flight >= 0),
    exports_unknown integer NOT NULL DEFAULT 0 CHECK (exports_unknown >= 0),
    pages_exported integer NOT NULL DEFAULT 0 CHECK (pages_exported >= 0),
    pages_possibly_created integer NOT NULL DEFAULT 0 CHECK (pages_possibly_created >= 0),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (request_id, scope)
);

-- The export lane's last outcome category and its time (logical-components §8).
CREATE TABLE export.lane_status (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    outcome text NOT NULL CHECK (outcome ~ '^[a-z][a-z0-9-]{0,63}$'),
    observed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE FUNCTION export.guard_connection_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.state <> 'pending' OR NEW.creation_capability <> 'unknown'
       OR NEW.last_destination_id IS NOT NULL THEN
        RAISE EXCEPTION 'a connection starts as a pending reservation' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER connection_insert BEFORE INSERT ON export.connection FOR EACH ROW EXECUTE FUNCTION export.guard_connection_insert();

CREATE FUNCTION export.guard_connection_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.id,NEW.account_id,NEW.provider,NEW.created_at)
       IS DISTINCT FROM (OLD.id,OLD.account_id,OLD.provider,OLD.created_at) THEN
        RAISE EXCEPTION 'connection identity is immutable' USING ERRCODE = '23514';
    END IF;
    IF NEW.revision < OLD.revision THEN
        RAISE EXCEPTION 'connection revision cannot regress' USING ERRCODE = '23514';
    END IF;
    IF OLD.state = 'pending' THEN
        IF NEW.state = 'pending' THEN
            -- Takeover: only the holder and its start time change (R-02).
            IF (NEW.revision,NEW.sealed_token,NEW.token_key_version,NEW.validated_at,
                NEW.workspace_name,NEW.workspace_id,NEW.connection_user_id,
                NEW.creation_capability,NEW.last_destination_id,NEW.limitations)
               IS DISTINCT FROM
               (OLD.revision,OLD.sealed_token,OLD.token_key_version,OLD.validated_at,
                OLD.workspace_name,OLD.workspace_id,OLD.connection_user_id,
                OLD.creation_capability,OLD.last_destination_id,OLD.limitations) THEN
                RAISE EXCEPTION 'a pending reservation changes only its holder' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END IF;
        IF NEW.state <> 'connected' OR NEW.revision <> 1 OR NEW.creation_capability <> 'unknown' THEN
            RAISE EXCEPTION 'a pending reservation becomes connected at revision 1' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.state = 'pending' THEN
        RAISE EXCEPTION 'a connection never returns to pending' USING ERRCODE = '23514';
    END IF;
    IF NEW.revision = OLD.revision THEN
        IF (NEW.sealed_token,NEW.token_key_version) IS DISTINCT FROM (OLD.sealed_token,OLD.token_key_version) THEN
            -- Operator re-seal: only the envelope and its key version change.
            IF OLD.sealed_token IS NULL OR NEW.sealed_token IS NULL
               OR (NEW.state,NEW.validated_at,NEW.workspace_name,NEW.workspace_id,
                   NEW.connection_user_id,NEW.creation_capability,NEW.last_destination_id,NEW.limitations)
                  IS DISTINCT FROM
                  (OLD.state,OLD.validated_at,OLD.workspace_name,OLD.workspace_id,
                   OLD.connection_user_id,OLD.creation_capability,OLD.last_destination_id,OLD.limitations) THEN
                RAISE EXCEPTION 'a re-seal changes only the envelope and its key version' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END IF;
        -- BR1.6: unavailability and recovery keep the revision; outcome facts may change.
        IF NEW.state IS DISTINCT FROM OLD.state
           AND (OLD.state,NEW.state) NOT IN (('connected','unavailable'),('unavailable','connected')) THEN
            RAISE EXCEPTION 'only unavailability keeps the connection revision' USING ERRCODE = '23514';
        END IF;
        IF (NEW.validated_at,NEW.workspace_name,NEW.workspace_id,NEW.connection_user_id,NEW.limitations)
           IS DISTINCT FROM
           (OLD.validated_at,OLD.workspace_name,OLD.workspace_id,OLD.connection_user_id,OLD.limitations) THEN
            RAISE EXCEPTION 'connection facts change only with a new revision' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.revision <> OLD.revision + 1 THEN
        RAISE EXCEPTION 'connection revision advances by exactly one' USING ERRCODE = '23514';
    END IF;
    -- Replace, reconnect, disconnect, revocation and withdrawal (BR1.3, BR1.4, BR6.1).
    IF NOT ((OLD.state = 'connected' AND NEW.state IN ('connected','disconnected','revoked'))
         OR (OLD.state = 'unavailable' AND NEW.state IN ('disconnected','revoked'))
         OR (OLD.state IN ('disconnected','revoked') AND NEW.state = 'connected')) THEN
        RAISE EXCEPTION 'invalid connection transition' USING ERRCODE = '23514';
    END IF;
    IF NEW.state = 'connected' AND NEW.creation_capability <> 'unknown' THEN
        RAISE EXCEPTION 'a new token starts with unknown creation capability' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER connection_update BEFORE UPDATE ON export.connection FOR EACH ROW EXECUTE FUNCTION export.guard_connection_update();

CREATE FUNCTION export.guard_pair_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.current_revision <> 0 THEN
        RAISE EXCEPTION 'an export pair starts without revisions' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER pair_insert BEFORE INSERT ON export.preview_pair FOR EACH ROW EXECUTE FUNCTION export.guard_pair_insert();

CREATE FUNCTION export.guard_pair_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.preview_id,NEW.account_id,NEW.artifact_id,NEW.destination_id,NEW.created_at)
       IS DISTINCT FROM (OLD.preview_id,OLD.account_id,OLD.artifact_id,OLD.destination_id,OLD.created_at) THEN
        RAISE EXCEPTION 'export pair identity is immutable' USING ERRCODE = '23514';
    END IF;
    IF NEW.current_revision <> OLD.current_revision AND NEW.current_revision <> OLD.current_revision + 1 THEN
        RAISE EXCEPTION 'preview revisions advance by one' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER pair_update BEFORE UPDATE ON export.preview_pair FOR EACH ROW EXECUTE FUNCTION export.guard_pair_update();

CREATE FUNCTION export.guard_revision_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE latest integer;
BEGIN
    SELECT current_revision INTO latest FROM export.preview_pair WHERE preview_id = NEW.preview_id FOR UPDATE;
    IF NOT FOUND THEN
        RETURN NEW;  -- The foreign key refuses an unknown pair.
    END IF;
    IF NEW.revision <> latest + 1 THEN
        RAISE EXCEPTION 'preview revisions are consecutive per export pair' USING ERRCODE = '23514';
    END IF;
    IF NEW.trimmed_at IS NOT NULL THEN
        RAISE EXCEPTION 'a preview revision starts with its rendered tree' USING ERRCODE = '23514';
    END IF;
    UPDATE export.preview_pair SET current_revision = NEW.revision WHERE preview_id = NEW.preview_id;
    RETURN NEW;
END $$;
CREATE TRIGGER revision_insert BEFORE INSERT ON export.preview_revision FOR EACH ROW EXECUTE FUNCTION export.guard_revision_insert();

CREATE FUNCTION export.guard_revision_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF OLD.trimmed_at IS NOT NULL THEN
        RAISE EXCEPTION 'a trimmed preview revision is frozen' USING ERRCODE = '23514';
    END IF;
    IF (NEW.preview_id,NEW.revision,NEW.source_revision,NEW.source_content_hash,
        NEW.source_eligibility_revision,NEW.source_title,NEW.connection_id,NEW.connection_revision,
        NEW.destination,NEW.render_policy,NEW.marker,NEW.rendered_content_hash,NEW.binding_hash,
        NEW.earlier_exports,NEW.prepared_at)
       IS DISTINCT FROM
       (OLD.preview_id,OLD.revision,OLD.source_revision,OLD.source_content_hash,
        OLD.source_eligibility_revision,OLD.source_title,OLD.connection_id,OLD.connection_revision,
        OLD.destination,OLD.render_policy,OLD.marker,OLD.rendered_content_hash,OLD.binding_hash,
        OLD.earlier_exports,OLD.prepared_at) THEN
        RAISE EXCEPTION 'a preview revision is immutable' USING ERRCODE = '23514';
    END IF;
    -- D12: the only change is the one trim of the rendered tree and text.
    IF NEW.trimmed_at IS NULL
       AND (NEW.rendered_blocks,NEW.rendered_text) IS DISTINCT FROM (OLD.rendered_blocks,OLD.rendered_text) THEN
        RAISE EXCEPTION 'a preview revision is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER revision_update BEFORE UPDATE ON export.preview_revision FOR EACH ROW EXECUTE FUNCTION export.guard_revision_update();

CREATE FUNCTION export.guard_approval_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE bound_hash text; owner_id uuid; trimmed timestamptz;
BEGIN
    IF NEW.state <> 'approved' THEN
        RAISE EXCEPTION 'an approval starts approved' USING ERRCODE = '23514';
    END IF;
    SELECT r.binding_hash, p.account_id, r.trimmed_at INTO bound_hash, owner_id, trimmed
      FROM export.preview_revision r JOIN export.preview_pair p ON p.preview_id = r.preview_id
     WHERE r.preview_id = NEW.preview_id AND r.revision = NEW.preview_revision;
    IF NOT FOUND THEN
        RETURN NEW;  -- The foreign key refuses an unknown preview revision.
    END IF;
    IF bound_hash <> NEW.binding_hash OR owner_id <> NEW.account_id OR trimmed IS NOT NULL THEN
        RAISE EXCEPTION 'an approval binds its own untrimmed preview revision' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER approval_insert BEFORE INSERT ON export.approval FOR EACH ROW EXECUTE FUNCTION export.guard_approval_insert();

CREATE FUNCTION export.guard_approval_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF OLD.state <> 'approved' THEN
        RAISE EXCEPTION 'a consumed, cancelled or invalidated approval is frozen' USING ERRCODE = '23514';
    END IF;
    IF (NEW.id,NEW.account_id,NEW.preview_id,NEW.preview_revision,NEW.binding_hash,NEW.policy,
        NEW.approved_at,NEW.expires_at,NEW.approving_session,NEW.request_key)
       IS DISTINCT FROM
       (OLD.id,OLD.account_id,OLD.preview_id,OLD.preview_revision,OLD.binding_hash,OLD.policy,
        OLD.approved_at,OLD.expires_at,OLD.approving_session,OLD.request_key) THEN
        RAISE EXCEPTION 'the approval binding is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER approval_update BEFORE UPDATE ON export.approval FOR EACH ROW EXECUTE FUNCTION export.guard_approval_update();

CREATE FUNCTION export.guard_effect_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE a export.approval%ROWTYPE; pair_artifact uuid; pair_destination text; bound_marker text;
BEGIN
    IF NEW.state <> 'accepted' OR NEW.revision <> 1 THEN
        RAISE EXCEPTION 'an effect starts accepted at revision 1' USING ERRCODE = '23514';
    END IF;
    SELECT * INTO a FROM export.approval WHERE id = NEW.approval_id;
    IF NOT FOUND THEN
        RETURN NEW;  -- The foreign key refuses an unknown approval.
    END IF;
    SELECT p.artifact_id, p.destination_id, r.marker INTO pair_artifact, pair_destination, bound_marker
      FROM export.preview_revision r JOIN export.preview_pair p ON p.preview_id = r.preview_id
     WHERE r.preview_id = a.preview_id AND r.revision = a.preview_revision;
    -- A bind consumes the approval in the same statement, so either state is accepted.
    IF a.state NOT IN ('approved','consumed') OR a.account_id <> NEW.account_id
       OR a.binding_hash <> NEW.binding_hash OR pair_artifact <> NEW.artifact_id
       OR pair_destination <> NEW.destination_id OR bound_marker <> NEW.marker THEN
        RAISE EXCEPTION 'an effect copies its approval binding and marker' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER effect_insert BEFORE INSERT ON export.effect FOR EACH ROW EXECUTE FUNCTION export.guard_effect_insert();

CREATE FUNCTION export.guard_effect_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF OLD.state IN ('succeeded','failed','cancelled','invalidated') THEN
        RAISE EXCEPTION 'a settled effect is frozen' USING ERRCODE = '23514';
    END IF;
    IF (NEW.id,NEW.approval_id,NEW.account_id,NEW.artifact_id,NEW.destination_id,NEW.binding_hash,
        NEW.marker,NEW.request_key,NEW.accepted_at)
       IS DISTINCT FROM
       (OLD.id,OLD.approval_id,OLD.account_id,OLD.artifact_id,OLD.destination_id,OLD.binding_hash,
        OLD.marker,OLD.request_key,OLD.accepted_at) THEN
        RAISE EXCEPTION 'effect identity is immutable' USING ERRCODE = '23514';
    END IF;
    IF NEW.revision <> OLD.revision + 1 THEN
        RAISE EXCEPTION 'the effect revision advances by one on every update' USING ERRCODE = '23514';
    END IF;
    -- BR4.3: unknown never returns to executing, failed never returns to accepted.
    IF NEW.state IS DISTINCT FROM OLD.state AND NOT (
        (OLD.state = 'accepted' AND NEW.state IN ('executing','invalidated','failed','cancelled')) OR
        (OLD.state = 'executing' AND NEW.state IN ('succeeded','failed','unknown')) OR
        (OLD.state = 'unknown' AND NEW.state IN ('succeeded','failed'))) THEN
        RAISE EXCEPTION 'invalid export effect transition' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER effect_update BEFORE UPDATE ON export.effect FOR EACH ROW EXECUTE FUNCTION export.guard_effect_update();

-- NFR4.8: a commit never leaves an executing effect without its attempt.
CREATE FUNCTION export.require_executing_attempt() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM export.effect e WHERE e.id = NEW.id AND e.state = 'executing'
               AND NOT EXISTS (SELECT 1 FROM export.attempt t WHERE t.effect_id = e.id)) THEN
        RAISE EXCEPTION 'an executing effect needs its attempt' USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER effect_attempt_required AFTER INSERT OR UPDATE ON export.effect
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION export.require_executing_attempt();

CREATE FUNCTION export.guard_attempt_insert() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE effect_state text; latest export.attempt%ROWTYPE;
BEGIN
    SELECT state INTO effect_state FROM export.effect WHERE id = NEW.effect_id;
    IF NOT FOUND THEN
        RETURN NEW;  -- The foreign key refuses an unknown effect.
    END IF;
    IF effect_state <> 'executing' THEN
        RAISE EXCEPTION 'an attempt starts only while its effect is executing' USING ERRCODE = '23514';
    END IF;
    IF (NEW.ended_at,NEW.response_class,NEW.provider_request_id,NEW.creator_confirmed)
       IS DISTINCT FROM (NULL::timestamptz,NULL::text,NULL::text,NULL::boolean) THEN
        RAISE EXCEPTION 'an attempt starts outstanding' USING ERRCODE = '23514';
    END IF;
    SELECT * INTO latest FROM export.attempt WHERE effect_id = NEW.effect_id
     ORDER BY attempt_number DESC LIMIT 1;
    IF NOT FOUND THEN
        IF NEW.attempt_number <> 1 THEN
            RAISE EXCEPTION 'attempt numbers are consecutive' USING ERRCODE = '23514';
        END IF;
    ELSIF NEW.attempt_number <> latest.attempt_number + 1 THEN
        RAISE EXCEPTION 'attempt numbers are consecutive' USING ERRCODE = '23514';
    ELSIF latest.response_class IS DISTINCT FROM 'rate-limited' THEN
        RAISE EXCEPTION 'only a rate-limited attempt is followed by another' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER attempt_insert BEFORE INSERT ON export.attempt FOR EACH ROW EXECUTE FUNCTION export.guard_attempt_insert();

CREATE FUNCTION export.guard_attempt_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.id,NEW.effect_id,NEW.attempt_number,NEW.started_at,NEW.deadline_at,NEW.writer_identity,
        NEW.connection_revision,NEW.path_kind)
       IS DISTINCT FROM
       (OLD.id,OLD.effect_id,OLD.attempt_number,OLD.started_at,OLD.deadline_at,OLD.writer_identity,
        OLD.connection_revision,OLD.path_kind) THEN
        RAISE EXCEPTION 'attempt identity is immutable' USING ERRCODE = '23514';
    END IF;
    IF (OLD.ended_at IS NOT NULL AND (NEW.ended_at,NEW.response_class) IS DISTINCT FROM (OLD.ended_at,OLD.response_class))
       OR (OLD.provider_request_id IS NOT NULL AND NEW.provider_request_id IS DISTINCT FROM OLD.provider_request_id)
       OR (OLD.creator_confirmed IS NOT NULL AND NEW.creator_confirmed IS DISTINCT FROM OLD.creator_confirmed) THEN
        RAISE EXCEPTION 'attempt outcome facts are set once' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER attempt_update BEFORE UPDATE ON export.attempt FOR EACH ROW EXECUTE FUNCTION export.guard_attempt_update();

CREATE FUNCTION export.refuse_check_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'reconciliation checks are insert-only' USING ERRCODE = '23514';
END $$;
CREATE TRIGGER check_update BEFORE UPDATE ON export.reconciliation_check FOR EACH ROW EXECUTE FUNCTION export.refuse_check_update();

-- D13: the runtime role reads, inserts and updates every column but the envelope pair,
-- and deletes nothing; deletes run only through owner-checked definer functions.
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA export FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON export.connection_pace,export.preview_pair,export.preview_revision,
    export.approval,export.effect,export.attempt,export.reconciliation_check,export.replay_record,
    export.lifecycle_evidence,export.lifecycle_counts,export.lane_status TO docsuri_export;
GRANT SELECT (id,account_id,revision,provider,state,pending_holder,pending_started_at,validated_at,
        workspace_name,workspace_id,connection_user_id,creation_capability,last_destination_id,
        limitations,created_at,updated_at),
    INSERT (id,account_id,revision,provider,state,pending_holder,pending_started_at,validated_at,
        workspace_name,workspace_id,connection_user_id,creation_capability,last_destination_id,
        limitations,created_at,updated_at),
    UPDATE (id,account_id,revision,provider,state,pending_holder,pending_started_at,validated_at,
        workspace_name,workspace_id,connection_user_id,creation_capability,last_destination_id,
        limitations,created_at,updated_at)
    ON export.connection TO docsuri_export;
