"""ResearchWorkspace's wait reason (U8 plan Steps 5 and 6; the research executor, your
decision of 2026-10-24).

`research.job.wait_reason` holds `DEADLINE_EXCEEDED`, `DEPENDENCY_UNAVAILABLE` or null,
setting it leaves the job's owner time where it was, and the chain applies the file once,
after the research owner's other U8 files. Every row here is written in one transaction
of the research login and rolled back, so the realm keeps nothing.
"""

from __future__ import annotations

import json
import time
from uuid import uuid4

import psycopg
import pytest

from backend import u8_migrations
from backend.u8_migrations import file_digest
from backend.u8_registry import chain_files_of

WAITS = "backend/modules/research/u8_research_waits.sql"
EARLIER = (
    "backend/modules/research/u8_research.sql",
    "backend/modules/research/u8_research_job_times.sql",
    "backend/modules/research/u8_research_erasure.sql",
)


def insert_job(conn) -> dict:
    """One accepted novelty analysis in a context of its own."""
    owner, context, job = uuid4(), uuid4(), uuid4()
    conn.execute("INSERT INTO research.context(id,owner_id,purpose) VALUES(%s,%s,'novelty')",
                 (context, owner))
    conn.execute(
        "INSERT INTO research.job(id,owner_id,context_id,authority_session,kind,"
        "operation_key,input_hash,input,scope,policy,usage_id) "
        "VALUES(%s,%s,%s,%s,'novelty-analysis',%s,%s,'{}','{}',%s,%s)",
        (job, owner, context, uuid4(), "waits-" + uuid4().hex, "0" * 64,
         json.dumps({"policyId": "u4-synthetic-research", "revision": "1"}), uuid4()),
    )
    return {"id": job, "owner": owner, "context": context}


@pytest.fixture
def research(connect):
    conn = connect("research")
    yield conn
    conn.rollback()


def job_times(conn, job) -> dict:
    return conn.execute("SELECT wait_reason,updated_at FROM research.job WHERE id=%s",
                        (job,)).fetchone()


def test_the_column_takes_the_two_reasons_or_null_and_refuses_any_other(research):
    job = insert_job(research)["id"]
    assert job_times(research, job)["wait_reason"] is None
    for reason in ("DEADLINE_EXCEEDED", "DEPENDENCY_UNAVAILABLE", None):
        research.execute("UPDATE research.job SET wait_reason=%s WHERE id=%s", (reason, job))
        assert job_times(research, job)["wait_reason"] == reason
    for wrong in ("deadline_exceeded", "TIMEOUT", "", "CAPACITY_EXHAUSTED"):
        with pytest.raises(psycopg.errors.CheckViolation), research.transaction():
            research.execute("UPDATE research.job SET wait_reason=%s WHERE id=%s", (wrong, job))
    with pytest.raises(psycopg.errors.CheckViolation), research.transaction():
        research.execute(
            "INSERT INTO research.job(id,owner_id,context_id,authority_session,kind,"
            "operation_key,input_hash,input,scope,policy,usage_id,wait_reason) "
            "SELECT %s,owner_id,context_id,%s,'novelty-analysis',%s,%s,'{}','{}',policy,%s,"
            "'LATER' FROM research.job WHERE id=%s",
            (uuid4(), uuid4(), "waits-" + uuid4().hex, "0" * 64, uuid4(), job))


def test_setting_the_reason_leaves_the_owner_time_unchanged(research):
    job = insert_job(research)["id"]
    before = job_times(research, job)["updated_at"]
    # job_touch reads `clock_timestamp()`: the update below runs once that clock has
    # passed the insert's time, so an unwanted touch could not keep the same value. A
    # bounded read of the clock, never a fixed pause.
    deadline = time.monotonic() + 10
    while not research.execute("SELECT clock_timestamp() > %s AS later",
                               (before,)).fetchone()["later"]:
        assert time.monotonic() < deadline, "the database clock never passed the insert"
    research.execute("UPDATE research.job SET wait_reason='DEADLINE_EXCEEDED' WHERE id=%s",
                     (job,))
    assert job_times(research, job)["updated_at"] == before
    # A change the owner sees still moves it (U8's job_touch, unchanged).
    research.execute("UPDATE research.job SET state='failed' WHERE id=%s", (job,))
    assert job_times(research, job)["updated_at"] > before


def test_the_chain_applies_it_once_after_the_research_owners_other_u8_files(connect):
    files = u8_migrations.chain_files()
    assert files.count(WAITS) == 1
    assert all(files.index(earlier) < files.index(WAITS) for earlier in EARLIER)
    owner = {file: role for role, file in u8_migrations.migrations()}
    assert owner[WAITS] == "research"
    with connect("operations") as conn:
        applied = conn.execute(
            "SELECT schema_hashes FROM public.docsuri_local_identity").fetchone()["schema_hashes"]
    assert applied[WAITS] == file_digest(WAITS)
    # The contribution's schema digest covers it: chain files are attributed by their
    # name's unit prefix, so every `u8_` file is the complete assembly's own contribution.
    assert WAITS in chain_files_of("service-operations")
    assert WAITS not in chain_files_of("research-workspace")
