"""The production composition (U8 plan Step 40; your decision of 2026-10-24).

On Step 12's production stand-in, with the real `BUILDERS` and never a stub, through
`compose()`, `Startup`, `host_app`, one workers pass, `run_scheduler_once` and
`model_lane` (built but not started). The shared model runtime answers through the
tests' stand-in transport; no provider, model or network address is ever reached. A case
that needs a contribution absent leaves its builder out (it is then `missing`), never
replaces it. § 11b reads the transport loggers once each production role has had its
logs configured, been composed and run its first use (U6's L2-3).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import re
import secrets
from uuid import UUID, uuid4

import httpx
import pytest

from backend.modules.accounts.integrations.account_mail import (
    HeldAccountMail,
    ResendAccountMail,
)
from backend.modules.accounts.integrations.identity_providers import (
    GoogleIdentityProvider,
    OrcidIdentityProvider,
    UnconfiguredIdentityProvider,
)
from backend.modules.accounts.integrations.u8_digest_mail import (
    AddressPendingDigestMail,
    GatedResendDigestMail,
    HeldDigestMail,
)
from backend.modules.accounts.services.control_identity import FixtureIdentityProvider
from backend.modules.accounts.u8_control_policy import PRODUCTION_POLICY
from backend.modules.accounts.u8_identity import ArrivalIdentityService
from backend.modules.discovery.citations import CitationExplorer
from backend.modules.discovery.local_embedding import LocalEmbeddings
from backend.modules.operations.observations import Observations
from backend.modules.research.errors import ResearchError
from backend.modules.summarization.model_runtime import ProductionAssistanceExecutor
from backend.u8_host import (
    BUILDERS,
    Startup,
    host_app,
    operations_runtime,
    run_scheduler_once,
)
from backend.u8_main import ROLES, configure_logs
from backend.u8_model_lane import model_lane
from backend.u8_outward import ImportedSources, NoCitationProvider, ObservedSearchEmbeddings
from backend.u8_policy import PRODUCTION_OPERATIONS
from backend.u8_registry import CAPABILITY_BY_ID
from backend.u8_research import (
    PRODUCTION_RESEARCH,
    ProductionResearchExecution,
    ProductionResearchService,
)
from backend.u8_research_model import LocalResearchModel
from backend.u8_routes import TOKEN_ROUTES
from backend.u8_topics import PRODUCTION_LIVE_TOPICS, PRODUCTION_REHEARSAL_TOPICS
from tests.u8_service_operations_integration import research_flows as rf
from tests.u8_service_operations_integration.host_flows import (
    EXPORT_DESTINATION,
    ROOT_MARK,
    installer_manifest,
    production_composition,
    production_root,
    standin_account,
    write_private,
)

EIGHT = ("paper-journey", "account-controls", "paper-corpus", "research-workspace",
         "topics-digests", "approved-export", "platform-control", "service-operations")


def without(name: str) -> dict:
    """The real builders, one left out (`missing`), never stubbed."""
    return {key: value for key, value in BUILDERS.items() if key != name}


async def ask(app, method: str, path: str, **options) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="https://docsuri.rvnnt.dev") as http:
        return await http.request(method, path, **options)


def observe(composition, capability: str, outcome: str = "available", reason=None) -> None:
    store = composition.parts["service-operations"]["observations"]
    observations = Observations(store)
    row = observations.make(capability, CAPABILITY_BY_ID[capability].producer, outcome,
                            observed_at=dt.datetime.now(dt.UTC), reason=reason,
                            limitations=(reason,) if reason else ())
    observations.record(CAPABILITY_BY_ID[capability].producer, [row])


def run_producers(composition) -> None:
    """One run of every producer, after the models' own (whose state the research and
    assistance producers read)."""
    schedule, _ = operations_runtime(composition)
    observe(composition, "provider.models")
    schedule.run_due()


# --- 1. every contribution active, in live and in rehearsal ----------------------------------


@pytest.mark.parametrize("mode", ["rehearsal", "live"])
def test_every_contribution_is_active_with_every_provider_configured(realm, mode):
    with production_composition(realm, mode=mode) as env:
        activations = env.composition.activations
        assert {name: (item.activation, item.reason) for name, item in activations.items()} == {
            name: ("active", None) for name in EIGHT}
        standin = env.standin
        startup = Startup(lambda: standin.profile, role="host",
                          release_root=standin.release_root, arrangement=standin.arrangement)
        try:
            assert startup.run() is not None and startup.state == "composed"
        finally:
            if startup.composition is not None:
                startup.composition.close()


# --- 2. each part is the real one ------------------------------------------------------------


@pytest.mark.parametrize("mode", ["rehearsal", "live"])
def test_each_part_is_the_real_one(realm, mode):
    with production_composition(realm, mode=mode) as env:
        parts = env.composition.parts
        entry = parts["account-controls"]["entry"]
        assert entry.control_policy is PRODUCTION_POLICY
        assert isinstance(entry.identity_providers["google"], GoogleIdentityProvider)
        assert isinstance(entry.identity_providers["orcid"], OrcidIdentityProvider)
        assert isinstance(entry.account_mail, ResendAccountMail)
        # Google and ORCID sign-in read the sign-in gate over the activation (L4-11).
        assert sign_in_gate_of(entry).activation is parts["service-operations"]["activation"]
        corpus = parts["paper-corpus"]
        assert isinstance(corpus["dispatch"].executor, ProductionAssistanceExecutor)
        assert isinstance(corpus["search"].embedder, ObservedSearchEmbeddings)
        assert isinstance(corpus["maintenance"].sources, ImportedSources)
        assert isinstance(corpus["citations"], CitationExplorer)
        assert isinstance(corpus["citations"].provider, NoCitationProvider)
        research = parts["research-workspace"]
        assert isinstance(research["service"], ProductionResearchService)
        assert isinstance(research["execution"], ProductionResearchExecution)
        assert research["service"].policy is PRODUCTION_RESEARCH
        assert research["execution"].policy is PRODUCTION_RESEARCH
        assert isinstance(research["provider"], LocalResearchModel)
        topics = parts["topics-digests"]
        assert topics["delivery"].policy is (PRODUCTION_LIVE_TOPICS if mode == "live"
                                             else PRODUCTION_REHEARSAL_TOPICS)
        assert isinstance(topics["delivery"].mail, GatedResendDigestMail)
        policy = parts["approved-export"]["policy"] if "policy" in parts["approved-export"] \
            else None
        if policy is not None:
            assert getattr(policy, "production_live", False) is (mode == "live")
        assert env.composition.policy is PRODUCTION_OPERATIONS
        lane = model_lane(env.composition)
        assert lane is not None and [owner.name for owner in lane.owners] == [
            "research", "assistance"]
        assert_one_allowance_and_counted_seams(env, mode)


def counted_base(factory) -> tuple[object, str]:
    """The base factory and kind a Step 56(c) counting layer closes over; fails unless
    `factory` is one of `u8_provider_probes`' counting layers."""
    assert factory.__module__ == "backend.u8_provider_probes", factory
    assert factory.__qualname__ in ("counting_client_factory.<locals>.factory",
                                    "counting_transport_factory.<locals>.factory"), factory
    cells = dict(zip(factory.__code__.co_freevars,
                     (cell.cell_contents for cell in factory.__closure__), strict=True))
    return cells["base"], cells["kind"]


