from __future__ import annotations

import os
import time
from uuid import UUID, uuid4

import psycopg
import pytest

from backend.artifacts import ArtifactUnavailable
from backend.transactions import Authority, Busy, UnknownCommit
from backend.modules.summarization.guarded_repository import intent_digest

pytestmark = pytest.mark.u1_repository


def accepted(r):
    operation = uuid4()
    payload = {
        "versionId": r["ids"]["version"],
        "sourceHash": "a" * 64,
        "action": "summary",
        "fixtureFamily": "repository-boundary",
    }
    admission = r["pa"].prepare(r["authority"], operation, payload)
    reservation = r["usage"].reserve(r["authority"], operation, admission["intent_hash"])
    job = r["pa"].accept(r["authority"], operation, reservation["id"])
    return job, payload


def test_unknown_commit_reconciles_original_receipt(repositories, monkeypatch):
    r = repositories
    key = uuid4()
    original = psycopg.Connection.commit
    once = [True]

    def lose_reply(conn):
        original(conn)
        if once[0]:
            once[0] = False
            raise psycopg.OperationalError("injected lost commit reply")

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "commit", lose_reply)
        with pytest.raises(UnknownCommit):
            r["library"].save(r["authority"], r["ids"]["paper"], r["ids"]["version"], key, None)
    receipt = r["library"].save(r["authority"], r["ids"]["paper"], r["ids"]["version"], key, None)
    assert receipt["revision"]
    assert len(r["library"].list_saved(r["authority"])) == 1


def test_failed_commit_has_no_acknowledged_saved_row(repositories, monkeypatch):
    r = repositories

    def fail_commit(conn):
        raise psycopg.OperationalError("injected unavailable commit")

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "commit", fail_commit)
        with pytest.raises(UnknownCommit):
            r["library"].save(r["authority"], r["ids"]["paper"], r["ids"]["version"], uuid4(), None)
    assert r["library"].list_saved(r["authority"]) == []


def test_admission_duplicate_conflict_and_durable_pending(repositories):
    r = repositories
    job, payload = accepted(r)
    repeated = r["pa"].prepare(r["authority"], job["id"], payload)
    assert repeated["disposition"] == "accepted"
    with pytest.raises(ValueError, match="conflict"):
        r["pa"].prepare(r["authority"], job["id"], dict(payload, action="translate"))
    restored = r["pa"].accept(r["authority"], job["id"], job["reservation_id"])
    assert restored["accepted_at"] == job["accepted_at"]
    assert {"id": job["id"]} in r["pa"].pending()


def test_published_result_and_usage_reconcile_once(repositories):
    r = repositories
    job, _ = accepted(r)
    claim = r["pa"].claim(job["id"], uuid4())
    fact = uuid4()
    result = r["pa"].complete(
        claim,
        fact,
        b"diagnostic bytes, not model evidence",
        {"fixture": True},
        {"testBoundary": True},
    )
    assert (
        r["pa"].complete(
            claim,
            fact,
            b"diagnostic bytes, not model evidence",
            {"fixture": True},
            {"testBoundary": True},
        )
        == result
    )
    assert (
        r["pa"].result(r["authority"], UUID(result["resultId"]))
        == b"diagnostic bytes, not model evidence"
    )
    assert any(row["id"] == job["id"] for row in r["pa"].unsettled())
    settlement = r["usage"].settle(
        job["reservation_id"], job["id"], disposition="committed", proof_hash=intent_digest(result)
    )
    assert (
        r["usage"].settle(
            job["reservation_id"],
            job["id"],
            disposition="committed",
            proof_hash=intent_digest(result),
        )
        == settlement
    )
    r["pa"].confirm_settlement(job["id"], settlement)
    assert all(row["id"] != job["id"] for row in r["pa"].unsettled())
    assert r["usage"].current(r["authority"])["counts"]["committed"] == 1


def test_source_withdrawal_denies_saved_and_result_reads(repositories, connect):
    r = repositories
    job, _ = accepted(r)
    claim = r["pa"].claim(job["id"], uuid4())
    result = r["pa"].complete(
        claim, uuid4(), b"diagnostic", {"fixture": True}, {"testBoundary": True}
    )
    r["library"].save(r["authority"], r["ids"]["paper"], r["ids"]["version"], uuid4(), None)
    with connect("corpus") as conn:
        conn.execute("UPDATE corpus.version SET eligible=false WHERE id=%s", (r["ids"]["version"],))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        r["library"].list_saved(r["authority"])
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        r["pa"].result(r["authority"], UUID(result["resultId"]))


