"""Step 20 (d): a failing digest step stays inside the digest failure domain.

U5 joins the one assembled release (backend/u5_host.py): its digest pass is the last
step of the shared worker pass, after the inherited corpus, assistance and research
work, and its routes sit beside the search, library, accounts and research routes.
Here the digest pass's due step fails on every pass, as a selection error would. The
inherited steps still run on every pass, the failure stays visible to the worker loop
(it is never swallowed into a success), the loop keeps scheduling passes, and the
search, library, accounts and research answers stay exactly what they were.

The failure is injected into the digest scheduler only; no store, authority or consent
check is replaced, and the four answers come from the real mounted routes.
"""

import asyncio
import secrets
import time
from uuid import uuid4

import pytest
from backend.control_runtime import ControlLoop
from backend.u3_policy import QUERY_VOCABULARY, SEARCH_POLICY
from backend.u5_host import TopicsWorker, assemble_u5
from fastapi.testclient import TestClient

PASSES = 3


class DigestStepFailure(RuntimeError):
    """The injected selection error; it carries no private text."""


def authorize(app, authority):
    """Bind a fresh browser credential to the fixture's existing session."""
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
    return token, csrf


def post(client, path, body):
    return client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})


def guest(app, origin):
    """A guest browser bound to the anonymous entry flow's CSRF token."""
    client = TestClient(app, base_url=origin)
    bootstrap = client.get("/api/v2/session")
    assert bootstrap.status_code == 200 and bootstrap.json()["signedIn"] is False
    client.headers.update({"Origin": origin, "X-CSRF-Token": bootstrap.json()["csrfToken"]})
    return client


def answers(client, visitor):
    """The four neighbouring answers, without their per-request identifiers.

    Search is the guest search: this realm admits a signed-in search only in the
    realms `GuardedDiscoveryRepository.admit` names, which do not include U5's.
    """
    session = client.get("/api/v2/session")
    library = post(client, "/api/v2/c03/library-list-saved-papers", {"page": {"limit": 5}})
    research = post(client, "/api/v2/c07/list-research-sessions", {"page": {"limit": 50}})
    query = {
        "query": "graph",
        "modeId": "lexical",
        "orderId": "relevance",
        "filters": [],
        "vocabularyRevision": QUERY_VOCABULARY,
        "policyRef": SEARCH_POLICY,
    }
    search = post(visitor, "/api/v2/c05/search", {"query": query, "page": {"limit": 10}})
    statuses = {
        "accounts": session.status_code,
        "library": library.status_code,
        "research": research.status_code,
        "search": search.status_code,
    }
    assert statuses == dict.fromkeys(statuses, 200), statuses
    found = search.json()
    return {
        "accounts": session.json(),
        "library": library.json()["items"],
        "research": research.json()["sessions"],
        # The execution identifier and its page cursor are new on every search.
        "search": {key: found[key] for key in ("outcome", "hits", "publication", "query")},
    }


def test_a_failing_digest_step_leaves_the_other_steps_and_answers_unaffected(
    realm, authority, monkeypatch
):
    app = assemble_u5(realm)
    try:
        worker = app.state.control_worker
        assert isinstance(worker, TopicsWorker)
        assert worker.scheduler is app.state.topics_scheduler
        token, csrf = authorize(app, authority)
        client = TestClient(app, base_url=realm.origin)
        client.cookies.set("session_id", token)
        client.headers.update({"Origin": realm.origin, "X-CSRF-Token": csrf})
        # Admission opens only on a genuine capacity observation; take one.
        app.state.control_capacity.refresh()
        visitor = guest(app, realm.origin)
        before = answers(client, visitor)
        assert before["accounts"]["signedIn"] is True

        inherited_passes = []
        inherited_run_once = worker.inherited.run_once

        def counted(limit=1):
            inherited_passes.append(limit)
            return inherited_run_once(limit=limit)

        def failing_due_step(result, limit):
            raise DigestStepFailure("digest selection failed")

        monkeypatch.setattr(worker.inherited, "run_once", counted)
        monkeypatch.setattr(app.state.topics_scheduler, "_evaluate_due", failing_due_step)
        passes = ControlLoop(worker, capacity=app.state.control_capacity)
        for expected in range(1, PASSES + 1):
            # The digest failure reaches the worker loop; it is not turned into a success.
            with pytest.raises(DigestStepFailure):
                passes.pass_once()
            # The inherited work ran in the same pass, before the digest step.
            assert len(inherited_passes) == expected

        # The running loop counts each failed pass and keeps scheduling the next one.
        async def run_loop():
            loop = ControlLoop(
                worker, interval=0.01, deadline=10.0, capacity=app.state.control_capacity
            )
            loop.start()
            target = len(inherited_passes) + PASSES
            deadline = time.monotonic() + 30
            while len(inherited_passes) < target and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            await loop.close()
            return loop.status, target

        status, target = asyncio.run(run_loop())
        assert len(inherited_passes) >= target
        assert status["failures"] >= PASSES and status["passes"] == 0
        assert status["state"] == "stopped"

        assert answers(client, visitor) == before
        client.close()
        visitor.close()
    finally:
        app.state.transactions.close()
