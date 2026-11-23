"""The static maintenance server (U8 plan Steps 36 and 78; BR9.10, security-design § 4,
NFR5.2, NFR9.7, NFR9.8).

A real server on a loopback port of the test's own serves a fixture build of the three
script-free pages, read once at start.
"""

from __future__ import annotations

import datetime as dt
import http.client
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from backend import maintenance_server as maintenance
from backend.production_boundary import FIXED_HEADERS, HSTS

ROOT = Path(__file__).resolve().parents[3]
NOTICE = b"<!doctype html><html lang=\"ko\"><title>DocSuri</title><h1>notice</h1></html>"


@pytest.fixture
def served(tmp_path):
    build = tmp_path / "dist"
    build.mkdir()
    (build / "maintenance.html").write_bytes(NOTICE)
    (build / "privacy.html").write_bytes(b"<h1>privacy</h1>")
    (build / "terms.html").write_bytes(b"<h1>terms</h1>")
    server = maintenance.MaintenanceServer(maintenance.Pages.load(build), port=0,
                                           public_authority="127.0.0.1:18110")
    server.start()
    yield server.httpd.server_address[1], build
    server.stop()


def request(port: int, method: str, path: str, *, host: str = "127.0.0.1:18111"):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request(method, path, headers={"Host": host})
        answer = connection.getresponse()
        return answer.status, {key.lower(): value for key, value in answer.getheaders()}, (
            answer.read())
    finally:
        connection.close()


def test_the_notice_everywhere_but_the_legal_pages(served):
    port, _ = served
    for path in ("/", "/health/ready", "/api/v2/c07/list-research-jobs", "/privacy/x"):
        status, headers, body = request(port, "GET", path)
        assert (status, body) == (503, NOTICE), path
        assert headers["retry-after"] == "300"
    assert request(port, "GET", "/privacy")[2] == b"<h1>privacy</h1>"
    assert request(port, "GET", "/terms?from=footer")[0:3:2] == (200, b"<h1>terms</h1>")


def test_the_pages_linked_stylesheets_and_nothing_else_of_the_build(tmp_path):
    """The hashed stylesheets the built pages link are served as CSS; every other file of
    the build, a script included, is the notice (U8 plan Step 43, the workspace build)."""
    build = tmp_path / "dist"
    (build / "assets").mkdir(parents=True)
    link = b'<link rel="stylesheet" crossorigin href="/assets/legal-BxtcjqMv.css">'
    (build / "maintenance.html").write_bytes(b"<!doctype html><head>" + link + b"</head>")
    (build / "privacy.html").write_bytes(b"<h1>privacy</h1>")
    (build / "terms.html").write_bytes(b"<h1>terms</h1>")
    (build / "assets" / "legal-BxtcjqMv.css").write_bytes(b"main{margin:0}")
    (build / "assets" / "index-CQdUjVhN.js").write_bytes(b"console.log(1)")
    server = maintenance.MaintenanceServer(maintenance.Pages.load(build), port=0,
                                           public_authority="127.0.0.1:18110")
    server.start()
    try:
        port = server.httpd.server_address[1]
        status, headers, body = request(port, "GET", "/assets/legal-BxtcjqMv.css")
        assert (status, body) == (200, b"main{margin:0}")
        assert headers["content-type"].startswith("text/css")
        assert headers["cache-control"] == "no-store"
        status, headers, _ = request(port, "GET", "/assets/index-CQdUjVhN.js")
        assert status == 503 and headers["content-type"].startswith("text/html")
    finally:
        server.stop()
    (build / "assets" / "legal-BxtcjqMv.css").unlink()
    with pytest.raises(FileNotFoundError):
        maintenance.Pages.load(build)  # a linked stylesheet the build lacks refuses the start


def test_get_and_head_only(served):
    port, _ = served
    status, headers, body = request(port, "HEAD", "/terms")
    assert status == 200 and body == b"" and headers["content-length"] == "14"
    for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
        status, headers, _ = request(port, method, "/")
        assert status == 405 and headers["allow"] == "GET, HEAD", method


def test_no_cookie_no_store_and_the_boundarys_headers(served):
    port, _ = served
    status, headers, _ = request(port, "GET", "/")
    assert "set-cookie" not in headers
    assert headers["cache-control"] == "no-store"
    for name, value in FIXED_HEADERS:
        assert headers[name.decode()] == value.decode()
    assert "strict-transport-security" not in headers  # not the public host
    assert request(port, "GET", "/privacy", host="127.0.0.1:18110")[1][
        "strict-transport-security"] == HSTS


