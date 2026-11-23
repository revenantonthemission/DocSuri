"""The one-model-job lane (U8 plan Step 22; your decision of 2026-10-24, "Build the
research executor").

On Step 12's production stand-in, with the real builders, event-gated mock answers and
the lane's injected clock and sleep, so no test waits for real time:

1. a research job and an assistance job never overlap;
2. a job held open leaves every workers pass under its deadline;
3. while the runtime does not answer, jobs stay accepted with no attempt spent, new
   requests are refused with `DEPENDENCY_UNAVAILABLE`, and research reads
   `model-runtime-waiting`;
4. a failing item is set aside and the next runs;
5. `stop()` returns within its bound with an item in hand;
6. `/api/tags` is asked at most once per 30 s while work waits;
7. a turn that ran no item sleeps once (every owner set aside, as when PostgreSQL is
   down, or assistance only deferring), and repeated set-aside turns back off;
8. (Step 87(c), P8, L1-6) research and novelty accepts through production's accept path
   record the job and answer at once, with no model request inside the call; two
   research jobs never hold the runtime at once; a search embedding answers while a
   research turn holds the lane; each job records its accepting request's identifier,
   and its worker lines name it.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import logging
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from backend.modules.research.errors import ResearchError
from backend.modules.summarization.model_runtime import LaneBusy
from backend.u8_model_lane import (
    BACKOFF_CEILING_SECONDS,
    LaneOwner,
    ModelLane,
    lane_owners,
    model_lane,
)
from backend.u8_policy import PRODUCTION_OPERATIONS
from backend.u8_workers import CompleteWorker, chain_steps
from docsuri_ops.local_models import MODEL_PINS
from tests.u8_service_operations_integration import research_flows as rf
from tests.u8_service_operations_integration.host_flows import (
    import_paper,
    set_flag,
    signal_or_failure,
    write_readiness,
)


def assistant_or_research(body: dict) -> httpx.Response:
    """Paper assistance's answer (cites the first allowed anchor) or research's."""
    import json

    properties = (body.get("format") or {}).get("properties", {})
    if "citations" in properties:
        anchors = properties["citations"]["items"]["enum"]
        content = json.dumps({"text": f"요약입니다 [{anchors[0]}]", "citations": anchors[:1]},
                             ensure_ascii=False)
        return httpx.Response(200, json={
            "model": body["model"], "message": {"role": "assistant", "content": content},
            "done": True, "done_reason": "stop", "prompt_eval_count": 40, "eval_count": 20})
    return rf.grounded(body)


@pytest.fixture(scope="module")
def env(realm):
    with rf.production_research(realm) as value:
        yield value


@pytest.fixture(autouse=True)
def fresh(env):
    env.model.chat, env.model.fail, env.model.down = assistant_or_research, None, None
    env.model.digests = dict(MODEL_PINS)
    env.provider._answer = None
    env.parts["paper-corpus"]["dispatch"].executor._answer = None
    write_readiness(env.standin.profile, {"assistance": rf.DIGEST_EVIDENCE,
                                          "research": rf.DIGEST_EVIDENCE})
    yield
    with env.standin.connect("research", autocommit=True) as conn:
        conn.execute("UPDATE research.job SET state='failed',error_code='EXPIRED',"
                     "usage_state='released' WHERE state IN "
                     "('accepted','running','cancel_requested')")


def composition_of(env):
    from backend.u8_host import environment_of

    return SimpleNamespace(profile=env.standin.profile, parts=env.parts,
                           environment=environment_of(env.standin.profile))


def assistance_job(env, owner):
    """One accepted paper assistance job through production's own catalog and admission."""
    from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
    from backend.modules.summarization.requests import AssistanceRequests

    corpus = env.parts["paper-corpus"]
    ref = import_paper(env.standin, rf.PAPER_CHUNKS)
    source = corpus["corpus_repository"].read(ref["versionId"])
    catalog = corpus["assistance_rule"].catalog(source)
    option = catalog.options()["options"][0]
    glossary = GuardedAssistanceRepository(env.standin.transactions, corpus["files"]
                                           ).current_glossary(owner)["revision"]
    requests = AssistanceRequests(corpus["dispatch"].admission, corpus["corpus_repository"],
                                  corpus["assistance_rule"].catalog)
    return requests.submit(owner, uuid4(), {
        "paper": catalog.paper, "contentRevision": catalog.content_revision,
        "contentHash": source["source_hash"], "operation": option["operation"],
        "optionId": option["optionId"], "optionsRevision": catalog.revision,
        "glossaryRevision": str(glossary), "processingPolicy": catalog.options()["policy"],
    })


