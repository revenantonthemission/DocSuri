"""A run's copy of v1 (U8 plan Step 31; BR4.3, BR8.11, BR8.12, BR8.15, BR9.12, Workflow 9
step 2).

1. The copy is recorded as a retained copy (`dry-run-snapshot`, or `v1-final-snapshot`
   with your decided disposal date) with every location it will occupy, before anything
   is copied: one archive per source on the backup volume, its database, its search
   index and its objects.
2. The backup agent's in-person `snapshot` dumps v1's database itself, through its
   read-only login in v1's data plane; the tool then streams the search index's
   documents and the objects (every document model under v1's `doc-model/` prefix, with
   the whole bucket's listing as a reserved member, Step 68(c)), each as a tar archive
   whose manifest carries its members' checksums, to the agent's in-person
   `snapshot-stream`.
3. When the copy completes, its checksums are recorded: the copy's record carries the
   digest of its parts (path and SHA-256 of each archive), which are kept owner-only
   beside the run's parity report. Before importing (re)starts, `verified_parts` checks
   them against that digest again, and each part's own digest is checked when it is
   streamed back.

A copy cut short is disposed through its record and taken again under a new one
(BR8.15).
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path

import rfc8785
from backend.modules.operations.migration.v1_source import (
    DOCMODEL_PREFIX,
    LISTING_MEMBER,
    encode_listing,
)

from docsuri_ops.backup_agent.archives import MAX_MEMBER, pack

PARTS = ("database", "index", "objects")
AGENT_KINDS = {"dry-run-snapshot": "dry-run-snapshot", "v1-final-snapshot": "final-snapshot"}


SCROLL = "1m"
PAGE = 500
MAX_DOCUMENTS = 1_000_000
MAX_OBJECTS = 100_000
MAX_OBJECT_BYTES = 16 * 1024 * 1024
MAX_LISTED_OBJECTS = 1_000_000


class OpenSearchDocuments:
    """v1's search index, read with the scroll API from its loopback address only: every
    document of the index, each one's source as v1 stored it."""

    def __init__(self, base_url: str, index: str, *, transport_factory: Callable | None = None,
                 timeout: float = 30.0):
        from urllib.parse import urlsplit

        parts = urlsplit(base_url)
        if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost"):
            raise SnapshotRefused("v1-index-not-loopback")
        self.base_url, self.index, self.timeout = base_url.rstrip("/"), index, timeout
        self.transport_factory = transport_factory

    def __call__(self) -> list[dict]:
        import httpx

        transport = self.transport_factory() if self.transport_factory else None
        with httpx.Client(base_url=self.base_url, transport=transport, timeout=self.timeout,
                          trust_env=False, follow_redirects=False) as client:
            answer = client.post(f"/{self.index}/_search", params={"scroll": SCROLL},
                                 json={"size": PAGE, "sort": ["_doc"]})
            documents: list[dict] = []
            while True:
                if answer.status_code != 200:
                    raise SnapshotRefused("v1-index-unreadable")
                value = answer.json()
                hits = value.get("hits", {}).get("hits", [])
                if not hits:
                    break
                documents.extend(hit.get("_source", {}) for hit in hits)
                if len(documents) > MAX_DOCUMENTS:
                    raise SnapshotRefused("v1-index-exceeds-its-bound")
                answer = client.post("/_search/scroll", json={"scroll": SCROLL,
                                                              "scroll_id": value["_scroll_id"]})
            return documents


class BucketObjects:
    """v1's object store as the migration copies it (L1-37), through an S3 client of it
    (`list_objects_v2`, `get_object`): the whole bucket listed page by page, never with a
    prefix, each object one `{"key", "size", "etag"}` entry (the ETag stands for NFR8.17's
    checksum); a body read only for a member, a key under v1's own `doc-model/` prefix
    (orphans included). The reader answers its members and, under the reserved name
    `v1-object-listing.jsonl`, the listing's JSON Lines form, sorted by key."""

    def __init__(self, client, bucket: str):
        self.client, self.bucket, self.prefix = client, bucket, DOCMODEL_PREFIX

    def __call__(self) -> dict[str, bytes]:
        objects: dict[str, bytes] = {}
        entries: list[dict] = []
        token = None
        while True:
            options = {"Bucket": self.bucket}
            if token:
                options["ContinuationToken"] = token
            page = self.client.list_objects_v2(**options)
            for item in page.get("Contents", []):
                entries.append({"key": item["Key"], "size": int(item["Size"]),
                                "etag": str(item.get("ETag", ""))})
                if len(entries) > MAX_LISTED_OBJECTS:
                    raise SnapshotRefused("v1-object-listing-exceeds-its-bound")
                if not item["Key"].startswith(self.prefix):
                    continue
                # The listing counts as one member within MAX_OBJECTS (the archive's
                # `MAX_MEMBERS`).
                if item["Size"] > MAX_OBJECT_BYTES or len(objects) + 1 >= MAX_OBJECTS:
                    raise SnapshotRefused("v1-objects-exceed-their-bound")
                body = self.client.get_object(Bucket=self.bucket, Key=item["Key"])["Body"]
                # The bound holds for the bytes copied, not only the listed size: v1 keeps
                # serving during dry runs, so an object rewritten after the listing is read
                # at most one byte past the bound and refused when longer.
                data = body.read(MAX_OBJECT_BYTES + 1)
                if len(data) > MAX_OBJECT_BYTES:
                    raise SnapshotRefused("v1-objects-exceed-their-bound")
                # A bounded read does not check the body against its Content-Length, so a
                # body cut short would pass as complete. One unbounded read finishes it: it
                # answers b"" for a complete body and makes botocore and http.client check
                # the length, raising on a short body so the copy is taken again (BR8.15).
                rest = body.read()
                if rest:
                    data += rest
                    if len(data) > MAX_OBJECT_BYTES:
                        raise SnapshotRefused("v1-objects-exceed-their-bound")
                objects[item["Key"]] = data
            if not page.get("IsTruncated"):
                break
            token = page["NextContinuationToken"]
        listing = encode_listing(entries)
        if len(listing) > MAX_MEMBER:
            raise SnapshotRefused("v1-object-listing-exceeds-its-bound")
        objects[LISTING_MEMBER] = listing
        return objects


