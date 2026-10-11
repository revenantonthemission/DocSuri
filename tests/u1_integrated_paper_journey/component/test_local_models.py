"""Explicit faults in model contracts; useful-output evidence uses real models."""

from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import threading
import time

import pytest

from backend.modules.discovery.local_embedding import LocalEmbeddings, cosine
from backend.modules.summarization.local_assistant import GroundedLocalAssistant
from docsuri_ops.local_models import (
    LocalModelRuntime,
    ModelUnavailable,
    generation_options,
    validate_request,
    validate_response,
)

pytestmark = pytest.mark.u1_component


def request():
    return {
        "model": "qwen3:8b",
        "keep_alive": 0,
        "think": False,
        "stream": False,
        "messages": [
            {"role": "system", "content": "diagnostic"},
            {"role": "user", "content": "test"},
        ],
        "options": {"num_ctx": 2048, "num_predict": 224, "num_thread": 2, "temperature": 0},
    }


def test_model_request_cannot_select_remote_identity_or_unbounded_execution():
    original = request()
    validate_request("qwen3:8b", original)
    changes = [
        {"model": "cloud-model"},
        {"keep_alive": -1},
        {"stream": True},
        {"think": True},
        {"options": {**original["options"], "num_predict": -1}},
        {"options": {**original["options"], "num_ctx": 32768}},
        {"tools": []},
        {"messages": []},
    ]
    for change in changes:
        with pytest.raises(ModelUnavailable):
            validate_request("qwen3:8b", {**original, **change})


def test_sampling_profiles_keep_allocations_and_reject_unplanned_seed_or_options():
    for seed in (42, 43):
        body = request()
        body["options"] = generation_options(seed)
        validate_request("qwen3:8b", body)
        assert body["options"]["num_ctx"] == 2048
        assert body["options"]["num_predict"] == 224
        for change in ({"top_k": 0}, {"seed": 44}, {"num_predict": 1024}):
            with pytest.raises(ModelUnavailable):
                validate_request("qwen3:8b", {**body, "options": {**body["options"], **change}})
    for invalid in (True, 42.0, 44, "42"):
        with pytest.raises(ValueError):
            generation_options(invalid)


def test_assistant_binds_sampling_seed_to_the_request_hash():
    response = {
        "message": {"content": json.dumps({"text": "Diagnostic.", "citations": ["s1.p1"]})},
        "model": "qwen3:8b",
        "prompt_eval_count": 10,
        "eval_count": 10,
        "done_reason": "stop",
    }
    hashes = []
    for seed in (42, 43):
        runtime = FaultRuntime(response)
        result = GroundedLocalAssistant(runtime, sampling_seed=seed).generate(
            source(), task="summary"
        )
        body = runtime.calls[0]["body"]
        validate_request("qwen3:8b", body)
        assert body["options"] == generation_options(seed)
        assert body["think"] is False
        hashes.append(result["requestHash"])
    assert hashes[0] != hashes[1]


def test_embedding_input_is_finite_and_cannot_silently_truncate():
    body = {
        "model": "bge-m3:latest",
        "input": ["diagnostic"],
        "truncate": False,
        "keep_alive": 0,
        "options": {"num_ctx": 2048, "num_thread": 2},
    }
    validate_request("bge-m3:latest", body)
    for change in (
        {"truncate": True},
        {"input": []},
        {"input": ["a"] * 9},
        {"input": ["x" * 8193]},
    ):
        with pytest.raises(ModelUnavailable):
            validate_request("bge-m3:latest", {**body, **change})


def test_truncated_or_wrong_model_response_cannot_be_accepted():
    body = {
        "model": "qwen3:8b",
        "done": True,
        "done_reason": "stop",
        "eval_count": 20,
        "prompt_eval_count": 100,
        "message": {"content": "diagnostic"},
    }
    validate_response(body, model="qwen3:8b")
    for change in (
        {"done": False},
        {"done_reason": "length"},
        {"eval_count": 225},
        {"prompt_eval_count": 2048},
        {"model": "other"},
        {"message": {"content": ""}},
    ):
        with pytest.raises(ModelUnavailable):
            validate_response({**body, **change}, model="qwen3:8b")


class FaultRuntime:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.last_response = None

    @contextmanager
    def work(self, *, seconds):
        yield time.monotonic() + seconds

    def infer(self, **kwargs):
        self.calls.append(kwargs)
        self.last_response = deepcopy(self.response)
        return deepcopy(self.response)


def source():
    text = "An authored diagnostic source."
    return [
        {
            "anchor": "s1.p1",
            "section": "Diagnostic",
            "text": text,
            "textHash": hashlib.sha256(text.encode()).hexdigest(),
        }
    ]


def test_changed_source_and_unsupported_language_never_reach_model():
    runtime = FaultRuntime({})
    assistant = GroundedLocalAssistant(runtime)
    altered = source()
    altered[0]["text"] = "changed"
    for chunks, task, language in (
        (altered, "summary", "en"),
        (source(), "translate", "en"),
        (source(), "unapproved", "en"),
        (source(), "summary", "fr"),
    ):
        with pytest.raises(ValueError):
            assistant.generate(chunks, task=task, language=language)
    assert not runtime.calls


