from uuid import uuid4

import pytest

from backend.modules.research.errors import ResearchError
from backend.modules.research.jobs import ResearchJobs


@pytest.fixture
def job_setup(transactions, authority):
    repo = ResearchJobs(transactions)
    context = repo.create_context(authority, "novelty")
    value = {
        "scope": {
            "contextId": str(context["id"]),
            "publicPapers": [],
            "attachmentIds": [],
            "webReferences": [],
            "scopePolicy": {},
        },
        "text": "synthetic",
        "policy": {},
    }
    yield repo, context, value
    repo.run(
        authority,
        lambda conn: conn.execute(
            "UPDATE research.job SET state='failed',seq=seq+1,revision=revision+1 WHERE context_id=%s AND state IN ('accepted','running','cancel_requested')",
            (context["id"],),
        ),
    )


def accept(repo, authority, value):
    return repo.accept(
        authority,
        kind="novelty-analysis",
        operation_key=str(uuid4()),
        value=value,
        usage_id=uuid4(),
    )


def test_job_read_is_read_only(job_setup, authority):
    repo, context, value = job_setup
    row = accept(repo, authority, value)
    first = repo.read_job(authority, row["id"], context["id"], "novelty-analysis")
    second = repo.read_job(authority, row["id"], context["id"], "novelty-analysis")
    assert first == second and first["seq"] == 1


def test_turn_scope_can_change_without_mutating_prior_snapshot(job_setup, authority):
    repo, context, value = job_setup
    session = repo.create_session(authority, "Sources", value["scope"])
    first_value = {**value, "sessionId": str(session["id"])}
    first = repo.accept(
        authority, kind="research-turn", operation_key=str(uuid4()),
        value=first_value, usage_id=uuid4(),
    )
    next_scope = {**value["scope"], "webReferences": ["https://example.org/paper"]}
    second = repo.accept(
        authority, kind="research-turn", operation_key=str(uuid4()),
        value={**first_value, "scope": next_scope}, usage_id=uuid4(),
    )
    assert second["scope"] == next_scope
    original = repo.read_job(authority, first["id"], context["id"], "research-turn")
    assert original["scope"] == value["scope"]
    assert repo.read_session(authority, session["id"])["scope"] == value["scope"]


def test_cross_context_and_kind_not_found(job_setup, authority):
    repo, context, value = job_setup
    row = accept(repo, authority, value)
    other = repo.create_context(authority, "novelty")
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        repo.read_job(authority, row["id"], other["id"], "novelty-analysis")
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        repo.read_job(authority, row["id"], context["id"], "research-turn")


def test_cancel_cas_and_repeat(job_setup, authority):
    repo, context, value = job_setup
    row = accept(repo, authority, value)
    assert repo.cancel(authority, row["id"], context["id"], "1")["state"] == "cancel_requested"
    with pytest.raises(ResearchError, match="CONFLICT"):
        repo.cancel(authority, row["id"], context["id"], "1")
    assert repo.cancel(authority, row["id"], context["id"], "2")["revision"] == 2


def test_queue_refusal_has_no_dispatch(job_setup, authority):
    repo, context, value = job_setup
    with pytest.raises(ResearchError, match="CAPACITY_EXHAUSTED"):
        repo.accept(
            authority,
            kind="novelty-analysis",
            operation_key=str(uuid4()),
            value=value,
            usage_id=uuid4(),
            queue_limit=0,
        )
    assert (
        repo.run(
            authority,
            lambda conn: conn.execute(
                "SELECT count(*) AS n FROM research.job WHERE context_id=%s", (context["id"],)
            ).fetchone(),
        )["n"]
        == 0
    )


def test_invalid_draft_rolls_back_acceptance(job_setup, authority):
    repo, context, value = job_setup
    value["submittedDraft"] = {"draftId": str(uuid4()), "revision": "1", "contentHash": "0" * 64}
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        accept(repo, authority, value)
    assert (
        repo.run(
            authority,
            lambda conn: conn.execute(
                "SELECT count(*) AS n FROM research.job WHERE context_id=%s", (context["id"],)
            ).fetchone(),
        )["n"]
        == 0
    )


def test_cross_owner_context_denial(job_setup, authority, connect):
    repo, _, _ = job_setup
    foreign = uuid4()
    with connect("research") as conn:
        conn.execute(
            "INSERT INTO research.context(id,owner_id,purpose) VALUES(%s,%s,'novelty')",
            (foreign, uuid4()),
        )
    with pytest.raises(ResearchError, match="NOT_FOUND"):
        repo.run(authority, lambda conn: repo.context(conn, authority, foreign))
