-- U1 / C7. Registered additive authority; never rewrite or backfill migration 002.
-- Old jobs/effects retain NULL authority_version. Missing old evidence is NOT a
-- NOT_STARTED dispatch or a new effect grant. The application must drain/isolate
-- unverifiable active legacy work before new-protocol exposure.

ALTER TABLE public.content_jobs
    ADD COLUMN authority_version SMALLINT,
    ADD COLUMN input_identity TEXT,
    ADD COLUMN prepared_result_id VARCHAR(64);
ALTER TABLE public.content_jobs ALTER COLUMN seq TYPE BIGINT;
ALTER TABLE public.content_job_events ALTER COLUMN seq TYPE BIGINT;
ALTER TABLE public.content_jobs
    ADD CONSTRAINT uq_content_jobs_identity UNIQUE (job_id, owner_id, task_type),
    ADD CONSTRAINT uq_content_jobs_owner_identity UNIQUE (job_id, owner_id),
    ADD CONSTRAINT ck_content_jobs_sequence CHECK (seq BETWEEN 0 AND 9007199254740991),
    ADD CONSTRAINT ck_content_jobs_v1 CHECK (
        authority_version IS NULL OR (
            authority_version = 1 AND task_type IN ('summarize', 'translate')
            AND attempt = 1 AND input_identity IS NOT NULL
            AND input_identity ~ '^[a-f0-9]{64}$'
            AND jsonb_typeof(input) = 'object'
            AND (prepared_result_id IS NULL OR state IN ('RUNNING', 'COMPLETED'))
            AND (state <> 'COMPLETED' OR (
                prepared_result_id IS NOT NULL AND result_ref IS NOT NULL
                AND result_ref = prepared_result_id AND result_expires_at IS NOT NULL
            ))
        )
    ),
    -- NOT VALID preserves existing orphan evidence without inventing an owner.
    -- Every NEW write is checked, and account deletion cascades to owned jobs.
    ADD CONSTRAINT fk_content_jobs_account FOREIGN KEY (owner_id)
        REFERENCES public.accounts(id) ON DELETE CASCADE NOT VALID;
ALTER TABLE public.content_job_events
    ADD CONSTRAINT ck_content_job_events_sequence CHECK (seq BETWEEN 1 AND 9007199254740991)
        NOT VALID,
    ADD CONSTRAINT fk_content_job_events_owner FOREIGN KEY (job_id, owner_id)
        REFERENCES public.content_jobs(job_id, owner_id) ON DELETE CASCADE NOT VALID;

