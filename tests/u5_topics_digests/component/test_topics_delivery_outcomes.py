"""Digest delivery outcomes over the real realm (`backend/modules/topics/delivery.py`
with the service's owner actions on an outcome): empty, sent, refused and unknown
outcomes, refusal detail, the unknown pause and evidence reconciliation, the owner's
resolution and its watermark, an unsubscribe against a queued and an in-flight run, and
a reactivation that never repeats delivery.

Moved unchanged from `test_topics_logic.py` (plan Step 35, decision L3-1); the shared
helpers are in `topics_flow.py`. An autouse fixture quiets the persistent realm first:
earlier runs of this suite leave active topics and queued runs behind, so every test
starts with only the topic it creates in the due page."""

import datetime as dt

import pytest
from backend.modules.accounts.integrations.digest_email import DigestMailResult
from backend.modules.topics.delivery import DigestDelivery
from backend.modules.topics.errors import TopicsError
from backend.modules.topics.repository import TopicsRepository

from tests.u5_topics_digests.topics_flow import (
    ITEM,
    W1,
    W2,
    W3,
    DetailedRefusalMail,
    RefusingMail,
    UnobservedMail,
    build,
    follow_topic,
    quiet_realm_rows,
    revision_of,
    run_row,
    seed_corpus,
    watermark_count,
    watermark_ids,
)


@pytest.fixture(autouse=True)
def quiet_realm(connect):
    quiet_realm_rows(connect)


def test_empty_window_is_recorded_not_failed(transactions, authority, connect):
    """BR2.3: an empty selection is a recorded empty digest, never a failure."""
    service, _, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="empty-topic")
    revision = revision_of(connect, topic_id)
    run, adopted = repository.prepare_run(topic_id, W1[0], W1[1], revision, [])
    assert adopted is False
    row = run_row(connect, run["id"])
    assert row["state"] == "empty"
    assert row["observed_state"] == "empty"
    assert row["failure_reason"] is None


def test_send_outcomes_sent_failed_unknown(transactions, authority, connect):
    service, scheduler, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="outcome-topic")
    revision = revision_of(connect, topic_id)
    run, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    # A refusing path records failed with a plain reason; it is never re-sent (BR3.3).
    delivery = DigestDelivery(transactions, None, mail=RefusingMail())
    sending = repository.begin_send(run["id"], delivery.path_kind())
    terminal = delivery.attempt(sending, {"account_id": authority.account_id, "display_name": "T"})
    assert terminal["state"] == "failed"
    assert run_row(connect, run["id"])["failure_reason"] == "delivery-path-refused"
    # An interrupted transport is unobserved: the run pauses as unknown (BR3.2).
    run2, _ = repository.prepare_run(topic_id, W2[0], W2[1], revision, [ITEM])
    delivery2 = DigestDelivery(transactions, None, mail=UnobservedMail())
    sending2 = repository.begin_send(run2["id"], delivery2.path_kind())
    terminal2 = delivery2.attempt(
        sending2, {"account_id": authority.account_id, "display_name": "T"}
    )
    assert terminal2["state"] == "unknown"
    assert run_row(connect, run2["id"])["observed_state"] == "unknown"


@pytest.mark.parametrize(
    "result,expected",
    [
        (
            DigestMailResult(
                "refused",
                refusal_reason="delivery-path-refused",
                provider_status=403,
                provider_error="validation_error",
            ),
            ("delivery-path-refused", 403, "validation_error"),
        ),
        (
            DigestMailResult("refused", refusal_reason="recipient-not-permitted"),
            ("recipient-not-permitted", None, None),
        ),
        (
            DigestMailResult("refused", refusal_reason="unsubscribe-url-invalid"),
            ("unsubscribe-url-invalid", None, None),
        ),
    ],
)
def test_refusal_detail_reaches_the_recorded_outcome(
    transactions, authority, connect, result, expected
):
    """A refusal fails once (BR3.3) and records who refused, without provider text."""
    service, _, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="refusal-detail-topic")
    run, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision_of(connect, topic_id), [ITEM])
    delivery = DigestDelivery(transactions, None, mail=DetailedRefusalMail(result))
    sending = repository.begin_send(run["id"], delivery.path_kind())
    terminal = delivery.attempt(sending, {"account_id": authority.account_id, "display_name": "T"})
    assert terminal["state"] == "failed"
    with connect("topics") as conn:
        recorded = conn.execute(
            "SELECT failure_reason,provider_status,provider_error "
            "FROM topics.delivery_outcome WHERE run_id=%s",
            (run["id"],),
        ).fetchone()
    assert (
        recorded["failure_reason"],
        recorded["provider_status"],
        recorded["provider_error"],
    ) == expected


