"""ProviderActivation and its two ports, wired by the composition (U8 plan Step 21; BR7.1,
BR7.3, BR7.5, BR7.6, BR7.8, BR9.5, BR9.7, BR9.14; functional spec "State machine —
ProviderActivation").

The machine runs over a real ledger in a private folder, with the injected clock; your
decisions are MaintainerApproval records the test harness appends as you, each with its
receipt's binding facts. Built early beside Step 22's tests: its natural home, Step 22's
`test_first_effects.py`, waits on the bounds decision.
"""

from __future__ import annotations

import hashlib
import json
import stat
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.modules.accounts.integrations import account_mail
from backend.modules.accounts.integrations.account_mail import (
    AccountMessage,
    HeldAccountMail,
    ResendAccountMail,
)
from backend.modules.accounts.integrations.provider_gate import (
    ProviderGate,
    RehearsalRecipients,
)
from backend.modules.export import notion_session
from backend.modules.operations.errors import OperationsError
from backend.modules.operations.ledger import Ledger, utc_text
from backend.modules.operations.provider_activation import (
    STEPS,
    ActivationSettings,
    ProviderActivation,
    provider_word,
)
from tests.u8_service_operations_integration import cutover_flows as cf

PROVIDERS = frozenset({"google", "orcid", "resend", "models", "notion"})


@pytest.fixture
def operations_ledger(tmp_path, clock):
    folder = tmp_path / "operations-ledger"
    folder.mkdir(mode=0o700)
    value = Ledger.open(folder, clock=clock)
    yield value
    value.close()


@pytest.fixture
def make(operations_ledger, clock, tmp_path):
    maintainer = uuid4()
    (tmp_path / "evidence").mkdir(mode=0o700)

    def build(mode: str, configured=PROVIDERS, *, owner=None) -> ProviderActivation:
        settings = ActivationSettings(mode, maintainer, frozenset(configured),
                                      tmp_path / "evidence" / "previews")
        activation = ProviderActivation(operations_ledger, settings, clock=clock,
                                        connection_owner=owner)
        activation.start()
        return activation

    build.maintainer = maintainer
    return build


def decide(ledger, clock, provider: str, digest: str | None = None, *, step=None,
           decision="approved"):
    """Your decision on the subject `cutover decide` shows, as `platform.decision.record`
    leaves it (`cutover_flows.provider_decision`, U8 plan Step 107(b)): its approval id
    and its subject, for `approve`. With another `step`, a decision on that step under
    the provider's subject reference, which `approve` refuses."""
    if step is not None and step != STEPS.get(provider):
        approval = cf.decision(ledger, step, "provider:" + provider, now=clock())
        return approval, {"step": step, "provider": provider}
    return cf.provider_decision(ledger, provider, now=clock(), decision=decision,
                                preview_digest=digest)


# The machine at a profile start -----------------------------------------------------------


def test_each_mode_starts_each_provider_as_the_machine_says(make):
    synthetic = make("synthetic", PROVIDERS - {"resend"})
    assert {p: synthetic.record(p)["state"] for p in PROVIDERS} == {
        "google": "active", "orcid": "active", "models": "active", "notion": "active",
        "resend": "unconfigured"}
    assert synthetic.state("resend") == "unavailable"  # the gate's vocabulary
    live = make("live", PROVIDERS - {"resend"})
    assert {p: live.record(p)["state"] for p in PROVIDERS} == {
        "google": "held", "orcid": "held", "notion": "held", "models": "active",
        "resend": "unconfigured"}
    assert live.record("notion")["limitations"] == ["first-effect-pending"]
    assert live.record("orcid")["limitations"] == ["sign-in-unverified"]
    assert live.state("notion") == "held" and not live.bounds_lifted("notion")
    rehearsal = make("rehearsal")
    assert {rehearsal.state(p) for p in PROVIDERS} == {"active"}
    assert not rehearsal.bounds_lifted("notion")  # BR7.6: never in rehearsal
    assert isinstance(rehearsal, ProviderGate) and isinstance(rehearsal, RehearsalRecipients)


