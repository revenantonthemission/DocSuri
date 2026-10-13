-- U7 PlatformControl schema: owner-scoped tables and SECURITY DEFINER guards.
--
-- Runs under `SET ROLE platform_control_owner` inside a freshly created
-- `platform_control` schema. Every function is schema-qualified and pinned to
-- `search_path = pg_catalog`; the runtime and provisioner login roles receive
-- EXECUTE on explicit functions only and no direct table DML.

CREATE TABLE IF NOT EXISTS platform_control.protocol (
    name text PRIMARY KEY,
    disposition text NOT NULL CHECK (disposition IN ('retained-local','compatibility-dependent','not-implemented-under-0')),
    authority_class text NOT NULL CHECK (authority_class IN ('routine','destructive-release')),
    max_age_seconds integer NOT NULL CHECK (max_age_seconds > 0),
    deadline_seconds integer NOT NULL CHECK (deadline_seconds > 0),
    effect_kind text NOT NULL CHECK (effect_kind IN ('file-write','file-probe','credential-presence')),
    native_verified boolean NOT NULL,
    consumer_impact text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS platform_control.target (
    target_id text PRIMARY KEY CHECK (target_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'),
    applied_count bigint NOT NULL DEFAULT 0 CHECK (applied_count >= 0),
    last_effect_ref text,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS platform_control.authority (
    authority_id uuid PRIMARY KEY,
    actor_reference text NOT NULL CHECK (length(actor_reference) BETWEEN 1 AND 128),
    target_scope text[] NOT NULL CHECK (array_length(target_scope, 1) >= 1),
    permitted_operation text[] NOT NULL CHECK (array_length(permitted_operation, 1) >= 1),
    authority_class text NOT NULL CHECK (authority_class IN ('routine','destructive-release','evidence-reader')),
    binding jsonb NOT NULL CHECK (octet_length(binding::text) <= 4096),
    provisioned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    revoked_at timestamptz,
    revocation text NOT NULL DEFAULT 'active' CHECK (revocation IN ('active','revoked'))
);

CREATE TABLE IF NOT EXISTS platform_control.evidence (
    evidence_id uuid PRIMARY KEY,
    target_id text NOT NULL REFERENCES platform_control.target(target_id),
    input_hash text NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    environment_binding text NOT NULL CHECK (length(environment_binding) BETWEEN 1 AND 256),
    generation bigint NOT NULL CHECK (generation > 0),
    observations jsonb NOT NULL CHECK (octet_length(observations::text) <= 8192),
    observed_at timestamptz NOT NULL,
    max_age_seconds integer NOT NULL CHECK (max_age_seconds > 0),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (target_id, generation)
);

CREATE TABLE IF NOT EXISTS platform_control.operation (
    operation_id uuid PRIMARY KEY,
    authority_id uuid NOT NULL REFERENCES platform_control.authority(authority_id),
    evidence_id uuid NOT NULL REFERENCES platform_control.evidence(evidence_id),
    operation_name text NOT NULL,
    authority_class text NOT NULL CHECK (authority_class IN ('routine','destructive-release')),
    authority_actor text NOT NULL,
    target_id text NOT NULL REFERENCES platform_control.target(target_id),
    input_hash text NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    environment_binding text NOT NULL CHECK (length(environment_binding) BETWEEN 1 AND 256),
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 128),
    preconditions jsonb NOT NULL CHECK (octet_length(preconditions::text) <= 4096),
    state text NOT NULL CHECK (state IN ('authorized','executing','completed','failed','unknown')),
    effect_disposition text NOT NULL CHECK (effect_disposition IN ('not-applied','applied','unknown')),
    deadline_seconds integer NOT NULL CHECK (deadline_seconds > 0),
    requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    started_at timestamptz,
    settled_at timestamptz,
    UNIQUE (authority_actor, idempotency_key)
);

CREATE TABLE IF NOT EXISTS platform_control.receipt (
    receipt_id uuid PRIMARY KEY,
    operation_id uuid NOT NULL UNIQUE REFERENCES platform_control.operation(operation_id),
    target_effect_reference text NOT NULL CHECK (length(target_effect_reference) BETWEEN 1 AND 256),
    revision uuid NOT NULL DEFAULT gen_random_uuid(),
    outcome text CHECK (outcome IN ('completed','failed','unknown')),
    effect_refs jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (octet_length(effect_refs::text) <= 8192),
    reconciliation_evidence jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (octet_length(reconciliation_evidence::text) <= 8192),
    reconciliation_state text NOT NULL CHECK (reconciliation_state IN ('pending','not-applicable','unresolved','reconciled-applied','reconciled-not-applied')),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    reconciled_at timestamptz
);

CREATE TABLE IF NOT EXISTS platform_control.target_lease (
    target_id text PRIMARY KEY REFERENCES platform_control.target(target_id),
    operation_id uuid NOT NULL UNIQUE REFERENCES platform_control.operation(operation_id),
    acquired_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    deadline_at timestamptz NOT NULL
);

-- ---------------------------------------------------------------------------
-- Helpers (owner-internal)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION platform_control._receipt_json(p_receipt platform_control.receipt, p_operation platform_control.operation)
RETURNS jsonb LANGUAGE sql STABLE SET search_path = pg_catalog AS $$
    SELECT jsonb_build_object(
        'receiptId', p_receipt.receipt_id,
        'operationId', p_receipt.operation_id,
        'targetId', p_operation.target_id,
        'inputHash', p_operation.input_hash,
        'authorityRef', p_operation.authority_id,
        'evidenceId', p_operation.evidence_id,
        'revision', p_receipt.revision,
        'operationState', p_operation.state,
        'outcome', p_receipt.outcome,
        'effectDisposition', p_operation.effect_disposition,
        'effectRefs', p_receipt.effect_refs,
        'reconciliationState', p_receipt.reconciliation_state,
        'reconciliationEvidence', p_receipt.reconciliation_evidence,
        'effectReference', p_receipt.target_effect_reference,
        'recordedAt', p_receipt.recorded_at,
        'reconciledAt', p_receipt.reconciled_at
    );
$$;

CREATE OR REPLACE FUNCTION platform_control._promote(p_operation uuid, p_reason text)
RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    UPDATE platform_control.operation
       SET state = 'unknown', effect_disposition = 'unknown', settled_at = clock_timestamp()
     WHERE operation_id = p_operation AND state IN ('authorized','executing');
    IF FOUND THEN
        UPDATE platform_control.receipt
           SET outcome = 'unknown',
               reconciliation_state = 'unresolved',
               revision = gen_random_uuid(),
               reconciliation_evidence = reconciliation_evidence || jsonb_build_array('promoted:' || p_reason)
         WHERE operation_id = p_operation AND outcome IS NULL;
    END IF;
    DELETE FROM platform_control.target_lease WHERE operation_id = p_operation;
END $$;

-- Validate a current, independent authority grant for actor/operation/target.
CREATE OR REPLACE FUNCTION platform_control.guard_authority(
    p_actor text,
    p_authority uuid,
    p_class text,
    p_operation text,
    p_target text,
    p_execute boolean
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE a platform_control.authority%ROWTYPE;
BEGIN
    IF p_actor IS NULL OR length(p_actor) = 0 OR p_authority IS NULL THEN
        RAISE EXCEPTION 'missing operator identity' USING ERRCODE = '42501';
    END IF;
    IF p_target IS NULL OR p_operation IS NULL THEN
        RAISE EXCEPTION 'missing operation target' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO a FROM platform_control.authority WHERE authority_id = p_authority FOR SHARE;
    IF NOT FOUND OR a.revocation <> 'active' THEN
        RAISE EXCEPTION 'authority not current' USING ERRCODE = '42501';
    END IF;
    IF a.actor_reference <> p_actor THEN
        RAISE EXCEPTION 'authority actor mismatch' USING ERRCODE = '42501';
    END IF;
    IF NOT (p_target = ANY(a.target_scope)) THEN
        RAISE EXCEPTION 'target outside authority scope' USING ERRCODE = '42501';
    END IF;
    IF p_execute THEN
        IF a.authority_class NOT IN ('routine','destructive-release') THEN
            RAISE EXCEPTION 'evidence-reader grant cannot authorize an effect' USING ERRCODE = '42501';
        END IF;
        IF a.authority_class <> p_class THEN
            RAISE EXCEPTION 'authority class does not cover operation' USING ERRCODE = '42501';
        END IF;
        IF NOT (p_operation = ANY(a.permitted_operation)) THEN
            RAISE EXCEPTION 'operation outside authority scope' USING ERRCODE = '42501';
        END IF;
    END IF;
END $$;

-- Atomically bind and admit an operation before any effect.
CREATE OR REPLACE FUNCTION platform_control.begin_operation(
    p_actor text,
    p_authority uuid,
    p_operation text,
    p_target text,
    p_input_hash text,
    p_environment text,
    p_evidence uuid,
    p_generation bigint,
    p_idempotency text,
    p_effect_reference text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    proto platform_control.protocol%ROWTYPE;
    prior platform_control.operation%ROWTYPE;
    rec platform_control.receipt%ROWTYPE;
    ev platform_control.evidence%ROWTYPE;
    lease platform_control.target_lease%ROWTYPE;
    op_id uuid;
    rec_id uuid;
BEGIN
    SELECT * INTO proto FROM platform_control.protocol WHERE name = p_operation;
    IF NOT FOUND OR proto.disposition <> 'retained-local' OR NOT proto.native_verified THEN
        RAISE EXCEPTION 'operation not admitted by retained inventory' USING ERRCODE = 'U7001';
    END IF;
    IF p_target IS NULL OR p_target !~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$' THEN
        RAISE EXCEPTION 'invalid target identity' USING ERRCODE = 'U7003';
    END IF;
    IF p_input_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'invalid input digest' USING ERRCODE = 'U7003';
    END IF;
    IF p_environment IS NULL OR length(p_environment) = 0 OR length(p_environment) > 256 THEN
        RAISE EXCEPTION 'invalid environment binding' USING ERRCODE = 'U7003';
    END IF;
    IF p_idempotency IS NULL OR length(p_idempotency) = 0 OR length(p_idempotency) > 128 THEN
        RAISE EXCEPTION 'invalid idempotency key' USING ERRCODE = 'U7003';
    END IF;
    PERFORM platform_control.guard_authority(p_actor, p_authority, proto.authority_class, p_operation, p_target, true);

    SELECT * INTO prior FROM platform_control.operation
      WHERE authority_actor = p_actor AND idempotency_key = p_idempotency;
    IF FOUND THEN
        IF prior.input_hash <> p_input_hash THEN
            RAISE EXCEPTION 'changed input under the same key' USING ERRCODE = '23505';
        END IF;
        SELECT * INTO rec FROM platform_control.receipt WHERE operation_id = prior.operation_id;
        RETURN platform_control._receipt_json(rec, prior) || jsonb_build_object('replayed', true);
    END IF;

    SELECT * INTO ev FROM platform_control.evidence WHERE evidence_id = p_evidence;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'evidence missing' USING ERRCODE = 'U7001';
    END IF;
    IF ev.target_id <> p_target OR ev.input_hash <> p_input_hash OR ev.environment_binding <> p_environment THEN
        RAISE EXCEPTION 'evidence mismatched' USING ERRCODE = 'U7002';
    END IF;
    IF ev.generation <> p_generation THEN
        RAISE EXCEPTION 'evidence generation mismatch' USING ERRCODE = 'U7002';
    END IF;
    IF clock_timestamp() > ev.observed_at + make_interval(secs => ev.max_age_seconds) THEN
        RAISE EXCEPTION 'evidence stale' USING ERRCODE = 'U7001';
    END IF;

    SELECT * INTO lease FROM platform_control.target_lease WHERE target_id = p_target FOR UPDATE;
    IF FOUND THEN
        IF lease.deadline_at > clock_timestamp() THEN
            RAISE EXCEPTION 'target already has an in-flight effect' USING ERRCODE = 'U7002';
        END IF;
        PERFORM platform_control._promote(lease.operation_id, 'stale in-flight lease reclaimed');
    END IF;

    op_id := gen_random_uuid();
    rec_id := gen_random_uuid();
    INSERT INTO platform_control.operation(
        operation_id, authority_id, evidence_id, operation_name, authority_class, authority_actor,
        target_id, input_hash, environment_binding, idempotency_key, preconditions, state,
        effect_disposition, deadline_seconds
    ) VALUES (
        op_id, p_authority, p_evidence, p_operation, proto.authority_class, p_actor,
        p_target, p_input_hash, p_environment, p_idempotency,
        jsonb_build_array(
            jsonb_build_object('name','authority','outcome','pass'),
            jsonb_build_object('name','evidence','outcome','pass'),
            jsonb_build_object('name','target','outcome','pass')
        ),
        'authorized', 'unknown', proto.deadline_seconds
    );
    INSERT INTO platform_control.receipt(receipt_id, operation_id, target_effect_reference, outcome, reconciliation_state)
      VALUES (rec_id, op_id, p_effect_reference, NULL, 'pending');
    INSERT INTO platform_control.target_lease(target_id, operation_id, deadline_at)
      VALUES (p_target, op_id, clock_timestamp() + make_interval(secs => proto.deadline_seconds));
    RETURN jsonb_build_object(
        'receiptId', rec_id, 'operationId', op_id, 'targetId', p_target, 'inputHash', p_input_hash,
        'authorityRef', p_authority, 'evidenceId', p_evidence, 'revision', gen_random_uuid(),
        'operationState', 'authorized', 'outcome', NULL, 'effectDisposition', 'unknown',
        'effectRefs', '[]'::jsonb, 'reconciliationState', 'pending', 'reconciliationEvidence', '[]'::jsonb,
        'effectReference', p_effect_reference, 'deadlineSeconds', proto.deadline_seconds,
        'authorityClass', proto.authority_class, 'replayed', false
    );
END $$;

CREATE OR REPLACE FUNCTION platform_control.mark_executing(p_operation uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE op platform_control.operation%ROWTYPE; rec platform_control.receipt%ROWTYPE;
BEGIN
    UPDATE platform_control.operation SET state = 'executing', started_at = clock_timestamp()
     WHERE operation_id = p_operation AND state = 'authorized';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'operation is not authorized' USING ERRCODE = 'U7002';
    END IF;
    SELECT * INTO op FROM platform_control.operation WHERE operation_id = p_operation;
    SELECT * INTO rec FROM platform_control.receipt WHERE operation_id = p_operation;
    RETURN platform_control._receipt_json(rec, op);
END $$;

CREATE OR REPLACE FUNCTION platform_control.settle_operation(p_operation uuid, p_outcome text, p_disposition text, p_effect_refs jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE op platform_control.operation%ROWTYPE; rec platform_control.receipt%ROWTYPE; refs jsonb;
BEGIN
    IF p_outcome NOT IN ('completed','failed','unknown') THEN
        RAISE EXCEPTION 'invalid outcome' USING ERRCODE = 'U7003';
    END IF;
    IF (p_outcome = 'completed' AND p_disposition <> 'applied')
       OR (p_outcome = 'failed' AND p_disposition <> 'not-applied')
       OR (p_outcome = 'unknown' AND p_disposition <> 'unknown') THEN
        RAISE EXCEPTION 'outcome and effect disposition disagree' USING ERRCODE = 'U7003';
    END IF;
    refs := coalesce(p_effect_refs, '[]'::jsonb);
    IF p_outcome = 'completed' AND jsonb_array_length(refs) = 0 THEN
        RAISE EXCEPTION 'completed requires observed effect evidence' USING ERRCODE = 'U7003';
    END IF;
    SELECT * INTO op FROM platform_control.operation WHERE operation_id = p_operation FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown operation' USING ERRCODE = 'U7004';
    END IF;
    IF op.state NOT IN ('authorized','executing') THEN
        RAISE EXCEPTION 'operation already settled' USING ERRCODE = 'U7002';
    END IF;
    UPDATE platform_control.operation
       SET state = p_outcome, effect_disposition = p_disposition, settled_at = clock_timestamp()
     WHERE operation_id = p_operation;
    UPDATE platform_control.receipt
       SET outcome = p_outcome,
           effect_refs = refs,
           reconciliation_state = CASE WHEN p_outcome IN ('completed','failed') THEN 'not-applicable' ELSE 'unresolved' END,
           revision = gen_random_uuid()
     WHERE operation_id = p_operation;
    IF p_outcome = 'completed' THEN
        UPDATE platform_control.target
           SET applied_count = applied_count + 1,
               last_effect_ref = refs->>0,
               updated_at = clock_timestamp()
         WHERE target_id = op.target_id;
    END IF;
    DELETE FROM platform_control.target_lease WHERE operation_id = p_operation;
    SELECT * INTO op FROM platform_control.operation WHERE operation_id = p_operation;
    SELECT * INTO rec FROM platform_control.receipt WHERE operation_id = p_operation;
    RETURN platform_control._receipt_json(rec, op);
END $$;

CREATE OR REPLACE FUNCTION platform_control.promote_in_flight()
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE lease platform_control.target_lease%ROWTYPE; promoted integer := 0;
BEGIN
    FOR lease IN SELECT * FROM platform_control.target_lease WHERE deadline_at < clock_timestamp() LOOP
        PERFORM platform_control._promote(lease.operation_id, 'in-flight deadline exceeded');
        promoted := promoted + 1;
    END LOOP;
    RETURN promoted;
END $$;

CREATE OR REPLACE FUNCTION platform_control.reconcile_receipt(p_operation uuid, p_applied boolean, p_evidence jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE op platform_control.operation%ROWTYPE; rec platform_control.receipt%ROWTYPE; add jsonb;
BEGIN
    SELECT * INTO rec FROM platform_control.receipt WHERE operation_id = p_operation FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown receipt' USING ERRCODE = 'U7004';
    END IF;
    IF rec.outcome <> 'unknown' OR rec.reconciliation_state <> 'unresolved' THEN
        RAISE EXCEPTION 'only an unresolved unknown may be reconciled' USING ERRCODE = 'U7002';
    END IF;
    add := coalesce(p_evidence, '[]'::jsonb);
    UPDATE platform_control.receipt
       SET reconciliation_state = CASE WHEN p_applied THEN 'reconciled-applied' ELSE 'reconciled-not-applied' END,
           reconciliation_evidence = reconciliation_evidence || add,
           reconciled_at = clock_timestamp(),
           revision = gen_random_uuid()
     WHERE operation_id = p_operation;
    SELECT * INTO op FROM platform_control.operation WHERE operation_id = p_operation;
    SELECT * INTO rec FROM platform_control.receipt WHERE operation_id = p_operation;
    RETURN platform_control._receipt_json(rec, op);
END $$;

CREATE OR REPLACE FUNCTION platform_control.record_evidence(p_target text, p_input_hash text, p_environment text, p_observations jsonb, p_max_age integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE gen bigint; ev platform_control.evidence%ROWTYPE;
BEGIN
    IF p_target IS NULL OR p_target !~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$' THEN
        RAISE EXCEPTION 'invalid target identity' USING ERRCODE = 'U7003';
    END IF;
    IF p_input_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'invalid input digest' USING ERRCODE = 'U7003';
    END IF;
    IF p_environment IS NULL OR length(p_environment) = 0 OR length(p_environment) > 256 THEN
        RAISE EXCEPTION 'invalid environment binding' USING ERRCODE = 'U7003';
    END IF;
    IF p_max_age IS NULL OR p_max_age <= 0 THEN
        RAISE EXCEPTION 'evidence requires a finite validity window' USING ERRCODE = 'U7003';
    END IF;
    IF p_observations IS NULL OR octet_length(p_observations::text) > 8192 THEN
        RAISE EXCEPTION 'observations are missing or oversized' USING ERRCODE = 'U7003';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM platform_control.target WHERE target_id = p_target) THEN
        RAISE EXCEPTION 'unknown target' USING ERRCODE = 'U7004';
    END IF;
    SELECT coalesce(max(generation), 0) + 1 INTO gen FROM platform_control.evidence WHERE target_id = p_target;
    INSERT INTO platform_control.evidence(evidence_id, target_id, input_hash, environment_binding, generation, observations, observed_at, max_age_seconds)
      VALUES (gen_random_uuid(), p_target, p_input_hash, p_environment, gen, p_observations, clock_timestamp(), p_max_age)
      RETURNING * INTO ev;
    RETURN jsonb_build_object(
        'evidenceId', ev.evidence_id, 'targetId', ev.target_id, 'inputHash', ev.input_hash,
        'environmentBinding', ev.environment_binding, 'generation', ev.generation,
        'observedAt', ev.observed_at, 'maxAgeSeconds', ev.max_age_seconds, 'observations', ev.observations
    );
END $$;

-- Enforce target-scope bounding in the store layer, not only at the CLI.
CREATE OR REPLACE FUNCTION platform_control.reader_scope(p_actor text, p_authority uuid)
RETURNS text[] LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE a platform_control.authority%ROWTYPE;
BEGIN
    IF p_actor IS NULL OR length(p_actor) = 0 OR p_authority IS NULL THEN
        RAISE EXCEPTION 'missing operator identity' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO a FROM platform_control.authority WHERE authority_id = p_authority FOR SHARE;
    IF NOT FOUND OR a.revocation <> 'active' OR a.actor_reference <> p_actor THEN
        RAISE EXCEPTION 'authority not current' USING ERRCODE = '42501';
    END IF;
    RETURN a.target_scope;
END $$;

CREATE OR REPLACE FUNCTION platform_control.read_receipt(p_actor text, p_authority uuid, p_operation uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE op platform_control.operation%ROWTYPE; rec platform_control.receipt%ROWTYPE;
BEGIN
    SELECT * INTO op FROM platform_control.operation WHERE operation_id = p_operation;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown receipt' USING ERRCODE = 'U7004';
    END IF;
    PERFORM platform_control.guard_authority(p_actor, p_authority, 'routine', 'readReceipt', op.target_id, false);
    SELECT * INTO rec FROM platform_control.receipt WHERE operation_id = p_operation;
    RETURN platform_control._receipt_json(rec, op);
END $$;

CREATE OR REPLACE FUNCTION platform_control.latest_evidence(p_actor text, p_authority uuid, p_target text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE ev platform_control.evidence%ROWTYPE;
BEGIN
    PERFORM platform_control.guard_authority(p_actor, p_authority, 'routine', 'inspectEvidence', p_target, false);
    SELECT * INTO ev FROM platform_control.evidence WHERE target_id = p_target ORDER BY generation DESC LIMIT 1;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;
    RETURN jsonb_build_object(
        'evidenceId', ev.evidence_id, 'targetId', ev.target_id, 'inputHash', ev.input_hash,
        'environmentBinding', ev.environment_binding, 'generation', ev.generation,
        'observedAt', ev.observed_at, 'maxAgeSeconds', ev.max_age_seconds, 'observations', ev.observations
    );
END $$;

CREATE OR REPLACE FUNCTION platform_control.list_unresolved(p_actor text, p_authority uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE scope text[];
BEGIN
    scope := platform_control.reader_scope(p_actor, p_authority);
    RETURN (
        SELECT coalesce(jsonb_agg(platform_control._receipt_json(r, o) ORDER BY r.recorded_at), '[]'::jsonb)
          FROM platform_control.receipt r JOIN platform_control.operation o ON o.operation_id = r.operation_id
         WHERE r.reconciliation_state = 'unresolved' AND o.target_id = ANY(scope)
    );
END $$;

CREATE OR REPLACE FUNCTION platform_control.status_counts(p_actor text, p_authority uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE scope text[];
BEGIN
    scope := platform_control.reader_scope(p_actor, p_authority);
    RETURN (SELECT jsonb_build_object(
        'authorized', count(*) FILTER (WHERE state = 'authorized' AND target_id = ANY(scope)),
        'executing', count(*) FILTER (WHERE state = 'executing' AND target_id = ANY(scope)),
        'completed', count(*) FILTER (WHERE state = 'completed' AND target_id = ANY(scope)),
        'failed', count(*) FILTER (WHERE state = 'failed' AND target_id = ANY(scope)),
        'unknown', count(*) FILTER (WHERE state = 'unknown' AND target_id = ANY(scope)),
        'unresolved', (SELECT count(*) FROM platform_control.receipt r
                        JOIN platform_control.operation o ON o.operation_id = r.operation_id
                       WHERE r.reconciliation_state = 'unresolved' AND o.target_id = ANY(scope))
    ) FROM platform_control.operation);
END $$;

-- Privileged local supervision view for the operator's supervisor only. Granted
-- to the provisioner role (already the privileged local role); it is not the
-- operator-facing `status` op, which stays target-scope bounded.
CREATE OR REPLACE FUNCTION platform_control.supervisor_summary()
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT jsonb_build_object(
        'authorized', count(*) FILTER (WHERE state = 'authorized'),
        'executing', count(*) FILTER (WHERE state = 'executing'),
        'completed', count(*) FILTER (WHERE state = 'completed'),
        'failed', count(*) FILTER (WHERE state = 'failed'),
        'unknown', count(*) FILTER (WHERE state = 'unknown'),
        'unresolved', (SELECT count(*) FROM platform_control.receipt WHERE reconciliation_state = 'unresolved'),
        'unresolvedOperations', (SELECT coalesce(jsonb_agg(operation_id), '[]'::jsonb)
                                   FROM platform_control.receipt WHERE reconciliation_state = 'unresolved')
    ) FROM platform_control.operation;
$$;

CREATE OR REPLACE FUNCTION platform_control.read_authority(p_authority uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE a platform_control.authority%ROWTYPE;
BEGIN
    SELECT * INTO a FROM platform_control.authority WHERE authority_id = p_authority;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown authority' USING ERRCODE = 'U7004';
    END IF;
    RETURN jsonb_build_object(
        'authorityId', a.authority_id, 'actorReference', a.actor_reference, 'targetScope', to_jsonb(a.target_scope),
        'permittedOperation', to_jsonb(a.permitted_operation), 'authorityClass', a.authority_class,
        'revocation', a.revocation, 'provisionedAt', a.provisioned_at, 'revokedAt', a.revoked_at
    );
END $$;

CREATE OR REPLACE FUNCTION platform_control.provision_authority(p_authority uuid, p_actor text, p_scope jsonb, p_operations jsonb, p_class text, p_binding jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE scope text[]; operations text[]; a platform_control.authority%ROWTYPE;
BEGIN
    IF p_actor IS NULL OR length(p_actor) = 0 OR length(p_actor) > 128 THEN
        RAISE EXCEPTION 'invalid actor identity' USING ERRCODE = 'U7003';
    END IF;
    IF p_class NOT IN ('routine','destructive-release','evidence-reader') THEN
        RAISE EXCEPTION 'invalid authority class' USING ERRCODE = 'U7003';
    END IF;
    IF p_scope IS NULL OR jsonb_typeof(p_scope) <> 'array' OR jsonb_array_length(p_scope) = 0 THEN
        RAISE EXCEPTION 'authority scope must be explicit and non-empty' USING ERRCODE = 'U7003';
    END IF;
    scope := ARRAY(SELECT jsonb_array_elements_text(p_scope));
    IF EXISTS (SELECT 1 FROM unnest(scope) s WHERE s !~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') THEN
        RAISE EXCEPTION 'authority scope contains a wildcard or invalid target' USING ERRCODE = 'U7003';
    END IF;
    IF p_operations IS NULL OR jsonb_typeof(p_operations) <> 'array' OR jsonb_array_length(p_operations) = 0 THEN
        RAISE EXCEPTION 'permitted operation set must be non-empty' USING ERRCODE = 'U7003';
    END IF;
    operations := ARRAY(SELECT jsonb_array_elements_text(p_operations));
    IF p_class = 'evidence-reader' THEN
        IF EXISTS (SELECT 1 FROM unnest(operations) op WHERE op NOT IN ('inspectEvidence','readReceipt')) THEN
            RAISE EXCEPTION 'evidence-reader grant permits read operations only' USING ERRCODE = 'U7003';
        END IF;
    ELSE
        IF EXISTS (
            SELECT 1 FROM unnest(operations) op
             WHERE NOT EXISTS (
                 SELECT 1 FROM platform_control.protocol pr
                  WHERE pr.name = op AND pr.disposition = 'retained-local' AND pr.native_verified
             )
        ) THEN
            RAISE EXCEPTION 'permitted operation is not a retained executable protocol' USING ERRCODE = 'U7003';
        END IF;
    END IF;
    INSERT INTO platform_control.authority(authority_id, actor_reference, target_scope, permitted_operation, authority_class, binding)
      VALUES (p_authority, p_actor, scope, operations, p_class, coalesce(p_binding, '{}'::jsonb))
      RETURNING * INTO a;
    RETURN platform_control.read_authority(a.authority_id);
END $$;

CREATE OR REPLACE FUNCTION platform_control.revoke_authority(p_authority uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    UPDATE platform_control.authority SET revocation = 'revoked', revoked_at = clock_timestamp()
     WHERE authority_id = p_authority AND revocation = 'active';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'authority not found or already revoked' USING ERRCODE = 'U7004';
    END IF;
    RETURN platform_control.read_authority(p_authority);
END $$;

CREATE OR REPLACE FUNCTION platform_control.provision_target(p_target text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    IF p_target IS NULL OR p_target !~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$' THEN
        RAISE EXCEPTION 'invalid target identity' USING ERRCODE = 'U7003';
    END IF;
    INSERT INTO platform_control.target(target_id) VALUES (p_target) ON CONFLICT (target_id) DO NOTHING;
    RETURN jsonb_build_object('targetId', p_target, 'appliedCount',
        (SELECT applied_count FROM platform_control.target WHERE target_id = p_target));
END $$;

-- ---------------------------------------------------------------------------
-- Privileges: explicit EXECUTE grants only; no runtime/provisioner table DML.
-- ---------------------------------------------------------------------------

REVOKE ALL ON SCHEMA platform_control FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA platform_control FROM PUBLIC;

REVOKE ALL ON FUNCTION platform_control._receipt_json(platform_control.receipt, platform_control.operation) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control._promote(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.guard_authority(text, uuid, text, text, text, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.begin_operation(text, uuid, text, text, text, text, uuid, bigint, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.mark_executing(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.settle_operation(uuid, text, text, jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.promote_in_flight() FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.reconcile_receipt(uuid, boolean, jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.record_evidence(text, text, text, jsonb, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.reader_scope(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.read_receipt(text, uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.latest_evidence(text, uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.list_unresolved(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.status_counts(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.supervisor_summary() FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.read_authority(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.provision_authority(uuid, text, jsonb, jsonb, text, jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.revoke_authority(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.provision_target(text) FROM PUBLIC;

GRANT USAGE ON SCHEMA platform_control TO platform_control_runtime, platform_control_provisioner;

GRANT EXECUTE ON FUNCTION platform_control.begin_operation(text, uuid, text, text, text, text, uuid, bigint, text, text) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.mark_executing(uuid) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.settle_operation(uuid, text, text, jsonb) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.promote_in_flight() TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.reconcile_receipt(uuid, boolean, jsonb) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.record_evidence(text, text, text, jsonb, integer) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.read_receipt(text, uuid, uuid) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.latest_evidence(text, uuid, text) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.list_unresolved(text, uuid) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.status_counts(text, uuid) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.guard_authority(text, uuid, text, text, text, boolean) TO platform_control_runtime;

GRANT EXECUTE ON FUNCTION platform_control.provision_authority(uuid, text, jsonb, jsonb, text, jsonb) TO platform_control_provisioner;
GRANT EXECUTE ON FUNCTION platform_control.revoke_authority(uuid) TO platform_control_provisioner;
GRANT EXECUTE ON FUNCTION platform_control.provision_target(text) TO platform_control_provisioner;
GRANT EXECUTE ON FUNCTION platform_control.read_authority(uuid) TO platform_control_provisioner;
GRANT EXECUTE ON FUNCTION platform_control.supervisor_summary() TO platform_control_provisioner;
