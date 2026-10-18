"""Real owner-role constraints for the topics/digests schema; no in-memory substitute."""

from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb


def subscribe(conn, *, account_id=None, topic_key=None):
    identifier = uuid4()
    conn.execute(
        "INSERT INTO topics.followed_topic(id,account_id,topic_key,display_name) VALUES(%s,%s,%s,'Synthetic Topic')",
        (identifier, account_id or uuid4(), topic_key or str(uuid4())),
    )
    return identifier


def add_settings(conn, topic_id, *, cadence="weekly", day="mon", window=7, revision=1):
    identifier = uuid4()
    conn.execute(
        "INSERT INTO topics.digest_settings(id,topic_id,cadence,delivery_time_local,delivery_day,content_window_days,revision) VALUES(%s,%s,%s,'09:00',%s,%s,%s)",
        (identifier, topic_id, cadence, day, window, revision),
    )
    return identifier


def prepared(conn, topic_id, *, start, end, content=None, settings_revision=1):
    identifier = uuid4()
    items = [{"paperId": str(uuid4())}] if content is None else content
    conn.execute(
        "INSERT INTO topics.digest_run(id,topic_id,window_start,window_end,state,digest_content,settings_revision) VALUES(%s,%s,%s,%s,'prepared',%s,%s)",
        (identifier, topic_id, start, end, Jsonb(items), settings_revision),
    )
    return identifier


def advance(conn, run_id, state):
    conn.execute(
        "UPDATE topics.digest_run SET state=%s,updated_at=clock_timestamp() WHERE id=%s",
        (state, run_id),
    )


def test_one_subscription_row_per_account_and_key(connect):
    """Reactivation reuses the same row; the key stays unique even when unsubscribed."""
    with connect("topics") as conn:
        account, key = uuid4(), "quantum-error-correction"
        first = subscribe(conn, account_id=account, topic_key=key)
        conn.execute("UPDATE topics.followed_topic SET status='unsubscribed' WHERE id=%s", (first,))
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            subscribe(conn, account_id=account, topic_key=key)
        conn.execute("UPDATE topics.followed_topic SET status='active' WHERE id=%s", (first,))


def test_topic_identity_and_follow_time_are_immutable(connect):
    with connect("topics") as conn:
        identifier = subscribe(conn)
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "UPDATE topics.followed_topic SET topic_key='renamed' WHERE id=%s", (identifier,)
            )
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "UPDATE topics.followed_topic SET followed_at=clock_timestamp() WHERE id=%s",
                (identifier,),
            )
        assert (
            conn.execute(
                "UPDATE topics.followed_topic SET status='unsubscribed' WHERE id=%s", (identifier,)
            ).rowcount
            == 1
        )


def test_settings_shape_and_revision_advance(connect):
    with connect("topics") as conn:
        topic_id = subscribe(conn)
        settings = add_settings(conn, topic_id)
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            add_settings(conn, topic_id)
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "UPDATE topics.digest_settings SET cadence='daily',delivery_day=NULL WHERE id=%s",
                (settings,),
            )
        conn.execute(
            "UPDATE topics.digest_settings SET cadence='daily',delivery_day=NULL,revision=2 WHERE id=%s",
            (settings,),
        )
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("UPDATE topics.digest_settings SET revision=1 WHERE id=%s", (settings,))
        other = subscribe(conn)
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO topics.digest_settings(id,topic_id,cadence,delivery_time_local,delivery_day,content_window_days) VALUES(%s,%s,'daily','09:00','mon',7)",
                (uuid4(), other),
            )
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO topics.digest_settings(id,topic_id,cadence,delivery_time_local,content_window_days) VALUES(%s,%s,'weekly','09:00',7)",
                (uuid4(), other),
            )
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO topics.digest_settings(id,topic_id,cadence,delivery_time_local,content_window_days) VALUES(%s,%s,'daily','09:00',14)",
                (uuid4(), other),
            )


def test_run_stamps_current_settings_revision_and_keeps_chronology(connect):
    with connect("topics") as conn:
        topic_id = subscribe(conn)
        add_settings(conn, topic_id)
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            prepared(conn, topic_id, start="2026-01-01", end="2026-01-07", settings_revision=2)
        first = prepared(conn, topic_id, start="2026-01-01", end="2026-01-07", content=[])
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            prepared(conn, topic_id, start="2026-01-08", end="2026-01-14")
        advance(conn, first, "empty")
        prepared(conn, topic_id, start="2026-01-08", end="2026-01-14")


