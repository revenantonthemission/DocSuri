"""The processes' failure counts (U8 plan Step 51(a), L1-29).

- **Writing.** `ProcessCounts(folder, process, *, policy, clock)` belongs to one v2
  process (`host`, `workers` or `scheduler`). `record(kind, *, failed)` adds one run to a
  registered kind's total, and to its failed count when `failed`, in the window open at
  the clock's now. A window is `policy.latency_window_seconds` long, aligned to the
  epoch. The first `record` after a window ends, and `close()`, append that window's
  lines to `<process>-counts-<UTC date of the window's start>.jsonl`: one line per kind
  counted in it, `{"failed": n, "kind": k, "total": m, "window": "<start>Z"}`, with
  sorted keys and no identifier or path.
- **Files.** Each append opens the folder with `O_DIRECTORY | O_NOFOLLOW` (making it
  0700 when absent) and the day file through the folder's descriptor with `O_NOFOLLOW`
  at 0600. A file whose last byte is not a newline (a cut write) gets one first. The
  lines are written until every byte is out (a short write goes on), then the file is
  synced; a failed sync after a complete write is logged and the lines count as
  written. When a write raises part way, every line whose bytes all reached the file
  counts as written, even one whose newline is missing (the next append's leading
  newline ends it and it parses), and only the lines after it stay pending; a line cut
  part way is left in the file and skipped when read, so no window is counted
  twice. Each append also removes this
  process's own day files whose day ended at least `policy.latency_retention_seconds`
  ago, regular files only. A failed append or removal is logged (`counts.unwritten`,
  with the error's type) and never fails a run; an unwritten window is kept for the next
  append.
- **Reading.** `counts_over(folder, kinds, now)` sums every process's lines whose window
  started in the 24 hours before `now`, reading only the two UTC days that can hold
  them. A line that is not JSON is skipped (one `counts.line-unread` line per read); a
  parsed line outside the shape raises `ValueError`.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import stat
import threading
from collections.abc import Callable, Iterable
from pathlib import Path

PROCESSES = ("host", "workers", "scheduler")
FOLDER_MODE, FILE_MODE = 0o700, 0o600
READ_HOURS = 24
# The registered kinds (Step 51(a)); Step 53(h) adds the account-mail sender's kind and
# Step 56(c) the providers' four kinds.
KINDS: set[str] = {
    "postgresql.connection", "postgresql.transaction",
    # The account-mail sender's failed runs (Step 53(h); your answer of 2026-11-08, L1-70).
    "mail.sender",
    # Each provider's answered calls and its refusals and over-limit answers, counted at
    # U8's composition seams (Step 56(c); your answer L1-12, "At the U8 seams").
    "provider.google", "provider.orcid", "provider.resend", "provider.notion",
}
_KINDS_LOCK = threading.Lock()
_KIND_FORM = re.compile(r"[a-z][a-z0-9._-]{0,63}")
_WINDOW_FORM = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_DAY_FILE = re.compile(r"(host|workers|scheduler)-counts-([0-9]{4}-[0-9]{2}-[0-9]{2})\.jsonl")
_LINE_KEYS = frozenset({"failed", "kind", "total", "window"})


def register_kind(kind: str) -> None:
    """Register one more counted kind (a fixed key)."""
    if not isinstance(kind, str) or _KIND_FORM.fullmatch(kind) is None:
        raise ValueError("a counted kind must be a fixed key")
    with _KINDS_LOCK:
        KINDS.add(kind)


def _log(component: str, event: str, **fields) -> None:
    from .log_events import current

    current().event(component, event, "warning", **fields)


def _utc(moment: dt.datetime) -> dt.datetime:
    if moment.tzinfo is None:  # a naive instant is read as UTC, never as local time
        return moment.replace(tzinfo=dt.UTC)
    return moment.astimezone(dt.UTC)


def _window_text(start: dt.datetime) -> str:
    return start.isoformat(timespec="seconds").replace("+00:00", "Z")


class _PartlyWritten(Exception):
    """A write that raised after its first `lines` lines had all reached the file."""

    def __init__(self, lines: int):
        super().__init__("a count file write ended early")
        self.lines = lines


def _open_folder(folder: Path, *, create: bool) -> int | None:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        return os.open(folder, flags)
    except FileNotFoundError:
        if not create:
            return None
    try:
        os.mkdir(folder, FOLDER_MODE)
    except FileExistsError:
        pass
    return os.open(folder, flags)


class ProcessCounts:
    """One process's per-window failure counts, appended to its day files."""

    def __init__(self, folder: Path, process: str, *, policy,
                 clock: Callable[[], dt.datetime]):
        if process not in PROCESSES:
            raise ValueError("unknown counted process")
        self.folder = Path(folder)
        self.process = process
        self.policy = policy
        self.clock = clock
        self._seconds = int(policy.latency_window_seconds)
        if self._seconds <= 0:
            raise ValueError("the counts' window must be positive")
        self._lock = threading.Lock()
        self._window: dt.datetime | None = None
        self._counts: dict[str, list[int]] = {}
        # Lines not yet written, each with its day file's date.
        self._pending: list[tuple[str, str]] = []
        self._closed = False

    def _start_of(self, now: dt.datetime) -> dt.datetime:
        seconds = int(now.timestamp()) // self._seconds * self._seconds
        return dt.datetime.fromtimestamp(seconds, dt.UTC)

    def record(self, kind: str, *, failed: bool) -> None:
        if kind not in KINDS:
            raise ValueError("unregistered counted kind")
        with self._lock:
            if self._closed:
                return
            now = _utc(self.clock())
            start = self._start_of(now)
            if self._window is not None and start != self._window:
                self._end_window()
                self._append(now)
            self._window = start
            counted = self._counts.setdefault(kind, [0, 0])
            counted[1] += 1
            if failed:
                counted[0] += 1

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._end_window()
            if self._pending:
                self._append(_utc(self.clock()))

    def _end_window(self) -> None:
        """Move the open window's lines to the pending list (lock held)."""
        if self._window is None:
            return
        window, day = _window_text(self._window), f"{self._window:%Y-%m-%d}"
        for kind in sorted(self._counts):
            failed, total = self._counts[kind]
            line = json.dumps({"failed": failed, "kind": kind, "total": total,
                               "window": window}, sort_keys=True)
            self._pending.append((day, line))
        self._window, self._counts = None, {}

    def _append(self, now: dt.datetime) -> None:
        """Write the pending lines, then expire old day files (lock held). Never raises."""
        try:
            descriptor = _open_folder(self.folder, create=True)
        except Exception as error:  # noqa: BLE001 - a count never fails a run
            _log(self.process, "counts.unwritten", errorType=type(error).__name__)
            return
        try:
            while self._pending:
                day = self._pending[0][0]
                lines = [line for line_day, line in self._pending if line_day == day]
                try:
                    self._write(descriptor, day, lines)
                except _PartlyWritten as partly:
                    # The lines whose bytes all reached the file are written; the rest
                    # are kept for the next append.
                    cause = partly.__cause__ if partly.__cause__ is not None else partly
                    _log(self.process, "counts.unwritten", errorType=type(cause).__name__)
                    self._drop_written(day, partly.lines)
                    return
                except Exception as error:  # noqa: BLE001 - kept for the next append
                    _log(self.process, "counts.unwritten", errorType=type(error).__name__)
                    return
                self._pending = [item for item in self._pending if item[0] != day]
            try:
                self._expire(descriptor, now)
            except Exception as error:  # noqa: BLE001 - a removal never fails a run
                _log(self.process, "counts.unwritten", errorType=type(error).__name__)
        finally:
            os.close(descriptor)

    def _drop_written(self, day: str, count: int) -> None:
        """Remove the first `count` pending lines of `day` (lock held)."""
        kept: list[tuple[str, str]] = []
        for item in self._pending:
            if item[0] == day and count > 0:
                count -= 1
                continue
            kept.append(item)
        self._pending = kept

    def _write(self, folder: int, day: str, lines: list[str]) -> None:
        name = f"{self.process}-counts-{day}.jsonl"
        descriptor = os.open(name, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
                             FILE_MODE, dir_fd=folder)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("a count file must be a regular file")
            encoded = [line.encode() for line in lines]
            prefix = b""
            if info.st_size and os.pread(descriptor, 1, info.st_size - 1) != b"\n":
                prefix = b"\n"  # a cut line stays on its own
            # Where each line's own bytes end (its newline excluded).
            ends, offset = [], len(prefix)
            for item in encoded:
                offset += len(item)
                ends.append(offset)
                offset += 1
            remaining = memoryview(prefix + b"\n".join(encoded) + b"\n")
            sent = 0
            try:
                while remaining:  # a short write goes on
                    written = os.write(descriptor, remaining)
                    if written <= 0:
                        raise OSError("a count file accepted no bytes")
                    sent += written
                    remaining = remaining[written:]
            except OSError as error:
                # A line whose bytes all reached the file is written, even without its
                # newline: the next append's leading newline ends it and it parses.
                raise _PartlyWritten(sum(1 for end in ends if end <= sent)) from error
            try:
                os.fsync(descriptor)
            except OSError as error:
                # Every byte was written: the lines are not queued again, which would
                # count their window twice, but the unsynced append is logged.
                _log(self.process, "counts.unwritten", errorType=type(error).__name__)
        finally:
            os.close(descriptor)

    def _expire(self, folder: int, now: dt.datetime) -> None:
        limit = now - dt.timedelta(seconds=self.policy.latency_retention_seconds)
        for name in os.listdir(folder):
            match = _DAY_FILE.fullmatch(name)
            if match is None or match.group(1) != self.process:
                continue
            day = dt.datetime.strptime(match.group(2), "%Y-%m-%d").replace(tzinfo=dt.UTC)
            if day + dt.timedelta(days=1) > limit:
                continue
            info = os.stat(name, dir_fd=folder, follow_symlinks=False)
            if stat.S_ISREG(info.st_mode):
                os.unlink(name, dir_fd=folder)