def assistance_state(env, job_id) -> str:
    with env.standin.connect("assistance") as conn:
        return conn.execute("SELECT state FROM assistance.job WHERE id=%s",
                            (job_id,)).fetchone()["state"]


class Recorder:
    def __init__(self):
        self.items = []

    def __call__(self, kind, identity, error):
        self.items.append((kind, identity, type(error).__name__))


def lane(env, *, owners=None, clock=None, sleep=None, stop_seconds=10.0, recorder=None):
    return ModelLane(owners or lane_owners(composition_of(env)), runtime=env.runtime,
                     set_aside=recorder or Recorder(), clock=clock or time.monotonic,
                     sleep=sleep, stop_seconds=stop_seconds)


# 1. A research job and an assistance job never overlap -----------------------------------


@contextlib.contextmanager
def request_identifier(value: str):
    """The accepting request's identifier, as the boundary sets it (L1-6)."""
    from backend import local_browser

    token = local_browser.CURRENT_REQUEST_ID.set(value)
    try:
        yield
    finally:
        local_browser.CURRENT_REQUEST_ID.reset(token)


def job_events(caplog, job_id) -> dict:
    """The captured `job.started` and `job.ended` lines of one job, by event."""
    from backend.log_events import EVENTS_LOGGER

    lines = [json.loads(record.getMessage()) for record in caplog.records
             if record.name == EVENTS_LOGGER]
    return {line["event"]: line for line in lines
            if line.get("jobId") == str(job_id)
            and line["event"] in ("job.started", "job.ended")}


def test_a_research_job_and_an_assistance_job_never_overlap(env, caplog):
    from backend.log_events import EVENTS_LOGGER

    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    owner = rf.member(env)
    research_request, assistance_request = str(uuid4()), str(uuid4())
    scope = rf.paper_scope(env, owner)
    with request_identifier(research_request):
        turn = rf.accept_turn(env, owner, scope)
    with request_identifier(assistance_request):
        job = assistance_job(env, owner)
    with env.standin.connect("research") as conn:
        assert str(conn.execute("SELECT origin_request_id FROM research.job WHERE id=%s",
                                (turn["jobId"],)).fetchone()["origin_request_id"]) == (
            research_request)
    with env.standin.connect("assistance") as conn:
        assert str(conn.execute("SELECT origin_request_id FROM assistance.job WHERE id=%s",
                                (job["id"],)).fetchone()["origin_request_id"]) == (
            assistance_request)
    active, peak, refused = [0], [0], []
    guard = threading.Lock()

    def tracked(body):
        with guard:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        try:
            # Another thread cannot take the lane while this job holds it.
            other = threading.Thread(target=lambda: refused.append(
                pytest.raises(LaneBusy, lambda: env.runtime.work(1, wait=0).__enter__())))
            other.start()
            other.join(5)
            return assistant_or_research(body)
        finally:
            with guard:
                active[0] -= 1

    env.model.chat = tracked
    done = lane(env).turn()
    assert done == {"research": "succeeded", "assistance": {"executed": 1, "deferred": 0}}
    assert peak == [1] and len(refused) >= 2
    assert rf.job_row(env, turn["jobId"])["state"] == "succeeded"
    assert assistance_state(env, job["id"]) == "succeeded"
    # Each job's lines name it and its accepting request (L1-6).
    for job_id, origin in ((turn["jobId"], research_request), (job["id"], assistance_request)):
        lines = job_events(caplog, job_id)
        assert set(lines) == {"job.started", "job.ended"}, (job_id, lines)
        assert {line["requestId"] for line in lines.values()} == {origin}


# Accepts record the job and answer at once (Step 87(c), P8) -------------------------------


