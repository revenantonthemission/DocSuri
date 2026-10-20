"""The U6 render policy: one ready novelty result becomes one Notion page-creation body.

Pure functions only. Nothing here reads a clock, a store, the network or the
environment, so the same result, title and marker always give byte-identical output.

- `derive_title` and `marker_for` fix the page title and the export marker (BR2.3, BR4.1).
- `build_page_body` maps the result to the canonical tree
  `{"properties": {"title": ...}, "children": [...]}`, exactly as it will be sent:
  summary, assessments, evidence items (each one top-level block with its quote, claim
  and source nested under it), coverage, limitations, method, and the marker as the last
  top-level block (BR2.3). Text is written as plain text runs, never as markup.
- `check_limits` answers whether that tree fits one page-creation request (BR2.4). A
  breach returns one plain refusal category; content is never truncated or split
  across requests.
- `project_text` is the read-only `renderedText` the owner sees, marker line last.
- `content_hash` is `renderedContentHash` in U4's `digest` form, and `binding_hash` is
  `bindingHash` by the frozen prefix plus JCS over the identity fields (NFR4.2; C09
  2.1.0 hash rule; security design §8.4).
"""

import hashlib
import json
import re
from collections.abc import Mapping
from uuid import UUID

import rfc8785

from .store_support import canonical_digest

TITLE_PREFIX = "신규성 분석 — "
TITLE_FALLBACK = "신규성 분석 결과"
# The derived title's sentence is cut at a word boundary near this many characters.
TITLE_TARGET = 60
# Contract bounds (C09 2.1.0): titles at most 2000 characters, marker at most 200.
TITLE_LIMIT = 2000
MARKER_LIMIT = 200
MARKER_PREFIX = "docsuri-export:v1:"
SHORT_ID_LENGTH = 8

BINDING_PREFIX = b"docsuri:export-binding:v1\n"
BINDING_FIELDS = (
    "ownerId",
    "previewId",
    "revision",
    "source",
    "sourceEligibilityRevision",
    "connectionRevision",
    "destination",
    "renderedContentHash",
    "renderPolicy",
)
# Display-only destination facts (title, context) never enter the binding, so renaming
# a page does not void an approval.
DESTINATION_IDENTITY = (
    "destinationId",
    "connectionId",
    "workspaceId",
    "parentPageId",
    "formatRevision",
)

# Notion's single-request limits for creating a page with content (BR2.4, as documented
# on 2026-10-19). Text lengths count UTF-16 code units, as Notion's JSON clients do, so
# an astral character such as an emoji counts twice and the bound is never undercounted.
RUN_LIMIT = 2000
MAX_TOP_LEVEL_BLOCKS = 100
MAX_LIST_ITEMS = 100
MAX_NESTING = 2
MAX_BLOCKS = 1000
MAX_BODY_BYTES = 500_000

# The plain refusal categories `check_limits` returns.
TITLE_TOO_LONG = "title-too-long"
TOO_MANY_TOP_LEVEL_BLOCKS = "too-many-top-level-blocks"
LIST_TOO_LONG = "list-too-long"
TEXT_RUN_TOO_LONG = "text-run-too-long"
NESTING_TOO_DEEP = "nesting-too-deep"
TOO_MANY_BLOCKS = "too-many-blocks"
BODY_TOO_LARGE = "body-too-large"
REFUSAL_CATEGORIES = (
    TITLE_TOO_LONG,
    TOO_MANY_TOP_LEVEL_BLOCKS,
    LIST_TOO_LONG,
    TEXT_RUN_TOO_LONG,
    NESTING_TOO_DEEP,
    TOO_MANY_BLOCKS,
    BODY_TOO_LARGE,
)

_SENTENCE_END = re.compile(r"[.!?。！？](?=\s|$)")
_SENTENCE_BREAK = re.compile(r"[.!?。！？]+\s+")
_WHITESPACE = re.compile(r"\s")
_NOT_ALNUM = re.compile(r"[^0-9A-Za-z]")

_STANCE = {"supports": "뒷받침", "contradicts": "반박", "uncertain": "불확실"}
_READ_COVERAGE = {"read": "전체 읽음", "partial": "일부 읽음", "not-read": "읽지 않음"}
_SOURCE_KIND = {
    "public-paper": "공개 논문",
    "private-attachment": "비공개 첨부",
    "retrieved-web": "웹 검색 자료",
    "unread-reference": "읽지 않은 참고 문헌",
}
_COVERAGE = {"complete": "전체 검토", "partial": "일부 검토", "abstained": "판단 보류"}
_PREFIX = {"bulleted_list_item": "• ", "quote": "> "}


