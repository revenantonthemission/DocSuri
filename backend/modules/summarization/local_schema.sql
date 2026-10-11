CREATE TABLE assistance.admission (
    operation_id uuid PRIMARY KEY, account_id uuid NOT NULL, intent_hash text NOT NULL,
    intent jsonb NOT NULL, disposition text NOT NULL CHECK (disposition IN ('open','accepted','rejected')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    reservation_id uuid UNIQUE, revision uuid NOT NULL DEFAULT gen_random_uuid()
);
CREATE TABLE assistance.job (
    id uuid PRIMARY KEY REFERENCES assistance.admission(operation_id), account_id uuid NOT NULL,
    authority_revision uuid NOT NULL, version_id text NOT NULL,
    source_hash text NOT NULL CHECK (source_hash ~ '^[0-9a-f]{64}$'),
    input_hash text NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 16384),
    glossary_revision text NOT NULL, glossary_snapshot jsonb NOT NULL,
    accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    reservation_id uuid UNIQUE NOT NULL,
    state text NOT NULL DEFAULT 'accepted' CHECK (state IN ('accepted','running','succeeded','failed')),
    revision uuid NOT NULL DEFAULT gen_random_uuid(), sequence bigint NOT NULL DEFAULT 1 CHECK (sequence > 0),
    phase text NOT NULL DEFAULT 'accepted', failure_code text,
    worker_id uuid, lease_id uuid, fence bigint NOT NULL DEFAULT 0 CHECK (fence >= 0),
    lease_revision uuid, lease_expires_at timestamptz, started_at timestamptz,
    dispatch_pending boolean NOT NULL DEFAULT true,
    settlement_pending boolean NOT NULL DEFAULT false, settlement_receipt jsonb,
    CHECK ((worker_id IS NULL) = (lease_id IS NULL)),
    CHECK ((worker_id IS NULL) = (lease_revision IS NULL))
);
CREATE INDEX pending_jobs ON assistance.job(accepted_at, id) WHERE state IN ('accepted','running');
CREATE INDEX owner_history ON assistance.job(account_id,accepted_at,id);
CREATE TABLE assistance.event (
    job_id uuid NOT NULL REFERENCES assistance.job(id), sequence bigint NOT NULL,
    snapshot jsonb NOT NULL, PRIMARY KEY (job_id, sequence)
);
CREATE TABLE assistance.result (
    id uuid PRIMARY KEY, job_id uuid UNIQUE NOT NULL REFERENCES assistance.job(id),
    account_id uuid NOT NULL, version_id text NOT NULL, input_hash text NOT NULL,
    source_hash text NOT NULL, output_hash text NOT NULL CHECK (output_hash ~ '^[0-9a-f]{64}$'),
    private_path text UNIQUE NOT NULL, byte_length integer NOT NULL CHECK (byte_length BETWEEN 1 AND 131072),
    coverage jsonb NOT NULL, provenance jsonb NOT NULL,
    availability text NOT NULL CHECK (availability IN ('retained','expired','withdrawn','restricted')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE assistance.glossary (
    account_id uuid PRIMARY KEY, revision text NOT NULL, snapshot jsonb NOT NULL
);

CREATE FUNCTION assistance.preserve_job_binding() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF ROW(NEW.id,NEW.account_id,NEW.authority_revision,NEW.version_id,NEW.source_hash,
           NEW.input_hash,NEW.payload,NEW.glossary_revision,NEW.glossary_snapshot,NEW.accepted_at,NEW.reservation_id)
       IS DISTINCT FROM
       ROW(OLD.id,OLD.account_id,OLD.authority_revision,OLD.version_id,OLD.source_hash,
           OLD.input_hash,OLD.payload,OLD.glossary_revision,OLD.glossary_snapshot,OLD.accepted_at,OLD.reservation_id)
    THEN RAISE EXCEPTION 'immutable acceptance binding' USING ERRCODE = '23514'; END IF;
    IF OLD.state IN ('succeeded','failed') AND NEW.state <> OLD.state THEN
       RAISE EXCEPTION 'terminal state cannot regress' USING ERRCODE = '23514';
    END IF;
    IF NEW.sequence < OLD.sequence OR NEW.fence < OLD.fence THEN
       RAISE EXCEPTION 'ordered state cannot regress' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER preserve_job_binding BEFORE UPDATE ON assistance.job
FOR EACH ROW EXECUTE FUNCTION assistance.preserve_job_binding();

CREATE FUNCTION assistance.acquire_claim(p_job uuid, p_worker uuid)
RETURNS assistance.job LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE j assistance.job%ROWTYPE; now_at timestamptz := clock_timestamp();
BEGIN
    SELECT * INTO j FROM assistance.job WHERE id = p_job;
    IF NOT FOUND THEN RAISE EXCEPTION 'job missing' USING ERRCODE = '42501'; END IF;
    PERFORM accounts.guard_execution(j.account_id, j.authority_revision);
    PERFORM corpus.guard_version(j.version_id, 'local-research');
    SELECT * INTO j FROM assistance.job WHERE id = p_job FOR UPDATE;
    IF j.state NOT IN ('accepted','running') OR p_worker IS NULL
       OR (j.lease_expires_at IS NOT NULL AND j.lease_expires_at > now_at)
       OR j.fence >= 3 OR j.accepted_at + interval '5 minutes' <= now_at
       OR (j.started_at IS NOT NULL AND j.started_at + interval '90 seconds' <= now_at)
    THEN RAISE EXCEPTION 'claim unavailable' USING ERRCODE = '55000'; END IF;
    UPDATE assistance.job SET worker_id = p_worker, lease_id = gen_random_uuid(),
      fence = fence + 1, lease_revision = gen_random_uuid(),
      started_at = coalesce(started_at,now_at),
      lease_expires_at = least(now_at + interval '30 seconds',coalesce(started_at,now_at) + interval '90 seconds'),
      state = 'running', phase = 'claimed', dispatch_pending = false,
      revision = gen_random_uuid(), sequence = sequence + 1
      WHERE id = p_job RETURNING * INTO j;
    RETURN j;
END $$;

CREATE FUNCTION assistance.guard_claim(p_job uuid, p_worker uuid, p_lease uuid, p_fence bigint)
RETURNS assistance.job LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE j assistance.job%ROWTYPE;
BEGIN
    SELECT * INTO j FROM assistance.job WHERE id = p_job;
    IF NOT FOUND THEN RAISE EXCEPTION 'job missing' USING ERRCODE = '42501'; END IF;
    PERFORM accounts.guard_execution(j.account_id,j.authority_revision);
    PERFORM corpus.guard_version(j.version_id,'local-research');
    SELECT * INTO j FROM assistance.job WHERE id = p_job FOR UPDATE;
    IF j.state <> 'running' OR j.worker_id IS DISTINCT FROM p_worker
       OR j.lease_id IS DISTINCT FROM p_lease OR j.fence IS DISTINCT FROM p_fence
       OR j.lease_expires_at <= clock_timestamp() THEN
       RAISE EXCEPTION 'stale execution claim' USING ERRCODE = '42501';
    END IF;
    RETURN j;
END $$;

CREATE FUNCTION assistance.renew_claim(p_job uuid,p_worker uuid,p_lease uuid,p_fence bigint,p_revision uuid)
RETURNS assistance.job LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE j assistance.job%ROWTYPE;
BEGIN
    j := assistance.guard_claim(p_job,p_worker,p_lease,p_fence);
    IF j.lease_revision IS DISTINCT FROM p_revision THEN
       RAISE EXCEPTION 'stale lease revision' USING ERRCODE = '40001';
    END IF;
    UPDATE assistance.job SET lease_revision = gen_random_uuid(),
      lease_expires_at = least(clock_timestamp() + interval '30 seconds', started_at + interval '90 seconds')
      WHERE id = p_job RETURNING * INTO j;
    RETURN j;
END $$;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA assistance FROM PUBLIC;