def accepted_at_once(env, owner, value: dict, kind: str) -> dict:
    """One accept through production's own accept path (`ProductionResearchService`):
    answered `accepted`, with no model request of any path inside the call; the job, its
    dispatch row and its admission row written in one transaction; the same key and body
    answering the same job with one job row and one reservation."""
    key = uuid4()
    before = len(env.model.requests)
    reserved_before = reservations_of(env, owner)
    answer = env.service.accept(owner, key, value, kind)
    assert answer["state"] == "accepted", answer
    assert len(env.model.requests) == before
    with env.standin.connect("research") as conn:
        job = conn.execute(
            "SELECT xmin::text AS x,attempts,lease_until,operation_key,usage_id FROM "
            "research.job WHERE id=%s", (answer["jobId"],)).fetchone()
        dispatch = conn.execute("SELECT xmin::text AS x FROM research.dispatch WHERE "
                                "job_id=%s", (answer["jobId"],)).fetchone()
        admission = conn.execute("SELECT xmin::text AS x,state FROM research.admission "
                                 "WHERE operation_id=%s", (answer["jobId"],)).fetchone()
    assert (job["attempts"], job["lease_until"], job["operation_key"]) == (0, None, str(key))
    assert job["x"] == dispatch["x"] == admission["x"]
    assert admission["state"] == "accepted"
    reserved_after = reservations_of(env, owner)
    assert len(reserved_after) == len(reserved_before) + 1
    assert job["usage_id"] in reserved_after  # the one the accept made
    again = env.service.accept(owner, key, value, kind)
    assert again["jobId"] == answer["jobId"]
    assert len(env.model.requests) == before
    with env.standin.connect("research") as conn:
        assert conn.execute("SELECT count(*) AS n FROM research.job WHERE owner_id=%s AND "
                            "operation_key=%s", (owner.account_id, str(key))
                            ).fetchone()["n"] == 1
    # The replay added no reservation of the owner's, under any id (the batch-7 review:
    # counting by the reservation's own primary key could never see a second one).
    assert reservations_of(env, owner) == reserved_after
    return answer


def reservations_of(env, owner) -> set:
    """Every usage.reservation id the owner holds."""
    with env.standin.admin() as conn:
        rows = conn.execute("SELECT id FROM usage.reservation WHERE account_id=%s",
                            (owner.account_id,)).fetchall()
    return {row[0] for row in rows}


def claimed_by_the_next_turn(env, job_id) -> None:
    done = lane(env).turn()
    assert done["research"] == "succeeded", done
    row = rf.job_row(env, job_id)
    assert row["state"] == "succeeded" and row["attempts"] >= 1


def test_research_and_novelty_accepts_record_the_job_and_answer_at_once(env):
    from backend.u8_research import PRODUCTION_RESEARCH

    owner = rf.member(env)
    scope = rf.paper_scope(env, owner)
    rf.observe(env, "research")
    session = env.service.create_session(owner, {"title": "합성 연구", "scope": scope})
    turn = accepted_at_once(env, owner, {
        "sessionId": session["sessionId"], "scope": scope, "mode": "question",
        "text": "어텐션은 무엇을 하나요?", "policy": PRODUCTION_RESEARCH.reference()},
        "research-turn")
    claimed_by_the_next_turn(env, turn["jobId"])
    rf.observe(env, "novelty")
    analysis = accepted_at_once(env, owner, {
        "scope": rf.paper_scope(env, owner, purpose="novelty"), "inputMode": "topic",
        "text": "어텐션 기반 번역", "policy": PRODUCTION_RESEARCH.reference()},
        "novelty-analysis")
    claimed_by_the_next_turn(env, analysis["jobId"])
    artifact = rf.job_row(env, analysis["jobId"])["artifact_id"]
    with env.standin.connect("research") as conn:
        content = conn.execute("SELECT content_hash FROM research.artifact WHERE id=%s",
                               (artifact,)).fetchone()["content_hash"]
    rf.observe(env, "novelty")
    discussion = accepted_at_once(env, owner, {
        "source": {"artifactId": str(artifact), "revision": "1", "contentHash": content},
        "text": "이 결과의 한계는?", "policy": PRODUCTION_RESEARCH.reference()},
        "novelty-discussion")
    claimed_by_the_next_turn(env, discussion["jobId"])


