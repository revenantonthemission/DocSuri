"""Registered log lines and the processes' handlers (U8 plan Step 10; D11, BR3.9, BR3.10)."""

from __future__ import annotations

import json
import logging
import os
import stat
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from backend import log_events
from backend.log_events import (
    EVENTS_LOGGER,
    EventLog,
    PrivateWatchedFileHandler,
    ThirdPartyFormatter,
)

ROOT = Path(__file__).resolve().parents[3]
# Packages that send errors or telemetry off the machine (BR3.10).
REPORTERS = (
    "sentry_sdk", "raven", "rollbar", "bugsnag", "honeybadger", "newrelic", "ddtrace",
    "opentelemetry", "elasticapm", "airbrake",
)


def test_a_registered_line_is_one_json_object_with_a_utc_millisecond_time():
    line = EventLog(strict=True).line(
        "operations", "ledger.opened", requestId=uuid4(), state="open", durationMs=12.5
    )
    assert set(line) == {"ts", "level", "component", "event", "requestId", "state", "durationMs"}
    assert line["ts"].endswith("Z") and len(line["ts"].split(".")[1]) == 4  # 3 digits + Z


def test_an_unregistered_field_raises_when_synthetic_and_is_dropped_and_counted_in_production():
    with pytest.raises(ValueError, match="unregistered"):
        EventLog(strict=True).line("operations", "probe", email="someone")
    production = EventLog(strict=False)
    line = production.line("operations", "probe", email="someone", state="open")
    assert "email" not in line and line["state"] == "open"
    assert production.refusals == 1


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("state", "free text here"),
        ("reason", "Contains Capitals"),
        ("accountId", "person@example.invalid"),
        ("objectId", "/Users/someone/secret.pdf"),
        ("durationMs", float("nan")),
        ("durationMs", True),
        ("jobId", 12),
    ],
)
def test_free_text_is_refused(name, value):
    with pytest.raises(ValueError):
        EventLog(strict=True).line("operations", "probe", **{name: value})
    production = EventLog(strict=False)
    assert name not in production.line("operations", "probe", **{name: value})
    assert production.refusals == 1


def test_the_line_identity_is_always_a_registered_key():
    for component, event in (("Operations", "probe"), ("operations", "has space")):
        with pytest.raises(ValueError):
            EventLog(strict=False).line(component, event)


def test_an_exception_is_logged_as_its_type_and_location_without_its_message(caplog):
    caplog.set_level(logging.INFO, logger=EVENTS_LOGGER)
    secret = "private input " + uuid4().hex
    try:
        raise LookupError(secret)
    except LookupError as error:
        line = EventLog(strict=True).exception("operations", "probe.failed", error)
    assert line["errorType"] == "LookupError"
    assert line["location"].startswith("test_log_events.py:")
    assert secret not in json.dumps(line)
    assert all(secret not in record.getMessage() for record in caplog.records)


def test_a_third_party_record_keeps_only_its_template():
    secret = "token-" + uuid4().hex
    try:
        raise RuntimeError(secret)
    except RuntimeError:
        record = logging.LogRecord(
            "httpx", logging.WARNING, __file__, 10, "request to %s failed", (secret,),
            sys.exc_info(),
        )
    output = ThirdPartyFormatter().format(record)
    value = json.loads(output)
    assert value["template"] == "request to %s failed" and value["logger"] == "httpx"
    assert value["errorType"] == "RuntimeError" and secret not in output


