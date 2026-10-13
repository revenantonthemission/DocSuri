"""Real bounded restart, restore, replacement and mixed-load evidence.

Runs against the owned journey realm and its persistent disposable volume:
container replacement, a coherent backup/restore round trip, worker replacement
with a stale closed fence, one result/accounting effect, a controlled injected
defect with owner recovery, and mixed load under the finite process gates.
Unexecuted cases (host/VM restart, optional-telemetry outage, remote defect
repair) are recorded in the code-generation evidence, not simulated here.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import psycopg
import pytest

from backend.artifacts import PrivateArtifacts
from backend.local_profile import LocalProfile
from backend.modules.corpus.repository import CorpusRepository, content_revision
from backend.modules.plans.guarded_repository import GuardedUsageRepository
from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.execution import ExecutionClaims
from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
from backend.modules.summarization.local_catalog import catalog_for
from backend.modules.summarization.local_result import encode_result
from backend.modules.summarization.payload import ExecutionPayloads
from backend.modules.summarization.requests import PROCESSING_POLICY, AssistanceRequests
from backend.transactions import Authority, OwnerTransactions

pytestmark = pytest.mark.u1_operations

ROOT = Path(__file__).resolve().parents[3]
PYTHON = ROOT / "backend/.venv/bin/python"
SUPERVISOR = ROOT / "scripts/supervise_docsuri_u1.py"
P1 = "1706.03762v7"
VERSIONS = {"1706.03762": "1706.03762v7", "2005.11401": "2005.11401v4"}
OPS_DOMAIN = "@ops.fixture.example.com"
PROCESSING = PROCESSING_POLICY


@pytest.fixture(scope="module")
def journey():
    manifest = Path(os.environ["DOCSURI_U1_ENVIRONMENT_FILE"])
    profile = LocalProfile.load(manifest).journey()
    credentials = json.loads((profile.root / "owner-credentials.json").read_text())
    return manifest, profile, credentials


@pytest.fixture(scope="module")
def connect(journey):
    _, profile, credentials = journey
    opened = []

    def connection(owner):
        conn = psycopg.connect(
            host="127.0.0.1",
            port=profile.database_port,
            dbname=profile.database_name,
            user=f"docsuri_{owner}",
            password=credentials["roles"][owner],
            connect_timeout=3,
        )
        conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        conn.commit()
        conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
        opened.append(conn)
        return conn

    yield connection
    for conn in opened:
        conn.close()


@pytest.fixture
def transactions(journey):
    _, profile, _ = journey
    value = OwnerTransactions(profile, process="maintenance")
    yield value
    value.close()


@pytest.fixture(scope="module")
def operator(journey):
    manifest, profile, _ = journey
    identity = uuid4().hex
    account = uuid5(UUID(int=0), identity)
    revision = uuid4()
    with psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="docsuri_accounts",
        password=json.loads((profile.root / "owner-credentials.json").read_text())["roles"][
            "accounts"
        ],
        connect_timeout=3,
    ) as conn:
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
            "authority_revision,display_name) VALUES(%s,%s,'ops-fixture-not-a-login',true,"
            "true,%s,'ops') ON CONFLICT(id) DO NOTHING",
            (account, identity + OPS_DOMAIN, revision),
        )
        for purpose in ("local-research", "personalization"):
            conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,%s,true) "
                "ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true",
                (account, purpose),
            )
        session = uuid4()
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
            "authority_revision,expires_at) VALUES(%s,%s,'ops-session','ops-csrf',%s,"
            "clock_timestamp()+interval '2 hours')",
            (session, account, revision),
        )
        conn.commit()
    yield Authority(account, session)
    with psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="docsuri_accounts",
        password=json.loads((profile.root / "owner-credentials.json").read_text())["roles"][
            "accounts"
        ],
        connect_timeout=3,
    ) as conn:
        for statement, parameter in (
            (
                "DELETE FROM assistance.event WHERE job_id IN (SELECT id FROM assistance.job WHERE account_id=%s)",
                account,
            ),
            ("DELETE FROM assistance.result WHERE account_id=%s", account),
            ("DELETE FROM assistance.job WHERE account_id=%s", account),
            ("DELETE FROM assistance.admission WHERE account_id=%s", account),
            ("DELETE FROM assistance.glossary WHERE account_id=%s", account),
        ):
            with psycopg.connect(
                host="127.0.0.1",
                port=profile.database_port,
                dbname=profile.database_name,
                user="docsuri_assistance",
                password=json.loads((profile.root / "owner-credentials.json").read_text())["roles"][
                    "assistance"
                ],
                connect_timeout=3,
            ) as owner_conn:
                owner_conn.execute(statement, (parameter,))
                owner_conn.commit()
        for statement in (
            "DELETE FROM usage.reservation WHERE account_id=%s",
            "DELETE FROM usage.entitlement WHERE account_id=%s",
        ):
            with psycopg.connect(
                host="127.0.0.1",
                port=profile.database_port,
                dbname=profile.database_name,
                user="docsuri_usage",
                password=json.loads((profile.root / "owner-credentials.json").read_text())["roles"][
                    "usage"
                ],
                connect_timeout=3,
            ) as owner_conn:
                owner_conn.execute(statement, (account,))
                owner_conn.commit()
        for statement in (
            "DELETE FROM library.saved_paper WHERE account_id=%s",
            "DELETE FROM library.history WHERE account_id=%s",
            "DELETE FROM library.history_boundary WHERE account_id=%s",
        ):
            with psycopg.connect(
                host="127.0.0.1",
                port=profile.database_port,
                dbname=profile.database_name,
                user="docsuri_library",
                password=json.loads((profile.root / "owner-credentials.json").read_text())["roles"][
                    "library"
                ],
                connect_timeout=3,
            ) as owner_conn:
                owner_conn.execute(statement, (account,))
                owner_conn.commit()
        conn.execute("DELETE FROM accounts.session WHERE account_id=%s", (account,))
        conn.execute("DELETE FROM accounts.consent WHERE account_id=%s", (account,))
        conn.execute("DELETE FROM accounts.account WHERE id=%s", (account,))
        conn.commit()


def supervise(journey, *arguments: str, timeout: int = 240) -> dict:
    manifest, _, _ = journey
    result = subprocess.run(
        [str(PYTHON), str(SUPERVISOR), *arguments, "--environment-file", str(manifest)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def save_paper(transactions, authority, paper_id: str) -> dict:
    """Idempotent owner-side save used to establish acknowledged state."""
    from backend.modules.library.repository.guarded import GuardedLibraryRepository

    repository = GuardedLibraryRepository(transactions)
    for row in repository.list_saved(authority, limit=20):
        if row["paper_id"] == paper_id:
            return {"paperId": paper_id}
    return repository.save(authority, paper_id, VERSIONS[paper_id], uuid4(), None)


def test_container_replacement_preserves_acknowledged_state(journey, transactions, operator):
    """A durable volume survives a real container restart."""
    saved = save_paper(transactions, operator, "1706.03762")
    assert saved["paperId"] == "1706.03762"
    report = supervise(journey, "restart-container")
    assert report["state"] == "running"
    # A real replacement: the container's start time changed.
    assert report["startedAt"] and report["startedAt"] != report["replacedFrom"]
    from backend.modules.library.repository.guarded import GuardedLibraryRepository

    rows = GuardedLibraryRepository(transactions).list_saved(operator, limit=20)
    assert [row["paper_id"] for row in rows] == ["1706.03762"]


def test_backup_restore_round_trip_preserves_commitments_and_restrictions(
    journey, transactions, operator, connect
):
    """A coherent rollback returns acknowledged state; later effects are gone."""
    save_paper(transactions, operator, "1706.03762")
    name = f"ops-round-trip-{uuid4().hex[:8]}"
    evidence = supervise(journey, "backup", "--name", name)
    assert evidence["sha256"] and evidence["byteLength"] > 0
    late = save_paper(transactions, operator, "2005.11401")
    assert late["paperId"] == "2005.11401"
    # Release this process's idle connections before the realm is recreated.
    transactions.close()
    restored = supervise(journey, "restore", "--from", name)
    assert restored["sha256"] == evidence["sha256"]
    from backend.modules.library.repository.guarded import GuardedLibraryRepository

    reopened = OwnerTransactions(journey[1], process="maintenance")
    try:
        rows = GuardedLibraryRepository(reopened).list_saved(operator, limit=20)
        assert [row["paper_id"] for row in rows] == ["1706.03762"]
    finally:
        reopened.close()
    # Owner restrictions survive the restore: a foreign direct write is denied.
    with connect("library") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE corpus.paper SET withdrawn=true WHERE id='1706.03762'")
        conn.rollback()
    with connect("corpus") as conn:
        identity = conn.execute("SELECT run_id FROM public.docsuri_local_identity").fetchone()[0]
    assert identity == journey[1].run_id


def test_worker_replacement_rejects_stale_fence_with_one_effect(journey, transactions, operator):
    """Replacement fences late work and keeps exactly one result and accounting effect."""
    _, profile, _ = journey
    corpus = CorpusRepository(
        transactions, PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
    )
    source = corpus.read(P1)
    catalog = catalog_for(source, quality_ready=True)
    assert catalog is not None
    option = catalog.options()["options"][0]
    glossary = transactions.run(
        "assistance",
        lambda conn: conn.execute(
            "SELECT * FROM assistance.read_glossary(%s)", (operator.account_id,)
        ).fetchone(),
    )
    request = {
        "paper": catalog.paper,
        "contentRevision": content_revision(source),
        "contentHash": source["source_hash"],
        "operation": option["operation"],
        "optionId": option["optionId"],
        "optionsRevision": catalog.revision,
        "glossaryRevision": glossary["revision"],
        "processingPolicy": PROCESSING,
    }
    assistance = GuardedAssistanceRepository(
        transactions, PrivateArtifacts(profile.root / "assistance-files")
    )
    usage = GuardedUsageRepository(transactions)
    admission = AssistanceAdmission(assistance, usage)
    usage.ensure_entitlement(operator)
    operation = uuid4()
    job = AssistanceRequests(admission, corpus, lambda _: catalog).submit(
        operator, operation, request
    )
    claims = ExecutionClaims(assistance)
    first = claims.acquire(claims.binding(job), uuid4())
    # The first worker's lease expires without publication (a replaced worker).
    with psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="docsuri_assistance",
        password=json.loads((profile.root / "owner-credentials.json").read_text())["roles"][
            "assistance"
        ],
        connect_timeout=3,
    ) as conn:
        conn.execute(
            "UPDATE assistance.job SET lease_expires_at=clock_timestamp()-interval '1 minute'"
            " WHERE id=%s",
            (operation,),
        )
        conn.commit()
    second_worker = uuid4()
    second = claims.acquire(
        claims.binding(job), second_worker, previous_fence=first["claim"]["fence"]
    )
    assert second["claim"]["fence"] > first["claim"]["fence"]
    payload = ExecutionPayloads(claims, corpus).read(second["claim"], trusted_worker=second_worker)
    cut = payload["sections"][0]
    content = encode_result(
        sections=[
            {
                "sectionId": cut["sectionId"],
                "heading": cut["heading"],
                "text": cut["text"],
                "anchor": cut["anchor"],
            }
        ],
        citations=[cut["anchor"]],
        definitions=[],
    )
    proposal = claims.proposal(
        second["claim"],
        input_hash=job["input_hash"],
        expected_job_revision=second["jobRevision"],
    )
    receipt = assistance.complete(
        proposal,
        uuid5(operation, "ops-worker-replacement"),
        content,
        coverage={"coverage": "partial", "scope": "selected-sections"},
        provenance={"executor": "ops-fixture"},
    )
    # The replaced worker cannot publish against the closed fence.
    stale = claims.proposal(
        first["claim"],
        input_hash=job["input_hash"],
        expected_job_revision=first["jobRevision"],
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        assistance.fail(stale, uuid5(operation, "ops-stale"), "insufficient-result")
    admission.settle_terminal(operation)
    snapshot = assistance.snapshot(operator, operation)
    assert snapshot["state"] == "succeeded"
    reservation = usage.reservation(operator, operation)
    assert reservation["disposition"] == "committed"
    with psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="docsuri_assistance",
        password=json.loads((profile.root / "owner-credentials.json").read_text())["roles"][
            "assistance"
        ],
        connect_timeout=3,
    ) as conn:
        results = conn.execute(
            "SELECT count(*) FROM assistance.result WHERE job_id=%s", (operation,)
        ).fetchone()[0]
    assert results == 1
    assert receipt["resultId"]


def test_controlled_repair_of_a_stuck_acceptance(journey, transactions, operator):
    """An injected stuck acceptance is diagnosed and repaired by owner recovery."""
    _, profile, _ = journey
    corpus = CorpusRepository(
        transactions, PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
    )
    source = corpus.read(P1)
    catalog = catalog_for(source, quality_ready=True)
    option = catalog.options()["options"][0]
    glossary = transactions.run(
        "assistance",
        lambda conn: conn.execute(
            "SELECT * FROM assistance.read_glossary(%s)", (operator.account_id,)
        ).fetchone(),
    )
    assistance = GuardedAssistanceRepository(
        transactions, PrivateArtifacts(profile.root / "assistance-files")
    )
    usage = GuardedUsageRepository(transactions)
    admission = AssistanceAdmission(assistance, usage)
    usage.ensure_entitlement(operator)
    operation = uuid4()
    job = AssistanceRequests(admission, corpus, lambda _: catalog).submit(
        operator,
        operation,
        {
            "paper": catalog.paper,
            "contentRevision": content_revision(source),
            "contentHash": source["source_hash"],
            "operation": option["operation"],
            "optionId": option["optionId"],
            "optionsRevision": catalog.revision,
            "glossaryRevision": glossary["revision"],
            "processingPolicy": PROCESSING,
        },
    )
    assert job["state"] == "accepted"
    # Controlled defect: the accepting authority is revoked after admission, so
    # no worker may execute the accepted operation any more.
    _, profile, credentials = journey
    with psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="docsuri_accounts",
        password=credentials["roles"]["accounts"],
        connect_timeout=3,
    ) as conn:
        original = conn.execute(
            "SELECT authority_revision FROM accounts.account WHERE id=%s",
            (operator.account_id,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE accounts.account SET authority_revision=gen_random_uuid() WHERE id=%s",
            (operator.account_id,),
        )
        conn.commit()
    try:
        recovered = assistance.recover_unexecutable(limit=4)
        assert operation in recovered
    finally:
        with psycopg.connect(
            host="127.0.0.1",
            port=profile.database_port,
            dbname=profile.database_name,
            user="docsuri_accounts",
            password=credentials["roles"]["accounts"],
            connect_timeout=3,
        ) as conn:
            conn.execute(
                "UPDATE accounts.account SET authority_revision=%s WHERE id=%s",
                (original, operator.account_id),
            )
            conn.commit()
    snapshot = assistance.snapshot(operator, operation)
    assert snapshot["state"] == "failed"
    assert snapshot["failure_code"] == "execution-authority-revoked"
    admission.settle_terminal(operation)
    reservation = usage.reservation(operator, operation)
    assert reservation["disposition"] == "released"


def test_mixed_load_stays_within_finite_process_allocation(journey, operator):
    """Concurrent real reads complete under the finite api-process gate."""
    _, profile, _ = journey
    corpora = OwnerTransactions(profile, process="api")
    started = time.monotonic()
    try:
        corpus = CorpusRepository(
            corpora, PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
        )
        from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository

        discovery = GuardedDiscoveryRepository(corpora)

        def search(_: int) -> int:
            return len(discovery.candidates(None))

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(search, range(8)))
        elapsed = time.monotonic() - started
        assert all(count >= 2 for count in results)
        sections = len(corpus.read(P1)["content"]["document"]["sections"])
    finally:
        corpora.close()
    # The finite api-process gate serializes at most four owner transactions;
    # every task completed and no allocation error surfaced.
    assert elapsed < 60, f"mixed load exceeded the bounded window: {elapsed:.1f}s"
    evidence = {
        "tasks": 8,
        "workers": 4,
        "elapsedSeconds": round(elapsed, 3),
        "sectionCount": sections,
        "recordedAt": time.time(),
    }
    target = journey[1].root / "operations-mixed-load.json"
    target.write_text(json.dumps(evidence))
    os.chmod(target, 0o600)
    assert evidence["elapsedSeconds"] < 60
