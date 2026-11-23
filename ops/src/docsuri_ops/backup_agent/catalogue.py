"""The backup agent's catalogue (U8 plan Step 7; BR4.3, BR9.17, rules.md "Catalogue").

An append-only, digest-chained record in U8's folder on the backup volume, written only
by the agent. Its head, adoption and torn-entry rules are the ledger's: it is the
ledger's `ChainedLog` with its own file names (`catalogue.jsonl`, `catalogue-head.json`,
`.catalogue.lock`).

Each entry is one event about one file; a file's current state is the fold of its
events. For each file the catalogue holds the path (relative to U8's folder), size and
digest, the record the file belongs to and that record's kind, the database incarnation
for a dump, the integrity result, the earliest disposal time and the state: `writing`,
`written`, `held` (by the retention floor) or `disposed`.

A catalogue that does not verify is rebuilt in person from the files present and their
ledger records, keeping for each file the later of the two disposal times it can find;
the damaged files are set aside, never deleted.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from backend.modules.operations.errors import LedgerDamaged
from backend.modules.operations.ledger import ChainedLog, utc_text

LOG = "catalogue.jsonl"
HEAD = "catalogue-head.json"
LOCK = ".catalogue.lock"
STATES = ("writing", "written", "held", "disposed")
INTEGRITY = ("passed", "failed")
RECORD_KIND = re.compile(r"[A-Z][A-Za-z]{1,63}")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
DIGEST = re.compile(r"[0-9a-f]{64}")
EVENTS = {
    "file.writing": ("writing",),
    "file.written": ("written",),
    "file.held": ("held",),
    "file.released": ("written",),
    "file.dated": ("written",),
    "file.disposed": ("disposed",),
}
# The states each event may follow; a rebuilt entry starts a file afresh.
ALLOWED = {
    "file.writing": (None, "disposed"),
    "file.written": ("writing",),
    "file.held": ("written",),
    "file.released": ("held",),
    "file.dated": ("written",),
    "file.disposed": ("writing", "written", "held"),
}


class CatalogueDamaged(LedgerDamaged):
    """The catalogue does not verify: every write and deletion stops until a rebuild."""


@dataclass(frozen=True)
class CatalogueFile:
    path: str
    record_id: str
    record_kind: str
    state: str
    incarnation: str | None = None
    size: int | None = None
    sha256: str | None = None
    integrity: str | None = None
    dispose_after: str | None = None
    held_since: str | None = None
    decision_receipt: str | None = None
    written_at: str | None = None


def check_path(path: str) -> str:
    """A path inside U8's folder: relative, plain parts, no traversal."""
    parts = path.split("/") if isinstance(path, str) else []
    if not 1 <= len(parts) <= 4 or not all(PART.fullmatch(part) for part in parts):
        raise ValueError("catalogue path outside U8's folder form")
    if any(part in (".", "..") for part in parts):
        raise ValueError("catalogue path outside U8's folder form")
    return path


def _time(moment: dt.datetime) -> str:
    return utc_text(moment)


def _later(first: str | None, second: str | None) -> str | None:
    values = [value for value in (first, second) if value is not None]
    if not values:
        return None
    return max(values, key=lambda value: dt.datetime.fromisoformat(value.replace("Z", "+00:00")))