def assert_one_allowance_and_counted_seams(env, mode: str) -> None:
    """Step 88(b): the one shared allowance (D12), Step 56(c)'s counting layer on each
    outward seam over its adapter's module attribute (L1-12), the cutover's availability
    folder and the composed embedder's batch."""
    from backend.modules.operations.producers import (
        CutoverProducer,
        DigestProducer,
        ProviderProducer,
    )
    from backend.modules.topics.delivery import DigestDelivery
    from backend.u8_host import availability_folder, operations_dashboard, worker_producers
    from backend.u8_provider_probes import identity_client, notion_transport, resend_client

    parts = env.composition.parts
    entry = parts["account-controls"]["entry"]
    allowance = parts["service-operations"]["allowance"]
    assert entry.account_mail.allowance is allowance
    producers = worker_producers(env.composition)
    resend = [item for item in producers
              if isinstance(item, ProviderProducer) and item.capability == "provider.resend"]
    assert len(resend) == 1 and resend[0].allowance is allowance
    delivery = parts["topics-digests"]["delivery"]
    # NFR9.2 (L3-2): the digest producer's due read is scoped as the scheduler's.
    digests = [item for item in producers if isinstance(item, DigestProducer)]
    assert len(digests) == 1 and digests[0].recipient is not None
    assert digests[0].recipient() == delivery.recipient_scope()
    if mode == "live":
        assert delivery.allowance is allowance
    else:
        assert type(delivery) is DigestDelivery
        assert delivery.policy is PRODUCTION_REHEARSAL_TOPICS
        assert not hasattr(delivery, "allowance")  # L1-38
    for name in ("google", "orcid"):
        base, kind = counted_base(entry.identity_providers[name]._verifier._client_factory)
        assert (base, kind) == (identity_client, "provider." + name)
    assert counted_base(entry.account_mail._resend._client_factory) == (
        resend_client, "provider.resend")
    assert counted_base(delivery.mail._client_factory) == (resend_client, "provider.resend")
    session = parts["approved-export"]["service"].adapter._session
    assert counted_base(session._transport_factory) == (notion_transport, "provider.notion")
    cutover = [item for item in producers if isinstance(item, CutoverProducer)]
    dashboard = operations_dashboard(env.composition, parts["service-operations"])
    assert len(cutover) == 1
    assert cutover[0].availability == dashboard.availability_folder == availability_folder(
        env.composition)
    embedder = parts["paper-corpus"]["embedder"]
    assert (embedder.batch, embedder.keep_alive) == (16, -1)


# --- 3. nothing synthetic --------------------------------------------------------------------

SYNTHETIC_NAMES = ("Synthetic", "Fixture", "Standin", "StandIn")


def synthetic_policies() -> set[int]:
    from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from backend.modules.corpus.limits import SYNTHETIC_LIMITS
    from backend.u8_policy import SYNTHETIC_OPERATIONS

    found = {id(SYNTHETIC_POLICY), id(U8_SYNTHETIC_POLICY), id(SYNTHETIC_LIMITS),
             id(SYNTHETIC_OPERATIONS)}
    try:
        from backend.u5_policy import SYNTHETIC_TOPICS

        found.add(id(SYNTHETIC_TOPICS))
    except ImportError:
        pass
    return found


def walk(value, seen: set[int], found: list[str], policies: set[int], depth: int = 0) -> None:
    if depth > 5 or id(value) in seen or callable(value) and not hasattr(value, "__dict__"):
        return
    seen.add(id(value))
    if id(value) in policies:
        found.append(f"synthetic policy {type(value).__name__}")
    if isinstance(value, dict):
        for item in value.values():
            walk(item, seen, found, policies, depth + 1)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            walk(item, seen, found, policies, depth + 1)
        return
    module = type(value).__module__
    if not module.startswith(("backend.", "docsuri_ops.")):
        return
    if any(name in type(value).__name__ for name in SYNTHETIC_NAMES):
        found.append(type(value).__name__)
    for item in vars(value).values() if hasattr(value, "__dict__") else ():
        if not isinstance(item, type) and not hasattr(item, "__self__"):
            walk(item, seen, found, policies, depth + 1)


def test_no_part_row_or_route_is_synthetic(realm):
    with production_composition(realm, mode="live") as env:
        found: list[str] = []
        walk(env.composition.parts, set(), found, synthetic_policies())
        assert found == []
        app = host_app(env.composition)
        for row in app.state.capability_catalog:
            assert not any("synthetic" in item for item in (*row["modeIds"], *row["levelIds"])), row
        live = asyncio.run(ask(app, "GET", "/health/live"))
        assert live.status_code == 200 and live.json()["profile"] == "production"


# --- 4. research turns under the production policy ---------------------------------------------


def test_a_research_turn_runs_under_the_production_policy_and_its_bound(realm):
    with production_composition(realm) as env:
        run_producers(env.composition)
        service = env.composition.parts["research-workspace"]["service"]
        env_like = type("Env", (), {"standin": env.standin, "service": service})()
        owner = rf.member(env_like)
        scope = rf.paper_scope(env_like, owner)
        session = service.create_session(owner, {"title": "합성 연구", "scope": scope})
        turn = {"sessionId": session["sessionId"], "scope": scope, "mode": "question",
                "text": "어텐션은 무엇을 하나요?", "policy": PRODUCTION_RESEARCH.reference()}
        accepted = service.accept(owner, uuid4(), turn, "research-turn")
        assert accepted["state"] in ("accepted", "queued") or "jobId" in accepted
        with pytest.raises(ResearchError) as refused:
            service.accept(owner, uuid4(), {**turn, "text": "가" * 700}, "research-turn")
        assert refused.value.code == "INVALID_ARGUMENT"


def test_without_research_in_the_marker_a_turn_is_refused(realm):
    with production_composition(realm, marker=("assistance",)) as env:
        run_producers(env.composition)
        states = env.composition.capability_states()
        assert states["research"]["reason"] == "model-runtime-waiting"
        service = env.composition.parts["research-workspace"]["service"]
        env_like = type("Env", (), {"standin": env.standin, "service": service})()
        owner = rf.member(env_like)
        scope = rf.paper_scope(env_like, owner)
        session = service.create_session(owner, {"title": "합성 연구", "scope": scope})
        with pytest.raises(ResearchError) as refused:
            service.accept(owner, uuid4(), {
                "sessionId": session["sessionId"], "scope": scope, "mode": "question",
                "text": "어텐션은 무엇을 하나요?", "policy": PRODUCTION_RESEARCH.reference()},
                "research-turn")
        assert refused.value.code == "DEPENDENCY_UNAVAILABLE"


# --- 5. without Google and ORCID -------------------------------------------------------------


def test_without_google_and_orcid_both_are_unconfigured_and_begin_writes_nothing(realm):
    environment = {key: value for key, value in rf_environment().items()
                   if not key.startswith(("google", "orcid"))}
    with production_composition(realm, environment=environment) as env:
        entry = env.composition.parts["account-controls"]["entry"]
        assert all(isinstance(entry.identity_providers[name], UnconfiguredIdentityProvider)
                   for name in ("google", "orcid"))
        service = ArrivalIdentityService(
            entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})

        def flows() -> int:
            with env.standin.connect("accounts") as conn:
                return conn.execute("SELECT count(*) AS n FROM accounts.identity_flow"
                                    ).fetchone()["n"]

        before = flows()
        for name in ("google", "orcid"):
            # A browser of the test's own (Step 20 item 9); the refusal writes nothing.
            with pytest.raises(TimeoutError):
                service.begin(None, name, "sign_in", "binding-" + uuid4().hex, "account")
        assert flows() == before


def rf_environment() -> dict:
    from tests.u8_service_operations_integration.host_flows import PROVIDER_ENVIRONMENT

    return dict(PROVIDER_ENVIRONMENT)


# --- 6. without the Resend key -----------------------------------------------------------------


def test_without_the_resend_key_mail_and_digests_are_held_and_all_stay_active(realm):
    environment = {key: value for key, value in rf_environment().items()
                   if key != "resendApiKey"}
    with production_composition(realm, environment=environment) as env:
        parts = env.composition.parts
        assert isinstance(parts["account-controls"]["entry"].account_mail, HeldAccountMail)
        assert isinstance(parts["topics-digests"]["delivery"].mail, HeldDigestMail)
        assert all(item.activation == "active"
                   for item in env.composition.activations.values())


# --- 7. without real-export.json -------------------------------------------------------------


def test_without_the_export_settings_export_is_policy_unresolved(realm):
    with production_composition(realm, export=False) as env:
        export = env.composition.activations["approved-export"]
        assert (export.activation, export.reason) == ("unavailable", "policy-unresolved")
        assert "export" in env.composition.readiness()["missing"]


