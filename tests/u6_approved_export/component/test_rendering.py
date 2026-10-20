"""The render policy: golden hashes, title, block order, single-request limits, splitting."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from backend.modules.export import rendering
from backend.modules.export.rendering import (
    BODY_TOO_LARGE,
    LIST_TOO_LONG,
    MAX_BODY_BYTES,
    NESTING_TOO_DEEP,
    REFUSAL_CATEGORIES,
    TEXT_RUN_TOO_LONG,
    TITLE_TOO_LONG,
    TOO_MANY_BLOCKS,
    TOO_MANY_TOP_LEVEL_BLOCKS,
    binding_hash,
    build_page_body,
    check_limits,
    content_hash,
    derive_title,
    marker_for,
    project_text,
    split_text,
)
from backend.modules.research.repository import digest
from docsuri_shared.workspace import wire

VECTORS = Path(__file__).resolve().parents[3] / "shared" / "export-hash-vectors.json"
ARTIFACT = UUID("5a1d7c3e-9b2f-4e8a-a6c1-0d4b3f2e1a99")
PREVIEW = UUID("0f6c3a7e-2b9d-4c1e-8a5f-6b7c8d9e0a1b")
U4_RESULT_BYTES = 32768
U4_EVIDENCE_ITEMS = 32


def evidence_item(index: int, *, quote: str | None = "인용된 문장입니다.") -> dict:
    return {
        "evidenceId": str(uuid5(NAMESPACE_URL, f"u6-render-evidence-{index}")),
        "sourceKind": "public-paper",
        "sourceId": f"paper-{index}",
        "sourceVersion": "1",
        "sourceContentHash": f"{index:064x}",
        "location": f"p.{index}",
        "readCoverage": "partial" if quote else "not-read",
        "quote": quote,
        "claim": f"근거 {index}의 주장입니다.",
        "stance": "supports" if quote else "uncertain",
        "sourceUrl": f"https://example.org/paper/{index}",
    }


def novelty_result() -> dict:
    evidence = [evidence_item(1), evidence_item(2, quote=None)]
    return {
        "summary": "관련 연구 두 건을 확인했습니다. 차이는 학습 방식에 있습니다.",
        "evidence": evidence,
        "coverage": "partial",
        "limitations": ["두 편만 읽었습니다.", "**굵게** <b>표시</b>는 서식이 아닙니다."],
        "methodRevision": "u4-synthetic-extractive-1",
        "assessments": [
            {
                "criterionId": "novelty",
                "label": "신규성",
                "score": 3.0,
                "scaleMinimum": 1,
                "scaleMaximum": 5,
                "evidenceIds": [evidence[0]["evidenceId"], evidence[1]["evidenceId"]],
                "limitations": ["점수는 참고용입니다."],
            }
        ],
    }


def run(text: str) -> dict:
    return {"type": "text", "text": {"content": text}}


def block(text: str = "x", children: list | None = None, runs: list | None = None) -> dict:
    content = {"rich_text": runs if runs is not None else [run(text)]}
    if children is not None:
        content["children"] = children
    return {"object": "block", "type": "paragraph", "paragraph": content}


def page(children: list, title: list | None = None) -> dict:
    return {"properties": {"title": title or [run("T")]}, "children": children}


def plain(item: dict) -> str:
    return "".join(r["text"]["content"] for r in item[item["type"]]["rich_text"])


def wire_size(body: dict) -> int:
    return len(json.dumps(body, separators=(",", ":"), ensure_ascii=True))


def sized_page(total: int) -> dict:
    """A body whose ASCII-escaped compact JSON is exactly `total` bytes."""
    empty = [[run("") for _ in range(100)] for _ in range(3)]
    deficit = total - wire_size(page([block(runs=r) for r in empty]))
    filled = []
    for _ in range(3):
        runs = []
        for _ in range(100):
            take = min(2000, deficit)
            runs.append(run("a" * take))
            deficit -= take
        filled.append(block(runs=runs))
    assert deficit == 0
    body = page(filled)
    assert wire_size(body) == total
    return body


def padded(result: dict, pad, total: int = U4_RESULT_BYTES) -> dict:
    """Grow one ASCII text field until U4's own size measure reaches `total` bytes."""
    deficit = total - len(json.dumps(result).encode())
    sentences = ("Finding %d is stated plainly here. " * 2000) % tuple(range(2000))
    return pad(result, sentences[:deficit])