def test_the_pages_come_only_from_regular_files_of_the_build(tmp_path, served):
    _, build = served
    with pytest.raises(FileNotFoundError):
        maintenance.Pages.load(tmp_path)  # no maintenance.html
    linked = tmp_path / "linked"
    linked.symlink_to(build)
    with pytest.raises(ValueError):
        maintenance.Pages.load(linked)
    (build / "terms.html").unlink()
    (build / "terms.html").symlink_to(build / "privacy.html")
    with pytest.raises(OSError):
        maintenance.Pages.load(build)
    with pytest.raises(SystemExit):
        maintenance.main(["--build", str(build), "--port", "3000"])  # not one of its ports


# --- U8 plan Step 78: its two ports, its headers, its counted log and the heartbeat's reading


def stylesheet_build(folder: Path) -> Path:
    """A build whose notice links `/assets/legal-BxtcjqMv.css`, as
    `test_the_pages_linked_stylesheets_and_nothing_else_of_the_build` builds it."""
    build = folder / "dist"
    (build / "assets").mkdir(parents=True)
    link = b'<link rel="stylesheet" crossorigin href="/assets/legal-BxtcjqMv.css">'
    (build / "maintenance.html").write_bytes(b"<!doctype html><head>" + link + b"</head>")
    (build / "privacy.html").write_bytes(b"<h1>privacy</h1>")
    (build / "terms.html").write_bytes(b"<h1>terms</h1>")
    (build / "assets" / "legal-BxtcjqMv.css").write_bytes(b"main{margin:0}")
    return build


def line_count(path: Path) -> int:
    return len(path.read_text().splitlines()) if path.exists() else 0


def test_it_listens_on_loopback_only_at_its_two_ports(tmp_path, monkeypatch):
    import signal

    build = stylesheet_build(tmp_path)
    real = maintenance.MaintenanceServer(maintenance.Pages.load(build), port=0,
                                         public_authority="127.0.0.1:18110")
    try:
        assert real.httpd.server_address[0] == "127.0.0.1"
    finally:
        real.httpd.server_close()
    logs = tmp_path / "logs"
    log_file = logs / "maintenance.log"
    made = []

    class Recorder:
        """Stands in for `ThreadingHTTPServer`, so nothing binds 18201 or 18111."""

        interrupt = False

        def __init__(self, address, handler):
            self.server_address = address
            self.daemon_threads = False
            self.handle_error = None
            self.serving = None
            self.closed: list[int] = []
            made.append(self)

        def serve_forever(self):
            self.serving = (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP))
            if Recorder.interrupt:
                signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

        def server_close(self):
            self.closed.append(line_count(log_file))

    monkeypatch.setattr(maintenance, "ThreadingHTTPServer", Recorder)
    before = (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP))
    assert maintenance.main(["--build", str(build), "--log-folder", str(logs)]) == 0
    Recorder.interrupt = True
    assert maintenance.main(["--build", str(build), "--log-folder", str(logs),
                             "--port", "18111"]) == 0
    assert [server.server_address for server in made] == [("127.0.0.1", 18201),
                                                           ("127.0.0.1", 18111)]
    for server in made:
        assert server.daemon_threads is True and callable(server.handle_error)
        assert server.serving[0] != before[0] and server.serving[1] != before[1]
    assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP)) == before
    for refused in (["--port", "18200"], ["--port", "0"], ["--port", "3000"],
                    ["--host", "0.0.0.0"]):
        with pytest.raises(SystemExit):
            maintenance.main(["--build", str(build), "--log-folder", str(logs), *refused])
    with pytest.raises(SystemExit):
        maintenance.main(["--build", str(build)])  # no --log-folder
    assert len(made) == 2  # none of the refused runs built a server
    assert os.stat(log_file).st_mode & 0o777 == 0o600
    for line in log_file.read_text().splitlines():
        value = json.loads(line)
        assert (value["answered"], value["refused"], value["failed"]) == (0, 0, 0)
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value["window"])
    # Each accepted run closed its server once, after its exit flush.
    first, second = (server.closed for server in made)
    assert len(first) == len(second) == 1
    assert first[0] >= 1 and second[0] > first[0]


