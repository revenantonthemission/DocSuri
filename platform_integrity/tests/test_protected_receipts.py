"""Real signatures, independent policy and adversarial clock/authority transitions."""

import json
import os
import stat
import time
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from docsuri_platform_integrity.adapters import receipt_signer
from docsuri_platform_integrity.adapters.nts import NativeTime
from docsuri_platform_integrity.application import receipts
from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import ValidityWindow
from docsuri_platform_integrity.deployment import receipt_policy
from docsuri_platform_integrity.deployment.capability import Outcome
from docsuri_platform_integrity.deployment.launchd import protected_bytes
from docsuri_platform_integrity.deployment.receipt import Capability, Receipt, issue, trust_key
from docsuri_platform_integrity.deployment.receipt_policy import (
    ClockReference,
    PolicySnapshot,
    ReceiptPolicy,
    ReceiptScope,
    ReceiptSignerReference,
)

NTS = Capability.NTS_CLOCK
D = digest(b"clock-config")
NOW = 1_790_000_000_000_000
DAY = 86_400_000_000


class Clock:
    def __init__(self, lower=NOW, upper=NOW + 100):
        self.window = lower, upper
        self.epoch = "boot", "resume"
        self.elapsed = 1000

    def __call__(self):
        return self.window

    def context(self):
        return NativeTime(self.elapsed, 0, *self.epoch)


@pytest.fixture
def protected(tmp_path, monkeypatch):
    root = tmp_path / "realm"
    (root / "sign").mkdir(parents=True, mode=0o700)
    (root / "receipt-policy").mkdir()
    uid, gid = os.getuid(), os.getgid()
    monkeypatch.setattr(receipt_policy, "REALMS", {"test": root})
    monkeypatch.setattr(receipt_signer, "REALMS", {"test": root})
    key = Ed25519PrivateKey.generate()
    keychain = receipt_policy.keychain_path("test", "r1.test", "receipt-key-1")
    keychain.write_bytes(b"encrypted-keychain-fixture")
    keychain.chmod(0o600)
    policy = ReceiptPolicy(
        profile="test", release="r1.test", host="host-1",
        clock=ClockReference(frame=str(root / "clock-public/current.json"), writer_uid=uid + 1,
                             config_digest=D),
        signer=ReceiptSignerReference(uid=uid, gid=gid, key_id="receipt-key-1",
                                      keychain=str(keychain),
                                      service="org.docsuri.rem1.test.receipt-signing",
                                      account="r1.test/receipt-key-1"),
        trust_keys=(trust_key("receipt-key-1", key.public_key(), validity=ValidityWindow(
            valid_from=str(NOW - DAY), valid_until=str(NOW + 30 * DAY))),),
        scopes=(ReceiptScope(capability=NTS, artifact=D),),
    ).validate_bindings()
    path = receipt_policy.policy_path("test", policy.release)
    data = canonical(policy.model_dump(mode="json"))
    path.write_bytes(data)
    path.chmod(0o444)
    # Root ownership/account provisioning alone are substituted for the unprivileged suite.
    monkeypatch.setattr(receipt_policy, "protected_chain", lambda path: None)
    monkeypatch.setattr(receipt_policy, "protected_bytes",
                        lambda path, **kw: protected_bytes(path, owner=uid, **kw))
    monkeypatch.setattr(receipt_policy, "verify_accounts", lambda value: None)
    monkeypatch.setattr(receipt_policy, "host_identity", lambda: "host-1")
    monkeypatch.setattr(receipt_signer, "kernel_groups", lambda: (gid,))

    class Reader:
        def __init__(self, path):
            self.path = path

        def get(self, service, account):
            assert self.path == keychain and service == policy.signer.service
            assert account == policy.signer.account
            return key.private_bytes_raw()

    snapshot = receipt_policy.load_policy("test", "r1.test")
    signer = receipt_signer.KeychainReceiptSigner(policy, reader_factory=Reader,
                                                  encryption_check=lambda: True)
    return SimpleNamespace(root=root, key=key, policy=policy, snapshot=snapshot, signer=signer,
                           clock=Clock(), path=path, raw=data, keychain=keychain)


def outcome(artifact=D, proven=True):
    return Outcome(capability=NTS, proven=proven, reason="verified", artifact=artifact,
                   evidence=digest(b"live-observation"))


def issue_now(p, probe=None, **kwargs):
    return receipts.issue_protected(p.snapshot, probe or (lambda window: {NTS: outcome()}),
                                    clock=p.clock, signer=p.signer, publish=lambda *args: None,
                                    **kwargs)


def evidence(envelopes):
    return {"release": "r1.test",
            "receipts": {key.value: value for key, value in envelopes.items()}}


