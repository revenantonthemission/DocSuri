"""Saved-reference parity and admission-ordered history on the real owner store."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from psycopg.errors import InsufficientPrivilege

from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository
from backend.modules.library.control_service import ControlLibraryService
from backend.modules.library.repository.guarded import LibraryConflict
from backend.transactions import Authority

QUERY = {
    "query": "Transformer",
    "modeId": "lexical",
    "orderId": "relevance",
    "filters": [],
    "vocabularyRevision": "synthetic-paper-options-1",
    "policyRef": {"policyId": "synthetic-local-search", "revision": "1"},
}


@pytest.fixture
def library(connect, authority, transactions):
    with connect("library") as conn:
        for table in ("saved_query", "saved_paper", "history", "history_boundary"):
            conn.execute(
                f"DELETE FROM library.{table} WHERE account_id=%s", (authority.account_id,)
            )
    return ControlLibraryService(transactions, SYNTHETIC_POLICY, ControlCursor(b"l" * 32))


@pytest.fixture
def library_paper(connect):
    revision = uuid4()
    with connect("corpus") as conn:
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,metadata) VALUES('u2-library-paper','Saved title','[]','{}') "
            "ON CONFLICT(id) DO UPDATE SET withdrawn=false,title='Saved title'"
        )
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,private_path,eligible,purpose,eligibility_revision,provenance,content) "
            "VALUES('u2-library-version','u2-library-paper','https://fixture.invalid/paper',%s,'u2','fixture',true,'local-research',%s,'{}','{}') "
            "ON CONFLICT(id) DO UPDATE SET eligible=true,eligibility_revision=excluded.eligibility_revision",
            ("b" * 64, revision),
        )
    return "u2-library-paper", "u2-library-version", revision


@pytest.fixture
def discovery(transactions):
    return GuardedDiscoveryRepository(transactions)


def admit(discovery, authority):
    identifier = uuid4()
    digest = hashlib.sha256(
        json.dumps(QUERY, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    sequence = discovery.admit(authority, identifier, digest)
    return identifier, digest, sequence


def complete(discovery, authority, admission):
    identifier, digest, sequence = admission
    return discovery.record(authority, identifier, QUERY, digest, [], sequence)


def test_empty_history_read_does_not_allocate(library, authority, connect):
    first = library.page(authority, "history", limit=5)
    assert first["items"] == [] and first["clearBoundary"]
    assert library.page(authority, "history", limit=5)["clearBoundary"] == first["clearBoundary"]
    with connect("library") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM library.history_boundary WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 0
        )


def test_clear_empty_history_has_durable_receipt(library, authority):
    before = library.history_boundary(authority)
    key = uuid4()
    first = library.clear_history(authority, key, before["revision"])
    assert library.clear_history(authority, key, before["revision"]) == first
    assert str(library.history_boundary(authority)["revision"]) == first["revision"]


def test_preclear_search_finishing_late_is_suppressed(library, authority, discovery):
    old = admit(discovery, authority)
    library.clear_history(authority, uuid4(), library.history_boundary(authority)["revision"])
    fact = complete(discovery, authority, old)
    assert not library.accept_history(authority, fact)
    assert library.page(authority, "history", limit=5)["items"] == []


def test_clear_replay_keeps_postclear_search(library, authority, discovery):
    before = library.history_boundary(authority)
    key = uuid4()
    first = library.clear_history(authority, key, before["revision"])
    fact = complete(discovery, authority, admit(discovery, authority))
    assert library.accept_history(authority, fact)
    assert library.clear_history(authority, key, before["revision"]) == first
    assert library.page(authority, "history", limit=5)["items"][0]["historyId"] == str(fact["id"])


def test_history_duplicate_and_forged_fact(library, authority, discovery):
    fact = complete(discovery, authority, admit(discovery, authority))
    assert library.accept_history(authority, fact)
    assert library.accept_history(authority, dict(fact, query={"query": "forged"}))
    assert library.read_record(authority, "history", str(fact["id"]))["queryContext"] == QUERY
    assert not library.accept_history(authority, dict(fact, id=uuid4()))
    assert len(library.page(authority, "history", limit=5)["items"]) == 1


def test_history_fact_requires_actual_admission(library, authority, discovery):
    with pytest.raises(PermissionError):
        discovery.record(authority, uuid4(), QUERY, "f" * 64, [], 99)


def test_saved_query_return_never_executes(library, authority, connect):
    saved = library.save_query(authority, uuid4(), QUERY, label="읽을 논문")
    assert (
        library.read_record(authority, "queries", saved["savedSearchId"])["queryContext"] == QUERY
    )
    assert len(library.page(authority, "queries", limit=2)["items"]) == 1
    with connect("library") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM library.history WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 0
        )


def test_query_keyset_excludes_subsequent_saves(library, authority):
    for word in ("first", "second", "third"):
        library.save_query(authority, uuid4(), dict(QUERY, query=word))
    first = library.page(authority, "queries", limit=2)
    latest = library.save_query(authority, uuid4(), dict(QUERY, query="new"))
    second = library.page(authority, "queries", limit=2, cursor=first["page"]["nextCursor"])
    ids = [item["savedSearchId"] for item in first["items"] + second["items"]]
    assert len(ids) == len(set(ids)) == 3 and latest["savedSearchId"] not in ids


def test_cursor_bound_to_owner_view_and_authority(library, authority, connect, identities):
    for _ in range(2):
        library.save_query(authority, uuid4(), QUERY)
    cursor = library.page(authority, "queries", limit=1)["page"]["nextCursor"]
    with pytest.raises(ValueError):
        library.page(authority, "papers", limit=1, cursor=cursor)
    with connect("accounts") as conn:
        revision = uuid4()
        conn.execute(
            "UPDATE accounts.account SET authority_revision=%s WHERE id=%s",
            (revision, authority.account_id),
        )
        conn.execute(
            "UPDATE accounts.session SET authority_revision=%s WHERE id=%s",
            (revision, authority.session_id),
        )
    with pytest.raises(ValueError):
        library.page(authority, "queries", limit=1, cursor=cursor)
    with pytest.raises(InsufficientPrivilege):
        library.page(Authority(identities["b"], authority.session_id), "queries", limit=1)


def test_concurrent_save_query_same_key_is_one_effect(library, authority):
    key = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: library.save_query(authority, key, QUERY), range(2)))
    assert results[0] == results[1]
    assert len(library.page(authority, "queries", limit=5)["items"]) == 1


def test_remove_conflict_then_replay(library, authority):
    saved = library.save_query(authority, uuid4(), QUERY)
    with pytest.raises(LibraryConflict):
        library.remove_query(authority, UUID(saved["savedSearchId"]), uuid4(), uuid4())
    key = uuid4()
    result = library.remove_query(
        authority, UUID(saved["savedSearchId"]), key, UUID(saved["revision"])
    )
    assert (
        library.remove_query(authority, UUID(saved["savedSearchId"]), key, UUID(saved["revision"]))
        == result
    )
    assert library.page(authority, "queries", limit=5)["items"] == []


def test_saved_paper_preserves_original_eligibility_and_title(
    library, authority, library_paper, connect
):
    paper, version, revision = library_paper
    library.save(authority, paper, version, uuid4(), eligibility=revision)
    changed = uuid4()
    with connect("corpus") as conn:
        conn.execute(
            "UPDATE corpus.version SET eligibility_revision=%s WHERE id=%s", (changed, version)
        )
        conn.execute("UPDATE corpus.paper SET title=%s WHERE id=%s", ("Current title", paper))
    saved = library.read_record(authority, "papers", paper)
    assert saved["savedPaper"]["eligibilityRevision"] == str(revision)
    assert saved["resolvedPaper"]["eligibilityRevision"] == str(changed)
    assert saved["savedTitle"] == "Saved title"


def test_saved_reference_survives_source_withdrawal_and_can_be_removed(
    library, authority, library_paper, connect
):
    paper, version, revision = library_paper
    saved = library.save(authority, paper, version, uuid4(), eligibility=revision)
    with connect("corpus") as conn:
        conn.execute("UPDATE corpus.paper SET withdrawn=true WHERE id=%s", (paper,))
    result = library.page(authority, "papers", limit=5)["items"][0]
    assert result["sourceDisposition"] == "withdrawn" and "resolvedPaper" not in result
    library.remove_paper(authority, paper, uuid4(), UUID(saved["revision"]))
    assert library.page(authority, "papers", limit=5)["items"] == []


def test_saved_work_read_without_research_consent(library, authority, connect):
    saved = library.save_query(authority, uuid4(), QUERY)
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=false WHERE account_id=%s AND purpose='local-research'",
            (authority.account_id,),
        )
    assert (
        library.read_record(authority, "queries", saved["savedSearchId"])["queryContext"] == QUERY
    )
    assert library.clear_history(
        authority, uuid4(), library.history_boundary(authority)["revision"]
    )


def test_save_source_binding_and_eligibility_checked(library, authority, library_paper):
    paper, version, revision = library_paper
    with pytest.raises(LibraryConflict):
        library.save(authority, paper, version, uuid4(), eligibility=uuid4())
    with pytest.raises(PermissionError):
        library.save(authority, "foreign-paper", version, uuid4(), eligibility=revision)
    assert library.page(authority, "papers", limit=5)["items"] == []


def test_save_existing_reference_converges(library, authority, library_paper):
    paper, version, revision = library_paper
    first = library.save(authority, paper, version, uuid4(), eligibility=revision)
    assert library.save(authority, paper, version, uuid4(), eligibility=revision) == first
    assert len(library.page(authority, "papers", limit=5)["items"]) == 1
