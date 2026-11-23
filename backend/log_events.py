"""Registered JSON log lines and the log handlers of v2's own processes (D11, BR3.9).

`log_event(component, event, **fields)` accepts only the registered field names, each
with a typed value (an identifier, a registered key or a number), and writes one JSON
object with a UTC `ts` in milliseconds. An unregistered field or free text raises
`ValueError` in every synthetic profile; in production the line is written without
it and `EventLog.refusals` counts it, so logging never fails a request.

- Exceptions are logged as their type and code location only (`log_exception`), never
  with their message or local values, because a message can quote input.
- Third-party records keep only the logger's name, the level and the message
  template, never its arguments. The root logger stays at WARNING, and `httpx`,
  `httpcore`, `urllib3` and `psycopg` at WARNING. Uvicorn's access log is off.
- v2's own processes write `profile/logs/<process>.log` through `WatchedFileHandler`,
  which reopens the file after the rotation job moves it aside; every file it creates
  is 0600 (security-design § 7.3).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import logging.handlers
import math
import os
import re
import threading
import traceback
from pathlib import Path
from uuid import UUID

from .local_browser import CURRENT_REQUEST_ID

EVENTS_LOGGER = "docsuri.events"
QUIET_LOGGERS = ("httpx", "httpcore", "urllib3", "psycopg")
PROCESSES = ("host", "workers", "scheduler", "maintenance", "standing")
LEVELS = ("debug", "info", "warning", "error")

_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._:-]{0,127}")
_KEY = re.compile(r"[a-z][a-z0-9._-]{0,63}")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
_LOCATION = re.compile(r"[A-Za-z0-9_.-]{1,128}:[0-9]{1,6}")

# security-design § 7.1: identifiers, states, fixed reasons and durations only.
IDENTIFIER_FIELDS = frozenset(
    {"requestId", "jobId", "operationId", "accountId", "ownerId", "objectId"}
)
KEY_FIELDS = frozenset({"state", "reason"})
NUMBER_FIELDS = frozenset({"durationMs"})
# The exception's type and code location (`log_exception`).
EXCEPTION_FIELDS = frozenset({"errorType", "location"})
REGISTERED = IDENTIFIER_FIELDS | KEY_FIELDS | NUMBER_FIELDS | EXCEPTION_FIELDS


def _valid(name: str, value) -> bool:
    if name in IDENTIFIER_FIELDS:
        if isinstance(value, UUID):
            return True
        return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None
    if name in KEY_FIELDS:
        return isinstance(value, str) and _KEY.fullmatch(value) is not None
    if name in NUMBER_FIELDS:
        return type(value) in (int, float) and math.isfinite(value)
    if name == "errorType":
        return isinstance(value, str) and _NAME.fullmatch(value) is not None
    if name == "location":
        return isinstance(value, str) and _LOCATION.fullmatch(value) is not None
    return False


def utc_milliseconds(moment: dt.datetime | None = None) -> str:
    moment = moment or dt.datetime.now(dt.UTC)
    return moment.astimezone(dt.UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventLog:
    """One process's registered log. `strict` (every synthetic profile) raises on a
    refused field; production drops it and counts the refusal."""

    def __init__(self, *, strict: bool = True):
        self.strict = strict
        self.refusals = 0
        self._lock = threading.Lock()
        self.logger = logging.getLogger(EVENTS_LOGGER)

    def _refuse(self, message: str) -> None:
        if self.strict:
            raise ValueError(message)
        with self._lock:
            self.refusals += 1

    def line(self, component: str, event: str, level: str = "info", **fields) -> dict:
        """The JSON object `event` writes, after every refusal it causes."""
        if level not in LEVELS:
            raise ValueError("unregistered log level")
        for name, value in (("component", component), ("event", event)):
            if not isinstance(value, str) or _KEY.fullmatch(value) is None:
                # The line's own identity is never dropped: it is always refused.
                raise ValueError(f"{name} must be a registered key")
        value = {"ts": utc_milliseconds(), "level": level, "component": component, "event": event}
        request = CURRENT_REQUEST_ID.get()
        if request is not None and "requestId" not in fields:
            # D13: every line written while a request runs carries its identifier.
            fields = {"requestId": request, **fields}
        for name, item in fields.items():
            if name not in REGISTERED:
                self._refuse("unregistered log field")
                continue
            if not _valid(name, item):
                self._refuse("log field value is not a registered form")
                continue
            value[name] = str(item) if isinstance(item, UUID) else item
        return value

    def event(self, component: str, event: str, level: str = "info", **fields) -> dict:
        value = self.line(component, event, level, **fields)
        self.logger.log(getattr(logging, level.upper()), json.dumps(value, sort_keys=True))
        return value

    def exception(self, component: str, event: str, error: BaseException, **fields) -> dict:
        frames = traceback.extract_tb(error.__traceback__)
        location = (
            f"{Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else "unknown:0"
        )
        return self.event(
            component, event, "error",
            errorType=type(error).__name__, location=location, **fields,
        )


_CURRENT = EventLog(strict=True)


def current() -> EventLog:
    return _CURRENT


def log_event(component: str, event: str, level: str = "info", **fields) -> dict:
    return _CURRENT.event(component, event, level, **fields)


def log_exception(component: str, event: str, error: BaseException, **fields) -> dict:
    return _CURRENT.exception(component, event, error, **fields)


class EventFormatter(logging.Formatter):
    """DocSuri's own lines are already one JSON object; they pass unchanged."""

    def format(self, record: logging.LogRecord) -> str:
        return str(record.msg)


class ThirdPartyFormatter(logging.Formatter):
    """Only the logger's name, the level and the message template: never its arguments,
    an exception's message or its local values."""

    def format(self, record: logging.LogRecord) -> str:
        value = {
            "ts": utc_milliseconds(dt.datetime.fromtimestamp(record.created, dt.UTC)),
            "level": record.levelname.lower(),
            "logger": record.name,
            "template": str(record.msg),
        }
        if record.exc_info and record.exc_info[0] is not None:
            frames = traceback.extract_tb(record.exc_info[2])
            value["errorType"] = record.exc_info[0].__name__
            if frames:
                value["location"] = f"{Path(frames[-1].filename).name}:{frames[-1].lineno}"
        return json.dumps(value, sort_keys=True)


class PrivateWatchedFileHandler(logging.handlers.WatchedFileHandler):
    """`WatchedFileHandler` whose every (re)opened file is created 0600, never through a
    link (security-design § 7.3)."""

    def _open(self):
        descriptor = os.open(
            self.baseFilename, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600
        )
        return os.fdopen(descriptor, "a", encoding=self.encoding or "utf-8")


def configure(process: str, folder: Path, *, production: bool) -> EventLog:
    """Install the process's handlers: one 0600 file, `<folder>/<process>.log`."""
    global _CURRENT
    if process not in PROCESSES:
        raise ValueError("unknown v2 process")
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.is_symlink():
        raise ValueError("the log folder must not be a link")
    path = folder / f"{process}.log"
    events = PrivateWatchedFileHandler(path)
    events.setFormatter(EventFormatter())
    others = PrivateWatchedFileHandler(path)
    others.setFormatter(ThirdPartyFormatter())
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(others)
    root.setLevel(logging.WARNING)
    logger = logging.getLogger(EVENTS_LOGGER)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.addHandler(events)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    access = logging.getLogger("uvicorn.access")
    access.disabled = True
    access.propagate = False
    _CURRENT = EventLog(strict=not production)
    return _CURRENT
