"""ResearchWorkspace's lifecycle participant (U8 plan Step 18; BR2.3).

The owner's research records are made through U4's own repository and execution APIs.
A request is made through AccountAccess's `ControlLifecycleService`, and each scope is
claimed, applied and acknowledged as the control worker does. The synthetic jobs carry
no UsageEntitlements reservation (U4's own job tests make them the same way), so once
their work is stopped this test marks their usage released through the research
owner's login, as the worker's settlement would.
"""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

import pytest

from backend.modules.accounts.password import get_password_hasher
from backend.modules.research.attachments import ResearchAttachments
from backend.modules.research.control_lifecycle import ResearchLifecycleParticipant
from backend.modules.research.evidence import SyntheticResearchProvider
from backend.modules.research.execution import ResearchExecution, binding
from backend.modules.research.jobs import ResearchJobs
from backend.modules.research.repository import digest
from backend.modules.research.service import artifact_dto
from backend.u8_host import compose
from tests.u8_service_operations_integration.conftest import _make_account

PASSWORD = "synthetic-research-participant-" + uuid4().hex[:12]  # per run (L1-36)
KINDS = ("context", "session", "job", "artifact", "evidence", "attachment", "draft")


@pytest.fixture
def composition(realm):
    value = compose(realm, process="workers")
    yield value
    value.close()


@pytest.fixture
def owner(connect, realm):
    authority = _make_account(connect, realm, suffix="research-participant")
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET lifecycle_state='active',active=true,"
                     "password_hash=%s WHERE id=%s",
                     (get_password_hasher().hash(PASSWORD), authority.account_id))
    yield authority
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET lifecycle_revision=gen_random_uuid() "
                     "WHERE id=%s", (authority.account_id,))


def research_records(transactions, owner) -> dict:
    """A context with a session, a succeeded job with its result and evidence, an open
    turn, an attachment and a draft, through U4's APIs."""
    execution = ResearchExecution(transactions, None)
    context = execution.create_context(owner, "research")
    scope = {"contextId": str(context["id"]), "publicPapers": [], "attachmentIds": [],
             "webReferences": [], "scopePolicy": {}}
    session = execution.create_session(owner, "Sources", scope)
    value = {"scope": scope, "text": "synthetic",
             "policy": {"policyId": "u8-synthetic-research", "revision": "1"},
             "sessionId": str(session["id"])}
    jobs = ResearchJobs(transactions)
    finished = jobs.accept(owner, kind="research-turn", operation_key=str(uuid4()),
                           value=value, usage_id=uuid4())
    acquired = execution.acquireExecutionClaim(owner, binding(finished), uuid4())
    output = SyntheticResearchProvider().run([])
    artifact_id = uuid4()
    prepared = artifact_dto({
        "id": artifact_id, "revision": 1, "content_hash": digest(output),
        "owner_id": owner.account_id, "context_id": context["id"], "job_id": finished["id"],
        "kind": "research-answer", "output": output, "eligibility_revision": 1,
        "policy": finished["policy"],
    })
    fact = {
        "messageId": str(uuid4()), "causationId": str(finished["id"]),
        "ownerComponent": "ResearchWorkspace", "operationId": str(finished["id"]),
        "kind": "research-turn", "outcome": "succeeded",
        "resultRef": {"resultId": str(artifact_id), "revision": "1",
                      "contentHash": digest(output), "mediaType": "application/json"},
        "error": None, "claim": acquired["claim"],
        "expectedJobRevision": acquired["jobRevision"], "inputHash": finished["input_hash"],
        "progress": None, "prepared": prepared, "usageRecordId": str(finished["usage_id"]),
    }
    try:
        execution.recordCompletion(owner, fact)
    except Exception:  # noqa: BLE001, S110 - the completion is written; only the settlement
        pass  # of the synthetic usage, which has no reservation, fails afterwards
    open_turn = jobs.accept(owner, kind="research-turn", operation_key=str(uuid4()),
                            value=value, usage_id=uuid4())
    content = b"synthetic attachment"
    ResearchAttachments(transactions).begin(owner, context["id"], "text/plain",
                                            len(content), hashlib.sha256(content).hexdigest(),
                                            {})
    execution.save_draft(owner, uuid4(), context["id"], "research-question", None,
                         "a synthetic draft", {})
    return {"jobs": [finished["id"], open_turn["id"]], "artifact": artifact_id}


def counts(connect, account) -> dict:
    with connect("research") as conn:
        row = conn.execute(
            "SELECT (SELECT count(*) FROM research.context WHERE owner_id=%(a)s) AS context,"
            " (SELECT count(*) FROM research.session WHERE owner_id=%(a)s) AS session,"
            " (SELECT count(*) FROM research.job WHERE owner_id=%(a)s) AS job,"
            " (SELECT count(*) FROM research.artifact WHERE owner_id=%(a)s) AS artifact,"
            " (SELECT count(*) FROM research.evidence WHERE owner_id=%(a)s) AS evidence,"
            " (SELECT count(*) FROM research.attachment WHERE owner_id=%(a)s) AS attachment,"
            " (SELECT count(*) FROM research.draft WHERE owner_id=%(a)s) AS draft",
            {"a": account},
        ).fetchone()
    return dict(row)


def start(composition, connect, owner, action: str) -> UUID:
    service = composition.parts["account-controls"]["lifecycle"]
    with connect("accounts") as conn:
        revision = conn.execute("SELECT lifecycle_revision FROM accounts.account WHERE id=%s",
                                (owner.account_id,)).fetchone()["lifecycle_revision"]
    return UUID(service.request(owner, uuid4(), revision, action, PASSWORD)["requestId"])


