"""Paper assistance's owner path in the complete realm (U8 plan Step 24; the person's
decisions of 2026-10-23, "U2's controls in the complete app" and "U2's controls for all
usage").

In the composed realm a paper assistance request runs PaperAssistance's own repository
and the usage owner's U2 controls under the realm's policy, through the owners' logins:

1. a prepared admission carries the realm's period and policy, a repeat returns it, and
   another input under the same operation is refused;
2. an accepted job is claimed, renewed, completed once (a repeated completion fact
   replays its outcome, a different one is refused) and read back by its owner only;
3. the completed job settles its reservation as committed through the usage owner,
   and the settlement replays but never changes;
4. a failed job releases its reservation, and the failure fact replays;
5. a rejected preparation is never accepted and is reconciled with nothing to release;
6. the owner repository's bounds refuse out-of-range reads;
7. the complete host's history page holds at most 50 rows, read with their metadata in
   one assistance transaction (Step 87(b), L1-8).

This file runs first in its integration part: PaperAssistance admits at most four open
or running items realm-wide, and later files leave open admissions behind.
"""

from __future__ import annotations

import datetime as dt
import json
import secrets
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from backend.artifacts import PrivateArtifacts
from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
from backend.modules.plans.guarded_repository import GuardedUsageRepository
from backend.modules.plans.u8_usage import ImportedUsage
from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration.conftest import _make_account
from tests.u8_service_operations_integration.host_flows import (
    assert_bounded_runs,
    complete_host,
    counted_post,
    member,
)

POLICY = U8_SYNTHETIC_POLICY.reference
CONTENT = json.dumps({"summary": "합성 요약", "sections": ["intro"]}).encode()


@pytest.fixture
def owner(connect, realm):
    """An account of this file's own, with no usage left from an earlier run, then the
    realm's grant through the usage owner's own operation."""
    authority = _make_account(connect, realm, suffix="assistance-owner")
    with rf.admin(realm, realm.database_name) as conn, conn.transaction():
        for table in ("rejected_operation", "reservation", "entitlement"):
            conn.execute(f"DELETE FROM usage.{table} WHERE account_id=%s",
                         (authority.account_id,))
    return authority


ADMISSION_PLACES = 4


@pytest.fixture
def parts(transactions, realm, owner, connect):
    with connect("assistance") as conn:
        held = conn.execute(
            "SELECT count(*) AS n FROM assistance.admission WHERE disposition='open' OR "
            "operation_id IN (SELECT id FROM assistance.job WHERE state IN "
            "('accepted','running'))").fetchone()["n"]
    if held >= ADMISSION_PLACES:
        pytest.fail("PaperAssistance's admission places are held by an earlier run's rows; "
                    "this file needs a fresh realm")
    usage = ImportedUsage(transactions, U8_SYNTHETIC_POLICY)
    assert usage.grant_imported(owner.account_id, source="realm_fixture")["disposition"] == (
        "imported")
    repository = GuardedAssistanceRepository(
        transactions, PrivateArtifacts.for_profile(realm, "assistance-files"))
    return repository, AssistanceAdmission(repository, GuardedUsageRepository(transactions))


@pytest.fixture
def version(connect, realm):
    """An eligible synthetic paper version written through the corpus owner's login."""
    token = secrets.token_hex(4)
    identifier = f"u8ca-{token}-v1"
    with connect("corpus") as conn:
        conn.execute("INSERT INTO corpus.paper(id,title,authors,metadata) "
                     "VALUES(%s,'Synthetic','[\"A\"]','{}')", (identifier + "-paper",))
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
            "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,"
            "'https://example.invalid/p',%s,'v1','synthetic',true,'local-research','{}','{}')",
            (identifier, identifier + "-paper", secrets.token_hex(32)))
    return identifier


def bound_input(version: str) -> dict:
    return {"versionId": version, "sourceHash": secrets.token_hex(32), "action": "summary"}


