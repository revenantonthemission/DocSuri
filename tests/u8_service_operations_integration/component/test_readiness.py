"""Capability states and service readiness (U8 plan Step 16; BR3.1, BR3.2, BR5.9)."""

from __future__ import annotations

import datetime as dt
import secrets

import httpx
import pytest
from docsuri_shared.workspace import wire

from backend.modules.operations import producers as producer_module
from backend.modules.operations.observation_store import ObservationRow, ObservationStore
from backend.modules.operations.readiness import Readiness
from backend.u8_host import Activation, compose, host_app
from backend.u8_policy import SYNTHETIC_OPERATIONS
from backend.u8_registry import CAPABILITIES, CONTRIBUTIONS, MANIFEST, REQUIRED, timing

NOW = dt.datetime(2026, 10, 22, 6, 0, tzinfo=dt.UTC)
ALL_ACTIVE = {entry.contribution_id: Activation(entry.contribution_id, "active")
              for entry in CONTRIBUTIONS}


def row(outcome: str, *, age: float = 0, reason: str | None = None, limitations=(),
        errors: int = 0) -> dict:
    return {"outcome": outcome, "reason_key": reason, "limitation_keys": list(limitations),
            "observed_at": NOW - dt.timedelta(seconds=age), "error_count": errors,
            "total_count": max(errors, 1)}


def readiness(activations=None, providers=None, store=None, admission=None,
              held_sign_in_offered=True) -> Readiness:
    return Readiness(MANIFEST, activations or ALL_ACTIVE, providers or {}, store,
                     SYNTHETIC_OPERATIONS, lambda: NOW, admission=admission,
                     held_sign_in_offered=held_sign_in_offered)


def all_available() -> dict:
    return {cap.capability_id: row("available") for cap in CAPABILITIES}


def test_br3_2s_table_row_by_row():
    stale_after = timing(next(c for c in CAPABILITIES if c.capability_id == "export"),
                         SYNTHETIC_OPERATIONS)[1]
    activations = {**ALL_ACTIVE,
                   "approved-export": Activation("approved-export", "unavailable",
                                                 "incompatible")}
    latest = {
        "public.static": None,
        "library.saved-work": row("available"),
        "usage.wallet": row("available", age=stale_after + 1),
        "discovery.search": row("degraded", reason="semantic-search-unavailable",
                                limitations=("semantic-search-unavailable",)),
        "corpus.content": row("unavailable", reason="store-unavailable"),
        "research": row("unknown", reason="producer-failed"),
        "export": row("available"),
    }
    view = readiness(activations, {"provider.orcid": "unconfigured"})
    states = view.derive({k: v for k, v in latest.items() if v is not None}, NOW)
    assert states["public.static"].brief() == {"state": "available", "reason": None}
    assert states["export"].brief() == {"state": "unavailable", "reason": "incompatible"}
    assert states["provider.notion"].brief()["reason"] == "incompatible"
    assert states["provider.orcid"].brief() == {"state": "unavailable", "reason": "unconfigured"}
    assert states["novelty"].brief() == {"state": "unknown", "reason": "no-observation"}
    assert states["usage.wallet"].brief() == {"state": "stale", "reason": "observation-stale"}
    assert states["usage.wallet"].age_seconds == stale_after + 1
    assert states["library.saved-work"].brief() == {"state": "available", "reason": None}
    assert states["discovery.search"].state == "degraded"
    assert states["discovery.search"].limitations == ("semantic-search-unavailable",)
    assert states["corpus.content"].brief() == {"state": "unavailable",
                                               "reason": "store-unavailable"}
    assert states["research"].brief() == {"state": "unknown", "reason": "producer-failed"}
    # Exactly at the bound it is still fresh.
    edge = view.derive({"usage.wallet": row("available", age=stale_after)}, NOW)
    assert edge["usage.wallet"].state == "available"


def test_platform_status_is_fresh_for_15_minutes_and_stale_after():
    """NFR9.2 (2): under the production policy platform.status is fresh for 900 s."""
    from backend.u8_policy import PRODUCTION_OPERATIONS

    view = Readiness(MANIFEST, ALL_ACTIVE, {}, None, PRODUCTION_OPERATIONS, lambda: NOW)
    fresh = view.derive({"platform.status": row("available", age=900)}, NOW)
    assert fresh["platform.status"].brief() == {"state": "available", "reason": None}
    old = view.derive({"platform.status": row("available", age=901)}, NOW)
    assert old["platform.status"].brief() == {"state": "stale", "reason": "observation-stale"}
    assert old["platform.status"].age_seconds == 901