# --- 8. rehearsal before the maintainer has an address ---------------------------------------


def test_rehearsal_without_the_maintainers_address_holds_every_digest(realm):
    with production_composition(realm, maintainer=False) as env:
        parts = env.composition.parts
        assert env.composition.activations["topics-digests"].activation == "active"
        assert isinstance(parts["topics-digests"]["delivery"].mail, AddressPendingDigestMail)
        assert env.composition.activations["approved-export"].activation == "active"
        run_producers(env.composition)
        digest = env.composition.capability_states()["topics.digest"]
        assert digest == {"state": "degraded", "reason": "maintainer-address-pending"}


def test_live_mode_without_the_maintainers_address_keeps_its_refusal(realm):
    with production_composition(realm, mode="live", maintainer=False) as env:
        topics = env.composition.activations["topics-digests"]
        assert (topics.activation, topics.reason) == ("unavailable", "policy-unresolved")


# --- 9. a marker that is `{}` or lacks research --------------------------------------------------


@pytest.mark.parametrize("marker", [{}, ("assistance",)])
def test_a_marker_without_research_leaves_research_and_novelty_waiting(realm, marker):
    with production_composition(realm, marker=marker) as env:
        run_producers(env.composition)
        states = env.composition.capability_states()
        for capability in ("research", "novelty"):
            assert states[capability] == {"state": "degraded",
                                          "reason": "model-runtime-waiting"}, states[capability]


# --- 10. without account-controls --------------------------------------------------------------


def test_without_account_controls_there_is_no_session_and_no_owner_route(realm):
    with production_composition(realm, builders=without("account-controls")) as env:
        assert env.composition.activations["account-controls"].reason == "missing"
        app = host_app(env.composition)
        assert not any(path.startswith(("/api/v2/c0", "/api/v2/c1", "/api/v2/session"))
                       for _, path in app.state.route_inventory)
        # The host answers an unmounted API path as not ready, never from an owner route.
        session = asyncio.run(ask(app, "GET", "/api/v2/session"))
        assert session.status_code == 503 and session.json()["code"] == "NOT_READY"
        for path in ("/api/v2/c03/library-list-saved-papers", "/api/v2/c07/list-research-jobs",
                     "/api/v2/c02/access-login"):
            answer = asyncio.run(ask(app, "POST", path, json={}))
            assert answer.status_code == 503 and answer.json()["code"] == "NOT_READY", path
        public = asyncio.run(ask(app, "GET", "/api/v2/capabilities"))
        assert public.status_code == 200
        assert "account.controls" in env.composition.readiness()["missing"]


# --- 11. the workers pass, the scheduler and the lane --------------------------------------------


def test_a_workers_pass_sends_no_model_request_and_the_lane_is_not_running(realm):
    with production_composition(realm, process="workers") as env:
        env.composition.worker.run_once(limit=1)
        assert env.model.calls("/api/chat") == [] and env.model.calls("/api/embed") == []
        outcomes = run_scheduler_once(env.composition)
        assert outcomes and set(outcomes.values()) == {"done"}, outcomes
        lane = model_lane(env.composition)
        assert lane is not None and lane.status()["state"] != "running"


# --- 11b. the transport loggers after each role's first use (U6's L2-3) ---

TRANSPORT_LOGGERS = ("httpx", "httpcore")


def is_transport_logger(name: str) -> bool:
    return name in TRANSPORT_LOGGERS or name.startswith(("httpx.", "httpcore."))


class KeptRecords(logging.Handler):
    """The probe's handler: it keeps each record it is handed."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def first_use(env, role: str):
    """`"ran"` when the role answers as its first use should, else what it answered."""
    composition = env.composition
    if role == "host":
        answer = asyncio.run(ask(host_app(composition), "GET", "/health/live"))
        return "ran" if answer.status_code == 200 else answer.status_code
    if role == "workers":
        lane = model_lane(composition)
        running = lane is None or lane.status()["state"] == "running"
        summary = composition.worker.run_once(limit=1)
        asked = env.model.calls("/api/chat") + env.model.calls("/api/embed")
        quiet = not running and not asked and isinstance(summary, dict)
        return "ran" if quiet and summary["chained"]["setAside"] == [] else (
            {"laneRunning": running, "summary": summary, "modelRequests": len(asked)})
    outcomes = run_scheduler_once(composition)
    return "ran" if outcomes and set(outcomes.values()) == {"done"} else outcomes


def transport_levels_below_warning() -> list[str]:
    names = set(TRANSPORT_LOGGERS) | {
        name for name, item in logging.Logger.manager.loggerDict.items()
        if isinstance(item, logging.Logger) and is_transport_logger(name)}
    return sorted(name for name in names
                  if logging.getLogger(name).getEffectiveLevel() < logging.WARNING)


def transport_probe() -> list[str]:
    """One request through httpx over a mock transport (no socket); the names of the
    records the transport loggers let through."""
    kept = KeptRecords()
    loggers = [logging.getLogger(name) for name in TRANSPORT_LOGGERS]
    for logger in loggers:
        logger.addHandler(kept)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(204)))
    try:
        client.get("https://transport-probe.invalid/")
    finally:
        client.close()
        for logger in loggers:
            logger.removeHandler(kept)
    return [record.name for record in kept.records]


def logged_transport_lines(path) -> list[str]:
    for handler in logging.getLogger().handlers:
        handler.flush()
    # `log_events.configure` opens the role's file at once: a missing one is a misplaced log.
    assert path.is_file(), f"the role's log file is not at {path.name}"
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return sorted(line["logger"] for line in lines
                  if is_transport_logger(str(line.get("logger", ""))))


@pytest.mark.parametrize("role", ROLES)
def test_the_composed_production_roles_keep_the_transport_loggers_at_warning(
        realm, role, tmp_path, logging_state):
    # Logs first, in `u8_main.main`'s order: a manifest outside the realm's is production.
    configure_logs(tmp_path / "environment.json", role)
    with production_composition(realm, process=role) as env:
        activations = {name: item.activation
                       for name, item in env.composition.activations.items()}
        use = first_use(env, role)
        below = transport_levels_below_warning()
        probe = transport_probe()
        logged = logged_transport_lines(tmp_path / "logs" / f"{role}.log")
    assert {"activations": activations, "use": use, "below": below, "probe": probe,
            "logged": logged} == {"activations": dict.fromkeys(EIGHT, "active"),
                                  "use": "ran", "below": [], "probe": [], "logged": []}


# --- 12. the installer's first manifest loads unchanged ------------------------------------------


def test_the_installers_first_manifest_loads_unchanged():
    from backend.local_profile import KEY_FOLDERS
    from backend.u8_profile import ProductionProfile

    manifest = installer_manifest("docsuri-v2-" + "a" * 16, uuid4())
    assert manifest["database"] == manifest["rehearsalDatabase"]
    with production_root() as folder:
        assert (folder / ROOT_MARK).is_file()
        root = folder / "profile"
        root.mkdir(mode=0o700)
        for name in KEY_FOLDERS:
            (root / name).mkdir(mode=0o700)
        write_private(root / "environment.json", json.dumps(manifest).encode())
        profile = ProductionProfile.load(root / "environment.json", service_uid=os.getuid())
        assert (profile.mode, profile.database_name, profile.rehearsal_database) == (
            "rehearsal", manifest["database"], manifest["rehearsalDatabase"])


# --- 13. the production boundary and Notion's seam (Step 88(a)-(b)) ----------------------------

PUBLIC = "https://docsuri.rvnnt.dev"


@pytest.fixture(scope="module")
def served(realm):
    """One production composition (rehearsal, maintainer imported) for the module's
    boundary and Notion tests: its `host_app` built once and its capacity refreshed once,
    as the host's refresher does."""
    from types import SimpleNamespace

    with production_composition(realm) as env:
        app = host_app(env.composition)
        app.state.control_capacity.refresh()
        yield SimpleNamespace(env=env, app=app)