def test_two_research_jobs_never_hold_the_runtime_at_once(env):
    owner = rf.member(env)
    first = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    second = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    started, release = threading.Event(), threading.Event()
    active, peak, guard = [0], [0], threading.Lock()

    def held(body):
        with guard:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        try:
            if not started.is_set():
                started.set()
                release.wait(20)
            return assistant_or_research(body)
        finally:
            with guard:
                active[0] -= 1

    env.model.chat = held
    running = lane(env)
    running.start()
    try:
        assert started.wait(10)
        assert lane(env).turn()["research"] == "busy"
        row = rf.job_row(env, second["jobId"])
        assert (row["state"], row["attempts"]) == ("accepted", 0)
    finally:
        release.set()
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and rf.job_row(env, second["jobId"])["state"] != (
                "succeeded"):
            time.sleep(0.1)
    finally:
        assert running.stop()
    one, two = rf.job_row(env, first["jobId"]), rf.job_row(env, second["jobId"])
    assert (one["state"], two["state"]) == ("succeeded", "succeeded")
    assert one["updated_at"] <= two["updated_at"]
    assert peak == [1]


def test_a_search_embedding_answers_while_a_research_turn_holds_the_lane(env):
    from backend.u8_host import build_paper_corpus

    corpus = build_paper_corpus(env.ctx)
    assert corpus["runtime"] is not env.parts["paper-corpus"]["runtime"]
    owner = rf.member(env)
    rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    started, release, order = threading.Event(), threading.Event(), []

    def held(body):
        started.set()
        release.wait(20)
        order.append("chat")
        return assistant_or_research(body)

    env.model.chat = held
    running = lane(env)
    running.start()
    try:
        assert started.wait(10)
        embeds = len(env.model.calls("/api/embed"))
        vector = corpus["embedder"].embed_query("어텐션")
        assert len(vector) == 1024
        assert len(env.model.calls("/api/embed")) == embeds + 1
        order.append("embed")
    finally:
        release.set()
        assert running.stop()
    assert order == ["embed", "chat"]


# 2. A job held open leaves every workers pass under its deadline ------------------------


def test_a_job_held_open_leaves_every_workers_pass_under_its_deadline(env):
    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    started, release = threading.Event(), threading.Event()

    def held(body):
        started.set()
        release.wait(20)
        return assistant_or_research(body)

    env.model.chat = held
    running = lane(env)
    running.start()
    try:
        assert started.wait(10)
        worker = CompleteWorker(env.research["worker"], model_work_in_lane=True,
                                set_aside=Recorder())
        for _ in range(3):
            began = time.monotonic()
            summary = worker.run_once(limit=1)
            assert time.monotonic() - began < worker.bounds["chained"]
            assert summary["chained"]["setAside"] == []
            assert "assistance-dispatch" not in summary["chained"]["steps"]
            assert "research-execution" in summary["chained"]["steps"]
        assert rf.job_row(env, turn["jobId"])["state"] == "running"  # still the lane's
    finally:
        release.set()
        assert running.stop()
    assert rf.job_row(env, turn["jobId"])["state"] == "succeeded"


def test_in_production_the_pass_leaves_model_work_to_the_lane():
    chained = SimpleNamespace(maintenance=None, dispatch=None, dispositions=None,
                              admission=None)
    names = [name for name, _ in chain_steps(chained, 1)]
    lane_names = [name for name, _ in chain_steps(chained, 1, model_work_in_lane=True)]
    assert "assistance-dispatch" in names and "assistance-dispatch" not in lane_names
    with pytest.raises(ValueError, match="step by step"):
        CompleteWorker(chained, model_work_in_lane=True)


# 3. While the runtime does not answer -----------------------------------------------------


