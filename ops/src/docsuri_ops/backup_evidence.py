"""Backup and restore evidence for the owner seams.

This module produces the evidence that ``docsuri_platform_integrity.domain.backup`` judges. It
does not decide whether a backup succeeded: the verdict belongs to the pure domain rules, so a
missing condition cannot be absorbed by the caller that gathered the evidence.

The design bias throughout is that an unobserved condition stays unobserved. Nothing here fills a
gap with an optimistic default -- a missing drive, a locked key, an unverified off-host copy or a
restore onto the incarnation we just cut all leave the corresponding evidence field at its
unproven value and therefore produce INCOMPLETE.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from docsuri_platform_integrity.domain.backup import (
    BackupEvidence,
    cut_is_exact,
    evaluate_backup,
)
from docsuri_platform_integrity.domain.retention import RetentionPolicy, gc_decision

# Retention and GC are bounded to paths this system created. Anything pre-existing -- operator
# logs, hand-made backups, the pre-existing docsuri backup tree -- is outside its authority.
MANAGED_MARKER = ".docsuri-rem1-managed"


class ArchiveStore(Protocol):
    """A destination that can hold an encrypted archive and prove what it wrote."""

    def available(self) -> tuple[bool, str]: ...

    def write_archive(self, source: Path, *, name: str) -> tuple[str | None, bool, str]: ...

    def verify_remote_copy(self, digest: str) -> tuple[bool, str]: ...


class RestoreTarget(Protocol):
    """A restore destination that must be a NEW incarnation, never the cut source."""

    def incarnation(self) -> str: ...

    def restore(self, archive: Path) -> tuple[bool, str]: ...


class KeyLock(Protocol):
    """Reports whether the backup key and the authenticated clock are actually usable."""

    def key_unlocked(self) -> bool: ...

    def clock_trusted(self) -> bool: ...


class LocalHostLock:
    """Host-level key/clock lock with no observations attached.

    This is the adapter a caller gets before the operator has wired the real Keychain and
    authenticated clock. It reports both as unusable, so an unwired deployment produces
    INCOMPLETE rather than quietly asserting a working backup key.
    """

    def key_unlocked(self) -> bool:
        return False

    def clock_trusted(self) -> bool:
        return False


@dataclass(frozen=True)
class BackupCut:
    """An exact snapshot cut: an instant plus the writer epoch that owned it."""

    cut_us: int
    generation: str
    writer_epoch: str
    source: Path


@dataclass
class ManagedPath:
    """A path this system owns, so retention may later act on it."""

    path: Path

    def claim(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        marker = self.path / MANAGED_MARKER
        if not marker.exists():
            marker.write_text("retention-managed\n", encoding="utf-8")
            marker.chmod(0o600)
        return self.path

    @staticmethod
    def is_managed(path: Path) -> bool:
        """Whether ``path`` lies inside a retention-managed subtree.

        Archives are written as *files* inside the managed root, and a marker can never exist
        inside a regular file. Testing only the entry itself therefore classified every archive
        this system writes as unmanaged -- the system could not retain its own backups, and a GC
        pass had no way to tell them apart from operator data. The marker means "this subtree is
        ours", so a containing directory carrying it is what makes a path managed.
        """
        for candidate in (path, *path.parents):
            if (candidate / MANAGED_MARKER).is_file():
                return True
        return False


@dataclass
class BackupReport:
    evidence: BackupEvidence
    verdict: str
    reasons: tuple[str, ...]
    notes: list[str] = field(default_factory=list)
    managed_paths: list[Path] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return self.verdict == "VERIFIED"

    def as_dict(self) -> dict:
        return {
            "state": "VERIFIED" if self.verified else "INCOMPLETE",
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "notes": list(self.notes),
            "cutUs": self.evidence.cut_us,
            "generation": self.evidence.generation,
            "archive": self.evidence.archive,
            "archiveEncrypted": self.evidence.archive_encrypted,
            "remoteCopyVerified": self.evidence.remote_copy_verified,
            "restoredIncarnation": self.evidence.restored_incarnation,
            "writerResolved": self.evidence.writer_resolved,
            "clockTrusted": self.evidence.clock_trusted,
            "keyUnlocked": self.evidence.key_unlocked,
            "managedPaths": [str(path) for path in self.managed_paths],
        }


def collect_backup_evidence(
    cut: BackupCut,
    *,
    archive: ArchiveStore,
    restore: RestoreTarget,
    key_lock: KeyLock,
    now_us: int,
    writer_resolved: bool = True,
    observed_writer_epoch: str | None = None,
    rpo_us: int | None = None,
    rto_us: int | None = None,
    managed_root: Path | None = None,
) -> BackupReport:
    """Gather evidence for one cut. Every field stays unproven unless actually observed."""
    notes: list[str] = []
    archive_digest: str | None = None
    archive_path: Path | None = None
    encrypted = False
    remote_verified = False

    exact = cut_is_exact(
        cut.cut_us, writer_epoch=cut.writer_epoch,
        observed_epoch=cut.writer_epoch if observed_writer_epoch is None else observed_writer_epoch,
    )
    if not exact:
        notes.append("cut spans a writer epoch rotation and is not an exact snapshot")

    available, reason = archive.available()
    if not available:
        notes.append(f"archive store unavailable: {reason}")
    else:
        managed = ManagedPath(managed_root) if managed_root else None
        if managed is not None:
            managed.claim()
        write_result = archive.write_archive(cut.source, name=cut.generation)
        archive_digest, encrypted, archive_path_str = write_result
        if archive_digest is None:
            notes.append(f"archive write did not produce a digest: {archive_path_str}")
        elif not encrypted:
            notes.append("archive was written without encryption")
        if archive_digest is not None and encrypted:
            archive_path = Path(archive_path_str)
            remote_verified, detail = archive.verify_remote_copy(archive_digest)
            if not remote_verified:
                notes.append(f"off-host copy not verified: {detail}")

    restored_incarnation: str | None = None
    target_incarnation = restore.incarnation()
    if target_incarnation == cut.writer_epoch:
        # Restoring onto the incarnation we just cut would prove nothing about recovery.
        notes.append("restore target is the cut incarnation, not a new one")
    elif archive_digest is not None and encrypted and archive_path is not None:
        if managed_root is not None:
            ManagedPath(managed_root).claim()
        ok, detail = restore.restore(archive_path)
        if ok:
            restored_incarnation = target_incarnation
        else:
            notes.append(f"isolated restore failed: {detail}")
    else:
        notes.append("no verified archive to restore from")

    evidence = BackupEvidence(
        cut_us=str(cut.cut_us),
        generation=cut.generation,
        archive=archive_digest,
        archive_encrypted=encrypted,
        remote_copy_verified=remote_verified,
        restored_incarnation=restored_incarnation,
        writer_resolved=writer_resolved and exact,
        clock_trusted=key_lock.clock_trusted(),
        key_unlocked=key_lock.key_unlocked(),
        rpo_us=None if rpo_us is None else str(rpo_us),
        rto_us=None if rto_us is None else str(rto_us),
    )
    verdict, reasons = evaluate_backup(evidence, now_us=now_us)
    return BackupReport(
        evidence=evidence,
        verdict=verdict,
        reasons=reasons,
        notes=notes,
        managed_paths=[managed_root] if managed_root is not None else [],
    )


def iter_backup_candidates(root: Path) -> Iterator[Path]:
    """Enumerate backup entries under root, whether they are files or directories.

    Enumeration is deliberately complete. A GC pass can only positively exclude an entry it can
    see, so hiding a pre-existing archive from this listing would not protect it -- it would just
    make ownership undecidable, and would equally hide this system's own ``*.archive`` files from
    retention. Exclusion happens at the marker check, not here.
    """
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir()):
        if entry.name == MANAGED_MARKER or entry.name.startswith("."):
            continue
        if entry.is_dir() or entry.is_file():
            yield entry


@dataclass
class CollectionResult:
    removed: list[Path] = field(default_factory=list)
    retained: list[tuple[Path, str]] = field(default_factory=list)
    dry_run: bool = True

    def as_dict(self) -> dict:
        return {
            "removed": [str(path) for path in self.removed],
            "retained": [
                {"path": str(path), "reason": reason} for path, reason in self.retained
            ],
            "dryRun": self.dry_run,
        }


def collect_expired_backups(
    root: Path,
    *,
    now_us: int,
    policy: RetentionPolicy,
    approved: bool = False,
    writer_resolved: bool = True,
    dry_run: bool = True,
) -> CollectionResult:
    """Delete expired managed backups. Anything without the managed marker is retained, always.

    The marker is the sole authority for ownership, and a pre-existing entry is retained with the
    reason ``unmanaged`` regardless of age or approval -- retention must never become a way to
    reclaim an operator's own backups. An unresolved writer also blocks collection, since a
    process that may still be appending is not safe to collect from.
    """
    result = CollectionResult(dry_run=dry_run)
    for entry in iter_backup_candidates(root):
        if not ManagedPath.is_managed(entry):
            result.retained.append((entry, "unmanaged"))
            continue
        try:
            stat_result = entry.stat()
        except OSError as error:
            result.retained.append((entry, f"unreadable: {type(error).__name__}"))
            continue
        classification = (
            "critical" if (entry / "critical").exists() else "ordinary"
        )
        if not gc_decision(
            classification, stat_result.st_mtime_ns // 1000, now_us, policy,
            managed=True, approved=approved, writer_resolved=writer_resolved,
        ):
            reason = (
                "writer_unresolved" if not writer_resolved
                else f"{classification}_retention_active"
            )
            result.retained.append((entry, reason))
            continue
        if dry_run:
            result.removed.append(entry)
            continue
        try:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        except OSError as error:
            result.retained.append((entry, f"removal_failed: {type(error).__name__}"))
            continue
        result.removed.append(entry)
    return result


def digest_file(path: Path, *, chunk: int = 1 << 20) -> str:
    """Streamed sha256, so a large archive is never held in memory."""
    accumulator = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            accumulator.update(block)
    return "sha256:" + accumulator.hexdigest()


def free_bytes(path: Path) -> int:
    stats = os.statvfs(path)
    return stats.f_bavail * stats.f_frsize
