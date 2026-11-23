"""Account mail: verification, password reset, email change and reactivation (U8 plan
Steps 19 and 21, reactivation by your decision of 2026-10-23; A7, D12, BR7.4, BR7.5, BR8.6).

AccountAccess hands each message to an `AccountMail` adapter and gets back one delivery
word, which the reset-required answer reports (C02 4.0.0 `AccessResetRequired`):

- `accepted`: the adapter took the message for sending;
- `held`: the provider's gate holds outward mail (unavailable, a first effect waiting for
  the maintainer's decision, or a rehearsal recipient other than the maintainer);
- `over_allowance`: the email allowance has no place left today or this month.

Every adapter reads the gate first, then reserves through the email-allowance port before
anything leaves, so a held message takes no place. `LocalAccountMail` is the built local
mailbox (the realms' private `verification-mail` folder) behind that same order.

`ResendAccountMail` (Step 21) sends through the Resend client the digest adapter shares
(`digest_email.ResendClient`). Each message keeps its own idempotency key, each attempt
has 10 seconds, and a timeout, a 408, a 409, a 429 or a 5xx is tried again, up to 3
attempts within 30 seconds; a 408 or a 409 is an unknown outcome, as a timeout or a 5xx
is (Step 53(k), L1-84). A send Resend definitely refused releases its reservation; an
unknown outcome keeps it (D12). Either way the message was not confirmed sent, so the answer
is `held`.
Its link opens a workspace page and carries the proof in the fragment, which no request
sends to a server (D3).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from urllib.parse import urlencode
from uuid import UUID

import httpx

from .digest_email import ResendClient
from .email_allowance import AllowanceExhausted, EmailAllowance
from .provider_gate import ProviderGate, RehearsalRecipients, rehearsal_refuses, require_state

DELIVERIES = ("accepted", "held", "over_allowance")
PURPOSES = ("password-reset", "verification", "email-change", "reactivation")
PROVIDER = "resend"
ATTEMPT_SECONDS, MAX_ATTEMPTS, TOTAL_SECONDS = 10.0, 3, 30.0
# Every 5xx is the retried unknown outcome (U8 plan Step 53(e)); a 429 has its own branch.
RETRIED_FIRST, RETRIED_LAST = 500, 599
# A 408 or a 409 is the same retried unknown outcome at every attempt (Step 53(k); your
# answer L1-84): a 409 answers a duplicate Idempotency-Key still in progress, and either
# can follow an accepted send, as U5's digest adapter reads them (digest_email.py).
UNKNOWN_STATUSES = (408, 409)
# The workspace page each message's link opens (D3); the page reads its fragment.
LINK_PATHS = {
    "password-reset": "/account/password-reset",
    "verification": "/account/verify-email",
    "email-change": "/account/email-change",
    "reactivation": "/account/reactivate",
}
SUBJECTS = {
    "password-reset": "DocSuri 비밀번호 재설정",
    "verification": "DocSuri 이메일 확인",
    "email-change": "DocSuri 이메일 변경 확인",
    "reactivation": "DocSuri 계정 재활성화",
}
INTROS = {
    "password-reset": "보안을 위해 비밀번호를 다시 설정해 주세요. 아래 링크는 5분 동안 쓸 수 "
                      "있습니다.",
    "verification": "DocSuri 이메일 주소를 확인해 주세요.",
    "email-change": "DocSuri 계정의 새 이메일 주소를 확인해 주세요.",
    "reactivation": "탈퇴한 DocSuri 계정을 다시 사용하려면 아래 링크를 열어 주세요. 링크는 "
                    "한 번만 쓸 수 있습니다.",
}
# The local mailbox remembers the file each recent message went to, by its key, so the
# proof that names it can say where its mail is (U2's local-mailbox readers).
MAX_REMEMBERED = 256


def run_to_completion(coroutine):
    """Run one coroutine on a loop of its own; the account services are synchronous and
    run on worker threads, but a caller on a running loop gets a thread of its own."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    result: dict = {}

    def target():
        try:
            result["value"] = asyncio.run(coroutine)
        except BaseException as error:  # noqa: BLE001 - re-raised on the caller's thread
            result["error"] = error

    worker = threading.Thread(target=target)
    worker.start()
    worker.join()
    if "error" in result:
        raise result["error"]
    return result["value"]


@dataclass(frozen=True)
class AccountMessage:
    """One account message. `message_key` is its own idempotency key: a retry passes the
    same key and gets the same reservation (and, at Resend, the same send)."""

    purpose: str
    message_key: str
    account_id: UUID | None
    payload: dict = field(repr=False)

    def __post_init__(self) -> None:
        if self.purpose not in PURPOSES:
            raise ValueError("account mail purpose outside the registered set")
        UUID(str(self.message_key))


@runtime_checkable
class AccountMail(Protocol):
    def deliver(self, message: AccountMessage) -> str: ...


