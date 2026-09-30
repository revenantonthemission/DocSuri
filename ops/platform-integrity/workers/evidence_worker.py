"""Evidence worker — handles evidence formation jobs."""

from __future__ import annotations

from ops.platform_integrity.workers.base_worker import BaseWorker


class EvidenceWorker(BaseWorker):
    """Evidence formation worker — consumes question, papers, attachments."""

    async def execute(self, input_data: dict) -> dict:
        question = input_data.get("question")
        paper_ids = input_data.get("paper_ids", [])
        attachments = input_data.get("attachments", [])

        # Consume EvidenceFormationPort only
        # Direct parsing/evidence logic reimplementation forbidden (BR-CONS-01)

        # Mock implementation
        import hashlib
        content = f"evidence:{input_data}".encode()
        asset_id = f"asset:{hashlib.sha256(content).hexdigest()[:32]}"

        return {"asset_id": asset_id}
