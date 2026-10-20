"""The worker's pass step: the orphan sweep, hand-over in security design §8.1's order
without duplicate scans, bounded housekeeping batches, NFR4.9's definite answers only,
and which preview revisions keep their tree (BR2.6, BR3.4, BR4.6, D4, D9).

The pass works realm-wide, and the realm persists across phases: the database and
repository layers leave rows of synthetic owners that have no account, so no erase
ticket can clear them. Housekeeping tests therefore first drain the realm with real
passes; hand-over tests read the store's real due order and keep this test's effects.
"""

import datetime as dt
from uuid import UUID

import psycopg
import pytest
from backend.modules.export import housekeeping_store
from backend.modules.export.lane_store import WriteOutcome
from backend.modules.export.store_support import next_check_time
from backend.modules.export.worker import ExportPassIncomplete, ExportWorker
from backend.modules.research.errors import ResearchError

from tests.u6_approved_export import lane_flows as lf
from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import service_flows as sf
from tests.u6_approved_export import store_flows as flows

OwnDue = lf.OwnDue
own_step = lf.own_step
drain = lf.drain


@pytest.fixture(autouse=True)
def second_owner_erased(connect, authority_b):
    """The second owner's rows from earlier tests are erased first (the first owner's
    are erased when the rig is built)."""
    flows.fresh(connect, authority_b.account_id)


def pass_rig(transactions, connect, authority, tmp_path, **options):
    double = lf.LaneDouble()
    lr = lf.build(transactions, connect, authority, tmp_path, lane=double, **options)
    lr.rig.configure()
    return lr, double


def open_approval(lr, *, page=None, source=None, approver=None) -> dict:
    """One prepared and approved revision, not executed."""
    preview = lr.rig.preview(page or lr.rig.page(), source)
    approval = lr.rig.approve(preview, authority=approver)
    return {"preview": preview, "approval": approval}


def approval_state(connect, flow) -> tuple:
    row = flows.approval_row(connect, UUID(flow["approval"]["approvalId"]))
    return row["state"], row["invalidation_reason"]


def kept_tree(connect, preview: dict) -> bool:
    row = flows.revision_row(connect, UUID(preview["previewId"]), int(preview["revision"]))
    return row["rendered_blocks"] is not None and row["trimmed_at"] is None


def test_the_worker_runs_the_inherited_pass_then_the_export_step():
    calls = []

    class Inherited:
        def run_once(self, limit=1):
            calls.append(("inherited", limit))
            return {"inherited": True}

    class Step:
        def run_once(self):
            calls.append(("export", None))
            return {}

    assert ExportWorker(Inherited(), Step()).run_once(limit=1) == {"inherited": True}
    assert calls == [("inherited", 1), ("export", None)]


def test_the_orphan_sweep_turns_an_outstanding_attempt_unknown(
    transactions, connect, authority, tmp_path
):
    lr, _ = pass_rig(transactions, connect, authority, tmp_path)
    flow = lr.rig.press(lr.rig.page())
    claimed = lr.rig.claim(flow["effect"])
    effect_id = claimed.effect["id"]

    lr.clock.advance(lr.rig.policy.orphan_after_seconds - 1)
    lr.step.run_once()
    assert flows.effect_row(connect, effect_id)["state"] == "executing"

    lr.clock.advance(1)
    assert lr.step.run_once()["orphans"] >= 1
    row = flows.effect_row(connect, effect_id)
    assert row["state"] == "unknown"
    # The check schedule still counts from the attempt's deadline (NFR4.4).
    deadline = claimed.attempt["deadline_at"]
    assert row["next_check_at"] == next_check_time(deadline, lr.clock.now, lr.rig.policy)
    assert row["next_check_at"] > lr.clock.now
    assert "orphaned-attempt" in lr.repo.effect_binding(effect_id)["effect"]["limitations"]
    [attempt] = lf.attempts(connect, claimed.effect)
    assert attempt["response_class"] == "uncertain"


