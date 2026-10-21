"""D4 against the realm: an unconsumed approval ends with its approving session. On the
next worker pass, through the shared control loop, AccountAccess's own guard reports the
session ended, and the approval is invalidated (authority-revoked) and trimmed in the same
step; an accepted export of that session is invalidated by the lane's pre-write check
and nothing is written (security design §10, §13 "Approvals"; BR3.3, BR3.4, NFR4.9)."""

from uuid import UUID

from backend.control_runtime import ControlLoop
from backend.modules.export.worker import ExportWorker

from tests.u6_approved_export import lane_flows as lf
from tests.u6_approved_export import store_flows as flows


class Inherited:
    def run_once(self, limit=1):
        return {}


def test_an_approval_whose_session_ended_is_invalidated_and_trimmed_on_the_next_pass(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path, lane=lf.LaneDouble(idle=False))
    lr.rig.configure()
    lf.drain(transactions, lr)
    approver = flows.second_session(connect, authority)
    preview = lr.rig.preview(lr.rig.page())
    approval = lr.rig.approve(preview, authority=approver)
    approval_id = UUID(approval["approvalId"])
    loop = ControlLoop(ExportWorker(Inherited(), lr.step))

    # While the session is current, a pass leaves the approval and its copy alone.
    loop.pass_once()
    assert flows.approval_row(connect, approval_id)["state"] == "approved"
    kept = flows.revision_row(connect, UUID(preview["previewId"]), int(preview["revision"]))
    assert kept["rendered_blocks"] is not None

    flows.end_session(connect, approver)
    loop.pass_once()
    row = flows.approval_row(connect, approval_id)
    assert (row["state"], row["invalidation_reason"]) == ("invalidated", "authority-revoked")
    trimmed = flows.revision_row(connect, UUID(preview["previewId"]), int(preview["revision"]))
    assert trimmed["rendered_blocks"] is None and trimmed["rendered_text"] is None
    assert trimmed["trimmed_at"] == lr.clock.now
    # The owner sees it as not continuable, with its reason.
    [entry] = [
        item
        for item in lr.rig.service.history(authority, {})["entries"]
        if item["approvalId"] == approval["approvalId"]
    ]
    assert (entry["state"], entry["invalidationReason"]) == ("invalidated", "authority-revoked")
    assert entry["continuable"] is False


def test_an_accepted_export_of_an_ended_session_is_invalidated_before_any_write(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    lr.rig.configure()
    approver = flows.second_session(connect, authority)
    preview = lr.rig.preview(lr.rig.page())
    approval = lr.rig.approve(preview, authority=approver)
    effect = lr.rig.execute(approval, authority=approver)
    flows.end_session(connect, approver)

    assert lr.lane.run_item(lf.item(effect)) == "invalidated"
    row = lf.row(connect, effect)
    assert (row["state"], row["outcome_reason"]) == ("invalidated", "authority-revoked")
    assert lr.fake.writes == []
