"""Writing a copy onto the backup volume (U8 plan Step 26; BR4.3, BR6.10, BR9.12, NFR3.13;
Workflow 19 steps 2–6 and its error paths).

A digest that differs removes the staging file and the partial archive and marks both
disposed; the dump's table of contents must list every table the agent saw; a ledger
copy's chain must verify; a decided date earlier than 14 days, or one without its
receipt, is refused; and the earlier tool's archive write never replaces a file.
"""

from __future__ import annotations

import datetime as dt
import stat
from uuid import uuid4

import pytest

from docsuri_ops.backup_agent.catalogue import Catalogue
from docsuri_ops.backup_agent.writing import AgentRefused, ArchiveWriter, Decided
from tests.u8_service_operations_integration import agent_flows as af


@pytest.fixture
def rig(tmp_path, clock):
    return af.build(tmp_path, clock)


def writer(rig) -> tuple[ArchiveWriter, Catalogue]:
    catalogue = Catalogue.open(rig.u8, clock=rig.clock)
    return ArchiveWriter(rig.config, catalogue, clock=rig.clock,
                         volume=rig.context.volume), catalogue


def listing(rig) -> tuple[list[str], list[str]]:
    return (sorted(path.name for path in (rig.u8 / "staging").iterdir()),
            sorted(path.name for path in (rig.u8 / "archives").iterdir()))


def test_a_digest_that_differs_removes_both_files_and_marks_both_disposed(rig):
    write, catalogue = writer(rig)
    record = str(uuid4())
    with pytest.raises(AgentRefused) as refused:
        write.write("ledger-copy", record_id=record, fill=lambda sink: sink.write(b"bytes\n"),
                    integrity=lambda archive: True, sender_digest="0" * 64)
    assert refused.value.reason == "digest-mismatch"
    assert listing(rig) == ([], [])
    files = catalogue.files()
    assert {entry.state for entry in files.values()} == {"disposed"} and len(files) == 2
    assert {entry.record_id for entry in files.values()} == {record}
    catalogue.close()


def test_a_failing_fill_removes_its_staging_file(rig):
    write, catalogue = writer(rig)

    def broken(sink):
        sink.write(b"partial")
        raise OSError("the volume went away")

    with pytest.raises(AgentRefused) as refused:
        write.write("live-set", record_id=str(uuid4()), fill=broken,
                    integrity=lambda archive: True)
    assert (refused.value.reason, refused.value.facts) == ("write-failed",
                                                          {"category": "OSError"})
    assert listing(rig) == ([], [])
    catalogue.close()


def test_the_table_of_contents_must_list_every_table_seen(tmp_path, clock):
    rig = af.build(tmp_path, clock, tools=af.FakeTools(listed={"accounts.account"}))
    failed = af.backed_up(rig)
    assert failed["integrity"] == "failed"  # kept as evidence, never restored
    rig.tools.listed = set(af.TABLES) | {"extra.table"}
    rig.clock.advance(60)
    passed = af.backed_up(rig)
    assert passed["integrity"] == "passed" and passed["size"] > 0
    archive = rig.u8 / passed["location"]
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert listing(rig)[0] == []  # the staging file is gone
    files = Catalogue.open(rig.u8, clock=rig.clock).files()
    assert files[passed["location"]].sha256 == passed["sha256"]
    assert files[failed["location"]].integrity == "failed"


def test_a_ledger_copys_chain_must_verify(rig, tmp_path, clock):
    copy = af.ledger_copy_bytes(tmp_path, clock)
    status, result, _ = af.invoke(rig, "ledger-copy", copy, caller=af.SCHEDULER)
    assert status == 0 and result["integrity"] == "passed"
    assert result["recordKind"] == "LedgerCopy" and result["copyKind"] == "ledger-copy"
    forged = copy.replace(b'"n":1', b'"n":9', 1)
    rig.clock.advance(60)
    status, result, _ = af.invoke(rig, "ledger-copy", forged, caller=af.SCHEDULER)
    assert status == 0 and result["integrity"] == "failed"
    rig.clock.advance(60)
    status, result, _ = af.invoke(rig, "ledger-copy", b"", caller=af.SCHEDULER)
    assert result["integrity"] == "failed"


def decided(rig, days: float, **overrides) -> dict:
    value = {"date": (rig.clock() + dt.timedelta(days=days)).isoformat(),
             "receipt": str(uuid4()), "subjectDigest": "d" * 64, **overrides}
    return value


