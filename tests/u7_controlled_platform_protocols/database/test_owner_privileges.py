from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from docsuri_ops.platform_control.errors import ControlError

pytestmark = pytest.mark.u7_database


def key() -> str:
    return uuid4().hex


def test_runtime_role_is_bounded(harness):
    with harness.runtime.connection() as conn:
        row = conn.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
        assert row == (False, False, False, False)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE platform_control.authority SET revocation = 'revoked'",
        "DELETE FROM platform_control.receipt",
        "INSERT INTO platform_control.target(target_id) VALUES ('forged')",
        "UPDATE platform_control.operation SET state = 'completed'",
        "SELECT * FROM public.docsuri_u7_identity",
        "SET ROLE platform_control_owner",
        "CREATE TABLE platform_control.unowned(id integer)",
    ],
)
def test_runtime_direct_dml_and_privilege_escape_are_denied(harness, statement):
    with harness.runtime.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(statement)


def test_provisioner_cannot_execute_an_effect(harness):
    target = harness.target()
    with harness.provisioner.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "SELECT platform_control.begin_operation(%s, gen_random_uuid(), 'platform.file.write', %s, %s, 'e', gen_random_uuid(), 1, 'k', 'x')",
                (harness.actor, target, "a" * 64),
            )


def test_runtime_cannot_mint_authority(harness):
    with harness.runtime.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "SELECT platform_control.provision_authority(gen_random_uuid(), 'me', '[\"t\"]'::jsonb, '[\"platform.file.write\"]'::jsonb, 'routine', '{}'::jsonb)"
            )


def test_guard_functions_have_a_fixed_nonlogin_owner_and_safe_search_path(harness):
    with harness.runtime.connection() as conn:
        rows = conn.execute(
            "SELECT p.proname, p.prosecdef, p.proconfig, r.rolcanlogin "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "JOIN pg_roles r ON r.oid = p.proowner "
            "WHERE n.nspname = 'platform_control' AND p.proname IN "
            "('guard_authority','begin_operation','settle_operation','reconcile_receipt')"
        ).fetchall()
        assert len(rows) == 4
        assert all(
            security and config == ["search_path=pg_catalog"] and not login
            for _, security, config, login in rows
        )


def test_legitimate_guarded_write_works_under_real_runtime_grants(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = "b" * 64
    recorded = harness.evidence(target=target, input_hash=digest)
    binding = harness.runtime.begin_operation(
        actor=harness.actor,
        authority_id=authority,
        operation="platform.file.write",
        target=target,
        input_hash=digest,
        environment=harness.environment,
        evidence_id=recorded["evidenceId"],
        generation=recorded["generation"],
        idempotency_key=key(),
        effect_reference=f"{target}/effect-0123456789abcdef.json",
    )
    assert binding["operationState"] == "authorized"
    settled = harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="completed",
        disposition="applied",
        effect_refs=[f"{target}/effect-0123456789abcdef.json"],
    )
    assert settled["operationState"] == "completed"
    assert harness.receipt(binding["operationId"], authority)["outcome"] == "completed"


def test_foreign_dml_denial_does_not_block_the_guarded_path(harness):
    target = harness.target()
    with harness.runtime.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM platform_control.operation")
    # the denial is a positive control: the guarded path still refuses correctly
    authority = harness.grant(target=target)
    digest = "c" * 64
    recorded = harness.evidence(target=target, input_hash=digest)
    with pytest.raises(ControlError):  # no matching authority operation set
        harness.runtime.begin_operation(
            actor=harness.actor,
            authority_id=authority,
            operation="platform.file.probe",
            target=target,
            input_hash=digest,
            environment=harness.environment,
            evidence_id=recorded["evidenceId"],
            generation=recorded["generation"],
            idempotency_key=key(),
            effect_reference="x",
        )
