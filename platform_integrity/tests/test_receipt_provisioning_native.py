"""End to end on this host: purpose Keychain -> real signature -> published -> verified.

Every security-relevant step is the production one. Only the identity root, the installed
clock and FileVault are substituted, because an unprivileged suite cannot create a realm
owned by root or run chronyd; the receipt path itself is real.
"""

import json
import os
import secrets
import stat
import sys
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from docsuri_platform_integrity.adapters import receipt_signer
from docsuri_platform_integrity.adapters.keychain_provisioning import (
    KeychainOperationError,
    NativeKeychain,
)
from docsuri_platform_integrity.adapters.nts import NativeTime
from docsuri_platform_integrity.application import receipts
from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import ValidityWindow
from docsuri_platform_integrity.deployment import receipt_policy
from docsuri_platform_integrity.deployment.capability import Outcome
from docsuri_platform_integrity.deployment.launchd import protected_bytes
from docsuri_platform_integrity.deployment.receipt import Capability, trust_key
from docsuri_platform_integrity.deployment.receipt_policy import (
    ClockReference,
    ReceiptPolicy,
    ReceiptScope,
    ReceiptSignerReference,
)

NTS = Capability.NTS_CLOCK
D = digest(b"clock-config")
NOW = 1_790_000_000_000_000
DAY = 86_400_000_000
RELEASE = "r1.native"
KEY_ID = "receipt-key-1"


class Clock:
    def __init__(self):
        self.window = NOW, NOW + 100
        self.elapsed = 1000

    def __call__(self):
        return self.window

    def context(self):
        return NativeTime(self.elapsed, 0, "boot", "resume")


@pytest.fixture
def native(tmp_path, monkeypatch):
    if sys.platform != "darwin":
        pytest.skip("native Security.framework required")
    root = tmp_path / "realm"
    (root / "sign").mkdir(parents=True, mode=0o700)
    (root / "receipt-policy").mkdir(mode=0o755)
    uid, gid = os.getuid(), os.getgid()
    monkeypatch.setattr(receipt_policy, "REALMS", {"test": root})
    monkeypatch.setattr(receipt_signer, "REALMS", {"test": root})
    monkeypatch.setattr(receipt_policy, "protected_chain", lambda path: None)
    monkeypatch.setattr(receipt_policy, "protected_bytes",
                        lambda path, **kw: protected_bytes(path, owner=uid, **kw))
    monkeypatch.setattr(receipt_policy, "verify_accounts", lambda policy: None)
    monkeypatch.setattr(receipt_policy, "host_identity", lambda: "host-1")
    monkeypatch.setattr(receipt_signer, "kernel_groups", lambda: (gid,))

    key = Ed25519PrivateKey.generate()
    keychain = receipt_policy.keychain_path("test", RELEASE, KEY_ID)
    password = secrets.token_urlsafe(32)
    NativeKeychain().create(keychain, password, "org.docsuri.rem1.test.receipt-signing",
                            RELEASE + "/" + KEY_ID, key.private_bytes_raw(),
                            __import__("pathlib").Path(sys.executable))
    policy = ReceiptPolicy(
        profile="test", release=RELEASE, host="host-1",
        clock=ClockReference(frame=str(root / "clock-public/current.json"),
                             writer_uid=uid + 1, config_digest=D),
        signer=ReceiptSignerReference(uid=uid, gid=gid, key_id=KEY_ID, keychain=str(keychain),
                                      service="org.docsuri.rem1.test.receipt-signing",
                                      account=RELEASE + "/" + KEY_ID),
        trust_keys=(trust_key(KEY_ID, key.public_key(), validity=ValidityWindow(
            valid_from=str(NOW - DAY), valid_until=str(NOW + 30 * DAY))),),
        scopes=(ReceiptScope(capability=NTS, artifact=D),),
    ).validate_bindings()
    path = receipt_policy.policy_path("test", RELEASE)
    path.write_bytes(canonical(policy.model_dump(mode="json")))
    path.chmod(0o444)
    directory = receipt_policy.output_directory("test", RELEASE)
    directory.mkdir(parents=True, mode=0o755)
    yield SimpleNamespace(root=root, key=key, keychain=keychain, password=password, policy=policy,
                          path=path, directory=directory, clock=Clock(),
                          snapshot=receipt_policy.load_policy("test", RELEASE),
                          manager=NativeKeychain())
    if keychain.exists():
        keychain.chmod(0o600)
        NativeKeychain().delete_disposable(keychain)


def outcome():
    return Outcome(capability=NTS, proven=True, reason="verified", artifact=D,
                   evidence=digest(b"live-observation"))


def test_a_purpose_keychain_produces_a_receipt_any_reader_can_verify(native):
    """The whole path on this host: locked Keychain item, unlocked once, signed, published."""
    signer = receipt_signer.KeychainReceiptSigner(native.policy, encryption_check=lambda: True)
    # A locked keychain cannot sign: the signer must not fall back to any other source.
    native.manager.lock(native.keychain)
    with pytest.raises(PermissionError, match="purpose signing key"):
        receipts.issue_protected(
            native.snapshot, lambda window: {NTS: outcome()}, clock=native.clock,
            signer=signer, publish=lambda *args: None)
    assert not list(native.directory.iterdir()), "a refused issuance writes nothing"
    native.manager.unlock(native.keychain, native.password)
    envelopes = receipts.issue_protected(
        native.snapshot, lambda window: {NTS: outcome()}, clock=native.clock, signer=signer)
    written = native.directory / "nts_clock.receipt.json"
    assert [p.name for p in native.directory.iterdir()] == ["nts_clock.receipt.json"]
    assert stat.S_IMODE(written.lstat().st_mode) == 0o444
    assert json.loads(written.read_bytes()) == envelopes[NTS]
    proven, reasons = receipts.verify_evidence(
        native.snapshot, {"release": RELEASE, "receipts": {NTS.value: envelopes[NTS]}},
        clock=native.clock)
    assert proven == frozenset({NTS.value})
    assert set(reasons.values()) == {"not_configured"}
    # A different key in the same purpose slot yields a receipt the policy will not accept.
    foreign = Ed25519PrivateKey.generate()
    with pytest.raises(PermissionError, match="purpose signing key"):
        receipts.issue_protected(
            native.snapshot, lambda window: {NTS: outcome()}, clock=native.clock,
            signer=receipt_signer.KeychainReceiptSigner(
                native.policy.model_copy(update={"trust_keys": (trust_key(
                    KEY_ID, foreign.public_key(), validity=ValidityWindow(
                        valid_from=str(NOW - DAY), valid_until=str(NOW + 30 * DAY))),)}),
                encryption_check=lambda: True),
            publish=lambda *args: None)


def test_a_wrong_keychain_password_cannot_unlock(native):
    with pytest.raises(KeychainOperationError) as refused:
        native.manager.unlock(native.keychain, secrets.token_urlsafe(32))
    assert refused.value.status != 0


def test_the_realm_layout_matches_what_the_signer_expects(native):
    """The provisioner layout must satisfy every path check the signer performs."""
    receipt_signer.verify_keychain_path(native.policy)
    assert stat.S_IMODE(native.keychain.lstat().st_mode) == 0o600
    assert stat.S_IMODE((native.root / "sign").lstat().st_mode) == 0o700
    native.keychain.chmod(0o644)
    with pytest.raises(PermissionError, match="unprotected"):
        receipt_signer.verify_keychain_path(native.policy)
