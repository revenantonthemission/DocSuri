"""Resource separation, cancellation and delayed worker termination."""

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

from backend.control_runtime import (
    RECOVERY_REQUEST,
    WORK_DEADLINE,
    ControlAdmission,
    ControlLoop,
    recovery_route,
    shell_route,
    work_budget,
)

pytestmark = pytest.mark.u2_operations


@pytest.fixture(scope="session", autouse=True)
def exclusive_environment():
    yield


def test_recovery_lane_is_exact_and_cannot_run_mutations():
    assert recovery_route("POST", "/api/v2/c02/lifecycle-inspect")
    assert recovery_route("GET", "/api/v2/session")
    assert recovery_route("GET", "/api/v2/c03/settings-resets")
    assert recovery_route("GET", "/api/v2/jobs/12345678-1234-1234-1234-123456789abc/result")
    for method, path in [
        ("POST", "/api/v2/c03/settings-reset"),
        ("POST", "/api/v2/c02/access-login"),
        ("POST", "/api/v2/c06/accept-assistance"),
        ("POST", "/api/v2/c02/lifecycle-inspect/other"),
        ("GET", "/api/v2/jobs/12345678-1234-1234-1234-123456789abc/events"),
    ]:
        assert not recovery_route(method, path)


async def request(app, path="/api/v2/c02/access-login", method="POST", chunks=(b"{}",)):
    messages, pending = [], list(chunks)

    async def receive():
        if pending:
            return {"type": "http.request", "body": pending.pop(0), "more_body": bool(pending)}
        await asyncio.Event().wait()

    async def send(message):
        messages.append(message)

    await app({"type": "http", "path": path, "method": method}, receive, send)
    return messages


def test_saturation_keeps_two_recovery_slots_and_releases_on_finish():
    async def scenario():
        release = asyncio.Event()
        seen = []

        async def downstream(scope, receive, send):
            seen.append(RECOVERY_REQUEST.get())
            assert (await receive())["body"] == b"{}"
            await release.wait()
            await send({"type": "http.response.start", "status": 200, "headers": []})

        app = ControlAdmission(downstream)
        normals = [asyncio.create_task(request(app)) for _ in range(8)]
        await asyncio.sleep(0)
        assert app.active == [8, 0]
        rejected = await request(app)
        assert rejected[0]["status"] == 503
        recoveries = [
            asyncio.create_task(request(app, "/api/v2/c02/lifecycle-inspect")) for _ in range(2)
        ]
        await asyncio.sleep(0)
        assert app.active == [8, 2]
        assert (await request(app, "/api/v2/c02/lifecycle-inspect"))[0]["status"] == 503
        release.set()
        await asyncio.gather(*normals, *recoveries)
        assert seen == [False] * 8 + [True] * 2
        assert app.active == [0, 0] and not RECOVERY_REQUEST.get()

    asyncio.run(scenario())


def test_stop_admission_preserves_recovery_and_other_asgi_scopes():
    async def scenario():
        seen = []

        async def downstream(scope, receive, send):
            seen.append(scope["type"])

        app = ControlAdmission(downstream)
        app.admitting = False
        assert (await request(app))[0]["status"] == 503
        await request(app, "/api/v2/c02/lifecycle-inspect")
        await app({"type": "lifespan"}, None, None)
        assert seen == ["http", "lifespan"]

    asyncio.run(scenario())


def test_chunked_body_rejected_before_handler_and_slot_freed():
    async def scenario():
        async def downstream(*args):
            pytest.fail("oversized request reached account code")

        app = ControlAdmission(downstream)
        messages = await request(app, chunks=(b"x" * 32768, b"y" * 32769))
        assert messages[0]["status"] == 413
        assert app.active == [0, 0]

    asyncio.run(scenario())


