from uuid import uuid4

import pytest

from backend.modules.research.errors import ResearchError
from backend.modules.research.jobs import ResearchJobs
from backend.modules.research.repository import ResearchRepository


@pytest.fixture
def repo(transactions):
    return ResearchRepository(transactions)


def scope(context):
    return {
        "contextId": str(context["id"]),
        "publicPapers": [],
        "attachmentIds": [],
        "webReferences": [],
        "scopePolicy": {"policyId": "u4-synthetic-research", "revision": "1"},
    }


def test_context_and_session_roundtrip(repo, authority):
    context = repo.create_context(authority, "research")
    session = repo.create_session(authority, "질문", scope(context))
    assert repo.read_session(authority, session["id"])["jobs"] == []
    assert session["id"] in {row["id"] for row in repo.list_sessions(authority)}


def test_unknown_context_does_not_create_session(repo, authority):
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        repo.create_session(authority, "private", scope({"id": uuid4()}))


def test_tombstone_and_revision_boundary(repo, authority):
    session = repo.create_session(
        authority, "delete", scope(repo.create_context(authority, "research"))
    )
    with pytest.raises(ResearchError, match="CONFLICT"):
        repo.delete_session(authority, session["id"], "99")
    assert repo.delete_session(authority, session["id"], "1")["lifecycle"] == "deleted"
    assert session["id"] not in {r["id"] for r in repo.list_sessions(authority)}


def test_draft_compare_and_swap_reports_current(repo, authority):
    context = repo.create_context(authority, "research")["id"]
    draft = uuid4()
    repo.save_draft(authority, draft, context, "research-question", None, "first", {})
    with pytest.raises(ResearchError) as error:
        repo.save_draft(authority, draft, context, "research-question", None, "stale", {})
    assert error.value.current == {"revision": "1"}
    assert repo.restore_draft(authority, draft, context)["text"] == "first"


def test_stale_discard_preserves_new_edit(repo, authority):
    context = repo.create_context(authority, "research")["id"]
    draft = uuid4()
    repo.save_draft(authority, draft, context, "research-question", None, "first", {})
    repo.save_draft(authority, draft, context, "research-question", "1", "new", {})
    with pytest.raises(ResearchError, match="CONFLICT"):
        repo.discard_draft(authority, draft, context, "1")
    assert repo.restore_draft(authority, draft, context)["state"] == "acknowledged"


def test_draft_cross_context_denied(repo, authority):
    first, second = [repo.create_context(authority, "research")["id"] for _ in range(2)]
    draft = uuid4()
    repo.save_draft(authority, draft, first, "research-question", None, "secret", {})
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        repo.restore_draft(authority, draft, second)
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        repo.save_draft(authority, draft, second, "research-question", "1", "other", {})


def test_revoked_authority_blocks_reads(repo, authority, connect):
    context = repo.create_context(authority, "research")
    session = repo.create_session(authority, "private", scope(context))
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.session SET revoked=true WHERE id=%s", (authority.session_id,)
        )
    with pytest.raises(Exception, match="authority|session|denied"):
        repo.read_session(authority, session["id"])


def test_acceptance_consumes_exact_revision_and_retains_dispatch(transactions, repo, authority):
    context = repo.create_context(authority, "research")
    selected_scope = scope(context)
    session = repo.create_session(authority, "question", selected_scope)
    draft = uuid4()
    old = repo.save_draft(authority, draft, context["id"], "research-question", None, "old", {})
    repo.save_draft(authority, draft, context["id"], "research-question", "1", "new", {})
    value = {
        "scope": selected_scope,
        "sessionId": str(session["id"]),
        "text": "old",
        "policy": {},
        "submittedDraft": {
            "draftId": str(draft),
            "revision": "1",
            "contentHash": old["content_hash"],
        },
    }
    jobs = ResearchJobs(transactions)
    key, usage = str(uuid4()), uuid4()
    job = jobs.accept(
        authority, kind="research-turn", operation_key=key, value=value, usage_id=usage
    )
    assert (
        jobs.accept(
            authority, kind="research-turn", operation_key=key, value=value, usage_id=usage
        )["id"]
        == job["id"]
    )
    assert repo.restore_draft(authority, draft, context["id"])["text"] == "new"
    assert repo.run(
        authority,
        lambda conn: conn.execute(
            "SELECT delivered FROM research.dispatch WHERE job_id=%s", (job["id"],)
        ).fetchone(),
    ) == {"delivered": False}
    with pytest.raises(ResearchError, match="IDEMPOTENCY_CONFLICT"):
        jobs.accept(
            authority,
            kind="research-turn",
            operation_key=key,
            value=dict(value, text="changed"),
            usage_id=usage,
        )
    repo.run(
        authority,
        lambda conn: conn.execute(
            "UPDATE research.job SET state='failed',seq=seq+1,revision=revision+1 WHERE id=%s",
            (job["id"],),
        ),
    )
