"""The earlier units' per-item hooks and U8's job lines (U8 plan Steps 51(d) and 52(h);
D13, NFR9.11, L1-6).

U3's `AssistanceDispatch._item` and U6's `ExportLane.item_hook` do nothing as built: no
`docsuri.events` record, and the lane's item budget as built. U8's
`CompleteAssistanceDispatch` and `ExportItemLines` write one `job.started` and one
`job.ended` line per item, naming the job and, when its row names one, the request that
started it.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from uuid import UUID, uuid4

import pytest

from backend.artifacts import PrivateArtifacts
from backend.log_events import EVENTS_LOGGER
from backend.modules.corpus.limits import for_profile
from backend.modules.export.lane import KINDS, SKIPPED, UNIT_SECONDS, ExportLane, LaneItem
from backend.modules.export.repository import ExportRepository
from backend.modules.summarization.u3_dispatch import AssistanceDispatch
from backend.modules.summarization.u3_provider import SyntheticAssistanceExecutor
from backend.u6_policy import SYNTHETIC_EXPORT
from backend.u8_job_lines import CompleteAssistanceDispatch, ExportItemLines
from backend.u8_transactions import CompleteTransactions


def events(caplog) -> list[dict]:
    return [json.loads(record.getMessage()) for record in caplog.records
            if record.name == EVENTS_LOGGER]


def built_seconds(kind: str) -> float:
    """`ExportLane.item_seconds` as built, from the policy."""
    policy = SYNTHETIC_EXPORT
    if kind == "scan":
        return policy.scan_budget_seconds + 2 * UNIT_SECONDS
    return (2 * policy.page_read_budget_seconds + policy.write_deadline_seconds
            + policy.read_back_budget_seconds + 6 * UNIT_SECONDS)


def files_of(realm) -> PrivateArtifacts:
    return PrivateArtifacts.for_profile(realm, "corpus-files",
                                        maximum_bytes=for_profile(realm).max_source_bytes)


def lane_of(transactions) -> ExportLane:
    """A lane as U6 builds it, without a hook; the adapter and the binding check are
    never reached for an unknown effect."""
    return ExportLane(ExportRepository(transactions, SYNTHETIC_EXPORT), None, None,
                      policy=SYNTHETIC_EXPORT, clock=lambda: dt.datetime.now(dt.UTC))


def test_the_dispatch_and_export_lane_hooks_do_nothing_by_default(realm, transactions, caplog):
    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    dispatch = AssistanceDispatch(transactions, files_of(realm), SyntheticAssistanceExecutor())
    assert type(dispatch)._item is AssistanceDispatch._item
    assert dispatch._item({"id": uuid4(), "origin_request_id": uuid4()}, "started") is None
    assert events(caplog) == []
    assert ExportLane.item_hook is None
    lane = lane_of(transactions)
    assert lane.item_hook is None
    assert {kind: lane.item_seconds(kind) for kind in KINDS} == {
        kind: built_seconds(kind) for kind in KINDS}
    assert lane.run_item(LaneItem("execute", uuid4(), 1)) == SKIPPED
    assert events(caplog) == []


def test_each_job_line_names_its_job_and_its_origin_request(realm, transactions, caplog):
    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    dispatch = CompleteAssistanceDispatch(transactions, files_of(realm),
                                          SyntheticAssistanceExecutor())
    job, origin = uuid4(), uuid4()
    dispatch._item({"id": job, "origin_request_id": origin}, "started")
    dispatch._item({"id": job, "origin_request_id": origin}, "executed")
    started, ended = events(caplog)
    assert set(started) == {"ts", "level", "component", "event", "jobId", "requestId"}
    assert (started["component"], started["event"], UUID(started["jobId"]),
            UUID(started["requestId"])) == ("workers", "job.started", job, origin)
    assert set(ended) == {"ts", "level", "component", "event", "jobId", "requestId", "state"}
    assert (ended["event"], ended["state"], UUID(ended["requestId"])) == (
        "job.ended", "executed", origin)
    caplog.clear()
    dispatch._item({"id": job, "origin_request_id": None}, "started")
    assert "requestId" not in events(caplog)[0]

    # The export lane's hook, for an effect no row names: both lines, no requestId.
    complete = CompleteTransactions(realm)
    hook = ExportItemLines(complete)
    item = LaneItem("execute", uuid4(), 1)
    caplog.clear()
    hook(item, "started")
    hook(item, SKIPPED)
    lines = events(caplog)
    assert [(line["event"], line.get("state")) for line in lines] == [
        ("job.started", None), ("job.ended", SKIPPED)]
    assert all("requestId" not in line and UUID(line["jobId"]) == item.effect_id
               for line in lines)
    # With its transactions closed, the lines still come, beside one unread line.
    complete.close()
    caplog.clear()
    hook(item, "started")
    hook(item, SKIPPED)
    lines = events(caplog)
    assert [line["event"] for line in lines] == ["job.origin-unread", "job.started",
                                                 "job.ended"]
    assert lines[0]["errorType"] == "ValueError"
    assert all("requestId" not in line for line in lines)

    lane = lane_of(transactions)
    lane.item_hook = ExportItemLines(transactions)
    for kind in KINDS:
        assert lane.item_seconds(kind) == pytest.approx(built_seconds(kind) + 5.0)
    assert UNIT_SECONDS == 5.0
