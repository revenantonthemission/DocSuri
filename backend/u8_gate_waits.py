"""The owner gates' waits and holds, for the composed realm's capacity measurement only.

U8 plan Step 114(a) (NFR design review-03's R-10, and the open-streams finding of
2026-11-14): the `capacity-burst` phase records how long each request waited at each gate
`OwnerTransactions.run` takes (`backend/transactions.py:306-322`) and how long it held it.
No pool statistic holds that wait, because the gates stand in front of the pools, so
`CompleteTransactions.observe_gates` wraps this instance's gates in `ObservedGate`, which
calls each wrapped semaphore through and replaces nothing: the same semaphore, the same
bound, the same queue and the same `Busy`.

Production never imports this module: `observe_gates` imports it inside its own body,
`require_observable` refuses any profile but the composed realm's, nothing in `backend/`
calls it, and only `scripts/serve_docsuri_u8.py --observe-gates` turns it on.
Standard library only; the record keeps counts and milliseconds, never an identifier, a
path or a text.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

GATE_WAITS_FILE = "gate-waits.json"
# Each granted take's wait is counted in the first bucket whose bound (ms) it does not
# exceed, or in `over`.
BUCKETS_MS = (1, 5, 10, 50, 100, 250, 500, 1000)
OVER = "over"
REALM = "service-operations"
DATABASE = "docsuri_u8"


def require_observable(profile) -> None:
    """Gate observation serves the composed realm only (the check `require_realm` makes
    for the served realm, `scripts/serve_docsuri_u8.py:51-54`)."""
    if getattr(profile, "is_production", False) or (
            getattr(profile, "realm", None), getattr(profile, "database_name", None)) != (
            REALM, DATABASE):
        raise ValueError("gate observation serves the composed realm only")


class ObservedGate:
    """One gate of one instance, called through: every take is timed and reported, every
    give-back reports its hold. A take and its give-back happen on one thread
    (`OwnerTransactions.run`, `backend/transactions.py:306-322`, `:367-369`), so each
    thread keeps its own stack of take moments."""

    def __init__(self, inner, gate: str, owner: str, observer: GateWaits):
        self._inner, self._gate_name, self._owner, self._observer = (
            inner, gate, owner, observer)
        self._moments = threading.local()

    def _stack(self) -> list[float]:
        stack = getattr(self._moments, "stack", None)
        if stack is None:
            stack = []
            self._moments.stack = stack
        return stack

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        begun = time.monotonic()
        # `threading.Semaphore` refuses a timeout on a non-blocking take.
        if timeout is None:
            granted = self._inner.acquire(blocking)
        else:
            granted = self._inner.acquire(blocking, timeout)
        taken = time.monotonic()
        self._observer.record(self._gate_name, self._owner, taken - begun,
                              granted=bool(granted))
        if granted:
            self._stack().append(taken)
        return granted

    def release(self, *args) -> None:
        stack = self._stack()
        if stack:
            self._observer.held(self._gate_name, self._owner, time.monotonic() - stack.pop())
        self._inner.release(*args)

    def __getattr__(self, name: str):
        # Reached only for names this class does not define: the wrapped gate's own state.
        if name == "_inner":
            raise AttributeError(name)
        return getattr(self._inner, name)


def _empty() -> dict:
    return {"granted": 0, "refused": 0, "waitMsTotal": 0.0, "waitMsMax": 0.0,
            "refusedWaitMsMax": 0.0, "holdMsTotal": 0.0, "holdMsMax": 0.0, "released": 0,
            "buckets": {**{str(bound): 0 for bound in BUCKETS_MS}, OVER: 0}}


def bucket_of(wait_ms: float) -> str:
    for bound in BUCKETS_MS:
        if wait_ms <= bound:
            return str(bound)
    return OVER


class GateWaits:
    """Every observed gate's counts under one lock, keyed `<gate>:<owner>`."""

    def __init__(self):
        self._lock = threading.Lock()
        self._gates: dict[str, dict] = {}
        self._sequence = 0

    def _entry(self, gate: str, owner: str) -> dict:
        return self._gates.setdefault(f"{gate}:{owner}", _empty())

    def record(self, gate: str, owner: str, seconds: float, *, granted: bool) -> None:
        wait_ms = max(0.0, seconds * 1000)
        with self._lock:
            entry = self._entry(gate, owner)
            if granted:
                entry["granted"] += 1
                entry["waitMsTotal"] += wait_ms
                entry["waitMsMax"] = max(entry["waitMsMax"], wait_ms)
                entry["buckets"][bucket_of(wait_ms)] += 1
            else:
                entry["refused"] += 1
                entry["refusedWaitMsMax"] = max(entry["refusedWaitMsMax"], wait_ms)

    def held(self, gate: str, owner: str, seconds: float) -> None:
        hold_ms = max(0.0, seconds * 1000)
        with self._lock:
            entry = self._entry(gate, owner)
            entry["released"] += 1
            entry["holdMsTotal"] += hold_ms
            entry["holdMsMax"] = max(entry["holdMsMax"], hold_ms)

    def snapshot(self) -> dict:
        with self._lock:
            self._sequence += 1
            gates = {key: {**value, "buckets": dict(value["buckets"])}
                     for key, value in self._gates.items()}
            return {"version": 1, "pid": os.getpid(), "sequence": self._sequence,
                    "writtenAt": time.time(), "gates": gates}


def write_snapshot(path: Path, value: dict) -> None:
    """The snapshot as private JSON, written beside `path` and moved onto it."""
    folder = path.parent
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("the gate record folder must be a real folder")
    pending = path.with_name(path.name + ".pending")
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                         0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream)
    os.replace(pending, path)


class SnapshotWriter:
    """A daemon thread writing the observer's snapshot every `every` seconds until
    `stop()`, which ends it and writes once more. A failed write is tried again at the
    next tick and never stops the host."""

    STOP_JOIN_SECONDS = 2.0

    def __init__(self, observer: GateWaits, path: Path, *, every: float = 0.5):
        self.observer, self.path, self.every = observer, Path(path), every
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._run, name="u8-gate-waits", daemon=True)
        self.failures = 0

    def start(self) -> SnapshotWriter:
        self._thread.start()
        return self

    def _write(self) -> None:
        try:
            write_snapshot(self.path, self.observer.snapshot())
        except (OSError, ValueError):
            self.failures += 1

    def _run(self) -> None:
        while not self._stopping.wait(self.every):
            self._write()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread.is_alive():
            self._thread.join(self.STOP_JOIN_SECONDS)
        self._write()