def test_the_maintainers_account_and_connection_are_known_only_by_the_profile(make):
    connection, other = uuid4(), uuid4()
    owners = {connection: make.maintainer, other: uuid4()}
    activation = make("rehearsal", owner=owners.get)
    assert activation.is_maintainer_account(make.maintainer)
    assert not activation.is_maintainer_account(uuid4())
    assert activation.is_maintainer_connection(connection)
    assert not activation.is_maintainer_connection(other)
    assert not make("rehearsal").is_maintainer_connection(connection)  # no owner read


def test_a_failed_owner_read_holds_and_no_maintainer_reads_nothing(
        make, operations_ledger, clock, tmp_path, caplog):
    """Your answer of 2026-11-11 ("Wire the owner read"): an owner read that fails reads
    as not the maintainer's, so the Notion operation is held, and is logged by type and
    location only; a profile that names no maintainer never reads an owner."""
    from backend.log_events import EVENTS_LOGGER
    from backend.modules.operations.provider_activation import connection_owner_reader

    connection = uuid4()
    calls = []

    def failing(connection_id):
        calls.append(connection_id)
        raise ConnectionError("database gone " + str(connection_id))

    activation = make("rehearsal", owner=failing)
    with caplog.at_level("ERROR", logger=EVENTS_LOGGER):
        assert not activation.is_maintainer_connection(connection)
    assert calls == [connection]
    lines = [record.getMessage() for record in caplog.records
             if record.name == EVENTS_LOGGER]
    unread = [json.loads(line) for line in lines
              if json.loads(line)["event"] == "provider.connection-owner-unread"]
    assert len(unread) == 1, lines
    assert (unread[0]["component"], unread[0]["level"], unread[0]["errorType"]) == (
        "operations", "error", "ConnectionError")
    assert not any(str(connection) in line for line in lines)
    nobody = ProviderActivation(
        operations_ledger,
        ActivationSettings("rehearsal", None, PROVIDERS, tmp_path / "evidence" / "previews"),
        clock=clock, connection_owner=failing)
    assert not nobody.is_maintainer_connection(connection)
    assert calls == [connection]  # no read without a maintainer
    with pytest.raises(TypeError):
        connection_owner_reader(SimpleNamespace(run=failing))(str(connection))
    assert calls == [connection]  # a malformed id is refused before any transaction


# The first effect, its preview and your decision (BR7.3) ----------------------------------


def test_a_held_first_effect_is_previewed_and_your_decision_on_its_digest_activates(
    make, operations_ledger, clock, tmp_path, window,
):
    activation = make("live")
    content = b'{"to":["maintainer@fixture.example.com"],"subject":"first"}'
    digest = activation.record_preview("resend", content)
    assert digest == hashlib.sha256(content).hexdigest()
    assert activation.record_preview("resend", content) == digest  # the same file
    [path] = (tmp_path / "evidence" / "previews").iterdir()
    assert path.read_bytes() == content and stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    with pytest.raises(OperationsError) as refused:
        activation.approve("resend", *decide(operations_ledger, clock, "resend", "e" * 64))
    assert refused.value.current == {"reasonKey": "approval-subject-differs"}
    assert activation.state("resend") == "held"
    activated = activation.approve("resend",
                                   *decide(operations_ledger, clock, "resend", digest))
    assert (activated["state"], activated["approvalContentHash"]) == ("active", digest)
    assert activated["approvedAt"] == utc_text(clock())
    assert activation.state("resend") == "active" and activation.bounds_lifted("resend")
    # No preview is taken once the provider is active.
    with pytest.raises(OperationsError):
        activation.record_preview("resend", b"later")


def test_a_decision_for_another_step_or_provider_changes_nothing(make, operations_ledger,
                                                                 clock, window):
    activation = make("live")
    digest = activation.record_preview("notion", b"page")
    for approval in (
        decide(operations_ledger, clock, "notion", digest, step="admission-opening"),
        decide(operations_ledger, clock, "resend", digest),
    ):
        with pytest.raises(OperationsError):
            activation.approve("notion", *approval)
    with pytest.raises(OperationsError):
        activation.approve("notion", uuid4(), {})  # no such decision
    assert activation.state("notion") == "held"


