"""U6:NFR6.2/free-terms-evidence: the recorded free-terms reference and the real row.

The reference is the check date plus the digest of the canonical evidence record; it is
stable under key order and changes with any edit. The real factory carries it into the
policy and the capability row, and an unusable reference refuses before any assembly.
"""

import dataclasses
import datetime as dt
import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from backend import u6_real_export as real_module
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.export.errors import ExportError
from backend.u6_host import ACTIVATION_FILE
from backend.u6_policy import real_activation_export
from backend.u6_real_export import (
    assemble_u6_real,
    free_terms_reference,
    load_activation,
    parse_activation,
    real_export_factory,
    real_policy,
)
from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import service_flows as sf

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


def write_settings(root, value, *, mode: int = 0o600) -> None:
    path = root / ACTIVATION_FILE
    path.write_text(value if isinstance(value, str) else json.dumps(value))
    os.chmod(path, mode)


def refusal_field(call) -> str:
    with pytest.raises(ExportError) as caught:
        call()
    assert caught.value.code == "POLICY_UNRESOLVED"
    return caught.value.current["field"]


class Inherited:
    def run_once(self, limit=1):
        return {"limit": limit}


def test_the_reference_digests_the_canonical_evidence_record():
    terms = settings()["freeTerms"]
    reference = free_terms_reference(terms)

    canonical = json.dumps(terms, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert reference == "notion-free:2026-10-19:" + hashlib.sha256(canonical.encode()).hexdigest()
    assert free_terms_reference(dict(reversed(list(terms.items())))) == reference
    changed_date = {**terms, "checkedOn": "2026-10-18"}
    assert free_terms_reference(changed_date) != reference
    changed_limit = {**terms, "publishedLimits": [*terms["publishedLimits"], "another"]}
    assert free_terms_reference(changed_limit) != reference
    assert real_activation_export(
        activation_destination_id=DESTINATION, free_terms_reference=reference
    ).free_terms_reference == reference


def test_the_real_factory_carries_the_evidence_and_the_realm_key_folder(transactions, realm):
    activation = parse_activation(settings(runId=realm.run_id), realm, today=TODAY)
    fake = nf.fake_with(nf.synthetic_token(), nf.bot_id())

    built = real_export_factory(activation, transport_factory=lambda: fake)(
        transactions,
        GuardedEntryService(transactions),
        None,
        Inherited(),
        research=sf.ResearchDouble(),
    )

    policy = built["service"].policy
    assert policy.free_terms_reference == activation.free_terms_reference
    assert policy.policy_id == "u6-real-activation"
    assert built["capabilities"][0]["modeIds"] == ["real-bounded"]
    assert built["capabilities"][0]["policy"] == policy.reference()
    assert built["service"].vault._keys.root == realm.root / "export-keys"
    assert activation.free_terms == {
        "plan": "free",
        "memberCount": 1,
        "checkedOn": "2026-10-19",
        "publishedLimits": ["Free plan block limit for workspaces with two or more members"],
    }


@pytest.mark.parametrize(
    "reference", ["", "with space", "x" * 257, "notion-free:2026-10-19:é"]
)
def test_an_unusable_evidence_reference_refuses_before_any_assembly(
    tmp_path, monkeypatch, reference
):
    activation = dataclasses.replace(
        parse_activation(settings(), stub_profile(tmp_path), today=TODAY),
        free_terms_reference=reference,
    )

    with pytest.raises(ExportError) as caught:
        real_policy(activation)
    assert caught.value.code == "POLICY_UNRESOLVED"
    assert caught.value.current["field"] == "policy"

    reached = []
    monkeypatch.setattr(real_module, "assemble_u5", lambda *args, **kwargs: reached.append(True))
    before = sorted(path.name for path in tmp_path.iterdir())
    with pytest.raises(ExportError) as caught:
        assemble_u6_real(stub_profile(tmp_path), activation)
    assert caught.value.current["field"] == "policy"
    assert reached == []
    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_only_the_private_settings_file_supplies_the_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "DOCSURI_FREE_TERMS",
        json.dumps(
            {
                "plan": "free",
                "memberCount": 1,
                "checkedOn": "2026-10-01",
                "publishedLimits": ["a decoy"],
            }
        ),
    )
    write_settings(tmp_path, settings())

    activation = load_activation(stub_profile(tmp_path), today=TODAY)

    assert activation.free_terms["checkedOn"] == "2026-10-19"
    assert activation.free_terms["publishedLimits"] != ["a decoy"]
    (tmp_path / ACTIVATION_FILE).unlink()
    assert refusal_field(lambda: load_activation(stub_profile(tmp_path), today=TODAY)) == (
        "settings-absent"
    )

    real = tmp_path / "real-settings.json"
    write_settings(tmp_path, settings())
    (tmp_path / ACTIVATION_FILE).replace(real)
    os.symlink(real, tmp_path / ACTIVATION_FILE)
    assert refusal_field(lambda: load_activation(stub_profile(tmp_path), today=TODAY)) == (
        "settings-custody"
    )
