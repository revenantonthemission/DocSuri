"""Fetch only the two approved private research fixtures; never publish them."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ingestion/src"))

import httpx

from backend.artifacts import Artifact, PrivateArtifacts
from backend.local_profile import LocalProfile
from backend.modules.corpus.source_parser import parse_source
from scripts.verify_docsuri_u1 import private_json

PAPERS = (
    ("1706.03762", 7, "Attention Is All You Need"),
    (
        "2005.11401",
        4,
        "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
    ),
)


def parser_identity() -> str:
    paths = sorted((ROOT / "ingestion/src/docsuri_ingestion/docmodel").glob("*.py"))
    paths.extend(
        [
            ROOT / "backend/modules/corpus/source_parser.py",
            ROOT / "shared/python/src/docsuri_shared/docmodel_contract.py",
            ROOT / "backend/uv.lock",
        ]
    )
    rows = [
        (str(path.relative_to(ROOT)), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in paths
    ]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def validate_manifest(current: dict, run_id: str) -> None:
    if (
        current.get("runId") != run_id
        or current.get("purpose") != "isolated-local-research"
        or current.get("publicRedistribution") is not False
        or [
            (p.get("paper"), p.get("version"), p.get("title"))
            for p in current.get("papers", [])
        ]
        != list(PAPERS)
    ):
        raise ValueError("fixture manifest scope or custody mismatch")
    for item in current["papers"]:
        expected_url = f"https://arxiv.org/html/{item['paper']}v{item['version']}"
        if (
            item.get("sourceUrl") != expected_url
            or item.get("sourceSha256") != item["rawArtifact"]["sha256"]
        ):
            raise ValueError("fixture source identity mismatch")


def parse_item(item: dict, raw: bytes, files: PrivateArtifacts) -> dict:
    document, chunks = parse_source(
        raw,
        paper=item["paper"],
        version=item["version"],
        title=item["title"],
        fetched_at=datetime.fromisoformat(item["fetchedAt"]),
    )
    parsed = files.publish(
        json.dumps(
            {"document": document, "chunks": chunks}, ensure_ascii=False
        ).encode()
    )
    return {**item, "chunkCount": len(chunks), "parsedArtifact": vars(parsed)}


def load() -> dict:
    profile = LocalProfile.load(Path("/tmp/docsuri-u1-run/environment.json").resolve())
    target = profile.root / "paper-fixtures.json"
    files = PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
    if target.exists():
        info = target.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or target.is_symlink()
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
        ):
            raise ValueError("fixture manifest custody mismatch")
        current = json.loads(target.read_text())
        validate_manifest(current, profile.run_id)
        raw_sources = []
        for item in current["papers"]:
            raw_sources.append(files.read(Artifact(**item["rawArtifact"])))
            files.read(Artifact(**item["parsedArtifact"]))
        identity = parser_identity()
        if current.get("parserIdentity") != identity:
            # Preserve the previous evidence before publishing a new parse of
            # the same checked raw bytes; no repeat network fetch is required.
            previous_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            private_json(profile.root / f"paper-fixtures-{previous_hash}.json", current)
            current = {
                **current,
                "parserIdentity": identity,
                "papers": [
                    parse_item(item, raw, files)
                    for item, raw in zip(current["papers"], raw_sources, strict=True)
                ],
            }
            private_json(target, current)
        return current
    output = {
        "runId": profile.run_id,
        "purpose": "isolated-local-research",
        "publicRedistribution": False,
        "parserIdentity": parser_identity(),
        "papers": [],
    }
    with httpx.Client(
        timeout=20,
        trust_env=False,
        follow_redirects=False,
        limits=httpx.Limits(max_connections=1),
    ) as client:
        for paper, version, title in PAPERS:
            if output["papers"]:
                time.sleep(3)
            url = f"https://arxiv.org/html/{paper}v{version}"
            raw = bytearray()
            with client.stream(
                "GET", url, headers={"User-Agent": "DocSuri-local-research/2"}
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2097152:
                        raise ValueError(
                            "source download exceeds approved fixture bound"
                        )
            fetched = datetime.now(UTC)
            document, chunks = parse_source(
                bytes(raw),
                paper=paper,
                version=version,
                title=title,
                fetched_at=fetched,
            )
            source = files.publish(bytes(raw))
            parsed = files.publish(
                json.dumps(
                    {"document": document, "chunks": chunks}, ensure_ascii=False
                ).encode()
            )
            output["papers"].append(
                {
                    "paper": paper,
                    "version": version,
                    "title": title,
                    "sourceUrl": url,
                    "fetchedAt": fetched.isoformat(),
                    "sourceSha256": hashlib.sha256(raw).hexdigest(),
                    "chunkCount": len(chunks),
                    "rawArtifact": vars(source),
                    "parsedArtifact": vars(parsed),
                    "eligibility": "arxiv-api-personal-research-use; no public redistribution",
                }
            )
    private_json(target, output)
    return output


if __name__ == "__main__":
    result = load()
    print(
        json.dumps(
            {
                "privateManifest": "/tmp/docsuri-u1-run/paper-fixtures.json",
                "papers": [
                    {
                        k: item[k]
                        for k in ("paper", "version", "sourceSha256", "chunkCount")
                    }
                    for item in result["papers"]
                ],
            }
        )
    )
