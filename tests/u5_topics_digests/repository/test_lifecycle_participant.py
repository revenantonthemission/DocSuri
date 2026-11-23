"""Step 29: the TopicsDigests lifecycle participant's three remaining dispositions (FR1.6).

`repository/test_lifecycle_isolation.py` checks that withdraw and erase reach only the
owner's topics rows; these tests pin what each action does to them, on the realm's own
stores and through the shared coordinator contract under the topics login:

- a reactivation changes no topics row and still records its disposition;
- a withdrawal unsubscribes the account's active topics and discards only its
  `prepared` runs, while a `sending` run is left to finish its single attempt (BR4.1);
- the `pending_work` scope of an erasure discards the account's prepared runs and
  leaves its topics' status unchanged (BR4.3).

Every test acts for one synthetic account of its own, reused across the three tests and
across reruns on the same realm, so the realm's finite account allocation is spent once.
"""

import datetime as dt
from uuid import uuid4

from psycopg.types.json import Jsonb

from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.topics.control_lifecycle import TopicsDigestsLifecycleParticipant
from backend.modules.topics.repository import TopicsRepository
from tests.u5_topics_digests.conftest import _make_authority

W1 = (dt.date(2026, 4, 6), dt.date(2026, 4, 12))
ITEM = {
    "versionId": "v-participant-1",
    "paperId": "p-participant-1",
    "title": "Participant Paper",
    "publishedOn": "2026-04-07",
}


def unique(base):
    return f"{base}-{uuid4().hex[:10]}"


def participant_owner(connect, realm):
    return _make_authority(connect, realm, suffix="lifecycle-participant")


def queue_run(repository, connect, topic_id):
    with connect("topics") as conn:
        revision = conn.execute(
            "SELECT revision FROM topics.digest_settings WHERE topic_id=%s", (topic_id,)
        ).fetchone()["revision"]
    run, adopted = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    assert adopted is False and run["state"] == "prepared"
    return run["id"]


def issue_ticket(connect, account_id, action, scope):
    """A live, current-generation TopicsDigests ticket, written by AccountAccess's login."""
    request, revision = uuid4(), uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s", (revision, account_id)
        )
        conn.execute(
            "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,"
            "manifest_revision,manifest,disposition,reason_key) "
            "VALUES(%s,%s,%s,%s,%s,'participant-test',%s,'pending','pending')",
            (
                request,
                account_id,
                revision,
                action,
                Jsonb(SYNTHETIC_POLICY.reference),
                Jsonb([["TopicsDigests", scope]]),
            ),
        )
        conn.execute(
            "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope,generation,"
            "lease_until,attempts) VALUES(%s,'TopicsDigests',%s,1,"
            "clock_timestamp()+interval '15 seconds',1)",
            (request, scope),
        )
    return dict(
        request_id=request,
        account_id=account_id,
        lifecycle_revision=revision,
        participant="TopicsDigests",
        scope=scope,
        generation=1,
        action=action,
        policy_ref=SYNTHETIC_POLICY.reference,
        manifest_revision="participant-test",
    )


def recorded_evidence(connect, ticket):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT evidence_ref FROM topics.lifecycle_evidence WHERE request_id=%s AND scope=%s",
            (ticket["request_id"], ticket["scope"]),
        ).fetchone()


def account_topics_rows(connect, account_id):
    """Every topics row the account owns, in full, read through the topics login."""
    with connect("topics") as conn:
        topics = conn.execute(
            "SELECT * FROM topics.followed_topic WHERE account_id=%s ORDER BY id", (account_id,)
        ).fetchall()
        ids = [row["id"] for row in topics]
        settings = conn.execute(
            "SELECT * FROM topics.digest_settings WHERE topic_id = ANY(%s) ORDER BY id", (ids,)
        ).fetchall()
        runs = conn.execute(
            "SELECT * FROM topics.digest_run WHERE topic_id = ANY(%s) ORDER BY id", (ids,)
        ).fetchall()
        run_ids = [row["id"] for row in runs]
        sends = conn.execute(
            "SELECT * FROM topics.send_log_entry WHERE run_id = ANY(%s) ORDER BY id", (run_ids,)
        ).fetchall()
        outcomes = conn.execute(
            "SELECT * FROM topics.delivery_outcome WHERE run_id = ANY(%s) ORDER BY id", (run_ids,)
        ).fetchall()
    return {
        "followed_topic": topics,
        "digest_settings": settings,
        "digest_run": runs,
        "send_log_entry": sends,
        "delivery_outcome": outcomes,
    }


def topic_statuses(connect, topic_ids):
    with connect("topics") as conn:
        rows = conn.execute(
            "SELECT id,status FROM topics.followed_topic WHERE id = ANY(%s)", (topic_ids,)
        ).fetchall()
    return {row["id"]: row["status"] for row in rows}


def run_states(connect, run_ids):
    with connect("topics") as conn:
        rows = conn.execute(
            "SELECT id,state FROM topics.digest_run WHERE id = ANY(%s)", (run_ids,)
        ).fetchall()
    return {row["id"]: row["state"] for row in rows}


