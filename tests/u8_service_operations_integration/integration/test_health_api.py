"""The complete host's health routes (U8 plan Step 40; BR3.1, NFR8.1, NFR9.4).

`/health/live` answers from memory; `/health/ready` reads the latest observations in one
short read and names what is missing; neither route asks a producer or a provider.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.modules.operations import producers
from backend.modules.operations.observation_store import ObservationStore
from backend.modules.operations.readiness import CapabilityState
from tests.u8_service_operations_integration.host_flows import complete_host


@pytest.fixture
def host(realm):
    with complete_host(realm) as value:
        yield value


def forced(host, chosen: dict[str, str]) -> None:
    real = host.composition.readiness_view

    def view():
        readiness = real()
        states = {name: CapabilityState(name, chosen.get(name, "available"), None)
                  for name in readiness.contribution_of}
        readiness.states = lambda: states
        return readiness

    host.composition.readiness_view = view


def test_liveness_answers_from_memory(host, monkeypatch):
    def refuse(*args, **options):
        raise AssertionError("liveness read the observation store")

    monkeypatch.setattr(ObservationStore, "latest", refuse)
    answer = host.client.get("/health/live")
    assert answer.status_code == 200 and answer.json()["process"] == "alive"
    # The composed realm names its own profile kind (your decision of 2026-10-24).
    assert answer.json()["profile"] == "synthetic-local"


def test_liveness_names_the_production_profile(realm):
    import asyncio

    import httpx

    from backend.u8_host import host_app
    from tests.u8_service_operations_integration.host_flows import production_composition

    async def live(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="https://docsuri.rvnnt.dev") as http:
            return await http.get("/health/live")

    with production_composition(realm) as env:
        answer = asyncio.run(live(host_app(env.composition)))
    assert answer.status_code == 200
    assert answer.json()["profile"] == "production" and answer.json()["process"] == "alive"


def test_readiness_names_what_is_missing(host):
    forced(host, {"storage.capacity": "unavailable", "background.work": "stale",
                  "discovery.search": "degraded"})
    answer = host.client.get("/health/ready")
    assert answer.status_code == 503
    report = answer.json()
    assert report["ready"] is False
    assert {"storage.capacity", "background.work"} <= set(report["missing"])
    assert "discovery.search" not in report["missing"]
    forced(host, {"discovery.search": "degraded"})
    ready = host.client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["ready"] is True
    assert "discovery.search" in ready.json()["degraded"]


def test_neither_route_asks_a_producer_or_a_provider(host, monkeypatch):
    def refuse(*args, **options):
        raise AssertionError("a health route asked a producer")

    def every(kind):
        for sub in kind.__subclasses__():
            yield sub
            yield from every(sub)

    for kind in (producers.Producer, *every(producers.Producer)):
        if "observe" in vars(kind):
            monkeypatch.setattr(kind, "observe", refuse)
    entry = host.composition.parts["account-controls"]["entry"]
    for adapter in (entry.identity_providers or {}).values():
        monkeypatch.setattr(adapter, "reachable", refuse, raising=False)
    assert host.client.get("/health/live").status_code == 200
    assert host.client.get("/health/ready").status_code in (200, 503)


# --- The release's signed-out probe (Step 139(a); NFR9.12, BR10.7, L2-14) -----------------

# The rows the probe must never write, each read through its owner's login.
COUNTED_ROWS = (
    ("accounts", "accounts.session"), ("accounts", "accounts.mail_outbox"),
    ("accounts", "accounts.delivery"), ("accounts", "accounts.lifecycle_request"),
    ("research", "research.job"), ("assistance", "assistance.job"),
    ("corpus", "corpus.run"), ("export", "export.effect"),
    ("topics", "topics.digest_run"), ("topics", "topics.send_log_entry"),
)
LIMIT_SUMS = ("accounts.entry_shared_limit", "accounts.entry_address_limit")
PROBE_JOURNEY = [
    ("GET", "/health/live"), ("GET", "/"), ("GET", "/api/v2/session"),
    ("POST", "/api/v2/c01/host-resolve-navigation"), ("GET", "/privacy"),
    ("GET", "/health/ready"),
]


def work(connect) -> dict[str, int]:
    """The row counts the probe must leave as they are, and D2's sign-in limit sums."""
    found = {}
    for owner, table in COUNTED_ROWS:
        with connect(owner) as conn:
            found[table] = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
    with connect("accounts") as conn:
        for table in LIMIT_SUMS:
            found[table] = conn.execute(
                f"SELECT coalesce(sum(attempts), 0) AS n FROM {table}").fetchone()["n"]
    return found


