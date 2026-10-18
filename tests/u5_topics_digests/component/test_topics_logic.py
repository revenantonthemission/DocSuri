"""Business behavior over the real realm: scheduler evaluation, delivery
outcomes, reconciliation, consent handling and lifecycle disposition.

An autouse fixture quiets the persistent realm first: earlier runs of this
suite leave active topics and queued runs behind, so every test starts with
only the topic it creates in the due page."""

import datetime as dt
from uuid import uuid4

import pytest
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.accounts.integrations.digest_email import DigestMailResult
from backend.modules.topics.control_lifecycle import TopicsDigestsLifecycleParticipant
from backend.modules.topics.delivery import DigestDelivery
from backend.modules.topics.errors import TopicsError
from backend.modules.topics.preparation import DigestPreparation
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.scheduler import TopicsScheduler
from backend.modules.topics.service import TopicsService
from psycopg.types.json import Jsonb

W1 = (dt.date(2026, 1, 1), dt.date(2026, 1, 7))
W2 = (dt.date(2026, 1, 8), dt.date(2026, 1, 14))
W3 = (dt.date(2026, 1, 15), dt.date(2026, 1, 21))
ITEM = {
    "versionId": "v-c1",
    "paperId": "p-c1",
    "title": "Component Paper",
    "publishedOn": "2026-01-03",
}


class RefusingMail:
    path_kind = "local-sink"

    async def send(self, email, presentation, request_key):
        return DigestMailResult("refused")


class UnobservedMail:
    path_kind = "local-sink"

    async def send(self, email, presentation, request_key):
        raise TimeoutError("transport cut mid-send")


@pytest.fixture(autouse=True)
def quiet_realm(connect):
    # The fixtures module owns the fixture-resolve topic (memberA's browser
    # fixture); component tests quiet everything except that shared fixture.
    with connect("topics") as conn:
        conn.execute(
            "UPDATE topics.followed_topic SET status='unsubscribed',updated_at="
            "clock_timestamp() WHERE status='active' "
            "AND topic_key <> 'fixture-resolve-topic'"
        )
        conn.execute(
            "UPDATE topics.digest_run SET state='discarded',updated_at=clock_timestamp() "
            "WHERE state='prepared' AND topic_id NOT IN "
            "(SELECT id FROM topics.followed_topic WHERE topic_key='fixture-resolve-topic')"
        )
        # Stale unknown outcomes from earlier suite runs would saturate the
        # reconciliation page: close them through the legal unknown->failed
        # transition and record the reconciliation on the outcome row.
        conn.execute(
            "UPDATE topics.digest_run SET state='failed',updated_at=clock_timestamp() "
            "WHERE state='unknown' AND topic_id NOT IN "
            "(SELECT id FROM topics.followed_topic WHERE topic_key='fixture-resolve-topic')"
        )
        conn.execute(
            "UPDATE topics.delivery_outcome o SET reconciled_state='failed',reconciled_at="
            "clock_timestamp() FROM topics.digest_run r WHERE o.run_id=r.id "
            "AND r.state='failed' AND o.observed_state='unknown' "
            "AND o.reconciled_state IS NULL"
        )


def build(transactions, mail=None):
    preparation = DigestPreparation(transactions, None)
    delivery = DigestDelivery(transactions, None, mail=mail)
    scheduler = TopicsScheduler(transactions, preparation, delivery)
    scheduler._now = lambda: dt.datetime.combine(
        dt.datetime.now(dt.UTC).date() + dt.timedelta(days=1), dt.time(12), tzinfo=dt.UTC
    )
    return TopicsService(transactions), scheduler, delivery


def follow_topic(service, authority, base="component-topic"):
    key = f"{base}-{uuid4().hex[:8]}"
    topic_id = service.follow(authority, key, "Component Topic")["topicId"]
    return key, topic_id


