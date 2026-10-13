"""Codec and deliberate authority faults; normal model output is not simulated."""

import copy
import hashlib
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from backend.modules.corpus.repository import content_revision
from backend.modules.summarization.payload import (
    ExecutionPayloads,
    encode_payload,
)
from docsuri_shared.workspace import execution as wire

pytestmark = pytest.mark.u1_component


def fixture():
    owner, operation, eligibility = uuid4(), uuid4(), uuid4()
    text = "Synthetic source for payload binding checks."
    chunk = {
        "anchor": "s1.p1",
        "section": "Diagnostic",
        "text": text,
        "textHash": hashlib.sha256(text.encode()).hexdigest(),
    }
    source = {
        "paper_id": "diagnostic",
        "id": "diagnostic-v1",
        "eligibility_revision": eligibility,
        "source_hash": "a" * 64,
        "content": {"document": {}, "chunks": [chunk]},
    }
    glossary_revision = f"empty:{owner}:local-v1"
    accepted = {
        "paper": {
            "paperId": source["paper_id"],
            "versionId": source["id"],
            "eligibilityRevision": str(eligibility),
        },
        "contentRevision": content_revision(source),
        "contentHash": source["source_hash"],
        "operation": "summary",
        "optionId": "diagnostic-selected-section",
        "optionsRevision": "diagnostic-v1",
        "glossaryRevision": glossary_revision,
        "processingPolicy": {"policyId": "local-research", "revision": "1"},
        "glossary": {
            "ownerId": str(owner),
            "revision": glossary_revision,
            "normalizationPolicy": {"policyId": "diagnostic-glossary", "revision": "1"},
            "terms": [],
        },
    }
    bound = {
        "binding": {
            "ownerComponent": "PaperAssistance",
            "operationId": str(operation),
            "inputRevision": str(operation),
            "inputHash": "b" * 64,
            "payloadRef": str(operation),
        },
        "payload": {
            "acceptedInput": accepted,
            "selectedSections": [
                {
                    "anchor": chunk["anchor"],
                    "heading": chunk["section"],
                    "textHash": chunk["textHash"],
                }
            ],
        },
        "acceptedAt": datetime.now(timezone.utc),
        "reservationId": uuid4(),
        "accountId": owner,
        "versionId": source["id"],
        "sourceHash": source["source_hash"],
        "glossaryRevision": glossary_revision,
        "glossarySnapshot": [],
    }
    return bound, source


def test_payload_uses_generated_contract_and_original_acceptance():
    bound, source = fixture()
    encoded = encode_payload(bound, source)
    assert (
        wire.AssistanceExecutionPayload.model_validate(encoded).model_dump(mode="json") == encoded
    )
    assert encoded["sections"][0]["text"] == source["content"]["chunks"][0]["text"]
    assert datetime.fromisoformat(encoded["acceptedAt"]) == bound["acceptedAt"]
    assert encoded["usageRecordId"] == str(bound["reservationId"])


@pytest.mark.parametrize(
    "field", ["paper", "source", "content", "glossary", "owner", "heading", "textHash"]
)
def test_changed_accepted_binding_is_rejected(field):
    bound, source = fixture()
    if field == "paper":
        bound["payload"]["acceptedInput"]["paper"]["eligibilityRevision"] = str(uuid4())
    elif field == "source":
        source["source_hash"] = "c" * 64
    elif field == "content":
        source["content"]["document"] = {"changed": True}
    elif field == "glossary":
        bound["glossaryRevision"] = "another-revision"
    elif field == "owner":
        bound["accountId"] = uuid4()
    else:
        bound["payload"]["selectedSections"][0][field] = "changed"
    with pytest.raises(ValueError):
        encode_payload(bound, source)


def test_missing_canonical_intent_is_not_reconstructed_from_current_state():
    bound, source = fixture()
    bound["payload"] = {"versionId": source["id"], "sourceHash": source["source_hash"]}
    with pytest.raises(KeyError):
        encode_payload(bound, source)


def test_repeated_selected_anchor_is_rejected():
    bound, source = fixture()
    bound["payload"]["selectedSections"] *= 2
    with pytest.raises(ValueError, match="repeated"):
        encode_payload(bound, source)


def test_exact_translation_span_binds_original_and_selected_bytes():
    bound, source = fixture()
    bound["payload"]["acceptedInput"]["operation"] = "translation"
    original = source["content"]["chunks"][0]["text"]
    selection = bound["payload"]["selectedSections"][0]
    selection.update(start=0, end=9, selectedHash=hashlib.sha256(original[:9].encode()).hexdigest())
    section = encode_payload(bound, source)["sections"][0]
    assert section["text"] == "Synthetic"
    assert section["sectionId"] == "s1.p1:0:9" and section["anchor"] == "s1.p1"
    selection["end"] = 10
    with pytest.raises(ValueError, match="span byte"):
        encode_payload(bound, source)


@pytest.mark.parametrize("start,end", [(-1, 3), (4, 2), (False, 3), (0, 10000)])
def test_invalid_span_offsets_are_rejected(start, end):
    bound, source = fixture()
    bound["payload"]["selectedSections"][0].update(start=start, end=end, selectedHash="a" * 64)
    with pytest.raises(ValueError, match="span"):
        encode_payload(bound, source)


def test_current_worker_authority_is_rechecked_after_corpus_read():
    bound, source = fixture()
    claims, corpus = Mock(), Mock()
    worker = uuid4()
    claims.read_input.side_effect = [bound, PermissionError("source withdrawn during assembly")]
    corpus.read.return_value = source
    with pytest.raises(PermissionError):
        ExecutionPayloads(claims, corpus).read({"workerId": str(worker)}, trusted_worker=worker)
    assert claims.read_input.call_count == 2


def test_other_worker_cannot_supply_a_valid_claim_for_payload_read():
    claims, corpus = Mock(), Mock()
    with pytest.raises(PermissionError):
        ExecutionPayloads(claims, corpus).read({"workerId": str(uuid4())}, trusted_worker=uuid4())
    claims.read_input.assert_not_called()
    corpus.read.assert_not_called()


def test_changed_acceptance_during_read_is_rejected():
    bound, source = fixture()
    altered = copy.deepcopy(bound)
    altered["payload"]["acceptedInput"]["optionsRevision"] = "different"
    claims, corpus = Mock(), Mock()
    claims.read_input.side_effect = [bound, altered]
    corpus.read.return_value = source
    worker = uuid4()
    with pytest.raises(ValueError, match="acceptance changed"):
        ExecutionPayloads(claims, corpus).read({"workerId": str(worker)}, trusted_worker=worker)
