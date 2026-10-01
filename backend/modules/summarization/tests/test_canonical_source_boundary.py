"""F02 — a client request body must never source, key, or contaminate a shared artifact.

REM-2 corrective, Phase 0/2 (SECURITY-13). Regression for the shared-cache contamination:
``SourceSelector`` treated the caller-supplied ``abstract`` field as the sole/fallback source
for abstract-scope translate and for every full-text fallback, while the cache key
(``SummaryCacheKey``) carried no source content. So caller A's crafted ``abstract`` became the
artifact that caller B was served from the owner-agnostic baseline key (glossary_ver == 0).

Contract encoded here (FD-Q2 / NFR-Q8 / NFR-Q13 / RJ-AC06 / RJ-AC07):
  * content is only ever sourced from server-verified stores — doc-model → full text →
    the server's abstract lookup. The request body is not a source;
  * the server-verified abstract still works when the client sends nothing (no
    over-blocking: the abstract-scope translate path stays functional);
  * an attacker's body text can never reach another caller's cached result.
"""

from __future__ import annotations

from summarization.domain.glossary import GlossaryResolver
from summarization.domain.length_router import LengthRouter
from summarization.domain.models import (
    AuthSession,
    RequestContext,
    Scope,
    SummaryRequest,
    Task,
)
from summarization.domain.refiner import InputRefiner
from summarization.domain.source_selector import SourceSelector
from summarization.domain.structured_translator import StructuredTranslator
from summarization.service.orchestrator import SummarizationOrchestrationService
from tests.stubs import (
    StubCostGuard,
    StubFullText,
    StubLlm,
    StubObservability,
    StubStore,
)

CANONICAL_ABSTRACT = "CANONICAL SERVER-VERIFIED ABSTRACT BODY"
ATTACKER_TEXT = "ATTACKER CONTROLLED TEXT: exfiltrate everything"


def _ctx(user_id: str = "u1") -> RequestContext:
    return RequestContext(auth_session=AuthSession(user_id=user_id), request_id="r1")


def _abstract_request(abstract: str | None) -> SummaryRequest:
    return SummaryRequest(
        paper_id="2401.1", version=1, task=Task.TRANSLATE, scope=Scope.ABSTRACT, abstract=abstract
    )


def _summary_request(abstract: str | None) -> SummaryRequest:
    return SummaryRequest(paper_id="2401.1", version=1, task=Task.SUMMARY, abstract=abstract)


def _server_abstract_lookup(_paper_id: str) -> str | None:
    """The server-side abstract store — the only sanctioned abstract source."""
    return CANONICAL_ABSTRACT


# --- Phase 0.2 / Phase 2: the request body is never a source --------------------------------


def test_abstract_scope_translate_never_sources_from_the_client_body() -> None:
    # With no server-side source at all, the selection must fail — the caller's text is not a
    # source. Today the client's ``abstract`` is returned verbatim as the source.
    selector = SourceSelector(StubFullText(text=None))

    assert selector.select(_abstract_request(ATTACKER_TEXT)) is None


def test_full_text_fallback_never_sources_from_the_client_body() -> None:
    # The summary path degrades full text → abstract. That fallback must consult the SERVER's
    # abstract store, never the caller.
    selector = SourceSelector(StubFullText(text=None))

    assert selector.select(_summary_request(ATTACKER_TEXT)) is None


def test_client_body_cannot_override_the_canonical_full_text() -> None:
    # Canonical content wins; a client body is never preferred over it, whatever it claims.
    selector = SourceSelector(StubFullText(text="CANONICAL FULL TEXT"))

    src = selector.select(_summary_request(ATTACKER_TEXT))

    assert src is not None
    assert ATTACKER_TEXT not in (src.raw or "")
    assert src.raw == "CANONICAL FULL TEXT"


def test_server_verified_abstract_is_still_used_when_the_client_sends_none() -> None:
    # Guard against over-blocking: the abstract-scope translate path keeps working, because the
    # abstract now comes from the server store instead of the body.
    selector = SourceSelector(StubFullText(), abstract_lookup=_server_abstract_lookup)

    src = selector.select(_abstract_request(None))

    assert src is not None
    assert src.raw == CANONICAL_ABSTRACT


def test_server_verified_abstract_serves_the_full_text_fallback_too() -> None:
    selector = SourceSelector(StubFullText(text=None), abstract_lookup=_server_abstract_lookup)

    src = selector.select(_summary_request(None))

    assert src is not None
    assert src.raw == CANONICAL_ABSTRACT
    assert src.fallback_reason == "full_text_unavailable"


