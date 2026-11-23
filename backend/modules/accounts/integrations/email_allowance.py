"""The email-allowance port the Resend adapters own (U8 plan Step 13; D12, NFR6.2).

Account mail (AccountAccess) and digests (TopicsDigests) each send through their Resend
adapter. Before it calls Resend, an adapter reserves the send through this port:
`reserve(kind, message_key)` takes a place in the shared count, `release(reservation)`
gives it back after a send Resend definitely refused, and `settle(reservation)` marks an
accepted send. A send whose outcome is unknown keeps its reservation. A retry passes the
same message key (the message's own Resend `Idempotency-Key`) and gets the same
reservation back.

The port is a `Protocol`: the composition wires ServiceOperations' ledger implementation
into the adapters (security-design § 13), so neither AccountAccess nor TopicsDigests
imports ServiceOperations and the component graph stays as components.md has it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

MAIL_KINDS = ("digest", "account")


class AllowanceExhausted(RuntimeError):
    """No place is left: `limit` is `daily` or `monthly`. A digest waits for the reset;
    account mail fails with a plain message (BR7.4)."""

    def __init__(self, limit: str):
        if limit not in ("daily", "monthly"):
            raise ValueError("allowance limit is daily or monthly")
        super().__init__(f"email allowance exhausted: {limit}")
        self.limit = limit


@dataclass(frozen=True)
class Reservation:
    """One reserved place: its identity, the kind of mail and the message's key."""

    reservation_id: str
    kind: str
    message_key: str


@runtime_checkable
class EmailAllowance(Protocol):
    def reserve(self, kind: str, message_key: str) -> Reservation: ...

    def release(self, reservation: Reservation) -> None: ...

    def settle(self, reservation: Reservation) -> None: ...

    def limit_reached(self, kind: str, message_key: str) -> str | None:
        """The limit `reserve(kind, message_key)` would refuse with now, `daily` or
        `monthly` (the month read first), or None while a place is left or the message's
        own reservation is already counted, so a retry keeps its place (U8 plan Step
        53(a), L1-10). It writes nothing."""
        ...
