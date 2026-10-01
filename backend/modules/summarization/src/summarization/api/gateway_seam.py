"""Gateway seam — the U7 entry the U6 gateway (or the thin router) calls.

Authn/authz/rate-limit (SEC-8/11) is the U6 gateway's job; the principal arrives in the
request context and U7 trusts it. Unlike U2 (where grounding is the seam), U7 owns its
deterministic grounding gate, so the seam is a thin, framework-agnostic entry that runs the
orchestrator and returns the terminal response (fail-closed on any unexpected error).

It also owns the REQUEST'S OWN bound (REM-2 F05 / NFR-Q11). The budget table in
``domain.timeout_profile`` orders the layers model → worker → **api** → bff → browser, each clearing
the one below it. That ordering only protects a response if something actually enforces the API
layer: before this, a stuck or simply slow generation ran until the browser's arbitrary 10-second
cut, so the client saw a network error and the user had no handle to collect the result that the
backend went on to produce and cache.

So a generation that has not finished inside the API budget is not left hanging. It is converted,
at that boundary, into the same outcome an over-threshold request already gets: the work is
accepted as a background job and the client is told to poll. With nowhere to accept it (no job
queue wired), the honest terminal answer is an abstain. Either way the request ends inside its own
budget, which is what keeps the outer layers' timeouts meaningful.
"""

from __future__ import annotations

import logging
import threading

from ..domain.models import AbstainDTO, PendingDTO, RequestContext, SummaryRequest, SummaryResponse
from ..domain.timeout_profile import POLL_BACKOFF_MS, profile_for
from ..service.orchestrator import SummarizationOrchestrationService

logger = logging.getLogger(__name__)


def run_summarization(
    orchestrator: SummarizationOrchestrationService,
    request: SummaryRequest,
    ctx: RequestContext,
    *,
    budget_sec: float | None = None,
) -> SummaryResponse:
    """Run one generation, bounded by the task's declared API budget.

    ``budget_sec`` defaults to the task's declared API layer (``profile_for(task).api_sec``) and is
    overridable only so the bound itself can be asserted in a test — the production path is always
    the declared table.

    An attempt that is still running at the bound is abandoned (a daemon thread: it cannot keep the
    process alive) and its work is handed to the job queue. The abandoned attempt may still land a
    result under the same deterministic cache key, which only shortens the client's poll — it never
    produces a second, differing result.
    """
    budget = float(profile_for(request.task).api_sec if budget_sec is None else budget_sec)
    outcome: list[SummaryResponse] = []
    failure: list[BaseException] = []

    def _attempt() -> None:
        try:
            outcome.append(orchestrator.run(request, ctx))
        except BaseException as exc:  # noqa: BLE001 — re-raised on the caller's thread below
            failure.append(exc)

    worker = threading.Thread(target=_attempt, name="u7-sync-generate", daemon=True)
    worker.start()
    worker.join(budget)

    if worker.is_alive():
        return _hand_over_over_budget_work(orchestrator, request, ctx, budget)

    if failure:
        # Same fail-closed contract as below, from the thread the work actually ran on.
        return _fail_closed(request, failure[0])
    return outcome[0]


def _hand_over_over_budget_work(
    orchestrator: SummarizationOrchestrationService,
    request: SummaryRequest,
    ctx: RequestContext,
    budget: float,
) -> SummaryResponse:
    """An over-budget generation becomes job + poll (or, with no queue, an abstain)."""
    accept = getattr(orchestrator, "accept_async_job", None)
    accepted = bool(accept(request, ctx)) if callable(accept) else False
    if accepted:
        logger.info(
            "summarization exceeded the api budget → job accepted, client polls "
            "(task=%s budget=%ss)",
            getattr(request, "task", "?"),
            budget,
        )
        return PendingDTO(retry_after_ms=POLL_BACKOFF_MS)
    logger.warning(
        "summarization exceeded the api budget with no job queue → bounded abstain "
        "(task=%s budget=%ss)",
        getattr(request, "task", "?"),
        budget,
    )
    return AbstainDTO(reason="unavailable")


def _fail_closed(request: SummaryRequest, exc: BaseException) -> SummaryResponse:
    """Never surface internals (INV-4/SEC-15).

    The response stays generic (no internals leak), but the cause is logged for operability —
    silently swallowing it makes a real fault (store/glossary/cost) indistinguishable from a
    legitimate abstain. (task=%s scope=%s so the failing path is identifiable.)
    """
    logger.exception(
        "summarization run failed → fail-closed abstain (task=%s scope=%s)",
        getattr(request, "task", "?"),
        getattr(request, "scope", "?"),
        exc_info=exc,
    )
    return AbstainDTO(reason="unavailable")
