-- Co-located PostgreSQL coordination. Process roles get commands, never raw metadata writes.
DO $$
DECLARE n text;
BEGIN
    FOREACH n IN ARRAY ARRAY['r1_run_owner','r1_run_operator'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=n) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', n);
        ELSIF EXISTS (SELECT FROM pg_roles WHERE rolname=n AND
            (rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole
             OR rolreplication OR rolbypassrls)) THEN
            RAISE EXCEPTION 'unsafe existing run role';
        END IF;
    END LOOP;
END $$;
GRANT USAGE ON SCHEMA r1_control,r1_audit,r1_target TO r1_run_owner;
GRANT USAGE ON SCHEMA r1_control TO r1_run_operator;
GRANT SELECT,INSERT ON r1_control.runs,r1_control.submissions,r1_control.attempts,
    r1_control.checkpoints TO r1_run_owner;
GRANT UPDATE (state,current_attempt,checkpoint_revision) ON r1_control.runs TO r1_run_owner;
GRANT SELECT ON r1_control.authority,r1_control.operator_role_bindings,r1_control.target_identity,
    r1_audit.events,r1_control.outbox TO r1_run_owner;
GRANT INSERT ON r1_audit.events,r1_control.outbox TO r1_run_owner;
GRANT EXECUTE ON FUNCTION r1_control.read_operator_authority(text,boolean)
    TO r1_run_owner,r1_run_operator;

CREATE TABLE r1_control.attempt_bindings (
    run_id text NOT NULL, attempt_id text NOT NULL, approval_id text NOT NULL,
    authority_revision bigint NOT NULL, executor_oid oid NOT NULL,
    PRIMARY KEY (run_id,attempt_id),
    FOREIGN KEY (run_id,attempt_id) REFERENCES r1_control.attempts(run_id,attempt_id),
    FOREIGN KEY (approval_id,authority_revision)
        REFERENCES r1_control.operator_role_bindings(approval_id,authority_revision)
);
CREATE TABLE r1_control.run_preparations (
    checkpoint_digest text PRIMARY KEY, run_id text NOT NULL, step text NOT NULL,
    attempt_id text NOT NULL, sequence numeric(20,0) NOT NULL, binding jsonb NOT NULL,
    token_hash text NOT NULL, approval_id text NOT NULL, authority_revision bigint NOT NULL,
    executor_oid oid NOT NULL,
    UNIQUE (run_id,step,attempt_id),
    FOREIGN KEY (run_id,sequence) REFERENCES r1_control.checkpoints(run_id,sequence)
);
ALTER TABLE r1_control.attempt_bindings OWNER TO r1_run_owner;
ALTER TABLE r1_control.run_preparations OWNER TO r1_run_owner;
REVOKE ALL ON r1_control.attempt_bindings,r1_control.run_preparations FROM PUBLIC;
CREATE TRIGGER immutable_attempt_binding BEFORE UPDATE OR DELETE ON r1_control.attempt_bindings
    FOR EACH ROW EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER immutable_preparation BEFORE UPDATE OR DELETE ON r1_control.run_preparations
    FOR EACH ROW EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER no_truncate_attempt_binding BEFORE TRUNCATE ON r1_control.attempt_bindings
    FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER no_truncate_preparation BEFORE TRUNCATE ON r1_control.run_preparations
    FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();