def test_while_the_runtime_does_not_answer_jobs_wait_and_new_requests_are_refused(env):
    from backend.modules.operations.observations import Observations
    from backend.modules.operations.producers import ProducerSchedule, ResearchProducer

    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    env.model.down = httpx.ConnectError("the runtime is stopped")
    done = lane(env).turn()
    assert done["research"] == "skipped"
    row = rf.job_row(env, turn["jobId"])
    assert (row["state"], row["attempts"]) == ("accepted", 0)
    states = {"provider.models": "unavailable"}
    producers = [ResearchProducer(name, env.standin.transactions, env.standin.profile,
                                  lambda: states["provider.models"])
                 for name in ("research", "novelty")]
    schedule = ProducerSchedule(producers, Observations(env.store), PRODUCTION_OPERATIONS,
                                lambda: dt.datetime.now(dt.UTC))
    assert sorted(schedule.run_due()) == ["novelty", "research"]
    latest = env.store.latest(["research", "novelty"])
    assert {row["reason_key"] for row in latest.values()} == {"model-runtime-waiting"}
    scope = rf.paper_scope(env, owner)
    session = env.service.create_session(owner, {"title": "합성", "scope": scope})
    with pytest.raises(ResearchError) as refused:
        env.service.accept(owner, uuid4(), {
            "sessionId": session["sessionId"], "scope": scope, "mode": "question",
            "text": "질문", "policy": env.service.policy.reference()}, "research-turn")
    assert refused.value.code == "DEPENDENCY_UNAVAILABLE"
    # The marker without `research` waits too; with both, research is available again.
    states["provider.models"] = "available"
    write_readiness(env.standin.profile, {"assistance": rf.DIGEST_EVIDENCE})
    assert producers[0].observe(dt.datetime.now(dt.UTC)).reason == "model-runtime-waiting"
    write_readiness(env.standin.profile, {"assistance": rf.DIGEST_EVIDENCE,
                                          "research": rf.DIGEST_EVIDENCE})
    assert producers[0].observe(dt.datetime.now(dt.UTC)).outcome == "available"


# 4. A failing item is set aside and the next runs ---------------------------------------


def test_a_failing_item_is_set_aside_and_the_next_owner_runs(env, monkeypatch):
    owner = rf.member(env)
    rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    job = assistance_job(env, owner)

    def broken(**kwargs):
        raise RuntimeError("an item that cannot be processed")

    monkeypatch.setattr(env.execution, "execute_next", broken)
    recorder = Recorder()
    done = lane(env, owners=lane_owners(composition_of(env)), recorder=recorder).turn()
    assert done["research"] == "set-aside"
    assert recorder.items == [("model-lane:research", "turn", "RuntimeError")]
    assert done["assistance"] == {"executed": 1, "deferred": 0}
    assert assistance_state(env, job["id"]) == "succeeded"


# 5. stop() returns within its bound with an item in hand --------------------------------


def test_stop_returns_within_its_bound_and_leaves_the_item_to_its_lease(env):
    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    started, release = threading.Event(), threading.Event()

    def held(body):
        started.set()
        release.wait(20)
        return assistant_or_research(body)

    env.model.chat = held
    running = lane(env, stop_seconds=0.5)
    assert running.status() == {"state": "idle"}  # building it started nothing
    running.start()
    try:
        assert started.wait(10)
        began = time.monotonic()
        assert running.stop() is False  # the item is still in hand
        assert time.monotonic() - began < 1.5
        assert rf.job_row(env, turn["jobId"])["state"] == "running"  # left to its lease
    finally:
        release.set()
        running._thread.join(20)
    assert running.status()["state"] == "stopped"


def test_a_lane_that_stopped_without_being_asked_reads_behind_its_deadline(env):
    def broken(_):
        raise SystemExit  # not an Exception: the thread itself ends

    owner = LaneOwner("research", lambda: True, lambda: True, broken)
    running = lane(env, owners=[owner])
    running.start()
    running._thread.join(5)
    assert running.status() == {"state": "deadline"}
    with pytest.raises(RuntimeError):
        running.start()
    assert running.stop() is True


# 6. /api/tags is asked at most once per 30 s while work waits ---------------------------


def test_tags_are_asked_at_most_once_per_30_seconds_while_work_waits(env, monkeypatch):
    owner = rf.member(env)
    rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    env.model.digests = {**MODEL_PINS, "qwen3:8b": "4" * 64}  # the pin does not match
    now = [0.0]
    monkeypatch.setattr(env.provider, "clock", lambda: now[0])
    env.provider._answer = None
    research = [o for o in lane_owners(composition_of(env)) if o.name == "research"]
    waiting = lane(env, owners=research, clock=lambda: now[0])
    before = len([r for r in env.model.requests if r.url.path == "/api/tags"])
    for _ in range(30):  # 60 s of turns, 2 s apart (the lane's poll)
        assert waiting.turn() == {"research": "skipped"}
        now[0] += 2.0
    asked = len([r for r in env.model.requests if r.url.path == "/api/tags"]) - before
    assert 1 <= asked <= 2


# 7. A turn that ran no item sleeps ------------------------------------------------------------


