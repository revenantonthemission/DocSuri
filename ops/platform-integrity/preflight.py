"""Readonly host/release preflight. Failure is data, not permission to alter the host.

This command never enables FileVault, formats a drive, switches Docker contexts or restarts a
service. A release operator supplies an existing mounted removable drive and verified evidence.
"""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from docsuri_platform_integrity.application.receipts import verify_evidence
from docsuri_platform_integrity.contracts.codec import decode
from docsuri_platform_integrity.deployment.receipt import Capability
from docsuri_platform_integrity.deployment.receipt_policy import PolicySnapshot, load_policy


def preflight(*, root: Path, drive: Path | None, peak_bytes: int, evidence: dict,
               policy: PolicySnapshot | None, clock=None) -> dict:
    reasons = []
    free = shutil.disk_usage(root).free
    if peak_bytes < 0 or free < 10 * 1024**3 + 2 * peak_bytes:
        reasons.append("disk_reserve")
    if drive is None or not drive.is_dir() or drive.is_symlink():
        reasons.append("removable_drive_unverified")
    elif os.stat(root).st_dev == os.stat(drive).st_dev:
        reasons.append("backup_on_same_filesystem")
    if sys.platform != "darwin":
        reasons.append("native_macos_required")
    else:
        try:
            process = subprocess.run(
                ["/usr/bin/fdesetup", "status"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if process.returncode or "FileVault is On." not in process.stdout:
                reasons.append("filevault_unverified")
        except (OSError, subprocess.TimeoutExpired):
            reasons.append("filevault_unavailable")
    # Existence/booleans in a caller file are NOT proof. A capability counts only when a
    # receipt signed by a key the release manifest trusts, bound to this host, this
    # release and this capability, verifies inside its validity window.
    proven = frozenset()
    unproven = {cap.value: "unproven" for cap in Capability}
    if policy is None:
        reasons.append("receipt_policy_unavailable")
    else:
        try:
            proven, unproven = verify_evidence(policy, evidence, clock=clock)
        except Exception:
            reasons.append("receipt_verification_unavailable")
    for capability, reason in sorted(unproven.items()):
        reasons.append(f"{capability}_{reason}")
    return {
        "ready": not reasons,
        "freeBytes": free,
        "requiredFreeBytes": 10 * 1024**3 + 2 * max(0, peak_bytes),
        "reasons": reasons,
        "provenCapabilities": sorted(proven),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--drive", type=Path)
    parser.add_argument("--estimated-peak-bytes", type=int, required=True)
    parser.add_argument("--profile", choices=("test", "production"), default="test")
    parser.add_argument("--release", required=True,
                        help="expected release; trust comes from its protected policy")
    parser.add_argument(
        "--evidence", type=Path,
        help="JSON evidence: {release, receipts: {capability: envelope}}; no trust inputs")
    args = parser.parse_args()
    evidence = {"release": args.release, "receipts": {}}
    if args.evidence is not None:
        try:
            fd = os.open(args.evidence, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 1_048_576:
                    raise ValueError("evidence bounds")
                evidence = decode(stream.read(1_048_577), max_bytes=1_048_576)
            if (not isinstance(evidence, dict) or set(evidence) != {"release", "receipts"}
                or evidence["release"] != args.release
                or not isinstance(evidence["receipts"], dict)):
                raise ValueError("evidence fields")
        except Exception:
            print(json.dumps({"ready": False, "provenCapabilities": [],
                              "reasons": ["evidence_invalid_or_contains_trust"]}))
            return 2
    try:
        policy = load_policy(args.profile, args.release)
    except Exception:
        policy = None
    result = preflight(
        root=args.root, drive=args.drive, peak_bytes=args.estimated_peak_bytes, evidence=evidence,
        policy=policy,
    )
    print(json.dumps(result))
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