def test_a_sign_in_provider_is_verified_by_your_decision_or_fails(make, operations_ledger,
                                                                  clock, window):
    activation = make("live")
    approval = decide(operations_ledger, clock, "google", "a" * 64, step="provider-sign-in")
    assert activation.approve("google", *approval)["state"] == "active"
    assert "approvalContentHash" not in activation.record("google")
    failed = activation.fail_verification("orcid")
    assert (failed["state"], failed["limitations"]) == (
        "unavailable", ["sign-in-verification-failed"])
    assert activation.state("orcid") == "unavailable"
    with pytest.raises(OperationsError):
        activation.report_service("orcid", "active")  # only a real sign-in moves it back


def test_a_declining_decision_returns_an_active_provider_to_held(make, operations_ledger,
                                                                 clock, window):
    activation = make("live")
    digest = activation.record_preview("notion", b"page")
    activation.approve("notion", *decide(operations_ledger, clock, "notion", digest))
    declined = activation.approve(
        "notion", *decide(operations_ledger, clock, "notion", digest, decision="declined"))
    assert (declined["state"], "approvedAt" in declined) == ("held", False)


def test_an_abort_clears_every_approval_and_the_next_switch_verifies_again(
    make, operations_ledger, clock, window,
):
    activation = make("live")
    digest = activation.record_preview("resend", b"mail")
    activation.approve("resend", *decide(operations_ledger, clock, "resend", digest))
    activation.approve("google", *decide(operations_ledger, clock, "google", "b" * 64,
                                         step="provider-sign-in"))
    states = activation.clear_approvals(mode="rehearsal")
    assert set(states.values()) == {"active"} and activation.mode == "rehearsal"
    for provider in ("resend", "google"):
        assert not {"approvedAt", "approvalId", "approvalContentHash"} & set(
            activation.record(provider))
    # The profile switches to live again: each outward and sign-in provider is held.
    again = make("live")
    assert {again.state(p) for p in ("resend", "google", "orcid", "notion")} == {"held"}


def test_an_active_provider_degrades_and_serves_again(make):
    activation = make("rehearsal")
    assert activation.report_service("resend", "degraded", "allowance-exhausted")[
        "limitations"] == ["allowance-exhausted"]
    assert activation.state("resend") == "active"  # a degraded provider still serves
    assert activation.report_service("resend", "unavailable", "provider-unreachable")[
        "state"] == "unavailable"
    assert activation.state("resend") == "unavailable"
    assert activation.report_service("resend", "active")["limitations"] == []
    with pytest.raises(ValueError):
        activation.report_service("resend", "held", "x")


# The two ports, wired by the composition (Step 21's "Two ports" box) --------------------


def production_parts(tmp_path, activation, environment: dict, *, capability_states=None):
    import json

    from backend import u8_host

    (tmp_path / "private-environment.json").write_text(json.dumps(environment))
    (tmp_path / "private-environment.json").chmod(0o600)
    profile = SimpleNamespace(is_production=True, root=tmp_path,
                              origin="https://docsuri.rvnnt.dev")
    entry = SimpleNamespace(account_mail=None, mail=None)
    parts = {"account-controls": {"entry": entry},
             "service-operations": {"activation": activation, "allowance": object()}}
    u8_host.wire_adapters(parts, profile, capability_states=capability_states)
    return entry


def test_production_wires_the_gate_into_account_mail_and_notion(make, tmp_path, monkeypatch):
    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    activation = make("live")
    entry = production_parts(tmp_path, activation, {
        "resendApiKey": "re_" + uuid4().hex[:24],  # generated per run (L1-36)
        "accountMailSender": "DocSuri <no-reply@x.example>"})
    assert isinstance(entry.account_mail, ResendAccountMail)
    assert entry.account_mail.gate is activation and entry.account_mail.recipients is activation
    assert notion_session._INSTALLED_GATE == {"gate": activation, "recipients": activation}
    assert entry.identity_gate is activation  # Google and ORCID sign-in (Step 106(g))
    # Held in live mode: the message is held before the allowance or the network.
    message = AccountMessage("verification", str(uuid4()), make.maintainer,
                             {"email": "m@x.example"})
    assert entry.account_mail.deliver(message) == "held"


