"""ResearchWorkspace's production execution and service (U8 plan Step 22; your decisions
of 2026-10-24, "Build the research executor" and "Until deleted or erased").

Item 1 runs on the composed realm, a synthetic realm, which keeps U4's built execution.
Items 2–12 run on Step 12's production stand-in (`research_flows.production_research`),
because `PRODUCTION_RESEARCH` refuses every realm but production. No model is called:
the shared runtime's client talks to a mock transport.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import secrets
import threading
from uuid import uuid4, uuid5

import httpx
import pytest
from psycopg.types.json import Jsonb

from backend.modules.research.evidence import SyntheticResearchProvider
from backend.modules.research.execution import ResearchExecution
from backend.modules.research.service import ResearchService
from backend.transactions import UnknownCommit
from backend.u4_policy import SYNTHETIC_RESEARCH
from backend.u8_research import (
    PRODUCTION_RESEARCH,
    ProductionResearchExecution,
    ProductionResearchService,
    capability_rows,
    observation_reader,
)
from docsuri_ops.local_models import MODEL_PINS
from tests.u8_service_operations_integration import research_flows as rf


@pytest.fixture(scope="module")
def env(realm):
    with rf.production_research(realm) as value:
        yield value


@pytest.fixture(autouse=True)
def fresh(env):
    """Each test starts with the runtime answering, a cold availability answer and no job
    of an earlier test due."""
    env.model.chat, env.model.fail, env.model.down = rf.grounded, None, None
    env.model.digests = dict(MODEL_PINS)
    env.provider._answer = None
    yield
    with env.standin.connect("research", autocommit=True) as conn:
        conn.execute("UPDATE research.job SET state='failed',error_code='EXPIRED',"
                     "usage_state='released' WHERE state IN "
                     "('accepted','running','cancel_requested')")


# 1. A synthetic realm keeps U4's built execution and service -------------------------------


def test_the_composed_realm_still_builds_u4s_execution_and_service(realm, transactions):
    from backend.u8_host import (
        BuildContext,
        build_paper_corpus,
        build_paper_journey,
        build_research_workspace,
    )

    ctx = BuildContext(realm, transactions, lambda: dt.datetime.now(dt.UTC), {})
    ctx.parts["paper-journey"] = build_paper_journey(ctx)
    ctx.parts["paper-corpus"] = build_paper_corpus(ctx)
    parts = build_research_workspace(ctx)
    assert type(parts["execution"]) is ResearchExecution
    assert type(parts["service"]) is ResearchService
    assert parts["service"].policy is SYNTHETIC_RESEARCH
    assert isinstance(parts["execution"].provider, SyntheticResearchProvider)
    assert all("synthetic-only" in row["modeIds"] for row in parts["capabilities"])


def test_production_builds_its_own_execution_service_and_rows(env):
    assert isinstance(env.execution, ProductionResearchExecution)
    assert isinstance(env.service, ProductionResearchService)
    assert env.service.policy is PRODUCTION_RESEARCH and env.execution.lane is env.runtime
    assert env.research["capabilities"] == capability_rows()
    rows = {row["id"]: row for row in capability_rows()}
    assert rows["research"]["modeIds"] == ["question", "compare", "quote", "excerpts"]
    assert rows["novelty"]["modeIds"] == ["topic", "excerpts"]
    assert all(row["state"] == "available" and row["languageIds"] == ["ko"]
               and "synthetic-only" not in row["modeIds"] for row in rows.values())


def test_production_research_refuses_without_a_runtime_or_an_embedder(env):
    from backend.u8_host import PolicyUnresolved
    from backend.u8_research import production_research

    ctx = env.standin.context(parts={**env.parts, "paper-corpus": {
        **env.parts["paper-corpus"], "runtime": None}})
    with pytest.raises(PolicyUnresolved, match="policy-unresolved"):
        production_research(ctx)


# 2. A typed failure records failed with its code and releases the usage ------------------


def test_a_typed_failure_records_failed_with_its_code_and_releases_the_usage(env):
    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    env.model.chat = lambda body: httpx.Response(200, json={
        "model": body["model"], "done": True, "done_reason": "length",
        "prompt_eval_count": 900, "eval_count": 1280,
        "message": {"role": "assistant", "content": "{}"}})
    assert rf.run_next(env) == "failed"
    row = rf.job_row(env, turn["jobId"])
    assert (row["state"], row["error_code"], row["usage_state"]) == (
        "failed", "INVALID_CONTENT", "released")
    assert rf.reservation(env, row["usage_id"])["disposition"] == "released"


# 3. A waiting failure cuts the lease, and spent attempts close with its reason ------------


def test_a_waiting_failure_cuts_the_lease_and_spent_attempts_close_with_its_reason(env):
    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    env.model.fail = httpx.ReadTimeout("slow generation")
    assert rf.run_next(env) == "waiting"
    with env.standin.connect("research") as conn:
        waited = conn.execute(
            "SELECT state,attempts,wait_reason,extract(epoch FROM lease_until-clock_timestamp())"
            " AS left FROM research.job WHERE id=%s", (turn["jobId"],)).fetchone()
    assert (waited["state"], waited["attempts"], waited["wait_reason"]) == (
        "running", 1, "DEADLINE_EXCEEDED")
    assert 20 < float(waited["left"]) <= 30  # 30 s between attempts, not the 150 s lease
    assert rf.run_next(env) == "idle"  # its lease holds until then
    for attempt in (2, 3):
        rf.lease_ends(env, turn["jobId"])
        assert rf.run_next(env) == "waiting"
        assert rf.job_row(env, turn["jobId"])["attempts"] == attempt
    rf.lease_ends(env, turn["jobId"])
    assert rf.run_next(env) == "idle"  # no attempt left: never claimed again
    assert env.execution.step()["closed"] == 1
    row = rf.job_row(env, turn["jobId"])
    assert (row["state"], row["error_code"], row["usage_state"]) == (
        "failed", "DEADLINE_EXCEEDED", "released")


# 4. An unknown commit replays once under the derived identifier and settles once --------


def test_an_unknown_commit_replays_once_and_settles_once(env, monkeypatch):
    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    real_run, lost = env.execution.run, []

    def losing(authority, action):
        result = real_run(authority, action)
        if action.__name__ == "complete" and not lost:
            lost.append(True)
            raise UnknownCommit("the commit's answer was lost")
        return result

    settled, real_settle = [], env.execution.usage.settle

    def counting(*args, **kwargs):
        settled.append(args)
        return real_settle(*args, **kwargs)

    monkeypatch.setattr(env.execution, "run", losing)
    monkeypatch.setattr(env.execution.usage, "settle", counting)
    assert rf.run_next(env) == "succeeded" and lost == [True]
    row = rf.job_row(env, turn["jobId"])
    assert (row["state"], row["usage_state"]) == ("succeeded", "settled")
    assert rf.reservation(env, row["usage_id"])["disposition"] == "committed"
    assert len(settled) == 1
    expected = uuid5(row["id"], f"{row['lease_id']}:{row['fence']}:terminal")
    with env.standin.connect("research") as conn:
        keys = [r["operation_key"] for r in conn.execute(
            "SELECT operation_key FROM research.receipt WHERE owner_id=%s AND operation_key "
            "LIKE 'completion:%%'", (owner.account_id,)).fetchall()]
    assert keys == [f"completion:{expected}"]


# 5. A fence moved mid-job discards the output ---------------------------------------------


def test_a_fence_moved_mid_job_discards_the_output(env):
    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))

    def moving(body):
        with env.standin.connect("research", autocommit=True) as conn:
            conn.execute("UPDATE research.job SET fence=fence+1 WHERE id=%s", (turn["jobId"],))
        return rf.grounded(body)

    env.model.chat = moving
    assert rf.run_next(env) == "fenced"
    row = rf.job_row(env, turn["jobId"])
    assert row["state"] == "running" and row["artifact_id"] is None
    with env.standin.connect("research") as conn:
        assert conn.execute("SELECT count(*) AS n FROM research.artifact WHERE job_id=%s",
                            (turn["jobId"],)).fetchone()["n"] == 0


# 6. A cancellation completes while the model is down ---------------------------------------


def test_a_cancellation_completes_while_the_model_is_down(env):
    owner = rf.member(env)
    scope = rf.paper_scope(env, owner, purpose="novelty")
    analysis = rf.accept_analysis(env, owner, scope)
    row = rf.job_row(env, analysis["jobId"])
    env.service.jobs.cancel(owner, row["id"], row["context_id"], row["revision"])
    env.model.down = httpx.ConnectError("the runtime is stopped")
    before = len(env.model.requests)
    assert env.execution.step()["cancelled"] == 1
    row = rf.job_row(env, analysis["jobId"])
    assert (row["state"], row["usage_state"]) == ("cancelled", "released")
    assert len(env.model.requests) == before  # completed without the model


# 7. An ended session closes with EXPIRED ---------------------------------------------------


def test_an_ended_session_closes_with_expired(env):
    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    with env.standin.connect("accounts", autocommit=True) as conn:
        conn.execute("UPDATE accounts.session SET revoked=true WHERE id=%s",
                     (owner.session_id,))
    assert env.execution.step()["closed"] == 1
    row = rf.job_row(env, turn["jobId"])
    assert (row["state"], row["error_code"], row["usage_state"]) == (
        "failed", "EXPIRED", "released")


# 8. The unclaimed bound closes only while the model is down -------------------------------


def test_the_unclaimed_bound_closes_only_while_the_model_is_down(env):
    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    # As if 901 s had passed since acceptance: `accepted_at` is immutable to the owner
    # (U4's guard), so the administrator moves it with triggers off for this statement.
    with env.standin.admin() as conn:
        conn.execute("SET session_replication_role = replica")
        conn.execute("UPDATE research.job SET accepted_at=accepted_at-interval '901 seconds',"
                     "updated_at=updated_at-interval '901 seconds' WHERE id=%s",
                     (turn["jobId"],))
        conn.execute("SET session_replication_role = origin")
    env.execution.step()
    assert rf.job_row(env, turn["jobId"])["state"] == "accepted"  # the model is ready
    env.model.down = httpx.ConnectError("the runtime is stopped")
    env.provider._answer = None
    assert env.execution.step()["closed"] == 1
    row = rf.job_row(env, turn["jobId"])
    assert (row["state"], row["error_code"], row["usage_state"]) == (
        "failed", "DEPENDENCY_UNAVAILABLE", "released")


# 9. step() never calls the provider -------------------------------------------------------


def test_step_and_the_whole_chain_never_call_the_provider(env, monkeypatch):
    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))

    def never(*args, **kwargs):
        raise AssertionError("model work outside the lane")

    monkeypatch.setattr(env.provider, "run", never)
    before = len(env.model.calls("/api/chat"))
    env.execution.step()
    env.research["worker"].run_once(limit=1)
    assert len(env.model.calls("/api/chat")) == before
    assert rf.job_row(env, turn["jobId"])["state"] == "accepted"


# 10. PRODUCTION_RESEARCH refuses any but the production realm -------------------------------


def test_production_research_refuses_any_but_the_production_realm(env, transactions):
    with pytest.raises(ValueError, match="production realm"):
        ProductionResearchExecution(transactions, None, env.provider, lane=env.runtime)
    with pytest.raises(ValueError, match="production realm"):
        ProductionResearchService(transactions, None, execution=None, observed=lambda c: None)
    with pytest.raises(ValueError, match="research policy"):
        ProductionResearchExecution(env.standin.transactions, None, env.provider,
                                    lane=env.runtime, policy=SYNTHETIC_RESEARCH)
    for change in ({"synthetic_only": True}, {"concurrency": 2}, {"retry_seconds": 150},
                   {"text_bytes": 0}, {"policy_id": "another"}, {"durable_drafts": True}):
        with pytest.raises(ValueError):
            dataclasses.replace(PRODUCTION_RESEARCH, **change)
    assert (PRODUCTION_RESEARCH.text_bytes, PRODUCTION_RESEARCH.lease_seconds,
            PRODUCTION_RESEARCH.retry_seconds, PRODUCTION_RESEARCH.unclaimed_seconds,
            PRODUCTION_RESEARCH.concurrency) == (2048, 150, 30, 900, 1)


def test_the_service_enforces_2048_bytes_and_waits_for_a_fresh_ready_observation(env):
    owner = rf.member(env)
    scope = rf.paper_scope(env, owner)
    session = env.service.create_session(owner, {"title": "합성", "scope": scope})
    value = {"sessionId": session["sessionId"], "scope": scope, "mode": "question",
             "text": "가" * 683, "policy": PRODUCTION_RESEARCH.reference()}
    rf.observe(env, "research")
    from backend.modules.research.errors import ResearchError

    with pytest.raises(ResearchError) as refused:
        env.service.accept(owner, uuid4(), value, "research-turn")
    assert refused.value.code == "INVALID_ARGUMENT"  # 2,049 bytes
    rf.observe(env, "research", "degraded", "model-runtime-waiting")
    with pytest.raises(ResearchError) as refused:
        env.service.accept(owner, uuid4(), {**value, "text": "질문"}, "research-turn")
    assert refused.value.code == "DEPENDENCY_UNAVAILABLE"
    # An observation older than its freshness bound reads as none.
    later = env.standin.context(parts=env.parts,
                                clock=lambda: dt.datetime.now(dt.UTC) + dt.timedelta(hours=1))
    assert observation_reader(later)("research") is None
    assert observation_reader(env.standin.context(parts={}))("research") is None


# 11. Results are kept until deleted or erased ---------------------------------------------


def _artifact_under(env, owner, context_id, policy_id: str) -> str:
    """One finished job and its artifact, written as ResearchWorkspace's owner, whose
    `expires_at` is an hour in the past as if the lifetime had passed."""
    job, artifact = uuid4(), uuid4()
    output = {"summary": "s", "evidence": [], "coverage": "abstained", "limitations": ["l"],
              "methodRevision": "m"}
    with env.standin.connect("research", autocommit=True) as conn:
        conn.execute(
            "INSERT INTO research.job(id,owner_id,context_id,session_id,authority_session,kind,"
            "operation_key,input_hash,input,scope,policy,usage_id,state,usage_state) VALUES"
            "(%s,%s,%s,NULL,%s,'novelty-analysis',%s,%s,'{}','{}',%s,%s,'succeeded',"
            "'settled')",
            (job, owner.account_id, context_id, owner.session_id, str(uuid4()),
             secrets.token_hex(32), Jsonb({"policyId": policy_id, "revision": "1"}), uuid4()))
        conn.execute(
            "INSERT INTO research.artifact(id,job_id,context_id,owner_id,content_hash,kind,"
            "output,policy,expires_at) VALUES(%s,%s,%s,%s,%s,'novelty-result',%s,%s,"
            "clock_timestamp()-interval '1 hour')",
            (artifact, job, context_id, owner.account_id, secrets.token_hex(32), Jsonb(output),
             Jsonb({"policyId": policy_id, "revision": "1"})))
    return str(artifact)


def test_production_results_are_kept_until_the_owner_is_erased(env):
    from backend.modules.research.job_list import JobListCursor
    from backend.modules.research.repository import ResearchRepository

    owner = rf.member(env)
    turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
    assert rf.run_next(env) == "succeeded"
    novelty_scope = rf.paper_scope(env, owner, purpose="novelty")
    analysis = rf.accept_analysis(env, owner, novelty_scope)
    assert rf.run_next(env) == "succeeded"
    mark = dt.datetime(9999, 12, 31, tzinfo=dt.UTC)
    rows = [rf.job_row(env, job["jobId"]) for job in (turn, analysis)]
    with env.standin.connect("research") as conn:
        stored = conn.execute("SELECT id,expires_at,availability FROM research.artifact "
                              "WHERE id=ANY(%s)", ([r["artifact_id"] for r in rows],)).fetchall()
    assert {item["expires_at"] for item in stored} == {mark}
    # One artifact under each policy, an hour past its lifetime: the sweep ends only the
    # synthetic one; the production one holds the mark.
    synthetic = _artifact_under(env, owner, novelty_scope["contextId"], "u4-synthetic-research")
    kept = _artifact_under(env, owner, novelty_scope["contextId"], PRODUCTION_RESEARCH.policy_id)
    expired = {str(item["id"]) for item in env.execution.expire_artifacts()}
    assert synthetic in expired and kept not in expired
    with env.standin.connect("research") as conn:
        states = {r["id"]: r["availability"] for r in conn.execute(
            "SELECT id::text AS id,availability FROM research.artifact WHERE "
            "id=ANY(%s::uuid[])", ([synthetic, kept],)).fetchall()}
    assert states == {synthetic: "expired", kept: "ready"}
    # The production results still answer every read.
    for row in rows:
        artifact = env.service.read_artifact(owner, {"artifact": {
            "artifactId": str(row["artifact_id"]), "revision": "1",
            "contentHash": _content_hash(env, row["artifact_id"])}})
        assert artifact["availability"] == "ready"
    novelty_ref = {"artifactId": str(rows[1]["artifact_id"]), "revision": "1",
                   "contentHash": _content_hash(env, rows[1]["artifact_id"])}
    assert env.service.readNoveltyArtifactForExport(owner, novelty_ref)["availability"] == (
        "ready")
    listing = ResearchRepository(env.standin.transactions, job_list_cursor=JobListCursor(
        secrets.token_bytes(32), clock=lambda: dt.datetime.now(dt.UTC))).list_owner_jobs(
        owner, None, None, 20, now=dt.datetime.now(dt.UTC))
    available = {item["jobId"]: item["resultAvailable"] for item in listing["items"]}
    assert available[turn["jobId"]] is True and available[analysis["jobId"]] is True
    rf.observe(env, "novelty")
    discussion = env.service.accept(owner, uuid4(), {
        "source": novelty_ref, "text": "이 결과의 한계는?",
        "policy": PRODUCTION_RESEARCH.reference()}, "novelty-discussion")
    assert discussion["state"] == "accepted"
    _erase(env, owner)
    with env.standin.connect("research") as conn:
        left = conn.execute("SELECT count(*) AS n FROM research.artifact WHERE owner_id=%s",
                            (owner.account_id,)).fetchone()["n"]
    assert left == 0
    from psycopg.errors import InsufficientPrivilege

    from backend.modules.research.errors import ResearchError

    # Nothing answers any more: the erased owner's authority itself is refused.
    with pytest.raises((ResearchError, InsufficientPrivilege)):
        env.service.readNoveltyArtifactForExport(owner, novelty_ref)


def _content_hash(env, artifact_id) -> str:
    with env.standin.connect("research") as conn:
        return conn.execute("SELECT content_hash FROM research.artifact WHERE id=%s",
                            (artifact_id,)).fetchone()["content_hash"]


def _erase(env, owner) -> None:
    """The owner's erasure through ResearchWorkspace's participant, scope by scope, as
    the lifecycle worker applies it."""
    from uuid import UUID

    from backend.modules.accounts.password import get_password_hasher
    from backend.modules.research.control_lifecycle import ResearchLifecycleParticipant
    from backend.u8_host import build_account_controls

    password = "synthetic-production-erasure-" + secrets.token_hex(6)  # per run (L1-36)
    with env.standin.connect("accounts", autocommit=True) as conn:
        conn.execute("UPDATE accounts.account SET lifecycle_state='active',active=true,"
                     "password_hash=%s WHERE id=%s",
                     (get_password_hasher().hash(password), owner.account_id))
        revision = conn.execute("SELECT lifecycle_revision FROM accounts.account WHERE id=%s",
                                (owner.account_id,)).fetchone()["lifecycle_revision"]
    lifecycle = build_account_controls(env.ctx)["lifecycle"]
    request = UUID(lifecycle.request(owner, uuid4(), revision, "erase", password)["requestId"])
    participant = ResearchLifecycleParticipant(env.standin.transactions)
    for scope in ("pending_work", "derived_artifacts", "live_records"):
        if scope == "live_records":
            with env.standin.connect("research", autocommit=True) as conn:
                conn.execute("UPDATE research.job SET usage_state='released' WHERE owner_id=%s "
                             "AND state IN ('failed','succeeded','cancelled')",
                             (owner.account_id,))
        ticket = lifecycle.claim(request, "ResearchWorkspace", scope)
        result = participant.apply(ticket)
        lifecycle.acknowledge(ticket, evidence=UUID(result["evidenceRef"]),
                              reason=result["reasonKey"])


# 12. execute_next's outcomes ------------------------------------------------------------------


def test_execute_next_is_busy_with_the_lane_held_and_idle_with_nothing_due(env):
    assert rf.run_next(env) == "idle"
    held, release = threading.Event(), threading.Event()

    def hold():
        with env.runtime.work(5, wait=0):
            held.set()
            release.wait(5)

    other = threading.Thread(target=hold)
    other.start()
    try:
        assert held.wait(5)
        assert rf.run_next(env) == "busy"
    finally:
        release.set()
        other.join(5)


def test_an_unexpected_error_reaches_the_caller(env, monkeypatch):
    owner = rf.member(env)
    rf.accept_turn(env, owner, rf.paper_scope(env, owner))

    def broken(*args, **kwargs):
        raise RuntimeError("an unexpected provider error")

    monkeypatch.setattr(env.provider, "run", broken)
    with pytest.raises(RuntimeError, match="unexpected provider error"):
        rf.run_next(env)


def test_corpus_research_reads_rank_by_exact_distance_and_name_shared_anchors(env):
    from psycopg.errors import InsufficientPrivilege

    from backend.modules.corpus.repository import CorpusRepository
    from backend.modules.discovery.u8_search import StandinEmbeddings
    from tests.u8_service_operations_integration.host_flows import import_paper

    embed = StandinEmbeddings().embed_query
    chunks = [{"anchor": "a", "section": "S", "text": "alpha one"},
              {"anchor": "a", "section": "S", "text": "alpha two"},
              {"anchor": "b", "section": "S", "text": "beta"},
              {"anchor": "c", "section": "S", "text": "gamma"}]
    ref = import_paper(env.standin, chunks, embed=embed)
    corpus = env.parts["paper-corpus"]["corpus_repository"]
    version = ref["versionId"]
    identity = corpus.research_identity(version)
    assert identity["paper_id"] == ref["paperId"]
    assert str(identity["eligibility_revision"]) == ref["eligibilityRevision"]
    assert identity["source_url"].startswith("https://")
    plain = corpus.research_excerpts(version)
    assert [(r["ordinal"], r["location"]) for r in plain] == [
        (0, "a~1"), (1, "a~2"), (2, "b"), (3, "c")]
    ranked = corpus.research_excerpts(version, vector=embed("beta"), limit=2)
    assert [r["ordinal"] for r in ranked][0] == 2 and len(ranked) == 2
    assert float(ranked[0]["distance"]) < 1e-6  # the exact distance, not an estimate
    assert [(r["ordinal"], r["location"], r["text"]) for r in corpus.research_rows(
        version, [3, 1])] == [(1, "a~2", "alpha two"), (3, "c", "gamma")]
    for bad in ({"limit": 25}, {"limit": 0}, {"vector": [1.0, 2.0]}):
        with pytest.raises(ValueError):
            corpus.research_excerpts(version, **bad)
    with pytest.raises(ValueError):
        corpus.research_rows(version, [])
    CorpusRepository(env.standin.transactions, files=None).withdraw(version)
    with pytest.raises(InsufficientPrivilege):
        corpus.research_excerpts(version)


def test_a_withdrawn_source_fails_the_job_with_source_ineligible(env):
    owner = rf.member(env)
    scope = rf.paper_scope(env, owner)
    turn = rf.accept_turn(env, owner, scope)
    from backend.modules.corpus.repository import CorpusRepository

    CorpusRepository(env.standin.transactions, files=None).withdraw(
        scope["publicPapers"][0]["versionId"])
    assert env.execution.step()["closed"] == 1
    row = rf.job_row(env, turn["jobId"])
    assert (row["state"], row["error_code"]) == ("failed", "SOURCE_INELIGIBLE")


# 13. The circuit breaker over provider.models (U8 plan Step 162(b); L4-4, L4-11) ---------------
#
# The breaker is opened by a stored observation, read back as the composition derives it
# (`readiness.observed_state`) at the real clock, which is the clock `rf.observe` and
# these helpers stamp with; an observation's age is built relative to that same clock.

MODELS = "provider.models"


def observe_models(env, outcome: str, reason: str | None = None, *, age: int = 0) -> None:
    """One stored observation of provider.models, as its producer records it, `age`
    seconds before now."""
    from backend.modules.operations.observations import Observations
    from backend.u8_registry import CAPABILITY_BY_ID

    producer = CAPABILITY_BY_ID[MODELS].producer
    observations = Observations(env.store)
    row = observations.make(
        MODELS, producer, outcome, reason=reason,
        observed_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=age))
    assert observations.record(producer, [row])["written"] == 1


def forget_models(env) -> None:
    """No observation of provider.models is stored (it then reads `unknown`)."""
    with env.standin.admin() as conn:
        conn.execute("DELETE FROM operations.observation_record WHERE capability=%s",
                     (MODELS,))


class ModelsBreaker:
    """The shared runtime reading provider.models' state from the stand-in's stored
    observations, for one test; the runtime is left as it was built."""

    def __init__(self, env):
        self.env = env

    def read(self) -> str:
        from backend.modules.operations.readiness import observed_state
        from backend.u8_policy import PRODUCTION_OPERATIONS

        row = self.env.store.latest([MODELS]).get(MODELS)
        return observed_state(MODELS, row, dt.datetime.now(dt.UTC),
                              PRODUCTION_OPERATIONS).state

    def __enter__(self):
        forget_models(self.env)
        self.env.runtime.observed = self.read
        return self.read

    def __exit__(self, *error) -> None:
        self.env.runtime.observed = None
        forget_models(self.env)


def overdue(env, job_id) -> None:
    """As if 901 s had passed since acceptance, by the database's own clock (the clock
    `_DUE` compares with): the administrator moves the immutable `accepted_at`."""
    with env.standin.admin() as conn:
        conn.execute("SET session_replication_role = replica")
        conn.execute("UPDATE research.job SET accepted_at=accepted_at-interval '901 seconds',"
                     "updated_at=updated_at-interval '901 seconds' WHERE id=%s", (job_id,))
        conn.execute("SET session_replication_role = origin")


def test_while_provider_models_is_observed_unavailable_research_asks_the_runtime_nothing(env):
    """Reliability-design § 10 (lines 133-137, 146), L4-11: research's availability asks
    the breaker first and afresh, outside its kept answer; while provider.models is
    observed unavailable it is False with no request, and it resumes with the probe."""
    with ModelsBreaker(env) as state:
        assert state() == "unknown"
        assert env.provider.available() is True  # asked once; the answer is kept 30 s
        before = len(env.model.requests)
        observe_models(env, "unavailable", "runtime-unreachable")
        assert (state(), env.provider.held()) == ("unavailable", True)
        assert env.provider.available() is False  # over the kept True answer
        env.provider._answer = None
        assert env.provider.available() is False  # and with no kept answer
        assert len(env.model.requests) == before  # nothing reached the runtime
        observe_models(env, "available")
        assert env.provider.available() is True
        assert len(env.model.requests) == before + 1


def test_an_unclaimed_job_waits_while_provider_models_is_observed_unavailable(env):
    """Your answer of 2026-11-22 (L4-4, option 1; reliability-design § 10, line 146):
    while provider.models is observed unavailable, housekeeping closes no unclaimed job
    and asks the runtime nothing, also 900 s after acceptance and with the model down;
    with the state unknown or stale and the model down, the job is closed as built."""
    owner = rf.member(env)
    with ModelsBreaker(env) as state:
        waiting = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
        overdue(env, waiting["jobId"])
        env.model.down = httpx.ConnectError("the runtime is stopped")
        env.provider._answer = None
        observe_models(env, "unavailable", "runtime-unreachable")
        before = len(env.model.requests)
        for _ in range(3):
            assert env.execution.step()["closed"] == 0
        row = rf.job_row(env, waiting["jobId"])
        assert (row["state"], row["attempts"], row["usage_state"]) == (
            "accepted", 0, "reserved")
        assert len(env.model.requests) == before  # housekeeping asked nothing

        # Unknown (nothing observed) and the model down: closed as built, after an ask.
        forget_models(env)
        assert state() == "unknown"
        assert env.execution.step()["closed"] == 1
        row = rf.job_row(env, waiting["jobId"])
        assert (row["state"], row["error_code"], row["usage_state"]) == (
            "failed", "DEPENDENCY_UNAVAILABLE", "released")
        assert len(env.model.requests) > before

        # Stale (an `unavailable` observation older than its 900 s bound): closed too.
        stale = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
        overdue(env, stale["jobId"])
        observe_models(env, "unavailable", "runtime-unreachable", age=901)
        assert state() == "stale"
        env.provider._answer = None
        assert env.execution.step()["closed"] == 1
        row = rf.job_row(env, stale["jobId"])
        assert (row["state"], row["error_code"], row["usage_state"]) == (
            "failed", "DEPENDENCY_UNAVAILABLE", "released")


# 14. Housekeeping behind jobs that wait out an outage (found by the independent check of
# Steps 161 and 162; an addition to 161(d) and 162(b)). On the code before the fix,
# housekeeping read only the oldest `HOUSEKEEPING_ROWS` (4) rows of all three states, and
# held jobs stay accepted and oldest, so neither test's later job was ever read.


def waiting_page(env, count: int) -> list:
    """`count` jobs accepted 901 s ago and never claimed, each by a member of its own on
    the stand-in (a member's period allows one reserved job): more than one page."""
    jobs = []
    for _ in range(count):
        owner = rf.member(env)
        turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
        overdue(env, turn["jobId"])
        jobs.append(turn["jobId"])
    return jobs


def still_waiting(env, jobs) -> bool:
    rows = [rf.job_row(env, job) for job in jobs]
    return all((row["state"], row["attempts"], row["usage_state"]) == (
        "accepted", 0, "reserved") for row in rows)


def test_a_cancel_behind_a_page_of_waiting_jobs_is_finalized_in_one_pass_of_the_outage(env):
    """L4-4, option 1: a waiting job keeps its usage "unless its owner cancels it". With
    more waiting jobs than one housekeeping page, a cancel requested behind them is
    finalized by the next pass and its usage released, while provider.models is still
    observed unavailable; the waiting jobs still wait and the runtime is asked nothing."""
    with ModelsBreaker(env) as state:
        waiting = waiting_page(env, env.execution.housekeeping_rows + 1)
        owner = rf.member(env)
        scope = rf.paper_scope(env, owner, purpose="novelty")
        analysis = rf.accept_analysis(env, owner, scope)
        row = rf.job_row(env, analysis["jobId"])
        env.model.down = httpx.ConnectError("the runtime is stopped")
        env.provider._answer = None
        observe_models(env, "unavailable", "runtime-unreachable")
        env.service.jobs.cancel(owner, row["id"], row["context_id"], row["revision"])
        before = len(env.model.requests)
        assert env.execution.step()["cancelled"] == 1  # within one pass
        row = rf.job_row(env, analysis["jobId"])
        assert (row["state"], row["usage_state"]) == ("cancelled", "released")
        assert state() == "unavailable" and still_waiting(env, waiting)
        assert len(env.model.requests) == before


def test_an_ended_scope_behind_a_page_of_waiting_jobs_is_closed_during_the_outage(env):
    """With more waiting jobs than one housekeeping page, a later job whose session ended
    is closed `EXPIRED` within ceil(open jobs / page) passes while provider.models is
    still observed unavailable; the waiting jobs still wait."""
    with ModelsBreaker(env) as state:
        page = env.execution.housekeeping_rows
        waiting = waiting_page(env, page + 1)
        owner = rf.member(env)
        ended = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
        env.model.down = httpx.ConnectError("the runtime is stopped")
        env.provider._answer = None
        observe_models(env, "unavailable", "runtime-unreachable")
        with env.standin.connect("accounts", autocommit=True) as conn:
            conn.execute("UPDATE accounts.session SET revoked=true WHERE id=%s",
                         (owner.session_id,))
        before = len(env.model.requests)
        passes = -(-(len(waiting) + 1) // page)  # ceil(open jobs / page): 2
        closed = sum(env.execution.step()["closed"] for _ in range(passes))
        assert closed == 1
        row = rf.job_row(env, ended["jobId"])
        assert (row["state"], row["error_code"], row["usage_state"]) == (
            "failed", "EXPIRED", "released")
        assert state() == "unavailable" and still_waiting(env, waiting)
        assert len(env.model.requests) == before
        # Every later pass keeps taking the waiting jobs in turn and closes none.
        assert sum(env.execution.step()["closed"] for _ in range(3)) == 0
        assert still_waiting(env, waiting)


def test_a_state_that_turns_unavailable_during_the_ask_closes_no_unclaimed_job(
        env, monkeypatch):
    """Housekeeping reads the breaker again after a not-ready answer: when the outage is
    observed while the model is being asked (the ask itself fails), the job accepted
    900 s ago is not closed; it waits."""
    owner = rf.member(env)
    with ModelsBreaker(env) as state:
        turn = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
        overdue(env, turn["jobId"])
        env.provider._answer = None
        asked = []

        def observed_during_the_ask(request):
            asked.append(request.url.path)
            observe_models(env, "unavailable", "runtime-unreachable")
            raise httpx.ConnectError("the runtime is stopped")

        monkeypatch.setattr(env.model, "handle", observed_during_the_ask)
        assert state() == "unknown"  # nothing observed when the pass starts
        assert env.execution.step()["closed"] == 0
        assert asked == ["/api/tags"] and state() == "unavailable"
        row = rf.job_row(env, turn["jobId"])
        assert (row["state"], row["attempts"], row["usage_state"]) == (
            "accepted", 0, "reserved")
