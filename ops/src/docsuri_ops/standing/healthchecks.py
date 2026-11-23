"""The healthchecks.io pings (U8 plan Step 35; observability-design § 5, NFR9.6, O4).

Three checks, each with its own address, held only by the scheduler account in
`scheduler/healthchecks.json`: `heartbeat` (every 5-minute slot), `backup` (after the
04:00 set and its ledger copy) and `verification` (after the Sunday 05:00 run). Each
ping is one request with no body to the check's address, or to its `/fail` address
when the slot is down, the run failed or the run was skipped, with a 10-second limit.
Only the check and pass or fail leave the machine, never an error detail (NFR3.10): a
ping that cannot be delivered is recorded and makes the check late, which alerts after
its grace.

Production's addresses are `https://hc-ping.com/…`; the composed realm's go to a local
stand-in that records pings, on loopback only.
"""

from __future__ import annotations

import json
import os
import stat
import urllib.request
from collections.abc import Callable
from pathlib import Path

CHECKS = ("heartbeat", "backup", "verification")
FILE = "healthchecks.json"
LIMIT_SECONDS = 10
MAX_FILE = 4096
PRODUCTION_HOST = "https://hc-ping.com/"
REALM_PREFIX = "http://127.0.0.1:"


def load_addresses(folder: Path, *, production: bool) -> dict[str, str]:
    """The checks' addresses from the scheduler account's own file (0600)."""
    descriptor = os.open(folder / FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or (
            info.st_size > MAX_FILE
        ):
            raise ValueError("the healthchecks file must be the scheduler's own, private")
        value = json.loads(os.read(descriptor, MAX_FILE))
    finally:
        os.close(descriptor)
    if not isinstance(value, dict) or set(value) != set(CHECKS):
        raise ValueError("the healthchecks file names exactly the three checks")
    prefix = PRODUCTION_HOST if production else REALM_PREFIX
    for address in value.values():
        if not isinstance(address, str) or not address.startswith(prefix) or (
            len(address) > 256 or any(character.isspace() for character in address)
        ):
            raise ValueError("a check address outside its fixed host")
    return value


def _send(url: str, seconds: float) -> int:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=seconds) as answer:  # noqa: S310
        return answer.status


class Healthchecks:
    """Pings with no body; `send(url, seconds)` is the one transport (tests record it)."""

    def __init__(self, addresses: dict[str, str], *,
                 send: Callable[[str, float], int] = _send,
                 record: Callable[[str, str], None] | None = None):
        if set(addresses) != set(CHECKS):
            raise ValueError("the three checks need their addresses")
        self.addresses, self.send = addresses, send
        self.record = record or (lambda check, outcome: None)
        self.last: dict[str, str] = {}

    def ping(self, check: str, *, ok: bool) -> bool:
        if check not in CHECKS:
            raise ValueError("unknown check")
        url = self.addresses[check] + ("" if ok else "/fail")
        outcome = "ok" if ok else "fail"
        try:
            delivered = 200 <= self.send(url, LIMIT_SECONDS) < 300
        except Exception:  # noqa: BLE001 - any transport failure (http.client's too) is undelivered
            delivered = False
        self.last[check] = outcome if delivered else "undelivered"
        self.record(check, self.last[check])
        return delivered

    def fail(self, check: str) -> bool:
        return self.ping(check, ok=False)
