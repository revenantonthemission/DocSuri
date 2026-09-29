"""Signed, host-bound capability receipts for host acceptance.

A caller-supplied capability list is an assertion, not proof: anyone can write
``{"native_commit_guard": true}`` into a file. Acceptance requires an Ed25519 receipt
signed by a key the release manifest trusts, bound to *this* host, *this* release and
*this* capability, inside its validity window, and naming the artifact that was
verified. A receipt that is missing, self-signed, expired, copied from another machine
or for another release is not evidence and must leave the capability unproven.
"""

import base64
import re
import subprocess
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import Field

from ..contracts.codec import canonical, digest, sign, verify
from ..contracts.models import Digest, Ref, ValidityWindow, Value

KIND = "capability-receipt"
PURPOSE = "accept-host"
# A receipt may not outlive a week; a permanent "verified" flag is not acceptance.
MAX_WINDOW_US = 7 * 86400 * 1_000_000
_UUID = re.compile(r'"IOPlatformUUID"\s*=\s*"([0-9A-Fa-f-]{36})"')
# 32 raw bytes as unpadded base64url.
PublicKey = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{43}$")]


class Capability(StrEnum):
    NATIVE_COMMIT_GUARD = "native_commit_guard"
    NTS_CLOCK = "nts_clock"
    KEYCHAIN_ROLES = "keychain_roles"
    TLS_ROLES = "tls_roles"
    RESTORE_RECEIPT = "restore_receipt"


class Receipt(Value):
    """What an installer asserts after actually verifying the capability."""

    capability: Capability
    host: Ref
    release: Ref
    validity: ValidityWindow
    artifact: Digest
    evidence: Digest


class TrustKey(Value):
    """A key the release manifest trusts. This comes from the manifest, never the receipt.

    The public key is canonical unpadded base64url rather than raw bytes: a strict model
    cannot serialise binary to JSON, and a fixed-width text form also rejects any
    alternative encoding of the same key material.
    """

    key_id: Ref
    public_key: PublicKey
    validity: ValidityWindow
    revoked: bool

    def key(self) -> Ed25519PublicKey:
        raw = base64.urlsafe_b64decode(self.public_key + "=" * (-len(self.public_key) % 4))
        if len(raw) != 32:
            raise ValueError("invalid trust key material")
        return Ed25519PublicKey.from_public_bytes(raw)


def trust_key(key_id: str, public_key: Ed25519PublicKey, *, validity, revoked=False) -> TrustKey:
    """Build a trust entry from a live key, encoding the public key canonically."""
    raw = public_key.public_bytes_raw()
    return TrustKey(
        key_id=key_id,
        public_key=base64.urlsafe_b64encode(raw).decode().rstrip("="),
        validity=validity,
        revoked=revoked,
    )


def host_identity() -> str:
    """This machine's hardware platform UUID.

    A receipt issued for another host is not evidence for this one, so the host binding
    has to survive a reboot, a rename and a reinstall.
    """
    process = subprocess.run(
        ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
        capture_output=True, text=True, timeout=5, check=False,
    )
    if process.returncode:
        raise ValueError("host identity unavailable")
    match = _UUID.search(process.stdout)
    if match is None:
        raise ValueError("host identity unavailable")
    return match.group(1).upper()


def issue(receipt: Receipt, *, key_id: str, key: Ed25519PrivateKey) -> dict:
    """Installer side. The signature is bound to the payload by canonical JSON."""
    return sign(receipt.model_dump(mode="json"), kind=KIND, purpose=PURPOSE,
                key_id=key_id, key=key)


def verify_capability(
    envelope, *, capability: Capability, host: str, release: str,
    trust: Mapping[str, TrustKey], lower: int, upper: int,
) -> tuple[bool, str]:
    """Return (proven, reason). Unknown is not proven, and a reason is always returned."""
    if not isinstance(envelope, dict) or not isinstance(envelope.get("keyId"), str):
        return False, "malformed"
    key = trust.get(envelope["keyId"])
    if key is None:
        return False, "untrusted_key"
    if key.revoked:
        return False, "revoked_key"
    if not key.validity.contains(lower, upper):
        return False, "key_not_valid_at_observation"
    try:
        payload = verify(envelope, kind=KIND, purpose=PURPOSE,
                         key_id=key.key_id, key=key.key())
    except (ValueError, TypeError, InvalidSignature):
        return False, "signature_invalid"
    try:
        # Wire models validate from JSON bytes here: strict mode rejects the enum string
        # in a plain dict, and re-canonicalising also rejects a non-canonical encoding.
        receipt = Receipt.model_validate_json(canonical(payload))
    except Exception:
        return False, "payload_invalid"
    if receipt.capability != capability:
        return False, "capability_mismatch"
    if receipt.host != host:
        return False, "host_mismatch"
    if receipt.release != release:
        return False, "release_mismatch"
    if int(receipt.validity.valid_until) - int(receipt.validity.valid_from) > MAX_WINDOW_US:
        return False, "window_too_long"
    if not receipt.validity.contains(lower, upper):
        return False, "outside_validity"
    return True, "verified"


def verify_capabilities(
    envelopes: Mapping[str, object], *, host: str, release: str,
    trust: Mapping[str, TrustKey], lower: int, upper: int,
) -> tuple[frozenset[str], dict[str, str]]:
    """Prove each required capability. Anything unproven is reported with its own reason."""
    proven, reasons = set(), {}
    for capability in Capability:
        ok, reason = verify_capability(
            envelopes.get(capability.value), capability=capability, host=host,
            release=release, trust=trust, lower=lower, upper=upper,
        )
        if ok:
            proven.add(capability.value)
        else:
            reasons[capability.value] = reason
    return frozenset(proven), reasons


def receipt_digest(envelope) -> str:
    """Content address of a signed receipt, for the release manifest."""
    return digest(canonical(envelope))
