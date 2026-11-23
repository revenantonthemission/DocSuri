"""Deleting on the backup volume (U8 plan Step 26; BR9.17, NFR3.13, A6's compatibility list;
Workflow 19 steps 8–10).

A forged ledger record cannot make the agent delete a file early, outside U8's folder,
through a link, with a changed digest or past the retention floor; a forged
RetainedCopy with a past `disposeAfter` does not bring a rolled-back copy forward; the
staging sweep removes only what is past its backstop; and a rebuilt catalogue keeps each
file's later disposal time.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import replace
from uuid import uuid4

import pytest

from backend.u8_policy import PRODUCTION_OPERATIONS
from docsuri_ops.backup_agent.catalogue import Catalogue
from docsuri_ops.backup_agent.config import Login, Retention, write
from docsuri_ops.backup_agent.writing import ArchiveWriter
from tests.u8_service_operations_integration import agent_flows as af

DAY = 86400


@pytest.fixture
def clock():
    """The injected clock, started on a Tuesday at noon in Seoul (03:00 UTC) of the
    current week. These tests space sets a day apart and expect the 14-day daily
    retention; a set that falls on a Seoul Sunday is kept 8 weeks instead (`writing.py`),
    so a clock started at real time failed whenever a later set crossed into a Sunday in
    Seoul (as on 2026-10-24, 00:34 Seoul time, a Saturday)."""
    from tests.u8_service_operations_integration.conftest import Clock

    now = dt.datetime.now(dt.UTC)
    tuesday = (now - dt.timedelta(days=(now.weekday() - 1) % 7)).replace(
        hour=3, minute=0, second=0, microsecond=0)
    return Clock(tuesday)


@pytest.fixture
def rig(tmp_path, clock):
    return af.build(tmp_path, clock)


def files(rig) -> dict:
    catalogue = Catalogue.open(rig.u8, clock=rig.clock)
    try:
        return catalogue.files()
    finally:
        catalogue.close()


def due_pass(rig, document=None) -> dict:
    status, result, _ = af.invoke(rig, "dispose-due", document or {}, caller=af.SCHEDULER)
    assert status == 0, result
    return result


def test_nothing_is_deleted_before_the_time_the_agent_recorded(rig):
    written = af.backed_up(rig)
    # A forged ledger claim with a past disposal point is refused and reported.
    report = due_pass(rig, {"ledgerPaths": [written["location"]], "claims": [
        {"path": written["location"], "disposeAfter": "2020-01-01T00:00:00Z"}]})
    assert report["disposed"] == [] and report["refusedClaims"] == [written["location"]]
    assert (rig.u8 / written["location"]).is_file()
    rig.clock.advance(15 * DAY)  # past the 14-day retention
    report = due_pass(rig, {"ledgerPaths": [written["location"]]})
    assert report["disposed"] == [written["location"]] and report["unrecorded"] == []
    assert not (rig.u8 / written["location"]).exists()
    assert files(rig)[written["location"]].state == "disposed"


def test_a_due_file_the_ledger_does_not_know_is_deleted_and_reported(rig):
    written = af.backed_up(rig)
    rig.clock.advance(15 * DAY)
    report = due_pass(rig, {"ledgerPaths": []})
    assert report["disposed"] == report["unrecorded"] == [written["location"]]


def test_a_link_or_a_changed_digest_is_never_followed_or_deleted(rig, tmp_path):
    linked, changed = af.backed_up(rig), None
    rig.clock.advance(60)
    changed = af.backed_up(rig, record_id=str(uuid4()))
    target = tmp_path / "outside.txt"
    target.write_bytes(b"outside U8's folder")
    link = rig.u8 / linked["location"]
    os.unlink(link)
    os.symlink(target, link)
    (rig.u8 / changed["location"]).write_bytes(b"altered after it was written")
    rig.clock.advance(15 * DAY)
    report = due_pass(rig)
    assert report["refused"] == [linked["location"]] and report["disposed"] == []
    assert target.read_bytes() == b"outside U8's folder" and link.is_symlink()
    assert report["mismatched"] == [changed["location"]]
    assert (rig.u8 / changed["location"]).read_bytes() == b"altered after it was written"
    # Only in person, after you are shown the mismatch, is it deleted.
    status, result, _ = af.invoke(rig, "dispose-mismatch", {"path": changed["location"]})
    assert status == 0 and not (rig.u8 / changed["location"]).exists()


@pytest.mark.parametrize("path", ["../outside.archive", "/etc/passwd", "archives/../x",
                                  "staging/x"])
def test_a_path_outside_u8s_archives_is_refused(rig, path):
    status, result, _ = af.invoke(rig, "dispose-event", {"path": path, "event": "run-ended"})
    assert status == 1 and result["reason"] in ("not-catalogued", "path-refused")


def test_the_retention_floor_holds_the_newest_passed_set_of_a_living_incarnation(rig):
    rig.tools.living = {"docsuri_u8:4242"}
    older = af.backed_up(rig)
    rig.clock.advance(DAY)
    newest = af.backed_up(rig, record_id=str(uuid4()))
    rig.clock.advance(30 * DAY)
    report = due_pass(rig)
    assert report["disposed"] == [older["location"]] and report["held"] == [newest["location"]]
    assert files(rig)[newest["location"]].state == "held"
    # Once that incarnation no longer exists, the floor releases it, and it is due.
    rig.tools.living = set()
    report = due_pass(rig)
    assert report["released"] == report["disposed"] == [newest["location"]]


def test_a_forged_retained_copy_does_not_bring_a_rolled_back_copy_forward(rig):
    when = rig.clock() + dt.timedelta(days=30)
    status, copy, _ = af.invoke(rig, "rollback-copy", {"recordId": str(uuid4()), "decided": {
        "date": when.isoformat(), "receipt": str(uuid4()), "subjectDigest": "e" * 64}})
    assert status == 0
    rig.clock.advance(20 * DAY)
    report = due_pass(rig, {"ledgerPaths": [copy["location"]], "claims": [
        {"path": copy["location"], "disposeAfter": rig.clock().isoformat()}]})
    assert report["refusedClaims"] == [copy["location"]] and report["disposed"] == []
    assert (rig.u8 / copy["location"]).is_file()
    # Nor can an event delete it: a rolled-back copy has no disposal event.
    status, result, _ = af.invoke(rig, "dispose-event", {"path": copy["location"],
                                                         "event": "run-ended"})
    assert (status, result["reason"]) == (1, "event-refused")


def test_your_decision_brings_a_date_forward_but_never_below_the_minimum(rig):
    when = rig.clock() + dt.timedelta(days=60)
    status, copy, _ = af.invoke(rig, "rollback-copy", {"recordId": str(uuid4()), "decided": {
        "date": when.isoformat(), "receipt": str(uuid4()), "subjectDigest": "f" * 64}})

    def set_date(days: float) -> tuple[int, dict]:
        document = {"path": copy["location"], "decided": {
            "date": (rig.clock() + dt.timedelta(days=days)).isoformat(),
            "receipt": str(uuid4()), "subjectDigest": "f" * 64}}
        status, result, _ = af.invoke(rig, "set-date", document)
        return status, result

    assert set_date(10)[1]["reason"] == "decided-date-too-early"
    assert set_date(90)[1]["reason"] == "decided-date-not-earlier"
    status, result = set_date(20)
    assert status == 0 and files(rig)[copy["location"]].decision_receipt == result[
        "decisionReceipt"]
    rig.clock.advance(21 * DAY)
    assert due_pass(rig)["disposed"] == [copy["location"]]


def test_a_dry_run_snapshot_and_a_rehearsal_set_go_on_their_events(rig):
    write(rig.context.folder, replace(rig.config, v1_database="docsuri",
                                      v1_login=Login("127.0.0.1", 15510, "docsuri_v1_reader",
                                                     "v1-login")))
    status, snapshot, _ = af.invoke(rig, "snapshot", {"kind": "dry-run-snapshot",
                                                      "recordId": str(uuid4())})
    assert status == 0 and snapshot["copyKind"] == "dry-run-snapshot"
    rehearsal = af.backed_up(rig, "docsuri_u8_rehearsal_0123456789ab")
    assert af.invoke(rig, "dispose-event", {"path": snapshot["location"],
                                            "event": "rehearsal-database-removed"})[1][
        "reason"] == "event-refused"
    for path, event in ((snapshot["location"], "run-ended"),
                        (rehearsal["location"], "rehearsal-database-removed")):
        status, result, _ = af.invoke(rig, "dispose-event", {"path": path, "event": event})
        assert status == 0 and not (rig.u8 / path).exists()


class CutShort(BaseException):
    """A write stopped after its `begin`, past `write`'s `except Exception`."""


