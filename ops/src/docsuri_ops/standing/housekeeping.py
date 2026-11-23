"""The hourly housekeeping lane (U8 plan Step 35; reliability-design § 11, observability-design
§ 3.1 and § 12, NFR7.10).

Each run, under the standing authority:

- expires every recovery request not admitted, or not started, within the 24-hour start
  bound (`RecoveryRequests.expire_due`);
- deletes observations older than 14 days, in bounded batches through the operations
  owner's deletion function (`ObservationStore.delete_old`);
- deletes the availability record's month files older than 13 months;
- deletes the start record's day files more than 14 days old, judged by name
  (`prunedStarts`, U8 plan Step 66(e)).

Each part runs on its own, so one that fails (a busy database, a damaged ledger) never
stops the others; the run reports each part's count or its failure's type.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

MAX_BATCHES = 20
START_DAYS = 14
_DAY_FILE = re.compile(r"(\d{4}-\d{2}-\d{2})\.jsonl")


def _nothing(now: dt.datetime) -> list[str]:
    return []


def starts_pruner(folder: Path, *, days: int = START_DAYS
                  ) -> Callable[[dt.datetime], list[str]]:
    """The start record's day files more than `days` days before `now`'s UTC day deleted,
    judged by name; never through a link, and only this record's own files."""

    def prune(now: dt.datetime) -> list[str]:
        today = now.astimezone(dt.UTC).date()
        removed: list[str] = []
        if not folder.is_dir() or folder.is_symlink():
            return removed
        for entry in sorted(os.scandir(folder), key=lambda item: item.name):
            matched = _DAY_FILE.fullmatch(entry.name)
            if matched is None or entry.is_symlink() or not entry.is_file(
                    follow_symlinks=False):
                continue
            try:
                day = dt.date.fromisoformat(matched.group(1))
            except ValueError:
                continue
            if (today - day).days > days:
                os.unlink(folder / entry.name)
                removed.append(matched.group(1))
        return removed

    return prune


@dataclass
class Housekeeping:
    expire_requests: Callable[[], list[str]]
    delete_observations: Callable[[dt.datetime], int]
    prune_availability: Callable[[dt.datetime], list[str]]
    prune_starts: Callable[[dt.datetime], list[str]] = field(default=_nothing)
    batch: int = 1000

    def run(self, now: dt.datetime) -> dict:
        report: dict = {}
        for name, part in (("expiredRequests", lambda: len(self.expire_requests())),
                           ("deletedObservations", lambda: self._observations(now)),
                           ("prunedMonths", lambda: len(self.prune_availability(now))),
                           ("prunedStarts", lambda: len(self.prune_starts(now)))):
            try:
                report[name] = part()
            except Exception as error:  # noqa: BLE001 - one part never stops the others
                report[name] = f"failed:{type(error).__name__}"
        return report

    def _observations(self, now: dt.datetime) -> int:
        total = 0
        for _ in range(MAX_BATCHES):
            deleted = int(self.delete_observations(now))
            total += deleted
            if deleted < self.batch:
                break
        return total
