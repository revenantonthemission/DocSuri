"""Bounded, duplicate-free JSON, RFC 8785 canonicalization and purpose-bound signatures."""

import base64
import hashlib
import json

import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

MAX_BYTES = 16 * 1024 * 1024
MAX_DEPTH = 64


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-finite JSON number")


def _validate(value, depth=0):
    if depth > MAX_DEPTH:
        raise ValueError("JSON nesting limit")
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object key must be a string")
            _validate(key, depth + 1)
            _validate(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _validate(item, depth + 1)


def decode(data: bytes, *, max_bytes: int = MAX_BYTES):
    if len(data) > max_bytes:
        raise ValueError("JSON byte limit")
    try:
        value = json.loads(
            data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant
        )
        _validate(value)
        rfc8785.dumps(value)  # rejects unsafe integers, NaN, Infinity and invalid Unicode
        return value
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("invalid JSON encoding or depth") from exc


def canonical(value) -> bytes:
    _validate(value)
    result = rfc8785.dumps(value)
    if len(result) > MAX_BYTES:
        raise ValueError("JSON byte limit")
    return result


def sign(payload: dict, *, kind: str, purpose: str, key_id: str, key: Ed25519PrivateKey) -> dict:
    envelope = {
        "version": 1,
        "domain": "docsuri.rem1",
        "kind": kind,
        "purpose": purpose,
        "keyId": key_id,
        "payload": payload,
    }
    signature = key.sign(canonical(envelope))
    return {**envelope, "signature": base64.urlsafe_b64encode(signature).decode().rstrip("=")}


def verify(envelope: dict, *, kind: str, purpose: str, key_id: str, key: Ed25519PublicKey) -> dict:
    if set(envelope) != {"version", "domain", "kind", "purpose", "keyId", "payload", "signature"}:
        raise ValueError("invalid signed envelope")
    unsigned = {k: v for k, v in envelope.items() if k != "signature"}
    if (
        type(unsigned["version"]) is not int
        or unsigned["version"] != 1
        or unsigned["domain"] != "docsuri.rem1"
        or unsigned["kind"] != kind
        or unsigned["purpose"] != purpose
        or unsigned["keyId"] != key_id
    ):
        raise ValueError("signature purpose mismatch")
    raw = envelope["signature"]
    if not isinstance(raw, str) or "=" in raw:
        raise ValueError("invalid signature encoding")
    signature = base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True)
    if len(signature) != 64 or base64.urlsafe_b64encode(signature).decode().rstrip("=") != raw:
        raise ValueError("noncanonical signature")
    key.verify(signature, canonical(unsigned))
    return unsigned["payload"]
