"""The snapshot's tar archives and the migration's identities (U8 plan Step 31; BR8.11,
BR8.12, BR4.3).

An archive carries its members' checksums in a manifest written first; reading it back
refuses a member outside the archive's form, a repeated or unreadable or missing
manifest, a member the manifest does not list and a member whose bytes changed. The
migration's canonical paper identity prefers the arXiv identifier, then the DOI, then a
bounded key, and refuses a paper with none.
"""

from __future__ import annotations

import io
import json
import tarfile

import pytest

from backend.modules.operations.migration import identities
from docsuri_ops.backup_agent import archives
from docsuri_ops.backup_agent.archives import ArchiveRefused, pack, unpack_bytes, verify


def raw_tar(entries: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, payload in entries:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def manifest(**members: str) -> bytes:
    return json.dumps({"members": members}).encode()


def test_a_packed_archive_reads_back_and_verifies(tmp_path):
    payload = pack({"b.json": b"{}", "a/doc.json": b"[1]"})
    assert unpack_bytes(payload) == {"a/doc.json": b"[1]", "b.json": b"{}"}
    assert pack({"b.json": b"{}", "a/doc.json": b"[1]"}) == payload  # deterministic
    path = tmp_path / "part.tar"
    path.write_bytes(payload)
    assert verify(path)
    path.write_bytes(payload[:100])
    assert not verify(path)


@pytest.mark.parametrize("name", ["../escape", "/absolute", archives.MANIFEST, ""])
def test_a_member_outside_the_form_is_not_packed(name):
    with pytest.raises(ArchiveRefused):
        pack({name: b"x"})


@pytest.mark.parametrize("entries", [
    [("doc.json", b"x")],  # no manifest
    [(archives.MANIFEST, b"not json"), ("doc.json", b"x")],
    [(archives.MANIFEST, manifest()), (archives.MANIFEST, manifest())],
    [(archives.MANIFEST, manifest(**{"doc.json": "0" * 64})), ("../doc.json", b"x")],
    [(archives.MANIFEST, manifest()), ("doc.json", b"x")],  # a member not listed
    [(archives.MANIFEST, manifest(**{"doc.json": "0" * 64})), ("doc.json", b"x")],
], ids=["missing", "unreadable", "repeated", "unsafe-name", "unlisted", "changed"])
def test_an_archive_that_differs_from_its_manifest_is_refused(entries):
    with pytest.raises(ArchiveRefused):
        unpack_bytes(raw_tar(entries))


def test_a_snapshot_records_each_parts_size(tmp_path, clock):
    """Step 71(e), NFR7.14: the take records each part's size from the agent's receipts
    on the copy, outside the parts file and its digest."""
    from backend.modules.operations.retained_copies import RetainedCopies
    from backend.u8_policy import SYNTHETIC_OPERATIONS
    from docsuri_ops.migration.snapshot import Snapshot
    from tests.u8_service_operations_integration import recovery_flows as rf

    sizes = {"index": 2048, "objects": 4096}
    calls: list = []

    def dump(kind, record_id, decided):
        calls.append(("dump", kind))
        return {"location": f"archives/{record_id}-database.archive", "sha256": "a" * 64,
                "size": 1024, "databaseBytes": 1048576, "integrity": "passed"}

    def stream(header, payload):
        calls.append(("stream", header["part"]))
        return {"location": f"archives/{header['recordId']}-{header['part']}.archive",
                "sha256": header["sha256"], "size": sizes[header["part"]],
                "integrity": "passed"}

    ledger = rf.open_ledger(tmp_path, clock)
    try:
        copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
        snapshot = Snapshot(copies, dump=dump, stream=stream, index=lambda: [{"id": 1}],
                            objects=lambda: {"doc-model/a.json": b"{}"},
                            evidence=tmp_path / "evidence")
        record = snapshot.record("dry-run-snapshot", "run-fixture")
        taken = snapshot.take(record)
        assert calls == [("dump", "dry-run-snapshot"), ("stream", "index"),
                         ("stream", "objects")]
        assert taken["partSizes"] == {"database": 1024, "index": 2048, "objects": 4096}
        assert taken["sourceDatabaseBytes"] == 1048576
        parts = snapshot.verified_parts(taken)  # its checksum is unchanged
        assert set(parts) == {"database", "index", "objects"}
        assert all(set(value) == {"path", "sha256"} for value in parts.values())
    finally:
        ledger.close()


def test_bytes_that_are_no_archive_are_refused():
    with pytest.raises(ArchiveRefused):
        unpack_bytes(b"\x00" * 10 + b"not a tar archive")


def test_the_canonical_paper_prefers_arxiv_then_doi_then_a_key():
    assert identities.canonical_paper(arxiv="arXiv:1706.03762v5") == "arxiv:1706.03762"
    assert identities.canonical_paper(arxiv="not an id", doi="doi:10.1000/ABC") == (
        "doi:10.1000/abc")
    assert identities.canonical_paper(doi="nonsense", key="Local-Paper-1") == (
        "key:local-paper-1")
    for given in ({}, {"arxiv": "x", "doi": "y", "key": "#bad key#"}):
        with pytest.raises(ValueError):
            identities.canonical_paper(**given)


def test_identities_refuse_values_outside_their_bounds():
    assert identities.arxiv_parts("hep-th/9901001v2") == ("hep-th/9901001", 2)
    assert identities.arxiv_parts("") is None
    assert identities.version_identity("arxiv:1706.03762", 2) == "arxiv:1706.03762@v2"
    for version in (0, 10000, "2", True):
        with pytest.raises(ValueError):
            identities.version_identity("arxiv:1706.03762", version)
    with pytest.raises(ValueError):
        identities.target_id("not-a-kind", "x")
    kind = sorted(identities.KINDS)[0]
    with pytest.raises(ValueError):
        identities.target_id(kind, "")
    assert identities.target_id(kind, "1") == identities.target_id(kind, "1")
