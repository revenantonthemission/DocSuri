"""Mounted C07 transport with real owner stores and current session verification."""

import secrets
from types import SimpleNamespace
from uuid import uuid4

import pytest
from docsuri_shared.workspace import wire
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.corpus.repository import CorpusRepository
from backend.modules.research.execution import ResearchExecution, binding
from backend.modules.research.http import research_router
from backend.modules.research.repository import digest
from backend.modules.research.service import ResearchService
from backend.transactions import Authority, OwnerTransactions

POLICY = {"policyId": "u4-synthetic-research", "revision": "1"}


@pytest.fixture(scope="module")
def mounted(realm):
    transactions = OwnerTransactions(realm)
    entry = GuardedEntryService(transactions)
    corpus = CorpusRepository(transactions, None)
    codec = ResearchExecution(transactions, corpus)
    service = ResearchService(transactions, corpus, execution=codec)
    app = FastAPI()
    app.include_router(research_router(transactions, entry=entry, service=service))
    clients, authorities = [], []
    for _ in range(2):
        owner, session, revision = uuid4(), uuid4(), uuid4()
        token = secrets.token_hex(32)
        csrf = entry.verifier("session-csrf", token)

        def seed(conn):
            # Tests obey the same finite realm allocation. Repeated verification
            # uses a fresh owned realm, never resets a prior owner's spent usage.
            conn.execute("LOCK TABLE accounts.account IN SHARE ROW EXCLUSIVE MODE")
            count = conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone()["n"]
            if count >= 20:
                pytest.fail("Synthetic account allocation exhausted; use a fresh owned U4 realm")
            conn.execute(
                "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
                "authority_revision,display_name) VALUES(%s,%s,'fixture',true,true,%s,'HTTP fixture')",
                (owner, f"{owner}@fixture.invalid", revision),
            )
            conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted) "
                "VALUES(%s,'local-research',true)",
                (owner,),
            )
            conn.execute(
                "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
                "authority_revision,expires_at) VALUES(%s,%s,%s,%s,%s,"
                "clock_timestamp()+interval '30 minutes')",
                (
                    session,
                    owner,
                    entry.verifier("session", token),
                    entry.verifier("csrf", csrf),
                    revision,
                ),
            )

        transactions.run("accounts", seed)
        authority = Authority(owner, session)
        codec.usage.ensure_entitlement(authority)
        client = TestClient(app, base_url=realm.origin)
        client.cookies.set("session_id", token)
        client.headers.update({"Origin": realm.origin, "X-CSRF-Token": csrf})
        clients.append(client)
        authorities.append(authority)
    yield SimpleNamespace(
        app=app,
        client=clients[0],
        other=clients[1],
        authority=authorities[0],
        other_authority=authorities[1],
        codec=codec,
        service=service,
        transactions=transactions,
    )
    for authority in authorities:
        rows = codec.run(
            authority,
            lambda conn: conn.execute(
                "UPDATE research.job SET state='failed',seq=seq+1,revision=revision+1 "
                "WHERE owner_id=%s AND state IN ('accepted','running','cancel_requested') RETURNING *",
                (authority.account_id,),
            ).fetchall(),
        )
        for row in rows:
            codec.reconcile(row)
    for client in clients:
        client.close()
    transactions.close()


def post(client, operation, body, key=None):
    return client.post(
        "/api/v2/c07/" + operation,
        json=body,
        headers={"Idempotency-Key": str(key or uuid4())},
    )


def scope(mounted, *, purpose="novelty"):
    response = post(
        mounted.client, "create-research-context", {"purpose": purpose, "policy": POLICY}
    )
    assert response.status_code == 200, response.text
    return {
        "contextId": response.json()["contextId"],
        "publicPapers": [],
        "attachmentIds": [],
        "webReferences": [],
        "scopePolicy": POLICY,
    }


def novelty(mounted):
    return {
        "scope": scope(mounted),
        "inputMode": "topic",
        "text": "Synthetic topic",
        "policy": POLICY,
    }