def test_hand_over_follows_the_due_order_and_never_duplicates_a_scan(
    transactions, connect, authority, authority_b, tmp_path
):
    lr, double = pass_rig(transactions, connect, authority, tmp_path)
    rig, now = lr.rig, lr.clock.now
    # Owner a: an unknown export (a scan once due) and one in a rate-limit wait (a resume).
    unknown = rig.uncertain(rig.press(rig.page())["effect"])
    claimed = rig.claim(rig.press(rig.page())["effect"])
    rig.repo.record_write_outcome(
        claimed.effect["id"],
        claimed.attempt["id"],
        claimed.effect["revision"],
        WriteOutcome("rate-limited", retry_at=now + dt.timedelta(seconds=1)),
        now=now,
    )
    # Owner b: an accepted export of an owner with nothing executing.
    other = sf.build(transactions, connect, authority_b, tmp_path, keys="keys-b", clock=lr.clock)
    other.configure()
    accepted = UUID(other.press(other.page())["effect"]["effectId"])
    order = [claimed.effect["id"], accepted, unknown["id"]]
    step = own_step(lr, double, order)

    double.idle = False
    assert step.run_once()["handedOver"] is None
    assert double.offered == []

    double.idle = True
    lr.clock.advance(rig.policy.settling_wait_seconds + rig.policy.write_deadline_seconds)
    due = [row["id"] for row in lr.repo.due_items(lr.clock.now, limit=lf.DUE_LIMIT)]
    assert set(order) <= set(due), "this test's effects must lie within one due batch"
    kinds = [step.run_once()["handedOver"] for _ in range(5)]
    assert kinds == ["resume", "execute", "scan", "resume", "execute"]
    assert [item.effect_id for item in double.offered[:3]] == order
    # The scan's next check moved past the scan budget plus one minute, at a new revision
    # the lane item carries, so no later pass hands the same scan again.
    pushed = flows.effect_row(connect, unknown["id"])
    assert pushed["next_check_at"] == lr.clock.now + dt.timedelta(
        seconds=rig.policy.scan_budget_seconds + 60
    )
    assert double.offered[2].revision == pushed["revision"] == unknown["revision"] + 1


def test_housekeeping_batches_stay_bounded(transactions, connect, authority, tmp_path):
    lr, _ = pass_rig(
        transactions, connect, authority, tmp_path, policy=nf.policy(housekeeping_batch=2)
    )
    drain(transactions, lr)
    approver = flows.second_session(connect, authority)
    opened = [open_approval(lr, approver=approver) for _ in range(3)]
    flows.end_session(connect, approver)

    counts = []
    for _ in range(10):
        counts.append(lr.step.run_once()["sessionInvalidated"])
        if sum(counts) == 3:
            break
    assert max(counts) == 2 and sum(counts) == 3
    assert {approval_state(connect, flow) for flow in opened} == {
        ("invalidated", "authority-revoked")
    }
    assert not any(kept_tree(connect, flow["preview"]) for flow in opened)


def absent(research, source):
    del research.results[source["artifactId"]]


def changed(research, source):
    research.results[source["artifactId"]]["prepared"]["artifact"]["contentHash"] = "f" * 64


def not_exportable(research, source):
    research.results[source["artifactId"]]["availability"] = "expired"


@pytest.mark.parametrize("change", [absent, changed, not_exportable])
def test_a_definite_source_answer_invalidates_and_trims_in_one_step(
    transactions, connect, authority, tmp_path, change
):
    lr, _ = pass_rig(transactions, connect, authority, tmp_path)
    drain(transactions, lr)
    source = lr.rig.research.ready()
    flow = open_approval(lr, source=source)
    change(lr.rig.research, source)

    assert lr.step.run_once()["sourceInvalidated"] == 1
    assert approval_state(connect, flow) == ("invalidated", "source-changed")
    assert not kept_tree(connect, flow["preview"])