def cut_short_write(rig, kind: str = "live-set") -> str:
    """A write cut short after its `begin`: both entries stay `writing`. Returns its
    record id."""
    catalogue = Catalogue.open(rig.u8, clock=rig.clock)
    writer = ArchiveWriter(rig.config, catalogue, clock=rig.clock, volume=rig.context.volume)
    record = str(uuid4())

    def fill(sink):
        sink.write(b"partial")
        raise CutShort

    try:
        with pytest.raises(CutShort):
            writer.write(kind, record_id=record, fill=fill, integrity=lambda archive: True)
    finally:
        catalogue.close()
    return record


def test_the_staging_sweep_removes_only_what_is_past_its_backstop(rig):
    staging = rig.u8 / "staging"
    old, fresh = staging / "left-by-a-crash", staging / "being-written"
    for path in (old, fresh):
        path.write_bytes(b"partial")
    stamp = (rig.clock() - dt.timedelta(days=2)).timestamp()
    os.utime(old, (stamp, stamp))
    report = due_pass(rig)
    assert report["swept"] == 1 and not old.exists() and fresh.exists()
    fresh.unlink()
    # A write cut short after its `begin`, with a partial file at its archive's path.
    record = cut_short_write(rig)
    entries = {path: entry for path, entry in files(rig).items() if entry.record_id == record}
    assert {entry.state for entry in entries.values()} == {"writing"} and len(entries) == 2
    archive_rel = next(path for path in entries if path.startswith("archives/"))
    staging_rel = next(path for path in entries if path.startswith("staging/"))
    (rig.u8 / archive_rel).write_bytes(b"partial archive")
    literal = dt.datetime(2026, 11, 3, 3, 0, tzinfo=dt.UTC)
    for relative in (archive_rel, staging_rel):
        os.utime(rig.u8 / relative, (literal.timestamp(), literal.timestamp()))
    rig.clock.now = literal + dt.timedelta(seconds=86399)
    due_pass(rig)
    assert (rig.u8 / archive_rel).exists() and (rig.u8 / staging_rel).exists()
    assert {files(rig)[path].state for path in entries} == {"writing"}
    rig.clock.now = literal + dt.timedelta(seconds=86401)
    due_pass(rig)
    assert not (rig.u8 / archive_rel).exists() and not (rig.u8 / staging_rel).exists()
    assert {files(rig)[path].state for path in entries} == {"disposed"}
    # A successful backup leaves its staging entry disposed and staging/ empty.
    written = af.backed_up(rig)
    assert files(rig)[written["stagingLocation"]].state == "disposed"
    assert list(staging.iterdir()) == []
    assert Retention.from_policy(PRODUCTION_OPERATIONS).staging_backstop_seconds == 86400


