"""A capability claim is only acceptance when a trusted, host-bound receipt proves it."""

import base64
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from docsuri_platform_integrity.contracts.codec import canonical, decode
from docsuri_platform_integrity.contracts.models import ValidityWindow
from docsuri_platform_integrity.deployment.receipt import (
    MAX_WINDOW_US,
    Capability,
    Receipt,
    host_identity,
    issue,
    receipt_digest,
    trust_key,
    verify_capabilities,
    verify_capability,
)

HOST = "11111111-2222-3333-4444-555555555555"
OTHER_HOST = "99999999-9999-9999-9999-999999999999"
RELEASE = "r1-2026.09"
DAY = 86400 * 1_000_000
SIGNING = Ed25519PrivateKey.generate()
TRUST_ID = "release-key-1"


def window(start_us, days=1):
    return ValidityWindow(valid_from=str(start_us), valid_until=str(start_us + days * DAY))


def trust(*, revoked=False, key_id=TRUST_ID, key=SIGNING, start_us=None, days=30):
    return {
        key_id: trust_key(
            key_id, key.public_key(),
            validity=window(start_us if start_us is not None else current_us() - DAY, days),
            revoked=revoked,
        ),
    }


def current_us():
    return int(time.time() * 1_000_000)


def receipt(capability=Capability.NTS_CLOCK, *, host=HOST, release=RELEASE, now=None,
            days=1):
    return Receipt(
        capability=capability,
        host=host,
        release=release,
        validity=window(now if now is not None else current_us(), days),
        artifact="sha256:" + "a" * 64,
        evidence="sha256:" + "b" * 64,
    )


def envelope_for(capability=Capability.NTS_CLOCK, *, key=SIGNING, key_id=TRUST_ID, **kwargs):
    return issue(receipt(capability, **kwargs), key_id=key_id, key=key)


def prove(envelope, capability, **kwargs):
    lower = kwargs.pop("lower", current_us())
    return verify_capability(
        envelope, capability=capability, host=kwargs.pop("host", HOST),
        release=kwargs.pop("release", RELEASE), trust=kwargs.pop("trust", trust()),
        lower=lower, upper=lower,
    )


def test_valid_receipt_proves_its_own_capability():
    assert prove(envelope_for(), Capability.NTS_CLOCK) == (True, "verified")


def test_receipt_does_not_prove_a_different_capability():
    assert prove(envelope_for(), Capability.TLS_ROLES) == (False, "capability_mismatch")


def test_absent_receipt_is_not_proof():
    assert prove(None, Capability.NTS_CLOCK) == (False, "malformed")


@pytest.mark.parametrize("envelope", ["{}", {"keyId": 1}, [], "signed", 7])
def test_non_envelope_is_rejected(envelope):
    assert prove(envelope, Capability.NTS_CLOCK)[0] is False


def test_self_signed_key_is_untrusted():
    envelope = envelope_for(key=Ed25519PrivateKey.generate(), key_id="stranger-key")
    assert prove(envelope, Capability.NTS_CLOCK)[1] == "untrusted_key"


def test_own_key_is_untrusted_without_the_release_manifest():
    """Signing alone proves nothing; only the manifest's trust list counts."""
    assert prove(envelope_for(), Capability.NTS_CLOCK, trust={})[1] == "untrusted_key"


def test_revoked_trust_key_cannot_prove():
    assert prove(envelope_for(), Capability.NTS_CLOCK, trust=trust(revoked=True))[1] == (
        "revoked_key")


def test_key_outside_its_window_cannot_prove():
    assert prove(envelope_for(), Capability.NTS_CLOCK, trust=trust(start_us=0, days=1))[1] == (
        "key_not_valid_at_observation")


def test_tampered_payload_fails_the_signature():
    envelope = envelope_for()
    envelope["payload"]["host"] = OTHER_HOST
    assert prove(envelope, Capability.NTS_CLOCK) == (False, "signature_invalid")


