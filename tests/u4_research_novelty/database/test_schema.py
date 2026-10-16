"""Real owner-role constraints; no in-memory database substitute."""

from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb


def context(conn, owner=None):
    identifier, owner = uuid4(), owner or uuid4()
    conn.execute("INSERT INTO research.context(id,owner_id,purpose) VALUES(%s,%s,'research')", (identifier, owner))
    return identifier, owner


def job(conn):
    context_id, owner = context(conn)
    identifier = uuid4()
    conn.execute("INSERT INTO research.job(id,owner_id,context_id,authority_session,kind,operation_key,input_hash,input,scope,policy,usage_id) VALUES(%s,%s,%s,%s,'novelty-analysis',%s,%s,%s,%s,%s,%s)",
                 (identifier, owner, context_id, uuid4(), str(uuid4()), "a" * 64, Jsonb({}), Jsonb({}), Jsonb({}), uuid4()))
    return identifier, context_id, owner


def test_composite_owner_context_fk(connect):
    with connect("research") as conn:
        context_id, _ = context(conn)
        with pytest.raises(psycopg.errors.ForeignKeyViolation), conn.transaction():
            conn.execute("INSERT INTO research.session(id,owner_id,context_id,title,scope) VALUES(%s,%s,%s,'x','{}')", (uuid4(), uuid4(), context_id))


def test_tombstone_never_reactivates(connect):
    with connect("research") as conn:
        identifier, _ = context(conn)
        conn.execute("UPDATE research.context SET lifecycle='deleted',deleted_at=clock_timestamp(),revision=2 WHERE id=%s", (identifier,))
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("UPDATE research.context SET lifecycle='active' WHERE id=%s", (identifier,))


def test_accepted_input_immutable(connect):
    with connect("research") as conn:
        identifier, _, _ = job(conn)
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("UPDATE research.job SET input='{" + '"text":"changed"' + "}' WHERE id=%s", (identifier,))


def test_monotonic_job_and_terminal_state(connect):
    with connect("research") as conn:
        identifier, _, _ = job(conn)
        conn.execute("UPDATE research.job SET state='running',seq=2,revision=2 WHERE id=%s", (identifier,))
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("UPDATE research.job SET seq=1 WHERE id=%s", (identifier,))
        conn.execute("UPDATE research.job SET state='failed',seq=3,revision=3 WHERE id=%s", (identifier,))
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("UPDATE research.job SET state='running' WHERE id=%s", (identifier,))


def test_immutable_artifact_and_idempotent_expiry(connect):
    with connect("research") as conn:
        identifier, context_id, owner = job(conn)
        artifact_id = uuid4()
        conn.execute("INSERT INTO research.artifact(id,job_id,context_id,owner_id,content_hash,kind,output,policy,expires_at) VALUES(%s,%s,%s,%s,%s,'novelty-result','{}','{}',clock_timestamp())", (artifact_id, identifier, context_id, owner, "b" * 64))
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("UPDATE research.artifact SET output='[]' WHERE id=%s", (artifact_id,))
        statement = "UPDATE research.artifact SET availability='expired' WHERE id=%s AND availability='ready' AND expires_at<=clock_timestamp()"
        assert conn.execute(statement, (artifact_id,)).rowcount == 1
        assert conn.execute(statement, (artifact_id,)).rowcount == 0


def test_tombstone_blocks_late_completion(connect):
    with connect("research") as conn:
        identifier, context_id, _ = job(conn)
        conn.execute("UPDATE research.job SET state='running' WHERE id=%s", (identifier,))
        conn.execute("UPDATE research.context SET lifecycle='deleted' WHERE id=%s", (context_id,))
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("UPDATE research.job SET state='succeeded' WHERE id=%s", (identifier,))


def test_other_owner_has_no_table_access(connect):
    with connect("library") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SELECT * FROM research.context")
