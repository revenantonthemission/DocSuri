-- Every new native effect requires a committed preparation and the unrecoverable reply secret.
-- The old signature is removed; installation of 010 alone already revokes its process grant.
ALTER TABLE r1_target.effect_ledger ADD COLUMN preparation_digest text;
ALTER TABLE r1_target.effect_ledger ALTER COLUMN fence_epoch TYPE numeric(20,0);
ALTER TABLE r1_target.effect_ledger ADD CONSTRAINT prepared_effect_required
    CHECK (preparation_digest IS NOT NULL) NOT VALID;
CREATE TABLE r1_target.helper_finalizations (
    run_id text NOT NULL, step text NOT NULL, attempt_id text NOT NULL,
    preparation_digest text NOT NULL, ledger_digest text NOT NULL,
    actor_role name NOT NULL, actor_oid oid NOT NULL,
    authority_revision bigint NOT NULL, lower_us numeric(20,0) NOT NULL,
    upper_us numeric(20,0) NOT NULL, payload jsonb NOT NULL, digest text NOT NULL,
    PRIMARY KEY(run_id,step,attempt_id),
    FOREIGN KEY(run_id,step,attempt_id) REFERENCES r1_target.effect_ledger(run_id,step,attempt_id)
);
ALTER TABLE r1_target.helper_finalizations OWNER TO r1_target_owner;
REVOKE ALL ON r1_target.helper_finalizations FROM PUBLIC;
GRANT SELECT ON r1_target.helper_finalizations TO r1_target_operator,r1_target_auditor,r1_run_owner;
GRANT SELECT ON r1_target.state,r1_target.effect_ledger TO r1_run_owner;
CREATE TRIGGER immutable_helper_finalization BEFORE UPDATE OR DELETE ON r1_target.helper_finalizations
    FOR EACH ROW EXECUTE FUNCTION r1_target.reject_mutation();
CREATE TRIGGER no_truncate_helper_finalization BEFORE TRUNCATE ON r1_target.helper_finalizations
    FOR EACH STATEMENT EXECUTE FUNCTION r1_target.reject_mutation();
GRANT EXECUTE ON FUNCTION r1_control.control_hash(jsonb),r1_control.control_u64(jsonb),
    r1_control.control_canonical(jsonb,integer)
    TO r1_target_owner;

