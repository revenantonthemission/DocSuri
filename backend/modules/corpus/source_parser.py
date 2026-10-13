"""Bounded source adaptation around the retained deterministic document parser."""

from __future__ import annotations

import hashlib
from datetime import datetime
from html.parser import HTMLParser

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

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.nodes = 0
        self.stack = []

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if tag not in self.void:
            self.stack.append(tag)
        if self.nodes > 20000 or len(self.stack) > 128:
            raise ValueError("source structure exceeds local parsing allocation")

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack.pop() != tag:
                pass


def parse_source(
    raw: bytes, *, paper: str, version: int, title: str, fetched_at: datetime
) -> tuple[dict, list[dict]]:
    if not 0 < len(raw) <= 2097152 or b"\0" in raw:
        raise ValueError("source bytes outside local parsing policy")
    html = raw.decode("utf-8", errors="strict")
    budget = _StructureBudget()
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
                if len(text.encode()) > 8192:
                    raise ValueError("source block requires an explicit bounded chunking policy")
                chunks.append(
                    {
                        "anchor": block["id"],
                        "section": heading,
                        "text": text,
                        "kind": kind,
                        "textHash": hashlib.sha256(text.encode()).hexdigest(),
                    }
                )
                if len(chunks) > 256:
                    raise ValueError("source projection exceeds local chunk allocation")
            walk(section.get("sections", []), [*ancestors, section["title"]])

    walk(document["sections"], [])
    if not chunks:
        raise ValueError("source contains no usable bounded content")
    return document, chunks