def test_unknown_pause_and_evidence_reconciliation(transactions, authority, connect):
    service, scheduler, delivery = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="pause-topic")
    revision = revision_of(connect, topic_id)
    # The later window is prepared first: the pause scenario needs two live
    # windows on one topic (the chronology gate otherwise refuses the insert).
    later, _ = repository.prepare_run(topic_id, W2[0], W2[1], revision, [ITEM])
    earlier, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    assert repository.begin_send(earlier["id"], "local-sink") is not None
    # The transport accepted, its facts landed in the send log, and only then
    # was the outcome lost: the run pauses as unknown WITH evidence (BR3.2).
    repository.record_transport_facts(earlier["id"], acknowledged_at=dt.datetime.now(dt.UTC))
    repository.finish_send(earlier["id"], "unknown")
    # The unreconciled unknown blocks the topic's next send (BR3.2).
    assert repository.begin_send(later["id"], "local-sink") is None
    # The scheduled check reconciles from the send log: the local sink
    # acknowledged, so the outcome resolves as delivered and the watermark
    # applies exactly as a direct send would.
    row = next(r for r in repository.unknown_runs(10) if r["id"] == earlier["id"])
    assert delivery.reconcile_decision(row) == "sent"
    assert scheduler.run_once(limit=1)["reconciled"] >= 1
    view = service.read_run(authority, topic_id, earlier["id"])
    assert view["state"] == "sent" and view["outcome"]["reconciledState"] == "sent"
    assert watermark_count(connect, topic_id) == 1
    # The same pass's send stage carried the unblocked queued run: the pause
    # lifted the moment the unknown reconciled.
    assert service.read_run(authority, topic_id, later["id"])["state"] == "sent"
    # No receipt and no acknowledgment never reconciles by silence (BR3.2):
    # the owner's explicit resolve is the only remaining path.
    run3, _ = repository.prepare_run(topic_id, W3[0], W3[1], revision, [ITEM])
    sending3 = repository.begin_send(run3["id"], "local-sink")
    assert sending3 is not None
    DigestDelivery(transactions, None, mail=UnobservedMail()).attempt(
        sending3, {"account_id": authority.account_id, "display_name": "T"}
    )
    row = next(r for r in repository.unknown_runs(10) if r["id"] == run3["id"])
    assert delivery.reconcile_decision(row) is None
    assert service.read_run(authority, topic_id, run3["id"])["state"] == "unknown"


