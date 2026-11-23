"""CorpusContent's parsing and projection limits, selected by the profile (U8 plan Step 23;
performance-design § 11, P9, BR8.7, NFR8.8).

- `SYNTHETIC_LIMITS`, every earlier realm's values: 20,000 elements, a depth of 128,
  2 MiB of source, at most 256 chunks, and a block over 8 KB refused.
- `PRODUCTION_LIMITS`, for the production profile and the composed realm: 250,000
  elements, a depth of 256, 16 MiB of source and at most 200 chunks, lowered from
  2,000 by your decision of 2026-11-08 (L1-74) and measured again by your answer of
  2026-11-09 (L1-81), provisional until the first dry run measures real papers. A block
  over 8 KB is split at sentence boundaries into pieces of at most 8 KB; each piece
  keeps its block's anchor and carries its piece number, so a citation still leads to
  the block.

A source beyond its limits is refused with `CorpusLimitExceeded`, whose reason is the
migration's misfit reason `exceeds-v2-limit`. A block refused for its 8 KB names itself
(`limit="block"`, U8 plan Step 68(i)); the one refusal a converted document model raises
unnamed is its chunk count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

BLOCK_BYTES = 8192
EXCEEDS_LIMIT = "exceeds-v2-limit"
_SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")


class CorpusLimitExceeded(ValueError):
    """A source beyond the profile's corpus limits; `reason` is its misfit reason."""

    reason = EXCEEDS_LIMIT

    def __init__(self, *args: object, limit: str | None = None):
        super().__init__(*args)
        self.limit = limit


@dataclass(frozen=True)
class CorpusLimits:
    name: str
    max_elements: int
    max_depth: int
    max_source_bytes: int
    max_chunks: int
    split_large_blocks: bool

    def __post_init__(self) -> None:
        for value in (self.max_elements, self.max_depth, self.max_source_bytes, self.max_chunks):
            if type(value) is not int or value <= 0:
                raise ValueError("corpus limits must be finite positive integers")

    def pieces(self, text: str) -> list[str]:
        """The block itself while it fits 8 KB; beyond that refused, or split at
        sentence boundaries into pieces of at most 8 KB."""
        if len(text.encode()) <= BLOCK_BYTES:
            return [text]
        if not self.split_large_blocks:
            raise CorpusLimitExceeded("source block requires an explicit bounded chunking policy",
                                      limit="block")
        return split_block(text)


def _hard_split(sentence: str) -> list[str]:
    """A sentence longer than a piece, cut on character boundaries."""
    pieces, current = [], ""
    for character in sentence:
        if len((current + character).encode()) > BLOCK_BYTES:
            pieces.append(current)
            current = ""
        current += character
    return [*pieces, current] if current else pieces


def split_block(text: str) -> list[str]:
    pieces, current = [], ""
    for sentence in _SENTENCE_END.split(text.strip()):
        for part in (_hard_split(sentence) if len(sentence.encode()) > BLOCK_BYTES
                     else [sentence]):
            joined = f"{current} {part}" if current else part
            if len(joined.encode()) <= BLOCK_BYTES:
                current = joined
                continue
            pieces.append(current)
            current = part
    if current:
        pieces.append(current)
    return [piece for piece in pieces if piece.strip()]


# 2 MiB equals U3's WORKSPACE_BYTES, so every earlier realm's bound is unchanged.
SYNTHETIC_LIMITS = CorpusLimits("synthetic", 20_000, 128, 2 * 1024 * 1024, 256, False)
PRODUCTION_LIMITS = CorpusLimits("production", 250_000, 256, 16 * 1024 * 1024, 200, True)
COMPOSED_REALM = "service-operations"


def for_profile(profile) -> CorpusLimits:
    """Production's limits for the production profile and the composed realm; every
    earlier realm keeps the synthetic ones."""
    if getattr(profile, "is_production", False) or getattr(profile, "realm", None) == (
        COMPOSED_REALM
    ):
        return PRODUCTION_LIMITS
    return SYNTHETIC_LIMITS
