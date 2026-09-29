"""Preflight reaches ready only on receipts proved against independent protected policy.

Trust, release authority and time come from the root-owned policy; evidence may carry
only ``{release, receipts}``. These tests pin both halves: policy-signed receipts clear
their reason, and anything self-asserted, copied or tampered does not.
"""

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from docsuri_platform_integrity.adapters.nts import NativeTime
from docsuri_platform_integrity.application import receipts as receipts_app
from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import ValidityWindow
from docsuri_platform_integrity.deployment import receipt_policy
from docsuri_platform_integrity.deployment.launchd import protected_bytes
from docsuri_platform_integrity.deployment.receipt import (
    Capability,
    Receipt,
    issue,
)
from docsuri_platform_integrity.deployment.receipt import (
    trust_key as trust_key_model,
)
from docsuri_platform_integrity.deployment.receipt_policy import (
    ClockReference,
    ReceiptPolicy,
    ReceiptScope,
    ReceiptSignerReference,
)

SCRIPT = Path(__file__).resolve().parents[1] / "platform-integrity" / "preflight.py"
DAY = 86_400_000_000
RELEASE = "r1-2026.09"
NTS = Capability.NTS_CLOCK
D = digest(b"clock-config")
OTHER_HOST = "99999999-9999-9999-9999-999999999999"


def load_preflight():
    spec = importlib.util.spec_from_file_location("rem1_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Clock:
    def __init__(self, lower=None):
        moment = lower if lower is not None else time.time_ns() // 1000
        self.window = moment, moment + 100
        self.elapsed = 1000

    def __call__(self):
        return self.window

    def context(self):
        return NativeTime(self.elapsed, 0, "boot", "resume")


def policy_fixture(tmp_path, monkeypatch, *, revoked=False, trust_key_id="release-key-1"):
    root = tmp_path / "realm"
    (root / "receipt-policy").mkdir(parents=True)
    uid, gid = os.getuid(), os.getgid()
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(receipt_policy, "REALMS", {"test": root})
    monkeypatch.setattr(receipt_policy, "host_identity", lambda: "host-1")
    monkeypatch.setattr(receipt_policy, "verify_accounts", lambda policy: None)
    monkeypatch.setattr(receipt_policy, "protected_chain", lambda path: None)
    monkeypatch.setattr(receipt_policy, "protected_bytes",
                        lambda path, **kw: protected_bytes(path, owner=uid, **kw))
    moment = Clock().window[0]
    policy = ReceiptPolicy(
        profile="test", release=RELEASE, host="host-1",
        clock=ClockReference(frame=str(root / "clock-public/current.json"),
                             writer_uid=uid + 1, config_digest=D),
        signer=ReceiptSignerReference(uid=uid, gid=gid, key_id=trust_key_id,
                                      keychain=str(receipt_policy.keychain_path(
                                          "test", RELEASE, trust_key_id)),
                                      service="org.docsuri.rem1.test.receipt-signing",
                                      account=RELEASE + "/" + trust_key_id),
        trust_keys=(trust_key_model(trust_key_id, key.public_key(), revoked=revoked,
                                    validity=ValidityWindow(
                                        valid_from=str(moment - DAY),
                                        valid_until=str(moment + 30 * DAY))),),
        scopes=(ReceiptScope(capability=NTS, artifact=D),),
    ).validate_bindings()
    path = receipt_policy.policy_path("test", RELEASE)
    path.write_bytes(canonical(policy.model_dump(mode="json")))
    path.chmod(0o444)
    return SimpleNamespace(root=root, key=key, policy=policy, clock=Clock(),
                           snapshot=receipt_policy.load_policy("test", RELEASE))


def signed_receipts(fixture, *, host=None, release=RELEASE, seconds=2 * 86400,
                    offset=-86400, key_id="release-key-1", key=None, artifact=None):
    moment = fixture.clock.window[0]
    lower = moment + offset * 1_000_000
    return {
        NTS.value: issue(
            Receipt(capability=NTS, host=host or "host-1", release=release,
                    validity=ValidityWindow(valid_from=str(lower),
                                            valid_until=str(lower + seconds * 1_000_000)),
                    artifact=artifact or D, evidence=digest(b"live-observation")),
            key_id=key_id, key=key or fixture.key),
    }


def run_preflight(fixture, receipts_map, *, evidence_release=RELEASE, root=None, **kwargs):
    module = load_preflight()
    return module.preflight(
        root=root or fixture.root, drive=None, peak_bytes=0,
        evidence={"release": evidence_release, "receipts": receipts_map},
        policy=fixture.snapshot, clock=fixture.clock, **kwargs)


def cli(tmp_path, *arguments):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path),
         "--estimated-peak-bytes", "0", *arguments],
        capture_output=True, text=True, timeout=60, check=False)


