"""The availability record (U8 plan Step 35; observability-design § 12, reliability-design
§ 2, NFR7.1, NFR9.13, O7).

- **Where.** `availability/` (production: `/Library/DocSuri/availability/`), the
  scheduler account's folder at mode 0755, its files 0644, so every account reads it and
  only the scheduler account writes. It holds no personal data.
- **Files.** One JSON Lines file per calendar month in Asia/Seoul, `YYYY-MM.jsonl`.
- **One line per slot**, appended and synced to disk: `slot` (the slot's start, UTC,
  ISO 8601), `up`, and `reason`, a fixed key (`REASONS`: `public-timeout` and
  `local-timeout` since Step 58(e); `probe-timeout` stays readable for earlier lines).
  If a slot ever has two lines, readers keep the first, and the writer never adds a
  second.
- **The month's figure.** Up slots over every scheduled slot of the month so far, a
  missing slot counting as down, from admission opening in its first month; the error
  budget is 1% of the month's slots, and the budget left is what the down slots have not
  used.
- **Retention.** Files older than 13 months are deleted by housekeeping.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .lanes import SEOUL, SLOT_SECONDS, slot_of

# `public-timeout` and `local-timeout` replace `probe-timeout` (Step 58(e), L1-30); the
# heartbeat never writes it again, but earlier lines holding it stay valid and count as
# unattributed.
REASONS = ("ok", "public-not-ready", "local-not-ready", "public-unreachable",
           "local-unreachable", "maintenance", "public-timeout", "local-timeout",
           "probe-timeout")
FOLDER_MODE = 0o755
FILE_MODE = 0o644
OBJECTIVE = 0.99
MAX_FILE = 16 * 1024 * 1024


def _iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def month_of(slot: dt.datetime) -> str:
    return slot.astimezone(SEOUL).strftime("%Y-%m")


def month_bounds(month: str) -> tuple[dt.datetime, dt.datetime]:
    year, number = (int(part) for part in month.split("-"))
    start = dt.datetime(year, number, 1, tzinfo=SEOUL)
    days = calendar.monthrange(year, number)[1]
    return start.astimezone(dt.UTC), (start + dt.timedelta(days=days)).astimezone(dt.UTC)


@dataclass(frozen=True)
class Figure:
    month: str
    scheduled: int
    up: int
    down: int
    ratio: float
    budget_slots: int
    budget_left_seconds: int

    def as_dict(self) -> dict:
        return {"month": self.month, "scheduledSlots": self.scheduled, "upSlots": self.up,
                "downSlots": self.down, "availability": round(self.ratio, 6),
                "budgetSlots": self.budget_slots, "budgetLeftSeconds": self.budget_left_seconds}


class AvailabilityRecord:
    def __init__(self, folder: Path, *, slot_seconds: int = SLOT_SECONDS):
        self.folder, self.slot_seconds = folder, slot_seconds

    def _ensure_folder(self) -> None:
        if self.folder.is_symlink():
            raise ValueError("the availability folder cannot be a link")
        self.folder.mkdir(mode=FOLDER_MODE, parents=True, exist_ok=True)
        os.chmod(self.folder, FOLDER_MODE, follow_symlinks=False)

    def path(self, month: str) -> Path:
        return self.folder / f"{month}.jsonl"

    def lines(self, month: str) -> list[dict]:
        """Every well-formed line of the month, the first per slot kept."""
        try:
            descriptor = os.open(self.path(month), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return []
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return []
            raw = os.read(descriptor, MAX_FILE)
        finally:
            os.close(descriptor)
        kept: dict[str, dict] = {}
        for line in raw.splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if not isinstance(value, dict) or set(value) != {"slot", "up", "reason"}:
                continue
            kept.setdefault(value["slot"], value)
        return list(kept.values())

    def append(self, slot: dt.datetime, up: bool, reason: str) -> bool:
        """The slot's line, synced; False when the slot already has one (the first is
        kept)."""
        if reason not in REASONS or (reason == "ok") != up:
            raise ValueError("an availability line has a fixed reason, ok only when up")
        start = slot_of(slot, self.slot_seconds)
        month = month_of(start)
        if any(line["slot"] == _iso(start) for line in self.lines(month)):
            return False
        self._ensure_folder()
        path = self.path(month)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                             FILE_MODE)
        try:
            os.fchmod(descriptor, FILE_MODE)
            payload = json.dumps({"slot": _iso(start), "up": up, "reason": reason},
                                 sort_keys=True).encode() + b"\n"
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return True

    def figure(self, month: str, now: dt.datetime, *,
               opened_at: dt.datetime | None = None) -> Figure:
        """Up slots over every scheduled slot of the month up to `now`, from admission
        opening in its first month; a missing slot counts as down."""
        start, end = month_bounds(month)
        if opened_at is not None and opened_at > start:
            start = slot_of(opened_at, self.slot_seconds)
        until = min(end, now)
        scheduled = max(0, int((until - start).total_seconds()) // self.slot_seconds)
        up = sum(1 for line in self.lines(month)
                 if line["up"] is True and start <= _parse(line["slot"]) < until)
        down = scheduled - up
        month_slots = int((end - start).total_seconds()) // self.slot_seconds
        budget = int(month_slots * (1 - OBJECTIVE))
        ratio = 1.0 if scheduled == 0 else up / scheduled
        left = max(0, budget - down) * self.slot_seconds
        return Figure(month, scheduled, up, down, ratio, budget, left)

    def prune(self, now: dt.datetime, *, months: int = 13) -> list[str]:
        """Delete month files older than `months` months (housekeeping); never through a
        link, and only this record's own files."""
        local = now.astimezone(SEOUL)
        index = local.year * 12 + local.month - 1 - months
        oldest = f"{index // 12:04d}-{index % 12 + 1:02d}"
        removed = []
        if not self.folder.is_dir() or self.folder.is_symlink():
            return removed
        for entry in sorted(os.scandir(self.folder), key=lambda item: item.name):
            name = entry.name
            if not name.endswith(".jsonl") or entry.is_symlink() or not entry.is_file(
                follow_symlinks=False
            ):
                continue
            month = name.removesuffix(".jsonl")
            if len(month) == 7 and month < oldest:
                os.unlink(self.folder / name)
                removed.append(month)
        return removed
