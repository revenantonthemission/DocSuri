"""Real isolated PostgreSQL privilege and current read-grant enforcement."""

import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest

from docsuri_platform_integrity.adapters.read_authority import PostgresReadAuthority
from docsuri_platform_integrity.contracts.codec import canonical, digest

DSN = os.environ.get("REM1_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="isolated REM1_TEST_PG_DSN required")
FP = "a" * 64


@pytest.fixture
def database():
    parsed = urlsplit(DSN)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 15439 and parsed.path == "/rem1_test"
    root = Path(__file__).resolve().parents[1] / "migrations"
    with psycopg.connect(DSN, autocommit=True) as conn:
        # This fixture applies every migration, so it must clear every schema they create.
        # Leaving r1_target behind made 007 collide with objects from a previous test.
        for schema in ("r1_control", "r1_audit", "r1_target"):
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        for source in sorted(root.glob("*.sql")):
            conn.execute(source.read_text())
        for role, group in (("r1_test_reader", "r1_control_reader"),
                            ("r1_test_issuer", "r1_read_grant_admin")):
            if conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone() is None:
                conn.execute(psycopg.sql.SQL("CREATE ROLE {} LOGIN").format(
                    psycopg.sql.Identifier(role)))
            conn.execute(psycopg.sql.SQL("GRANT {} TO {}").format(
                psycopg.sql.Identifier(group), psycopg.sql.Identifier(role)))
    yield


@contextmanager
def as_role(role):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL("SET SESSION AUTHORIZATION {}").format(
            psycopg.sql.Identifier(role)))
        yield conn


def issue(revision=0, revoked=False, starts=0):
    with as_role("r1_test_issuer") as conn:
        return conn.execute("SELECT r1_control.set_reader_grant(%s,%s,%s,%s,%s,%s)",
                            (FP, "subject", revision, starts, 200, revoked)).fetchone()[0]


def test_readonly_role_cannot_mutate_or_issue_grants(database):
    with as_role("r1_test_reader") as conn:
        conn.execute("SELECT * FROM r1_control.heads")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO r1_control.reader_grants VALUES (%s,'subject',1,0,200,false)",
                         (FP,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT r1_control.set_reader_grant(%s,'subject',0,0,200,false)", (FP,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM r1_control.authority")


def test_command_only_issuer_has_atomic_canonical_audit_and_live_revoke(database):
    assert issue() == 1
    authority = PostgresReadAuthority(lambda: as_role("r1_test_reader"), lambda: (100, 100))
    assert authority.permits(FP, "subject")
    assert not authority.permits(FP, "other")
    with as_role("r1_test_issuer") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM r1_control.reader_grants")
    assert issue(1, revoked=True) == 2
    assert not authority.permits(FP, "subject")
    with psycopg.connect(DSN) as conn:
        rows = conn.execute("SELECT payload,digest FROM r1_audit.events").fetchall()
        assert len(rows) == 2
        assert all(digest(canonical(payload)) == expected for payload, expected in rows)
        assert conn.execute("SELECT count(*) FROM r1_control.outbox").fetchone()[0] == 2


def test_bad_revision_fractional_time_and_audit_failure_do_not_change_grant(database):
    issue()
    with pytest.raises(psycopg.Error):
        issue(0, revoked=True)
    with pytest.raises(psycopg.Error):
        issue(1, starts=0.5)
    with psycopg.connect(DSN) as conn:
        conn.execute("REVOKE INSERT ON r1_audit.events FROM r1_control_owner")
    with pytest.raises(psycopg.Error):
        issue(1, revoked=True)
    with psycopg.connect(DSN) as conn:
        row = conn.execute("SELECT revision,revoked FROM r1_control.reader_grants").fetchone()
        assert row == (1, False)
