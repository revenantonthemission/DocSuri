"""F04 purge integrity against a real Postgres (live smoke, no AWS).

Exercises migration 013/014 behaviour that SQLite cannot:
- the BEFORE INSERT/UPDATE guard actually refuses writes for a non-ACTIVE owner (and permits
  them for an ACTIVE owner);
- ``accounts_try_purge_lock()`` is a genuine cross-connection transaction-scoped advisory lock,
  so a second sweep stands down while the first holds it and proceeds once the first commits.

Gated on ``DOCSURI_TEST_PG_DSN`` (skips otherwise — same convention as
``summarization/tests/test_assets_rds_real.py``). Set it to a throwaway Postgres; the test
applies the real migration files and cleans up after itself.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

DSN = os.environ.get("DOCSURI_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="set DOCSURI_TEST_PG_DSN to a test Postgres")

_MIGRATIONS = Path(__file__).resolve().parents[2] / "backend" / "modules" / "accounts" / "migrations"

# Minimal shapes the migration targets. The guard/function name the real tables, so these must
# exist (with the same names) for 013 to attach its triggers.
_SETUP = """
CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, status TEXT NOT NULL);
DROP TABLE IF EXISTS novelty_artifacts;
CREATE TABLE novelty_artifacts (
    artifact_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    object_key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS account_deletions (account_id TEXT PRIMARY KEY);
"""

_TEARDOWN = """
DROP TRIGGER IF EXISTS trg_block_owner_write_novelty_artifacts ON novelty_artifacts;
DROP TABLE IF EXISTS novelty_artifacts;
DROP TABLE IF EXISTS account_deletions;
DROP FUNCTION IF EXISTS accounts_block_owner_write_when_inactive();
DROP FUNCTION IF EXISTS accounts_try_purge_lock();
"""


@pytest.fixture
def db():
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(_TEARDOWN)
        c.execute(_SETUP)
        for name in ("013_block_late_writes_during_purge.sql", "014_add_purge_version.sql"):
            c.execute((_MIGRATIONS / name).read_text(encoding="utf-8"))
        c.execute("DELETE FROM accounts")
        c.execute("INSERT INTO accounts VALUES ('active-1','ACTIVE'), ('gone-1','DEACTIVATED')")
    yield


def test_late_write_guard_blocks_inactive_owner_only(db):
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("INSERT INTO novelty_artifacts VALUES ('a1','active-1','novelty/active-1/x')")
        for owner in ("gone-1", "no-such-owner"):
            with pytest.raises(psycopg.errors.CheckViolation):
                c.execute(
                    "INSERT INTO novelty_artifacts VALUES (%s,%s,'k')",
                    (f"art-{owner}", owner),
                )


def test_purge_advisory_lock_is_cross_connection_and_transaction_scoped(db):
    with psycopg.connect(DSN) as a:  # a transaction is open (autocommit off)
        assert a.execute("SELECT accounts_try_purge_lock()").fetchone()[0] is True
        with psycopg.connect(DSN) as b:
            assert b.execute("SELECT accounts_try_purge_lock()").fetchone()[0] is False
        a.commit()  # xact-scoped: releases on commit with no sweeper to clean up
    with psycopg.connect(DSN) as c:
        assert c.execute("SELECT accounts_try_purge_lock()").fetchone()[0] is True
        c.rollback()
