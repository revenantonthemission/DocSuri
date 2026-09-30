"""Ingest worker — handles private userdoc ingestion."""

from __future__ import annotations

from pathlib import Path
from ops.platform_integrity.workers.base_worker import BaseWorker


class IngestWorker(BaseWorker):
    """Private userdoc ingestion worker."""

    async def execute(self, input_data: dict) -> dict:
        source_bytes = input_data.get("source_bytes", b"")
        source_format = input_data.get("format", "pdf")
        owner = input_data.get("owner")
        doc_id = input_data.get("doc_id")

        # Reuse existing ingestion pipeline
        from docsuri_platform_integrity.adapters.ingestion import parse_document

        try:
            doc_model = parse_document(source_bytes=source_bytes, format=source_format)
        except Exception as e:
            return {"error": {"error_type": "validation_failed", "message": str(e), "retryable": False}}

        # Verify doc_id matches
        if doc_id != doc_model.id:
            return {"error": {"error_type": "validation_failed", "message": "doc_id mismatch", "retryable": False}}

        # Store in private userdoc namespace
        from docsuri_platform_integrity.adapters.private_userdoc import PrivateUserDocFS, PrivateUserDocWriter

        fs = PrivateUserDocFS(root=Path("/Library/Application Support/DocSuri/rem-2"), owner=owner)
        writer = PrivateUserDocWriter(fs)

        try:
            doc_id, doc_model = writer.ingest(doc_id, input_data.get("source_bytes", b""), input_data.get("format", "pdf"))
        except Exception as e:
            return {"error": {"error_type": "validation_failed", "message": str(e), "retryable": False}}

        asset_id = f"asset:userdoc:{doc_model.id}"

        return {"asset_id": asset_id, "doc_id": doc_model.id}
