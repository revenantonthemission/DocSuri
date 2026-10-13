"""Short-lived authenticated cursors scoped to owner, view and policy."""

from __future__ import annotations

import base64
import hmac
import json
import time
from uuid import UUID


class ControlCursor:
    def __init__(self, key: bytes, *, lifetime: int = 300):
        if len(key) != 32 or type(lifetime) is not int or not 1 <= lifetime <= 300:
            raise ValueError("finite cursor key and lifetime required")
        self.key, self.lifetime = key, lifetime

    def _scope(self, owner: UUID, view: str) -> str:
        return hmac.digest(self.key, (str(owner) + ":" + view).encode(), "sha256").hex()

    def encode(self, owner: UUID, view: str, position: dict) -> str:
        raw = json.dumps(
            {
                "scope": self._scope(owner, view),
                "expires": int(time.time()) + self.lifetime,
                "position": position,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        if len(raw) > 2048:
            raise ValueError("cursor state exceeds policy")
        return base64.urlsafe_b64encode(raw + hmac.digest(self.key, raw, "sha256")).decode()

    def decode(self, owner: UUID, view: str, token: str) -> dict:
        if not isinstance(token, str) or len(token) > 4096:
            raise ValueError("invalid cursor")
        try:
            value = base64.b64decode(token, altchars=b"-_", validate=True)
            raw, signature = value[:-32], value[-32:]
            if not hmac.compare_digest(signature, hmac.digest(self.key, raw, "sha256")):
                raise ValueError("invalid cursor")
            parsed = json.loads(raw)
            if parsed["scope"] != self._scope(owner, view) or parsed["expires"] <= time.time():
                raise ValueError("stale or foreign cursor")
            return parsed["position"]
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid cursor") from error