def text_units(text: str) -> int:
    """The length Notion counts: UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def _prefix_length(text: str, limit: int) -> int:
    """The longest prefix, in code points, whose UTF-16 length is at most `limit`."""
    units = 0
    for index, char in enumerate(text):
        units += 2 if ord(char) > 0xFFFF else 1
        if units > limit:
            return index
    return len(text)


def _cut_point(text: str, limit: int) -> int:
    """Where to end the next run: a sentence boundary in the second half of the
    window, else the last whitespace, else a hard cut for one overlong word."""
    end = _prefix_length(text, limit)
    sentences = [m.end() for m in _SENTENCE_BREAK.finditer(text, 0, end)]
    if sentences and sentences[-1] >= end // 2:
        return sentences[-1]
    spaces = [m.end() for m in _WHITESPACE.finditer(text, 0, end)]
    if spaces:
        return spaces[-1]
    return end


def split_text(text: str, limit: int = RUN_LIMIT) -> list[str]:
    """Split `text` into runs of at most `limit` UTF-16 units, at sentence or word
    boundaries. The runs join back to exactly `text`: nothing is dropped or added."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if type(limit) is not int or limit < 2:
        raise ValueError("a run must hold at least one astral character")
    runs = []
    rest = text
    while text_units(rest) > limit:
        cut = _cut_point(rest, limit)
        runs.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        runs.append(rest)
    return runs


def _short_id(artifact_id) -> str:
    short = _NOT_ALNUM.sub("", str(artifact_id)).lower()[:SHORT_ID_LENGTH]
    if not short:
        raise ValueError("artifact id has no identifying characters")
    return short


def _first_sentence(summary: str) -> str:
    text = " ".join(summary.split())
    found = _SENTENCE_END.search(text)
    return text[: found.end()] if found else text


def _shorten(sentence: str, target: int) -> str:
    if len(sentence) <= target:
        return sentence
    space = sentence.rfind(" ", 0, target + 1)
    head = sentence[:space] if space >= target // 2 else sentence[:target]
    return head.rstrip() + "…"


def derive_title(summary, artifact_id) -> str:
    """The page title, which is also the preview's source title (BR2.3): the summary's
    first sentence cut at a word boundary near 60 characters, prefixed; the fallback
    for an empty summary names the artifact's short identifier."""
    sentence = _first_sentence(summary) if isinstance(summary, str) else ""
    if not sentence:
        return f"{TITLE_FALLBACK} · {_short_id(artifact_id)}"
    return TITLE_PREFIX + _shorten(sentence, TITLE_TARGET)


def marker_for(preview_id: UUID, revision: int) -> str:
    """The export marker of one preview revision (BR4.1). It names only the preview id
    and revision, so it carries no personal data."""
    if not isinstance(preview_id, UUID):
        raise TypeError("preview id must be a UUID")
    if type(revision) is not int or revision < 1:
        raise ValueError("revision must be a positive integer")
    return f"{MARKER_PREFIX}{preview_id.hex}:{revision}"


def _run(text: str) -> dict:
    return {"type": "text", "text": {"content": text}}


def _block(kind: str, text: str, children: list | None = None) -> dict:
    content = {"rich_text": [_run(part) for part in split_text(text)]}
    if children:
        content["children"] = children
    return {"object": "block", "type": kind, kind: content}


def _number(value) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("assessment scores must be numbers")
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("assessment scores must be finite")
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value)


def _require_text(value, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"result field {field} must be text")
    return value


def _require_list(value, field: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"result field {field} must be a list")
    return value


def _summary_blocks(summary: str) -> list:
    text = summary if summary.strip() else "요약이 없습니다."
    return [_block("heading_2", "요약"), _block("paragraph", text)]


