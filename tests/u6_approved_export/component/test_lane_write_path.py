"""The lane's write path: the atomic claim, definite change versus could-not-check with
its 24 h bound, the rate-limit window, no rewrite of an unknown export, the settling wait
from `deadlineAt`, and the connection facts of a write's outcome (BR3.3, BR4.2, BR4.3,
NFR4.4, NFR4.5; security design §8.2, §8.5)."""

import datetime as dt
import logging
from uuid import UUID, uuid4

import psycopg
import pytest
from backend.modules.export.fake_notion import Answer
from backend.modules.export.lane import ExportLane, LaneItem
from backend.modules.research.errors import ResearchError

from tests.u6_approved_export import lane_flows as lf
from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import store_flows as flows


class Interleaved:
    """The real store, with a step of another actor run just before or just after the
    lane's claim, and optionally a pace record that cannot be reserved."""

    def __init__(self, repository, *, before_claim=None, after_claim=None, pace=True):
        self._repository = repository
        self._before, self._after, self._pace = before_claim, after_claim, pace

    def claim(self, *args, **kwargs):
        if self._before:
            self._before()
        claimed = self._repository.claim(*args, **kwargs)
        if self._after:
            self._after()
        return claimed

    def reserve_pace_slot(self, *args, **kwargs):
        return self._repository.reserve_pace_slot(*args, **kwargs) if self._pace else None

    def __getattr__(self, name):
        return getattr(self._repository, name)


def interleaved_lane(lr, **steps) -> ExportLane:
    return ExportLane(
        Interleaved(lr.repo, **steps),
        lr.rig.service.adapter,
        lr.rig.service.binding,
        policy=lr.rig.policy,
        clock=lr.clock,
    )


def test_a_write_claims_its_attempt_atomically_and_a_stale_item_writes_nothing(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    item = lf.item(flow["effect"])

    assert lr.lane.run_item(item) == "succeeded"
    [attempt] = lf.attempts(connect, flow["effect"])
    assert attempt["response_class"] == "created"
    assert attempt["creator_confirmed"] is True
    assert attempt["provider_request_id"]
    assert attempt["writer_identity"] == lr.rig.bot
    assert attempt["deadline_at"] - attempt["started_at"] == dt.timedelta(
        seconds=lr.rig.policy.write_deadline_seconds
    )
    assert lf.row(connect, flow["effect"])["settled_by"] == "provider"
    assert len(lr.fake.pages_under(flow["page"])) == 1
    assert lf.latest_lane_status(connect)["outcome"] == "succeeded"

    # The same item again: the compare-and-set sees the revision moved on.
    assert lr.lane.run_item(item) == "skipped"
    assert len(lr.fake.writes) == 1
    assert len(lf.attempts(connect, flow["effect"])) == 1


def test_a_claim_taken_elsewhere_first_leaves_the_lane_nothing_to_write(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    item = lf.item(flow["effect"])
    assert lr.rig.claim(flow["effect"]) is not None

    assert lr.lane.run_item(item) == "skipped"
    assert lr.fake.writes == []
    [attempt] = lf.attempts(connect, flow["effect"])
    assert attempt["ended_at"] is None
    assert lf.row(connect, flow["effect"])["state"] == "executing"


def test_a_definite_change_ends_an_accepted_export_without_writing(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    source = lr.rig.research.ready()
    flow = lf.pressed(lr, source=source)
    lr.rig.research.set_eligibility(source, "2")

    assert lr.lane.run_item(lf.item(flow["effect"])) == "invalidated"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["outcome_reason"]) == ("invalidated", "source-changed")
    assert lr.fake.writes == []
    assert lf.attempts(connect, flow["effect"]) == []


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (RuntimeError("U4 unreachable"), "dependency-unavailable"),
        (ResearchError("POLICY_UNRESOLVED"), "policy-unresolved"),
    ],
)
def test_could_not_check_waits_and_fails_only_at_the_24_hour_bound(
    transactions, connect, authority, tmp_path, failure, reason
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    lr.rig.research.failure = failure
    first = lr.clock.now

    assert lr.lane.run_item(lf.item(flow["effect"])) == "waiting"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["waiting_since"]) == ("accepted", first)

    lr.clock.advance(lr.rig.policy.could_not_check_wait_seconds - 1)
    assert lr.lane.run_item(lf.item(row)) == "waiting"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["waiting_since"]) == ("accepted", first)

    lr.clock.advance(1)
    assert lr.lane.run_item(lf.item(row)) == "failed"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["outcome_reason"]) == ("failed", reason)
    assert lr.fake.writes == []


