"""Corpus-owned immutable sources and projection publication for local research."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date

from backend.artifacts import PrivateArtifacts
from backend.modules.corpus.limits import PRODUCTION_LIMITS
from backend.transactions import OwnerTransactions
from psycopg.types.json import Jsonb


def content_revision(source: dict) -> str:
    """Corpus-owned token shared by reading and immutable assistance acceptance."""
    encoded = json.dumps(
        source["content"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    if len(encoded) > 2097152:
        raise ValueError("parsed source exceeds local payload allocation")
    return hashlib.sha256(encoded).hexdigest()


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

    # --- The research executor's reads (U8 plan Step 21; your decision of 2026-10-24) ---
    # Read-only, each under `guard_version(…, 'local-research')`, so an ineligible or
    # withdrawn version is refused (InsufficientPrivilege) before any row is read. A
    # row's location is its anchor, or `anchor~k` (k from 1, in ordinal order) among the
    # rows of the version that share that anchor, so every location names one row.

    RESEARCH_EXCERPT_LIMIT = 24
    _RESEARCH_ROWS = (
        "WITH rows AS MATERIALIZED (SELECT ordinal,anchor,section,text_content,"
        "count(*) OVER (PARTITION BY anchor) AS shared,"
        "row_number() OVER (PARTITION BY anchor ORDER BY ordinal) AS piece,"
        # The exact distance, computed inside the materialised scan over the version's own
        # rows, so no approximate index is ever used; rows lacking a vector of the pinned
        # policy have none and come last.
        "CASE WHEN %(ranked)s AND embedding_vector IS NOT NULL AND vector_policy=%(policy)s "
        "THEN embedding_vector <=> %(vector)s::public.vector END AS distance "
        "FROM corpus.projection WHERE version_id=%(version)s) "
        "SELECT ordinal,anchor,section,text_content AS text,distance,"
        "CASE WHEN shared>1 THEN anchor||'~'||piece ELSE anchor END AS location FROM rows "
    )

    def research_identity(self, version: str) -> dict:
        """The paper, the eligibility revision and the source address of one version:
        the research scope check reads only this, never the version's content."""

        def read(conn):
            revision = conn.execute(
                "SELECT corpus.guard_version(%s,%s) AS revision", (version, "local-research")
            ).fetchone()["revision"]
            row = conn.execute(
                "SELECT paper_id,source_url FROM corpus.version WHERE id=%s", (version,)
            ).fetchone()
            return {"paper_id": row["paper_id"], "eligibility_revision": revision,
                    "source_url": row["source_url"]}

        return self.transactions.run("corpus", read)

    def research_excerpts(self, version: str, *, vector: list[float] | None = None,
                          limit: int = RESEARCH_EXCERPT_LIMIT) -> list[dict]:
        """Up to `limit` (at most 24) rows of one version with their locations: closest
        first by exact distance to `vector` under the pinned vector policy, rows without
        such a vector last and ties by ordinal; without a vector, in document order."""
        if type(limit) is not int or not 1 <= limit <= self.RESEARCH_EXCERPT_LIMIT:
            raise ValueError("research excerpt limit outside its bound")
        from backend.modules.discovery.u8_search import VECTOR_POLICY

        literal = None if vector is None else _research_vector(vector)

        def read(conn):
            conn.execute("SELECT corpus.guard_version(%s,%s)", (version, "local-research"))
            return conn.execute(
                self._RESEARCH_ROWS
                + "ORDER BY distance IS NULL, distance, ordinal LIMIT %(limit)s",
                {"ranked": literal is not None, "policy": VECTOR_POLICY, "vector": literal,
                 "version": version, "limit": limit},
            ).fetchall()

        return self.transactions.run("corpus", read)

    def research_rows(self, version: str, ordinals: list[int]) -> list[dict]:
        """The rows a research job sent, re-read by version and ordinal, with the same
        locations, in ordinal order."""
        wanted = sorted({int(ordinal) for ordinal in ordinals})
        if not 1 <= len(wanted) <= self.RESEARCH_EXCERPT_LIMIT:
            raise ValueError("research rows outside their bound")

        def read(conn):
            conn.execute("SELECT corpus.guard_version(%s,%s)", (version, "local-research"))
            return conn.execute(
                self._RESEARCH_ROWS + "WHERE ordinal = ANY(%(ordinals)s) ORDER BY ordinal",
                {"ranked": False, "policy": None, "vector": None, "version": version,
                 "ordinals": wanted},
            ).fetchall()

        return self.transactions.run("corpus", read)

    def identify(self, identifier: str, version_label: str | None = None) -> dict | None:
        """Exact paper/version lookup by public identity; no content bytes returned."""
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 160:
            raise ValueError("identifier outside finite policy")
        if version_label is not None and (
            not isinstance(version_label, str) or not 1 <= len(version_label) <= 64
        ):
            raise ValueError("version label outside finite policy")

        def read(conn):
            return conn.execute(
                "SELECT v.*,p.title,p.authors,p.published_on,p.withdrawn,p.revision AS "
                "paper_revision,p.metadata FROM corpus.version v JOIN corpus.paper p ON "
                "p.id=v.paper_id WHERE (v.id=%s OR v.paper_id=%s) AND (%s::text IS NULL OR "
                "v.version_label=%s) ORDER BY v.id LIMIT 1",
                (identifier, identifier, version_label, version_label),
            ).fetchone()

        return self.transactions.run("corpus", read)

    def reader_view(self, version: str) -> dict:
        """Current disposition plus the authorized row; withdrawn stays readable as metadata."""
        if not isinstance(version, str) or not 1 <= len(version) <= 160:
            raise ValueError("version identity outside finite policy")

        def read(conn):
            row = conn.execute(
                "SELECT v.*,p.title,p.authors,p.published_on,p.withdrawn,p.metadata "
                "FROM corpus.version v JOIN corpus.paper p ON p.id=v.paper_id WHERE v.id=%s",
                (version,),
            ).fetchone()
            if not row:
                raise PermissionError("source unavailable")
            # Corpus-owned row state decides the disposition; the runtime role
            # does not receive the library/assistance-only availability function.
            if row["withdrawn"] or not row["eligible"]:
                return {"disposition": "withdrawn", "row": row}
            if row["purpose"] != "local-research":
                return {"disposition": "restricted", "row": row}
            conn.execute("SELECT corpus.guard_version(%s,%s)", (version, "local-research"))
            return {"disposition": "ready", "row": row}

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


