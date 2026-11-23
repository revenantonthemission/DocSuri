"""A2's owner job list over HTTP (U8 plan Step 40; BR5.4).

`POST /api/v2/c07/list-research-jobs` answers the signed-in owner's research and novelty
jobs, newest first, paged by an opaque cursor, filtered by kind. Another owner's jobs never
appear, a tampered cursor is refused, and reading the list never starts, repeats or
cancels work.
"""

from __future__ import annotations

import json
import os
import stat
from types import SimpleNamespace

import pytest
from docsuri_shared.workspace import wire

from backend.local_profile import private_bytes
from tests.u8_service_operations_integration.host_flows import (
    OTHER_MEMBER,
    assert_bounded_runs,
    by_owner,
    call,
    complete_host,
    counted_post,
    fresh_client,
    make_jobs,
    member,
    session_of,
)

pytestmark = pytest.mark.usefixtures("own_address")
PATH = "/api/v2/c07/list-research-jobs"
KINDS = ("research-turn", "novelty-analysis", "research-turn", "novelty-discussion",
         "research-turn")


@pytest.fixture
def owner_jobs(realm, own_address, sign_in_account, connect):
    with complete_host(realm, address=own_address) as host:
        authority, _ = member(host, sign_in_account)
        jobs = make_jobs(connect, authority.account_id, session_of(connect, authority.account_id),
                         KINDS)
        yield host, authority, jobs


def listed(client, body: dict) -> dict:
    answer = call(client, PATH, body)
    assert answer.status_code == 200, answer.text
    return wire.ResearchJobListPage.model_validate(answer.json()).model_dump(mode="json")


def test_the_list_pages_newest_first_by_its_cursor(owner_jobs):
    host, _, jobs = owner_jobs
    first = listed(host.client, {"limit": 2})
    assert [item["jobId"] for item in first["items"]] == [str(job) for job in jobs[:2]]
    assert first["nextCursor"]
    second = listed(host.client, {"limit": 3, "cursor": first["nextCursor"]})
    assert [item["jobId"] for item in second["items"]] == [str(job) for job in jobs[2:5]]
    item = first["items"][0]
    assert (item["kind"], item["state"], item["resultAvailable"]) == ("research", "accepted",
                                                                       False)
    assert item["label"] == "합성 연구 세션"


def test_the_kind_filter_and_its_refusals(owner_jobs):
    host, _, jobs = owner_jobs
    novelty = listed(host.client, {"kind": "novelty", "limit": 50})
    ours = {str(job) for job in jobs}
    assert {item["kind"] for item in novelty["items"] if item["jobId"] in ours} == {"novelty"}
    assert len([item for item in novelty["items"] if item["jobId"] in ours]) == 2
    assert call(host.client, PATH, {"kind": "digest"}).status_code == 422
    assert call(host.client, PATH, {"limit": 51}).status_code == 422
    first = listed(host.client, {"limit": 1})
    tampered = first["nextCursor"][:-2] + ("AA" if not first["nextCursor"].endswith("AA")
                                           else "BB")
    refused = call(host.client, PATH, {"limit": 1, "cursor": tampered})
    assert refused.status_code == 422 and refused.json()["code"] == "INVALID_ARGUMENT"
    # A cursor cut for one kind is refused for another.
    other_kind = call(host.client, PATH, {"limit": 1, "kind": "novelty",
                                          "cursor": first["nextCursor"]})
    assert other_kind.status_code == 422


def test_another_owner_never_sees_these_jobs(owner_jobs, sign_in_account):
    host, _, jobs = owner_jobs
    with fresh_client(host, address="198.18.250.9") as other:
        member(SimpleNamespace(client=other), sign_in_account, OTHER_MEMBER)
        page = listed(other, {"limit": 50})
    assert not {str(job) for job in jobs} & {item["jobId"] for item in page["items"]}
    with fresh_client(host) as signed_out:
        assert call(signed_out, PATH, {}).status_code == 401


def frames_of(text: str) -> list[dict]:
    """The event stream's frames, each as `{"id", "event", "data"}`."""
    frames = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        frames.append({"id": fields.get("id"), "event": fields.get("event"),
                       "data": json.loads(fields["data"])})
    return frames


def test_the_job_registry_answers_a_research_job_and_its_events(owner_jobs, monkeypatch,
                                                                 sign_in_account, connect):
    import backend.u8_routes as routes

    host, _, jobs = owner_jobs
    snapshot = host.client.get(f"/api/v2/jobs/{jobs[0]}")
    assert snapshot.status_code == 200, snapshot.text
    assert snapshot.headers.get_list("cache-control") == ["no-store"]
    value = wire.JobSnapshot.model_validate(snapshot.json()).model_dump(mode="json")
    assert (value["jobId"], value["kind"], value["state"]) == (str(jobs[0]), "research-turn",
                                                               "accepted")
    assert value["seq"] == 1
    monkeypatch.setattr(routes, "JOB_STREAM_SECONDS", 0.3)
    monkeypatch.setattr(routes, "JOB_POLL_SECONDS", 0.05)
    events = host.client.get(f"/api/v2/jobs/{jobs[0]}/events")
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert events.headers.get_list("cache-control") == ["no-store"]
    assert events.text.count("event: snapshot") == 1 and f"id: {value['seq']}" in events.text
    # Resumed after the last event id: nothing newer to send.
    resumed = host.client.get(f"/api/v2/jobs/{jobs[0]}/events",
                              headers={"last-event-id": str(value["seq"])})
    assert resumed.headers.get_list("cache-control") == ["no-store"]
    assert "event: snapshot" not in resumed.text
    # Advanced through the research owner's own login (research.guard_job_update allows
    # it): the resumed stream sends exactly the newer state, once (L1-14).
    with connect("research") as conn:
        conn.execute("UPDATE research.job SET state='running', seq=2, revision=2 WHERE id=%s",
                     (jobs[0],))
    advanced = host.client.get(f"/api/v2/jobs/{jobs[0]}/events",
                               headers={"last-event-id": "1"})
    assert advanced.status_code == 200
    assert advanced.headers.get_list("cache-control") == ["no-store"]
    snapshots = [frame for frame in frames_of(advanced.text) if frame["event"] == "snapshot"]
    assert len(snapshots) == 1, advanced.text
    assert snapshots[0]["id"] == "2" and snapshots[0]["data"]["state"] == "running"
    # Another owner's job, and an identifier no owner has, answer alike.
    with fresh_client(host, address="198.18.250.11") as other:
        member(SimpleNamespace(client=other), sign_in_account, OTHER_MEMBER)
        foreign = other.get(f"/api/v2/jobs/{jobs[0]}")
        missing = other.get("/api/v2/jobs/00000000-0000-4000-8000-000000000000")
        assert (foreign.status_code, foreign.json()["code"]) == (
            missing.status_code, missing.json()["code"])
        assert other.get("/api/v2/jobs/not-a-uuid").status_code == 422
    with fresh_client(host) as signed_out:
        assert signed_out.get(f"/api/v2/jobs/{jobs[0]}").status_code == 401


