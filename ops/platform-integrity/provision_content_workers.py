#!/usr/bin/env python3
"""Provision launchd worker services for REM-2 content jobs."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

REALM_ROOT = Path("/Library/Application Support/DocSuri/rem-2")
WORKER_UIDS = {
    "translate": 700,
    "summarize": 701,
    "novelty": 702,
    "evidence": 703,
}
GROUP = "_docsuri_rem2_worker"
GROUP_GID = 700
GROUP_NAME = "_docsuri_rem2_worker"
LABEL_PREFIX = "rem-2-content"


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}: {result.stderr}")
    return result


def ensure_group_and_users() -> None:
    """Ensure the group and user accounts exist with correct UID/GID."""
    try:
        run_cmd(["dscl", ".", "-read", f"/Groups/{GROUP}"], check=True)
    except RuntimeError:
        run_cmd(["dscl", ".", "-create", f"/Groups/{GROUP}"])
        run_cmd(["dscl", ".", "-create", f"/Groups/{GROUP}", "PrimaryGroupID", str(GROUP_GID)])
        run_cmd(["dscl", ".", "-create", f"/Groups/{GROUP}", "RealName", "DocSuri REM-2 Workers"])
        run_cmd(["dscl", ".", "-create", f"/Groups/{GROUP}", "Password", "*"])

    for worker_type, uid in WORKER_UIDS.items():
        username = f"_docsuri_rem2_{worker_type}"
        try:
            run_cmd(["dscl", ".", "-read", f"/Users/{username}"], check=True)
            result = run_cmd(["dscl", ".", "-read", f"/Users/{username}", "UniqueID", "PrimaryGroupID"], check=True)
            if f"UniqueID: {uid}" not in result.stdout or f"PrimaryGroupID: {GROUP_GID}" not in result.stdout:
                raise RuntimeError(f"Existing user {username} has wrong UID/GID")
        except RuntimeError:
            run_cmd(["dscl", ".", "-create", f"/Users/{username}"])
            run_cmd(["dscl", ".", "-create", f"/Users/{username}", "UniqueID", str(uid)])
            run_cmd(["dscl", ".", "-create", f"/Users/{username}", "PrimaryGroupID", str(GROUP_GID)])
            run_cmd(["dscl", ".", "-create", f"/Users/{username}", "UserShell", "/usr/bin/false"])
            run_cmd(["dscl", ".", "-create", f"/Users/{username}", "NFSHomeDirectory", "/var/empty"])
            run_cmd(["dscl", ".", "-create", f"/Users/{username}", "IsHidden", "1"])
            run_cmd(["dscl", ".", "-create", f"/Users/{username}", "RealName", f"DocSuri REM-2 {worker_type.title()} Worker"])
            run_cmd(["dscl", ".", "-create", f"/Users/{username}", "Password", "*"])
            run_cmd(["dscl", ".", "-append", f"/Groups/{GROUP}", "GroupMembership", f"_docsuri_rem2_{worker_type}"])


def create_plist(label: str, worker_type: str, uid: int, gid: int, working_dir: Path) -> bytes:
    """Create a launchd plist matching the working rem-1 pattern."""
    result = {
        "Label": f"org.docsuri.{label}",
        "UserName": "root",
        "GroupName": "wheel",
        "InitGroups": False,
        "Umask": 0o077,
        "WorkingDirectory": str(working_dir),
        "ProcessType": "Background",
        "ThrottleInterval": 5,
        "ExitTimeOut": 30,
        "RunAtLoad": False,
        "StandardOutPath": str(working_dir / "logs" / f"{worker_type}.out"),
        "StandardErrorPath": str(working_dir / "logs" / f"{worker_type}.err"),
        "SoftResourceLimits": {"NumberOfFiles": 256, "Core": 0},
        "HardResourceLimits": {"NumberOfFiles": 256, "Core": 0},
        "ProgramArguments": [
            "/usr/bin/env",
            "-i",
            "PATH=/usr/bin:/bin",
            "LANG=en_US.UTF-8",
            "HOME=/var/empty",
            f"PYTHONPATH={working_dir}/lib",
            "/usr/bin/python3.13",
            "-B",
            str(Path("/Library/Application Support/DocSuri/rem-2/workers") / worker_type / f"{worker_type}_worker.py"),
            "run",
            "--state",
            str(working_dir / "job.json"),
            "--",
            "--capability",
            "nts_clock",
            "--days",
            "1",
        ],
    }
    return plistlib.dumps(result, sort_keys=True)


def install(worker_type: str, replace: bool = False) -> None:
    label = f"{LABEL_PREFIX}-{worker_type}"
    working_dir = REALM_ROOT / "workers" / worker_type
    plist_path = Path("/Library/LaunchDaemons") / f"org.docsuri.{label}.plist"

    if replace:
        subprocess.run(["launchctl", "bootout", f"system/{label}"], capture_output=True)
        if plist_path.exists():
            plist_path.unlink()
        if working_dir.exists():
            for path in sorted(working_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.chmod(0o700)
                    path.unlink()
                elif path.is_dir():
                    path.chmod(0o700)
                    path.rmdir()

    working_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    (working_dir / "logs").mkdir(parents=True, exist_ok=True, mode=0o700)

    # Copy worker script
    source = Path(__file__).resolve().parent / "workers" / f"{worker_type}_worker.py"
    dest = working_dir / f"{worker_type}_worker.py"
    shutil.copy2(source, dest)
    os.chown(dest, 0, 0)
    dest.chmod(0o555)

    # Copy the job state template
    job_state = {
        "profile": "test",
        "release": "r1-clock-20260927-r3",
        "keychain": "/Library/Application Support/DocSuri/rem-1-test/sign/r1t-clock-20260927-r3--k1.keychain-db",
        "policyPath": "/Library/Application Support/DocSuri/rem-1-test/receipt-policy/r1t-clock-20260927-r3.json",
        "policyDigest": "sha256:...",
        "interpreter": "/usr/bin/python3.13",
        "interpreterDigest": "sha256:...",
        "bundledLibrary": "sha256:...",
        "library": str(working_dir / "lib"),
        "libraryFiles": {},
        "bootstrap": str(working_dir / "bootstrap.py"),
        "issuer": str(working_dir / "issue_receipt.py"),
        "issuerDigest": "sha256:...",
        "results": str(working_dir / "results"),
        "uid": WORKER_UIDS[worker_type],
        "gid": 700,
    }
    import json
    state_path = working_dir / "job.json"
    state_path.write_text(json.dumps(job_state, indent=2, sort_keys=True) + "\n")
    os.chown(state_path, 0, 0)
    state_path.chmod(0o444)

    # Install library (shadow the platform_integrity package)
    library_src = Path("/Users/revenantonthemission/Projects/DocSuri/platform_integrity/src")
    library_dst = working_dir / "lib"
    if library_dst.exists():
        shutil.rmtree(library_dst)
    shutil.copytree(src=library_src, dst=library_dst)
    for root, dirs, files in os.walk(library_dst):
        for d in dirs:
            os.chmod(Path(root) / d, 0o700)
        for f in files:
            p = Path(root) / f
            os.chown(p, 0, 0)
            p.chmod(0o444)
    os.chown(library_dst, 0, 0)
    library_dst.chmod(0o700)

    plist_data = create_plist(label, worker_type, WORKER_UIDS[worker_type], 700, working_dir)
    plist_path = Path("/Library/LaunchDaemons") / f"org.docsuri.{label}.plist"
    plist_path.write_bytes(plist_data)
    os.chown(plist_path, 0, 0)
    plist_path.chmod(0o644)

    # Bootstrap
    result = subprocess.run(
        ["launchctl", "bootstrap", "system", str(plist_path)],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"stdout: {result.stdout}", file=sys.stderr)
        print(f"stderr: {result.stderr}", file=sys.stderr)
        raise RuntimeError(f"launchctl bootstrap failed: {result.stderr.decode().strip()}")

    print(json.dumps({
        "state": "INSTALLED",
        "label": label,
        "plist": str(plist_path),
        "working_dir": str(working_dir),
    }, indent=2))


def uninstall(worker_type: str) -> None:
    label = f"{LABEL_PREFIX}-{worker_type}"
    plist_path = Path("/Library/LaunchDaemons") / f"org.docsuri.{label}.plist"

    subprocess.run(["launchctl", "bootout", f"system/{label}"], capture_output=True, check=False)

    if plist_path.exists():
        plist_path.unlink()

    print(json.dumps({"state": "UNINSTALLED", "label": label}))


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision launchd worker services for REM-2 content jobs.")
    parser.add_argument("--profile", choices=("test", "production"), default="test")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("worker_type", nargs="?", choices=["translate", "summarize", "novelty", "evidence", "all"])

    args = parser.parse_args()

    if os.geteuid() != 0:
        print("This script must be run as root", file=sys.stderr)
        return 1

    if args.uninstall:
        if args.worker_type == "all" or args.worker_type is None:
            for wt in ["translate", "summarize", "novelty", "evidence"]:
                uninstall(wt)
        else:
            uninstall(args.worker_type)
        return 0

    # Ensure group and users exist first
    ensure_group_and_users()

    if args.worker_type == "all" or args.worker_type is None:
        for wt in ["translate", "summarize", "novelty", "evidence"]:
            install(wt, replace=args.replace)
    else:
        install(args.worker_type, replace=args.replace)

    return 0


if __name__ == "__main__":
    sys.exit(main())