def maximal_by_evidence() -> dict:
    evidence = [evidence_item(i, quote="q") for i in range(1, U4_EVIDENCE_ITEMS + 1)]
    result = {**novelty_result(), "evidence": evidence, "assessments": []}
    share = (U4_RESULT_BYTES - len(json.dumps(result).encode())) // U4_EVIDENCE_ITEMS
    words = ("Quoted finding %d reads as written. " * 400) % tuple(range(400))
    evidence = [{**item, "quote": "q" + words[: share - 1]} for item in evidence]
    result = {**result, "evidence": evidence}
    return padded(result, lambda r, extra: {**r, "summary": r["summary"] + extra})


def maximal_by_summary() -> dict:
    evidence = [evidence_item(i, quote="q") for i in range(1, U4_EVIDENCE_ITEMS + 1)]
    result = {**novelty_result(), "evidence": evidence, "summary": "S. "}
    return padded(result, lambda r, extra: {**r, "summary": r["summary"] + extra})


def test_both_hashes_match_every_golden_vector_and_the_u4_digest():
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    rendered = vectors["renderedContentHash"]["cases"]
    bound = vectors["bindingHash"]["cases"]
    assert rendered and bound
    for case in rendered:
        assert content_hash(case["input"]) == case["sha256"], case["name"]
        assert digest(case["input"]) == case["sha256"], case["name"]
    assert vectors["bindingHash"]["prefix"].encode() == rendering.BINDING_PREFIX
    for case in bound:
        assert binding_hash(case["input"]) == case["sha256"], case["name"]
        # Display-only destination facts and extra fields never enter the binding.
        shown = {**case["input"], "renderedText": "보기 전용"}
        display = {"title": "새 이름", "context": "위치"}
        shown["destination"] = {**case["input"]["destination"], **display}
        assert binding_hash(shown) == case["sha256"], case["name"]
        moved = {**case["input"], "destination": {**case["input"]["destination"]}}
        moved["destination"]["parentPageId"] = "f" * 32
        assert binding_hash(moved) != case["sha256"], case["name"]
    body = build_page_body(novelty_result(), title="제목", marker=marker_for(PREVIEW, 1))
    assert content_hash(body) == digest(body)
    with pytest.raises(ValueError, match="renderPolicy"):
        binding_hash({k: v for k, v in bound[0]["input"].items() if k != "renderPolicy"})
    destination = {k: v for k, v in bound[0]["input"]["destination"].items() if k != "workspaceId"}
    with pytest.raises(ValueError, match="workspaceId"):
        binding_hash({**bound[0]["input"], "destination": destination})
    with pytest.raises(ValueError):
        content_hash({**body, "extra": True})


TITLES = (
    (
        "관련 연구 두 건을 확인했습니다. 차이는 학습 방식에 있습니다.",
        "신규성 분석 — 관련 연구 두 건을 확인했습니다.",
    ),
    ("첫 줄이\n이어집니다. 다음 문장.", "신규성 분석 — 첫 줄이 이어집니다."),
    ("a" * 100, "신규성 분석 — " + "a" * 60 + "…"),
    ("", "신규성 분석 결과 · 5a1d7c3e"),
    ("   \n\t ", "신규성 분석 결과 · 5a1d7c3e"),
    (None, "신규성 분석 결과 · 5a1d7c3e"),
)


def test_title_is_cut_at_a_word_boundary_prefixed_and_falls_back():
    for summary, expected in TITLES:
        assert derive_title(summary, ARTIFACT) == expected, summary
    with pytest.raises(ValueError):
        derive_title("", "---")
    sentence = "신규성 검토 결과가 " * 20
    title = derive_title(sentence, ARTIFACT)
    head = title.removeprefix(rendering.TITLE_PREFIX)
    assert title.startswith(rendering.TITLE_PREFIX) and head.endswith("…")
    kept = head.removesuffix("…")
    assert 30 <= len(kept) <= 60
    normalized = " ".join(sentence.split())
    assert normalized.startswith(kept) and normalized[len(kept)] == " "


