"""The restore-enforcement register: accepted erasures, in the ledger (U8 plan Step 13;
BR2.6, BR4.6, NFR4.3).

Each erase request's tombstone is a `restore-tombstone` record holding the owner's
stable identity, the lifecycle request and the time, numbered gap-free and chained by
digest to the tombstone before it. It is appended on the first claim of the request's
`restore_enforcement` scope, under the ledger's lock, synced before the ledger head
moves (the file layer's append). A retried claim finds its tombstone by request and
appends nothing.

The register head (count and the last tombstone's digest) is recorded with every
evidence that relies on it. `verify(recorded)` recomputes the chain and refuses a
register that no longer reaches a head some evidence recorded, so a truncated tail is
detected even when the ledger file itself was cut back consistently. Valid entries a
crash left beyond the ledger's head are adopted by the file layer on open, and a torn
last entry discarded, exactly as for every other record (BR4.6).
"""

from __future__ import annotations

import datetime as dt
import hashlib
from uuid import UUID

import rfc8785

from .errors import LedgerDamaged
from .ledger import Ledger, utc_text
from .ledger_records import ZERO

KIND = "restore-tombstone"


def tombstone_digest(sequence: int, account_id: str, request_id: str, appended_at: str,
                     previous: str) -> str:
    return hashlib.sha256(rfc8785.dumps({
        "sequence": sequence, "accountId": account_id, "lifecycleRequestId": request_id,
        "appendedAt": appended_at, "previousDigest": previous,
    })).hexdigest()


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


class Tombstones:
    def __init__(self, ledger: Ledger):
        self.ledger = ledger

    # --- reading -------------------------------------------------------------------

    def all(self) -> list[dict]:
        return sorted(self.ledger.records(KIND), key=lambda item: item["sequence"])

    def by_request(self, request_id: UUID | str) -> dict | None:
        return self.ledger.get(KIND, str(request_id))

    def head(self) -> dict:
        """The register head: its count and the last tombstone's digest."""
        return _head(self.all())

    def verify(self, recorded: dict | None = None) -> dict:
        """Recompute the register's chain; refuse it when it is broken or no longer
        reaches `recorded`, a head some evidence relied on."""
        tombstones = self.all()
        previous = ZERO
        for position, item in enumerate(tombstones, start=1):
            if item["sequence"] != position or item["previousDigest"] != previous:
                raise LedgerDamaged("register-broken")
            if item["digest"] != tombstone_digest(
                item["sequence"], item["accountId"], item["lifecycleRequestId"],
                item["appendedAt"], item["previousDigest"],
            ):
                raise LedgerDamaged("register-broken")
            previous = item["digest"]
        head = _head(tombstones)
        if recorded is not None:
            sequence = recorded.get("sequence")
            if type(sequence) is not int or sequence < 0 or sequence > head["sequence"]:
                raise LedgerDamaged("register-truncated")
            reached = ZERO if sequence == 0 else tombstones[sequence - 1]["digest"]
            if reached != recorded.get("digest"):
                raise LedgerDamaged("register-broken")
        return head

    def newer_than(self, backup_set: dict) -> list[dict]:
        """The tombstones a restore of `backup_set` replays: every one appended at or
        after the moment the set was taken, in register order (BR4.6)."""
        taken = _parse(backup_set["takenAt"])
        return [item for item in self.all() if _parse(item["appendedAt"]) >= taken]

    # --- appending -----------------------------------------------------------------

    def claim(self, account_id: UUID | str, request_id: UUID | str) -> dict:
        """The request's tombstone, appended on its first claim and found afterwards."""
        account, request = str(UUID(str(account_id))), str(UUID(str(request_id)))

        def step(view):
            prior = view.get(KIND, request)
            if prior is not None:
                if prior["accountId"] != account:
                    raise LedgerDamaged("register-binding")
                return prior
            tombstones = sorted(view.records(KIND), key=lambda item: item["sequence"])
            head = _head(tombstones)
            sequence = head["sequence"] + 1
            appended_at = utc_text(self.ledger.clock())
            record = {
                "sequence": sequence, "accountId": account, "lifecycleRequestId": request,
                "appendedAt": appended_at, "previousDigest": head["digest"],
                "digest": tombstone_digest(sequence, account, request, appended_at,
                                           head["digest"]),
            }
            view.append(KIND, record, expect_revision=0)
            return record

        return self.ledger.atomic(step)


def _head(tombstones: list[dict]) -> dict:
    if not tombstones:
        return {"sequence": 0, "digest": ZERO}
    return {"sequence": tombstones[-1]["sequence"], "digest": tombstones[-1]["digest"]}
