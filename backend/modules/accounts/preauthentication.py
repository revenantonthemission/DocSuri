"""Finite signed browser-entry context; no account identity or bearer session."""

from __future__ import annotations

import hmac
import time
from dataclasses import dataclass
from uuid import UUID, uuid4

from .services.guarded_entry import GuardedEntryService


@dataclass(frozen=True, repr=False)
class EntryContext:
    cookie: str
    csrf: str
    flow: str
    expires_at: int


class Preauthentication:
    lifetime = 900

    def __init__(self, entry: GuardedEntryService):
        self.entry = entry
        profile = entry.transactions.profile
        self.binding = f"{profile.run_id}:{profile.database_name}:{profile.origin}"
        self.expires_at = profile.expires_at

    def issue(self) -> EntryContext:
        now = int(time.time())
        expiry = min(now + self.lifetime, int(self.expires_at))
        if expiry <= now:
            raise PermissionError("entry context unavailable")
        unsigned = f"1.{now}.{expiry}.{uuid4()}"
        signature = self.entry.verifier("entry-context", self.binding + ":" + unsigned)
        return self.read(unsigned + "." + signature)

    def read(self, cookie: str, *, csrf: str | None = None) -> EntryContext:
        if not isinstance(cookie, str) or not 1 <= len(cookie) <= 256:
            raise PermissionError("entry context unavailable")
        fields = cookie.split(".")
        if (
            len(fields) != 5
            or fields[0] != "1"
            or len(fields[4]) != 64
            or any(character not in "0123456789abcdef" for character in fields[4])
        ):
            raise PermissionError("entry context unavailable")
        try:
            issued, expiry = int(fields[1]), int(fields[2])
            flow = str(UUID(fields[3]))
        except (ValueError, OverflowError) as error:
            raise PermissionError("entry context unavailable") from error
        now = int(time.time())
        unsigned = ".".join(fields[:4])
        expected = self.entry.verifier("entry-context", self.binding + ":" + unsigned)
        if (
            not issued <= now < expiry <= self.expires_at
            or not 0 < expiry - issued <= self.lifetime
            or fields[3] != flow
            or not hmac.compare_digest(fields[4], expected)
        ):
            raise PermissionError("entry context unavailable")
        expected_csrf = self.entry.verifier("entry-csrf", self.binding + ":" + cookie)
        if csrf is not None and (
            not isinstance(csrf, str)
            or len(csrf) != 64
            or any(character not in "0123456789abcdef" for character in csrf)
            or not hmac.compare_digest(csrf, expected_csrf)
        ):
            raise PermissionError("entry context unavailable")
        return EntryContext(cookie, expected_csrf, flow, expiry)