def settle(service, participant, request, scope) -> dict:
    ticket = service.claim(request, "ResearchWorkspace", scope)
    result = participant.apply(ticket)
    service.acknowledge(ticket, evidence=UUID(result["evidenceRef"]), reason=result["reasonKey"])
    return {"ticket": ticket, "result": result}


def release_usage(connect, jobs, *, owner=None) -> None:
    """Every stopped or finished synthetic job of the list (or of this test's own
    account, earlier runs included) has its synthetic usage settled."""
    with connect("research") as conn:
        if owner is not None:
            conn.execute("UPDATE research.job SET usage_state='released' WHERE owner_id=%s "
                         "AND state IN ('failed','succeeded','cancelled')", (owner,))
        conn.execute("UPDATE research.job SET usage_state='released' WHERE id=ANY(%s) "
                     "AND state IN ('failed','succeeded','cancelled')", (list(jobs),))


def recorded(connect, request) -> list[dict]:
    with connect("research") as conn:
        return conn.execute("SELECT * FROM research.lifecycle_counts WHERE request_id=%s "
                            "ORDER BY scope", (request,)).fetchall()


def test_erase_removes_every_research_kind_and_counts_it(composition, connect,
                                                         transactions, owner):
    made = research_records(transactions, owner)
    before = counts(connect, owner.account_id)
    # The synthetic result cites no public paper, so it carries no evidence rows.
    assert all(before[kind] >= 1 for kind in KINDS if kind != "evidence"), before
    request = start(composition, connect, owner, "erase")
    service = composition.parts["account-controls"]["lifecycle"]
    participant = ResearchLifecycleParticipant(transactions)
    info = {"id": request, "account_id": owner.account_id, "action": "erase"}
    assert participant.ready(info, "live_records") is False  # an open turn remains
    stopped = settle(service, participant, request, "pending_work")
    release_usage(connect, made["jobs"], owner=owner.account_id)
    assert participant.ready(info, "live_records") is True
    settle(service, participant, request, "derived_artifacts")
    settle(service, participant, request, "live_records")
    assert counts(connect, owner.account_id) == dict.fromkeys(KINDS, 0)
    rows = {row["scope"]: row for row in recorded(connect, request)}
    assert rows["pending_work"]["jobs_stopped"] == 1
    assert rows["derived_artifacts"]["artifacts"] == before["artifact"]
    assert rows["derived_artifacts"]["evidence"] == before["evidence"]
    live = rows["live_records"]
    assert (live["contexts"], live["sessions"], live["jobs"], live["attachments"]) == (
        before["context"], before["session"], before["job"], before["attachment"])
    assert live["drafts"] >= before["draft"]
    assert all(row["action"] == "erase" for row in rows.values())
    assert stopped["result"]["reasonKey"] == "owner-scope-complete"


def test_once_per_request_and_scope_a_retry_writes_nothing(composition, connect,
                                                          transactions, owner):
    made = research_records(transactions, owner)
    request = start(composition, connect, owner, "withdraw")
    service = composition.parts["account-controls"]["lifecycle"]
    participant = ResearchLifecycleParticipant(transactions)
    settle(service, participant, request, "pending_work")
    # The scope is complete: a retried claim is refused, and the recorded evidence stays.
    with pytest.raises(ValueError):
        service.claim(request, "ResearchWorkspace", "pending_work")
    ticket = service.claim(request, "ResearchWorkspace", "live_records")
    result = participant.apply(ticket)
    retried = participant.apply(ticket)  # a retry of the same ticket
    assert retried["evidenceRef"] == result["evidenceRef"]
    assert len(recorded(connect, request)) == 2
    release_usage(connect, made["jobs"])


def test_withdraw_stops_work_and_keeps_every_record(composition, connect, transactions,
                                                   owner):
    made = research_records(transactions, owner)
    before = counts(connect, owner.account_id)
    request = start(composition, connect, owner, "withdraw")
    service = composition.parts["account-controls"]["lifecycle"]
    participant = ResearchLifecycleParticipant(transactions)
    info = {"id": request, "account_id": owner.account_id, "action": "withdraw"}
    assert all(participant.ready(info, scope) for scope in participant.scopes)
    for scope in ("derived_artifacts", "live_records", "pending_work"):
        settle(service, participant, request, scope)
    assert counts(connect, owner.account_id) == before
    rows = {row["scope"]: row for row in recorded(connect, request)}
    assert rows["pending_work"]["jobs_stopped"] == 1
    assert rows["live_records"]["contexts"] == before["context"]
    assert rows["derived_artifacts"]["artifacts"] == before["artifact"]
    with connect("research") as conn:
        states = {row["state"] for row in conn.execute(
            "SELECT state FROM research.job WHERE id=ANY(%s)", (made["jobs"],)).fetchall()}
    assert states == {"succeeded", "failed"}
    release_usage(connect, made["jobs"])


def test_the_participant_writes_only_research_records_through_its_guard(
    composition, connect, transactions, owner,
):
    request = start(composition, connect, owner, "withdraw")
    service = composition.parts["account-controls"]["lifecycle"]
    participant = ResearchLifecycleParticipant(transactions)
    ticket = service.claim(request, "ResearchWorkspace", "pending_work")
    with pytest.raises(PermissionError):
        participant.apply({**ticket, "participant": "Library"})
    with pytest.raises(PermissionError):
        participant.apply({**ticket, "scope": "backups"})
    stale = {**ticket, "generation": ticket["generation"] + 1}
    with pytest.raises(Exception):  # noqa: B017 - the guard's 42501, as any owner's
        participant.apply(stale)
    assert recorded(connect, request) == []