@pytest.mark.parametrize("state", ["unknown", "stale", "unavailable"])
def test_unknown_stale_and_unavailable_never_count_as_available(state):
    latest = all_available()
    if state == "unknown":
        del latest["topics.digest"]
    elif state == "stale":
        latest["topics.digest"] = row("available", age=10_000)
    else:
        latest["topics.digest"] = row("unavailable", reason="store-unavailable")
    view = readiness()
    report = view.report(view.derive(latest, NOW))
    assert report["ready"] is False and report["missing"] == ["topics.digest"]


def test_a_degraded_required_capability_is_named_and_the_service_stays_ready():
    latest = all_available()
    latest["export"] = row("degraded", reason="export-effect-late",
                           limitations=("export-effect-late",))
    view = readiness()
    report = view.report(view.derive(latest, NOW))
    assert report["ready"] is True and report["degraded"] == ["export"]
    assert report["missing"] == []
    # A provider or platform outage never makes the service unready (BR3.11).
    latest["provider.models"] = row("unavailable", reason="model-evidence-mismatch")
    latest["platform.isolation"] = row("unavailable", reason="runtime-isolation-lapsed")
    assert view.report(view.derive(latest, NOW))["ready"] is True
    # A closed storage admission keeps it unready.
    closed = readiness(admission=lambda: False)
    report = closed.report(closed.derive(all_available(), NOW))
    assert report["ready"] is False and report["admission"] == "closed"


def test_an_unreadable_store_leaves_every_observed_capability_unknown():
    class Down:
        def latest(self, names):
            raise ConnectionError("down")

    states = readiness(store=Down()).states()
    assert states["export"].brief() == {"state": "unknown", "reason": "store-unavailable"}
    assert states["public.static"].state == "available"
    assert all(states[name].state == "unknown" for name in REQUIRED)


async def test_health_ready_reads_once_and_makes_no_producer_call(realm, monkeypatch):
    composition = compose(realm)
    calls = {"latest": 0, "observe": 0}
    original = ObservationStore.latest

    def counted(self, names):
        calls["latest"] += 1
        return original(self, names)

    def refused(self, now):
        calls["observe"] += 1
        raise AssertionError("a producer was asked during /health/ready")

    monkeypatch.setattr(ObservationStore, "latest", counted)
    for value in vars(producer_module).values():
        if isinstance(value, type) and issubclass(value, producer_module.Producer):
            monkeypatch.setattr(value, "observe", refused)
    try:
        app = host_app(composition)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://127.0.0.1:18109") as client:
            ready = await client.get("/health/ready")
            live = await client.get("/health/live")
        assert ready.status_code in (200, 503) and "missing" in ready.json()
        assert live.status_code == 200
        assert calls == {"latest": 1, "observe": 0}
    finally:
        composition.close()


def test_the_public_projection_holds_state_and_reason_alone():
    latest = all_available()
    latest["discovery.search"] = row("degraded", reason="semantic-search-unavailable",
                                     limitations=("semantic-search-unavailable",), errors=2)
    view = readiness()
    page = view.public_projection(view.derive(latest, NOW))
    wire.HostPublicCapabilityPage.model_validate(page)
    names = [item["capabilityId"] for item in page["items"]]
    assert names == ["discovery.search", "corpus.content", "public.static", "account.entry",
                     "provider.google", "provider.orcid", "provider.resend"]
    resend = page["items"][-1]
    assert resend == {"capabilityId": "provider.resend", "state": "available",
                      "reasonKey": "available"}
    for item in page["items"]:
        assert set(item) == {"capabilityId", "state", "reasonKey"}
    search = page["items"][0]
    assert search == {"capabilityId": "discovery.search", "state": "degraded",
                      "reasonKey": "semantic-search-unavailable"}
    text = str(page)
    for hidden in ("ageSeconds", "limitation", "evidence", "error", "Count", "producer",
                   "library", "operations"):
        assert hidden not in text
    assert page["manifestRevision"] == MANIFEST.revision


MAIL_HIDDEN = ("allowance-exhausted", "first-effect-pending", "unconfigured",
               "observation-stale", "no-observation", "store-unavailable", "degraded",
               "stale", "unknown")


def mail_item(view: Readiness, states: dict) -> dict:
    page = view.public_projection(states)
    wire.HostPublicCapabilityPage.model_validate(page)
    (item,) = [item for item in page["items"] if item["capabilityId"] == "provider.resend"]
    # Nothing of the internal state or reason reaches the caller, anywhere in the answer.
    text = repr([value for value in page["items"] if value["capabilityId"] == "provider.resend"])
    for hidden in MAIL_HIDDEN:
        assert hidden not in text
    return item


