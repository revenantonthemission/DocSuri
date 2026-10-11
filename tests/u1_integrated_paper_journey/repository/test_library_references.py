from uuid import UUID, uuid4

import psycopg
import pytest

from backend.transactions import Authority, UnknownCommit
from backend.modules.library.repository.guarded import GuardedLibraryRepository, LibraryConflict
from tests.u1_integrated_paper_journey.component.test_library_context import submitted_query

pytestmark = pytest.mark.u1_repository


@pytest.fixture
def queries(repositories, connect):
    r = repositories
    created = []

    def save(key=None, query=None):
        receipt = r["library"].save_query(
            r["authority"], key or uuid4(), query or submitted_query(), label="diagnostic"
        )
        created.append(UUID(receipt["savedSearchId"]))
        return receipt

    yield save
    # Only exact references created by this test helper in the diagnostic DB.
    # Receipts remain durable; no journey data or unknown query is removed.
    with connect("library") as conn:
        for identity in created:
            conn.execute(
                "DELETE FROM library.saved_query WHERE account_id=%s AND id=%s",
                (r["ids"]["a"], identity),
            )


def test_saved_query_reappears_on_fresh_repository_and_changed_intent_conflicts(
    repositories, queries
):
    r = repositories
    key = uuid4()
    receipt = queries(key)
    assert queries(key) == receipt
    fresh = GuardedLibraryRepository(r["tx"])
    rows = fresh.list_queries(r["authority"])
    found = next(row for row in rows if str(row["id"]) == receipt["savedSearchId"])
    assert found["query"] == {"queryContext": submitted_query(), "label": "diagnostic"}
    with pytest.raises(LibraryConflict):
        queries(key, dict(submitted_query(), query="different intended query"))


def test_remove_query_requires_revision_and_replays_after_deletion(repositories, queries):
    r = repositories
    saved = queries()
    identity, revision = UUID(saved["savedSearchId"]), UUID(saved["revision"])
    with pytest.raises(LibraryConflict):
        r["library"].remove_query(r["authority"], identity, uuid4(), uuid4())
    key = uuid4()
    removed = r["library"].remove_query(r["authority"], identity, key, revision)
    assert removed["removed"] is True
    assert r["library"].remove_query(r["authority"], identity, key, revision) == removed
    assert all(row["id"] != identity for row in r["library"].list_queries(r["authority"]))


def test_remove_withdrawn_paper_removes_reference_but_not_source(repositories, connect):
    r = repositories
    saved = r["library"].save(r["authority"], r["ids"]["paper"], r["ids"]["version"], uuid4(), None)
    with connect("corpus") as conn:
        conn.execute("UPDATE corpus.paper SET withdrawn=true WHERE id=%s", (r["ids"]["paper"],))
    key = uuid4()
    result = r["library"].remove_paper(
        r["authority"], r["ids"]["paper"], key, UUID(saved["revision"])
    )
    assert result["removed"] and r["library"].list_saved(r["authority"]) == []
    assert (
        r["library"].remove_paper(r["authority"], r["ids"]["paper"], key, UUID(saved["revision"]))
        == result
    )
    with connect("corpus") as conn:
        assert conn.execute(
            "SELECT withdrawn FROM corpus.paper WHERE id=%s", (r["ids"]["paper"],)
        ).fetchone()[0]


def test_remove_old_receipt_does_not_delete_a_later_resave(repositories):
    r = repositories

    def save(expected):
        return r["library"].save(
            r["authority"], r["ids"]["paper"], r["ids"]["version"], uuid4(), expected
        )

    original = save(None)
    key = uuid4()
    removed = r["library"].remove_paper(
        r["authority"], r["ids"]["paper"], key, UUID(original["revision"])
    )
    later = save(None)
    assert (
        r["library"].remove_paper(
            r["authority"], r["ids"]["paper"], key, UUID(original["revision"])
        )
        == removed
    )
    assert str(r["library"].list_saved(r["authority"])[0]["revision"]) == later["revision"]


def test_query_replay_checks_current_owner_and_revocation(repositories, queries, connect):
    r = repositories
    key = uuid4()
    queries(key)
    other = Authority(r["ids"]["b"], r["ids"]["session"])
    with pytest.raises(psycopg.Error):
        r["library"].list_queries(other)
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.session SET revoked=true WHERE id=%s", (r["ids"]["session"],))
    with pytest.raises(psycopg.Error):
        queries(key)


def test_history_clear_preserves_saved_query_and_reading_does_not_execute(repositories, queries):
    r = repositories
    saved = queries()
    before = r["library"].history_boundary(r["authority"])
    r["library"].clear_history(r["authority"], uuid4(), before["revision"])
    assert r["library"].list_history(r["authority"]) == []
    assert any(
        str(row["id"]) == saved["savedSearchId"]
        for row in r["library"].list_queries(r["authority"])
    )
    assert r["library"].history_boundary(r["authority"])["generation"] == before["generation"] + 1


def test_lost_remove_reply_reconciles_original_receipt(repositories, queries, monkeypatch):
    r = repositories
    saved = queries()
    identity, revision, key = UUID(saved["savedSearchId"]), UUID(saved["revision"]), uuid4()
    original = psycopg.Connection.commit

    def lost(conn):
        original(conn)
        raise psycopg.OperationalError("diagnostic lost removal response")

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "commit", lost)
        with pytest.raises(UnknownCommit):
            r["library"].remove_query(r["authority"], identity, key, revision)
    assert r["library"].remove_query(r["authority"], identity, key, revision)["removed"] is True


def test_valid_owner_b_cannot_read_or_remove_a_query_with_own_positive_control(
    repositories, queries, connect
):
    r = repositories
    a_saved = queries()
    a_id = UUID(a_saved["savedSearchId"])
    b_session = uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
            "authority_revision,expires_at) VALUES(%s,%s,%s,%s,%s,clock_timestamp()+"
            "interval '10 minutes')",
            (b_session, r["ids"]["b"], str(uuid4()), str(uuid4()), r["ids"]["revision"]),
        )
    b = Authority(r["ids"]["b"], b_session)
    b_saved = None
    try:
        assert all(row["account_id"] == b.account_id for row in r["library"].list_queries(b))
        b_saved = r["library"].save_query(b, uuid4(), submitted_query())
        b_id = UUID(b_saved["savedSearchId"])
        assert r["library"].read_query(b, b_id)["account_id"] == b.account_id
        with pytest.raises(PermissionError):
            r["library"].read_query(b, a_id)
        with pytest.raises(LibraryConflict):
            r["library"].remove_query(b, a_id, uuid4(), UUID(a_saved["revision"]))
        assert r["library"].read_query(r["authority"], a_id)["account_id"] == r["ids"]["a"]
        assert r["library"].remove_query(r["authority"], a_id, uuid4(), UUID(a_saved["revision"]))[
            "removed"
        ]
        assert r["library"].remove_query(b, b_id, uuid4(), UUID(b_saved["revision"]))["removed"]
    finally:
        with connect("accounts") as conn:
            conn.execute("UPDATE accounts.session SET revoked=true WHERE id=%s", (b_session,))
        if b_saved:
            with connect("library") as conn:
                conn.execute(
                    "DELETE FROM library.saved_query WHERE account_id=%s AND id=%s",
                    (b.account_id, UUID(b_saved["savedSearchId"])),
                )
