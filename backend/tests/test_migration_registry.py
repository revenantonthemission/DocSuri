"""F08: readonly inspection and complete, owner-qualified migration identities."""

from unittest.mock import MagicMock

import pytest

from backend import migrations


def test_pending_inspection_never_issues_ddl(monkeypatch, tmp_path):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.return_value.fetchone.return_value = (None,)
    connection.execute.return_value.fetchall.return_value = []
    monkeypatch.setattr("psycopg.connect", lambda *args, **kwargs: connection)
    migrations.pending_migrations("postgresql://unused", [])
    statements = [str(call.args[0]).upper() for call in connection.execute.call_args_list]
    assert not any("CREATE " in sql or "INSERT " in sql for sql in statements)


def test_registry_covers_evidence_glossary_and_mypage():
    from backend.migrations.registry import registry

    owners = {spec.owner for spec in registry()}
    assert {"evidence", "summarization", "mypage", "research", "ingestion"} <= owners


def test_default_apply_cannot_run_without_explicit_authority(monkeypatch, tmp_path):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr("psycopg.connect", lambda *args, **kwargs: connection)
    with pytest.raises(migrations.MigrationBlocked, match="explicit"):
        migrations.apply_migrations("postgresql://unused", [tmp_path])


@pytest.mark.parametrize(
    "sql",
    [
        b"CREATE TABLE x(a int); COMMIT;",
        b"COPY x TO PROGRAM 'bad';",
        b"CREATE INDEX CONCURRENTLY x ON y(z);",
    ],
)
def test_nonatomic_or_external_effect_script_is_refused(sql):
    with pytest.raises(migrations.MigrationBlocked, match="ATOMIC_STEP"):
        migrations._atomic_sql(sql)
