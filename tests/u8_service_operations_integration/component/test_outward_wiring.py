"""The production outward wiring's small decisions (U8 plan Step 21; BR6.7, BR7.2, BR7.3).

- `digest_mail` gives TopicsDigests the held adapter while Resend is unavailable or its
  key or sender is missing, and the Resend adapter behind the gate otherwise; building
  the adapter sends nothing.
- `maintainer_address` refuses a profile that names no maintainer account.
- `first_export_previews` composes its pass only for a production composition holding
  both ApprovedExport and ServiceOperations; the pass refuses an unbounded batch and
  records nothing for an item that is not the maintainer's execute.
"""

from __future__ import annotations

import datetime as dt
from secrets import token_hex
from types import SimpleNamespace

import pytest

from backend.modules.accounts.integrations.u8_digest_mail import (
    GatedResendDigestMail,
    HeldDigestMail,
)
from backend.u8_host import PROVIDER_SECRETS, PolicyUnresolved
from backend.u8_outward import (
    DIGEST_SENDER,
    FirstExportPreviews,
    digest_mail,
    first_export_previews,
    maintainer_address,
)
from tests.u6_approved_export import store_flows
from tests.u8_service_operations_integration.host_flows import (
    production_stand_in,
    standin_account,
)

ORIGIN = "https://docsuri.example.org"
MAINTAINER = "maintainer@fixture.example.com"
KEY = PROVIDER_SECRETS["provider.resend"]
# A Resend key in its shape, generated per run (L1-36).
RESEND_KEY = "re_" + token_hex(10)


class Gate:
    def __init__(self, state: str = "active", mode: str = "live", maintainer=()):
        self._state, self.mode, self.maintainer = state, mode, set(maintainer)
        self.previews = []

    def state(self, provider: str) -> str:
        return self._state

    def is_maintainer_account(self, account) -> bool:
        return account in self.maintainer

    def record_preview(self, provider, payload):
        self.previews.append((provider, payload))
        return {"provider": provider}


def build(environment, gate):
    return digest_mail(environment, origin=ORIGIN, maintainer=MAINTAINER, activation=gate,
                       account_of=lambda email: None)


@pytest.mark.parametrize("environment,state", [
    ({KEY: RESEND_KEY, DIGEST_SENDER: "digest@fixture.example.com"}, "unavailable"),
    ({DIGEST_SENDER: "digest@fixture.example.com"}, "active"),
    ({KEY: RESEND_KEY}, "active"),
    ({KEY: "", DIGEST_SENDER: ""}, "held"),
])
def test_resend_is_held_while_unavailable_or_unconfigured(environment, state):
    assert isinstance(build(environment, Gate(state)), HeldDigestMail)


def test_a_configured_resend_is_the_real_adapter_behind_the_gate():
    gate = Gate("active")
    mail = build({KEY: RESEND_KEY, DIGEST_SENDER: "digest@fixture.example.com"}, gate)
    assert isinstance(mail, GatedResendDigestMail) and mail.path_kind == "real"
    assert mail.gate is gate


def test_a_profile_naming_no_maintainer_account_has_no_maintainer_address():
    with pytest.raises(PolicyUnresolved):
        maintainer_address(transactions=None, profile=SimpleNamespace())


@pytest.mark.parametrize("composition", [
    SimpleNamespace(profile=SimpleNamespace(is_production=False), parts={}),
    SimpleNamespace(profile=SimpleNamespace(is_production=True),
                    parts={"service-operations": {}}),
    SimpleNamespace(profile=SimpleNamespace(is_production=True),
                    parts={"approved-export": {}}),
])
def test_the_preview_pass_needs_a_production_export_and_operations(composition):
    assert first_export_previews(composition) is None


def test_production_topics_needs_the_provider_gate_composed():
    from backend.u8_outward import production_topics

    for parts in ({}, {"service-operations": {}}, {"account-controls": {}}):
        with pytest.raises(PolicyUnresolved):
            production_topics(SimpleNamespace(parts=parts))


def test_production_export_refuses_while_its_settings_are_absent(tmp_path):
    from backend.u8_outward import production_export

    profile = SimpleNamespace(root=tmp_path, is_production=True, mode="rehearsal",
                              run_id="production")
    gate = {"service-operations": {"activation": Gate(), "allowance": object()}}
    with pytest.raises(PolicyUnresolved, match="export settings"):
        production_export(SimpleNamespace(profile=profile, parts=gate))


@pytest.mark.parametrize("parts", [
    {},
    {"service-operations": {}},
    {"service-operations": {"activation": Gate()}},
    {"service-operations": {"allowance": object()}},
])
@pytest.mark.parametrize("mode", ["live", "rehearsal"])
def test_every_outward_production_builder_needs_the_provider_gate(tmp_path, parts, mode):
    from backend.u8_outward import production_export, production_gate, production_topics

    profile = SimpleNamespace(root=tmp_path, is_production=True, mode=mode, run_id="x")
    ctx = SimpleNamespace(profile=profile, parts={**parts, "account-controls": {}})
    for builder in (production_gate, production_topics, production_export):
        with pytest.raises(PolicyUnresolved, match="provider gate"):
            builder(ctx)


