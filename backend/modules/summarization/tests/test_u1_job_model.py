"""Test-after checks of U1 value/codec behavior, not real-store authority proof."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from summarization.domain.job import ContentJob, JobEvent, JobState, job_state_payload
from summarization.domain.job_protocol import (
    ClaimDisposition,
    DispatchMessage,
    DispatchOutcome,
    EffectStatus,
    ExecutionClaim,
    GenerationEffect,
    JobInput,
    JobProtocolError,
    JobSubmission,
    JobTask,
    MaintenanceClass,
    MaintenanceProgress,
    SubmissionBinding,
    canonical_json,
    content_digest,
)
from summarization.domain.models import (
    AbstainDTO,
    CostDegradedDTO,
    PendingDTO,
    Persona,
    Scope,
    SourceUnavailableDTO,
    SummaryResultDTO,
    Task,
)
from summarization.domain.prepared_result import (
    PreparationIdentity,
    PreparedJobResult,
    final_content,
    inspect_outcome,
    safe_job_error,
)
from tests.stubs import valid_draft


def job_input(task: JobTask = JobTask.SUMMARIZE) -> JobInput:
    return JobSubmission.legacy(task.value, {"paperId": "2401.00001", "version": 2}).input


def summary_payload() -> dict:
    return SummaryResultDTO(task=Task.SUMMARY, summary=valid_draft(),
                            meta={"source": "full_text"}).to_dict()


def translation_payload() -> dict:
    return {
        "status": "ok", "task": "translate", "cached": False,
        "translation": {
            "docModel": {
                "meta": {
                    "paperId": "2401.00001", "version": 2, "title": "개인화된 용어",
                    "provenance": {"sourceTier": "native_html",
                                   "parserVersion": "docmodel-parser@4",
                                   "schemaVersion": "1", "generatedAt": "2026-10-03T00:00:00Z"},
                },
                "fullText": "준비 시점의 사용자 용어입니다.", "sections": [],
            },
            "keptTerms": ["Attention"],
            "standardGlossary": [{"term": "attention", "translated": "사용자 용어"}],
        },
    }


def capture(task: JobTask = JobTask.SUMMARIZE, payload: object | None = None) -> PreparedJobResult:
    return PreparedJobResult.capture(
        "job-one", "owner-one", task,
        payload if payload is not None else summary_payload(),
        result_id="prepared-one", prepared_at=100,
        identity=PreparationIdentity(job_input(task)),
    )


def test_browser_profile_captures_full_input_and_key_without_mutable_alias() -> None:
    raw = {"taskType": "summarize", "idempotencyKey": "a" * 64,
           "input": job_input().to_dict()}
    submission = JobSubmission.browser(raw)
    raw["input"]["persona"] = "beginner"
    assert submission.input.persona is Persona.EXPERT
    assert submission.input.scope is Scope.FULL
    assert submission.input.request(submission.task).abstract is None
    assert len(submission.input_identity) == 64
    with pytest.raises(FrozenInstanceError):
        submission.input.version = 3


@pytest.mark.parametrize("change", [
    {"taskType": "novelty"}, {"idempotencyKey": "short"}, {"idempotencyKey": "A" * 64},
    {"ownerId": "forged"}, {"input": {"paperId": "2401.1"}},
    {"input": {**job_input().to_dict(), "version": True}},
    {"input": {**job_input().to_dict(), "version": 1.5}},
    {"input": {**job_input().to_dict(), "scope": "abstract"}},
    {"input": {**job_input().to_dict(), "targetLang": "en"}},
    {"input": {**job_input().to_dict(), "abstract": "untrusted"}},
])
def test_browser_profile_refuses_invalid_or_extra_authority_input(change: dict) -> None:
    body = {"taskType": "summarize", "idempotencyKey": "a" * 64,
            "input": job_input().to_dict(), **change}
    with pytest.raises(JobProtocolError):
        JobSubmission.browser(body)


def test_supported_legacy_defaults_and_keys_do_not_synthesize_a_binding() -> None:
    summary = JobSubmission.legacy("summary", {"paperId": "2401.00001v3", "abstract": "ignored"})
    translation = JobSubmission.legacy("translate", {"paperId": "2401.00001"}, "legacy-key")
    assert summary.input.version == 3
    assert summary.input.scope is Scope.FULL
    assert summary.idempotency_key is None
    assert translation.input.scope is Scope.ABSTRACT
    assert translation.input.target_lang.value == "ko"
    assert translation.idempotency_key == "legacy-key"
    assert summary.input_identity != translation.input_identity


@pytest.mark.parametrize("payload", [{}, [], {"paperId": ""}, {"paperId": "a\x00"},
                                      {"paperId": "x", "version": -1},
                                      {"paperId": "x", "persona": "invented"}])
def test_legacy_normalization_never_guesses_invalid_supplied_values(payload: object) -> None:
    with pytest.raises(JobProtocolError):
        JobSubmission.legacy("summary", payload)


def test_private_canonical_identity_preserves_unicode_array_order_and_json_numbers() -> None:
    a = {"z": ["한글", 1.25, 2], "a": {"b": True}}
    b = {"a": {"b": True}, "z": ["한글", 1.25, 2]}
    assert canonical_json(a) == '{"a":{"b":true},"z":["한글",1.25,2]}'
    assert content_digest(a) == content_digest(b)
    assert content_digest(a) != content_digest({**a, "z": list(reversed(a["z"]))})
    assert content_digest(a) != content_digest({**a, "z": ["한글 ", 1.25, 2]})


@pytest.mark.parametrize("payload", [float("nan"), float("inf"), float("-inf"),
                                     {"value": float("nan")}, {1: "numeric-key"},
                                     {"value": object()}, {"value": "\ud800"}])
def test_canonical_codec_refuses_nonfinite_nonjson_or_non_utf8_payloads(payload: object) -> None:
    with pytest.raises(JobProtocolError):
        canonical_json(payload)


def test_queue_v1_identity_ignores_additive_owner_and_input_as_authority() -> None:
    message = DispatchMessage.parse({"schemaVersion": 1, "jobId": "job-one",
                                     "dispatchId": "send-one",
                                     "userId": "forged", "input": {"paperId": "not-authority"}})
    assert message.to_dict() == {"schemaVersion": 1, "jobId": "job-one", "dispatchId": "send-one"}


@pytest.mark.parametrize("body", [{"schemaVersion": 2, "jobId": "j", "dispatchId": "d"},
                                  {"schemaVersion": True, "jobId": "j", "dispatchId": "d"},
                                  {"jobId": "j"},
                                  {"schemaVersion": 1, "jobId": "j", "dispatchId": ""}])
def test_queue_codec_does_not_adopt_missing_or_unknown_authority(body: object) -> None:
    with pytest.raises(JobProtocolError):
        DispatchMessage.parse(body)


def test_binding_unknown_retains_key_and_rejection_alone_has_release_evidence() -> None:
    initial = SubmissionBinding("binding", "job", "owner", "dispatch", "a" * 64, "key")
    unknown = replace(initial, outcome=DispatchOutcome.UNKNOWN, fence=1, started_at=100)
    assert unknown.retained
    with pytest.raises(JobProtocolError, match="release"):
        replace(unknown, released_at=120)
    rejected = replace(unknown, outcome=DispatchOutcome.REJECTED, released_at=120)
    assert not rejected.retained
    with pytest.raises(JobProtocolError):
        replace(initial, outcome=DispatchOutcome.SENDING)


def test_effect_intent_prepared_and_active_claim_do_not_adopt_legacy_jobs() -> None:
    effect = GenerationEffect("job", 1, "worker", 190, 100)
    with pytest.raises(JobProtocolError, match="binding"):
        replace(effect, status=EffectStatus.PREPARED)
    with pytest.raises(JobProtocolError):
        replace(effect, attempt=2)
    legacy = ContentJob("job", "owner", "summarize", JobState.RUNNING, {})
    with pytest.raises(JobProtocolError, match="grant"):
        ExecutionClaim(ClaimDisposition.ACTIVE, legacy, effect)
    claim = ExecutionClaim(ClaimDisposition.ACTIVE, replace(legacy, authority_version=1), effect)
    assert claim.effect.fence == 1


def test_progress_cursor_is_an_explicit_paired_key_not_successful_empty_scan() -> None:
    progress = MaintenanceProgress("u1-staging", MaintenanceClass.AMBIGUOUS_DISPATCH, "cycle", 100)
    assert progress.last_success_at is None
    with pytest.raises(JobProtocolError, match="cursor"):
        replace(progress, last_job_id="j")
    assert replace(progress, last_job_id="j", last_eligible_at=90).processed == 0


def test_summary_capture_preserves_reproducibility_and_filters_internal_metadata() -> None:
    payload = summary_payload()
    payload["modelId"] = "not-public"
    payload["meta"]["objectKey"] = "not-public"
    result = capture(payload=payload).initialize_expiry(3700)
    content = result.envelope(101)["preparedResult"]["content"]
    assert content["summary"]["reproducibility"] == payload["summary"]["reproducibility"]
    assert isinstance(content["summary"]["reproducibility"], dict)
    assert "modelId" not in content and "objectKey" not in content["meta"]
    assert "contentDigest" not in json.dumps(result.envelope(101))


def test_translation_capture_retains_final_personalization_and_unavailable_provenance() -> None:
    payload = translation_payload()
    result = capture(JobTask.TRANSLATE, payload).initialize_expiry(3700)
    payload["translation"]["docModel"]["fullText"] = "현재 설정으로 바뀐 문자열"
    content = result.envelope(101)["preparedResult"]["content"]
    assert content["translation"]["docModel"]["fullText"] == "준비 시점의 사용자 용어입니다."
    assert content["translation"]["standardGlossary"][0]["translated"] == "사용자 용어"
    identity = json.loads(result.serialized_identity)
    assert identity["generation"]["status"] == "unavailable"
    assert identity["personalization"]["status"] == "unavailable"
    assert "modelVersion" not in identity["generation"]
    assert "assetId" not in result.envelope(101)["preparedResult"]


@pytest.mark.parametrize("doc", [
    {"status": "building", "retryAfterMs": 1000}, {"status": "license_unavailable"},
    {"status": "source_unavailable", "reason": "missing"}, {"status": "ok", "docModel": {}},
    {"meta": {"paperId": "2401.00001", "version": 2, "title": "missing provenance"},
     "fullText": "text", "sections": []},
])
def test_translation_rejects_wrappers_and_missing_bare_document_provenance(doc: dict) -> None:
    payload = translation_payload()
    payload["translation"]["docModel"] = doc
    with pytest.raises(JobProtocolError):
        capture(JobTask.TRANSLATE, payload)


@pytest.mark.parametrize("change", [{"version": 1}, {"paperId": "other"}, {"version": True}])
def test_translation_matches_recorded_paper_revision_without_coercion(change: dict) -> None:
    payload = translation_payload()
    payload["translation"]["docModel"]["meta"].update(change)
    with pytest.raises(JobProtocolError):
        capture(JobTask.TRANSLATE, payload)


def test_snapshot_digest_and_persisted_content_cannot_be_overwritten_or_bypassed() -> None:
    result = capture().initialize_expiry(3700)
    envelope = result.envelope(101)
    envelope["preparedResult"]["content"]["summary"]["tldr"] = "local mutation"
    assert result.envelope(102)["preparedResult"]["content"]["summary"]["tldr"] != "local mutation"
    with pytest.raises(JobProtocolError, match="unavailable"):
        replace(result, content_digest="0" * 64)
    with pytest.raises(JobProtocolError, match="unavailable"):
        replace(result, serialized_content="{}")
    with pytest.raises(JobProtocolError, match="immutable"):
        result.initialize_expiry(4000)


def test_staged_expiry_and_payload_purge_preserve_the_fixed_boundary() -> None:
    staged = capture()
    with pytest.raises(JobProtocolError, match="not_ready"):
        staged.envelope(101)
    result = staged.initialize_expiry(200)
    assert result.envelope(199)["resultRef"] == "prepared-one"
    with pytest.raises(JobProtocolError, match="expired"):
        result.envelope(200)
    with pytest.raises(JobProtocolError, match="not_due"):
        result.purge(199)
    purged = result.purge(201)
    assert purged.expires_at == 200 and purged.serialized_content is None
    assert purged.serialized_identity == "{}"
    assert purged.purge(202) is purged
    with pytest.raises(JobProtocolError, match="expired"):
        purged.envelope(202)


@pytest.mark.parametrize("response,state,category", [
    (AbstainDTO("generation_unavailable"), JobState.ABSTAINED, None),
    (AbstainDTO("private raw error"), JobState.ABSTAINED, None),
    (CostDegradedDTO("private raw error"), JobState.FAILED, "cost_degraded"),
    (SourceUnavailableDTO("private raw error"), JobState.FAILED, "source_unavailable"),
    (PendingDTO(), JobState.FAILED, "generation_protocol_error"),
])
def test_unsuccessful_outcomes_never_become_completed_content(response, state, category) -> None:
    result = inspect_outcome(JobTask.SUMMARIZE, job_input(), response)
    assert result.state is state and result.serialized_content is None
    assert (result.error.error_type if result.error else None) == category
    assert "private raw error" not in str(result)


def test_successful_pipeline_mapping_requires_valid_matching_final_content() -> None:
    response = SummaryResultDTO(task=Task.SUMMARY, summary=valid_draft())
    result = inspect_outcome(JobTask.SUMMARIZE, job_input(), response)
    assert result.state is JobState.COMPLETED and result.serialized_content
    wrong_task = inspect_outcome(JobTask.TRANSLATE, job_input(JobTask.TRANSLATE), response)
    assert wrong_task.state is JobState.FAILED
    with pytest.raises(JobProtocolError):
        final_content(JobTask.SUMMARIZE, job_input(), {"status": "ok", "task": "summary"})


def test_thrown_serialization_and_unknown_error_categories_are_scrubbed() -> None:
    class BrokenResponse:
        def to_dict(self):
            raise RuntimeError("private raw provider credentials")

    result = inspect_outcome(JobTask.SUMMARIZE, job_input(), BrokenResponse())
    assert result.state is JobState.FAILED
    assert result.error.error_type == "generation_failed"
    assert safe_job_error("unknown private category").error_type == "generation_failed"
    assert "private" not in str(result)


def test_event_cursor_and_sequence_remain_distinct_and_state_never_echoes_input() -> None:
    event = JobEvent(3, "942", "job-one", "owner", JobState.RUNNING, created_at=100)
    body = event.to_dict()
    assert body["eventId"] == "942" and body["seq"] == 3
    job = ContentJob("job-one", "owner", "summarize", JobState.RUNNING,
                     {"paperId": "not-telemetry"}, seq=3)
    assert job_state_payload(job) == {"jobId": "job-one", "state": "RUNNING", "seq": 3}
