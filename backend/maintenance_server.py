"""The static maintenance server (U8 plan Step 35; BR9.10, security-design § 4, NFR5.2).

`python -m backend.maintenance_server --build <dist> --port <port> --public-authority
<host> --log-folder <folder>` serves, on loopback only, the release's build of three
script-free pages:

- the maintenance notice (`maintenance.html`) at every address but `/privacy` and
  `/terms`, with `503 Service Unavailable`, so a health probe through the public address
  reads it as not ready (the availability record's `maintenance` slot);
- the legal pages' static copies (`privacy.html`, `terms.html`) at `/privacy` and
  `/terms`, with `200`.

It answers `GET` and `HEAD` only (anything else is `405` with `Allow: GET, HEAD`), sets no
cookie, and sends security-design § 4's headers with `Cache-Control: no-store` on every
answer, plus `Strict-Transport-Security` when the request's host is the public
authority. It has no application or database dependency: it imports no owner module and
no database driver, reads the three files once at start (each a regular file reached
without following a link), and keeps them in memory.

Its port is the production arrangement's 18201, or the composed realm's 18111 (the plan's
decision "The composed realm's addresses"); the tunnel or the realm's public stand-in
routes the public address to it.

Its own log (U8 plan Step 74(c); NFR9.7, NFR9.8, observability-design § 6 and § 7) is
`<log folder>/maintenance.log`: one JSON line per 5-minute UTC window, exactly
`{"answered": n, "failed": n, "refused": n, "window": "YYYY-MM-DDTHH:MM:SSZ"}`, and
nothing else — no path, query, host or method. `answered` is a 200 or the notice's 503 to
`GET` or `HEAD`; `refused` a 405 or any answer sent through `send_error`; `failed` an
answer that raised once counted, or a request that raised before it was counted. The
file is opened relative to the folder's descriptor, never through a link, 0600, and
reopened after the rotation moves it aside. It uses the standard library only:
`backend.log_events` would import the application (psycopg, FastAPI, AccountAccess).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import logging.handlers
import os
import re
import signal
import stat
import sys
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGES = {"/privacy": "privacy.html", "/terms": "terms.html"}
NOTICE = "maintenance.html"
MAX_PAGE = 512 * 1024
PRODUCTION_PORT = 18201
REALM_PORT = 18111
# security-design § 4's headers: the same set the production boundary sends
# (`backend.production_boundary.FIXED_HEADERS`; a test keeps the two equal), repeated here
# so the maintenance server imports nothing of the application.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self' https://accounts.google.com https://orcid.org"
)
HEADERS = (
    ("Content-Security-Policy", CONTENT_SECURITY_POLICY),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
    ("Cache-Control", "no-store"),
)
HSTS = "max-age=31536000"
LOG_NAME = "maintenance.log"
UNWRITABLE = "maintenance-log-unwritable"
WINDOW = dt.timedelta(minutes=5)
CLASSES = ("answered", "refused", "failed")


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def window_start(moment: dt.datetime) -> dt.datetime:
    """The 5-minute UTC window holding `moment`."""
    moment = moment.astimezone(dt.UTC)
    return moment.replace(minute=moment.minute - moment.minute % 5, second=0, microsecond=0)


class CountsFile(logging.handlers.WatchedFileHandler):
    """`<folder>/maintenance.log`, attached to no logger, so only `CountedLog`'s lines
    reach it. Nothing is opened until the first line (`delay=True`); each (re)open makes
    the folder at 0700 when it is missing, opens it without following a link and opens
    the file relative to it, 0600, never through a link. `WatchedFileHandler` reopens the
    file once the path's device or inode no longer match, as after the rotation."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        super().__init__(str(self.folder / LOG_NAME), encoding="utf-8", delay=True)
        self.setFormatter(logging.Formatter("%(message)s"))

    def _open(self):
        try:
            os.mkdir(self.folder, 0o700)
        except FileExistsError:
            pass
        directory = os.open(self.folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            descriptor = os.open(LOG_NAME, os.O_WRONLY | os.O_APPEND | os.O_CREAT |
                                 os.O_NOFOLLOW, 0o600, dir_fd=directory)
        finally:
            os.close(directory)
        try:
            stream = os.fdopen(descriptor, "a", encoding=self.encoding or "utf-8")
        except BaseException:
            os.close(descriptor)
            raise
        info = os.fstat(stream.fileno())
        self.dev, self.ino = info.st_dev, info.st_ino
        return stream

    def handleError(self, record):  # noqa: N802 - logging's name
        raise  # the open or write failure reaches CountedLog; no traceback is printed

    def discard(self) -> None:
        """Drop the stream after a failure, so the next line opens the file afresh."""
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


@dataclass
class ClosedWindow:
    """A closed window waiting for a flush: kept as counts, so a later failure of one of
    its answers still moves inside it, until its line is written. A flush serializes it
    (`line`) just before its own write; when that write fails, `line` is cleared again,
    so the retry writes its counts as they then stand."""

    start: dt.datetime
    counts: dict[str, int]
    line: str | None = None


def count_line(start: dt.datetime, counts: Mapping[str, int]) -> str:
    """One window's line: exactly its start and its three counts, sorted keys."""
    return json.dumps({"window": start.strftime("%Y-%m-%dT%H:%M:%SZ"), **counts},
                      sort_keys=True)


class CountedLog:
    """The maintenance server's counts per 5-minute UTC window, under a lock. Windows
    follow each other from the clock's first window, so none is written twice; a closed
    window waits in memory, as counts, until a flush writes it, in order, and a window
    with no request still gets its line."""

    def __init__(self, folder: Path, *, clock: Callable[[], dt.datetime] = _utc_now):
        self.folder = Path(folder)
        self.clock = clock
        self._lock = threading.Lock()
        self._flushing = threading.Lock()
        self._start = window_start(clock())
        self._counts = dict.fromkeys(CLASSES, 0)
        self._pending: list[ClosedWindow] = []
        self._file = CountsFile(self.folder)

    def _close_window(self) -> None:
        self._pending.append(ClosedWindow(self._start, self._counts))
        self._start += WINDOW
        self._counts = dict.fromkeys(CLASSES, 0)

    def _roll(self) -> None:
        now = self.clock()
        while self._start + WINDOW <= now:
            self._close_window()

    def count(self, kind: str) -> dt.datetime:
        """Count one answer; returns its window, for a later `move`."""
        with self._lock:
            self._roll()
            self._counts[kind] += 1
            return self._start

    def move(self, kind: str, window: dt.datetime) -> None:
        """An answer counted `kind` failed while it was written: it becomes `failed`, in
        its own window, open or closed and still waiting (your answer of 2026-11-10,
        "Count it in the open window"). Only when that window's line is already written
        (or being written) is the failure counted `failed` in the open window, so that one
        request shows in two lines."""
        with self._lock:
            self._roll()
            if window == self._start:
                self._counts[kind] -= 1
                self._counts["failed"] += 1
                return
            for closed in self._pending:
                if closed.start == window and closed.line is None:
                    closed.counts[kind] -= 1
                    closed.counts["failed"] += 1
                    return
            self._counts["failed"] += 1

    def seconds_left(self) -> float:
        """Seconds until the open window's end."""
        with self._lock:
            return max((self._start + WINDOW - self.clock()).total_seconds(), 0.0)

    def flush(self, *, final: bool = False) -> bool:
        """Close every window whose end the clock has reached (and, at exit, the open
        one), then append every line not yet written. False, with the fixed key on
        standard error, when the file cannot be written; the lines stay for the next."""
        with self._flushing:
            with self._lock:
                self._roll()
                if final:
                    self._close_window()
                waiting = len(self._pending)
            for _ in range(waiting):
                with self._lock:  # serialized only now, just before its own write
                    closed = self._pending[0]
                    closed.line = count_line(closed.start, closed.counts)
                try:
                    self._file.handle(logging.makeLogRecord({"msg": closed.line}))
                except (OSError, ValueError):
                    with self._lock:  # not written: a later move still lands inside it
                        closed.line = None
                    self._file.discard()
                    print(UNWRITABLE, file=sys.stderr, flush=True)
                    return False
                with self._lock:
                    self._pending.pop(0)
            return True

    def close(self) -> None:
        self._file.discard()


def read_page(folder: Path, name: str) -> bytes:
    """One page of the release's build: a regular file, never followed through a link,
    bounded in size."""
    descriptor = os.open(folder / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_PAGE:
            raise ValueError("a maintenance page must be a bounded regular file")
        return os.read(descriptor, MAX_PAGE + 1)
    finally:
        os.close(descriptor)


STYLESHEET = re.compile(rb'<link rel="stylesheet"[^>]* href="(/assets/[A-Za-z0-9_.-]+\.css)"')


@dataclass(frozen=True)
class Pages:
    notice: bytes
    legal: Mapping[str, bytes]
    # The content-hashed stylesheets the three pages link (`/assets/<name>-<hash>.css`,
    # scripts/u8_build_workspace.py), and nothing else of the build.
    styles: Mapping[str, bytes] = field(default_factory=dict)

    @classmethod
    def load(cls, folder: Path) -> Pages:
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("the build folder must be a real folder")
        notice = read_page(folder, NOTICE)
        legal = {path: read_page(folder, name) for path, name in PAGES.items()}
        styles = {}
        for page in (notice, *legal.values()):
            for href in STYLESHEET.findall(page):
                route = href.decode()
                styles[route] = read_page(folder, route.lstrip("/"))
        return cls(notice, legal, styles)

    def answer(self, path: str) -> tuple[int, bytes]:
        route = path.split("?", 1)[0].split("#", 1)[0]
        if route in self.legal:
            return 200, self.legal[route]
        if route in self.styles:
            return 200, self.styles[route]
        return 503, self.notice

    def content_type(self, path: str) -> str:
        route = path.split("?", 1)[0].split("#", 1)[0]
        return "text/css; charset=utf-8" if route in self.styles else "text/html; charset=utf-8"


def handler_for(pages: Pages, public_authority: str, log: CountedLog | None = None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "docsuri-maintenance"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):  # noqa: A002 - the stdlib's name
            return  # no access log: a request line can carry a private path (D11)

        def _count(self, kind: str) -> dt.datetime | None:
            return None if log is None else log.count(kind)

        def _failed(self, kind: str, window: dt.datetime | None) -> None:
            if log is not None and window is not None:
                log.move(kind, window)
            self.close_connection = True

        def _fixed_headers(self) -> None:
            for name, value in HEADERS:
                self.send_header(name, value)
            headers = getattr(self, "headers", None)
            if headers is not None and headers.get("Host") == public_authority:
                self.send_header("Strict-Transport-Security", HSTS)

        def _send(self, status: int, body: bytes, *, head: bool = False,
                  allow: bool = False) -> None:
            kind = "refused" if status == 405 else "answered"
            window = self._count(kind)  # before the answer's first byte
            try:
                self.send_response(status)
                self.send_header("Content-Type", pages.content_type(self.path))
                self.send_header("Content-Length", str(len(body)))
                self._fixed_headers()
                if status == 503:
                    self.send_header("Retry-After", "300")
                if allow:
                    self.send_header("Allow", "GET, HEAD")
                self.send_header("Connection", "close")
                self.end_headers()
                if not head:
                    self.wfile.write(body)
            except Exception:  # noqa: BLE001 - counted once as failed, never re-raised
                self._failed(kind, window)
                return
            self.close_connection = True

        def send_error(self, code, message=None, explain=None):
            """Every answer the standard library refuses with (400, 414, 431, 501, 505):
            no body, the fixed headers with `no-store`, the connection closed. A request
            line read as HTTP/0.9 gets no status line and no headers, as in the stdlib."""
            window = self._count("refused")
            try:
                self.send_response(code, message)
                self._fixed_headers()
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
            except Exception:  # noqa: BLE001 - counted once as failed, never re-raised
                self._failed("refused", window)
                return
            self.close_connection = True

        def do_GET(self):  # noqa: N802 - the stdlib's name
            status, body = pages.answer(self.path)
            self._send(status, body)

        def do_HEAD(self):  # noqa: N802 - the stdlib's name
            status, body = pages.answer(self.path)
            self._send(status, body, head=True)

        def _refuse(self):
            self._send(405, pages.notice, allow=True)

        do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = _refuse  # noqa: N815
        do_CONNECT = _refuse  # noqa: N815

    return Handler


class MaintenanceServer:
    """The server on `127.0.0.1:<port>`; `running()` serves from a background thread."""

    def __init__(self, pages: Pages, *, port: int, public_authority: str,
                 log: CountedLog | None = None):
        self.pages, self.port, self.public_authority = pages, port, public_authority
        self.log = log
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port),
                                         handler_for(pages, public_authority, log))
        self.httpd.daemon_threads = True
        self.httpd.handle_error = self.handle_error

    def handle_error(self, request, client_address) -> None:
        """A request that raised before it was counted (the handler never re-raises once
        it has counted) is counted `failed`, once. Nothing is printed: socketserver's
        default would print the traceback and the client's address (D11)."""
        if self.log is not None:
            self.log.count("failed")

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def flush_at_window_ends(log: CountedLog, stop: threading.Event) -> None:
    """Wait until the open window's end, then flush; a wait that ends early writes
    nothing, because `flush()` closes only windows whose end the clock has reached."""
    while not stop.wait(log.seconds_left() + 0.01):
        log.flush()


