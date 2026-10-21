"""U6 contribution to the shared application; no separate export service.

The ApprovedExport module joins the one assembled release (logical-components §7): its
service, its C09 routes, its worker step on the existing worker entry, its export lane
in the shared lifespan and its `export` capability row. Every part is built from ONE
`ExportPolicy` and ONE clock, so every due-time decision compares against the same
`now` (decision "One clock").

The capability row is derived from the bound transport, as U5's digest row is: the
synthetic realm's fake Notion reports `synthetic-only`; the operator-composed real path
(`backend/u6_real_export.py`) reports `real-bounded`. Both stay `degraded`, because
neither is general export. A synthetic policy composes only the fake Notion: it never
reaches `notion_session.network_transport()` (NFR6.3).
"""

import datetime as dt
import json
import logging
from collections.abc import Callable
from functools import partial

from backend.u5_host import assemble_u5
from backend.u6_policy import SYNTHETIC_EXPORT, ExportPolicy

EXPORT_MODES = {"synthetic": "synthetic-only", "real": "real-bounded"}
KEY_FOLDER = "export-keys"
SCENARIO_FILE = "fake-notion.json"
CLOCK_FILE = "export-fixture-clock.json"
ACTIVATION_FILE = "real-export.json"
# The transport libraries log request lines with headers at DEBUG and INFO (security
# design §5.4); they are kept at WARNING or above in every composition.
TRANSPORT_LOGGERS = ("httpx", "httpcore")
# The delegated browser clock may run at most this far from the real one.
CLOCK_BEHIND = dt.timedelta(hours=1)
CLOCK_AHEAD = dt.timedelta(days=2)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def export_capability(policy: ExportPolicy, path_kind: str) -> dict:
    """The truthful `export` row for the transport actually bound."""
    if path_kind not in EXPORT_MODES:
        raise ValueError("unknown export transport kind")
    if (path_kind == "real") == policy.synthetic_only:
        raise ValueError("export capability policy and transport disagree")
    return {
        "id": "export",
        "state": "degraded",
        "modeIds": [EXPORT_MODES[path_kind]],
        "languageIds": ["ko"],
        # The frozen catalog requires the field; export has no presentation levels.
        "levelIds": [],
        "formatIds": ["notion"],
        "policy": policy.reference(),
    }


def _fake_only(transport_factory: Callable) -> Callable:
    """A synthetic composition's factory: every transport it hands out is the fake."""
    from backend.modules.export.fake_notion import FakeNotion

    def factory():
        transport = transport_factory()
        if not isinstance(transport, FakeNotion):
            raise RuntimeError("a synthetic export composes only the fake Notion")
        return transport

    return factory


def bound_transport(policy: ExportPolicy, transport_factory: Callable | None):
    """The session's transport factory and the path it stands for.

    - A synthetic policy needs a factory that hands out the fake Notion; anything else,
      including no factory (the network), disagrees and raises.
    - A real policy uses the network transport (no factory), or the test-only seam,
      which stands in for the network under the real policy and its limits.
    """
    from backend.modules.export.fake_notion import FakeNotion

    if not policy.synthetic_only:
        export_capability(policy, "real")
        return transport_factory, "real"
    path = "real"
    if transport_factory is not None and isinstance(transport_factory(), FakeNotion):
        path = "synthetic"
    export_capability(policy, path)
    return _fake_only(transport_factory), path


def quiet_transport_loggers() -> None:
    for name in TRANSPORT_LOGGERS:
        logger = logging.getLogger(name)
        if logger.level < logging.WARNING:
            logger.setLevel(logging.WARNING)