def test_missing_or_invented_citations_are_insufficient_results():
    for payload in (
        {"text": "A fake answer without citations.", "citations": []},
        {"text": "A fake answer.", "citations": ["s9.p9"]},
        {"text": "A fake grouped citation [s1.p1, s9.p9].", "citations": ["s1.p1"]},
    ):
        runtime = FaultRuntime({"message": {"content": json.dumps(payload)}})
        with pytest.raises(ModelUnavailable, match="references"):
            GroundedLocalAssistant(runtime).generate(source(), task="summary")


def test_malformed_or_empty_structured_output_is_not_repaired():
    for payload in (
        "unfinished {",
        json.dumps({"text": "", "citations": ["s1.p1"]}),
        json.dumps({"text": "answer", "citations": ["s1.p1"], "extra": True}),
    ):
        runtime = FaultRuntime({"message": {"content": payload}})
        with pytest.raises(ModelUnavailable):
            GroundedLocalAssistant(runtime).generate(source(), task="summary")


def test_valid_reference_only_establishes_binding_not_semantic_quality():
    runtime = FaultRuntime(
        {
            "message": {
                "content": json.dumps({"text": "Authored fault-control.", "citations": ["s1.p1"]})
            },
            "model": "qwen3:8b",
            "prompt_eval_count": 100,
            "eval_count": 20,
            "done_reason": "stop",
        }
    )
    result = GroundedLocalAssistant(runtime).generate(source(), task="summary")
    assert result["citations"] == ["s1.p1"]
    assert result["sourceAnchors"] == ["s1.p1"] and len(result["requestHash"]) == 64
    validate_request("qwen3:8b", runtime.calls[0]["body"])


def test_bad_embedding_cardinality_dimensions_and_nonfinite_values_reject():
    invalid = [[], [[0.0] * 1024], [[1.0] * 10], [[float("nan")] * 1024]]
    for vectors in invalid:
        with pytest.raises(ModelUnavailable):
            LocalEmbeddings(FaultRuntime({"embeddings": vectors})).embed(["diagnostic"])


def test_cosine_positive_and_negative_controls():
    left = [1.0] + [0.0] * 1023
    assert cosine(left, left) == 1.0
    assert cosine(left, [-x for x in left]) == -1.0
    with pytest.raises(ValueError):
        cosine(left, [0.0] * 1024)


def test_admission_waits_for_release_without_lowering_memory_floor(monkeypatch):
    import docsuri_ops.local_models as module

    runtime = object.__new__(LocalModelRuntime)
    runtime.expires_at = float("inf")
    runtime.root = module.Path("/tmp/docsuri-u1-run/model-runtime")
    attempts = []

    def floor(*, starting):
        attempts.append(starting)
        if len(attempts) == 1:
            raise ModelUnavailable("model resource floor reached")

    monkeypatch.setattr(runtime, "_floor", floor)
    monkeypatch.setattr(runtime, "_request", lambda path: {"models": []})
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    runtime._wait_admission(module.time.monotonic() + 10)
    assert attempts == [True, True]


def test_clone_accounting_distinguishes_reuse_from_unrelated_disk_growth():
    from docsuri_ops.local_models import validate_clone_allocation

    existing = {"pinned-blob": 5 * 1024**3}
    validate_clone_allocation([], existing, dict(existing), 300 * 1024**2)
    with pytest.raises(ModelUnavailable, match="allocation changed"):
        validate_clone_allocation([], existing, {"pinned-blob": 6 * 1024**3}, 0)
    with pytest.raises(ModelUnavailable, match="scratch growth"):
        validate_clone_allocation(["new-blob"], {}, existing, 65 * 1024**2)
    validate_clone_allocation(["new-blob"], {}, existing, 64 * 1024**2)


def test_whole_work_timer_stops_during_blocking_work_and_holds_permit():
    runtime = object.__new__(LocalModelRuntime)
    runtime.permit = threading.RLock()
    stopped = threading.Event()
    calls = []

    def close(*, force=False):
        calls.append(force)
        stopped.set()

    runtime.close = close
    with pytest.raises(ModelUnavailable, match="whole model work deadline"):
        with runtime.work(seconds=0.05):
            competing = []

            def try_other_work():
                try:
                    with runtime.work(seconds=1):
                        competing.append("incorrectly admitted")
                except ModelUnavailable:
                    competing.append("denied")

            contender = threading.Thread(target=try_other_work)
            contender.start()
            contender.join(timeout=1)
            assert competing == ["denied"]
            assert stopped.wait(timeout=1)
    assert calls == [True]