def revision_of(connect, topic_id):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT revision FROM topics.digest_settings WHERE topic_id=%s", (topic_id,)
        ).fetchone()["revision"]


def make_due(connect, topic_id):
    """Move the topic's delivery time to midnight so it is due at any hour."""
    with connect("topics") as conn:
        conn.execute(
            "UPDATE topics.digest_settings SET delivery_time_local=%s,revision=revision+1 "
            "WHERE topic_id=%s",
            (dt.time(0, 0), topic_id),
        )


def run_row(connect, run_id):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT r.state,o.observed_state,o.failure_reason FROM topics.digest_run r "
            "LEFT JOIN topics.delivery_outcome o ON o.run_id=r.id WHERE r.id=%s",
            (run_id,),
        ).fetchone()


def watermark_count(connect, topic_id):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM topics.topic_delivery_watermark WHERE topic_id=%s",
            (topic_id,),
        ).fetchone()["n"]


def watermark_ids(connect, topic_id):
    with connect("topics") as conn:
        return {
            row["content_id"]
            for row in conn.execute(
                "SELECT content_id FROM topics.topic_delivery_watermark WHERE topic_id=%s",
                (topic_id,),
            ).fetchall()
        }


def seed_corpus(connect, rows):
    with connect("corpus") as conn:
        for version_id, paper_id, published, eligible in rows:
            conn.execute(
                "INSERT INTO corpus.paper(id,title,authors,metadata,published_on,withdrawn) "
                "VALUES(%s,'Synthetic Paper','[]','{}',%s,false) ON CONFLICT (id) DO UPDATE "
                "SET published_on=excluded.published_on,withdrawn=false",
                (paper_id, published),
            )
            conn.execute(
                "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
                "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,'local://x',"
                "repeat('a',64),'v1','synthetic',%s,'local-research','{}','{}') "
                "ON CONFLICT (id) DO UPDATE SET eligible=excluded.eligible",
                (version_id, paper_id, eligible),
            )


def test_due_window_boundaries_and_late_firing(transactions):
    _, scheduler, _ = build(transactions)
    daily = {
        "id": uuid4(),
        "cadence": "daily",
        "delivery_time_local": dt.time(8, 0),
        "delivery_day": None,
        "content_window_days": 7,
        "preferences": {"timeZone": "UTC"},
    }
    # Before the scheduled minute the topic is not due (BR1.2).
    scheduler._now = lambda: dt.datetime(2026, 3, 10, 7, 59, tzinfo=scheduler.zone)
    assert scheduler._due_window(daily) is None
    # At the scheduled minute — and hours late — the window still delivers.
    scheduler._now = lambda: dt.datetime(2026, 3, 10, 8, 0, tzinfo=scheduler.zone)
    assert scheduler._due_window(daily) == (dt.date(2026, 3, 4), dt.date(2026, 3, 10))
    scheduler._now = lambda: dt.datetime(2026, 3, 10, 23, 0, tzinfo=scheduler.zone)
    assert scheduler._due_window(daily) == (dt.date(2026, 3, 4), dt.date(2026, 3, 10))
    # Weekly cadence fires only on its anchor day (BR1.2).
    weekly = dict(daily, cadence="weekly", delivery_day="tue")
    assert scheduler._due_window(weekly) == (dt.date(2026, 3, 4), dt.date(2026, 3, 10))
    monday = dict(weekly, delivery_day="mon")
    assert scheduler._due_window(monday) is None