CREATE FUNCTION r1_control.require_preparation(b jsonb, preparation text, secret text, approval text)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE p record; c record; r r1_control.runs; latest jsonb; caller_oid oid;
BEGIN
    SELECT * INTO p FROM r1_control.run_preparations WHERE checkpoint_digest=preparation;
    IF NOT FOUND THEN RAISE EXCEPTION 'preparation rejected' USING ERRCODE='R1T04'; END IF;
    SELECT oid INTO caller_oid FROM pg_roles WHERE rolname=session_user;
    IF (p.binding=b AND p.approval_id=approval AND p.executor_oid=caller_oid AND
        p.token_hash='sha256:' || encode(sha256(convert_to(secret,'UTF8')),'hex')) IS NOT TRUE
        OR pg_has_role(session_user,'r1_run_operator','MEMBER')
        OR EXISTS (SELECT 1 FROM r1_target.effect_ledger l WHERE l.run_id=p.run_id
            AND l.step=p.step AND l.attempt_id=p.attempt_id) THEN
        RAISE EXCEPTION 'preparation rejected' USING ERRCODE='R1T04';
    END IF;
    SELECT x.*,x.xmin::text AS writer_xid INTO c FROM r1_control.checkpoints x
        WHERE x.run_id=p.run_id AND x.sequence=p.sequence;
    IF NOT FOUND OR c.digest<>preparation OR c.digest<>r1_control.control_hash(c.payload)
       OR c.payload->'binding'<>b OR c.assurance<>'UNKNOWN'
       OR NOT EXISTS (SELECT 1 FROM r1_audit.events e JOIN r1_control.outbox o USING(event_id)
           WHERE e.event_id=r1_control.control_hash(jsonb_build_array('checkpoint',p.run_id,p.sequence::text))
             AND e.digest=r1_control.control_hash(e.payload)
             AND e.payload->>'checkpoint'=preparation AND e.payload->'binding'=b) THEN
        RAISE EXCEPTION 'checkpoint or audit evidence invalid' USING ERRCODE='R1T04';
    END IF;
    IF c.writer_xid::numeric=mod(pg_current_xact_id_if_assigned()::text::numeric,4294967296) THEN
        RAISE EXCEPTION 'checkpoint not independently committed' USING ERRCODE='R1T04';
    END IF;
    IF current_setting('fsync')<>'on' OR pg_is_in_recovery() THEN
        RAISE EXCEPTION 'preparation WAL durability unproven' USING ERRCODE='R1T04';
    END IF;
    -- The protected control adapter releases the secret only after synchronous commit ACK.
    -- MVCC plus the different-XID check proves independent commit here. A global WAL insertion
    -- pointer is not a checkpoint receipt: it includes unrelated/unimportant hint records.
    -- Target exclusion is already held. Pin coordination until the target transaction ends.
    SELECT * INTO r FROM r1_control.runs WHERE run_id=p.run_id FOR SHARE;
    latest := r1_control.latest_run_checkpoint(p.run_id,p.step);
    IF (r.state='RECONCILE_REQUIRED' AND r.current_attempt=p.attempt_id
        AND latest->'binding'=b AND latest#>>'{checkpoint,assurance}'='UNKNOWN') IS NOT TRUE THEN
        RAISE EXCEPTION 'preparation no longer dispatchable' USING ERRCODE='R1T04';
    END IF;
    RETURN p.authority_revision;
END $$;
ALTER FUNCTION r1_control.require_preparation(jsonb,text,text,text) OWNER TO r1_run_owner;
REVOKE ALL ON FUNCTION r1_control.require_preparation(jsonb,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION r1_control.require_preparation(jsonb,text,text,text) TO r1_target_owner;

CREATE FUNCTION r1_target.prepared_ledger_payload(b jsonb, approval text, revision bigint,
    actor text, preparation text) RETURNS jsonb
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
    SELECT jsonb_build_object('kind','rem1.target-effect.v3','binding',b,'approval',approval,
        'authorization_revision',revision::text,'actor_role',actor,'preparation',preparation)
$$;
ALTER FUNCTION r1_target.prepared_ledger_payload(jsonb,text,bigint,text,text) OWNER TO r1_target_owner;
REVOKE ALL ON FUNCTION r1_target.prepared_ledger_payload(jsonb,text,bigint,text,text) FROM PUBLIC;

DROP FUNCTION r1_target.apply_effect(text,text,text,text,text,text,text,text,text,bigint,text,text);
CREATE FUNCTION r1_target.apply_effect(
    target_name text,target_namespace text,target_incarnation text,
    effect_run_id text,effect_step text,effect_attempt_id text,effect_definition_digest text,
    effect_expected_before text,effect_expected_after text,effect_fence_epoch numeric,
    approval_id text,effect_plan_digest text,preparation text,secret text
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE b jsonb; expected_revision bigint; source record; ledger_digest text;
BEGIN
    PERFORM r1_control.control_u64(to_jsonb(effect_fence_epoch::text));
    b := jsonb_build_object('run_id',effect_run_id,'attempt_id',effect_attempt_id,
        'target',jsonb_build_object('target_id',target_name,'namespace',target_namespace,
            'incarnation',target_incarnation),'plan',effect_plan_digest,'step',effect_step,
        'definition_digest',effect_definition_digest,'expected_before',effect_expected_before,
        'expected_after',effect_expected_after,'fence_epoch',effect_fence_epoch::text);
    PERFORM pg_advisory_xact_lock(r1_target.lock_key(target_name,target_namespace));
    expected_revision := r1_control.require_preparation(b,preparation,secret,approval_id);
    SELECT * INTO source FROM r1_control.read_operator_authority(approval_id,false);
    IF (source.purpose='apply' AND source.revision=expected_revision
        AND source.plan_digest=effect_plan_digest AND source.target=target_name
        AND source.namespace=target_namespace AND source.incarnation=target_incarnation
        AND source.target_incarnation=target_incarnation AND source.target_epoch=effect_fence_epoch)
        IS NOT TRUE THEN
        RAISE EXCEPTION 'operator authority rejected' USING ERRCODE='R1T02';
    END IF;
    UPDATE r1_target.state SET digest=effect_expected_after WHERE target_id=target_name
        AND namespace=target_namespace AND incarnation=target_incarnation AND digest=effect_expected_before;
    IF NOT FOUND THEN RAISE EXCEPTION 'target state no longer matches expected_before' USING ERRCODE='R1T01'; END IF;
    ledger_digest := r1_control.control_hash(r1_target.prepared_ledger_payload(
        b,approval_id,source.revision,session_user::text,preparation));
    INSERT INTO r1_target.effect_ledger(run_id,step,attempt_id,definition_digest,expected_before,
        expected_after,fence_epoch,actor_role,authorization_revision,applied_at,digest,target_id,
        namespace,incarnation,plan_digest,approval_id,preparation_digest)
        VALUES(effect_run_id,effect_step,effect_attempt_id,effect_definition_digest,effect_expected_before,
            effect_expected_after,effect_fence_epoch,session_user,source.revision,clock_timestamp(),
            ledger_digest,target_name,target_namespace,target_incarnation,effect_plan_digest,approval_id,preparation);
    RETURN ledger_digest;
END $$;
ALTER FUNCTION r1_target.apply_effect(text,text,text,text,text,text,text,text,text,numeric,text,text,text,text)
    OWNER TO r1_target_owner;
REVOKE ALL ON FUNCTION r1_target.apply_effect(text,text,text,text,text,text,text,text,text,numeric,text,text,text,text)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION r1_target.apply_effect(text,text,text,text,text,text,text,text,text,numeric,text,text,text,text)
    TO r1_target_operator;

-- Only the protected target helper can attest its own in-flight effect after its clock/guard check.
-- This is a role-authenticated helper witness, not a coordinator-supplied authorization boolean.
CREATE FUNCTION r1_target.attest_effect(run_identity text,effect text,attempt text,
    preparation text,lower_bound text,upper_bound text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE l record; g record; lower_us numeric; upper_us numeric; body jsonb; caller_oid oid;
BEGIN
    lower_us := r1_control.control_u64(to_jsonb(lower_bound));
    upper_us := r1_control.control_u64(to_jsonb(upper_bound));
    SELECT x.*,x.xmin::text AS writer_xid INTO l FROM r1_target.effect_ledger x
        WHERE x.run_id=run_identity AND x.step=effect AND x.attempt_id=attempt;
    IF NOT FOUND OR l.preparation_digest IS DISTINCT FROM preparation
        OR l.actor_role IS DISTINCT FROM session_user
        OR l.writer_xid::numeric IS DISTINCT FROM mod(pg_current_xact_id()::text::numeric,4294967296) THEN
        RAISE EXCEPTION 'helper finalization rejected' USING ERRCODE='R1T04';
    END IF;
    SELECT * INTO g FROM r1_control.read_operator_authority(l.approval_id,true);
    IF g.revision<>l.authorization_revision OR lower_us>upper_us OR upper_us-lower_us>2000000
       OR extract(epoch FROM g.valid_from)*1000000>lower_us
       OR upper_us>=extract(epoch FROM g.valid_until)*1000000 THEN
        RAISE EXCEPTION 'helper clock or authority rejected' USING ERRCODE='R1T02';
    END IF;
    SELECT oid INTO caller_oid FROM pg_roles WHERE rolname=session_user;
    body := jsonb_build_object('kind','rem1.helper-finalization.v1','preparation',preparation,
        'ledger',l.digest,'actor_role',session_user::text,'actor_oid',caller_oid::text,
        'authority_revision',g.revision::text,'lower',lower_bound,'upper',upper_bound);
    INSERT INTO r1_target.helper_finalizations VALUES(run_identity,effect,attempt,preparation,
        l.digest,session_user,caller_oid,g.revision,lower_us,upper_us,body,r1_control.control_hash(body));
END $$;
ALTER FUNCTION r1_target.attest_effect(text,text,text,text,text,text) OWNER TO r1_target_owner;
REVOKE ALL ON FUNCTION r1_target.attest_effect(text,text,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION r1_target.attest_effect(text,text,text,text,text,text) TO r1_target_operator;

CREATE FUNCTION r1_target.require_helper_finalization() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM r1_target.helper_finalizations f
        WHERE f.run_id=NEW.run_id AND f.step=NEW.step AND f.attempt_id=NEW.attempt_id
          AND f.preparation_digest=NEW.preparation_digest AND f.ledger_digest=NEW.digest
          AND f.actor_role=NEW.actor_role AND f.authority_revision=NEW.authorization_revision
          AND f.digest=r1_control.control_hash(f.payload)) THEN
        RAISE EXCEPTION 'helper finalization missing' USING ERRCODE='R1T04';
    END IF;
    RETURN NEW;
END $$;
ALTER FUNCTION r1_target.require_helper_finalization() OWNER TO r1_target_owner;
REVOKE ALL ON FUNCTION r1_target.require_helper_finalization() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER guarded_prepared_commit AFTER INSERT ON r1_target.effect_ledger
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION r1_target.require_helper_finalization();

CREATE FUNCTION r1_target.observe_prepared_effect(b jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE l record; f record; target_state text; identity record; observed jsonb; expected jsonb;
    durable boolean; receipt text;
BEGIN
    observed := jsonb_build_object('binding',b,'authoritative',false,'receipt',NULL,'committed',false,
        'aborted',false,'quiescent',false,'observed_state',NULL,'authorization_verified',false,
        'durability_verified',false);
    IF NOT pg_try_advisory_xact_lock(r1_target.lock_key(b#>>'{target,target_id}',b#>>'{target,namespace}')) THEN
        RETURN observed;
    END IF;
    SELECT * INTO l FROM r1_target.effect_ledger WHERE run_id=b->>'run_id' AND step=b->>'step'
        AND attempt_id=b->>'attempt_id';
    SELECT digest INTO target_state FROM r1_target.state WHERE target_id=b#>>'{target,target_id}'
        AND namespace=b#>>'{target,namespace}' AND incarnation=b#>>'{target,incarnation}';
    SELECT incarnation,epoch INTO identity FROM r1_control.target_identity
        WHERE target_id=b#>>'{target,target_id}' AND namespace=b#>>'{target,namespace}';
    -- This profile's effect and helper witness commit together under the native synchronous
    -- finalizer. A global insertion pointer also includes this observer's caller row locks,
    -- so it cannot measure that historical commit. Reconciliation itself commits synchronously.
    durable := current_setting('fsync')='on' AND NOT pg_is_in_recovery();
    observed := observed || jsonb_build_object('observed_state',target_state);
    IF l.run_id IS NOT NULL THEN
        expected := jsonb_build_object('run_id',l.run_id,'attempt_id',l.attempt_id,
            'target',jsonb_build_object('target_id',l.target_id,'namespace',l.namespace,'incarnation',l.incarnation),
            'plan',l.plan_digest,'step',l.step,'definition_digest',l.definition_digest,
            'expected_before',l.expected_before,'expected_after',l.expected_after,'fence_epoch',l.fence_epoch::text);
        IF b IS DISTINCT FROM expected OR l.preparation_digest IS NULL
           OR l.digest<>r1_control.control_hash(r1_target.prepared_ledger_payload(
               b,l.approval_id,l.authorization_revision,l.actor_role,l.preparation_digest)) THEN
            RETURN observed;
        END IF;
        SELECT * INTO f FROM r1_target.helper_finalizations WHERE run_id=l.run_id AND step=l.step
            AND attempt_id=l.attempt_id AND ledger_digest=l.digest
            AND preparation_digest=l.preparation_digest AND actor_role=l.actor_role
            AND authority_revision=l.authorization_revision;
        RETURN observed || jsonb_build_object('authoritative',true,'receipt',l.digest,
            'committed',true,'quiescent',true,'durability_verified',durable,
            'authorization_verified',CASE WHEN f.digest IS NULL THEN false
                ELSE f.digest=r1_control.control_hash(f.payload) END);
    ELSIF durable AND target_state=b->>'expected_before' AND identity.incarnation=b#>>'{target,incarnation}'
        AND identity.epoch>(b->>'fence_epoch')::numeric THEN
        receipt := r1_control.control_hash(jsonb_build_object('kind','rem1.fenced-abort.v1','binding',b,
            'observedEpoch',identity.epoch::text,'observedState',target_state));
        RETURN observed || jsonb_build_object('authoritative',true,'receipt',receipt,'aborted',true,
            'quiescent',true,'durability_verified',true);
    END IF;
    RETURN observed;
END $$;
ALTER FUNCTION r1_target.observe_prepared_effect(jsonb) OWNER TO r1_target_owner;
REVOKE ALL ON FUNCTION r1_target.observe_prepared_effect(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION r1_target.observe_prepared_effect(jsonb) TO r1_target_operator,r1_run_owner;

-- Source-owner safety operation: advance (never reset) an epoch with CAS and atomic audit.
GRANT EXECUTE ON FUNCTION r1_control.control_hash(jsonb),r1_control.control_canonical(jsonb,integer),
    r1_control.control_u64(jsonb) TO r1_operator_authority_owner;
CREATE FUNCTION r1_control.advance_target_epoch(target_name text,target_namespace text,expected text)
RETURNS numeric LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE previous numeric; next_epoch numeric; incarnation_value text; body jsonb; event text;
BEGIN
    previous := r1_control.control_u64(to_jsonb(expected));
    UPDATE r1_control.target_identity t SET epoch=t.epoch+1
        WHERE t.target_id=target_name AND t.namespace=target_namespace AND t.epoch=previous
          AND t.epoch<18446744073709551615 RETURNING t.epoch,t.incarnation INTO next_epoch,incarnation_value;
    IF NOT FOUND THEN RAISE EXCEPTION 'target fence conflict or exhaustion' USING ERRCODE='R1C01'; END IF;
    body := jsonb_build_object('code','target_fence_advanced','target',target_name,
        'namespace',target_namespace,'incarnation',incarnation_value,'previous',expected,
        'epoch',next_epoch::text,'actorRole',session_user::text);
    event := r1_control.control_hash(body);
    INSERT INTO r1_audit.events(event_id,payload,digest) VALUES(event,body,event);
    INSERT INTO r1_control.outbox(event_id) VALUES(event);
    RETURN next_epoch;
END $$;
ALTER FUNCTION r1_control.advance_target_epoch(text,text,text) OWNER TO r1_operator_authority_owner;
REVOKE ALL ON FUNCTION r1_control.advance_target_epoch(text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION r1_control.advance_target_epoch(text,text,text) TO r1_operator_grant_admin;