def test_actual_keychain_signer_crypto_roundtrip_uses_trusted_time(protected, monkeypatch):
    def forbidden():
        pytest.fail("protected path used local wall time")

    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "time_ns", forbidden)
    envelopes = issue_now(protected)
    assert envelopes[NTS]["payload"]["validity"]["valid_from"] == str(NOW)
    proven, reasons = receipts.verify_evidence(protected.snapshot, evidence(envelopes),
                                               clock=protected.clock)
    assert proven == frozenset({"nts_clock"})
    assert set(reasons.values()) == {"not_configured"}


def test_evidence_cannot_supply_its_own_trust(protected):
    supplied = evidence(issue_now(protected))
    supplied["trustKeys"] = ["attacker.json"]
    with pytest.raises(ValueError, match="only matching"):
        receipts.verify_evidence(protected.snapshot, supplied, clock=protected.clock)


def test_signer_rejects_other_keychain_key(protected):
    class WrongKey:
        def __init__(self, path):
            pass

        def get(self, *args):
            return Ed25519PrivateKey.generate().private_bytes_raw()

    protected.signer.reader_factory = WrongKey
    with pytest.raises(PermissionError, match="purpose signing key"):
        issue_now(protected)


def test_signing_key_failure_names_its_underlying_cause(protected):
    """A bare "unavailable" cannot be acted on.

    A locked keychain, an ACL refusing the interpreter and a key that does not match the
    policy all surface as one indistinguishable reason unless the cause is carried, which has
    already cost a diagnosis cycle on the live host.
    """
    protected.signer.reader_factory = lambda path: (_ for _ in ()).throw(
        PermissionError("User interaction is not allowed"))
    with pytest.raises(PermissionError) as raised:
        issue_now(protected)
    message = str(raised.value)
    assert "purpose signing key unavailable" in message
    assert "PermissionError" in message
    assert "User interaction is not allowed" in message
    assert isinstance(raised.value.__cause__, PermissionError)


@pytest.mark.parametrize("failure", ["locked", "filevault", "mode", "group", "root"])
def test_unavailable_or_wrong_role_signer_cannot_sign(protected, monkeypatch, failure):
    if failure == "locked":
        protected.signer.reader_factory = lambda path: (_ for _ in ()).throw(
            PermissionError("locked"))
    elif failure == "filevault":
        protected.signer.encryption_check = lambda: False
    elif failure == "mode":
        protected.keychain.chmod(0o644)
    elif failure == "group":
        monkeypatch.setattr(receipt_signer, "kernel_groups", lambda: (os.getgid(), 12))
    else:
        monkeypatch.setattr(receipt_signer.os, "geteuid", lambda: 0)
    with pytest.raises(PermissionError):
        issue_now(protected)


def test_unproven_or_wrong_artifact_never_reads_signing_key(protected):
    protected.signer.reader_factory = lambda path: pytest.fail("read unneeded private key")
    for result in (outcome(proven=False), outcome(artifact=digest(b"another-config"))):
        with pytest.raises(PermissionError, match="not proven"):
            issue_now(protected, lambda window, result=result: {NTS: result})


@pytest.mark.parametrize("change", ["policy", "resume", "deadline", "clock"])
def test_mid_probe_authority_or_clock_change_cannot_publish(protected, change):
    def probe(window):
        if change == "policy":
            protected.path.chmod(0o644)
            protected.path.write_bytes(b"{}")
            protected.path.chmod(0o444)
        elif change == "resume":
            protected.clock.epoch = "boot", "another-resume"
        elif change == "deadline":
            protected.clock.elapsed += 30_000_000_000
        else:
            protected.clock.window = 0, 3_000_000
        return {NTS: outcome()}

    with pytest.raises((PermissionError, ValueError)):
        issue_now(protected, probe)


def test_policy_cannot_be_selected_from_evidence_or_cross_host(protected, monkeypatch):
    with pytest.raises(ValueError):
        receipt_policy.load_policy("test", "../r1.test")
    monkeypatch.setattr(receipt_policy, "host_identity", lambda: "another-host")
    with pytest.raises(PermissionError, match="host or release"):
        receipt_policy.load_policy("test", "r1.test")


def test_policy_refuses_writable_and_symlinked_trust(protected):
    protected.path.chmod(0o666)
    with pytest.raises(PermissionError):
        receipt_policy.load_policy("test", "r1.test")
    protected.path.unlink()
    protected.path.symlink_to(protected.keychain)
    with pytest.raises(OSError):
        receipt_policy.load_policy("test", "r1.test")


