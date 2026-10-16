"""C14 research completion is typed without widening another owner's envelope."""

from __future__ import annotations

from copy import deepcopy

import pytest
from conftest import all_schema_paths, load_schema
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

from docsuri_shared.workspace import execution


@pytest.fixture
def validator():
    resources = []
    for path in all_schema_paths():
        document = load_schema(str(path.relative_to(path.parents[1])))
        resources.append((document["$id"], Resource.from_contents(document)))
    schema = load_schema("events/execution.schema.json")
    return Draft202012Validator(
        {"$ref": f"{schema['$id']}#/$defs/DispatchFact"},
        registry=Registry().with_resources(resources),
    )


@pytest.fixture
def research_fact():
    result = {
        "resultId": "artifact-1", "revision": "1", "contentHash": "a" * 64,
        "mediaType": "application/json",
    }
    return {
        "messageId": "message-1", "causationId": "dispatch-1",
        "ownerComponent": "ResearchWorkspace", "operationId": "operation-1",
        "kind": "research-turn", "outcome": "succeeded", "resultRef": result,
        "error": None,
        "claim": {
            "binding": {
                "ownerComponent": "ResearchWorkspace", "operationId": "operation-1",
                "inputRevision": "1", "inputHash": "b" * 64, "payloadRef": "payload-1",
            },
            "workerId": "worker-1", "leaseId": "lease-1", "fence": 1,
            "leaseRevision": "1", "expiresAt": "2026-10-16T04:00:00Z",
        },
        "expectedJobRevision": "2", "inputHash": "b" * 64, "progress": None,
        "prepared": {
            "artifact": {"artifactId": "artifact-1", "revision": "1", "contentHash": "a" * 64},
            "ownerId": "owner-1", "contextId": "context-1", "operationId": "operation-1",
            "kind": "research-answer",
            "output": {
                "summary": "No eligible evidence in this synthetic fixture.", "evidence": [],
                "coverage": "abstained", "limitations": ["Synthetic fixture only"],
                "methodRevision": "1",
            },
            "currentEligibilityRevision": "1", "mediaType": "application/json",
            "policy": {"policyId": "synthetic-local", "revision": "1"},
        },
        "usageRecordId": "usage-1",
    }


def assistance_fact(research_fact):
    fact = deepcopy(research_fact)
    fact["ownerComponent"] = "PaperAssistance"
    fact["claim"]["binding"]["ownerComponent"] = "PaperAssistance"
    fact["kind"] = "summary"
    fact["prepared"] = {
        "result": fact["resultRef"], "ownerId": "owner-1", "jobId": "operation-1",
        "paper": {"paperId": "paper-1", "versionId": "paper-1:v1", "eligibilityRevision": "1"},
        "sourceContentHash": "c" * 64, "operation": "summary", "optionId": "option-1",
        "glossaryRevision": "1", "sections": [], "coverage": "abstained",
        "limitations": ["Synthetic fixture only"], "methodRevision": "1",
    }
    return fact


@pytest.mark.parametrize("owner", ["research", "assistance"])
def test_valid_owner_completion_schema_and_generated_roundtrip(validator, research_fact, owner):
    fact = research_fact if owner == "research" else assistance_fact(research_fact)
    validator.validate(fact)
    decoded = execution.DispatchFact.model_validate(fact)
    encoded = decoded.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert encoded == fact
    validator.validate(encoded)


@pytest.mark.parametrize("field", ["prepared", "resultRef", "usageRecordId"])
def test_research_success_requires_prepared_reference_and_accounting(
    validator, research_fact, field
):
    research_fact[field] = None
    with pytest.raises(ValidationError):
        validator.validate(research_fact)


@pytest.mark.parametrize("owner", ["PaperAssistance", "UnregisteredOwner"])
def test_other_owner_cannot_carry_research_artifact(validator, research_fact, owner):
    research_fact["ownerComponent"] = owner
    with pytest.raises(ValidationError):
        validator.validate(research_fact)


def test_research_cannot_carry_assistance_result(validator, research_fact):
    research_fact["prepared"] = assistance_fact(research_fact)["prepared"]
    with pytest.raises(ValidationError):
        validator.validate(research_fact)


@pytest.mark.parametrize("outcome", ["progress", "failed", "cancelled", "unknown"])
def test_non_success_cannot_smuggle_prepared_artifact(validator, research_fact, outcome):
    research_fact["outcome"] = outcome
    with pytest.raises(ValidationError):
        validator.validate(research_fact)


def test_result_reference_does_not_replace_research_artifact_reference(validator, research_fact):
    research_fact["prepared"]["artifact"] = research_fact["resultRef"]
    with pytest.raises(ValidationError):
        validator.validate(research_fact)


def test_private_extra_payload_is_rejected(validator, research_fact):
    research_fact["prepared"]["privateDraft"] = "must not cross this boundary"
    with pytest.raises(ValidationError):
        validator.validate(research_fact)