CREATE TABLE public.content_job_submission_bindings (
    binding_id VARCHAR(64) PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL UNIQUE,
    owner_id VARCHAR(36) NOT NULL,
    dispatch_id VARCHAR(64) NOT NULL UNIQUE,
    idempotency_key VARCHAR(128),
    input_identity TEXT NOT NULL CHECK (input_identity ~ '^[a-f0-9]{64}$'),
    dispatch_outcome VARCHAR(16) NOT NULL DEFAULT 'NOT_STARTED',
    dispatch_fence BIGINT NOT NULL DEFAULT 0 CHECK (dispatch_fence BETWEEN 0 AND 9007199254740991),
    dispatch_started_at TIMESTAMPTZ,
    queue_message_id TEXT,
    released_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (job_id, owner_id) REFERENCES public.content_jobs(job_id, owner_id)
        ON DELETE CASCADE,
    CHECK (dispatch_outcome IN ('NOT_STARTED', 'SENDING', 'CONFIRMED', 'REJECTED', 'UNKNOWN')),
    CHECK (
        (dispatch_outcome = 'NOT_STARTED' AND dispatch_fence = 0 AND dispatch_started_at IS NULL)
        OR (dispatch_outcome IN ('SENDING', 'CONFIRMED', 'UNKNOWN')
            AND dispatch_fence > 0 AND dispatch_started_at IS NOT NULL)
        OR (dispatch_outcome = 'REJECTED' AND (
            (dispatch_fence = 0 AND dispatch_started_at IS NULL)
            OR (dispatch_fence > 0 AND dispatch_started_at IS NOT NULL)
        ))
    ),
    CHECK ((dispatch_outcome = 'REJECTED') = (released_at IS NOT NULL))
);
CREATE UNIQUE INDEX ux_content_job_binding_owner_key
    ON public.content_job_submission_bindings(owner_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND released_at IS NULL;
CREATE INDEX ix_content_job_first_dispatch
    ON public.content_job_submission_bindings(created_at, job_id)
    WHERE dispatch_outcome = 'NOT_STARTED' AND released_at IS NULL;
CREATE INDEX ix_content_job_ambiguous_dispatch
    ON public.content_job_submission_bindings(dispatch_started_at, job_id)
    WHERE dispatch_outcome IN ('SENDING', 'UNKNOWN') AND released_at IS NULL;

CREATE TABLE public.content_job_prepared_results (
    prepared_result_id VARCHAR(64) PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL UNIQUE,
    owner_id VARCHAR(36) NOT NULL,
    task_type VARCHAR(32) NOT NULL CHECK (task_type IN ('summarize', 'translate')),
    schema_version SMALLINT NOT NULL CHECK (schema_version = 1),
    content_digest TEXT NOT NULL CHECK (content_digest ~ '^[a-f0-9]{64}$'),
    -- Opaque canonical-json-ascii-v2 characters, bound as TEXT by the adapter.
    -- In particular, JSON \u0000 is six ASCII characters, never a SQL NUL.
    -- C2/task validation and exact-byte digest checking belong to the application;
    -- NO JSON cast/function/operator is permitted on this payload column.
    prepared_content TEXT,
    content_encoding TEXT NOT NULL CHECK (content_encoding = 'json-ascii'),
    canonical_version SMALLINT NOT NULL CHECK (canonical_version = 2),
    preparation_identity JSONB NOT NULL,
    submitted_level VARCHAR(16) CHECK (submitted_level IN ('expert', 'beginner')),
    asset_id TEXT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    expires_at TIMESTAMPTZ,
    content_purged_at TIMESTAMPTZ,
    UNIQUE (prepared_result_id, job_id, owner_id, task_type),
    FOREIGN KEY (job_id, owner_id, task_type)
        REFERENCES public.content_jobs(job_id, owner_id, task_type) ON DELETE CASCADE,
    CHECK (isfinite(prepared_at)),
    CHECK (expires_at IS NULL OR (isfinite(expires_at) AND expires_at > prepared_at)),
    CHECK (content_purged_at IS NULL OR isfinite(content_purged_at)),
    CHECK (
        (prepared_content IS NOT NULL AND content_purged_at IS NULL
            AND prepared_content <> ''
            AND length(prepared_content) = octet_length(prepared_content))
        OR (prepared_content IS NULL AND content_purged_at IS NOT NULL
            AND expires_at IS NOT NULL AND content_purged_at >= expires_at
            AND preparation_identity = '{}'::jsonb)
    )
);
CREATE INDEX ix_content_job_prepared_owner ON public.content_job_prepared_results(owner_id, job_id);
CREATE INDEX ix_content_job_payload_cleanup ON public.content_job_prepared_results(expires_at, job_id)
    WHERE expires_at IS NOT NULL AND content_purged_at IS NULL;
ALTER TABLE public.content_jobs
    ADD CONSTRAINT fk_content_jobs_prepared FOREIGN KEY
        (prepared_result_id, job_id, owner_id, task_type)
        REFERENCES public.content_job_prepared_results(prepared_result_id, job_id, owner_id, task_type)
        DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE public.content_job_effect_ledger
    ADD COLUMN authority_version SMALLINT,
    ADD COLUMN owner_id VARCHAR(36),
    ADD COLUMN effect_status VARCHAR(16),
    ADD COLUMN fence BIGINT,
    ADD COLUMN worker_id TEXT,
    ADD COLUMN lease_until TIMESTAMPTZ,
    ADD COLUMN prepared_result_id VARCHAR(64),
    ADD CONSTRAINT ck_content_job_effect_v1 CHECK (
        authority_version IS NULL OR (
            authority_version = 1 AND attempt = 1 AND effect = 'generate'
            AND owner_id IS NOT NULL AND worker_id IS NOT NULL AND worker_id <> ''
            AND effect_status IS NOT NULL AND effect_status IN ('INTENT', 'PREPARED', 'TERMINAL')
            AND fence IS NOT NULL AND fence BETWEEN 1 AND 9007199254740991
            AND lease_until IS NOT NULL AND lease_until > claimed_at
            AND (effect_status <> 'PREPARED' OR prepared_result_id IS NOT NULL)
        )
    ),
    ADD CONSTRAINT fk_content_job_effect_owner FOREIGN KEY (job_id, owner_id)
        REFERENCES public.content_jobs(job_id, owner_id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_content_job_effect_prepared FOREIGN KEY (prepared_result_id)
        REFERENCES public.content_job_prepared_results(prepared_result_id)
        DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX ix_content_job_expired_execution
    ON public.content_job_effect_ledger(lease_until, job_id)
    WHERE authority_version = 1 AND effect_status IN ('INTENT', 'PREPARED');
CREATE INDEX ix_content_jobs_v1_state ON public.content_jobs(state, updated_at, job_id)
    WHERE authority_version = 1;

CREATE TABLE public.content_job_maintenance_progress (
    environment TEXT NOT NULL,
    eligibility_class VARCHAR(32) NOT NULL CHECK (eligibility_class IN (
        'first_dispatch', 'ambiguous_dispatch', 'expired_execution', 'cleanup'
    )),
    cycle_id VARCHAR(64) NOT NULL,
    cutoff TIMESTAMPTZ NOT NULL,
    cursor_at TIMESTAMPTZ,
    cursor_job_id VARCHAR(64),
    processed BIGINT NOT NULL DEFAULT 0 CHECK (processed >= 0),
    outcome VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (outcome IN ('pending', 'running', 'complete', 'failed')),
    next_due_at TIMESTAMPTZ NOT NULL,
    last_started_at TIMESTAMPTZ,
    last_finished_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    PRIMARY KEY (environment, eligibility_class),
    CHECK ((cursor_at IS NULL) = (cursor_job_id IS NULL))
);
CREATE INDEX ix_content_job_maintenance_due
    ON public.content_job_maintenance_progress(environment, next_due_at);

-- Recheck ACTIVE under a row lock that conflicts with account invalidation and
-- deletion. This adds no lifecycle state/policy and does not replace the purger's
-- existing sweep lock. Application transactions must retain one bounded lock order.
CREATE FUNCTION public.content_jobs_require_active_owner() RETURNS trigger AS $$
DECLARE owner_status TEXT;
BEGIN
    SELECT status INTO owner_status FROM public.accounts WHERE id = NEW.owner_id FOR SHARE;
    IF owner_status IS DISTINCT FROM 'ACTIVE' THEN
        RAISE EXCEPTION 'content_job_owner_inactive' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.authority_version = 1 THEN
        IF (NEW.owner_id, NEW.task_type, NEW.input, NEW.input_identity, NEW.authority_version,
            NEW.attempt, NEW.created_at) IS DISTINCT FROM
           (OLD.owner_id, OLD.task_type, OLD.input, OLD.input_identity, OLD.authority_version,
            OLD.attempt, OLD.created_at) THEN
            RAISE EXCEPTION 'content_job_input_immutable' USING ERRCODE = '23514';
        END IF;
        IF NEW.state IS DISTINCT FROM OLD.state THEN
            IF NEW.seq <> OLD.seq + 1 OR NOT (
                (OLD.state = 'SUBMITTED' AND NEW.state IN ('ACCEPTED', 'FAILED')) OR
                (OLD.state = 'ACCEPTED' AND NEW.state IN ('QUEUED', 'FAILED')) OR
                (OLD.state = 'QUEUED' AND NEW.state IN ('RUNNING', 'FAILED')) OR
                (OLD.state = 'RUNNING' AND NEW.state IN ('COMPLETED', 'FAILED', 'ABSTAINED'))
            ) THEN
                RAISE EXCEPTION 'content_job_transition_invalid' USING ERRCODE = '23514';
            END IF;
        ELSIF NEW.seq <> OLD.seq THEN
            RAISE EXCEPTION 'content_job_sequence_invalid' USING ERRCODE = '23514';
        END IF;
        IF OLD.prepared_result_id IS NOT NULL
            AND NEW.prepared_result_id IS DISTINCT FROM OLD.prepared_result_id THEN
            RAISE EXCEPTION 'content_job_binding_immutable' USING ERRCODE = '23514';
        END IF;
        IF OLD.result_expires_at IS NOT NULL AND
            (NEW.result_expires_at, NEW.result_ref) IS DISTINCT FROM
            (OLD.result_expires_at, OLD.result_ref) THEN
            RAISE EXCEPTION 'content_job_expiry_immutable' USING ERRCODE = '23514';
        END IF;
    ELSIF TG_OP = 'UPDATE' AND NEW.authority_version IS NOT NULL THEN
        RAISE EXCEPTION 'legacy_authority_adoption_refused' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_content_jobs_active_owner BEFORE INSERT OR UPDATE ON public.content_jobs
    FOR EACH ROW EXECUTE FUNCTION public.content_jobs_require_active_owner();

CREATE FUNCTION public.content_job_binding_guard() RETURNS trigger AS $$
DECLARE job public.content_jobs;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.content_jobs
            WHERE job_id = OLD.job_id AND authority_version = 1) THEN
            RAISE EXCEPTION 'dispatch_binding_deletion_refused' USING ERRCODE = '23514';
        END IF;
        RETURN OLD; -- A job/account cascade has already removed the parent.
    END IF;
    SELECT * INTO job FROM public.content_jobs WHERE job_id = NEW.job_id FOR UPDATE;
    IF NOT FOUND OR job.authority_version IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION 'dispatch_job_authority_required' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.binding_id, NEW.job_id, NEW.owner_id, NEW.dispatch_id, NEW.idempotency_key,
            NEW.input_identity, NEW.created_at) IS DISTINCT FROM
           (OLD.binding_id, OLD.job_id, OLD.owner_id, OLD.dispatch_id, OLD.idempotency_key,
            OLD.input_identity, OLD.created_at) OR NEW.dispatch_fence < OLD.dispatch_fence THEN
            RAISE EXCEPTION 'dispatch_identity_immutable' USING ERRCODE = '23514';
        END IF;
        IF OLD.dispatch_started_at IS NOT NULL
            AND NEW.dispatch_started_at IS DISTINCT FROM OLD.dispatch_started_at THEN
            RAISE EXCEPTION 'dispatch_start_immutable' USING ERRCODE = '23514';
        END IF;
        IF OLD.dispatch_outcome IN ('CONFIRMED', 'REJECTED') AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'dispatch_settlement_immutable' USING ERRCODE = '23514';
        END IF;
        IF NEW.dispatch_outcome IS DISTINCT FROM OLD.dispatch_outcome AND NOT (
            (OLD.dispatch_outcome = 'NOT_STARTED' AND NEW.dispatch_outcome IN ('SENDING', 'REJECTED'))
            OR (OLD.dispatch_outcome = 'SENDING'
                AND NEW.dispatch_outcome IN ('CONFIRMED', 'REJECTED', 'UNKNOWN'))
            OR (OLD.dispatch_outcome = 'UNKNOWN' AND NEW.dispatch_outcome IN ('CONFIRMED', 'REJECTED'))
        ) THEN
            RAISE EXCEPTION 'dispatch_transition_invalid' USING ERRCODE = '23514';
        END IF;
        IF NEW.dispatch_outcome = 'SENDING' AND OLD.dispatch_outcome = 'NOT_STARTED'
            AND NEW.dispatch_fence <> OLD.dispatch_fence + 1 THEN
            RAISE EXCEPTION 'dispatch_first_fence_required' USING ERRCODE = '23514';
        END IF;
        IF OLD.queue_message_id IS NOT NULL
            AND NEW.queue_message_id IS DISTINCT FROM OLD.queue_message_id THEN
            RAISE EXCEPTION 'dispatch_evidence_immutable' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_content_job_binding_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.content_job_submission_bindings
    FOR EACH ROW EXECUTE FUNCTION public.content_job_binding_guard();

