from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from backend.artifacts import PrivateArtifacts
from backend.modules.corpus.repository import CorpusRepository
from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository
from backend.modules.discovery.local_search import POLICY, VOCABULARY, SearchPageBuilder
from backend.modules.summarization.guarded_repository import intent_digest

pytestmark = pytest.mark.u1_repository


def test_corpus_publication_and_readonly_projection_boundary(repositories, realm, connect):
    r = repositories
    files = PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152)
    corpus = CorpusRepository(r["tx"], files)
    # Recreate only this published diagnostic source, which has no accepted jobs.
    with connect("assistance") as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM assistance.job WHERE version_id='repository-fixture-v1'"
            ).fetchone()[0]
            == 0
        )
    with connect("corpus") as conn:
        prior = conn.execute(
            "SELECT provenance FROM corpus.version WHERE id='repository-fixture-v1'"
        ).fetchone()
        if prior:
            assert prior[0].get("testBoundary") is True
            conn.execute("DELETE FROM corpus.projection WHERE version_id='repository-fixture-v1'")
            conn.execute("DELETE FROM corpus.version WHERE id='repository-fixture-v1'")
            conn.execute("DELETE FROM corpus.paper WHERE id='repository-fixture'")
    args = {
        "paper": "repository-fixture",
        "version": "repository-fixture-v1",
        "title": "Repository diagnostic",
        "authors": ["Synthetic"],
        "source_url": "https://fixture.invalid/repository",
        "version_label": "v1",
        "content": {"fixture": True},
        "raw": b"bounded storage fixture",
        "provenance": {"testBoundary": True},
        "chunks": [
            {"anchor": "diagnostic-1", "section": "Diagnostic", "text": "bounded storage fixture"}
        ],
    }
    # One explicitly owned diagnostic projection makes 256 new chunks exceed
    # the aggregate cap. The rejected transaction must publish no version.
    with connect("corpus") as conn:
        conn.execute(
            "INSERT INTO corpus.projection(version_id,ordinal,content_hash,anchor,"
            "section,text_content) VALUES('fixture-v1',2147483647,%s,"
            "'allocation-control','Diagnostic','allocation control')",
            ("a" * 64,),
        )
    try:
        oversized = [dict(args["chunks"][0], anchor=f"diagnostic-{i}") for i in range(256)]
        with pytest.raises(ValueError, match="aggregate projection"):
            corpus.publish(**{**args, "chunks": oversized})
        with connect("corpus") as conn:
            assert not conn.execute(
                "SELECT id FROM corpus.version WHERE id=%s", (args["version"],)
            ).fetchone()
    finally:
        with connect("corpus") as conn:
            conn.execute(
                "DELETE FROM corpus.projection WHERE version_id='fixture-v1' "
                "AND ordinal=2147483647 AND anchor='allocation-control'"
            )
    row = corpus.publish(**args)
    with connect("corpus") as conn:
        # Re-enable only the same named diagnostic after an earlier run's withdrawal.
        conn.execute(
            "UPDATE corpus.version SET eligible=true WHERE id='repository-fixture-v1' AND provenance->>'testBoundary'='true'"
        )
    assert corpus.publish(**args)["source_hash"] == row["source_hash"]
    assert corpus.read(args["version"])["title"] == args["title"]
    discovery = GuardedDiscoveryRepository(r["tx"])
    before = discovery.snapshot(None)["publication"]
    assert len(before["manifest_hash"]) == 64
    with pytest.raises(ValueError, match="parsed content"):
        corpus.publish(**{**args, "content": {"changed": True}})
    assert discovery.snapshot(None)["publication"]["revision"] == before["revision"]
    assert any(item["version_id"] == args["version"] for item in discovery.candidates(None))
    ranked_snapshot = discovery.snapshot(None, query="storage")
    scored = next(
        row for row in ranked_snapshot["candidates"] if row["version_id"] == args["version"]
    )
    assert scored["lexical_score"] > 0
    page = SearchPageBuilder(b"diagnostic-cursor-key" * 2).build(
        snapshot=ranked_snapshot,
        query={
            "query": "storage",
            "modeId": "lexical",
            "orderId": "relevance",
            "filters": [],
            "vocabularyRevision": VOCABULARY,
            "policyRef": POLICY,
        },
        execution=str(uuid4()),
        owner="anonymous",
    )
    assert page["hits"][0]["paper"]["versionId"] == args["version"]
    with connect("discovery") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM corpus.projection")
    with connect("discovery") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE corpus.publication SET revision=gen_random_uuid()")
    r["library"].save(r["authority"], args["paper"], args["version"], uuid4(), None)
    r["library"].save(r["authority"], r["ids"]["paper"], r["ids"]["version"], uuid4(), None)
    corpus.withdraw(args["version"])
    after = discovery.snapshot(None)["publication"]
    assert after["revision"] != before["revision"]
    assert after["generation_id"] == before["generation_id"]
    assert after["manifest_hash"] != before["manifest_hash"]
    saved = {item["version_id"]: item for item in r["library"].list_saved(r["authority"])}
    assert len(saved) == 2
    assert saved[args["version"]]["availability"] == "withdrawn"
    assert saved[r["ids"]["version"]]["availability"] == "available"
    assert all(
        item["version_id"] != args["version"] for item in discovery.candidates(r["authority"])
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        corpus.read(args["version"])


def test_durable_history_delivery_after_clear_is_suppressed(repositories):
    r = repositories
    discovery = GuardedDiscoveryRepository(r["tx"])
    boundary = r["library"].history_boundary(r["authority"])
    query = {"q": "diagnostic query"}
    execution = discovery.record(
        r["authority"], uuid4(), query, intent_digest(query), [], boundary["generation"]
    )
    r["library"].clear_history(r["authority"], uuid4(), boundary["revision"])
    pending = discovery.pending_history(r["authority"])
    assert any(fact["id"] == execution["id"] for fact in pending)
    assert not r["library"].accept_history(r["authority"], execution)
    discovery.acknowledge_history(r["authority"], execution["id"], delivered=False)
    assert all(fact["id"] != execution["id"] for fact in discovery.pending_history(r["authority"]))


def test_container_replacement_preserves_acknowledged_save(repositories, realm):
    r = repositories
    key = uuid4()
    receipt = r["library"].save(r["authority"], r["ids"]["paper"], r["ids"]["version"], key, None)
    path = Path(__file__).resolve().parents[3] / "scripts/verify_docsuri_u1.py"
    spec = importlib.util.spec_from_file_location("owned_runtime", path)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    manifest = runtime.load_manifest(realm[0].root / "environment.json")
    runtime.replace_database(manifest)
    assert (
        r["library"].save(r["authority"], r["ids"]["paper"], r["ids"]["version"], key, None)
        == receipt
    )
    assert r["library"].list_saved(r["authority"])[0]["revision"] == __import__("uuid").UUID(
        receipt["revision"]
    )
