"""A real-path digest send over the owned store, through a recording HTTP client.

The real delivery step, the real Resend adapter and a run-bound cancellation
capability take part; only the adapter's HTTP client is replaced, by a client that
records the request and answers with a provider receipt. Nothing leaves the host, so
a send made here is contract evidence, never delivery evidence. Each send spends one
of the realm's durable real attempts: the allocation is the realm's current count of
real attempts plus one, the same bound the integration checks use.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from types import SimpleNamespace
from uuid import uuid4

import httpx
from backend.modules.topics.delivery import DigestDelivery
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.unsubscribe import EmailUnsubscribe
from backend.u5_policy import REAL_DEMONSTRATION_TOPICS
from backend.u5_real_delivery import parse_activation, real_mail

PUBLIC = "https://unsubscribe.fixture.invalid"
SENDER = "no-reply@docsuri.fixture.invalid"
FAKE_KEY = "re_fakeCredentialNeverReal_stepTwenty01"
ENVIRON = {"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": FAKE_KEY}


class RecordingClient:
    """Stands in for the adapter's HTTP client: records each request, sends nothing."""

    def __init__(self):
        self.requests = []

    def __call__(self, **options):
        assert options == {"timeout": 3.0}
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, *, headers, json):
        self.requests.append({"url": url, "headers": dict(headers), "json": json})
        return httpx.Response(200, json={"id": str(uuid4())})


def activation_value(realm, recipient):
    """The operator's non-secret decisions; the provider key is never part of them."""
    return {
        "runId": realm.run_id,
        "sender": SENDER,
        "permittedRecipient": recipient,
        "unsubscribeOrigin": PUBLIC,
        "capabilityExpiresAt": (dt.datetime.now(dt.UTC) + dt.timedelta(minutes=30)).isoformat(),
        "freePlanVerified": True,
        "unsubscribeEndpointVerified": True,
    }


def real_attempts(repository):
    return repository.system(
        lambda conn: conn.execute(
            "SELECT count(*) AS n FROM topics.send_log_entry WHERE path_kind='real'"
        ).fetchone()["n"]
    )


def recipient_of(transactions, account_id):
    return TopicsRepository(transactions).digest_recipient(account_id)["email"]


def real_path(transactions, realm, recipient):
    """The real delivery step for one permitted recipient, with one more real attempt."""
    activation = parse_activation(activation_value(realm, recipient), realm)
    client = RecordingClient()
    policy = dataclasses.replace(
        REAL_DEMONSTRATION_TOPICS,
        real_send_limit=real_attempts(TopicsRepository(transactions)) + 1,
    )
    delivery = DigestDelivery(
        transactions,
        None,
        mail=real_mail(activation, ENVIRON, client_factory=client),
        policy=policy,
        unsubscribe=EmailUnsubscribe(
            transactions,
            origin=activation.unsubscribe_origin,
            expires_at=activation.capability_expires_at,
        ),
    )
    return SimpleNamespace(activation=activation, client=client, delivery=delivery, policy=policy)


def send(transactions, path, run, account_id):
    """Admit the prepared run as a real attempt and deliver it; returns the terminal run."""
    sending = TopicsRepository(transactions).begin_send(
        run["id"],
        path.delivery.path_kind(),
        real_send_limit=path.policy.real_send_limit,
        evidence_retention_days=path.policy.real_evidence_retention_days,
    )
    assert sending is not None, "the real attempt was not admitted"
    return path.delivery.attempt(sending, {"account_id": account_id})
