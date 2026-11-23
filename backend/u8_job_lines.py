"""The workers' job lines (U8 plan Step 51(d); D13, NFR9.11, L1-6).

`job_line(event, job_id, origin, state=None)` writes one `docsuri.events` line with
component `workers` and event `job.started` or `job.ended`: the job's identifier, the
identifier of the request that started it only when its row names one, and its state on
`job.ended`. The earlier units' per-item hooks call it through two U8 classes:

- `CompleteAssistanceDispatch`, U3's `AssistanceDispatch` whose `_item` hook writes the
  lines from the job row's `origin_request_id`;
- `ExportItemLines`, the hook U8's composition sets on U6's export lane. The lane's
  binding carries no origin, so it reads the effect's `origin_request_id` once per item,
  in one short read through ApprovedExport's own login under the lane's own work budget
  (the one read of an ApprovedExport table by U8 code). A failed read writes the lines
  without `requestId`, beside one `job.origin-unread` line; the hook never raises into
  the lane.
"""

from __future__ import annotations

from .log_events import current
from .modules.summarization.u3_dispatch import AssistanceDispatch

STARTED, ENDED = "job.started", "job.ended"
COMPONENT = "workers"


def job_line(event: str, job_id, origin, state: str | None = None) -> dict:
    """One job line; `requestId` only when `origin` is not None (the strict log refuses
    `None`)."""
    if event not in (STARTED, ENDED):
        raise ValueError("unknown job line")
    fields = {"jobId": job_id}
    if origin is not None:
        fields["requestId"] = origin
    if event == ENDED and state is not None:
        fields["state"] = state
    return current().event(COMPONENT, event, **fields)


def item_lines(job_id, origin, state: str) -> dict:
    """`job.started` for `started`, otherwise `job.ended` with the state."""
    if state == "started":
        return job_line(STARTED, job_id, origin)
    return job_line(ENDED, job_id, origin, state)


class CompleteAssistanceDispatch(AssistanceDispatch):
    """U3's dispatch whose per-item hook writes the job lines."""

    def _item(self, job: dict, state: str) -> None:
        item_lines(job["id"], job.get("origin_request_id"), state)


class ExportItemLines:
    """The export lane's per-item hook: both lines carry the effect's origin request."""

    def __init__(self, transactions):
        self.transactions = transactions
        self._origins: dict = {}

    def __call__(self, item, state: str) -> None:
        if state == "started":
            origin = self._origins[item] = self._origin(item.effect_id)
        else:
            origin = self._origins.pop(item, None)
        item_lines(item.effect_id, origin, state)

    def _origin(self, effect_id):
        from .control_runtime import work_budget
        from .modules.export.lane import UNIT_SECONDS

        try:
            with work_budget(UNIT_SECONDS):
                row = self.transactions.run("export", lambda conn: conn.execute(
                    "SELECT origin_request_id FROM export.effect WHERE id=%s",
                    (effect_id,)).fetchone())
        except Exception as error:  # noqa: BLE001 - the hook never raises into the lane
            current().event(COMPONENT, "job.origin-unread", "warning",
                            jobId=effect_id, errorType=type(error).__name__)
            return None
        return None if row is None else row["origin_request_id"]


def with_export_item_lines(part: dict, transactions) -> dict:
    """Set `ExportItemLines` on the export lane an export contribution returns."""
    lane = part.get("lane")
    if lane is not None:
        lane.item_hook = ExportItemLines(transactions)
    return part