def test_tampered_signature_fails():
    envelope = envelope_for()
    raw = bytearray(base64.urlsafe_b64decode(
        envelope["signature"] + "=" * (-len(envelope["signature"]) % 4)))
    raw[0] ^= 0xFF
    envelope["signature"] = base64.urlsafe_b64encode(bytes(raw)).decode().rstrip("=")
    assert prove(envelope, Capability.NTS_CLOCK) == (False, "signature_invalid")


def test_receipt_for_another_host_is_rejected():
    """The exact attack a copied receipt file enables."""
    assert prove(envelope_for(host=OTHER_HOST), Capability.NTS_CLOCK) == (False, "host_mismatch")


def test_receipt_for_another_release_is_rejected():
    assert prove(envelope_for(release="r1-2026.10"), Capability.NTS_CLOCK) == (
        False, "release_mismatch")


def test_expired_receipt_is_rejected():
    stale = current_us() - 3 * DAY
    assert prove(envelope_for(now=stale, days=1), Capability.NTS_CLOCK) == (
        False, "outside_validity")


def test_not_yet_valid_receipt_is_rejected():
    future = current_us() + 3 * DAY
    assert prove(envelope_for(now=future, days=1), Capability.NTS_CLOCK) == (
        False, "outside_validity")


def test_permanent_receipt_is_refused():
    assert prove(envelope_for(days=30), Capability.NTS_CLOCK) == (False, "window_too_long")


def test_receipt_window_is_bounded_at_the_contract_limit():
    assert prove(envelope_for(days=7), Capability.NTS_CLOCK)[0] is True
    assert MAX_WINDOW_US == 7 * 86400 * 1_000_000


def test_payload_with_extra_fields_is_refused():
    envelope = envelope_for()
    envelope["payload"]["note"] = "looks fine to me"
    assert prove(envelope, Capability.NTS_CLOCK)[0] is False


def test_unsigned_boolean_evidence_is_not_a_receipt():
    assert prove({"native_commit_guard": True}, Capability.NATIVE_COMMIT_GUARD)[0] is False


def test_verify_capabilities_reports_every_unproven_reason():
    envelopes = {"nts_clock": envelope_for(), "tls_roles": envelope_for(Capability.TLS_ROLES)}
    proven, reasons = verify_capabilities(
        envelopes, host=HOST, release=RELEASE, trust=trust(),
        lower=current_us(), upper=current_us())
    assert proven == frozenset({"nts_clock", "tls_roles"})
    assert set(reasons) == {"native_commit_guard", "keychain_roles", "restore_receipt"}
    assert set(reasons.values()) == {"malformed"}


def test_all_capabilities_can_be_proven_together():
    envelopes = {c.value: envelope_for(c) for c in Capability}
    proven, reasons = verify_capabilities(
        envelopes, host=HOST, release=RELEASE, trust=trust(),
        lower=current_us(), upper=current_us())
    assert proven == frozenset(c.value for c in Capability)
    assert reasons == {}


def test_one_bad_receipt_does_not_poison_the_others():
    envelopes = {c.value: envelope_for(c) for c in Capability}
    envelopes["keychain_roles"] = envelope_for(Capability.KEYCHAIN_ROLES, host=OTHER_HOST)
    proven, reasons = verify_capabilities(
        envelopes, host=HOST, release=RELEASE, trust=trust(),
        lower=current_us(), upper=current_us())
    assert "keychain_roles" not in proven
    assert reasons == {"keychain_roles": "host_mismatch"}
    assert len(proven) == len(Capability) - 1


def test_receipt_digest_is_stable_and_content_addressed():
    moment = current_us()
    first = receipt_digest(envelope_for(now=moment))
    assert first == receipt_digest(envelope_for(now=moment))
    assert first != receipt_digest(envelope_for(now=moment, capability=Capability.TLS_ROLES))
    assert first.startswith("sha256:")


def test_signed_receipt_survives_a_canonical_round_trip():
    envelope = envelope_for()
    assert decode(canonical(envelope)) == envelope


def test_host_identity_is_this_machine_and_stable():
    identity = host_identity()
    assert len(identity) == 36 and identity == identity.upper()
    assert identity == host_identity()
    assert identity != HOST