def literal_rig(tmp_path, start: dt.datetime, **options) -> af.Rig:
    from tests.u8_service_operations_integration.conftest import Clock

    return af.build(tmp_path, Clock(start), **options)


def decided_document(rig, date: dt.datetime) -> dict:
    return {"date": date.isoformat(), "receipt": str(uuid4()), "subjectDigest": "a" * 64}


def test_each_decided_volume_copy_is_deleted_at_its_date_and_not_before(tmp_path):
    week = dt.datetime(2026, 11, 2, 0, 0, tzinfo=dt.UTC)  # W
    rig = literal_rig(tmp_path, week)
    write(rig.context.folder, replace(rig.config, v1_database="docsuri",
                                      v1_login=Login("127.0.0.1", 15510, "docsuri_v1_reader",
                                                     "v1-login")))
    deadline = dt.datetime(2026, 12, 2, 0, 0, tzinfo=dt.UTC)  # D = W + 30 days
    status, copy, _ = af.invoke(rig, "rollback-copy", {
        "recordId": str(uuid4()), "decided": decided_document(rig, deadline)})
    assert status == 0 and dt.datetime.fromisoformat(copy["disposeAfter"]) == deadline
    switch_start = dt.datetime(2027, 3, 2, 0, 0, tzinfo=dt.UTC)  # W + 120 days (L1-3)
    status, snapshot, _ = af.invoke(rig, "snapshot", {
        "kind": "final-snapshot", "recordId": str(uuid4()),
        "decided": decided_document(rig, switch_start)})
    assert status == 0 and dt.datetime.fromisoformat(snapshot["disposeAfter"]) == switch_start
    # The settlement moves the snapshot to 30 days after it, with the decision's receipt.
    settled = dt.datetime(2026, 11, 9, 0, 0, tzinfo=dt.UTC)  # T
    moved = dt.datetime(2026, 12, 9, 0, 0, tzinfo=dt.UTC)  # T + 30 days
    rig.clock.now = settled
    decision = decided_document(rig, moved)
    status, result, _ = af.invoke(rig, "set-date", {"path": snapshot["location"],
                                                    "decided": decision})
    assert status == 0 and result["decisionReceipt"] == decision["receipt"]
    entry = files(rig)[snapshot["location"]]
    assert entry.decision_receipt == decision["receipt"]
    assert dt.datetime.fromisoformat(entry.dispose_after.replace("Z", "+00:00")) == moved
    for later in (moved, moved + dt.timedelta(days=1)):
        status, refused, _ = af.invoke(rig, "set-date", {
            "path": snapshot["location"], "decided": decided_document(rig, later)})
        assert (status, refused["reason"]) == (1, "decided-date-not-earlier")
    # The rolled-back copy: kept one second before its date, deleted at it.
    rig.clock.now = deadline - dt.timedelta(seconds=1)
    assert due_pass(rig)["disposed"] == [] and (rig.u8 / copy["location"]).is_file()
    rig.clock.now = deadline
    assert due_pass(rig)["disposed"] == [copy["location"]]
    assert not (rig.u8 / copy["location"]).exists()
    # The final snapshot: kept one second before its new date, deleted at it.
    rig.clock.now = moved - dt.timedelta(seconds=1)
    assert due_pass(rig)["disposed"] == [] and (rig.u8 / snapshot["location"]).is_file()
    rig.clock.now = moved
    assert due_pass(rig)["disposed"] == [snapshot["location"]]