def client_of(app):
    from fastapi.testclient import TestClient

    return TestClient(app, base_url=PUBLIC, follow_redirects=False)


def test_the_production_host_accepts_only_its_public_and_loopback_names(served):
    from backend.production_boundary import BoundaryHosts

    profile = served.env.composition.profile
    assert BoundaryHosts.for_profile(profile).accepted == {
        "docsuri.rvnnt.dev", "127.0.0.1", "127.0.0.1:18200"}
    client = client_of(served.app)
    for host in ("docsuri.rvnnt.dev", "127.0.0.1:18200", "127.0.0.1"):
        assert client.get("/health/live", headers={"host": host}).status_code == 200, host
    for host in ("127.0.0.1:18110", "127.0.0.1:18109", "127.0.0.1:18201", "localhost:18200",
                 "localhost", "[::1]:18200", "docsuri.rvnnt.dev:443", "elsewhere.example"):
        refused = client.get("/health/live", headers={"host": host})
        assert refused.status_code == 400, host
        assert refused.json()["messageKey"] == "request.host", host
    assert client.get("/api/v2/session",
                      headers={"host": "docsuri.rvnnt.dev"}).status_code == 200
    for host in ("127.0.0.1:18200", "127.0.0.1"):
        # The http scheme these names take is refused by every browser route.
        answer = client.get("/api/v2/session", headers={"host": host})
        assert (answer.status_code, answer.json()["code"]) == (403, "FORBIDDEN"), host


def login_body() -> dict:
    """A sign-in whose policy is not the entry's: both checks pass, no sign-in runs."""
    return {"email": f"nobody-{uuid4().hex[:8]}@fixture.example.com",
            "password": f"Synthetic-{secrets.token_hex(8)}-Aa1!",  # generated per run (L1-36)
            "policyRef": {"policyId": "synthetic-local-entry", "revision": "2"}}


def login(client, csrf: str | None, *, origin: str = PUBLIC, host: str | None = None):
    headers = {"origin": origin, "idempotency-key": str(uuid4())}
    if csrf is not None:
        headers["x-csrf-token"] = csrf
    if host is not None:
        headers["host"] = host
    return client.post("/api/v2/c02/access-login", json=login_body(), headers=headers)


def test_origin_and_csrf_are_bound_to_the_public_origin(served):
    from backend.local_browser import ENTRY_COOKIE

    client = client_of(served.app)
    session = client.get("/api/v2/session")
    assert session.status_code == 200, session.text
    cookies = [value for value in session.headers.get_list("set-cookie")
               if value.startswith(ENTRY_COOKIE + "=")]
    assert len(cookies) == 1
    attributes = {part.strip().split("=", 1)[0].lower(): part.strip()
                  for part in cookies[0].split(";")[1:]}
    assert {"secure", "httponly", "samesite", "path"} <= set(attributes)
    assert attributes["samesite"].lower() == "samesite=strict"
    assert attributes["path"] == "Path=/" and "domain" not in attributes
    csrf = session.json()["csrfToken"]
    passed = login(client, csrf)
    assert (passed.status_code, passed.json()["code"]) == (503, "POLICY_UNRESOLVED"), passed.text
    for origin in ("http://127.0.0.1:18200", "https://127.0.0.1:18110"):
        refused = login(client, csrf, origin=origin)
        assert refused.status_code == 403, origin
        assert refused.json()["messageKey"] == "request.origin", origin
    other = client_of(served.app)
    foreign = other.get("/api/v2/session").json()["csrfToken"]
    for token in (None, foreign):
        refused = login(client, token)
        assert (refused.status_code, refused.json()["code"]) == (403, "FORBIDDEN"), token
    loopback = login(client, csrf, host="127.0.0.1:18200")
    assert (loopback.status_code, loopback.json()["code"]) == (403, "FORBIDDEN")


# D7's Origin rule on every state-changing route (Step 131, L2-12): every request whose
# method is neither GET nor HEAD, less `TOKEN_ROUTES` (the one-click unsubscribe POST,
# authorized by its single-use token, and the identity callback GET).
UNSUBSCRIBE_POST = ("POST", "/api/v2/topics/email-unsubscribe/{token}")
# Routes whose part is waiting or unavailable and whose handler, read, refuses before
# `require_post_headers` would run: `(method, path) -> (status, code, reason)`. An entry
# is added only by Step 131(c)'s rule; the walk leaves its Origin rule unchecked.
REFUSED_BEFORE_THE_ORIGIN_CHECK: dict[tuple[str, str], tuple[int, str, str]] = {}
PLACEHOLDER = re.compile(r"\{([^}:]+)(?::[^}]*)?\}")


def filled(template: str) -> str:
    """A request path for `template`: each placeholder a fresh UUID, `{provider}` orcid."""
    return PLACEHOLDER.sub(
        lambda match: "orcid" if match.group(1) == "provider" else str(uuid4()), template)


def changing_request(client, method: str, path: str, csrf: str, *, origin: str | None):
    headers = {"x-csrf-token": csrf, "idempotency-key": str(uuid4())}
    if origin is not None:
        headers["origin"] = origin
    return client.request(method, path, json={}, headers=headers)


def answer_of(response) -> tuple[int, str | None, str | None]:
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    return response.status_code, body.get("code"), body.get("messageKey")


def test_every_state_changing_route_refuses_a_request_without_the_public_origin(
        served, record_property):
    client = client_of(served.app)
    session = client.get("/api/v2/session")
    assert session.status_code == 200, session.text
    csrf = session.json()["csrfToken"]
    inventory = served.app.state.route_inventory
    changing = sorted(key for key in inventory
                      if key[0] not in ("GET", "HEAD") and key not in TOKEN_ROUTES)
    accepting = {key for key, (kind, _) in inventory.items()
                 if kind == "accept" and key not in TOKEN_ROUTES}
    assert accepting <= set(changing), sorted(accepting - set(changing))
    assert {key for key in TOKEN_ROUTES if key[0] not in ("GET", "HEAD")} == {UNSUBSCRIBE_POST}
    assert changing, "the inventory holds no state-changing route"
    record_property("changingRoutes", len(changing))
    collected, met = {}, set()
    for method, template in changing:
        path = filled(template)
        missing = answer_of(changing_request(client, method, path, csrf, origin=None))
        if missing == (403, "FORBIDDEN", "request.forbidden"):
            continue
        if 200 <= missing[0] < 300:
            collected[(method, template)] = missing
            continue
        public = answer_of(changing_request(client, method, path, csrf, origin=PUBLIC))
        entry = REFUSED_BEFORE_THE_ORIGIN_CHECK.get((method, template))
        if entry is not None and missing[:2] == public[:2] == entry[:2]:
            met.add((method, template))
            continue
        collected[(method, template)] = (missing, public)
    assert collected == {}, collected
    assert met == set(REFUSED_BEFORE_THE_ORIGIN_CHECK), sorted(
        set(REFUSED_BEFORE_THE_ORIGIN_CHECK) - met)
    passed = login(client, csrf)
    assert (passed.status_code, passed.json()["code"]) == (503, "POLICY_UNRESOLVED"), passed.text
    saved = client.post("/api/v2/c03/library-list-saved-papers", json={"page": {"limit": 1}},
                        headers={"origin": PUBLIC, "x-csrf-token": csrf,
                                 "idempotency-key": str(uuid4())})
    assert (saved.status_code, saved.json()["code"]) == (401, "UNAUTHENTICATED"), saved.text


def maintainer_authority(standin):
    """A live session for the imported maintainer, with its research consent, written
    through the accounts login as `standin_account` writes them."""
    from backend.transactions import Authority

    session = uuid4()
    with standin.connect("accounts") as conn:
        conn.execute("INSERT INTO accounts.consent(account_id,purpose,granted) "
                     "VALUES(%s,'local-research',true) ON CONFLICT(account_id,purpose) "
                     "DO NOTHING", (standin.maintainer,))
        revision = conn.execute("SELECT authority_revision FROM accounts.account WHERE id=%s",
                                (standin.maintainer,)).fetchone()["authority_revision"]
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,"
            "expires_at) VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '30 minutes')",
            (session, standin.maintainer, str(uuid4()), str(uuid4()), revision))
    return Authority(standin.maintainer, session)