def _assessment_block(assessment, numbers: dict) -> dict:
    if not isinstance(assessment, Mapping):
        raise ValueError("an assessment must be an object")
    text = _require_text(assessment.get("label"), "assessments.label")
    if assessment.get("score") is not None:
        text += f" — 점수 {_number(assessment['score'])}"
        low, high = assessment.get("scaleMinimum"), assessment.get("scaleMaximum")
        if low is not None and high is not None:
            text += f" (범위 {_number(low)}–{_number(high)})"
    children = []
    evidence_ids = _require_list(assessment.get("evidenceIds", []), "assessments.evidenceIds")
    if evidence_ids:
        names = ", ".join(numbers.get(item, str(item)) for item in evidence_ids)
        children.append(_block("paragraph", f"관련 근거: {names}"))
    for limitation in _require_list(assessment.get("limitations", []), "limitations"):
        children.append(_block("bulleted_list_item", _require_text(limitation, "limitation")))
    return _block("bulleted_list_item", text, children)


def _evidence_block(position: int, evidence) -> dict:
    if not isinstance(evidence, Mapping):
        raise ValueError("an evidence item must be an object")
    stance = _require_text(evidence.get("stance"), "evidence.stance")
    coverage = _require_text(evidence.get("readCoverage"), "evidence.readCoverage")
    heading = (
        f"근거 {position} · {_STANCE.get(stance, stance)} · "
        f"{_READ_COVERAGE.get(coverage, coverage)}"
    )
    children = []
    if evidence.get("quote") is not None:
        children.append(_block("quote", _require_text(evidence["quote"], "evidence.quote")))
    children.append(_block("paragraph", "주장: " + _require_text(evidence.get("claim"), "claim")))
    kind = _require_text(evidence.get("sourceKind"), "evidence.sourceKind")
    source = f"출처: {_SOURCE_KIND.get(kind, kind)} · "
    source += _require_text(evidence.get("location"), "evidence.location")
    if evidence.get("sourceUrl") is not None:
        source += " · " + _require_text(evidence["sourceUrl"], "evidence.sourceUrl")
    children.append(_block("paragraph", source))
    return _block("bulleted_list_item", heading, children)


def _section(heading: str, blocks: list) -> list:
    return [_block("heading_2", heading), *blocks] if blocks else []


def build_page_body(result: Mapping, *, title: str, marker: str) -> dict:
    """The canonical page-creation body for one novelty result (`prepared.output` of
    U4's export read), exactly as it will be sent. Raises ValueError for a result,
    title or marker that is not well formed; limits are `check_limits`' concern."""
    if not isinstance(result, Mapping):
        raise ValueError("the result must be an object")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("the title must be non-empty text")
    if not isinstance(marker, str) or not 1 <= len(marker) <= MARKER_LIMIT or "\n" in marker:
        raise ValueError("the marker must be one line of at most 200 characters")
    summary = _require_text(result.get("summary"), "summary")
    evidence = _require_list(result.get("evidence"), "evidence")
    coverage = _require_text(result.get("coverage"), "coverage")
    limitations = _require_list(result.get("limitations"), "limitations")
    method = _require_text(result.get("methodRevision"), "methodRevision")
    assessments = _require_list(result.get("assessments") or [], "assessments")
    numbers = {
        item.get("evidenceId"): f"근거 {index}"
        for index, item in enumerate(evidence, start=1)
        if isinstance(item, Mapping)
    }
    children = [
        *_summary_blocks(summary),
        *_section("평가", [_assessment_block(item, numbers) for item in assessments]),
        *_section("근거", [_evidence_block(i, item) for i, item in enumerate(evidence, 1)]),
        _block("paragraph", f"검토 범위: {_COVERAGE.get(coverage, coverage)}"),
        *_section(
            "한계",
            [_block("bulleted_list_item", _require_text(t, "limitation")) for t in limitations],
        ),
        _block("paragraph", f"분석 방법: {method}"),
        _block("paragraph", marker),
    ]
    title_runs = [_run(part) for part in split_text(title)]
    return {"properties": {"title": title_runs}, "children": children}


def _content(block) -> dict:
    if not isinstance(block, Mapping) or not isinstance(block.get(block.get("type")), Mapping):
        raise ValueError("malformed block")
    return block[block["type"]]


def _runs_refusal(runs) -> str | None:
    if not isinstance(runs, list):
        raise ValueError("malformed text runs")
    if len(runs) > MAX_LIST_ITEMS:
        return LIST_TOO_LONG
    for run in runs:
        if text_units(_run_text(run)) > RUN_LIMIT:
            return TEXT_RUN_TOO_LONG
    return None


def _run_text(run) -> str:
    try:
        text = run["text"]["content"]
    except (KeyError, TypeError):
        raise ValueError("malformed text run") from None
    if not isinstance(text, str):
        raise ValueError("malformed text run")
    return text