def live_states(rig, kind: str) -> set[str]:
    return {path for path, entry in files(rig).items()
            if path.startswith(f"archives/{kind}-") and entry.state != "disposed"}


def test_daily_runs_keep_at_most_twenty_two_live_sets(tmp_path):
    start = dt.datetime(2026, 10, 24, 19, 0, tzinfo=dt.UTC)  # Sunday 2026-10-25 04:00 Seoul
    rig = literal_rig(tmp_path, start)
    rig.tools.living = {"docsuri_u8:4242"}
    copy = af.ledger_copy_bytes(tmp_path, rig.clock)
    sets: dict[str, dt.datetime] = {}
    copies: dict[str, dt.datetime] = {}
    first_set = first_copy = None
    for day in range(58):
        rig.clock.now = start + dt.timedelta(days=day)
        written = af.backed_up(rig)
        status, ledger_copy, _ = af.invoke(rig, "ledger-copy", copy, caller=af.SCHEDULER)
        assert status == 0 and ledger_copy["integrity"] == "passed", ledger_copy
        keep = 56 if day % 7 == 0 else 14
        sets[written["location"]] = rig.clock.now + dt.timedelta(days=keep)
        copies[ledger_copy["location"]] = rig.clock.now + dt.timedelta(days=keep)
        for receipt in (written, ledger_copy):
            assert dt.datetime.fromisoformat(receipt["disposeAfter"]) == (
                rig.clock.now + dt.timedelta(days=keep))
        if day == 0:
            first_set, first_copy = written["location"], ledger_copy["location"]
        due_pass(rig)
        now = rig.clock.now
        live_sets = live_states(rig, "live-set")
        live_copies = live_states(rig, "ledger-copy")
        assert live_sets == {path for path, until in sets.items() if until > now}, day
        assert live_copies == {path for path, until in copies.items() if until > now}, day
        assert len(live_sets) <= 22 and len(live_copies) <= 22, day
        if day == 55:
            assert {first_set, first_copy} <= live_sets | live_copies
        if day == 56:
            assert sets[first_set] == copies[first_copy] == now
            assert first_set not in live_sets and first_copy not in live_copies


