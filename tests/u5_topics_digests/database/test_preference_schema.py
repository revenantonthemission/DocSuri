"""Owner grants and additive preparation evidence on the real store."""

from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_schema import add_settings, prepared, subscribe


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