def test_no_evidence_leaves_every_capability_unproven(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    result = run_preflight(fixture, {})
    assert not result["ready"]
    assert result["provenCapabilities"] == []
    assert "nts_clock_malformed" in result["reasons"]
    # Capabilities the policy does not configure are reported as unconfigured, not proven.
    assert "keychain_roles_not_configured" in result["reasons"]


def test_verified_receipt_clears_its_reason(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    result = run_preflight(fixture, signed_receipts(fixture))
    assert result["provenCapabilities"] == [NTS.value]
    assert not [r for r in result["reasons"] if r.startswith("nts_clock")]


def test_valid_receipts_leave_only_host_conditions(tmp_path, monkeypatch):
    """The regression: a proved capability may only keep host-only blockers."""
    fixture = policy_fixture(tmp_path, monkeypatch)
    result = run_preflight(fixture, signed_receipts(fixture))
    assert set(result["reasons"]) <= {
        "disk_reserve", "removable_drive_unverified", "backup_on_same_filesystem",
        "native_macos_required", "filevault_unverified", "filevault_unavailable",
        "keychain_roles_not_configured", "tls_roles_not_configured",
        "native_commit_guard_not_configured", "restore_receipt_not_configured"}


def test_receipt_copied_from_another_host_does_not_clear_the_reason(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    result = run_preflight(fixture, signed_receipts(fixture, host=OTHER_HOST))
    assert result["provenCapabilities"] == []
    assert "nts_clock_host_mismatch" in result["reasons"]


def test_receipt_for_another_release_does_not_clear_the_reason(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    result = run_preflight(fixture, signed_receipts(fixture, release="r1-2026.10"))
    assert "nts_clock_release_mismatch" in result["reasons"]


def test_receipt_from_an_untrusted_key_does_not_clear_the_reason(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    stranger = Ed25519PrivateKey.generate()
    result = run_preflight(fixture, signed_receipts(fixture, key_id="stranger-key", key=stranger))
    assert "nts_clock_untrusted_key" in result["reasons"]


def test_revoked_trust_key_does_not_clear_the_reason(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch, revoked=True)
    result = run_preflight(fixture, signed_receipts(fixture))
    assert "nts_clock_revoked_key" in result["reasons"]


def test_expired_receipt_does_not_clear_the_reason(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    result = run_preflight(fixture, signed_receipts(fixture, offset=-3 * 86400, seconds=86400))
    assert "nts_clock_outside_validity" in result["reasons"]


def test_receipt_window_longer_than_seven_days_is_refused(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    result = run_preflight(fixture, signed_receipts(fixture, seconds=30 * 86400))
    assert "nts_clock_window_too_long" in result["reasons"]


def test_receipt_with_the_wrong_artifact_is_refused(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    result = run_preflight(fixture, signed_receipts(fixture, artifact=digest(b"other")))
    assert "nts_clock_artifact_mismatch" in result["reasons"]


def test_tampered_receipt_signature_does_not_clear_the_reason(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    envelope = signed_receipts(fixture)[NTS.value]
    envelope["signature"] = "0" * 128
    result = run_preflight(fixture, {NTS.value: envelope})
    assert "nts_clock_signature_invalid" in result["reasons"]


def test_boolean_evidence_is_not_accepted(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    result = run_preflight(fixture, {cap.value: True for cap in Capability})
    assert result["provenCapabilities"] == []


def test_evidence_receipts_may_not_carry_its_own_trust(tmp_path, monkeypatch):
    """Trust must never travel inside the evidence it is supposed to vouch for."""
    fixture = policy_fixture(tmp_path, monkeypatch)
    module = load_preflight()
    result = module.preflight(
        root=fixture.root, drive=None, peak_bytes=0,
        evidence={"release": RELEASE, "receipts": signed_receipts(fixture),
                  "trustKeys": ["release-key-1.json"]},
        policy=fixture.snapshot, clock=fixture.clock)
    assert result["provenCapabilities"] == []
    assert "receipt_verification_unavailable" in result["reasons"]


def test_evidence_for_another_release_is_refused(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    module = load_preflight()
    result = module.preflight(
        root=fixture.root, drive=None, peak_bytes=0,
        evidence={"release": "r1-2026.10", "receipts": signed_receipts(fixture)},
        policy=fixture.snapshot, clock=fixture.clock)
    assert result["provenCapabilities"] == []
    assert "receipt_verification_unavailable" in result["reasons"]


def test_missing_policy_reports_a_policy_reason_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(receipt_policy, "REALMS", {"test": tmp_path / "absent"})
    monkeypatch.setattr(receipt_policy, "host_identity", lambda: "host-1")
    result = run_preflight(SimpleNamespace(root=tmp_path, snapshot=None, clock=Clock()), {})
    assert "receipt_policy_unavailable" in result["reasons"]
    assert result["provenCapabilities"] == []


def test_clock_must_be_authenticated_for_verification(tmp_path, monkeypatch):
    """A window wider than the authentication bound is refused, not silently accepted."""
    fixture = policy_fixture(tmp_path, monkeypatch)
    wide = Clock()
    wide.window = wide.window[0], wide.window[1] + 5_000_000
    with pytest.raises(ValueError):
        receipts_app.verify_evidence(fixture.snapshot,
                                     {"release": RELEASE, "receipts": signed_receipts(fixture)},
                                     clock=wide)


def test_cli_without_a_policy_reports_unproven_capabilities(tmp_path):
    result = cli(tmp_path, "--profile", "test", "--release", RELEASE)
    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["provenCapabilities"] == []
    assert "receipt_policy_unavailable" in payload["reasons"]


def test_cli_evidence_containing_trust_keys_is_refused(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({"release": RELEASE,
                                    "receipts": signed_receipts(fixture),
                                    "trustKeys": ["release-key-1.json"]}))
    result = cli(tmp_path, "--profile", "test", "--release", RELEASE, "--evidence", str(evidence))
    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["reasons"] == ["evidence_invalid_or_contains_trust"]


def test_cli_evidence_for_another_release_is_refused(tmp_path, monkeypatch):
    fixture = policy_fixture(tmp_path, monkeypatch)
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({"release": "r1-2026.10",
                                    "receipts": signed_receipts(fixture)}))
    result = cli(tmp_path, "--profile", "test", "--release", RELEASE, "--evidence", str(evidence))
    assert json.loads(result.stdout)["reasons"] == ["evidence_invalid_or_contains_trust"]


def test_cli_evidence_must_be_a_json_object(tmp_path):
    (tmp_path / "evidence.json").write_text(json.dumps(["not", "an", "object"]))
    result = cli(tmp_path, "--profile", "test", "--release", RELEASE,
                 "--evidence", str(tmp_path / "evidence.json"))
    assert json.loads(result.stdout)["reasons"] == ["evidence_invalid_or_contains_trust"]


def test_cli_evidence_file_must_be_canonical_json(tmp_path):
    (tmp_path / "evidence.json").write_text('{"release": "' + RELEASE + '", }')
    result = cli(tmp_path, "--profile", "test", "--release", RELEASE,
                 "--evidence", str(tmp_path / "evidence.json"))
    assert json.loads(result.stdout)["reasons"] == ["evidence_invalid_or_contains_trust"]


def test_preflight_signature_takes_policy_instead_of_a_trust_file():
    """The preflight interface must not regress to caller-supplied trust."""
    parameters = load_preflight().preflight.__annotations__
    assert "policy" in parameters and "evidence" in parameters
    assert "trust" not in parameters
