"""Repository behavior over the real realm: owner isolation, checked transitions,
atomic settings saves, window ordering and watermark exclusion.

Every follow key is unique per execution: the synthetic realm persists between
phase runs, so tests re-run cleanly against accumulated state."""

import datetime as dt
from uuid import uuid4

import pytest

from backend.modules.topics.errors import TopicsError
from backend.modules.topics.repository import TopicsRepository

W1 = (dt.date(2026, 1, 1), dt.date(2026, 1, 7))
W2 = (dt.date(2026, 1, 8), dt.date(2026, 1, 14))
ITEM = {"versionId": "v-1", "paperId": "p-1", "title": "Synthetic", "publishedOn": "2026-01-03"}


def unique(base):
    return f"{base}-{uuid4().hex[:10]}"


def repo(transactions):
    return TopicsRepository(transactions)


def settings_of(connect, topic_id):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT cadence,delivery_time_local,delivery_day,content_window_days,"
            "revision AS settings_revision FROM topics.digest_settings WHERE topic_id=%s",
            (topic_id,),
        ).fetchone()


def make_run(repo_, connect, topic_id, window, *, items=(ITEM,)):
    row = settings_of(connect, topic_id)
    run, adopted = repo_.prepare_run(
        topic_id, window[0], window[1], row["settings_revision"], list(items)
    )
    assert adopted is False
    return run


def set_consent(connect, account_id, granted):
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=%s WHERE account_id=%s AND purpose='local-research'",
            (granted, account_id),
        )


def seed_corpus(connect, rows):
    with connect("corpus") as conn:
        for version_id, paper_id, published, eligible, withdrawn in rows:
            conn.execute(
                "INSERT INTO corpus.paper(id,title,authors,metadata,published_on,withdrawn) "
                "VALUES(%s,'Synthetic Paper','[]','{}',%s,%s) ON CONFLICT (id) DO UPDATE "
                "SET published_on=excluded.published_on,withdrawn=excluded.withdrawn",
                (paper_id, published, withdrawn),
            )
            conn.execute(
                "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
                "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,'local://x',"
                "repeat('a',64),'v1','synthetic',%s,'local-research','{}','{}') "
                "ON CONFLICT (id) DO UPDATE SET eligible=excluded.eligible",
                (version_id, paper_id, eligible),
            )


def test_follow_duplicate_and_reactivation(transactions, authority, connect):
    repo_ = repo(transactions)
    key = unique("quantum-error-correction")
    first = repo_.follow(authority, key, "Quantum Error Correction")
    assert first["reactivated"] is False and first["topic"]["status"] == "active"
    with pytest.raises(TopicsError) as duplicate:
        repo_.follow(authority, key, "Quantum Error Correction")
    assert duplicate.value.code == "DUPLICATE"
    topic_id = first["topic"]["id"]
    settings = settings_of(connect, topic_id)
    assert settings["cadence"] == "daily" and settings["content_window_days"] == 7
    repo_.unsubscribe(authority, topic_id)
    again = repo_.follow(authority, key, "Quantum Error Correction")
    assert again["reactivated"] is True and again["topic"]["id"] == topic_id
    reset = settings_of(connect, topic_id)
    assert reset["cadence"] == "daily" and reset["delivery_day"] is None
    assert reset["settings_revision"] == settings["settings_revision"] + 1


def test_cross_owner_denial(transactions, authority, authority_b, connect):
    repo_ = repo(transactions)
    mine = repo_.follow(authority, unique("topic-owner-a"), "Owned By A")["topic"]["id"]
    theirs = repo_.follow(authority_b, unique("topic-owner-b"), "Owned By B")["topic"]["id"]
    run = make_run(repo_, connect, mine, W1)
    with pytest.raises(TopicsError) as denial:
        repo_.read_topic(authority_b, mine)
    assert denial.value.code == "NOT_FOUND"
    for call in (
        lambda: repo_.read_run(authority_b, mine, run["id"]),
        lambda: repo_.save_settings(
            authority_b, mine, 1, "daily", dt.time(8, 0), None, 7
        ),
        lambda: repo_.unsubscribe(authority_b, mine),
        lambda: repo_.resolve_run(authority_b, mine, run["id"], "sent"),
    ):
        with pytest.raises(TopicsError) as refused:
            call()
        assert refused.value.code == "NOT_FOUND"
    listed = repo_.list_topics(authority_b, 50)
    assert mine not in [row["id"] for row in listed]
    assert theirs in [row["id"] for row in listed]


