"""Actual shared-host C07 -> supervised C14 -> persisted read-only recovery.

The deterministic synthetic account keeps its finite usage ledger across runs.
No executor, owner store, worker pass, completion or capacity probe is mocked.
"""

import secrets
import time
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.u4_host import assemble_u4

POLICY = {"policyId": "u4-synthetic-research", "revision": "1"}


def post(client, operation, body):
    return client.post(
        "/api/v2/c07/" + operation,
        json=body,
        headers={"Idempotency-Key": str(uuid4())},
    )


def wait_until(check, *, seconds=16):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("supervised application did not reach the expected state")


def authorize(app, authority):
    token = secrets.token_hex(32)
    csrf = app.state.entry.verifier("session-csrf", token)
    app.state.transactions.run(
        "accounts",
        lambda conn: conn.execute(
            "UPDATE accounts.session SET token_hash=%s,csrf_hash=%s WHERE id=%s AND account_id=%s",
            (
                app.state.entry.verifier("session", token),
                app.state.entry.verifier("csrf", csrf),
                authority.session_id,
                authority.account_id,
            ),
        ),
    )
    app.state.research_execution.usage.ensure_entitlement(authority)
    return token, csrf


def client_auth(client, realm, token, csrf):
    client.cookies.set("session_id", token)
    client.headers.update({"Origin": realm.origin, "X-CSRF-Token": csrf})


def durable_state(app, job_id):
    tx = app.state.transactions
    job = tx.run(
        "research",
        lambda conn: conn.execute(
            "SELECT j.state,j.revision,j.seq,j.fence,j.attempts,j.worker_id,j.usage_id,"
            "j.usage_state,a.id AS artifact_id,a.content_hash,d.delivered,"
            "(SELECT count(*) FROM research.artifact WHERE job_id=j.id) AS artifacts "
            "FROM research.job j JOIN research.dispatch d ON d.job_id=j.id "
            "LEFT JOIN research.artifact a ON a.job_id=j.id WHERE j.id=%s",
            (job_id,),
        ).fetchone(),
    )
    usage = tx.run(
        "usage",
        lambda conn: conn.execute(
            "SELECT id,operation_id,disposition,revision,settlement_key,settlement_hash "
            "FROM usage.reservation WHERE operation_id=%s",
            (job_id,),
        ).fetchall(),
    )
    return job, usage


def test_full_assembly_supervises_source_bound_completion_and_restart(realm, authority):
    app = assemble_u4(realm)
    token, csrf = authorize(app, authority)
    # Explicit synthetic proof opt-in. It does not enable a deployment profile.
    app.state.research_execution.enabled = True
    assert app.state.research.execution is app.state.research_execution
    assert app.state.control_worker.execution is app.state.research_execution
    assert app.state.research.repository.transactions is app.state.transactions
    source = app.state.research.corpus.read("u4-paper-alpha/v1")
    paper = {
        "paperId": source["paper_id"],
        "versionId": source["id"],
        "eligibilityRevision": str(source["eligibility_revision"]),
    }
    with TestClient(app, base_url=realm.origin) as client:
        client_auth(client, realm, token, csrf)
        wait_until(lambda: app.state.control_capacity.admitting)
        loop = app.state.control_loop
        assert loop.task is not None and not loop.task.done()
        assert client.get("/health/ready").status_code == 200
        assert not any(path.startswith("/api/v2/c14/") for path in app.openapi()["paths"])
        assert client.post("/api/v2/c14/acquire-execution-claim", json={}).status_code in {404, 405}
        created = post(client, "create-research-context", {"purpose": "research", "policy": POLICY})
        assert created.status_code == 200, created.text
        scope = {
            "contextId": created.json()["contextId"],
            "publicPapers": [paper],
            "attachmentIds": [],
            "webReferences": [],
            "scopePolicy": POLICY,
        }
        session = post(
            client, "create-research-session", {"title": "Supervised fixture", "scope": scope}
        )
        assert session.status_code == 200, session.text
        session_id = session.json()["sessionId"]
        accepted = post(
            client,
            "accept-research-turn",
            {
                "sessionId": session_id,
                "scope": scope,
                "mode": "question",
                "text": "What does this synthetic retrieval fixture establish?",
                "policy": POLICY,
            },
        )
        assert accepted.status_code == 200, accepted.text
        job_id = accepted.json()["jobId"]
        query = {"jobId": job_id, "kind": "research-turn", "contextId": scope["contextId"]}

        def completed():
            response = post(client, "read-research-job", query)
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["state"] not in {"failed", "cancelled"}, result
            return result if result["state"] == "succeeded" else None

        result = wait_until(completed)
        ref = {
            "artifactId": result["result"]["resultId"],
            "revision": result["result"]["revision"],
            "contentHash": result["result"]["contentHash"],
        }
        read = post(client, "read-research-artifact", {"artifact": ref})
        assert read.status_code == 200, read.text
        prepared = read.json()["prepared"]
        assert prepared["ownerId"] == str(authority.account_id)
        assert prepared["operationId"] == job_id
        assert prepared["kind"] == "research-answer"
        assert prepared["output"]["evidence"]
        assert prepared["output"]["evidence"][0]["sourceId"] == paper["paperId"]
        assert prepared["output"]["evidence"][0]["sourceVersion"] == paper["versionId"]
        assert prepared["output"]["methodRevision"] == "u4-synthetic-extractive-1"
        assert prepared["output"]["coverage"] == "partial"
        assert prepared["output"]["limitations"]
        wait_until(lambda: durable_state(app, job_id)[0]["usage_state"] == "settled")
        before = durable_state(app, job_id)
        assert before[0]["worker_id"] == app.state.research_execution.worker_id
        assert before[0]["attempts"] == before[0]["fence"] == before[0]["artifacts"] == 1
        assert before[0]["delivered"] is True
        assert len(before[1]) == 1 and before[1][0]["disposition"] == "committed"
        assert loop.status["failures"] == loop.status["timeouts"] == 0
    assert loop.task.done() and loop.status["state"] == "stopped"

    restarted = assemble_u4(realm)
    restarted.state.research_execution.enabled = True
    with TestClient(restarted, base_url=realm.origin) as client:
        client_auth(client, realm, token, csrf)
        next_loop = restarted.state.control_loop
        wait_until(lambda: next_loop.status["passes"] >= 1)
        assert post(client, "read-research-job", query).json() == result
        reopened = post(client, "read-research-session", {"sessionId": session_id})
        assert reopened.status_code == 200 and reopened.json()["turnIds"] == [job_id]
        assert post(client, "read-research-artifact", {"artifact": ref}).json() == read.json()
        turn = post(client, "read-research-turn", {"sessionId": session_id, "turnId": job_id})
        assert turn.status_code == 200 and turn.json()["artifact"] == ref
        assert durable_state(restarted, job_id) == before
        assert next_loop.status["failures"] == next_loop.status["timeouts"] == 0
    assert next_loop.task.done() and next_loop.status["state"] == "stopped"