def test_notions_gate_opens_only_while_provider_notion_is_observed_unavailable(make):
    """L2-13 (reliability-design § 10): Notion's breaker opens only on an observed
    `unavailable`; `unknown` and `stale` fail open, every other provider keeps the
    activation's answer, and each call reads the observation afresh."""
    from backend.modules.accounts.integrations.provider_gate import require_state
    from backend.u8_outward import notion_gate

    def reader_of(state: str):
        return lambda: {"provider.notion": {"state": state, "reason": None}}

    activation = make("rehearsal")
    for observed in ("available", "degraded", "unknown", "stale", "unavailable"):
        gate = notion_gate(activation, reader_of(observed))
        assert isinstance(gate, ProviderGate), observed
        expected = "unavailable" if observed == "unavailable" else "active"
        assert require_state(gate, "notion") == expected, observed
        assert gate.mode == "rehearsal", observed
        for provider in ("google", "orcid", "resend", "models"):
            assert gate.state(provider) == activation.state(provider), (observed, provider)
    current = {"state": "unavailable"}
    changing = notion_gate(activation, lambda: {"provider.notion": dict(current)})
    assert changing.state("notion") == "unavailable"
    current["state"] = "available"  # the probe passes: calls resume (line 137)
    assert changing.state("notion") == "active"
    assert notion_gate(activation, None) is activation
    # Last, since a live start writes each provider's held record to the shared ledger.
    live = make("live")
    for observed in ("available", "degraded", "unknown", "stale", "unavailable"):
        expected = "unavailable" if observed == "unavailable" else "held"
        assert notion_gate(live, reader_of(observed)).state("notion") == expected, observed


def test_production_installs_notions_breaker_over_the_activation(make, tmp_path,
                                                                 monkeypatch):
    from backend.u8_outward import ObservedNotionGate

    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    activation = make("rehearsal")
    states = {"provider.notion": {"state": "unavailable", "reason": "provider-unreachable"},
              "provider.resend": {"state": "available", "reason": None}}
    entry = production_parts(tmp_path, activation, {}, capability_states=lambda: states)
    gate = notion_session._INSTALLED_GATE["gate"]
    assert isinstance(gate, ObservedNotionGate) and gate.activation is activation
    assert gate.state("notion") == "unavailable"
    assert activation.state("notion") == "active"
    assert notion_session._INSTALLED_GATE["recipients"] is activation
    assert sign_in_gate_of(entry).activation is activation  # the sign-in gate (L4-11)


def test_an_unconfigured_resend_holds_every_message_in_production(make, tmp_path,
                                                                  monkeypatch):
    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    activation = make("rehearsal", PROVIDERS - {"resend"})
    entry = production_parts(tmp_path, activation, {})
    assert isinstance(entry.account_mail, HeldAccountMail)
    assert entry.account_mail.deliver(
        AccountMessage("password-reset", str(uuid4()), None, {})) == "held"
    assert account_mail.HeldAccountMail.path_kind == "held"


def test_a_synthetic_profile_keeps_its_built_adapters_and_no_gate(realm, monkeypatch):
    from backend.u8_host import compose

    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    composition = compose(realm)
    try:
        entry = composition.parts["account-controls"]["entry"]
        assert entry.account_mail.gate is None
        assert notion_session._INSTALLED_GATE == {}
        activation = composition.parts["service-operations"]["activation"]
        assert activation.mode == "synthetic" and activation.state("notion") == "active"
    finally:
        composition.close()


def test_production_without_service_operations_leaves_no_identity_gate(tmp_path, monkeypatch):
    """U8 plan Step 107(j): with ServiceOperations unavailable, production's entry keeps no
    identity gate (provider sign-in then refuses) and its account mail is held."""
    from backend import u8_host

    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    entry = SimpleNamespace(account_mail=None, mail=None, identity_gate=object())
    profile = SimpleNamespace(is_production=True, root=tmp_path,
                              origin="https://docsuri.rvnnt.dev")
    u8_host.wire_adapters({"account-controls": {"entry": entry}}, profile)
    assert entry.identity_gate is None
    assert isinstance(entry.account_mail, HeldAccountMail)


# Approving providers at the switch (U8 plan Step 107(b), CP-3; R-116, BR7.3, BR7.8) --------