def notion_token() -> str:
    """A Notion token the test's scenario knows, generated per run (L1-36)."""
    return "synthetic-notion-token-" + uuid4().hex


def fake_notion_factory(tokens, fakes: list):
    """`notion_session.network_transport` for these tests: on each call a new `FakeNotion`
    (U6's fake transport under the real adapter) knowing every one of `tokens` and
    `EXPORT_DESTINATION`'s page, kept in `fakes`."""
    from backend.modules.export.fake_notion import FakeNotion

    def factory():
        fake = FakeNotion()
        for token in tokens:
            fake.add_token(token, bot_id=uuid4().hex,
                           workspace_id="0b7d2a51c4e94f36a8e1d2c3b4a59687",
                           workspace_name="Synthetic Workspace")
        fake.add_page(EXPORT_DESTINATION, title="합성 페이지")
        fakes.append(fake)
        return fake

    return factory


def owner_reads(activation, monkeypatch) -> list:
    """A call-through spy on the composed recipients' owner read: each call's connection
    id and the owner the real read answered."""
    reads: list = []
    real = activation._connection_owner

    def spied(connection_id):
        owner = real(connection_id)
        reads.append((connection_id, owner))
        return owner

    monkeypatch.setattr(activation, "_connection_owner", spied)
    return reads


def configure_first(service, authority, token: str) -> dict:
    """A first configure through the composed `ExportService`, as the configure route
    hands it over."""
    return service.configure(authority, {"token": token,
                                         "credentialPolicy": service.policy.reference()},
                             operation=uuid4())


def assert_anothers_pending_connection_is_refused(standin, service, token: str, seen,
                                                  *, cause: str) -> None:
    """Another account's first configure, with a token the scenario accepts, is held on
    its pending row: its owner is read and is not the maintainer, nothing is sent, the
    configure answers DEPENDENCY_UNAVAILABLE and its reservation is released."""
    from backend.modules.export.classification import COULD_NOT_CHECK
    from backend.modules.export.errors import ExportError

    results, reads, fakes = seen
    other = standin_account(standin, "notion-other")
    made, read = len(fakes), len(reads)
    with pytest.raises(ExportError) as refused:
        configure_first(service, other, token)
    assert refused.value.code == "DEPENDENCY_UNAVAILABLE"
    assert results[-1].category == COULD_NOT_CHECK and results[-1].cause == cause
    assert len(fakes) == made  # nothing was sent
    assert [owner for _, owner in reads[read:]] == [other.account_id]
    with standin.connect("export") as conn:
        left = conn.execute("SELECT count(*) AS n FROM export.connection WHERE account_id=%s",
                            (other.account_id,)).fetchone()["n"]
    assert left == 0


def test_each_notion_operation_gets_its_own_counted_transport_and_client(
        served, monkeypatch, tmp_path):
    import base64

    import notion_client

    from backend.modules.export import notion_session
    from backend.modules.export.classification import CAUSE_TRANSPORT, COULD_NOT_CHECK, OK
    from backend.modules.export.errors import ProtectionUnavailable
    from backend.modules.export.fake_notion import FakeNotion
    from backend.modules.export.notion_session import (
        CAUSE_NOT_PERMITTED,
        StoredConnection,
        install_provider_gate,
    )
    from backend.modules.export.token_keyring import TokenKeyring
    from backend.modules.export.token_vault import TokenVault
    from backend.u8_provider_probes import CountingTransport
    from tests.u8_service_operations_integration.conftest import (
        NetworkRefused,
        refuse_network_transport,
    )

    composition = served.env.composition
    operations = composition.parts["service-operations"]
    # This module's composition's gate, as `_wire_production` installs it: a later
    # composition in this process installs its own.
    install_provider_gate(operations["activation"], operations["activation"])
    service = composition.parts["approved-export"]["service"]
    adapter = service.adapter
    session = adapter._session
    authority = maintainer_authority(served.env.standin)
    token, other_token = notion_token(), notion_token()
    fakes: list[FakeNotion] = []
    recording_factory = fake_notion_factory((token, other_token), fakes)

    sdks: list = []

    class Recording(notion_client.AsyncClient):
        def __init__(self, *args, **options):
            super().__init__(*args, **options)
            sdks.append((self, options["client"]))

    results: list = []
    real_run = session.run

    async def spied_run(*args, **options):
        result = await real_run(*args, **options)
        results.append(result)
        return result

    monkeypatch.setattr(notion_client, "AsyncClient", Recording)
    monkeypatch.setattr(session, "run", spied_run)
    monkeypatch.setattr(notion_session, "network_transport", recording_factory)
    reads = owner_reads(operations["activation"], monkeypatch)
    # The maintainer's connection, configured through the composed `ExportService` (your
    # answer of 2026-11-11, "Wire the owner read"): its check runs on a candidate token
    # that carries only the pending row's id, and the gate reads that row's owner.
    configured = configure_first(service, authority, token)
    assert configured["state"] == "connected", configured
    assert results[-1].category == OK and len(fakes) == 1
    connection_id = UUID(configured["connectionId"])
    assert reads[0] == (connection_id, authority.account_id)  # the pending row's owner
    assert_anothers_pending_connection_is_refused(
        served.env.standin, service, other_token, (results, reads, fakes),
        cause=CAUSE_NOT_PERMITTED)
    target = StoredConnection(authority.account_id, connection_id)
    before = len(sdks)
    reads = [asyncio.run(adapter.read_destination(target, EXPORT_DESTINATION,
                                                  gate_key=connection_id))
             for _ in range(2)]
    assert [read.category for read in reads] == [OK, OK], reads
    built = sdks[before:]
    assert len(built) == 2 and built[0][0] is not built[1][0]
    clients = [http for _, http in built]
    assert clients[0] is not clients[1] and all(http.is_closed for http in clients)
    counted = [http._transport._inner for http in clients]
    assert all(isinstance(item, CountingTransport) for item in counted)
    assert counted[0] is not counted[1]
    inner = [item._inner for item in counted]
    assert inner == fakes[-2:] and inner[0] is not inner[1]
    assert all(fake.requests for fake in inner)
    # The session guard back in place: the counting factory refuses, and a third read
    # sends nothing and is reduced to could-not-check with its transport cause.
    monkeypatch.setattr(notion_session, "network_transport", refuse_network_transport)
    with pytest.raises(NetworkRefused):
        session._transport_factory()
    made, built_count = len(fakes), len(sdks)
    third = asyncio.run(adapter.read_destination(target, EXPORT_DESTINATION,
                                                 gate_key=connection_id))
    assert third.category == COULD_NOT_CHECK
    assert results[-1].category == COULD_NOT_CHECK
    assert results[-1].verdict.cause == CAUSE_TRANSPORT
    assert (len(fakes), len(sdks)) == (made, built_count)
    # U6's sealing (NFR3.1): the composed vault's keyring lives in the export key folder,
    # the envelope holds the token in no encoding, and only that vault opens it.
    keyring = service.vault._keys
    assert keyring.root == composition.profile.root / "export-keys"
    row = service.repository.open_token_envelope(authority.account_id, connection_id)
    envelope = row["sealed_token"]
    raw = token.encode()
    for encoded in (raw, raw.hex().encode(), base64.b64encode(raw),
                    base64.urlsafe_b64encode(raw)):
        assert encoded not in envelope
    assert service.vault.open(envelope, account_id=authority.account_id,
                              connection_id=connection_id, revision=row["revision"]) == token
    elsewhere = tmp_path / "other-export-keys"
    elsewhere.mkdir(mode=0o700)

    class NoSealedTokens:
        def token_key_counts(self):
            return []

    other = TokenVault(TokenKeyring(elsewhere, keyring.run_id, NoSealedTokens(),
                                    policy=service.policy))
    with pytest.raises(ProtectionUnavailable):
        other.open(envelope, account_id=authority.account_id, connection_id=connection_id,
                   revision=row["revision"])