def completion(mounted, job, acquired):
    payload = mounted.codec.readExecutionPayload(mounted.authority, acquired["claim"])
    output = mounted.codec.provider.run([])
    ref = {"artifactId": str(uuid4()), "revision": "1", "contentHash": digest(output)}
    return {
        "messageId": str(uuid4()),
        "causationId": str(job["id"]),
        "ownerComponent": "ResearchWorkspace",
        "operationId": str(job["id"]),
        "kind": job["kind"],
        "outcome": "succeeded",
        "resultRef": {
            "resultId": ref["artifactId"],
            "revision": "1",
            "contentHash": ref["contentHash"],
            "mediaType": "application/json",
        },
        "error": None,
        "claim": acquired["claim"],
        "expectedJobRevision": acquired["jobRevision"],
        "inputHash": job["input_hash"],
        "progress": None,
        "usageRecordId": payload["usageRecordId"],
        "prepared": {
            "artifact": ref,
            "ownerId": str(mounted.authority.account_id),
            "contextId": str(job["context_id"]),
            "operationId": str(job["id"]),
            "kind": "novelty-result",
            "output": output,
            "currentEligibilityRevision": "1",
            "mediaType": "application/json",
            "policy": POLICY,
        },
    }


def test_creation_replay_and_changed_intent(mounted):
    key = uuid4()
    body = {"purpose": "research", "policy": POLICY}
    first = post(mounted.client, "create-research-context", body, key)
    assert first.status_code == 200, first.text
    assert post(mounted.client, "create-research-context", body, key).json() == first.json()
    assert (
        post(
            mounted.client, "create-research-context", dict(body, purpose="novelty"), key
        ).status_code
        == 409
    )
    source = dict(scope(mounted, purpose="research"), contextId=first.json()["contextId"])
    body = {"title": "Synthetic session", "scope": source}
    key = uuid4()
    first = post(mounted.client, "create-research-session", body, key)
    assert first.status_code == 200, first.text
    assert post(mounted.client, "create-research-session", body, key).json() == first.json()
    assert (
        post(
            mounted.client, "create-research-session", dict(body, title="changed"), key
        ).status_code
        == 409
    )


def test_sessions_are_private_and_reads_create_no_work(mounted):
    created = post(
        mounted.client,
        "create-research-session",
        {"title": "Private", "scope": scope(mounted, purpose="research")},
    )
    assert created.status_code == 200, created.text
    body = {"sessionId": created.json()["sessionId"]}
    read = post(mounted.client, "read-research-session", body)
    wire.ResearchSession.model_validate(read.json())
    assert read.json()["turnIds"] == []
    assert read.headers["cache-control"] == "no-store"
    assert post(mounted.other, "read-research-session", body).status_code == 404
    assert (
        post(mounted.other, "read-research-session", {"sessionId": str(uuid4())}).status_code == 404
    )
    listed = post(mounted.client, "list-research-sessions", {"page": {"limit": 50}})
    wire.ResearchSessions.model_validate(listed.json())
    assert body["sessionId"] in [item["sessionId"] for item in listed.json()["sessions"]]


def test_acceptance_stays_closed_without_codec(mounted):
    mounted.codec.enabled = False
    response = post(mounted.client, "accept-novelty-analysis", novelty(mounted))
    assert response.status_code == 503 and response.json()["code"] == "DEPENDENCY_UNAVAILABLE"


def test_mounted_accept_c14_completion_and_readonly_recovery(mounted):
    mounted.codec.enabled = True  # Explicit conformance proof before assembly enablement.
    value, key = novelty(mounted), uuid4()
    accepted = post(mounted.client, "accept-novelty-analysis", value, key)
    assert accepted.status_code == 200, accepted.text
    assert post(mounted.client, "accept-novelty-analysis", value, key).json() == accepted.json()
    assert (
        post(
            mounted.client, "accept-novelty-analysis", dict(value, text="different"), key
        ).status_code
        == 409
    )
    job_id = accepted.json()["jobId"]
    read = {"kind": "novelty-analysis", "jobId": job_id, "contextId": value["scope"]["contextId"]}
    row = mounted.codec.read_job(mounted.authority, job_id, read["contextId"], read["kind"])
    acquired = mounted.codec.acquireExecutionClaim(mounted.authority, binding(row), uuid4())
    fact = completion(mounted, row, acquired)
    mounted.codec.recordCompletion(mounted.authority, fact)
    mounted.codec.recordCompletion(mounted.authority, fact)
    before = mounted.codec.usage.current(mounted.authority)["counts"]
    for _ in range(2):
        status = post(mounted.client, "read-research-job", read)
        assert status.status_code == 200, status.text
        assert status.json()["state"] == "succeeded"
        wire.JobSnapshot.model_validate(status.json())
        result = post(
            mounted.client, "read-research-artifact", {"artifact": fact["prepared"]["artifact"]}
        )
        assert result.status_code == 200, result.text
        assert result.json()["availability"] == "ready"
        assert result.json()["prepared"]["output"]["coverage"] == "abstained"
    assert mounted.codec.usage.current(mounted.authority)["counts"] == before
    assert post(mounted.other, "read-research-job", read).status_code == 404
    assert (
        post(mounted.client, "read-research-job", dict(read, contextId=str(uuid4()))).status_code
        == 404
    )
    assert (
        post(mounted.client, "read-research-job", dict(read, kind="research-turn")).status_code
        == 404
    )
    assert (
        post(
            mounted.other, "read-research-artifact", {"artifact": fact["prepared"]["artifact"]}
        ).status_code
        == 404
    )
    invalid_ref = dict(fact["prepared"]["artifact"], contentHash="0" * 64)
    assert (
        post(mounted.client, "read-research-artifact", {"artifact": invalid_ref}).status_code == 409
    )
    discussion = {
        "source": fact["prepared"]["artifact"],
        "text": "Which source supports this result?",
        "policy": POLICY,
    }
    assert post(mounted.other, "accept-novelty-discussion", discussion).status_code == 404
    assert (
        post(
            mounted.client, "accept-novelty-discussion", dict(discussion, source=invalid_ref)
        ).status_code
        == 409
    )
    followup_key = uuid4()
    followup = post(mounted.client, "accept-novelty-discussion", discussion, followup_key)
    assert followup.status_code == 200, followup.text
    assert (
        post(mounted.client, "accept-novelty-discussion", discussion, followup_key).json()
        == followup.json()
    )