@pytest.mark.parametrize("blocked_by", ["consent", "unknown"])
def test_blocked_page_cannot_starve_another_owner(
    transactions, authority, authority_b, connect, blocked_by
):
    service, scheduler, _ = build(transactions)
    repository = TopicsRepository(transactions)
    today = dt.datetime.now(dt.UTC).date()
    tomorrow = today + dt.timedelta(days=1)
    scheduler._now = lambda: dt.datetime.combine(tomorrow, dt.time(12), tzinfo=dt.UTC)
    seed_corpus(connect, [("v-fairness", "p-fairness", today, True)])
    blocked = []
    # More than one full page sorts before the later owner's 11:00 occurrences.
    # Seed only through the owner module; do not mock the due query or authority.
    for _ in range(51):
        _, topic = follow_topic(service, authority, "blocked-page")
        make_due(connect, topic)
        blocked.append(topic)
        if blocked_by == "unknown":
            run, _ = repository.prepare_run(
                topic, today - dt.timedelta(days=6), today, revision_of(connect, topic), [ITEM]
            )
            repository.begin_send(run["id"], "local-sink")
            repository.finish_send(run["id"], "unknown")
    eligible = []
    for _ in range(2):
        _, topic = follow_topic(service, authority_b, "eligible-later")
        service.save_settings(
            authority_b,
            topic,
            {
                "revision": 1,
                "cadence": "daily",
                "deliveryTimeLocal": "11:00",
                "deliveryDay": None,
                "contentWindowDays": 7,
            },
        )
        eligible.append(topic)
    if blocked_by == "consent":
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.consent SET granted=false WHERE account_id=%s "
                "AND purpose='local-research'",
                (authority.account_id,),
            )
    with connect("topics") as conn:
        attempts_before = conn.execute(
            "SELECT count(*) AS n FROM topics.send_log_entry l JOIN topics.digest_run r "
            "ON r.id=l.run_id WHERE r.topic_id=ANY(%s::uuid[])",
            (blocked,),
        ).fetchone()["n"]
    due = repository.due_topics(scheduler._now(), 50)
    assert not set(blocked).intersection(str(row["id"]) for row in due)
    assert set(eligible).issubset({str(row["id"]) for row in due})
    passes = [scheduler.run_once(1) for _ in range(3)]
    assert all(result["prepared"] <= 1 and result["sent"] <= 1 for result in passes)
    assert sum(result["sent"] for result in passes) >= 2
    for topic in eligible:
        assert any(run["state"] == "sent" for run in service.read_topic(authority_b, topic)["runs"])
    with connect("topics") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM topics.send_log_entry l JOIN topics.digest_run r "
                "ON r.id=l.run_id WHERE r.topic_id=ANY(%s::uuid[])",
                (blocked,),
            ).fetchone()["n"]
            == attempts_before
        )
        if blocked_by == "unknown":
            assert (
                conn.execute(
                    "SELECT count(*) AS n FROM topics.digest_run WHERE topic_id=ANY(%s::uuid[]) "
                    "AND state='unknown'",
                    (blocked,),
                ).fetchone()["n"]
                == 51
            )


def test_refire_idempotence_and_chronological_ordering(transactions, authority, connect):
    service, scheduler, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority)
    make_due(connect, topic_id)
    # BR2.4: a non-terminal earlier window blocks later preparation within a
    # pass; the send pass completes that window, and the next pass proceeds.
    revision = revision_of(connect, topic_id)
    earlier, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    blocked = scheduler.run_once(limit=1)
    assert blocked["prepared"] == 0
    assert run_row(connect, earlier["id"])["state"] == "sent"
    # The first unblocked evaluation prepares the rolling window.
    first = scheduler.run_once(limit=1)
    assert first["prepared"] == 1
    runs = service.read_topic(authority, topic_id)["runs"]
    today = scheduler._now().date()
    rolling = next(
        r for r in runs if r["windowStart"] == (today - dt.timedelta(days=6)).isoformat()
    )
    # The pass's send stage may already have carried it; the window is what matters.
    assert rolling["state"] in ("sent", "failed", "unknown", "empty", "prepared")
    # A repeated tick does not re-prepare the covered day (idempotence).
    assert scheduler.run_once(limit=1)["prepared"] == 0
    # BR1.3: a settings revision discards the queued (prepared) run.
    revision = revision_of(connect, topic_id)
    queued, _ = repository.prepare_run(topic_id, W2[0], W2[1], revision, [ITEM])
    saved = service.save_settings(
        authority,
        topic_id,
        {
            "revision": revision,
            "cadence": "daily",
            "deliveryTimeLocal": "00:00",
            "deliveryDay": None,
            "contentWindowDays": 30,
        },
    )
    assert str(queued["id"]) in saved["discardedRunIds"]


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


