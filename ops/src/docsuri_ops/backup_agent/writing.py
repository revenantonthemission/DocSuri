"""Writing one copy onto the backup volume (U8 plan Step 25; BR4.3, BR9.12, BR9.17,
NFR3.12, NFR3.13; Workflow 19 steps 2–6).

Every file copy U8 makes takes this one path:

1. the file is entered in the catalogue as writing, at its staging and its final
   location, before anything is written;
2. the bytes reach the staging folder on the volume (a new file, 0600, never replaced);
3. the staged file is written into the archives folder with the earlier tool's archive
   write (`adapters/backup.py`'s `write_archive`), which never replaces a file and asks
   the volume's mount point whether it is encrypted. The written digest must equal the
   staged one and, for a stream, the sender's;
4. the agent checks integrity itself (a dump's table of contents, a ledger copy's
   chain);
5. the staging file is removed and the catalogue entry completed with the size, the
   digest, the integrity result and the earliest disposal time.

A failure removes the staging file and any partial archive and marks both disposed.

The kind of a copy comes only from the command and its source (`COPY_KINDS`), never
from a caller. Its earliest disposal time is fixed here: `retainUntil` from the agent's
retention policy for a backup set or a ledger copy (Sunday's sets, by the Seoul date,
for 8 weeks; others 14 days), the backstop for a copy disposed on an event, or, for the
v1 final snapshot and a rolled-back database's copy, the date your decision approved,
refused below the kind's minimum and without its decision's receipt.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from zoneinfo import ZoneInfo

from docsuri_ops.adapters.backup import LocalDriveArchive

from .catalogue import Catalogue
from .config import STAGING, AgentConfig

SEOUL = ZoneInfo("Asia/Seoul")
SUNDAY = 6
CHUNK = 1 << 20
_RECEIPT = re.compile(r"[0-9a-f-]{36}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_PART = re.compile(r"[a-z]{1,16}")


@dataclass(frozen=True)
class CopyKind:
    name: str
    record_kind: str
    disposal: str  # retention | backstop | decided


COPY_KINDS = {
    "live-set": CopyKind("live-set", "BackupSet", "retention"),
    "rehearsal-set": CopyKind("rehearsal-set", "BackupSet", "retention"),
    "ledger-copy": CopyKind("ledger-copy", "LedgerCopy", "retention"),
    "dry-run-snapshot": CopyKind("dry-run-snapshot", "RetainedCopy", "backstop"),
    "final-snapshot": CopyKind("final-snapshot", "RetainedCopy", "decided"),
    "rolled-back-copy": CopyKind("rolled-back-copy", "RetainedCopy", "decided"),
}


class AgentRefused(Exception):
    """A command refused, with its fixed reason key."""

    def __init__(self, reason: str, **facts):
        super().__init__(reason)
        self.reason, self.facts = reason, facts


@dataclass(frozen=True)
class Decided:
    """Your disposal-date decision: the date, its receipt and its subject digest."""

    date: dt.datetime
    receipt: str
    subject_digest: str

    @classmethod
    def parse(cls, value) -> Decided:
        if not isinstance(value, dict) or set(value) != {"date", "receipt", "subjectDigest"}:
            raise AgentRefused("decided-date-refused")
        try:
            date = dt.datetime.fromisoformat(str(value["date"]).replace("Z", "+00:00"))
        except ValueError:
            raise AgentRefused("decided-date-refused") from None
        if date.tzinfo is None or not _RECEIPT.fullmatch(str(value["receipt"])) or not (
            _DIGEST.fullmatch(str(value["subjectDigest"]))
        ):
            raise AgentRefused("decided-date-refused")
        return cls(date, str(value["receipt"]), str(value["subjectDigest"]))


def retain_until(kind: CopyKind, config: AgentConfig, now: dt.datetime,
                 decided: Decided | None) -> dt.datetime:
    """The earliest disposal time, fixed when the file is written."""
    retention = config.retention
    if kind.disposal == "decided":
        if decided is None:
            raise AgentRefused("decided-date-required")
        if decided.date < now + dt.timedelta(seconds=retention.decided_minimum_seconds):
            raise AgentRefused("decided-date-too-early")
        return decided.date
    if decided is not None:
        raise AgentRefused("decided-date-refused")
    if kind.disposal == "backstop":
        return now + dt.timedelta(seconds=retention.dry_run_backstop_seconds)
    sunday = now.astimezone(SEOUL).weekday() == SUNDAY
    if kind.name == "ledger-copy":
        # A ledger copy is kept by its own write time, beside a set or alone (L1-24).
        seconds = retention.sunday_set_seconds if sunday else retention.ledger_copy_seconds
        return now + dt.timedelta(seconds=seconds)
    seconds = retention.sunday_set_seconds if sunday else retention.daily_set_seconds
    return now + dt.timedelta(seconds=seconds)


def file_digest(path: Path) -> str:
    accumulator = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        while block := stream.read(CHUNK):
            accumulator.update(block)
    return accumulator.hexdigest()


class ArchiveWriter:
    def __init__(self, config: AgentConfig, catalogue: Catalogue, *, clock, volume):
        self.config, self.catalogue, self.clock, self.volume = config, catalogue, clock, volume

    def write(self, kind_name: str, *, record_id: str, fill: Callable[[BinaryIO], None],
              integrity: Callable[[Path], bool], incarnation: str | None = None,
              sender_digest: str | None = None, decided: Decided | None = None,
              part: str | None = None) -> dict:
        """`part` names one archive of a copy made of several, each one archive file
        per source (a snapshot's `index` and `objects`, U8 plan Step 31)."""
        kind = COPY_KINDS.get(kind_name)
        if kind is None:
            raise AgentRefused("kind-refused")
        if part is not None and _PART.fullmatch(part) is None:
            raise AgentRefused("part-refused")
        now = self.clock()
        dispose_after = retain_until(kind, self.config, now, decided)
        name = f"{kind.name}-{now.astimezone(dt.UTC):%Y%m%dT%H%M%S}-{record_id}"
        if part is not None:
            name = f"{name}-{part}"
        staged_rel, archive_rel = f"{STAGING}/{name}", f"archives/{name}.archive"
        # Each entry carries its disposal point from its first `file.writing` (L1-2): the
        # archive's retention date, and the staging file's one-day backstop.
        staging_backstop = now + dt.timedelta(
            seconds=self.config.retention.staging_backstop_seconds)
        try:
            self.catalogue.begin(archive_rel, record_id=record_id,
                                 record_kind=kind.record_kind, incarnation=incarnation,
                                 dispose_after=dispose_after)
        except ValueError:
            raise AgentRefused("archive-exists") from None  # a catalogued file stays as it is
        self.catalogue.begin(staged_rel, record_id=record_id, record_kind=kind.record_kind,
                             incarnation=incarnation, dispose_after=staging_backstop)
        staged, archive = self.config.u8_folder / staged_rel, self.config.u8_folder / archive_rel
        try:
            digest = self._stage(staged, fill)
            if sender_digest is not None and sender_digest != digest:
                raise AgentRefused("digest-mismatch")
            written = self._write_archive(staged, name, digest)
            passed = bool(integrity(archive))
        except AgentRefused as refusal:
            # A file already at the archive's name is not this write's: it is left alone.
            ours = None if refusal.reason == "archive-exists" else archive
            self._abandon(staged, staged_rel, ours, archive_rel)
            raise
        except Exception as error:  # noqa: BLE001 - every write failure removes both files
            self._abandon(staged, staged_rel, archive, archive_rel)
            raise AgentRefused("write-failed", category=type(error).__name__) from None
        os.unlink(staged)
        removed = self.clock()
        self.catalogue.dispose(staged_rel)
        size = archive.stat().st_size
        self.catalogue.complete(
            archive_rel, size=size, sha256=written, integrity="passed" if passed else "failed",
            dispose_after=dispose_after, decision_receipt=decided.receipt if decided else None,
        )
        receipt = {
            "recordId": record_id, "recordKind": kind.record_kind, "copyKind": kind.name,
            "location": archive_rel, "stagingLocation": staged_rel, "sha256": written,
            "size": size,
            "integrity": "passed" if passed else "failed",
            "disposeAfter": dispose_after.astimezone(dt.UTC).isoformat(),
            "stagingRemovedAt": removed.astimezone(dt.UTC).isoformat(),
        }
        if incarnation is not None:
            receipt["incarnation"] = incarnation
        if decided is not None:
            receipt["decisionReceipt"] = decided.receipt
        return receipt

    def _stage(self, staged: Path, fill: Callable[[BinaryIO], None]) -> str:
        descriptor = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            fill(stream)
            stream.flush()
            os.fsync(stream.fileno())
        return file_digest(staged)

    def _write_archive(self, staged: Path, name: str, digest: str) -> str:
        adapter = LocalDriveArchive(self.config.archives, encryption_probe=self.volume.encrypted)
        written, encrypted, detail = adapter.write_archive(staged, name=name)
        if written is None:
            raise AgentRefused("archive-exists" if "already exists" in detail
                               else "write-failed")
        archive = Path(detail)
        os.chmod(archive, 0o600, follow_symlinks=False)
        if not encrypted:
            raise AgentRefused("backup-volume-unencrypted")
        if written.removeprefix("sha256:") != digest:
            raise AgentRefused("digest-mismatch")
        return digest

    def _abandon(self, staged: Path, staged_rel: str, archive: Path | None,
                 archive_rel: str) -> None:
        """Remove the staging file and any partial archive this write made, and mark
        both disposed. A file that cannot be removed now (the volume went away) stays
        `writing` in the catalogue, so the first disposal pass once the volume is back
        removes it. `archive` is None when the name was already taken by another file."""
        for path, relative in ((staged, staged_rel), (archive, archive_rel)):
            try:
                if path is not None and (path.exists() or path.is_symlink()):
                    os.unlink(path)
            except OSError:
                continue
            self.catalogue.dispose(relative)
