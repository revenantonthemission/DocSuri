import json

import pytest
from evidence_support import verified_context

from docsuri_platform_integrity.adapters.authority import CurrentReadAuthority, ReadGrant
from docsuri_platform_integrity.application.evidence import EvidenceService
from docsuri_platform_integrity.cli.__main__ import main
from docsuri_platform_integrity.contracts.codec import digest
from docsuri_platform_integrity.contracts.models import (
    EvidenceHeadSelection,
    GateVerdict,
    SubjectSnapshot,
    ValidityWindow,
    VerificationAttestation,
)
from docsuri_platform_integrity.domain.bindings import validate_catalog
from docsuri_platform_integrity.domain.gate import evaluate
from docsuri_platform_integrity.domain.supply_chain import parse_pip_audit

D = digest(b"artifact")
SUBJECT = SubjectSnapshot(subject="s", artifact=D, incarnation="i", policy=D)


@pytest.mark.parametrize(
    "outcome,verdict", [("FAIL", GateVerdict.BLOCKED), ("UNKNOWN", GateVerdict.INCOMPLETE)]
)
def test_selected_failure_cannot_fall_back_to_pass(outcome, verdict):
    current = VerificationAttestation(
        evidence_id="new",
        verification_id="v-new",
        subject=SUBJECT,
        slot="schema",
        revision="2",
        outcome=outcome,
        validity=ValidityWindow(valid_from="0", valid_until="200"),
    )
    old = current.model_copy(update={"evidence_id": "old", "revision": "1", "outcome": "PASS"})
    head = EvidenceHeadSelection(
        subject=SUBJECT, verification_id="v-new", slot="schema", revision="2",
        state="RESOLVED", evidence_id="new",
    )
    assert (
        evaluate(
            SUBJECT, ("schema",), (head,), (current, old), lower=100, upper=100,
            trusted=True, current=verified_context(SUBJECT, (current,)),
        ).verdict
        == verdict
    )


def test_revocation_during_observation_denies_delivery():
    grants = {"cert": ReadGrant("cert", frozenset({"s"}), 200)}
    authority = CurrentReadAuthority(grants.get, lambda: (100, 100))

    class RevokeDuringRead:
        def snapshot(self, subject):
            grants.clear()
            return (), ()

    service = EvidenceService(
        RevokeDuringRead(), authority, lambda: (100, 100), {"s": (SUBJECT, ("schema",))}
    )
    with pytest.raises(PermissionError):
        service.read("cert", "s")


def test_historical_exception_reference_alone_cannot_make_subject_eligible():
    record = VerificationAttestation(
        evidence_id="historical", subject=SUBJECT, slot="sca", revision="1", outcome="PASS",
        validity=ValidityWindow(valid_from="0", valid_until="200"),
        exceptions=("exception-without-current-proof",),
    )
    head = EvidenceHeadSelection(
        slot="sca", revision="1", state="RESOLVED", evidence_id=record.evidence_id,
    )
    assert not evaluate(SUBJECT, ("sca",), (head,), (record,), lower=100, upper=100).eligible


def test_read_service_does_not_promote_checksum_only_pass():
    record = VerificationAttestation(
        evidence_id="unsigned", subject=SUBJECT, slot="schema", revision="1", outcome="PASS",
        validity=ValidityWindow(valid_from="0", valid_until="200"),
    )
    head = EvidenceHeadSelection(
        slot="schema", revision="1", state="RESOLVED", evidence_id=record.evidence_id,
    )

    class Reader:
        def snapshot(self, subject):
            return (head,), (record,)

    grant = ReadGrant("cert", frozenset({"s"}), 200)
    authority = CurrentReadAuthority(lambda _: grant, lambda: (100, 100))
    service = EvidenceService(
        Reader(), authority, lambda: (100, 100), {"s": (SUBJECT, ("schema",))},
    )
    assert not service.read("cert", "s").eligible


def test_scanner_success_requires_exact_inventory_and_full_results():
    report = {"dependencies": [{"name": "package", "version": "1", "vulns": []}]}
    assert parse_pip_audit(report, returncode=0, expected={"package": "1"}, source="pypi") == ()
    with pytest.raises(ValueError):
        parse_pip_audit(report, returncode=1, expected={"package": "1"}, source="pypi")
    with pytest.raises(ValueError):
        parse_pip_audit(report, returncode=0, expected={"package": "2"}, source="pypi")
    with pytest.raises(ValueError):
        parse_pip_audit(
            report, returncode=0, expected={"package": "1", "missing": "1"}, source="pypi"
        )
    report["dependencies"][0]["vulns"] = [{"id": "CVE-123", "aliases": []}]
    (finding,) = parse_pip_audit(report, returncode=1, expected={"package": "1"}, source="pypi")
    assert finding.advisory == "CVE-123" and finding.severity == "unknown"


def test_local_schema_fragments_and_duplicate_ids_are_checked():
    schema = {
        "$id": "https://schema.test/x",
        "$defs": {"Thing": {"type": "string"}},
        "properties": {"x": {"$ref": "#/$defs/Thing"}},
    }
    assert len(validate_catalog((schema,))) == 1
    with pytest.raises(ValueError):
        validate_catalog((schema, schema))
    schema["properties"]["x"]["$ref"] = "#/$defs/Missing"
    with pytest.raises(ValueError):
        validate_catalog((schema,))


def test_cli_never_applies_by_default_and_does_not_leak_paths(capsys, tmp_path):
    with pytest.raises(SystemExit):
        main([])
    assert main(["apply"]) == 2
    assert main(["check-schemas", str(tmp_path / "PRIVATE-SENTINEL")]) == 2
    assert "PRIVATE-SENTINEL" not in capsys.readouterr().out
    (tmp_path / "ok.schema.json").write_text(json.dumps({"$id": "https://local.test/root"}))
    assert main(["check-schemas", str(tmp_path)]) == 2
    assert main(["check-schemas", str(tmp_path), "--flat"]) == 0
    report = tmp_path / "report.json"
    inventory = tmp_path / "inventory.json"
    report.write_text(json.dumps({"dependencies": [{"name": "pkg", "version": "1", "vulns": []}]}))
    inventory.write_text(json.dumps({"pkg": "1"}))
    assert main(["verify-audit", str(report), str(inventory), "--returncode", "0"]) == 0