class QuietRuntime:
    """The runtime's lane with nothing behind it: `work` hands out a deadline."""

    def __init__(self):
        self.taken = 0

    def work(self, seconds, *, wait):
        import contextlib

        self.taken += 1
        return contextlib.nullcontext(time.monotonic() + seconds)


def run_turns(lane_value: ModelLane, turns: int) -> list[float]:
    """The lane's own loop (`_run`) on the injected sleep: each sleep is recorded, and
    the lane is asked to stop from the sleep that follows its `turns`-th turn (each case
    ends on a turn that ran nothing)."""
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        if lane_value.turns >= turns:
            lane_value.stop()

    lane_value._sleep = sleep
    lane_value._run()
    return slept


def database_down():
    raise ConnectionError("the database is not answering")


def test_a_turn_where_every_owner_raises_sleeps_and_backs_off():
    recorder = Recorder()
    owners = [LaneOwner("research", database_down, lambda: True, lambda deadline: "succeeded"),
              LaneOwner("assistance", database_down, lambda: True, lambda deadline: {})]
    quiet = ModelLane(owners, runtime=QuietRuntime(), set_aside=recorder,
                      clock=time.monotonic, poll_seconds=2.0)
    slept = run_turns(quiet, 7)
    # One sleep per turn, doubling from the poll up to the ceiling: never a spin.
    assert quiet.turns == 7 and len(slept) == 7
    assert slept == [2.0, 4.0, 8.0, 16.0, 32.0, BACKOFF_CEILING_SECONDS,
                     BACKOFF_CEILING_SECONDS]
    assert quiet.last == {"research": "set-aside", "assistance": "set-aside"}
    assert len(recorder.items) == 14 and {kind for kind, _, _ in recorder.items} == {
        "model-lane:research", "model-lane:assistance"}


def test_a_turn_where_assistance_only_defers_sleeps_once():
    runtime = QuietRuntime()
    owners = [LaneOwner("assistance", lambda: True, lambda: True,
                        lambda deadline: {"executed": 0, "deferred": 1})]
    quiet = ModelLane(owners, runtime=runtime, set_aside=Recorder(), clock=time.monotonic,
                      poll_seconds=2.0)
    slept = run_turns(quiet, 3)
    assert quiet.turns == 3 and slept == [2.0, 2.0, 2.0]
    assert runtime.taken == 3  # the row was offered each turn, and nothing ran


def test_a_turn_that_ran_an_item_does_not_sleep_and_ends_the_backoff():
    outcomes = iter([RuntimeError("down"), RuntimeError("down"), "succeeded",
                     RuntimeError("down"), "idle"])

    def run_one(deadline):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    owners = [LaneOwner("research", lambda: True, lambda: True, run_one)]
    quiet = ModelLane(owners, runtime=QuietRuntime(), set_aside=Recorder(),
                      clock=time.monotonic, poll_seconds=2.0)
    slept = run_turns(quiet, 5)
    # set-aside, set-aside, an item ran (no sleep, back-off ended), set-aside, idle.
    assert slept == [2.0, 4.0, 2.0, 2.0]


# The lane's place in the workers role -------------------------------------------------------


def test_model_lane_is_built_for_production_only_and_starts_nothing(env, realm):
    built = model_lane(composition_of(env))
    assert isinstance(built, ModelLane) and built.status() == {"state": "idle"}
    assert [owner.name for owner in built.owners] == ["research", "assistance"]
    synthetic = SimpleNamespace(profile=realm, parts={})
    assert model_lane(synthetic) is None
    assert model_lane(SimpleNamespace(profile=env.standin.profile, parts={})) is None


def test_run_workers_starts_and_stops_the_model_lane_beside_the_export_lane(realm,
                                                                          monkeypatch):
    from backend import u8_model_lane
    from backend.u8_host import compose, run_workers

    events = []
    started = threading.Event()

    class FakeLane:
        def start(self):
            events.append("start")
            started.set()

        def stop(self):
            events.append("stop")
            return True

        def status(self):
            return {"state": "running"}

    monkeypatch.setattr(u8_model_lane, "model_lane", lambda composition: FakeLane())
    composition = compose(realm, process="workers")
    try:
        async def once():
            stopping = asyncio.Event()
            task = asyncio.create_task(run_workers(composition, stopping, watch_seconds=0.1))
            # Stopped once the lane has started, never after a fixed time.
            await signal_or_failure(set_flag(started), task, 10, "the model lane never started")
            stopping.set()
            await task

        asyncio.run(once())
    finally:
        composition.close()
    assert events == ["start", "stop"]


