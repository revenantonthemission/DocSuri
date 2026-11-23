"""SCRAM on every owner connection, and the per-process gates (U8 plan Step 10; D9).

The refusal cases use a stand-in listener on a loopback port the system assigns free
(never a realm address: 15510 is the synthetic v1's PostgreSQL, which the
integration-carrying phases run). It speaks just enough of the PostgreSQL protocol to ask for a
weaker authentication than SCRAM, which the client must refuse before sending any
password.

Step 52(a)-(d) (L1-13, L1-29): the statement and transaction bounds, the deadlock retry,
every row of performance-design § 3.1's connection table on the realm, and
`CompleteTransactions`' counts of failed connections and transactions.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import os
import random
import socket
import stat
import struct
import threading
import time

import psycopg
import pytest
from psycopg_pool import PoolTimeout

from backend import u8_counts
from backend.control_runtime import RECOVERY_REQUEST
from backend.local_profile import private_bytes
from backend.log_events import EVENTS_LOGGER
from backend.modules.accounts.entry_limits import EntryLimited
from backend.modules.operations.errors import OperationsError
from backend.transactions import (
    REQUIRE_AUTH,
    Busy,
    OwnerTransactions,
    UnknownCommit,
    complete_gates,
    complete_realm,
)
from backend.u8_counts import ProcessCounts, counts_over
from backend.u8_policy import PRODUCTION_OPERATIONS
from backend.u8_profile import ProductionProfile
from backend.u8_transactions import CompleteTransactions
from tests.u8_service_operations_integration.conftest import Clock


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


STANDIN_PORT = free_port()
SSL_REQUEST, GSS_REQUEST, PROTOCOL_3 = 80877103, 80877104, 196608


def _receive(connection: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionError("client closed")
        data += chunk
    return data


class WeakAuthStandin:
    """Answers the startup message with one authentication request."""

    def __init__(self, request: bytes):
        self.request = request
        self.listener = socket.create_server(("127.0.0.1", STANDIN_PORT))
        self.listener.settimeout(10)
        self.passwords_seen = 0
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def serve(self) -> None:
        try:
            connection, _ = self.listener.accept()
        except OSError:
            return
        with connection:
            connection.settimeout(10)
            try:
                while True:
                    length, code = struct.unpack("!II", _receive(connection, 8))
                    if code in (SSL_REQUEST, GSS_REQUEST) and length == 8:
                        connection.sendall(b"N")
                        continue
                    _receive(connection, length - 8)
                    break
                connection.sendall(self.request)
                kind = connection.recv(1)
                if kind == b"p":  # a password message would follow the request
                    self.passwords_seen += 1
            except (ConnectionError, OSError):
                return

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.listener.close()
        self.thread.join(5)


CLEARTEXT = b"R" + struct.pack("!II", 8, 3)
MD5 = b"R" + struct.pack("!II", 12, 5) + b"salt"
TRUST = b"R" + struct.pack("!II", 8, 0) + b"Z" + struct.pack("!I", 5) + b"I"


def test_every_connection_carries_scram(transactions):
    assert REQUIRE_AUTH == "scram-sha-256"
    pools = [*transactions._pools.values(), *transactions._recovery_pools.values()]
    assert pools and all(pool.kwargs["require_auth"] == "scram-sha-256" for pool in pools)
    # The realm's own login completes the exchange the client demands.
    assert transactions.run("operations", lambda conn: conn.execute("SELECT 1 AS one").fetchone())


@pytest.mark.parametrize(
    "request_bytes", [CLEARTEXT, MD5, TRUST], ids=["cleartext", "md5", "trust"]
)
def test_a_login_that_is_not_scram_is_refused_by_the_client(transactions, request_bytes):
    kwargs = dict(transactions._pools["operations"].kwargs, port=STANDIN_PORT)
    with WeakAuthStandin(request_bytes) as standin:
        with pytest.raises(psycopg.OperationalError, match="scram-sha-256"):
            psycopg.connect(**kwargs)
    assert standin.passwords_seen == 0


def test_the_complete_realms_admit_the_production_realm_on_its_databases():
    assert complete_realm("docsuri_u8", "service-operations")
    assert complete_realm("docsuri_v2", "production")
    assert complete_realm("docsuri_v2_rehearsal_" + "0a" * 6, "production")
    assert not complete_realm("docsuri_v2_scratch_" + "0a" * 6, "production")
    assert not complete_realm("docsuri_u6", "approved-export")
    assert not complete_realm("docsuri_v2", "service-operations")
    # A cutover journey's production stand-in, and the rehearsal database its dry run
    # imports into (the migration journey found the second refused); nothing else of it.
    assert complete_realm("docsuri_u8j0a1b2", "service-operations")
    assert complete_realm("docsuri_u8j0a1b2_rehearsal_" + "0a" * 6, "service-operations")
    assert not complete_realm("docsuri_u8j0a1b2_scratch_" + "0a" * 6, "service-operations")
    assert not complete_realm("docsuri_u8j0a1b2_rehearsal_" + "0a" * 6, "production")


def test_the_gates_take_their_limits_from_the_operations_policy(realm):
    assert complete_gates() == {
        "api": PRODUCTION_OPERATIONS.host_connections,
        "worker": PRODUCTION_OPERATIONS.worker_connections,
        "observation": PRODUCTION_OPERATIONS.observation_connections,
        "maintenance": PRODUCTION_OPERATIONS.maintenance_connections,
        "migration": PRODUCTION_OPERATIONS.migration_tool_connections,
    } == {"api": 12, "worker": 8, "observation": 2, "maintenance": 2, "migration": 4}
    for process, limit in complete_gates().items():
        value = OwnerTransactions(realm, process=process)
        try:
            taken = 0
            while value._gate.acquire(blocking=False):
                taken += 1
            assert taken == limit, process
            for _ in range(taken):
                value._gate.release()
        finally:
            value.close()


def test_the_gates_hold_their_limits_under_concurrency(transactions):
    active, peak, lock = [0], [0], threading.Lock()

    def slow(conn):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.2)
        with lock:
            active[0] -= 1
        return conn.execute("SELECT 1 AS one").fetchone()["one"]

    failures = []

    def call():
        try:
            transactions.run("library", slow)
        except Busy:
            failures.append("busy")

    threads = [threading.Thread(target=call) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    # One normal operation per owner login at a time, whatever the demand.
    assert peak[0] == 1
    # A caller past the one-second queue gets the busy answer; the rest complete.
    assert len(failures) < 6
    # A full process gate refuses at once with the built busy answer.
    held = 0
    while transactions._gate.acquire(blocking=False):
        held += 1
    try:
        assert held == 12
        with pytest.raises(Busy):
            transactions.run("operations", lambda conn: conn.execute("SELECT 1").fetchone())
    finally:
        for _ in range(held):
            transactions._gate.release()


def test_a_production_profile_is_admitted_with_infinite_retention(realm, tmp_path):
    """The production realm on its rehearsal database is admitted, and its owner
    credentials are checked like every realm's; its retention never expires."""
    production = ProductionProfile(
        tmp_path, "docsuri-v2-" + "0" * 16, "https://docsuri.rvnnt.dev", 15432,
        float("inf"), "docsuri_v2_rehearsal_" + "0a" * 6, "production",
    )
    with pytest.raises(FileNotFoundError):
        OwnerTransactions(production)  # no owner credentials in this root
    assert dataclasses.replace(realm).expires_at < production.expires_at


