"""Sealing and opening of Notion tokens (security design §4.1, NFR3.1).

```text
envelope = "DSE1" | len(version) | version | nonce (12 random bytes) | AES-256-GCM(token)+tag
AAD      = "u6-notion-token:" + version + ":" + accountId + ":" + connectionId + ":" + revision
```

The AAD binds the envelope to one account, connection and connection revision, so an
envelope copied to another row, account or revision fails to open. A fresh nonce comes
from the operating system's random source on every seal. Keys are read from the keyring
on every call, so the next operation sees a rotation.

Every fault raises `ProtectionUnavailable` with a fixed category and no cause or context,
so no token, key or provider text can travel with it.
"""

from __future__ import annotations

import secrets
from typing import Protocol
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.modules.export.errors import ProtectionUnavailable
from backend.modules.export.token_keyring import VERSION

ENVELOPE_TAG = b"DSE1"
NONCE_BYTES = 12
TAG_BYTES = 16
AAD_PREFIX = "u6-notion-token:"


class KeySource(Protocol):
    def key(self, version: str) -> bytes: ...

    def active_key(self) -> tuple[str, bytes]: ...


def _aad(version: str, account_id: UUID, connection_id: UUID, revision: int) -> bytes:
    return f"{AAD_PREFIX}{version}:{account_id}:{connection_id}:{revision}".encode("ascii")


def _check_binding(account_id, connection_id, revision) -> None:
    if (
        not isinstance(account_id, UUID)
        or not isinstance(connection_id, UUID)
        or type(revision) is not int
        or revision < 1
    ):
        raise ProtectionUnavailable("envelope-binding-invalid")


def envelope_version(envelope: bytes) -> str:
    """The key version an envelope names; a malformed envelope is unavailable."""
    version = None
    if isinstance(envelope, bytes | bytearray | memoryview):
        value = bytes(envelope)
        if value.startswith(ENVELOPE_TAG) and len(value) > len(ENVELOPE_TAG):
            size = value[4]
            candidate = value[5 : 5 + size]
            if (
                1 <= size <= 40
                and len(value) >= 5 + size + NONCE_BYTES + TAG_BYTES
                and VERSION.fullmatch(candidate.decode("ascii", "replace"))
            ):
                version = candidate.decode("ascii")
    if version is None:
        raise ProtectionUnavailable("envelope-malformed")
    return version


class TokenVault:
    """Seals and opens tokens with keys from one key source (a token keyring)."""

    def __init__(self, keys: KeySource):
        self._keys = keys

    def seal(
        self, token: str, *, account_id: UUID, connection_id: UUID, revision: int
    ) -> tuple[bytes, str]:
        """The envelope under the active key, and that key's version for its column."""
        _check_binding(account_id, connection_id, revision)
        if not isinstance(token, str) or not token:
            raise ProtectionUnavailable("token-invalid")
        version, key = self._keys.active_key()
        sealed = None
        try:
            nonce = secrets.token_bytes(NONCE_BYTES)
            body = AESGCM(key).encrypt(
                nonce,
                token.encode("utf-8"),
                _aad(version, account_id, connection_id, revision),
            )
            encoded = version.encode("ascii")
            sealed = ENVELOPE_TAG + bytes([len(encoded)]) + encoded + nonce + body
        except Exception:  # every sealing fault fails closed; the cause is dropped
            pass
        if sealed is None:
            raise ProtectionUnavailable("seal-unavailable")
        return sealed, version

    def open(
        self, envelope: bytes, *, account_id: UUID, connection_id: UUID, revision: int
    ) -> str:
        """The token, only for the account, connection and revision it was sealed for."""
        _check_binding(account_id, connection_id, revision)
        version = envelope_version(envelope)
        key = self._keys.key(version)
        value = bytes(envelope)
        body = value[5 + len(version) :]
        token = None
        try:
            token = (
                AESGCM(key)
                .decrypt(
                    body[:NONCE_BYTES],
                    body[NONCE_BYTES:],
                    _aad(version, account_id, connection_id, revision),
                )
                .decode("utf-8")
            )
        except Exception:  # a wrong binding, key or tag fails closed; the cause is dropped
            pass
        if token is None:
            raise ProtectionUnavailable("envelope-unopenable")
        return token
