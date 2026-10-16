from copy import deepcopy

import pytest

from backend.modules.research.errors import ResearchError
from backend.modules.research.evidence import SyntheticResearchProvider, validate_output


@pytest.fixture
def source():
    return {
        "sourceKind": "public-paper",
        "sourceId": "paper-a",
        "sourceVersion": "1",
        "location": "section-1",
        "text": "The result is supported by this bounded fixture.",
        "sourceUrl": "https://arxiv.org/abs/1706.03762",
    }


@pytest.mark.parametrize("stance", ["supports", "contradicts", "uncertain"])
def test_fixture_stances_are_grounded_and_labelled(source, stance):
    output = SyntheticResearchProvider().run([source], stance=stance)
    assert output["evidence"][0]["stance"] == stance
    assert output["coverage"] == "partial" and "synthetic" in output["methodRevision"]


def test_unread_reference_cannot_support_answer(source):
    source.update(sourceKind="unread-reference", text=None)
    output = SyntheticResearchProvider().run([source])
    assert output["coverage"] == "abstained" and output["evidence"] == []


def test_invented_quote_rejected(source):
    output = SyntheticResearchProvider().run([source])
    output["evidence"][0]["quote"] = "An invented quote"
    with pytest.raises(ResearchError, match="DEPENDENCY_UNAVAILABLE"):
        validate_output(output, [source])


def test_malformed_provider_output_rejected(source):
    with pytest.raises(ResearchError, match="DEPENDENCY_UNAVAILABLE"):
        validate_output({"summary": "trust me"}, [source])


def test_no_false_complete_or_stale_hash(source):
    output = SyntheticResearchProvider().run([source])
    other = deepcopy(output)
    other["coverage"] = "complete"
    with pytest.raises(ResearchError, match="DEPENDENCY_UNAVAILABLE"):
        validate_output(other, [source])
    output["evidence"][0]["sourceContentHash"] = "0" * 64
    with pytest.raises(ResearchError, match="DEPENDENCY_UNAVAILABLE"):
        validate_output(output, [source])


def test_scores_need_method_scale_and_evidence(source):
    output = SyntheticResearchProvider().run([source])
    output["assessments"] = [
        {
            "criterionId": "similarity",
            "label": "fixture",
            "score": 12,
            "scaleMinimum": 0,
            "scaleMaximum": 10,
            "evidenceIds": [],
            "limitations": [],
        }
    ]
    with pytest.raises(ResearchError, match="DEPENDENCY_UNAVAILABLE"):
        validate_output(output, [source])
