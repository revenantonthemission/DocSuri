"""Operator-only real digest composition: Resend, one permitted recipient, one send.

This entry is separate from the synthetic `assemble_u5` and runs only when an
operator starts the owned U5 host with `--real-delivery`. Configuration comes
from exactly two places:

- non-secret operator decisions in the realm's private, run-bound
  `real-delivery.json` (sender, permitted recipient, public unsubscribe origin,
  capability expiry and the two verification gates);
- the provider credential, only from the process environment
  (`EMAIL_PROVIDER=resend`, `RESEND_API_KEY`). It is never written to a file,
  echoed, logged or placed in an error message.

`freePlanVerified` and `unsubscribeEndpointVerified` are explicit operator
statements; anything but `true` refuses. Missing or invalid configuration
refuses: there is no local-sink, SES, paid or mock-success fallback. The policy
is `REAL_DEMONSTRATION_TOPICS`: one real attempt per realm database (failures
never replenish it; account erasure or a fresh realm resets it, see
`backend/u5_policy.py`) and provider receipts kept at most 30 days.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from backend.local_profile import LocalProfile, private_bytes
from backend.modules.accounts.integrations.digest_email import (
    UNSUBSCRIBE_PATH,
    digest_mail_binding,
    digest_message,
)
from backend.modules.topics.unsubscribe import (
    EmailUnsubscribe,
    PublicCancellationOrigin,
    approved_origin,
)
from backend.u4_host import assemble_u4
from backend.u5_host import topics_contribution
from backend.u5_policy import REAL_DEMONSTRATION_TOPICS, TopicsPolicy

ACTIVATION_FILE = "real-delivery.json"
FIELDS = frozenset(
    {
        "runId",
        "sender",
        "permittedRecipient",
        "unsubscribeOrigin",
        "capabilityExpiresAt",
        "freePlanVerified",
        "unsubscribeEndpointVerified",
    }
)
# A bare, bounded address: no display name, whitespace, header separators or quoting.
ADDRESS = re.compile(r"[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}\Z")
REDACTED_TOKEN = "REDACTED-single-use-token-issued-only-at-send-admission"
# Shape only (Resend keys are `re_` plus URL-safe characters); never logged.
CREDENTIAL_SHAPE = re.compile(r"re_[A-Za-z0-9_]{8,200}")


class RealDeliveryRefused(ValueError):
    """Real delivery is not configured; the message never contains a credential."""


@dataclass(frozen=True)
class RealDeliveryActivation:
    run_id: str
    sender: str
    permitted_recipient: str
    unsubscribe_origin: str
    capability_expires_at: dt.datetime
    free_plan_verified: bool
    unsubscribe_endpoint_verified: bool


def _public_origin(value) -> str:
    try:
        origin = approved_origin(value)
    except ValueError as error:
        raise RealDeliveryRefused("unsubscribeOrigin must be an exact HTTPS origin") from error
    host = urlsplit(origin).hostname or ""
    try:
        ipaddress.ip_address(host)
        literal = True
    except ValueError:
        literal = False
    if literal or host == "localhost" or "." not in host or urlsplit(origin).port is not None:
        raise RealDeliveryRefused("unsubscribeOrigin must be the public HTTPS hostname")
    return origin


def _address(value, field: str) -> str:
    if not isinstance(value, str) or not ADDRESS.fullmatch(value):
        raise RealDeliveryRefused(f"{field} must be one bare email address")
    return value


def _expiry(value, profile: LocalProfile, now: dt.datetime) -> dt.datetime:
    try:
        expires = dt.datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        expires = None
    if expires is None or expires.tzinfo is None:
        raise RealDeliveryRefused("capabilityExpiresAt must be an explicit aware instant")
    realm_end = dt.datetime.fromtimestamp(profile.expires_at, dt.UTC)
    if not now < expires <= realm_end:
        raise RealDeliveryRefused("capabilityExpiresAt must be in the future and within the realm")
    return expires


def _gate(value, field: str) -> bool:
    if value is not True:
        raise RealDeliveryRefused(f"{field} is not confirmed by the operator")
    return True


def parse_activation(value, profile: LocalProfile, *, now: dt.datetime | None = None):
    """Validate the operator's decisions; every gap refuses, nothing defaults."""
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise RealDeliveryRefused("real-delivery activation requires exactly its fields")
    if value["runId"] != profile.run_id:
        raise RealDeliveryRefused("real-delivery activation belongs to another realm")
    now = now or dt.datetime.now(dt.UTC)
    return RealDeliveryActivation(
        run_id=profile.run_id,
        sender=_address(value["sender"], "sender"),
        permitted_recipient=_address(value["permittedRecipient"], "permittedRecipient"),
        unsubscribe_origin=_public_origin(value["unsubscribeOrigin"]),
        capability_expires_at=_expiry(value["capabilityExpiresAt"], profile, now),
        free_plan_verified=_gate(value["freePlanVerified"], "freePlanVerified"),
        unsubscribe_endpoint_verified=_gate(
            value["unsubscribeEndpointVerified"], "unsubscribeEndpointVerified"
        ),
    )