def test_a_decided_date_below_the_minimum_or_without_its_receipt_is_refused(rig):
    for document, reason in (
        ({"recordId": str(uuid4()), "decided": decided(rig, 13)}, "decided-date-too-early"),
        ({"recordId": str(uuid4())}, "decided-date-refused"),
        ({"recordId": str(uuid4()), "decided": {"date": decided(rig, 30)["date"]}},
         "decided-date-refused"),
        ({"recordId": str(uuid4()), "decided": decided(rig, 30, receipt="not-a-receipt")},
         "decided-date-refused"),
        ({"recordId": str(uuid4()), "decided": decided(rig, 30, date="tomorrow")},
         "decided-date-refused"),
    ):
        status, result, _ = af.invoke(rig, "rollback-copy", document)
        assert (status, result["reason"]) == (1, reason)
    assert listing(rig) == ([], [])
    choice = decided(rig, 30)
    status, result, _ = af.invoke(rig, "rollback-copy", {"recordId": str(uuid4()),
                                                         "decided": choice})
    assert status == 0 and result["decisionReceipt"] == choice["receipt"]
    assert result["copyKind"] == "rolled-back-copy" and result["recordKind"] == "RetainedCopy"
    assert result["disposeAfter"] == dt.datetime.fromisoformat(choice["date"]).isoformat()
    # A decided date is refused where the kind's time comes from the retention policy.
    write, catalogue = writer(rig)
    with pytest.raises(AgentRefused) as refused:
        write.write("live-set", record_id=str(uuid4()), fill=lambda sink: None,
                    integrity=lambda archive: True, decided=Decided.parse(decided(rig, 30)))
    assert refused.value.reason == "decided-date-refused"
    catalogue.close()


def test_retention_follows_the_seoul_sunday(rig):
    write, catalogue = writer(rig)
    # 2026-10-25 is a Sunday in Seoul from 2026-10-24T15:00Z.
    rig.clock.now = dt.datetime(2026, 10, 24, 15, 30, tzinfo=dt.UTC)
    sunday = write.write("live-set", record_id=str(uuid4()), fill=lambda sink: sink.write(b"s"),
                         integrity=lambda archive: True)
    rig.clock.now = dt.datetime(2026, 10, 26, 3, 0, tzinfo=dt.UTC)
    monday = write.write("live-set", record_id=str(uuid4()), fill=lambda sink: sink.write(b"m"),
                         integrity=lambda archive: True)
    catalogue.close()
    assert dt.datetime.fromisoformat(sunday["disposeAfter"]) == dt.datetime(
        2026, 10, 24, 15, 30, tzinfo=dt.UTC) + dt.timedelta(weeks=8)
    assert dt.datetime.fromisoformat(monday["disposeAfter"]) == dt.datetime(
        2026, 10, 26, 3, 0, tzinfo=dt.UTC) + dt.timedelta(days=14)


def test_the_archive_write_never_replaces_a_file(rig):
    write, catalogue = writer(rig)
    record = str(uuid4())
    first = write.write("live-set", record_id=record, fill=lambda sink: sink.write(b"one"),
                        integrity=lambda archive: True)
    before = (rig.u8 / first["location"]).read_bytes()
    with pytest.raises(AgentRefused) as refused:  # the same name in the same second
        write.write("live-set", record_id=record, fill=lambda sink: sink.write(b"two"),
                    integrity=lambda archive: True)
    assert refused.value.reason == "archive-exists"
    assert (rig.u8 / first["location"]).read_bytes() == before
    # A file the catalogue does not know, already at the name: the write refuses, and
    # the file is left exactly as it was.
    rig.clock.advance(5)
    other = str(uuid4())
    stamp = rig.clock().astimezone(dt.UTC).strftime("%Y%m%dT%H%M%S")
    stray = rig.u8 / "archives" / f"live-set-{stamp}-{other}.archive"
    stray.write_bytes(b"not the agent's")
    with pytest.raises(AgentRefused) as refused:
        write.write("live-set", record_id=other, fill=lambda sink: sink.write(b"three"),
                    integrity=lambda archive: True)
    assert refused.value.reason == "archive-exists"
    assert stray.read_bytes() == b"not the agent's" and listing(rig)[0] == []
    catalogue.close()


