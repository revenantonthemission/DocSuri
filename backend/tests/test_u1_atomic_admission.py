"""Pure admission/inherited guarded-executor tests. NO PostgreSQL SQL is executed."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import Mock

import pytest

from backend import migrations
from backend.migrations.registry import registry
from backend.migrations.u1_atomic_admission import EXPECTED_DIGEST, admits_u1_atomic_script


def candidate():
    definition = registry(owners={"summarization"})[-1]
    return definition, definition.path.read_bytes()


def test_exact_actual_definition_and_fixed_policy_pin_admit_unchanged_candidate_bytes() -> None:
    definition, payload = candidate()
    assert definition.digest == EXPECTED_DIGEST
    assert admits_u1_atomic_script(payload, definition)
    assert migrations._atomic_sql(payload, definition).encode() == payload
    with pytest.raises(migrations.MigrationBlocked, match="ATOMIC_STEP"):
        migrations._atomic_sql(payload)  # no definition => original conservative refusal


@pytest.mark.parametrize("change", [
    {"owner": "accounts"}, {"local_id": "004.sql"}, {"digest": "sha256:" + "0" * 64},
])
def test_owner_identity_and_definition_digest_lookalikes_are_not_registration(change) -> None:
    definition, payload = candidate()
    forged = replace(definition, **change)
    assert not admits_u1_atomic_script(payload, forged)
    with pytest.raises(migrations.MigrationBlocked):
        migrations._atomic_sql(payload, forged)


def test_copy_mutation_and_unregistered_context_cannot_self_admit(tmp_path) -> None:
    definition, payload = candidate()
    copy = tmp_path / definition.local_id
    copy.write_bytes(payload)
    assert not admits_u1_atomic_script(payload, replace(definition, path=copy))
    mutated = payload + b"\n-- changed bytes are a new definition\n"
    forged = replace(definition, digest="sha256:" + hashlib.sha256(mutated).hexdigest())
    assert not admits_u1_atomic_script(mutated, forged)
    with pytest.raises(migrations.MigrationBlocked):
        migrations._atomic_sql(mutated, forged)
    assert not admits_u1_atomic_script(payload, Mock(owner=definition.owner))
    # Even a nonprocedural replacement cannot escape the reserved candidate pin
    # through the general lane. Default context-free benign SQL stays unchanged.
    for replacement in (b"SELECT 1;", b"CREATE TABLE replacement(a int);"):
        changed = replace(definition, digest="sha256:" + hashlib.sha256(replacement).hexdigest())
        with pytest.raises(migrations.MigrationBlocked, match="U1 definition"):
            migrations._atomic_sql(replacement, changed)
    assert migrations._atomic_sql(b"SELECT 1;") == "SELECT 1;"


@pytest.mark.parametrize("payload", [
    b"BEGIN; SELECT 1; END;", b"START TRANSACTION;", b"COMMIT;", b"ROLLBACK;",
    b"VACUUM x;", b"CREATE INDEX CONCURRENTLY x ON y(z);", b"COPY x TO PROGRAM 'bad';",
    b"COPY x FROM '/external';", b"CALL x();", b"DO $$ BEGIN NULL; END; $$;",
    b"SET ROLE admin;", b"CREATE ROLE admin;", b"ALTER ROLE x SUPERUSER;",
    b"DROP USER x;", b"SET SESSION AUTHORIZATION admin;", b"RESET ROLE;",
    b"CREATE DATABASE x;", b"DROP DATABASE x;", b"ALTER SYSTEM SET x='y';",
])
def test_transaction_external_procedural_and_privileged_operations_remain_rejected(payload) -> None:
    definition, _ = candidate()
    for context in (None, definition):
        with pytest.raises(migrations.MigrationBlocked, match="ATOMIC_STEP"):
            migrations._atomic_sql(payload, context)
    assert migrations._atomic_sql(b"-- BEGIN in a full-line comment\nCREATE TABLE x(a int);")


class FakeConnection:
    """Records Python call order only; a string in execute is never interpreted."""

    def __init__(self):
        self.calls = []
        self.locked = True
        self.existing = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, parameters=()):
        self.calls.append(("execute", sql, parameters))
        row = (self.locked,) if "pg_try_advisory_lock" in sql else None
        return Mock(fetchone=Mock(return_value=row), fetchall=Mock(return_value=self.existing))

    @contextmanager
    def transaction(self):
        self.calls.append(("transaction_enter",))
        try:
            yield
        except Exception:
            self.calls.append(("transaction_rollback",))
            raise
        else:
            self.calls.append(("transaction_commit",))


class FakeAuthority:
    def __init__(self, connection, *, revoke_enter=False, revoke_commit=False):
        self.connection = connection
        self.revoke_enter, self.revoke_commit = revoke_enter, revoke_commit

    @contextmanager
    def guard(self, connection, identity, digest):
        assert connection is self.connection
        connection.calls.append(("guard_enter", identity, digest))
        if identity != "registry:bootstrap" and self.revoke_enter:
            raise PermissionError("revoked current authority")
        final = Mock()

        def before_commit():
            connection.calls.append(("before_commit", identity))
            if identity != "registry:bootstrap" and self.revoke_commit:
                raise PermissionError("revoked before commit")

        final.before_commit.side_effect = before_commit
        yield final
        connection.calls.append(("guard_exit", identity))


def configured(monkeypatch, *, status="PENDING"):
    definition, payload = candidate()
    connection = FakeConnection()
    monkeypatch.setattr("psycopg.connect", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(migrations, "for_paths", lambda _paths: (definition,))
    monkeypatch.setattr(migrations, "_inspect",
                        lambda *_args: migrations.Inspection(status, (definition.identity,)))
    return definition, payload, connection


def test_admission_is_inside_guard_transaction_before_ledger_and_commit(monkeypatch) -> None:
    definition, payload, connection = configured(monkeypatch)
    original = migrations._atomic_sql

    def admission(raw, actual):
        connection.calls.append(("admission", actual.identity))
        assert raw == payload and actual == definition
        return original(raw, actual)

    monkeypatch.setattr(migrations, "_atomic_sql", admission)
    applied = migrations.apply_migrations("postgresql://unused",
                                          authority=FakeAuthority(connection))
    assert applied == [definition.identity]
    calls = connection.calls
    guard = calls.index(("guard_enter", definition.identity, definition.digest))
    assert calls[guard + 1] == ("transaction_enter",)
    assert calls[guard + 2] == ("admission", definition.identity)
    assert calls[guard + 3] == ("execute", payload.decode(), ())
    assert "INSERT INTO public._migrations_v2" in calls[guard + 4][1]
    assert calls[guard + 4][2][:2] == (definition.identity, EXPECTED_DIGEST)
    assert calls[guard + 5] == ("before_commit", definition.identity)
    assert calls[guard + 6] == ("transaction_commit",)
    assert "pg_advisory_unlock(1380798032, 1)" in calls[-1][1]


@pytest.mark.parametrize("point", ["enter", "commit"])
def test_revoked_authority_is_not_applied_and_guarded_commit_rolls_back(monkeypatch, point) -> None:
    definition, payload, connection = configured(monkeypatch)
    authority = FakeAuthority(connection, revoke_enter=point == "enter",
                              revoke_commit=point == "commit")
    with pytest.raises(PermissionError, match="revoked"):
        migrations.apply_migrations("postgresql://unused", authority=authority)
    script_calls = [call for call in connection.calls if call[:2] == ("execute", payload.decode())]
    assert len(script_calls) == (0 if point == "enter" else 1)
    if point == "commit":
        assert ("transaction_rollback",) in connection.calls
    assert "pg_advisory_unlock" in connection.calls[-1][1]


def test_inherited_byte_lock_baseline_and_reconciliation_refusals(monkeypatch, tmp_path) -> None:
    definition, payload, connection = configured(monkeypatch)
    connection.locked = False
    with pytest.raises(migrations.MigrationBlocked, match="another"):
        migrations.apply_migrations("postgresql://unused", authority=FakeAuthority(connection))
    connection.locked = True
    for status, fields in [("CHANGED_DEFINITION", {"changed": (definition.identity,)}),
                           ("NEEDS_RECONCILIATION", {"legacy": (definition.local_id,)})]:
        monkeypatch.setattr(migrations, "_inspect",
                            lambda *_args, status=status, fields=fields:
                            migrations.Inspection(status, (), **fields))
        with pytest.raises(migrations.MigrationBlocked, match=status):
            migrations.apply_migrations("postgresql://unused", authority=FakeAuthority(connection))
    monkeypatch.setattr(migrations, "_inspect",
                        lambda *_args: migrations.Inspection("UNINITIALIZED", ()))
    connection.existing = [("u1_test_realm",)]
    with pytest.raises(migrations.MigrationBlocked, match="baseline reconciliation"):
        migrations.apply_migrations("postgresql://unused", authority=FakeAuthority(connection))
    connection.existing = []
    changed = tmp_path / "changed.sql"
    changed.write_bytes(payload + b"\n")
    monkeypatch.setattr(migrations, "for_paths", lambda _: (replace(definition, path=changed),))
    with pytest.raises(migrations.MigrationBlocked, match="changed after planning"):
        migrations.apply_migrations("postgresql://unused", authority=FakeAuthority(connection))
    with pytest.raises(migrations.MigrationBlocked, match="explicit current-authority"):
        migrations.apply_migrations("postgresql://unused")


def test_fixture_preadmits_every_definition_before_any_ddl(monkeypatch) -> None:
    from tests.u1_integration import conftest

    assert len(conftest.admitted_schema_statements()) == 4
    original = conftest._atomic_sql
    seen = []

    def refuse_last(payload, definition):
        seen.append(definition.identity)
        if definition.local_id.startswith("003_"):
            raise migrations.MigrationBlocked("candidate refused")
        return original(payload, definition)

    monkeypatch.setattr(conftest, "_atomic_sql", refuse_last)
    connection = Mock()
    with pytest.raises(migrations.MigrationBlocked, match="refused"):
        next(conftest.authority_schema.__wrapped__(connection))
    assert len(seen) == 4
    connection.execute.assert_not_called()
