-- Scoped target command role and genuine append-only enforcement.
--
-- Two defects are corrected here. 006 declared r1_target.effect_ledger append-only in a comment
-- but installed no trigger, so nothing actually prevented UPDATE or DELETE. And the executor held
-- direct INSERT/UPDATE on the target plane, which is precisely the arbitrary table write that a
-- scoped command role exists to prevent. The effect is now reachable only through one narrow
-- SECURITY DEFINER command; the process role never holds table write rights.
CREATE SCHEMA IF NOT EXISTS r1_target;

DO $$
DECLARE name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['r1_target_owner','r1_target_operator','r1_target_auditor'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', name);
        ELSIF EXISTS (SELECT FROM pg_roles WHERE rolname=name AND
            (rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole
             OR rolreplication OR rolbypassrls)) THEN
            RAISE EXCEPTION 'existing REM-1 target group role is not safe';
        END IF;
    END LOOP;
END $$;

ALTER TABLE r1_target.state OWNER TO r1_target_owner;
ALTER TABLE r1_target.effect_ledger OWNER TO r1_target_owner;
ALTER TABLE r1_control.outbox OWNER TO r1_control_owner;

-- The 006 comment claimed append-only without enforcing it. Now it is enforced, and the same is
-- true of the outbox, which the plan requires to be append-only alongside the critical events.
CREATE FUNCTION r1_target.reject_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'target effect ledger is append-only';
END $$;
CREATE TRIGGER immutable_effect_ledger BEFORE UPDATE OR DELETE ON r1_target.effect_ledger
    FOR EACH ROW EXECUTE FUNCTION r1_target.reject_mutation();
-- A row trigger never fires for TRUNCATE, so the append-only guarantee needs its own guard.
CREATE TRIGGER immutable_effect_ledger_truncate BEFORE TRUNCATE ON r1_target.effect_ledger
    FOR EACH STATEMENT EXECUTE FUNCTION r1_target.reject_mutation();

CREATE FUNCTION r1_control.reject_outbox_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'control outbox is append-only';
END $$;
CREATE TRIGGER immutable_outbox BEFORE UPDATE OR DELETE ON r1_control.outbox
    FOR EACH ROW EXECUTE FUNCTION r1_control.reject_outbox_mutation();
CREATE TRIGGER immutable_outbox_truncate BEFORE TRUNCATE ON r1_control.outbox
    FOR EACH STATEMENT EXECUTE FUNCTION r1_control.reject_outbox_mutation();

-- The single scoped command. No caller-selected SQL, table or lock scope: the only inputs are
-- scalars, the compare-and-set target is fixed, and the row lock is taken by this function.
--
-- The command re-verifies the authority itself. The Python guard is defence in depth, not the
-- enforcement boundary: this role can be used to call this function directly, so a revoked,
-- expired, or retargeted grant must fail here even when no guard is in the call path.
CREATE FUNCTION r1_target.apply_effect(
    target_name text, target_namespace text, target_incarnation text,
    effect_run_id text, effect_step text, effect_attempt_id text,
    effect_definition_digest text, effect_expected_before text, effect_expected_after text,
    effect_fence_epoch bigint, approval_id text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE caller_role text; revision bigint; applied timestamptz; payload text; ledger_digest text;
BEGIN
    IF session_user !~ '^[A-Za-z0-9_]{1,63}$' OR effect_fence_epoch IS NULL
       OR effect_fence_epoch <= 0
       OR effect_run_id !~ '^[A-Za-z0-9_.:@/-]{1,200}$'
       OR effect_step !~ '^[A-Za-z0-9_.:@/-]{1,200}$'
       OR effect_attempt_id !~ '^[A-Za-z0-9_.:@/-]{1,200}$'
       OR effect_expected_before !~ '^sha256:[0-9a-f]{64}$'
       OR effect_expected_after !~ '^sha256:[0-9a-f]{64}$'
       OR effect_expected_before = effect_expected_after THEN
        RAISE EXCEPTION 'invalid effect command';
    END IF;
    caller_role := session_user;
    -- The clock-independent half of the authority check. These are facts about the grant that
    -- cannot change without a write, so they are verified here and cannot be skipped by a caller
    -- that bypasses the guard.
    --
    -- Two checks are deliberately NOT made here:
    --   * the validity window, because judging it needs a trustworthy clock and clock_timestamp()
    --     is not the protected chrony/NTS clock the plan requires. The guard decides expiry.
    --   * the approval's actor label, because binding a session to that label needs the database
    --     role mapping. Until that exists, only the guard can check it. See Step 10.
    IF NOT EXISTS (
        SELECT 1 FROM r1_control.authority a
        WHERE a.binding_id = approval_id
          AND a.revoked = false
          AND a.purpose = 'apply'
          AND a.target = target_name
          AND a.namespace = target_namespace
          AND a.incarnation = target_incarnation
    ) THEN
        RAISE EXCEPTION 'operator authority is not current' USING ERRCODE = 'R1T02';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM r1_control.target_identity t
        WHERE t.target_id = target_name AND t.namespace = target_namespace
          AND t.incarnation = target_incarnation AND t.epoch = effect_fence_epoch
    ) THEN
        RAISE EXCEPTION 'target identity is not current' USING ERRCODE = 'R1T02';
    END IF;
    -- Serialize every effect on this target state row; a second writer waits and then loses the
    -- compare-and-set rather than applying the same effect twice.
    PERFORM 1 FROM r1_target.state
        WHERE target_id=target_name AND namespace=target_namespace
          AND incarnation=target_incarnation FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'target state is not provisioned';
    END IF;
    IF (SELECT digest FROM r1_target.state WHERE target_id=target_name
          AND namespace=target_namespace AND incarnation=target_incarnation)
       <> effect_expected_before THEN
        RAISE EXCEPTION 'target state no longer matches expected_before' USING ERRCODE = 'R1T01';
    END IF;
    SELECT a.revision INTO revision FROM r1_control.authority a WHERE a.binding_id=approval_id;
    IF revision IS NULL THEN
        RAISE EXCEPTION 'operator authority row is absent';
    END IF;
    applied := clock_timestamp();
    -- Fixed ASCII keys, validated scalar strings, lexical ordering, lossless integers as text.
    payload := format('{"actorRole":%s,"approval":%s,"attemptId":%s,"authorizationRevision":%s,'
        '"definitionDigest":%s,"expectedAfter":%s,"expectedBefore":%s,"fenceEpoch":%s,'
        '"runId":%s,"step":%s,"targetId":%s}',
        to_json(caller_role)::text, to_json(approval_id)::text, to_json(effect_attempt_id)::text,
        to_json(revision::text)::text, to_json(effect_definition_digest)::text,
        to_json(effect_expected_after)::text, to_json(effect_expected_before)::text,
        to_json(effect_fence_epoch::text)::text, to_json(effect_run_id)::text,
        to_json(effect_step)::text, to_json(target_name)::text);
    ledger_digest := 'sha256:' || encode(sha256(convert_to(payload,'UTF8')),'hex');
    UPDATE r1_target.state SET digest=effect_expected_after
        WHERE target_id=target_name AND namespace=target_namespace
          AND incarnation=target_incarnation;
    INSERT INTO r1_target.effect_ledger(run_id,step,attempt_id,definition_digest,expected_before,
        expected_after,fence_epoch,actor_role,authorization_revision,applied_at,digest)
        VALUES (effect_run_id,effect_step,effect_attempt_id,effect_definition_digest,
                effect_expected_before,effect_expected_after,effect_fence_epoch,caller_role,revision,
                applied,ledger_digest);
    RETURN ledger_digest;
END $$;
ALTER FUNCTION r1_target.apply_effect(text,text,text,text,text,text,text,text,text,bigint,text)
    OWNER TO r1_target_owner;
REVOKE ALL ON FUNCTION r1_target.apply_effect(text,text,text,text,text,text,text,text,text,bigint,text)
    FROM PUBLIC;

-- Scoped grants. The operator may invoke the one command and read what it wrote; it may not
-- write, delete or truncate any table, and it has no rights at all in the control plane.
GRANT USAGE ON SCHEMA r1_target TO r1_target_owner, r1_target_operator, r1_target_auditor;
REVOKE ALL ON ALL TABLES IN SCHEMA r1_target FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA r1_target FROM r1_target_operator, r1_target_auditor;
-- Read-only reconciliation needs to see the state and the ledger it just wrote.
GRANT SELECT ON r1_target.state, r1_target.effect_ledger
    TO r1_target_operator, r1_target_auditor;
GRANT EXECUTE ON FUNCTION r1_target.apply_effect(text,text,text,text,text,text,text,text,text,bigint,text)
    TO r1_target_operator;
-- The command re-verifies the authority, so its owner may read exactly the columns that check
-- needs and nothing else. r1_target_owner is a NOLOGIN group role reachable only through the
-- function above, so these column rights are not usable on their own.
GRANT USAGE ON SCHEMA r1_control TO r1_target_owner;
GRANT SELECT (binding_id, revision, revoked, purpose, target, namespace, incarnation)
    ON r1_control.authority TO r1_target_owner;
GRANT SELECT (target_id, namespace, incarnation, epoch)
    ON r1_control.target_identity TO r1_target_owner;