# 9. The circuit breaker over provider.models (U8 plan Step 162(c); L4-11) -----------------------


def test_while_provider_models_is_observed_unavailable_accepted_jobs_wait_and_nothing_reaches_the_runtime(  # noqa: E501
        env):
    """Reliability-design § 10 (lines 133-137, 146), L4-11: while provider.models is
    observed unavailable the lane claims nothing: accepted jobs wait with no attempt
    spent and no request reaches the runtime, also over kept availability answers and
    while the runtime itself answers normally. Once the probe passes, the jobs run. The
    breaker is opened by the real producer's own observation each time, and the state is
    derived from the stored rows as the composition derives it, at the real clock."""
    from backend.modules.operations.observations import Observations
    from backend.modules.operations.producers import (
        ModelsProducer,
        OllamaTags,
        ProducerSchedule,
    )
    from backend.modules.operations.readiness import observed_state
    from backend.modules.summarization.model_runtime import EMBEDDING_MODEL
    from backend.u8_outward import install_models_breaker

    capability = "provider.models"

    def states() -> dict:
        row = env.store.latest([capability]).get(capability)
        return {capability: observed_state(
            capability, row, dt.datetime.now(dt.UTC), PRODUCTION_OPERATIONS).brief()}

    def probe() -> dict:
        """One observation through the producer and its own client, then the state."""
        schedule = ProducerSchedule(
            [ModelsProducer(OllamaTags(), PRODUCTION_OPERATIONS)], Observations(env.store),
            PRODUCTION_OPERATIONS, lambda: dt.datetime.now(dt.UTC))
        assert schedule.run_due() == [capability]
        return states()[capability]

    def forget() -> None:
        with env.standin.admin() as conn:
            conn.execute("DELETE FROM operations.observation_record WHERE capability=%s",
                         (capability,))

    def run_until_done(turn_job, assistance) -> None:
        for _ in range(4):
            lane(env).turn()
            if (rf.job_row(env, turn_job)["state"] == "succeeded"
                    and assistance_state(env, assistance) == "succeeded"):
                return
        raise AssertionError("the waiting jobs did not run once the probe passed")

    executor = env.parts["paper-corpus"]["dispatch"].executor
    owner = rf.member(env)
    forget()
    install_models_breaker(env.parts, states)
    try:
        turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
        job = assistance_job(env, owner)
        waiting = assistance_state(env, job["id"])
        # Both availability answers are kept True before the outage is observed.
        assert env.provider.available() is True and executor.available() is True
        env.model.down = httpx.ConnectError("the model runtime is not answering")
        assert probe() == {"state": "unavailable", "reason": "runtime-unreachable"}
        env.model.down = None  # the runtime answers normally again; nothing observed yet
        before = len(env.model.requests)
        for _ in range(3):
            assert lane(env).turn() == {"research": "skipped", "assistance": "skipped"}
        row = rf.job_row(env, turn["jobId"])
        assert (row["state"], row["attempts"]) == ("accepted", 0)
        assert assistance_state(env, job["id"]) == waiting
        assert len(env.model.requests) == before  # nothing reached the runtime
        assert probe()["state"] == "available"
        run_until_done(turn["jobId"], job["id"])

        # The search model's digest alone is wrong: the generation model's own check
        # would pass, and only the observed state holds the jobs. A second member,
        # because the first has spent its period's usage.
        owner = rf.member(env)
        turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
        job = assistance_job(env, owner)
        env.provider._answer = executor._answer = None  # no kept answer either way
        env.model.digests = {**MODEL_PINS, EMBEDDING_MODEL: "0" * 64}
        assert probe() == {"state": "unavailable", "reason": "model-evidence-mismatch"}
        before = len(env.model.requests)
        for _ in range(3):
            assert lane(env).turn() == {"research": "skipped", "assistance": "skipped"}
        row = rf.job_row(env, turn["jobId"])
        assert (row["state"], row["attempts"]) == ("accepted", 0)
        assert len(env.model.requests) == before
        env.model.digests = dict(MODEL_PINS)
        assert probe()["state"] == "available"
        run_until_done(turn["jobId"], job["id"])
    finally:
        env.runtime.observed = None
        forget()