def test_marker_and_malformed_inputs_are_refused():
    marker = marker_for(PREVIEW, 12)
    assert marker == "docsuri-export:v1:0f6c3a7e2b9d4c1e8a5f6b7c8d9e0a1b:12"
    assert len(marker) <= rendering.MARKER_LIMIT
    with pytest.raises(TypeError):
        marker_for(str(PREVIEW), 1)
    for revision in (0, -1, True, "1"):
        with pytest.raises(ValueError):
            marker_for(PREVIEW, revision)
    for result, title, mark in (
        ([], "제목", marker),
        ({**novelty_result(), "summary": None}, "제목", marker),
        ({**novelty_result(), "evidence": "none"}, "제목", marker),
        ({**novelty_result(), "assessments": [{"label": "x", "score": float("nan")}]}, "t", marker),
        (novelty_result(), " ", marker),
        (novelty_result(), "제목", "line\nbreak"),
        (novelty_result(), "제목", "m" * 201),
    ):
        with pytest.raises(ValueError):
            build_page_body(result, title=title, marker=mark)
    with pytest.raises(ValueError):
        check_limits({"properties": {"title": []}})


def test_blocks_come_in_order_as_plain_text_with_evidence_nested_and_marker_last():
    result = novelty_result()
    title = derive_title(result["summary"], ARTIFACT)
    marker = marker_for(PREVIEW, 1)
    body = build_page_body(result, title=title, marker=marker)
    assert list(body) == ["properties", "children"]
    assert [plain(item) for item in body["children"]] == [
        "요약",
        result["summary"],
        "평가",
        "신규성 — 점수 3 (범위 1–5)",
        "근거",
        "근거 1 · 뒷받침 · 일부 읽음",
        "근거 2 · 불확실 · 읽지 않음",
        "검토 범위: 일부 검토",
        "한계",
        "두 편만 읽었습니다.",
        "**굵게** <b>표시</b>는 서식이 아닙니다.",
        "분석 방법: u4-synthetic-extractive-1",
        marker,
    ]
    first, second = body["children"][5], body["children"][6]
    assert [c["type"] for c in first["bulleted_list_item"]["children"]] == [
        "quote",
        "paragraph",
        "paragraph",
    ]
    assert [plain(c) for c in first["bulleted_list_item"]["children"]] == [
        "인용된 문장입니다.",
        "주장: 근거 1의 주장입니다.",
        "출처: 공개 논문 · p.1 · https://example.org/paper/1",
    ]
    assert [c["type"] for c in second["bulleted_list_item"]["children"]] == [
        "paragraph",
        "paragraph",
    ]
    assessment = body["children"][3]["bulleted_list_item"]["children"]
    assert [plain(c) for c in assessment] == ["관련 근거: 근거 1, 근거 2", "점수는 참고용입니다."]
    last = body["children"][-1]
    assert last["type"] == "paragraph" and "children" not in last["paragraph"]
    for item in json.dumps(body, ensure_ascii=False).split('"type":"text"')[1:]:
        assert '"annotations"' not in item and '"link"' not in item
    text = project_text(body)
    lines = text.split("\n")
    assert lines[0] == title and lines[-1] == marker
    assert "  > 인용된 문장입니다." in lines
    assert "• **굵게** <b>표시</b>는 서식이 아닙니다." in lines
    assert check_limits(body) is None
    assert build_page_body({**result, "summary": " "}, title=title, marker=marker)["children"][
        1
    ] == block_text("요약이 없습니다.")


def block_text(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [run(text)]}}


def nested(depth: int) -> dict:
    return block() if depth == 0 else block(children=[nested(depth - 1)])


LIMITS = {
    "top-level-blocks": (
        page([block()] * 100),
        page([block()] * 101),
        TOO_MANY_TOP_LEVEL_BLOCKS,
    ),
    "children-list": (
        page([block(children=[block()] * 100)]),
        page([block(children=[block()] * 101)]),
        LIST_TOO_LONG,
    ),
    "rich-text-list": (
        page([block(runs=[run("a")] * 100)]),
        page([block(runs=[run("a")] * 101)]),
        LIST_TOO_LONG,
    ),
    "title-list": (
        page([], title=[run("a")] * 100),
        page([], title=[run("a")] * 101),
        LIST_TOO_LONG,
    ),
    "nesting": (page([nested(2)]), page([nested(3)]), NESTING_TOO_DEEP),
    "total-blocks": (
        page([block(children=[block()] * 99)] * 10),
        page([block(children=[block()] * 99)] * 10 + [block()]),
        TOO_MANY_BLOCKS,
    ),
    "run-length": (page([block("a" * 2000)]), page([block("a" * 2001)]), TEXT_RUN_TOO_LONG),
    "run-length-astral": (
        page([block("🔬" * 1000)]),
        page([block("🔬" * 1000 + "a")]),
        TEXT_RUN_TOO_LONG,
    ),
    "title-length": (
        page([], title=[run("가" * 2000)]),
        page([], title=[run("가" * 2000), run("가")]),
        TITLE_TOO_LONG,
    ),
}


