"""Test-after C2/ASCII-v2 evidence; no database or read-side authority assertion."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest
from docsuri_shared._generated.dtos.summarization_schema import Reproducibility
from docsuri_shared.dtos import DocModel
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from summarization.domain.assembler import ResultAssembler
from summarization.domain.job import JobState
from summarization.domain.job_protocol import (
    JobProtocolError,
    JobTask,
    canonical_json,
    content_digest,
)
from summarization.domain.models import (
    Glossary,
    SummaryResultDTO,
    Task,
    TermMapping,
    TranslationDraft,
)
from summarization.domain.prepared_result import inspect_outcome
from summarization.domain.result_storage_codec import (
    CANONICAL_VERSION,
    CONTENT_ENCODING,
    canonical_content,
    decode_canonical_content,
    decode_prepared_content,
    prepared_content_digest,
)
from tests.stubs import valid_draft
from tests.test_u1_job_model import capture, job_input, summary_payload, translation_payload

PAIR = "\ud800\udc00"
SCALAR = "\U00010000"
LITERAL_PAIR = r"\ud800\udc00"
STRINGS = ["\x00", r"\u0000", "", "e\u0301", "é", "한글", "😀", ' \t\r\n"\\ ', "\ud800",
           PAIR, SCALAR, LITERAL_PAIR, r"\\ud800\\udc00", "\\"]
ALL_CODEPOINT_TEXT = st.text(alphabet=st.integers(0, 0x10FFFF).map(chr), max_size=30)


def test_actual_dto_and_shared_reproducibility_shape_have_exact_capture_parity() -> None:
    draft = replace(valid_draft(), reproducibility={"code": "code\x00" + PAIR,
                                                  "data": r"data\u0000" + SCALAR + LITERAL_PAIR})
    dto = SummaryResultDTO(task=Task.SUMMARY, summary=draft)
    actual = dto.to_dict()
    assert Reproducibility.model_validate(actual["summary"]["reproducibility"], strict=True)
    result = capture(payload=actual).initialize_expiry(200)
    assert result.content() == actual
    assert result.envelope(199)["preparedResult"]["content"] == actual
    assert result.serialized_content.isascii() and "\x00" not in result.serialized_content
    stored_digest = hashlib.sha256(result.serialized_content.encode("ascii")).hexdigest()
    assert result.content_digest == stored_digest
    assert result.content_encoding == CONTENT_ENCODING
    assert result.canonical_version == CANONICAL_VERSION


def test_actual_translation_dto_and_final_assembler_values_not_shared_base_are_captured() -> None:
    document = translation_payload()["translation"]["docModel"]
    document["sections"] = [{"id": "s", "title": "", "blocks": [
        {"id": "p", "type": "paragraph", "text": "사용자 결과"},
    ]}]
    dto = SummaryResultDTO(Task.TRANSLATE, translation=TranslationDraft(
        DocModel.model_validate_json(json.dumps(document)),
    ), meta={"source": "full_text"})
    base = dto.to_dict()
    original = Glossary(user_overrides=(TermMapping("사용자", "개인\x00", False),))
    final = ResultAssembler.render_translation(base, original)
    result = capture(JobTask.TRANSLATE, final).initialize_expiry(200)
    changed = ResultAssembler.render_translation(
        base, Glossary(user_overrides=(TermMapping("사용자", "changed setting", False),)),
    )
    assert "개인\x00" in final["translation"]["docModel"]["fullText"]
    changed_text = changed["translation"]["docModel"]["fullText"]
    assert changed_text != final["translation"]["docModel"]["fullText"]
    assert result.envelope(101)["preparedResult"]["content"] == final
    assert result.content()["meta"] == {"source": "full_text"}
    assert "standardGlossary" in result.content()["translation"]


@pytest.mark.parametrize("reproduction", [
    "flat", [], {"data": "data"}, {"code": "code"}, {"code": 1, "data": "data"},
    {"code": "code", "data": None}, {"code": "code", "data": "data", "extra": "do not drop"},
])
def test_malformed_success_has_no_fallback_defaults_or_dropped_fields(reproduction) -> None:
    with pytest.raises(ValidationError):
        Reproducibility.model_validate(reproduction, strict=True)
    dto = SummaryResultDTO(Task.SUMMARY, replace(valid_draft(), reproducibility=reproduction))
    with pytest.raises(JobProtocolError, match="content_invalid"):
        capture(payload=dto.to_dict())
    inspected = inspect_outcome(JobTask.SUMMARIZE, job_input(), dto)
    assert inspected.state is JobState.FAILED and inspected.serialized_content is None
    assert inspected.error.error_type == "generation_protocol_error"


@pytest.mark.parametrize("task", list(JobTask))
@pytest.mark.parametrize("text", STRINGS)
def test_full_content_string_domain_survives_capture_decode_and_public_v1(task, text) -> None:
    payload = summary_payload() if task is JobTask.SUMMARIZE else translation_payload()
    if task is JobTask.SUMMARIZE:
        payload["summary"].update(
            tldr=text, method=text, results=text, limitations=text,
            contributions=[text, ""], reproducibility={"code": text, "data": text},
        )
    else:
        doc = payload["translation"]["docModel"]
        doc["fullText"] = doc["meta"]["title"] = text
        doc["meta"]["macros"] = {text: text}
        doc["sections"] = [{"id": "s", "title": text,
                            "blocks": [{"id": "p", "type": "paragraph", "text": text}]}]
        payload["translation"]["keptTerms"] = [text]
        payload["translation"]["standardGlossary"] = [{"term": text, "translated": text}]
    result = capture(task, payload).initialize_expiry(200)
    assert result.envelope(101)["preparedResult"]["schemaVersion"] == 1
    assert result.content() == payload


@given(st.text(), st.text())
@settings(max_examples=120, deadline=None)
def test_property_c2_roundtrip_detachment_and_identity(code: str, data: str) -> None:
    payload = summary_payload()
    payload["summary"]["reproducibility"] = {"code": code, "data": data}
    result = capture(payload=payload)
    payload["summary"]["reproducibility"]["code"] = "mutated after capture"
    assert result.content()["summary"]["reproducibility"] == {"code": code, "data": data}
    assert prepared_content_digest(result.content()) == result.content_digest


def test_pair_scalar_and_literal_escape_have_distinct_reversible_bytes_digests_and_keys() -> None:
    originals = (PAIR, SCALAR, LITERAL_PAIR)
    serialized = tuple(canonical_content(value) for value in originals)
    assert serialized == (r'"\\ud800\\udc00"', r'"\ud800\udc00"', r'"\\\\ud800\\\\udc00"')
    assert len(set(serialized)) == len({prepared_content_digest(value) for value in originals}) == 3
    assert tuple(decode_canonical_content(value) for value in serialized) == originals
    assert [ord(char) for char in decode_canonical_content(serialized[0])] == [0xD800, 0xDC00]
    assert [ord(char) for char in decode_canonical_content(serialized[1])] == [0x10000]
    value = {key: [key, "\x00", r"\u0000", "\\"] for key in originals}
    stored = canonical_content(value)
    assert decode_canonical_content(stored) == value
    assert len(decode_canonical_content(stored)) == 3
    assert canonical_content(dict(reversed(list(value.items())))) == stored


@pytest.mark.parametrize("task", list(JobTask))
def test_both_task_capture_and_public_read_retain_distinct_pair_scalar_and_escape(task) -> None:
    results = []
    for text in (PAIR, SCALAR, LITERAL_PAIR):
        payload = summary_payload() if task is JobTask.SUMMARIZE else translation_payload()
        if task is JobTask.SUMMARIZE:
            payload["summary"]["reproducibility"] = {"code": text, "data": LITERAL_PAIR}
        else:
            doc = payload["translation"]["docModel"]
            doc["fullText"] = text
            doc["meta"]["macros"] = {PAIR: text, SCALAR: text, LITERAL_PAIR: text}
        result = capture(task, payload).initialize_expiry(200)
        assert result.content() == payload
        assert result.envelope(101)["preparedResult"]["content"] == payload
        results.append(result)
    assert len({result.serialized_content for result in results}) == 3
    assert len({result.content_digest for result in results}) == 3
    # A different admitted string cannot be substituted under the original identity/digest.
    with pytest.raises(JobProtocolError, match="unavailable"):
        replace(results[0], serialized_content=results[1].serialized_content)


def test_actual_python_translation_dto_fields_are_not_coalesced_or_normalized() -> None:
    doc = DocModel.model_validate_json(json.dumps(translation_payload()["translation"]["docModel"]))
    doc.fullText = PAIR
    doc.meta.title = SCALAR
    doc.meta.macros = {PAIR: SCALAR, LITERAL_PAIR: PAIR}
    dto = SummaryResultDTO(Task.TRANSLATE, translation=TranslationDraft(doc))
    raw = dto.to_dict()
    result = capture(JobTask.TRANSLATE, raw).initialize_expiry(200)
    assert raw["translation"]["docModel"]["fullText"] == PAIR
    assert result.envelope(101)["preparedResult"]["content"] == raw
    assert dto.translation.doc_model.fullText == PAIR


@pytest.mark.parametrize("task", list(JobTask))
@given(high=st.integers(0xD800, 0xDBFF), low=st.integers(0xDC00, 0xDFFF),
       prefix=ALL_CODEPOINT_TEXT, suffix=ALL_CODEPOINT_TEXT)
@settings(max_examples=120, deadline=None)
def test_forced_surrogate_adjacency_escape_values_and_keys_preserve_complete_source_strings(
    task: JobTask, high: int, low: int, prefix: str, suffix: str,
) -> None:
    pair = chr(high) + chr(low)
    scalar = chr(0x10000 + (high - 0xD800) * 0x400 + low - 0xDC00)
    literal = f"\\u{high:04x}\\u{low:04x}"
    family = [prefix + value + suffix for value in (pair, scalar, literal)]
    assert len({canonical_content(value) for value in family}) == 3
    assert len({prepared_content_digest(value) for value in family}) == 3
    # Every example includes adjacency, its scalar, literal escapes, a literal
    # backslash, NUL and decomposed/whitespace content; no random coverage assumption.
    code = prefix + pair + scalar + literal + "\\\x00e\u0301 \t\n" + suffix
    value = {family[0]: code, family[1]: literal, family[2]: [pair, scalar, literal]}
    assert decode_canonical_content(canonical_content(value)) == value
    payload = summary_payload() if task is JobTask.SUMMARIZE else translation_payload()
    if task is JobTask.SUMMARIZE:
        payload["summary"]["reproducibility"] = {"code": code, "data": literal}
    else:
        doc = payload["translation"]["docModel"]
        doc["fullText"] = code
        doc["meta"]["macros"] = {key: value for key, value in zip(family, family, strict=True)}
        payload["translation"]["keptTerms"] = family
    result = capture(task, payload).initialize_expiry(200)
    assert result.content() == payload
    assert result.envelope(101)["preparedResult"]["content"] == payload


@pytest.mark.parametrize("layered", [
    "\\", r"\u", r"\ud80", r"\uD800", r"\ud800\uDC00", r"\u0041", r"\q",
    "\ud800", "\udc00", {r"\u0041": "noncanonical key"},
])
def test_malformed_noncanonical_string_layer_cannot_be_guessed_into_originals(layered) -> None:
    # These are admitted SOURCE values. Only their unlayered storage form is
    # refused; valid encoding must preserve every one, not narrow the C2 domain.
    assert decode_canonical_content(canonical_content(layered)) == layered
    serialized = json.dumps(layered, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    # A matching digest does not excuse an invalid inverse/canonical representation.
    digest = hashlib.sha256(serialized.encode("ascii")).hexdigest()
    with pytest.raises(JobProtocolError, match="unavailable"):
        decode_prepared_content(serialized, content_encoding=CONTENT_ENCODING,
                                canonical_version=CANONICAL_VERSION, digest=digest)


@pytest.mark.parametrize("serialized", [
    '{ "a":1}', '{"a":1,"a":1}', '{"a":NaN}', '{"a":1e999}', '{"a":1',
    '{"x":"한글"}', '{"x":"\x00"}', '{"b":1,"a":2}', '{"x":"\\u0061"}',
])
def test_corrupt_nonfinite_noncanonical_or_nonascii_storage_is_unavailable(serialized) -> None:
    with pytest.raises(JobProtocolError, match="unavailable"):
        decode_prepared_content(serialized, content_encoding=CONTENT_ENCODING,
                                canonical_version=CANONICAL_VERSION, digest="a" * 64)


@pytest.mark.parametrize("changes", [
    {"content_encoding": None}, {"content_encoding": "jsonb"}, {"canonical_version": None},
    {"canonical_version": 1}, {"canonical_version": True}, {"content_digest": "0" * 64},
    {"owner_id": "other"}, {"job_id": "other"}, {"prepared_result_id": "other"},
    {"prepared_at": 101}, {"serialized_identity": "{}"},
])
def test_versions_digest_and_preparation_identity_cannot_be_adopted_or_swapped(changes) -> None:
    with pytest.raises(JobProtocolError, match="unavailable"):
        replace(capture(), **changes)


def test_content_only_canonical_policy_does_not_change_server_or_browser_input_bytes() -> None:
    value = {"z": ["한글", 1.25], "a": "e\u0301"}
    assert canonical_json(value) == '{"a":"é","z":["한글",1.25]}'
    assert canonical_content(value) == r'{"a":"e\u0301","z":["\ud55c\uae00",1.25]}'
    expected_digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    assert content_digest(value) == expected_digest
    assert content_digest(value) != prepared_content_digest(value)
    serialized_request = ('{"paperId":"한글","version":2,"targetLang":"ko",'
                          '"persona":"expert","scope":"full"}')
    browser_bytes = ("사용자:한글:summarize:" + serialized_request).encode("utf-8")
    assert b"\\ud" not in browser_bytes
    assert json.loads(serialized_request)["paperId"] == "한글"
    assert canonical_content({"x": "\x00"}) != canonical_content({"x": r"\u0000"})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "bad"}, {"x": object()}])
def test_encoder_refuses_unsupported_or_nonfinite_values(value) -> None:
    with pytest.raises(JobProtocolError):
        canonical_content(value)
