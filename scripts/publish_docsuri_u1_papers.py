"""Publish the checked P1/P2 corpus into the explicitly owned local journey realm."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops/src"))
sys.path.insert(0, str(ROOT / "ingestion/src"))

import psycopg
from docsuri_ops.local_models import MODEL_PINS, LocalModelRuntime, ModelUnavailable

from backend.artifacts import Artifact, PrivateArtifacts
from backend.local_profile import LocalProfile, private_bytes
from backend.modules.corpus.repository import CorpusRepository
from backend.modules.discovery.local_embedding import LocalEmbeddings
from backend.transactions import OwnerTransactions
from scripts.load_docsuri_u1_papers import PAPERS, parser_identity, validate_manifest
from scripts.verify_docsuri_u1 import private_json, source_identity

METADATA = ROOT / "tests/u1_integrated_paper_journey/fixtures/paper-metadata.json"
QUERIES = ROOT / "tests/u1_integrated_paper_journey/fixtures/research-queries.json"
VECTOR_POLICY = "bge-m3-1024-pinned-1"


def checked_metadata(raw: bytes) -> list[dict]:
    if len(raw) > 16384:
        raise ValueError("bibliographic fixture exceeds allocation")
    value = json.loads(raw)
    papers = value["papers"]
    if [(p["paper"], p["version"], p["title"]) for p in papers] != list(PAPERS):
        raise ValueError("bibliographic fixture identity changed")
    for paper in papers:
        if paper["metadataSource"] != f"https://arxiv.org/abs/{paper['paper']}":
            raise ValueError("bibliographic source differs")
        date.fromisoformat(paper["publishedOn"])
        if not 1 <= len(paper["authors"]) <= 30 or any(
            not isinstance(name, str) or not name.strip() or len(name) > 100
            for name in paper["authors"]
        ):
            raise ValueError("bibliographic author list invalid")
    return papers


def batches(chunks: list[dict]):
    """Respect both cardinality and serialized request bounds without truncation."""
    batch = []
    size = 0
    for chunk in chunks:
        text = chunk["text"]
        encoded = len(json.dumps(text).encode())
        if not text.strip() or len(text.encode()) > 8192 or encoded > 12000:
            raise ValueError(
                "source chunk requires an explicit smaller embedding policy"
            )
        if batch and (len(batch) == 8 or size + encoded > 12000):
            yield batch
            batch, size = [], 0
        batch.append(text)
        size += encoded
    if batch:
        yield batch


def publish() -> dict:
    profile = LocalProfile.load(
        Path("/tmp/docsuri-u1-run/environment.json").resolve()
    ).journey()
    metadata_raw = METADATA.read_bytes()
    metadata = checked_metadata(metadata_raw)
    query_raw = QUERIES.read_bytes()
    if len(query_raw) > 8192:
        raise ValueError("research query fixture exceeds allocation")
    queries = json.loads(query_raw)
    if len(queries) != 4 or any(
        q["expectedPaper"] not in {p[0] for p in PAPERS} for q in queries
    ):
        raise ValueError("research query fixture scope differs")
    manifest = json.loads(private_bytes(profile.root / "paper-fixtures.json"))
    validate_manifest(manifest, profile.run_id)
    if manifest["parserIdentity"] != parser_identity():
        raise ValueError("source parser revision changed; explicit reparse required")
    files = PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
    identity = {
        "runId": profile.run_id,
        "database": profile.database_name,
        "realm": profile.realm,
        "parserIdentity": manifest["parserIdentity"],
        "metadataHash": hashlib.sha256(metadata_raw).hexdigest(),
        "queriesHash": hashlib.sha256(query_raw).hexdigest(),
        "sourceHashes": [p["sourceSha256"] for p in manifest["papers"]],
        "vectorPolicy": VECTOR_POLICY,
        "embeddingModel": MODEL_PINS["bge-m3:latest"],
    }
    target = profile.root / "corpus-publication.json"
    record = {"identity": identity, "papers": [], "ready": False, "attemptCount": 0}
    if target.exists():
        record = json.loads(private_bytes(target, maximum=65536))
        if record["identity"] != identity:
            raise ValueError("existing publication has different bound inputs")
    if record["attemptCount"] >= 16:
        raise ValueError("publication attempt evidence allocation exhausted")
    attempt = {
        "startedAt": time.time(),
        "sourceIdentity": source_identity(),
        "status": "running",
    }
    attempt_path = profile.root / f"corpus-publication-attempt-{time.time_ns()}.json"
    # Full source evidence stays separate from the small resumable manifest.
    if len(json.dumps(attempt).encode()) > 262144:
        raise ValueError("publication source evidence exceeds allocation")
    record.update(ready=False, attemptCount=record["attemptCount"] + 1)
    record["latestAttempt"] = {"file": attempt_path.name, "status": "running"}
    private_json(attempt_path, attempt)
    private_json(target, record)
    runtime = LocalModelRuntime(profile.root, profile.run_id, profile.expires_at)
    transactions = OwnerTransactions(profile, process="maintenance")
    corpus = CorpusRepository(transactions, files)
    try:
        for item, bibliography in zip(manifest["papers"], metadata, strict=True):
            raw = files.read(Artifact(**item["rawArtifact"]))
            parsed = json.loads(files.read(Artifact(**item["parsedArtifact"])))
            prior = next(
                (p for p in record["papers"] if p["paper"] == item["paper"]), None
            )
            if prior:
                vectors = json.loads(files.read(Artifact(**prior["vectorArtifact"])))
            else:
                if runtime.process is None:
                    runtime.__enter__()
                vectors = []
                for batch in batches(parsed["chunks"]):
                    vectors.extend(LocalEmbeddings(runtime).embed(batch))
                artifact = files.publish(
                    json.dumps(vectors, separators=(",", ":")).encode()
                )
                prior = {
                    "paper": item["paper"],
                    "vectorArtifact": vars(artifact),
                    "published": False,
                }
                record["papers"].append(prior)
                private_json(target, record)
            if len(vectors) != len(parsed["chunks"]):
                raise ValueError("cached projection cardinality changed")
            chunks = [
                dict(chunk, embedding=vector, vectorPolicy=VECTOR_POLICY)
                for chunk, vector in zip(parsed["chunks"], vectors, strict=True)
            ]
            row = corpus.publish(
                paper=item["paper"],
                version=f"{item['paper']}v{item['version']}",
                title=item["title"],
                authors=bibliography["authors"],
                published_on=date.fromisoformat(bibliography["publishedOn"]),
                source_url=item["sourceUrl"],
                version_label=f"v{item['version']}",
                content=parsed,
                raw=raw,
                provenance={
                    **identity,
                    "metadataSource": bibliography["metadataSource"],
                },
                chunks=chunks,
            )
            prior.update(published=True, version=row["id"], chunks=len(chunks))
            private_json(target, record)
        if "queryArtifact" not in record:
            if runtime.process is None:
                runtime.__enter__()
            query_vectors = LocalEmbeddings(runtime).embed(
                [q["query"] for q in queries]
            )
            query_artifact = files.publish(
                json.dumps({"queries": queries, "vectors": query_vectors}).encode()
            )
            record["queryArtifact"] = vars(query_artifact)
            private_json(target, record)
        else:
            query_cache = json.loads(files.read(Artifact(**record["queryArtifact"])))
            if query_cache["queries"] != queries or len(query_cache["vectors"]) != len(
                queries
            ):
                raise ValueError("bound research query cache differs")
        publication = corpus.confirm_publication(
            {
                f"{item['paper']}v{item['version']}": item["sourceSha256"]
                for item in manifest["papers"]
            }
        )
        record["publication"] = {key: str(value) for key, value in publication.items()}
        record["ready"] = True
        attempt["status"] = "published"
    except Exception as exc:
        attempt.update(status="failed", error=type(exc).__name__)
        raise
    finally:
        transactions.close()
        runtime.close()
        attempt.update(
            endedAt=time.time(),
            runtime=runtime.identity,
            samples=runtime.samples,
            serverExit=runtime.process.returncode if runtime.process else None,
        )
        if len(json.dumps(attempt).encode()) > 524288:
            record["ready"] = False
            record["latestAttempt"]["status"] = "evidence-allocation-refused"
            private_json(target, record)
            raise ValueError("publication attempt evidence exceeds allocation")
        private_json(attempt_path, attempt)
        record["latestAttempt"] = {
            "file": attempt_path.name,
            "status": attempt["status"],
            "sha256": hashlib.sha256(attempt_path.read_bytes()).hexdigest(),
        }
        private_json(target, record)
    return {
        "database": profile.database_name,
        "papers": len(record["papers"]),
        "ready": record["ready"],
    }


def main() -> int:
    profile = LocalProfile.load(Path("/tmp/docsuri-u1-run/environment.json").resolve())
    # Same advisory file lock as mutating test phases. Never reset either realm.
    descriptor = os.open(
        profile.root / "fixture-run.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
    )
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("fixture lock is not an owned regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(json.dumps(publish()))
        return 0
    except (
        ValueError,
        OSError,
        ModelUnavailable,
        psycopg.Error,
        subprocess.SubprocessError,
    ) as exc:
        # Database errors can carry bound data. Preserve detailed run evidence
        # privately and emit only the failure category at the command boundary.
        print(f"Publication refused: {type(exc).__name__}", file=sys.stderr)
        return 2
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