def test_a_job_read_after_the_owners_research_consent_ends_is_refused_not_failed(
    owner_jobs, monkeypatch, connect,
):
    """The lifecycle journey's J05 found it: the registry's snapshot ran under the owner's
    current authority but let the database's refusal escape as a 500. A snapshot and an
    event stream now answer 403, and an open stream ends with one closing frame."""
    import backend.u8_routes as routes

    host, authority, jobs = owner_jobs
    monkeypatch.setattr(routes, "JOB_STREAM_SECONDS", 0.3)
    monkeypatch.setattr(routes, "JOB_POLL_SECONDS", 0.05)

    def consent(granted: bool) -> None:
        with connect("accounts") as conn:
            conn.execute("UPDATE accounts.consent SET granted=%s WHERE account_id=%s AND "
                         "purpose='local-research'", (granted, authority.account_id))

    consent(False)
    try:
        snapshot = host.client.get(f"/api/v2/jobs/{jobs[0]}")
        assert (snapshot.status_code, snapshot.json()["code"]) == (403, "FORBIDDEN")
        events = host.client.get(f"/api/v2/jobs/{jobs[0]}/events")
        assert (events.status_code, events.json()["code"]) == (403, "FORBIDDEN")
    finally:
        consent(True)
    assert host.client.get(f"/api/v2/jobs/{jobs[0]}").status_code == 200

    # Withdrawn while the stream is open: its next read closes it with one error frame.
    # The consent ends at the stream's second wait between reads.
    import asyncio

    real, waits = asyncio.sleep, {"count": 0}

    async def sleep(seconds, *args, **kwargs):
        if seconds == routes.JOB_POLL_SECONDS:
            waits["count"] += 1
            if waits["count"] == 2:
                consent(False)
        return await real(seconds, *args, **kwargs)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    try:
        stream = host.client.get(f"/api/v2/jobs/{jobs[0]}/events")
    finally:
        monkeypatch.setattr(asyncio, "sleep", real)
        consent(True)
    assert stream.status_code == 200
    assert stream.text.count("event: snapshot") == 1
    assert "event: error" in stream.text and "FORBIDDEN" in stream.text


def test_each_read_is_one_short_serializable_bounded_transaction(owner_jobs):
    """Step 87(b) (L1-8): a page of 50 is one `accounts` run (the session) and one
    `research` run (the page), each bounded as Step 52(a) proves."""
    host, _, _ = owner_jobs
    answer, runs = counted_post(host, PATH, {"limit": 50})
    assert answer.status_code == 200, answer.text
    assert len(answer.json()["items"]) <= 50
    assert by_owner(runs) == {"accounts": 1, "research": 1}, runs
    assert_bounded_runs(host.composition, ("accounts", "research"))


def test_reading_the_list_never_starts_repeats_or_cancels_work(owner_jobs, connect):
    host, authority, jobs = owner_jobs

    def snapshot():
        with connect("research") as conn:
            return conn.execute(
                "SELECT id,state,updated_at FROM research.job "
                "WHERE owner_id=%s ORDER BY id", (authority.account_id,)).fetchall()

    before = snapshot()
    for _ in range(3):
        listed(host.client, {"limit": 50})
        listed(host.client, {"limit": 2, "kind": "research"})
    assert snapshot() == before


def test_the_served_realms_observer_times_the_routes_owner_gates(
        realm, own_address, sign_in_account, connect, tmp_path):
    """Step 115(b) (CP-6): the served realm's `observe_host_gates` on the complete host
    records the owner gates the routes take, in a private file of this process."""
    from scripts import serve_docsuri_u8 as serve

    path = tmp_path / "gate-waits.json"
    writers = []
    try:
        with complete_host(realm, address=own_address, prepare=lambda composition: writers.append(
                serve.observe_host_gates(composition, path))) as host:
            authority, _ = member(host, sign_in_account)
            make_jobs(connect, authority.account_id,
                      session_of(connect, authority.account_id), ("research-turn",))
            listed(host.client, {"limit": 20})
    finally:
        for writer in writers:
            writer.stop()
    assert len(writers) == 1
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
    value = json.loads(private_bytes(path))
    assert value["pid"] == os.getpid()
    gates = value["gates"]
    for owner in ("accounts", "research"):
        gate = gates[f"normal-owner:{owner}"]
        assert gate["granted"] >= 1 and gate["refused"] == 0, (owner, gate)
    assert gates["owner:accounts"]["holdMsTotal"] > 0