def test_disconnect_and_exception_release_only_their_slot():
    async def scenario():
        async def downstream(*args):
            raise ValueError("adapter failure")

        app = ControlAdmission(downstream)
        with pytest.raises(ValueError, match="adapter failure"):
            await request(app)

        async def disconnect():
            return {"type": "http.disconnect"}

        async def send(message):
            pytest.fail("disconnected request emitted response")

        await app(
            {"type": "http", "path": "/api/v2/c02/access-login", "method": "POST"}, disconnect, send
        )
        assert app.active == [0, 0] and not RECOVERY_REQUEST.get()

    asyncio.run(scenario())


def test_worker_deadline_keeps_original_capacity_charged_until_return():
    async def scenario():
        entered, release = threading.Event(), threading.Event()
        calls = []

        def work(limit):
            calls.append((limit, WORK_DEADLINE.get()))
            entered.set()
            release.wait(2)

        loop = ControlLoop(SimpleNamespace(run_once=work), interval=0.01, deadline=0.02)
        loop.start()
        try:
            while not entered.is_set():
                await asyncio.sleep(0.002)
            await asyncio.sleep(0.05)
            assert loop.status["timeouts"] == 1 and len(calls) == 1
            closing = asyncio.create_task(loop.close())
            await asyncio.sleep(0.03)
            assert not closing.done() and len(calls) == 1
            assert calls[0][0] == 1 and calls[0][1] is not None
            release.set()
            await closing
            assert loop.status["state"] == "stopped" and len(calls) == 1
        finally:
            release.set()
            await loop.close()

    asyncio.run(scenario())


def test_worker_failure_does_not_invent_completion_and_stops_cleanly():
    async def scenario():
        def work(limit):
            raise RuntimeError("private details never copied to status")

        loop = ControlLoop(SimpleNamespace(run_once=work), interval=0.05, deadline=0.1)
        loop.start()
        with pytest.raises(ValueError, match="already"):
            loop.start()
        while loop.status["failures"] == 0:
            await asyncio.sleep(0.002)
        assert loop.status["state"] == "degraded" and loop.status["passes"] == 0
        assert "private" not in str(loop.status)
        await loop.close()

    asyncio.run(scenario())


def test_worker_context_restores_callers_deadline_and_policy_cannot_expand():
    assert WORK_DEADLINE.get() is None
    with work_budget(0.1):
        outer = WORK_DEADLINE.get()
        assert outer > time.monotonic()
        with work_budget(0.01):
            assert WORK_DEADLINE.get() < outer
        assert WORK_DEADLINE.get() == outer
    assert WORK_DEADLINE.get() is None
    with pytest.raises(ValueError):
        ControlLoop(None, deadline=11)
    with pytest.raises(ValueError):
        ControlAdmission(None, normal=100)


def test_recovery_request_uses_reserved_db_pool_and_shared_process_gate(tmp_path, monkeypatch):
    import json
    from contextlib import contextmanager

    from backend import transactions as tx

    class Connection:
        def execute(self, query, params=None, **kwargs):
            return SimpleNamespace(
                fetchone=lambda: {"run_id": "budget-run", "database_name": "docsuri_u2"}
            )

        def commit(self):
            pass

    class Pool:
        def __init__(self, *, kwargs, **options):
            self.kwargs, self.options, self.calls, self.closed = kwargs, options, 0, False

        @contextmanager
        def connection(self, **kwargs):
            self.calls += 1
            yield Connection()

        def close(self):
            self.closed = True

    path = tmp_path / "owner-credentials.json"
    path.write_text(
        json.dumps({"runId": "budget-run", "roles": {owner: "fixture" for owner in tx.OWNERS}})
    )
    path.chmod(0o600)
    profile = SimpleNamespace(
        root=tmp_path,
        run_id="budget-run",
        realm="account-controls",
        database_name="docsuri_u2",
        database_port=1,
        expires_at=time.time() + 100,
    )
    monkeypatch.setattr(tx, "NullConnectionPool", Pool)
    normal = tx.OwnerTransactions(profile)
    observation = tx.OwnerTransactions(profile, process="observation")
    assert normal._recovery_gate is observation._gate
    held = []
    try:
        for _ in range(5):
            assert normal._gate.acquire(blocking=False)
            held.append(True)
        token = RECOVERY_REQUEST.set(True)
        try:
            assert normal.run("accounts", lambda conn: 42) == 42
        finally:
            RECOVERY_REQUEST.reset(token)
        assert normal._pools["accounts"].calls == 0
        assert normal._recovery_pools["accounts"].calls == 1
        with work_budget(0.001):
            time.sleep(0.003)
            with pytest.raises(tx.Busy, match="deadline"):
                normal.run("accounts", lambda conn: pytest.fail("late action executed"))
    finally:
        for _ in held:
            normal._gate.release()
        normal.close()
        observation.close()
    assert all(p.closed for p in normal._recovery_pools.values())