def test_artifact_mismatch_in_a_genuine_signature_is_unproven(protected):
    value = Receipt(capability=NTS, host="host-1", release="r1.test",
                    validity=ValidityWindow(valid_from=str(NOW), valid_until=str(NOW + DAY)),
                    artifact=digest(b"wrong"), evidence=D)
    envelope = issue(value, key_id="receipt-key-1", key=protected.key)
    proven, reasons = receipts.verify_evidence(protected.snapshot, evidence({NTS: envelope}),
                                               clock=protected.clock)
    assert not proven and reasons["nts_clock"] == "artifact_mismatch"


@settings(max_examples=2000, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(offset=st.integers(min_value=-1000, max_value=DAY + 1000),
       width=st.integers(min_value=0, max_value=2_000_000))
def test_property_verification_requires_the_entire_authenticated_window(protected, offset, width):
    value = Receipt(capability=NTS, host="host-1", release="r1.test",
                    validity=ValidityWindow(valid_from=str(NOW), valid_until=str(NOW + DAY)),
                    artifact=D, evidence=D)
    envelope = issue(value, key_id="receipt-key-1", key=protected.key)
    protected.clock.window = NOW + offset, NOW + offset + width
    proven, _ = receipts.verify_evidence(protected.snapshot, evidence({NTS: envelope}),
                                         clock=protected.clock)
    assert ("nts_clock" in proven) == (0 <= offset and offset + width < DAY)


def test_policy_roundtrip_remains_exact(protected):
    parsed = ReceiptPolicy.model_validate_json(json.dumps(protected.policy.model_dump(mode="json")))
    assert parsed == protected.policy
    assert isinstance(protected.snapshot, PolicySnapshot)


def protected_output(policy_fixture):
    """A signer-owned 0755 public directory under the fixture realm, as root would create."""
    directory = receipt_policy.output_directory("test", policy_fixture.policy.release)
    if not directory.exists():
        for parent in (directory.parent, *directory.parents):
            if not parent.exists():
                parent.mkdir(parents=True, mode=0o755)
        directory.mkdir(mode=0o755)
    return directory


def test_publication_writes_readonly_receipts_and_leaves_no_temporary(protected):
    directory = protected_output(protected)
    envelopes = issue_now(protected)
    receipts.publish_receipts(protected.snapshot, envelopes)
    written = directory / "nts_clock.receipt.json"
    assert [p.name for p in directory.iterdir()] == ["nts_clock.receipt.json"]
    assert stat.S_IMODE(written.lstat().st_mode) == 0o444
    assert json.loads(written.read_bytes()) == envelopes[NTS]
    # Republishing replaces atomically and still leaves exactly one file.
    receipts.publish_receipts(protected.snapshot, envelopes)
    assert [p.name for p in directory.iterdir()] == ["nts_clock.receipt.json"]


@pytest.mark.parametrize("mode", [0o700, 0o775, 0o757])
def test_publication_refuses_an_unprotected_output_directory(protected, mode):
    directory = protected_output(protected)
    directory.chmod(mode)
    with pytest.raises(PermissionError, match="output directory"):
        receipts.publish_receipts(protected.snapshot, {NTS: {"payload": {}, "signature": "x"}})


def test_publication_refuses_to_overwrite_a_foreign_receipt(protected):
    directory = protected_output(protected)
    planted = directory / "nts_clock.receipt.json"

    def writable(path):
        path.write_bytes(b"{}")
        path.chmod(0o666)

    def hardlinked(path):
        path.unlink(missing_ok=True)
        os.link(protected.keychain, path)

    def symlinked(path):
        path.unlink(missing_ok=True)
        path.symlink_to(protected.keychain)

    for description, damage in (("writable", writable), ("hardlinked", hardlinked),
                                ("symlinked", symlinked)):
        damage(planted)
        with pytest.raises(PermissionError, match="existing receipt"):
            receipts.publish_receipts(protected.snapshot, {NTS: {"payload": {}, "signature": "x"}})
        assert not list(directory.glob(".receipt-*")), description


@pytest.mark.parametrize("seconds", [0, -1, 7 * 86400 + 1, "86400", True])
def test_receipt_duration_beyond_release_policy_is_refused(protected, seconds):
    with pytest.raises((ValueError, TypeError)):
        issue_now(protected, seconds=seconds)


def test_requested_capability_outside_policy_is_refused(protected):
    with pytest.raises(PermissionError, match="outside release policy"):
        receipts.requested_capabilities(protected.policy, [Capability.RESTORE_RECEIPT])
    with pytest.raises(PermissionError, match="outside release policy"):
        receipts.requested_capabilities(protected.policy, [NTS, NTS])
    assert receipts.requested_capabilities(protected.policy) == (NTS,)
