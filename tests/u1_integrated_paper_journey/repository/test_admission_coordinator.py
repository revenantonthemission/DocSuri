from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time

import pytest
from psycopg.errors import InsufficientPrivilege

from backend.modules.summarization.admission import AssistanceAdmission
from backend.transactions import UnknownCommit

pytestmark = pytest.mark.u1_repository


def prepared(r):
    return {
        "versionId": r["ids"]["version"],
        "sourceHash": "a" * 64,
        "action": "summary",
        "fixtureFamily": "repository-boundary",
    }


def complete(r, job):
    claim = r["pa"].claim(job["id"], uuid4())
    return r["pa"].complete(
        claim,
        uuid4(),
        b"diagnostic result bytes, not model-quality evidence",
        {"fixture": True},
        {"testBoundary": True},
    )


def test_admission_replay_has_one_job_reservation_and_original_acceptance(repositories):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    operation = uuid4()
    first = service.accept(r["authority"], operation, prepared(r))
    repeated = service.accept(r["authority"], operation, prepared(r))
    assert repeated["accepted_at"] == first["accepted_at"]
    assert repeated["reservation_id"] == first["reservation_id"]
    assert r["usage"].current(r["authority"])["counts"] == {"reserved": 1}


def test_restart_between_reservation_and_acceptance_reconciles_same_intent(
    repositories, monkeypatch
):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    operation = uuid4()
    with monkeypatch.context() as patch:
        patch.setattr(
            r["pa"],
            "accept",
            lambda *args: (_ for _ in ()).throw(RuntimeError("injected process stop")),
        )
        with pytest.raises(RuntimeError):
            service.accept(r["authority"], operation, prepared(r))
    reserved = r["usage"].reservation(r["authority"], operation)
    assert reserved["disposition"] == "reserved"
    job = AssistanceAdmission(r["pa"], r["usage"]).accept(r["authority"], operation, prepared(r))
    assert job["reservation_id"] == reserved["id"]


def test_lost_acceptance_reply_does_not_release_or_duplicate(repositories, monkeypatch):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    operation = uuid4()
    original = r["pa"].accept

    def lost(*args):
        original(*args)
        raise UnknownCommit("injected lost acknowledgement")

    with monkeypatch.context() as patch:
        patch.setattr(r["pa"], "accept", lost)
        with pytest.raises(UnknownCommit):
            service.accept(r["authority"], operation, prepared(r))
    job = service.accept(r["authority"], operation, prepared(r))
    assert job["id"] == operation
    assert r["usage"].reservation(r["authority"], operation)["disposition"] == "reserved"


def test_lost_committed_reservation_reply_replays_same_reservation(repositories, monkeypatch):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    operation = uuid4()
    original = r["usage"].reserve

    def lost(*args):
        original(*args)
        raise UnknownCommit("injected reply loss after real reservation commit")

    with monkeypatch.context() as patch:
        patch.setattr(r["usage"], "reserve", lost)
        with pytest.raises(UnknownCommit):
            service.accept(r["authority"], operation, prepared(r))
    reservation = r["usage"].reservation(r["authority"], operation)
    assert reservation["disposition"] == "reserved"
    job = service.accept(r["authority"], operation, prepared(r))
    assert job["reservation_id"] == reservation["id"]
    assert r["usage"].current(r["authority"])["counts"] == {"reserved": 1}


def test_lost_settlement_reply_leaves_obligation_then_reconciles_once(repositories, monkeypatch):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    job = service.accept(r["authority"], uuid4(), prepared(r))
    complete(r, job)
    original = r["usage"].settle

    def lost(*args, **kwargs):
        original(*args, **kwargs)
        raise UnknownCommit("injected lost settlement acknowledgement")

    with monkeypatch.context() as patch:
        patch.setattr(r["usage"], "settle", lost)
        with pytest.raises(UnknownCommit):
            service.settle_terminal(job["id"])
    assert any(row["id"] == job["id"] for row in r["pa"].unsettled())
    receipt = service.settle_terminal(job["id"])
    assert service.settle_terminal(job["id"]) == receipt
    assert all(row["id"] != job["id"] for row in r["pa"].unsettled())
    assert r["usage"].current(r["authority"])["counts"] == {"committed": 1}