def test_window_uniqueness_excludes_discarded_runs(connect):
    with connect("topics") as conn:
        topic_id = subscribe(conn)
        add_settings(conn, topic_id)
        first = prepared(conn, topic_id, start="2026-01-01", end="2026-01-07")
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            prepared(conn, topic_id, start="2026-01-01", end="2026-01-07")
        advance(conn, first, "discarded")
        prepared(conn, topic_id, start="2026-01-01", end="2026-01-07")


def test_run_state_machine_and_content_immutability(connect):
    with connect("topics") as conn:
        topic_id = subscribe(conn)
        add_settings(conn, topic_id)
        run_id = prepared(conn, topic_id, start="2026-01-01", end="2026-01-07")
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("UPDATE topics.digest_run SET digest_content='[]' WHERE id=%s", (run_id,))
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            advance(conn, run_id, "sent")
        advance(conn, run_id, "sending")
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            advance(conn, run_id, "prepared")
        advance(conn, run_id, "unknown")
        advance(conn, run_id, "sent")
        empty_topic = subscribe(conn)
        add_settings(conn, empty_topic)
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO topics.digest_run(id,topic_id,window_start,window_end,digest_content,settings_revision) VALUES(%s,%s,'2026-02-01','2026-02-07','{}',1)",
                (uuid4(), empty_topic),
            )
        filled = prepared(conn, empty_topic, start="2026-02-01", end="2026-02-07")
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            advance(conn, filled, "empty")


def test_single_flight_allows_one_sending_run_per_topic(connect):
    with connect("topics") as conn:
        topic_id = subscribe(conn)
        add_settings(conn, topic_id)
        later = prepared(conn, topic_id, start="2026-01-08", end="2026-01-14")
        earlier = prepared(conn, topic_id, start="2026-01-01", end="2026-01-07")
        advance(conn, earlier, "sending")
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            advance(conn, later, "sending")


def test_send_log_and_outcome_follow_the_run_state(connect):
    with connect("topics") as conn:
        topic_id = subscribe(conn)
        add_settings(conn, topic_id)
        run_id = prepared(conn, topic_id, start="2026-01-01", end="2026-01-07")
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO topics.send_log_entry(id,run_id,path_kind) VALUES(%s,%s,'local-sink')",
                (uuid4(), run_id),
            )
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO topics.delivery_outcome(id,run_id,observed_state) VALUES(%s,%s,'failed')",
                (uuid4(), run_id),
            )
        advance(conn, run_id, "sending")
        conn.execute(
            "INSERT INTO topics.send_log_entry(id,run_id,path_kind) VALUES(%s,%s,'local-sink')",
            (uuid4(), run_id),
        )
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            conn.execute(
                "INSERT INTO topics.send_log_entry(id,run_id,path_kind) VALUES(%s,%s,'local-sink')",
                (uuid4(), run_id),
            )
        advance(conn, run_id, "failed")
        outcome = uuid4()
        conn.execute(
            "INSERT INTO topics.delivery_outcome(id,run_id,observed_state,failure_reason) VALUES(%s,%s,'failed','transport-error')",
            (outcome, run_id),
        )
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "UPDATE topics.delivery_outcome SET observed_state='sent' WHERE id=%s", (outcome,)
            )


def test_watermark_requires_a_sent_run_of_the_same_topic(connect):
    with connect("topics") as conn:
        topic_id = subscribe(conn)
        add_settings(conn, topic_id)
        run_id = prepared(conn, topic_id, start="2026-01-01", end="2026-01-07")
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO topics.topic_delivery_watermark(id,topic_id,content_id,included_in_run_id) VALUES(%s,%s,'c1',%s)",
                (uuid4(), topic_id, run_id),
            )
        advance(conn, run_id, "sending")
        advance(conn, run_id, "sent")
        conn.execute(
            "INSERT INTO topics.topic_delivery_watermark(id,topic_id,content_id,included_in_run_id) VALUES(%s,%s,'c1',%s)",
            (uuid4(), topic_id, run_id),
        )
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            conn.execute(
                "INSERT INTO topics.topic_delivery_watermark(id,topic_id,content_id,included_in_run_id) VALUES(%s,%s,'c1',%s)",
                (uuid4(), topic_id, run_id),
            )
        other = subscribe(conn)
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO topics.topic_delivery_watermark(id,topic_id,content_id,included_in_run_id) VALUES(%s,%s,'c2',%s)",
                (uuid4(), other, run_id),
            )


def test_owner_isolation_and_no_delete(connect):
    with connect("topics") as conn:
        identifier = subscribe(conn)
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("DELETE FROM topics.followed_topic WHERE id=%s", (identifier,))
    with connect("library") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SELECT * FROM topics.followed_topic")