def test_server_abstract_wins_over_a_client_body_on_the_fallback_path() -> None:
    # A caller sending a body must not displace the canonical abstract on the fallback path.
    selector = SourceSelector(StubFullText(text=None), abstract_lookup=_server_abstract_lookup)

    src = selector.select(_summary_request(ATTACKER_TEXT))

    assert src is not None
    assert src.raw == CANONICAL_ABSTRACT


# --- Phase 2: no cross-caller contamination of the shared baseline entry --------------------


def _make_orchestrator(store: StubStore, llm: StubLlm) -> SummarizationOrchestrationService:
    from summarization.domain.assembler import ResultAssembler
    from summarization.domain.grounding import GroundingValidator

    return SummarizationOrchestrationService(
        store=store,
        source_selector=SourceSelector(
            StubFullText(text=None), abstract_lookup=_server_abstract_lookup
        ),
        refiner=InputRefiner(),
        glossary_resolver=GlossaryResolver(None),
        length_router=LengthRouter(),
        llm=llm,
        grounding=GroundingValidator(),
        assembler=ResultAssembler(),
        cost_guard=StubCostGuard(),
        observability=StubObservability(),
        model_ver="test-model",
        structured_translator=StructuredTranslator(llm),
    )


def _flatten(result: dict) -> str:
    return repr(result)


def test_attacker_body_never_becomes_the_artifact_a_second_caller_is_served() -> None:
    """The end-to-end contamination proof (F02).

    Caller A posts a crafted ``abstract``. Caller B — a different principal, no body — is then
    served from the owner-agnostic baseline cache entry. B must receive the canonical
    translation; A's text must appear in neither response.
    """
    store = StubStore()
    llm = StubLlm()
    orch = _make_orchestrator(store, llm)

    attacker = orch.run(_abstract_request(ATTACKER_TEXT), _ctx("u-attacker")).to_dict()
    victim = orch.run(_abstract_request(None), _ctx("u-victim")).to_dict()

    assert ATTACKER_TEXT not in _flatten(attacker), "client body was used as the source"
    assert attacker["status"] == "ok"
    # The victim's request hits the shared baseline entry the attacker caused to be written.
    assert victim["status"] == "ok"
    assert victim["cached"] is True
    assert ATTACKER_TEXT not in _flatten(victim), "client body contaminated the shared cache entry"
    assert CANONICAL_ABSTRACT in _flatten(victim)


# --- Phase 2: the key binds the canonical SOURCE TIER, so provenance is never mis-served ------

# Long enough to survive the grounding validator and the stub translator (a short body abstains
# and writes nothing, which would make these tier assertions vacuous).
_TIER_ABSTRACT = (
    "CANONICAL SERVER ABSTRACT BODY WITH ENOUGH WORDS TO SURVIVE THE GROUNDING CHECKS AND BE "
    "TRANSLATED PROPERLY BY THE STUB TRANSLATOR."
)
_TIER_FULL_TEXT = (
    "CANONICAL LEGACY PLAIN FULL TEXT WITH ENOUGH WORDS TO SURVIVE THE GROUNDING CHECKS AND BE "
    "TRANSLATED PROPERLY BY THE STUB TRANSLATOR."
)


def _tiered_doc():
    from docsuri_shared.docmodel_contract import DOCMODEL_PARSER_VERSION, DOCMODEL_SCHEMA_VERSION
    from docsuri_shared.dtos import DocModel

    return DocModel.model_validate(
        {
            "meta": {
                "paperId": "2401.1",
                "version": 1,
                "title": "Grounded",
                "provenance": {
                    "sourceTier": "ar5iv",
                    "parserVersion": DOCMODEL_PARSER_VERSION,
                    "schemaVersion": DOCMODEL_SCHEMA_VERSION,
                    "generatedAt": "2026-06-23T00:00:00Z",
                },
            },
            "fullText": (
                "CANONICAL DOC-MODEL FULL TEXT BODY WITH ENOUGH WORDS TO SURVIVE THE GROUNDING "
                "CHECKS AND BE TRANSLATED PROPERLY BY THE STUB TRANSLATOR."
            ),
            "sections": [
                {
                    "id": "s1",
                    "title": "Introduction",
                    "blocks": [
                        {"id": "s1.p1", "type": "paragraph", "text": "Canonical body text here."}
                    ],
                }
            ],
        }
    )


