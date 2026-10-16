-- ResearchWorkspace owns these records; no public corpus identity is created.
CREATE TABLE research.context (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL,
    purpose text NOT NULL CHECK (purpose IN ('research','novelty')),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
    lifecycle text NOT NULL DEFAULT 'active' CHECK (lifecycle IN ('active','deleting','deleted')),
    deleted_at timestamptz, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (id,owner_id)
);
CREATE TABLE research.session (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL, context_id uuid NOT NULL,
    title text NOT NULL CHECK (octet_length(title) BETWEEN 1 AND 1024),
    scope jsonb NOT NULL, revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
    lifecycle text NOT NULL DEFAULT 'active' CHECK (lifecycle IN ('active','deleting','deleted')),
    deleted_at timestamptz, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (context_id,owner_id) REFERENCES research.context(id,owner_id),
    UNIQUE(id,context_id,owner_id)
);
CREATE INDEX session_owner ON research.session(owner_id,created_at,id);
CREATE TABLE research.job (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL, context_id uuid NOT NULL,
    session_id uuid, authority_session uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('research-turn','novelty-analysis','novelty-discussion')),
    operation_key text NOT NULL, input_hash text NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    input jsonb NOT NULL, scope jsonb NOT NULL, policy jsonb NOT NULL,
    state text NOT NULL DEFAULT 'accepted' CHECK (state IN ('accepted','running','cancel_requested','cancelled','succeeded','failed')),
    revision bigint NOT NULL DEFAULT 1, seq bigint NOT NULL DEFAULT 1,
    accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    lease_id uuid, worker_id uuid, fence bigint NOT NULL DEFAULT 0,
    lease_until timestamptz, attempts integer NOT NULL DEFAULT 0,
    artifact_id uuid, error_code text, usage_id uuid NOT NULL UNIQUE,
    usage_state text NOT NULL DEFAULT 'reserved' CHECK (usage_state IN ('reserved','settled','released','unknown')),
    FOREIGN KEY(context_id,owner_id) REFERENCES research.context(id,owner_id),
    FOREIGN KEY(session_id,context_id,owner_id) REFERENCES research.session(id,context_id,owner_id),
    UNIQUE(owner_id,operation_key), UNIQUE(id,context_id,owner_id),
    CHECK (kind <> 'research-turn' OR session_id IS NOT NULL),
    CHECK (kind = 'novelty-analysis' OR state NOT IN ('cancel_requested','cancelled')),
    CHECK (revision > 0 AND seq > 0 AND fence >= 0 AND attempts >= 0)
);
CREATE INDEX job_pending ON research.job(state,accepted_at,id);
CREATE TABLE research.dispatch (
    job_id uuid PRIMARY KEY REFERENCES research.job(id),
    delivered boolean NOT NULL DEFAULT false,
    accepted_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE research.artifact (
    id uuid PRIMARY KEY, job_id uuid NOT NULL UNIQUE, context_id uuid NOT NULL, owner_id uuid NOT NULL,
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0), content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    kind text NOT NULL CHECK (kind IN ('research-answer','novelty-result','novelty-discussion')),
    output jsonb NOT NULL, policy jsonb NOT NULL, eligibility_revision bigint NOT NULL DEFAULT 1,
    availability text NOT NULL DEFAULT 'ready' CHECK (availability IN ('ready','expired','deleted','restricted')),
    expires_at timestamptz NOT NULL,
    FOREIGN KEY(job_id,context_id,owner_id) REFERENCES research.job(id,context_id,owner_id),
    UNIQUE(id,context_id,owner_id)
);
CREATE TABLE research.evidence (
    id uuid PRIMARY KEY, artifact_id uuid NOT NULL REFERENCES research.artifact(id),
    context_id uuid NOT NULL, owner_id uuid NOT NULL,
    record jsonb NOT NULL, FOREIGN KEY(context_id,owner_id) REFERENCES research.context(id,owner_id),
    FOREIGN KEY(artifact_id,context_id,owner_id) REFERENCES research.artifact(id,context_id,owner_id)
);
CREATE TABLE research.assessment (
    id uuid PRIMARY KEY, artifact_id uuid NOT NULL REFERENCES research.artifact(id),
    method_revision text NOT NULL, record jsonb NOT NULL
);
CREATE TABLE research.attachment (
    id uuid PRIMARY KEY, context_id uuid NOT NULL, owner_id uuid NOT NULL,
    revision bigint NOT NULL DEFAULT 1, content_hash text NOT NULL,
    media_type text NOT NULL CHECK (media_type IN ('application/pdf','text/plain')),
    byte_length integer NOT NULL CHECK (byte_length BETWEEN 1 AND 2097152),
    write_handle uuid NOT NULL UNIQUE, expires_at timestamptz NOT NULL,
    disposition text NOT NULL DEFAULT 'pending' CHECK (disposition IN ('pending','extracted','unsupported','malformed','truncated','protected','failed','deleted')),
    content bytea, extracted text, policy jsonb NOT NULL,
    FOREIGN KEY(context_id,owner_id) REFERENCES research.context(id,owner_id),
    CHECK (content IS NULL OR octet_length(content) <= 2097152)
);
CREATE TABLE research.draft (
    id uuid PRIMARY KEY, context_id uuid NOT NULL, owner_id uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('research-question','novelty-topic','novelty-manuscript','novelty-discussion')),
    current_revision bigint NOT NULL DEFAULT 1,
    FOREIGN KEY(context_id,owner_id) REFERENCES research.context(id,owner_id)
);
CREATE TABLE research.draft_revision (
    draft_id uuid NOT NULL REFERENCES research.draft(id), revision bigint NOT NULL CHECK (revision > 0),
    parent_revision bigint, content_hash text NOT NULL, text text NOT NULL CHECK (octet_length(text) <= 32768),
    state text NOT NULL DEFAULT 'acknowledged' CHECK (state IN ('acknowledged','consumed','discarded','expired','deleted')),
    acknowledged_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    consumed_by uuid REFERENCES research.job(id), policy jsonb NOT NULL,
    PRIMARY KEY(draft_id,revision)
);
CREATE TABLE research.receipt (
    owner_id uuid NOT NULL, operation_key text NOT NULL, input_hash text NOT NULL,
    response jsonb NOT NULL, PRIMARY KEY(owner_id,operation_key)
);