def test_settings_revision_conflict_and_discard(transactions, authority, connect):
    repo_ = repo(transactions)
    topic_id = repo_.follow(authority, unique("settings-topic"), "Settings Topic")["topic"]["id"]
    make_run(repo_, connect, topic_id, W1)
    revision = settings_of(connect, topic_id)["settings_revision"]
    with pytest.raises(TopicsError) as stale:
        repo_.save_settings(
            authority, topic_id, revision + 5, "daily", dt.time(9, 0), None, 7
        )
    assert stale.value.code == "CONFLICT" and stale.value.current["revision"] == revision
    unchanged = repo_.save_settings(
        authority, topic_id, revision, "daily", dt.time(8, 0), None, 7
    )
    assert unchanged["unchanged"] is True
    saved = repo_.save_settings(
        authority, topic_id, revision, "weekly", dt.time(9, 30), "mon", 30
    )
    assert saved["unchanged"] is False and len(saved["discarded"]) == 1
    assert settings_of(connect, topic_id)["settings_revision"] == revision + 1
    runs = repo_.read_topic(authority, topic_id)["runs"]
    assert [run["state"] for run in runs] == ["discarded"]


def test_window_order_and_adoption(transactions, authority, connect):
    repo_ = repo(transactions)
    topic_id = repo_.follow(authority, unique("window-topic"), "Window Topic")["topic"]["id"]
    row = settings_of(connect, topic_id)
    first, adopted = repo_.prepare_run(
        topic_id, W1[0], W1[1], row["settings_revision"], [ITEM]
    )
    assert adopted is False
    again, adopted_again = repo_.prepare_run(
        topic_id, W1[0], W1[1], row["settings_revision"], [ITEM]
    )
    assert adopted_again is True and again["id"] == first["id"]
    with pytest.raises(TopicsError) as ordered:
        repo_.prepare_run(topic_id, W2[0], W2[1], row["settings_revision"], [ITEM])
    assert ordered.value.code == "WINDOW_ORDER"
    repo_.save_settings(
        authority, topic_id, row["settings_revision"], "daily", dt.time(8, 5), None, 7
    )
    later, _ = repo_.prepare_run(topic_id, W2[0], W2[1], row["settings_revision"] + 1, [ITEM])
    assert later["window_start"] == W2[0]


def test_begin_send_guards(transactions, authority, connect):
    repo_ = repo(transactions)
    topic_id = repo_.follow(authority, unique("send-guard-topic"), "Send Guard Topic")["topic"]["id"]
    account_id = authority.account_id
    later = make_run(repo_, connect, topic_id, W2)
    earlier = make_run(repo_, connect, topic_id, W1)
    set_consent(connect, account_id, False)
    assert repo_.begin_send(earlier["id"], "local-sink") is None
    set_consent(connect, account_id, True)
    sending = repo_.begin_send(earlier["id"], "local-sink")
    assert sending is not None and sending["state"] == "sending" and sending["send_log_id"]
    assert repo_.begin_send(later["id"], "local-sink") is None
    stopped = repo_.unsubscribe(authority, topic_id)
    assert stopped["unchanged"] is False and len(stopped["discarded"]) == 1
    assert later["id"] in stopped["discarded"]
    finished = repo_.finish_send(earlier["id"], "sent", transport_receipt="sink-1")
    assert finished is not None and finished["state"] == "sent"
    outcome = repo_.read_run(authority, topic_id, earlier["id"])
    assert outcome["observed_state"] == "sent" and outcome["path_kind"] == "local-sink"
    assert repo_.finish_send(earlier["id"], "failed") is None
    assert repo_.discard_prepared_runs(topic_id) == []


def test_unknown_pause_and_reconcile(transactions, authority, connect):
    repo_ = repo(transactions)
    topic_id = repo_.follow(authority, unique("pause-topic"), "Pause Topic")["topic"]["id"]
    later = make_run(repo_, connect, topic_id, W2)
    earlier = make_run(repo_, connect, topic_id, W1)
    assert repo_.begin_send(earlier["id"], "local-sink") is not None
    unknown = repo_.finish_send(earlier["id"], "unknown")
    assert unknown["state"] == "unknown"
    assert repo_.begin_send(later["id"], "local-sink") is None
    assert repo_.reconcile_run(earlier["id"], "sent")["state"] == "sent"
    resumed = repo_.begin_send(later["id"], "local-sink")
    assert resumed is not None
    failed = repo_.finish_send(later["id"], "failed", failure_reason="transport-error")
    assert failed["state"] == "failed"
    outcome = repo_.read_run(authority, topic_id, later["id"])
    assert outcome["observed_state"] == "failed" and outcome["failure_reason"] == "transport-error"


