"""U3 CorpusContent reading: exact-version resolution, truthful availability
dispositions and opaque authorized asset handles.

Reads are side-effect-free: they never enqueue, allocate or advance a boundary.
A version under a non-terminal run is `building`; a version whose content stage
failed is `failed`; malformed committed content is `unsupported`; eligibility
always wins over any cached or projected copy (BR3.1, BR6.1-6.3).
"""

from __future__ import annotations

from uuid import UUID

from backend.modules.corpus.local_http import _flatten
from backend.modules.corpus.repository import content_revision
from backend.transactions import Authority, guard
from backend.u3_policy import READING_POLICY


class ContentUnavailable(RuntimeError):
    """Absent or foreign content uses the contract-safe denied response."""


class CorpusReading:
    def __init__(self, transactions):
        self.transactions = transactions

    def resolve(self, authority: Authority, identifier: str, version_label: str | None) -> dict:
        """Canonical identity lookup; never substitutes an unrelated paper."""
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 160:
            raise ValueError("identifier outside finite policy")
        if version_label is not None and (
            not isinstance(version_label, str) or not 1 <= len(version_label) <= 64
        ):
            raise ValueError("version label outside finite policy")

        def read(conn):
            if authority is not None:
                guard(conn, authority)
            row = conn.execute(
                "SELECT v.*,p.title,p.authors,p.published_on,p.withdrawn,"
                "p.revision AS paper_revision FROM corpus.version v JOIN corpus.paper p "
                "ON p.id=v.paper_id WHERE (v.id=%s OR v.paper_id=%s) "
                "AND (%s::text IS NULL OR v.version_label=%s) ORDER BY v.id LIMIT 1",
                (identifier, identifier, version_label, version_label),
            ).fetchone()
            if not row:
                return None
            disposition = self._disposition(conn, row)
            return {
                "paperId": row["paper_id"],
                "versionId": row["id"],
                "title": row["title"],
                "authors": row["authors"],
                "sourceUrl": row["source_url"],
                "versionLabel": row["version_label"],
                "eligibilityRevision": str(row["eligibility_revision"]),
                "metadataRevision": str(row["paper_revision"]),
                "canonicalDisposition": {
                    "available": "same",
                    "building": "same",
                    "withdrawn": "withdrawn",
                    "restricted": "restricted",
                    "unsupported": "unavailable",
                }.get(disposition, "unavailable"),
                "disposition": disposition,
            }

        return self.transactions.run("corpus", read)

    def read_content(self, authority: Authority, paper: dict, purpose: str) -> dict:
        """Exact-version read with bounded availability states and no fabricated text."""
        if purpose not in (
            "metadata",
            "read",
            "assistance",
            "research",
            "citation",
            "saved-reference",
        ):
            raise ValueError("unknown read purpose")
        version_id = _paper_version(paper)

        def read(conn):
            if authority is not None:
                guard(conn, authority)
            row = conn.execute(
                "SELECT v.*,p.title,p.authors,p.published_on,p.withdrawn FROM corpus.version v "
                "JOIN corpus.paper p ON p.id=v.paper_id WHERE v.id=%s",
                (version_id,),
            ).fetchone()
            if not row or row["paper_id"] != paper.get("paperId"):
                return {"availability": "absent", "retryable": False}
            disposition = self._disposition(conn, row)
            if disposition != "available":
                return {
                    "availability": disposition,
                    "paperId": row["paper_id"],
                    "versionId": row["id"],
                    "eligibilityRevision": str(row["eligibility_revision"]),
                    "title": row["title"],
                    "sourceUrl": row["source_url"],
                    "retryable": disposition in ("building", "failed"),
                }
            conn.execute(
                "SELECT corpus.guard_version(%s,'local-research')", (version_id,)
            )
            sections, figures, _ = _flatten(row["content"]["document"]["sections"])
            assets = self._asset_refs(conn, row)
            return {
                "availability": "available",
                "paperId": row["paper_id"],
                "versionId": row["id"],
                "eligibilityRevision": str(row["eligibility_revision"]),
                "contentRevision": content_revision(row),
                "contentHash": row["source_hash"],
                "title": row["title"],
                "authors": row["authors"],
                "sourceUrl": row["source_url"],
                "versionLabel": row["version_label"],
                "sections": sections,
                "assets": assets["refs"],
                "figures": figures,
                "coverage": "complete" if not figures else "partial",
                "limitations": assets["limitations"],
            }

        return self.transactions.run("corpus", read)

    def read_asset(
        self, authority: Authority, paper: dict, content_revision_value: str, asset_id: str
    ) -> dict:
        """Opaque handle resolution under current eligibility; no arbitrary paths."""
        version_id = _paper_version(paper)
        try:
            UUID(str(asset_id))
        except (ValueError, TypeError):
            raise ContentUnavailable("unknown asset handle") from None

        def read(conn):
            if authority is not None:
                guard(conn, authority)
            row = conn.execute(
                "SELECT v.*,p.withdrawn FROM corpus.version v JOIN corpus.paper p "
                "ON p.id=v.paper_id WHERE v.id=%s",
                (version_id,),
            ).fetchone()
            if not row or row["paper_id"] != paper.get("paperId"):
                raise ContentUnavailable("unknown asset handle")
            if self._disposition(conn, row) != "available":
                raise ContentUnavailable("source unavailable with disposition")
            if content_revision_value != content_revision(row):
                raise ValueError("content revision changed")
            asset = conn.execute(
                "SELECT * FROM corpus.asset WHERE id=%s AND version_id=%s",
                (asset_id, version_id),
            ).fetchone()
            if not asset:
                raise ContentUnavailable("unknown asset handle")
            return {
                "assetId": str(asset["id"]),
                "mediaType": asset["media_type"],
                "contentHash": asset["content_hash"],
                "altText": asset["alt_text"],
                "storage": asset["storage"],
                "byteLength": asset["byte_length"],
                "policy": READING_POLICY,
            }

        return self.transactions.run("corpus", read)

    # --- helpers ---------------------------------------------------------------

    @staticmethod
    def _disposition(conn, row) -> str:
        if row["withdrawn"] or not row["eligible"]:
            if row["withdrawn"]:
                return "withdrawn"
            pending = conn.execute(
                "SELECT state FROM corpus.run_effect WHERE stage='content' AND subject=%s "
                "ORDER BY recorded_at DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            if pending and pending["state"] in ("pending", "unknown"):
                return "building"
            if pending and pending["state"] == "failed":
                return "failed"
            if row["purpose"] != "local-research":
                return "restricted"
            return "building"
        if row["purpose"] != "local-research":
            return "restricted"
        try:
            content = row["content"]["document"]["sections"]
        except (KeyError, TypeError):
            return "unsupported"
        if not content:
            return "unsupported"
        return "available"

    @staticmethod
    def _asset_refs(conn, row) -> dict:
        assets = conn.execute(
            "SELECT * FROM corpus.asset WHERE version_id=%s ORDER BY created_at, id LIMIT 64",
            (row["id"],),
        ).fetchall()
        refs = [
            {
                "assetId": str(asset["id"]),
                "mediaType": asset["media_type"],
                "contentHash": asset["content_hash"],
                "altText": asset["alt_text"],
                "sectionId": asset["section_id"],
            }
            for asset in assets
        ]
        unavailable = sum(1 for asset in assets if asset["storage"] != "private")
        limitations = []
        if unavailable or not refs:
            limitations.append(
                "그림 원본은 로컬 합성 환경에 보관되지 않습니다. 캡션과 서지 정보만 표시됩니다."
            )
        return {"refs": refs, "limitations": limitations}


def _paper_version(paper: dict) -> str:
    if not isinstance(paper, dict):
        raise ValueError("paper reference outside finite policy")
    version = paper.get("versionId")
    if not isinstance(version, str) or not 1 <= len(version) <= 160:
        raise ValueError("version identity outside finite policy")
    return version
