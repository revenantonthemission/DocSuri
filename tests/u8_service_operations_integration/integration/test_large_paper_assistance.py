"""Paper assistance at production's corpus limits (U8 plan Step 24; your decision of
2026-10-24, "Fix it in U8").

On Step 12's production stand-in, with the real builders and a mock model transport:

1. a paper at the chunk limit, 200 chunks (lowered from 2,000 by your decision of
   2026-11-08, L1-74, and measured again by your answer of 2026-11-09, L1-81), is
   offered and assisted in production;
2. a paper with split pieces is assisted, and its citations lead to the block;
3. a synthetic realm still refuses above 256 chunks: the composed realm offers no
   assistance for a 257-chunk paper, and the payload refuses one;
4. U3's lane passes with `.coveragerc.u3` unchanged (the lane's own run, and
   `operations/test_u3_scope.py`).

The 200-chunk paper is loaded once per module, without vectors (assistance reads no
embedding), so the file stays inside its half's 300 s bound.
"""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import httpx
import pytest

from backend.modules.summarization.payload import BUILT_RULE, selected_sections
from backend.modules.summarization.u3_catalog import catalog_for
from backend.modules.summarization.u8_assistance_sources import (
    MAX_CHUNKS,
    PAYLOAD_RULE,
    SELECTION_BYTES,
    blocks,
    definitions_for,
)
from tests.u8_service_operations_integration import research_flows as rf
from tests.u8_service_operations_integration.host_flows import import_paper


def assistant(body: dict) -> httpx.Response:
    anchors = body["format"]["properties"]["citations"]["items"]["enum"]
    content = json.dumps({"text": f"요약입니다 [{anchors[0]}]", "citations": anchors[:1]},
                         ensure_ascii=False)
    return httpx.Response(200, json={
        "model": body["model"], "message": {"role": "assistant", "content": content},
        "done": True, "done_reason": "stop", "prompt_eval_count": 40, "eval_count": 20})


def chunk(index: int, text: str | None = None, **extra) -> dict:
    return {"anchor": f"p{index}", "section": f"Section {index // 50}",
            "text": text or f"Paragraph {index} describes one part of the method in detail.",
            **extra}


LARGE = [chunk(i) for i in range(200)]
BIG_TEXT = ["Piece one of a long proof states the lemma and its conditions. " * 40,
            "Piece two applies the lemma to the bounded case in full detail. " * 40,
            "Piece three closes the argument and names the remaining case. " * 40]
SPLIT = [
    {"anchor": "intro", "section": "Introduction", "text": "We prove a bound on attention."},
    *[{"anchor": "proof", "section": "Proof", "text": text.strip(), "piece": number}
      for number, text in enumerate(BIG_TEXT, start=1)],
    {"anchor": "end", "section": "Conclusion", "text": "The bound is tight."},
]


@pytest.fixture(scope="module")
def env(realm):
    with rf.production_research(realm, ready=("assistance",)) as value:
        value.model.chat = assistant
        value.large = import_paper(value.standin, LARGE)
        yield value


def assist(env, owner, ref, *, option_index: int = 0) -> tuple[dict, dict]:
    """Production's own catalog, admission and one dispatch through the shared runtime."""
    from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
    from backend.modules.summarization.requests import AssistanceRequests

    corpus = env.parts["paper-corpus"]
    source = corpus["corpus_repository"].read(ref["versionId"])
    catalog = corpus["assistance_rule"].catalog(source)
    options = catalog.options()
    option = options["options"][option_index]
    repository = GuardedAssistanceRepository(env.standin.transactions, corpus["files"])
    glossary = repository.current_glossary(owner)["revision"]
    requests = AssistanceRequests(corpus["dispatch"].admission, corpus["corpus_repository"],
                                  corpus["assistance_rule"].catalog)
    accepted = requests.submit(owner, uuid4(), {
        "paper": catalog.paper, "contentRevision": catalog.content_revision,
        "contentHash": source["source_hash"], "operation": option["operation"],
        "optionId": option["optionId"], "optionsRevision": catalog.revision,
        "glossaryRevision": str(glossary), "processingPolicy": options["policy"],
    })
    # As the model lane runs it: the lane first, handed to the worker's executor thread.
    with env.runtime.work(90, wait=0), env.runtime.hand_over():
        assert corpus["dispatch"].run_once(limit=1) == {"executed": 1, "deferred": 0}
    with env.standin.connect("assistance") as conn:
        job = conn.execute("SELECT * FROM assistance.job WHERE id=%s",
                           (accepted["id"],)).fetchone()
    return job, catalog.definitions[option_index]


def result_of(env, owner, job) -> dict:
    from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository

    repository = GuardedAssistanceRepository(env.standin.transactions,
                                             env.parts["paper-corpus"]["files"])
    reference = repository.result_reference(owner, job["id"])
    return json.loads(repository.result(owner, reference["resultId"]))