@pytest.fixture
def window(operations_ledger, clock):
    """The private ledger's CutoverRecord brought to `switching` through the machine's own
    moves (the clock moved on by the soak's week), before the test body, so every preview
    and decision follows the switch's check. Answers the machine and the record."""
    return cf.switching(operations_ledger, clock)


def refused(call) -> tuple[str, str]:
    with pytest.raises(OperationsError) as error:
        call()
    return error.value.code, error.value.current["reasonKey"]


def instant(text: str):
    import datetime as dt

    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def unchanged(ledger, provider: str):
    """The provider's record and revision now, to compare after a refusal."""
    return ledger.get("provider-activation", provider), ledger.revision(
        "provider-activation", provider)


def test_an_approval_holds_only_for_its_switch_and_its_latest_decision(
        make, operations_ledger, clock, window):
    import datetime as dt

    cutover, record = window
    activation = make("live")
    digest = activation.record_preview("notion", b'{"page": "first"}')
    before = unchanged(operations_ledger, "notion")
    checked = instant(record["switchCheckedAt"])
    # Recorded one second before the switch's check.
    early = cf.provider_decision(operations_ledger, "notion", preview_digest=digest,
                                 now=checked - dt.timedelta(seconds=1))
    assert refused(lambda: activation.approve("notion", *early)) == (
        "CONFLICT", "approval-outside-this-switch")
    assert unchanged(operations_ledger, "notion") == before
    # A subject naming another cutover.
    _, subject = cf.provider_decision(operations_ledger, "notion", now=clock(),
                                      preview_digest=digest)
    other = {**subject, "cutoverId": str(uuid4())}
    elsewhere = cf.decision(operations_ledger, "provider-first-effect", "provider:notion",
                            now=clock(), subject=other)
    assert refused(lambda: activation.approve("notion", elsewhere, other)) == (
        "CONFLICT", "approval-outside-this-switch")
    assert unchanged(operations_ledger, "notion") == before
    # A subject changed after its decision.
    approval, subject = cf.provider_decision(operations_ledger, "notion", now=clock(),
                                             preview_digest=digest)
    assert refused(lambda: activation.approve(
        "notion", approval, {**subject, "previewDigest": "f" * 64})) == (
        "CONFLICT", "approval-subject-differs")
    assert unchanged(operations_ledger, "notion") == before
    # An approved decision A superseded by a later declined decision D.
    a = cf.provider_decision(operations_ledger, "notion", now=clock(), preview_digest=digest)
    d = cf.provider_decision(operations_ledger, "notion", now=clock(), preview_digest=digest,
                             decision="declined")
    assert refused(lambda: activation.approve("notion", *a)) == (
        "CONFLICT", "approval-superseded")
    assert unchanged(operations_ledger, "notion") == before
    assert activation.approve("notion", *d)["state"] == "held"
    assert activation.state("notion") == "held"
    assert refused(lambda: activation.approve("notion", *a)) == (
        "CONFLICT", "approval-superseded")
    held = unchanged(operations_ledger, "notion")
    # After an abort the record is rehearsing: no switch is current.
    latest = cf.provider_decision(operations_ledger, "notion", now=clock(),
                                  preview_digest=digest)
    cutover.abort(reason="operator-abort")
    cutover.aborted()
    assert refused(lambda: activation.approve("notion", *latest)) == (
        "CONFLICT", "approval-outside-this-switch")
    assert unchanged(operations_ledger, "notion") == held


def test_a_preview_held_before_the_switchs_check_is_not_approvable(
        make, operations_ledger, clock):
    activation = make("live")
    content = b'{"to": ["maintainer@fixture.example.com"], "subject": "earlier"}'
    preview = activation.record_preview("resend", content)
    _, record = cf.switching(operations_ledger, clock)
    checked = instant(record["switchCheckedAt"])
    assert activation.previews_of("resend", since=checked) == frozenset()
    assert activation.previews_of("resend") == {preview}  # still on disk
    assert provider_word(activation, "provider-previews", {"provider": "resend"}) == {
        "provider": "resend", "previews": []}
    assert refused(lambda: activation.approve("resend", *cf.provider_decision(
        operations_ledger, "resend", now=clock(), preview_digest=preview))) == (
        "CONFLICT", "approval-subject-differs")
    assert activation.state("resend") == "held"
    # The owning module holds the same effect again in this switch.
    assert activation.record_preview("resend", content) == preview
    assert activation.previews_of("resend", since=checked) == {preview}
    activated = activation.approve("resend", *cf.provider_decision(
        operations_ledger, "resend", now=clock(), preview_digest=preview))
    assert (activated["state"], activated["approvalContentHash"]) == ("active", preview)


