"""Real owner recovery of no-job admissions; no quota resets or new accounts."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from psycopg.errors import CheckViolation, InsufficientPrivilege

from backend.modules.corpus.repository import CorpusRepository
from backend.modules.research.errors import ResearchError
from backend.modules.research.execution import ResearchExecution
from backend.modules.research.jobs import ResearchJobs
from backend.modules.research.repository import digest
from backend.transactions import Authority, UnknownCommit


def prepared(transactions, authority, connect, *, seconds=-1):
    codec = ResearchExecution(transactions, CorpusRepository(transactions, None))
    codec.usage.ensure_entitlement(authority)
    context = codec.create_context(authority, "novelty")
    value = {
        "scope": {"contextId": str(context["id"]), "publicPapers": [],
                  "attachmentIds": [], "webReferences": [],
                  "scopePolicy": codec.policy.reference()},
        "text": "Synthetic prepared recovery", "inputMode": "topic",
        "policy": codec.policy.reference(),
    }
    key = str(uuid4())
    operation = uuid5(NAMESPACE_URL, f"ResearchWorkspace:{authority.account_id}:{key}")
    # Seed historical crash state; never move an existing deadline or session expiry.
    with connect("research") as conn:
        conn.execute(
            "INSERT INTO research.admission(operation_id,owner_id,operation_key,input_hash,"
            "accept_before) VALUES(%s,%s,%s,%s,clock_timestamp()+(%s * interval '1 second'))",
            (operation, authority.account_id, key, digest(value), seconds),
        )
    return codec, key, operation, value


def assert_released(codec, operation, connect):
    with connect("research") as conn:
        assert conn.execute(
            "SELECT state,release_reconciled FROM research.admission WHERE operation_id=%s",
            (operation,),
        ).fetchone() == {"state": "closed", "release_reconciled": True}
        assert conn.execute("SELECT 1 FROM research.job WHERE id=%s", (operation,)).fetchone() is None
    with connect("usage") as conn:
        row = conn.execute(
            "SELECT disposition,revision FROM usage.reservation WHERE operation_id=%s", (operation,),
        ).fetchone()
        assert row["disposition"] == "released"
        assert conn.execute(
            "SELECT count(*) AS n FROM usage.rejected_operation WHERE operation_id=%s", (operation,),
        ).fetchone()["n"] == 1
    codec.admission.reconcile_release(codec.usage, operation)
    with connect("usage") as conn:
        assert conn.execute(
            "SELECT revision FROM usage.reservation WHERE operation_id=%s", (operation,),
        ).fetchone()["revision"] == row["revision"]


@pytest.mark.parametrize("fault", ["crash", "unknown-reserve", "unknown-closure", "revoked", "expired"])
def test_prepared_recovers_without_browser_authority(
    transactions, authority, connect, fault, monkeypatch,
):
    if fault in {"revoked", "expired"}:
        # Separate session on the existing owner; never reactivate/extend the
        # invalidated session or allocate another account.
        session = uuid4()
        with connect("accounts") as conn:
            conn.execute(
                "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
                "authority_revision,expires_at) SELECT %s,account_id,%s,%s,"
                "authority_revision,expires_at FROM accounts.session WHERE id=%s",
                (session, str(uuid4()), str(uuid4()), authority.session_id),
            )
        authority = Authority(authority.account_id, session)
    codec, key, operation, value = prepared(transactions, authority, connect)
    if fault == "unknown-reserve":
        reserve = codec.usage.reserve

        def lost_ack(*args):
            reserve(*args)
            raise UnknownCommit("synthetic lost reserve acknowledgement")

        with monkeypatch.context() as patch:
            patch.setattr(codec.usage, "reserve", lost_ack)
            with pytest.raises(UnknownCommit):
                codec.accept(authority, key, value, "novelty-analysis")
    else:
        reservation = codec.usage.reserve(authority, operation, digest(value))
    if fault == "unknown-closure":
        run = transactions.run

        def lost_closure(owner, action):
            result = run(owner, action)
            if owner == "research" and action.__name__ == "recover":
                raise UnknownCommit("synthetic lost closure acknowledgement")
            return result

        with monkeypatch.context() as patch:
            patch.setattr(transactions, "run", lost_closure)
            with pytest.raises(UnknownCommit):
                codec.admission.recover_prepared()
    if fault in {"revoked", "expired"}:
        with connect("accounts") as conn:
            if fault == "revoked":
                conn.execute("UPDATE accounts.session SET revoked=true WHERE id=%s", (authority.session_id,))
            else:
                conn.execute(
                    "UPDATE accounts.session SET expires_at=clock_timestamp()-interval '1 second' "
                    "WHERE id=%s", (authority.session_id,),
                )
        with pytest.raises(InsufficientPrivilege) as error:
            ResearchJobs(transactions).accept(
                authority, kind="novelty-analysis", operation_key=key, value=value,
                usage_id=reservation["id"], operation_id=operation,
            )
        assert error.value.sqlstate == "42501"
    restarted = ResearchExecution(transactions, CorpusRepository(transactions, None))
    # Bounded fixture backlog only; each worker turn closes at most one admission.
    for _ in range(32):
        restarted.admission.recover_prepared()
        restarted.admission.reconcile_release(restarted.usage)
    assert_released(restarted, operation, connect)


def test_recovery_wins_and_fences_late_reserve_and_accept(transactions, authority, connect):
    codec, key, operation, value = prepared(transactions, authority, connect)
    for _ in range(32):
        codec.admission.recover_prepared()
    codec.admission.reconcile_release(codec.usage, operation)
    with pytest.raises(ValueError, match="rejected"):
        codec.usage.reserve(authority, operation, digest(value))
    with pytest.raises(ResearchError, match="CONFLICT"):
        ResearchJobs(transactions).accept(
            authority, kind="novelty-analysis", operation_key=key, value=value,
            usage_id=uuid4(), operation_id=operation,
        )


def test_acceptance_wins_unknown_ack_preserves_job(
    transactions, authority, connect, monkeypatch,
):
    codec, key, operation, value = prepared(transactions, authority, connect, seconds=1)
    accept = ResearchJobs.accept

    def lost_ack(self, *args, **kwargs):
        accept(self, *args, **kwargs)
        raise UnknownCommit("synthetic lost acceptance acknowledgement")

    with monkeypatch.context() as patch:
        patch.setattr(ResearchJobs, "accept", lost_ack)
        with pytest.raises(UnknownCommit):
            codec.accept(authority, key, value, "novelty-analysis")
    sleep(1.05)  # Deadline passes; accepted work must still be rediscovered.
    for _ in range(32):
        codec.admission.recover_prepared()
    codec.admission.reconcile_release(codec.usage, operation)
    assert codec.accept(authority, key, value, "novelty-analysis")["id"] == operation
    with connect("research") as conn:
        assert conn.execute(
            "SELECT state FROM research.admission WHERE operation_id=%s", (operation,),
        ).fetchone()["state"] == "accepted"
    with connect("usage") as conn:
        assert conn.execute(
            "SELECT 1 FROM usage.rejected_operation WHERE operation_id=%s", (operation,),
        ).fetchone() is None
    codec.step()


@pytest.mark.parametrize("first", ["reserve", "reject"])
def test_concurrent_usage_reserve_and_rejection_share_fence(
    transactions, authority, connect, monkeypatch, first,
):
    codec, key, operation, value = prepared(transactions, authority, connect)
    for _ in range(32):
        codec.admission.recover_prepared()
    held, release, second_entered = Event(), Event(), Event()
    pids = set()
    run = transactions.run

    def gated(owner, callback, **kwargs):
        def call(conn):
            if owner == "usage":
                pids.add(conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"])
                if len(pids) == 2:
                    second_entered.set()
            result = callback(conn)
            if owner == "usage" and not held.is_set():
                held.set()
                assert release.wait(5)
            return result
        return run(owner, call, **kwargs)

    def reserve():
        return codec.usage.reserve(authority, operation, digest(value))

    def reject():
        return codec.admission.reconcile_release(codec.usage, operation)

    with monkeypatch.context() as patch, ThreadPoolExecutor(max_workers=2) as pool:
        patch.setattr(transactions, "run", gated)
        initial = pool.submit(reserve if first == "reserve" else reject)
        assert held.wait(5)
        delayed = pool.submit(reject if first == "reserve" else reserve)
        try:
            assert second_entered.wait(1), "both real Usage transactions must overlap"
            assert not delayed.done()
        finally:
            release.set()
        initial.result(timeout=5)
        if first == "reject":
            with pytest.raises(ValueError, match="rejected"):
                delayed.result(timeout=5)
            with connect("usage") as conn:
                assert conn.execute(
                    "SELECT 1 FROM usage.reservation WHERE operation_id=%s", (operation,),
                ).fetchone() is None
        else:
            delayed.result(timeout=5)
            assert_released(codec, operation, connect)


def test_acceptance_lock_wins_over_expiry_recovery(
    transactions, authority, connect, monkeypatch,
):
    codec, key, operation, value = prepared(transactions, authority, connect, seconds=1)
    reservation = codec.usage.reserve(authority, operation, digest(value))
    held, release = Event(), Event()
    pids = set()
    run = transactions.run

    def gated(owner, callback, **kwargs):
        def call(conn):
            if owner == "research":
                pids.add(conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"])
            result = callback(conn)
            if owner == "research" and isinstance(result, dict) and result.get("id") == operation:
                held.set()
                assert release.wait(5)
            return result
        return run(owner, call, **kwargs)

    with monkeypatch.context() as patch, ThreadPoolExecutor(max_workers=1) as pool:
        patch.setattr(transactions, "run", gated)
        future = pool.submit(
            ResearchJobs(transactions).accept, authority, kind="novelty-analysis",
            operation_key=key, value=value, usage_id=reservation["id"], operation_id=operation,
        )
        assert held.wait(5)
        try:
            sleep(1.05)
            codec.admission.recover_prepared()  # Locked acceptance is skipped, never closed.
            assert len(pids) == 2, "normal acceptance and actual recovery must overlap in PostgreSQL"
        finally:
            release.set()
        assert future.result(timeout=5)["id"] == operation
    codec.admission.recover_prepared()
    assert codec.accept(authority, key, value, "novelty-analysis")["id"] == operation
    codec.step()


def test_deadline_is_immutable(transactions, authority, connect):
    codec, key, operation, value = prepared(transactions, authority, connect)
    with pytest.raises(CheckViolation), connect("research") as conn:
        conn.execute(
            "UPDATE research.admission SET accept_before=clock_timestamp()+interval '1 day' "
            "WHERE operation_id=%s", (operation,),
        )
    with pytest.raises(ResearchError, match="CONFLICT"):
        codec.accept(authority, key, value, "novelty-analysis")
