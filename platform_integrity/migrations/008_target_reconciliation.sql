-- Bind new receipts completely. Legacy 006/007 rows stay unchanged and cannot be promoted
-- into v2 proof: missing target/plan/approval metadata is deliberately not backfilled.
ALTER TABLE r1_target.effect_ledger
    ADD COLUMN target_id text,
    ADD COLUMN namespace text,
    ADD COLUMN incarnation text,
    ADD COLUMN plan_digest text,
    ADD COLUMN approval_id text;
ALTER TABLE r1_target.effect_ledger ADD CONSTRAINT complete_effect_binding CHECK (
    target_id IS NOT NULL AND namespace IS NOT NULL AND incarnation IS NOT NULL
    AND plan_digest IS NOT NULL AND approval_id IS NOT NULL
) NOT VALID;

-- One physical target scope, independent of run, step, attempt and incarnation. The session
-- executor and readonly observer derive this same key; direct SQL also takes the transaction lock.
CREATE FUNCTION r1_target.lock_key(target_name text, target_namespace text) RETURNS bigint
LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog AS $$
    SELECT ('x' || substr(encode(sha256(convert_to(format(
        '["rem1.target-lock.v1",%s,%s]', to_json(target_name)::text,
        to_json(target_namespace)::text), 'UTF8')), 'hex'), 1, 15))::bit(60)::bigint