CREATE FUNCTION public.content_job_prepared_immutable() RETURNS trigger AS $$
DECLARE job public.content_jobs; owner_status TEXT;
BEGIN
    SELECT * INTO job FROM public.content_jobs WHERE job_id = NEW.job_id FOR UPDATE;
    IF NOT FOUND OR job.authority_version IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION 'prepared_job_authority_required' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'INSERT' AND job.state <> 'RUNNING' THEN
        RAISE EXCEPTION 'prepared_running_job_required' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'INSERT' AND (NEW.prepared_content IS NULL OR NEW.content_purged_at IS NOT NULL
        OR NEW.expires_at IS NOT NULL) THEN
        RAISE EXCEPTION 'prepared_initial_payload_required' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.prepared_result_id, NEW.job_id, NEW.owner_id, NEW.task_type, NEW.schema_version,
            NEW.content_digest, NEW.prepared_at, NEW.submitted_level, NEW.asset_id,
            NEW.content_encoding, NEW.canonical_version) IS DISTINCT FROM
           (OLD.prepared_result_id, OLD.job_id, OLD.owner_id, OLD.task_type, OLD.schema_version,
            OLD.content_digest, OLD.prepared_at, OLD.submitted_level, OLD.asset_id,
            OLD.content_encoding, OLD.canonical_version) THEN
            RAISE EXCEPTION 'prepared_content_immutable' USING ERRCODE = '23514';
        END IF;
        IF OLD.expires_at IS NOT NULL AND NEW.expires_at IS DISTINCT FROM OLD.expires_at THEN
            RAISE EXCEPTION 'prepared_expiry_immutable' USING ERRCODE = '23514';
        END IF;
        IF NEW.prepared_content IS DISTINCT FROM OLD.prepared_content OR
            NEW.preparation_identity IS DISTINCT FROM OLD.preparation_identity THEN
            IF NOT (OLD.content_purged_at IS NULL AND NEW.prepared_content IS NULL
                AND NEW.preparation_identity = '{}'::jsonb AND NEW.content_purged_at IS NOT NULL
                AND OLD.expires_at IS NOT NULL AND OLD.expires_at <= clock_timestamp()
                AND job.state = 'COMPLETED' AND job.result_expires_at = OLD.expires_at) THEN
                RAISE EXCEPTION 'prepared_content_immutable' USING ERRCODE = '23514';
            END IF;
            -- Expiry cleanup must remain possible for inactive, not-yet-purged
            -- owners. It removes content only; it grants no new write/invocation.
            RETURN NEW;
        END IF;
        IF NEW.content_purged_at IS DISTINCT FROM OLD.content_purged_at THEN
            RAISE EXCEPTION 'prepared_purge_immutable' USING ERRCODE = '23514';
        END IF;
    END IF;
    SELECT status INTO owner_status FROM public.accounts WHERE id = NEW.owner_id FOR SHARE;
    IF owner_status IS DISTINCT FROM 'ACTIVE' THEN
        RAISE EXCEPTION 'content_job_owner_inactive' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_content_job_prepared_immutable
    BEFORE INSERT OR UPDATE ON public.content_job_prepared_results
    FOR EACH ROW EXECUTE FUNCTION public.content_job_prepared_immutable();

