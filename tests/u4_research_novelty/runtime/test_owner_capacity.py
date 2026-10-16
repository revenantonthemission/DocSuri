"""Real transaction admission with event-controlled pools, without a database."""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import uuid4

import pytest

from backend import transactions as tx
from backend.control_runtime import RECOVERY_REQUEST
from backend.local_profile import LocalProfile


@pytest.fixture
def allocation(tmp_path, monkeypatch):
    profile = LocalProfile(
        tmp_path, str(uuid4()), "https://127.0.0.1:18079", 15479,
        time.time() + 120, "docsuri_u4", "research-workspace",
    )
    credentials = tmp_path / "owner-credentials.json"
    credentials.write_text(json.dumps({
        "runId": profile.run_id,
        "roles": {owner: "synthetic" for owner in tx.OWNERS | {"research"}},
    }))
    credentials.chmod(0o600)
    lock = threading.Lock()
    counts = {"active": 0, "peak": 0}

    class Connection:
        def execute(self, query, params=None, **kwargs):
            return self

        def fetchone(self):
            return {"run_id": profile.run_id, "database_name": profile.database_name}

        def commit(self):
            pass

    class Pool:
        def __init__(self, **options):
            self.kwargs = options["kwargs"]

        @contextmanager
        def connection(self, timeout):
            with lock:
                counts["active"] += 1
                counts["peak"] = max(counts["peak"], counts["active"])
            try:
                yield Connection()
            finally:
                with lock:
                    counts["active"] -= 1

        def close(self):
            pass

    monkeypatch.setattr(tx, "NullConnectionPool", Pool)
    clients = {name: tx.OwnerTransactions(profile, process=name)
               for name in ("api", "worker", "observation", "maintenance")}
    for client in clients.values():
        client._queue_seconds = 0.05
    yield clients, counts
    assert counts["active"] == 0
    for client in clients.values():
        client.close()


def held(client, entered, release, *, recovery=False):
    token = RECOVERY_REQUEST.set(recovery)
    try:
        def action(_):
            entered.set()
            assert release.wait(3), "test did not release held connection"
            return "completed"

        return client.run("research", action)
    finally:
        RECOVERY_REQUEST.reset(token)


def test_normal_worker_cannot_consume_reserved_recovery_slot(allocation):
    clients, counts = allocation
    entered, release = threading.Event(), threading.Event()
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(held, clients["api"], entered, release)
        assert entered.wait(1)
        try:
            started = time.monotonic()
            with pytest.raises(tx.Busy):
                clients["worker"].run("research", lambda _: "must not run")
            assert time.monotonic() - started < 0.5
            token = RECOVERY_REQUEST.set(True)
            try:
                assert clients["api"].run("research", lambda _: "recovered") == "recovered"
            finally:
                RECOVERY_REQUEST.reset(token)
            assert counts["peak"] == 2
        finally:
            release.set()
        assert first.result(timeout=1) == "completed"
    assert clients["worker"].run("research", lambda _: "released") == "released"


@pytest.mark.parametrize("third", ["api", "worker", "observation", "maintenance"])
def test_all_instances_share_role_limit_two(allocation, third):
    clients, counts = allocation
    first_in, second_in, release = threading.Event(), threading.Event(), threading.Event()
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(held, clients["api"], first_in, release)
        assert first_in.wait(1)
        second = executor.submit(held, clients["worker"], second_in, release, recovery=True)
        assert second_in.wait(1)
        try:
            token = RECOVERY_REQUEST.set(True)
            try:
                with pytest.raises(tx.Busy):
                    clients[third].run("research", lambda _: "must not run")
            finally:
                RECOVERY_REQUEST.reset(token)
            assert counts == {"active": 2, "peak": 2}
        finally:
            release.set()
        assert first.result(timeout=1) == second.result(timeout=1) == "completed"
    assert clients[third].run("research", lambda _: "released") == "released"


@pytest.mark.parametrize("recovery", [False, True])
def test_callback_failure_releases_every_gate(allocation, recovery):
    clients, counts = allocation

    def fail(_):
        raise RuntimeError("synthetic failure")

    token = RECOVERY_REQUEST.set(recovery)
    try:
        for _ in range(4):
            with pytest.raises(RuntimeError, match="synthetic failure"):
                clients["api"].run("research", fail)
            assert counts["active"] == 0
        assert clients["api"].run("research", lambda _: "usable") == "usable"
    finally:
        RECOVERY_REQUEST.reset(token)