# --- Step 52(a): the connect, statement and transaction bounds -----------------------------


def write_private_json(path, value: dict) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(descriptor, json.dumps(value).encode())
    finally:
        os.close(descriptor)


def rebound_production(realm, root) -> ProductionProfile:
    """A production profile whose root holds the realm's owner credentials rebound to its
    own run ID; its pools open with `min_size` 0, so nothing connects."""
    run_id = "docsuri-v2-" + "0" * 16
    roles = json.loads(private_bytes(realm.root / "owner-credentials.json"))["roles"]
    write_private_json(root / "owner-credentials.json", {"runId": run_id, "roles": roles})
    return ProductionProfile(root, run_id, "https://docsuri.rvnnt.dev", 15432, float("inf"),
                             "docsuri_v2_rehearsal_" + "0a" * 6, "production")


class CountingConnection:
    """Passes every call through to the raw connection and counts `execute` calls."""

    def __init__(self, raw):
        self.raw, self.calls = raw, 0

    def execute(self, *args, **kwargs):
        self.calls += 1
        return self.raw.execute(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.raw, name)


def test_connect_statement_and_transaction_bounds(realm, tmp_path):
    values = [OwnerTransactions(realm), OwnerTransactions(rebound_production(realm, tmp_path))]
    try:
        for value in values:
            pools = [*value._pools.values(), *value._recovery_pools.values()]
            assert pools and value._recovery_pools
            assert all(pool.kwargs["connect_timeout"] == 3 for pool in pools)
            assert all(pool.min_size == 0 for pool in pools)
            assert (value._statement_ms, value._transaction_seconds) == (3000, 5)
        transactions = values[0]
        started = time.monotonic()
        with pytest.raises(psycopg.errors.QueryCanceled):
            transactions.run("operations", lambda conn: conn.execute("SELECT pg_sleep(3.2)"))
        assert 2.9 <= time.monotonic() - started <= 3.5

        seen = {}

        def three_sleeps(bounded):
            bounded.execute("SELECT pg_sleep(1.9)")
            bounded.execute("SELECT pg_sleep(1.9)")
            try:
                with bounded.transaction():
                    bounded.execute("SELECT pg_sleep(1.9)")
            except psycopg.errors.QueryCanceled:
                seen["cancelled"] = time.monotonic() - started
            # The statement timeout is rounded down to whole milliseconds, so the cancel
            # can come just before the deadline: wait until it has passed.
            while time.monotonic() <= bounded.deadline:
                time.sleep(0.005)
            counter = CountingConnection(bounded.connection)
            seen["counter"] = counter
            bounded.connection = counter
            bounded.execute("SELECT 1")

        started = time.monotonic()
        with pytest.raises(Busy, match="aggregate transaction deadline reached"):
            transactions.run("operations", three_sleeps)
        assert 4.8 <= seen["cancelled"] <= 5.6, seen
        assert seen["counter"].calls == 0
    finally:
        for value in values:
            value.close()


# --- Step 52(b): a deadlock is retried up to three times -----------------------------------


def test_a_deadlock_is_retried_up_to_three_times(transactions):
    keys = random.sample(range(1, 2**62), 2)
    barrier = threading.Barrier(2, timeout=10)
    attempts = {"accounts": 0, "library": 0}
    results, errors = {}, []

    def locking(owner: str, first: int, second: int):
        def action(conn):
            attempts[owner] += 1
            # The realm's lock_timeout (1000 ms) equals PostgreSQL's default
            # deadlock_timeout; the deadlock check must come first.
            conn.execute("SET LOCAL lock_timeout = '3000ms'")
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (first,))
            if attempts[owner] == 1:
                barrier.wait()
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (second,))
            return owner

        def call():
            try:
                results[owner] = transactions.run(owner, action)
            except Exception as error:  # noqa: BLE001 - asserted below
                errors.append(error)

        return threading.Thread(target=call)

    threads = [locking("accounts", keys[0], keys[1]), locking("library", keys[1], keys[0])]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert errors == []
    assert results == {"accounts": "accounts", "library": "library"}
    # One run met the deadlock and was retried once; the other committed at once.
    assert sorted(attempts.values()) == [1, 2]

    calls = [0]

    def deadlocked(conn):
        calls[0] += 1
        raise psycopg.errors.DeadlockDetected("deadlock detected")

    with pytest.raises(psycopg.errors.DeadlockDetected):
        transactions.run("operations", deadlocked)
    assert calls[0] == 3


# --- Step 52(c): every row of the connection table holds (L1-13) ---------------------------