def test_configure_writes_a_private_file_per_process_and_quiets_the_rest(
    tmp_path, logging_state
):
    folder = tmp_path / "logs"
    events = log_events.configure("host", folder, production=False)
    assert events.strict and log_events.current() is events
    log_events.log_event("host", "started", state="running")
    logging.getLogger("httpx").info("dropped at info %s", "value")
    logging.getLogger("psycopg").warning("kept %s", "argument")
    for handler in (*logging.getLogger().handlers, *logging.getLogger(EVENTS_LOGGER).handlers):
        handler.flush()
    path = folder / "host.log"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert {"component": "host", "event": "started", "state": "running"}.items() <= lines[0].items()
    assert lines[1]["template"] == "kept %s" and "argument" not in path.read_text()
    assert logging.getLogger().level == logging.WARNING
    assert all(
        logging.getLogger(name).level == logging.WARNING for name in log_events.QUIET_LOGGERS
    )
    assert logging.getLogger("uvicorn.access").disabled
    # The rotation job moves the file aside; the handler reopens a new 0600 file.
    path.rename(folder / "host.log.20261022")
    log_events.log_event("host", "rotated")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert log_events.configure("host", folder, production=True).strict is False
    with pytest.raises(ValueError):
        log_events.configure("browser", folder, production=False)


def test_an_unhandled_exception_through_the_server_keeps_only_its_type_and_location(
    tmp_path, logging_state, capfd
):
    """Step 80(b): with `log_config` None (Step 79(a)), Uvicorn's unhandled-exception
    line reaches the root handler `configure` installed, which keeps only its template,
    type and location; nothing reaches standard error."""
    from backend.production_boundary import server_config

    log_events.configure("host", tmp_path / "logs", production=False)
    config = server_config(object(), 18109)
    assert config.log_config is None
    assert logging.getLogger("uvicorn").handlers == []
    assert logging.getLogger("uvicorn.error").handlers == []
    secret = "unhandled input " + uuid4().hex
    try:
        raise RuntimeError(secret)
    except RuntimeError as error:
        raised_at = error.__traceback__.tb_lineno
        # As uvicorn's HTTP protocol logs it (httptools_impl.py, h11_impl.py).
        logging.getLogger("uvicorn.error").error("Exception in ASGI application\n",
                                                 exc_info=error)
    for handler in (*logging.getLogger().handlers, *logging.getLogger(EVENTS_LOGGER).handlers):
        handler.flush()
    captured = capfd.readouterr()
    text = (tmp_path / "logs" / "host.log").read_text()
    assert secret not in captured.out and secret not in captured.err
    assert secret not in text
    lines = [json.loads(line) for line in text.splitlines()]
    assert len(lines) == 1
    assert lines[0]["logger"] == "uvicorn.error"
    assert lines[0]["template"] == "Exception in ASGI application\n"
    assert lines[0]["errorType"] == "RuntimeError"
    assert lines[0]["location"] == f"test_log_events.py:{raised_at}"


# Step 80(c): one Notion operation in a fresh interpreter set up as `u8_main` sets up a
# role. The SDK's recorded logger is checked, then sent a WARNING and an ERROR carrying
# the token; the result line names neither logger, so the parent can search every line.
NOTION_SDK_SCRIPT = """
import asyncio, importlib, json, logging, os, sys
from pathlib import Path
from uuid import uuid4
role, folder = sys.argv[1], Path(sys.argv[2])
for name in json.loads(sys.argv[3]):
    importlib.import_module(name)
from backend import log_events
log_events.configure(role, folder, production=True)
if role == 'host':
    from backend.production_boundary import server_config
    server_config(object(), 18200)
import httpx
import notion_client
from backend.modules.export.notion_session import CandidateToken, NotionSession
from backend.u6_policy import SYNTHETIC_EXPORT
token = os.environ['DOCSURI_TEST_NOTION_TOKEN']
recorded = {}
class Recording(notion_client.AsyncClient):
    def __init__(self, *args, **options):
        recorded.update(options)
        super().__init__(*args, **options)
notion_client.AsyncClient = Recording
class RaiseOnly:
    def __getattr__(self, name):
        raise AssertionError('neither the store nor the vault is read')
def answer(request):
    return httpx.Response(500, json={'object': 'error', 'status': 500,
                                     'code': 'internal_server_error', 'message': token})
session = NotionSession(store=RaiseOnly(), vault=RaiseOnly(), policy=SYNTHETIC_EXPORT,
                        transport_factory=lambda: httpx.MockTransport(answer))
async def work(sdk, context):
    return await sdk.users.me()
result = asyncio.run(session.run(CandidateToken(uuid4(), token), 30, work, prepaid_slots=1))
logger = recorded['logger']
facts = {
    'same': logger is logging.getLogger('docsuri.' + 'export.notion_sdk'),
    'handlers': [type(handler).__name__ for handler in logger.handlers],
    'propagate': logger.propagate,
    'level': logger.level,
    'sdkHandlers': len(logging.getLogger('notion' + '_client').handlers),
    'ok': result.ok,
}
logger.warning('request failed for %s', token)
logger.error('response body %s', token, exc_info=RuntimeError(token))
for handler in logging.getLogger().handlers:
    handler.flush()
print(json.dumps(facts))
"""