def free_port() -> int:
    """A loopback port the system gives, never a realm's or v1's."""
    import socket

    with socket.socket() as chosen:
        chosen.bind(("127.0.0.1", 0))
        return chosen.getsockname()[1]


def recording(app, record: list[dict]):
    """An ASGI callable that notes each HTTP request's method, path, cookie names (never
    values) and whether it carried `Authorization`, then calls the app unchanged."""

    async def wrapper(scope, receive, send):
        if scope["type"] == "http":
            headers = {}
            for key, value in scope.get("headers", ()):
                headers.setdefault(key.lower(), []).append(value.decode("latin-1"))
            names = sorted({part.split("=", 1)[0].strip()
                            for line in headers.get(b"cookie", ())
                            for part in line.split(";") if part.strip()})
            record.append({"method": scope["method"], "path": scope["path"],
                           "cookies": names, "authorization": b"authorization" in headers})
        await app(scope, receive, send)

    return wrapper


@pytest.fixture
def probed(realm, tmp_path, monkeypatch, empty_outbox):
    import threading

    import uvicorn

    import backend.local_host as local_host
    import backend.u8_host as u8_host
    from backend.production_boundary import server_config
    from backend.u8_host import compose, host_app
    from tests.u8_service_operations_integration.integration.test_boundary import wait_port
    from tests.u8_service_operations_integration.integration.test_static_routes import (
        fixture_build,
    )

    release = tmp_path / "release"
    monkeypatch.setattr(u8_host, "BUILD", fixture_build(release / "frontend" / "dist"))
    # The shared host serves its shell from `frontend/dist` beside its own file, and CI's
    # backend job builds no frontend: `/` answers the fixture's shell in every run.
    monkeypatch.setattr(local_host, "__file__", str(release / "backend" / "local_host.py"))
    composition = compose(realm)
    try:
        app = host_app(composition)
        app.state.control_capacity.refresh()
        record: list[dict] = []
        port = free_port()
        server = uvicorn.Server(server_config(recording(app, record), port, log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            wait_port(port)
            yield SimpleNamespace(composition=composition, base=f"http://127.0.0.1:{port}",
                                  record=record)
        finally:
            server.should_exit = True
            thread.join(15)
    finally:
        composition.close()


def test_the_signed_out_probe_reads_liveness_readiness_and_a_signed_out_journey_only(
        probed, connect):
    from backend.u8_profile import public_authority
    from docsuri_ops.production_wiring import signed_out_probe

    authority = public_authority(probed.composition.profile)
    forced(probed, {})
    before = work(connect)
    probed.record.clear()
    assert signed_out_probe(probed.base, authority=authority) is True
    assert work(connect) == before
    assert not any("docsuri_session" in item["cookies"] or item["authorization"]
                   for item in probed.record)
    assert [(item["method"], item["path"]) for item in probed.record] == PROBE_JOURNEY
    assert [item["path"] for item in probed.record if "docsuri_entry" in item["cookies"]] == [
        "/api/v2/c01/host-resolve-navigation"]

    forced(probed, {"library.saved-work": "unavailable"})
    probed.record.clear()
    assert signed_out_probe(probed.base, authority=authority) is False
    assert (probed.record[-1]["method"], probed.record[-1]["path"]) == ("GET", "/health/ready")
    assert work(connect) == before

    probed.record.clear()
    assert signed_out_probe(probed.base, authority="elsewhere.example") is False
    assert [(item["method"], item["path"]) for item in probed.record] == [
        ("GET", "/health/live")]


def test_the_signed_out_probe_answers_false_for_a_body_that_is_not_an_object():
    import http.server
    import threading

    from docsuri_ops.production_wiring import signed_out_probe

    class Listing(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - the standard library's handler name
            body = b"[]"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    standin = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Listing)
    thread = threading.Thread(target=standin.serve_forever, daemon=True)
    thread.start()
    try:
        assert signed_out_probe(f"http://127.0.0.1:{standin.server_address[1]}",
                                authority="docsuri.rvnnt.dev") is False
    finally:
        standin.shutdown()
        standin.server_close()
        thread.join(15)


def test_the_signed_out_probe_answers_false_for_an_answer_that_is_not_http():
    """A listener whose status line is not HTTP: urllib re-raises `http.client`'s
    `BadStatusLine`, which is no `OSError`, so the probe must catch it too (Step 138(b):
    a malformed answer never escapes the release's verify)."""
    import socket
    import threading

    from docsuri_ops.production_wiring import signed_out_probe

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    listener.settimeout(15)

    def answer_once():
        try:
            connection, _ = listener.accept()
        except OSError:
            return
        with connection:
            connection.settimeout(5)
            try:
                connection.recv(65536)
                connection.sendall(b"NOT-HTTP garbage\r\n\r\n")
            except OSError:
                pass

    thread = threading.Thread(target=answer_once, daemon=True)
    thread.start()
    try:
        assert signed_out_probe(f"http://127.0.0.1:{listener.getsockname()[1]}",
                                authority="docsuri.rvnnt.dev") is False
    finally:
        listener.close()
        thread.join(15)


# --- Shutdown (R7) --------------------------------------------------------------------------


def run_drain(*, frames: int, drain_after: int | None, draining_at_start: bool = False):
    """One event stream through `StreamDrain`: the app sends `frames` frames, yielding to
    the event loop between them (no fixed time); the host drains after `drain_after`
    frames."""
    import asyncio

    from backend.u8_routes import StreamDrain

    async def scenario():
        draining = asyncio.Event()
        if draining_at_start:
            draining.set()
        sent = []

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"text/event-stream")]})
            for index in range(frames):
                await send({"type": "http.response.body", "body": f"id: {index}\n\n".encode(),
                            "more_body": True})
                if drain_after is not None and index + 1 == drain_after:
                    draining.set()
                await asyncio.sleep(0)
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        await StreamDrain(app, draining=draining)(
            {"type": "http", "path": "/api/v2/jobs/x/events"}, receive, send)
        return sent

    return asyncio.run(scenario())