@pytest.mark.parametrize(("planted", "internal", "public"), [
    # The daily limit stays hidden, although at the account and monthly limits every
    # account's mail is refused: its change of state would tell an account from an
    # unknown address, and the up-front refusal tells the caller instead.
    (row("degraded", reason="allowance-exhausted", limitations=("allowance-exhausted",)),
     ("degraded", "allowance-exhausted"), ("available", "available")),
    # The first-send hold: every account's mail is refused.
    (row("degraded", reason="first-effect-pending", limitations=("first-effect-pending",)),
     ("degraded", "first-effect-pending"), ("unavailable", "provider-unreachable")),
    # An observed outage.
    (row("unavailable", reason="provider-unreachable"),
     ("unavailable", "provider-unreachable"), ("unavailable", "provider-unreachable")),
    # No observation yet: no outage is shown.
    (None, ("unknown", "no-observation"), ("available", "available")),
    # Stale: no outage is shown.
    ("stale", ("stale", "observation-stale"), ("available", "available")),
    (row("available"), ("available", None), ("available", "available")),
])
def test_signed_out_the_mail_provider_reads_only_serving_or_not(planted, internal, public):
    """The person's answer of 2026-11-13, "Working or not, no reasons": decided server-side
    from the internal state and reason; no limit or hold reason reaches the caller."""
    latest = all_available()
    freshness = timing(next(c for c in CAPABILITIES if c.capability_id == "provider.resend"),
                       SYNTHETIC_OPERATIONS)[1]
    if planted is None:
        del latest["provider.resend"]
    elif planted == "stale":
        latest["provider.resend"] = row("available", age=freshness + 1)
    else:
        latest["provider.resend"] = planted
    view = readiness()
    states = view.derive(latest, NOW)
    assert (states["provider.resend"].state, states["provider.resend"].reason) == internal
    item = mail_item(view, states)
    assert (item["state"], item["reasonKey"]) == public
    assert set(item) == {"capabilityId", "state", "reasonKey"}


def test_signed_out_mail_not_configured_reads_not_serving():
    view = readiness(providers={"provider.resend": "unconfigured"})
    states = view.derive(all_available(), NOW)
    assert states["provider.resend"].brief() == {"state": "unavailable", "reason": "unconfigured"}
    item = mail_item(view, states)
    assert (item["state"], item["reasonKey"]) == ("unavailable", "provider-unreachable")


def test_signed_out_mail_reads_not_serving_while_its_contribution_is_unavailable():
    owner = readiness().contribution_of["provider.resend"].contribution_id
    view = readiness({**ALL_ACTIVE, owner: Activation(owner, "unavailable", "incompatible")})
    states = view.derive(all_available(), NOW)
    assert states["provider.resend"].brief() == {"state": "unavailable", "reason": "incompatible"}
    item = mail_item(view, states)
    assert (item["state"], item["reasonKey"]) == ("unavailable", "provider-unreachable")


def test_signed_out_only_the_mail_provider_loses_its_reason():
    latest = all_available()
    latest["provider.google"] = row("degraded", reason="sign-in-unverified",
                                    limitations=("sign-in-unverified",))
    latest["provider.resend"] = row("degraded", reason="allowance-exhausted",
                                    limitations=("allowance-exhausted",))
    view = readiness()
    page = view.public_projection(view.derive(latest, NOW))
    by_name = {item["capabilityId"]: item for item in page["items"]}
    assert by_name["provider.google"] == {"capabilityId": "provider.google",
                                          "state": "degraded", "reasonKey": "sign-in-unverified"}
    assert by_name["provider.resend"] == {"capabilityId": "provider.resend",
                                          "state": "available", "reasonKey": "available"}
    assert "allowance-exhausted" not in repr(page)


def test_a_held_sign_in_provider_reads_as_not_serving_signed_out_once_admission_opens(realm):
    """U8 plan Step 107(e), BR7.8: once admission opens a held sign-in provider is refused
    at the start for everyone, so signed out it reads as not serving, with the generic
    reason; in the window and in every synthetic profile it reads as built."""
    from types import SimpleNamespace

    from backend.modules.operations.readiness import offers_held_sign_in

    latest = all_available()
    latest["provider.google"] = row("degraded", reason="sign-in-unverified",
                                    limitations=("sign-in-unverified",))

    def items(view, planted) -> dict:
        page = view.public_projection(view.derive(planted, NOW))
        wire.HostPublicCapabilityPage.model_validate(page)
        return {item["capabilityId"]: (item["state"], item["reasonKey"])
                for item in page["items"]}

    opened, window = readiness(held_sign_in_offered=False), readiness()
    closed = items(opened, latest)
    assert closed["provider.google"] == ("unavailable", "provider-unreachable")
    assert closed["provider.orcid"] == ("available", "available")
    assert "sign-in-unverified" not in repr(closed)
    assert items(window, latest)["provider.google"] == ("degraded", "sign-in-unverified")
    down = {**latest, "provider.google": row("unavailable", reason="provider-unreachable")}
    for view in (opened, window):
        assert items(view, down)["provider.google"] == ("unavailable", "provider-unreachable")
        assert items(view, latest)["provider.resend"] == ("available", "available")
    # The truthful state stays for /health/ready and 운영.
    assert opened.derive(latest, NOW)["provider.google"].brief() == {
        "state": "degraded", "reason": "sign-in-unverified"}
    assert not offers_held_sign_in(SimpleNamespace(is_production=True, mode="live",
                                                   admission="open"))
    for profile in (SimpleNamespace(is_production=True, mode="live", admission="maintainer-only"),
                    SimpleNamespace(is_production=True, mode="rehearsal", admission="open"),
                    SimpleNamespace(is_production=False)):
        assert offers_held_sign_in(profile)
    composition = compose(realm)
    try:
        assert composition.readiness_view().held_sign_in_offered is True
    finally:
        composition.close()


