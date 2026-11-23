"""The operations ledger's file layer (Step 8; BR4.6, BR6.10, NFR4.3).

Each test uses its own private folder; nothing here touches the realm's database.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.modules.operations.errors import LedgerDamaged
from backend.modules.operations.ledger import ADOPTED, DISCARDED, LedgerStore

ROOT = Path(__file__).resolve().parents[3]
WRITERS = 2
PER_WRITER = 40

APPENDER = """
import datetime as dt, sys
from pathlib import Path
from backend.modules.operations.ledger import LedgerStore
store = LedgerStore.open(Path(sys.argv[1]), clock=lambda: dt.datetime.now(dt.UTC))
for index in range(int(sys.argv[3])):
    store.append_entry("test.concurrent", {"writer": sys.argv[2], "index": index})
store.close()
"""


def open_store(folder: Path, clock) -> LedgerStore:
    return LedgerStore.open(folder, clock=clock)


def lines(folder: Path) -> list[dict]:
    raw = (folder / "ledger.jsonl").read_bytes()
    return [json.loads(line) for line in raw.split(b"\n") if line]


def test_entries_chain_by_digest_and_the_head_names_the_last(ledger, tmp_path):
    first = ledger.append_entry("test.event", {"n": 1})
    second = ledger.append_entry("test.event", {"n": 2})
    assert first.prev == "0" * 64 and second.prev == first.digest
    raw = (tmp_path / "ledger" / "ledger.jsonl").read_bytes().split(b"\n")
    assert hashlib.sha256(raw[1]).hexdigest() == second.digest
    head = json.loads((tmp_path / "ledger" / "head.json").read_bytes())
    assert head == {"count": 2, "head": second.digest}
    assert oct((tmp_path / "ledger" / "ledger.jsonl").stat().st_mode & 0o777) == "0o600"


def test_an_entry_synced_before_its_head_moved_is_adopted_on_open(ledger, tmp_path, clock,
                                                                 monkeypatch):
    folder = tmp_path / "ledger"
    ledger.append_entry("test.event", {"n": 1})

    def fault(self):
        raise OSError("fault between the line sync and the head replacement")

    monkeypatch.setattr(LedgerStore, "_replace_head", fault)
    with pytest.raises(OSError):
        ledger.append_entry("test.event", {"n": 2})
    monkeypatch.undo()
    assert json.loads((folder / "head.json").read_bytes())["count"] == 1
    reopened = open_store(folder, clock)
    try:
        entries = reopened.entries()
        assert [entry.kind for entry in entries] == ["test.event", "test.event", ADOPTED]
        assert entries[1].record == {"n": 2}
        assert entries[2].record == {"from": 1, "to": 2}
        assert reopened.head.count == 3
    finally:
        reopened.close()


def test_a_torn_last_entry_is_discarded_with_a_record(ledger, tmp_path, clock):
    folder = tmp_path / "ledger"
    ledger.append_entry("test.event", {"n": 1})
    ledger.close()
    with open(folder / "ledger.jsonl", "ab") as stream:
        stream.write(b'{"at":"2026-10-22T00:00:00.000Z","kind":"test.ev')
    reopened = open_store(folder, clock)
    try:
        entries = reopened.entries()
        assert [entry.kind for entry in entries] == ["test.event", DISCARDED]
        assert entries[1].record["bytes"] > 0
        assert (folder / "ledger.jsonl").read_bytes().endswith(b"\n")
        reopened.verify()
    finally:
        reopened.close()


def _damage_break(folder: Path) -> None:
    raw = (folder / "ledger.jsonl").read_bytes().split(b"\n")
    raw[0], raw[1] = raw[1], raw[0]
    (folder / "ledger.jsonl").write_bytes(b"\n".join(raw))


def _damage_shorten(folder: Path) -> None:
    raw = (folder / "ledger.jsonl").read_bytes().split(b"\n")
    (folder / "ledger.jsonl").write_bytes(b"\n".join(raw[:1]) + b"\n")


def _damage_forge(folder: Path) -> None:
    raw = (folder / "ledger.jsonl").read_bytes().split(b"\n")
    middle = json.loads(raw[1])
    middle["record"] = {"n": 999}
    raw[1] = json.dumps(middle, sort_keys=True, separators=(",", ":")).encode()
    (folder / "ledger.jsonl").write_bytes(b"\n".join(raw))


@pytest.mark.parametrize("damage", [_damage_break, _damage_shorten, _damage_forge])
def test_a_break_a_shortened_file_or_a_forged_middle_entry_is_damage(
        ledger, tmp_path, clock, damage):
    folder = tmp_path / "ledger"
    for n in range(3):
        ledger.append_entry("test.event", {"n": n})
    ledger.close()
    damage(folder)
    with pytest.raises(LedgerDamaged) as raised:
        open_store(folder, clock)
    assert "999" not in str(raised.value) and raised.value.category in (
        "chain-break", "truncated", "head-mismatch")


def test_a_missing_head_beside_entries_is_damage(ledger, tmp_path, clock):
    folder = tmp_path / "ledger"
    ledger.append_entry("test.event", {"n": 1})
    ledger.close()
    (folder / "head.json").unlink()
    with pytest.raises(LedgerDamaged, match="head-missing"):
        open_store(folder, clock)


def test_two_processes_appending_at_once_serialise_on_the_lock(ledger, tmp_path):
    folder = tmp_path / "ledger"
    ledger.close()
    environment = {**os.environ, "PYTHONPATH": str(ROOT)}
    writers = [
        subprocess.Popen(
            [sys.executable, "-c", APPENDER, str(folder), f"w{index}", str(PER_WRITER)],
            cwd=ROOT, env=environment,
        )
        for index in range(WRITERS)
    ]
    assert [writer.wait(timeout=60) for writer in writers] == [0] * WRITERS
    written = lines(folder)
    assert len(written) == WRITERS * PER_WRITER
    assert [entry["seq"] for entry in written] == list(range(1, WRITERS * PER_WRITER + 1))
    for index in range(WRITERS):
        mine = [entry["record"]["index"] for entry in written
                if entry["record"]["writer"] == f"w{index}"]
        assert mine == list(range(PER_WRITER))


def test_the_copy_digest_equals_the_file_up_to_the_head(ledger, tmp_path):
    for n in range(5):
        ledger.append_entry("test.event", {"n": n})
    sink = io.BytesIO()
    copied = ledger.copy(sink)
    on_disk = (tmp_path / "ledger" / "ledger.jsonl").read_bytes()
    assert sink.getvalue() == on_disk
    assert copied["sha256"] == hashlib.sha256(on_disk).hexdigest()
    assert copied["count"] == 5 and copied["bytes"] == len(on_disk)


def test_seq_never_repeats_across_reopens(ledger, tmp_path, clock):
    folder = tmp_path / "ledger"
    seen = [ledger.append_entry("test.event", {"n": n}).seq for n in range(3)]
    ledger.close()
    for _ in range(2):
        store = open_store(folder, clock)
        seen.append(store.append_entry("test.event", {}).seq)
        store.close()
    assert seen == [1, 2, 3, 4, 5] and len(set(seen)) == len(seen)


def test_an_unregistered_kind_or_a_non_canonical_record_is_refused(ledger):
    with pytest.raises(ValueError):
        ledger.append_entry("Not A Kind", {})
    with pytest.raises(ValueError):
        ledger.append_entry("test.event", {"value": float("nan")})
    assert ledger.head.count == 0


def test_a_loose_folder_mode_is_refused(tmp_path, clock):
    folder = tmp_path / "loose"
    folder.mkdir(mode=0o755)
    folder.chmod(0o755)
    with pytest.raises(LedgerDamaged, match="custody-differs"):
        open_store(folder, clock)
