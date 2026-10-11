"""Real local outputs retained for independent semantic rubric review.

These checks verify execution and source binding. They do not automatically
certify the factual completeness or quality of a generated answer.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

from backend.artifacts import Artifact, PrivateArtifacts
from backend.local_profile import LocalProfile
from backend.modules.discovery.local_embedding import LocalEmbeddings, cosine
from backend.modules.summarization.local_assistant import GroundedLocalAssistant
from docsuri_ops.local_models import LocalModelRuntime
from scripts.load_docsuri_u1_papers import parser_identity, validate_manifest
from scripts.verify_docsuri_u1 import private_json, source_identity

pytestmark = pytest.mark.u1_model


@pytest.fixture(scope="module")
def model_context():
    profile = LocalProfile.load(Path(os.environ["DOCSURI_U1_ENVIRONMENT_FILE"]))
    manifest = json.loads((profile.root / "paper-fixtures.json").read_text())
    validate_manifest(manifest, profile.run_id)
    assert manifest["parserIdentity"] == parser_identity()
    files = PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
    papers = {}
    for paper in manifest["papers"]:
        files.read(Artifact(**paper["rawArtifact"]))
        papers[paper["paper"]] = json.loads(files.read(Artifact(**paper["parsedArtifact"])))
    result = {
        "runId": profile.run_id,
        "startedAt": time.time(),
        "sourceIdentity": source_identity(),
        "paperManifest": manifest,
        "semanticReview": "pending",
        "cases": [],
    }
    evidence = profile.root / f"model-output-{time.time_ns()}.json"
    private_json(evidence, result)
    runtime = LocalModelRuntime(profile.root, profile.run_id, profile.expires_at)
    try:
        with runtime:
            result["runtime"] = runtime.identity
            yield runtime, papers, result, evidence
    finally:
        result["runtime"] = runtime.identity
        result["samples"] = runtime.samples
        result["serverExit"] = runtime.process.returncode if runtime.process else None
        result["endedAt"] = time.time()
        private_json(evidence, result)
        print(f"protected model evidence: {evidence}")


CASES = [
    (
        "P1-scaling",
        "1706.03762",
        ["s3.2.1.eq1", "s3.2.1.p4"],
        "summary",
        "en",
    ),
    (
        "P1-position",
        "1706.03762",
        ["s3.5.p1", "s3.5.p2", "s3.5.p3", "s3.5.p4"],
        "summary",
        "en",
    ),
    (
        "P2-memories",
        "2005.11401",
        [
            "s1.p2",
            "s1.fig1",
            "s2.1.1.p1",
            "s2.1.2.p1",
            "s2.2.p2",
            "s2.3.p1",
        ],
        "summary",
        "en",
    ),
    ("P1-en-ko", "1706.03762", ["s3.5.p1"], "translate", "ko"),
]


@pytest.mark.parametrize("case_id,paper,anchors,task,language", CASES)
def test_real_bound_source_response(model_context, case_id, paper, anchors, task, language):
    runtime, papers, result, evidence = model_context
    indexed = {c["anchor"]: c for c in papers[paper]["chunks"]}
    chunks = [dict(indexed[anchor]) for anchor in anchors]
    if task == "translate":
        original = chunks[0]["text"]
        start = original.index("To this end,")
        end = original.index("stacks.", start) + len("stacks.")
        text = original[start:end]
        chunks[0].update(
            text=text,
            textHash=hashlib.sha256(text.encode()).hexdigest(),
            sourceSpan={
                "start": start,
                "end": end,
                "fullTextHash": indexed[anchors[0]]["textHash"],
            },
        )
    record = {
        "case": case_id,
        "paper": paper,
        "inputs": chunks,
        "startedAt": time.time(),
        "semanticReview": "pending",
    }
    assistant = GroundedLocalAssistant(runtime)
    try:
        record["output"] = assistant.generate(chunks, task=task, language=language)
        record["status"] = "returned-bound-result"
        assert record["output"]["citations"]
    except Exception as exc:
        record.update(status="failed", error=type(exc).__name__ + ": " + str(exc))
        raise
    finally:
        record["sectionAttempts"] = assistant.attempts
        record["rawResponse"] = runtime.last_response
        record["wallSeconds"] = time.time() - record["startedAt"]
        result["cases"].append(record)
        private_json(evidence, result)
        # keep_alive=0 requests unload; verify no loaded model before another call.
        deadline = time.monotonic() + 10
        while runtime.process and runtime.process.poll() is None and time.monotonic() < deadline:
            if not runtime._request("/api/ps").get("models"):
                break
            time.sleep(0.2)


def test_real_embedding_retrieves_relevant_source_in_two_paper_diagnostic(model_context):
    runtime, papers, result, evidence = model_context
    selected = [
        next(c for c in papers[p]["chunks"] if c["anchor"] == anchor)
        for p, anchor in [("1706.03762", "s3.5.p1"), ("2005.11401", "s1.p2")]
    ]
    queries = [
        "How does the Transformer represent token order?",
        "What memories does retrieval augmented generation combine?",
    ]
    texts = [c["text"] for c in selected] + queries
    record = {
        "case": "two-paper-dense-retrieval",
        "inputHashes": [hashlib.sha256(t.encode()).hexdigest() for t in texts],
        "queries": queries,
        "sourceAnchors": [c["anchor"] for c in selected],
        "startedAt": time.time(),
    }
    try:
        vectors = LocalEmbeddings(runtime).embed(texts)
        scores = [[cosine(query, source) for source in vectors[:2]] for query in vectors[2:]]
        record.update(status="returned", scores=scores, dimensions=len(vectors[0]))
        assert scores[0][0] > scores[0][1] and scores[1][1] > scores[1][0]
    except Exception as exc:
        record.update(status="failed", error=type(exc).__name__ + ": " + str(exc))
        raise
    finally:
        record["wallSeconds"] = time.time() - record["startedAt"]
        result["cases"].append(record)
        private_json(evidence, result)