def export_contribution(
    transactions,
    entry,
    corpus,
    inherited_worker,
    *,
    research,
    policy: ExportPolicy | None = None,
    transport_factory: Callable | None = None,
    clock: Callable[[], dt.datetime] | None = None,
):
    """The service, routes, worker step, lane and capability row of ApprovedExport.

    `entry` is the shared guarded entry; `corpus` is accepted for the factory signature
    every contribution shares and is not used: U6 reads results only through U4's
    `readNoveltyArtifactForExport` on `research`.
    """
    from backend.modules.export.http import export_router
    from backend.modules.export.lane import ExportLane
    from backend.modules.export.notion_adapter import NotionAdapter, StoreContentPort
    from backend.modules.export.notion_session import NotionSession
    from backend.modules.export.repository import ExportRepository
    from backend.modules.export.service import ExportService
    from backend.modules.export.token_keyring import TokenKeyring
    from backend.modules.export.token_vault import TokenVault
    from backend.modules.export.worker import ExportPass, ExportWorker

    del corpus
    policy = policy or SYNTHETIC_EXPORT
    if not isinstance(policy, ExportPolicy):
        raise TypeError("an ExportPolicy is required")
    clock = clock or _utc_now
    factory, path = bound_transport(policy, transport_factory)
    quiet_transport_loggers()
    profile = transactions.profile
    repository = ExportRepository(transactions, policy)
    keyring = TokenKeyring(profile.root / KEY_FOLDER, profile.run_id, repository, policy=policy)
    vault = TokenVault(keyring)
    session = NotionSession(store=repository, vault=vault, policy=policy, transport_factory=factory)
    adapter = NotionAdapter(session, repository, content=StoreContentPort(repository), clock=clock)
    service = ExportService(transactions, repository, adapter, vault, research, policy, clock)
    lane = ExportLane(repository, adapter, service.binding, policy=policy, clock=clock)
    export_pass = ExportPass(repository, research, lane, policy=policy, clock=clock)
    return {
        "service": service,
        "repository": repository,
        "lane": lane,
        "export_pass": export_pass,
        "worker": ExportWorker(inherited_worker, export_pass),
        "router": export_router(transactions, entry=entry, service=service),
        "capabilities": [export_capability(policy, path)],
    }


def fixture_clock(profile) -> Callable[[], dt.datetime]:
    """The delegated, run-bound synthetic clock (`export-fixture-clock.json`), like U5's
    digest clock: absent, it is the real time; present, it must name this run and an
    aware instant within an hour behind and two days ahead of the real time."""
    from backend.local_profile import private_bytes

    def clock() -> dt.datetime:
        path = profile.root / CLOCK_FILE
        now = _utc_now()
        if not path.exists():
            return now
        value = json.loads(private_bytes(path))
        instant = dt.datetime.fromisoformat(value["instant"])
        if (
            value.get("runId") != profile.run_id
            or instant.tzinfo is None
            or not now - CLOCK_BEHIND <= instant <= now + CLOCK_AHEAD
        ):
            raise ValueError("synthetic export clock binding differs")
        return instant

    return clock


def synthetic_notion(profile, clock):
    """The fake Notion of this run: its scenario file when the fixtures wrote one, or an
    empty fake that knows no token (every connect then answers INVALID_TOKEN)."""
    from backend.modules.export.fake_notion import FakeNotion

    path = profile.root / SCENARIO_FILE
    if not path.exists():
        return FakeNotion(clock=clock)
    return FakeNotion.load(path, run_id=profile.run_id, clock=clock)


def assemble_u6(profile):
    """The synthetic U6 host: `assemble_u5` with the export contribution over the fake.

    It refuses an environment that holds the operator's `real-export.json`, whose real
    sealed token the synthetic composition must never open (cicd-pipeline §4.3).
    """
    if (profile.root / ACTIVATION_FILE).exists() or (profile.root / ACTIVATION_FILE).is_symlink():
        raise ValueError("a synthetic export refuses an environment with real-export settings")
    clock = fixture_clock(profile)
    fake = synthetic_notion(profile, clock)
    factory = partial(export_contribution, transport_factory=lambda: fake, clock=clock)
    return assemble_u5(profile, export_factory=factory)