@pytest.mark.parametrize("name", [*LIMITS, "body-bytes"])
def test_every_limit_accepts_its_bound_and_refuses_one_past_it(name):
    if name == "body-bytes":
        at_bound, past_bound, category = (
            sized_page(MAX_BODY_BYTES),
            sized_page(MAX_BODY_BYTES + 1),
            BODY_TOO_LARGE,
        )
    else:
        at_bound, past_bound, category = LIMITS[name]
    assert category in REFUSAL_CATEGORIES
    before = json.dumps(past_bound, ensure_ascii=False)
    assert check_limits(at_bound) is None
    assert check_limits(past_bound) == category
    assert json.dumps(past_bound, ensure_ascii=False) == before  # never truncated


def test_text_splits_at_sentence_then_word_boundaries_without_loss():
    assert split_text("") == [] and split_text("짧은 문장.") == ["짧은 문장."]
    sentences = "가나다라마바사. " * 300
    runs = split_text(sentences)
    assert "".join(runs) == sentences and len(runs) > 1
    assert all(rendering.text_units(r) <= 2000 for r in runs)
    assert all(r.endswith(". ") for r in runs[:-1])
    words = "word " * 900
    runs = split_text(words)
    assert "".join(runs) == words and all(r.endswith(" ") for r in runs[:-1])
    long_word = "x" * 4500
    assert split_text(long_word) == ["x" * 2000, "x" * 2000, "x" * 500]
    astral = "a" + "🔬" * 1000
    runs = split_text(astral)
    assert runs == ["a" + "🔬" * 999, "🔬"] and "".join(runs) == astral
    body = build_page_body({**novelty_result(), "summary": sentences}, title="t", marker="m")
    summary = body["children"][1]["paragraph"]["rich_text"]
    assert len(summary) > 1 and "".join(r["text"]["content"] for r in summary) == sentences
    for bad in ((None,), ("text", 1), ("text", 2.5)):
        with pytest.raises((TypeError, ValueError)):
            split_text(*bad)


def test_rendering_is_deterministic():
    result = novelty_result()
    reordered = dict(reversed(list(result.items())))
    title = derive_title(result["summary"], ARTIFACT)
    marker = marker_for(PREVIEW, 3)
    first = build_page_body(result, title=title, marker=marker)
    second = build_page_body(reordered, title=derive_title(reordered["summary"], ARTIFACT),
                             marker=marker_for(PREVIEW, 3))
    assert json.dumps(first, ensure_ascii=False) == json.dumps(second, ensure_ascii=False)
    assert content_hash(first) == content_hash(second)
    assert project_text(first) == project_text(second)
    other = build_page_body(result, title=title, marker=marker_for(PREVIEW, 4))
    assert content_hash(other) != content_hash(first)


@pytest.mark.parametrize("build", [maximal_by_evidence, maximal_by_summary])
def test_u4_maximum_result_fits_one_request(build):
    result = build()
    size = len(json.dumps(result).encode())
    assert U4_RESULT_BYTES - 64 <= size <= U4_RESULT_BYTES
    assert len(result["evidence"]) == U4_EVIDENCE_ITEMS
    wire.ResearchOutput.model_validate_json(json.dumps(result), strict=True)
    marker = marker_for(PREVIEW, 1)
    body = build_page_body(result, title=derive_title(result["summary"], ARTIFACT), marker=marker)
    assert check_limits(body) is None
    evidence = [b for b in body["children"] if plain(b).startswith("근거 ")]
    assert len(evidence) == U4_EVIDENCE_ITEMS
    assert project_text(body).split("\n")[-1] == marker
