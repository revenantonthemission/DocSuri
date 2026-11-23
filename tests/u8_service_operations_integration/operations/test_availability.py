"""The availability record and the heartbeat lane (U8 plan Step 36; observability-design §
12, reliability-design § 2, NFR7.1, NFR9.13).

The record is a real folder under the test's own temporary folder; the heartbeat's two
probes and the checks' transport are stand-ins that answer as a ready host, a host that
is not ready, the maintenance notice or nothing.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import stat
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from docsuri_ops.standing.availability import AvailabilityRecord, month_bounds
from docsuri_ops.standing.healthchecks import Healthchecks, load_addresses
from docsuri_ops.standing.heartbeat import Answer, Heartbeat, classify, probe

MONTH = "2026-11"
START, END = month_bounds(MONTH)
ADDRESSES = {name: f"http://127.0.0.1:18115/{name}" for name in ("heartbeat", "backup",
                                                                   "verification")}
READY, DOWN = Answer("answered", 200), Answer("answered", 503)


class Sent:
    def __init__(self, status: int = 200):
        self.urls, self.status = [], status

    def __call__(self, url: str, seconds: float) -> int:
        assert seconds == 10
        self.urls.append(url)
        if self.status is None:
            raise OSError("no route")
        return self.status


def slot(index: int) -> dt.datetime:
    return START + dt.timedelta(minutes=5 * index)


def test_a_missing_slot_counts_as_down(tmp_path):
    record = AvailabilityRecord(tmp_path / "availability")
    for index in (0, 1, 3):  # slot 2 has no line at all
        record.append(slot(index), True, "ok")
    figure = record.figure(MONTH, slot(4))
    assert (figure.scheduled, figure.up, figure.down) == (4, 3, 1)
    assert figure.ratio == 0.75


def test_two_lines_in_one_slot_keep_the_first(tmp_path):
    record = AvailabilityRecord(tmp_path / "availability")
    assert record.append(slot(0) + dt.timedelta(seconds=40), False, "public-not-ready")
    assert not record.append(slot(0) + dt.timedelta(seconds=90), True, "ok")
    # A second line written by something else is still read as the first.
    with open(record.path(MONTH), "a") as stream:
        stream.write(json.dumps({"slot": "2026-10-31T15:00:00Z", "up": True,
                                 "reason": "ok"}) + "\n")
        stream.write("not json\n")
    [line] = record.lines(MONTH)
    assert line == {"slot": "2026-10-31T15:00:00Z", "up": False, "reason": "public-not-ready"}
    with pytest.raises(ValueError):
        record.append(slot(1), True, "maintenance")
    with pytest.raises(ValueError):
        record.append(slot(1), False, "elsewhere")


def test_the_months_figure_and_the_budget_left(tmp_path):
    record = AvailabilityRecord(tmp_path / "availability")
    slots = int((END - START).total_seconds()) // 300  # 8,640 in a 30-day month
    assert slots == 8640
    for index in range(10):
        record.append(slot(index), index != 3, "ok" if index != 3 else "maintenance")
    figure = record.figure(MONTH, slot(10))
    assert figure.budget_slots == 86  # 1% of the month: 7 hours 10 minutes of slots
    assert figure.down == 1 and figure.budget_left_seconds == 85 * 300
    # In its first month the figure counts from admission opening.
    opened = record.figure(MONTH, slot(10), opened_at=slot(5))
    assert opened.scheduled == 5 and opened.up == 5
    assert figure.as_dict()["availability"] == 0.9
    assert record.figure("2026-12", slot(10)).scheduled == 0  # nothing scheduled yet


def test_the_file_is_0644_in_a_0755_folder(tmp_path):
    record = AvailabilityRecord(tmp_path / "availability")
    record.append(slot(0), True, "ok")
    assert stat.S_IMODE(os.stat(record.folder).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(record.path(MONTH)).st_mode) == 0o644
    linked = tmp_path / "linked"
    linked.symlink_to(tmp_path / "availability")
    with pytest.raises(ValueError):
        AvailabilityRecord(linked).append(slot(1), True, "ok")


def test_a_down_slot_pings_fail_and_the_next_up_slot_clears_it(tmp_path):
    record = AvailabilityRecord(tmp_path / "availability")
    sent = Sent()
    answers = {"public": DOWN, "local": READY}
    heartbeat = Heartbeat(record, Healthchecks(ADDRESSES, send=sent),
                          public=lambda: answers["public"], local=lambda: answers["local"])
    assert heartbeat.run(slot(0)) == "public-not-ready"
    assert sent.urls[-1] == ADDRESSES["heartbeat"] + "/fail"
    answers["public"] = READY
    assert heartbeat.run(slot(1)) == "ok"
    assert sent.urls[-1] == ADDRESSES["heartbeat"]
    assert [line["up"] for line in record.lines(MONTH)] == [False, True]
    undelivered = Healthchecks(ADDRESSES, send=Sent(None))
    assert undelivered.ping("heartbeat", ok=True) is False
    assert undelivered.last == {"heartbeat": "undelivered"}
    with pytest.raises(ValueError):
        undelivered.ping("elsewhere", ok=True)


def test_each_reason_is_the_first_that_applies(tmp_path):
    html = Answer("answered", 503, True)
    error_page = Answer("answered", 530, True)  # Cloudflare's error page, HTML
    timeout, unreachable = Answer("timeout"), Answer("unreachable")
    cases = [
        ((timeout, READY), (False, "public-timeout")),
        ((unreachable, READY), (False, "public-unreachable")),
        ((html, READY), (False, "maintenance")),
        ((DOWN, READY), (False, "public-not-ready")),
        ((READY, unreachable), (False, "local-unreachable")),
        ((READY, DOWN), (False, "local-not-ready")),
        ((READY, READY), (True, "ok")),
        # Step 59(j) (L1-30): the tunnel's reasons only while the local probe is ready.
        ((html, unreachable), (False, "maintenance")),
        ((error_page, READY), (False, "public-unreachable")),
        ((error_page, unreachable), (False, "local-unreachable")),
        ((timeout, timeout), (False, "local-timeout")),
        ((unreachable, unreachable), (False, "local-unreachable")),
        ((READY, timeout), (False, "local-timeout")),
    ]
    for (public, local), expected in cases:
        assert classify(public, local) == expected, (public, local)
    record = AvailabilityRecord(tmp_path / "availability")
    for index, reason in enumerate(("public-timeout", "local-timeout", "probe-timeout")):
        assert record.append(slot(index), False, reason) is True
    with pytest.raises(ValueError):
        record.append(slot(3), False, "tunnel-down")
    assert [line["reason"] for line in record.lines(MONTH)] == [
        "public-timeout", "local-timeout", "probe-timeout"]


class Ready(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def do_GET(self):  # noqa: N802
        body = b"<html>notice</html>" if self.path == "/notice" else b'{"ready": true}'
        status = 503 if self.path == "/notice" else 200
        self.send_response(status)
        self.send_header("Content-Type", "text/html" if status == 503 else "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_a_probe_reads_a_real_answer_its_status_and_its_kind():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Ready)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        assert probe(f"http://127.0.0.1:{port}/health/ready") == Answer("answered", 200, False)
        assert probe(f"http://127.0.0.1:{port}/notice") == Answer("answered", 503, True)
    finally:
        server.shutdown()
        server.server_close()
    assert probe(f"http://127.0.0.1:{port}/health/ready", seconds=1).kind == "unreachable"


class Ticking:
    """An injected monotonic clock; the waiter advances it by its limit without waiting,
    and an opener can advance it by its answer's time."""

    def __init__(self):
        self.now = 0.0
        self.blocked: list[threading.Event] = []
        self.hangs = 0

    def __call__(self) -> float:
        return self.now

    def waiter(self, thread: threading.Thread, seconds: float) -> None:
        if self.hangs:
            self.hangs -= 1
            self.now += seconds  # the limit passes on the injected clock, nothing waits
            return
        thread.join(5)

    def answering(self, status: int, after: float):
        def opener(url, *, timeout, context):
            self.now += after
            return _Response(status)

        return opener

    def hanging(self):
        gate = threading.Event()
        self.blocked.append(gate)
        self.hangs += 1

        def opener(url, *, timeout, context):
            gate.wait(30)
            raise OSError("released")

        return opener

    def release(self) -> None:
        for gate in self.blocked:
            gate.set()


