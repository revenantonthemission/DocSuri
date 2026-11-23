"""The heartbeat lane (U8 plan Step 35; reliability-design § 2, R1, NFR7.1).

In each 5-minute slot it runs one probe pair, each within 10 seconds: the public
address's `/health/ready` (out to Cloudflare and back through the tunnel, so the whole
public path) and the local one (`127.0.0.1:18200`, the realm's 18109). The slot is up only
if both answer ready. It then appends the slot's line to the availability record, synced,
and pings the heartbeat check: `/fail` on a down slot, and the next up slot's ping clears
it. The reason is the first that applies (Step 58(e), L1-30):

1. `maintenance`: the public address answered 503 with HTML, the maintenance notice;
2. a public timeout, public unreachable, or any other public HTML answer (such as
   Cloudflare's error page): `public-timeout` (a timeout) or `public-unreachable` when
   the local probe answered ready, otherwise the local probe's own reason (rules 4-6);
3. `public-not-ready`: any other public answer than 200;
4. `local-timeout`; 5. `local-unreachable`; 6. `local-not-ready`: any other local
   answer than 200;
7. otherwise `ok`.

The heartbeat no longer writes `probe-timeout`; the record still accepts it, so earlier
lines stay valid.

Each probe's 10 seconds is a hard limit (Step 66(d)): the request runs in a daemon thread
waited for at most that long, so the sequential pair ends within 20 s, under the lane's
25 s. `StartWatch` (Step 66(e)) writes the standing job's start record (NFR8.6).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import ssl
import stat
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .availability import AvailabilityRecord
from .healthchecks import Healthchecks
from .lanes import slot_of

LIMIT_SECONDS = 10
PRODUCTION_PUBLIC = "https://docsuri.rvnnt.dev/health/ready"
PRODUCTION_LOCAL = "http://127.0.0.1:18200/health/ready"
REALM_PUBLIC = "https://127.0.0.1:18110/health/ready"
REALM_LOCAL = "http://127.0.0.1:18109/health/ready"


@dataclass(frozen=True)
class Answer:
    """What one probe saw: `timeout`, `unreachable`, or an HTTP status with whether the
    body was HTML (the maintenance notice)."""

    kind: str
    status: int | None = None
    html: bool = False


def _ask(url: str, seconds: float, context: ssl.SSLContext | None, opener) -> Answer:
    try:
        with opener(url, timeout=seconds, context=context) as answer:
            kind = answer.headers.get("Content-Type", "")
            return Answer("answered", answer.status, kind.startswith("text/html"))
    except urllib.error.HTTPError as error:
        kind = error.headers.get("Content-Type", "") if error.headers else ""
        return Answer("answered", error.code, kind.startswith("text/html"))
    except TimeoutError:
        return Answer("timeout")
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            return Answer("timeout")
        return Answer("unreachable")
    except OSError:
        return Answer("unreachable")


def probe(url: str, *, seconds: float = LIMIT_SECONDS,
          context: ssl.SSLContext | None = None, opener: Callable | None = None,
          clock: Callable[[], float] = time.monotonic,
          waiter: Callable[[threading.Thread, float], object] | None = None) -> Answer:
    """One probe within a hard `seconds` (R1, R4, U8 plan Step 66(d)): the request runs in
    a daemon thread and is waited for at most `seconds`, so DNS, connect, TLS and a slow
    answer all fall inside the limit. A thread still alive at the limit, or an answer that
    came after it, is `timeout`. `opener` (`urllib.request.urlopen`), `clock`
    (`time.monotonic`) and `waiter` (`Thread.join`) are injectable."""
    open_url = opener or urllib.request.urlopen
    wait = waiter or threading.Thread.join
    box: dict[str, Answer] = {}

    def attempt() -> None:
        box["answer"] = _ask(url, seconds, context, open_url)

    started = clock()
    thread = threading.Thread(target=attempt, name="standing-probe", daemon=True)
    thread.start()
    wait(thread, seconds)
    if thread.is_alive() or "answer" not in box or clock() - started > seconds:
        return Answer("timeout")
    return box["answer"]


MAINTENANCE_STATUS = 503


def _local_ready(local: Answer) -> bool:
    return local.kind == "answered" and local.status == 200


def _local_reason(local: Answer) -> str | None:
    """The local probe's own reason (rules 4 to 6), or None when it answered ready."""
    if local.kind == "timeout":
        return "local-timeout"
    if local.kind == "unreachable":
        return "local-unreachable"
    if local.status != 200:
        return "local-not-ready"
    return None