def test_stream_back_sends_one_catalogued_file_with_its_digest_and_nothing_else(rig):
    import hashlib

    written = af.backed_up(rig)
    entry = {"path": written["location"], "sha256": written["sha256"]}
    status, result, payload = af.invoke(rig, "stream-back", entry)
    assert status == 0 and hashlib.sha256(payload).hexdigest() == written["sha256"]
    assert (result["size"], result["recordKind"]) == (len(payload), "BackupSet")
    for document, reason in (
        ({"path": written["location"], "sha256": "0" * 64}, "not-catalogued"),
        ({"path": "staging/anything", "sha256": written["sha256"]}, "path-refused"),
        ({"path": "../escape", "sha256": written["sha256"]}, "path-refused"),
        ({"path": written["location"]}, "input-field-refused"),
    ):
        status, result, payload = af.invoke(rig, "stream-back", document)
        assert (status, result["reason"], payload) == (1, reason, b"")
    (rig.u8 / written["location"]).write_bytes(b"altered")
    status, result, payload = af.invoke(rig, "stream-back", entry)
    assert (status, result["reason"], payload) == (1, "digest-mismatch", b"")


def _instant(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


MONDAY = dt.datetime(2026, 10, 26, 3, 0, tzinfo=dt.UTC)
SEOUL_SUNDAY = dt.datetime(2026, 10, 24, 15, 30, tzinfo=dt.UTC)  # Sunday 00:30 in Seoul


def test_each_file_is_catalogued_with_its_disposal_point_before_its_first_byte(rig):
    """L1-2: the archive's entry carries its disposal point, and the staging entry its
    one-day backstop, from their first `file.writing` entry, before the first byte."""
    write, catalogue = writer(rig)
    day = dt.timedelta(days=1)
    cases = [
        ("live-set", MONDAY, None, MONDAY + 14 * day),
        ("rehearsal-set", MONDAY, None, MONDAY + 14 * day),
        ("ledger-copy", MONDAY, None, MONDAY + 14 * day),
        ("dry-run-snapshot", MONDAY, None, MONDAY + 14 * day),
        ("live-set", SEOUL_SUNDAY, None, SEOUL_SUNDAY + 56 * day),
        ("final-snapshot", MONDAY, 120, MONDAY + 120 * day),
        ("rolled-back-copy", MONDAY, 30, MONDAY + 30 * day),
    ]
    try:
        for kind, now, decided_days, expected in cases:
            # The plan's literal instants: each name already carries its record id.
            rig.clock.now = now
            record = str(uuid4())
            choice = None
            if decided_days is not None:
                choice = Decided(expected, str(uuid4()), "d" * 64)
            seen: dict = {}

            def fill(sink, record=record, seen=seen):
                entries = [entry for entry in catalogue.files().values()
                           if entry.record_id == record]
                seen.update({entry.path.split("/", 1)[0]: entry for entry in entries})
                sink.write(b"first byte")

            receipt = write.write(kind, record_id=record, fill=fill,
                                  integrity=lambda archive: True, decided=choice)
            assert set(seen) == {"archives", "staging"}, kind
            for entry in seen.values():
                assert entry.state == "writing" and entry.record_kind == receipt["recordKind"]
            assert _instant(seen["archives"].dispose_after) == expected, kind
            assert _instant(seen["staging"].dispose_after) == (
                rig.clock.now + dt.timedelta(seconds=86400)), kind
            after = catalogue.files()
            assert _instant(after[receipt["location"]].dispose_after) == _instant(
                receipt["disposeAfter"]) == expected, kind
            assert after[receipt["stagingLocation"]].state == "disposed"
    finally:
        catalogue.close()


def test_a_sunday_ledger_copy_is_kept_eight_weeks(rig, tmp_path, clock):
    """L1-24: a ledger copy is kept by its own write time, as a set is."""
    copy = af.ledger_copy_bytes(tmp_path, clock)
    for written_at, expected in (
        (dt.datetime(2026, 10, 24, 15, 0, tzinfo=dt.UTC),      # Sunday 00:00 in Seoul
         dt.datetime(2026, 12, 19, 15, 0, tzinfo=dt.UTC)),
        (dt.datetime(2026, 10, 24, 14, 59, 59, tzinfo=dt.UTC),  # Saturday 23:59:59 in Seoul
         dt.datetime(2026, 11, 7, 14, 59, 59, tzinfo=dt.UTC)),
        (MONDAY, dt.datetime(2026, 11, 9, 3, 0, tzinfo=dt.UTC)),
    ):
        rig.clock.now = written_at
        status, result, _ = af.invoke(rig, "ledger-copy", copy, caller=af.SCHEDULER)
        assert status == 0 and result["integrity"] == "passed", result
        assert _instant(result["disposeAfter"]) == expected


def test_an_unknown_kind_is_refused(rig):
    write, catalogue = writer(rig)
    with pytest.raises(AgentRefused) as refused:
        write.write("anything", record_id=str(uuid4()), fill=lambda sink: None,
                    integrity=lambda archive: True)
    assert refused.value.reason == "kind-refused"
    catalogue.close()