def test_a_live_start_keeps_only_approvals_that_still_hold(make, operations_ledger, clock,
                                                           window):
    cutover, _ = window
    activation = make("live")
    digest = activation.record_preview("resend", b'{"mail": 1}')
    activation.approve("resend", *cf.provider_decision(operations_ledger, "resend",
                                                       now=clock(), preview_digest=digest))
    activation.approve("google", *cf.provider_decision(operations_ledger, "google",
                                                       now=clock()))
    restarted = make("live")
    for provider in ("resend", "google"):
        assert restarted.record(provider)["state"] == "active"
        assert {"approvedAt", "approvalId"} <= set(restarted.record(provider))
    assert restarted.bounds_lifted("resend")
    # A later declined decision, recorded and not applied: state and bounds agree.
    cf.provider_decision(operations_ledger, "resend", now=clock(), preview_digest=digest,
                         decision="declined")
    assert restarted.state("resend") == "active" and restarted.bounds_lifted("resend")
    again = make("live")
    assert again.record("resend") == {"provider": "resend", "outward": True,
                                      "state": "held", "limitations": ["first-effect-pending"]}
    assert not again.bounds_lifted("resend")
    assert again.record("google")["state"] == "active"
    # A second switch, with no clearing: the earlier switch's approval no longer holds.
    cutover.abort(reason="operator-abort")
    cutover.aborted()
    record = cutover.check_ready([])
    clock.advance(60)
    start = cf.decision(operations_ledger, "switch-start", record["cutoverId"], now=clock())
    assert cutover.approve_start(start, [])["state"] == "switching"
    second = make("live")
    assert second.record("google") == {"provider": "google", "outward": False,
                                       "state": "held", "limitations": ["sign-in-unverified"]}
    rehearsal = make("rehearsal")
    assert {rehearsal.state(p) for p in PROVIDERS} == {"active"}


def test_a_failed_sign_in_provider_stays_unavailable_until_cleared_or_declined(
        make, operations_ledger, clock, window):
    failed = {"provider": "orcid", "outward": False, "state": "unavailable",
              "limitations": ["sign-in-verification-failed"]}
    activation = make("live")
    activation.fail_verification("orcid")
    for _ in range(2):
        assert make("live").record("orcid") == failed
    assert refused(lambda: activation.approve("orcid", *cf.provider_decision(
        operations_ledger, "orcid", now=clock()))) == (
        "FAILED_PRECONDITION", "provider-not-held")
    assert activation.record("orcid") == failed
    # Reading CP-3(b): a declined decision returns it to held, to try again.
    declined = activation.approve("orcid", *cf.provider_decision(
        operations_ledger, "orcid", now=clock(), decision="declined"))
    assert (declined["state"], declined["limitations"]) == ("held", ["sign-in-unverified"])
    activation.fail_verification("orcid")
    assert activation.clear_approvals(mode="rehearsal")["orcid"] == "active"
    assert make("live").record("orcid")["state"] == "held"


def test_serving_again_never_activates_a_provider_whose_approval_does_not_hold(
        make, operations_ledger, clock, window):
    activation = make("live")
    content = b'{"mail": "again"}'
    digest = activation.record_preview("resend", content)
    activation.approve("resend", *cf.provider_decision(operations_ledger, "resend",
                                                       now=clock(), preview_digest=digest))
    cf.provider_decision(operations_ledger, "resend", now=clock(), preview_digest=digest,
                         decision="declined")
    activation.report_service("resend", "degraded", "provider-unreachable")
    served = activation.report_service("resend", "active")
    assert (served["state"], served["limitations"]) == ("held", ["first-effect-pending"])
    assert "approvedAt" not in served
    # With no later decision, the same pair returns it to active with its approval.
    activation.record_preview("resend", content)
    approval, subject = cf.provider_decision(operations_ledger, "resend", now=clock(),
                                             preview_digest=digest)
    activation.approve("resend", approval, subject)
    activation.report_service("resend", "degraded", "provider-unreachable")
    served = activation.report_service("resend", "active")
    assert served["state"] == "active" and served["approvalId"] == approval
    assert served["approvalContentHash"] == digest