def classify(public: Answer, local: Answer) -> tuple[bool, str]:
    """The slot's (up, reason) from its two probes: the first reason that applies (U8
    plan Step 58(e), L1-30)."""
    if public.kind == "answered" and public.html and public.status == MAINTENANCE_STATUS:
        return False, "maintenance"
    if public.kind in ("timeout", "unreachable") or public.html:
        if _local_ready(local):
            return False, ("public-timeout" if public.kind == "timeout"
                           else "public-unreachable")
        return False, _local_reason(local) or "local-not-ready"
    if public.status != 200:
        return False, "public-not-ready"
    reason = _local_reason(local)
    if reason is not None:
        return False, reason
    return True, "ok"


class Heartbeat:
    def __init__(self, record: AvailabilityRecord, checks: Healthchecks, *,
                 public: Callable[[], Answer], local: Callable[[], Answer]):
        self.record, self.checks, self.public, self.local = record, checks, public, local

    def run(self, now: dt.datetime) -> str:
        """One slot: the probe pair, the record's line, then the ping."""
        up, reason = classify(self.public(), self.local())
        self.record.append(slot_of(now, self.record.slot_seconds), up, reason)
        self.checks.ping("heartbeat", ok=up)
        return reason


# --- the start record (NFR8.6, U8 plan Step 66(e)) ------------------------------------------

WATCH_EVERY_SECONDS = 5
WATCH_BOUND_SECONDS = 600
STARTS_FOLDER_MODE = 0o700
STARTS_FILE_MODE = 0o600


def _iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class StartWatch:
    """One watch per process start, in a daemon thread of its own and not a lane: every
    5 s on its clock it runs the local probe (within its own limit), until the probe
    answers ready (200) or 600 s have passed since the start, then appends one synced
    line to `<folder>/<YYYY-MM-DD>.jsonl` (the start's UTC day): `{startedAt, readyAt,
    seconds}`, or `{startedAt, readyAt: null}` when the bound passed first. It probes
    nothing after that. The folder is 0700 and the file 0600, opened with `O_APPEND |
    O_NOFOLLOW`, never through a link; it is never the 0755 availability folder."""

    folder: Path
    local: Callable[[], Answer]
    clock: Callable[[], dt.datetime]
    sleep: Callable[[float], object] = time.sleep
    every_seconds: float = WATCH_EVERY_SECONDS
    bound_seconds: float = WATCH_BOUND_SECONDS

    def watch(self) -> dict:
        """The watch itself, run to its line; the line it wrote."""
        started = self.clock()
        ready: dt.datetime | None = None
        while True:
            answer = self.local()
            now = self.clock()
            if answer.kind == "answered" and answer.status == 200:
                ready = now
                break
            if (now - started).total_seconds() >= self.bound_seconds:
                break
            self.sleep(self.every_seconds)
        line: dict = {"startedAt": _iso(started), "readyAt": None}
        if ready is not None:
            line = {"startedAt": _iso(started), "readyAt": _iso(ready),
                    "seconds": round((ready - started).total_seconds(), 3)}
        self._append(started, line)
        return line

    def _ensure_folder(self) -> None:
        for folder in (self.folder.parent, self.folder):
            if folder.is_symlink():
                raise ValueError("the starts folder cannot be reached through a link")
        self.folder.mkdir(mode=STARTS_FOLDER_MODE, parents=True, exist_ok=True)
        os.chmod(self.folder, STARTS_FOLDER_MODE, follow_symlinks=False)

    def _append(self, started: dt.datetime, line: dict) -> None:
        self._ensure_folder()
        path = self.folder / f"{started.astimezone(dt.UTC):%Y-%m-%d}.jsonl"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                             STARTS_FILE_MODE)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("a start record is a regular file")
            os.fchmod(descriptor, STARTS_FILE_MODE)
            os.write(descriptor, json.dumps(line, sort_keys=True).encode() + b"\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def start(self) -> threading.Thread:
        """The watch in a daemon thread; a watch that cannot write never stops the job."""

        def run() -> None:
            try:
                self.watch()
            except (OSError, ValueError):
                return

        thread = threading.Thread(target=run, name="standing-start-watch", daemon=True)
        thread.start()
        return thread
