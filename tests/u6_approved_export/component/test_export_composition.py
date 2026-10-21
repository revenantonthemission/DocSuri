"""The export contribution (logical-components §7): the capability row derived from the
bound transport, the raise when policy and transport disagree, one policy and one clock
for every part, and a synthetic composition that never builds the network transport."""

import asyncio
import datetime as dt
import logging

import httpx
import pytest
from backend.local_host import NAVIGATION, SYNTHETIC_CAPABILITIES, navigation_items
from backend.local_observation import PROBES, observe_all
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.export import notion_session
from backend.modules.export.fake_notion import FakeNotion
from backend.modules.export.lane import ExportLane
from backend.modules.export.notion_session import CandidateToken
from backend.modules.export.worker import ExportWorker
from backend.u3_host import catalog_revision
from backend.u6_host import (
    TRANSPORT_LOGGERS,
    bound_transport,
    export_capability,
    export_contribution,
)
from backend.u6_policy import SYNTHETIC_EXPORT, real_activation_export
from docsuri_shared.workspace import wire

from tests.u6_approved_export import service_flows as sf
from tests.u6_approved_export import store_flows as flows

REAL = real_activation_export(
    activation_destination_id="0123456789abcdef0123456789abcdef",
    free_terms_reference="notion-free:2026-10-01:" + "b" * 64,
)


class Inherited:
    def __init__(self):
        self.calls = 0

    def run_once(self, limit=1):
        self.calls += 1
        return {"limit": limit}


def contribution(transactions, *, fake=None, **options):
    fake = fake or FakeNotion()
    return export_contribution(
        transactions,
        GuardedEntryService(transactions),
        None,
        Inherited(),
        research=sf.ResearchDouble(),
        transport_factory=lambda: fake,
        **options,
    )


def test_the_capability_row_follows_the_bound_transport():
    synthetic = export_capability(SYNTHETIC_EXPORT, "synthetic")
    real = export_capability(REAL, "real")

    assert synthetic == {
        "id": "export",
        "state": "degraded",
        "modeIds": ["synthetic-only"],
        "languageIds": ["ko"],
        "levelIds": [],
        "formatIds": ["notion"],
        "policy": SYNTHETIC_EXPORT.reference(),
    }
    assert real["modeIds"] == ["real-bounded"] and real["policy"] == REAL.reference()
    for policy, kind in ((SYNTHETIC_EXPORT, "real"), (REAL, "synthetic")):
        with pytest.raises(ValueError, match="disagree"):
            export_capability(policy, kind)
    with pytest.raises(ValueError, match="unknown"):
        export_capability(SYNTHETIC_EXPORT, "network")


def test_the_export_row_validates_in_the_frozen_catalog():
    catalog = [export_capability(SYNTHETIC_EXPORT, "synthetic")]

    value = wire.CapabilityCatalog.model_validate(
        {"revision": catalog_revision(catalog), "capabilities": catalog}
    ).model_dump(mode="json", exclude_none=True)

    assert value["capabilities"][0]["levelIds"] == []
    without_levels = {key: item for key, item in catalog[0].items() if key != "levelIds"}
    with pytest.raises(ValueError):
        wire.CapabilityCatalog.model_validate({"revision": "r", "capabilities": [without_levels]})


def test_a_synthetic_policy_binds_only_the_fake_notion():
    fake = FakeNotion()

    factory, path = bound_transport(SYNTHETIC_EXPORT, lambda: fake)

    assert path == "synthetic" and factory() is fake
    with pytest.raises(ValueError, match="disagree"):
        bound_transport(SYNTHETIC_EXPORT, None)
    with pytest.raises(ValueError, match="disagree"):
        bound_transport(SYNTHETIC_EXPORT, lambda: httpx.MockTransport(lambda request: None))
    answers = iter([fake, httpx.MockTransport(lambda request: None)])
    checked, _ = bound_transport(SYNTHETIC_EXPORT, lambda: next(answers))
    with pytest.raises(RuntimeError, match="fake Notion"):
        checked()
    assert bound_transport(REAL, None) == (None, "real")


