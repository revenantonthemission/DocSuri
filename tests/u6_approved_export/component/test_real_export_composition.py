"""The operator-only real composition (`backend/u6_real_export.py`; cicd-pipeline §4.6, §5):
every settings refusal, the test-only seam, the test-wide network guard and the refusal
of an environment that holds evidence. Settings files are written only into `tmp_path`,
never into an environment folder, and no request reaches Notion."""

import asyncio
import datetime as dt
import json
import os
from types import SimpleNamespace

import pytest
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.export import notion_session
from backend.modules.export.errors import ExportError
from backend.modules.export.notion_session import CandidateToken
from backend.u6_host import ACTIVATION_FILE, assemble_u6
from backend.u6_policy import ExportPolicy
from backend.u6_real_export import (
    RealExportActivation,
    assemble_u6_real,
    load_activation,
    parse_activation,
    real_export_factory,
    require_no_evidence,
)

from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import service_flows as sf
from tests.u6_approved_export import store_flows as flows

RUN = "docsuri-u6-0123456789abcdef"
DESTINATION = "0123456789abcdef0123456789abcdef"
TODAY = dt.date(2026, 10, 20)


def settings(**overrides) -> dict:
    terms = {
        "plan": "free",
        "memberCount": 1,
        "checkedOn": "2026-10-19",
        "publishedLimits": ["Free plan block limit for workspaces with two or more members"],
    }
    terms.update(overrides.pop("freeTerms", {}))
    return {"runId": RUN, "activationDestinationId": DESTINATION, "freeTerms": terms, **overrides}


def stub_profile(root, run_id: str = RUN):
    return SimpleNamespace(root=root, run_id=run_id)


def refusal_field(call) -> str:
    with pytest.raises(ExportError) as caught:
        call()
    assert caught.value.code == "POLICY_UNRESOLVED"
    return caught.value.current["field"]


def write_settings(root, value, *, mode: int = 0o600) -> None:
    path = root / ACTIVATION_FILE
    path.write_text(value if isinstance(value, str) else json.dumps(value))
    os.chmod(path, mode)


@pytest.mark.parametrize(
    "value,field",
    [
        ([], "settings"),
        ({**settings(), "token": "never-here"}, "settings"),
        ({key: item for key, item in settings().items() if key != "freeTerms"}, "settings"),
        (settings(runId="docsuri-u6-another"), "runId"),
        (settings(activationDestinationId=DESTINATION.upper()), "activationDestinationId"),
        (settings(activationDestinationId=DESTINATION[:31]), "activationDestinationId"),
        (settings(activationDestinationId=None), "activationDestinationId"),
        ({**settings(), "freeTerms": "free"}, "freeTerms"),
        (settings(freeTerms={"plan": "plus"}), "freeTerms.plan"),
        (settings(freeTerms={"memberCount": 2}), "freeTerms.memberCount"),
        (settings(freeTerms={"memberCount": True}), "freeTerms.memberCount"),
        (settings(freeTerms={"checkedOn": "19/10/2026"}), "freeTerms.checkedOn"),
        (settings(freeTerms={"checkedOn": "2026-02-30"}), "freeTerms.checkedOn"),
        (settings(freeTerms={"checkedOn": "2026-10-21"}), "freeTerms.checkedOn"),
        (settings(freeTerms={"publishedLimits": []}), "freeTerms.publishedLimits"),
        (settings(freeTerms={"publishedLimits": [" "]}), "freeTerms.publishedLimits"),
        (settings(freeTerms={"publishedLimits": ["x"] * 9}), "freeTerms.publishedLimits"),
        (settings(freeTerms={"publishedLimits": [3]}), "freeTerms.publishedLimits"),
        (settings(freeTerms={"publishedLimits": ["x" * 257]}), "freeTerms.publishedLimits"),
    ],
)
def test_every_settings_gap_refuses_with_policy_unresolved(tmp_path, value, field):
    profile = stub_profile(tmp_path)
    assert refusal_field(lambda: parse_activation(value, profile, today=TODAY)) == field


