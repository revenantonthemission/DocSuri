"""U5 contribution to the shared application; no separate digest service.

The TopicsDigests module joins the one assembled release: its service, its
owner-scoped router, its capability rows and its worker hook on the existing
worker entry (evaluating due topics each bounded pass). The email delivery
capability is reused from the built accounts seam; the synthetic realm's
delivery path is the local sink, so the capability stays truthfully degraded.
"""

from backend.u4_host import assemble_u4


class TopicsWorker:
    """One inherited bounded pass plus the due-topic digest pass."""

    def __init__(self, inherited, scheduler):
        self.inherited = inherited
        self.scheduler = scheduler

    def run_once(self, limit=1):
        result = self.inherited.run_once(limit=limit)
        self.scheduler.run_once(limit=limit)
        return result


def topics_contribution(transactions, entry, corpus, inherited_worker):
    from backend.modules.topics.delivery import DigestDelivery
    from backend.modules.topics.http import topics_router
    from backend.modules.topics.preparation import DigestPreparation
    from backend.modules.topics.scheduler import TopicsScheduler
    from backend.modules.topics.service import TopicsService
    from backend.u5_policy import SYNTHETIC_TOPICS

    service = TopicsService(transactions)
    preparation = DigestPreparation(transactions, corpus)
    delivery = DigestDelivery(transactions, corpus)
    scheduler = TopicsScheduler(transactions, preparation, delivery)
    capabilities = [
        {
            "id": "topics.digest",
            "state": "degraded",
            "modeIds": ["synthetic-only"],
            "languageIds": ["ko"],
            "levelIds": [],
            "formatIds": ["email"],
            "policy": SYNTHETIC_TOPICS.reference(),
        }
    ]
    return {
        "service": service,
        "scheduler": scheduler,
        "capabilities": capabilities,
        "router": topics_router(transactions, entry=entry, service=service),
        "worker": TopicsWorker(inherited_worker, scheduler),
    }


def assemble_u5(profile):
    return assemble_u4(profile, topics_factory=topics_contribution)