@pytest.mark.parametrize(
    "failure", [RuntimeError("U4 unreachable"), ResearchError("POLICY_UNRESOLVED")]
)
def test_a_source_that_could_not_be_checked_stays_approved_until_a_definite_answer(
    transactions, connect, authority, tmp_path, failure
):
    lr, _ = pass_rig(transactions, connect, authority, tmp_path)
    drain(transactions, lr)
    source = lr.rig.research.ready()
    flow = open_approval(lr, source=source)
    lr.rig.research.failure = failure

    result = lr.step.run_once()
    assert (result["sourceInvalidated"], result["sourceUnchecked"]) == (0, 1)
    assert approval_state(connect, flow) == ("approved", None)
    assert kept_tree(connect, flow["preview"])

    lr.rig.research.failure = None
    lr.rig.research.set_eligibility(source, "2")
    assert lr.step.run_once()["sourceInvalidated"] == 1
    assert approval_state(connect, flow) == ("invalidated", "source-changed")


def test_a_session_check_that_could_not_complete_leaves_the_approval_for_the_next_pass(
    transactions, connect, authority, tmp_path, monkeypatch
):
    lr, _ = pass_rig(transactions, connect, authority, tmp_path)
    drain(transactions, lr)
    approver = flows.second_session(connect, authority)
    flow = open_approval(lr, approver=approver)
    flows.end_session(connect, approver)

    def unreachable(conn, account_id, session_id):
        raise psycopg.OperationalError("guard unreachable")

    with monkeypatch.context() as patch:
        patch.setattr(housekeeping_store, "session_current", unreachable)
        result = lr.step.run_once()
    assert result["sessionInvalidated"] == 0 and result["sessionUnchecked"] >= 1
    assert approval_state(connect, flow) == ("approved", None)

    assert lr.step.run_once()["sessionInvalidated"] == 1
    assert approval_state(connect, flow) == ("invalidated", "authority-revoked")


def test_revisions_that_can_no_longer_lead_to_a_write_lose_their_tree(
    transactions, connect, authority, tmp_path
):
    lr, _ = pass_rig(transactions, connect, authority, tmp_path)
    rig = lr.rig
    # Invalidated by a connection change (a replace).
    replaced = open_approval(lr)
    token, _ = rig.new_token()
    rig.configure(token=token, expected=rig.connection()["revision"])
    assert approval_state(connect, replaced) == ("invalidated", "connection-changed")
    # Cancelled before binding.
    cancelled = open_approval(lr)
    rig.service.cancel(
        authority,
        {
            "approvalId": cancelled["approval"]["approvalId"],
            "expectedRevision": cancelled["preview"]["revision"],
        },
    )
    # A never-approved revision superseded by a newer one of its pair.
    page, source = rig.page(), rig.research.ready()
    superseded = rig.preview(page, source)
    current = rig.preview(page, source)
    # An approved, unconsumed revision superseded by a newer one keeps its tree.
    held_page, held_source = rig.page(), rig.research.ready()
    held = open_approval(lr, page=held_page, source=held_source)
    newer = rig.preview(held_page, held_source)
    assert int(newer["revision"]) == int(held["preview"]["revision"]) + 1

    drain(transactions, lr)
    assert not kept_tree(connect, replaced["preview"])
    assert not kept_tree(connect, cancelled["preview"])
    assert not kept_tree(connect, superseded)
    assert kept_tree(connect, current)
    assert kept_tree(connect, held["preview"])
    assert kept_tree(connect, newer)
    assert approval_state(connect, held) == ("approved", None)


def test_a_failing_step_does_not_stop_the_others(transactions, connect, authority, tmp_path):
    lr, double = pass_rig(transactions, connect, authority, tmp_path)
    effect = UUID(lr.rig.press(lr.rig.page())["effect"]["effectId"])

    class Faulty(OwnDue):
        def sweep_orphans(self, now):
            raise psycopg.OperationalError("store unreachable: secret detail")

    step = own_step(lr, double, [effect], repository=Faulty(lr.repo, [effect]))
    with pytest.raises(ExportPassIncomplete) as raised:
        step.run_once()
    assert raised.value.steps == ("orphans",)
    assert "secret detail" not in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__context__ is None
    # Every other step still ran, the hand-over included.
    assert [item.effect_id for item in double.offered] == [effect]