def accepted_job(admission: AssistanceAdmission, owner, version: str):
    operation, payload = uuid4(), bound_input(version)
    job = admission.accept(owner, operation, payload)
    assert job["id"] == operation and job["state"] == "accepted"
    return operation, job, payload


def test_a_prepared_admission_carries_the_realms_period_and_policy(parts, owner, version):
    repository, _admission = parts
    operation, payload = uuid4(), bound_input(version)
    prepared = repository.prepare(owner, operation, payload)
    assert prepared["disposition"] == "open"
    assert prepared["policy_ref"] == POLICY and prepared["period_id"].startswith("u2-period:")
    # A repeat returns the same admission; another input under the operation is refused.
    assert repository.prepare(owner, operation, payload)["revision"] == prepared["revision"]
    with pytest.raises(ValueError, match="operation identity conflict"):
        repository.prepare(owner, operation, bound_input(version))
    # A replay of a request it never held is refused; an unknown operation has none.
    request = {"paper": {"versionId": version}}
    with pytest.raises(ValueError, match="operation identity conflict"):
        repository.replay_request(owner, operation, request)
    assert repository.replay_request(owner, uuid4(), request) is None
    # Closed again, so it holds no admission place for the files after this one.
    assert repository.reject_open(owner, operation)["disposition"] == "rejected"


def test_an_accepted_job_completes_once_and_its_owner_reads_it_back(
        parts, owner, authority_b, version):
    repository, admission = parts
    operation, job, payload = accepted_job(admission, owner, version)
    # Acceptance is idempotent for the same input and reservation.
    assert admission.accept(owner, operation, payload)["id"] == operation
    with pytest.raises(ValueError, match="accepted work cannot be rejected"):
        repository.reject_open(owner, operation)
    assert all(len(row) == 1 for row in repository.pending())
    claim = repository.claim(operation, uuid4())
    assert claim["state"] == "running" and claim["fence"] == 1
    renewed = repository.renew(claim)
    assert renewed["lease_revision"] != claim["lease_revision"]
    assert repository.payload(renewed)["versionId"] == version
    fact = uuid4()
    outcome = repository.complete(renewed, fact, CONTENT, {"sections": 1}, {"model": "synthetic"})
    assert outcome["jobId"] == str(operation)
    # The same fact replays its outcome; a different submission under it is refused.
    assert repository.complete(renewed, fact, CONTENT, {"sections": 1},
                               {"model": "synthetic"}) == outcome
    with pytest.raises(ValueError, match="completion fact conflict"):
        repository.complete(renewed, fact, CONTENT, {"sections": 2}, {"model": "synthetic"})
    # The owner reads it back.
    snapshot = repository.snapshot(owner, operation)
    assert snapshot["state"] == "succeeded" and snapshot["settlement_pending"]
    assert repository.disposition_snapshot(owner, operation)["state"] == "succeeded"
    reference = repository.result_reference(owner, operation)
    assert reference["resultId"] == outcome["resultId"]
    assert reference["contentHash"] == outcome["outputHash"]
    assert repository.result(owner, reference["resultId"]) == CONTENT
    assert repository.result_metadata(owner, operation)["availability"] == "retained"
    source = repository.source_metadata(owner, version)
    assert (source["versionId"], source["title"]) == (version, "Synthetic")
    history = repository.history(owner, limit=5)
    assert history[0]["id"] == operation and history[0]["result"]["id"]
    assert repository.current_glossary(owner)["revision"] == job["glossary_revision"]
    events = repository.events(owner, operation, 0)
    assert [row["sequence"] for row in events] == sorted(row["sequence"] for row in events)
    # Another owner never reads it.
    with pytest.raises(PermissionError):
        repository.snapshot(authority_b, operation)
    with pytest.raises(PermissionError):
        repository.disposition_snapshot(authority_b, operation)
    with pytest.raises(PermissionError):
        repository.events(authority_b, operation, 0)
    with pytest.raises(PermissionError):
        repository.result(authority_b, reference["resultId"])
    assert repository.result_reference(authority_b, operation) is None
    assert repository.result_metadata(authority_b, operation) is None
    settle(repository, admission, operation, "committed")


