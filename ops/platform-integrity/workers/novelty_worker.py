"""Novelty worker — handles novelty detection jobs."""

from __future__ import annotations

from ops.platform_integrity.workers.base_worker import BaseWorker


class NoveltyWorker(BaseWorker):
    """Novelty detection worker — consumes evidence agent results."""

    async def execute(self, input_data: dict) -> dict:
        intent = input_data.get("intent")
        manuscript = input_data.get("manuscript")  # optional upload
        evidence_result = input_data.get("evidence_result")  # from evidence agent

        # Consume evidence agent result + SourceRef only
        # Direct parsing/evidence logic reimplementation forbidden (BR-CONS-02)

        # Mock implementation
        import hashlib
        content = f"novelty:{input_data}".encode()
        asset_id = f"asset:{hashlib.sha256(content).hexdigest()[:32]}"

        return {"asset_id": asset_id}