def gate_holds_all(gate: ProviderGate | None) -> bool:
    """True while the gate holds every account message (U8 plan Step 53(g), L1-53): its
    `resend` state is anything but `active` (`held` while a first effect waits or was
    declined, `unavailable` while Resend is unconfigured). False without a gate. It reads
    no message, recipient or allowance."""
    if gate is None:
        return False
    return require_state(gate, PROVIDER) != "active"


def gated(gate: ProviderGate | None, recipients: RehearsalRecipients | None,
          message: AccountMessage) -> bool:
    """True when the provider's gate holds this message (BR7.3, BR7.5): a hold of all
    mail first, then the rehearsal bound, which depends on the recipient."""
    if gate is None:
        return False
    if gate_holds_all(gate):
        return True
    return rehearsal_refuses(gate, recipients, message.account_id)


class LocalAccountMail:
    """The built local mailbox, behind the gate and the allowance when the composition
    wired them. Nothing leaves the host."""

    path_kind = "local-sink"

    def __init__(self, mailbox, *, allowance: EmailAllowance | None = None,
                 gate: ProviderGate | None = None,
                 recipients: RehearsalRecipients | None = None):
        self.mailbox = mailbox
        self.allowance, self.gate, self.recipients = allowance, gate, recipients
        self._delivered: dict[str, object] = {}
        self._lock = threading.Lock()

    def deliver(self, message: AccountMessage) -> str:
        if gated(self.gate, self.recipients, message):
            return "held"
        reservation = None
        if self.allowance is not None:
            try:
                reservation = self.allowance.reserve("account", message.message_key)
            except AllowanceExhausted:
                return "over_allowance"
        artifact = self.mailbox.publish(json.dumps(message.payload).encode())
        with self._lock:
            self._delivered[message.message_key] = artifact
            while len(self._delivered) > MAX_REMEMBERED:
                self._delivered.pop(next(iter(self._delivered)))
        if reservation is not None:
            self.allowance.settle(reservation)
        return "accepted"

    def limit_reached(self, message_key: str) -> str | None:
        """The allowance's limit for this account message, or None (Step 53(b)); None
        without an allowance."""
        if self.allowance is None:
            return None
        return self.allowance.limit_reached("account", message_key)

    def held_for_all(self) -> bool:
        """True while the gate holds every message (Step 53(g)); the local mailbox sends
        nothing through Resend, so no outage counts here."""
        return gate_holds_all(self.gate)

    def artifact_of(self, message_key: str):
        """The mailbox artifact (name, digest, size) a recent message went to, or None."""
        with self._lock:
            return self._delivered.get(message_key)

    def delivery_of(self, message_key: str) -> str | None:
        """The mailbox file a recent message went to, or None."""
        artifact = self.artifact_of(message_key)
        return None if artifact is None else artifact.name


class HeldAccountMail:
    """The production profile's account mail while Resend is unconfigured (its key or
    its sender missing, BR6.7): no stand-in runs in production (BR7.1), so every message
    is held and nothing leaves (BR7.2)."""

    path_kind = "held"

    def deliver(self, message: AccountMessage) -> str:
        if not isinstance(message, AccountMessage):
            raise TypeError("an account message is required")
        return "held"

    def limit_reached(self, message_key: str) -> None:
        """Every message is held, so no limit is ever the answer (Step 53(b))."""
        return None

    def held_for_all(self) -> bool:
        """Every message is held (Step 53(g), L1-53)."""
        return True


def account_message(*, sender: str, origin: str, message: AccountMessage) -> dict:
    """The exact Resend payload of one account message: plain Korean text whose link
    opens the workspace page, the proof in the link's fragment."""
    payload = message.payload
    fragment = urlencode({
        "challenge": payload["challengeId"], "proof": payload["proof"],
        "flow": payload["flowBinding"],
    })
    link = origin + LINK_PATHS[message.purpose] + "#" + fragment
    return {
        "from": sender,
        "to": [payload["email"]],
        "subject": SUBJECTS[message.purpose],
        "text": INTROS[message.purpose] + "\n\n" + link + "\n",
    }