def header_lines(raw: bytes) -> tuple[int, list[tuple[str, str]]]:
    head = raw.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1").split("\r\n")
    status = int(head[0].split(" ", 2)[1])
    return status, [(name, value.strip()) for name, _, value in
                    (line.partition(":") for line in head[1:])]


def raw_answer(port: int, data: bytes) -> bytes:
    import socket

    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        connection.sendall(data)
        received = b""
        while chunk := connection.recv(65536):
            received += chunk
    return received


def test_its_headers_are_the_literal_boundary_set_with_no_store(tmp_path):
    build = stylesheet_build(tmp_path)
    public = "127.0.0.1:18110"
    server = maintenance.MaintenanceServer(maintenance.Pages.load(build), port=0,
                                           public_authority=public)
    server.start()
    expected = {
        "Content-Security-Policy": (
            "default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self' https://accounts.google.com "
            "https://orcid.org"),
        "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin", "Cache-Control": "no-store"}
    # The boundary keeps ASGI's lower-case names; header names compare without case.
    assert {(name.decode().lower(), value.decode()) for name, value in FIXED_HEADERS} == {
        (name.lower(), value) for name, value in expected.items() if name != "Cache-Control"}
    try:
        port = server.httpd.server_address[1]
        for host in (public, "127.0.0.1:18111"):
            answers = []
            for method, path, status in (("GET", "/", 503), ("GET", "/privacy", 200),
                                         ("GET", "/assets/legal-BxtcjqMv.css", 200),
                                         ("HEAD", "/terms", 200), ("POST", "/", 405)):
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                try:
                    connection.request(method, path, headers={"Host": host})
                    answer = connection.getresponse()
                    answer.read()
                    answers.append((answer.status, status, answer.getheaders()))
                finally:
                    connection.close()
            got, headers = header_lines(raw_answer(
                port, f"BREW / HTTP/1.1\r\nHost: {host}\r\n\r\n".encode()))
            answers.append((got, 501, headers))
            for got, status, headers in answers:
                assert got == status
                names = [name.lower() for name, _ in headers]
                for name, value in expected.items():
                    assert names.count(name.lower()) == 1, (status, name)
                    assert dict((n.lower(), v) for n, v in headers)[name.lower()] == value
                assert "set-cookie" not in names
                hsts = [value for name, value in headers
                        if name.lower() == "strict-transport-security"]
                assert hsts == ([HSTS] if host == public else []), (status, host)
        assert HSTS == "max-age=31536000"
    finally:
        server.stop()


class Clock:
    def __init__(self, at: str):
        self.now = dt.datetime.fromisoformat(at)

    def __call__(self) -> dt.datetime:
        return self.now

    def at(self, moment: str) -> None:
        self.now = dt.datetime.fromisoformat(moment)


class Unwritable:
    """A body with a length but no buffer interface: `wfile.write` raises after the
    headers are sent."""

    def __len__(self) -> int:
        return 5


class FailingPages:
    notice = NOTICE

    def answer(self, path: str):
        if path.startswith("/raises"):
            raise RuntimeError("an injected fault before the answer")
        return 200, Unwritable()

    def content_type(self, path: str) -> str:
        return "text/html; charset=utf-8"