def test_live_answers_from_memory():
    assert Readiness.live() == {"process": "alive"}


def test_the_release_defaults_to_null():
    """BR6.5 (Step 80(d)): the running release's tag and commit alone, never its kind or
    its path."""
    plain = readiness()
    report = plain.report(plain.derive(all_available(), NOW))
    assert report["release"] == {"tag": None, "commit": None}
    # While admission is open, the report holds exactly these keys.
    assert report["ready"] is True
    assert set(report) == {"ready", "missing", "degraded", "manifestRevision",
                           "contributions", "release"}
    released = Readiness(
        MANIFEST, ALL_ACTIVE, {}, None, SYNTHETIC_OPERATIONS, lambda: NOW,
        release={"tag": "v2.0.0", "commit": "c" * 40, "kind": "release",
                 "path": "/Library/DocSuri/releases/v2.0.0"},
    )
    shown = released.report(released.derive(all_available(), NOW))
    assert shown["release"] == {"tag": "v2.0.0", "commit": "c" * 40}
    assert "/Library/DocSuri/releases" not in repr(shown)


# A renewal written while the fixture clock is held carries the same `observed_at` as the
# row before it (decision 9222ed3d, "Renew on real time too"); `latest` breaks the tie by
# revision. Each test names its own capabilities, so rows other tests leave in the
# persistent realm never change its result; readiness derives from the row read back.
def stored(capability: str, at: dt.datetime, outcome: str, revision: int) -> ObservationRow:
    return ObservationRow(
        capability=capability, producer="test.producer", outcome=outcome,
        reason_key=None if outcome == "available" else "store-unavailable",
        observed_at=at, revision=revision, error_count=0, total_count=1,
    )


def test_a_same_instant_renewal_is_the_latest_row_and_readiness_reads_it(
        transactions, clock):
    store = ObservationStore(transactions)
    token = secrets.token_hex(4)
    first, second = f"test-{token}-renewed", f"test-{token}-reversed"
    at = clock()
    # An older row first, then a renewal at the same held instant with a higher revision
    # (as a process writes them, and after a restart too, since Observations seeds from
    # the stored revision) ...
    store.insert([stored(first, at, "available", 7)])
    store.insert([stored(first, at, "unavailable", 8)])
    # ... and the opposite insertion order, so the answer is not the heap's order.
    store.insert([stored(second, at, "unavailable", 8)])
    store.insert([stored(second, at, "available", 7)])
    latest = store.latest([first, second])
    for name in (first, second):
        assert latest[name]["revision"] == 8 and latest[name]["outcome"] == "unavailable"
    view = Readiness(MANIFEST, ALL_ACTIVE, {}, None, SYNTHETIC_OPERATIONS, lambda: at)
    state = view.derive({"export": latest[first]}, at)["export"]
    assert state.brief() == {"state": "unavailable", "reason": "store-unavailable"}
    assert state.age_seconds == 0


def test_a_later_observation_stays_the_latest_whatever_its_revision(transactions, clock):
    store = ObservationStore(transactions)
    name = f"test-{secrets.token_hex(4)}-ordered"
    at = clock()
    store.insert([stored(name, at, "unavailable", 9),
                  stored(name, at + dt.timedelta(seconds=1), "available", 3),
                  stored(name, at - dt.timedelta(seconds=1), "unavailable", 12)])
    latest = store.latest([name])[name]
    assert latest["revision"] == 3 and latest["outcome"] == "available"
    assert latest["observed_at"] == at + dt.timedelta(seconds=1)
    view = Readiness(MANIFEST, ALL_ACTIVE, {}, None, SYNTHETIC_OPERATIONS,
                     lambda: at + dt.timedelta(seconds=1))
    state = view.derive({"export": latest}, at + dt.timedelta(seconds=1))["export"]
    assert state.brief() == {"state": "available", "reason": None}