def test_only_authoritative_rejection_releases_pre_acceptance_reservation(repositories):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    operation = uuid4()
    admission = r["pa"].prepare(r["authority"], operation, prepared(r))
    r["usage"].reserve(r["authority"], operation, admission["intent_hash"])
    with pytest.raises(ValueError, match="no durable rejected"):
        service.release_rejected(r["authority"], operation)
    r["pa"].reject_open(r["authority"], operation)
    released = service.release_rejected(r["authority"], operation)
    assert released["disposition"] == "released"
    assert service.release_rejected(r["authority"], operation) == released
    with pytest.raises(ValueError, match="rejected"):
        service.accept(r["authority"], operation, prepared(r))


def test_accepted_nonterminal_work_is_not_released_by_reconciliation(repositories):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    job = service.accept(r["authority"], uuid4(), prepared(r))
    with pytest.raises(ValueError):
        service.release_rejected(r["authority"], job["id"])
    with pytest.raises(ValueError, match="no durable terminal"):
        service.settle_terminal(job["id"])
    assert r["usage"].reservation(r["authority"], job["id"])["disposition"] == "reserved"


def test_existing_terminal_obligation_settles_after_account_revocation(repositories, connect):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    job = service.accept(r["authority"], uuid4(), prepared(r))
    complete(r, job)
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET active=false WHERE id=%s", (r["ids"]["a"],))
    assert service.settle_terminal(job["id"])["disposition"] == "committed"
    assert all(row["id"] != job["id"] for row in r["pa"].unsettled())


def test_four_committed_work_items_exhaust_explicit_no_reset_quota(repositories):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    for _ in range(4):
        job = service.accept(r["authority"], uuid4(), prepared(r))
        complete(r, job)
        service.settle_terminal(job["id"])
    operation = uuid4()
    with pytest.raises(ValueError, match="quota exhausted"):
        service.accept(r["authority"], operation, prepared(r))
    assert r["usage"].reservation(r["authority"], operation) is None
    assert r["usage"].current(r["authority"])["counts"] == {"committed": 4}
    assert r["pa"].prepare(r["authority"], operation, prepared(r))["disposition"] == "rejected"


def age_open(connect, operation):
    # Explicit fixture clock adjustment; production sweep uses owner DB time.
    with connect("assistance") as conn:
        conn.execute(
            "UPDATE assistance.admission SET created_at=clock_timestamp()-interval '6 minutes' "
            "WHERE operation_id=%s",
            (operation,),
        )


def drain_prior_rejections(service):
    for _ in range(100):
        if service.reconcile_admissions() == 0:
            return
    raise AssertionError("diagnostic rejection backlog exceeds bounded fixture allocation")


def test_reserved_open_reconciles_after_revocation_and_lost_tombstone_reply(
    repositories, connect, monkeypatch
):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    drain_prior_rejections(service)
    operation = uuid4()
    admission = r["pa"].prepare(r["authority"], operation, prepared(r))
    r["usage"].reserve(r["authority"], operation, admission["intent_hash"])
    age_open(connect, operation)
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET active=false WHERE id=%s", (r["ids"]["a"],))
    original = r["usage"].reject_operation

    def lost(proof):
        original(proof)
        raise UnknownCommit("injected lost tombstone acknowledgement")

    with monkeypatch.context() as patch:
        patch.setattr(r["usage"], "reject_operation", lost)
        with pytest.raises(UnknownCommit):
            service.reconcile_admissions()
    assert service.reconcile_admissions() == 1
    assert service.reconcile_admissions() == 0
    with connect("usage") as conn:
        assert (
            conn.execute(
                "SELECT disposition FROM usage.reservation WHERE operation_id=%s", (operation,)
            ).fetchone()[0]
            == "released"
        )


def test_tombstone_before_late_reserve_fences_creation_and_preserves_accepted(
    repositories, connect
):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    drain_prior_rejections(service)
    accepted = service.accept(r["authority"], uuid4(), prepared(r))
    operation = uuid4()
    admission = r["pa"].prepare(r["authority"], operation, prepared(r))
    assert service.reconcile_admissions() == 0  # Fresh open is not abandoned.
    age_open(connect, operation)
    assert service.reconcile_admissions() == 1
    with pytest.raises(ValueError, match="rejected"):
        r["usage"].reserve(r["authority"], operation, admission["intent_hash"])
    assert r["usage"].reservation(r["authority"], operation) is None
    assert r["usage"].reservation(r["authority"], accepted["id"])["disposition"] == "reserved"
    assert r["pa"].prepare(r["authority"], accepted["id"], prepared(r))["disposition"] == "accepted"