CREATE FUNCTION research.guard_job_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.id,NEW.owner_id,NEW.context_id,NEW.session_id,NEW.kind,NEW.input_hash,NEW.input,NEW.scope,NEW.accepted_at,NEW.usage_id,NEW.policy,NEW.operation_key,NEW.authority_session)
       IS DISTINCT FROM
       (OLD.id,OLD.owner_id,OLD.context_id,OLD.session_id,OLD.kind,OLD.input_hash,OLD.input,OLD.scope,OLD.accepted_at,OLD.usage_id,OLD.policy,OLD.operation_key,OLD.authority_session) THEN
        RAISE EXCEPTION 'accepted input is immutable' USING ERRCODE='23514';
    END IF;
    IF NEW.state IS DISTINCT FROM OLD.state AND NOT (
       (OLD.state='accepted' AND NEW.state IN ('running','failed','cancel_requested')) OR
       (OLD.state='running' AND NEW.state IN ('succeeded','failed','cancel_requested')) OR
       (OLD.state='cancel_requested' AND NEW.state IN ('cancelled','succeeded','failed'))) THEN
        RAISE EXCEPTION 'terminal or invalid transition' USING ERRCODE='23514';
    END IF;
    IF NEW.seq < OLD.seq OR NEW.revision < OLD.revision OR NEW.fence < OLD.fence THEN
        RAISE EXCEPTION 'monotonic boundary required' USING ERRCODE='23514';
    END IF;
    IF NEW.state='succeeded' AND EXISTS (
        SELECT 1 FROM research.context WHERE id=NEW.context_id AND lifecycle <> 'active'
        UNION ALL SELECT 1 FROM research.session WHERE id=NEW.session_id AND lifecycle <> 'active'
    ) THEN
        RAISE EXCEPTION 'tombstone prevents publication' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER job_update BEFORE UPDATE ON research.job FOR EACH ROW EXECUTE FUNCTION research.guard_job_update();

CREATE FUNCTION research.guard_artifact_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.id,NEW.job_id,NEW.context_id,NEW.owner_id,NEW.revision,NEW.content_hash,NEW.output,NEW.kind,NEW.policy,NEW.expires_at)
       IS DISTINCT FROM (OLD.id,OLD.job_id,OLD.context_id,OLD.owner_id,OLD.revision,OLD.content_hash,OLD.output,OLD.kind,OLD.policy,OLD.expires_at)
       OR (OLD.availability <> 'ready' AND NEW.availability <> OLD.availability) THEN
        RAISE EXCEPTION 'immutable artifact or terminal availability' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER artifact_update BEFORE UPDATE ON research.artifact FOR EACH ROW EXECUTE FUNCTION research.guard_artifact_update();

CREATE FUNCTION research.guard_draft_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.draft_id,NEW.revision,NEW.content_hash,NEW.text,NEW.acknowledged_at,NEW.parent_revision)
       IS DISTINCT FROM (OLD.draft_id,OLD.revision,OLD.content_hash,OLD.text,OLD.acknowledged_at,OLD.parent_revision)
       OR (OLD.state <> 'acknowledged' AND NEW.state <> OLD.state) THEN
        RAISE EXCEPTION 'immutable draft revision or terminal disposition' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER draft_update BEFORE UPDATE ON research.draft_revision FOR EACH ROW EXECUTE FUNCTION research.guard_draft_update();

CREATE FUNCTION research.guard_tombstone() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (OLD.lifecycle <> 'active' AND NEW.lifecycle='active') OR NEW.revision < OLD.revision
       OR NEW.owner_id <> OLD.owner_id OR NEW.id <> OLD.id THEN
        RAISE EXCEPTION 'tombstone or identity cannot regress' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER context_tombstone BEFORE UPDATE ON research.context FOR EACH ROW EXECUTE FUNCTION research.guard_tombstone();
CREATE TRIGGER session_tombstone BEFORE UPDATE ON research.session FOR EACH ROW EXECUTE FUNCTION research.guard_tombstone();
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA research FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA research TO docsuri_research;
GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA research TO docsuri_research;
