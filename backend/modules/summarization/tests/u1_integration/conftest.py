from __future__ import annotations

import hashlib

import pytest

from backend.migrations import MigrationBlocked, _atomic_sql
from tests.u1_integration.realm import (
    RealmBlocked,
    open_authority_connection,
    require_authority_realm,
)


@pytest.fixture
def authority_database():
    """Dedicated database, with transaction rollback; never DROP/TRUNCATE a schema."""
    try:
        realm = require_authority_realm()
        connection = open_authority_connection(realm)
    except (OSError, RealmBlocked) as exc:
        pytest.fail(str(exc), pytrace=False)
    try:
        with connection.transaction(force_rollback=True):
            existing = connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename <> 'u1_test_realm'"
            ).fetchall()
            if existing:
                pytest.fail(
                    "U1 disposable authority database is not empty; setup refused", pytrace=False
                )
            yield connection
    finally:
        connection.close()


def admitted_schema_statements() -> tuple[str, ...]:
    from backend.migrations.registry import registry

    # Actual definitions, with every byte rechecked before first fixture DDL.
    # This is rollback-only schema evidence, not production-ledger/adoption proof.
    definitions = [item for item in registry(owners={"accounts"})
                   if item.local_id == "001_create_accounts_table.sql"]
    definitions.extend(registry(owners={"summarization"}))
    statements = []
    for definition in definitions:
        payload = definition.path.read_bytes()
        if "sha256:" + hashlib.sha256(payload).hexdigest() != definition.digest:
            raise MigrationBlocked("script changed after planning")
        statements.append(_atomic_sql(payload, definition))
    return tuple(statements)


@pytest.fixture
def authority_schema(authority_database):
    # Admission for *every* script precedes the first DDL. No partially admitted
    # schema is created just to discover that 003 is blocked later.
    for statement in admitted_schema_statements():
        authority_database.execute(statement)
    yield authority_database