$$;
REVOKE ALL ON FUNCTION r1_target.lock_key(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION r1_target.lock_key(text,text) TO r1_target_owner;

-- An observed newer fence must not later be rewound to admit a delayed old dispatch.
CREATE FUNCTION r1_control.reject_epoch_rewind() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF NEW.epoch < OLD.epoch OR
       (NEW.incarnation <> OLD.incarnation AND NEW.epoch <= OLD.epoch) THEN
        RAISE EXCEPTION 'target epoch must advance across incarnation changes';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER monotonic_target_epoch BEFORE UPDATE ON r1_control.target_identity
    FOR EACH ROW EXECUTE FUNCTION r1_control.reject_epoch_rewind();

-- A direct caller cannot skip finalization by skipping the Python guard. Deferred checks
-- run at COMMIT, after expensive work, and hold source locks until the actual commit finishes.
-- This covers database facts only; it is NOT proof of the protected clock or actor mapping.
CREATE FUNCTION r1_target.finalize_effect() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE live_target record; grant_row record;
BEGIN
    SELECT incarnation,epoch INTO live_target FROM r1_control.target_identity
        WHERE target_id=NEW.target_id AND namespace=NEW.namespace FOR SHARE;
    IF NOT FOUND OR live_target.incarnation IS DISTINCT FROM NEW.incarnation
       OR live_target.epoch IS DISTINCT FROM NEW.fence_epoch THEN
        RAISE EXCEPTION 'target identity is not current' USING ERRCODE='R1T02';
    END IF;
    SELECT revision,revoked,purpose,target,namespace,incarnation,plan_digest INTO grant_row
        FROM r1_control.authority WHERE binding_id=NEW.approval_id FOR SHARE;
    IF NOT FOUND OR grant_row.revoked OR grant_row.purpose <> 'apply'
       OR grant_row.target IS DISTINCT FROM NEW.target_id
       OR grant_row.namespace IS DISTINCT FROM NEW.namespace
       OR grant_row.incarnation IS DISTINCT FROM NEW.incarnation
       OR grant_row.plan_digest IS DISTINCT FROM NEW.plan_digest
       OR grant_row.revision IS DISTINCT FROM NEW.authorization_revision THEN
        RAISE EXCEPTION 'operator authority is not current' USING ERRCODE='R1T02';
    END IF;
    IF current_setting('fsync') <> 'on' OR current_setting('synchronous_commit') <> 'on'
       OR pg_is_in_recovery() THEN
        RAISE EXCEPTION 'target durability is unavailable' USING ERRCODE='R1T03';
    END IF;
    RETURN NEW;
END $$;
ALTER FUNCTION r1_target.finalize_effect() OWNER TO r1_target_owner;
REVOKE ALL ON FUNCTION r1_target.finalize_effect() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER current_effect_at_commit AFTER INSERT ON r1_target.effect_ledger
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION r1_target.finalize_effect();

-- Remove the unbound signature rather than leaving an alternative execution path.
DROP FUNCTION r1_target.apply_effect(text,text,text,text,text,text,text,text,text,bigint,text);
CREATE FUNCTION r1_target.apply_effect(
    target_name text, target_namespace text, target_incarnation text,
    effect_run_id text, effect_step text, effect_attempt_id text,
    effect_definition_digest text, effect_expected_before text, effect_expected_after text,
    effect_fence_epoch bigint, approval_id text, effect_plan_digest text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE revision bigint; payload text; ledger_digest text; value text;
BEGIN
    FOREACH value IN ARRAY ARRAY[target_name,target_namespace,target_incarnation,
                                effect_run_id,effect_step,effect_attempt_id,approval_id] LOOP
        IF value IS NULL OR value !~ '^[A-Za-z0-9_.:@/-]{1,200}$' THEN
            RAISE EXCEPTION 'invalid effect command';
        END IF;
    END LOOP;
    FOREACH value IN ARRAY ARRAY[effect_definition_digest,effect_expected_before,
                                effect_expected_after,effect_plan_digest] LOOP
        IF value IS NULL OR value !~ '^sha256:[0-9a-f]{64}$' THEN
            RAISE EXCEPTION 'invalid effect command';
        END IF;
    END LOOP;
    IF effect_fence_epoch IS NULL OR effect_fence_epoch <= 0
       OR effect_expected_before=effect_expected_after THEN
        RAISE EXCEPTION 'invalid effect command';
    END IF;
    PERFORM pg_advisory_xact_lock(r1_target.lock_key(target_name,target_namespace));
    SELECT a.revision INTO revision FROM r1_control.authority a
        WHERE a.binding_id=approval_id AND NOT a.revoked AND a.purpose='apply'
          AND a.target=target_name AND a.namespace=target_namespace
          AND a.incarnation=target_incarnation AND a.plan_digest=effect_plan_digest;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'operator authority is not current' USING ERRCODE='R1T02';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM r1_control.target_identity t
        WHERE t.target_id=target_name AND t.namespace=target_namespace
          AND t.incarnation=target_incarnation AND t.epoch=effect_fence_epoch) THEN
        RAISE EXCEPTION 'target identity is not current' USING ERRCODE='R1T02';
    END IF;
    UPDATE r1_target.state SET digest=effect_expected_after
        WHERE target_id=target_name AND namespace=target_namespace
          AND incarnation=target_incarnation AND digest=effect_expected_before;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'target state no longer matches expected_before' USING ERRCODE='R1T01';
    END IF;
    -- Fixed ASCII keys in JCS order; every value is a string. No caller-selected SQL or path.
    payload := format('{"actorRole":%s,"approval":%s,"attemptId":%s,"authorizationRevision":%s,'
        '"definitionDigest":%s,"expectedAfter":%s,"expectedBefore":%s,"fenceEpoch":%s,'
        '"incarnation":%s,"kind":"rem1.target-effect.v2","namespace":%s,"plan":%s,'
        '"runId":%s,"step":%s,"targetId":%s}',
        to_json(session_user::text)::text,to_json(approval_id)::text,
        to_json(effect_attempt_id)::text,to_json(revision::text)::text,
        to_json(effect_definition_digest)::text,to_json(effect_expected_after)::text,
        to_json(effect_expected_before)::text,to_json(effect_fence_epoch::text)::text,
        to_json(target_incarnation)::text,to_json(target_namespace)::text,
        to_json(effect_plan_digest)::text,to_json(effect_run_id)::text,to_json(effect_step)::text,
        to_json(target_name)::text);
    ledger_digest := 'sha256:' || encode(sha256(convert_to(payload,'UTF8')),'hex');
    INSERT INTO r1_target.effect_ledger(run_id,step,attempt_id,definition_digest,expected_before,
        expected_after,fence_epoch,actor_role,authorization_revision,applied_at,digest,
        target_id,namespace,incarnation,plan_digest,approval_id)
        VALUES (effect_run_id,effect_step,effect_attempt_id,effect_definition_digest,
            effect_expected_before,effect_expected_after,effect_fence_epoch,session_user,revision,
            clock_timestamp(),ledger_digest,target_name,target_namespace,target_incarnation,
            effect_plan_digest,approval_id);
    RETURN ledger_digest;
END $$;
ALTER FUNCTION r1_target.apply_effect(text,text,text,text,text,text,text,text,text,bigint,text,text)
    OWNER TO r1_target_owner;
REVOKE ALL ON FUNCTION
    r1_target.apply_effect(text,text,text,text,text,text,text,text,text,bigint,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    r1_target.apply_effect(text,text,text,text,text,text,text,text,text,bigint,text,text)
    TO r1_target_operator;
GRANT SELECT (plan_digest) ON r1_control.authority TO r1_target_owner;
-- PostgreSQL requires UPDATE on at least one column for FOR SHARE. Only the inaccessible
-- definer role receives it, never the operator/auditor process roles.
GRANT UPDATE (revision) ON r1_control.authority TO r1_target_owner;
GRANT UPDATE (epoch) ON r1_control.target_identity TO r1_target_owner;
GRANT USAGE ON SCHEMA r1_control TO r1_target_operator,r1_target_auditor;
GRANT SELECT (target_id,namespace,incarnation,epoch) ON r1_control.target_identity
    TO r1_target_operator,r1_target_auditor;

-- Critical audit must not disappear with an outbox-cascading TRUNCATE either.
CREATE TRIGGER immutable_audit_truncate BEFORE TRUNCATE ON r1_audit.events
    FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();
