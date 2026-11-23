"""The migration's isolation gate (U8 plan Step 31; BR6.12, BR8.11).

The migration tool reads the runtime isolation evidence directly from its folder, never
through ServiceOperations: the newest result there must have passed and be within the
freshness bound (15 minutes, `isolation_freshness_seconds`). A dry run starts only
then; the tool reads it again at every phase boundary and at least once per freshness
bound during a phase, and a lapse interrupts the run.

A result is one JSON file: production's root check writes `{"passed": true, "checkedAt":
...}` into `evidence/isolation/`, and the composed realm's driver writes its stand-in
`{"result": "passed", "standin": true, "checkedAt": ...}` into `platform/isolation/`.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

MAX_RESULT = 256 * 1024
MAX_FILES = 10_000


@dataclass(frozen=True)
class Reading:
    passed: bool
    reason: str
    checked_at: dt.datetime | None = None


def _parse(text) -> dt.datetime | None:
    try:
        moment = dt.datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def _result(path: Path) -> dict | None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RESULT:
            return None
        value = json.loads(os.read(descriptor, MAX_RESULT))
    except (OSError, ValueError):
        return None
    finally:
        os.close(descriptor)
    return value if isinstance(value, dict) else None


class IsolationGate:
    def __init__(self, folder: Path, *, freshness_seconds: int,
                 clock: Callable[[], dt.datetime]):
        self.folder, self.freshness, self.clock = folder, freshness_seconds, clock

    def latest(self) -> dict | None:
        try:
            names = sorted(entry.name for entry in os.scandir(self.folder)
                           if entry.name.endswith(".json"))[-MAX_FILES:]
        except OSError:
            return None
        results = [value for value in (_result(self.folder / name) for name in names)
                   if value is not None and _parse(value.get("checkedAt")) is not None]
        return max(results, key=lambda value: _parse(value["checkedAt"]), default=None)

    def read(self) -> Reading:
        result = self.latest()
        if result is None:
            return Reading(False, "isolation-evidence-missing")
        checked = _parse(result["checkedAt"])
        passed = result.get("passed") is True or result.get("result") == "passed"
        if not passed:
            return Reading(False, "isolation-failed", checked)
        if (self.clock() - checked).total_seconds() > self.freshness:
            return Reading(False, "isolation-stale", checked)
        return Reading(True, "isolation-passed", checked)
