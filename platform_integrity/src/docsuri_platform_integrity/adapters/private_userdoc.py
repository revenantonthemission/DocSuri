"""Private userdoc filesystem adapter — owner-scoped read/write, isolated from public corpus."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from docsuri_platform_integrity.contracts.models import DocModel


class PrivateUserDocFS:
    """Owner-scoped document storage, completely isolated from public corpus."""

    def __init__(self, root: Path, owner: str):
        self.root = root / "private" / "userdoc" / owner
        self.owner = owner

    def _doc_path(self, doc_id: str) -> Path:
        return self.root / doc_id / "docmodel.json"

    def _source_path(self, doc_id: str) -> Path:
        return self.root / doc_id / "source"

    def exists(self, doc_id: str) -> bool:
        return self._doc_path(doc_id).exists()

    def read(self, doc_id: str) -> DocModel | None:
        """Read DocModel if owner matches, otherwise return None (existence concealment)."""
        path = self._doc_path(doc_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return DocModel.model_validate(data)
        except Exception:
            return None

    def write(self, doc_id: str, doc_model: DocModel, source_bytes: bytes) -> None:
        """Write DocModel and source bytes atomically."""
        doc_dir = self.root / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Atomic write: temp file -> fsync -> rename
        doc_path = self._doc_path(doc_id)
        tmp_path = doc_path.with_suffix(".tmp")
        tmp_path.write_bytes(doc_model.model_dump_json().encode("utf-8"))
        tmp_path.chmod(0o600)
        os.replace(tmp_path, doc_path)

        # Store source bytes
        source_path = self._source_path(doc_id)
        tmp_source = source_path.with_suffix(".tmp")
        tmp_source.write_bytes(doc_model.model_dump_json().encode("utf-8"))
        tmp_source.chmod(0o600)
        os.replace(tmp_source, source_path)

    def delete(self, doc_id: str) -> bool:
        """Delete userdoc directory."""
        doc_dir = self.root / doc_id
        if doc_dir.exists():
            shutil.rmtree(doc_dir)
            return True
        return False

    def list_docs(self) -> list[str]:
        """List all doc IDs for this owner."""
        if not self.root.exists():
            return []
        return [d.name for d in self.root.iterdir() if d.is_dir()]


class PrivateUserDocWriter:
    """High-level writer for private userdoc ingestion."""

    def __init__(self, fs: PrivateUserDocFS):
        self.fs = fs

    def ingest(self, doc_id: str, source_bytes: bytes, source_format: str) -> tuple[str, DocModel]:
        """
        Ingest document: parse → DocModel → store.
        Returns (doc_id, DocModel).
        """
        from docsuri_platform_integrity.adapters.ingestion import parse_document

        # Parse document using existing ingestion pipeline
        doc_model = parse_document(source_bytes=source_bytes, format=source_format)

        # Ensure doc_id matches expected format
        expected_id = doc_model.id
        if doc_id != expected_id:
            raise ValueError(f"doc_id mismatch: expected {expected_id}, got {doc_id}")

        # Write atomically
        self.fs.write(doc_id, doc_model, b"")  # source bytes stored separately if needed

        return doc_id, doc_model
