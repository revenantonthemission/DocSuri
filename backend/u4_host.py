"""U4 contribution to the shared application; no separate research service."""

from backend.modules.research.execution import ResearchExecution
from backend.modules.research.service import ResearchService
from backend.u3_host import assemble_u3
from backend.u4_policy import SYNTHETIC_RESEARCH


class ResearchWorker:
    def __init__(self, inherited, execution):
        self.inherited = inherited
        self.execution = execution

    def run_once(self, limit=1):
        result = self.inherited.run_once(limit=limit)
        if self.execution.enabled:
            self.execution.step()
        self.execution.expire_artifacts()
        return result


def research_contribution(transactions, entry, corpus, inherited_worker):
    from backend.modules.research.http import research_router

    execution = ResearchExecution(transactions, corpus)
    # C14 research payload/completion bindings and the real supervised round trip
    # are verified in test_assembly.py. Only this exact synthetic realm opts in.
    execution.enabled = True
    service = ResearchService(transactions, corpus, execution=execution)
    capabilities = [
        {
            "id": name,
            "state": "degraded",
            "modeIds": ["synthetic-only"],
            "languageIds": ["ko"],
            "levelIds": [],
            "formatIds": ["json"],
            "policy": SYNTHETIC_RESEARCH.reference(),
        }
        for name in ("research", "novelty")
    ]
    return {
        "service": service,
        "execution": execution,
        "capabilities": capabilities,
        "router": research_router(transactions, entry=entry, service=service),
        "worker": ResearchWorker(inherited_worker, execution),
    }


def assemble_u4(profile, *, topics_factory=None, export_factory=None):
    return assemble_u3(
        profile,
        research_factory=research_contribution,
        topics_factory=topics_factory,
        export_factory=export_factory,
    )