def test_an_open_stream_closes_with_a_retry_hint_when_the_host_drains():
    sent = run_drain(frames=50, drain_after=2)
    bodies = [message["body"] for message in sent if message["type"] == "http.response.body"]
    assert bodies[:2] == [b"id: 0\n\n", b"id: 1\n\n"]
    assert bodies[-1] == b"retry: 2000\n\n" and sent[-1]["more_body"] is False
    assert len(bodies) < 50


def test_a_stream_asked_for_while_draining_is_refused_with_retry_after():
    sent = run_drain(frames=3, drain_after=None, draining_at_start=True)
    start = sent[0]
    assert start["status"] == 503 and (b"retry-after", b"2") in start["headers"]


def test_a_stream_that_ends_by_itself_is_unchanged():
    sent = run_drain(frames=3, drain_after=None)
    bodies = [message["body"] for message in sent if message["type"] == "http.response.body"]
    assert bodies == [b"id: 0\n\n", b"id: 1\n\n", b"id: 2\n\n", b""]


def test_the_host_process_drains_its_app_and_prepares_the_composition(realm, empty_outbox):
    import asyncio

    from backend.u8_host import HostProcess, Startup, draining_server
    from backend.u8_main import REALM_MANIFEST, boundary_hosts

    prepared = []
    process = HostProcess(Startup(lambda: realm), hosts=boundary_hosts(REALM_MANIFEST),
                          prepare=prepared.append)
    process.drain()  # nothing composed yet: nothing to drain
    process.startup.run()

    async def scenario():
        try:
            await process._serve_composition()
            assert prepared == [process.startup.composition]
            assert not process.app.state.draining.is_set()
            process.drain()
            assert process.app.state.draining.is_set()
        finally:
            await process.close()

    asyncio.run(scenario())
    server = draining_server(process, type("Config", (), {"loaded": False})())
    assert type(server).__name__ == "DrainingServer"