def settle(repository, admission, operation, disposition: str) -> None:
    """The terminal job settles its reservation through the usage owner once."""
    pending = repository.unsettled(4)
    assert len(pending) <= 4 and all(
        set(row) == {"id", "account_id", "reservation_id", "state"} for row in pending)
    proof = repository.settlement_proof(operation)
    assert proof["disposition"] == disposition and len(proof["proofHash"]) == 64
    receipt = admission.settle_terminal(operation)
    assert receipt["disposition"] == disposition
    # The settlement replays; a receipt bound to anything else is refused.
    assert admission.settle_terminal(operation) == receipt
    with pytest.raises(ValueError, match="settlement receipt"):
        repository.confirm_settlement(operation, {**receipt, "disposition": "other"})
    with pytest.raises(ValueError, match="settlement receipt conflict"):
        repository.confirm_settlement(operation, {**receipt, "settlementId": str(uuid4())})


def test_a_failed_job_releases_its_reservation_and_the_failure_replays(
        parts, owner, version):
    repository, admission = parts
    operation, _job, _payload = accepted_job(admission, owner, version)
    with pytest.raises(ValueError, match="no durable terminal proof"):
        repository.settlement_proof(operation)
    claim = repository.claim(operation, uuid4())
    with pytest.raises(ValueError, match="unsupported safe failure code"):
        repository.fail(claim, uuid4(), "anything")
    fact = uuid4()
    failed = repository.fail(claim, fact, "dependency-unavailable")
    assert failed == {"jobId": str(operation), "state": "failed",
                      "reason": "dependency-unavailable"}
    assert repository.fail(claim, fact, "dependency-unavailable") == failed
    with pytest.raises(ValueError, match="failure fact conflict"):
        repository.fail(claim, fact, "invalid-source")
    assert repository.result_reference(owner, operation) is None
    settle(repository, admission, operation, "released")


def test_a_rejected_preparation_is_never_accepted_and_reconciles_with_nothing_to_release(
        parts, owner, version):
    repository, admission = parts
    operation, payload = uuid4(), bound_input(version)
    repository.prepare(owner, operation, payload)
    with pytest.raises(ValueError, match="no durable rejected admission proof"):
        repository.rejected_admission_proof(owner, operation)
    assert repository.reject_open(owner, operation)["disposition"] == "rejected"
    with pytest.raises(ValueError, match="original admission was rejected"):
        admission.accept(owner, operation, payload)
    proof = repository.rejected_admission_proof(owner, operation)
    assert proof["operationId"] == str(operation) and len(proof["proofHash"]) == 64
    # No reservation was ever made for it, so nothing is released; the reconciliation
    # is recorded once and repeats without change.
    assert admission.release_rejected(owner, operation) is None
    assert admission.release_rejected(owner, operation) is None
    with pytest.raises(ValueError, match="rejection acknowledgement binding mismatch"):
        repository.confirm_rejection({**proof, "intentHash": "0" * 64})
    with pytest.raises(PermissionError, match="admission unavailable"):
        repository.reject_open(owner, uuid4())
    with pytest.raises(PermissionError, match="admission unavailable"):
        repository.accept(owner, uuid4(), uuid4())


HISTORY = "/api/v2/c06/read-assistance-history"