class SnapshotRefused(RuntimeError):
    """The copy could not be taken or no longer matches its record; a fixed reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def parts_digest(parts: dict) -> str:
    return hashlib.sha256(rfc8785.dumps(parts)).hexdigest()


def _write_private(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    pending = path.with_name(f".{path.name}.pending")
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(rfc8785.dumps(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)


class Snapshot:
    def __init__(self, copies, *, dump: Callable[[str, str, dict | None], dict],
                 stream: Callable[[dict, bytes], dict], index: Callable[[], list[dict]],
                 objects: Callable[[], dict[str, bytes]], evidence: Path):
        """`dump(kind, recordId, decided)` is the agent's `snapshot`; `stream(header,
        payload)` its `snapshot-stream`; `index` reads v1's search index documents and
        `objects` the objects the migration reads (each document model), by key."""
        self.copies, self.dump, self.stream = copies, dump, stream
        self.index, self.objects, self.evidence = index, objects, evidence

    def parts_path(self, copy_id: str) -> Path:
        return self.evidence / f"snapshot-{copy_id}.json"

    def record(self, kind: str, run_id: str, *, dispose_after=None, approval_id=None) -> dict:
        """The retained copy, recorded before anything is copied."""
        if kind not in AGENT_KINDS:
            raise SnapshotRefused("snapshot-kind-refused")
        from uuid import uuid4

        copy_id = str(uuid4())
        return self.copies.record(
            kind, f"run:{run_id}", [f"backup-volume:{copy_id}:{part}" for part in PARTS],
            dispose_after=dispose_after, approval_id=approval_id, copy_id=copy_id)

    def take(self, record: dict, *, decided: dict | None = None) -> dict:
        """Copy v1 into the recorded copy and record its checksums."""
        copy_id, kind = record["copyId"], AGENT_KINDS[record["kind"]]
        dumped = self.dump(kind, copy_id, decided)
        documents = self.index()
        index_tar = pack({"documents.jsonl": b"".join(
            json.dumps(item, sort_keys=True).encode() + b"\n" for item in documents)})
        objects_tar = pack(self.objects())
        parts = {"database": {"path": dumped["location"], "sha256": dumped["sha256"]}}
        # Each part's size from the agent's receipt (`size`), kept on the copy's record
        # outside the parts file and its digest (U8 plan Step 70(b), NFR7.14).
        sizes = {"database": int(dumped.get("size", 0) or 0)}
        for part, payload in (("index", index_tar), ("objects", objects_tar)):
            header = {"kind": kind, "recordId": copy_id, "part": part,
                      "sha256": hashlib.sha256(payload).hexdigest()}
            if decided is not None:
                header["decided"] = decided
            written = self.stream(header, payload)
            if written.get("integrity") != "passed":
                raise SnapshotRefused("snapshot-archive-integrity-failed")
            parts[part] = {"path": written["location"], "sha256": written["sha256"]}
            sizes[part] = int(written.get("size", 0) or 0)
        if dumped.get("integrity") != "passed":
            raise SnapshotRefused("snapshot-dump-integrity-failed")
        _write_private(self.parts_path(copy_id), parts)
        return self.copies.complete(copy_id, checksum=parts_digest(parts),
                                    source_database_bytes=int(dumped.get("databaseBytes", 0)),
                                    part_sizes=sizes)

    def verified_parts(self, record: dict) -> dict:
        """The copy's parts, once they match the checksums its record holds."""
        if "completedAt" not in record or "checksum" not in record:
            raise SnapshotRefused("snapshot-incomplete")
        try:
            parts = json.loads(self.parts_path(record["copyId"]).read_bytes())
        except (OSError, ValueError):
            raise SnapshotRefused("snapshot-parts-missing") from None
        if set(parts) != set(PARTS) or parts_digest(parts) != record["checksum"]:
            raise SnapshotRefused("snapshot-checksum-differs")
        return parts