def load_activation(profile: LocalProfile, *, now: dt.datetime | None = None):
    """Read the realm's private, owner-only activation record (never the credential)."""
    try:
        raw = private_bytes(profile.root / ACTIVATION_FILE, maximum=4096)
    except FileNotFoundError as error:
        raise RealDeliveryRefused("real-delivery activation is absent") from error
    except ValueError as error:
        raise RealDeliveryRefused("real-delivery activation custody differs") from error
    try:
        value = json.loads(raw)
    except ValueError as error:
        raise RealDeliveryRefused("real-delivery activation is not JSON") from error
    return parse_activation(value, profile, now=now)


def provider_configuration(activation: RealDeliveryActivation, environ: Mapping[str, str]):
    """Server-held adapter configuration; the credential comes only from `environ`."""
    if environ.get("EMAIL_PROVIDER") != "resend":
        raise RealDeliveryRefused("EMAIL_PROVIDER=resend is required for real delivery")
    credential = environ.get("RESEND_API_KEY")
    if not isinstance(credential, str) or not credential:
        raise RealDeliveryRefused("RESEND_API_KEY must be set in the process environment")
    # A malformed value (stray quotes or whitespace) would be refused by the
    # provider and spend the single attempt; refuse it locally instead.
    if not CREDENTIAL_SHAPE.fullmatch(credential):
        raise RealDeliveryRefused("RESEND_API_KEY does not have the Resend key shape")
    return {
        "apiKey": credential,
        "sender": activation.sender,
        "permittedRecipient": activation.permitted_recipient,
        "unsubscribeUrl": activation.unsubscribe_origin,
        "freePlanVerified": activation.free_plan_verified,
        "unsubscribeEndpointVerified": activation.unsubscribe_endpoint_verified,
    }


def real_mail(activation, environ: Mapping[str, str], *, client_factory=None):
    """The Resend adapter; `client_factory` is only for fake-transport contract tests."""
    try:
        return digest_mail_binding(
            synthetic=False,
            provider="resend",
            configuration=provider_configuration(activation, environ),
            client_factory=client_factory,
        )
    except RealDeliveryRefused:
        raise
    except ValueError as error:
        raise RealDeliveryRefused("the real digest adapter refused its configuration") from error


def real_topics_factory(
    activation: RealDeliveryActivation, mail, *, policy: TopicsPolicy = REAL_DEMONSTRATION_TOPICS
) -> Callable:
    """Topics contribution with the real adapter and its run-bound cancellation."""
    if policy.synthetic_only:
        raise RealDeliveryRefused("real composition requires a real-delivery policy")

    def factory(transactions, entry, corpus, inherited_worker):
        unsubscribe = EmailUnsubscribe(
            transactions,
            origin=activation.unsubscribe_origin,
            expires_at=activation.capability_expires_at,
        )
        return topics_contribution(
            transactions,
            entry,
            corpus,
            inherited_worker,
            policy=policy,
            mail=mail,
            unsubscribe=unsubscribe,
        )

    return factory


def assemble_u5_real(
    profile: LocalProfile,
    activation: RealDeliveryActivation,
    *,
    environ: Mapping[str, str] | None = None,
    client_factory=None,
):
    """Assemble the owned U5 host with real delivery; refuses instead of degrading."""
    if activation.run_id != profile.run_id:
        raise RealDeliveryRefused("real-delivery activation belongs to another realm")
    mail = real_mail(
        activation, os.environ if environ is None else environ, client_factory=client_factory
    )
    app = assemble_u4(profile, topics_factory=real_topics_factory(activation, mail))
    app.add_middleware(PublicCancellationOrigin, origin=activation.unsubscribe_origin)
    return app


def message_preview(run: dict, activation: RealDeliveryActivation) -> dict:
    """The exact submission a send of `run` would make, with the bearer token redacted.

    No capability is issued and no adapter is constructed: previewing can never
    send, spend the allocation or touch the credential.
    """
    if run.get("state") != "prepared" or not run.get("presentation"):
        raise RealDeliveryRefused("only a prepared run with a presentation can be previewed")
    url = activation.unsubscribe_origin + UNSUBSCRIBE_PATH + REDACTED_TOKEN
    return {
        "runId": str(run["id"]),
        "requestKey": str(run["request_key"]),
        "window": [str(run["window_start"]), str(run["window_end"])],
        "preferenceSnapshot": run.get("preference_snapshot"),
        "pathKind": "real",
        "providerRequest": {
            "method": "POST",
            "endpoint": "https://api.resend.com/emails",
            "headers": {
                "Authorization": "Bearer (RESEND_API_KEY from the environment; never shown)",
                "Idempotency-Key": str(run["request_key"]),
            },
        },
        "message": digest_message(
            sender=activation.sender,
            recipient=activation.permitted_recipient,
            presentation=run["presentation"],
            unsubscribe_url=url,
        ),
    }