def failed_jobs(connect, account_id, version: str, count: int) -> list:
    """`count` terminal (failed) jobs of the account, written through the assistance
    owner's login as `host_flows.make_jobs` writes research jobs: each accepted later
    than any earlier job of the account, each with the six fields U3's history read takes
    in `payload.acceptedInput`. Being terminal, they hold no admission place."""
    base = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=5)
    jobs = []
    with connect("assistance") as conn:
        for index in range(count):
            job, content, reservation = uuid4(), secrets.token_hex(32), uuid4()
            accepted = {"contentRevision": f"content-{index}", "contentHash": content,
                        "operation": "summary", "optionId": "summary.default",
                        "optionsRevision": "options-1", "glossaryRevision": "glossary-0"}
            intent = {"versionId": version, "sourceHash": content, "action": "summary"}
            conn.execute(
                "INSERT INTO assistance.admission(operation_id,account_id,intent_hash,intent,"
                "disposition,reservation_id) VALUES(%s,%s,%s,%s,'accepted',%s)",
                (job, account_id, secrets.token_hex(32), Jsonb(intent), reservation))
            conn.execute(
                "INSERT INTO assistance.job(id,account_id,authority_revision,version_id,"
                "source_hash,input_hash,payload,glossary_revision,glossary_snapshot,"
                "reservation_id,accepted_at,state,phase,failure_code,dispatch_pending) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,'glossary-0','[]',%s,%s,'failed','failed',"
                "'dependency-unavailable',false)",
                (job, account_id, uuid4(), version, content, secrets.token_hex(32),
                 Jsonb({**intent, "acceptedInput": accepted}), reservation,
                 base + dt.timedelta(milliseconds=10 * index)))
            jobs.append(job)
    return jobs


def remove_jobs(realm, jobs) -> None:
    """The test's own jobs removed again, so no later file counts them."""
    with rf.admin(realm, realm.database_name) as conn, conn.transaction():
        for table, column in (("event", "job_id"), ("job", "id"), ("admission", "operation_id")):
            conn.execute(f"DELETE FROM assistance.{table} WHERE {column} = ANY(%s)",
                         (list(jobs),))


def test_the_assistance_history_reads_its_page_in_bounded_transactions(
        realm, own_address, sign_in_account, connect, version):
    """Step 87(b) (L1-8): in the complete realm the history's page of 50 is one
    `accounts` run (the session) and one `assistance` run (the rows with their metadata),
    both on the recovery pools, because the route is a recovery route; 51 answers 422
    before any assistance run."""
    jobs: list = []
    try:
        with complete_host(realm, address=own_address) as host:
            authority, _ = member(host, sign_in_account)
            jobs = failed_jobs(connect, authority.account_id, version, 51)
            paper = {"paperId": version + "-paper", "versionId": version,
                     "eligibilityRevision": "1"}
            answer, runs = counted_post(host, HISTORY, {"paper": paper, "page": {"limit": 50}})
            assert answer.status_code == 200, answer.text
            items = answer.json()["items"]
            assert [item["jobId"] for item in items] == [str(job) for job in reversed(jobs)][:50]
            assert {item["availability"] for item in items} == {"failed"}
            assert runs == {("recovery", "accounts"): 1, ("recovery", "assistance"): 1}, runs
            assert_bounded_runs(host.composition, ("accounts", "assistance"), recovery=True)
            refused, runs = counted_post(host, HISTORY,
                                         {"paper": paper, "page": {"limit": 51}})
            assert (refused.status_code, refused.json()["code"]) == (422, "INVALID_ARGUMENT")
            assert not any(owner == "assistance" for _, owner in runs), runs
    finally:
        if jobs:
            remove_jobs(realm, jobs)


def test_the_owner_repositorys_bounds_refuse_out_of_range_reads(parts, owner):
    repository, _admission = parts
    for call in (lambda: repository.pending(0), lambda: repository.pending(5),
                 lambda: repository.unsettled(0), lambda: repository.history(owner, limit=0),
                 lambda: repository.history(owner, limit=101),
                 lambda: repository.events(owner, uuid4(), -1),
                 lambda: repository.recover_unexecutable(0),
                 lambda: repository.reject_abandoned(limit=5)):
        with pytest.raises(ValueError):
            call()
    with pytest.raises(PermissionError, match="job unavailable"):
        repository.snapshot(owner, uuid4())
    with pytest.raises(PermissionError, match="result unavailable"):
        repository.result(owner, uuid4())
    with pytest.raises(ValueError, match="settlement receipt binding mismatch"):
        repository.confirm_settlement(uuid4(), {})