def test_research_turn_and_novelty_cancellation_are_distinct(mounted):
    mounted.codec.enabled = True
    source = scope(mounted, purpose="research")
    session = post(
        mounted.client, "create-research-session", {"title": "Turn", "scope": source}
    ).json()
    value = {
        "sessionId": session["sessionId"],
        "scope": source,
        "mode": "question",
        "text": "x" * 32768,
        "policy": POLICY,
    }
    accepted = post(mounted.client, "accept-research-turn", value)
    assert accepted.status_code == 200, accepted.text
    read = {
        "kind": "research-turn",
        "jobId": accepted.json()["jobId"],
        "contextId": source["contextId"],
    }
    assert post(mounted.client, "cancel-novelty-analysis", read).status_code == 422
    turn = post(
        mounted.client,
        "read-research-turn",
        {"sessionId": session["sessionId"], "turnId": read["jobId"]},
    )
    assert turn.status_code == 200, turn.text
    assert turn.json()["committedText"] == value["text"]
    too_large = post(mounted.client, "accept-research-turn", dict(value, text="x" * 32769))
    assert too_large.status_code == 422
    other_value = novelty(mounted)
    analysis = post(mounted.client, "accept-novelty-analysis", other_value)
    assert analysis.status_code == 200, analysis.text
    read = {
        "kind": "novelty-analysis",
        "jobId": analysis.json()["jobId"],
        "contextId": other_value["scope"]["contextId"],
    }
    cancelled = post(mounted.client, "cancel-novelty-analysis", read)
    assert cancelled.status_code == 200 and cancelled.json()["state"] == "cancel_requested"
    assert post(mounted.client, "cancel-novelty-analysis", read).json() == cancelled.json()


@pytest.mark.parametrize(
    "name,body",
    [
        (
            "save-draft",
            {
                "draftId": str(uuid4()),
                "kind": "research-question",
                "baseRevision": None,
                "text": "private",
                "policy": POLICY,
            },
        ),
        ("restore-draft", {"draftId": str(uuid4())}),
        (
            "discard-draft",
            {
                "draft": {"draftId": str(uuid4()), "revision": "1", "contentHash": "a" * 64},
                "confirmed": True,
                "policy": POLICY,
            },
        ),
        (
            "begin-private-attachment",
            {
                "fileName": "fixture.txt",
                "mediaType": "text/plain",
                "byteLength": 7,
                "contentHash": "a" * 64,
                "policy": POLICY,
            },
        ),
        ("finish-private-attachment", {"uploadId": str(uuid4()), "contentHash": "a" * 64}),
        ("read-private-attachment", {"attachmentId": str(uuid4())}),
        ("read-private-asset", {"attachmentId": str(uuid4()), "assetId": str(uuid4())}),
    ],
)
def test_unresolved_private_policy_refuses_without_persisting(mounted, name, body):
    context = scope(mounted)["contextId"]
    response = post(mounted.client, name, dict(body, contextId=context))
    assert response.status_code == 503 and response.json()["code"] == "POLICY_UNRESOLVED"
    assert post(mounted.other, name, dict(body, contextId=context)).status_code == 404