# --- Every provider down (Step 88(i); NFR7.12, L1-11, L1-53) ----------------------------------

PROVIDER_HOSTS = {
    "google": frozenset({"accounts.google.com", "oauth2.googleapis.com", "www.googleapis.com"}),
    "orcid": frozenset({"orcid.org"}),
    "resend": frozenset({"api.resend.com"}),
    "notion": frozenset({"api.notion.com"}),
}
# Two literal account-message keys (each message's own idempotency key).
FIRST_KEY = "88000000-0000-4000-8000-000000000001"
SECOND_KEY = "88000000-0000-4000-8000-000000000002"


class ProviderTransports:
    """A recording `httpx.MockTransport` per provider. While `down` is unset each answers
    as its provider would; once set, every request raises `httpx.ReadTimeout`."""

    def __init__(self):
        self.down = False
        self.requests: dict[str, list] = {name: [] for name in (*PROVIDER_HOSTS, "elsewhere")}

    def _answer(self, provider: str, request):
        import httpx

        self.requests[provider].append(request)
        if self.down:
            raise httpx.ReadTimeout("provider not answering", request=request)
        if provider in ("google", "orcid"):
            return httpx.Response(200, json={"issuer": f"https://{request.url.host}"})
        if provider == "resend" and request.method == "POST":
            return httpx.Response(200, json={"id": "88-resend-accepted"})
        return httpx.Response(401, json={"object": "error", "status": 401,
                                         "code": "unauthorized", "message": "no credential"})

    def transport(self, *providers: str):
        import httpx

        def handle(request):
            for provider in providers:
                if request.url.host in PROVIDER_HOSTS[provider]:
                    return self._answer(provider, request)
            self.requests["elsewhere"].append(request)
            raise httpx.ConnectError("not this provider's host", request=request)

        return httpx.MockTransport(handle)

    def posts(self) -> int:
        return len([request for request in self.requests["resend"] if request.method == "POST"])


def mailbox_files(root) -> list[str]:
    folder = root / "verification-mail"
    return sorted(str(path) for path in folder.rglob("*")) if folder.exists() else []


