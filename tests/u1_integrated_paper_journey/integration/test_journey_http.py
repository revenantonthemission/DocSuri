"""Mounted canonical paper journey over the real published corpus and owner stores.

Two synthetic accounts cover the whole module; each test signs in afresh.
Test-only readiness injection creates the assistance job used to exercise the
owner-bound read/stream paths; the mounted accept route itself is asserted to
refuse new work truthfully while the reviewed-readiness marker is absent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from backend.artifacts import Artifact, PrivateArtifacts
from backend.local_host import assemble_journey
from backend.local_profile import LocalProfile
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
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

pytestmark = pytest.mark.u1_integration
ORIGIN = "https://127.0.0.1:18039"
PASSWORD = "JourneyFixture!28-A"
DOMAIN = "@journey.fixture.example.com"
DEMO_NAMESPACE = "@fixture.invalid"
ENTRY_POLICY = {"policyId": "synthetic-local-entry", "revision": "1"}
SEARCH_POLICY = {"policyId": "synthetic-paper-search", "revision": "1"}
LIBRARY_POLICY = {"policyId": "synthetic-local-library", "revision": "1"}
SETTINGS_POLICY = {"policyId": "synthetic-personal-settings", "revision": "1"}
VOCABULARY = "synthetic-paper-options-1"
P1 = "1706.03762v7"


def connect(journey, owner):
    profile, credentials = journey

    def connection():
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
        return conn

    return connection


@pytest.fixture(scope="module")
def journey():
    profile = LocalProfile.load(Path(os.environ["DOCSURI_U1_ENVIRONMENT_FILE"])).journey()
    credentials = json.loads((profile.root / "owner-credentials.json").read_text())
    assert credentials["runId"] == profile.run_id
    return profile, credentials


@pytest.fixture(scope="module")
def journey_tx(journey):
    transactions = OwnerTransactions(journey[0], process="maintenance")
    yield transactions
    transactions.close()


@pytest.fixture(scope="module", autouse=True)
def retire_fixture_accounts(journey):
    """Repeatable synthetic identities; unknown active accounts refuse the phase.

    Only this module's own namespace is deleted. The established journey demo
    account keeps its rows: it is temporarily deactivated to free the finite
    two-account allocation and reactivated after the module.
    """
    with connect(journey, "accounts")() as conn:
        conn.execute(
            "UPDATE accounts.account SET active=true WHERE NOT active AND email LIKE %s "
            "AND email NOT LIKE %s",
            ("%" + DEMO_NAMESPACE, "%" + DOMAIN),
        )
        # The finite attempt ledger is test-owned diagnostic state, reset between runs.
        conn.execute("DELETE FROM accounts.entry_budget")
        rows = conn.execute("SELECT id,email,active FROM accounts.account").fetchall()
    mine = [identifier for identifier, email, _ in rows if email.endswith(DOMAIN)]
    active_other = [
        (identifier, email)
        for identifier, email, active in rows
        if active and not email.endswith(DOMAIN)
    ]
    assert all(email.endswith(DEMO_NAMESPACE) for _, email in active_other), (
        "unknown ordinary account in journey realm; refuse fixture transition"
    )
    demo = [identifier for identifier, _ in active_other]
    if mine:
        _delete_accounts(journey, mine)
    if demo:
        with connect(journey, "accounts")() as conn:
            conn.execute("UPDATE accounts.account SET active=false WHERE id = ANY(%s)", (demo,))
    yield
    # Remove only this run's own accounts; the demo account keeps every row.
    with connect(journey, "accounts")() as conn:
        created = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM accounts.account WHERE email LIKE %s", ("%" + DOMAIN,)
            ).fetchall()
        ]
    if created:
        _delete_accounts(journey, created)
    if demo:
        with connect(journey, "accounts")() as conn:
            conn.execute("UPDATE accounts.account SET active=true WHERE id = ANY(%s)", (demo,))


def _delete_accounts(journey, accounts):
    with connect(journey, "assistance")() as conn:
        conn.execute(
            "DELETE FROM assistance.event WHERE job_id IN (SELECT id FROM assistance.job "
            "WHERE account_id = ANY(%s))",
            (accounts,),
        )
        conn.execute("DELETE FROM assistance.result WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM assistance.job WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM assistance.admission WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM assistance.glossary WHERE account_id = ANY(%s)", (accounts,))
    with connect(journey, "usage")() as conn:
        conn.execute("DELETE FROM usage.reservation WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM usage.entitlement WHERE account_id = ANY(%s)", (accounts,))
    with connect(journey, "library")() as conn:
        conn.execute("DELETE FROM library.saved_paper WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM library.saved_query WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM library.history WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM library.history_boundary WHERE account_id = ANY(%s)", (accounts,))
    with connect(journey, "personalization")() as conn:
        conn.execute("DELETE FROM personalization.settings WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM personalization.behavior WHERE account_id = ANY(%s)", (accounts,))
    with connect(journey, "discovery")() as conn:
        conn.execute("DELETE FROM discovery.execution WHERE account_id = ANY(%s)", (accounts,))
    with connect(journey, "accounts")() as conn:
        conn.execute(
            "DELETE FROM accounts.delivery WHERE challenge_id IN (SELECT id FROM "
            "accounts.challenge WHERE account_id = ANY(%s))",
            (accounts,),
        )
        conn.execute("DELETE FROM accounts.challenge WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM accounts.session WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM accounts.consent WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM accounts.lifecycle WHERE account_id = ANY(%s)", (accounts,))
        conn.execute("DELETE FROM accounts.account WHERE id = ANY(%s)", (accounts,))


@pytest.fixture(scope="module")
def client(journey):
    app = assemble_journey(journey[0])
    with TestClient(app, base_url=ORIGIN) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def entry(journey):
    transactions = OwnerTransactions(journey[0], process="maintenance")
    service = GuardedEntryService(transactions)
    yield service
    transactions.close()


def read_mail(entry, journey, email):
    with connect(journey, "accounts")() as conn:
        row = conn.execute(
            "SELECT c.id,d.private_path,d.content_hash,d.byte_length FROM accounts.challenge c "
            "JOIN accounts.account a ON a.id=c.account_id JOIN accounts.delivery d ON "
            "d.challenge_id=c.id WHERE a.email=%s AND NOT c.consumed",
            (email,),
        ).fetchone()
    return json.loads(entry.mail.read(Artifact(row[1], row[2], row[3])))


def boot(client):
    response = client.get("/api/v2/session")
    assert response.status_code == 200
    return response.json()


def new_browser(client):
    """Cleared cookie jar + fresh bootstrap is an actual new browser context."""
    client.cookies.clear()
    return boot(client)


def post_headers(client, *, operation=None, csrf=None):
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": csrf or boot(client)["csrfToken"],
        "Idempotency-Key": str(operation or uuid4()),
    }


def register(client, entry, journey, email):
    response = client.post(
        "/api/v2/c02/access-register",
        headers=post_headers(client),
        json={
            "email": email,
            "password": PASSWORD,
            "displayName": "연구자",
            "policyRef": ENTRY_POLICY,
        },
    )
    assert response.status_code == 200, response.text
    mail = read_mail(entry, journey, email)
    response = client.post(
        "/api/v2/c02/access-verify-email",
        headers=post_headers(client),
        json={"verification": {key: mail[key] for key in ("challengeId", "proof", "flowBinding")}},
    )
    assert response.status_code == 200, response.text


def login(client, email):
    response = client.post(
        "/api/v2/c02/access-login",
        headers=post_headers(client),
        json={"email": email, "password": PASSWORD, "policyRef": ENTRY_POLICY},
    )
    assert response.status_code == 200, response.text
    assert boot(client)["signedIn"] is True


@pytest.fixture(scope="module")
def account_a(client, entry, journey):
    email = uuid4().hex + DOMAIN
    register(client, entry, journey, email)
    return email


@pytest.fixture(scope="module")
def account_b(client, entry, journey):
    """One registered second owner for isolation checks in this module."""
    email = uuid4().hex + DOMAIN
    new_browser(client)
    register(client, entry, journey, email)
    return email


def session_identity(client):
    response = client.post(
        "/api/v2/c02/access-inspect-session", headers=post_headers(client), json={}
    )
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    return UUID(session["accountId"]), UUID(session["sessionId"])


def search_body(query: str):
    return {
        "query": {
            "query": query,
            "modeId": "lexical",
            "orderId": "relevance",
            "filters": [],
            "vocabularyRevision": VOCABULARY,
            "policyRef": SEARCH_POLICY,
        },
        "page": {"limit": 10},
    }


def run_search(client, query: str, *, expect=200):
    response = client.post(
        "/api/v2/c05/search", headers=post_headers(client), json=search_body(query)
    )
    assert response.status_code == expect, response.text
    return response


def test_journey_search_read_save_revisit_settings_and_usage(client, account_a):
    login(client, account_a)
    account_id, _ = session_identity(client)
    response = run_search(client, "transformer attention")
    hits = response.json()["hits"]
    assert hits[0]["paper"]["paperId"] == "1706.03762"
    assert [hit["paper"]["paperId"] for hit in hits] == ["1706.03762", "2005.11401"]
    paper = hits[0]["paper"]

    content = client.post(
        "/api/v2/c04/read-content",
        headers=post_headers(client),
        json={"paper": paper, "purpose": "read"},
    )
    assert content.status_code == 200, content.text
    body = content.json()
    assert body["availability"] == "ready"
    reading = body["content"]
    assert reading["paper"]["versionId"] == P1
    assert any("softmax" in section["text"] for section in reading["sections"])

    saved = client.post(
        "/api/v2/c03/library-save-paper",
        headers=post_headers(client),
        json={"paper": paper, "policyRef": LIBRARY_POLICY},
    )
    assert saved.status_code == 200, saved.text
    record = saved.json()
    assert record["savedTitle"] == "Attention Is All You Need"
    assert record["sourceDisposition"] == "available"

    settings = client.post(
        "/api/v2/c03/settings-read", headers=post_headers(client), json={}
    ).json()
    updated = client.post(
        "/api/v2/c03/settings-update",
        headers=post_headers(client),
        json={
            "appearance": "dark",
            "policyRef": SETTINGS_POLICY,
            "expectedRevision": settings["revision"],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["appearance"] == "dark"

    usage = client.post(
        "/api/v2/c03/usage-inspect", headers=post_headers(client), json={"page": {}}
    )
    assert usage.status_code == 200, usage.text
    measure = usage.json()["items"][0]
    assert measure["state"] == "known" and measure["allocated"] == 4
    assert measure["used"] == 0 and measure["reserved"] == 0

    # Fresh authenticated return discovers the acknowledged save and the recorded
    # search through owned lists, without relying on volatile URLs.
    new_browser(client)
    login(client, account_a)
    saved_list = client.post(
        "/api/v2/c03/library-list-saved-papers",
        headers=post_headers(client),
        json={"page": {"limit": 20}},
    )
    assert saved_list.status_code == 200, saved_list.text
    items = saved_list.json()["items"]
    assert [item["savedTitle"] for item in items] == ["Attention Is All You Need"]
    assert items[0]["accountId"] == str(account_id)
    history = client.post(
        "/api/v2/c03/library-list-history",
        headers=post_headers(client),
        json={"page": {"limit": 20}},
    )
    assert history.status_code == 200, history.text
    queries = [row["queryContext"]["query"] for row in history.json()["items"]]
    assert "transformer attention" in queries
    settings = client.post(
        "/api/v2/c03/settings-read", headers=post_headers(client), json={}
    ).json()
    assert settings["appearance"] == "dark"


def test_guest_search_and_owner_history_clear(client, entry, journey, account_a):
    new_browser(client)
    guest = client
    response = guest.post(
        "/api/v2/c05/search",
        headers=post_headers(guest),
        json=search_body("retrieval augmented generation"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["hits"][0]["paper"]["paperId"] == "2005.11401"
    assert response.json()["limitations"] == []
    history = guest.post(
        "/api/v2/c03/library-list-history", headers=post_headers(guest), json={"page": {}}
    )
    assert history.status_code == 401
    login(client, account_a)
    run_search(client, "retrieval augmented generation")
    listed = client.post(
        "/api/v2/c03/library-list-history", headers=post_headers(client), json={"page": {}}
    ).json()
    assert listed["clearBoundary"]
    queries = [row["queryContext"]["query"] for row in listed["items"]]
    assert "retrieval augmented generation" in queries
    cleared = client.post(
        "/api/v2/c03/library-clear-history",
        headers=post_headers(client),
        json={"policyRef": LIBRARY_POLICY, "expectedRevision": listed["clearBoundary"]},
    )
    assert cleared.status_code == 200, cleared.text
    body = cleared.json()
    assert body["checkpoint"]["admissionSequence"] >= 1
    after = client.post(
        "/api/v2/c03/library-list-history", headers=post_headers(client), json={"page": {}}
    ).json()
    assert after["items"] == []
    del entry, journey


def test_precondition_dispositions_and_policy_refusals(client, account_a):
    login(client, account_a)
    body = search_body("transformer")
    body["snapshotRevision"] = str(uuid4())
    stale = client.post("/api/v2/c05/search", headers=post_headers(client), json=body)
    assert stale.status_code == 410 and stale.json()["code"] == "SNAPSHOT_EXPIRED"
    unknown = client.post(
        "/api/v2/c04/resolve-paper",
        headers=post_headers(client),
        json={"identifier": "no-such-paper"},
    )
    assert unknown.status_code == 404
    read_unknown = client.post(
        "/api/v2/c04/read-content",
        headers=post_headers(client),
        json={
            "paper": {
                "paperId": "no-such-paper",
                "versionId": "no-such-version",
                "eligibilityRevision": str(uuid4()),
            },
            "purpose": "read",
        },
    )
    assert read_unknown.status_code == 404
    wrong_policy = client.post(
        "/api/v2/c03/library-save-paper",
        headers=post_headers(client),
        json={
            "paper": {
                "paperId": "1706.03762",
                "versionId": P1,
                "eligibilityRevision": str(uuid4()),
            },
            "policyRef": {"policyId": "paid", "revision": "1"},
        },
    )
    assert wrong_policy.status_code == 503
    assert wrong_policy.json()["code"] == "POLICY_UNRESOLVED"
    settings = client.post(
        "/api/v2/c03/settings-read", headers=post_headers(client), json={}
    ).json()
    client.post(
        "/api/v2/c03/settings-update",
        headers=post_headers(client),
        json={
            "appearance": "dark",
            "policyRef": SETTINGS_POLICY,
            "expectedRevision": settings["revision"],
        },
    )
    stale_update = client.post(
        "/api/v2/c03/settings-update",
        headers=post_headers(client),
        json={
            "appearance": "light",
            "policyRef": SETTINGS_POLICY,
            "expectedRevision": settings["revision"],
        },
    )
    assert stale_update.status_code == 409
    # Onboarding transitions use the same control revision and the retained
    # manual vocabulary; unsupported interests are refused before any effect.
    current = client.post("/api/v2/c03/settings-read", headers=post_headers(client), json={}).json()
    assert current["onboarding"] == "not_started" and current["interestIds"] == []
    saved = client.post(
        "/api/v2/c03/settings-update-onboarding",
        headers=post_headers(client),
        json={
            "action": "save_interests",
            "interestIds": ["1706.03762"],
            "policyRef": SETTINGS_POLICY,
            "expectedRevision": current["revision"],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["onboarding"] == "in_progress"
    assert saved.json()["interestIds"] == ["1706.03762"]
    unsupported = client.post(
        "/api/v2/c03/settings-update-onboarding",
        headers=post_headers(client),
        json={
            "action": "save_interests",
            "interestIds": ["not-retained"],
            "policyRef": SETTINGS_POLICY,
            "expectedRevision": saved.json()["revision"],
        },
    )
    assert unsupported.status_code == 422
    completed = client.post(
        "/api/v2/c03/settings-update-onboarding",
        headers=post_headers(client),
        json={
            "action": "complete",
            "interestIds": ["1706.03762"],
            "policyRef": SETTINGS_POLICY,
            "expectedRevision": saved.json()["revision"],
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["onboarding"] == "completed"
    stale_onboarding = client.post(
        "/api/v2/c03/settings-update-onboarding",
        headers=post_headers(client),
        json={
            "action": "skip",
            "interestIds": [],
            "policyRef": SETTINGS_POLICY,
            "expectedRevision": saved.json()["revision"],
        },
    )
    assert stale_onboarding.status_code == 409


def test_assistance_options_truthful_unavailability_and_accept_refusal(client, account_a):
    login(client, account_a)
    paper = {
        "paperId": "1706.03762",
        "versionId": P1,
        "eligibilityRevision": str(uuid4()),
    }
    options = client.post(
        "/api/v2/c06/read-assistance-options",
        headers=post_headers(client),
        json={"paper": paper},
    )
    assert options.status_code == 200, options.text
    body = options.json()
    assert body["options"] == [] and len(body["limitations"]) == 2
    accepted = client.post(
        "/api/v2/c06/accept-assistance",
        headers=post_headers(client),
        json={
            "paper": paper,
            "contentRevision": "1",
            "contentHash": "a" * 64,
            "operation": "summary",
            "optionId": "key-sections-summary",
            "optionsRevision": body["revision"],
            "glossaryRevision": "1",
            "processingPolicy": PROCESSING_POLICY,
        },
    )
    assert accepted.status_code == 503 and accepted.json()["code"] == "NOT_READY"


def test_owner_bound_job_snapshot_result_and_events(
    client, journey, journey_tx, account_a, account_b
):
    login(client, account_a)
    account_id, session_id = session_identity(client)
    authority = Authority(account_id, session_id)
    profile, _ = journey
    corpus = CorpusRepository(
        journey_tx, PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
    )
    source = corpus.read(P1)
    # Test-only readiness injection exercises the transport bindings; the mounted
    # accept route stays truthfully refused while the readiness marker is absent.
    catalog = catalog_for(source, quality_ready=True)
    assert catalog is not None
    option = catalog.options()["options"][0]
    # The mounted read-glossary binding supplies the acceptance token; the
    # repository re-validates it against the current glossary at acceptance.
    glossary = client.post("/api/v2/c06/read-glossary", headers=post_headers(client), json={})
    assert glossary.status_code == 200, glossary.text
    request = {
        "paper": catalog.paper,
        "contentRevision": content_revision(source),
        "contentHash": source["source_hash"],
        "operation": option["operation"],
        "optionId": option["optionId"],
        "optionsRevision": catalog.revision,
        "glossaryRevision": glossary.json()["revision"],
        "processingPolicy": PROCESSING_POLICY,
    }
    pa = GuardedAssistanceRepository(
        journey_tx, PrivateArtifacts(profile.root / "assistance-files")
    )
    usage = GuardedUsageRepository(journey_tx)
    admission = AssistanceAdmission(pa, usage)
    operation, worker = uuid4(), uuid4()
    job = AssistanceRequests(admission, corpus, lambda _: catalog).submit(
        authority, operation, request
    )
    claims = ExecutionClaims(pa)
    acquired = claims.acquire(claims.binding(job), worker)
    payload = ExecutionPayloads(claims, corpus).read(acquired["claim"], trusted_worker=worker)
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
        acquired["claim"],
        input_hash=job["input_hash"],
        expected_job_revision=acquired["jobRevision"],
    )
    receipt = pa.complete(
        proposal,
        uuid5(operation, "mounted-journey-completion"),
        content,
        coverage={"coverage": "partial", "scope": "selected-sections"},
        provenance={"executor": "mounted-journey-fixture"},
    )
    admission.settle_terminal(operation)
    assert receipt["resultId"]

    snapshot = client.get(f"/api/v2/jobs/{operation}")
    assert snapshot.status_code == 200, snapshot.text
    body = snapshot.json()
    assert body["state"] == "succeeded" and body["ownerId"] == str(account_id)
    assert body["result"]["resultId"] == receipt["resultId"]

    prepared = client.get(f"/api/v2/jobs/{operation}/result")
    assert prepared.status_code == 200, prepared.text
    read = prepared.json()
    assert read["availability"] == "ready"
    assert read["prepared"]["sections"][0]["text"] == cut["text"]
    assert read["prepared"]["coverage"] == "partial"

    history = client.post(
        "/api/v2/c06/read-assistance-history",
        headers=post_headers(client),
        json={"paper": catalog.paper, "page": {"limit": 10}},
    )
    assert history.status_code == 200, history.text
    row = next(item for item in history.json()["items"] if item["jobId"] == str(operation))
    assert row["availability"] == "ready" and row["result"]["resultId"] == receipt["resultId"]

    events = client.get(f"/api/v2/jobs/{operation}/events", headers={"Last-Event-ID": "0"})
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    raw = b"".join(events.iter_bytes())
    frames = [chunk for chunk in raw.split(b"\n\n") if chunk]
    assert frames, "terminal replay returned no frames"
    sequences = []
    final = None
    for frame in frames:
        lines = frame.decode().split("\n")
        header = dict(line.split(": ", 1) for line in lines if ": " in line)
        assert header["event"] in ("progress", "snapshot", "error")
        if header["event"] != "error":
            sequences.append(int(header["id"]))
        payload = json.loads(header["data"])
        assert payload["jobId"] == str(operation)
        if header["event"] == "snapshot":
            final = payload
    assert sequences == sorted(sequences), "frames must carry monotonic owner sequences"
    assert final is not None and final["state"] == "succeeded"
    assert final["seq"] == body["seq"]

    # Owner B cannot read, stream or replay A's retained work; A's access above
    # remains the authorized positive control.
    new_browser(client)
    login(client, account_b)
    assert client.get(f"/api/v2/jobs/{operation}").status_code == 404
    assert (
        client.get(f"/api/v2/jobs/{operation}/events", headers={"Last-Event-ID": "0"}).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v2/c06/read-prepared-assistance",
            headers=post_headers(client),
            json={"jobId": str(operation)},
        ).status_code
        == 404
    )
    denied_history = client.post(
        "/api/v2/c06/read-assistance-history",
        headers=post_headers(client),
        json={"paper": catalog.paper, "page": {"limit": 10}},
    )
    assert denied_history.status_code == 200
    assert denied_history.json()["items"] == []
    # Reads create no new work and no debit.
    assert usage.reservation(authority, operation)["disposition"] == "committed"
    assert pa.snapshot(authority, operation)["state"] == "succeeded"


def test_read_glossary_owner_bound_token_and_isolation(client, journey, account_a, account_b):
    """The current owner's glossary token is readable and captured at acceptance."""
    login(client, account_a)
    account_id, _ = session_identity(client)
    empty = client.post("/api/v2/c06/read-glossary", headers=post_headers(client), json={})
    assert empty.status_code == 200, empty.text
    body = empty.json()
    assert body["ownerId"] == str(account_id)
    assert body["revision"].startswith("empty:")
    assert body["terms"] == []
    assert body["normalizationPolicy"] == {"policyId": "local-glossary", "revision": "1"}
    empty_revision = body["revision"]

    terms = [
        {
            "termId": "term-attention",
            "source": "attention",
            "preferred": "어텐션",
            "languageId": "ko",
        }
    ]
    with connect(journey, "assistance")() as conn:
        conn.execute(
            "INSERT INTO assistance.glossary(account_id,revision,snapshot) VALUES(%s,%s,%s) "
            "ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,"
            "snapshot=excluded.snapshot",
            (account_id, "stored:journey-v1", Jsonb(terms)),
        )
    try:
        stored = client.post("/api/v2/c06/read-glossary", headers=post_headers(client), json={})
        assert stored.status_code == 200, stored.text
        assert stored.json()["revision"] == "stored:journey-v1"
        assert stored.json()["terms"] == terms

        # Owner B sees only its own empty token, never A's stored terms.
        new_browser(client)
        login(client, account_b)
        other = client.post("/api/v2/c06/read-glossary", headers=post_headers(client), json={})
        assert other.status_code == 200, other.text
        assert other.json()["revision"].startswith("empty:")
        assert other.json()["revision"] != "stored:journey-v1"
        assert other.json()["revision"] != empty_revision
        assert other.json()["terms"] == []
    finally:
        with connect(journey, "assistance")() as conn:
            conn.execute(
                "DELETE FROM assistance.glossary WHERE account_id=%s AND revision=%s",
                (account_id, "stored:journey-v1"),
            )


