"""RJ-AC01–08 / AC12 — the job contract: durable acceptance, idempotency, ordering, authorization.

REM-2 corrective, Phase 0.5 / Phase 5. Every test in this file failed before the contract existed.

The system it pins down previously had no jobs at all. ``POST /api/summarize`` enqueued an SQS
message, answered ``pending``, and returned nothing that could be looked up again — so:

  * **acceptance was a claim, not a receipt** (RJ-AC01). If the enqueue or the response died, the
    caller was told to poll work that did not exist, and could not tell "accepted" from "lost";
  * **a retry was a second billable job** (RJ-AC06). There was no idempotency key, so a client that
    re-sent after a timeout paid twice for one piece of work;
  * **history was invisible** (RJ-AC04). A reconnecting client had no replay point, so a dropped
    connection either lost progress or re-fetched a full log it had already seen;
  * **possession of a job id was authorization** (RJ-AC05). Nothing re-checked the caller, and
    nothing distinguished "not yours" from "does not exist";
  * **redelivery re-ran the effect** (ND-Q8). SQS guarantees at-least-once delivery; the only
    guard was a cache write-through that arrives *after* the LLM call, i.e. after the money.
"""

from __future__ import annotations

import pytest

from summarization.domain.job import (
    TERMINAL_STATES,
    TRANSITIONS,
    ContentJob,
    JobContractError,
    JobError,
    JobState,
    can_transition,
)
from summarization.service.job_service import ContentJobService


def _ctx(user_id: str | None):
    from summarization.domain.models import AuthSession, RequestContext

    session = AuthSession(user_id=user_id) if user_id else None
    return RequestContext(auth_session=session, request_id="r1")


