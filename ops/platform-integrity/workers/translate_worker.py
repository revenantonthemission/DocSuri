"""Translate worker — handles translation jobs with cache integration."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from ops.platform_integrity.workers.base_worker import BaseWorker, JobMessage
from ops.platform_integrity.content_job_service import ContentJobService, JobEventEmitter


class TranslateWorker(BaseWorker):
    """Translation worker with cache integration."""

    def __init__(
        self,
        semaphore: asyncio.Semaphore,
        job_service: "ContentJobService",
        event_emitter: JobEventEmitter,
        translation_cache: "RedisTranslationCache",
        registry: "CanonicalPaperRegistry",
    ):
        super().__init__("TRANSLATE", semaphore, None, None)
        self.translation_cache = translation_cache
        self.registry = registry

    async def execute(self, input_data: dict) -> dict:
        """Execute translation with cache lookup."""
        paper_id = input_data.get("paper_id")
        version = input_data.get("version", 1)
        target_lang = input_data.get("target_lang", "ko")
        persona = input_data.get("persona", {})

        # 1. Resolve canonical identity
        canonical = self.registry.resolve(input_data["paper_id"], input_data.get("version", 1))

        # 2. Check cache
        persona_hash = self._make_persona_hash(input_data.get("persona", {}))
        cache_key = self.translation_cache.compose_key(
            canonical.canonical_id,
            input_data.get("version", 1),
            canonical.source_tier,
            input_data.get("target_lang", "ko"),
            self._make_persona_hash(input_data.get("persona", {})),
        )

        cached = await self.translation_cache.lookup(cache_key)
        if cached:
            # Cache hit - return asset_id immediately
            return {"asset_id": cached.asset_id, "source": "cache"}

        # Cache miss - perform translation
        translation_result = await self._perform_translation(input_data)

        # Store in cache
        entry = TranslationCacheEntry(
            asset_id=translation_result["asset_id"],
            canonical_paper_id=canonical.canonical_id,
            version=input_data.get("version", 1),
            source_tier=canonical.source_tier,
            target_lang=input_data.get("target_lang", "ko"),
            persona_hash=self._make_persona_hash(input_data.get("persona", {})),
        )
        await self.translation_cache.store(entry)

        return {"asset_id": translation_result["asset_id"]}

    def _make_persona_hash(self, persona: dict) -> str:
        import hashlib
        import json
        canonical = json.dumps(persona, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    async def _perform_translation(self, input_data: dict) -> dict:
        """Perform actual translation using model."""
        # Placeholder: in real implementation, call translation model
        content = f"translated:{input_data}".encode()
        asset_id = f"asset:{hashlib.sha256(content).hexdigest()[:32]}"
        return {"asset_id": asset_id}


# Import for type hints
from ops.platform_integrity.content_job_service import ContentJobService, JobEventEmitter
from ops.platform_integrity.adapters.cache import RedisTranslationCache
from docsuri_platform_integrity.adapters.registry import CanonicalPaperRegistry
from docsuri_platform_integrity.adapters.cache import TranslationCacheEntry, SourceTier
