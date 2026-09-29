-- Explicit owner bootstrap. A reviewed source approval is bound to one authenticated login
-- per revision. Neither a caller's actor label nor SET ROLE can substitute for session_user.
DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['r1_operator_authority_owner','r1_operator_grant_admin',
                                    'r1_operator_authority_reader'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', role_name);
        ELSIF EXISTS (SELECT FROM pg_roles WHERE rolname=role_name AND
            (rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole
             OR rolreplication OR rolbypassrls)) THEN
            RAISE EXCEPTION 'existing REM-1 authority group role is not safe';
        END IF;
    END LOOP;
END $$;

CREATE TABLE r1_control.operator_role_bindings (
    approval_id text NOT NULL REFERENCES r1_control.authority(binding_id),
    authority_revision bigint NOT NULL CHECK (authority_revision >= 0),
    actor text NOT NULL,
    login_role name NOT NULL,
    login_oid oid NOT NULL,
    PRIMARY KEY (approval_id,authority_revision)
);
ALTER TABLE r1_control.operator_role_bindings OWNER TO r1_operator_authority_owner;
REVOKE ALL ON r1_control.operator_role_bindings FROM PUBLIC;
CREATE TRIGGER immutable_operator_binding BEFORE UPDATE OR DELETE
    ON r1_control.operator_role_bindings FOR EACH ROW EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER no_truncate_operator_bindings BEFORE TRUNCATE
    ON r1_control.operator_role_bindings FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();
GRANT USAGE ON SCHEMA r1_control TO r1_operator_authority_owner,
    r1_operator_grant_admin,r1_operator_authority_reader;
GRANT USAGE ON SCHEMA r1_audit TO r1_operator_authority_owner;
GRANT SELECT ON r1_control.authority,r1_control.target_identity TO r1_operator_authority_owner;
-- Required by source revoke and FOR SHARE, never granted to a process/helper login.
GRANT UPDATE (revision,revoked) ON r1_control.authority TO r1_operator_authority_owner;
GRANT UPDATE (epoch) ON r1_control.target_identity TO r1_operator_authority_owner;
GRANT INSERT ON r1_audit.events,r1_control.outbox TO r1_operator_authority_owner;

CREATE FUNCTION r1_control.bind_operator_role(
    approval text, expected_revision bigint, principal name
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE grant_row record; login record; existing record; payload text; event_digest text;
BEGIN
    SELECT * INTO login FROM pg_roles WHERE rolname=principal;
    IF NOT FOUND OR NOT login.rolcanlogin OR login.rolsuper OR login.rolcreatedb
       OR login.rolcreaterole OR login.rolreplication OR login.rolbypassrls
       OR principal !~ '^r1_[a-z0-9_]{1,59}$' THEN
        RAISE EXCEPTION 'unsafe operator login';
    END IF;
    IF pg_has_role(login.oid,'r1_operator_authority_owner','MEMBER')
       OR pg_has_role(login.oid,'r1_target_owner','MEMBER')
       OR pg_has_role(login.oid,'r1_control_owner','MEMBER')
       OR pg_has_role(login.oid,'r1_operator_grant_admin','MEMBER')
       OR pg_has_role(login.oid,'pg_read_all_data','MEMBER')
       OR pg_has_role(login.oid,'pg_write_all_data','MEMBER')
       OR pg_has_role(login.oid,'pg_execute_server_program','MEMBER')
       OR EXISTS (
           SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname IN ('r1_control','r1_target','r1_audit') AND c.relkind IN ('r','p')
             AND (has_table_privilege(login.oid,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE')
                  OR has_any_column_privilege(login.oid,c.oid,'INSERT,UPDATE'))
       ) THEN
        RAISE EXCEPTION 'unsafe operator login';
    END IF;
    SELECT actor,revision,revoked,valid_from,valid_until INTO grant_row
        FROM r1_control.authority WHERE binding_id=approval FOR UPDATE;
    IF NOT FOUND OR grant_row.revoked OR expected_revision IS NULL
       OR grant_row.revision <> expected_revision OR grant_row.valid_from IS NULL
       OR grant_row.valid_until <= grant_row.valid_from
       OR grant_row.valid_until-grant_row.valid_from > interval '30 minutes' THEN
        RAISE EXCEPTION 'operator approval cannot be bound';
    END IF;
    SELECT * INTO existing FROM r1_control.operator_role_bindings
        WHERE approval_id=approval AND authority_revision=expected_revision;
    IF FOUND THEN
        IF (existing.actor,existing.login_role,existing.login_oid) IS DISTINCT FROM
           (grant_row.actor,principal,login.oid) THEN
            RAISE EXCEPTION 'operator binding revision is immutable';
        END IF;
        RETURN;
    END IF;
    INSERT INTO r1_control.operator_role_bindings VALUES
        (approval,expected_revision,grant_row.actor,principal,login.oid);
    payload := format('{"actor":%s,"actorRole":%s,"approval":%s,'
        '"code":"operator_role_bound","loginOid":%s,"loginRole":%s,"revision":%s}',
        to_json(grant_row.actor)::text,to_json(session_user::text)::text,to_json(approval)::text,
        to_json(login.oid::text)::text,to_json(principal::text)::text,
        to_json(expected_revision::text)::text);
    event_digest := 'sha256:' || encode(sha256(convert_to(payload,'UTF8')),'hex');
    INSERT INTO r1_audit.events(event_id,payload,digest)
        VALUES (event_digest,payload::jsonb,event_digest);
    INSERT INTO r1_control.outbox(event_id) VALUES (event_digest);
END $$;
ALTER FUNCTION r1_control.bind_operator_role(text,bigint,name) OWNER TO r1_operator_authority_owner;
REVOKE ALL ON FUNCTION r1_control.bind_operator_role(text,bigint,name) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION r1_control.bind_operator_role(text,bigint,name) TO r1_operator_grant_admin;

CREATE FUNCTION r1_control.revoke_operator_grant(approval text) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE revision bigint; payload text; event_digest text;
BEGIN
    UPDATE r1_control.authority a SET revoked=true,revision=a.revision+1
        WHERE a.binding_id=approval RETURNING a.revision INTO revision;
    IF NOT FOUND THEN RAISE EXCEPTION 'operator grant not found'; END IF;
    payload := format('{"actorRole":%s,"approval":%s,"code":"operator_grant_revoked","revision":%s}',
        to_json(session_user::text)::text,to_json(approval)::text,to_json(revision::text)::text);
    event_digest := 'sha256:' || encode(sha256(convert_to(payload,'UTF8')),'hex');
    INSERT INTO r1_audit.events(event_id,payload,digest)
        VALUES (event_digest,payload::jsonb,event_digest);
    INSERT INTO r1_control.outbox(event_id) VALUES (event_digest);
    RETURN revision;
END $$;
ALTER FUNCTION r1_control.revoke_operator_grant(text) OWNER TO r1_operator_authority_owner;
REVOKE ALL ON FUNCTION r1_control.revoke_operator_grant(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION r1_control.revoke_operator_grant(text) TO r1_operator_grant_admin;

CREATE FUNCTION r1_control.read_operator_authority(approval text, finalizing boolean)
RETURNS TABLE(actor text,purpose text,target text,namespace text,incarnation text,plan_digest text,
    artifact_digest text,policy_digest text,revision bigint,valid_from timestamptz,
    valid_until timestamptz,revoked boolean,target_incarnation text,target_epoch numeric)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE g record; t record; mapped record; caller_oid oid;
BEGIN
    IF finalizing IS NULL THEN
        RAISE EXCEPTION 'operator authority rejected' USING ERRCODE='R1T02';
    END IF;
    SELECT a.* INTO g FROM r1_control.authority a WHERE a.binding_id=approval;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'operator authority rejected' USING ERRCODE='R1T02';
    END IF;
    -- Same order as the native finalizer: target identity, source grant, then immutable mapping.
    IF finalizing THEN
        SELECT i.incarnation,i.epoch INTO t FROM r1_control.target_identity i
            WHERE i.target_id=g.target AND i.namespace=g.namespace FOR SHARE;
        SELECT a.* INTO g FROM r1_control.authority a WHERE a.binding_id=approval FOR SHARE;
    ELSE
        SELECT i.incarnation,i.epoch INTO t FROM r1_control.target_identity i
            WHERE i.target_id=g.target AND i.namespace=g.namespace;
    END IF;
    SELECT p.oid INTO caller_oid FROM pg_roles p WHERE p.rolname=session_user;
    SELECT b.* INTO mapped FROM r1_control.operator_role_bindings b
        WHERE b.approval_id=approval AND b.authority_revision=g.revision;
    IF NOT FOUND OR g.revoked OR t.incarnation IS NULL
       OR mapped.actor IS DISTINCT FROM g.actor
       OR mapped.login_role IS DISTINCT FROM session_user
       OR mapped.login_oid IS DISTINCT FROM caller_oid THEN
        RAISE EXCEPTION 'operator authority rejected' USING ERRCODE='R1T02';
    END IF;
    RETURN QUERY SELECT g.actor,g.purpose,g.target,g.namespace,g.incarnation,g.plan_digest,
        g.artifact_digest,g.policy_digest,g.revision,g.valid_from,g.valid_until,g.revoked,
        t.incarnation,t.epoch;
END $$;
ALTER FUNCTION r1_control.read_operator_authority(text,boolean) OWNER TO r1_operator_authority_owner;
REVOKE ALL ON FUNCTION r1_control.read_operator_authority(text,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION r1_control.read_operator_authority(text,boolean)
    TO r1_target_operator,r1_target_owner,r1_operator_authority_reader;

-- Direct EXECUTE cannot bypass login binding, even when the Python guard is not in the path.
-- Check again at COMMIT; a source revision change invalidates the earlier mapping.
CREATE FUNCTION r1_target.require_operator_role() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE source record;
BEGIN
    SELECT * INTO source FROM r1_control.read_operator_authority(
        NEW.approval_id,TG_WHEN='AFTER');
    IF NEW.actor_role IS DISTINCT FROM session_user
       OR NEW.authorization_revision IS DISTINCT FROM source.revision THEN
        RAISE EXCEPTION 'operator authority rejected' USING ERRCODE='R1T02';
    END IF;
    RETURN NEW;
END $$;
ALTER FUNCTION r1_target.require_operator_role() OWNER TO r1_target_owner;
REVOKE ALL ON FUNCTION r1_target.require_operator_role() FROM PUBLIC;
CREATE TRIGGER mapped_effect_caller BEFORE INSERT ON r1_target.effect_ledger
    FOR EACH ROW EXECUTE FUNCTION r1_target.require_operator_role();
CREATE CONSTRAINT TRIGGER current_operator_at_commit AFTER INSERT ON r1_target.effect_ledger
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION r1_target.require_operator_role();
