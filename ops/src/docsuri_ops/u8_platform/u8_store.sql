-- U8's additive amendment to PlatformControl's store (U8 plan Step 27; A6).
-- Applied after U7's schema.sql, as the store's owner role, by the composed realm's
-- tool and the production environment tool. Idempotent. U7's schema.sql, its rows and
-- its kinds are unchanged:
--   1. the protocol table also accepts A6's effect kinds (U7's three still do);
--   2. `read_receipt_named` answers U7's `read_receipt` plus the bound operation's
--      name, which C10's OperatorReceipt does not carry and the ledger component needs
--      to admit a receipt-bearing record (`platform.decision.record` included);
--   3. each store login is bound to its actor (your decision of 2026-10-26, "Bind each
--      login to its actor"): `u8_login_actor` maps a login to the one actor it acts as,
--      and U8's guarded functions refuse a binding, an evidence record or a settle whose
--      actor is not the calling login's (`session_user`) before U7's `guard_authority`
--      runs. In this store U7's runtime role holds only U8's guarded functions, not U7's
--      own; the reader login holds only the read functions, through the reader role
--      (`platform_control_u8_reader`, which the installer and the realm's tool create),
--      and is no member of the runtime role.

ALTER TABLE platform_control.protocol DROP CONSTRAINT IF EXISTS protocol_effect_kind_check;
ALTER TABLE platform_control.protocol ADD CONSTRAINT protocol_effect_kind_check CHECK (
    effect_kind IN (
        'file-write', 'file-probe', 'credential-presence',
        'database-backup', 'database-restore', 'database-recreate', 'database-remove',
        'service-control', 'tunnel-route', 'isolation-check', 'profile-change',
        'copy-dispose', 'v1-lifecycle-apply', 'decision-record', 'ledger-copy'
    )
);

CREATE OR REPLACE FUNCTION platform_control.read_receipt_named(p_actor text, p_authority uuid, p_operation uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE op platform_control.operation%ROWTYPE;
BEGIN
    SELECT * INTO op FROM platform_control.operation WHERE operation_id = p_operation;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown receipt' USING ERRCODE = 'U7004';
    END IF;
    RETURN platform_control.read_receipt(p_actor, p_authority, p_operation)
        || jsonb_build_object('operation', op.operation_name);
END $$;

REVOKE ALL ON FUNCTION platform_control.read_receipt_named(text, uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.read_receipt_named(text, uuid, uuid) FROM platform_control_runtime;

-- ---------------------------------------------------------------------------
-- 3. Each login bound to its actor
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS platform_control.u8_login_actor (
    login_name text PRIMARY KEY CHECK (login_name ~ '^[a-z_][a-z0-9_]{0,62}$'),
    actor_reference text NOT NULL CHECK (length(actor_reference) BETWEEN 1 AND 128),
    login_kind text NOT NULL CHECK (login_kind IN ('operator', 'scheduler', 'reader')),
    bound_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
REVOKE ALL ON platform_control.u8_login_actor FROM PUBLIC;

-- The provisioner binds a login once; a login is never rebound to another actor.
CREATE OR REPLACE FUNCTION platform_control.u8_bind_login(p_login text, p_actor text, p_kind text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE b platform_control.u8_login_actor%ROWTYPE;
BEGIN
    SELECT * INTO b FROM platform_control.u8_login_actor WHERE login_name = p_login FOR UPDATE;
    IF FOUND THEN
        IF b.actor_reference <> p_actor OR b.login_kind <> p_kind THEN
            RAISE EXCEPTION 'login already bound to another actor' USING ERRCODE = 'U7002';
        END IF;
    ELSE
        INSERT INTO platform_control.u8_login_actor(login_name, actor_reference, login_kind)
          VALUES (p_login, p_actor, p_kind) RETURNING * INTO b;
    END IF;
    RETURN jsonb_build_object('login', b.login_name, 'actor', b.actor_reference,
                              'kind', b.login_kind);
END $$;

-- What the provisioner reads back at an install's verify and on an existing install
-- (review findings, Minor, R16 and R17): for each named login, whether it is bound,
-- to which actor and kind, and whether it is a member of the runtime role (the reader
-- login must not be). A login the cluster does not hold is reported unbound.
CREATE OR REPLACE FUNCTION platform_control.u8_login_bindings(p_logins text[])
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE result jsonb := '{}'::jsonb; login text; b platform_control.u8_login_actor%ROWTYPE;
BEGIN
    FOREACH login IN ARRAY p_logins LOOP
        SELECT * INTO b FROM platform_control.u8_login_actor WHERE login_name = login;
        result := result || jsonb_build_object(login, jsonb_build_object(
            'bound', FOUND, 'actor', b.actor_reference, 'kind', b.login_kind,
            'runtimeMember', EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = login)
                             AND pg_catalog.pg_has_role(login, 'platform_control_runtime', 'MEMBER')));
    END LOOP;
    RETURN result;
END $$;

-- The actor the calling login acts as; `p_acting` refuses the reader login.
CREATE OR REPLACE FUNCTION platform_control.u8_calling_actor(p_acting boolean)
RETURNS text LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE b platform_control.u8_login_actor%ROWTYPE;
BEGIN
    SELECT * INTO b FROM platform_control.u8_login_actor WHERE login_name = session_user::text;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'login bound to no actor' USING ERRCODE = '42501';
    END IF;
    IF p_acting AND b.login_kind = 'reader' THEN
        RAISE EXCEPTION 'a reader login cannot act' USING ERRCODE = '42501';
    END IF;
    RETURN b.actor_reference;
END $$;

-- The calling login's actor must be the actor it names.
CREATE OR REPLACE FUNCTION platform_control.u8_require_actor(p_actor text, p_acting boolean)
RETURNS void LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    IF p_actor IS DISTINCT FROM platform_control.u8_calling_actor(p_acting) THEN
        RAISE EXCEPTION 'actor is not the calling login''s' USING ERRCODE = '42501';
    END IF;
END $$;

-- An operation the calling login's actor bound.
CREATE OR REPLACE FUNCTION platform_control.u8_require_own_operation(p_operation uuid)
RETURNS void LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE bound text;
BEGIN
    SELECT authority_actor INTO bound FROM platform_control.operation WHERE operation_id = p_operation;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown operation' USING ERRCODE = 'U7004';
    END IF;
    IF bound IS DISTINCT FROM platform_control.u8_calling_actor(true) THEN
        RAISE EXCEPTION 'operation bound by another actor' USING ERRCODE = '42501';
    END IF;
END $$;

-- The acting functions: a binding names the calling login's actor; an evidence record
-- comes from an acting login; a settle, a reconciliation and the executing mark touch
-- only the calling login's actor's own operations.
CREATE OR REPLACE FUNCTION platform_control.u8_record_evidence(p_target text, p_input_hash text, p_environment text, p_observations jsonb, p_max_age integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_calling_actor(true);
    RETURN platform_control.record_evidence(p_target, p_input_hash, p_environment, p_observations, p_max_age);
END $$;

CREATE OR REPLACE FUNCTION platform_control.u8_begin_operation(
    p_actor text, p_authority uuid, p_operation text, p_target text, p_input_hash text,
    p_environment text, p_evidence uuid, p_generation bigint, p_idempotency text,
    p_effect_reference text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_require_actor(p_actor, true);
    RETURN platform_control.begin_operation(p_actor, p_authority, p_operation, p_target,
        p_input_hash, p_environment, p_evidence, p_generation, p_idempotency, p_effect_reference);
END $$;

CREATE OR REPLACE FUNCTION platform_control.u8_mark_executing(p_operation uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_require_own_operation(p_operation);
    RETURN platform_control.mark_executing(p_operation);
END $$;

CREATE OR REPLACE FUNCTION platform_control.u8_settle_operation(p_operation uuid, p_outcome text, p_disposition text, p_effect_refs jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_require_own_operation(p_operation);
    RETURN platform_control.settle_operation(p_operation, p_outcome, p_disposition, p_effect_refs);
END $$;

CREATE OR REPLACE FUNCTION platform_control.u8_reconcile_receipt(p_operation uuid, p_applied boolean, p_evidence jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_require_own_operation(p_operation);
    RETURN platform_control.reconcile_receipt(p_operation, p_applied, p_evidence);
END $$;

CREATE OR REPLACE FUNCTION platform_control.u8_promote_in_flight()
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_calling_actor(true);
    RETURN platform_control.promote_in_flight();
END $$;

-- The read functions: any bound login, reading as its own actor.
CREATE OR REPLACE FUNCTION platform_control.u8_read_receipt(p_actor text, p_authority uuid, p_operation uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_require_actor(p_actor, false);
    RETURN platform_control.read_receipt(p_actor, p_authority, p_operation);
END $$;

CREATE OR REPLACE FUNCTION platform_control.u8_read_receipt_named(p_actor text, p_authority uuid, p_operation uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_require_actor(p_actor, false);
    RETURN platform_control.read_receipt_named(p_actor, p_authority, p_operation);
END $$;

CREATE OR REPLACE FUNCTION platform_control.u8_latest_evidence(p_actor text, p_authority uuid, p_target text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_require_actor(p_actor, false);
    RETURN platform_control.latest_evidence(p_actor, p_authority, p_target);
END $$;

CREATE OR REPLACE FUNCTION platform_control.u8_list_unresolved(p_actor text, p_authority uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_require_actor(p_actor, false);
    RETURN platform_control.list_unresolved(p_actor, p_authority);
END $$;

CREATE OR REPLACE FUNCTION platform_control.u8_status_counts(p_actor text, p_authority uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM platform_control.u8_require_actor(p_actor, false);
    RETURN platform_control.status_counts(p_actor, p_authority);
END $$;

-- The open operations of the named protocols in the caller's target scope: bound but
-- unsettled (receipt `pending`) or unknown and not yet reconciled (`unresolved`). An
-- erasure's backups scope waits while a set or a ledger copy is being written (L1-2,
-- U8 plan Step 64(g)); U7's `latest_evidence` and `list_unresolved` cannot answer it.
CREATE OR REPLACE FUNCTION platform_control.u8_open_operations(p_actor text, p_authority uuid, p_operations text[])
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE scope text[];
BEGIN
    PERFORM platform_control.u8_require_actor(p_actor, false);
    scope := platform_control.reader_scope(p_actor, p_authority);
    RETURN (
        SELECT coalesce(jsonb_agg(jsonb_build_object(
                   'operationId', o.operation_id, 'operation', o.operation_name,
                   'targetId', o.target_id) ORDER BY r.recorded_at), '[]'::jsonb)
          FROM platform_control.receipt r JOIN platform_control.operation o ON o.operation_id = r.operation_id
         WHERE r.reconciliation_state IN ('pending', 'unresolved')
           AND o.operation_name = ANY(p_operations) AND o.target_id = ANY(scope)
    );
END $$;

-- Grants. In this store the runtime role reaches U7's functions only through U8's
-- guarded ones (U7's own store and lane keep U7's grants).
REVOKE ALL ON FUNCTION platform_control.u8_bind_login(text, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_login_bindings(text[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_calling_actor(boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_require_actor(text, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_require_own_operation(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_record_evidence(text, text, text, jsonb, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_begin_operation(text, uuid, text, text, text, text, uuid, bigint, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_mark_executing(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_settle_operation(uuid, text, text, jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_reconcile_receipt(uuid, boolean, jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_promote_in_flight() FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_read_receipt(text, uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_read_receipt_named(text, uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_latest_evidence(text, uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_list_unresolved(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_status_counts(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_control.u8_open_operations(text, uuid, text[]) FROM PUBLIC;

REVOKE EXECUTE ON FUNCTION platform_control.begin_operation(text, uuid, text, text, text, text, uuid, bigint, text, text) FROM platform_control_runtime;
REVOKE EXECUTE ON FUNCTION platform_control.mark_executing(uuid) FROM platform_control_runtime;
REVOKE EXECUTE ON FUNCTION platform_control.settle_operation(uuid, text, text, jsonb) FROM platform_control_runtime;
REVOKE EXECUTE ON FUNCTION platform_control.promote_in_flight() FROM platform_control_runtime;
REVOKE EXECUTE ON FUNCTION platform_control.reconcile_receipt(uuid, boolean, jsonb) FROM platform_control_runtime;
REVOKE EXECUTE ON FUNCTION platform_control.record_evidence(text, text, text, jsonb, integer) FROM platform_control_runtime;
REVOKE EXECUTE ON FUNCTION platform_control.read_receipt(text, uuid, uuid) FROM platform_control_runtime;
REVOKE EXECUTE ON FUNCTION platform_control.latest_evidence(text, uuid, text) FROM platform_control_runtime;
REVOKE EXECUTE ON FUNCTION platform_control.list_unresolved(text, uuid) FROM platform_control_runtime;
REVOKE EXECUTE ON FUNCTION platform_control.status_counts(text, uuid) FROM platform_control_runtime;
REVOKE EXECUTE ON FUNCTION platform_control.guard_authority(text, uuid, text, text, text, boolean) FROM platform_control_runtime;

GRANT EXECUTE ON FUNCTION platform_control.u8_bind_login(text, text, text) TO platform_control_provisioner;
GRANT EXECUTE ON FUNCTION platform_control.u8_login_bindings(text[]) TO platform_control_provisioner;
GRANT EXECUTE ON FUNCTION platform_control.u8_record_evidence(text, text, text, jsonb, integer) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_begin_operation(text, uuid, text, text, text, text, uuid, bigint, text, text) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_mark_executing(uuid) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_settle_operation(uuid, text, text, jsonb) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_reconcile_receipt(uuid, boolean, jsonb) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_promote_in_flight() TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_read_receipt(text, uuid, uuid) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_read_receipt_named(text, uuid, uuid) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_latest_evidence(text, uuid, text) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_list_unresolved(text, uuid) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_status_counts(text, uuid) TO platform_control_runtime;
GRANT EXECUTE ON FUNCTION platform_control.u8_open_operations(text, uuid, text[]) TO platform_control_runtime;

-- The reader role: the read functions only. The installer and the realm's tool create
-- it (a role is the cluster's, not the owner's to create); without it the reader login
-- reads nothing, which fails closed.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'platform_control_u8_reader') THEN
        GRANT USAGE ON SCHEMA platform_control TO platform_control_u8_reader;
        GRANT EXECUTE ON FUNCTION platform_control.u8_read_receipt(text, uuid, uuid) TO platform_control_u8_reader;
        GRANT EXECUTE ON FUNCTION platform_control.u8_read_receipt_named(text, uuid, uuid) TO platform_control_u8_reader;
        GRANT EXECUTE ON FUNCTION platform_control.u8_latest_evidence(text, uuid, text) TO platform_control_u8_reader;
        GRANT EXECUTE ON FUNCTION platform_control.u8_list_unresolved(text, uuid) TO platform_control_u8_reader;
        GRANT EXECUTE ON FUNCTION platform_control.u8_status_counts(text, uuid) TO platform_control_u8_reader;
        GRANT EXECUTE ON FUNCTION platform_control.u8_open_operations(text, uuid, text[]) TO platform_control_u8_reader;
    END IF;
END $$;