def test_failed_requests_are_counted_in_its_own_log(tmp_path, capfd):
    build = stylesheet_build(tmp_path)
    clock = Clock("2026-11-01T00:02:30+00:00")
    logs = tmp_path / "logs"
    log = maintenance.CountedLog(logs, clock=clock)
    assert not logs.exists()  # building it opens nothing
    server = maintenance.MaintenanceServer(maintenance.Pages.load(build), port=0,
                                           public_authority="127.0.0.1:18110", log=log)
    failing = maintenance.MaintenanceServer(FailingPages(), port=0,
                                            public_authority="127.0.0.1:18110", log=log)
    server.start()
    failing.start()
    try:
        port, other = server.httpd.server_address[1], failing.httpd.server_address[1]
        for method, path in (("GET", "/"), ("GET", "/privacy"), ("GET", "/terms?from=footer"),
                             ("HEAD", "/terms"), ("POST", "/")):
            request(port, method, path)
        assert raw_answer(port, b"GARBAGE\r\n") == b""  # read as HTTP/0.9: only the close
        connection = http.client.HTTPConnection("127.0.0.1", other, timeout=10)
        try:
            connection.request("GET", "/raises", headers={"Host": "127.0.0.1:18111"})
            with pytest.raises(http.client.RemoteDisconnected):
                connection.getresponse()
        finally:
            connection.close()
        connection = http.client.HTTPConnection("127.0.0.1", other, timeout=10)
        try:
            connection.request("GET", "/unwritable", headers={"Host": "127.0.0.1:18111"})
            answer = connection.getresponse()
            assert answer.status == 200
            with pytest.raises(http.client.IncompleteRead):
                answer.read()
        finally:
            connection.close()
    finally:
        server.stop()
        failing.stop()
    assert capfd.readouterr().err == ""  # no traceback, no client address
    log_file = logs / "maintenance.log"
    clock.at("2026-11-01T00:05:00+00:00")
    assert log.flush() is True
    lines = log_file.read_text().splitlines()
    assert [json.loads(line) for line in lines] == [
        {"window": "2026-11-01T00:00:00Z", "answered": 4, "refused": 2, "failed": 2}]
    assert os.stat(log_file).st_mode & 0o777 == 0o600
    body = log_file.read_text()
    for word in ("/privacy", "/terms", "from=footer", "/raises", "/unwritable",
                 "127.0.0.1:18111", "GET", "HEAD", "POST", "GARBAGE"):
        assert word not in body, word
    clock.at("2026-11-01T00:10:00+00:00")
    assert log.flush() is True
    assert json.loads(log_file.read_text().splitlines()[-1]) == {
        "window": "2026-11-01T00:05:00Z", "answered": 0, "refused": 0, "failed": 0}
    moved = logs / "maintenance.log.20261101"
    first_inode = os.stat(log_file).st_ino
    log_file.rename(moved)
    clock.at("2026-11-01T00:15:00+00:00")
    assert log.flush() is True
    assert os.stat(log_file).st_ino != first_inode
    assert os.stat(log_file).st_mode & 0o777 == 0o600
    assert [json.loads(line)["window"] for line in log_file.read_text().splitlines()] == [
        "2026-11-01T00:10:00Z"]
    assert len(moved.read_text().splitlines()) == 2
    log.close()
    assert capfd.readouterr().err == ""
    link_cases(tmp_path, capfd)


def link_cases(tmp_path: Path, capfd) -> None:
    """Step 78(c)'s link cases, each with its own `CountedLog` over its own folder."""
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"not the maintenance log\n")
    folder = tmp_path / "linked-name"
    folder.mkdir()
    (folder / "maintenance.log").symlink_to(outside)
    clock = Clock("2026-11-01T00:02:30+00:00")
    log = maintenance.CountedLog(folder, clock=clock)
    assert outside.read_bytes() == b"not the maintenance log\n"  # building opens nothing
    clock.at("2026-11-01T00:05:00+00:00")
    assert log.flush() is False
    assert outside.read_bytes() == b"not the maintenance log\n"
    assert capfd.readouterr().err == "maintenance-log-unwritable\n"
    (folder / "maintenance.log").unlink()
    clock.at("2026-11-01T00:10:00+00:00")
    assert log.flush() is True
    written = folder / "maintenance.log"
    assert not written.is_symlink() and os.stat(written).st_mode & 0o777 == 0o600
    assert [json.loads(line)["window"] for line in written.read_text().splitlines()] == [
        "2026-11-01T00:00:00Z", "2026-11-01T00:05:00Z"]
    log.close()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    linked = tmp_path / "linked-folder"
    linked.symlink_to(elsewhere, target_is_directory=True)
    clock = Clock("2026-11-01T00:02:30+00:00")
    log = maintenance.CountedLog(linked, clock=clock)
    clock.at("2026-11-01T00:05:00+00:00")
    assert log.flush() is False
    assert list(elsewhere.iterdir()) == []
    assert capfd.readouterr().err == "maintenance-log-unwritable\n"
    log.close()