# performance-design § 3.1's rows as Step 104 records them. Gate rows (each a process's
# gate), login rows (bounded by the login's CONNECTION LIMIT) and PlatformControl's three
# logins at 2 each. The restore login and PlatformControl's provisioner stand outside.
CONNECTION_TABLE = {
    "host": 12,
    "host observation and recovery": 2,
    "workers": 8,
    "workers observation and recovery": 2,
    "v2 scheduler process": 2,
    "production environment tool": 2,
    "migration tool": 4,
    "scheduler login": 3,
    "backup agent": 3,
    "operator tool": 2,
    "PlatformControl logins": 6,
}
MAX_CONNECTIONS, SUPERUSER_RESERVED = 50, 3
OWNER_LOGINS = ("accounts", "assistance", "corpus", "discovery", "export", "library",
                "operations", "personalization", "research", "topics", "usage")


def gate_capacity(gate) -> int:
    taken = 0
    while gate.acquire(blocking=False):
        taken += 1
    for _ in range(taken):
        gate.release()
    return taken


def held_runs(instance, owners, *, recovery: bool = False):
    """One held run per owner; each reads its backend pid, then waits for `release`."""
    release, ready = threading.Event(), threading.Semaphore(0)
    pids, errors = [], []

    def action(conn):
        pids.append(conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"])
        ready.release()
        release.wait(4)

    def call(owner):
        token = RECOVERY_REQUEST.set(recovery)
        try:
            instance.run(owner, action)
        except Exception as error:  # noqa: BLE001 - asserted by the caller
            errors.append(error)
            ready.release()
        finally:
            RECOVERY_REQUEST.reset(token)

    threads = [threading.Thread(target=call, args=(owner,)) for owner in owners]
    for thread in threads:
        thread.start()
    for _ in owners:
        assert ready.acquire(timeout=10)
    return threads, pids, release, errors


def backends(monitor, name: str, since) -> dict[int, str]:
    rows = monitor.execute(
        "SELECT pid,state FROM pg_stat_activity WHERE application_name LIKE %s "
        "AND backend_start > %s", (f"docsuri-service-operations-{name}-%", since)).fetchall()
    return {row["pid"]: row["state"] for row in rows}


def one_more(instance, owner: str, *, recovery: bool = False) -> Busy:
    token = RECOVERY_REQUEST.set(recovery)
    try:
        with pytest.raises(Busy) as raised:
            instance.run(owner, lambda conn: conn.execute("SELECT 1").fetchone())
    finally:
        RECOVERY_REQUEST.reset(token)
    return raised.value


def test_every_row_of_the_connection_table_holds(realm, connect):
    # The gates' values, as literals.
    assert complete_gates() == {"api": 12, "worker": 8, "observation": 2, "maintenance": 2,
                                "migration": 4}
    instances = {process: OwnerTransactions(realm, process=process)
                 for process in complete_gates()}
    monitor = connect("operations", autocommit=True)
    # The operations login is NOINHERIT, so its pg_monitor membership is used by setting
    # that role; without it other logins' activity shows without its details.
    monitor.execute("SET ROLE pg_monitor")
    since =monitor.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    measured = {}
    try:
        for process, value in instances.items():
            measured[process] = gate_capacity(value._gate)
            assert measured[process] == complete_gates()[process], process
            pools = [*value._pools.values(), *value._recovery_pools.values()]
            assert pools and all(pool.max_size == 2 for pool in pools), process
        recovery = instances["api"]._recovery_gate
        assert recovery is instances["worker"]._recovery_gate is instances["observation"]._gate
        measured["recovery"] = gate_capacity(recovery)
        assert measured["recovery"] == 2
        assert instances["maintenance"]._recovery_gate is None
        assert instances["migration"]._recovery_gate is None

        owners = sorted(instances["api"]._pools)
        assert owners == sorted(OWNER_LOGINS)
        cases = [("api", "api", 11, False, "owner connection allocation exhausted"),
                 ("worker", "worker", 8, False, "process connection allocation exhausted"),
                 ("maintenance", "maintenance", 2, False,
                  "process connection allocation exhausted"),
                 ("migration", "migration", 4, False,
                  "process connection allocation exhausted"),
                 ("api", "recovery", 2, True, "process connection allocation exhausted")]
        for process, name, count, under_recovery, refusal in cases:
            instance = instances[process]
            threads, pids, release, errors = held_runs(instance, owners[:count],
                                                       recovery=under_recovery)
            try:
                assert errors == [], (name, errors)
                # The twelfth api run takes one of the held owners; the others another.
                extra = owners[0] if name == "api" else owners[count]
                assert str(one_more(instance, extra, recovery=under_recovery)) == refusal
                found = backends(monitor, name, since)
                assert set(found) == set(pids) and len(pids) == count, (name, found, pids)
                assert set(found.values()) == {"idle in transaction"}, (name, found)
            finally:
                release.set()
                for thread in threads:
                    thread.join(10)
            assert errors == [], (name, errors)

        # The realm's logins: every login the realm's tool creates, with its limit.
        limits = {row["rolname"]: row["rolconnlimit"] for row in monitor.execute(
            "SELECT rolname,rolconnlimit FROM pg_roles").fetchall()}
        expected = {**{f"docsuri_{owner}": 4 for owner in OWNER_LOGINS},
                    "docsuri_scheduler": 3, "docsuri_backup_agent": 3, "docsuri_restore": 3,
                    "docsuri_operator": 2,
                    "docsuri_u8_platform_operator": 2, "docsuri_u8_platform_scheduler": 2,
                    "docsuri_u8_platform_reader": 2,
                    "platform_control_runtime": 2, "platform_control_provisioner": 2}
        assert {name: limits.get(name) for name in expected} == expected
        password = json.loads(private_bytes(realm.root / "owner-credentials.json"))[
            "roles"]["usage"]
        options = {"host": "127.0.0.1", "port": realm.database_port,
                   "dbname": realm.database_name, "user": "docsuri_usage",
                   "password": password, "connect_timeout": 3}
        opened = [psycopg.connect(**options) for _ in range(4)]
        try:
            with pytest.raises(psycopg.OperationalError, match="too many connections for role"):
                psycopg.connect(**options)
        finally:
            for conn in opened:
                conn.close()

        # The server.
        settings = {name: monitor.execute(f"SHOW {name}").fetchone()[name] for name in (
            "max_connections", "superuser_reserved_connections", "reserved_connections")}
        assert settings == {"max_connections": "50", "superuser_reserved_connections": "3",
                            "reserved_connections": "0"}

        # The recount: each row equals what was measured above.
        assert CONNECTION_TABLE["host"] == measured["api"]
        assert CONNECTION_TABLE["host observation and recovery"] == measured["recovery"]
        assert CONNECTION_TABLE["workers"] == measured["worker"]
        assert CONNECTION_TABLE["workers observation and recovery"] == measured["recovery"]
        assert CONNECTION_TABLE["v2 scheduler process"] == measured["maintenance"]
        assert CONNECTION_TABLE["production environment tool"] == measured["maintenance"]
        assert CONNECTION_TABLE["migration tool"] == measured["migration"]
        assert CONNECTION_TABLE["scheduler login"] == limits["docsuri_scheduler"]
        assert CONNECTION_TABLE["backup agent"] == limits["docsuri_backup_agent"]
        assert CONNECTION_TABLE["operator tool"] == limits["docsuri_operator"]
        assert CONNECTION_TABLE["PlatformControl logins"] == sum(limits[name] for name in (
            "docsuri_u8_platform_operator", "docsuri_u8_platform_scheduler",
            "docsuri_u8_platform_reader"))
        assert sum(CONNECTION_TABLE.values()) == 46
        assert MAX_CONNECTIONS - SUPERUSER_RESERVED - sum(CONNECTION_TABLE.values()) == 1
        assert int(settings["max_connections"]) == MAX_CONNECTIONS
        assert int(settings["superuser_reserved_connections"]) == SUPERUSER_RESERVED
    finally:
        for value in instances.values():
            value.close()


# --- Step 52(d): CompleteTransactions counts failed connections and transactions (L1-29) ---

WINDOW_START = dt.datetime(2026, 11, 1, 10, 0, tzinfo=dt.UTC)
KINDS = ("postgresql.connection", "postgresql.transaction")


def count_lines(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def event_lines(caplog, event: str) -> list[dict]:
    found = []
    for record in caplog.records:
        if record.name == EVENTS_LOGGER:
            value = json.loads(record.getMessage())
            if value["event"] == event:
                found.append(value)
    return found


def raising(error: BaseException):
    def action(*args, **kwargs):
        raise error

    return action


def test_complete_transactions_count_failed_connections_and_transactions(
        realm, tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    clock = Clock(WINDOW_START)
    folder = tmp_path / "evidence"
    value = CompleteTransactions(realm, counts=ProcessCounts(
        folder, "host", policy=PRODUCTION_OPERATIONS, clock=clock))
    success = lambda conn: conn.execute("SELECT 1 AS one").fetchone()["one"]  # noqa: E731
    try:
        # Four failed connections.
        held = 0
        while value._gate.acquire(blocking=False):
            held += 1
        try:
            with pytest.raises(Busy, match="process connection allocation exhausted"):
                value.run("operations", success)
        finally:
            for _ in range(held):
                value._gate.release()
        pool = value._pools["operations"]
        monkeypatch.setattr(pool, "connection", raising(PoolTimeout("pool timeout")))
        with pytest.raises(PoolTimeout):
            value.run("operations", success)
        monkeypatch.setattr(pool, "connection", raising(psycopg.OperationalError("refused")))
        with pytest.raises(psycopg.OperationalError):
            value.run("operations", success)
        monkeypatch.undo()
        # A fourth: a connect refused on a retried attempt (review of 2026-11-09). The
        # first attempt's action meets a serialization failure, and the retry's connect
        # is refused before its action begins.
        connection, attempts = pool.connection, []

        def refused_on_retry(*args, **kwargs):
            attempts.append(None)
            if len(attempts) == 2:
                raise psycopg.OperationalError("too many connections for role")
            return connection(*args, **kwargs)

        monkeypatch.setattr(pool, "connection", refused_on_retry)
        with pytest.raises(psycopg.OperationalError, match="too many connections"):
            value.run("operations", raising(psycopg.errors.SerializationFailure("retry")))
        monkeypatch.undo()
        assert len(attempts) == 2
        # Three failed transactions.
        with pytest.raises(psycopg.errors.SerializationFailure):
            value.run("operations", raising(psycopg.errors.SerializationFailure("retry")))
        with pytest.raises(UnknownCommit):
            value.run("operations", raising(UnknownCommit("reconcile")))

        def cancelled(bounded):
            bounded.connection.execute("SET LOCAL statement_timeout = '50ms'")
            bounded.connection.execute("SELECT pg_sleep(1)")

        with pytest.raises(psycopg.errors.QueryCanceled):
            value.run("operations", cancelled)
        # Five errors that are not counted as failed.
        for error in (ValueError("refused"), OperationsError("CONFLICT"),
                      EntryLimited("address-limit", 60), Busy("local account allocation exhausted"),
                      psycopg.errors.UniqueViolation("duplicate")):
            with pytest.raises(type(error)):
                value.run("operations", raising(error))
        # One success.
        assert value.run("operations", success) == 1
        day_file = folder / "host-counts-2026-11-01.jsonl"
        assert not day_file.exists()  # nothing is written until the window ends

        clock.now = WINDOW_START + dt.timedelta(minutes=5)
        assert value.run("operations", success) == 1
        assert count_lines(day_file) == [
            {"failed": 4, "kind": "postgresql.connection", "total": 13,
             "window": "2026-11-01T10:00:00Z"},
            {"failed": 3, "kind": "postgresql.transaction", "total": 9,
             "window": "2026-11-01T10:00:00Z"}]
        assert stat.S_IMODE(day_file.stat().st_mode) == 0o600
        assert stat.S_IMODE(folder.stat().st_mode) == 0o700
        # A window 24 h and 1 s before the read is left out.
        planted = folder / "host-counts-2026-10-31.jsonl"
        planted.write_text(json.dumps({"failed": 5, "kind": "postgresql.connection",
                                       "total": 5, "window": "2026-10-31T10:05:00Z"}) + "\n")
        assert counts_over(folder, KINDS, WINDOW_START + dt.timedelta(minutes=5, seconds=1)) == {
            "postgresql.connection": (4, 13), "postgresql.transaction": (3, 9)}

        # The folder replaced by a link: the run still returns, the append is refused.
        real = tmp_path / "evidence-real"
        folder.rename(real)
        folder.symlink_to(real)
        caplog.clear()
        clock.now = WINDOW_START + dt.timedelta(minutes=10)
        assert value.run("operations", success) == 1
        unwritten = event_lines(caplog, "counts.unwritten")
        assert len(unwritten) == 1 and unwritten[0]["errorType"] in (
            "OSError", "NotADirectoryError"), unwritten
        assert len(count_lines(real / "host-counts-2026-11-01.jsonl")) == 2

        # The folder back: the kept 10:05 window, then the 10:10 window.
        folder.unlink()
        real.rename(folder)
        clock.now = WINDOW_START + dt.timedelta(minutes=15)
        assert value.run("operations", success) == 1
        lines = count_lines(day_file)
        assert lines[2:] == [
            {"failed": 0, "kind": kind, "total": 1, "window": window}
            for window in ("2026-11-01T10:05:00Z", "2026-11-01T10:10:00Z") for kind in KINDS]
        clock.now = WINDOW_START + dt.timedelta(minutes=16)
        value.close()
        lines = count_lines(day_file)
        assert lines[6:] == [{"failed": 0, "kind": kind, "total": 1,
                              "window": "2026-11-01T10:15:00Z"} for kind in KINDS]
        with pytest.raises(ValueError, match="closed or unknown owner pool"):
            value.run("operations", success)
        assert count_lines(day_file) == lines
    finally:
        value.close()


def test_a_passed_deadline_is_counted_as_a_failed_transaction(realm, tmp_path):
    """Step 69(h), addition 1: a passed transaction deadline raises `DeadlineReached`, a
    `Busy` subclass that Step 51(b)'s exclusion never drops: the run's own action moves its
    bounded connection's deadline into the past and executes one statement, so the real
    `remaining()` raises at once, with no wait and no double."""
    from backend.transactions import DeadlineReached

    clock = Clock(WINDOW_START)
    folder = tmp_path / "evidence"
    value = CompleteTransactions(realm, counts=ProcessCounts(
        folder, "host", policy=PRODUCTION_OPERATIONS, clock=clock))
    try:
        def passed(bounded):
            bounded.deadline = time.monotonic() - 1.0
            bounded.execute("SELECT 1 AS one")

        with pytest.raises(DeadlineReached, match="aggregate transaction deadline reached"):
            value.run("operations", passed)
        clock.now = WINDOW_START + dt.timedelta(minutes=5)
        value.close()
        assert count_lines(folder / "host-counts-2026-11-01.jsonl") == [
            {"failed": 0, "kind": "postgresql.connection", "total": 1,
             "window": "2026-11-01T10:00:00Z"},
            {"failed": 1, "kind": "postgresql.transaction", "total": 1,
             "window": "2026-11-01T10:00:00Z"}]
    finally:
        value.close()


def test_the_count_files_keep_fourteen_days(tmp_path):
    folder = tmp_path / "evidence"
    folder.mkdir(mode=0o700)
    line = json.dumps({"failed": 0, "kind": "postgresql.connection", "total": 1,
                       "window": "2026-10-01T00:00:00Z"}) + "\n"
    for name in ("host-counts-2026-10-01.jsonl", "host-counts-2026-10-02.jsonl",
                 "workers-counts-2026-09-30.jsonl"):
        (folder / name).write_text(line)
    target = tmp_path / "elsewhere.jsonl"
    target.write_text(line)
    (folder / "host-counts-2026-09-01.jsonl").symlink_to(target)
    clock = Clock(dt.datetime(2026, 10, 15, 23, 59, tzinfo=dt.UTC))
    counts = ProcessCounts(folder, "host", policy=PRODUCTION_OPERATIONS, clock=clock)
    counts.record("postgresql.connection", failed=False)
    clock.now = dt.datetime(2026, 10, 16, 0, 0, 5, tzinfo=dt.UTC)
    counts.record("postgresql.connection", failed=False)  # the first append
    assert not (folder / "host-counts-2026-10-01.jsonl").exists()
    assert (folder / "host-counts-2026-10-02.jsonl").exists()
    assert (folder / "host-counts-2026-10-15.jsonl").exists()
    link = folder / "host-counts-2026-09-01.jsonl"
    assert link.is_symlink() and target.read_text() == line
    assert (folder / "workers-counts-2026-09-30.jsonl").exists()
    counts.close()


def test_a_cut_line_and_a_window_crossed_by_two_threads(tmp_path, caplog):
    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    folder = tmp_path / "evidence"
    folder.mkdir(mode=0o700)
    day_file = folder / "host-counts-2026-11-01.jsonl"
    complete = json.dumps({"failed": 1, "kind": "postgresql.connection", "total": 4,
                           "window": "2026-11-01T09:00:00Z"}, sort_keys=True)
    day_file.write_text(complete + '\n{"failed": 1, "ki')
    clock = Clock(WINDOW_START)
    counts = ProcessCounts(folder, "host", policy=PRODUCTION_OPERATIONS, clock=clock)
    counts.record("postgresql.connection", failed=True)
    clock.now = WINDOW_START + dt.timedelta(minutes=5)
    counts.record("postgresql.connection", failed=False)
    assert day_file.read_text().splitlines() == [
        complete, '{"failed": 1, "ki',
        json.dumps({"failed": 1, "kind": "postgresql.connection", "total": 1,
                    "window": "2026-11-01T10:00:00Z"}, sort_keys=True)]
    caplog.clear()
    assert counts_over(folder, KINDS, WINDOW_START + dt.timedelta(minutes=5, seconds=1)) == {
        "postgresql.connection": (2, 5), "postgresql.transaction": (0, 0)}
    assert len(event_lines(caplog, "counts.line-unread")) == 1
    counts.close()

    damaged = tmp_path / "damaged"
    damaged.mkdir(mode=0o700)
    (damaged / "host-counts-2026-11-01.jsonl").write_text(json.dumps(
        {"failed": 0, "kind": "unregistered.kind", "total": 1,
         "window": "2026-11-01T10:00:00Z"}) + "\n")
    with pytest.raises(ValueError):
        counts_over(damaged, KINDS, WINDOW_START + dt.timedelta(minutes=5))

    crossed = tmp_path / "crossed"
    clock = Clock(WINDOW_START)
    counts = ProcessCounts(crossed, "host", policy=PRODUCTION_OPERATIONS, clock=clock)
    counts.record("postgresql.connection", failed=False)
    clock.now = WINDOW_START + dt.timedelta(minutes=5)
    barrier = threading.Barrier(2, timeout=10)

    def first_after_the_window():
        barrier.wait()
        counts.record("postgresql.connection", failed=False)

    threads = [threading.Thread(target=first_after_the_window) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    path = crossed / "host-counts-2026-11-01.jsonl"
    assert count_lines(path) == [{"failed": 0, "kind": "postgresql.connection", "total": 1,
                                  "window": "2026-11-01T10:00:00Z"}]
    counts.close()
    assert count_lines(path)[1:] == [{"failed": 0, "kind": "postgresql.connection",
                                      "total": 2, "window": "2026-11-01T10:05:00Z"}]


def test_a_short_write_goes_on_and_a_failed_sync_is_not_written_again(
        tmp_path, monkeypatch, caplog):
    """Review of 2026-11-09: a short `os.write` drops no line, and an `fsync` that fails
    after a complete write is logged without queueing the lines again, so the next append
    writes no duplicate and `counts_over` counts the window once."""
    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    folder = tmp_path / "evidence"
    day_file = folder / "host-counts-2026-11-01.jsonl"
    clock = Clock(WINDOW_START)
    counts = ProcessCounts(folder, "host", policy=PRODUCTION_OPERATIONS, clock=clock)
    real_write, writes = os.write, []

    def short_write(descriptor, data):
        writes.append(len(data))
        return real_write(descriptor, bytes(data[:7]))

    def failed_fsync(descriptor):
        raise OSError("sync refused")

    counts.record("postgresql.connection", failed=True)
    counts.record("postgresql.transaction", failed=False)
    clock.now = WINDOW_START + dt.timedelta(minutes=5)
    caplog.clear()
    monkeypatch.setattr(u8_counts.os, "write", short_write)
    monkeypatch.setattr(u8_counts.os, "fsync", failed_fsync)
    try:
        counts.record("postgresql.connection", failed=False)  # appends the 10:00 window
    finally:
        monkeypatch.undo()
    first = [
        {"failed": 1, "kind": "postgresql.connection", "total": 1,
         "window": "2026-11-01T10:00:00Z"},
        {"failed": 0, "kind": "postgresql.transaction", "total": 1,
         "window": "2026-11-01T10:00:00Z"},
    ]
    assert count_lines(day_file) == first
    assert len(writes) > 1  # the write went on after each short write
    unwritten = event_lines(caplog, "counts.unwritten")
    assert len(unwritten) == 1 and unwritten[0]["errorType"] == "OSError", unwritten
    clock.now = WINDOW_START + dt.timedelta(minutes=10)
    counts.record("postgresql.connection", failed=False)  # the next append
    assert count_lines(day_file) == first + [
        {"failed": 0, "kind": "postgresql.connection", "total": 1,
         "window": "2026-11-01T10:05:00Z"}]
    assert counts_over(folder, KINDS, WINDOW_START + dt.timedelta(minutes=10)) == {
        "postgresql.connection": (1, 2), "postgresql.transaction": (0, 1)}
    counts.close()


def test_a_write_that_raises_part_way_keeps_only_the_lines_not_yet_written(
        tmp_path, monkeypatch, caplog):
    """Re-review of 2026-11-09: when one `os.write` writes the first line and part of the
    second and the next raises, the first line counts as written and only the second stays
    pending, so the next append writes the second alone and `counts_over` counts each line
    once."""
    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    folder = tmp_path / "evidence"
    day_file = folder / "host-counts-2026-11-01.jsonl"
    clock = Clock(WINDOW_START)
    counts = ProcessCounts(folder, "host", policy=PRODUCTION_OPERATIONS, clock=clock)
    connection_line = {"failed": 1, "kind": "postgresql.connection", "total": 1,
                       "window": "2026-11-01T10:00:00Z"}
    transaction_line = {"failed": 0, "kind": "postgresql.transaction", "total": 1,
                        "window": "2026-11-01T10:00:00Z"}
    first_bytes = len(json.dumps(connection_line, sort_keys=True)) + 1 + 9
    real_write, writes = os.write, []

    def partial_then_no_space(descriptor, data):
        writes.append(len(data))
        if len(writes) == 1:
            return real_write(descriptor, bytes(data[:first_bytes]))
        raise OSError(28, "No space left on device")

    counts.record("postgresql.connection", failed=True)
    counts.record("postgresql.transaction", failed=False)
    clock.now = WINDOW_START + dt.timedelta(minutes=5)
    caplog.clear()
    monkeypatch.setattr(u8_counts.os, "write", partial_then_no_space)
    try:
        counts.record("postgresql.connection", failed=False)  # appends the 10:00 window
    finally:
        monkeypatch.undo()
    assert len(writes) == 2
    raw = day_file.read_text()
    assert raw.startswith(json.dumps(connection_line, sort_keys=True) + "\n")
    assert len(raw.encode()) == first_bytes  # the second line was cut part way
    unwritten = event_lines(caplog, "counts.unwritten")
    assert len(unwritten) == 1 and unwritten[0]["errorType"] == "OSError", unwritten

    clock.now = WINDOW_START + dt.timedelta(minutes=10)
    counts.record("postgresql.connection", failed=False)  # the next append
    lines = day_file.read_text().splitlines()
    assert [json.loads(line) for line in lines if line != lines[1]] == [
        connection_line, transaction_line,
        {"failed": 0, "kind": "postgresql.connection", "total": 1,
         "window": "2026-11-01T10:05:00Z"}]
    assert len(lines) == 4  # the cut part of the second line stays on its own
    caplog.clear()
    assert counts_over(folder, KINDS, WINDOW_START + dt.timedelta(minutes=10)) == {
        "postgresql.connection": (1, 2), "postgresql.transaction": (0, 1)}
    assert len(event_lines(caplog, "counts.line-unread")) == 1
    counts.close()


# --- Step 115(a): the gate observer (CP-6) -----------------------------------------------------
# Imported here, below every earlier test, so the never-mocked scan's listed lines stay put.

from types import SimpleNamespace  # noqa: E402

from backend.u8_gate_waits import (  # noqa: E402
    GateWaits,
    ObservedGate,
    SnapshotWriter,
    require_observable,
    write_snapshot,
)


def read_select(conn):
    return conn.execute("SELECT 1").fetchone()


def test_the_gate_observer_times_and_holds_each_gate_this_instance_takes(realm):
    observer = GateWaits()
    instance = CompleteTransactions(realm, process="api")
    threads, release = [], None
    try:
        instance.observe_gates(observer)
        instance.run("accounts", read_select)
        gates = observer.snapshot()["gates"]
        for key in ("process:*", "normal-owner:accounts", "owner:accounts"):
            assert (gates[key]["granted"], gates[key]["refused"]) == (1, 0), key
            assert sum(gates[key]["buckets"].values()) == 1, key

        threads, _, release, errors = held_runs(instance, ["accounts"])
        busy = one_more(instance, "accounts")
        assert str(busy) == "owner connection allocation exhausted"
        normal = observer.snapshot()["gates"]["normal-owner:accounts"]
        assert (normal["granted"], normal["refused"]) == (2, 1)
        assert normal["refusedWaitMsMax"] >= 900  # the 1 s queue (transactions.py:194)

        token = RECOVERY_REQUEST.set(True)
        try:
            instance.run("accounts", read_select)
        finally:
            RECOVERY_REQUEST.reset(token)
        gates = observer.snapshot()["gates"]
        assert gates["recovery:*"]["granted"] == 1
        assert gates["owner:accounts"]["granted"] == 3
        assert gates["process:*"]["granted"] == 3

        release.set()
        for thread in threads:
            thread.join(10)
        release = None
        assert not errors
        assert observer.snapshot()["gates"]["normal-owner:accounts"]["holdMsMax"] >= 900
        assert isinstance(instance._gate, ObservedGate)
        assert instance._gate._value == instance._gate._inner._value
        with pytest.raises(ValueError, match="gates already observed"):
            instance.observe_gates(GateWaits())
    finally:
        if release is not None:
            release.set()
        for thread in threads:
            thread.join(10)
        instance.close()


def test_gate_observation_serves_the_composed_realm_only(realm):
    require_observable(realm)
    for profile in (dataclasses.replace(realm, realm="production", database_name="docsuri_v2"),
                    SimpleNamespace(is_production=True, realm="service-operations",
                                    database_name="docsuri_u8")):
        with pytest.raises(ValueError, match="gate observation serves the composed realm only"):
            require_observable(profile)


def test_the_gate_record_buckets_waits_and_is_written_privately(tmp_path):
    observer = GateWaits()
    for seconds in (0.001, 0.003, 0.2, 1.2):
        observer.record("normal-owner", "accounts", seconds, granted=True)
    observer.record("normal-owner", "accounts", 1.0, granted=False)
    for seconds in (0.010, 0.030):
        observer.held("normal-owner", "accounts", seconds)
    snapshot = observer.snapshot()
    gate = snapshot["gates"]["normal-owner:accounts"]
    assert (gate["granted"], gate["refused"]) == (4, 1)
    assert gate["buckets"] == {"1": 1, "5": 1, "10": 0, "50": 0, "100": 0, "250": 1, "500": 0,
                               "1000": 0, "over": 1}
    assert round(gate["waitMsMax"]) == 1200 and round(gate["refusedWaitMsMax"]) == 1000
    assert round(gate["holdMsTotal"]) == 40 and round(gate["holdMsMax"]) == 30

    path = tmp_path / "gate-waits.json"
    write_snapshot(path, snapshot)
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
    assert json.loads(private_bytes(path)) == snapshot
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real)
    with pytest.raises(ValueError, match="the gate record folder must be a real folder"):
        write_snapshot(linked / "gate-waits.json", snapshot)

    written = tmp_path / "writer.json"
    writer = SnapshotWriter(observer, written, every=0.01).start()
    seen = []
    try:
        deadline = time.monotonic() + 5
        while len(seen) < 3 and time.monotonic() < deadline:
            if written.exists():
                sequence = json.loads(private_bytes(written))["sequence"]
                if not seen or sequence != seen[-1]:
                    seen.append(sequence)
            time.sleep(0.005)
    finally:
        writer.stop()
    assert seen, "the writer wrote no snapshot while it ran"
    assert json.loads(private_bytes(written))["sequence"] > max(seen)


# --- Step 135(a): one SCRAM login timed through an owner's own pool (NFR8.3; L2-5) ---------


def test_a_login_is_timed_through_the_owners_own_pool_and_takes_no_gate(realm):
    from backend.transactions import OWNERS

    value = CompleteTransactions(realm, process="maintenance")
    gates = [value._gate, value._owner_gates["accounts"]]
    taken = []
    try:
        assert value.owners == tuple(sorted(OWNERS | {"research", "topics", "export"}))
        assert len(value.owners) == 11
        for gate in gates:
            while gate.acquire(blocking=False):
                taken.append(gate)
        seconds = value.login_seconds("accounts")
        assert 0 < seconds < 3
        pool = value._pools["accounts"]
        assert pool.get_stats()["connections_num"] == 1
        assert pool.kwargs["require_auth"] == "scram-sha-256"
        # Every slot is still the test's: the login took no gate.
        assert all(not gate.acquire(blocking=False) for gate in gates)
        with pytest.raises(ValueError, match="^closed or unknown owner pool$"):
            value.login_seconds("nobody")
        value.close()
        with pytest.raises(ValueError, match="^closed or unknown owner pool$"):
            value.login_seconds("accounts")
    finally:
        for gate in taken:
            gate.release()
        value.close()


@pytest.mark.parametrize(
    "request_bytes", [CLEARTEXT, MD5, TRUST], ids=["cleartext", "md5", "trust"]
)
def test_a_login_that_is_not_scram_is_never_timed(realm, request_bytes):
    value = CompleteTransactions(dataclasses.replace(realm, database_port=STANDIN_PORT),
                                 process="maintenance")
    try:
        with WeakAuthStandin(request_bytes) as standin:
            with pytest.raises(psycopg.OperationalError, match="scram-sha-256"):
                value.login_seconds("operations")
        assert standin.passwords_seen == 0
    finally:
        value.close()


def test_a_login_outside_the_composed_realm_or_past_its_life_is_refused_before_any_connection(
        realm, tmp_path):
    production = dataclasses.replace(rebound_production(realm, tmp_path),
                                     database_port=free_port())
    refused = CompleteTransactions(production, process="maintenance")
    expired = CompleteTransactions(dataclasses.replace(realm, expires_at=time.time() - 1),
                                   process="maintenance")
    try:
        with pytest.raises(ValueError, match="^login timing serves the composed realm only$"):
            refused.login_seconds("accounts")
        assert "connections_num" not in refused._pools["accounts"].get_stats()
        with pytest.raises(ValueError, match="^synthetic retention expired$"):
            expired.login_seconds("operations")
        assert "connections_num" not in expired._pools["operations"].get_stats()
    finally:
        refused.close()
        expired.close()


# --- Step 164(h): v2's start against a listener that skips SCRAM (NFR3.3, BR6.11 (1)) -------


def _start_until_its_first_wait(profile) -> tuple:
    """v2's host start on `profile`, stopped once it has recorded a wait: the state it
    waited in, the composition it returned and the waits it recorded."""
    from backend.u8_host import Startup

    startup = Startup(lambda: profile, role="host")
    returned = []
    thread = threading.Thread(target=lambda: returned.append(startup.run()))
    thread.start()
    deadline = time.monotonic() + 15
    while not startup.waits and time.monotonic() < deadline:
        time.sleep(0.02)
    waited_in = startup.state
    startup.stop()
    thread.join(15)
    assert not thread.is_alive()
    return waited_in, returned, startup


class CountingStandin(WeakAuthStandin):
    """The stand-in, counting: every client it accepted, and the first byte each sent
    after its authentication request. A client that demands SCRAM hangs up and sends
    nothing. One that does not sends `p`, a password, to the cleartext and MD5 requests;
    to `TRUST`, which answers as a server with no authentication does (AuthenticationOk,
    then ReadyForQuery), it sends its first query, because for it the login is done."""

    def __init__(self, request: bytes):
        super().__init__(request)
        self.accepted = 0
        self.followed: list[bytes] = []

    def answer(self, connection: socket.socket) -> None:
        while True:
            length, code = struct.unpack("!II", _receive(connection, 8))
            if code in (SSL_REQUEST, GSS_REQUEST) and length == 8:
                connection.sendall(b"N")
                continue
            _receive(connection, length - 8)
            break
        connection.sendall(self.request)
        kind = connection.recv(1)
        self.followed.append(kind)
        self.passwords_seen += kind == b"p"

    def serve(self) -> None:
        while True:
            try:
                connection, _ = self.listener.accept()
            except OSError:
                return
            self.accepted += 1
            with connection:
                connection.settimeout(10)
                try:
                    self.answer(connection)
                except (ConnectionError, OSError):  # the client left mid-message
                    continue


@pytest.mark.parametrize(
    "request_bytes", [CLEARTEXT, MD5, TRUST], ids=["cleartext", "md5", "trust"]
)
def test_v2s_start_does_not_complete_against_a_listener_that_skips_scram(
        realm, monkeypatch, request_bytes):
    """A program listening in the instance's place cannot complete v2's login: the
    start's own connection is refused for want of SCRAM before any password is sent,
    the start waits and returns nothing, and the host is not ready. The built start does
    not exit: it waits and tries again (NFR7.4), so "fails" is shown as the check
    failing and the start not completing."""
    import sys

    from backend.u8_host import DATABASE_WAITS, PROCESS_GATES

    # A port of this test's own: a pool the stopped start leaves behind retries nowhere
    # another test listens.
    monkeypatch.setattr(sys.modules[__name__], "STANDIN_PORT", free_port())
    profile = dataclasses.replace(realm, database_port=STANDIN_PORT)
    pools = CompleteTransactions(profile, process=PROCESS_GATES["host"])
    try:
        with WeakAuthStandin(request_bytes) as standin:
            with pytest.raises(psycopg.OperationalError, match="scram-sha-256"):
                pools.run("operations", lambda conn: conn.execute("SELECT 1").fetchone())
        assert standin.passwords_seen == 0
    finally:
        pools.close()
    with CountingStandin(request_bytes) as standin:
        waited_in, returned, startup = _start_until_its_first_wait(profile)
    # The start reached the listener, and each client hung up on its request: it sent no
    # password, and to the trust answer no query, so it never took the login as done.
    assert standin.accepted >= 1 and standin.followed == [b""] * standin.accepted
    assert standin.passwords_seen == 0
    assert waited_in == "waiting-database" and startup.waits == [DATABASE_WAITS[0]]
    assert returned == [None] and startup.composition is None
    assert startup.state == "stopped"  # never `composed`: the host answers not ready
