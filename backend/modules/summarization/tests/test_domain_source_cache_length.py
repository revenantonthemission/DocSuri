"""SourceSelector (Q1), cache key (BR-S1/INV-5), LengthRouter (Q3)."""

from __future__ import annotations

from summarization.domain.cache_key import build_cache_key
from summarization.domain.length_router import LengthRoute, LengthRouter
from summarization.domain.models import Scope, SourceKind, SummaryRequest, Task
from summarization.domain.source_selector import SourceSelector
from tests.stubs import StubFullText


def _req(
    task: Task, abstract: str | None = None, scope: Scope = Scope.ABSTRACT
) -> SummaryRequest:
    # ``abstract`` is the DEPRECATED client field (REM-2 F02): retained on the dataclass for
    # wire compatibility, ignored as a source. The selector tests below therefore supply the
    # abstract through the server-side ``abstract_lookup`` instead — which is how the canonical
    # abstract actually reaches the pipeline in production.
    return SummaryRequest(
        paper_id="2401.00001", version=1, task=task, scope=scope, abstract=abstract
    )


def _selector_with_server_abstract(text: str | None = None, abstract: str | None = None):
    """A selector whose abstract comes from the SERVER store, never the request body."""
    return SourceSelector(
        StubFullText(text=text), abstract_lookup=lambda _pid: abstract
    )


def test_summary_uses_full_text() -> None:
    src = SourceSelector(StubFullText(text="full body")).select(_req(Task.SUMMARY))
    assert src is not None and src.kind == SourceKind.FULL_TEXT


def test_summary_falls_back_to_abstract() -> None:
    src = _selector_with_server_abstract(text=None, abstract="abs").select(_req(Task.SUMMARY))
    assert src is not None and src.kind == SourceKind.ABSTRACT
    assert src.fallback_reason == "full_text_unavailable"


def test_summary_none_when_no_source() -> None:
    assert SourceSelector(StubFullText(text=None)).select(_req(Task.SUMMARY)) is None


def test_translate_uses_abstract() -> None:
    src = _selector_with_server_abstract(abstract="abs").select(_req(Task.TRANSLATE))
    assert src is not None and src.kind == SourceKind.ABSTRACT


def test_translate_full_uses_full_text() -> None:
    src = SourceSelector(StubFullText(text="full body")).select(
        _req(Task.TRANSLATE, scope=Scope.FULL)
    )
    assert src is not None and src.kind == SourceKind.FULL_TEXT


def test_translate_full_falls_back_to_abstract() -> None:
    src = _selector_with_server_abstract(text=None, abstract="abs").select(
        _req(Task.TRANSLATE, scope=Scope.FULL)
    )
    assert src is not None and src.kind == SourceKind.ABSTRACT
    assert src.fallback_reason == "full_text_unavailable"


def test_cache_key_is_immutable_and_pathed() -> None:
    key = build_cache_key(_req(Task.SUMMARY), glossary_ver=0, model_ver="m1", user_id="u1")
    same = build_cache_key(_req(Task.SUMMARY), glossary_ver=0, model_ver="m1", user_id="u1")
    assert key == same  # deterministic identity (PBT-S1)
    assert key.object_path().startswith("summaries/2401.00001/v1/")
    assert key.redis_key().startswith("sum:")


def test_cache_key_scope_dimension() -> None:
    # summary is fixed to full text; translate varies by scope -> distinct objects.
    summary = build_cache_key(_req(Task.SUMMARY), glossary_ver=0, model_ver="m1", user_id="u1")
    assert summary.scope == Scope.FULL
    abs_tr = build_cache_key(
        _req(Task.TRANSLATE, scope=Scope.ABSTRACT), glossary_ver=0, model_ver="m1", user_id="u1"
    )
    full_tr = build_cache_key(
        _req(Task.TRANSLATE, scope=Scope.FULL), glossary_ver=0, model_ver="m1", user_id="u1"
    )
    assert abs_tr.scope == Scope.ABSTRACT and full_tr.scope == Scope.FULL
    assert abs_tr != full_tr
    assert abs_tr.object_path() != full_tr.object_path()


def test_cache_key_carries_docmodel_parser_generation() -> None:
    from docsuri_shared.docmodel_contract import DOCMODEL_PARSER_VERSION

    key = build_cache_key(_req(Task.SUMMARY), glossary_ver=0, model_ver="m1", user_id="u1")
    # The current parser generation rides in the path (e.g. docmodel-parser@4 → "_d4").
    gen = DOCMODEL_PARSER_VERSION.rpartition("@")[2]
    assert key.docmodel_ver == gen
    assert f"_d{gen}.json" in key.object_path()


