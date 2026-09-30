"""Backup evidence and retention for the operator seams.

    backup_evidence.py collect --cut-us N --generation sha256:... --source DUMP \\
        --archive-root /Volumes/DocSuri_Backup --restore-root /Volumes/Restore \\
        --key /path/to/key --clock-evidence /path/to/clock.json --output report.json

    backup_evidence.py gc --root /Volumes/DocSuri_Backup --output gc.json \\
        [--apply] [--approve-critical]

`gc` is a dry run unless --apply is given, and it only ever removes directories carrying the
managed marker. Pre-existing operator archives are reported as `unmanaged` and left alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
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

from docsuri_ops.adapters.backup import (
    LocalDriveArchive,
    LocalKeyLock,
    LocalRestoreTarget,
)

# Retention and GC are bounded to paths this system created. Anything pre-existing -- operator
# logs, hand-made backups, the pre-existing docsuri backup tree -- is outside its authority.
MANAGED_MARKER = ".docsuri-rem1-managed"


def _emit(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        archive_digest, encrypted, detail = archive.write_archive(cut.source, name=cut.generation)
        if archive_digest is None:
            notes.append(f"archive write did not produce a digest: {detail}")
        elif not encrypted:
            notes.append("archive was written without encryption")
        if archive_digest is not None and encrypted:
            remote_verified, detail = archive.verify_remote_copy(archive_digest)
            if not remote_verified:
                notes.append(f"off-host copy not verified: {detail}")

    restored_incarnation: str | None = None
    target_incarnation = restore.incarnation()
    if target_incarnation == cut.writer_epoch:
        # Restoring onto the incarnation we just cut would prove nothing about recovery.
        notes.append("restore target is the cut incarnation, not a new one")
    elif archive_digest is not None and encrypted:
        if managed_root is not None:
            ManagedPath(managed_root).claim()
        ok, detail = restore.restore(Path(archive_digest))
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
    verdict, reasons = evaluate_backup(evidence, now_us=time.time_ns() // 1000)
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


def do_collect(args) -> int:
    cut = BackupCut(
        cut_us=args.cut_us,
        generation=args.generation,
        writer_epoch=args.writer_epoch,
        source=Path(args.source),
    )
    report = collect_backup_evidence(
        cut,
        archive=LocalDriveArchive(
            mount=Path(args.archive_root), minimum_free_bytes=args.minimum_free_bytes
        ),
        restore=LocalRestoreTarget(root=Path(args.restore_root), incarnation_id=args.incarnation),
        key_lock=LocalKeyLock(
            key_path=Path(args.key) if args.key else None,
            clock_evidence=Path(args.clock_evidence) if args.clock_evidence else None,
            clock_quality=args.clock_quality,
        ),
        now_us=int(time.time() * 1_000_000),
        writer_resolved=not args.writer_unresolved,
        observed_writer_epoch=args.observed_writer_epoch,
        managed_root=Path(args.managed_root) if args.managed_root else None,
    )
    _emit(Path(args.output), report.as_dict())
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.verified else 2


def do_gc(args) -> int:
    result = collect_expired_backups(
        Path(args.root),
        now_us=int(time.time() * 1_000_000),
        policy=RetentionPolicy(
            ordinary_days=args.ordinary_days, critical_days=args.critical_days
        ),
        approved=args.approve_critical,
        writer_resolved=not args.writer_unresolved,
        dry_run=not args.apply,
    )
    _emit(Path(args.output), result.as_dict())
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="gather backup/restore evidence for one cut")
    collect.add_argument("--cut-us", type=int, required=True)
    collect.add_argument("--generation", required=True)
    collect.add_argument("--source", required=True)
    collect.add_argument("--writer-epoch", required=True)
    collect.add_argument("--observed-writer-epoch")
    collect.add_argument("--archive-root", required=True)
    collect.add_argument("--restore-root", required=True)
    collect.add_argument("--incarnation", required=True)
    collect.add_argument("--key")
    collect.add_argument("--clock-evidence")
    collect.add_argument("--clock-quality", default="unknown")
    collect.add_argument("--managed-root")
    collect.add_argument("--minimum-free-bytes", type=int, default=0)
    collect.add_argument("--writer-unresolved", action="store_true")
    collect.add_argument("--output", required=True, type=Path)
    collect.set_defaults(handler=do_collect)

    gc = sub.add_parser("gc", help="collect expired managed backups (dry run by default)")
    gc.add_argument("--root", required=True)
    gc.add_argument("--ordinary-days", type=int, default=14)
    gc.add_argument("--critical-days", type=int, default=90)
    gc.add_argument("--approve-critical", action="store_true")
    gc.add_argument("--writer-unresolved", action="store_true")
    gc.add_argument("--apply", action="store_true", help="actually remove (otherwise a dry run)")
    gc.add_argument("--output", required=True, type=Path)
    gc.set_defaults(handler=do_gc)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