def test_explicit_rejection_without_reservation_fences_late_reserve(repositories):
    r = repositories
    service = AssistanceAdmission(r["pa"], r["usage"])
    operation = uuid4()
    admission = r["pa"].prepare(r["authority"], operation, prepared(r))
    r["pa"].reject_open(r["authority"], operation)
    assert service.release_rejected(r["authority"], operation) is None
    assert service.release_rejected(r["authority"], operation) is None
    with pytest.raises(ValueError, match="rejected"):
        r["usage"].reserve(r["authority"], operation, admission["intent_hash"])


@pytest.mark.parametrize("reserve_first", [True, False])
def test_concurrent_reservation_and_tombstone_serialize(
    repositories, connect, monkeypatch, reserve_first
):
    r = repositories
    operation = uuid4()
    admission = r["pa"].prepare(r["authority"], operation, prepared(r))
    locked, resume = Event(), Event()
    second_entered = Event()
    pids = {}
    original = r["tx"].run
    prefix = (
        "SELECT * FROM usage.entitlement" if reserve_first else "SELECT 1 FROM usage.entitlement"
    )

    class PausedConnection:
        """Inject a pause after real owner lock acquisition, not a fake DB result."""

        def __init__(self, connection):
            self.connection = connection

        def execute(self, query, params=None, **kwargs):
            if "FROM usage.entitlement" in query and "FOR UPDATE" in query:
                name = "first" if query.startswith(prefix) else "second"
                pids[name] = self.connection.execute("SELECT pg_backend_pid() AS pid").fetchone()[
                    "pid"
                ]
                if name == "second":
                    second_entered.set()
            result = self.connection.execute(query, params, **kwargs)
            if query.startswith(prefix) and not locked.is_set():
                locked.set()
                assert resume.wait(5), "test lock barrier timed out"
            return result

    def paused(owner, action):
        return original(owner, lambda conn: action(PausedConnection(conn)))

    monkeypatch.setattr(r["tx"], "run", paused)

    def reserve():
        return r["usage"].reserve(r["authority"], operation, admission["intent_hash"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        try:
            if reserve_first:
                first = executor.submit(reserve)
                assert locked.wait(3)
                r["pa"].reject_open(r["authority"], operation)
                proof = r["pa"].rejected_admission_proof(r["authority"], operation)
                second = executor.submit(r["usage"].reject_operation, proof)
            else:
                r["pa"].reject_open(r["authority"], operation)
                proof = r["pa"].rejected_admission_proof(r["authority"], operation)
                first = executor.submit(r["usage"].reject_operation, proof)
                assert locked.wait(3)
                second = executor.submit(reserve)
            assert second_entered.wait(2)
            assert pids["first"] != pids["second"]
            with connect("assistance") as observer:
                until = time.monotonic() + 2
                while True:
                    blockers = observer.execute(
                        "SELECT pg_blocking_pids(%s)", (pids["second"],)
                    ).fetchone()[0]
                    if pids["first"] in blockers:
                        break
                    assert time.monotonic() < until, "second real connection never blocked on first"
                    time.sleep(0.01)
        finally:
            resume.set()
        first.result(timeout=10)
        if reserve_first:
            second.result(timeout=10)
            assert r["usage"].reservation(r["authority"], operation)["disposition"] == "released"
        else:
            with pytest.raises(ValueError, match="rejected"):
                second.result(timeout=10)
            assert r["usage"].reservation(r["authority"], operation) is None


def test_tombstone_runtime_grants_are_append_only_and_owner_scoped(repositories, connect):
    r = repositories
    operation = uuid4()
    r["pa"].prepare(r["authority"], operation, prepared(r))
    r["pa"].reject_open(r["authority"], operation)
    AssistanceAdmission(r["pa"], r["usage"]).release_rejected(r["authority"], operation)
    with connect("usage") as conn:
        assert (
            conn.execute(
                "SELECT operation_id FROM usage.rejected_operation WHERE operation_id=%s",
                (operation,),
            ).fetchone()[0]
            == operation
        )
    for query in (
        "UPDATE usage.rejected_operation SET proof_hash=proof_hash WHERE operation_id=%s",
        "DELETE FROM usage.rejected_operation WHERE operation_id=%s",
        "DELETE FROM assistance.admission WHERE operation_id=%s",
    ):
        with pytest.raises(InsufficientPrivilege):
            with connect("usage") as conn:
                conn.execute(query, (operation,))