def test_the_maintainers_first_notion_connection_is_made_in_the_live_window(
        realm, monkeypatch):
    """Your answer of 2026-11-11 ("Wire the owner read"): in the live maintainer-only
    window, with Notion held for your decision, the maintainer's first configure through
    the composed `ExportService` runs its check on the pending row and stores the
    connection, a browser-driven read through it prepares the export, and another
    account's pending connection stays held (`provider-held`)."""
    from backend.modules.export import notion_session
    from backend.modules.export.classification import OK
    from backend.modules.export.notion_session import CAUSE_PROVIDER_HELD, StoredConnection

    with production_composition(realm, mode="live") as env:
        composition = env.composition
        activation = composition.parts["service-operations"]["activation"]
        assert (activation.mode, activation.state("notion")) == ("live", "held")
        service = composition.parts["approved-export"]["service"]
        session = service.adapter._session
        authority = maintainer_authority(env.standin)
        token, other_token = notion_token(), notion_token()
        fakes: list = []
        results: list = []
        real_run = session.run

        async def spied_run(*args, **options):
            result = await real_run(*args, **options)
            results.append(result)
            return result

        monkeypatch.setattr(session, "run", spied_run)
        monkeypatch.setattr(notion_session, "network_transport",
                            fake_notion_factory((token, other_token), fakes))
        reads = owner_reads(activation, monkeypatch)
        configured = configure_first(service, authority, token)
        assert configured["state"] == "connected", configured
        connection_id = UUID(configured["connectionId"])
        assert results[-1].category == OK and len(fakes) == 1
        assert reads == [(connection_id, authority.account_id)]  # the pending row's owner
        read = asyncio.run(service.adapter.read_destination(
            StoredConnection(authority.account_id, connection_id), EXPORT_DESTINATION,
            gate_key=connection_id))
        assert read.category == OK and len(fakes) == 2
        assert activation.state("notion") == "held"  # nothing approved Notion
        assert_anothers_pending_connection_is_refused(
            env.standin, service, other_token, (results, reads, fakes),
            cause=CAUSE_PROVIDER_HELD)


def test_while_notion_is_observed_unavailable_exports_wait_and_nothing_reaches_notion(
        realm, monkeypatch):
    """L2-13 (reliability-design § 10): Notion's breaker opens only while provider.notion
    is observed unavailable. While open, every operation answers `provider-held` before
    any client, request or token; the export page's answer is DEPENDENCY_UNAVAILABLE;
    once the probe passes, calls resume."""
    from backend.modules.export import notion_session
    from backend.modules.export.classification import (
        COULD_NOT_CHECK,
        OK,
        PROTECTION_UNAVAILABLE,
        classify_write,
    )
    from backend.modules.export.errors import ExportError
    from backend.modules.export.notion_session import CAUSE_PROVIDER_HELD, StoredConnection
    from backend.modules.operations.producers import ProducerSchedule, ProviderProducer
    from backend.u8_outward import ObservedNotionGate

    with production_composition(realm) as env:
        composition = env.composition
        operations = composition.parts["service-operations"]
        activation = operations["activation"]
        service = composition.parts["approved-export"]["service"]
        adapter = service.adapter
        session = adapter._session
        authority = maintainer_authority(env.standin)
        token, other_token = notion_token(), notion_token()
        fakes: list = []
        results: list = []
        opened: list = []
        real_run = session.run

        async def spied_run(*args, **options):
            result = await real_run(*args, **options)
            results.append(result)
            return result

        class SpiedVault:
            def __init__(self, real):
                self._real = real

            def open(self, *args, **options):
                value = self._real.open(*args, **options)
                opened.append(options.get("connection_id"))
                return value

        monkeypatch.setattr(notion_session, "network_transport",
                            fake_notion_factory((token, other_token), fakes))
        monkeypatch.setattr(session, "run", spied_run)
        monkeypatch.setattr(session, "_vault", SpiedVault(session._vault))

        def probe_once(passes: bool) -> None:
            producer = ProviderProducer("provider.notion", composition.ledger,
                                        probe=lambda: passes)
            schedule = ProducerSchedule([producer], Observations(operations["observations"]),
                                        composition.policy, composition.clock)
            assert schedule.run_due() == ["provider.notion"]

        # Not yet observed: the breaker stays closed.
        assert composition.capability_states()["provider.notion"]["state"] == "unknown"
        configured = configure_first(service, authority, token)
        assert configured["state"] == "connected", configured
        assert len(fakes) == 1 and opened == []
        connection_id = UUID(configured["connectionId"])
        target = StoredConnection(authority.account_id, connection_id)
        # The probe fails: provider.notion is observed unavailable, the ledger unchanged.
        probe_once(False)
        assert composition.capability_states()["provider.notion"] == {
            "state": "unavailable", "reason": "provider-unreachable"}
        assert activation.state("notion") == "active"
        for gate_key in (connection_id, None):
            read = asyncio.run(adapter.read_destination(target, EXPORT_DESTINATION,
                                                        gate_key=gate_key))
            assert read.category == COULD_NOT_CHECK, gate_key
            assert results[-1].cause == CAUSE_PROVIDER_HELD, gate_key

        async def work(sdk, context):
            pytest.fail("the held write reached its work")

        written = asyncio.run(session.run(target, 5.0, work, classify=classify_write))
        assert (written.category, written.cause) == (PROTECTION_UNAVAILABLE,
                                                     CAUSE_PROVIDER_HELD)
        other = standin_account(env.standin, "notion-other")
        with pytest.raises(ExportError) as refused:
            configure_first(service, other, other_token)
        assert refused.value.code == "DEPENDENCY_UNAVAILABLE"
        assert results[-1].category == COULD_NOT_CHECK
        assert results[-1].cause == CAUSE_PROVIDER_HELD
        with env.standin.connect("export") as conn:
            left = conn.execute("SELECT count(*) AS n FROM export.connection "
                                "WHERE account_id=%s", (other.account_id,)).fetchone()["n"]
        assert left == 0
        assert len(fakes) == 1 and opened == []  # no client, no request, no token
        # The probe passes: calls resume.
        probe_once(True)
        assert composition.capability_states()["provider.notion"]["state"] == "available"
        read = asyncio.run(adapter.read_destination(target, EXPORT_DESTINATION,
                                                    gate_key=connection_id))
        assert read.category == OK and len(fakes) == 2 and opened == [connection_id]
        gate = notion_session._INSTALLED_GATE["gate"]
        assert isinstance(gate, ObservedNotionGate) and gate.activation is activation
        assert notion_session._INSTALLED_GATE["recipients"] is activation


KEY_FOLDER_OF = {
    "account-verifier.key": "verifier-key",
    "search-cursor.key": "cursor-key",
    "account-control-keyring.json": "control-keys",
    "account-control-keyring.lock": "control-keys",
    "account-control-keyring.initialized": "control-keys",
    "export-token-keyring.json": "export-keys",
    "export-token-keyring.lock": "export-keys",
    "export-token-keyring.initialized": "export-keys",
}
STAGING_FOLDER_OF = {
    ".account-verifier.key-": "verifier-key",  # ensure_key_file's `.<name>-<16 hex>`
    ".search-cursor.key-": "cursor-key",
    ".control-key-": "control-keys",           # the control keyring's staging prefix
    ".export-key-": "export-keys",             # U6's keyring staging prefix
}


def key_folder_of(path) -> str | None:
    """The key folder a key path belongs in, or None for a path that is no key."""
    import re
    from pathlib import Path

    path = Path(path)
    if path.name in KEY_FOLDER_OF:
        return KEY_FOLDER_OF[path.name]
    for prefix, folder in STAGING_FOLDER_OF.items():
        if path.name.startswith(prefix):
            return folder
    if path.parent.name == "u8-keyring-snapshot" and re.fullmatch(r"[0-9a-f]{64}\.json",
                                                                 path.name):
        return "control-keys/u8-keyring-snapshot"
    return None