def test_source_tier_ver_names_the_canonical_tier_each_source_resolves_to() -> None:
    # REM-2 F02 / FD-Q2: the key segment that records WHICH canonical source an artifact came from.
    from docsuri_shared.docmodel_contract import DOCMODEL_PARSER_VERSION
    from docsuri_shared.dtos import DocModel

    from summarization.domain.cache_key import source_tier_ver
    from summarization.domain.models import SourceKind, SourceText

    assert source_tier_ver(None) == "none"
    assert source_tier_ver(SourceText(kind=SourceKind.ABSTRACT, raw="x")) == "abs"
    assert source_tier_ver(SourceText(kind=SourceKind.FULL_TEXT, raw="x")) == "txt"

    doc = DocModel.model_validate(
        {
            "meta": {
                "paperId": "2401.1",
                "version": 1,
                "title": "Sample",
                "provenance": {
                    "sourceTier": "ar5iv",
                    "parserVersion": DOCMODEL_PARSER_VERSION,
                    "schemaVersion": "1.1.0",
                    "generatedAt": "1970-01-01T00:00:00Z",
                },
            },
            "fullText": "5.2 Results",
            "sections": [],
        }
    )
    gen = DOCMODEL_PARSER_VERSION.rpartition("@")[2]
    assert source_tier_ver(SourceText(kind=SourceKind.FULL_TEXT, doc_model=doc)) == f"dm{gen}"


def test_cache_key_source_tier_change_invalidates_path() -> None:
    # Same request, different tier → different path, so a degraded artifact is never served to a
    # healthy request (the provenance the key does not describe cannot be trusted).
    kwargs = {"glossary_ver": 0, "model_ver": "m1", "user_id": "u1"}
    legacy = build_cache_key(_req(Task.SUMMARY), source_ver="txt", **kwargs)
    modelled = build_cache_key(_req(Task.SUMMARY), source_ver="dm4", **kwargs)
    assert legacy != modelled
    assert legacy.object_path() != modelled.object_path()
    assert "_xtxt.json" in legacy.object_path()
    assert "_xdm4.json" in modelled.object_path()
    # No tier (a pre-selection/legacy key) stays a distinct path too — never silently equal.
    untiered = build_cache_key(_req(Task.SUMMARY), **kwargs)
    assert len({untiered.object_path(), legacy.object_path(), modelled.object_path()}) == 3


def test_cache_key_parser_bump_invalidates_path() -> None:
    # A doc-model parser bump changes the fullText a summary was derived from, so the artifact must
    # miss → regenerate. Two keys differing only by parser generation must not share an object path,
    # so objects built at the older generation self-heal after the doc-model rebuild.
    at2 = build_cache_key(
        _req(Task.SUMMARY), glossary_ver=0, model_ver="m1", user_id="u1",
        docmodel_parser="docmodel-parser@2",
    )
    at4 = build_cache_key(
        _req(Task.SUMMARY), glossary_ver=0, model_ver="m1", user_id="u1",
        docmodel_parser="docmodel-parser@4",
    )
    assert at2.object_path() != at4.object_path()
    assert at2.redis_key() != at4.redis_key()


def test_length_router_branches() -> None:
    router = LengthRouter(context_budget=100, input_cap=1000)
    assert router.route(50) == LengthRoute.SINGLE
    assert router.route(500) == LengthRoute.MAP_REDUCE
    assert router.route(5000) == LengthRoute.OVER_CAP


def test_source_selector_abstract_lookup_success() -> None:
    lookup_called = []
    def dummy_lookup(paper_id: str) -> str | None:
        lookup_called.append(paper_id)
        return "looked up abstract"

    selector = SourceSelector(StubFullText(text=None), abstract_lookup=dummy_lookup)
    src = selector.select(_req(Task.TRANSLATE, abstract=None, scope=Scope.ABSTRACT))
    assert src is not None
    assert src.kind == SourceKind.ABSTRACT
    assert src.raw == "looked up abstract"
    assert lookup_called == ["2401.00001"]


def test_source_selector_fallback_with_abstract_lookup() -> None:
    def dummy_lookup(paper_id: str) -> str | None:
        return "looked up abstract fallback"

    selector = SourceSelector(StubFullText(text=None), abstract_lookup=dummy_lookup)
    src = selector.select(_req(Task.SUMMARY))
    assert src is not None
    assert src.kind == SourceKind.ABSTRACT
    assert src.raw == "looked up abstract fallback"
    assert src.fallback_reason == "full_text_unavailable"