def test_send_watermark_exclusion(transactions, authority, connect):
    repo_ = repo(transactions)
    seed_corpus(
        connect,
        [
            ("v-sent-a", "p-a", dt.date(2026, 1, 3), True, False),
            ("v-sent-b", "p-b", dt.date(2026, 1, 5), True, False),
            ("v-ineligible", "p-c", dt.date(2026, 1, 4), False, False),
            ("v-late", "p-d", dt.date(2026, 1, 10), True, False),
        ],
    )
    topic_id = repo_.follow(authority, unique("watermark-topic"), "Watermark Topic")["topic"]["id"]

    def select(start, end):
        return [
            item["versionId"]
            for item in repo_.select_window_content(
                topic_id, start, end, selection_limit=50, content_limit=10
            )
        ]

    # Other suites seed their own corpus into the same realm: assert on this
    # suite's versions by membership, never on the window's exact contents.
    first = select(W1[0], W1[1])
    assert "v-sent-a" in first and "v-sent-b" in first
    assert first.index("v-sent-a") < first.index("v-sent-b")
    assert "v-ineligible" not in first
    run = make_run(repo_, connect, topic_id, W1, items=[
        item
        for item in repo_.select_window_content(
            topic_id, W1[0], W1[1], selection_limit=50, content_limit=10
        )
        if item["versionId"] in ("v-sent-a", "v-sent-b")
    ])
    assert repo_.begin_send(run["id"], "local-sink") is not None
    assert repo_.finish_send(run["id"], "sent", transport_receipt="sink-2") is not None
    repeat = select(W1[0], W1[1])
    assert "v-sent-a" not in repeat and "v-sent-b" not in repeat
    later = select(W2[0], W2[1])
    assert "v-late" in later
    seed_corpus(connect, [("v-fresh", "p-e", dt.date(2026, 1, 2), True, False)])
    widened = select(dt.date(2025, 12, 1), dt.date(2026, 1, 7))
    assert "v-fresh" in widened
    assert "v-sent-a" not in widened and "v-sent-b" not in widened
    with connect("corpus") as conn:
        conn.execute("UPDATE corpus.paper SET withdrawn=true WHERE id='p-e'")
    shrunk = select(dt.date(2025, 12, 1), dt.date(2026, 1, 7))
    assert "v-fresh" not in shrunk


def test_owner_resolve_action(transactions, authority, connect):
    repo_ = repo(transactions)
    topic_id = repo_.follow(authority, unique("resolve-topic"), "Resolve Topic")["topic"]["id"]
    run = make_run(repo_, connect, topic_id, W1)
    assert repo_.begin_send(run["id"], "local-sink") is not None
    repo_.finish_send(run["id"], "unknown")
    with pytest.raises(TopicsError) as bad:
        repo_.resolve_run(authority, topic_id, run["id"], "maybe")
    assert bad.value.code == "INVALID_ARGUMENT"
    resolved = repo_.resolve_run(authority, topic_id, run["id"], "sent")
    assert resolved["state"] == "sent"
    view = repo_.read_run(authority, topic_id, run["id"])
    assert view["reconciled_state"] == "sent" and view["reconciled_at"] is not None
    with pytest.raises(TopicsError) as closed:
        repo_.resolve_run(authority, topic_id, run["id"], "failed")
    assert closed.value.code == "INVALID_STATE"
    not_delivered = make_run(repo_, connect, topic_id, W2)
    assert repo_.begin_send(not_delivered["id"], "local-sink") is not None
    repo_.finish_send(not_delivered["id"], "unknown")
    resolved_failed = repo_.resolve_run(authority, topic_id, not_delivered["id"], "failed")
    assert resolved_failed["state"] == "failed"
    assert repo_.reconcile_run(not_delivered["id"], "failed") is None


def test_orphan_sweep_records_evidence_gap(transactions, authority, connect):
    repo_ = repo(transactions)
    topic_id = repo_.follow(authority, unique("orphan-topic"), "Orphan Topic")["topic"]["id"]
    run = make_run(repo_, connect, topic_id, W1)
    with connect("topics") as conn:
        conn.execute(
            "UPDATE topics.digest_run SET state='sending',updated_at=clock_timestamp() WHERE id=%s",
            (run["id"],),
        )
    assert run["id"] not in [
        row["id"] for row in repo_.orphaned_sending(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1), 10)
    ]
    found = repo_.orphaned_sending(dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=5), 10)
    assert run["id"] in [row["id"] for row in found]
    retired = repo_.retire_orphan(run["id"])
    assert retired["state"] == "unknown"
    view = repo_.read_run(authority, topic_id, run["id"])
    assert view["observed_state"] == "unknown"
    assert view["path_kind"] is None and view["transport_receipt"] is None
    assert repo_.retire_orphan(run["id"]) is None
    assert run["id"] not in [
        row["id"] for row in repo_.orphaned_sending(dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=5), 10)
    ]
