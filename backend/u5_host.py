"""U5 contribution to the shared application; no separate digest service.

The TopicsDigests module joins the one assembled release: its service, its
owner-scoped router, its capability rows and its worker hook on the existing
worker entry (evaluating due topics each bounded pass). The email delivery
capability is reused from the built accounts seam. Its capability record is
derived from the bound adapter: the synthetic realm's local sink reports
`synthetic-only`; the operator-composed real path (backend/u5_real_delivery.py)
reports `real-bounded`. Both stay `degraded`: neither is general delivery.
"""

from backend.u4_host import assemble_u4

# One permitted recipient and a finite allocation: real, but not general delivery.
DELIVERY_MODES = {"local-sink": "synthetic-only", "real": "real-bounded"}


def digest_capability(policy, delivery):
    """The truthful `topics.digest` row for the adapter actually bound."""
    path = delivery.path_kind()
    if (path == "real") == policy.synthetic_only:
        raise ValueError("digest capability policy and adapter disagree")
    return {
        "id": "topics.digest",
        "state": "degraded",
        "modeIds": [DELIVERY_MODES[path]],
        "languageIds": ["en", "ko"],
        "levelIds": ["standard"],
        "formatIds": ["email"],
        "policy": policy.reference(),
    }


class TopicsWorker:
    """One inherited bounded pass plus the due-topic digest pass."""

    def __init__(self, inherited, scheduler):
        self.inherited = inherited
        self.scheduler = scheduler

    def run_once(self, limit=1):
        result = self.inherited.run_once(limit=limit)
        self.scheduler.run_once(limit=limit)
        return result


def topics_contribution(
    transactions,
    entry,
    corpus,
    inherited_worker,
    *,
    policy=None,
    mail=None,
    clock=None,
    unsubscribe=None,
):
    from fastapi import APIRouter

    from backend.modules.personalization.local_http import settings_router
    from backend.modules.topics.delivery import DigestDelivery
    from backend.modules.topics.http import topics_router
    from backend.modules.topics.preparation import DigestPreparation
    from backend.modules.topics.scheduler import TopicsScheduler
    from backend.modules.topics.service import TopicsService
    from backend.u5_policy import SYNTHETIC_TOPICS

    policy = policy or SYNTHETIC_TOPICS
    service = TopicsService(transactions)
    preparation = DigestPreparation(transactions, corpus, policy=policy)
    if unsubscribe is None and policy.synthetic_only:
        import datetime as dt

        from backend.modules.topics.unsubscribe import EmailUnsubscribe

        unsubscribe = EmailUnsubscribe(
            transactions,
            origin=transactions.profile.origin,
            expires_at=dt.datetime.fromtimestamp(transactions.profile.expires_at, dt.UTC),
            synthetic=True,
        )
    delivery = DigestDelivery(
        transactions, corpus, policy=policy, mail=mail, unsubscribe=unsubscribe
    )
    scheduler = TopicsScheduler(transactions, preparation, delivery, policy=policy)
    if clock is not None:
        if not policy.synthetic_only:
            raise ValueError("a fixture clock requires synthetic delivery")
        scheduler._now = clock
    router = APIRouter()
    router.include_router(topics_router(transactions, entry=entry, service=service))
    router.include_router(settings_router(transactions, entry=entry))
    if unsubscribe is not None:
        from backend.modules.topics.unsubscribe import unsubscribe_router

        router.include_router(unsubscribe_router(unsubscribe))
    capabilities = [digest_capability(policy, delivery)]
    return {
        "service": service,
        "delivery": delivery,
        "scheduler": scheduler,
        "capabilities": capabilities,
        "router": router,
        "worker": TopicsWorker(inherited_worker, scheduler),
    }


def assemble_u5(profile, *, export_factory=None):
    import datetime as dt
    import json
    from functools import partial

    from backend.local_profile import private_bytes

    def fixture_clock():
        path = profile.root / "digest-fixture-clock.json"
        now = dt.datetime.now(dt.UTC)
        if not path.exists():
            return now
        value = json.loads(private_bytes(path))
        instant = dt.datetime.fromisoformat(value["instant"])
        if (
            value.get("runId") != profile.run_id
            or instant.tzinfo is None
            or not now - dt.timedelta(hours=1) <= instant <= now + dt.timedelta(days=2)
        ):
            raise ValueError("synthetic digest clock binding differs")
        return instant

    return assemble_u4(
        profile,
        topics_factory=partial(topics_contribution, clock=fixture_clock),
        export_factory=export_factory,
    )
