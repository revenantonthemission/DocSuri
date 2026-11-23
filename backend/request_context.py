"""Request identifiers and latency summaries (D13, P10; U8 plan Step 9).

- **Identifiers.** Each request gets a fresh UUID in `local_browser.CURRENT_REQUEST_ID`,
  never one taken from a header (`X-Request-Id` is ignored). The error answer's
  `requestId`, every log line, observation and job accept read it from there.
- **Latency.** A fixed-bucket histogram is kept per route class in memory, with no
  per-request record. Every 5 minutes (`latency_window_seconds`) the host appends one
  line per class to `evidence/latency/YYYY-MM-DD.jsonl`: the window, the class, the
  count, the median, the 95th percentile, the maximum and the 5xx count. It writes no
  identifier or path, and keeps files 14 days (`latency_retention_seconds`).
- **Route classes.** `RouteClasses` gives each mounted route its class from the fixed
  list of performance-design § 10; `check` refuses an application with a route that
  has none, so a route registered without a class fails the assembly check.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import stat
import threading
import time
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from starlette.routing import compile_path

from .local_browser import CURRENT_REQUEST_ID
from .u8_policy import ROUTE_CLASSES

# Fixed bucket upper bounds in milliseconds; the last bucket is open.
BUCKETS_MS = (5, 10, 25, 50, 100, 200, 300, 500, 750, 1000, 2000, 3000, 5000, 10000, 30000)
LATENCY_FOLDER = ("evidence", "latency")
FOLDER_MODE, FILE_MODE = 0o700, 0o600


class RouteClasses:
    """The route class of each registered route template (performance-design § 10)."""

    def __init__(self):
        self._entries: list[tuple[frozenset[str], str, object, str]] = []

    def register(self, path: str, route_class: str, *, methods=("GET", "POST")) -> None:
        if route_class not in ROUTE_CLASSES:
            raise ValueError("unregistered route class")
        regex, _, _ = compile_path(path)
        self._entries.append((frozenset(methods), path, regex, route_class))

    def classify(self, method: str, path: str) -> str | None:
        for methods, _, regex, route_class in self._entries:
            if method in methods and regex.match(path):
                return route_class
        return None

    def template_class(self, method: str, template: str) -> str | None:
        for methods, path, _, route_class in self._entries:
            if method in methods and path == template:
                return route_class
        return None

    def check(self, routes) -> None:
        """Refuse an application holding a route that has no class."""
        for route in routes:
            for method in sorted(getattr(route, "methods", None) or ()):
                if method == "HEAD":
                    continue
                if self.template_class(method, route.path) is None:
                    raise ValueError(f"route without a route class: {method} {route.path}")


class _Histogram:
    __slots__ = ("buckets", "count", "maximum", "errors")

    def __init__(self):
        self.buckets = [0] * (len(BUCKETS_MS) + 1)
        self.count = 0
        self.maximum = 0.0
        self.errors = 0

    def add(self, milliseconds: float, status: int) -> None:
        index = next(
            (i for i, bound in enumerate(BUCKETS_MS) if milliseconds <= bound), len(BUCKETS_MS)
        )
        self.buckets[index] += 1
        self.count += 1
        self.maximum = max(self.maximum, milliseconds)
        if status >= 500:
            self.errors += 1

    def quantile(self, fraction: float) -> float | None:
        """The upper bound of the bucket that holds the quantile; the open bucket
        reports the window's maximum."""
        if not self.count:
            return None
        needed = fraction * self.count
        seen = 0
        for index, value in enumerate(self.buckets):
            seen += value
            if seen >= needed:
                return float(BUCKETS_MS[index]) if index < len(BUCKETS_MS) else self.maximum
        return self.maximum


