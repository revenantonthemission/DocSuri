"""The production-size synthetic corpus (U8 plan Step 43, the `fixtures` phase).

600 papers of 100 chunks each, until the first dry run measures the real size, imported
through CorpusContent's own import operation (`backend.modules.corpus.paper_import.
PaperImport`, A4's `importPaper`) under the production corpus limits, with the realm's
deterministic stand-in embedder (`StandinEmbeddings`, BR7.1): every vector is derived from
its chunk's text, so the corpus and its search answers are the same in every run.

Every paper is synthetic: generated titles, one synthetic author, `arxiv:2610.<n>@v1`
identities that no real paper holds, and text built from a fixed vocabulary so the words
query and the meaning query both have something to find. The import is idempotent: a
paper already present answers `unchanged`, so an interrupted run resumes.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from pathlib import Path

PAPERS = 600
CHUNKS = 100
VERSION = "u8-corpus-v1"
VOCABULARY = (
    "attention", "transformer", "retrieval", "graph", "diffusion", "contrastive", "protein",
    "language", "vision", "reinforcement", "causal", "federated", "quantum", "sparse",
    "multilingual", "benchmark", "alignment", "embedding", "segmentation", "robustness",
)


def identity(index: int) -> str:
    return f"arxiv:2610.{index:05d}@v1"


def words(index: int, chunk: int) -> str:
    """A deterministic sentence of the vocabulary for one chunk of one paper."""
    seed = hashlib.sha256(f"{index}:{chunk}".encode()).digest()
    chosen = [VOCABULARY[seed[position] % len(VOCABULARY)] for position in range(8)]
    return (f"Synthetic paragraph {chunk} of paper {index} studies "
            + " ".join(chosen) + " in a generated setting, not a published result.")


def document(index: int) -> dict:
    paper = f"2610.{index:05d}"
    return {
        "meta": {"paperId": paper, "version": 1,
                 "title": f"Synthetic production-size paper {index}",
                 "provenance": {"sourceTier": "native_html",
                                "parserVersion": "docmodel-parser@8", "schemaVersion": "1.1.0",
                                "generatedAt": "2026-10-01T00:00:00Z"}},
        "fullText": f"Synthetic production-size paper {index}.",
        "sections": [{"id": "s1", "title": "Body", "blocks": [
            {"id": f"s1.p{chunk}", "type": "paragraph", "text": words(index, chunk)}
            for chunk in range(CHUNKS)]}],
    }


def anchor(root: Path) -> dt.date:
    """The realm's creation day: the UTC date of `createdAt` in `<root>/environment.json`
    (U8 plan Step 96(a)). Every resumed run of one realm reads the same day, so the
    corpus's dates hold across its runs, and a digest window ending on a realm's day
    holds corpus papers."""
    from backend.local_profile import private_bytes

    created = json.loads(private_bytes(root / "environment.json")).get("createdAt")
    try:
        return dt.datetime.fromtimestamp(float(created), dt.UTC).date()
    except (TypeError, ValueError, OverflowError, OSError) as error:
        raise ValueError("the realm's environment names no creation time") from error


def source(index: int, anchor: dt.date):
    from backend.modules.corpus.paper_import import PaperSource

    return PaperSource(
        source_key=f"u8-corpus-{index:05d}", version=identity(index),
        title=f"Synthetic production-size paper {index}", authors=("A. Synthetic",),
        source_url=f"https://arxiv.org/abs/2610.{index:05d}v1",
        published_on=anchor - dt.timedelta(days=index % 365),
        document=document(index),
        metadata={"synthetic": True, "corpusVersion": VERSION},
    )


def importer(profile):
    """CorpusContent's import operation over the realm, as the migration's owners use it
    (`docsuri_ops.migration.realm.owners_for`): production limits, the stand-in embedder."""
    from backend.artifacts import PrivateArtifacts
    from backend.modules.corpus.limits import PRODUCTION_LIMITS
    from backend.modules.corpus.paper_import import PaperImport
    from backend.modules.discovery.u8_search import VECTOR_POLICY, StandinEmbeddings
    from backend.transactions import OwnerTransactions

    transactions = OwnerTransactions(profile, process="maintenance")
    files = PrivateArtifacts.for_profile(profile, "corpus-files",
                                         maximum_bytes=PRODUCTION_LIMITS.max_source_bytes)
    return PaperImport(transactions, files, limits=PRODUCTION_LIMITS,
                       embedder=StandinEmbeddings(), vector_policy=VECTOR_POLICY), transactions


def present(transactions, papers: int = PAPERS) -> set[int]:
    """The corpus papers already in the realm, each with all its chunks: a paper's import
    is one transaction, so a present version is a whole one."""
    def read(conn):
        return conn.execute(
            "SELECT v.id FROM corpus.version v WHERE v.id = ANY(%s) AND "
            "EXISTS (SELECT 1 FROM corpus.projection c WHERE c.version_id = v.id)",
            ([identity(index) for index in range(papers)],),
        ).fetchall()

    found = {row["id"] for row in transactions.run("corpus", read)}
    return {index for index in range(papers) if identity(index) in found}


def prepare(profile, *, papers: int = PAPERS, seconds: float = 240.0) -> dict:
    """Import the papers still missing within `seconds`, picking up where an earlier run
    stopped. Deviation by the person's decision of 2026-10-23 ("Load over two runs"): the
    corpus may take more than one `fixtures` run, each inside its bound; the result says
    plainly whether it is complete, with the counts, and is never shrunk to fit."""
    started = time.monotonic()
    imported, outcomes = 0, {}
    day = anchor(profile.root)
    operation, transactions = importer(profile)
    try:
        already = present(transactions, papers)
        for index in range(papers):
            if index in already:
                continue
            if time.monotonic() - started > seconds:
                break
            result = operation.import_paper(source(index, day), re_embed=True)
            state = result.get("disposition", "unknown")
            if state == "refused":
                raise RuntimeError(f"a synthetic corpus paper was refused: {result['reasonKey']}")
            outcomes[state] = outcomes.get(state, 0) + 1
            imported += 1
        total = len(present(transactions, papers))
    finally:
        transactions.close()
    return {"version": VERSION, "papers": total, "target": papers,
            "chunksPerPaper": CHUNKS, "complete": total == papers,
            "remaining": papers - total, "presentAtStart": len(already),
            "importedThisRun": imported, "outcomes": outcomes,
            "seconds": round(time.monotonic() - started, 1)}


def record(path: Path, value: dict) -> None:
    from u8_fixtures import write_private

    write_private(path, value)


def describe() -> dict:
    return {"version": VERSION, "papers": PAPERS, "chunksPerPaper": CHUNKS,
            "digest": hashlib.sha256(json.dumps(
                [words(0, 0), identity(PAPERS - 1)]).encode()).hexdigest()}
