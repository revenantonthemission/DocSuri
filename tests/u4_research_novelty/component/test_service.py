from uuid import uuid4

import pytest
from docsuri_shared.workspace import wire

from backend.modules.corpus.repository import CorpusRepository
from backend.modules.research.errors import ResearchError
from backend.modules.research.service import ResearchService


@pytest.fixture
def service(transactions):
    return ResearchService(transactions, CorpusRepository(transactions, None))


def context_and_scope(service, authority):
    context = service.create_context(
        authority, {"purpose": "research", "policy": service.policy.reference()}
    )
    scope = {
        "contextId": context["contextId"],
        "publicPapers": [],
        "attachmentIds": [],
        "webReferences": [],
        "scopePolicy": service.policy.reference(),
    }
    return context, scope


def test_create_retry_receipt_and_intent_conflict(service, authority):
    key = uuid4()
    value = {"purpose": "research", "policy": service.policy.reference()}
    context = service.create_context(authority, value, operation=key)
    assert service.create_context(authority, value, operation=key) == context
    with pytest.raises(ResearchError, match="IDEMPOTENCY_CONFLICT"):
        service.create_context(authority, dict(value, purpose="novelty"), operation=key)


def test_session_retry_and_canonical_read(service, authority):
    _, scope = context_and_scope(service, authority)
    key = uuid4()
    value = {"title": "질문", "scope": scope}
    session = service.create_session(authority, value, operation=key)
    assert service.create_session(authority, value, operation=key) == session
    wire.ResearchSession.model_validate(session)
    assert service.read_session(authority, {"sessionId": session["sessionId"]}) == session


def test_policy_suspended_private_material(service, authority):
    context, _ = context_and_scope(service, authority)
    with pytest.raises(ResearchError, match="POLICY_UNRESOLVED"):
        service.suspended_private(authority, {"contextId": context["contextId"]})
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        service.suspended_private(authority, {"contextId": str(uuid4())})


def test_codec_gate_rejects_before_acceptance(service, authority):
    _, scope = context_and_scope(service, authority)
    with pytest.raises(ResearchError, match="DEPENDENCY_UNAVAILABLE"):
        service.accept(
            authority,
            str(uuid4()),
            {"scope": scope, "text": "test", "policy": service.policy.reference(),
             "inputMode": "topic"},
            "novelty-analysis",
        )


def test_snapshot_cursor_expires_on_mutation(service, authority):
    _, scope = context_and_scope(service, authority)
    for title in ("one", "two"):
        service.create_session(authority, {"title": title, "scope": scope})
    page = service.list_sessions(authority, {"page": {"limit": 1}})
    wire.ResearchSessions.model_validate(page)
    cursor = page["page"]["nextCursor"]
    assert cursor
    assert service.list_sessions(authority, {"page": {"limit": 1, "cursor": cursor}})["sessions"]
    service.create_session(authority, {"title": "new", "scope": scope})
    with pytest.raises(ResearchError, match="SNAPSHOT_EXPIRED"):
        service.list_sessions(authority, {"page": {"cursor": cursor}})


def test_all_session_delete_uses_snapshot_and_reports_limits(service, authority):
    _, scope = context_and_scope(service, authority)
    service.create_session(authority, {"title": "remove", "scope": scope})
    page = service.list_sessions(authority, {"page": {}})
    value = {
        "scope": "all-sessions",
        "expectedRevision": page["page"]["snapshotRevision"],
        "confirmed": True,
        "policy": service.policy.reference(),
    }
    key = uuid4()
    result = service.delete_sessions(authority, value, operation=key)
    wire.ResearchDeletion.model_validate(result)
    assert result["state"] == "limited" and result["limitations"]
    assert service.delete_sessions(authority, value, operation=key) == result
    assert service.list_sessions(authority, {"page": {}})["sessions"] == []


def test_byte_limit_and_unresolved_policy(service, authority):
    _, scope = context_and_scope(service, authority)
    with pytest.raises(ResearchError, match="INVALID_ARGUMENT"):
        service.accept(
            authority,
            str(uuid4()),
            {"scope": scope, "text": "한" * 10923, "policy": service.policy.reference()},
            "novelty-analysis",
        )
    with pytest.raises(ResearchError, match="POLICY_UNRESOLVED"):
        service.create_context(
            authority, {"purpose": "research", "policy": {"policyId": "unknown", "revision": "1"}}
        )
