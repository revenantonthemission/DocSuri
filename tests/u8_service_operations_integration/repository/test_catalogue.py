"""The backup agent's catalogue (Step 8; BR4.3, BR9.17, rules.md "Catalogue").

Each test uses a private folder standing in for U8's folder on the backup volume.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from docsuri_ops.backup_agent.catalogue import Catalogue, CatalogueDamaged

DIGEST_A, DIGEST_B = "a" * 64, "b" * 64


@pytest.fixture
def folder(tmp_path):
    path = tmp_path / "docsuri-v2"
    path.mkdir(mode=0o700)
    return path


@pytest.fixture
def catalogue(folder, clock):
    opened = Catalogue.open(folder, clock=clock)
    yield opened
    opened.close()


def write_set(catalogue, clock, path="archives/set-1.dump", *, days=14):
    catalogue.begin(path, record_id="backup-set-1", record_kind="BackupSet",
                    incarnation="incarnation-1")
    return catalogue.complete(path, size=1024, sha256=DIGEST_A, integrity="passed",
                              dispose_after=clock() + dt.timedelta(days=days))


def test_an_entry_records_every_field_of_its_file(catalogue, clock):
    entry = write_set(catalogue, clock)
    assert entry.state == "written" and entry.size == 1024 and entry.sha256 == DIGEST_A
    assert (entry.record_id, entry.record_kind, entry.incarnation, entry.integrity) == (
        "backup-set-1", "BackupSet", "incarnation-1", "passed")
    held = catalogue.hold("archives/set-1.dump", since=clock())
    assert held.state == "held" and catalogue.due(clock() + dt.timedelta(days=30)) == []
    catalogue.release("archives/set-1.dump")
    assert [e.path for e in catalogue.due(clock() + dt.timedelta(days=30))] == [
        "archives/set-1.dump"]
    assert catalogue.dispose("archives/set-1.dump").state == "disposed"


def test_an_event_out_of_order_or_a_path_outside_the_folder_is_refused(catalogue, clock):
    with pytest.raises(ValueError):
        catalogue.complete("archives/never-begun.dump", size=1, sha256=DIGEST_A,
                           integrity="passed", dispose_after=clock())
    for path in ("../outside.dump", "/archives/abs.dump", "archives/../x", ""):
        with pytest.raises(ValueError):
            catalogue.begin(path, record_id="r-1", record_kind="BackupSet")
    write_set(catalogue, clock)
    with pytest.raises(ValueError):
        catalogue.begin("archives/set-1.dump", record_id="r-2", record_kind="BackupSet")


def test_an_entry_beyond_the_head_is_adopted_on_open(catalogue, folder, clock, monkeypatch):
    write_set(catalogue, clock)

    def fault(self):
        raise OSError("fault between the line sync and the head replacement")

    monkeypatch.setattr(type(catalogue.log), "_replace_head", fault)
    with pytest.raises(OSError):
        catalogue.hold("archives/set-1.dump", since=clock())
    monkeypatch.undo()
    reopened = Catalogue.open(folder, clock=clock)
    try:
        assert reopened.files()["archives/set-1.dump"].state == "held"
        assert [entry.kind for entry in reopened.log.recoveries] == ["ledger.adopted"]
    finally:
        reopened.close()


def test_a_torn_last_entry_is_discarded(catalogue, folder, clock):
    write_set(catalogue, clock)
    catalogue.close()
    with open(folder / "catalogue.jsonl", "ab") as stream:
        stream.write(b'{"kind":"file.disposed","record":{"pa')
    reopened = Catalogue.open(folder, clock=clock)
    try:
        assert reopened.files()["archives/set-1.dump"].state == "written"
        assert [entry.kind for entry in reopened.log.recoveries] == ["ledger.discarded"]
    finally:
        reopened.close()


def test_a_forged_entry_is_damage_and_stops_every_write(catalogue, folder, clock):
    write_set(catalogue, clock)
    catalogue.close()
    lines = (folder / "catalogue.jsonl").read_bytes().split(b"\n")
    forged = json.loads(lines[1])
    forged["record"]["disposeAfter"] = "2000-01-01T00:00:00.000Z"
    lines[1] = json.dumps(forged, sort_keys=True, separators=(",", ":")).encode()
    (folder / "catalogue.jsonl").write_bytes(b"\n".join(lines))
    with pytest.raises(CatalogueDamaged):
        Catalogue.open(folder, clock=clock)


def test_a_rebuild_keeps_each_files_later_disposal_time(catalogue, folder, clock):
    later = write_set(catalogue, clock, "archives/set-1.dump", days=30)
    earlier = write_set(catalogue, clock, "archives/set-2.dump", days=5)
    catalogue.close()
    lines = (folder / "catalogue.jsonl").read_bytes().split(b"\n")
    lines[0] = lines[0].replace(b'"seq":1', b'"seq":7')  # break the chain
    (folder / "catalogue.jsonl").write_bytes(b"\n".join(lines))
    with pytest.raises(CatalogueDamaged):
        Catalogue.open(folder, clock=clock)
    ledger_says = {
        # The ledger's date is earlier for set-1 and later for set-2.
        "archives/set-1.dump": {"recordId": "backup-set-1", "recordKind": "BackupSet",
                                "disposeAfter": "2026-01-01T00:00:00.000Z"},
        "archives/set-2.dump": {"recordId": "backup-set-2", "recordKind": "BackupSet",
                                "disposeAfter": "2099-01-01T00:00:00.000Z"},
    }
    present = [("archives/set-1.dump", 1024, DIGEST_A), ("archives/set-2.dump", 1024, DIGEST_A),
               ("archives/unknown.dump", 10, DIGEST_B)]
    rebuilt = Catalogue.rebuild(folder, clock=clock, present=present, ledger_records=ledger_says)
    try:
        files = rebuilt.files()
        assert files["archives/set-1.dump"].dispose_after == later.dispose_after
        assert files["archives/set-2.dump"].dispose_after == "2099-01-01T00:00:00.000Z"
        assert earlier.dispose_after != files["archives/set-2.dump"].dispose_after
        assert "archives/unknown.dump" not in files
        assert rebuilt.unrecorded == ["archives/unknown.dump"]
        assert any(Path(name).name.startswith("catalogue.jsonl.damaged-")
                   for name in folder.iterdir())
    finally:
        rebuilt.close()
