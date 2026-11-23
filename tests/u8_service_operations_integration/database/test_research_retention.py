"""How long production's research results are kept (U8 plan Steps 5 and 6; your decision
of 2026-10-24, "Until deleted or erased").

An artifact inserted under the `docsuri-production-research` policy stores the fixed
mark 9999-12-31 00:00:00+00 as its `expires_at`, whatever the insert gave; any other
policy keeps its own; U4's update guard still refuses a changed `expires_at`; and the
chain applies the file once, right after `u8_research_waits.sql`. Every row here is
written in one transaction of the research login and rolled back.
"""

from __future__ import annotations

import datetime as dt
import json
from uuid import uuid4

import psycopg
import pytest

from backend import u8_migrations
from backend.u8_migrations import file_digest

RETENTION = "backend/modules/research/u8_research_retention.sql"
WAITS = "backend/modules/research/u8_research_waits.sql"
MARK = dt.datetime(9999, 12, 31, tzinfo=dt.UTC)
PRODUCTION = {"policyId": "docsuri-production-research", "revision": "1"}
SYNTHETIC = {"policyId": "u4-synthetic-research", "revision": "1"}


@pytest.fixture
def research(connect):
    conn = connect("research")
    yield conn
    conn.rollback()


def insert_artifact(conn, policy: dict, expires_at) -> dict:
    """A novelty result for a job of its own; `expires_at` is a timestamp or SQL text."""
    owner, context, job, artifact = uuid4(), uuid4(), uuid4(), uuid4()
    conn.execute("INSERT INTO research.context(id,owner_id,purpose) VALUES(%s,%s,'novelty')",
                 (context, owner))
    conn.execute(
        "INSERT INTO research.job(id,owner_id,context_id,authority_session,kind,"
        "operation_key,input_hash,input,scope,policy,usage_id) "
        "VALUES(%s,%s,%s,%s,'novelty-analysis',%s,%s,'{}','{}',%s,%s)",
        (job, owner, context, uuid4(), "retention-" + uuid4().hex, "0" * 64,
         json.dumps(policy), uuid4()),
    )
    conn.execute(
        "INSERT INTO research.artifact(id,job_id,context_id,owner_id,content_hash,kind,"
        "output,policy,expires_at) VALUES(%s,%s,%s,%s,%s,'novelty-result','{}',%s,%s)",
        (artifact, job, context, owner, "1" * 64, json.dumps(policy), expires_at),
    )
    return conn.execute("SELECT id,expires_at,availability FROM research.artifact WHERE id=%s",
                        (artifact,)).fetchone()


def test_a_production_artifact_stores_the_fixed_mark_whatever_the_insert_gave(research):
    for given in (dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
                  dt.datetime.now(dt.UTC) - dt.timedelta(days=1),
                  dt.datetime(2026, 1, 1, tzinfo=dt.timezone(dt.timedelta(hours=9)))):
        row = insert_artifact(research, PRODUCTION, given)
        assert row["expires_at"] == MARK and row["availability"] == "ready"
    # The mark loads into a Python date in any session time zone.
    research.execute("SET LOCAL TIME ZONE 'Asia/Seoul'")
    loaded = research.execute(
        "SELECT expires_at FROM research.artifact WHERE id=%s", (row["id"],)).fetchone()
    assert loaded["expires_at"] == MARK


def test_any_other_policy_keeps_the_expiry_it_was_given(research):
    given = dt.datetime.now(dt.UTC).replace(microsecond=0) + dt.timedelta(hours=1)
    for policy in (SYNTHETIC, {"policyId": "docsuri-production-research-2", "revision": "1"},
                   {"policyId": "Docsuri-Production-Research", "revision": "1"}, {}):
        assert insert_artifact(research, policy, given)["expires_at"] == given


def test_u4s_update_guard_still_refuses_a_changed_expiry(research):
    for policy in (PRODUCTION, SYNTHETIC):
        row = insert_artifact(research, policy, dt.datetime.now(dt.UTC))
        with pytest.raises(psycopg.errors.CheckViolation, match="immutable artifact"), \
                research.transaction():
            research.execute("UPDATE research.artifact SET expires_at=clock_timestamp() "
                             "WHERE id=%s", (row["id"],))
    # Its availability may still end, as U4 built it (deletion, erasure, expiry).
    research.execute("UPDATE research.artifact SET availability='deleted' WHERE id=%s",
                     (row["id"],))


def test_the_chain_applies_the_file_once_right_after_the_wait_reason(connect):
    files = u8_migrations.chain_files()
    assert files.count(RETENTION) == 1
    assert files.index(RETENTION) == files.index(WAITS) + 1
    assert {file: role for role, file in u8_migrations.migrations()}[RETENTION] == "research"
    with connect("operations") as conn:
        applied = conn.execute(
            "SELECT schema_hashes FROM public.docsuri_local_identity").fetchone()["schema_hashes"]
    assert applied[RETENTION] == file_digest(RETENTION)