class Catalogue:
    def __init__(self, log: ChainedLog):
        self.log = log
        self.unrecorded: list[str] = []  # set by `rebuild`

    @classmethod
    def open(cls, folder: Path, *, clock) -> Catalogue:
        log = ChainedLog(folder, clock=clock, log_name=LOG, head_name=HEAD, lock_name=LOCK)
        try:
            log.open()
        except LedgerDamaged as error:
            raise CatalogueDamaged(error.category) from None
        return cls(log)

    def close(self) -> None:
        self.log.close()

    # --- folding ------------------------------------------------------------------------

    def files(self) -> dict[str, CatalogueFile]:
        try:
            entries = self.log.entries()
        except LedgerDamaged as error:
            raise CatalogueDamaged(error.category) from None
        files: dict[str, CatalogueFile] = {}
        for entry in entries:
            if entry.kind not in EVENTS:
                continue  # the chain's own recovery records
            record = entry.record
            current = files.get(record["path"])
            rebuilt = record.get("rebuilt") is True
            if (current.state if current else None) not in ALLOWED[entry.kind] and not rebuilt:
                raise CatalogueDamaged("state-order")
            files[record["path"]] = self._apply(current, entry.kind, record)
            if entry.kind == "file.written":
                files[record["path"]] = replace(files[record["path"]], written_at=entry.at)
        return files

    @staticmethod
    def _apply(current: CatalogueFile | None, kind: str, record: dict) -> CatalogueFile:
        state = EVENTS[kind][0]
        if kind == "file.writing" or record.get("rebuilt") is True:
            return CatalogueFile(
                path=record["path"], record_id=record["recordId"],
                record_kind=record["recordKind"], state=state,
                incarnation=record.get("incarnation"), size=record.get("size"),
                sha256=record.get("sha256"), integrity=record.get("integrity"),
                dispose_after=record.get("disposeAfter"),
            )
        if kind == "file.written":
            return replace(
                current, state=state, size=record["size"], sha256=record["sha256"],
                integrity=record["integrity"], dispose_after=record["disposeAfter"],
                decision_receipt=record.get("decisionReceipt"),
            )
        if kind == "file.dated":
            return replace(current, dispose_after=record["disposeAfter"],
                           decision_receipt=record["decisionReceipt"])
        if kind == "file.held":
            return replace(current, state=state, held_since=record["since"])
        if kind == "file.released":
            return replace(current, state=state, held_since=None)
        return replace(current, state=state)

    def _append(self, kind: str, record: dict) -> CatalogueFile:
        current = self.files().get(record["path"])
        if (current.state if current else None) not in ALLOWED[kind]:
            raise ValueError("catalogue event out of order for this file")
        try:
            self.log.append(kind, record)
        except LedgerDamaged as error:
            raise CatalogueDamaged(error.category) from None
        return self._apply(current, kind, record)

    # --- events ---------------------------------------------------------------------------

    def begin(self, path: str, *, record_id: str, record_kind: str,
              incarnation: str | None = None,
              dispose_after: dt.datetime | None = None) -> CatalogueFile:
        """A file is entered before anything is written (rules.md BR4.3), with its
        disposal point when the writer knows it (L1-2, U8 plan Step 62(a)). `due` lists
        only written files, so a date on a writing entry deletes nothing."""
        if not IDENTIFIER.fullmatch(record_id or "") or not RECORD_KIND.fullmatch(
                record_kind or ""):
            raise ValueError("catalogue record reference outside its form")
        if incarnation is not None and not IDENTIFIER.fullmatch(incarnation):
            raise ValueError("database incarnation outside its form")
        if dispose_after is not None and dispose_after.tzinfo is None:
            raise ValueError("disposal point without its time zone")
        record = {"path": check_path(path), "recordId": record_id, "recordKind": record_kind}
        if incarnation is not None:
            record["incarnation"] = incarnation
        if dispose_after is not None:
            record["disposeAfter"] = _time(dispose_after)
        return self._append("file.writing", record)

    def complete(self, path: str, *, size: int, sha256: str, integrity: str,
                 dispose_after: dt.datetime,
                 decision_receipt: str | None = None) -> CatalogueFile:
        if type(size) is not int or size < 0 or not DIGEST.fullmatch(sha256 or ""):
            raise ValueError("written file facts outside their form")
        if integrity not in INTEGRITY:
            raise ValueError("integrity result outside its vocabulary")
        record = {
            "path": check_path(path), "size": size, "sha256": sha256, "integrity": integrity,
            "disposeAfter": _time(dispose_after),
        }
        if decision_receipt is not None:
            if not IDENTIFIER.fullmatch(decision_receipt):
                raise ValueError("decision receipt outside its form")
            record["decisionReceipt"] = decision_receipt
        return self._append("file.written", record)

    def date(self, path: str, *, dispose_after: dt.datetime,
             decision_receipt: str) -> CatalogueFile:
        """Your disposal-date decision brings a written file's time forward (set-date)."""
        if not IDENTIFIER.fullmatch(decision_receipt or ""):
            raise ValueError("decision receipt outside its form")
        return self._append("file.dated", {
            "path": check_path(path), "disposeAfter": _time(dispose_after),
            "decisionReceipt": decision_receipt,
        })

    def hold(self, path: str, *, since: dt.datetime) -> CatalogueFile:
        return self._append("file.held", {"path": check_path(path), "since": _time(since)})

    def release(self, path: str) -> CatalogueFile:
        return self._append("file.released", {"path": check_path(path)})

    def dispose(self, path: str) -> CatalogueFile:
        return self._append("file.disposed", {"path": check_path(path)})

    def due(self, now: dt.datetime) -> list[CatalogueFile]:
        """Written files whose earliest disposal time has passed; held files never."""
        instant = now.astimezone(dt.UTC)
        return sorted(
            (
                entry for entry in self.files().values()
                if entry.state == "written" and entry.dispose_after is not None
                and dt.datetime.fromisoformat(entry.dispose_after.replace("Z", "+00:00"))
                <= instant
            ),
            key=lambda entry: entry.path,
        )

    # --- rebuild ----------------------------------------------------------------------------

    @classmethod
    def rebuild(
        cls, folder: Path, *, clock, present: Iterable[tuple[str, int, str]],
        ledger_records: Mapping[str, dict],
    ) -> Catalogue:
        """A new catalogue from the files present and their ledger records. For each
        file the disposal time kept is the later of the ledger's and of whatever the
        damaged catalogue still shows for it; the damaged files are set aside."""
        prior = read_disposal_times(folder)
        stamp = clock().strftime("%Y%m%dT%H%M%S%fZ")
        for name in (LOG, HEAD):
            source = folder / name
            if source.exists() and not source.is_symlink():
                os.rename(source, folder / f"{name}.damaged-{stamp}")
        catalogue = cls.open(folder, clock=clock)
        catalogue.unrecorded = []
        for path, size, sha256 in sorted(present):
            record = ledger_records.get(path)
            if record is None:
                # A file the ledger has no record of is reported, never adopted.
                catalogue.unrecorded.append(check_path(path))
                continue
            dispose_after = _later(record.get("disposeAfter"), prior.get(path))
            entry = {
                "path": check_path(path), "recordId": record["recordId"],
                "recordKind": record["recordKind"], "size": size, "sha256": sha256,
                "integrity": record.get("integrity", "passed"),
                "disposeAfter": dispose_after, "rebuilt": True,
            }
            if record.get("incarnation") is not None:
                entry["incarnation"] = record["incarnation"]
            catalogue.log.append("file.written", entry)
        return catalogue


def read_disposal_times(folder: Path) -> dict[str, str]:
    """Best effort over a damaged catalogue: every disposal time a readable line still
    shows, latest per file. Used only to keep a later time, never to shorten one."""
    times: dict[str, str] = {}
    path = folder / LOG
    if not path.exists() or path.is_symlink():
        return times
    for line in path.read_bytes().split(b"\n"):
        try:
            record = json.loads(line)["record"]
            when, file_path = record["disposeAfter"], record["path"]
        except (ValueError, KeyError, TypeError):
            continue
        if isinstance(when, str) and isinstance(file_path, str):
            later = _later(times.get(file_path), when)
            if later is not None:
                times[file_path] = later
    return times