MONDAY = dt.datetime(2026, 10, 26, 3, 0, tzinfo=dt.UTC)


def test_the_floor_keeps_the_newest_verified_ledger_copy(tmp_path):
    rig = literal_rig(tmp_path, MONDAY)
    chain = af.ledger_copy_bytes(tmp_path, rig.clock)
    forged = chain.replace(b'"n":1', b'"n":9', 1)
    written = []
    for day, body in enumerate((chain, chain, forged)):
        rig.clock.now = MONDAY + dt.timedelta(days=day)
        status, result, _ = af.invoke(rig, "ledger-copy", body, caller=af.SCHEDULER)
        assert status == 0, result
        written.append(result)
    older, newer, failed = (result["location"] for result in written)
    assert [result["integrity"] for result in written] == ["passed", "passed", "failed"]
    rig.clock.now = MONDAY + dt.timedelta(days=2 + 14, seconds=1)
    report = due_pass(rig)
    assert report["held"] == [newer] and sorted(report["disposed"]) == sorted([older, failed])
    assert files(rig)[newer].state == "held"
    status, fourth, _ = af.invoke(rig, "ledger-copy", chain, caller=af.SCHEDULER)
    assert status == 0 and fourth["integrity"] == "passed"
    report = due_pass(rig)
    assert report["released"] == report["disposed"] == [newer]
    assert files(rig)[fourth["location"]].state == "written"


def test_the_floor_keeps_the_newest_passed_set_of_each_living_database(tmp_path):
    rig = literal_rig(tmp_path, MONDAY)
    production, rehearsal = "docsuri_u8", "docsuri_u8_rehearsal_0123456789ab"
    rig.tools.living = {f"{production}:4242", f"{rehearsal}:4242"}
    made: dict[str, list[str]] = {production: [], rehearsal: []}
    for day in range(2):
        rig.clock.now = MONDAY + dt.timedelta(days=day)
        for database in (production, rehearsal):
            made[database].append(af.backed_up(rig, database, record_id=str(uuid4()))["location"])
    rig.clock.now = MONDAY + dt.timedelta(days=1 + 14, seconds=1)
    report = due_pass(rig)
    assert sorted(report["held"]) == sorted([made[production][1], made[rehearsal][1]])
    assert sorted(report["disposed"]) == sorted([made[production][0], made[rehearsal][0]])
    rig.tools.living = {f"{production}:4242"}
    report = due_pass(rig)
    assert report["released"] == report["disposed"] == [made[rehearsal][1]]
    assert files(rig)[made[production][1]].state == "held"


def test_a_rebuilt_catalogue_keeps_each_files_later_disposal_time(rig):
    written = af.backed_up(rig)
    recorded = files(rig)[written["location"]].dispose_after
    log = rig.u8 / "catalogue.jsonl"
    log.write_bytes(log.read_bytes() + b'{"torn": "not a chained entry"}\n')
    assert af.invoke(rig, "status", caller=af.SCHEDULER)[1]["catalogue"] == "damaged"
    earlier = "2026-01-01T00:00:00Z"
    status, result, _ = af.invoke(rig, "rebuild-catalogue", {"records": {
        written["location"]: {"recordId": written["recordId"], "recordKind": "BackupSet",
                              "disposeAfter": earlier, "integrity": "passed"}}})
    assert status == 0 and result == {"ok": True, "files": 1, "unrecorded": []}
    assert files(rig)[written["location"]].dispose_after == recorded  # the later one kept
    assert any(path.name.startswith("catalogue.jsonl.damaged-") for path in rig.u8.iterdir())