class CreationSpies:
    """Delegating spies on every way a file is created; each calls the real function
    and returns its result, recording the created path."""

    def __init__(self, monkeypatch):
        import builtins
        import fcntl
        import tempfile

        self.paths: list[str] = []
        real_open, real_builtin = os.open, builtins.open
        real_link, real_replace, real_mkstemp = os.link, os.replace, tempfile.mkstemp

        def where(path, dir_fd=None) -> str:
            path = os.fsdecode(path)
            if dir_fd is not None and not os.path.isabs(path):
                folder = fcntl.fcntl(dir_fd, fcntl.F_GETPATH, bytes(1024))
                return os.path.join(os.fsdecode(folder.rstrip(b"\0")), path)
            return path

        def spy_open(path, flags, mode=0o777, *, dir_fd=None):
            descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
            if flags & os.O_CREAT:
                self.paths.append(where(path, dir_fd))
            return descriptor

        def spy_builtin(file, mode="r", *args, **options):
            stream = real_builtin(file, mode, *args, **options)
            if isinstance(file, (str, bytes, os.PathLike)) and any(
                    flag in mode for flag in "wax+"):
                self.paths.append(where(file))
            return stream

        def spy_link(source, target, *args, **options):
            result = real_link(source, target, *args, **options)
            self.paths.append(where(target, options.get("dst_dir_fd")))
            return result

        def spy_replace(source, target, *args, **options):
            result = real_replace(source, target, *args, **options)
            self.paths.append(where(target, options.get("dst_dir_fd")))
            return result

        def spy_mkstemp(*args, **options):
            result = real_mkstemp(*args, **options)
            self.paths.append(os.fsdecode(result[1]))
            return result

        monkeypatch.setattr(os, "open", spy_open)
        monkeypatch.setattr(builtins, "open", spy_builtin)
        monkeypatch.setattr(os, "link", spy_link)
        monkeypatch.setattr(os, "replace", spy_replace)
        monkeypatch.setattr(tempfile, "mkstemp", spy_mkstemp)

    def keys(self) -> list[tuple[str, str]]:
        return [(path, folder) for path in self.paths
                if (folder := key_folder_of(path)) is not None]


def test_every_key_lives_only_in_its_key_folder(realm, monkeypatch):
    import tempfile
    from pathlib import Path

    from backend.modules.accounts import u8_verifier_key

    spies = CreationSpies(monkeypatch)
    with production_composition(realm, maintainer=False) as env:
        profile = env.composition.profile
        root = Path(profile.root).resolve()
        # With no account, the compose's `start_keys(occupied=False)` made both start keys.
        made = {Path(path).name for path, _ in spies.keys()}
        assert {"account-verifier.key", "search-cursor.key"} <= made
        # `control-key-start`'s path: the control keyring, its marker and U8's snapshot.
        u8_verifier_key.start_keyring(profile.root, profile.run_id)
        # The first load of the composed contribution's keyring creates U6's export keyring.
        env.composition.parts["approved-export"]["service"].vault._keys.load()
        expected = {
            "verifier-key": {"account-verifier.key"},
            "cursor-key": {"search-cursor.key"},
            "export-keys": {"export-token-keyring.json", "export-token-keyring.lock",
                            "export-token-keyring.initialized"},
        }
        for folder, names in expected.items():
            assert {path.name for path in (root / folder).iterdir()} == names, folder
        controls = root / "control-keys"
        assert {path.name for path in controls.iterdir()} == {
            "account-control-keyring.json", "account-control-keyring.lock",
            "account-control-keyring.initialized", "u8-keyring-snapshot"}
        snapshots = list((controls / "u8-keyring-snapshot").iterdir())
        assert len(snapshots) == 1 and key_folder_of(snapshots[0]) is not None
        files = {path.name for path in root.iterdir() if path.is_file()}
        assert files == {"environment.json", "owner-credentials.json",
                         "private-environment.json", "real-export.json"}
        recorded = spies.keys()
        assert recorded
        elsewhere = [Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve(),
                     Path("/private/tmp").resolve()]
        for path, folder in recorded:
            place = Path(path).resolve().parent
            assert place == root / folder, (path, folder)
            assert not any(place == other or other in place.parents for other in elsewhere)


# --- search's circuit breaker in a composed production (L3-7) --------------------------------


def composed_search(corpus) -> dict:
    from backend.u3_policy import QUERY_VOCABULARY, SEARCH_POLICY

    return corpus["search"].search(None, {"query": {
        "query": "attention", "modeId": "semantic", "orderId": "relevance", "filters": [],
        "vocabularyRevision": QUERY_VOCABULARY, "policyRef": SEARCH_POLICY}})


def embeds(model) -> int:
    return sum(1 for request in model.requests if request.url.path == "/api/embed")


def probe_models(composition) -> None:
    """One provider.models observation through a new schedule (a schedule that has run
    is not due again within the producer's interval)."""
    from backend.modules.operations.producers import (
        ModelsProducer,
        OllamaTags,
        ProducerSchedule,
    )

    observations = Observations(composition.parts["service-operations"]["observations"])
    schedule = ProducerSchedule([ModelsProducer(OllamaTags(), composition.policy)],
                                observations, composition.policy, composition.clock)
    assert schedule.run_due() == ["provider.models"]


def test_while_provider_models_is_observed_unavailable_search_answers_by_words_and_calls_no_model(  # noqa: E501
        realm):
    """Reliability-design § 10 (lines 133-137, 145), L3-7: in a composed production the
    search embedder sits behind the breaker; while provider.models is observed
    unavailable a semantic search answers by words and nothing reaches the runtime, even
    once the runtime answers again; after a passing probe, semantic search resumes."""
    with production_composition(realm) as env:
        composition, model = env.composition, env.model
        parts = composition.parts
        corpus = parts["paper-corpus"]
        assert isinstance(corpus["search"].embedder, ObservedSearchEmbeddings)
        assert corpus["search"].embedder.embedder is corpus["embedder"]
        assert isinstance(corpus["embedder"], LocalEmbeddings)
        assert parts["research-workspace"]["provider"].ranker.embedder is corpus["embedder"]

        before = embeds(model)
        answer = composed_search(corpus)
        assert (answer["outcome"], answer["effectiveModeId"]) == ("complete", "semantic")
        assert embeds(model) == before + 1

        model.down = httpx.ConnectError("the model runtime is not answering")
        probe_models(composition)
        assert composition.capability_states()["provider.models"] == {
            "state": "unavailable", "reason": "runtime-unreachable"}

        model.down = None
        before = len(model.requests)
        held = composed_search(corpus)
        assert (held["outcome"], held["effectiveModeId"]) == ("degraded", "lexical")
        assert "semantic-search-unavailable" in held["limitations"]
        assert len(model.requests) == before

        probe_models(composition)
        assert composition.capability_states()["provider.models"]["state"] == "available"
        before = embeds(model)
        resumed = composed_search(corpus)
        assert (resumed["outcome"], resumed["effectiveModeId"]) == ("complete", "semantic")
        assert embeds(model) == before + 1


# --- every provider's circuit breaker in a composed production (U8 plan Step 162(d); L4-11) ----


def sign_in_gate_of(entry):
    """The entry's identity gate, which must be the sign-in breaker for Google and ORCID."""
    from backend.u8_outward import ObservedProviderGate

    gate = entry.identity_gate
    assert isinstance(gate, ObservedProviderGate) and gate.providers == {"google", "orcid"}
    return gate