def test_cross_account_result_and_claim_payload_denied(repositories):
    r = repositories
    job, _ = accepted(r)
    claim = r["pa"].claim(job["id"], uuid4())
    assert r["pa"].payload(claim)["versionId"] == r["ids"]["version"]
    wrong = dict(claim, worker_id=uuid4())
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        r["pa"].payload(wrong)
    bad = Authority(r["ids"]["b"], r["ids"]["session"])
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        r["pa"].snapshot(bad, job["id"])


@pytest.mark.parametrize("fault", ["missing", "corrupt", "partial", "mode", "symlink", "fifo"])
def test_private_files_reject_invalid_storage_without_hanging(repositories, fault):
    files = repositories["files"]
    item = files.publish(b"diagnostic bytes")
    path = files.root / item.name
    if fault == "missing":
        path.unlink()
    elif fault == "corrupt":
        path.write_bytes(b"wrong bytes here")
    elif fault == "partial":
        path.write_bytes(b"diagnostic")
    elif fault == "mode":
        path.chmod(0o644)
    elif fault == "symlink":
        path.unlink()
        path.symlink_to("/dev/null")
    else:
        path.unlink()
        os.mkfifo(path, 0o600)
    started = time.monotonic()
    with pytest.raises(ArtifactUnavailable):
        files.read(item)
    assert time.monotonic() - started < 1
    path.unlink(missing_ok=True)


def test_failure_before_and_after_publication_never_creates_success(repositories, monkeypatch):
    r = repositories
    job, _ = accepted(r)
    claim = r["pa"].claim(job["id"], uuid4())

    def denied_link(*args, **kwargs):
        raise PermissionError("injected publication denial")

    with monkeypatch.context() as patch:
        patch.setattr(os, "link", denied_link)
        with pytest.raises(ArtifactUnavailable):
            r["pa"].complete(claim, uuid4(), b"diagnostic", {}, {"testBoundary": True})
    assert r["pa"].snapshot(r["authority"], job["id"])["state"] == "running"
    with monkeypatch.context() as patch:
        patch.setattr(
            r["tx"],
            "run",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("injected crash after file publication")
            ),
        )
        with pytest.raises(RuntimeError, match="crash"):
            r["pa"].complete(claim, uuid4(), b"diagnostic", {}, {"testBoundary": True})
    assert r["pa"].snapshot(r["authority"], job["id"])["state"] == "running"


def test_aggregate_deadline_prevents_commit_after_late_callback(repositories, monkeypatch):
    r = repositories
    from backend import transactions

    clock = [0.0]
    with monkeypatch.context() as patch:
        patch.setattr(transactions.time, "monotonic", lambda: clock[0])

        def delayed(conn):
            conn.execute(
                "INSERT INTO library.saved_query(account_id,id,query) VALUES(%s,%s,'{}')",
                (r["ids"]["a"], uuid4()),
            )
            clock[0] = 11.0

        with pytest.raises(Busy, match="deadline"):
            r["tx"].run("library", delayed)


def test_serialization_retries_keep_finite_attempt_budget(repositories):
    r = repositories
    attempts = []

    def conflict(conn):
        attempts.append(1)
        raise psycopg.errors.SerializationFailure("deliberate conflict")

    with pytest.raises(psycopg.errors.SerializationFailure):
        r["tx"].run("library", conflict)
    assert len(attempts) == 3


