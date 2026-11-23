"""The complete assembly's digest adapters (U8 plan Step 21; BR6.7, BR7.2, BR7.3, BR7.5,
BR7.6).

U5's `ResendDigestMail` stays as U5 built it. Production composes these instead:

- `GatedResendDigestMail` is U5's Resend adapter read through the provider gate. While
  Resend is held or unavailable nothing leaves (`provider-held`); in rehearsal a digest
  to any account but the maintainer's is held as not permitted (BR7.5); in live mode,
  once Resend is active there, U5's single permitted recipient gives way and every
  subscriber who consented may receive one (BR7.6).
- `HeldDigestMail` is the production adapter while Resend is unconfigured: it permits
  nobody, takes no preview and refuses every send with `provider-held`.

`provider-held` is U8's own refusal reason: `ProviderHeldResult` is a `DigestMailResult`
that admits it, so U5's result keeps U5's reasons.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from . import digest_email
from .digest_email import (
    RECIPIENT_NOT_PERMITTED,
    UNSUBSCRIBE_PATH,
    DigestMailResult,
    ResendDigestMail,
    digest_message,
)
from .provider_gate import gate_active, preview_bytes, rehearsal_refuses

PROVIDER = "resend"
PROVIDER_HELD = "provider-held"
# A held first effect's preview shows the single-use cancellation token redacted: the
# service issues it only at send admission, and the preview is the content you approve.
PREVIEW_TOKEN = "REDACTED-single-use-token-issued-only-at-send-admission"


@dataclass(frozen=True)
class ProviderHeldResult(DigestMailResult):
    """The gate held Resend when the send began: nothing left, and the recipient was not
    at fault. It is a refusal with no provider detail and no other reason."""

    def __post_init__(self):
        if (
            self.state != "refused"
            or self.refusal_reason != PROVIDER_HELD
            or (self.receipt, self.acknowledged_at, self.provider_status,
                self.provider_error) != (None, None, None, None)
        ):
            raise ValueError("a provider-held result is a bare refusal")


def provider_held() -> ProviderHeldResult:
    return ProviderHeldResult("refused", refusal_reason=PROVIDER_HELD)


def _network(**options):
    """Resolved at call time, so a test-wide guard that replaces the shared client's
    `network_client` also guards this adapter."""
    return digest_email.network_client(**options)


class GatedResendDigestMail(ResendDigestMail):
    def __init__(self, *, api_key, sender, unsubscribe_url, permitted_recipient, gate,
                 recipients, account_of, client_factory=None):
        if gate is None or recipients is None or account_of is None:
            raise ValueError("the gated adapter needs the gate, recipients and account lookup")
        super().__init__(
            api_key=api_key, sender=sender, unsubscribe_url=unsubscribe_url,
            permitted_recipient=permitted_recipient,
            client_factory=client_factory if client_factory is not None else _network,
        )
        self._gate, self._recipients, self._account_of = gate, recipients, account_of

    @property
    def gate(self):
        return self._gate

    def bounds_lifted(self) -> bool:
        """BR7.6: only in live mode, once Resend is active there."""
        return self._gate.mode == "live" and gate_active(self._gate, PROVIDER)

    def permits(self, recipient):
        """U5's one permitted address, until Resend is active in live mode: then every
        subscriber who consented may (consent is checked at send start)."""
        return self.bounds_lifted() or super().permits(recipient)

    def preview_content(self, recipient, presentation, request_key) -> bytes:
        """The exact submission a send would make, its cancellation token redacted: what
        a held first effect records as its preview (BR7.3). Pure and network-free."""
        url = self._unsubscribe_origin + UNSUBSCRIBE_PATH + PREVIEW_TOKEN
        return preview_bytes({
            "endpoint": self.endpoint,
            "idempotencyKey": str(UUID(str(request_key))),
            "message": digest_message(sender=self._sender, recipient=recipient,
                                      presentation=presentation, unsubscribe_url=url),
        })

    async def send(self, recipient, presentation, request_key, *, unsubscribe_url=None):
        if not gate_active(self._gate, PROVIDER):
            # Held or unavailable: nothing leaves (BR7.2, BR7.3). The scheduler holds its
            # runs before this, so this answers only a hold that arrived meanwhile.
            return provider_held()
        if not self.permits(recipient):
            return DigestMailResult("refused", refusal_reason=RECIPIENT_NOT_PERMITTED)
        if rehearsal_refuses(self._gate, self._recipients, self._account_of(recipient)):
            # Held before any network call, and recorded by U5 with this reason.
            return DigestMailResult("refused", refusal_reason=RECIPIENT_NOT_PERMITTED)
        return await super().send(recipient, presentation, request_key,
                                  unsubscribe_url=unsubscribe_url)


class HeldDigestMail:
    """The production digest adapter while Resend is unconfigured (BR6.7, BR7.2): it is
    the real path, so the scheduler holds every run behind the gate and nothing is sent;
    a call that still reaches it is refused before any network call."""

    path_kind = "real"

    def __init__(self, *, permitted_recipient, gate):
        if gate is None or not permitted_recipient:
            raise ValueError("a held digest adapter needs the gate and the maintainer")
        self._permitted_recipient, self._gate = permitted_recipient, gate

    @property
    def permitted_recipient(self):
        return self._permitted_recipient

    @property
    def gate(self):
        return self._gate

    def bounds_lifted(self) -> bool:
        return False

    def permits(self, recipient):
        return False

    def preview_content(self, recipient, presentation, request_key) -> bytes:
        raise ValueError("an unconfigured provider takes no first effect")

    async def send(self, recipient, presentation, request_key, *, unsubscribe_url=None):
        return provider_held()


MAINTAINER_ADDRESS_PENDING = "maintainer-address-pending"
# U5's real delivery requires one permitted recipient; this one is no address at all (the
# reserved `.invalid` name, which v2's email form refuses), so it matches no subscriber.
NO_RECIPIENT = "maintainer-address-pending@docsuri.invalid"


class AddressPendingDigestMail(HeldDigestMail):
    """Rehearsal's held adapter before the maintainer's account has an address (BR7.5;
    your decision of 2026-10-24): it permits nobody, so every run stays prepared, and
    `topics.digest` reads degraded with `maintainer-address-pending`."""

    limitation = MAINTAINER_ADDRESS_PENDING

    def __init__(self, *, gate):
        super().__init__(permitted_recipient=NO_RECIPIENT, gate=gate)