def test_failed_section_rejects_whole_result_and_preserves_partial_diagnostics():
    runtime = FaultRuntime(
        {
            "message": {
                "content": json.dumps(
                    {
                        "text": "Diagnostic supported output.",
                        "citations": ["s1.p1"],
                    }
                )
            },
            "model": "qwen3:8b",
            "prompt_eval_count": 10,
            "eval_count": 10,
            "done_reason": "stop",
        }
    )
    assistant = GroundedLocalAssistant(runtime)
    chunks = source() + [dict(source()[0], anchor="s1.p2", section="Different diagnostic")]
    with pytest.raises(ModelUnavailable, match="references"):
        assistant.generate(chunks, task="summary")
    assert [a["status"] for a in assistant.attempts] == ["returned-bound-section", "failed"]
    assert runtime.calls[0]["work_deadline"] == runtime.calls[1]["work_deadline"]


def test_invalid_later_source_is_rejected_before_any_inference_or_attempt_record():
    runtime = FaultRuntime({})
    for change in ({"text": "changed source"}, {"anchor": "invalid [anchor]"}):
        assistant = GroundedLocalAssistant(runtime)
        chunks = source() + [{**source()[0], "anchor": "s1.p2", **change}]
        with pytest.raises(ValueError):
            assistant.generate(chunks, task="summary")
        assert not runtime.calls and not assistant.attempts


def structured_response():
    return {
        "text": "A diagnostic explanation.",
        "citations": ["s1.p1"],
        "definitions": [
            {
                "term": "diagnostic source",
                "meaning": "An authored source used for diagnosis.",
                "anchor": "s1.p1",
                "quote": "An authored diagnostic source.",
            }
        ],
    }


def structured_runtime(payload):
    return FaultRuntime(
        {
            "message": {"content": json.dumps(payload)},
            "model": "qwen3:8b",
            "prompt_eval_count": 100,
            "eval_count": 40,
            "done_reason": "stop",
        }
    )


def test_structured_definition_preserves_exact_evidence_and_renders_without_synthesis():
    runtime = structured_runtime(structured_response())
    result = GroundedLocalAssistant(runtime, structured_summary=True).generate(
        source(), task="summary"
    )
    section = result["sections"][0]
    assert section["definitions"] == structured_response()["definitions"]
    assert section["explanation"] == "A diagnostic explanation."
    assert "diagnostic source: An authored source used for diagnosis. [s1.p1]" in result["text"]
    validate_request("qwen3:8b", runtime.calls[0]["body"])
    assert runtime.calls[0]["body"]["options"]["num_predict"] == 224


@pytest.mark.parametrize(
    "change",
    [
        {"quote": "A fabricated quotation."},
        {"anchor": "s9.p9"},
        {"meaning": ""},
        {"meaning": "d_{\text{model}}"},  # Actual tab after JSON decode, not literal LaTeX.
        {"term": "x" * 65},
        {"quote": "x" * 181},
        {"extra": "unapproved field"},
    ],
)
def test_invalid_definition_rejects_whole_result_without_repair(change):
    payload = structured_response()
    payload["definitions"][0].update(change)
    runtime = structured_runtime(payload)
    assistant = GroundedLocalAssistant(runtime, structured_summary=True)
    with pytest.raises(ModelUnavailable):
        assistant.generate(source(), task="summary")
    assert len(runtime.calls) == 1
    assert assistant.attempts[0]["status"] == "failed"
    assert assistant.attempts[0]["rawResponse"]["message"]["content"] == json.dumps(payload)


def test_empty_definition_array_is_allowed_but_missing_or_unbounded_array_is_not():
    payload = structured_response()
    payload["definitions"] = []
    result = GroundedLocalAssistant(structured_runtime(payload), structured_summary=True).generate(
        source(), task="summary"
    )
    assert result["sections"][0]["definitions"] == []
    for definitions in (None, [structured_response()["definitions"][0]] * 3):
        payload["definitions"] = definitions
        with pytest.raises(ModelUnavailable):
            GroundedLocalAssistant(structured_runtime(payload), structured_summary=True).generate(
                source(), task="summary"
            )
    del payload["definitions"]
    with pytest.raises(ModelUnavailable):
        GroundedLocalAssistant(structured_runtime(payload), structured_summary=True).generate(
            source(), task="summary"
        )


def test_math_backslash_is_preserved_but_decoded_control_characters_are_rejected():
    payload = {"text": r"Dimension d_{\text{model}}.", "citations": ["s1.p1"]}
    result = GroundedLocalAssistant(structured_runtime(payload)).generate(source(), task="summary")
    assert result["text"] == payload["text"]
    for character in ("\t", "\b", "\r", "\n", "\x00", "\x7f"):
        payload["text"] = "Mathematical text " + character
        with pytest.raises(ModelUnavailable, match="control characters"):
            GroundedLocalAssistant(structured_runtime(payload)).generate(source(), task="summary")


def test_translation_keeps_translation_only_shape_in_structured_experiment():
    payload = {"text": "진단 문장입니다.", "citations": ["s1.p1"]}
    runtime = structured_runtime(payload)
    result = GroundedLocalAssistant(runtime, structured_summary=True).generate(
        source(), task="translate", language="ko"
    )
    assert result["text"] == payload["text"]
    assert "definitions" not in runtime.calls[0]["body"]["format"]["properties"]
