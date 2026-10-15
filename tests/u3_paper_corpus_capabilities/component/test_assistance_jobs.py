"""U3 assistance job component behavior: options, binding, executor."""

import pytest

from backend.modules.summarization.guarded_repository import intent_digest
from backend.modules.summarization.local_http import FAILURE_CODES
from backend.modules.summarization.u3_catalog import (
    SYNTHETIC_NOTE,
    catalog_for,
    definitions_for,
    unavailable_options,
)
from backend.modules.summarization.u3_provider import SyntheticAssistanceExecutor
from backend.modules.summarization.worker import ExecutionRefused
from fixtures import document_model

pytestmark = pytest.mark.u3_component


def source(paper_id="paper-a", *, paragraphs=None, figures=0, checksum="a" * 64):
    content = document_model(
        paper_id,
        title=f"논문 {paper_id}",
        paragraphs=paragraphs or ["첫 문단입니다.", "둘째 문단입니다."],
        figures=figures,
    )
    return {
        "id": f"{paper_id}:v1",
        "paper_id": paper_id,
        "source_hash": checksum,
        "eligibility_revision": "00000000-0000-0000-0000-000000000000",
        "content": content,
    }


def test_options_offer_only_bounded_reconciled_anchors():
    catalog = catalog_for(source(), provider_ready=True)
    assert catalog is not None
    options = catalog.options()
    assert options["options"], "a usable source offers runnable options"
    for option in options["options"]:
        definition = next(
            item for item in catalog.definitions if item["option"]["optionId"] == option["optionId"]
        )
        assert 1 <= len(definition["selectedSections"]) <= 8
    assert SYNTHETIC_NOTE in options["limitations"]


def test_source_without_chunks_gets_no_runnable_option():
    broken = source()
    broken["content"]["chunks"] = []
    assert definitions_for(broken) is None
    view = unavailable_options(broken)
    assert view["options"] == []
    assert view["limitations"], "an empty option list must explain itself"


def test_binding_refuses_changed_source_or_revision():
    catalog = catalog_for(source(), provider_ready=True)
    request = {
        "paper": catalog.paper,
        "contentRevision": catalog.content_revision,
        "contentHash": "a" * 64,
        "operation": "summary",
        "optionId": "u3-key-sections-summary",
        "optionsRevision": catalog.revision,
        "glossaryRevision": "empty:x",
        "processingPolicy": {"policyId": "local-research", "revision": "1"},
    }
    bound = catalog.bind(request)
    assert bound["action"] == "summary"
    for change in (
        {"contentHash": "b" * 64},
        {"optionsRevision": "changed"},
        {"optionId": "u3-key-sections-unknown"},
        {"processingPolicy": {"policyId": "other", "revision": "1"}},
    ):
        with pytest.raises(ValueError):
            catalog.bind(dict(request, **change))


def test_executor_labels_synthetic_output_and_bounds_it():
    executor = SyntheticAssistanceExecutor()
    payload = {
        "input": {"operation": "summary"},
        "sections": [
            {"sectionId": "s", "heading": "Intro", "text": "긴 문장 " * 200, "anchor": "a1"}
        ],
    }
    output = executor.run(payload, float("inf"))
    assert output.provenance["synthetic"] is True
    assert output.provenance["provider"] == "synthetic-fixture"
    assert output.coverage["synthetic"] is True
    assert max(len(item["text"]) for item in _document_sections(output.content)) <= 240
    assert executor.stopped() is True


def _document_sections(content: bytes):
    from backend.modules.summarization.local_result import decode_result

    return decode_result(content)["sections"]


def test_executor_refuses_malformed_and_insufficient_input():
    executor = SyntheticAssistanceExecutor()
    with pytest.raises(ExecutionRefused) as invalid:
        executor.run({"input": {"operation": "summary"}, "sections": []}, 0)
    assert invalid.value.reason == "invalid-source"
    with pytest.raises(ExecutionRefused) as insufficient:
        executor.run(
            {
                "input": {"operation": "summary"},
                "sections": [
                    {"sectionId": "s", "heading": "H", "text": "   ", "anchor": "a"}
                ],
            },
            0,
        )
    assert insufficient.value.reason == "invalid-source"
    failing = SyntheticAssistanceExecutor(fail_with="dependency-unavailable")
    with pytest.raises(ExecutionRefused) as failure:
        failing.run(
            {
                "input": {"operation": "translation"},
                "sections": [
                    {"sectionId": "s", "heading": "H", "text": "문장", "anchor": "a"}
                ],
            },
            0,
        )
    assert failure.value.reason == "dependency-unavailable"


def test_failure_codes_map_to_bounded_envelopes():
    for reason, code in FAILURE_CODES.items():
        assert code in {
            "DEPENDENCY_UNAVAILABLE",
            "DEADLINE_EXCEEDED",
            "SOURCE_INELIGIBLE",
            "FORBIDDEN",
            "NOT_READY",
            "INVALID_CONTENT",
        }
    digest = intent_digest({"paper": "p", "contentHash": "a" * 64})
    assert digest == intent_digest({"contentHash": "a" * 64, "paper": "p"})
    assert digest != intent_digest({"paper": "p", "contentHash": "b" * 64})


def test_reconcile_without_quality_evidence_is_explicit():
    """A source whose provider is not installed offers no runnable option."""
    with pytest.raises(ValueError):
        catalog_for(source(), provider_ready=False)