def test_the_production_export_builder_refuses_a_synthetic_profile(tmp_path):
    from backend.u8_outward import production_export

    with pytest.raises(PolicyUnresolved, match="synthetic"):
        production_export(SimpleNamespace(profile=SimpleNamespace(is_production=False),
                                          parts={}))


def test_only_production_live_export_builds_the_live_policy():
    from backend.u6_policy import ExportPolicy, production_live_export

    with pytest.raises(ValueError, match="only by production_live_export"):
        ExportPolicy(policy_id="x", production_live=True,
                     free_terms_reference="notion-free:" + "f" * 16)
    with pytest.raises(ValueError, match="only by production_live_export"):
        ExportPolicy(live_authority=object())
    live = production_live_export(free_terms_reference="notion-free:" + "f" * 16)
    assert live.production_live and not live.synthetic_only
    # A copy keeps its authority; a synthetic policy holds none.
    import dataclasses

    assert dataclasses.replace(live, revision="2").production_live
    with pytest.raises(ValueError, match="only by production_live_export"):
        dataclasses.replace(ExportPolicy(), production_live=True,
                            free_terms_reference="notion-free:" + "f" * 16)


def test_a_synthetic_profile_composes_no_production_export_policy():
    from backend.u8_outward import export_policy

    with pytest.raises(PolicyUnresolved):
        export_policy(SimpleNamespace(is_production=False), None)


class Due:
    """A store the pass must never ask: an unbounded batch is refused before any call
    (your answer of 2026-11-11, "Rewrite, keep two": `Due([])` stays a stub)."""

    def due_items(self, now, *, limit):
        raise AssertionError("an unbounded preview batch reached the store")


@pytest.fixture(scope="module")
def export_store(realm):
    """The export preview's due items from a real store: U6's `ExportRepository` on a
    production stand-in of its own, so the real `due_items` query answers only this
    module's rows. Through U6's own store units, it holds another account's accepted
    export, and the maintainer's export left unknown (a scan, not an execute) beside the
    maintainer's later accepted one. Yields the store, the maintainer, the three effects
    and the moment the scan is due."""
    with production_stand_in(realm) as standin:
        repository = store_flows.repository(standin.transactions)
        now = dt.datetime.now(dt.UTC)
        someone = standin_account(standin, "someone", grant=False)
        maintainer = standin_account(standin, "maintainer", grant=False)
        effects = {}
        # U6 binds one export at a time per owner (BR5.1), so the maintainer's first
        # export is left unknown, on a pair of its own, before the second is bound.
        for name, authority in (("someone", someone), ("scanned", maintainer),
                                ("pending", maintainer)):
            if name != "pending":
                store_flows.configure(repository, authority, now)
            connection = repository.read_connection(authority)
            effects[name] = store_flows.bound(repository, authority, connection,
                                              now)["effect"]
            if name == "scanned":
                store_flows.uncertain(repository, effects["scanned"], now)
        due = store_flows.effect_row(standin.connect, effects["scanned"]["id"])["next_check_at"]
        yield repository, maintainer.account_id, effects, due


class Unread:
    """A content port the pass must never read: it raises when asked."""

    def bound_content(self, identifier):
        raise AssertionError("the pass read content it must not read")


@pytest.mark.parametrize("batch", [0, 101])
def test_the_preview_pass_refuses_an_unbounded_batch(batch):
    with pytest.raises(ValueError):
        FirstExportPreviews(Due(), Unread(), Gate(), clock=lambda: dt.datetime.now(dt.UTC),
                            batch=batch)


def test_the_preview_pass_skips_what_is_not_the_maintainers_execute(export_store):
    from backend.modules.export.notion_adapter import StoreContentPort
    from backend.u8_outward import export_preview

    repository, maintainer, effects, due = export_store
    # The real query answers exactly the three due items.
    assert {(row["kind"], row["id"]) for row in repository.due_items(due, limit=100)} == {
        ("execute", effects["someone"]["id"]), ("execute", effects["pending"]["id"]),
        ("scan", effects["scanned"]["id"])}
    # The real content port over the same store. The maintainer's execute was bound
    # through U6's own store units, which render its blocks, so it has bound content:
    # exactly its one preview is recorded. The other account's execute and the maintainer's
    # scan record nothing.
    port, gate = StoreContentPort(repository), Gate("held", maintainer={maintainer})
    pending = port.bound_content(effects["pending"]["id"])
    assert pending is not None
    passed = FirstExportPreviews(repository, port, gate, clock=lambda: due).run_once()
    assert passed == {"recorded": 1}
    assert gate.previews == [("notion", export_preview(pending))]
    # Outside live mode, or once Notion is no longer held, the pass reads no content and
    # records nothing.
    for other in (Gate("held", mode="rehearsal", maintainer={maintainer}),
                  Gate("active", maintainer={maintainer})):
        assert FirstExportPreviews(repository, Unread(), other,
                                   clock=lambda: due).run_once() == {"recorded": 0}
        assert other.previews == []