def _parsed(value) -> tuple[str, dt.datetime, int, int]:
    """A complete line's kind, window start, failed and total; `ValueError` otherwise."""
    if not isinstance(value, dict) or set(value) != _LINE_KEYS:
        raise ValueError("a count line must hold its four keys")
    kind, window = value["kind"], value["window"]
    failed, total = value["failed"], value["total"]
    if kind not in KINDS:
        raise ValueError("a count line names an unregistered kind")
    if not isinstance(window, str) or _WINDOW_FORM.fullmatch(window) is None:
        raise ValueError("a count line's window is not in its form")
    start = dt.datetime.strptime(window, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
    if not all(type(item) is int for item in (failed, total)) or not 0 <= failed <= total:
        raise ValueError("a count line's figures are not counts")
    return kind, start, failed, total


def _read_file(folder: int, name: str) -> bytes:
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=folder)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("a count file must be a regular file")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1 << 16)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(descriptor)


def counts_over(folder: Path, kinds: Iterable[str],
                now: dt.datetime) -> dict[str, tuple[int, int]]:
    """Each kind's `(failed, total)` over every process's windows that started in the 24
    hours before `now`."""
    wanted = tuple(kinds)
    if any(kind not in KINDS for kind in wanted):
        raise ValueError("unregistered counted kind")
    now = _utc(now)
    earliest = now - dt.timedelta(hours=READ_HOURS)
    sums = {kind: [0, 0] for kind in wanted}
    days = {f"{earliest:%Y-%m-%d}", f"{now:%Y-%m-%d}"}
    descriptor = _open_folder(Path(folder), create=False)
    if descriptor is None:
        return {kind: (0, 0) for kind in wanted}
    skipped = 0
    try:
        for name in sorted(os.listdir(descriptor)):
            match = _DAY_FILE.fullmatch(name)
            if match is None or match.group(2) not in days:
                continue
            for raw in _read_file(descriptor, name).splitlines():
                if not raw.strip():
                    continue
                try:
                    value = json.loads(raw)
                except ValueError:
                    skipped += 1  # a cut line
                    continue
                kind, start, failed, total = _parsed(value)
                if kind in sums and earliest < start <= now:
                    sums[kind][0] += failed
                    sums[kind][1] += total
    finally:
        os.close(descriptor)
    if skipped:
        _log("operations", "counts.line-unread")
    return {kind: (failed, total) for kind, (failed, total) in sums.items()}
