#!/usr/bin/env python3
"""Backup evidence and retention for the operator seams.

    backup_evidence.py collect --cut-us N --generation sha256:... --source DUMP \\
        --archive-root /Volumes/DocSuri_Backup --restore-root /Volumes/Restore \\
        --key /path/to/key --clock-evidence /path/to/clock.json --output report.json

    backup_evidence.py gc --root /Volumes/DocSuri_Backup --output gc.json \
        [--apply] [--approve-critical]

`gc` is a dry run unless --apply is given, and it only ever removes directories carrying the
managed marker. Pre-existing operator archives are reported as `unmanaged` and left alone.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from docsuri_platform_integrity.domain.retention import RetentionPolicy  # noqa: E402

from docsuri_ops.adapters.backup import (  # noqa: E402
    LocalDriveArchive,
    LocalKeyLock,
    LocalRestoreTarget,
)
from docsuri_ops.backup_evidence import (  # noqa: E402
    BackupCut,
    collect_backup_evidence,
    collect_expired_backups,
)


def _emit(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