def create_job(client, journey, journey_tx, account_a, *, complete=True):
    """Create one real assistance job through the repository path (test fixture).

    The mounted accept route truthfully refuses while the reviewed-readiness
    marker is absent; this helper exercises the transport bindings against a
    real admitted, claimed and (optionally) completed owner job.
    """
    login(client, account_a)
    account_id, session_id = session_identity(client)
    authority = Authority(account_id, session_id)
    profile, _ = journey
    corpus = CorpusRepository(
        journey_tx, PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
    )
    source = corpus.read(P1)
    catalog = catalog_for(source, quality_ready=True)
    assert catalog is not None
    option = catalog.options()["options"][0]
    glossary = journey_tx.run(
        "assistance",
        lambda conn: conn.execute(
            "SELECT * FROM assistance.read_glossary(%s)", (account_id,)
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
        "processingPolicy": PROCESSING_POLICY,
    }
    pa = GuardedAssistanceRepository(
        journey_tx, PrivateArtifacts(profile.root / "assistance-files")
    )
    usage = GuardedUsageRepository(journey_tx)
    admission = AssistanceAdmission(pa, usage)
    operation, worker = uuid4(), uuid4()
    job = AssistanceRequests(admission, corpus, lambda _: catalog).submit(
        authority, operation, request
    )
    claims = ExecutionClaims(pa)
    if not complete:
        return {
            "operation": operation,
            "worker": worker,
            "job": job,
            "authority": authority,
            "corpus": corpus,
            "catalog": catalog,
            "pa": pa,
            "usage": usage,
            "claims": claims,
        }
    acquired = claims.acquire(claims.binding(job), worker)
    payload = ExecutionPayloads(claims, corpus).read(acquired["claim"], trusted_worker=worker)
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
        acquired["claim"],
        input_hash=job["input_hash"],
        expected_job_revision=acquired["jobRevision"],
    )
    receipt = pa.complete(
        proposal,
        uuid5(operation, "mounted-journey-completion"),
        content,
        coverage={"coverage": "partial", "scope": "selected-sections"},
        provenance={"executor": "mounted-journey-fixture"},
    )
    admission.settle_terminal(operation)
    return {
        "operation": operation,
        "worker": worker,
        "job": job,
        "receipt": receipt,
        "authority": authority,
        "corpus": corpus,
        "catalog": catalog,
        "pa": pa,
        "usage": usage,
        "claims": claims,
        "payload": payload,
    }