def test_a_destination_that_cannot_be_read_is_could_not_check_not_a_change(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    lr.fake.queue("pages.retrieve", Answer.error(503), target=flow["page"])

    assert lr.lane.run_item(lf.item(flow["effect"])) == "waiting"
    row = lf.row(connect, flow["effect"])
    assert row["state"] == "accepted" and row["waiting_since"] is not None

    # The next check passes: the wait ends with the claim and the write.
    assert lr.lane.run_item(lf.item(row)) == "succeeded"
    assert lf.row(connect, flow["effect"])["waiting_since"] is None
    assert len(lr.fake.writes) == 1


def resume(lr, connect, flow) -> str:
    return lr.lane.run_item(lf.item(lf.row(connect, flow["effect"]), "resume"))


def test_the_rate_limit_window_allows_at_most_four_attempts(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    for _ in range(4):
        lr.fake.queue("pages.create", Answer.rate_limited(wait=1))

    assert lr.lane.run_item(lf.item(flow["effect"])) == "rate-limited"
    # A resume before the stated wait has passed is not due.
    assert resume(lr, connect, flow) == "skipped"
    outcomes = []
    for _ in range(3):
        lr.clock.advance(2)
        outcomes.append(resume(lr, connect, flow))

    assert outcomes == ["rate-limited", "rate-limited", "failed"]
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["outcome_reason"]) == ("failed", "rate-limit-budget-spent")
    assert [a["response_class"] for a in lf.attempts(connect, flow["effect"])] == [
        "rate-limited"
    ] * 4
    assert len(lr.fake.writes) == 4


def test_a_stated_wait_past_the_window_fails_at_once(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    wait = lr.rig.policy.rate_limit_window_seconds + 60
    lr.fake.queue("pages.create", Answer.rate_limited(wait=wait))

    assert lr.lane.run_item(lf.item(flow["effect"])) == "failed"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["outcome_reason"]) == ("failed", "rate-limit-budget-spent")
    assert len(lr.fake.writes) == 1


def test_a_resume_after_the_window_fails_without_writing(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    lr.fake.queue("pages.create", Answer.rate_limited(wait=1))
    assert lr.lane.run_item(lf.item(flow["effect"])) == "rate-limited"

    lr.clock.advance(lr.rig.policy.rate_limit_window_seconds)
    assert resume(lr, connect, flow) == "failed"
    assert lf.row(connect, flow["effect"])["outcome_reason"] == "rate-limit-budget-spent"
    assert len(lr.fake.writes) == 1


def test_a_could_not_check_during_a_resume_fails_as_dependency_unavailable(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    lr.fake.queue("pages.create", Answer.rate_limited(wait=1))
    assert lr.lane.run_item(lf.item(flow["effect"])) == "rate-limited"

    lr.clock.advance(2)
    lr.rig.research.failure = RuntimeError("U4 unreachable")
    assert resume(lr, connect, flow) == "waiting"
    row = lf.row(connect, flow["effect"])
    assert row["state"] == "executing" and row["waiting_since"] is not None

    lr.clock.advance(lr.rig.policy.rate_limit_window_seconds)
    assert resume(lr, connect, flow) == "failed"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["outcome_reason"]) == ("failed", "dependency-unavailable")
    assert len(lr.fake.writes) == 1


def test_a_definite_change_during_a_resume_fails_the_effect(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    source = lr.rig.research.ready()
    flow = lf.pressed(lr, source=source)
    lr.fake.queue("pages.create", Answer.rate_limited(wait=1))
    assert lr.lane.run_item(lf.item(flow["effect"])) == "rate-limited"

    lr.clock.advance(2)
    lr.rig.research.set_eligibility(source, "2")
    assert resume(lr, connect, flow) == "failed"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["outcome_reason"]) == ("failed", "source-changed")


def test_an_unclear_write_becomes_unknown_is_never_written_again_and_settles_from_deadline(
    transactions, connect, authority, tmp_path
):
    policy = nf.policy(write_deadline_seconds=1)
    lr = lf.build(transactions, connect, authority, tmp_path, policy=policy)
    flow = lf.pressed(lr)
    lr.fake.queue("pages.create", Answer.slow(3))

    assert lr.lane.run_item(lf.item(flow["effect"])) == "unknown"
    [attempt] = lf.attempts(connect, flow["effect"])
    assert attempt["response_class"] == "uncertain"
    row = lf.row(connect, flow["effect"])
    assert row["next_check_at"] == attempt["deadline_at"] + dt.timedelta(
        seconds=lr.rig.policy.settling_wait_seconds
    )

    for kind in ("execute", "resume"):
        assert lr.lane.run_item(LaneItem(kind, row["id"], row["revision"])) == "skipped"
    lr.clock.advance(3600)
    assert lr.lane.run_item(LaneItem("scan", row["id"], row["revision"])) == "scan-not-found"
    assert len(lr.fake.writes) == 1
    assert len(lf.attempts(connect, flow["effect"])) == 1


def test_a_created_page_names_the_destination_and_confirms_the_capability(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    before = lf.connection(connect, lr.rig)
    assert before["creation_capability"] == "unknown"

    assert lr.lane.run_item(lf.item(flow["effect"])) == "succeeded"
    after = lf.connection(connect, lr.rig)
    assert after["last_destination_id"] == flow["page"]
    assert after["creation_capability"] == "confirmed"
    assert after["revision"] == before["revision"]


def test_a_no_access_refusal_marks_the_capability_refused(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    before = lf.connection(connect, lr.rig)
    lr.fake.queue("pages.create", Answer.error(403), target=flow["page"])

    assert lr.lane.run_item(lf.item(flow["effect"])) == "failed"
    row = lf.row(connect, flow["effect"])
    assert (row["outcome_reason"], row["settled_by"]) == ("no-access", "provider")
    after = lf.connection(connect, lr.rig)
    assert after["creation_capability"] == "refused"
    assert after["revision"] == before["revision"]
    assert after["last_destination_id"] == before["last_destination_id"]


def test_after_a_replace_an_old_attempts_outcome_leaves_the_new_capability_unknown(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    token, _ = lr.rig.new_token()
    revision = lr.rig.connection()["revision"]
    # The replace lands while the old token's create is in flight.
    lf.on_write(lr.fake, lambda: lr.rig.configure(token=token, expected=revision))

    assert lr.lane.run_item(lf.item(flow["effect"])) == "succeeded"
    after = lf.connection(connect, lr.rig)
    assert after["revision"] == int(revision) + 1
    assert after["creation_capability"] == "unknown"
    assert after["last_destination_id"] == flow["page"]
    [attempt] = lf.attempts(connect, flow["effect"])
    assert attempt["connection_revision"] == int(revision)


def test_a_disconnect_between_claim_and_write_sends_nothing_and_fails_the_effect(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    lane = interleaved_lane(lr, after_claim=lambda: lr.rig.service.disconnect(authority, {}))

    assert lane.run_item(lf.item(flow["effect"])) == "failed"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["outcome_reason"]) == ("failed", "connection-changed")
    [attempt] = lf.attempts(connect, flow["effect"])
    assert attempt["response_class"] == "refused"
    assert lr.fake.writes == []


def test_a_session_ended_by_the_time_of_the_claim_invalidates_the_export(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    lr.rig.configure()
    approver = flows.second_session(connect, authority)
    preview = lr.rig.preview(lr.rig.page())
    approval = lr.rig.approve(preview, authority=approver)
    effect = lr.rig.execute(approval, authority=approver)
    lane = interleaved_lane(lr, before_claim=lambda: flows.end_session(connect, approver))

    assert lane.run_item(lf.item(effect)) == "invalidated"
    row = lf.row(connect, effect)
    assert (row["state"], row["outcome_reason"]) == ("invalidated", "authority-revoked")
    assert lf.attempts(connect, effect) == [] and lr.fake.writes == []


def test_an_unopenable_token_at_the_claim_and_an_unreservable_pace_slot_both_wait(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    connection = lr.rig.connection()

    def unavailable():
        lr.repo.set_availability(
            authority.account_id,
            UUID(connection["connectionId"]),
            int(connection["revision"]),
            available=False,
        )

    assert interleaved_lane(lr, pace=False).run_item(lf.item(flow["effect"])) == "waiting"
    row = lf.row(connect, flow["effect"])
    assert row["state"] == "accepted" and row["waiting_since"] is not None
    assert interleaved_lane(lr, before_claim=unavailable).run_item(lf.item(row)) == "waiting"
    row = lf.row(connect, flow["effect"])
    assert row["state"] == "accepted"
    assert lf.connection(connect, lr.rig)["revision"] == int(connection["revision"])
    assert lf.attempts(connect, flow["effect"]) == [] and lr.fake.writes == []


def test_items_that_no_longer_match_their_effect_are_skipped(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)

    assert lr.lane.run_item(lf.item(flow["effect"], "resume")) == "skipped"
    assert lr.lane.run_item(lf.item(flow["effect"], "scan")) == "skipped"
    assert lr.lane.run_item(LaneItem("execute", uuid4(), 1)) == "skipped"
    assert lf.row(connect, flow["effect"])["state"] == "accepted"
    assert lr.fake.writes == []


def test_a_store_fault_is_reduced_to_a_category_and_its_text_never_logged(
    transactions, connect, authority, tmp_path, caplog
):
    lr = lf.build(transactions, connect, authority, tmp_path)

    class Broken:
        def effect_binding(self, effect_id):
            raise psycopg.OperationalError("store down: synthetic-secret-detail")

        def record_lane_status(self, outcome):
            raise psycopg.OperationalError("store down: synthetic-secret-detail")

    lane = ExportLane(
        Broken(), lr.rig.service.adapter, lr.rig.service.binding, policy=lr.rig.policy,
        clock=lr.clock,
    )
    with caplog.at_level(logging.DEBUG):
        assert lane.run_item(LaneItem("execute", uuid4(), 1)) == "error"
    assert "OperationalError" in caplog.text
    assert "synthetic-secret-detail" not in caplog.text
    for record in caplog.records:
        assert record.exc_info is None
        assert not any(isinstance(arg, BaseException) for arg in tuple(record.args or ()))


def test_the_lane_lifecycle_guards(transactions, connect, authority, tmp_path):
    lr = lf.build(transactions, connect, authority, tmp_path)
    policy = lr.rig.policy

    def lane() -> ExportLane:
        return ExportLane(
            lr.repo, lr.rig.service.adapter, lr.rig.service.binding, policy=policy,
            clock=lr.clock,
        )

    for kind, effect, revision, error in (
        ("write", uuid4(), 1, ValueError),
        ("execute", "not-an-id", 1, TypeError),
        ("execute", uuid4(), 0, ValueError),
    ):
        with pytest.raises(error):
            LaneItem(kind, effect, revision)
    with pytest.raises(TypeError):
        ExportLane(lr.repo, None, None, policy=object(), clock=lr.clock)

    never_started = lane()
    assert not never_started.idle
    assert not never_started.offer(LaneItem("execute", uuid4(), 1))
    with pytest.raises(TypeError):
        never_started.offer("an item")
    assert never_started.stop() is True

    running = lane()
    running.start()
    with pytest.raises(ValueError):
        running.start()
    assert running.idle and running.running
    assert running.stop()
    assert not running.running and not running.offer(LaneItem("execute", uuid4(), 1))

    assert never_started.item_seconds("scan") > policy.scan_budget_seconds
    assert never_started.item_seconds("execute") > (
        policy.write_deadline_seconds + policy.read_back_budget_seconds
    )