class _Queue:
    """The dispatch seam. Fails on demand so the "queued but not accepted" path is reachable."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.fail = False

    def __call__(self, job: ContentJob) -> None:
        if self.fail:
            raise RuntimeError("queue unavailable")
        self.sent.append((job.job_id, job.owner_id))


def _service(*, queue=None, ttl=3600.0, t=1000.0):
    from summarization.adapters.in_memory_jobs import InMemoryJobStore

    store = InMemoryJobStore()
    return store, ContentJobService(
        store=store, enqueue=queue or _Queue(), result_ttl_seconds=ttl, now=lambda: t
    )


# --- the state machine itself (plan item 20) ---------------------------------------------------


def test_the_lifecycle_is_the_declared_one() -> None:
    # Plan item 20 names the sequence explicitly; a state machine that grows an extra state to make
    # a caller happy is how a status becomes untrustworthy.
    assert [s.value for s in JobState] == [
        "SUBMITTED",
        "ACCEPTED",
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "ABSTAINED",
    ]


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobState.SUBMITTED, JobState.ACCEPTED),
        (JobState.ACCEPTED, JobState.QUEUED),
        (JobState.QUEUED, JobState.RUNNING),
        (JobState.RUNNING, JobState.COMPLETED),
        (JobState.RUNNING, JobState.FAILED),
        (JobState.RUNNING, JobState.ABSTAINED),
        (JobState.SUBMITTED, JobState.FAILED),
        (JobState.ACCEPTED, JobState.FAILED),
    ],
)
def test_declared_forward_moves_are_allowed(current: JobState, target: JobState) -> None:
    assert can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        # Terminal is terminal: a late or duplicated message must not resurrect finished work.
        (JobState.COMPLETED, JobState.RUNNING),
        (JobState.FAILED, JobState.RUNNING),
        (JobState.ABSTAINED, JobState.RUNNING),
        # No skipping ahead: "running" is a claim about work in flight, not a guess.
        (JobState.SUBMITTED, JobState.COMPLETED),
        (JobState.ACCEPTED, JobState.RUNNING),
        (JobState.QUEUED, JobState.COMPLETED),
        # No going backwards.
        (JobState.RUNNING, JobState.QUEUED),
        (JobState.RUNNING, JobState.SUBMITTED),
    ],
)
def test_every_other_move_is_refused(current: JobState, target: JobState) -> None:
    assert not can_transition(current, target)
    assert target not in TRANSITIONS[current]


def test_a_terminal_state_has_no_outgoing_edge() -> None:
    for state in TERMINAL_STATES:
        assert TRANSITIONS[state] == frozenset()


def test_an_illegal_move_on_a_held_record_raises_instead_of_quietly_moving() -> None:
    # A caller holding a stale in-memory copy must not be able to write an illegal edge over a
    # fresh one — that is how a finished job turns back into "running" and bills twice.
    job = ContentJob(
        job_id="j1",
        owner_id="u1",
        task_type="summarize",
        state=JobState.COMPLETED,
        input={},
        created_at=1.0,
        updated_at=1.0,
    )

    with pytest.raises(JobContractError):
        job.transitioned(JobState.RUNNING, now=2.0)


# --- durable acceptance + idempotency (items 20, 21 / RJ-AC01, RJ-AC06) -----------------------


def test_a_submission_is_durable_before_it_is_reported_as_accepted() -> None:
    # RJ-AC01: the caller must be able to come back and ask "did you get this?" — so the record has
    # to exist, and the state has to say ACCEPTED, at the moment acceptance is reported.
    queue = _Queue()
    _, svc = _service(queue=queue)

    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")

    assert outcome.state is JobState.ACCEPTED
    assert outcome.job_id
    assert len(queue.sent) == 1


def test_the_same_idempotency_key_returns_the_same_job_instead_of_a_second_one() -> None:
    # RJ-AC06: the client's retry after a lost response is a lookup, not a second billable job.
    queue = _Queue()
    _, svc = _service(queue=queue)

    first = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    second = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")

    assert second.job_id == first.job_id
    assert second.deduplicated is True
    # The work was dispatched exactly once.
    assert len(queue.sent) == 1


def test_two_different_callers_may_use_the_same_idempotency_key() -> None:
    # Idempotency is per caller. A shared key space would either leak one caller's job to another
    # or silently collapse their distinct work into one job.
    _, svc = _service()

    first = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    other = svc.submit(_ctx("u2"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")

    assert other.job_id != first.job_id


def test_a_submission_without_an_idempotency_key_is_always_a_new_job() -> None:
    # The key is what makes a retry safe; without it the caller has said nothing about intent, so
    # collapsing two identical submissions would silently drop a deliberate re-run.
    _, svc = _service()

    first = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key=None)
    second = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key=None)

    assert first.job_id != second.job_id


def test_a_queue_failure_does_not_leave_a_job_claiming_accepted_work() -> None:
    # RJ-AC01's other half: if the work cannot be dispatched, the job must say so. Reporting
    # ACCEPTED for work that was never queued is the exact lie this contract exists to remove.
    queue = _Queue()
    queue.fail = True
    store, svc = _service(queue=queue)

    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")

    assert outcome.state is JobState.FAILED
    stored = store.get(outcome.job_id)
    assert stored is not None and stored.state is JobState.FAILED
    assert stored.error is not None and stored.error.retryable is True
    # And the failure is retryable: the same key must not permanently poison the caller's retry.
    queue.fail = False
    retry = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    assert retry.job_id != outcome.job_id


def test_an_unauthenticated_caller_cannot_submit() -> None:
    # SEC-8: no principal, no acceptance — and no job row a later request could claim.
    store, svc = _service()

    with pytest.raises(PermissionError):
        svc.submit(_ctx(None), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")

    assert store.get("nope") is None


# --- authorization (item 23 / RJ-AC05) --------------------------------------------------------


def test_another_caller_can_neither_read_nor_advance_someone_elses_job() -> None:
    # RJ-AC05: possession of a job id is not authorization.
    store, svc = _service()
    mine = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")

    assert svc.state_of(_ctx("u2"), mine.job_id) is None
    assert svc.events(_ctx("u2"), mine.job_id) == []
    assert svc.mark_running(_ctx("u2"), mine.job_id) is None
    # ...and the owner's job is untouched by the attempt.
    assert store.get(mine.job_id).state is JobState.ACCEPTED


def test_a_caller_cannot_even_tell_that_another_callers_job_exists() -> None:
    # SEC-8 / RJ-AC05: "not yours" must be indistinguishable from "does not exist", or the status
    # code becomes an existence oracle for other tenants' work.
    _, svc = _service()
    mine = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")

    assert svc.state_of(_ctx("u2"), "no-such-job") is None
    assert svc.state_of(_ctx("u2"), mine.job_id) is None


# --- events, ordering, replay (item 22 / RJ-AC02, RJ-AC04) ------------------------------------


def test_every_state_change_is_recorded_in_order_with_a_growing_sequence() -> None:
    _, svc = _service()
    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")

    svc.mark_queued(_ctx("u1"), outcome.job_id)
    svc.mark_running(_ctx("u1"), outcome.job_id)
    svc.mark_completed(_ctx("u1"), outcome.job_id, result_ref="summary/2401.1/v1")

    events = svc.events(_ctx("u1"), outcome.job_id)
    assert [e.state for e in events] == [
        JobState.ACCEPTED,
        JobState.QUEUED,
        JobState.RUNNING,
        JobState.COMPLETED,
    ]
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


def test_a_reconnecting_client_replays_exactly_the_events_it_missed() -> None:
    # RJ-AC04: the whole point of the per-job seq. Reconnect from the last event seen and receive
    # the gap — not the full log (duplicated progress) and not a hole (silently skipped states).
    _, svc = _service()
    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    svc.mark_queued(_ctx("u1"), outcome.job_id)
    svc.mark_running(_ctx("u1"), outcome.job_id)
    last_seen = svc.events(_ctx("u1"), outcome.job_id)[-1].seq

    svc.mark_completed(_ctx("u1"), outcome.job_id, result_ref="summary/2401.1/v1")

    missed = svc.events(_ctx("u1"), outcome.job_id, after_seq=last_seen)
    assert [e.state for e in missed] == [JobState.COMPLETED]


def test_reading_status_does_not_create_another_job() -> None:
    # RJ-AC02: reading a job's status is not itself a job to be queued and polled.
    store, svc = _service()
    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    before = store.get(outcome.job_id)

    svc.state_of(_ctx("u1"), outcome.job_id)
    svc.state_of(_ctx("u1"), outcome.job_id)

    after = store.get(outcome.job_id)
    assert after.state is before.state
    assert after.created_at == before.created_at


def test_an_abstention_is_not_reported_as_a_completion() -> None:
    # RJ-AC03: "we chose not to" and "here are your results" are different answers, and a known
    # abstention must never be laundered into an empty success.
    store, svc = _service()
    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    svc.mark_queued(_ctx("u1"), outcome.job_id)
    svc.mark_running(_ctx("u1"), outcome.job_id)

    svc.mark_abstained(_ctx("u1"), outcome.job_id, reason="input_too_long")

    job = store.get(outcome.job_id)
    assert job.state is JobState.ABSTAINED
    assert job.abstain_reason == "input_too_long"
    assert job.result_ref is None


# --- effect ledger (item 25 / ND-Q8) ----------------------------------------------------------


def test_a_redelivered_attempt_does_not_pay_for_the_work_twice() -> None:
    # SQS is at-least-once. The claim is taken BEFORE the effect, so the duplicate delivery is
    # cheap rather than expensive.
    from summarization.adapters.in_memory_jobs import InMemoryJobStore

    store = InMemoryJobStore()

    assert store.claim_effect("j1", 1, "generate") is True
    assert store.claim_effect("j1", 1, "generate") is False


def test_an_attempt_spends_its_effect_budget_exactly_once() -> None:
    # Plan item 25 fixes the ledger at (job_id, attempt): one attempt may buy one externally
    # observable effect. Allowing a second claim under a different label would let a redelivery pay
    # twice for one attempt, which is the whole failure the ledger exists to prevent.
    from summarization.adapters.in_memory_jobs import InMemoryJobStore

    store = InMemoryJobStore()
    assert store.claim_effect("j1", 1, "generate") is True

    assert store.claim_effect("j1", 1, "write_through") is False  # same attempt
    assert store.claim_effect("j1", 2, "generate") is True  # a genuine retry


def test_releasing_a_failed_claim_lets_the_retry_proceed() -> None:
    from summarization.adapters.in_memory_jobs import InMemoryJobStore

    store = InMemoryJobStore()
    assert store.claim_effect("j1", 1, "generate") is True
    store.release_effect("j1", 1)

    assert store.claim_effect("j1", 1, "generate") is True


def test_a_duplicate_terminal_write_cannot_resurrect_a_finished_job() -> None:
    # The compare-and-set guard that makes the ledger unnecessary for the common case: even a
    # message that skips the ledger entirely cannot walk a completed job back into running.
    from summarization.adapters.in_memory_jobs import InMemoryJobStore

    store = InMemoryJobStore()
    job, _ = store.accept(
        job_id="j1", owner_id="u1", task_type="summarize", input={}, idempotency_key="k", now=1.0
    )
    store.transition(
        job.job_id,
        JobState.ACCEPTED,
        expect_from=frozenset({JobState.SUBMITTED}),
        now=2.0,
    )
    store.transition(
        job.job_id, JobState.QUEUED, expect_from=frozenset({JobState.ACCEPTED}), now=3.0
    )
    store.transition(
        job.job_id, JobState.RUNNING, expect_from=frozenset({JobState.QUEUED}), now=4.0
    )
    done = store.transition(
        job.job_id, JobState.COMPLETED, expect_from=frozenset({JobState.RUNNING}), now=5.0
    )
    assert done is not None

    late = store.transition(
        job.job_id, JobState.RUNNING, expect_from=frozenset({JobState.QUEUED}), now=6.0
    )

    assert late is None
    assert store.get("j1").state is JobState.COMPLETED


# --- result delivery + expiry (items 24, 26 / RJ-AC07, RJ-AC08) -------------------------------


def test_a_prepared_result_is_delivered_directly_without_another_job() -> None:
    # RJ-AC08: once the work is done the result is a normal authorized read — not a new job that
    # then has to be polled, and not a redirect to somewhere else.
    store, svc = _service()
    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    svc.mark_queued(_ctx("u1"), outcome.job_id)
    svc.mark_running(_ctx("u1"), outcome.job_id)
    svc.mark_completed(_ctx("u1"), outcome.job_id, result_ref="summary/2401.1/v1")

    delivered = svc.result_ref(_ctx("u1"), outcome.job_id)

    assert delivered == "summary/2401.1/v1"
    assert store.get(outcome.job_id).state is JobState.COMPLETED


def test_another_caller_cannot_deliver_someone_elses_result() -> None:
    _, svc = _service()
    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    svc.mark_queued(_ctx("u1"), outcome.job_id)
    svc.mark_running(_ctx("u1"), outcome.job_id)
    svc.mark_completed(_ctx("u1"), outcome.job_id, result_ref="summary/2401.1/v1")

    assert svc.result_ref(_ctx("u2"), outcome.job_id) is None


def test_an_expired_prepared_result_is_no_longer_delivered() -> None:
    # RJ-AC07 bounds reuse: a job that sat unclaimed must not serve a result indefinitely, or the
    # job store becomes an unbounded read path around the result TTL.
    from summarization.adapters.in_memory_jobs import InMemoryJobStore

    clock = {"t": 1000.0}
    store = InMemoryJobStore()
    svc = ContentJobService(
        store=store, enqueue=_Queue(), result_ttl_seconds=60.0, now=lambda: clock["t"]
    )
    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    svc.mark_queued(_ctx("u1"), outcome.job_id)
    svc.mark_running(_ctx("u1"), outcome.job_id)
    svc.mark_completed(_ctx("u1"), outcome.job_id, result_ref="summary/2401.1/v1")

    clock["t"] += 59.0
    assert svc.result_ref(_ctx("u1"), outcome.job_id) == "summary/2401.1/v1"

    clock["t"] += 120.0
    assert svc.result_ref(_ctx("u1"), outcome.job_id) is None


def test_a_failed_job_has_no_result_to_deliver() -> None:
    _, svc = _service()
    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    svc.mark_queued(_ctx("u1"), outcome.job_id)
    svc.mark_running(_ctx("u1"), outcome.job_id)
    svc.mark_failed(
        _ctx("u1"), outcome.job_id, error=JobError("internal", "처리 중 문제가 발생했습니다.", True)
    )

    assert svc.result_ref(_ctx("u1"), outcome.job_id) is None


# --- purge (G3 / NFR-R4) ----------------------------------------------------------------------


def test_purging_an_owner_leaves_no_traceable_job() -> None:
    # Account deletion has to actually remove the work: an event log that outlives the account is a
    # re-identification path, and a late worker write must find nothing to attach to.
    store, svc = _service()
    outcome = svc.submit(_ctx("u1"), "summarize", {"paperId": "2401.1"}, idempotency_key="k1")
    svc.mark_queued(_ctx("u1"), outcome.job_id)

    store.purge_owner("u1")

    assert store.get(outcome.job_id) is None
    assert svc.events(_ctx("u1"), outcome.job_id) == []