def test_legacy_defect_q01_ordering_and_q04_frame_framing(
    client, entry, journey, journey_tx, account_a
):
    """Q-01/Q-04 regressions through the real U1 browser and stream bindings."""
    completed = create_job(client, journey, journey_tx, account_a)
    operation = completed["operation"]

    # Q-01: the mounted state carries the ordering field the browser needs and
    # recovery reads are monotonic.
    snapshot = client.get(f"/api/v2/jobs/{operation}")
    assert snapshot.status_code == 200, snapshot.text
    body = snapshot.json()
    assert type(body["seq"]) is int and body["seq"] >= completed["job"]["sequence"]
    posted = client.post(
        "/api/v2/c06/read-assistance-job",
        headers=post_headers(client),
        json={"jobId": str(operation)},
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["seq"] == body["seq"]
    again = client.get(f"/api/v2/jobs/{operation}").json()
    assert again["seq"] == body["seq"] and again["state"] == "succeeded"

    # Q-04: frames are real SSE records - no escaped-newline payloads - and a
    # reconnect resumes from the authoritative sequence without older events.
    events = client.get(f"/api/v2/jobs/{operation}/events", headers={"Last-Event-ID": "0"})
    assert events.status_code == 200
    raw = b"".join(events.iter_bytes())
    assert b"\\n" not in raw, "stream frame contains a literal escaped newline"
    frames = [chunk for chunk in raw.split(b"\n\n") if chunk]
    assert frames
    sequences, final = [], None
    for frame in frames:
        lines = frame.decode().split("\n")
        header = dict(line.split(": ", 1) for line in lines if ": " in line)
        assert header["event"] in ("progress", "snapshot", "error")
        if header["event"] != "error":
            sequences.append(int(header["id"]))
        payload = json.loads(header["data"])
        assert payload["jobId"] == str(operation)
        if header["event"] == "snapshot":
            final = payload
    assert sequences == sorted(sequences)
    assert final is not None and final["seq"] == body["seq"]
    resumed = b"".join(
        client.get(
            f"/api/v2/jobs/{operation}/events", headers={"Last-Event-ID": str(final["seq"])}
        ).iter_bytes()
    )
    resumed_sequences = [
        int(dict(line.split(": ", 1) for line in frame.decode().split("\n") if ": " in line)["id"])
        for frame in resumed.split(b"\n\n")
        if frame and b"id: " in frame
    ]
    assert all(sequence >= final["seq"] for sequence in resumed_sequences)


def test_legacy_defect_q02_result_semantics_q03_dispatch_recovery(
    client, entry, journey, journey_tx, account_a
):
    """Q-02/Q-03 regressions through the real U1 browser and worker bindings."""
    completed = create_job(client, journey, journey_tx, account_a)
    operation = completed["operation"]
    # Q-02: a retained success is usable through the browser result read.
    ready = client.get(f"/api/v2/jobs/{operation}/result")
    assert ready.status_code == 200, ready.text
    prepared = ready.json()
    assert prepared["availability"] == "ready"
    assert (
        prepared["prepared"]["sections"][0]["text"] == completed["payload"]["sections"][0]["text"]
    )
    assert prepared["prepared"]["coverage"] == "partial"

    # Q-03: acceptance is not a no-op enqueue - an unclaimed job stays
    # recoverable and is claimable with its payload readable through the real
    # claim/execution path.
    pending = create_job(client, journey, journey_tx, account_a, complete=False)
    pending_operation = pending["operation"]
    with connect(journey, "assistance")() as conn:
        row = conn.execute(
            "SELECT state,dispatch_pending,fence FROM assistance.job WHERE id=%s",
            (pending_operation,),
        ).fetchone()
    assert row == ("accepted", True, 0)
    acquired = pending["claims"].acquire(
        pending["claims"].binding(pending["job"]), pending["worker"]
    )
    payload = ExecutionPayloads(pending["claims"], pending["corpus"]).read(
        acquired["claim"], trusted_worker=pending["worker"]
    )
    assert payload["binding"]["operationId"] == str(pending_operation)
    assert payload["sections"], "dispatched payload carried no source sections"
    pending_read = client.get(f"/api/v2/jobs/{pending_operation}/result")
    assert pending_read.status_code == 200
    assert pending_read.json()["availability"] == "pending"

    # The claimed job fails with an explicit safe reason and reads distinguish
    # failed from pending; the terminal state never regresses.
    proposal = pending["claims"].proposal(
        acquired["claim"],
        input_hash=pending["job"]["input_hash"],
        expected_job_revision=acquired["jobRevision"],
    )
    pending["pa"].fail(proposal, uuid5(pending_operation, "mounted-failure"), "insufficient-result")
    failed = client.get(f"/api/v2/jobs/{pending_operation}/result")
    assert failed.status_code == 200
    assert failed.json()["availability"] == "failed"
    failed_snapshot = client.get(f"/api/v2/jobs/{pending_operation}").json()
    assert (
        failed_snapshot["state"] == "failed"
        and failed_snapshot["error"]["code"] == "INVALID_CONTENT"
    )

    # A retained result that expires stays distinguishable without rewriting the
    # historical terminal job state.
    with connect(journey, "assistance")() as conn:
        conn.execute(
            "UPDATE assistance.result SET availability='expired' WHERE job_id=%s",
            (operation,),
        )
    expired = client.get(f"/api/v2/jobs/{operation}/result")
    assert expired.status_code == 200
    assert expired.json()["availability"] == "expired"
    historical = client.get(f"/api/v2/jobs/{operation}").json()
    assert historical["state"] == "succeeded" and historical.get("result") is None
    # Reads create no new work: exactly the two jobs created here exist.
    with connect(journey, "assistance")() as conn:
        count = conn.execute(
            "SELECT count(*) FROM assistance.job WHERE id = ANY(%s)",
            ([operation, pending_operation],),
        ).fetchone()[0]
    assert count == 2


def test_capabilities_and_readiness_truthfulness(client, journey):
    catalog = client.get("/api/v2/capabilities")
    assert catalog.status_code == 200
    capabilities = {item["id"]: item for item in catalog.json()["capabilities"]}
    assert capabilities["discovery.search"]["modeIds"] == ["lexical"]
    assert capabilities["assistance.summary"]["state"] == "policy_pending"
    assert capabilities["assistance.summary"]["modeIds"] == []
    readiness = client.get("/health/ready")
    assert readiness.status_code == 200, readiness.text
    body = readiness.json()
    assert body["ready"] is True and body["missing"] == []
    # Readiness derives from one recorded observation per installed owner, and
    # each observation carries bounded counts only - no content or credentials.
    assert {row["capability"] for row in body["observations"]} == {
        "accounts",
        "corpus",
        "discovery",
        "library",
        "personalization",
        "usage",
        "assistance",
        "operations",
    }
    for row in body["observations"]:
        assert row["status"] == "available", row
        assert row["observedAt"] and row["expiresAt"]
        assert isinstance(row["evidence"], dict) and row["evidence"]
        assert all(isinstance(value, int) for value in row["evidence"].values())
    # A stale observation is re-probed within the same bounded call and the
    # refreshed result is recorded again; readiness never passes stale evidence.
    with connect(journey, "operations")() as conn:
        conn.execute(
            "UPDATE operations.observation SET disposition='unavailable',"
            " expires_at=clock_timestamp()-interval '1 hour' WHERE capability='library'"
        )
    refreshed = client.get("/health/ready")
    assert refreshed.status_code == 200, refreshed.text
    library = next(
        row for row in refreshed.json()["observations"] if row["capability"] == "library"
    )
    assert library["status"] == "available" and library["expiresAt"]
    with connect(journey, "operations")() as conn:
        stored = conn.execute(
            "SELECT disposition,expires_at > clock_timestamp() AS fresh "
            "FROM operations.observation WHERE capability='library'"
        ).fetchone()
    assert stored == ("available", True)


def test_host_navigation_manifest_permissions_and_context(client, journey, journey_tx, account_a):
    """C01 returns only permitted navigation for the current principal."""
    new_browser(client)
    anonymous = client.post(
        "/api/v2/c01/host-resolve-navigation",
        headers=post_headers(client),
        json={"routeId": "search"},
    )
    assert anonymous.status_code == 200, anonymous.text
    body = anonymous.json()
    items = {item["routeId"]: item for item in body["items"]}
    assert set(items) == {"search", "paper", "library", "settings", "usage", "jobs", "account"}
    assert items["search"]["available"] is True and items["paper"]["available"] is True
    # Owner-bound destinations and pending capabilities stay visible but denied.
    assert items["library"]["available"] is False
    assert items["library"]["reasonKey"] == "nav.authenticationRequired"
    assert items["jobs"]["available"] is False
    assert items["jobs"]["reasonKey"] == "nav.capabilityPending"
    assert body["resolvedRouteId"] == "search"
    assert body["clearPriorOwnerState"] is True
    assert body["manifestRevision"] == client.get("/api/v2/capabilities").json()["revision"]
    anonymous_revision = body["authorityRevision"]
    unknown = client.post(
        "/api/v2/c01/host-resolve-navigation",
        headers=post_headers(client),
        json={"routeId": "not-a-route"},
    )
    assert unknown.status_code == 404
    malformed = client.post(
        "/api/v2/c01/host-resolve-navigation",
        headers=post_headers(client),
        json={"routeId": "paper", "returnContext": {"kind": "paper"}},
    )
    assert malformed.status_code == 422

    login(client, account_a)
    context = {
        "kind": "search",
        "queryContext": {
            "query": "transformer attention",
            "modeId": "lexical",
            "orderId": "relevance",
            "filters": [],
            "vocabularyRevision": VOCABULARY,
            "policyRef": SEARCH_POLICY,
        },
        "resultWindowId": str(uuid4()),
        "resultPosition": 1,
    }
    with connect(journey, "assistance")() as conn:
        before = conn.execute("SELECT count(*) AS n FROM assistance.job").fetchone()[0]
    signed_in = client.post(
        "/api/v2/c01/host-resolve-navigation",
        headers=post_headers(client),
        json={"routeId": "library", "returnContext": context},
    )
    assert signed_in.status_code == 200, signed_in.text
    signed = signed_in.json()
    signed_items = {item["routeId"]: item for item in signed["items"]}
    assert signed_items["library"]["available"] is True
    assert signed_items["settings"]["available"] is True
    assert signed_items["usage"]["available"] is True
    assert signed["clearPriorOwnerState"] is False
    assert signed["authorityRevision"] != anonymous_revision
    assert signed["returnContext"] == context
    assert signed["resolvedRouteId"] == "library"
    # Navigation is presentation only: no job, claim or accounting effect.
    with connect(journey, "assistance")() as conn:
        after = conn.execute("SELECT count(*) AS n FROM assistance.job").fetchone()[0]
    assert after == before
    del journey_tx


def test_corpus_asset_bounded_unavailability_and_denial(client, journey, journey_tx, account_a):
    """Figure captions read; asset bytes are bounded-absent for every caller."""
    new_browser(client)
    login(client, account_a)
    paper = {
        "paperId": "1706.03762",
        "versionId": P1,
        "eligibilityRevision": str(uuid4()),
    }
    content = client.post(
        "/api/v2/c04/read-content",
        headers=post_headers(client),
        json={"paper": paper, "purpose": "read"},
    )
    assert content.status_code == 200, content.text
    reading = content.json()["content"]
    assert any("그림" in note for note in reading["limitations"])
    profile, _ = journey
    corpus = CorpusRepository(
        journey_tx, PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
    )
    source = corpus.read(P1)
    figure_ids = [
        block["assetRef"]["assetId"]
        for section in source["content"]["document"]["sections"]
        for block in _all_blocks(section)
        if block.get("type") == "figure" and block.get("assetRef")
    ]
    assert figure_ids, "fixture exposes figure captions with asset references"
    asset_id = figure_ids[0]
    route = f"/api/v2/papers/1706.03762/versions/{P1}/assets/{asset_id}"
    signed = client.get(route)
    assert signed.status_code == 404 and signed.json()["code"] == "NOT_FOUND"
    assert (
        client.get(f"/api/v2/papers/1706.03762/versions/{P1}/assets/no-such-asset").status_code
        == 404
    )
    assert (
        client.get("/api/v2/papers/no-such-paper/versions/no-such/assets/no-such").status_code
        == 404
    )
    # An anonymous caller is refused before any corpus read; the same refusal
    # covers both known and unknown identifiers.
    new_browser(client)
    assert client.get(route).status_code == 401
    assert (
        client.get("/api/v2/papers/no-such-paper/versions/no-such/assets/no-such").status_code
        == 401
    )


def _all_blocks(section):
    yield from section.get("blocks", [])
    for child in section.get("sections", []) or []:
        yield from _all_blocks(child)


def test_search_bounds_relay_fault_and_library_read_paths(client, account_a, journey, monkeypatch):
    """Guest refusals, a deliberate history-relay fault and the library read paths."""
    # The finite attempt ledger is this suite's own diagnostic state, reset like
    # the module fixture does; the 20/minute policy itself stays untouched.
    with connect(journey, "accounts")() as conn:
        conn.execute("DELETE FROM accounts.entry_budget")
    new_browser(client)
    oversized = search_body("transformer")
    oversized["page"] = {"limit": 0}
    refused = client.post("/api/v2/c05/search", headers=post_headers(client), json=oversized)
    assert refused.status_code == 422
    stale = search_body("transformer")
    stale["snapshotRevision"] = str(uuid4())
    expired = client.post("/api/v2/c05/search", headers=post_headers(client), json=stale)
    assert expired.status_code == 410 and expired.json()["code"] == "SNAPSHOT_EXPIRED"
    semantic = search_body("transformer")
    semantic["query"]["modeId"] = "semantic"
    unavailable = client.post("/api/v2/c05/search", headers=post_headers(client), json=semantic)
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "DEPENDENCY_UNAVAILABLE"

    login(client, account_a)
    from backend.modules.library.repository.guarded import GuardedLibraryRepository

    def relay_fault(*_args, **_kwargs):
        raise RuntimeError("deliberate relay fault")

    monkeypatch.setattr(GuardedLibraryRepository, "accept_history", relay_fault)
    degraded = run_search(client, "transformer attention")
    assert any("검색 기록을 저장하지 못했습니다" in note for note in degraded.json()["limitations"])
    monkeypatch.undo()
    healthy = run_search(client, "retrieval augmented generation")
    assert healthy.status_code == 200 and healthy.json()["limitations"] == []

    paper = {
        "paperId": "1706.03762",
        "versionId": P1,
        "eligibilityRevision": str(uuid4()),
    }
    existing = client.post(
        "/api/v2/c03/library-list-saved-papers",
        headers=post_headers(client),
        json={"page": {"limit": 20}},
    ).json()
    record = next(
        (item for item in existing["items"] if item["savedPaperId"] == "1706.03762"), None
    )
    if record is None:
        response = client.post(
            "/api/v2/c03/library-save-paper",
            headers=post_headers(client),
            json={"paper": paper, "policyRef": LIBRARY_POLICY},
        )
        assert response.status_code == 200, response.text
        record = response.json()
    saved = record
    read = client.post(
        "/api/v2/c03/library-read-saved-paper",
        headers=post_headers(client),
        json={"savedPaperId": saved["savedPaperId"]},
    )
    assert read.status_code == 200 and read.json()["savedPaperId"] == saved["savedPaperId"]
    unknown = client.post(
        "/api/v2/c03/library-read-saved-paper",
        headers=post_headers(client),
        json={"savedPaperId": "no-such-paper"},
    )
    assert unknown.status_code == 404
    malformed_removal = client.post(
        "/api/v2/c03/library-remove-saved-paper",
        headers=post_headers(client),
        json={"savedPaperId": saved["savedPaperId"], "expectedRevision": "not-a-uuid"},
    )
    assert malformed_removal.status_code == 422
    bad_limit = client.post(
        "/api/v2/c03/library-list-history",
        headers=post_headers(client),
        json={"page": {"limit": 0}},
    )
    assert bad_limit.status_code == 422
    bad_cursor = client.post(
        "/api/v2/c03/library-list-saved-papers",
        headers=post_headers(client),
        json={"page": {"cursor": "stale-cursor"}},
    )
    assert bad_cursor.status_code == 410

    query = search_body("transformer attention")["query"]
    created = client.post(
        "/api/v2/c03/library-save-search",
        headers=post_headers(client),
        json={"queryContext": query},
    )
    assert created.status_code == 200, created.text
    saved_search = created.json()
    listed = client.post(
        "/api/v2/c03/library-list-saved-searches",
        headers=post_headers(client),
        json={"page": {"limit": 20}},
    ).json()
    assert any(item["savedSearchId"] == saved_search["savedSearchId"] for item in listed["items"])
    malformed_search_removal = client.post(
        "/api/v2/c03/library-remove-saved-search",
        headers=post_headers(client),
        json={"savedSearchId": saved_search["savedSearchId"], "expectedRevision": "not-a-uuid"},
    )
    assert malformed_search_removal.status_code == 422
    removed_search = client.post(
        "/api/v2/c03/library-remove-saved-search",
        headers=post_headers(client),
        json={
            "savedSearchId": saved_search["savedSearchId"],
            "expectedRevision": saved_search["revision"],
        },
    )
    assert removed_search.status_code == 200, removed_search.text

    history = client.post(
        "/api/v2/c03/library-list-history",
        headers=post_headers(client),
        json={"page": {"limit": 20}},
    ).json()
    assert history["items"], "an acknowledged search records one history fact"
    first = history["items"][0]
    read_history = client.post(
        "/api/v2/c03/library-read-history",
        headers=post_headers(client),
        json={"historyId": first["historyId"]},
    )
    assert read_history.status_code == 200
    assert read_history.json()["historyId"] == first["historyId"]
    missing_history = client.post(
        "/api/v2/c03/library-read-history",
        headers=post_headers(client),
        json={"historyId": str(uuid4())},
    )
    assert missing_history.status_code == 404
    bad_clear = client.post(
        "/api/v2/c03/library-clear-history",
        headers=post_headers(client),
        json={"policyRef": LIBRARY_POLICY, "expectedRevision": "nope"},
    )
    assert bad_clear.status_code == 422


def test_library_receipt_replay_and_changed_intent_conflict(client, account_a):
    """Current authority, then exact receipt replay, then fresh CAS.

    The original save, an acknowledged later removal, a fresh-session replay of
    the original operation key and a changed-intent reuse of that key through
    the mounted browser bindings.
    """
    login(client, account_a)
    paper = {
        "paperId": "2005.11401",
        "versionId": "2005.11401v4",
        "eligibilityRevision": str(uuid4()),
    }
    operation = uuid4()
    first = client.post(
        "/api/v2/c03/library-save-paper",
        headers=post_headers(client, operation=operation),
        json={"paper": paper, "policyRef": LIBRARY_POLICY},
    )
    assert first.status_code == 200, first.text
    saved = first.json()
    removed = client.post(
        "/api/v2/c03/library-remove-saved-paper",
        headers=post_headers(client),
        json={
            "savedPaperId": saved["savedPaperId"],
            "expectedRevision": saved["revision"],
        },
    )
    assert removed.status_code == 200, removed.text
    # A fresh authenticated session replays the exact original intent: the
    # original receipt returns and no new effect overwrites the later removal.
    new_browser(client)
    login(client, account_a)
    replay = client.post(
        "/api/v2/c03/library-save-paper",
        headers=post_headers(client, operation=operation),
        json={"paper": paper, "policyRef": LIBRARY_POLICY},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["savedPaperId"] == saved["savedPaperId"]
    listed = client.post(
        "/api/v2/c03/library-list-saved-papers",
        headers=post_headers(client),
        json={"page": {"limit": 20}},
    ).json()
    assert all(item["savedPaperId"] != saved["savedPaperId"] for item in listed["items"])
    # The same operation key with a changed intended paper conflicts instead of
    # silently rewriting the original outcome.
    changed = client.post(
        "/api/v2/c03/library-save-paper",
        headers=post_headers(client, operation=operation),
        json={
            "paper": {
                "paperId": "1706.03762",
                "versionId": P1,
                "eligibilityRevision": str(uuid4()),
            },
            "policyRef": LIBRARY_POLICY,
        },
    )
    assert changed.status_code == 409, changed.text
    assert changed.json()["code"] == "CONFLICT"
