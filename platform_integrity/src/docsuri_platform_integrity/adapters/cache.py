"""Translation cache with canonical identity binding — client source ignored."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import redis.asyncio as redis

from docsuri_platform_integrity.adapters.registry import CanonicalPaperRegistry


class SourceTier(StrEnum):
    ARXIV_HTML = "ARXIV_HTML"
    SEMANTIC_SCHOLAR_PDF = "SEMANTIC_SCHOLAR_PDF"
    OPENALEX_PDF = "OPENALEX_PDF"
    USER_UPLOAD = "USER_UPLOAD"

    @property
    def rank(self) -> int:
        return {
            SourceTier.ARXIV_HTML: 4,
            SourceTier.SEMANTIC_SCHOLAR_PDF: 3,
            SourceTier.OPENALEX_PDF: 2,
            SourceTier.USER_UPLOAD: 1,
        }[self]


@dataclass(frozen=True)
class TranslationCacheEntry:
    asset_id: str
    canonical_paper_id: str
    version: int
    source_tier: SourceTier
    target_lang: str
    persona_hash: str
    hit_count: int = 0


class TranslationCacheService(Protocol):
    async def lookup(self, cache_key: str) -> TranslationCacheEntry | None: ...
    async def store(self, entry: TranslationCacheEntry) -> None: ...
    def compose_key(
        self,
        canonical_id: str,
        version: int,
        source_tier: SourceTier,
        target_lang: str,
        persona_hash: str,
    ) -> str: ...


class RedisTranslationCache:
    KEY_PREFIX = "translate"
    TTL_SECONDS = 30 * 24 * 3600

    def __init__(
        self,
        redis_client: redis.Redis,
        registry: CanonicalPaperRegistry,
    ):
        self.redis = redis_client
        self.registry = registry

    def compose_key(
        self,
        canonical_id: str,
        version: int,
        source_tier: SourceTier,
        target_lang: str,
        persona_hash: str,
    ) -> str:
        return (
            f"translate:{canonical_id}:{version}:"
            f"{source_tier.value}:{target_lang}:{persona_hash}"
        )

    async def lookup(self, cache_key: str) -> TranslationCacheEntry | None:
        data = await self.redis.get(cache_key)
        if not data:
            return None
        entry = TranslationCacheEntry.model_validate_json(data)
        await self.redis.hincrby(cache_key, "hit_count", 1)
        return entry

    async def store(self, entry: TranslationCacheEntry) -> None:
        cache_key = self.compose_key(
            entry.canonical_paper_id,
            entry.version,
            entry.source_tier,
            entry.target_lang,
            entry.persona_hash,
        )
        pipe = self.redis.pipeline()
        write_result = (
            f"translate:{entry.canonical_paper_id}:{entry.version}:"
            f"{entry.source_tier.value}:{entry.target_lang}:{entry.persona_hash}"
        )
        pipe.set(write_result, entry.model_dump_json())
        pipe.expire(cache_key, self.TTL_SECONDS)
        await pipe.execute()

    async def invalidate(self, canonical_id: str, version: int) -> int:
        pattern = f"translate:{canonical_id}:{version}:*"
        count = 0
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)
            count += 1
        return count


def make_persona_hash(persona_config: dict) -> str:
    import hashlib
    canonical = json.dumps(persona_config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