def test_auth_json_origin_and_identity_boundaries(mounted):
    body = {"purpose": "research", "policy": POLICY}
    with TestClient(mounted.app, base_url=mounted.client.base_url) as anonymous:
        anonymous.headers.update(
            {"Origin": str(mounted.client.base_url).rstrip("/"), "X-CSRF-Token": "a" * 64}
        )
        assert post(anonymous, "create-research-context", body).status_code == 401
    assert (
        post(
            mounted.client, "create-research-context", dict(body, ownerId=str(uuid4()))
        ).status_code
        == 422
    )
    assert (
        post(mounted.client, "read-research-session", {"sessionId": "malformed"}).status_code == 422
    )
    path = "/api/v2/c07/create-research-context"
    assert (
        mounted.client.post(path, json=body, headers={"Origin": "https://evil.invalid"}).status_code
        == 403
    )
    assert (
        mounted.client.post(
            path, json=body, headers={"Idempotency-Key": str(uuid4()), "X-CSRF-Token": "b" * 64}
        ).status_code
        == 403
    )
    response = mounted.client.post(
        path,
        content='{"purpose":"research","purpose":"novelty"}',
        headers={"Idempotency-Key": str(uuid4()), "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert mounted.client.get("/api/v2/c14/read-execution-payload").status_code == 404


def test_delete_requires_exact_scope_and_tombstone_hides_session(mounted):
    created = post(
        mounted.client,
        "create-research-session",
        {"title": "Delete", "scope": scope(mounted, purpose="research")},
    ).json()
    body = {
        "scope": "one-session",
        "sessionId": created["sessionId"],
        "expectedRevision": created["revision"],
        "confirmed": True,
        "policy": POLICY,
    }
    bad = dict(body)
    del bad["sessionId"]
    assert post(mounted.client, "delete-research-sessions", bad).status_code == 422
    assert (
        post(
            mounted.client, "delete-research-sessions", dict(body, scope="all-sessions")
        ).status_code
        == 422
    )
    operation = uuid4()
    response = post(mounted.client, "delete-research-sessions", body, key=operation)
    assert response.status_code == 200, response.text
    wire.ResearchDeletion.model_validate(response.json())
    assert response.json()["requestId"] == str(operation)
    replay = post(mounted.client, "delete-research-sessions", body, key=operation)
    assert replay.status_code == 200, replay.text
    assert replay.json() == response.json()
    changed = post(
        mounted.client, "delete-research-sessions",
        dict(body, expectedRevision="another-revision"), key=operation,
    )
    assert changed.status_code == 409
    assert changed.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert post(
        mounted.client, "read-research-session", {"sessionId": created["sessionId"]}
    ).status_code == 404


def test_manuscript_policy_is_enforced_before_admission(mounted):
    source = scope(mounted, purpose="novelty")
    before = mounted.service.repository.run(
        mounted.authority,
        lambda conn: conn.execute("SELECT count(*) AS n FROM research.admission").fetchone()["n"],
    )
    for attachments in ([], [str(uuid4())]):
        body = {
            "scope": dict(source, attachmentIds=attachments),
            "text": "Synthetic manuscript", "inputMode": "manuscript", "policy": POLICY,
        }
        response = post(mounted.client, "accept-novelty-analysis", body)
        assert response.status_code == 503
        assert response.json()["code"] == "POLICY_UNRESOLVED"
    after = mounted.service.repository.run(
        mounted.authority,
        lambda conn: conn.execute("SELECT count(*) AS n FROM research.admission").fetchone()["n"],
    )
    assert after == before


def test_revoked_session_cannot_read_prior_private_context(mounted):
    created = post(
        mounted.other,
        "create-research-session",
        {
            "title": "Revoke",
            "scope": {
                "contextId": post(
                    mounted.other,
                    "create-research-context",
                    {"purpose": "research", "policy": POLICY},
                ).json()["contextId"],
                "publicPapers": [],
                "attachmentIds": [],
                "webReferences": [],
                "scopePolicy": POLICY,
            },
        },
    ).json()
    mounted.transactions.run(
        "accounts",
        lambda conn: conn.execute(
            "UPDATE accounts.session SET revoked=true WHERE id=%s",
            (mounted.other_authority.session_id,),
        ),
    )
    assert (
        post(
            mounted.other, "read-research-session", {"sessionId": created["sessionId"]}
        ).status_code
        == 404
    )
    # Keep teardown under current authority without touching any other session.
    mounted.transactions.run(
        "accounts",
        lambda conn: conn.execute(
            "UPDATE accounts.session SET revoked=false WHERE id=%s",
            (mounted.other_authority.session_id,),
        ),
    )
