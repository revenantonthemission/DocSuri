"""The owner job list (Step 8; A2, common rule 6).

Jobs are written as ResearchWorkspace's own login. Their accepted times are later than
anything an earlier run left, so each test's jobs are the owner's newest.
"""

from __future__ import annotations

import datetime as dt
import secrets
from uuid import uuid4

import pytest

from backend.modules.research.errors import ResearchError
from backend.modules.research.job_list import JobListCursor
from backend.modules.research.repository import ResearchRepository

KINDS = ("research-turn", "novelty-analysis", "research-turn", "novelty-discussion",
         "research-turn")


@pytest.fixture
def repository(transactions, clock):
    return ResearchRepository(
        transactions, job_list_cursor=JobListCursor(secrets.token_bytes(32), clock=clock))


def make_jobs(connect, authority, clock, kinds=KINDS, *, title="Synthetic session"):
    """One context and session for the owner, then one job per kind, newest last."""
    base = clock() + dt.timedelta(seconds=5)
    context, session = uuid4(), uuid4()
    jobs = []
    with connect("research") as conn:
        conn.execute("INSERT INTO research.context(id,owner_id,purpose) VALUES(%s,%s,'research')",
                     (context, authority.account_id))
        conn.execute(
            "INSERT INTO research.session(id,owner_id,context_id,title,scope) "
            "VALUES(%s,%s,%s,%s,'{}')", (session, authority.account_id, context, title))
        for index, kind in enumerate(kinds):
            job, accepted = uuid4(), base + dt.timedelta(milliseconds=10 * index)
            conn.execute(
                "INSERT INTO research.job(id,owner_id,context_id,session_id,authority_session,"
                "kind,operation_key,input_hash,input,scope,policy,accepted_at,updated_at,"
                "usage_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'{}','{}','{}',%s,%s,%s)",
                (job, authority.account_id, context,
                 session if kind == "research-turn" else None, authority.session_id, kind,
                 str(uuid4()), secrets.token_hex(32), accepted, accepted, uuid4()),
            )
            jobs.append((job, kind, accepted))
    return list(reversed(jobs))  # newest first


def our(page, jobs):
    mine = {str(job) for job, _, _ in jobs}
    return [item for item in page["items"] if item["jobId"] in mine]


def test_the_list_is_newest_first_and_pages_with_a_cursor(repository, authority, connect,
                                                          clock):
    jobs = make_jobs(connect, authority, clock)
    first = repository.list_owner_jobs(authority, None, None, 2, now=clock())
    assert [item["jobId"] for item in first["items"]] == [str(job) for job, _, _ in jobs[:2]]
    assert first["nextCursor"] is not None
    second = repository.list_owner_jobs(authority, None, first["nextCursor"], 3, now=clock())
    assert [item["jobId"] for item in second["items"]] == [str(job) for job, _, _ in jobs[2:5]]
    item = first["items"][0]
    assert set(item) == {"jobId", "kind", "label", "state", "createdAt", "updatedAt",
                         "resultAvailable"}
    assert item["kind"] == "research" and item["label"] == "Synthetic session"
    assert item["state"] == "accepted" and item["resultAvailable"] is False


def test_another_owners_jobs_never_appear(repository, authority, authority_b, connect, clock):
    mine = make_jobs(connect, authority, clock, ("research-turn",))
    theirs = make_jobs(connect, authority_b, clock, ("novelty-analysis",))
    page = repository.list_owner_jobs(authority, None, None, 50, now=clock())
    listed = {item["jobId"] for item in page["items"]}
    assert str(mine[0][0]) in listed and str(theirs[0][0]) not in listed


def test_the_kind_filter_keeps_one_kind(repository, authority, connect, clock):
    jobs = make_jobs(connect, authority, clock)
    novelty = repository.list_owner_jobs(authority, "novelty", None, 50, now=clock())
    found = our(novelty, jobs)
    assert [item["jobId"] for item in found] == [
        str(job) for job, kind, _ in jobs if kind.startswith("novelty")]
    assert {item["kind"] for item in novelty["items"]} == {"novelty"}
    assert {item["label"] for item in found} == {"참신성 분석", "참신성 토론"}
    with pytest.raises(ResearchError, match="INVALID_ARGUMENT"):
        repository.list_owner_jobs(authority, "summary", None, 10, now=clock())
    with pytest.raises(ResearchError, match="INVALID_ARGUMENT"):
        repository.list_owner_jobs(authority, None, None, 51, now=clock())