class ResendAccountMail:
    """Account mail through Resend, behind the gate and the allowance (A7, D12)."""

    path_kind = "real"

    def __init__(self, *, api_key: str, sender: str, origin: str,
                 allowance: EmailAllowance, gate: ProviderGate | None = None,
                 recipients: RehearsalRecipients | None = None, client_factory=None,
                 clock=time.monotonic, observed_state: Callable[[], str] | None = None):
        if not sender or not origin.startswith("https://") or allowance is None:
            raise ValueError("account mail needs its sender, its public origin and the "
                             "allowance")
        self._resend = ResendClient(api_key, client_factory=client_factory)
        self.sender, self.origin, self.allowance = sender, origin, allowance
        self.gate, self.recipients, self._clock = gate, recipients, clock
        # provider.resend's state as ServiceOperations derives it (BR3.2), read only by
        # the up-front check `held_for_all` (Step 53(g)); `deliver()` never reads it.
        self._observed_state = observed_state
        self._unreachable = False
        # Each key's latest outcome word (Step 53(j)), as `LocalAccountMail._delivered`.
        self._outcomes: dict[str, str] = {}
        self._outcomes_lock = threading.Lock()

    def limit_reached(self, message_key: str) -> str | None:
        """The allowance's limit for this account message, or None (Step 53(b))."""
        return self.allowance.limit_reached("account", message_key)

    def held_for_all(self) -> bool:
        """True while no account mail can be sent (Step 53(g), L1-53): the gate holds all
        mail, or else Resend is observed `unavailable`. `degraded` still serves, and
        `unknown` or `stale` show no outage. The adapter's own `reachable()` is never
        read: only a send clears it, so a refusal based on it would stop the send that
        ends it."""
        if gate_holds_all(self.gate):
            return True
        if self._observed_state is None:
            return False
        return self._observed_state() == "unavailable"

    def deliver(self, message: AccountMessage) -> str:
        # Each call first forgets its key's earlier outcome, so a call the gate holds or
        # the allowance refuses leaves none (Step 53(j), L1-73).
        self._remember(message.message_key, None)
        if gated(self.gate, self.recipients, message):
            return "held"
        try:
            reservation = self.allowance.reserve("account", message.message_key)
        except AllowanceExhausted:
            return "over_allowance"
        payload = account_message(sender=self.sender, origin=self.origin, message=message)
        outcome = run_to_completion(self._send(payload, message.message_key))
        self._remember(message.message_key, outcome)
        if outcome == "accepted":
            self.allowance.settle(reservation)
            return "accepted"
        if outcome in ("refused", "throttled"):
            self.allowance.release(reservation)
        return "held"

    def _remember(self, message_key: str, outcome: str | None) -> None:
        """Keep each try's outcome word under its key, bounded at `MAX_REMEMBERED`; the
        map holds keys and outcome words only, never an address or a payload."""
        with self._outcomes_lock:
            self._outcomes.pop(message_key, None)
            if outcome is None:
                return
            self._outcomes[message_key] = outcome
            while len(self._outcomes) > MAX_REMEMBERED:
                self._outcomes.pop(next(iter(self._outcomes)))

    def refused(self, message_key: str) -> bool:
        """True only when this key's latest `deliver()` ended in a definite refusal
        (Step 53(j), L1-73): any status other than 200, 201, 408, 409, 429 and 500-599; a
        408 or a 409 is unknown at every attempt, as a timeout or a 5xx is (Step 53(k),
        L1-84). A key never tried, or one the bound has dropped, answers False, so its row
        keeps the retry."""
        with self._outcomes_lock:
            return self._outcomes.get(message_key) == "refused"

    async def _send(self, payload: dict, key: str) -> str:
        """`accepted`, `throttled` (three 429s: a definite "not now"), `refused` (Resend
        definitely did not take it: any status other than 200, 201, 408, 409, 429 and
        500-599) or `unknown` (Step 53(j), L1-73). A 408 or a 409 is unknown at every
        attempt, as a timeout or a 5xx is (Step 53(k), L1-84). Once an attempt has timed
        out or answered 5xx, 408 or 409, Resend may already hold the send under this key,
        so a later 429 proves nothing about it and the outcome stays `unknown` (D12)."""
        started, outcome, uncertain = self._clock(), "unknown", False
        for attempt in range(MAX_ATTEMPTS):
            if attempt and self._clock() - started >= TOTAL_SECONDS:
                break
            try:
                response = await asyncio.wait_for(
                    self._resend.post(payload, key, timeout=ATTEMPT_SECONDS),
                    timeout=ATTEMPT_SECONDS,
                )
            except (TimeoutError, httpx.TimeoutException):
                outcome, uncertain = "unknown", True
                continue
            except httpx.HTTPError:
                self._unreachable = True
                return "unknown"
            if response.status_code in (200, 201):
                self._unreachable = False
                return "accepted"
            if response.status_code == 429:
                # A definite "not now" for this attempt only: it cannot undo an earlier
                # unknown outcome under the same key.
                outcome = "unknown" if uncertain else "throttled"
                continue
            if (RETRIED_FIRST <= response.status_code <= RETRIED_LAST
                    or response.status_code in UNKNOWN_STATUSES):
                # Any 5xx may follow an accepted send (Step 53(e)), and so may a 408 or a
                # 409 (Step 53(k), L1-84).
                outcome, uncertain = "unknown", True
                continue
            self._unreachable = False
            return "refused"
        self._unreachable = outcome == "unknown"
        return outcome

    def reachable(self) -> bool:
        """False after the last message could not reach Resend at all."""
        return not self._unreachable