def test_a_failure_after_its_window_closed_is_counted_in_that_window_until_it_is_written(
        tmp_path, capfd):
    """Your answer of 2026-11-10 ("Count it in the open window"): a failed write whose
    window has closed but is not yet written moves inside that window (its class minus
    one, `failed` plus one) and adds nothing to the open window; once that window's line
    is written, a later failure of one of its answers is counted `failed` in the open
    window."""
    logs = tmp_path / "logs"
    clock = Clock("2026-11-01T00:02:30+00:00")
    log = maintenance.CountedLog(logs, clock=clock)
    first = log.count("answered")
    log.count("answered")
    refused = log.count("refused")
    assert first == refused == dt.datetime.fromisoformat("2026-11-01T00:00:00+00:00")
    clock.at("2026-11-01T00:06:00+00:00")  # the first window closes, unwritten
    open_window = log.count("answered")
    log.move("answered", first)
    log.move("refused", refused)
    clock.at("2026-11-01T00:10:00+00:00")
    assert log.flush() is True
    log_file = logs / "maintenance.log"
    lines = log_file.read_text().splitlines()
    assert lines == [
        '{"answered": 1, "failed": 2, "refused": 0, "window": "2026-11-01T00:00:00Z"}',
        '{"answered": 1, "failed": 0, "refused": 0, "window": "2026-11-01T00:05:00Z"}']
    assert open_window == dt.datetime.fromisoformat("2026-11-01T00:05:00+00:00")
    # Both windows are written: a failure of the answer counted at 00:06 now counts in
    # the open window (00:10), which alone changes; no window is written twice.
    log.move("answered", open_window)
    clock.at("2026-11-01T00:15:00+00:00")
    assert log.flush() is True
    lines = log_file.read_text().splitlines()
    assert [json.loads(line) for line in lines] == [
        {"window": "2026-11-01T00:00:00Z", "answered": 1, "refused": 0, "failed": 2},
        {"window": "2026-11-01T00:05:00Z", "answered": 1, "refused": 0, "failed": 0},
        {"window": "2026-11-01T00:10:00Z", "answered": 0, "refused": 0, "failed": 1}]
    log.close()
    assert capfd.readouterr().err == ""


def test_a_failure_in_a_window_whose_write_failed_still_lands_inside_that_window(
        tmp_path, capfd):
    """A flush that cannot write leaves every waiting window as counts: a later failure
    of one of its answers moves inside it, and the retry writes the moved counts; the
    open window does not change."""
    logs = tmp_path / "logs"
    logs.mkdir(mode=0o700)
    clock = Clock("2026-11-01T00:02:30+00:00")
    log = maintenance.CountedLog(logs, clock=clock)
    first = log.count("answered")
    log.count("answered")
    log.count("refused")
    clock.at("2026-11-01T00:06:00+00:00")
    log.count("refused")  # the open window (00:05): one refused
    os.chmod(logs, 0o500)  # the log cannot be created
    try:
        assert log.flush() is False
        assert capfd.readouterr().err == "maintenance-log-unwritable\n"
        log.move("answered", first)
    finally:
        os.chmod(logs, 0o700)
    assert log.flush() is True
    log_file = logs / "maintenance.log"
    assert [json.loads(line) for line in log_file.read_text().splitlines()] == [
        {"window": "2026-11-01T00:00:00Z", "answered": 1, "refused": 1, "failed": 1}]
    clock.at("2026-11-01T00:10:00+00:00")
    assert log.flush() is True
    assert json.loads(log_file.read_text().splitlines()[-1]) == {
        "window": "2026-11-01T00:05:00Z", "answered": 0, "refused": 1, "failed": 0}
    log.close()
    assert capfd.readouterr().err == ""


def test_the_heartbeats_probe_reads_its_notice_as_maintenance(served):
    from docsuri_ops.standing.heartbeat import Answer, classify, probe

    port, _ = served
    public = probe(f"http://127.0.0.1:{port}/health/ready")
    assert public == Answer("answered", 503, True)
    assert classify(public, Answer("answered", 200, False)) == (False, "maintenance")


def test_it_imports_no_owner_module_and_no_database_driver():
    script = ("import json, sys; import backend.maintenance_server; print(json.dumps("
              "sorted(m for m in sys.modules if m.startswith(('backend.', 'psycopg', "
              "'sqlalchemy', 'fastapi', 'starlette', 'docsuri_')))))")
    completed = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True,
                               timeout=60, check=True,
                               env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                                    "PYTHONPATH": str(ROOT)})
    assert json.loads(completed.stdout) == ["backend.maintenance_server"]
