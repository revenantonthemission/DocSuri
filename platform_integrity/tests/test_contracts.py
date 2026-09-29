import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from hypothesis import given
from hypothesis import strategies as st

from docsuri_platform_integrity.contracts.codec import canonical, decode, sign, verify
from docsuri_platform_integrity.contracts.models import TargetRef, ValidityWindow


@given(st.from_regex(r"[a-z][a-z0-9]{0,30}", fullmatch=True))
def test_target_roundtrip_and_strict_fields(name):
    value = TargetRef(target_id=name, namespace="public", incarnation="install-1")
    assert TargetRef.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b"NaN",
        b"Infinity",
        b"9007199254740992",
        b'"\\ud800"',
        b"[" * 66 + b"]" * 66,
    ],
)
def test_rejects_ambiguous_json(raw):
    with pytest.raises(ValueError):
        decode(raw)


def test_canonical_utf16_order_and_exact_source_bytes():
    assert canonical({"z": 1, "a": "\u20ac"}) == '{"a":"€","z":1}'.encode()
    assert canonical({"n": "18446744073709551615"}) == b'{"n":"18446744073709551615"}'


def test_signature_is_bound_to_purpose_and_bytes():
    key = Ed25519PrivateKey.generate()
    envelope = sign({"target": "one"}, kind="receipt", purpose="observe", key_id="k1", key=key)
    assert verify(
        envelope, kind="receipt", purpose="observe", key_id="k1", key=key.public_key()
    ) == {"target": "one"}
    with pytest.raises(ValueError):
        verify(envelope, kind="approval", purpose="apply", key_id="k1", key=key.public_key())
    with pytest.raises(InvalidSignature):
        verify(
            {**envelope, "payload": {"target": "two"}},
            kind="receipt",
            purpose="observe",
            key_id="k1",
            key=key.public_key(),
        )


def test_expiry_window_never_adds_clock_grace():
    window = ValidityWindow(valid_from="100", valid_until="200")
    assert window.contains(100, 199)
    assert not window.contains(190, 200)
    assert not window.contains(99, 110)
