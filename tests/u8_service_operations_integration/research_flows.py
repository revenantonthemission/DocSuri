"""Production research on the production stand-in (U8 plan Step 22; your decision of
2026-10-24, "Build the research executor").

`production_research` composes, on Step 12's production stand-in and with the real
builders, ServiceOperations' store and ledger, the paper journey, the production corpus
(the shared model runtime's client over a mock transport) and the production research
contribution. The mock answers `/api/tags` with the pins and `/api/chat` with a grounded
answer that quotes the first excerpt sent, unless a test scripts it otherwise; no model
is ever called.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from tests.u8_service_operations_integration.host_flows import (
    ModelStandIn,
    import_paper,
    production_stand_in,
    standin_account,
    write_readiness,
)

PAPER_CHUNKS = [
    {"anchor": "intro", "section": "Introduction",
     "text": "Attention lets a model weigh every input token against every other token."},
    {"anchor": "method", "section": "Method",
     "text": "We train the encoder on paired sentences and report the loss on held out data."},
    {"anchor": "results", "section": "Results",
     "text": "The model improves translation quality on every benchmark we measured here."},
]
DIGEST_EVIDENCE = "e" * 64


def excerpts_of(body: dict) -> list[dict]:
    return json.loads(body["messages"][1]["content"].split("SOURCE EXCERPTS\n", 1)[1])


def grounded(body: dict) -> httpx.Response:
    """An answer quoting the first excerpt's first six words; three assessments for an
    analysis."""
    first = excerpts_of(body)[0]
    quote = " ".join(first["text"].split()[:6])
    answer = {"summary": "발췌한 구간이 질문에 답합니다.",
              "evidence": [{"location": first["location"], "quote": quote,
                            "claim": "구간이 이렇게 설명합니다", "stance": "supports"}]}
    if "assessments" in body["format"]["properties"]:
        answer["assessments"] = [{"criterionId": name, "evidence": [0]}
                                 for name in ("research-question", "method", "contribution")]
    return httpx.Response(200, json={
        "model": body["model"], "done": True, "done_reason": "stop",
        "prompt_eval_count": 900, "eval_count": 120,
        "message": {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}})


def observe(env, capability: str, outcome: str = "available", reason: str | None = None):
    """A fresh observation of `capability`, as its producer records it."""
    from backend.modules.operations.observations import Observations
    from backend.u8_registry import CAPABILITY_BY_ID

    observations = Observations(env.store)
    row = observations.make(capability, CAPABILITY_BY_ID[capability].producer, outcome,
                            observed_at=dt.datetime.now(dt.UTC), reason=reason,
                            limitations=(reason,) if reason else ())
    assert observations.record(CAPABILITY_BY_ID[capability].producer, [row])["written"] == 1


@contextlib.contextmanager
def production_research(realm, *, ready=("assistance", "research")):
    """The production stand-in with the research contribution built by the real
    builders; `ready` names the purposes the readiness marker records."""
    from backend.modules.summarization import model_runtime
    from backend.u8_host import (
        build_paper_corpus,
        build_paper_journey,
        build_research_workspace,
        build_service_operations,
        open_ledger,
        start_keys,
    )

    model = ModelStandIn(chat=grounded)
    patch = pytest.MonkeyPatch()
    patch.setattr(model_runtime, "network_transport", model.factory)
    try:
        with production_stand_in(realm) as standin:
            # The start's own key step, as a start runs it before any builder (L1-4,
            # Step 72(a)): the stand-in holds no account, so both keys are created here.
            start_keys(standin.profile, occupied=False)
            if ready:
                write_readiness(standin.profile, dict.fromkeys(ready, DIGEST_EVIDENCE))
            ctx = standin.context()
            ledger = open_ledger(standin.profile, ctx.clock)
            try:
                ctx.parts["ledger"] = ledger
                for name, build in (("service-operations", build_service_operations),
                                    ("paper-journey", build_paper_journey),
                                    ("paper-corpus", build_paper_corpus),
                                    ("research-workspace", build_research_workspace)):
                    ctx.parts[name] = build(ctx)
                research = ctx.parts["research-workspace"]
                yield SimpleNamespace(
                    standin=standin, ctx=ctx, model=model, parts=ctx.parts,
                    research=research, execution=research["execution"],
                    service=research["service"], provider=research["provider"],
                    store=ctx.parts["service-operations"]["observations"],
                    runtime=ctx.parts["paper-corpus"]["runtime"],
                )
            finally:
                ledger.close()
    finally:
        patch.undo()


def paper_scope(env, owner, *, purpose: str = "research", papers: int = 1,
                web=()) -> dict:
    """A research context of `owner` and a scope over freshly imported papers."""
    from backend.u8_research import PRODUCTION_RESEARCH

    refs = [import_paper(env.standin, PAPER_CHUNKS) for _ in range(papers)]
    context = env.service.create_context(owner, {"purpose": purpose,
                                                 "policy": PRODUCTION_RESEARCH.reference()})
    return {"contextId": context["contextId"], "publicPapers": refs, "attachmentIds": [],
            "webReferences": list(web), "scopePolicy": PRODUCTION_RESEARCH.reference()}


def accept_turn(env, owner, scope: dict, *, text: str = "어텐션은 무엇을 하나요?",
                mode: str = "question") -> dict:
    """A research turn accepted through the production service (research observed
    available first)."""
    from backend.u8_research import PRODUCTION_RESEARCH

    observe(env, "research")
    session = env.service.create_session(owner, {"title": "합성 연구", "scope": scope})
    return env.service.accept(owner, uuid4(), {
        "sessionId": session["sessionId"], "scope": scope, "mode": mode, "text": text,
        "policy": PRODUCTION_RESEARCH.reference()}, "research-turn")


def accept_analysis(env, owner, scope: dict, *, text: str = "어텐션 기반 번역") -> dict:
    from backend.u8_research import PRODUCTION_RESEARCH

    observe(env, "novelty")
    return env.service.accept(owner, uuid4(), {
        "scope": scope, "inputMode": "topic", "text": text,
        "policy": PRODUCTION_RESEARCH.reference()}, "novelty-analysis")


def job_row(env, job_id) -> dict:
    with env.standin.connect("research") as conn:
        return conn.execute("SELECT * FROM research.job WHERE id=%s", (job_id,)).fetchone()


def reservation(env, usage_id) -> dict:
    from psycopg.rows import dict_row

    with env.standin.admin() as conn:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("SELECT * FROM usage.reservation WHERE id=%s", (usage_id,))
        return cursor.fetchone()


def lease_ends(env, job_id) -> None:
    """The job's lease as if its time had passed (the wait between attempts)."""
    with env.standin.connect("research", autocommit=True) as conn:
        conn.execute("UPDATE research.job SET lease_until=clock_timestamp()-interval '1 second'"
                     " WHERE id=%s", (job_id,))


def run_next(env) -> str:
    import time

    return env.execution.execute_next(deadline=time.monotonic() + 90)


def member(env, suffix: str = "research"):
    return standin_account(env.standin, f"{suffix}-{uuid4().hex[:6]}")
