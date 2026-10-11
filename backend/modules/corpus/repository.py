"""Corpus-owned immutable sources and projection publication for local research."""

from __future__ import annotations

import hashlib
import json
from datetime import date

from backend.artifacts import PrivateArtifacts
from backend.transactions import OwnerTransactions
from psycopg.types.json import Jsonb


class CorpusRepository:
    def __init__(self, transactions: OwnerTransactions, files: PrivateArtifacts):
        self.transactions = transactions
        self.files = files

    def publish(
        self,
        *,
        paper: str,
        version: str,
        title: str,
        authors: list[str],
        source_url: str,
        version_label: str,
        content: dict,
        raw: bytes,
        provenance: dict,
        chunks: list[dict],
        published_on: date | None = None,
    ) -> dict:
        if not 1 <= len(chunks) <= 256:
            raise ValueError("projection allocation exceeded")
        if published_on is not None and type(published_on) is not date:
            raise ValueError("publication date must be an explicit calendar date")
        projection_hash = hashlib.sha256(
            json.dumps(chunks, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        artifact = self.files.publish(raw)

        def write(conn):
            # All publication writers use this barrier before paper/version locks.
            # The shared allocation and cursor snapshot change atomically.
            conn.execute("SELECT singleton FROM corpus.publication FOR UPDATE")
            conn.execute(
                "INSERT INTO corpus.paper(id,title,authors,published_on,metadata) "
                "VALUES(%s,%s,%s,%s,%s) ON "
                "CONFLICT(id) DO NOTHING",
                (paper, title, Jsonb(authors), published_on, Jsonb({"localResearchOnly": True})),
            )
            metadata = conn.execute(
                "SELECT title,authors,published_on FROM corpus.paper WHERE id=%s FOR UPDATE",
                (paper,),
            ).fetchone()
            if metadata != {"title": title, "authors": authors, "published_on": published_on}:
                raise ValueError("immutable paper metadata conflict")
            existing = conn.execute(
                "SELECT * FROM corpus.version WHERE id=%s FOR UPDATE", (version,)
            ).fetchone()
            if existing:
                if existing["paper_id"] != paper or existing["source_hash"] != artifact.sha256:
                    raise ValueError("immutable source identity conflict")
                if (
                    existing["content"] != content
                    or existing["provenance"].get("projectionHash") != projection_hash
                    or existing["source_url"] != source_url
                    or existing["version_label"] != version_label
                ):
                    raise ValueError("immutable parsed content conflict")
                return existing
            count = conn.execute("SELECT count(*) AS count FROM corpus.version").fetchone()["count"]
            if count >= 2:
                raise ValueError("source fixture allocation exhausted")
            projected = conn.execute("SELECT count(*) AS count FROM corpus.projection").fetchone()[
                "count"
            ]
            if projected + len(chunks) > 256:
                raise ValueError("aggregate projection allocation exhausted")
            row = conn.execute(
                "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
                "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,%s,%s,%s,%s,"
                "true,'local-research',%s,%s) RETURNING *",
                (
                    version,
                    paper,
                    source_url,
                    artifact.sha256,
                    version_label,
                    artifact.name,
                    Jsonb(
                        dict(provenance, byteLength=artifact.size, projectionHash=projection_hash)
                    ),
                    Jsonb(content),
                ),
            ).fetchone()
            for ordinal, chunk in enumerate(chunks):
                conn.execute(
                    "INSERT INTO corpus.projection(version_id,ordinal,content_hash,anchor,"
                    "section,text_content,embedding,vector_policy) VALUES(%s,%s,%s,%s,%s,%s,%s,"
                    "%s)",
                    (
                        version,
                        ordinal,
                        artifact.sha256,
                        chunk["anchor"],
                        chunk["section"],
                        chunk["text"],
                        chunk.get("embedding"),
                        chunk.get("vectorPolicy"),
                    ),
                )
            self._advance_publication(conn)
            return row

        return self.transactions.run("corpus", write)

    def read(self, version: str) -> dict:
        def read(conn):
            conn.execute("SELECT corpus.guard_version(%s,%s)", (version, "local-research"))
            return conn.execute(
                "SELECT v.*,p.title,p.authors,p.metadata FROM corpus.version v JOIN "
                "corpus.paper p ON p.id=v.paper_id WHERE v.id=%s",
                (version,),
            ).fetchone()

        return self.transactions.run("corpus", read)

    def withdraw(self, version: str) -> None:
        def write(conn):
            conn.execute("SELECT singleton FROM corpus.publication FOR UPDATE")
            row = conn.execute(
                "SELECT paper_id FROM corpus.version WHERE id=%s", (version,)
            ).fetchone()
            if not row:
                raise ValueError("unknown source version")
            conn.execute("SELECT id FROM corpus.paper WHERE id=%s FOR UPDATE", (row["paper_id"],))
            conn.execute(
                "UPDATE corpus.version SET eligible=false,"
                "eligibility_revision=gen_random_uuid() WHERE id=%s",
                (version,),
            )
            conn.execute("DELETE FROM corpus.projection WHERE version_id=%s", (version,))
            self._advance_publication(conn)

        self.transactions.run("corpus", write)

    def confirm_publication(self, expected: dict[str, str]) -> dict:
        """Bind readiness to one locked publication and currently eligible sources."""
        if not 1 <= len(expected) <= 2:
            raise ValueError("publication source count outside local allocation")

        def read(conn):
            publication = conn.execute("SELECT * FROM corpus.publication FOR SHARE").fetchone()
            for version, digest in sorted(expected.items()):
                conn.execute("SELECT corpus.guard_version(%s,%s)", (version, "local-research"))
                row = conn.execute(
                    "SELECT source_hash FROM corpus.version WHERE id=%s", (version,)
                ).fetchone()
                if row["source_hash"] != digest:
                    raise ValueError("current publication source binding differs")
            return publication

        return self.transactions.run("corpus", read)

    @staticmethod
    def _advance_publication(conn) -> None:
        rows = conn.execute(
            "SELECT v.id,v.source_hash,v.eligibility_revision,v.eligible,"
            "p.withdrawn,count(c.ordinal) AS chunks FROM corpus.version v "
            "JOIN corpus.paper p ON p.id=v.paper_id LEFT JOIN corpus.projection c "
            "ON c.version_id=v.id GROUP BY v.id,p.withdrawn ORDER BY v.id"
        ).fetchall()
        manifest = hashlib.sha256(
            json.dumps(rows, sort_keys=True, default=str, separators=(",", ":")).encode()
        ).hexdigest()
        conn.execute(
            "UPDATE corpus.publication SET revision=gen_random_uuid(),manifest_hash=%s,"
            "published_at=clock_timestamp() WHERE singleton",
            (manifest,),
        )