# --- A4: the paper import and its parity read (U8 plan Step 7; BR8.7, BR8.8) -----------

# One value bounds both the conversion and the write: production's chunk limit, 200,
# lowered by your decision of 2026-11-08 (L1-74) and measured again by your answer of
# 2026-11-09 (L1-81), provisional until the first dry run.
IMPORT_MAX_CHUNKS = PRODUCTION_LIMITS.max_chunks
IMPORT_DIMENSIONS = 1024
IMPORT_MAX_PARITY_RECORDS = 100_000


def _research_vector(vector) -> str:
    """A question's vector as pgvector's literal, refused unless it has the pinned
    embedding's 1,024 finite values."""
    import math

    values = list(vector)
    if len(values) != IMPORT_DIMENSIONS or not all(
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        for value in values
    ):
        raise ValueError("question vector outside the pinned embedding's shape")
    return "[" + ",".join(repr(float(value)) for value in values) + "]"


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def paper_import_fields(paper: dict, version: dict, chunks: list[dict]) -> dict:
    """The compared normalized fields of one imported paper version: its paper's
    metadata, its version's identity and content, and each chunk's text and vector."""
    return {
        "paper": paper["id"],
        "title": paper["title"],
        "authors": list(paper["authors"]),
        "publishedOn": None if paper.get("publishedOn") is None else str(paper["publishedOn"]),
        "version": version["id"],
        "label": version["label"],
        "sourceUrl": version["sourceUrl"],
        "sourceHash": version["sourceHash"],
        "eligible": bool(version["eligible"]),
        "content": _sha(version["content"]),
        "chunks": [
            [chunk["anchor"], chunk["section"], _sha(chunk["text"]),
             None if chunk.get("embedding") is None else _sha(list(chunk["embedding"]))]
            for chunk in chunks
        ],
    }


def _check_paper_import(paper: dict, version: dict, chunks: list[dict]) -> None:
    if not isinstance(paper.get("id"), str) or not 1 <= len(paper["id"]) <= 160:
        raise ValueError("paper identity outside its bound")
    if not isinstance(version.get("id"), str) or not 1 <= len(version["id"]) <= 160:
        raise ValueError("version identity outside its bound")
    published = paper.get("publishedOn")
    if published is not None and type(published) is not date:
        raise ValueError("publication date must be an explicit calendar date")
    if not 1 <= len(chunks) <= IMPORT_MAX_CHUNKS:
        raise ValueError("projection allocation exceeded")
    for chunk in chunks:
        embedding = chunk.get("embedding")
        if embedding is not None and len(embedding) != IMPORT_DIMENSIONS:
            raise ValueError("chunk vector outside the pinned embedding's shape")


