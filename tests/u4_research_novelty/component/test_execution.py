from uuid import uuid4

import pytest

from backend.modules.corpus.repository import CorpusRepository
from backend.modules.research.errors import ResearchError
from backend.modules.research.execution import ResearchExecution, binding
from backend.modules.research.repository import digest
from backend.transactions import Authority


@pytest.fixture
def execution(transactions, connect):
    owner, session, revision = uuid4(), uuid4(), uuid4()
    with connect("accounts") as conn:
        conn.execute("LOCK TABLE accounts.account IN SHARE ROW EXCLUSIVE MODE")
        count = conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone()["n"]
        if count >= 20:
            pytest.fail("Synthetic account allocation exhausted; a fresh owned realm is required")
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,authority_revision,display_name) VALUES(%s,%s,'fixture',true,true,%s,'synthetic execution test')",
            (owner, f"{owner}@fixture.invalid", revision),
        )
        conn.execute(
            "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,'local-research',true)",
            (owner,),
        )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '30 minutes')",
            (session, owner, str(uuid4()), str(uuid4()), revision),
        )
    authority = Authority(owner, session)
    codec = ResearchExecution(transactions, CorpusRepository(transactions, None))
    codec.usage.ensure_entitlement(authority)
    context = codec.create_context(authority, "novelty")
    value = {
        "scope": {
            "contextId": str(context["id"]),
            "publicPapers": [],
            "attachmentIds": [],
            "webReferences": [],
            "scopePolicy": codec.policy.reference(),
        },
        "text": "synthetic question",
        "policy": codec.policy.reference(),
        "inputMode": "topic",
    }
    yield codec, authority, value
    # Explicitly close this test's remaining work; no other test/account rows change.
    rows = codec.run(
        authority,
        lambda conn: conn.execute(
            "UPDATE research.job SET state='failed',seq=seq+1,revision=revision+1 WHERE owner_id=%s AND state IN ('accepted','running','cancel_requested') RETURNING *",
            (owner,),
        ).fetchall(),
    )
    for row in rows:
        codec.reconcile(row)


def accepted(execution):
    codec, authority, value = execution
    row = codec.accept(authority, str(uuid4()), value, "novelty-analysis")
    acquired = codec.acquireExecutionClaim(authority, binding(row), uuid4())
    return row, acquired


def completion(codec, authority, row, acquired):
    output = codec.provider.run([])
    ref = {"artifactId": str(uuid4()), "revision": "1", "contentHash": digest(output)}
    return {
        "messageId": str(uuid4()),
        "causationId": str(row["id"]),
        "ownerComponent": "ResearchWorkspace",
        "operationId": str(row["id"]),
        "kind": "novelty-analysis",
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
        "inputHash": row["input_hash"],
        "progress": None,
        "prepared": {
            "artifact": ref,
            "ownerId": str(authority.account_id),
            "contextId": str(row["context_id"]),
            "operationId": str(row["id"]),
            "kind": "novelty-result",
            "output": output,
            "currentEligibilityRevision": "1",
            "mediaType": "application/json",
            "policy": codec.policy.reference(),
        },
        "usageRecordId": str(row["usage_id"]),
    }


def test_claim_payload_completion_real_store(execution):
    codec, authority, value = execution
    row, acquired = accepted(execution)
    payload = codec.readExecutionPayload(authority, acquired["claim"])
    assert payload["input"]["inputSnapshot"] == value
    fact = completion(codec, authority, row, acquired)
    done = codec.recordCompletion(authority, fact)
    assert done["state"] == "succeeded"
    assert codec.recordCompletion(authority, fact)["id"] == done["id"]
    codec.reconcile(done)
    assert codec.usage.current(authority)["counts"]["committed"] == 1


def test_replacement_claim_fences_old_payload(execution):
    codec, authority, _ = execution
    row, acquired = accepted(execution)
    codec.run(
        authority,
        lambda conn: conn.execute(
            "UPDATE research.job SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",
            (row["id"],),
        ),
    )
    second = codec.acquireExecutionClaim(authority, binding(row), uuid4(), previous_fence=1)
    assert second["claim"]["fence"] == 2
    with pytest.raises(ResearchError, match="CONFLICT"):
        codec.readExecutionPayload(authority, acquired["claim"])


def test_result_tuple_and_owner_cannot_be_substituted(execution):
    codec, authority, _ = execution
    row, acquired = accepted(execution)
    fact = completion(codec, authority, row, acquired)
    fact["resultRef"]["resultId"] = str(uuid4())
    with pytest.raises(ResearchError, match="CONFLICT"):
        codec.recordCompletion(authority, fact)
    fact = completion(codec, authority, row, acquired)
    fact["ownerComponent"] = "PaperAssistance"
    with pytest.raises(ResearchError, match="CONFLICT"):
        codec.recordCompletion(authority, fact)


def test_cancel_revision_wins_stale_completion(execution):
    codec, authority, _ = execution
    row, acquired = accepted(execution)
    codec.cancel(authority, row["id"], row["context_id"], acquired["jobRevision"])
    with pytest.raises(ResearchError, match="CONFLICT"):
        codec.recordCompletion(authority, completion(codec, authority, row, acquired))


def test_tombstone_prevents_payload(execution):
    codec, authority, _ = execution
    row, acquired = accepted(execution)
    codec.run(
        authority,
        lambda conn: conn.execute(
            "UPDATE research.context SET lifecycle='deleted' WHERE id=%s", (row["context_id"],)
        ),
    )
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        codec.readExecutionPayload(authority, acquired["claim"])


def test_closed_admission_cannot_accept_late(execution):
    codec, authority, value = execution
    key = str(uuid4())
    admission = codec.admission.prepare(authority, key, value)
    proof = codec.admission.close(authority, admission["operation_id"])
    codec.usage.reject_operation(proof)
    with pytest.raises(ResearchError, match="CONFLICT"):
        codec.accept(authority, key, value, "novelty-analysis")


def test_completion_wins_later_cancel_without_second_effect(execution):
    codec, authority, _ = execution
    row, acquired = accepted(execution)
    done = codec.recordCompletion(authority, completion(codec, authority, row, acquired))
    observed = codec.cancel(authority, row["id"], row["context_id"], str(done["revision"]))
    assert observed["state"] == "succeeded"
    assert codec.usage.current(authority)["counts"]["committed"] == 1


def test_active_claim_refuses_second_worker(execution):
    codec, authority, _ = execution
    row, acquired = accepted(execution)
    with pytest.raises(ResearchError, match="CONFLICT"):
        codec.acquireExecutionClaim(authority, binding(row), uuid4())
    same = codec.acquireExecutionClaim(authority, binding(row), acquired["claim"]["workerId"])
    assert same == acquired
