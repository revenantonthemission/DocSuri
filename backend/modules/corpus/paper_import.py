"""CorpusContent's `importPaper` operation (U8 plan Step 31; A4, BR8.2, BR8.7, BR8.8, BR8.13,
NFR4.4).

Under trusted composition authority only, never a browser route: the migration tool
hands one v1 paper version (its canonical version identity, its metadata and v1's parsed
document model), and CorpusContent decides by its own rules:

- **Identity.** The version is named by the one canonical version identity
  (`CorpusVersionIdentity`, `arxiv:2101.00001@v2`): its canonical paper identity is the
  paper, so a version of a paper already in the corpus is linked to it, never
  duplicated (BR8.7).
- **Eligibility** (`ineligible-in-v2`): the corpus's finite source policy, as
  `maintenance._normalize_source` holds it for every other source: a title, one to 64
  authors, an HTTPS or HTTP source address and an explicit publication date when one
  is given.
- **Conversion** (`content-shape-unconvertible`, `exceeds-v2-limit`): v1's document
  model must validate as the shared document model and give usable chunks through the
  same walk the corpus uses for its own sources, under the profile's production limits
  (`chunks_from_document`).
- **Embeddings** (BR8.8, NFR4.4): every chunk is embedded again with the pinned model,
  in batches of 16, when your decision maps `embedding-provenance-unproven` to the
  re-embedding rule; v1's vectors are never reused. Otherwise the chunks are imported
  without vectors, so search answers them by words alone.

It writes through `CorpusImports` (Step 7), behind the publication barrier, and answers
A4's `ImportOutcome`: `imported`, `unchanged`, or `refused` with a reason, with the
digest of the stored normalized fields. A version or a paper's metadata never changes
once written: a changed one answers `refused`.

- **Time limits** (`refused-by-database-time-limits`, U8 plan Step 68(h), L1-75): an import
  whose own transaction the database's time limits refuse (the statement timeout's
  `QueryCanceled`, or the passed transaction deadline, `DeadlineReached`) answers
  `refused` with that reason, and the source file it published just before is erased, as
  is a `paper-metadata-changed` refusal's; a file reused from an existing version is
  never erased. Every other database error still propagates.
- **The measure** (Step 68(i), L1-79): `import_measured` answers the outcome with a
  `PaperMeasure`, the paper's chunk count and stored bytes when it landed, or the limit
  that refused it, which the migration adds to its run's `LimitRecord`. The outcome
  itself keeps exactly A4's fields.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from typing import Protocol

import psycopg
from backend.import_parity import outcome, stored_digest
from backend.modules.corpus.limits import CorpusLimitExceeded, CorpusLimits
from backend.modules.corpus.repository import CorpusImports
from backend.modules.corpus.source_parser import chunks_from_document
from backend.transactions import DeadlineReached

VERSION_IDENTITY = re.compile(r"((?:arxiv|doi|key):[^\s@]{1,240})@v([1-9][0-9]{0,3})")
INELIGIBLE, UNCONVERTIBLE = "ineligible-in-v2", "content-shape-unconvertible"
EXCEEDS = "exceeds-v2-limit"
# Your wording: "refused by the database's time limits" (L1-75).
TIME_REFUSED = "refused-by-database-time-limits"
METADATA_CHANGED = "paper-metadata-changed"
MAX_TITLE, MAX_AUTHORS, MAX_AUTHOR = 400, 64, 200
BLOCK_LIMIT = 8192


class Embedder(Protocol):
    """The pinned embedder's batch interface (`LocalEmbeddings`, or the realm's
    `StandinEmbeddings`)."""

    def embed_batches(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class PaperSource:
    """One v1 paper version as the migration hands it (A4's `PaperImport`)."""

    source_key: str
    version: str
    title: str
    authors: tuple[str, ...]
    source_url: str
    published_on: dt.date | None
    document: dict
    metadata: dict


@dataclass(frozen=True)
class PaperMeasure:
    """What one import measured (L1-79): the chunk count and stored bytes of a paper that
    landed (`imported` or `unchanged`), or the limit that refused it."""

    chunks: int | None = None
    source_bytes: int | None = None
    refused_by: str | None = None


@dataclass(frozen=True)
class LimitRecord:
    """A run's record of the corpus limits: each limit's value, whether an import checks
    it, the largest value among the papers that landed, and how many papers it refused.
    Only the chunk count and the stored bytes are checked: an import receives v1's papers
    already parsed, so HTML elements and nesting depth are never counted."""

    limits: CorpusLimits
    largest_chunks: int | None = None
    largest_bytes: int | None = None
    refused: tuple[tuple[str, int], ...] = field(default=())

    @classmethod
    def of(cls, limits: CorpusLimits) -> LimitRecord:
        return cls(limits)

    def _refusals(self, name: str) -> int:
        return dict(self.refused).get(name, 0)

    def add(self, measure: PaperMeasure | None) -> LimitRecord:
        """A new record with the measure added; this one stays as it was."""
        if measure is None:
            return self
        if measure.refused_by is not None:
            counts = dict(self.refused)
            counts[measure.refused_by] = counts.get(measure.refused_by, 0) + 1
            return replace(self, refused=tuple(sorted(counts.items())))
        chunks, size = self.largest_chunks, self.largest_bytes
        if measure.chunks is not None and (chunks is None or measure.chunks > chunks):
            chunks = measure.chunks
        if measure.source_bytes is not None and (size is None or measure.source_bytes > size):
            size = measure.source_bytes
        return replace(self, largest_chunks=chunks, largest_bytes=size)

    def as_dict(self) -> dict:
        limits = self.limits

        def entry(limit: int, checked: bool, largest: int | None, name: str) -> dict:
            return {"limit": limit, "checked": checked,
                    "largest": largest if checked else None, "refused": self._refusals(name)}

        value = {
            "profile": limits.name,
            "chunks": entry(limits.max_chunks, True, self.largest_chunks, "chunks"),
            "sourceBytes": entry(limits.max_source_bytes, True, self.largest_bytes,
                                 "sourceBytes"),
            "elements": entry(limits.max_elements, False, None, "elements"),
            "depth": entry(limits.max_depth, False, None, "depth"),
        }
        if not limits.split_large_blocks:
            # Only under limits that refuse a block over 8 KB, which no import composition
            # passes (the block refusal names itself, Step 68(i)).
            value["block"] = entry(BLOCK_LIMIT, True, None, "block")
        return value


def split_identity(version: str) -> tuple[str, str]:
    """The canonical paper identity and the version label of a version identity."""
    match = VERSION_IDENTITY.fullmatch(version or "")
    if match is None:
        raise ValueError("version identity outside the canonical form")
    return match.group(1), f"v{match.group(2)}"


def _eligible(source: PaperSource) -> bool:
    return (
        isinstance(source.title, str) and 1 <= len(source.title) <= MAX_TITLE
        and 1 <= len(source.authors) <= MAX_AUTHORS
        and all(isinstance(name, str) and 1 <= len(name) <= MAX_AUTHOR
                for name in source.authors)
        and isinstance(source.source_url, str)
        and source.source_url.startswith(("https://", "http://"))
        and (source.published_on is None or type(source.published_on) is dt.date)
    )


def convert(document: object, limits: CorpusLimits) -> dict:
    """v1's document model in the corpus's content shape: the model and its chunks.
    Raises `ValueError` (`content-shape-unconvertible`) or `CorpusLimitExceeded`."""
    from docsuri_shared.dtos import DocModel
    from pydantic import ValidationError

    if not isinstance(document, dict):
        raise ValueError("document model missing")
    try:
        model = DocModel.model_validate(document).model_dump(mode="json", exclude_none=True)
    except ValidationError:
        raise ValueError("document model outside the shared contract") from None
    return {"document": model, "chunks": chunks_from_document(model, limits)}


class PaperImport:
    def __init__(self, transactions, files, *, limits: CorpusLimits,
                 embedder: Embedder | None, vector_policy: str | None):
        """`files` is CorpusContent's private artifact store; `embedder` the pinned
        embedder (the realm's deterministic stand-in, BR7.1), or None."""
        self.transactions, self.files, self.limits = transactions, files, limits
        self.imports = CorpusImports(transactions)
        self.embedder, self.vector_policy = embedder, vector_policy

    def _existing_path(self, version: str) -> str | None:
        return self.transactions.run("corpus", lambda conn: (conn.execute(
            "SELECT private_path FROM corpus.version WHERE id=%s", (version,)
        ).fetchone() or {}).get("private_path"))

    def import_paper(self, source: PaperSource, *, re_embed: bool) -> dict:
        """A4's `importPaper` for one version; `re_embed` is your decision's mapping
        rule for `embedding-provenance-unproven`."""
        return self.import_measured(source, re_embed=re_embed)[0]

    def import_measured(self, source: PaperSource, *,
                        re_embed: bool) -> tuple[dict, PaperMeasure | None]:
        """`importPaper`'s outcome and what the import measured (L1-79); the measure never
        travels inside A4's outcome."""
        paper_id, label = split_identity(source.version)
        result, measure = self._decide(source, paper_id, label, re_embed)
        return {"sourceKey": source.source_key, "targetId": source.version, **result}, measure

    def _refused(self, source: PaperSource, reason: str) -> dict:
        digest = stored_digest({"version": source.version, "refused": reason})
        return outcome("refused", digest, reason=reason)

    def _decide(self, source: PaperSource, paper_id: str, label: str,
                re_embed: bool) -> tuple[dict, PaperMeasure | None]:
        if not _eligible(source):
            return self._refused(source, INELIGIBLE), None
        try:
            content = convert(source.document, self.limits)
        except CorpusLimitExceeded as error:
            # A paper over both limits counts once, under the chunk limit, checked first.
            return self._refused(source, EXCEEDS), PaperMeasure(
                refused_by=getattr(error, "limit", None) or "chunks")
        except ValueError:
            return self._refused(source, UNCONVERTIBLE), None
        chunks = self._chunks(content["chunks"], re_embed)
        raw = json.dumps(content["document"], sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
        if len(raw) > self.limits.max_source_bytes:
            return self._refused(source, EXCEEDS), PaperMeasure(refused_by="sourceBytes")
        paper = {"id": paper_id, "title": source.title, "authors": list(source.authors),
                 "publishedOn": source.published_on, "metadata": dict(source.metadata)}
        version = {"id": source.version, "label": label, "sourceUrl": source.source_url,
                   "sourceHash": hashlib.sha256(raw).hexdigest(), "eligible": True,
                   "content": content}
        existing = self._existing_path(source.version)
        published = None if existing else self.files.publish(raw).name
        try:
            result = self.imports.import_paper(
                paper=paper, version=version, chunks=chunks,
                private_path=existing or published,
                provenance={"source": "v1-import", "sourceKey": source.source_key},
            )
        except (psycopg.errors.QueryCanceled, DeadlineReached):
            # Refused inside CorpusContent's own transaction, before its commit: nothing
            # was written, so the file published for it is erased (Step 68(h)).
            self._erase(published)
            return self._refused(source, TIME_REFUSED), None
        state = result["disposition"]
        if state in ("imported", "unchanged"):
            return result, PaperMeasure(chunks=len(content["chunks"]), source_bytes=len(raw))
        if result.get("reasonKey") == METADATA_CHANGED:
            self._erase(published)
        return result, None

    def _erase(self, name: str | None) -> None:
        """A file this import published and no row names, erased; a reused one never."""
        if name is not None:
            self.files.erase(name)

    def _chunks(self, chunks: list[dict], re_embed: bool) -> list[dict]:
        texts = [chunk["text"] for chunk in chunks]
        vectors: list = [None] * len(texts)
        if re_embed:
            if self.embedder is None:
                raise ValueError("the pinned embedder is not composed")
            vectors = self.embedder.embed_batches(texts)
            if len(vectors) != len(texts):
                raise ValueError("embedding cardinality mismatch")
        return [
            {"anchor": chunk["anchor"], "section": chunk["section"], "text": chunk["text"],
             "embedding": vector,
             "vectorPolicy": self.vector_policy if vector is not None else None}
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