def test_a_tampered_foreign_or_other_kind_cursor_is_refused(repository, authority, authority_b,
                                                            connect, clock):
    make_jobs(connect, authority, clock)
    cursor = repository.list_owner_jobs(authority, None, None, 1, now=clock())["nextCursor"]
    tampered = cursor[:-4] + ("AAAA" if not cursor.endswith("AAAA") else "BBBB")
    for value, owner, kind in ((tampered, authority, None), (cursor, authority_b, None),
                               (cursor, authority, "research"), ("not-a-cursor", authority,
                                                                 None)):
        with pytest.raises(ResearchError, match="INVALID_ARGUMENT"):
            repository.list_owner_jobs(owner, kind, value, 5, now=clock())
    clock.advance(301)
    with pytest.raises(ResearchError, match="INVALID_ARGUMENT"):
        repository.list_owner_jobs(authority, None, cursor, 5, now=clock())


def test_a_result_is_available_only_for_a_succeeded_job_with_a_live_artifact(
        repository, authority, connect, clock):
    jobs = make_jobs(connect, authority, clock,
                     ("novelty-analysis", "novelty-analysis", "novelty-analysis"))
    (live, _, _), (missing, _, _), (withdrawn, _, _) = jobs
    with connect("research") as conn:
        artifacts = {}
        for job in (live, withdrawn):
            context = conn.execute("SELECT context_id FROM research.job WHERE id=%s",
                                   (job,)).fetchone()["context_id"]
            artifacts[job] = uuid4()
            conn.execute(
                "INSERT INTO research.artifact(id,job_id,context_id,owner_id,content_hash,kind,"
                "output,policy,expires_at) VALUES(%s,%s,%s,%s,%s,'novelty-result','{}','{}',"
                "%s)",
                (artifacts[job], job, context, authority.account_id, secrets.token_hex(32),
                 clock() + dt.timedelta(days=1)))
        conn.execute("UPDATE research.artifact SET availability='deleted' WHERE id=%s",
                     (artifacts[withdrawn],))
        for job in (live, missing, withdrawn):
            # U4's guard: accepted -> running -> succeeded.
            conn.execute("UPDATE research.job SET state='running' WHERE id=%s", (job,))
            conn.execute("UPDATE research.job SET state='succeeded',artifact_id=%s WHERE id=%s",
                         (artifacts.get(job), job))
        moved = conn.execute("SELECT updated_at,accepted_at FROM research.job WHERE id=%s",
                             (live,)).fetchone()
    assert moved["updated_at"] >= moved["accepted_at"]
    items = {item["jobId"]: item for item in our(
        repository.list_owner_jobs(authority, "novelty", None, 50, now=clock()), jobs)}
    assert items[str(live)]["resultAvailable"] is True
    assert items[str(missing)]["resultAvailable"] is False
    assert items[str(withdrawn)]["resultAvailable"] is False
    assert {items[str(job)]["state"] for job in (live, missing, withdrawn)} == {"succeeded"}
    later = repository.list_owner_jobs(authority, "novelty", None, 50,
                                       now=clock() + dt.timedelta(days=2))
    assert {item["jobId"]: item for item in our(later, jobs)}[str(live)][
        "resultAvailable"] is False


def test_reading_the_list_never_starts_retries_or_cancels_work(repository, authority, connect,
                                                               clock):
    jobs = make_jobs(connect, authority, clock)
    ids = [job for job, _, _ in jobs]

    def snapshot():
        with connect("research") as conn:
            rows = conn.execute(
                "SELECT id,state,revision,seq,lease_id,attempts,updated_at FROM research.job "
                "WHERE id=ANY(%s) ORDER BY id", (ids,)).fetchall()
            dispatched = conn.execute(
                "SELECT count(*) AS n FROM research.dispatch WHERE job_id=ANY(%s)",
                (ids,)).fetchone()["n"]
        return rows, dispatched

    before = snapshot()
    page = repository.list_owner_jobs(authority, None, None, 2, now=clock())
    repository.list_owner_jobs(authority, None, page["nextCursor"], 50, now=clock())
    assert snapshot() == before and before[1] == 0


def test_a_job_whose_state_changes_moves_its_updated_time(connect, authority, clock):
    (job, _, accepted), = make_jobs(connect, authority, clock, ("novelty-analysis",))
    with connect("research") as conn:
        conn.execute("UPDATE research.job SET fence=fence+1 WHERE id=%s", (job,))
        unmoved = conn.execute("SELECT updated_at FROM research.job WHERE id=%s",
                               (job,)).fetchone()["updated_at"]
        conn.execute("UPDATE research.job SET state='running' WHERE id=%s", (job,))
        moved = conn.execute("SELECT updated_at FROM research.job WHERE id=%s",
                             (job,)).fetchone()["updated_at"]
    assert unmoved == accepted and moved >= accepted