class LatencyRecorder:
    """In-memory histograms per class, flushed to the evidence folder each window."""

    def __init__(self, root: Path, *, policy, clock: Callable[[], dt.datetime]):
        self.folder = root.joinpath(*LATENCY_FOLDER)
        self.policy = policy
        self.clock = clock
        self._lock = threading.Lock()
        self._histograms = {name: _Histogram() for name in ROUTE_CLASSES}
        self._window = clock()

    def observe(self, route_class: str, seconds: float, status: int) -> None:
        if route_class not in self._histograms:
            raise ValueError("unregistered route class")
        with self._lock:
            self._histograms[route_class].add(max(0.0, seconds) * 1000, status)

    def summary(self, route_class: str) -> dict:
        with self._lock:
            histogram = self._histograms[route_class]
            return self._line(route_class, histogram)

    @staticmethod
    def _line(route_class: str, histogram: _Histogram) -> dict:
        return {
            "class": route_class,
            "count": histogram.count,
            "medianMs": histogram.quantile(0.5),
            "p95Ms": histogram.quantile(0.95),
            "maxMs": histogram.maximum if histogram.count else None,
            "errors5xx": histogram.errors,
        }

    def flush(self) -> Path:
        """Append one line per class for the window that ends now, start a new window,
        and delete files older than the retention."""
        now = self.clock()
        with self._lock:
            start, self._window = self._window, now
            current, self._histograms = self._histograms, {n: _Histogram() for n in ROUTE_CLASSES}
        window = start.astimezone(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        lines = [
            json.dumps({"window": window, **self._line(name, current[name])}, sort_keys=True)
            for name in ROUTE_CLASSES
        ]
        path = self._file(start)
        descriptor = os.open(
            path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, FILE_MODE
        )
        try:
            os.write(descriptor, ("\n".join(lines) + "\n").encode())
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.expire(now)
        return path

    def _file(self, moment: dt.datetime) -> Path:
        self.folder.parent.mkdir(mode=FOLDER_MODE, exist_ok=True)
        self.folder.mkdir(mode=FOLDER_MODE, exist_ok=True)
        if self.folder.is_symlink():
            raise ValueError("the latency evidence folder must not be a link")
        return self.folder / f"{moment.astimezone(dt.UTC):%Y-%m-%d}.jsonl"

    def expire(self, now: dt.datetime) -> list[str]:
        """Delete day files whose day ended more than the retention ago."""
        removed = []
        if not self.folder.is_dir():
            return removed
        limit = now - dt.timedelta(seconds=self.policy.latency_retention_seconds)
        for path in self.folder.iterdir():
            try:
                day = dt.datetime.strptime(path.name, "%Y-%m-%d.jsonl").replace(tzinfo=dt.UTC)
            except ValueError:
                continue
            if day + dt.timedelta(days=1) <= limit and not path.is_symlink() and path.is_file():
                path.unlink()
                removed.append(path.name)
        return removed

    async def run(self, stopping: asyncio.Event) -> None:
        """Flush every window until `stopping` is set, then once more."""
        while not stopping.is_set():
            try:
                await asyncio.wait_for(stopping.wait(), self.policy.latency_window_seconds)
            except TimeoutError:
                await asyncio.to_thread(self.flush)
        await asyncio.to_thread(self.flush)


def _window_start(value) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def _read_day_file(path: Path) -> bytes:
    """One day file, opened without following a link (a linked file raises `OSError`);
    a missing file reads as empty, and anything but a regular file is refused."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return b""
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise OSError("a latency day file must be a regular file")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def window_summaries(folder: Path, *, start: dt.datetime, end: dt.datetime,
                     window_seconds: int) -> dict:
    """The latency lines `LatencyRecorder` wrote for windows that start at or after
    `start` and end, `window_seconds` later, at or before `end` (U8 plan Step 70(d),
    performance-design § 10, L1-59). The UTC day files from `start`'s day to `end`'s are
    read, each with `O_NOFOLLOW`; a missing day file reads as empty and a malformed line
    is skipped. For every route class it answers the largest window `p95Ms` (None when no
    counted window holds a request) and the sum of `count`, with the number of distinct
    windows counted: the cautious reading of windows whose samples are not kept, as the
    performance phase reads NFR8.3."""
    length = dt.timedelta(seconds=window_seconds)
    peaks: dict[str, float | None] = {name: None for name in ROUTE_CLASSES}
    requests = {name: 0 for name in ROUTE_CLASSES}
    windows: set[dt.datetime] = set()
    day = start.astimezone(dt.UTC).date()
    last = end.astimezone(dt.UTC).date()
    while day <= last:
        text = _read_day_file(folder / f"{day:%Y-%m-%d}.jsonl").decode(errors="replace")
        for line in text.splitlines():
            try:
                value = json.loads(line)
                route_class = value["class"]
                count = int(value.get("count") or 0)
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
            begun = _window_start(value.get("window"))
            if route_class not in peaks or begun is None or begun < start or (
                begun + length > end
            ):
                continue
            windows.add(begun)
            requests[route_class] += count
            p95 = value.get("p95Ms")
            if count and isinstance(p95, (int, float)):
                peaks[route_class] = max(peaks[route_class] or 0.0, float(p95))
        day += dt.timedelta(days=1)
    return {"windows": len(windows), "p95Ms": peaks, "requests": requests}


class RequestContext:
    """Just inside D7's boundary: one fresh identifier per request, and its latency."""

    def __init__(self, recorder: LatencyRecorder | None, classes: RouteClasses | None):
        self.recorder = recorder
        self.classes = classes

    def wrap(self, app):
        return _RequestContextApp(app, self)


class _RequestContextApp:
    def __init__(self, app, context: RequestContext):
        self.app = app
        self.context = context

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # Never read from the request: a caller cannot plant text in the logs this way.
        token = CURRENT_REQUEST_ID.set(str(uuid4()))
        started = time.monotonic()
        status = {"code": 500}

        async def observed(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            return await self.app(scope, receive, observed)
        finally:
            self._record(scope, time.monotonic() - started, status["code"])
            CURRENT_REQUEST_ID.reset(token)

    def _record(self, scope, seconds: float, status: int) -> None:
        context = self.context
        if context.recorder is None:
            return
        route_class = None
        if context.classes is not None:
            route_class = context.classes.classify(scope["method"], scope["path"])
        context.recorder.observe(route_class or "static", seconds, status)