# 1. A paper at the chunk limit (200) is offered and assisted in production ----------------


def test_a_paper_at_the_chunk_limit_is_offered_and_assisted_in_production(env):
    owner = rf.member(env, "large")
    source = env.parts["paper-corpus"]["corpus_repository"].read(env.large["versionId"])
    assert len(source["content"]["chunks"]) == MAX_CHUNKS == 200
    options = env.parts["paper-corpus"]["assistance_rule"].catalog(source).options()
    assert [item["operation"] for item in options["options"]] == ["summary", "translation"]
    job, definition = assist(env, owner, env.large)
    assert job["state"] == "succeeded"
    anchors = {item["anchor"] for item in definition["selectedSections"]}
    result = result_of(env, owner, job)
    assert result["citations"] and set(result["citations"]) <= anchors
    # The worker's payload accepted all 200 chunks under production's rule.
    assert env.parts["paper-corpus"]["dispatch"].payloads.rule is PAYLOAD_RULE


# 2. Split pieces are assisted as one block, and citations lead to the block ---------------


def test_a_split_blocks_pieces_are_offered_selected_and_cited_as_that_block(env):
    owner = rf.member(env, "split")
    ref = import_paper(env.standin, SPLIT)
    units = blocks([{**item, "textHash": hashlib.sha256(item["text"].encode()).hexdigest()}
                    for item in SPLIT])
    assert [unit["anchor"] for unit in units] == ["intro", "proof", "end"]
    proof = units[1]
    assert proof["text"] == " ".join(text.strip() for text in BIG_TEXT)
    assert proof["textHash"] == hashlib.sha256(proof["text"].encode()).hexdigest()
    job, definition = assist(env, owner, ref)
    selection = definition["selectedSections"]
    assert [item["anchor"] for item in selection] == ["intro", "proof"]
    # The block over the selection's bound is selected as a span of its own text.
    span = selection[1]
    assert (span["start"], span["textHash"]) == (0, proof["textHash"])
    assert sum(len(i["text"].encode()) for i in units[:1]) + len(
        proof["text"][:span["end"]].encode()) <= SELECTION_BYTES
    assert job["state"] == "succeeded"
    result = result_of(env, owner, job)
    # Each citation names a block's own anchor, the split one included.
    assert "proof" in result["citations"] and set(result["citations"]) <= {"intro", "proof"}
    assert {section["anchor"] for section in result["sections"]} <= {"intro", "proof"}


def test_the_production_rule_refuses_what_it_cannot_cite():
    # A repeated anchor that is not a run of pieces stays ambiguous: no options at all.
    repeated = [{"anchor": "a", "section": "S", "text": "one", "textHash": "x"},
                {"anchor": "a", "section": "S", "text": "two", "textHash": "y"}]
    assert definitions_for({"content": {"chunks": repeated}}) is None
    assert definitions_for({"content": {"chunks": [chunk(i) for i in range(201)]}}) is None
    assert definitions_for({"content": {}}) is None


# 3. A synthetic realm still refuses above 256 chunks ---------------------------------------


def _source(count: int) -> dict:
    chunks = [{**chunk(i), "textHash": hashlib.sha256(chunk(i)["text"].encode()).hexdigest()}
              for i in range(count)]
    return {"id": "v", "paper_id": "p", "eligibility_revision": "1", "source_hash": "h" * 64,
            "content": {"chunks": chunks}}


def test_a_synthetic_realm_still_refuses_a_257_chunk_paper(realm, transactions):
    from backend.u8_host import BuildContext, build_paper_corpus

    composed = build_paper_corpus(BuildContext(realm, transactions, None, {}))
    assert "assistance_rule" not in composed
    assert composed["dispatch"].payloads.rule is BUILT_RULE
    # The composed realm's catalog (no source rule) offers nothing for 257 chunks.
    assert catalog_for(_source(257), provider_ready=True) is None
    assert catalog_for(_source(256), provider_ready=True) is not None
    selection = [{"anchor": "p0", "heading": "Section 0",
                  "textHash": _source(1)["content"]["chunks"][0]["textHash"]}]
    with pytest.raises(ValueError, match="finite allocation"):
        selected_sections(_source(257), selection)
    # Production's rule takes a paper at its own limit, 200, now below the synthetic 256
    # (L1-81); the refusals at 257 above stay.
    assert selected_sections(_source(200), selection, max_chunks=PAYLOAD_RULE.max_chunks,
                             blocks=PAYLOAD_RULE.blocks)[0]["anchor"] == "p0"
    # L1-81: production's rule refuses 201 chunks, which the built 256 would accept, so
    # this case fails again whenever the payload seam falls back to the built limit.
    with pytest.raises(ValueError, match="finite allocation"):
        selected_sections(_source(201), selection, max_chunks=PAYLOAD_RULE.max_chunks,
                          blocks=PAYLOAD_RULE.blocks)