class _Response:
    def __init__(self, status: int):
        self.status, self.headers = status, {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def timed(clock: Ticking, opener, url: str = "http://127.0.0.1:1/health/ready") -> Answer:
    return probe(url, seconds=10, opener=opener, clock=clock, waiter=clock.waiter)


def test_each_probe_has_its_own_ten_seconds(tmp_path):
    """U8 plan Step 66(d) (R1, R4): a hard 10 s per probe, on the injected clock."""
    clock = Ticking()
    public, local = timed(clock, clock.answering(200, 9.9)), timed(clock, clock.answering(200, 9.9))
    assert classify(public, local) == (True, "ok")
    late = timed(clock, clock.answering(200, 10.1))
    assert late == Answer("timeout")
    assert classify(late, READY) == (False, "public-timeout")
    assert classify(READY, timed(clock, clock.answering(200, 10.1))) == (False, "local-timeout")
    try:
        started = clock()
        assert timed(clock, clock.hanging()) == Answer("timeout")
        assert clock() - started == 10
        record = AvailabilityRecord(tmp_path / "availability")
        sent = Sent()
        heartbeat = Heartbeat(record, Healthchecks(ADDRESSES, send=sent),
                              public=lambda: timed(clock, clock.hanging()),
                              local=lambda: READY)
        assert heartbeat.run(slot(0)) == "public-timeout"
        assert record.lines(MONTH)[0]["up"] is False
        assert sent.urls == [ADDRESSES["heartbeat"] + "/fail"]
    finally:
        clock.release()


def test_the_slot_line_is_synced_before_the_ping(tmp_path, monkeypatch):
    from docsuri_ops.standing import availability

    events: list[str] = []
    real_fsync = availability.os.fsync

    def fsync(descriptor):
        events.append("fsync")
        return real_fsync(descriptor)

    monkeypatch.setattr(availability.os, "fsync", fsync)

    def send(url: str, seconds: float) -> int:
        events.append("ping")
        return 200

    heartbeat = Heartbeat(AvailabilityRecord(tmp_path / "availability"),
                          Healthchecks(ADDRESSES, send=send),
                          public=lambda: READY, local=lambda: READY)
    heartbeat.run(slot(0))
    assert events == ["fsync", "ping"]


def test_a_hanging_probe_pair_ends_in_under_twenty_five_seconds(tmp_path):
    """Both probes hang: the pair ends after 20 s on the injected clock, under the lane's
    25 s; with neither answering, the first reason that applies is the local probe's
    own (Step 58(e)'s rule 2, L1-30)."""
    clock = Ticking()
    record, sent = AvailabilityRecord(tmp_path / "availability"), Sent()
    heartbeat = Heartbeat(record, Healthchecks(ADDRESSES, send=sent),
                          public=lambda: timed(clock, clock.hanging()),
                          local=lambda: timed(clock, clock.hanging()))
    try:
        assert heartbeat.run(slot(0)) == "local-timeout"
        assert clock() == 20 and clock() < 25
        assert record.lines(MONTH) == [{"slot": "2026-10-31T15:00:00Z", "up": False,
                                        "reason": "local-timeout"}]
        assert sent.urls == [ADDRESSES["heartbeat"] + "/fail"]
    finally:
        clock.release()


def test_each_slot_appends_one_synced_line_in_the_schedulers_record(tmp_path, monkeypatch):
    from docsuri_ops.standing import availability

    synced: list[tuple[int, int]] = []
    real_fsync = availability.os.fsync

    def fsync(descriptor):
        info = os.fstat(descriptor)
        synced.append((info.st_dev, info.st_ino))
        return real_fsync(descriptor)

    monkeypatch.setattr(availability.os, "fsync", fsync)
    record = AvailabilityRecord(tmp_path / "availability")
    heartbeat = Heartbeat(record, Healthchecks(ADDRESSES, send=Sent()),
                          public=lambda: READY, local=lambda: READY)
    heartbeat.run(slot(0))
    heartbeat.run(slot(0) + dt.timedelta(seconds=30))  # the same slot: no second line
    heartbeat.run(slot(1))
    assert record.lines(MONTH) == [
        {"slot": "2026-10-31T15:00:00Z", "up": True, "reason": "ok"},
        {"slot": "2026-10-31T15:05:00Z", "up": True, "reason": "ok"}]
    assert len(record.path(MONTH).read_text().splitlines()) == 2
    month = os.stat(record.path(MONTH))
    assert synced == [(month.st_dev, month.st_ino)] * 2
    # A ping that raises still leaves the slot recorded.
    unsent = Heartbeat(record, Healthchecks(ADDRESSES, send=Sent(None)),
                       public=lambda: READY, local=lambda: READY)
    assert unsent.run(slot(2)) == "ok"
    assert len(record.lines(MONTH)) == 3


def test_the_check_addresses_are_the_schedulers_own_and_fixed(tmp_path):
    folder = tmp_path / "scheduler"
    folder.mkdir()
    path = folder / "healthchecks.json"
    path.write_text(json.dumps(ADDRESSES))
    path.chmod(0o600)
    assert load_addresses(folder, production=False) == ADDRESSES
    with pytest.raises(ValueError):
        load_addresses(folder, production=True)  # production's go to hc-ping.com only
    path.chmod(0o644)
    with pytest.raises(ValueError):
        load_addresses(folder, production=False)
    path.chmod(0o600)
    path.write_text(json.dumps({"heartbeat": ADDRESSES["heartbeat"]}))
    with pytest.raises(ValueError):
        load_addresses(folder, production=False)


# --- Step 73(d): the operator tool's availability report (NFR9.13, L1-45) -----------------------


def opening_ledger(tmp_path, name: str, opened_at: str | None):
    """A ledger with no CutoverRecord, or one moved to `switched` with its opening."""
    from tests.u8_service_operations_integration import recovery_flows as rf

    folder = tmp_path / name
    folder.mkdir()
    ledger = rf.open_ledger(folder, lambda: slot(10))
    if opened_at is not None:
        # The schema admits only `preparing` first, then each state in its order.
        record = rf.cutover_record(ledger, "preparing")
        for state in ("rehearsing", "ready-to-switch", "switching"):
            record = rf.advance_cutover(ledger, record, state)
        rf.advance_cutover(ledger, record, "switched", admissionOpenedAt=opened_at)
    return ledger


def report(record_folder, ledger, month=None) -> tuple[int, dict]:
    import io

    from docsuri_ops.u8_platform import availability_words

    out = io.StringIO()
    code = availability_words.run(month, folder=record_folder, slot_seconds=300,
                                  ledger_reader=lambda: ledger, clock=lambda: slot(10),
                                  stdout=out)
    return code, json.loads(out.getvalue())


def test_the_operator_tool_reports_the_running_figure_and_budget_left(tmp_path, monkeypatch,
                                                                      capsys):
    import io
    import subprocess

    from docsuri_ops.production_wiring import WiringRefused
    from docsuri_ops.u8_platform import availability_words, operator_tool

    def no_process(*args, **kwargs):
        raise AssertionError("the report starts no process")

    monkeypatch.setattr(subprocess, "run", no_process)
    folder = tmp_path / "availability"
    record = AvailabilityRecord(folder)
    for index in range(10):
        record.append(slot(index), index != 3, "ok" if index != 3 else "maintenance")
    assert slot(10) == dt.datetime(2026, 10, 31, 15, 50, tzinfo=dt.UTC)
    assert report(folder, opening_ledger(tmp_path, "none", None)) == (0, {
        "month": "2026-11", "scheduledSlots": 10, "upSlots": 9, "downSlots": 1,
        "beforeOpening": True, "closed": False, "admissionOpenedAt": None})
    early = "2026-09-01T00:00:00.000Z"
    assert report(folder, opening_ledger(tmp_path, "early", early)) == (0, {
        "month": "2026-11", "scheduledSlots": 10, "upSlots": 9, "downSlots": 1,
        "availability": 0.9, "budgetSlots": 86, "budgetLeftSeconds": 25500,
        "closed": False, "admissionOpenedAt": early})
    assert report(folder, opening_ledger(tmp_path, "early-closed", early), "2026-10") == (0, {
        "month": "2026-10", "scheduledSlots": 8928, "upSlots": 0, "downSlots": 8928,
        "availability": 0.0, "budgetSlots": 89, "budgetLeftSeconds": 0, "closed": True,
        "admissionOpenedAt": early})
    late = "2026-10-31T15:25:00.000Z"  # slot 5
    assert report(folder, opening_ledger(tmp_path, "late", late)) == (0, {
        "month": "2026-11", "scheduledSlots": 5, "upSlots": 5, "downSlots": 0,
        "availability": 1.0, "budgetSlots": 86, "budgetLeftSeconds": 25800,
        "closed": False, "admissionOpenedAt": late})
    # 8,635 slots from the opening to the month's end, so a budget of 86.
    assert int((END - slot(5)).total_seconds()) // 300 == 8635
    assert report(folder, opening_ledger(tmp_path, "late-before", late), "2026-10") == (0, {
        "month": "2026-10", "scheduledSlots": 8928, "upSlots": 0, "downSlots": 8928,
        "beforeOpening": True, "closed": True, "admissionOpenedAt": late})

    def refused():
        raise WiringRefused("ledger-copy-refused")

    out = io.StringIO()
    assert availability_words.run(None, folder=folder, slot_seconds=300, ledger_reader=refused,
                                  clock=lambda: slot(10), stdout=out) == 1
    assert json.loads(out.getvalue()) == {"ok": False, "reason": "ledger-copy-refused"}
    capsys.readouterr()
    assert operator_tool.main(["availability", "other"]) == 2
    assert capsys.readouterr().err == availability_words.USAGE
    for argv in (["availability", "report"],
                 ["availability", "report", "--production", "--environment-file", "x"],
                 ["availability", "report", "--month", "2026-13", "--production"]):
        assert operator_tool.main(argv) == 2, argv
