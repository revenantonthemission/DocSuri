"""Deterministic U3 fixture builders.

Fixture papers carry recorded source identity, version label and checksums;
chunk hashes bind every projection chunk to its literal text. These builders
are shared by database, repository, component and integration layers.
"""

from __future__ import annotations

import hashlib

# The finite synthetic vocabulary mirrors backend.u3_policy; importing the
# production constants here keeps fixtures from drifting from the service.
from backend.u3_policy import (  # noqa: F401 (re-exported for tests)
    ASSISTANCE_VOCABULARY,
    CITATION_POLICY,
    CORPUS_POLICY,
    ELIGIBILITY_POLICY,
    GLOSSARY_POLICY,
    PROJECTION_COMPATIBILITY,
    QUERY_VOCABULARY,
    SEARCH_POLICY,
)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def document_model(
    paper_id: str,
    *,
    title: str,
    paragraphs: list[str],
    figures: int = 0,
) -> dict:
    """One bounded document/chunks pair in the canonical corpus content shape."""
    blocks = [
        {"type": "paragraph", "id": f"{paper_id}-p{index + 1}", "text": text}
        for index, text in enumerate(paragraphs)
    ]
    for index in range(figures):
        blocks.append(
            {
                "type": "figure",
                "id": f"{paper_id}-f{index + 1}",
                "anchorLabel": f"Figure {index + 1}",
                "caption": f"합성 그림 캡션 {index + 1}",
                "assetRef": {"assetId": f"{paper_id}-asset-{index + 1}"},
            }
        )
    section = {"id": f"{paper_id}-s1", "title": "Introduction", "blocks": blocks}
    chunks = []
    for block in blocks:
        if block["type"] == "figure":
            text = block["caption"]
            kind = "figure"
        else:
            text = block["text"]
            kind = "paragraph"
        chunks.append(
            {
                "anchor": block["id"],
                "section": "Introduction",
                "text": text,
                "kind": kind,
                "textHash": text_hash(text),
            }
        )
    return {
        "document": {
            "paperId": paper_id,
            "title": title,
            "sections": [section],
        },
        "chunks": chunks,
    }


def source_record(
    source_id: str,
    *,
    paper_id: str,
    version_label: str = "v1",
    title: str | None = None,
    authors: list[str] | None = None,
    paragraphs: list[str] | None = None,
    figures: int = 0,
    permission: str = "permitted",
    system: str = "fixture",
) -> dict:
    """One provider record shaped exactly like the ingest adapter output."""
    title = title or f"합성 논문 {paper_id}"
    authors = authors or ["연구자 A", "연구자 B"]
    paragraphs = paragraphs or [
        f"{paper_id}의 첫 번째 문단입니다. 로컬 합성 코퍼스 문장.",
        f"{paper_id}의 두 번째 문단입니다. 검색과 인용 확인용입니다.",
    ]
    content = document_model(
        paper_id, title=title, paragraphs=paragraphs, figures=figures
    )
    raw = ("\n\n".join(paragraphs)).encode()
    return {
        "sourceId": source_id,
        "paperId": paper_id,
        "versionLabel": version_label,
        "title": title,
        "authors": authors,
        "sourceUrl": f"https://fixture.invalid/{paper_id}/{version_label}",
        "publishedOn": None,
        "retrievedAt": "2026-10-15T00:00:00+00:00",
        "permission": permission,
        "identity": {
            "system": system,
            "recordId": f"{paper_id}@{version_label}",
            "checksum": hashlib.sha256(raw).hexdigest(),
        },
        "content": content,
        "raw": raw,
    }


class MemorySources:
    """Bounded in-process provider double at the adapter boundary."""

    def __init__(self, records: dict[str, dict], *, clock=None):
        self.records = {key: dict(value) for key, value in records.items()}
        self.reads = 0
        self.clock = clock

    def read(self, source_id: str) -> dict | None:
        self.reads += 1
        return self.records.get(source_id)


class StaticCitationRecords(dict):
    """Deterministic citation adjacency for the fixture provider."""

    @classmethod
    def chain(cls, root: str, *, links: list[tuple[str, str]], cited: bool = True) -> "StaticCitationRecords":
        records: dict[str, dict] = {root: {"cited": [], "citing": []}}
        for parent, child in links:
            records.setdefault(parent, {"cited": [], "citing": []})
            records.setdefault(child, {"cited": [], "citing": []})
            bucket = "cited" if cited else "citing"
            records[parent][bucket].append(
                {
                    "versionId": child,
                    "paperId": child.split(":")[0],
                    "title": f"인용 논문 {child}",
                    "sourceUrl": f"https://fixture.invalid/{child}",
                }
            )
        return cls(records)


def request_body(operation: str, scope: list[str], *, revision: str = "u3-input-1") -> dict:
    digest = hashlib.sha256(
        ("|".join(sorted(scope)) + operation).encode()
    ).hexdigest()
    return {
        "operation": operation,
        "sourceScopeIds": scope,
        "authoritativeInputRevision": revision,
        "inputManifestHash": digest,
        "sourcePolicy": CORPUS_POLICY,
        "compatibilityRevision": PROJECTION_COMPATIBILITY,
    }