def test_capacity_probe_stops_new_work_at_threshold_and_on_failure():
    from backend.control_runtime import ControlCapacity

    class Transactions:
        row = {"database_bytes": 10_000_000, "wal_bytes": 33_554_432}
        failure = False

        def run(self, owner, action):
            assert owner == "operations" and RECOVERY_REQUEST.get()
            if self.failure:
                raise RuntimeError("private transport detail")
            return action(
                SimpleNamespace(execute=lambda sql: SimpleNamespace(fetchone=lambda: self.row))
            )

    transactions = Transactions()
    capacity = ControlCapacity(transactions)
    assert not capacity.admitting
    capacity.refresh()
    assert capacity.admitting and capacity.last_bytes == 43_554_432
    transactions.row = {"database_bytes": 512 * 1024 * 1024 * 4 // 5, "wal_bytes": 0}
    capacity.refresh()
    assert not capacity.admitting
    transactions.failure = True
    with pytest.raises(RuntimeError):
        capacity.refresh()
    assert not capacity.admitting and not RECOVERY_REQUEST.get()
    transactions.failure = False
    transactions.row = {"database_bytes": True, "wal_bytes": 0}
    with pytest.raises(ValueError, match="observation"):
        capacity.refresh()
    assert not capacity.admitting


def test_shell_route_is_exempt_from_capacity_admission():
    assert shell_route("GET", "/")
    assert shell_route("GET", "/assets/index-abc123.js")
    assert shell_route("GET", "/api/v2/capabilities")
    for method, path in [
        ("GET", "/api/v2/session"),
        ("POST", "/"),
        ("GET", "/api/v2/c02/access-read-profile"),
    ]:
        assert not shell_route(method, path)


def test_capacity_stop_keeps_the_workspace_shell_loadable():
    async def scenario():
        seen = []
        capacity = SimpleNamespace(admitting=False)

        async def downstream(scope, receive, send):
            seen.append(scope["path"])

        app = ControlAdmission(downstream, capacity=capacity)
        await request(app, "/", method="GET")
        await request(app, "/assets/index-abc.js", method="GET")
        await request(app, "/api/v2/capabilities", method="GET")
        assert seen == ["/", "/assets/index-abc.js", "/api/v2/capabilities"]
        assert (await request(app))[0]["status"] == 503

    asyncio.run(scenario())


def test_capacity_stop_keeps_authenticated_recovery_routes_available():
    async def scenario():
        seen = []
        capacity = SimpleNamespace(admitting=False)

        async def downstream(scope, receive, send):
            seen.append(scope["path"])

        app = ControlAdmission(downstream, capacity=capacity)
        assert (await request(app))[0]["status"] == 503
        await request(app, "/api/v2/session", method="GET")
        await request(app, "/api/v2/c02/lifecycle-inspect")
        assert len(seen) == 2
        capacity.admitting = True
        await request(app)
        assert len(seen) == 3

    asyncio.run(scenario())
