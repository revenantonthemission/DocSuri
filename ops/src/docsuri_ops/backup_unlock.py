"""`docsuri-backup-unlock`: the backup volume's unlock job (U8 plan Step 35; BR6.11,
NFR3.5, NFR7.3, Workflow 20 step 8).

The root job `org.docsuri.v2.backup-unlock` runs at boot and every 60 seconds. Each run:

1. reads the volume `DocSuri_Backup` with `diskutil info`; when it is absent, or present
   and already unlocked, there is nothing to do;
2. when it is present and locked, reads its passphrase from the System keychain as root
   (`security find-generic-password -s DocSuri_Backup -w`) and passes it to `diskutil
   apfs unlockVolume <device> -stdinpassphrase` on standard input only;
3. reads the volume again, which must now be unlocked.

A run that cannot unlock records its fixed reason, and the next run, a minute later,
tries again. The passphrase never appears in an argument, an environment variable, a
file or a log line, and is dropped as soon as the unlock returns. Every tool runs through
one `run` callable, so the sequence and its retry are tested against recorded output.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from docsuri_ops.arrangement.paths import ArrangementPaths

VOLUME = "DocSuri_Backup"
DISKUTIL = "/usr/sbin/diskutil"
SECURITY = "/usr/bin/security"
SYSTEM_KEYCHAIN = "/Library/Keychains/System.keychain"
LOG = "backup-unlock.jsonl"
SECONDS = 60
DEVICE = re.compile(r"^\s*Device Identifier:\s*(disk\d+s\d+)\s*$", re.MULTILINE)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _info(run: Callable) -> tuple[dict | None, str]:
    from .isolation_macos import parse_diskutil_info

    completed = run([DISKUTIL, "info", VOLUME], capture_output=True, timeout=SECONDS,
                    check=False)
    text = (completed.stdout or b"").decode("utf-8", "replace")
    if completed.returncode == 1:
        # A missing volume's `Could not find disk` line is on standard error, exit 1
        # (measured on this Mac, U8 plan Step 74(d)).
        text += (getattr(completed, "stderr", None) or b"").decode("utf-8", "replace")
    return parse_diskutil_info(text), text


def once(*, run: Callable = subprocess.run) -> str:
    """One run: `absent`, `unlocked` (nothing to do), `unlocked-now`, or a fixed reason
    the next run retries after."""
    found, text = _info(run)
    if found is None:
        return "volume-unreadable"
    if not found["present"]:
        return "absent"
    if not found.get("locked"):
        return "unlocked"
    device = DEVICE.search(text)
    if device is None:
        return "device-unknown"
    secret = run([SECURITY, "find-generic-password", "-s", VOLUME, "-w", SYSTEM_KEYCHAIN],
                 capture_output=True, timeout=SECONDS, check=False)
    passphrase = (secret.stdout or b"").rstrip(b"\n")
    if secret.returncode != 0 or not passphrase:
        return "passphrase-unavailable"
    try:
        unlocked = run([DISKUTIL, "apfs", "unlockVolume", device.group(1), "-stdinpassphrase"],
                       input=passphrase, capture_output=True, timeout=SECONDS, check=False)
    finally:
        passphrase = b""
    if unlocked.returncode != 0:
        return "unlock-refused"
    again, _ = _info(run)
    if again is None or again.get("locked"):
        return "still-locked"
    return "unlocked-now"


def main(argv: list[str] | None = None, *, run: Callable = subprocess.run,
         paths: ArrangementPaths | None = None,
         clock: Callable[[], dt.datetime] = _now) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments or any(name.startswith(("PYTHON", "DYLD_", "LD_")) for name in os.environ):
        print(json.dumps({"ok": False, "reason": "invocation-refused"}))
        return 2
    outcome = once(run=run)
    ok = outcome in ("absent", "unlocked", "unlocked-now")
    line = {"ts": clock().isoformat(timespec="seconds"), "ok": ok, "outcome": outcome}
    folder: Path = (paths or ArrangementPaths()).control_logs
    try:
        descriptor = os.open(folder / LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND |
                             os.O_NOFOLLOW, 0o600)
        try:
            os.write(descriptor, json.dumps(line, sort_keys=True).encode() + b"\n")
        finally:
            os.close(descriptor)
    except OSError:
        pass  # the outcome still goes to standard output
    print(json.dumps(line))
    return 0 if ok else 1