CREATE FUNCTION public.content_job_effect_guard() RETURNS trigger AS $$
DECLARE job public.content_jobs;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.authority_version = 1 AND EXISTS (
            SELECT 1 FROM public.content_jobs WHERE job_id = OLD.job_id
        ) THEN
            RAISE EXCEPTION 'effect_intent_deletion_refused' USING ERRCODE = '23514';
        END IF;
        RETURN OLD; -- A job/account cascade has already removed the parent.
    END IF;
    IF NEW.authority_version = 1 THEN
        SELECT * INTO job FROM public.content_jobs WHERE job_id = NEW.job_id FOR UPDATE;
        IF NOT FOUND OR job.authority_version IS DISTINCT FROM 1
            OR job.owner_id IS DISTINCT FROM NEW.owner_id THEN
            RAISE EXCEPTION 'execution_job_authority_required' USING ERRCODE = '23514';
        END IF;
        IF TG_OP = 'INSERT' AND (job.state <> 'RUNNING' OR NEW.effect_status <> 'INTENT'
            OR NOT EXISTS (SELECT 1 FROM public.content_job_submission_bindings
                WHERE job_id = NEW.job_id AND dispatch_outcome = 'CONFIRMED')) THEN
            RAISE EXCEPTION 'execution_running_job_required' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.authority_version IS NULL AND NEW.authority_version IS NOT NULL THEN
        RAISE EXCEPTION 'legacy_authority_adoption_refused' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.authority_version = 1 THEN
        IF (NEW.job_id, NEW.attempt, NEW.effect, NEW.authority_version, NEW.owner_id,
            NEW.worker_id, NEW.claimed_at) IS DISTINCT FROM
           (OLD.job_id, OLD.attempt, OLD.effect, OLD.authority_version, OLD.owner_id,
            OLD.worker_id, OLD.claimed_at) OR NEW.fence < OLD.fence THEN
            RAISE EXCEPTION 'effect_identity_immutable' USING ERRCODE = '23514';
        END IF;
        IF OLD.effect_status = 'TERMINAL' AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'effect_terminal_immutable' USING ERRCODE = '23514';
        END IF;
        IF OLD.effect_status = 'PREPARED' AND NEW.effect_status = 'INTENT' THEN
            RAISE EXCEPTION 'effect_transition_invalid' USING ERRCODE = '23514';
        END IF;
        IF OLD.prepared_result_id IS NOT NULL AND
            NEW.prepared_result_id IS DISTINCT FROM OLD.prepared_result_id THEN
            RAISE EXCEPTION 'effect_binding_immutable' USING ERRCODE = '23514';
        END IF;
        IF NEW.fence > OLD.fence AND
            (NEW.effect_status <> 'TERMINAL' OR NEW.lease_until <> OLD.lease_until) THEN
            RAISE EXCEPTION 'reconciliation_is_publication_only' USING ERRCODE = '23514';
        END IF;
        IF NEW.lease_until IS DISTINCT FROM OLD.lease_until AND
            (NEW.fence <> OLD.fence OR OLD.lease_until <= clock_timestamp()
                OR NEW.lease_until <= OLD.lease_until) THEN
            RAISE EXCEPTION 'effect_renewal_fenced' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_content_job_effect_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.content_job_effect_ledger
    FOR EACH ROW EXECUTE FUNCTION public.content_job_effect_guard();