def test_the_contribution_shares_one_policy_and_one_clock(transactions):
    clock = sf.Clock(dt.datetime(2026, 10, 1, tzinfo=dt.UTC))
    policy = SYNTHETIC_EXPORT

    built = contribution(transactions, policy=policy, clock=clock)

    service, lane, worker = built["service"], built["lane"], built["worker"]
    assert built["capabilities"] == [export_capability(policy, "synthetic")]
    assert service.policy is policy and service.repository.policy is policy
    assert service.adapter.policy is policy and service.clock is clock
    assert isinstance(lane, ExportLane) and lane.running is False
    assert isinstance(worker, ExportWorker) and worker.export_pass is built["export_pass"]
    assert service.vault._keys.root == transactions.profile.root / "export-keys"
    paths = {route.path for route in built["router"].routes}
    assert "/api/v2/c09/list-export-history" in paths and len(paths) == 11
    assert worker.run_once(limit=1) == {"limit": 1} and worker.inherited.calls == 1


def test_a_synthetic_composition_never_builds_the_network_transport(
    transactions, connect, authority, monkeypatch
):
    built_network = []

    def refuse():
        built_network.append(True)
        raise RuntimeError("the network transport was built")

    monkeypatch.setattr(notion_session, "network_transport", refuse)
    fake = FakeNotion()
    built = contribution(transactions, fake=fake)
    flows.fresh(connect, authority.account_id)
    slot = built["repository"].reserve_connection(authority, None, now=dt.datetime.now(dt.UTC))
    try:
        identified = asyncio.run(
            built["service"].adapter.identify(CandidateToken(slot.connection_id, "unknown"))
        )
    finally:
        built["repository"].release_pending(authority, slot.holder)

    assert identified.category == "token-invalid"
    assert built_network == []
    assert [entry.path for entry in fake.requests] == ["/v1/users/me"]


def test_the_contribution_keeps_the_transport_loggers_quiet(transactions):
    loggers = [logging.getLogger(name) for name in TRANSPORT_LOGGERS]
    levels = [logger.level for logger in loggers]
    try:
        for logger in loggers:
            logger.setLevel(logging.DEBUG)
        contribution(transactions)
        assert [logger.level for logger in loggers] == [logging.WARNING] * len(loggers)
        for logger in loggers:
            logger.setLevel(logging.ERROR)
        contribution(transactions)
        assert [logger.level for logger in loggers] == [logging.ERROR] * len(loggers)
    finally:
        for logger, level in zip(loggers, levels, strict=True):
            logger.setLevel(level)


def test_the_shell_names_the_export_route_and_probe(transactions):
    catalog = [export_capability(SYNTHETIC_EXPORT, "synthetic")]
    entry = next(item for item in NAVIGATION if item["routeId"] == "export")

    owner = {item["routeId"]: item for item in navigation_items(catalog, authenticated=True)}
    elsewhere = {item["routeId"] for item in navigation_items([], authenticated=True)}
    observed = observe_all(transactions, {"export"})["export"]

    assert entry == {
        "routeId": "export",
        "titleKey": "nav.export",
        "path": "/export",
        "capabilityId": "export",
        "ownerBound": True,
    }
    assert "export" in SYNTHETIC_CAPABILITIES
    assert owner["export"]["available"] is True and "export" not in elsewhere
    assert observed["disposition"] == "available"
    assert set(observed["evidence"]) == {"previews", "approvals", "effects", "guard_functions"}
    assert observed["evidence"]["guard_functions"] == 1
    assert all(type(value) is int for value in observed["evidence"].values())
    # The default observed set leaves out the unit-owned probes.
    assert "export" in PROBES and "export" not in observe_all(transactions, None)