-- Restricted C0 canonical profile, not a general RFC8785 replacement: ASCII field names,
-- safe integral JSON numbers, bounded depth/size. Run contracts use decimal strings for U64.
CREATE FUNCTION r1_control.control_canonical(v jsonb, depth integer DEFAULT 0) RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
DECLARE result text; item record; number numeric;
BEGIN
    IF v IS NULL OR depth>64 OR (depth=0 AND octet_length(v::text)>1048576) THEN
        RAISE EXCEPTION 'control JSON limit' USING ERRCODE='R1C01';
    END IF;
    CASE jsonb_typeof(v)
    WHEN 'object' THEN
        result := '';
        FOR item IN SELECT key,value FROM jsonb_each(v) ORDER BY key COLLATE "C" LOOP
            IF item.key !~ '^[A-Za-z_][A-Za-z0-9_]*$' THEN
                RAISE EXCEPTION 'unsupported control key' USING ERRCODE='R1C01';
            END IF;
            result := result || CASE WHEN result='' THEN '' ELSE ',' END ||
                to_json(item.key)::text || ':' || r1_control.control_canonical(item.value,depth+1);
        END LOOP;
        RETURN '{' || result || '}';
    WHEN 'array' THEN
        SELECT '[' || coalesce(string_agg(r1_control.control_canonical(value,depth+1),','
            ORDER BY ordinality),'') || ']' INTO result FROM jsonb_array_elements(v) WITH ORDINALITY;
        RETURN result;
    WHEN 'number' THEN
        number := (v#>>'{}')::numeric;
        IF number<>trunc(number) OR abs(number)>9007199254740991 THEN
            RAISE EXCEPTION 'unsafe control number' USING ERRCODE='R1C01';
        END IF;
        RETURN number::bigint::text;
    ELSE RETURN v::text;
    END CASE;
END $$;
CREATE FUNCTION r1_control.control_hash(v jsonb) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
    SELECT 'sha256:' || encode(sha256(convert_to(r1_control.control_canonical(v),'UTF8')),'hex')
$$;
CREATE FUNCTION r1_control.control_fields(v jsonb, names text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
    SELECT coalesce(jsonb_typeof(v)='object' AND v ?& names AND v-names='{}'::jsonb,false)
$$;
CREATE FUNCTION r1_control.control_ref(v text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
    SELECT coalesce(v ~ '^[A-Za-z0-9_.:@/-]{1,200}$',false)
$$;
CREATE FUNCTION r1_control.control_digest(v text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
    SELECT coalesce(v ~ '^sha256:[0-9a-f]{64}$',false)
$$;
CREATE FUNCTION r1_control.control_u64(v jsonb) RETURNS numeric
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
DECLARE value text := v#>>'{}';
BEGIN
    IF (jsonb_typeof(v)='string' AND value ~ '^(0|[1-9][0-9]{0,19})$') IS NOT TRUE THEN
        RAISE EXCEPTION 'invalid control integer' USING ERRCODE='R1C01';
    END IF;
    IF value::numeric>18446744073709551615 THEN
        RAISE EXCEPTION 'control integer overflow' USING ERRCODE='R1C01';
    END IF;
    RETURN value::numeric;
END $$;
CREATE FUNCTION r1_control.validate_run_plan(p jsonb) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE item jsonb; count_steps integer;
BEGIN
    IF (r1_control.control_fields(p,ARRAY['action','target','registry_digest','artifact_digest',
        'policy_digest','recovery_digest','steps']) AND r1_control.control_ref(p->>'action')
        AND r1_control.control_fields(p->'target',ARRAY['target_id','namespace','incarnation'])
        AND r1_control.control_ref(p#>>'{target,target_id}')
        AND r1_control.control_ref(p#>>'{target,namespace}')
        AND r1_control.control_ref(p#>>'{target,incarnation}')
        AND r1_control.control_digest(p->>'registry_digest')
        AND r1_control.control_digest(p->>'artifact_digest')
        AND r1_control.control_digest(p->>'policy_digest')
        AND r1_control.control_digest(p->>'recovery_digest')
        AND jsonb_typeof(p->'steps')='array') IS NOT TRUE THEN
        RAISE EXCEPTION 'invalid frozen plan' USING ERRCODE='R1C01';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_each(p) WHERE key NOT IN ('target','steps')
        AND jsonb_typeof(value)<>'string') OR EXISTS (
        SELECT 1 FROM jsonb_each(p->'target') WHERE jsonb_typeof(value)<>'string') THEN
        RAISE EXCEPTION 'invalid plan scalar type' USING ERRCODE='R1C01';
    END IF;
    count_steps := jsonb_array_length(p->'steps');
    IF count_steps NOT BETWEEN 1 AND 2000 OR count_steps<>(
        SELECT count(DISTINCT value->>'step') FROM jsonb_array_elements(p->'steps')) THEN
        RAISE EXCEPTION 'invalid planned steps' USING ERRCODE='R1C01';
    END IF;
    FOR item IN SELECT value FROM jsonb_array_elements(p->'steps') LOOP
        IF (r1_control.control_fields(item,ARRAY['step','definition_digest','expected_before',
            'expected_after']) AND r1_control.control_ref(item->>'step')
            AND r1_control.control_digest(item->>'definition_digest')
            AND r1_control.control_digest(item->>'expected_before')
            AND r1_control.control_digest(item->>'expected_after')
            AND item->>'expected_before'<>item->>'expected_after') IS NOT TRUE
            OR EXISTS (SELECT 1 FROM jsonb_each(item) WHERE jsonb_typeof(value)<>'string') THEN
            RAISE EXCEPTION 'invalid planned effect' USING ERRCODE='R1C01';
        END IF;
    END LOOP;
END $$;
CREATE FUNCTION r1_control.run_scope(approval text, p jsonb, purpose text, finalizing boolean)
RETURNS text LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE g record;
BEGIN
    SELECT * INTO g FROM r1_control.read_operator_authority(approval,finalizing);
    IF (g.purpose IN ('plan','run','reconcile') AND (purpose IS NULL OR g.purpose=purpose)
        AND g.plan_digest=r1_control.control_hash(p) AND g.target=p#>>'{target,target_id}'
        AND g.namespace=p#>>'{target,namespace}' AND g.incarnation=p#>>'{target,incarnation}'
        AND g.artifact_digest=p->>'artifact_digest' AND g.policy_digest=p->>'policy_digest')
        IS NOT TRUE THEN
        RAISE EXCEPTION 'control source scope rejected' USING ERRCODE='R1T02';
    END IF;
    RETURN g.actor;
END $$;
CREATE FUNCTION r1_control.checked_run(identity text, locked boolean DEFAULT false)
RETURNS r1_control.runs LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE r r1_control.runs; total numeric; latest numeric; expected jsonb;
BEGIN
    IF locked THEN
        SELECT * INTO r FROM r1_control.runs WHERE run_id=identity FOR UPDATE;
    ELSE SELECT * INTO r FROM r1_control.runs WHERE run_id=identity;
    END IF;
    IF NOT FOUND THEN RAISE EXCEPTION 'run not found' USING ERRCODE='R1C01'; END IF;
    expected := jsonb_build_object('run_id',identity,'plan',r.plan_digest,'target',r.plan_payload->'target',
        'semantic_key',r1_control.control_hash(jsonb_build_object(
            'kind','rem1.run-intent.v1','plan',r.plan_digest)));
    SELECT count(*),coalesce(max(sequence),0) INTO total,latest FROM r1_control.checkpoints
        WHERE run_id=identity;
    IF r.plan_digest<>r1_control.control_hash(r.plan_payload) OR r.intent_payload<>expected
        OR r.intent_digest<>r1_control.control_hash(expected)
        OR r.semantic_key<>expected->>'semantic_key'
        OR total<>r.checkpoint_revision OR latest<>r.checkpoint_revision THEN
        RAISE EXCEPTION 'run integrity or history gap' USING ERRCODE='R1C01';
    END IF;
    RETURN r;
END $$;
CREATE FUNCTION r1_control.latest_run_checkpoint(identity text, effect text) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE c record;
BEGIN
    SELECT * INTO c FROM r1_control.checkpoints WHERE run_id=identity AND step=effect
        ORDER BY sequence DESC LIMIT 1;
    IF NOT FOUND THEN RETURN NULL; END IF;
    IF c.digest<>r1_control.control_hash(c.payload)
       OR c.payload#>>'{binding,run_id}' IS DISTINCT FROM identity
       OR c.payload#>>'{binding,step}' IS DISTINCT FROM effect
       OR c.payload#>>'{binding,attempt_id}' IS DISTINCT FROM c.attempt_id
       OR c.payload#>>'{checkpoint,assurance}' IS DISTINCT FROM c.assurance
       OR c.payload#>>'{checkpoint,sequence}' IS DISTINCT FROM c.sequence::text THEN
        RAISE EXCEPTION 'checkpoint integrity mismatch' USING ERRCODE='R1C01';
    END IF;
    RETURN c.payload;
END $$;
CREATE FUNCTION r1_control.run_receipt(record jsonb, secret text DEFAULT NULL) RETURNS jsonb
LANGUAGE sql SET search_path=pg_catalog AS $$
    SELECT jsonb_build_object('record',record,'record_digest',r1_control.control_hash(record),
        'event_id',r1_control.control_hash(jsonb_build_array('checkpoint',
            record#>>'{binding,run_id}',record#>>'{checkpoint,sequence}')),'dispatch_token',secret)
$$;
CREATE FUNCTION r1_control.run_event(identity jsonb, body jsonb) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE event_id text := r1_control.control_hash(identity);
BEGIN
    body := body || jsonb_build_object('executorRole',session_user::text);
    INSERT INTO r1_audit.events(event_id,payload,digest)
        VALUES(event_id,body,r1_control.control_hash(body));
    INSERT INTO r1_control.outbox(event_id) VALUES(event_id);
END $$;
CREATE FUNCTION r1_control.append_run_checkpoint(record jsonb, ctx jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE b jsonb := record->'binding'; c jsonb := record->'checkpoint';
BEGIN
    INSERT INTO r1_control.checkpoints(run_id,sequence,payload,digest,step,attempt_id,assurance)
        VALUES(b->>'run_id',(c->>'sequence')::numeric,record,r1_control.control_hash(record),
            b->>'step',b->>'attempt_id',c->>'assurance');
    PERFORM r1_control.run_event(jsonb_build_array('checkpoint',b->>'run_id',c->>'sequence'),
        jsonb_build_object('code','effect_checkpoint','checkpoint',r1_control.control_hash(record),
            'binding',b,'assurance',c->>'assurance','context',ctx));
    RETURN r1_control.run_receipt(record);
END $$;

CREATE FUNCTION r1_control.run_read(identity text, approval text, part text, item text DEFAULT NULL)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE r r1_control.runs; payload jsonb; hash text;
BEGIN
    r := r1_control.checked_run(identity);
    PERFORM r1_control.run_scope(approval,r.plan_payload,NULL,false);
    CASE part
    WHEN 'run' THEN RETURN jsonb_build_object('intent',r.intent_payload,'plan',r.plan_payload,
        'state',r.state,'revision',r.checkpoint_revision::text,'attempt_id',r.current_attempt);
    WHEN 'latest' THEN
        payload := r1_control.latest_run_checkpoint(identity,item);
        RETURN CASE WHEN payload IS NULL THEN NULL ELSE r1_control.run_receipt(payload) END;
    WHEN 'attempt' THEN
        SELECT a.payload,a.digest INTO payload,hash FROM r1_control.attempts a
            WHERE a.run_id=identity AND a.attempt_id=item;
        IF NOT FOUND THEN RETURN NULL; END IF;
        IF hash<>r1_control.control_hash(payload) THEN
            RAISE EXCEPTION 'attempt integrity mismatch' USING ERRCODE='R1C01';
        END IF;
        RETURN payload;
    ELSE RAISE EXCEPTION 'invalid read command' USING ERRCODE='R1C01';
    END CASE;
END $$;

CREATE FUNCTION r1_control.run_command(action text, data jsonb, approval text, ctx jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE r r1_control.runs; p jsonb; payload jsonb; result jsonb; current jsonb; observation jsonb;
    b jsonb; effect jsonb; a record; apply_grant record; mapping record; command_actor text; purpose text;
    identity text := data->>'run_id'; attempt text := data->>'attempt_id'; step text := data->>'step';
    plan_hash text; semantic text; sequence numeric; ordinal bigint; fence_epoch numeric; found_run text;
    token text; assurance text; verified boolean := false; next_state text; predecessor jsonb;
BEGIN
    PERFORM r1_control.control_canonical(data);
    IF pg_has_role(session_user,'r1_target_operator','MEMBER') THEN
        RAISE EXCEPTION 'separate coordinator and target identities required' USING ERRCODE='R1T02';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_each(data) WHERE key NOT IN ('plan','fence')
        AND jsonb_typeof(value)<>'string') OR EXISTS (
        SELECT 1 FROM jsonb_each(ctx) WHERE jsonb_typeof(value)<>'string') THEN
        RAISE EXCEPTION 'control scalar types rejected' USING ERRCODE='R1C01';
    END IF;
    purpose := CASE action WHEN 'register' THEN 'plan' WHEN 'begin' THEN 'run'
        WHEN 'prepare' THEN 'run' WHEN 'reconcile' THEN 'reconcile' END;
    IF purpose IS NULL OR (r1_control.control_fields(ctx,ARRAY['actor','purpose','correlation',
        'recorded_at','time_quality']) AND ctx->>'purpose'=purpose
        AND r1_control.control_ref(ctx->>'actor') AND r1_control.control_ref(ctx->>'correlation')
        AND ctx->>'time_quality' IN ('trusted','unknown') AND r1_control.control_ref(identity))
        IS NOT TRUE THEN
        RAISE EXCEPTION 'invalid control command context' USING ERRCODE='R1C01';
    END IF;
    PERFORM r1_control.control_u64(ctx->'recorded_at');
    IF action='register' THEN
        IF NOT r1_control.control_fields(data,ARRAY['run_id','submission_key','plan'])
           OR NOT r1_control.control_ref(data->>'submission_key') THEN
            RAISE EXCEPTION 'invalid registration' USING ERRCODE='R1C01';
        END IF;
        p := data->'plan';
        PERFORM r1_control.validate_run_plan(p);
        command_actor := r1_control.run_scope(approval,p,purpose,false);
        IF command_actor<>ctx->>'actor' THEN RAISE EXCEPTION 'actor rejected' USING ERRCODE='R1T02'; END IF;
        plan_hash := r1_control.control_hash(p);
        semantic := r1_control.control_hash(jsonb_build_object('kind','rem1.run-intent.v1',
                                                               'plan',plan_hash));
        PERFORM pg_advisory_xact_lock(1380798032,2);
        SELECT s.run_id INTO found_run FROM r1_control.submissions s
            WHERE s.submission_key=data->>'submission_key';
        IF FOUND THEN
            r := r1_control.checked_run(found_run);
            IF r.semantic_key<>semantic THEN
                RAISE EXCEPTION 'submission changed meaning' USING ERRCODE='R1C01';
            END IF;
        ELSE
            SELECT x.run_id INTO found_run FROM r1_control.runs x WHERE x.semantic_key=semantic;
            IF FOUND THEN r := r1_control.checked_run(found_run);
            ELSE
                payload := jsonb_build_object('run_id',identity,'semantic_key',semantic,
                                             'plan',plan_hash,'target',p->'target');
                INSERT INTO r1_control.runs(run_id,semantic_key,plan_digest,state,plan_payload,
                    intent_payload,intent_digest) VALUES(identity,semantic,plan_hash,'PLANNED',p,
                    payload,r1_control.control_hash(payload));
                r := r1_control.checked_run(identity);
            END IF;
            INSERT INTO r1_control.submissions VALUES(data->>'submission_key',r.run_id);
            PERFORM r1_control.run_event(jsonb_build_array('submission',data->>'submission_key'),
                jsonb_build_object('code','run_registered','intent',r.intent_payload,'context',ctx));
        END IF;
        result := r.intent_payload;
    ELSE
        r := r1_control.checked_run(identity);
        command_actor := r1_control.run_scope(approval,r.plan_payload,purpose,false);
        IF command_actor<>ctx->>'actor' THEN RAISE EXCEPTION 'actor rejected' USING ERRCODE='R1T02'; END IF;
        -- Reconcile acquires target exclusion before the run row, matching native dispatch.
        -- If a writer is active, return the existing UNKNOWN rather than wait/replay anything.
        IF action='reconcile' AND NOT pg_try_advisory_xact_lock(r1_target.lock_key(
            r.plan_payload#>>'{target,target_id}',r.plan_payload#>>'{target,namespace}')) THEN
            IF r.checkpoint_revision<>r1_control.control_u64(data->'expected_revision') THEN
                RAISE EXCEPTION 'checkpoint revision conflict' USING ERRCODE='R1C01';
            END IF;
            current := r1_control.latest_run_checkpoint(identity,step);
            IF current IS NULL THEN RAISE EXCEPTION 'checkpoint not found' USING ERRCODE='R1C01'; END IF;
            RETURN r1_control.run_receipt(current);
        END IF;
        r := r1_control.checked_run(identity,true);
        p := r.plan_payload;
        IF action='begin' THEN
            IF NOT r1_control.control_fields(data,ARRAY['run_id','attempt_id','approval','invocation'])
               OR NOT r1_control.control_ref(attempt) OR NOT r1_control.control_ref(data->>'approval')
               OR NOT r1_control.control_ref(data->>'invocation') THEN
                RAISE EXCEPTION 'invalid attempt' USING ERRCODE='R1C01';
            END IF;
            SELECT * INTO a FROM r1_control.attempts WHERE run_id=identity AND attempt_id=attempt;
            IF FOUND THEN
                IF a.digest<>r1_control.control_hash(a.payload) OR
                   (a.payload->>'actor',a.payload->>'approval',a.invocation) IS DISTINCT FROM
                   (command_actor,data->>'approval',data->>'invocation') THEN
                    RAISE EXCEPTION 'attempt identity conflict' USING ERRCODE='R1C01';
                END IF;
                result := a.payload;
            ELSE
                IF r.state NOT IN ('PLANNED','PAUSED') OR EXISTS (
                    SELECT 1 FROM (SELECT DISTINCT ON (c.step) c.assurance FROM r1_control.checkpoints c
                        WHERE c.run_id=identity ORDER BY c.step,c.sequence DESC) latest
                        WHERE latest.assurance='UNKNOWN') THEN
                    RAISE EXCEPTION 'run requires reconciliation' USING ERRCODE='R1C01';
                END IF;
                SELECT g.* INTO apply_grant FROM r1_control.authority g WHERE g.binding_id=data->>'approval';
                IF NOT FOUND OR (NOT apply_grant.revoked AND apply_grant.purpose='apply'
                    AND apply_grant.actor=command_actor AND apply_grant.plan_digest=r.plan_digest
                    AND apply_grant.target=p#>>'{target,target_id}'
                    AND apply_grant.namespace=p#>>'{target,namespace}'
                    AND apply_grant.incarnation=p#>>'{target,incarnation}'
                    AND apply_grant.artifact_digest=p->>'artifact_digest'
                    AND apply_grant.policy_digest=p->>'policy_digest') IS NOT TRUE THEN
                    RAISE EXCEPTION 'apply approval rejected' USING ERRCODE='R1T02';
                END IF;
                SELECT * INTO mapping FROM r1_control.operator_role_bindings m
                    WHERE m.approval_id=apply_grant.binding_id AND m.authority_revision=apply_grant.revision
                      AND m.actor=command_actor;
                IF NOT FOUND THEN RAISE EXCEPTION 'executor mapping missing' USING ERRCODE='R1T02'; END IF;
                SELECT coalesce(max(x.ordinal),0)+1 INTO ordinal FROM r1_control.attempts x WHERE x.run_id=identity;
                payload := jsonb_build_object('run_id',identity,'attempt_id',attempt,'ordinal',ordinal,
                    'outcome','RUNNING','actor',command_actor,'approval',data->>'approval',
                    'invocation',data->>'invocation','started_at',ctx->>'recorded_at');
                INSERT INTO r1_control.attempts VALUES(identity,attempt,ordinal,data->>'invocation',
                                                       payload,r1_control.control_hash(payload));
                INSERT INTO r1_control.attempt_bindings VALUES(identity,attempt,apply_grant.binding_id,
                                                               apply_grant.revision,mapping.login_oid);
                UPDATE r1_control.runs SET state='RUNNING',current_attempt=attempt WHERE run_id=identity;
                PERFORM r1_control.run_event(jsonb_build_array('attempt',identity,attempt),
                    jsonb_build_object('code','attempt_started','attempt',payload,'context',ctx));
                result := payload;
            END IF;
        ELSE
            IF r.checkpoint_revision<>r1_control.control_u64(data->'expected_revision')
               OR r.checkpoint_revision>=18446744073709551615 THEN
                RAISE EXCEPTION 'checkpoint revision conflict or exhaustion' USING ERRCODE='R1C01';
            END IF;
            sequence := r.checkpoint_revision+1;
            current := r1_control.latest_run_checkpoint(identity,step);
            IF action='prepare' THEN
                IF NOT r1_control.control_fields(data,ARRAY['run_id','attempt_id','step','fence','expected_revision'])
                   OR (r.state='RUNNING' AND r.current_attempt=attempt
                       AND r1_control.control_fields(data->'fence',ARRAY['target','epoch','holder','validity'])
                       AND data#>'{fence,target}'=p->'target' AND data#>>'{fence,holder}'=attempt)
                       IS NOT TRUE THEN
                    RAISE EXCEPTION 'run or fence is not dispatchable' USING ERRCODE='R1C01';
                END IF;
                fence_epoch := r1_control.control_u64(data#>'{fence,epoch}');
                IF (jsonb_typeof(data#>'{fence,holder}')='string' AND r1_control.control_fields(
                    data#>'{fence,validity}',ARRAY['valid_from','valid_until'])) IS NOT TRUE THEN
                    RAISE EXCEPTION 'invalid fence validity' USING ERRCODE='R1C01';
                END IF;
                IF r1_control.control_u64(data#>'{fence,validity,valid_until}')
                    <=r1_control.control_u64(data#>'{fence,validity,valid_from}') THEN
                    RAISE EXCEPTION 'invalid fence interval' USING ERRCODE='R1C01';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM r1_control.target_identity t
                    WHERE t.target_id=p#>>'{target,target_id}' AND t.namespace=p#>>'{target,namespace}'
                      AND t.incarnation=p#>>'{target,incarnation}' AND t.epoch=fence_epoch) THEN
                    RAISE EXCEPTION 'target fence changed' USING ERRCODE='R1T02';
                END IF;
                SELECT x.payload INTO payload FROM r1_control.attempts x
                    WHERE x.run_id=identity AND x.attempt_id=attempt;
                SELECT * INTO a FROM r1_control.attempt_bindings x
                    WHERE x.run_id=identity AND x.attempt_id=attempt;
                IF NOT FOUND OR payload->>'actor' IS DISTINCT FROM command_actor THEN
                    RAISE EXCEPTION 'attempt provenance missing' USING ERRCODE='R1T02';
                END IF;
                IF EXISTS (SELECT 1 FROM (SELECT DISTINCT ON (c.step) c.assurance
                    FROM r1_control.checkpoints c WHERE c.run_id=identity
                    ORDER BY c.step,c.sequence DESC) latest WHERE latest.assurance='UNKNOWN') THEN
                    RAISE EXCEPTION 'unresolved effect' USING ERRCODE='R1C01';
                END IF;
                effect := NULL;
                FOR payload IN SELECT value FROM jsonb_array_elements(p->'steps') LOOP
                    IF payload->>'step'=step THEN effect := payload; EXIT; END IF;
                    predecessor := r1_control.latest_run_checkpoint(identity,payload->>'step');
                    IF predecessor->>'completion_verified' IS DISTINCT FROM 'true' THEN
                        RAISE EXCEPTION 'predecessor not verified' USING ERRCODE='R1C01';
                    END IF;
                    observation := r1_target.observe_prepared_effect(predecessor->'binding');
                    IF (observation->>'committed'='true' AND observation->>'authorization_verified'='true'
                        AND observation->>'durability_verified'='true') IS NOT TRUE THEN
                        RAISE EXCEPTION 'native predecessor proof missing' USING ERRCODE='R1C01';
                    END IF;
                END LOOP;
                IF effect IS NULL OR (current IS NOT NULL AND (
                    current#>>'{checkpoint,assurance}'<>'NO_EFFECT_CONFIRMED'
                    OR current#>>'{binding,attempt_id}'=attempt
                    OR (current#>>'{binding,fence_epoch}')::numeric>=fence_epoch)) THEN
                    RAISE EXCEPTION 'effect not dispatchable' USING ERRCODE='R1C01';
                END IF;
                b := jsonb_build_object('run_id',identity,'attempt_id',attempt,'target',p->'target',
                    'plan',r.plan_digest,'step',step,'definition_digest',effect->>'definition_digest',
                    'expected_before',effect->>'expected_before','expected_after',effect->>'expected_after',
                    'fence_epoch',fence_epoch::text);
                payload := jsonb_build_object('binding',b,'checkpoint',jsonb_build_object(
                    'run_id',identity,'step',step,'sequence',sequence::text,'assurance','UNKNOWN','receipt',NULL),
                    'recorded_at',ctx->>'recorded_at','completion_verified',false);
                result := r1_control.append_run_checkpoint(payload,ctx);
                token := gen_random_uuid()::text || gen_random_uuid()::text;
                INSERT INTO r1_control.run_preparations VALUES(r1_control.control_hash(payload),
                    identity,step,attempt,sequence,b,
                    'sha256:' || encode(sha256(convert_to(token,'UTF8')),'hex'),a.approval_id,
                    a.authority_revision,a.executor_oid);
                result := result || jsonb_build_object('dispatch_token',token);
                next_state := 'RECONCILE_REQUIRED';
            ELSE
                IF NOT r1_control.control_fields(data,ARRAY['run_id','step','expected_revision']) OR current IS NULL THEN
                    RAISE EXCEPTION 'checkpoint not found or invalid reconcile' USING ERRCODE='R1C01';
                END IF;
                IF current#>>'{checkpoint,assurance}' IN ('COMMITTED','NO_EFFECT_CONFIRMED') THEN
                    result := r1_control.run_receipt(current);
                    PERFORM r1_control.run_scope(approval,p,purpose,true);
                    RETURN result;
                END IF;
                b := current->'binding';
                -- Native observation only. No caller-supplied success/authorization booleans.
                observation := r1_target.observe_prepared_effect(b);
                assurance := 'UNKNOWN';
                IF observation->>'committed'='true' AND observation->>'observed_state'=b->>'expected_after' THEN
                    assurance := 'COMMITTED';
                    verified := observation->>'authorization_verified'='true'
                            AND observation->>'durability_verified'='true';
                ELSIF observation->>'aborted'='true' AND observation->>'quiescent'='true'
                    AND observation->>'observed_state'=b->>'expected_before' THEN
                    assurance := 'NO_EFFECT_CONFIRMED';
                END IF;
                payload := jsonb_build_object('binding',b,'checkpoint',jsonb_build_object('run_id',identity,
                    'step',step,'sequence',sequence::text,'assurance',assurance,'receipt',
                    CASE WHEN assurance='UNKNOWN' THEN NULL ELSE observation->>'receipt' END),
                    'recorded_at',ctx->>'recorded_at','completion_verified',verified);
                result := r1_control.append_run_checkpoint(payload,ctx);
                next_state := CASE WHEN assurance='UNKNOWN' THEN 'RECONCILE_REQUIRED' ELSE 'PAUSED' END;
                IF verified THEN
                    next_state := 'SUCCEEDED';
                    FOR effect IN SELECT value FROM jsonb_array_elements(p->'steps') LOOP
                        predecessor := r1_control.latest_run_checkpoint(identity,effect->>'step');
                        IF predecessor->>'completion_verified' IS DISTINCT FROM 'true' THEN next_state := 'RUNNING'; END IF;
                    END LOOP;
                END IF;
            END IF;
            UPDATE r1_control.runs SET state=next_state,checkpoint_revision=sequence WHERE run_id=identity;
        END IF;
    END IF;
    IF r1_control.run_scope(approval,p,purpose,true) IS DISTINCT FROM command_actor THEN
        RAISE EXCEPTION 'control source changed' USING ERRCODE='R1T02';
    END IF;
    IF current_setting('fsync')<>'on' OR current_setting('synchronous_commit')<>'on' OR pg_is_in_recovery() THEN
        RAISE EXCEPTION 'control durability unavailable' USING ERRCODE='R1C01';
    END IF;
    RETURN result;
END $$;

-- Private helpers are executable only by the inaccessible definer. Public entry points are fixed.
DO $$
DECLARE f regprocedure;
BEGIN
    FOR f IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='r1_control' AND p.proname IN ('control_canonical','control_hash','control_fields',
            'control_ref','control_digest','control_u64','validate_run_plan','run_scope','checked_run',
            'latest_run_checkpoint','run_receipt','run_event','append_run_checkpoint','run_read','run_command') LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO r1_run_owner',f);
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',f);
    END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION r1_control.run_read(text,text,text,text),
    r1_control.run_command(text,jsonb,text,jsonb) TO r1_run_operator;
GRANT EXECUTE ON FUNCTION r1_target.lock_key(text,text) TO r1_run_owner;
-- No unprepared apply during a partially installed 010/011 profile.
REVOKE EXECUTE ON FUNCTION r1_target.apply_effect(text,text,text,text,text,text,text,text,text,bigint,text,text)
    FROM r1_target_operator;