@contextmanager
def interrupts() -> Iterator[None]:
    """SIGTERM (launchd's stop, the realm's `stop_children`) and SIGHUP end the serving as
    Ctrl-C does, so the open window's counts are flushed at exit; the earlier handlers come
    back afterwards (as `docsuri_ops.release.interrupts()`, which this module cannot
    import)."""

    def interrupt(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    previous = {number: signal.signal(number, interrupt)
                for number in (signal.SIGHUP, signal.SIGTERM)}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, signal.SIG_DFL if handler is None else handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.maintenance_server")
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--port", type=int, choices=(PRODUCTION_PORT, REALM_PORT),
                        default=PRODUCTION_PORT)
    parser.add_argument("--public-authority", default="docsuri.rvnnt.dev")
    parser.add_argument("--log-folder", required=True, type=Path)
    args = parser.parse_args(argv)
    log = CountedLog(args.log_folder)
    server = MaintenanceServer(Pages.load(args.build), port=args.port,
                               public_authority=args.public_authority, log=log)
    stop = threading.Event()
    flusher = threading.Thread(target=flush_at_window_ends, args=(log, stop), daemon=True)
    flusher.start()
    try:
        with interrupts():
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        flusher.join(timeout=10)
        log.flush(final=True)
        log.close()
        server.httpd.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover - the launch job's entry
    raise SystemExit(main())