def test_reactivation_changes_no_topics_row_and_records_its_disposition(
    transactions, connect, realm
):
    owner = participant_owner(connect, realm)
    repository = TopicsRepository(transactions)
    participant = TopicsDigestsLifecycleParticipant(transactions)
    active = repository.follow(owner, unique("participant-active"), "Active")["topic"]["id"]
    stopped = repository.follow(owner, unique("participant-stopped"), "Stopped")["topic"]["id"]
    queued = queue_run(repository, connect, active)
    repository.unsubscribe(owner, stopped)
    before = account_topics_rows(connect, owner.account_id)
    assert before["followed_topic"] and before["digest_run"]

    ticket = issue_ticket(connect, owner.account_id, "reactivate", "live_records")
    result = participant.apply(ticket)

    assert result["disposition"] == "complete" and result["evidenceRef"]
    assert account_topics_rows(connect, owner.account_id) == before
    assert topic_statuses(connect, [active, stopped]) == {active: "active", stopped: "unsubscribed"}
    assert run_states(connect, [queued]) == {queued: "prepared"}
    evidence = recorded_evidence(connect, ticket)
    assert evidence is not None and str(evidence["evidence_ref"]) == result["evidenceRef"]
    # Leave no queued run behind for another suite's scheduler pass.
    repository.unsubscribe(owner, active)


def test_withdrawal_unsubscribes_and_discards_prepared_runs_while_a_sending_run_finishes(
    transactions, connect, realm, authority_b
):
    owner = participant_owner(connect, realm)
    repository = TopicsRepository(transactions)
    participant = TopicsDigestsLifecycleParticipant(transactions)
    waiting_topic = repository.follow(owner, unique("participant-waiting"), "Waiting")["topic"]["id"]
    flight_topic = repository.follow(owner, unique("participant-flight"), "Flight")["topic"]["id"]
    bystander = repository.follow(authority_b, unique("participant-bystander"), "Bystander")[
        "topic"
    ]["id"]
    waiting = queue_run(repository, connect, waiting_topic)
    in_flight = queue_run(repository, connect, flight_topic)
    untouched = queue_run(repository, connect, bystander)
    assert repository.begin_send(in_flight, "local-sink") is not None

    ticket = issue_ticket(connect, owner.account_id, "withdraw", "live_records")
    result = participant.apply(ticket)

    assert result["disposition"] == "complete" and result["evidenceRef"]
    assert topic_statuses(connect, [waiting_topic, flight_topic, bystander]) == {
        waiting_topic: "unsubscribed",
        flight_topic: "unsubscribed",
        bystander: "active",
    }
    assert run_states(connect, [waiting, in_flight, untouched]) == {
        waiting: "discarded",
        in_flight: "sending",
        untouched: "prepared",
    }
    # The in-flight attempt finishes once and records its outcome normally (BR4.1).
    finished = repository.finish_send(in_flight, "sent", transport_receipt="sink-participant")
    assert finished is not None and finished["state"] == "sent"
    assert repository.finish_send(in_flight, "sent") is None
    with connect("topics") as conn:
        outcome = conn.execute(
            "SELECT observed_state FROM topics.delivery_outcome WHERE run_id=%s", (in_flight,)
        ).fetchall()
    assert [row["observed_state"] for row in outcome] == ["sent"]
    # The discarded run can no longer start a send.
    assert repository.begin_send(waiting, "local-sink") is None
    evidence = recorded_evidence(connect, ticket)
    assert evidence is not None and str(evidence["evidence_ref"]) == result["evidenceRef"]
    # Leave no queued run behind for another suite's scheduler pass.
    repository.unsubscribe(authority_b, bystander)


def test_erasure_pending_work_discards_prepared_runs_and_keeps_topic_status(
    transactions, connect, realm
):
    owner = participant_owner(connect, realm)
    repository = TopicsRepository(transactions)
    participant = TopicsDigestsLifecycleParticipant(transactions)
    first = repository.follow(owner, unique("participant-pending-a"), "Pending A")["topic"]["id"]
    second = repository.follow(owner, unique("participant-pending-b"), "Pending B")["topic"]["id"]
    flight_topic = repository.follow(owner, unique("participant-pending-c"), "Pending C")[
        "topic"
    ]["id"]
    queued = [queue_run(repository, connect, topic) for topic in (first, second)]
    in_flight = queue_run(repository, connect, flight_topic)
    assert repository.begin_send(in_flight, "local-sink") is not None
    topics = [first, second, flight_topic]

    ticket = issue_ticket(connect, owner.account_id, "erase", "pending_work")
    result = participant.apply(ticket)

    assert result["disposition"] == "complete" and result["evidenceRef"]
    assert run_states(connect, [*queued, in_flight]) == {
        queued[0]: "discarded",
        queued[1]: "discarded",
        in_flight: "sending",
    }
    # The pending_work scope removes no topic and changes no topic's status.
    assert topic_statuses(connect, topics) == dict.fromkeys(topics, "active")
    evidence = recorded_evidence(connect, ticket)
    assert evidence is not None and str(evidence["evidence_ref"]) == result["evidenceRef"]
    # Leave no in-flight attempt or active topic behind for a later scheduler pass.
    assert repository.finish_send(in_flight, "sent", transport_receipt="sink-pending") is not None
    for topic in topics:
        repository.unsubscribe(owner, topic)