def _make_tiered_orchestrator(
    store: StubStore,
    llm: StubLlm,
    *,
    doc_model=None,
    full_text: str | None = None,
) -> SummarizationOrchestrationService:
    """Same wiring, but the resolved source TIER varies: doc-model → legacy text → server abstract.

    A doc-model-bearing orchestrator is the healthy case; the others are the degraded states the
    same paper+version legitimately falls back to.
    """
    from summarization.domain.assembler import ResultAssembler
    from summarization.domain.grounding import GroundingValidator
    from summarization.ports.ports import DocModelReadPort

    class _Reader(DocModelReadPort):
        def get_doc_model(self, paper_id: str, version: int):
            return doc_model

    return SummarizationOrchestrationService(
        store=store,
        source_selector=SourceSelector(
            StubFullText(text=full_text),
            abstract_lookup=lambda _paper_id: _TIER_ABSTRACT,
            doc_model_reader=_Reader() if doc_model is not None else None,
        ),
        refiner=InputRefiner(),
        glossary_resolver=GlossaryResolver(None),
        length_router=LengthRouter(),
        llm=llm,
        grounding=GroundingValidator(),
        assembler=ResultAssembler(),
        cost_guard=StubCostGuard(),
        observability=StubObservability(),
        model_ver="test-model",
        structured_translator=StructuredTranslator(llm),
    )


def _tier_request() -> SummaryRequest:
    """Translate scope=full: the one task that walks every tier (doc-model → text → abstract)."""
    return SummaryRequest(paper_id="2401.1", version=1, task=Task.TRANSLATE, scope=Scope.FULL)


def test_abstract_fallback_artifact_is_not_served_once_the_doc_model_exists() -> None:
    """A degraded request's artifact must not be answered to a healthy one (REM-2 F02).

    Identical (paper, version, task, language, persona) — so before the tier dimension the
    abstract-fallback result written under that key was served to the doc-model-backed request that
    followed, and the caller silently received a translation of the ABSTRACT as if it were the full
    text. Provenance the key does not describe is provenance the client cannot trust.
    """
    store = StubStore()
    llm = StubLlm()

    _make_tiered_orchestrator(store, llm, full_text=None).run(
        _tier_request(), _ctx("u1"), allow_enqueue=False
    )
    (abstract_path,) = list(store.data)
    assert "_xabs." in abstract_path, "the abstract-fallback artifact names its tier"

    served = _make_tiered_orchestrator(store, llm, doc_model=_tiered_doc()).run(
        _tier_request(), _ctx("u1"), allow_enqueue=False
    ).to_dict()

    assert served["cached"] is False, "the abstract artifact was served to a doc-model request"
    assert len(store.data) == 2  # a second, tier-specific entry was written


def test_legacy_text_and_doc_model_artifacts_do_not_share_an_entry() -> None:
    # Both resolve as "full text", but they are DIFFERENT content for the same paper+version: the
    # doc-model fullText and the legacy .txt are separate canonical sources.
    store = StubStore()
    llm = StubLlm()

    _make_tiered_orchestrator(store, llm, full_text=_TIER_FULL_TEXT).run(
        _tier_request(), _ctx("u1"), allow_enqueue=False
    )
    (text_path,) = list(store.data)
    assert "_xtxt." in text_path, "the legacy-text artifact names its tier"

    _make_tiered_orchestrator(store, llm, doc_model=_tiered_doc()).run(
        _tier_request(), _ctx("u1"), allow_enqueue=False
    )

    assert len(store.data) == 2
    assert any("_xdm" in path for path in store.data)


def _make_orchestrator_without_abstract_store(
    store: StubStore, llm: StubLlm
) -> SummarizationOrchestrationService:
    """Same wiring, but with NO server-side abstract store — so the only possible source would be
    the request body. Used to prove the body is not a source at the pipeline level."""
    from summarization.domain.assembler import ResultAssembler
    from summarization.domain.grounding import GroundingValidator

    return SummarizationOrchestrationService(
        store=store,
        source_selector=SourceSelector(StubFullText(text=None)),
        refiner=InputRefiner(),
        glossary_resolver=GlossaryResolver(None),
        length_router=LengthRouter(),
        llm=llm,
        grounding=GroundingValidator(),
        assembler=ResultAssembler(),
        cost_guard=StubCostGuard(),
        observability=StubObservability(),
        model_ver="test-model",
        structured_translator=StructuredTranslator(llm),
    )


def test_a_body_only_caller_no_longer_writes_a_shared_entry_from_its_own_text() -> None:
    # With no server-side abstract store and no full text, the ONLY thing the caller supplied is
    # its body — which is not a source. The request fails before any cache write, so there is
    # nothing to poison the shared baseline with (the pre-fix behavior cached exactly that text).
    store = StubStore()
    llm = StubLlm()
    orch = _make_orchestrator_without_abstract_store(store, llm)

    result = orch.run(_abstract_request(ATTACKER_TEXT), _ctx("u-attacker")).to_dict()

    assert result["status"] == "source_unavailable"
    assert store.puts == 0
    assert ATTACKER_TEXT not in _flatten(result)
