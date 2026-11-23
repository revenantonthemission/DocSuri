"""Owner grants and additive preparation evidence on the real store."""

import datetime as dt
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_schema import add_settings, advance, prepared, subscribe


def test_timezone_rejects_unknown_database_zone(connect):
    with connect("personalization") as conn:
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO personalization.settings(account_id,revision,defaults) VALUES(%s,%s,%s)",
                (uuid4(), uuid4(), Jsonb({"timeZone": "Mars/Olympus"})),
            )


def test_timezone_confirmation_has_database_effective_boundary(connect):
    with connect("personalization") as conn:
        owner = uuid4()
        row = conn.execute(
            "INSERT INTO personalization.settings(account_id,revision,defaults) VALUES(%s,%s,%s) RETURNING defaults",
            (owner, uuid4(), Jsonb({"timeZone": "Asia/Seoul"})),
        ).fetchone()
        assert row["defaults"]["timeZoneEffectiveAt"]
        after = conn.execute(
            "UPDATE personalization.settings SET appearance='dark' WHERE account_id=%s RETURNING defaults",
            (owner,),
        ).fetchone()
        assert after == row


def test_topics_can_read_only_narrow_preferences(connect):
    with connect("topics") as conn:
        row = conn.execute(
            "SELECT personalization.digest_preferences(%s) AS p", (uuid4(),)
        ).fetchone()
        assert row["p"]["languageId"] == "en"
        assert row["p"]["timeZone"] is None
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SELECT * FROM personalization.settings")


def test_other_owner_role_cannot_read_background_preferences(connect):
    with connect("library") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SELECT personalization.digest_preferences(%s)", (uuid4(),))


def test_run_snapshot_and_request_identity_are_immutable(connect):
    with connect("topics") as conn:
        topic = subscribe(conn)
        add_settings(conn, topic)
        run = prepared(conn, topic, start="2026-01-01", end="2026-01-07")
        for column, value in (
            ("preference_snapshot", "'{}'::jsonb"),
            ("presentation", "'{}'::jsonb"),
            ("request_key", "gen_random_uuid()"),
        ):
            with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
                conn.execute(f"UPDATE topics.digest_run SET {column}={value} WHERE id=%s", (run,))


def test_unconfigured_owner_has_no_invented_schedule(connect):
    with connect("topics") as conn:
        topic = subscribe(conn)
        add_settings(conn, topic)
        assert (
            conn.execute(
                "SELECT * FROM topics.next_occurrence(%s,clock_timestamp())", (topic,)
            ).fetchall()
            == []
        )


def test_a_runs_scheduled_instant_is_set_once_and_never_changes(connect):
    """Build and Test loop-back 4 (L4-2): the instant is a fact of the insert. The
    database refuses every later change, from none to a value included, and the
    replaced guard keeps the fixed search path and the grants of the one it replaced."""
    instant = dt.datetime(2026, 1, 7, 9, 30, tzinfo=dt.UTC)
    other = dt.datetime(2026, 1, 8, 9, 30, tzinfo=dt.UTC)

    def stored(conn, run):
        return conn.execute(
            "SELECT state,scheduled_at FROM topics.digest_run WHERE id=%s", (run,)
        ).fetchone()

    with connect("topics") as conn:
        scheduled_topic, direct_topic = subscribe(conn), subscribe(conn)
        add_settings(conn, scheduled_topic)
        add_settings(conn, direct_topic)
        # The scheduled run names its instant in the insert, as the repository does;
        # `prepared` names none, the path of every run no schedule prepared.
        scheduled = uuid4()
        conn.execute(
            "INSERT INTO topics.digest_run(id,topic_id,window_start,window_end,state,"
            "digest_content,settings_revision,scheduled_at) "
            "VALUES(%s,%s,'2026-01-01','2026-01-07','prepared',%s,1,%s)",
            (scheduled, scheduled_topic, Jsonb([{"paperId": str(uuid4())}]), instant),
        )
        direct = prepared(conn, direct_topic, start="2026-01-01", end="2026-01-07")
        assert stored(conn, scheduled) == {"state": "prepared", "scheduled_at": instant}
        assert stored(conn, direct) == {"state": "prepared", "scheduled_at": None}
        for run, value in ((scheduled, other), (scheduled, None), (direct, instant)):
            with pytest.raises(psycopg.errors.CheckViolation) as refusal, conn.transaction():
                conn.execute(
                    "UPDATE topics.digest_run SET scheduled_at=%s WHERE id=%s", (value, run)
                )
            assert "preparation snapshot is immutable" in str(refusal.value)
        advance(conn, scheduled, "sending")
        advance(conn, direct, "sending")
        assert stored(conn, scheduled) == {"state": "sending", "scheduled_at": instant}
        assert stored(conn, direct) == {"state": "sending", "scheduled_at": None}
        guard = conn.execute(
            "SELECT pg_get_userbyid(p.proowner) AS owner,p.prosecdef AS definer,"
            "p.proconfig AS settings,"
            "(SELECT array_agg(pg_get_userbyid(a.grantee) || ':' || a.privilege_type) "
            "FROM aclexplode(p.proacl) a) AS grants "
            "FROM pg_proc p WHERE p.oid='topics.guard_preparation_snapshot()'::regprocedure"
        ).fetchone()
    assert dict(guard, grants=sorted(guard["grants"])) == {
        "owner": "docsuri_topics_owner",
        "definer": False,
        "settings": ["search_path=pg_catalog"],
        "grants": ["docsuri_topics:EXECUTE", "docsuri_topics_owner:EXECUTE"],
    }