def test_while_provider_models_is_observed_unavailable_only_its_probe_reaches_the_runtime(
        realm):
    """Reliability-design § 10 (lines 133-137, 145-146), L4-11: in a composed production,
    once one real observation reads provider.models unavailable, nothing but the next
    observation's own requests reaches the runtime, although it answers again: not the
    lane's turns, a workers pass or a semantic search. After the probe passes the
    accepted jobs run, and one semantic search costs exactly one state read."""
    from test_model_lane import assistance_job, assistance_state, assistant_or_research

    from backend.u8_outward import install_models_breaker, install_search_breaker

    with production_composition(realm, process="workers") as env:
        composition, model = env.composition, env.model
        parts = composition.parts
        corpus = parts["paper-corpus"]
        model.chat = assistant_or_research
        run_producers(composition)
        flows = type("Env", (), {
            "standin": env.standin, "parts": parts,
            "service": parts["research-workspace"]["service"],
            "store": parts["service-operations"]["observations"]})()
        owner = rf.member(flows)
        turn = rf.accept_turn(flows, owner, rf.paper_scope(flows, owner))
        job = assistance_job(flows, owner)
        waiting = assistance_state(flows, job["id"])
        lane = model_lane(composition)

        model.down = httpx.ConnectError("the model runtime is not answering")
        probe_models(composition)
        assert composition.capability_states()["provider.models"] == {
            "state": "unavailable", "reason": "runtime-unreachable"}
        model.down = None  # the runtime answers again; nothing has observed it yet
        before = len(model.requests)
        for _ in range(3):
            assert lane.turn() == {"research": "skipped", "assistance": "skipped"}
        composition.worker.run_once(limit=1)
        held = composed_search(corpus)
        assert (held["outcome"], held["effectiveModeId"]) == ("degraded", "lexical")
        row = rf.job_row(flows, turn["jobId"])
        assert (row["state"], row["attempts"]) == ("accepted", 0)
        assert assistance_state(flows, job["id"]) == waiting
        assert len(model.requests) == before  # nothing reached the runtime

        # The next observation is the test call: its own requests are the only ones.
        probe_models(composition)
        probed = model.requests[before:]
        assert [request.url.path for request in probed] == ["/api/tags", "/api/embed"]
        assert json.loads(probed[1].content)["input"] == ""  # the probe's own re-pin
        assert composition.capability_states()["provider.models"]["state"] == "available"
        for _ in range(4):
            lane.turn()
        assert rf.job_row(flows, turn["jobId"])["state"] == "succeeded"
        assert assistance_state(flows, job["id"]) == "succeeded"

        # One semantic search costs exactly one state read: the same breakers, installed
        # again over a reader that counts each read.
        reads: list[int] = []

        def counted() -> dict:
            reads.append(1)
            return composition.capability_states()

        install_search_breaker(parts, counted)
        install_models_breaker(parts, counted)
        embedded = embeds(model)
        answer = composed_search(corpus)
        assert (answer["outcome"], answer["effectiveModeId"]) == ("complete", "semantic")
        assert (len(reads), embeds(model)) == (1, embedded + 1)


class OutwardStandIn:
    """One outward provider behind its adapter's own network builder: every request is
    kept; while `down` every answer is 503, otherwise 200."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.down = False

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            return httpx.Response(503)
        return httpx.Response(200, json={"id": str(uuid4())})

    def client(self, **options) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle), **options)

    def seen(self) -> list[tuple[str, str]]:
        return [(request.method, str(request.url)) for request in self.requests]


def probe_provider(composition, capability: str) -> dict:
    """One observation of `capability` through production's own probe and producer; the
    state it gives."""
    from backend.modules.operations.producers import ProducerSchedule, ProviderProducer
    from backend.u8_provider_probes import production_probe

    producer = ProviderProducer(capability, composition.ledger,
                                probe=production_probe(capability))
    observations = Observations(composition.parts["service-operations"]["observations"])
    schedule = ProducerSchedule([producer], observations, composition.policy,
                                composition.clock)
    assert schedule.run_due() == [capability]
    return composition.capability_states()[capability]


def test_while_google_or_resend_is_observed_unavailable_only_the_probe_reaches_it(
        realm, monkeypatch):
    """Reliability-design § 10 (lines 133-137, 141, 143), L4-11: in a composed production,
    while provider.google is observed unavailable a sign-in start through the served app
    gets the deadline answer and writes no flow, and while provider.resend is observed
    unavailable a prepared digest waits; each provider's stand-in records the probes'
    requests alone. Once the probes pass, the start is taken and the digest is sent."""
    from backend.modules.accounts.integrations import digest_email, identity_providers
    from backend.modules.topics.repository import TopicsRepository
    from backend.u8_provider_probes import PROBE_REQUESTS
    from tests.u8_service_operations_integration.host_flows import save_zone

    google, resend = OutwardStandIn(), OutwardStandIn()
    # For this test only: each adapter's one network builder answers in process.
    monkeypatch.setattr(identity_providers, "network_transport",
                        lambda: httpx.MockTransport(google.handle))
    monkeypatch.setattr(digest_email, "network_client", resend.client)
    google_probe = ("GET", PROBE_REQUESTS["provider.google"][0])
    resend_probe = ("GET", PROBE_REQUESTS["provider.resend"][0])
    with production_composition(realm) as env:
        composition = env.composition
        parts = composition.parts
        entry = parts["account-controls"]["entry"]
        activation = parts["service-operations"]["activation"]
        scheduler = parts["topics-digests"]["scheduler"]
        assert scheduler.gate is parts["topics-digests"]["gate"]
        app = host_app(composition)
        app.state.control_capacity.refresh()

        def start() -> tuple[int, str | None]:
            client = client_of(app)
            csrf = client.get("/api/v2/session").json()["csrfToken"]
            answer = client.post("/api/v2/c02/access-begin-identity-flow", json={
                "provider": "google", "intent": "sign_in", "returnRouteId": "account",
                "policyRef": entry.control_policy.reference,
            }, headers={"origin": PUBLIC, "x-csrf-token": csrf,
                        "idempotency-key": str(uuid4())})
            return answer.status_code, answer.json().get("code")

        def flows() -> int:
            with env.standin.connect("accounts") as conn:
                return conn.execute("SELECT count(*) AS n FROM accounts.identity_flow"
                                    ).fetchone()["n"]

        # The maintainer's digest, prepared and waiting to be sent; its window is built
        # from the real clock, the clock the composition's parts read.
        authority = maintainer_authority(env.standin)
        save_zone(env.standin, authority, "Asia/Seoul")
        repository = TopicsRepository(env.standin.transactions)
        topic = repository.follow(authority, "breaker-" + uuid4().hex[:12], "차단기")[
            "topic"]["id"]
        first = dt.datetime.now(dt.UTC).date() - dt.timedelta(days=7)
        run, _ = repository.prepare_run(
            topic, first, first + dt.timedelta(days=6), 1,
            [{"title": "합성 논문", "publishedOn": first.isoformat()}])

        def run_state() -> str:
            return repository.system(lambda conn: conn.execute(
                "SELECT state FROM topics.digest_run WHERE id=%s", (run["id"],)
            ).fetchone()["state"])

        google.down = resend.down = True
        for capability in ("provider.google", "provider.resend"):
            assert probe_provider(composition, capability) == {
                "state": "unavailable", "reason": "provider-unreachable"}
        google.down = resend.down = False  # both answer again; nothing observed yet
        assert [activation.state("google"), activation.state("resend")] == ["active"] * 2

        before = flows()
        assert start() == (504, "DEADLINE_EXCEEDED")  # the deadline answer
        assert flows() == before  # no record was written
        for _ in range(3):
            result = scheduler.run_once()
            assert result["sent"] == result["failed"] == result["unknown"] == 0
        assert run_state() == "prepared"
        # Each stand-in holds the probe's request alone.
        assert google.seen() == [google_probe] and resend.seen() == [resend_probe]

        for capability in ("provider.google", "provider.resend"):
            assert probe_provider(composition, capability)["state"] == "available"
        assert start()[0] == 200 and flows() == before + 1
        for _ in range(6):
            scheduler.run_once()
            if run_state() == "sent":
                break
        assert run_state() == "sent"
        assert google.seen() == [google_probe] * 2  # a start sends the provider nothing
        assert resend.seen() == [resend_probe] * 2 + [("POST", "https://api.resend.com/emails")]