CREATE FUNCTION public.content_job_event_immutable() RETURNS trigger AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.content_jobs
        WHERE job_id = OLD.job_id AND authority_version = 1) THEN
        RAISE EXCEPTION 'job_history_immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' THEN RETURN NEW; END IF;
    RETURN OLD; -- Parent deletion permits its child cascade; history is not a restart lever.
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_content_job_event_immutable BEFORE UPDATE OR DELETE ON public.content_job_events
    FOR EACH ROW EXECUTE FUNCTION public.content_job_event_immutable();

-- Deferred validation makes T1 job+binding and T5/T6 root/effect/result/event
-- consistency commit facts, without requiring one arbitrary statement order.
CREATE FUNCTION public.content_job_validate_authority() RETURNS trigger AS $$
DECLARE job public.content_jobs; binding public.content_job_submission_bindings;
        effect_row public.content_job_effect_ledger; prepared public.content_job_prepared_results;
BEGIN
    SELECT * INTO job FROM public.content_jobs WHERE job_id = NEW.job_id;
    IF NOT FOUND OR job.authority_version IS NULL THEN RETURN NULL; END IF;
    SELECT * INTO binding FROM public.content_job_submission_bindings WHERE job_id = job.job_id;
    IF NOT FOUND OR binding.owner_id <> job.owner_id OR binding.input_identity <> job.input_identity THEN
        RAISE EXCEPTION 'submission_binding_required' USING ERRCODE = '23514';
    END IF;
    IF (binding.released_at IS NULL AND binding.idempotency_key IS DISTINCT FROM job.idempotency_key)
        OR (binding.released_at IS NOT NULL AND job.idempotency_key IS NOT NULL) THEN
        RAISE EXCEPTION 'retained_key_binding_required' USING ERRCODE = '23514';
    END IF;
    IF job.state NOT IN ('SUBMITTED', 'FAILED') AND binding.dispatch_outcome <> 'CONFIRMED' THEN
        RAISE EXCEPTION 'dispatch_confirmation_required' USING ERRCODE = '23514';
    END IF;
    IF binding.released_at IS NOT NULL AND (job.state <> 'FAILED' OR EXISTS (
        SELECT 1 FROM public.content_job_effect_ledger WHERE job_id = job.job_id
    )) THEN
        RAISE EXCEPTION 'dispatch_release_refused' USING ERRCODE = '23514';
    END IF;
    IF job.seq > 0 AND NOT EXISTS (
        SELECT 1 FROM public.content_job_events
        WHERE job_id = job.job_id AND owner_id = job.owner_id AND seq = job.seq AND state = job.state
    ) THEN
        RAISE EXCEPTION 'state_event_required' USING ERRCODE = '23514';
    END IF;
    SELECT * INTO effect_row FROM public.content_job_effect_ledger
        WHERE job_id = job.job_id AND attempt = 1;
    IF job.state IN ('RUNNING', 'COMPLETED', 'ABSTAINED') AND (
        NOT FOUND OR effect_row.authority_version IS DISTINCT FROM 1
        OR effect_row.owner_id IS DISTINCT FROM job.owner_id
    ) THEN
        RAISE EXCEPTION 'execution_intent_required' USING ERRCODE = '23514';
    END IF;
    IF FOUND AND job.state IN ('COMPLETED', 'FAILED', 'ABSTAINED')
        AND effect_row.effect_status IS DISTINCT FROM 'TERMINAL' THEN
        RAISE EXCEPTION 'terminal_effect_required' USING ERRCODE = '23514';
    END IF;
    IF job.prepared_result_id IS NOT NULL THEN
        SELECT * INTO prepared FROM public.content_job_prepared_results
            WHERE prepared_result_id = job.prepared_result_id;
        IF NOT FOUND OR prepared.job_id <> job.job_id OR prepared.owner_id <> job.owner_id
            OR prepared.task_type <> job.task_type OR
            effect_row.prepared_result_id IS DISTINCT FROM prepared.prepared_result_id THEN
            RAISE EXCEPTION 'exact_prepared_binding_required' USING ERRCODE = '23514';
        END IF;
        IF job.state = 'COMPLETED' AND prepared.expires_at IS DISTINCT FROM job.result_expires_at THEN
            RAISE EXCEPTION 'exact_prepared_expiry_required' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER trg_content_job_validate_job
    AFTER INSERT OR UPDATE ON public.content_jobs DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.content_job_validate_authority();
CREATE CONSTRAINT TRIGGER trg_content_job_validate_binding
    AFTER INSERT OR UPDATE ON public.content_job_submission_bindings DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.content_job_validate_authority();
CREATE CONSTRAINT TRIGGER trg_content_job_validate_effect
    AFTER INSERT OR UPDATE ON public.content_job_effect_ledger DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.content_job_validate_authority();
CREATE CONSTRAINT TRIGGER trg_content_job_validate_prepared
    AFTER INSERT OR UPDATE ON public.content_job_prepared_results DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION public.content_job_validate_authority();

CREATE VIEW public.content_job_legacy_classification AS
    SELECT j.job_id, j.owner_id,
        CASE WHEN a.id IS NULL THEN 'legacy_orphan'
             WHEN j.state IN ('COMPLETED', 'FAILED', 'ABSTAINED') THEN 'legacy_terminal'
             ELSE 'legacy_active_unverified' END AS classification
    FROM public.content_jobs j LEFT JOIN public.accounts a ON a.id = j.owner_id
    WHERE j.authority_version IS NULL;
