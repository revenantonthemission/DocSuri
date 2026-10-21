"""Sealed Notion tokens: bound to one connection revision, fresh nonces, no secret text."""

from uuid import uuid4

import pytest
from backend.modules.export.errors import ProtectionUnavailable
from backend.modules.export.token_keyring import TokenKeyring
from backend.modules.export.token_vault import (
    ENVELOPE_TAG,
    NONCE_BYTES,
    TokenVault,
    envelope_version,
)

TOKEN = "synthetic-vault-token-" + uuid4().hex


class Witness:
    def token_key_counts(self):
        return []


@pytest.fixture
def keyring(tmp_path):
    root = tmp_path / "export-keys"
    root.mkdir(mode=0o700)
    return TokenKeyring(root, "u6-vault-test", Witness())


@pytest.fixture
def binding():
    return {"account_id": uuid4(), "connection_id": uuid4(), "revision": 1}


def refused(call, category: str) -> ProtectionUnavailable:
    with pytest.raises(ProtectionUnavailable) as raised:
        call()
    error = raised.value
    assert str(error) == category and TOKEN not in str(error) and TOKEN not in repr(error)
    assert error.__cause__ is None and error.__context__ is None
    return error


def test_seal_and_open_round_trip_in_the_dse1_layout(keyring, binding):
    vault = TokenVault(keyring)
    envelope, version = vault.seal(TOKEN, **binding)
    assert envelope.startswith(ENVELOPE_TAG) and envelope[4] == len(version)
    assert envelope[5 : 5 + len(version)].decode() == version
    assert TOKEN.encode() not in envelope
    assert vault.open(envelope, **binding) == TOKEN


def test_the_version_column_equals_the_envelopes_version(keyring, binding):
    envelope, version = TokenVault(keyring).seal(TOKEN, **binding)
    assert envelope_version(envelope) == version == keyring.load()["active"]


@pytest.mark.parametrize("field", ["account_id", "connection_id", "revision"])
def test_an_envelope_copied_to_another_binding_fails_to_open(keyring, binding, field):
    vault = TokenVault(keyring)
    envelope, _ = vault.seal(TOKEN, **binding)
    moved = {**binding, field: 2 if field == "revision" else uuid4()}
    refused(lambda: vault.open(envelope, **moved), "envelope-unopenable")


def test_every_seal_gets_a_fresh_nonce(keyring, binding):
    vault = TokenVault(keyring)
    envelopes = [vault.seal(TOKEN, **binding)[0] for _ in range(40)]
    offset = 5 + envelopes[0][4]
    nonces = {envelope[offset : offset + NONCE_BYTES] for envelope in envelopes}
    assert len(nonces) == len(envelopes) and len(set(envelopes)) == len(envelopes)


def test_the_next_seal_and_open_see_a_rotation_and_a_retirement(keyring, binding):
    vault = TokenVault(keyring)
    old, old_version = vault.seal(TOKEN, **binding)
    with keyring.holding() as held:
        held.rotate()
    new, new_version = vault.seal(TOKEN, **binding)
    assert new_version != old_version and new_version == keyring.load()["active"]
    assert vault.open(old, **binding) == vault.open(new, **binding) == TOKEN
    with keyring.holding() as held:
        held.retire(old_version)
    refused(lambda: vault.open(old, **binding), "key-version-unavailable")


def test_tampered_and_malformed_envelopes_carry_no_secret_text(keyring, binding):
    vault = TokenVault(keyring)
    envelope, version = vault.seal(TOKEN, **binding)
    tampered = envelope[:-1] + bytes([envelope[-1] ^ 1])
    refused(lambda: vault.open(tampered, **binding), "envelope-unopenable")
    for malformed in (
        b"",
        b"DSE1",
        b"DSC2" + envelope[4:],
        envelope[:4] + bytes([0]) + envelope[5:],
        envelope[:5] + b"x" * len(version) + envelope[5 + len(version) :],
        envelope[: 5 + len(version) + NONCE_BYTES],
        "not bytes",
    ):
        refused(lambda value=malformed: vault.open(value, **binding), "envelope-malformed")


@pytest.mark.parametrize(
    "change",
    [{"revision": 0}, {"revision": True}, {"account_id": "not-a-uuid"}, {"connection_id": None}],
)
def test_an_invalid_binding_is_refused_before_any_key_is_read(keyring, binding, change):
    vault = TokenVault(keyring)
    refused(lambda: vault.seal(TOKEN, **{**binding, **change}), "envelope-binding-invalid")
    assert list(keyring.root.iterdir()) == []


def test_an_empty_token_and_unavailable_custody_are_refused(keyring, binding):
    vault = TokenVault(keyring)
    refused(lambda: vault.seal("", **binding), "token-invalid")
    envelope, _ = vault.seal(TOKEN, **binding)
    keyring.root.chmod(0o755)
    try:
        refused(lambda: vault.seal(TOKEN, **binding), "key-folder-unavailable")
        refused(lambda: vault.open(envelope, **binding), "key-folder-unavailable")
    finally:
        keyring.root.chmod(0o700)
