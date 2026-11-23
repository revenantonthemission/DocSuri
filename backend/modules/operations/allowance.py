"""The email allowance on the operations ledger (U8 plan Step 13; D12, BR7.4, NFR6.2).

`LedgerAllowance` implements the adapters' `EmailAllowance` port. Every reservation is
an `email-allowance` record in the ledger, appended under the ledger's lock after the
count is read in the same step, so two processes can never take the last place twice,
and a production restore cannot roll the count back (security-design § 13).

- Days are UTC days and months UTC months, taken from the one injected clock.
- A digest is reserved only while the day's count of all mail is below 60; account mail
  while it is below 90; nothing once the month's count reaches 2,700.
- The count holds every reservation still reserved or settled; a released one gives its
  place back.
- A retry with the same message key returns the same reservation. A message whose
  reservation was released (a definite refusal) reserves again under the same identity.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from backend.modules.accounts.integrations.email_allowance import (
    MAIL_KINDS,
    AllowanceExhausted,
    Reservation,
)

from .ledger import Ledger, utc_text

KIND = "email-allowance"
COUNTED = ("reserved", "settled")


def reservation_id(kind: str, message_key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"docsuri-email-allowance:{kind}:{message_key}"))


class LedgerAllowance:
    def __init__(self, ledger: Ledger, policy):
        self.ledger, self.policy = ledger, policy

    def _today(self) -> tuple[str, str]:
        now = utc_text(self.ledger.clock())
        return now[:10], now[:7]

    @staticmethod
    def _counts(records, day: str, month: str) -> tuple[int, int]:
        counted = [item for item in records if item["state"] in COUNTED]
        return (
            sum(item["day"] == day for item in counted),
            sum(item["month"] == month for item in counted),
        )

    def _daily_limit(self, kind: str) -> int:
        return (
            self.policy.digest_daily_limit if kind == "digest"
            else self.policy.account_mail_daily_limit
        )

    def _refusal(self, kind: str, records) -> str | None:
        """The limit a new reservation of `kind` meets in `records`, the month first."""
        day, month = self._today()
        daily, monthly = self._counts(records, day, month)
        if monthly >= self.policy.mail_monthly_limit:
            return "monthly"
        if daily >= self._daily_limit(kind):
            return "daily"
        return None

    @staticmethod
    def _identity(kind: str, message_key: str) -> tuple[str, str]:
        if kind not in MAIL_KINDS:
            raise ValueError("mail kind outside the registered set")
        message = str(UUID(str(message_key)))
        return message, reservation_id(kind, message)

    def reserve(self, kind: str, message_key: str) -> Reservation:
        message, identity = self._identity(kind, message_key)

        def step(view):
            prior = view.get(KIND, identity)
            if prior is not None and prior["state"] in COUNTED:
                return Reservation(identity, kind, message)
            day, month = self._today()
            refusal = self._refusal(kind, view.records(KIND))
            if refusal is not None:
                raise AllowanceExhausted(refusal)
            now = utc_text(self.ledger.clock())
            view.append(KIND, {
                "reservationId": identity, "mailKind": kind, "messageKey": message,
                "day": day, "month": month, "state": "reserved",
                "reservedAt": now, "updatedAt": now,
            }, expect_revision=view.revision(KIND, identity))
            return Reservation(identity, kind, message)

        return self.ledger.atomic(step)

    def limit_reached(self, kind: str, message_key: str) -> str | None:
        """The limit `reserve(kind, message_key)` would refuse with now, or None (U8 plan
        Step 53(a), L1-10). It reads the same counts and the same reservation identity as
        `reserve()`, through `ledger.get` and `ledger.records`, which take the ledger's
        lock only to catch up with the log; it never runs inside `ledger.atomic` and
        writes nothing."""
        message, identity = self._identity(kind, message_key)
        prior = self.ledger.get(KIND, identity)
        if prior is not None and prior["state"] in COUNTED:
            return None  # a retry keeps its place
        return self._refusal(kind, self.ledger.records(KIND))

    def _finish(self, reservation: Reservation, state: str) -> None:
        def step(view):
            current = view.get(KIND, reservation.reservation_id)
            if current is None or current["messageKey"] != reservation.message_key:
                raise ValueError("unknown reservation")
            if current["state"] == state:
                return
            view.append(KIND, {**current, "state": state,
                               "updatedAt": utc_text(self.ledger.clock())},
                        expect_revision=view.revision(KIND, reservation.reservation_id))

        self.ledger.atomic(step)

    def release(self, reservation: Reservation) -> None:
        """A send Resend definitely refused gives its place back."""
        self._finish(reservation, "released")

    def settle(self, reservation: Reservation) -> None:
        """An accepted send keeps its place for good."""
        self._finish(reservation, "settled")

    def counts(self) -> dict:
        """The UTC day's and month's counts, for 운영 and provider.resend's observation."""
        day, month = self._today()
        daily, monthly = self._counts(self.ledger.records(KIND), day, month)
        return {"day": day, "month": month, "daily": daily, "monthly": monthly}

    def remaining(self) -> dict:
        """ProviderActivation's `allowanceRemaining` for Resend."""
        counts = self.counts()
        return {
            "daily": max(0, self.policy.account_mail_daily_limit - counts["daily"]),
            "monthly": max(0, self.policy.mail_monthly_limit - counts["monthly"]),
        }

    def exhausted(self, kind: str = "digest") -> bool:
        counts = self.counts()
        return (
            counts["monthly"] >= self.policy.mail_monthly_limit
            or counts["daily"] >= self._daily_limit(kind)
        )
