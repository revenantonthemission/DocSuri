"""`docsuri-pf-load`: the packet filter's boot job (U8 plan Step 35; D10, BR6.11, NFR3.8,
security-design § 6.8).

The root job `org.docsuri.v2.pf` loads DocSuri's anchor file, `/etc/pf.anchors/
org.docsuri.v2`, under the system's own `com.apple/*` anchor point, so `/etc/pf.conf`,
which macOS updates may replace, is never edited, then enables the filter. The sequence
is fixed:

1. the anchor file is a root-owned regular file no other account can write;
2. `pfctl -a com.apple/org.docsuri.v2 -f /etc/pf.anchors/org.docsuri.v2` loads it;
3. `pfctl -E` enables the filter (taking a reference, so the system's own use is kept);
4. `pfctl -s info` must then read `Status: Enabled`.

Each run writes one line to `control/logs/pf-load.jsonl` with the steps done and, on a
failure, the step's fixed reason key. Every tool runs through one `run` callable, so the
sequence is tested against recorded tool output.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from docsuri_ops.arrangement.paths import ArrangementPaths

PFCTL = "/sbin/pfctl"
ANCHOR = "com.apple/org.docsuri.v2"
ANCHOR_FILE = Path("/etc/pf.anchors/org.docsuri.v2")
LOG = "pf-load.jsonl"
SECONDS = 30


class LoadFailed(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def load(*, run: Callable = subprocess.run, anchor_file: Path = ANCHOR_FILE,
         owner_uid: int = 0) -> list[str]:
    """The fixed sequence; returns the steps done, raises `LoadFailed` at the first
    that fails."""
    from .isolation_macos import parse_pf_info

    done: list[str] = []
    try:
        info = anchor_file.lstat()
    except OSError:
        raise LoadFailed("anchor-missing") from None
    if not stat.S_ISREG(info.st_mode) or info.st_uid != owner_uid or info.st_mode & 0o022:
        raise LoadFailed("anchor-custody")
    done.append("anchor-checked")
    steps = (
        ("anchor-loaded", [PFCTL, "-a", ANCHOR, "-f", str(anchor_file)]),
        ("filter-enabled", [PFCTL, "-E"]),
    )
    for name, argv in steps:
        completed = run(argv, capture_output=True, timeout=SECONDS, check=False)
        if completed.returncode != 0:
            raise LoadFailed(f"{name.split('-')[0]}-refused")
        done.append(name)
    status = run([PFCTL, "-s", "info"], capture_output=True, timeout=SECONDS, check=False)
    text = (status.stdout or b"").decode("utf-8", "replace")
    if status.returncode != 0 or parse_pf_info(text) is not True:
        raise LoadFailed("filter-not-enabled")
    done.append("filter-confirmed")
    return done


def record(folder: Path, line: dict) -> None:
    try:
        descriptor = os.open(folder / LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                             0o600)
    except OSError:
        return
    try:
        os.write(descriptor, json.dumps(line, sort_keys=True).encode() + b"\n")
    finally:
        os.close(descriptor)


def main(argv: list[str] | None = None, *, run: Callable = subprocess.run,
         paths: ArrangementPaths | None = None, anchor_file: Path = ANCHOR_FILE,
         owner_uid: int = 0, clock: Callable[[], dt.datetime] = _now) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments or any(name.startswith(("PYTHON", "DYLD_", "LD_")) for name in os.environ):
        print(json.dumps({"ok": False, "reason": "invocation-refused"}))
        return 2
    folder = (paths or ArrangementPaths()).control_logs
    try:
        done = load(run=run, anchor_file=anchor_file, owner_uid=owner_uid)
    except LoadFailed as failure:
        line = {"ts": clock().isoformat(timespec="seconds"), "ok": False,
                "reason": failure.reason}
        record(folder, line)
        print(json.dumps(line))
        return 1
    line = {"ts": clock().isoformat(timespec="seconds"), "ok": True, "steps": done}
    record(folder, line)
    print(json.dumps(line))
    return 0