@pytest.mark.parametrize("role", ["workers", "host"])
def test_the_notion_sdk_keeps_u6s_null_logger_in_the_complete_assembly(tmp_path, role):
    """NFR3.9 (Step 80(c)): in the complete assembly, the Notion SDK's logger is U6's null
    logger, and nothing it is sent reaches the role's log or its standard streams."""
    modules = sorted(
        f"backend.{path.stem}"
        for path in (ROOT / "backend").glob("*.py")
        if path.stem.startswith("u8_")
        or path.stem in ("production_boundary", "request_context", "log_events")
    )
    modules += ["backend.u6_host", "backend.modules.export.notion_session"]
    token = "secret_" + uuid4().hex  # generated per run (L1-36)
    folder = tmp_path / "logs"
    result = subprocess.run(
        [sys.executable, "-c", NOTION_SDK_SCRIPT, role, str(folder), json.dumps(modules)],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT), str(ROOT / "ops/src")]),
             "DOCSURI_TEST_NOTION_TOKEN": token},
    )
    assert result.returncode == 0, result.stderr[-2000:].replace(token, "<token>")
    facts = json.loads(result.stdout.splitlines()[-1])
    assert facts["same"] is True
    assert facts["handlers"] == ["NullHandler"]
    assert facts["propagate"] is False and facts["level"] == logging.WARNING
    assert facts["sdkHandlers"] == 0
    assert facts["ok"] is False  # the 500 answer was reduced to a fixed category
    log = (folder / f"{role}.log").read_text() if (folder / f"{role}.log").exists() else ""
    for text in (log, result.stdout, result.stderr):
        assert token not in text
        assert "notion_client" not in text and "docsuri.export.notion_sdk" not in text


def test_the_private_handler_never_writes_through_a_link(tmp_path):
    target = tmp_path / "elsewhere.log"
    target.write_text("")
    (tmp_path / "host.log").symlink_to(target)
    with pytest.raises(OSError):
        PrivateWatchedFileHandler(tmp_path / "host.log")


def test_the_complete_assembly_imports_and_configures_no_external_error_reporter(tmp_path):
    """BR3.10: every U8 backend module is imported in a fresh interpreter, which then
    holds no error reporter, and `configure` installs only the private file handlers."""
    modules = sorted(
        f"backend.{path.stem}"
        for path in (ROOT / "backend").glob("*.py")
        if path.stem.startswith("u8_")
        or path.stem in ("production_boundary", "request_context", "log_events")
    )
    assert "backend.log_events" in modules
    script = (
        "import importlib, json, logging, sys\n"
        f"for name in {modules!r}: importlib.import_module(name)\n"
        "from backend import log_events\n"
        f"log_events.configure('host', __import__('pathlib').Path({str(tmp_path / 'logs')!r}),"
        " production=True)\n"
        f"found = [name for name in {REPORTERS!r} if name in sys.modules]\n"
        "handlers = [type(h).__name__ for h in logging.getLogger().handlers]\n"
        "handlers += [type(h).__name__ for h in logging.getLogger('docsuri.events').handlers]\n"
        "print(json.dumps({'reporters': found, 'handlers': handlers}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT), str(ROOT / "ops/src")])},
    )
    assert result.returncode == 0, result.stderr[-2000:]
    value = json.loads(result.stdout.splitlines()[-1])
    assert value["reporters"] == []
    assert set(value["handlers"]) == {"PrivateWatchedFileHandler"}