def test_owner_resolve_watermark_and_redelivery_bound(transactions, authority, connect):
    service, _, _ = build(transactions)
    repository = TopicsRepository(transactions)
    seed_corpus(
        connect,
        [("v-c1", "p-c1", dt.date(2026, 1, 3), True), ("v-c2", "p-c2", dt.date(2026, 1, 4), True)],
    )
    _, topic_id = follow_topic(service, authority, base="resolve-topic")
    revision = revision_of(connect, topic_id)
    c1 = {"versionId": "v-c1", "paperId": "p-c1", "title": "C1", "publishedOn": "2026-01-03"}
    c2 = {"versionId": "v-c2", "paperId": "p-c2", "title": "C2", "publishedOn": "2026-01-04"}
    selected = [
        item["versionId"]
        for item in repository.select_window_content(
            topic_id, W1[0], W1[1], selection_limit=50, content_limit=10
        )
    ]
    assert "v-c1" in selected
    run, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [c1])
    assert repository.begin_send(run["id"], "local-sink") is not None
    repository.finish_send(run["id"], "unknown")
    # The resolve control requires the human decision to name its assumption.
    with pytest.raises(TopicsError) as unnamed:
        service.resolve(authority, topic_id, run["id"], {"decision": "delivered"})
    assert unnamed.value.code == "INVALID_ARGUMENT"
    resolved = service.resolve(
        authority,
        topic_id,
        run["id"],
        {"decision": "delivered", "assumption": "the send landed before the cut"},
    )
    assert resolved["state"] == "sent"
    assert "v-c1" in watermark_ids(connect, topic_id)
    # Resolve-delivered re-applies the watermark: no repeat delivery.
    after = [
        item["versionId"]
        for item in repository.select_window_content(
            topic_id, W1[0], W1[1], selection_limit=50, content_limit=10
        )
    ]
    assert "v-c1" not in after
    # Resolve-not-delivered records failed and leaves the window's content
    # re-deliverable inside a later window's bounds (BR3.3/BR2.1).
    run2, _ = repository.prepare_run(topic_id, W2[0], W2[1], revision, [c2])
    assert repository.begin_send(run2["id"], "local-sink") is not None
    repository.finish_send(run2["id"], "unknown")
    service.resolve(
        authority,
        topic_id,
        run2["id"],
        {"decision": "not-delivered", "assumption": "no send landed"},
    )
    assert service.read_run(authority, topic_id, run2["id"])["state"] == "failed"
    assert "v-c2" not in watermark_ids(connect, topic_id)
    later = [
        item["versionId"]
        for item in repository.select_window_content(
            topic_id, dt.date(2026, 1, 2), dt.date(2026, 1, 8), selection_limit=50, content_limit=10
        )
    ]
    assert "v-c2" in later and "v-c1" not in later


def test_unsubscribe_queued_versus_midflight(transactions, authority, connect):
    service, _, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="unsubscribe-topic")
    revision = revision_of(connect, topic_id)
    # Later window first, so both runs can coexist (BR2.4 insertion order).
    queued, _ = repository.prepare_run(topic_id, W2[0], W2[1], revision, [ITEM])
    in_flight, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    sending = repository.begin_send(in_flight["id"], "local-sink")
    assert sending is not None
    # Unsubscribe discards the queued run; the in-flight attempt is untouched.
    stopped = service.unsubscribe(authority, topic_id)
    assert str(queued["id"]) in stopped["discardedRunIds"]
    assert run_row(connect, queued["id"])["state"] == "discarded"
    assert run_row(connect, in_flight["id"])["state"] == "sending"
    # The send transition refuses an unsubscribed topic's queued run (BR4.1).
    assert repository.begin_send(queued["id"], "local-sink") is None
    # Mid-flight: the in-flight attempt finishes and records its outcome.
    delivery = DigestDelivery(transactions, None)
    terminal = delivery.attempt(sending, {"account_id": authority.account_id, "display_name": "T"})
    assert terminal is not None
    view = service.read_run(authority, topic_id, in_flight["id"])
    assert view["state"] in ("sent", "failed", "unknown")
    assert view["outcome"] is not None


def test_reactivation_never_repeats_delivery(transactions, authority, connect):
    service, _, delivery = build(transactions)
    repository = TopicsRepository(transactions)
    key, topic_id = follow_topic(service, authority, base="reactivate-topic")
    revision = revision_of(connect, topic_id)
    run, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    assert repository.begin_send(run["id"], "local-sink") is not None
    delivery.attempt(run, {"account_id": authority.account_id, "display_name": "T"})
    service.unsubscribe(authority, topic_id)
    again = service.follow(authority, key, "Reactivate")
    assert again["reactivated"] is True
    # The watermark survived reactivation: this topic's delivered content is
    # never re-sent (other owners' eligible corpus stays selectable).
    assert "v-c1" not in [
        item["versionId"]
        for item in repository.select_window_content(
            topic_id, W1[0], W1[1], selection_limit=50, content_limit=10
        )
    ]
