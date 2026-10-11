from uuid import uuid4
from datetime import datetime, timedelta

import pytest
from psycopg.errors import InsufficientPrivilege
from psycopg.types.json import Jsonb

from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.execution import ExecutionClaims

pytestmark = pytest.mark.u1_repository


def accepted(r):
    service = AssistanceAdmission(r["pa"], r["usage"])
    payload = {
        "versionId": r["ids"]["version"],
        "sourceHash": "a" * 64,
        "action": "summary",
        "fixtureFamily": "repository-boundary",
    }
    return service, service.accept(r["authority"], uuid4(), payload)


def inspect(connect, identifier):
    with connect("assistance") as conn:
        return conn.execute(
            "SELECT state,failure_code,settlement_pending,accepted_at,revision "
            "FROM assistance.job WHERE id=%s",
            (identifier,),
        ).fetchone()


def test_live_claim_remains_unchanged_by_owner_recovery(repositories, connect):
    r = repositories
    service, job = accepted(r)
    claim = r["pa"].claim(job["id"], uuid4())
    before = inspect(connect, job["id"])
    service.recover_execution()
    assert inspect(connect, job["id"]) == before
    assert r["pa"].payload(claim) == job["payload"]
    assert r["usage"].reservation(r["authority"], job["id"])["disposition"] == "reserved"


@pytest.mark.parametrize("reason", ["execution-deadline-exceeded", "execution-attempts-exhausted"])
def test_expired_owner_transition_proves_failure_before_one_release(repositories, connect, reason):
    r = repositories
    service, job = accepted(r)
    claim = r["pa"].claim(job["id"], uuid4())
    with connect("assistance") as conn:
        # Explicit owned-fixture clock/fence injection, not a production time override.
        if reason == "execution-deadline-exceeded":
            conn.execute(
                "UPDATE assistance.job SET started_at=clock_timestamp()-interval '91 seconds',"
                "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (job["id"],),
            )
        else:
            conn.execute(
                "UPDATE assistance.job SET fence=3,lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (job["id"],),
            )
    with pytest.raises(InsufficientPrivilege):
        r["pa"].payload(claim)
    receipts = service.recover_execution()
    assert any(
        x["operationId"] == str(job["id"]) and x["disposition"] == "released" for x in receipts
    )
    row = inspect(connect, job["id"])
    assert row[:3] == ("failed", reason, False)
    assert row[3] == job["accepted_at"]
    service.recover_execution()
    assert inspect(connect, job["id"]) == row


@pytest.mark.parametrize("owner", ["accounts", "corpus"])
def test_current_revocation_can_finalize_without_a_live_worker_privilege(
    repositories, connect, owner
):
    r = repositories
    service, job = accepted(r)
    claim = r["pa"].claim(job["id"], uuid4())
    with connect(owner) as conn:
        if owner == "accounts":
            conn.execute("UPDATE accounts.account SET active=false WHERE id=%s", (r["ids"]["a"],))
        else:
            conn.execute(
                "UPDATE corpus.version SET eligible=false WHERE id=%s", (r["ids"]["version"],)
            )
    with pytest.raises(InsufficientPrivilege):
        r["pa"].payload(claim)
    service.recover_execution()
    assert inspect(connect, job["id"])[:3] == ("failed", "execution-authority-revoked", False)
    with connect("usage") as conn:
        assert (
            conn.execute(
                "SELECT disposition FROM usage.reservation WHERE operation_id=%s", (job["id"],)
            ).fetchone()[0]
            == "released"
        )


def test_expired_lease_alone_preserves_replacement_opportunity(repositories, connect):
    r = repositories
    service, job = accepted(r)
    claims = ExecutionClaims(r["pa"])
    first = claims.acquire(claims.binding(job), uuid4())
    with connect("assistance") as conn:
        conn.execute(
            "UPDATE assistance.job SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (job["id"],),
        )
    service.recover_execution()
    assert inspect(connect, job["id"])[0] == "running"
    second = claims.acquire(claims.binding(job), uuid4(), previous_fence=first["claim"]["fence"])
    assert second["claim"]["fence"] == 2


def queued_fixture(r, connect, age_seconds):
    operation = uuid4()
    payload = {
        "versionId": r["ids"]["version"],
        "sourceHash": "a" * 64,
        "fixtureFamily": "repository-boundary",
    }
    admission = r["pa"].prepare(r["authority"], operation, payload)
    reservation = r["usage"].reserve(r["authority"], operation, admission["intent_hash"])
    with connect("assistance") as conn:
        conn.execute(
            "INSERT INTO assistance.job(id,account_id,authority_revision,version_id,source_hash,"
            "input_hash,payload,glossary_revision,glossary_snapshot,reservation_id,accepted_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,'empty-fixture','{}',%s,clock_timestamp()-%s*interval '1 second')",
            (
                operation,
                r["ids"]["a"],
                r["ids"]["revision"],
                r["ids"]["version"],
                "a" * 64,
                admission["intent_hash"],
                Jsonb(payload),
                reservation["id"],
                age_seconds,
            ),
        )
        conn.execute(
            "UPDATE assistance.admission SET disposition='accepted',reservation_id=%s WHERE operation_id=%s",
            (reservation["id"], operation),
        )
    return r["pa"].snapshot(r["authority"], operation)


def test_old_queued_fixture_gets_visible_terminal_proof_not_silent_release(repositories, connect):
    r = repositories
    operation = queued_fixture(r, connect, 360)["id"]
    assert operation in r["pa"].recover_unexecutable()
    assert inspect(connect, operation)[:3] == ("failed", "job-recovery-window-expired", True)
    assert r["usage"].reservation(r["authority"], operation)["disposition"] == "reserved"
    AssistanceAdmission(r["pa"], r["usage"]).settle_terminal(operation)
    assert r["usage"].reservation(r["authority"], operation)["disposition"] == "released"


def test_late_start_and_renew_cannot_exceed_absolute_recovery_window(repositories, connect):
    r = repositories
    job = queued_fixture(r, connect, 290)
    claims = ExecutionClaims(r["pa"])
    acquired = claims.acquire(claims.binding(job), uuid4())
    deadline = job["accepted_at"] + timedelta(seconds=300)
    assert datetime.fromisoformat(acquired["claim"]["expiresAt"]) <= deadline
    remaining = claims.read_input(acquired["claim"])["remainingSeconds"]
    assert 0 < remaining <= 10
    renewed = claims.renew(
        acquired["claim"], expected_lease_revision=acquired["claim"]["leaseRevision"]
    )
    assert datetime.fromisoformat(renewed["claim"]["expiresAt"]) <= deadline
    assert job["id"] not in r["pa"].recover_unexecutable()
