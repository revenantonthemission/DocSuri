"""Canonical Paper Registry — paperId + version → canonical_id + source_tier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from docsuri_platform_integrity.adapters.cache import SourceTier


class CanonicalPaperRegistry(Protocol):
    def resolve(self, paper_id: str, version: int) -> CanonicalIdentity: ...
    def get_source_tier(self, canonical_id: str) -> SourceTier: ...


@dataclass(frozen=True)
class CanonicalIdentity:
    canonical_id: str
    source_tier: SourceTier


class DefaultCanonicalPaperRegistry:
    """Default implementation resolving paperId + version to canonical identity."""

    def resolve(self, paper_id: str, version: int) -> CanonicalIdentity:
        if paper_id.startswith("arxiv:"):
            arxiv_id = paper_id.split(":", 1)[1]
            return CanonicalIdentity(
                canonical_id=f"arxiv:{arxiv_id}",
                source_tier=SourceTier.ARXIV_HTML,
            )
        if paper_id.startswith("semantic:"):
            sem_id = paper_id.split(":", 1)[1]
            return CanonicalIdentity(
                canonical_id=f"semantic:{sem_id}",
                source_tier=SourceTier.SEMANTIC_SCHOLAR_PDF,
            )
        if paper_id.startswith("openalex:"):
            oa_id = paper_id.split(":", 1)[1]
            return CanonicalIdentity(
                canonical_id=f"openalex:{oa_id}",
                source_tier=SourceTier.OPENALEX_PDF,
            )
        if paper_id.startswith("userdoc:"):
            return CanonicalIdentity(
                canonical_id=paper_id,
                source_tier=SourceTier.USER_UPLOAD,
            )
        raise ValueError(f"Unknown paper_id format: {paper_id}")

    def get_source_tier(self, canonical_id: str) -> SourceTier:
        if canonical_id.startswith("arxiv:"):
            return SourceTier.ARXIV_HTML
        if canonical_id.startswith("semantic:"):
            return SourceTier.SEMANTIC_SCHOLAR_PDF
        if canonical_id.startswith("openalex:"):
            return SourceTier.OPENALEX_PDF
        if canonical_id.startswith("userdoc:"):
            return SourceTier.USER_UPLOAD
        raise ValueError(f"Unknown canonical_id format: {canonical_id}")