def test_failure_reconciliation_and_readonly_history_events(repositories):
    r = repositories
    job, _ = accepted(r)
    claim = r["pa"].claim(job["id"], uuid4())
    renewed = r["pa"].renew(claim)
    assert renewed["revision"] == claim["revision"]
    fact = uuid4()
    failed = r["pa"].fail(renewed, fact, "insufficient-result")
    assert r["pa"].fail(renewed, fact, "insufficient-result") == failed
    before = r["usage"].current(r["authority"])
    assert any(row["id"] == job["id"] for row in r["pa"].history(r["authority"]))
    events = r["pa"].events(r["authority"], job["id"], 0)
    assert [row["snapshot"]["state"] for row in events] == ["accepted", "running", "failed"]
    assert r["usage"].current(r["authority"]) == before
    receipt = r["usage"].settle(
        job["reservation_id"], job["id"], disposition="released", proof_hash=intent_digest(failed)
    )
    r["pa"].confirm_settlement(job["id"], receipt)
    assert r["pa"].snapshot(r["authority"], job["id"])["settlement_pending"] is False
    with pytest.raises(ValueError, match="conflict"):
        r["usage"].settle(
            job["reservation_id"],
            job["id"],
            disposition="committed",
            proof_hash=intent_digest(failed),
        )


def test_rejected_admission_cannot_later_accept_and_usage_intent_conflicts(repositories):
    r = repositories
    operation = uuid4()
    payload = {
        "versionId": r["ids"]["version"],
        "sourceHash": "a" * 64,
        "fixtureFamily": "repository-boundary",
    }
    admission = r["pa"].prepare(r["authority"], operation, payload)
    reservation = r["usage"].reserve(r["authority"], operation, admission["intent_hash"])
    assert r["usage"].reserve(r["authority"], operation, admission["intent_hash"]) == reservation
    with pytest.raises(ValueError, match="conflict"):
        r["usage"].reserve(r["authority"], operation, "c" * 64)
    rejection = r["pa"].reject_open(r["authority"], operation)
    assert rejection["disposition"] == "rejected"
    with pytest.raises(ValueError, match="closed"):
        r["pa"].accept(r["authority"], operation, reservation["id"])
    r["usage"].settle(reservation["id"], operation, disposition="released", proof_hash="d" * 64)


def test_aggregate_real_statement_deadline_rolls_back(repositories):
    r = repositories
    query_id = uuid4()

    def slow(conn):
        conn.execute(
            "INSERT INTO library.saved_query(account_id,id,query) VALUES(%s,%s,'{}')",
            (r["ids"]["a"], query_id),
        )
        for _ in range(3):
            conn.execute("SELECT pg_sleep(4)")

    started = time.monotonic()
    with pytest.raises(psycopg.errors.QueryCanceled):
        r["tx"].run("library", slow)
    elapsed = time.monotonic() - started
    assert 9 <= elapsed <= 11.5
    assert (
        r["tx"].run(
            "library",
            lambda conn: conn.execute(
                "SELECT count(*) AS count FROM library.saved_query WHERE id=%s", (query_id,)
            ).fetchone()["count"],
        )
        == 0
    )


def test_replaced_worker_cannot_publish_and_winner_survives_lost_settlement_reply(
    repositories, connect, monkeypatch
):
    r = repositories
    job, _ = accepted(r)
    old_claim = r["pa"].claim(job["id"], uuid4())
    # A narrow fixture clock transition avoids a 30-second sleep; acquisition
    # and both publication attempts still cross the actual owner repository.
    with connect("assistance") as conn:
        conn.execute(
            "UPDATE assistance.job SET lease_expires_at=clock_timestamp()-interval '1 second' "
            "WHERE id=%s",
            (job["id"],),
        )
    winner = r["pa"].claim(job["id"], uuid4())
    assert winner["fence"] == old_claim["fence"] + 1
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        r["pa"].complete(old_claim, uuid4(), b"stale diagnostic", {}, {"testBoundary": True})
    result = r["pa"].complete(winner, uuid4(), b"winning diagnostic", {}, {"testBoundary": True})
    original = psycopg.Connection.commit
    once = [True]

    def lose_reply(conn):
        original(conn)
        if once[0]:
            once[0] = False
            raise psycopg.OperationalError("injected lost settlement reply")

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "commit", lose_reply)
        with pytest.raises(UnknownCommit):
            r["usage"].settle(
                job["reservation_id"],
                job["id"],
                disposition="committed",
                proof_hash=intent_digest(result),
            )
    receipt = r["usage"].settle(
        job["reservation_id"], job["id"], disposition="committed", proof_hash=intent_digest(result)
    )
    r["pa"].confirm_settlement(job["id"], receipt)
    assert r["usage"].current(r["authority"])["counts"]["committed"] == 1
    assert r["pa"].result(r["authority"], UUID(result["resultId"])) == b"winning diagnostic"
