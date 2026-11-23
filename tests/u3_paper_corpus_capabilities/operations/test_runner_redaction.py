"""U3's tool writes no connection string into a phase log (U8 plan Step 44; the person's
decision of 2026-10-25, "Redact it in U3's tool").

A phase log is the child's output. pytest's long traceback prints a failed connection's
arguments: its libpq key=value string and keyword dict, each with the password. The tool
writes only the database name in their place. The failing connection here is made on
purpose, to a closed loopback port, by a pytest child the tool supervises as it supervises
a phase; the password is read from a credentials file, as the realm's tests read theirs.
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.u3_operations

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

PROBE_DATABASE = "docsuri_u3_redaction_probe"
FAILING_TEST = '''
import json
from pathlib import Path

import psycopg


def test_a_connection_that_fails(tmp_path_factory):
    credentials = json.loads((Path(__file__).parent / "credentials.json").read_text())
    psycopg.connect(host="127.0.0.1", port=credentials["port"], dbname=credentials["dbname"],
                    user="docsuri_probe", password=credentials["password"],
                    connect_timeout=2)


def test_a_uri_that_fails():
    credentials = json.loads((Path(__file__).parent / "credentials.json").read_text())
    psycopg.connect(credentials["uri"], connect_timeout=2)
'''


def closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def runner():
    from scripts import verify_docsuri_u3

    return verify_docsuri_u3


def test_a_failed_connection_leaves_no_password_or_connection_string_in_the_log(
        runner, tmp_path):
    password = "probe-" + "a1b2c3d4e5f6" * 3
    port = closed_port()
    (tmp_path / "credentials.json").write_text(json.dumps({
        "port": port, "dbname": PROBE_DATABASE, "password": password,
        "uri": f"postgresql://docsuri_probe:{password}@127.0.0.1:{port}/{PROBE_DATABASE}",
    }))
    (tmp_path / "test_failing_connection.py").write_text(FAILING_TEST)
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -ra\n")
    log = tmp_path / "u3-phase-probe.log"
    report = tmp_path / "probe.xml"
    with pytest.raises(runner.Refused):  # the child fails, as a phase with a down database
        runner.bounded_process(
            [str(runner.PYTHON), "-m", "pytest", "-c", str(tmp_path / "pytest.ini"),
             "--rootdir", str(tmp_path), "-p", "no:cacheprovider", "-q",
             f"--junitxml={report}", str(tmp_path / "test_failing_connection.py")],
            log, seconds=60)
    text = log.read_text(errors="replace")
    # The connection really failed, and pytest printed its traceback.
    assert "2 failed" in text and "OperationalError" in text
    assert_no_connection_string(text, password)
    # pytest writes the JUnit report itself; it carries the same traceback until the
    # tool redacts it, as run_phase does once the child has exited.
    raw = report.read_text(errors="replace")
    assert password in raw  # the probe really reaches the report unredacted
    assert runner.redact_report(report) == "redacted"
    redacted = report.read_text(errors="replace")
    assert_no_connection_string(redacted, password)
    # The report still parses and still counts what the phase evidence counts.
    cases = list(runner.ET.parse(report).getroot().iter("testcase"))
    assert len(cases) == 2
    assert all(case.find("failure") is not None for case in cases)
    assert oct(report.stat().st_mode & 0o777) == oct(0o600)


def assert_no_connection_string(text: str, password: str) -> None:
    assert password not in text
    for fragment in ("postgresql://", "password=" + password[:6], "host=127.0.0.1 port=",
                     "'password': '", "&apos;password&apos;", "password=&apos;"):
        assert fragment not in text, fragment
    # Only the database name stands where the connection string was.
    assert PROBE_DATABASE in text


def test_an_unreadable_report_is_removed_rather_than_kept(runner, tmp_path):
    report = tmp_path / "cut.xml"
    report.write_text("<testsuites><testsuite><testcase><failure>password=s3cret")
    assert runner.redact_report(report) == "removed"
    assert not report.exists()
    assert runner.redact_report(report) == "absent"


@pytest.mark.parametrize(("line", "expected"), [
    (b"conninfo = 'host=127.0.0.1 port=15459 dbname=docsuri_u3 user=postgres "
     b"password=s3cret connect_timeout=3'", b"conninfo = 'docsuri_u3'"),
    (b"kwargs = {'host': '127.0.0.1', 'dbname': 'docsuri_u3', 'password': 's3cret'}",
     b"kwargs = docsuri_u3"),
    (b"url = postgresql://postgres:s3cret@127.0.0.1:15459/docsuri_u3?sslmode=disable",
     b"url = docsuri_u3"),
    (b"host=127.0.0.1 user=postgres password=s3cret", b"[connection]"),
    (b"PGPASSWORD password: 's3cret'", b"PGPASSWORD password: [redacted]"),
    (b'FATAL:  password authentication failed for user "postgres"',
     b'FATAL:  password authentication failed for user "postgres"'),
    (b"12 passed in 3.01s", b"12 passed in 3.01s"),
])
def test_each_connection_string_form_keeps_only_its_database_name(runner, line, expected):
    assert runner.redact_connection_strings(line) == expected


def test_a_connection_string_split_across_reads_is_still_redacted(runner, tmp_path):
    import io

    stream = io.BytesIO()
    writer = runner.RedactingLog(stream)
    line = b"conninfo = 'host=127.0.0.1 dbname=docsuri_u3 user=postgres password=s3cret'\n"
    for start in range(0, len(line), 7):
        writer.write(line[start:start + 7])
    writer.write(b"tail without newline password=s3cret")
    writer.close()
    assert b"s3cret" not in stream.getvalue()
    assert stream.getvalue().startswith(b"conninfo = 'docsuri_u3'\n")