class CorpusImports:
    """CorpusContent's A4 writes, as its own login and behind the publication barrier.

    A version is immutable once written (`corpus.preserve_version_binding`), and so is
    its paper's metadata, as every corpus writer holds: an existing version with the same
    fields answers `unchanged`, and one whose fields differ answers `refused` with
    `version-content-changed` (or `paper-metadata-changed`), never a rewrite. A new
    version of a known paper links to it rather than duplicating it (BR8.7).
    """

    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions

    def import_paper(
        self, *, paper: dict, version: dict, chunks: list[dict], private_path: str,
        provenance: dict,
    ) -> dict:
        from backend.import_parity import decide, outcome, stored_digest

        _check_paper_import(paper, version, chunks)
        incoming = stored_digest(paper_import_fields(paper, version, chunks))

        def write(conn):
            conn.execute("SELECT singleton FROM corpus.publication FOR UPDATE")
            known = conn.execute(
                "SELECT title,authors,published_on FROM corpus.paper WHERE id=%s FOR UPDATE",
                (paper["id"],),
            ).fetchone()
            if known and (
                known["title"] != paper["title"]
                or known["authors"] != list(paper["authors"])
                or known["published_on"] != paper.get("publishedOn")
            ):
                return outcome("refused", incoming, reason="paper-metadata-changed")
            existing = self._stored_digest(conn, version["id"])
            if existing is not None:
                if decide(existing, incoming) == "unchanged":
                    return outcome("unchanged", incoming)
                return outcome("refused", existing, reason="version-content-changed")
            if not known:
                conn.execute(
                    "INSERT INTO corpus.paper(id,title,authors,published_on,metadata) "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (paper["id"], paper["title"], Jsonb(list(paper["authors"])),
                     paper.get("publishedOn"), Jsonb(paper.get("metadata") or {})),
                )
            conn.execute(
                "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
                "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,%s,%s,%s,%s,"
                "%s,'local-research',%s,%s)",
                (version["id"], paper["id"], version["sourceUrl"], version["sourceHash"],
                 version["label"], private_path, bool(version["eligible"]),
                 Jsonb(dict(provenance, importDigest=incoming)), Jsonb(version["content"])),
            )
            # The version's chunks in one multi-row statement (one round trip, under the
            # transaction's deadline), not one round trip per chunk.
            if chunks:
                rows = ",".join(["(%s,%s,%s,%s,%s,%s,%s,%s)"] * len(chunks))
                conn.execute(
                    "INSERT INTO corpus.projection(version_id,ordinal,content_hash,anchor,"
                    "section,text_content,embedding,vector_policy) VALUES " + rows,
                    [value for ordinal, chunk in enumerate(chunks) for value in (
                        version["id"], ordinal, version["sourceHash"], chunk["anchor"],
                        chunk["section"], chunk["text"], chunk.get("embedding"),
                        chunk.get("vectorPolicy"))],
                )
            CorpusRepository._advance_publication(conn)
            return outcome("imported", incoming)

        return self.transactions.run("corpus", write)

    @staticmethod
    def _stored_digest(conn, version_id: str) -> str | None:
        from backend.import_parity import stored_digest

        row = conn.execute(
            "SELECT v.*,p.title,p.authors,p.published_on FROM corpus.version v "
            "JOIN corpus.paper p ON p.id=v.paper_id WHERE v.id=%s",
            (version_id,),
        ).fetchone()
        if row is None:
            return None
        chunks = conn.execute(
            "SELECT anchor,section,text_content AS text,embedding FROM corpus.projection "
            "WHERE version_id=%s ORDER BY ordinal",
            (version_id,),
        ).fetchall()
        return stored_digest(paper_import_fields(
            {"id": row["paper_id"], "title": row["title"], "authors": row["authors"],
             "publishedOn": row["published_on"]},
            {"id": row["id"], "label": row["version_label"], "sourceUrl": row["source_url"],
             "sourceHash": row["source_hash"], "eligible": row["eligible"],
             "content": row["content"]},
            chunks,
        ))

    def parity(self, *, now, version_ids=None) -> dict:
        """The order-independent digest of every stored paper version (or the named
        ones), with their content and vectors; reading it writes nothing."""
        from backend.import_parity import parity

        ids = None if version_ids is None else sorted({str(v) for v in version_ids})

        def read(conn):
            names = conn.execute(
                "SELECT id FROM corpus.version WHERE %s::text[] IS NULL OR id=ANY(%s::text[]) "
                "ORDER BY id LIMIT %s",
                (ids, ids, IMPORT_MAX_PARITY_RECORDS + 1),
            ).fetchall()
            if len(names) > IMPORT_MAX_PARITY_RECORDS:
                raise ValueError("parity read exceeds its bound")
            return [self._stored_digest(conn, row["id"]) for row in names]

        digests = self.transactions.run("corpus", read)
        observed = now.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
        return parity("paper", digests, observed)