def test_the_provider_words_serve_the_cutovers_three_words(make, operations_ledger, clock,
                                                           window):
    cutover, _ = window
    activation = make("live")
    content = b'{"to": ["maintainer@fixture.example.com"], "subject": "first"}'
    digest = activation.record_preview("resend", content)
    assert provider_word(activation, "provider-previews", {"provider": "resend"}) == {
        "provider": "resend", "previews": [{"digest": digest, "sizeBytes": len(content)}]}
    assert provider_word(activation, "provider-previews",
                         {"provider": "resend", "digest": digest}) == {
        "provider": "resend", "digest": digest, "sizeBytes": len(content),
        "content": json.loads(content)}
    assert refused(lambda: provider_word(activation, "provider-previews",
                                         {"provider": "resend", "digest": "a" * 64})) == (
        "CONFLICT", "preview-not-recorded")
    approval, subject = cf.provider_decision(operations_ledger, "resend", now=clock(),
                                             preview_digest=digest)
    answer = provider_word(activation, "provider-decision",
                           {"provider": "resend", "approvalId": approval, "subject": subject})
    assert answer == {"provider": "resend", "state": "active", "limitations": [],
                      "approvedAt": utc_text(clock()), "approvalContentHash": digest}
    failed = provider_word(activation, "provider-failed", {"provider": "google"})
    assert failed == {"provider": "google", "state": "unavailable",
                      "limitations": ["sign-in-verification-failed"]}
    for document in ({"provider": "resend", "approvalId": approval, "subject": subject,
                      "extra": 1},
                     {"provider": "resend", "approvalId": "not-a-uuid", "subject": subject}):
        assert refused(lambda d=document: provider_word(
            activation, "provider-decision", d)) == ("INVALID_INPUT", "word-or-input-refused")
    assert refused(lambda: provider_word(activation, "provider-previews",
                                         {"provider": "orcid"})) == (
        "INVALID_INPUT", "provider-outside-its-word")
    cutover.abort(reason="operator-abort")
    cutover.aborted()
    assert refused(lambda: provider_word(activation, "provider-failed",
                                         {"provider": "orcid"})) == (
        "FAILED_PRECONDITION", "cutover-not-switching")
    assert activation.state("orcid") == "held"


# The sign-in and digest breakers over the activation (U8 plan Step 162(f), (g); L4-11) ----------


def sign_in_gate_of(entry):
    """The entry's identity gate, which must be the sign-in breaker for Google and ORCID."""
    from backend.u8_outward import ObservedProviderGate

    gate = entry.identity_gate
    assert isinstance(gate, ObservedProviderGate) and isinstance(gate, ProviderGate)
    assert gate.providers == {"google", "orcid"}
    return gate


def production_topics_parts(tmp_path, transactions, activation, *, maintainer=None) -> dict:
    """Production's parts with TopicsDigests built by `production_topics` itself, in
    rehearsal, over stand-in neighbours: before the maintainer has an address, or, with
    `maintainer` (an account that has one), with the real digest adapter."""
    import datetime as dt

    from backend.u8_outward import production_topics

    profile = SimpleNamespace(is_production=True, mode="rehearsal", root=tmp_path,
                              origin="https://docsuri.rvnnt.dev", maintainer_account=maintainer)
    entry = SimpleNamespace(
        account_mail=None, mail=None, account_of=lambda email: None,
        verifier=lambda purpose, value: hashlib.sha256(
            f"{purpose}:{value}".encode()).hexdigest())
    parts = {"account-controls": {"entry": entry}, "paper-journey": {"entry": entry},
             "paper-corpus": {"corpus_repository": None},
             "research-workspace": {"worker": None},
             "service-operations": {"activation": activation, "allowance": object()}}
    ctx = SimpleNamespace(profile=profile, transactions=transactions, parts=parts,
                          clock=lambda: dt.datetime.now(dt.UTC))
    parts["topics-digests"] = production_topics(ctx)
    return {"parts": parts, "profile": profile, "entry": entry}