def test_ready_stays_true_and_features_say_so_while_every_provider_is_down(realm, monkeypatch):
    import asyncio
    import datetime as dt
    from uuid import uuid4

    import httpx

    from backend.modules.accounts.entry_limits import AccountMailUnavailable, client_address
    from backend.modules.accounts.integrations import digest_email, identity_providers
    from backend.modules.accounts.integrations.account_mail import (
        AccountMessage,
        ResendAccountMail,
    )
    from backend.modules.accounts.integrations.identity_providers import ProviderUnreachable
    from backend.modules.export import notion_session
    from backend.modules.operations.observations import Observations
    from backend.modules.operations.producers import (
        CapacityProducer,
        ModelsProducer,
        ProducerSchedule,
    )
    from backend.u8_host import host_app, worker_producers
    from tests.u8_service_operations_integration.host_flows import production_composition

    providers = ProviderTransports()
    monkeypatch.setattr(identity_providers, "network_transport",
                        lambda: providers.transport("google", "orcid"))
    monkeypatch.setattr(digest_email, "network_client", lambda **options: httpx.AsyncClient(
        transport=providers.transport("resend"), **options))
    monkeypatch.setattr(notion_session, "network_transport",
                        lambda: providers.transport("notion"))
    with production_composition(realm) as env:
        composition, standin = env.composition, env.standin
        entry = composition.parts["account-controls"]["entry"]
        mail, adapters = entry.account_mail, dict(entry.identity_providers)
        assert isinstance(mail, ResendAccountMail)
        root = composition.profile.root
        mailbox = mailbox_files(root)
        with standin.connect("accounts") as conn:
            address = conn.execute("SELECT email FROM accounts.account WHERE id=%s",
                                   (standin.maintainer,)).fetchone()["email"]

        def message(key: str) -> AccountMessage:
            return AccountMessage("verification", key, standin.maintainer, {
                "challengeId": str(uuid4()), "proof": "p" * 43,
                "flowBinding": "flow-" + uuid4().hex, "purpose": "verification",
                "email": address})

        producers = worker_producers(
            composition, lambda: {"state": "idle", "passes": 1, "timeouts": 0})
        for producer in producers:
            if isinstance(producer, CapacityProducer):
                producer._free = lambda: 10 ** 13  # plentiful: this Mac's disk never decides
        models = [item for item in producers if isinstance(item, ModelsProducer)]
        assert len(models) == 1
        schedule = ProducerSchedule(
            models + [item for item in producers if not isinstance(item, ModelsProducer)],
            Observations(ObservationStore(composition.transactions)), composition.policy,
            composition.clock)
        started = composition.clock()

        # Run 1: every provider answers.
        first = mail.deliver(message(FIRST_KEY))
        schedule.run_due(started)
        states, report = composition.capability_states(), composition.readiness()
        for capability in ("provider.google", "provider.orcid", "provider.resend",
                           "provider.notion", "provider.models", "research", "novelty"):
            assert states[capability]["state"] == "available", (capability, states[capability])
        assert report["ready"] is True, report
        assert mail.held_for_all() is False

        # Run 2: every request to those hosts times out, and the model runtime is down.
        providers.down = True
        env.model.down = httpx.ConnectError("the model runtime is not answering")
        for name, adapter in adapters.items():
            with pytest.raises(ProviderUnreachable):
                adapter.exchange("code-" + name, verifier="v" * 43, nonce="n" * 22)
        second = mail.deliver(message(SECOND_KEY))
        schedule.run_due(started + dt.timedelta(seconds=300))
        states, after = composition.capability_states(), composition.readiness()
        assert after["ready"] is True and after["missing"] == report["missing"], after
        for capability in ("provider.google", "provider.orcid", "provider.resend",
                           "provider.notion"):
            assert states[capability] == {"state": "unavailable",
                                          "reason": "provider-unreachable"}, capability
        assert states["provider.models"] == {"state": "unavailable",
                                             "reason": "runtime-unreachable"}
        for capability in ("research", "novelty"):
            assert states[capability] == {"state": "degraded",
                                          "reason": "model-runtime-waiting"}, capability
        assert (first, second) == ("accepted", "held")
        # L1-53: the account mail is refused up front while Resend is observed down.
        assert entry.account_mail is mail and mail.held_for_all() is True
        posts = providers.posts()
        refusals = []
        for email in (address, f"unknown-{uuid4().hex[:8]}@fixture.example.com"):
            with client_address(f"198.18.88.{len(refusals) + 1}"):
                with pytest.raises(AccountMailUnavailable) as refused:
                    entry.request_password_reset(uuid4(), email, "flow-" + uuid4().hex)
            refusals.append((refused.value.message_key, refused.value.retry_after_seconds))
        assert refusals == [("account-mail.unavailable", None)] * 2
        assert providers.posts() == posts
        assert all(entry.identity_providers[name] is adapter
                   for name, adapter in adapters.items())
        assert mailbox_files(root) == mailbox
        assert providers.requests["elsewhere"] == []
        for provider, requests in providers.requests.items():
            if provider != "elsewhere":
                assert requests, provider
                assert {request.url.host for request in requests} <= PROVIDER_HOSTS[provider]

        async def public_capabilities():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=host_app(composition)),
                                         base_url="https://docsuri.rvnnt.dev") as http:
                return await http.get("/api/v2/capabilities")

        page = asyncio.run(public_capabilities())
        assert page.status_code == 200, page.text
        items = {item["capabilityId"]: item for item in page.json()["items"]}
        for capability in ("provider.google", "provider.orcid", "provider.resend"):
            assert (items[capability]["state"], items[capability]["reasonKey"]) == (
                "unavailable", "provider-unreachable"), items[capability]