def _tree_refusal(children: list) -> tuple[str | None, int]:
    """Walk every block below the page; return the first breach and the block count."""
    count = 0
    pending = [(block, 0) for block in children]
    while pending:
        block, depth = pending.pop()
        count += 1
        content = _content(block)
        refusal = _runs_refusal(content.get("rich_text", []))
        if refusal:
            return refusal, count
        nested = content.get("children", [])
        if not isinstance(nested, list):
            raise ValueError("malformed children")
        if nested and depth + 1 > MAX_NESTING:
            return NESTING_TOO_DEEP, count
        if len(nested) > MAX_LIST_ITEMS:
            return LIST_TOO_LONG, count
        pending.extend((child, depth + 1) for child in nested)
    return None, count


def _require_body(body) -> tuple[list, list]:
    if not isinstance(body, Mapping) or set(body) != {"properties", "children"}:
        raise ValueError("the body must hold exactly properties and children")
    properties = body["properties"]
    if not isinstance(properties, Mapping) or not isinstance(properties.get("title"), list):
        raise ValueError("the body must carry a title")
    if not isinstance(body["children"], list):
        raise ValueError("the body's children must be a list")
    return properties["title"], body["children"]


def check_limits(body: Mapping) -> str | None:
    """None when the body fits one page-creation request (BR2.4), else the first breach
    as one of REFUSAL_CATEGORIES. The body is never altered. Size is measured as the
    ASCII-escaped compact JSON, the largest form a client may send."""
    title, children = _require_body(body)
    if text_units("".join(_run_text(run) for run in title)) > TITLE_LIMIT:
        return TITLE_TOO_LONG
    if len(children) > MAX_TOP_LEVEL_BLOCKS:
        return TOO_MANY_TOP_LEVEL_BLOCKS
    refusal = _runs_refusal(title)
    if refusal:
        return refusal
    refusal, count = _tree_refusal(children)
    if refusal:
        return refusal
    if count > MAX_BLOCKS:
        return TOO_MANY_BLOCKS
    if len(json.dumps(body, separators=(",", ":"), ensure_ascii=True)) > MAX_BODY_BYTES:
        return BODY_TOO_LARGE
    return None


def _project(block, depth: int, lines: list) -> None:
    kind = block["type"]
    content = _content(block)
    text = "".join(_run_text(run) for run in content.get("rich_text", []))
    if kind.startswith("heading") and lines and lines[-1]:
        lines.append("")
    indent = "  " * depth
    first, *rest = text.split("\n")
    lines.append(indent + _PREFIX.get(kind, "") + first)
    lines.extend(indent + line for line in rest)
    for child in content.get("children", []):
        _project(child, depth + 1, lines)


def project_text(body: Mapping) -> str:
    """The read-only `renderedText`: the title, then every block in order, nested items
    indented, and the marker as the last line (BR2.3)."""
    title, children = _require_body(body)
    lines = ["".join(_run_text(run) for run in title), ""]
    for block in children:
        _project(block, 0, lines)
    return "\n".join(lines)


def content_hash(body: Mapping) -> str:
    """`renderedContentHash`: SHA-256 of the page body in U4's `digest` form (sorted
    keys, compact separators, UTF-8 without escaping), with no prefix (NFR4.2)."""
    _require_body(body)
    return canonical_digest(body)


def binding_hash(binding: Mapping) -> str:
    """`bindingHash`: SHA-256 of the frozen prefix and the RFC 8785 bytes of exactly the
    nine binding fields, with `destination` reduced to its five identity fields."""
    if not isinstance(binding, Mapping):
        raise ValueError("the binding must be an object")
    missing = [field for field in BINDING_FIELDS if field not in binding]
    destination = binding.get("destination")
    if missing or not isinstance(destination, Mapping):
        raise ValueError("the binding lacks fields: " + ", ".join(missing or ["destination"]))
    absent = [field for field in DESTINATION_IDENTITY if field not in destination]
    if absent:
        raise ValueError("the destination lacks identity fields: " + ", ".join(absent))
    preimage = {field: binding[field] for field in BINDING_FIELDS}
    preimage["destination"] = {field: destination[field] for field in DESTINATION_IDENTITY}
    return hashlib.sha256(BINDING_PREFIX + rfc8785.dumps(preimage)).hexdigest()