def test_valid_settings_give_the_real_activation(tmp_path):
    write_settings(tmp_path, settings())

    activation = load_activation(stub_profile(tmp_path), today=TODAY)

    assert activation.activation_destination_id == DESTINATION
    assert activation.run_id == RUN and activation.free_terms["memberCount"] == 1
    assert activation.free_terms_reference.startswith("notion-free:2026-10-19:")
    policy = real_export_factory(activation).keywords["policy"]
    assert isinstance(policy, ExportPolicy) and policy.synthetic_only is False
    assert policy.activation_destination_id == DESTINATION
    assert policy.free_terms_reference == activation.free_terms_reference


def test_the_settings_file_custody_is_checked(tmp_path):
    profile = stub_profile(tmp_path)
    assert refusal_field(lambda: load_activation(profile, today=TODAY)) == "settings-absent"
    write_settings(tmp_path, settings(), mode=0o644)
    assert refusal_field(lambda: load_activation(profile, today=TODAY)) == "settings-custody"
    write_settings(tmp_path, "x" * 5000)
    assert refusal_field(lambda: load_activation(profile, today=TODAY)) == "settings-custody"
    write_settings(tmp_path, "{not json")
    assert refusal_field(lambda: load_activation(profile, today=TODAY)) == "settings"


def test_an_environment_holding_evidence_is_refused_before_any_assembly(tmp_path):
    activation = parse_activation(settings(), stub_profile(tmp_path), today=TODAY)
    (tmp_path / "component-evidence-1792477395181016000.json").write_text("{}")

    assert refusal_field(lambda: require_no_evidence(tmp_path)) == "environment"
    assert refusal_field(lambda: assemble_u6_real(stub_profile(tmp_path), activation)) == (
        "environment"
    )
    foreign = stub_profile(tmp_path, "docsuri-u6-another")
    assert refusal_field(lambda: assemble_u6_real(foreign, activation)) == "runId"
    assert refusal_field(lambda: assemble_u6_real(stub_profile(tmp_path), object())) == "runId"


def test_the_synthetic_composition_refuses_real_export_settings(tmp_path):
    write_settings(tmp_path, settings())
    with pytest.raises(ValueError, match="real-export settings"):
        assemble_u6(stub_profile(tmp_path))


def real_contribution(transactions, activation: RealExportActivation, **seam):
    factory = real_export_factory(activation, **seam)
    return factory(
        transactions,
        GuardedEntryService(transactions),
        None,
        None,
        research=sf.ResearchDouble(),
    )


def identify(built, authority, connect, token: str):
    """A candidate check on a fresh pending reservation, released afterwards."""
    flows.fresh(connect, authority.account_id)
    repository = built["repository"]
    slot = repository.reserve_connection(authority, None, now=dt.datetime.now(dt.UTC))
    try:
        return asyncio.run(
            built["service"].adapter.identify(CandidateToken(slot.connection_id, token))
        )
    finally:
        repository.release_pending(authority, slot.holder)


def test_the_seam_injects_a_transport_under_the_real_policy(
    transactions, connect, authority, realm
):
    activation = parse_activation(settings(runId=realm.run_id), realm, today=TODAY)
    token, bot = nf.synthetic_token(), nf.bot_id()
    fake = nf.fake_with(token, bot)

    built = real_contribution(transactions, activation, transport_factory=lambda: fake)
    identified = identify(built, authority, connect, token)

    assert built["capabilities"][0]["modeIds"] == ["real-bounded"]
    assert built["capabilities"][0]["policy"]["policyId"] == "u6-real-activation"
    assert built["service"].policy.activation_destination_id == DESTINATION
    assert (identified.category, identified.integration_id) == ("ok", bot)
    assert [entry.path for entry in fake.requests] == ["/v1/users/me"]


def test_without_the_seam_the_real_composition_stops_at_the_network_guard(
    transactions, connect, authority, realm, no_network_transport, monkeypatch
):
    reached = []

    def guard():
        reached.append(True)
        return no_network_transport()

    monkeypatch.setattr(notion_session, "network_transport", guard)
    activation = parse_activation(settings(runId=realm.run_id), realm, today=TODAY)

    built = real_contribution(transactions, activation)
    identified = identify(built, authority, connect, nf.synthetic_token())

    assert reached == [True]  # the guard ran where the network transport would be built
    assert identified.category == "could-not-check"
