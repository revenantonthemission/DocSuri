"""Explicit faults in model contracts; useful-output evidence uses real models."""

from copy import deepcopy
import hashlib
import json

import pytest

from backend.modules.discovery.local_embedding import LocalEmbeddings, cosine
from backend.modules.summarization.local_assistant import GroundedLocalAssistant
from docsuri_ops.local_models import (
    LocalModelRuntime,
    ModelUnavailable,
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

    def infer(self, **kwargs):
        self.calls.append(kwargs)
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