def test_production_wires_the_sign_in_and_digest_breakers_over_the_activation(
        make, tmp_path, transactions, realm, authority, monkeypatch):
    """L4-11, BR7.1: with the composition's derived states, production's entry reads the
    sign-in breaker over the activation, and the digest adapter and scheduler read one
    digest breaker, bound to provider.resend's state; without the states the bare
    activation stays; a synthetic profile has neither. This shows which objects are
    wired, not what they do."""
    from backend import u8_host
    from backend.u8_outward import ObservedProviderGate

    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    activation = make("rehearsal")
    down = {"state": "unavailable", "reason": "provider-unreachable"}
    states = {"provider." + name: dict(down)
              for name in ("google", "orcid", "resend", "notion", "models")}
    (tmp_path / "private-environment.json").write_text(json.dumps({
        "resendApiKey": "re_" + uuid4().hex[:24],  # generated per run (L1-36)
        "digestSender": "DocSuri <digest@x.example>"}))
    (tmp_path / "private-environment.json").chmod(0o600)

    built = production_topics_parts(tmp_path, transactions, activation)
    topics = built["parts"]["topics-digests"]
    gate = topics["gate"]
    assert isinstance(gate, ObservedProviderGate) and gate.activation is activation
    assert gate.providers == {"resend"} and isinstance(gate, ProviderGate)
    # The scheduler's gate is the adapter's gate; the other ports stay the activation.
    assert topics["scheduler"].gate is gate and topics["delivery"].mail.gate is gate
    assert topics["scheduler"].recipients is activation
    assert topics["scheduler"].first_effects is activation
    # Built before the composition's states exist: unbound, it is the activation's answer.
    assert gate.state("resend") == activation.state("resend") == "active"

    # Without the derived states: the bare activation, and the digest gate stays unbound.
    u8_host.wire_adapters(built["parts"], built["profile"])
    assert built["entry"].identity_gate is activation
    assert gate.state("resend") == "active"
    # With them: the sign-in breaker, and the digest gate bound to provider.resend.
    u8_host.wire_adapters(built["parts"], built["profile"], capability_states=lambda: states)
    sign_in = sign_in_gate_of(built["entry"])
    assert sign_in.activation is activation
    assert [sign_in.state("google"), sign_in.state("orcid")] == ["unavailable"] * 2
    assert gate.state("resend") == "unavailable" and activation.state("resend") == "active"
    assert topics["scheduler"].gate is gate and topics["delivery"].mail.gate is gate

    # With the maintainer's address present (the realm's own fixture account, no new
    # one) the real Resend digest adapter is built, over its module's guarded network
    # builder, and it reads the scheduler's gate too. Nothing is sent here.
    from backend.modules.accounts.integrations.u8_digest_mail import GatedResendDigestMail

    real = production_topics_parts(tmp_path, transactions, activation,
                                   maintainer=authority.account_id)
    real_topics = real["parts"]["topics-digests"]
    mail = real_topics["delivery"].mail
    assert isinstance(mail, GatedResendDigestMail)
    assert isinstance(real_topics["gate"], ObservedProviderGate)
    assert real_topics["gate"] is not gate and real_topics["gate"].activation is activation
    assert real_topics["scheduler"].gate is real_topics["gate"] and mail.gate is real_topics[
        "gate"]
    u8_host.wire_adapters(real["parts"], real["profile"], capability_states=lambda: states)
    assert real_topics["gate"].state("resend") == "unavailable"
    assert real_topics["scheduler"].gate is mail.gate

    # A synthetic profile has neither.
    from backend.u8_host import compose

    composition = compose(realm)
    try:
        entry = composition.parts["account-controls"]["entry"]
        assert getattr(entry, "identity_gate", None) is None
        assert "gate" not in composition.parts["topics-digests"]
        scheduler = composition.parts["topics-digests"]["scheduler"]
        assert not isinstance(getattr(scheduler, "gate", None), ObservedProviderGate)
    finally:
        composition.close()