def test_orphan_sweep_via_scheduler(transactions, authority, connect):
    service, scheduler, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="orphan-topic")
    revision = revision_of(connect, topic_id)
    run, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    with connect("topics") as conn:
        conn.execute(
            "UPDATE topics.digest_run SET state='sending',updated_at=clock_timestamp() "
            "- interval '1000 seconds' WHERE id=%s",
            (run["id"],),
        )
    result = scheduler.run_once(limit=1)
    assert result["recovered"] >= 1
    assert service.read_run(authority, topic_id, run["id"])["state"] == "unknown"


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


def test_consent_stop_and_restore(transactions, authority, connect):
    service, scheduler, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="consent-topic")
    make_due(connect, topic_id)
    revision = revision_of(connect, topic_id)
    run, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=false WHERE account_id=%s "
            "AND purpose='local-research'",
            (authority.account_id,),
        )
    # The scheduler drops queued work while consent is stopped (BR4.2).
    scheduler.run_once(limit=1)
    assert run_row(connect, run["id"])["state"] == "discarded"
    assert repository.begin_send(run["id"], "local-sink") is None
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=true WHERE account_id=%s "
            "AND purpose='local-research'",
            (authority.account_id,),
        )
    assert scheduler.run_once(limit=1)["prepared"] >= 1


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


def test_lifecycle_disposition_reporting(transactions, authority, connect):
    service, _, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="lifecycle-topic")
    revision = revision_of(connect, topic_id)
    queued, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    participant = TopicsDigestsLifecycleParticipant(transactions)

    def ticket(action):
        request, lifecycle_revision = uuid4(), uuid4()
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s",
                (lifecycle_revision, authority.account_id),
            )
            conn.execute(
                "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,"
                "policy_ref,manifest_revision,manifest,disposition,reason_key) "
                "VALUES(%s,%s,%s,%s,%s,'owner-effect-test',%s,'pending','pending')",
                (
                    request,
                    authority.account_id,
                    lifecycle_revision,
                    action,
                    Jsonb(SYNTHETIC_POLICY.reference),
                    Jsonb([["TopicsDigests", "live_records"]]),
                ),
            )
            conn.execute(
                "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope,generation,"
                "lease_until,attempts) VALUES(%s,'TopicsDigests','live_records',1,"
                "clock_timestamp()+interval '15 seconds',1)",
                (request,),
            )
        return dict(
            request_id=request,
            account_id=authority.account_id,
            lifecycle_revision=lifecycle_revision,
            participant="TopicsDigests",
            scope="live_records",
            generation=1,
            action=action,
            policy_ref=SYNTHETIC_POLICY.reference,
            manifest_revision="owner-effect-test",
        )

    result = participant.apply(ticket("withdraw"))
    assert result["evidenceRef"] and result["disposition"] == "complete"
    with connect("topics") as conn:
        status = conn.execute(
            "SELECT status FROM topics.followed_topic WHERE id=%s", (topic_id,)
        ).fetchone()["status"]
        discarded = conn.execute(
            "SELECT state FROM topics.digest_run WHERE id=%s", (queued["id"],)
        ).fetchone()["state"]
    assert status == "unsubscribed" and discarded == "discarded"
    # The erase disposition removes every digest fact for the account.
    erased = participant.apply(ticket("erase"))
    assert erased["disposition"] == "complete"
    with connect("topics") as conn:
        remaining = conn.execute(
            "SELECT count(*) AS n FROM topics.followed_topic WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()["n"]
    assert remaining == 0
