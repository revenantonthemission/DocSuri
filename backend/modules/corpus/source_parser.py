"""Bounded source adaptation around the retained deterministic document parser."""

from __future__ import annotations

import hashlib
from datetime import datetime
from html.parser import HTMLParser

from backend.modules.corpus.limits import SYNTHETIC_LIMITS, CorpusLimitExceeded, CorpusLimits
from bs4 import BeautifulSoup
from docsuri_ingestion.docmodel.parser import parse_html_to_docmodel
from docsuri_shared.docmodel_contract import DOCMODEL_PARSER_VERSION, DOCMODEL_SCHEMA_VERSION
from docsuri_shared.dtos import SourceTier


class _StructureBudget(HTMLParser):
    void = frozenset(
        (
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        )
    )

    def __init__(self, limits: CorpusLimits = SYNTHETIC_LIMITS):
        super().__init__(convert_charrefs=False)
        self.nodes = 0
        self.stack = []
        self.limits = limits

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if tag not in self.void:
            self.stack.append(tag)
        if self.nodes > self.limits.max_elements or len(self.stack) > self.limits.max_depth:
            raise CorpusLimitExceeded("source structure exceeds local parsing allocation")

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack.pop() != tag:
                pass


def parse_source(
    raw: bytes, *, paper: str, version: int, title: str, fetched_at: datetime,
    limits: CorpusLimits = SYNTHETIC_LIMITS,
) -> tuple[dict, list[dict]]:
    """The document model and its chunks, under the profile's limits (Step 23). A
    split block's pieces keep its anchor and carry `piece` (1, 2, ...)."""
    if b"\0" in raw or not raw:
        raise ValueError("source bytes outside local parsing policy")
    if len(raw) > limits.max_source_bytes:
        raise CorpusLimitExceeded("source bytes outside local parsing policy")
    html = raw.decode("utf-8", errors="strict")
    budget = _StructureBudget(limits)
    budget.feed(html)
    budget.close()
    soup = BeautifulSoup(html, "lxml")
    for element in soup.find_all(("script", "style", "iframe", "object", "embed")):
        element.decompose()
    document = parse_html_to_docmodel(
        str(soup),
        paper_id=paper,
        version=version,
        title=title,
        abstract=None,
        source_tier=SourceTier.native_html,
        parser_version=DOCMODEL_PARSER_VERSION,
        schema_version=DOCMODEL_SCHEMA_VERSION,
        generated_at=fetched_at,
    ).model_dump(mode="json", exclude_none=True)
    return document, chunks_from_document(document, limits)


def chunks_from_document(document: dict, limits: CorpusLimits = SYNTHETIC_LIMITS) -> list[dict]:
    """The bounded chunks of one parsed document model: a block per chunk, a block over
    8 KB refused or split by the profile's limits, at most `max_chunks` (Step 23). The
    migration's paper import converts v1's document models through the same walk
    (BR8.7, U8 plan Step 31)."""
    chunks = []

    def walk(sections, ancestors):
        for section in sections:
            heading = " / ".join([*ancestors, section["title"]])
            for block in section["blocks"]:
                # Preserve the parser's literal text/LaTeX, without stripping
                # equations into ambiguous Unicode or duplicating MathML tokens.
                kind = block["type"]
                if kind in ("paragraph", "code"):
                    text = block.get("text", block.get("code", ""))
                elif kind == "formula":
                    text = block["latex"]
                elif kind in ("figure", "table"):
                    text = block.get("caption", "")
                elif kind == "list":
                    text = "\n".join(item["text"] for item in block["items"])
                else:
                    raise ValueError("unsupported parsed block kind")
                if not text.strip():
                    continue
                pieces = limits.pieces(text)
                for number, piece in enumerate(pieces, start=1):
                    chunk = {
                        "anchor": block["id"],
                        "section": heading,
                        "text": piece,
                        "kind": kind,
                        "textHash": hashlib.sha256(piece.encode()).hexdigest(),
                    }
                    if len(pieces) > 1:
                        chunk["piece"] = number
                    chunks.append(chunk)
                if len(chunks) > limits.max_chunks:
                    raise CorpusLimitExceeded("source projection exceeds local chunk allocation")
            walk(section.get("sections", []), [*ancestors, section["title"]])

    walk(document["sections"], [])
    if not chunks:
        raise ValueError("source contains no usable bounded content")
    return chunks
