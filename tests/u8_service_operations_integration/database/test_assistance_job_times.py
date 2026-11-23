"""PaperAssistance's job times (U8 plan Steps 47(a) and 48(a); NFR9.7).

`assistance.job.updated_at` starts at the job's own `accepted_at`, moves only when the
job's state or failure code changes, and the chain applies the file once, after
`u8_assistance.sql`, under PaperAssistance's owner. Every row here is written in one
transaction and rolled back, so the realm keeps nothing.
"""

from __future__ import annotations

import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend import u8_migrations
from backend.local_profile import private_bytes
from backend.u8_migrations import file_digest
from backend.u8_registry import chain_files_of

JOB_TIMES = "backend/modules/summarization/u8_assistance_job_times.sql"
ASSISTANCE = "backend/modules/summarization/u8_assistance.sql"
SOURCE_HASH = "a" * 64
INPUT_HASH = "b" * 64


def insert_job(conn) -> dict:
    """An open admission and its job, written with PaperAssistance's own column list
    (`guarded_repository.py`, which names no `updated_at`)."""
    operation, account, reservation = uuid4(), uuid4(), uuid4()
    intent = {"versionId": "u8-job-times-v1", "sourceHash": SOURCE_HASH}
    conn.execute(
        "INSERT INTO assistance.admission(operation_id,account_id,intent_hash,intent,"
        "disposition) VALUES(%s,%s,%s,%s,'open')",
        (operation, account, INPUT_HASH, Jsonb(intent)))
    conn.execute(
        "INSERT INTO assistance.job(id,account_id,authority_revision,version_id,"
        "source_hash,input_hash,payload,glossary_revision,glossary_snapshot,"
        "reservation_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (operation, account, uuid4(), intent["versionId"], SOURCE_HASH, INPUT_HASH,
         Jsonb(intent), "glossary-0", Jsonb([]), reservation))
    return {"id": operation}


def job_times(conn, job) -> dict:
    return conn.execute(
        "SELECT accepted_at, updated_at FROM assistance.job WHERE id=%s", (job,)).fetchone()


def now(conn):
    return conn.execute("SELECT clock_timestamp() AS at").fetchone()["at"]


@pytest.fixture
def assistance(connect):
    conn = connect("assistance")
    yield conn
    conn.rollback()


@pytest.fixture
def superuser(realm):
    """The realm's superuser on `docsuri_u8`, in a transaction rolled back at the end."""
    password = json.loads(private_bytes(realm.root / "migration-credentials.json"))[
        "databaseAdminPassword"]
    conn = psycopg.connect(
        host="127.0.0.1", port=realm.database_port, dbname=realm.database_name,
        user="postgres", password=password, connect_timeout=3, row_factory=dict_row)
    yield conn
    conn.rollback()
    conn.close()


def test_a_new_job_starts_at_its_accepted_time(assistance):
    job = insert_job(assistance)["id"]
    times = job_times(assistance, job)
    assert times["updated_at"] == times["accepted_at"]
    column = assistance.execute(
        "SELECT a.attnotnull AS not_null, format_type(a.atttypid, a.atttypmod) AS kind "
        "FROM pg_attribute a WHERE a.attrelid='assistance.job'::regclass "
        "AND a.attname='updated_at' AND NOT a.attisdropped").fetchone()
    assert column == {"not_null": True, "kind": "timestamp with time zone"}


def stamped(conn, job, statement: str, params: tuple = ()):
    """Run one update and return (before, updated_at, after)."""
    before = now(conn)
    conn.execute(statement, (*params, job))
    after = now(conn)
    return before, job_times(conn, job)["updated_at"], after


def test_a_state_change_stamps_updated_at_and_nothing_else_does(assistance):
    job = insert_job(assistance)["id"]
    # 1. A claim, complete as `acquire_claim` sets one (`complete_running_claim`).
    before, claimed, after = stamped(
        assistance, job,
        "UPDATE assistance.job SET state='running', worker_id=%s, lease_id=%s, "
        "lease_revision=%s, started_at=clock_timestamp(), "
        "lease_expires_at=clock_timestamp()+interval '30 seconds', fence=fence+1, "
        "phase='claimed' WHERE id=%s", (uuid4(), uuid4(), uuid4()))
    assert before <= claimed <= after
    # 2. While running, three updates that leave it where it was.
    for statement, params in (
        ("UPDATE assistance.job SET lease_id=%s, lease_revision=%s, fence=fence+1, "
         "lease_expires_at=lease_expires_at+interval '5 seconds' WHERE id=%s",
         (uuid4(), uuid4())),
        ("UPDATE assistance.job SET phase='generating' WHERE id=%s", ()),
        ("UPDATE assistance.job SET updated_at='2000-01-01 00:00:00+00' WHERE id=%s", ()),
    ):
        assistance.execute(statement, (*params, job))
        assert job_times(assistance, job)["updated_at"] == claimed, statement
    # 3. A failure code while running stamps.
    before, coded, after = stamped(
        assistance, job, "UPDATE assistance.job SET failure_code=%s WHERE id=%s",
        ("PROVIDER_UNAVAILABLE",))
    assert before <= coded <= after and coded >= claimed
    # 4. The terminal state stamps.
    before, failed, after = stamped(
        assistance, job, "UPDATE assistance.job SET state='failed' WHERE id=%s")
    assert before <= failed <= after and failed >= coded


def test_existing_jobs_take_their_accepted_time(superuser):
    superuser.execute("SET LOCAL ROLE docsuri_assistance_owner")
    superuser.execute("DROP FUNCTION assistance.job_touch() CASCADE")
    superuser.execute("ALTER TABLE assistance.job DROP COLUMN updated_at")
    job = insert_job(superuser)["id"]
    superuser.execute(
        (u8_migrations.ROOT / JOB_TIMES).read_text(), prepare=False)
    times = job_times(superuser, job)
    assert times["updated_at"] == times["accepted_at"]


def test_the_chain_applies_it_once_after_u8_assistance_sql(connect):
    files = u8_migrations.chain_files()
    assert files.count(JOB_TIMES) == 1
    assert files.index(ASSISTANCE) < files.index(JOB_TIMES)
    owner = {file: role for role, file in u8_migrations.migrations()}
    assert owner[JOB_TIMES] == "assistance"
    with connect("operations") as conn:
        applied = conn.execute(
            "SELECT schema_hashes FROM public.docsuri_local_identity").fetchone()["schema_hashes"]
    assert applied[JOB_TIMES] == file_digest(JOB_TIMES)
    assert JOB_TIMES in chain_files_of("service-operations")
    assert JOB_TIMES not in chain_files_of("paper-corpus")
