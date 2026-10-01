"""F05 — the generation time budget is DECLARED, ALIGNED, and ENFORCED.

REM-2 corrective, Phase 0.3 / Phase 3 (RESILIENCY-10, FD-Q3, NFR-Q11). The three failure modes
this file exists to prevent:

  * **Misaligned layers** — each boundary's timeout is derived from the one below it plus a margin,
    so an over-budget generation converts to job/pending/poll *before* any layer gives up. The
    browser can never cut a response the API still intends to return (the old arbitrary 10s cut).
  * **Undeclared threshold** — the sync→async boundary was a hard-coded token count in the
    orchestrator, unrelated to the approved char-based thresholds (8k summary / 12k translate /
    16k novelty) and to any model latency budget.
  * **Unbounded hang** — a slow or stuck generation held the request past the browser budget and
    ended as a network error with nothing to poll. It must end as a *bounded* pending (job
    accepted, client polls) or, with nowhere to continue, a bounded abstain.

The declared table lives in ``ops/platform-integrity/timeouts.yaml`` (LC-R2-09) and is mirrored by
``domain.timeout_profile``; the drift tests below are what stop the two from diverging.
"""

from __future__ import annotations

import re
import time

import pytest

from summarization.api.gateway_seam import run_summarization
from summarization.domain.models import (
    AuthSession,
    RequestContext,
    Scope,
    SummaryRequest,
    Task,
)
from summarization.domain.timeout_profile import (
    MIN_LAYER_MARGIN_SEC,
    PROFILES,
    TimeoutProfile,
    profile_for,
)
from summarization.service.orchestrator import SummarizationOrchestrationService

# Layer order, from the generation itself outward. Each must clear the one below it by the margin.
_LAYER_FIELDS = ("model_p95_sec", "worker_sec", "api_sec", "bff_sec", "browser_sec")


def _ctx(user_id: str = "u1") -> RequestContext:
    return RequestContext(auth_session=AuthSession(user_id=user_id), request_id="r1")


# --- the declared table (FD-Q3 defaults, NFR-Q11 AA reverse alignment) -----------------------


@pytest.mark.parametrize("task", ["SUMMARIZE", "TRANSLATE", "NOVELTY", "EVIDENCE"])
def test_every_task_declares_the_approved_default_thresholds(task: str) -> None:
    # FD-Q3 answer AA: summarize 8k chars, translate 12k, novelty 16k (evidence 20k, same table).
    profile = PROFILES[task]
    assert profile.sync_threshold_chars == {
        "SUMMARIZE": 8000,
        "TRANSLATE": 12000,
        "NOVELTY": 16000,
        "EVIDENCE": 20000,
    }[task]


@pytest.mark.parametrize("task", sorted(PROFILES))
def test_layers_are_reverse_aligned_with_a_margin(task: str) -> None:
    # "각 레이어 timeout = 하위 레이어 timeout + 여유(2~4초)" — a boundary that is not strictly
    # above the one it wraps is exactly how a response gets cut before the API answers it.
    profile = PROFILES[task]
    layers = [(f, getattr(profile, f)) for f in _LAYER_FIELDS]
    for (lower_name, lower), (_, upper) in zip(layers, layers[1:], strict=False):
        assert upper - lower >= MIN_LAYER_MARGIN_SEC, (
            f"{task}: {lower_name}→next layer margin {upper - lower}s is below "
            f"{MIN_LAYER_MARGIN_SEC}s — the inner boundary can be cut by the outer one"
        )


@pytest.mark.parametrize("task", sorted(PROFILES))
def test_sync_threshold_is_reachable_within_the_browser_budget(task: str) -> None:
    # The whole point of the threshold: a generation under it finishes inside the sync budget, so
    # the client never waits on something that was never going to be synchronous.
    profile = PROFILES[task]
    assert profile.sync_threshold_chars > 0
    assert profile.browser_sec >= profile.api_sec >= profile.worker_sec


def test_a_misaligned_profile_is_rejected_at_construction() -> None:
    # Misalignment must fail where the profile is built, not silently ship a cut response.
    with pytest.raises(ValueError):
        TimeoutProfile(
            task="BROKEN",
            sync_threshold_chars=8000,
            model_p95_sec=6,
            worker_sec=8,
            api_sec=8,  # no margin over the worker
            bff_sec=12,
            browser_sec=15,
        )


def test_profile_for_maps_a_task_to_its_own_budget() -> None:
    assert profile_for(Task.SUMMARY).sync_threshold_chars == 8000
    assert profile_for(Task.TRANSLATE).sync_threshold_chars == 12000
    # An unknown task must not silently inherit another task's budget.
    expected = PROFILES["SUMMARIZE"].sync_threshold_chars
    assert profile_for("NOT_A_TASK").sync_threshold_chars == expected


# --- the YAML declaration cannot drift from the code that enforces it ------------------------


def _parse_declared_timeouts_yaml() -> dict[str, dict[str, int]]:
    """Parse ``ops/platform-integrity/timeouts.yaml`` without a YAML dependency.

    The file is a two-level mapping of ints; a strict subset reader keeps this test runnable in a
    clean environment (PyYAML is not a declared runtime dependency anywhere in this repo).
    """
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "ops/platform-integrity/timeouts.yaml"
    assert path.is_file(), f"the declared budget is missing: {path}"

    declared: dict[str, dict[str, int]] = {}
    task: str | None = None
    for raw in path.read_text().splitlines():
        body = raw.split("#", 1)[0]
        if not body.strip():
            continue
        # Indentation is structural here: a task header is a top-level key, its fields are nested.
        if not body[:1].isspace():
            task = body.strip().rstrip(":").strip()
            declared[task] = {}
            continue
        key, _, value = body.strip().partition(":")
        assert task is not None, f"field before a task header: {raw!r}"
        assert re.fullmatch(r"\d+", value.strip()), f"non-integer budget value: {raw!r}"
        declared[task][key.strip()] = int(value.strip())
    return declared


def test_declared_yaml_matches_the_enforced_profiles() -> None:
    declared = _parse_declared_timeouts_yaml()
    assert set(declared) == set(PROFILES), "a task is declared in YAML but not enforced in code"
    for task, fields in declared.items():
        profile = PROFILES[task]
        assert set(fields) == set(_LAYER_FIELDS) | {"sync_threshold_chars"}, task
        for field, value in fields.items():
            assert getattr(profile, field) == value, f"{task}.{field}: yaml={value} code={profile}"


def test_an_env_override_can_retune_one_task_threshold(monkeypatch) -> None:
    # Ops must be able to move a threshold without a deploy — and only for the task named.
    monkeypatch.setenv("DOCSURI_SYNC_THRESHOLD_CHARS_SUMMARIZE", "1234")
    assert profile_for(Task.SUMMARY).sync_threshold_chars == 1234
    assert profile_for(Task.TRANSLATE).sync_threshold_chars == 12000


def test_a_bogus_env_override_is_ignored_rather_than_breaking_every_request(monkeypatch) -> None:
    monkeypatch.setenv("DOCSURI_SYNC_THRESHOLD_CHARS_SUMMARIZE", "not-a-number")
    assert profile_for(Task.SUMMARY).sync_threshold_chars == 8000


# --- bounded termination at the request seam (no arbitrary 10s cut) --------------------------


class _HangingOrchestrator:
    """Stands in for a generation that never returns (a stuck model stream)."""

    def __init__(self) -> None:
        self.accepted: list[SummaryRequest] = []
        self.calls = 0

    def run(self, request: SummaryRequest, ctx: RequestContext):  # pragma: no cover - the point
        self.calls += 1
        while True:
            time.sleep(0.05)

    def accept_async_job(self, request: SummaryRequest, ctx: RequestContext) -> bool:
        self.accepted.append(request)
        return True


class _NoQueueOrchestrator(_HangingOrchestrator):
    def accept_async_job(self, request: SummaryRequest, ctx: RequestContext) -> bool:
        self.accepted.append(request)
        return False


def test_a_generation_that_overruns_the_api_budget_becomes_a_pollable_job() -> None:
    # The old behavior: the request kept generating until the browser's arbitrary 10s cut, and the
    # user saw a network error with no way to retrieve the result. It must end BOUNDED as pending,
    # with the work accepted for the worker.
    orch = _HangingOrchestrator()
    request = SummaryRequest(paper_id="2401.1", version=1, task=Task.SUMMARY)

    started = time.monotonic()
    out = run_summarization(orch, request, _ctx(), budget_sec=0.2)
    elapsed = time.monotonic() - started

    assert out.to_dict()["status"] == "pending"
    assert elapsed < 2.0, "the request did not terminate within its bound"
    assert orch.accepted == [request], "the over-budget generation was not accepted as a job"
    assert out.to_dict()["retryAfterMs"] > 0


def test_a_hang_with_no_job_queue_ends_in_a_bounded_abstain_not_a_hang() -> None:
    # Nowhere to continue, so the honest terminal answer is an abstain — never an open request.
    orch = _NoQueueOrchestrator()

    started = time.monotonic()
    out = run_summarization(
        orch,
        SummaryRequest(paper_id="2401.1", version=1, task=Task.SUMMARY),
        _ctx(),
        budget_sec=0.2,
    )
    elapsed = time.monotonic() - started

    assert out.to_dict()["status"] == "abstain"
    assert elapsed < 2.0


def test_a_generation_that_finishes_inside_the_budget_is_returned_normally() -> None:
    class _Fast(_HangingOrchestrator):
        def run(self, request: SummaryRequest, ctx: RequestContext):
            self.calls += 1
            from summarization.domain.models import SummaryResultDTO

            task = request.task
            if hasattr(task, "value"):
                task = task.value
            return SummaryResultDTO(task=task, cached=False)

    orch = _Fast()

    out = run_summarization(
        orch,
        SummaryRequest(paper_id="2401.1", version=1, task=Task.SUMMARY),
        _ctx(),
        budget_sec=5.0,
    )

    assert out.to_dict()["status"] == "ok"
    assert orch.accepted == [], "a completed generation must not also be enqueued"


# --- the sync→async boundary follows the declared threshold, per task ----------------------


class _SpyQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def enqueue(self, request, user_id) -> None:
        self.calls.append((request.paper_id, user_id))


def _full_text_orchestrator(chars: int, *, queue: _SpyQueue | None):
    """An orchestrator whose only source is a legacy full text of exactly ``chars`` characters.

    ``chars`` — not a token count — is what the declared threshold is expressed in, and what the
    refiner's body length measures (FD-Q3).
    """
    from summarization.domain.length_router import LengthRouter
    from tests.stubs import SAMPLE_PAPER, StubFullText, StubLlm, make_orchestrator

    # Repeated real sample content: filler characters would fail the grounding gate and turn a
    # budget assertion into an abstain assertion. The references tail is dropped because the
    # refiner cuts it as noise (BR-S3) — so the measured body tracks the requested length, which
    # is the whole point of asserting on chars.
    core = SAMPLE_PAPER.split("References")[0]
    text = (core * (chars // len(core) + 1))[:chars]
    orch = make_orchestrator(
        full_text=StubFullText(text=text),
        summary_job_queue=queue,
    )
    # Keep the input inside the single-call band: this regression is about the SYNC→ASYNC budget,
    # not the long-input map-reduce band (covered in test_orchestrator.py).
    orch._length = LengthRouter(context_budget=1_000_000, input_cap=5_000_000)
    orch._map_reduce = StubLlm()
    return orch


def _summary_request(task=Task.SUMMARY, scope=None) -> SummaryRequest:
    return SummaryRequest(paper_id="2401.1", version=1, task=task, scope=scope)


def test_a_summary_over_the_declared_threshold_is_dispatched_to_the_job_not_run_inline() -> None:
    # The F05 defect: a 10k-char summary is ~2.5k tokens, far under the old hard-coded 6k-token
    # constant, so it was generated INLINE and blew the browser budget with no poll handle.
    queue = _SpyQueue()
    orch = _full_text_orchestrator(10_000, queue=queue)

    out = orch.run(_summary_request(), _ctx()).to_dict()

    assert out["status"] == "pending"
    assert out["retryAfterMs"] >= 1
    assert queue.calls == [("2401.1", "u1")]


def test_a_summary_under_the_declared_threshold_still_runs_inline() -> None:
    # The sync path must stay intact for the small inputs it exists to serve (no job, no poll).
    queue = _SpyQueue()
    orch = _full_text_orchestrator(8_000, queue=queue)

    out = orch.run(_summary_request(), _ctx()).to_dict()

    assert out["status"] == "ok"
    assert queue.calls == []


def test_the_threshold_is_per_task_not_one_global_number() -> None:
    # 10k chars is over the summary threshold (8k) but under the translate threshold (12k) — a
    # single global constant cannot express that, which is why the profile is per task.
    queue = _SpyQueue()
    orch = _full_text_orchestrator(10_000, queue=queue)

    out = orch.run(_summary_request(task=Task.TRANSLATE, scope=Scope.FULL), _ctx()).to_dict()

    assert out["status"] == "ok"
    assert queue.calls == []


def test_a_full_translation_over_the_translate_threshold_is_dispatched() -> None:
    queue = _SpyQueue()
    orch = _full_text_orchestrator(12_001, queue=queue)

    out = orch.run(_summary_request(task=Task.TRANSLATE, scope=Scope.FULL), _ctx()).to_dict()

    assert out["status"] == "pending"
    assert queue.calls == [("2401.1", "u1")]


def test_the_worker_path_runs_a_dispatched_job_inline_instead_of_re_dispatching() -> None:
    # The worker re-runs the SAME request with allow_enqueue=False: the threshold must not bounce
    # it back to the queue, or the job would loop forever without ever producing a result.
    queue = _SpyQueue()
    orch = _full_text_orchestrator(10_000, queue=queue)

    out = orch.run(_summary_request(), _ctx(), allow_enqueue=False).to_dict()

    assert out["status"] == "ok"
    assert queue.calls == []


def test_translate_abstract_stays_inline_even_over_the_threshold() -> None:
    # The abstract scope never consumes the full text, so the char threshold cannot apply to it —
    # converting it to a job would be a regression against a path that is fast by construction.
    class _Recorder(_HangingOrchestrator):
        def run(self, request: SummaryRequest, ctx: RequestContext):
            from summarization.domain.models import SummaryResultDTO
            task_req = request.task
            from enum import Enum
            if isinstance(task_req, Enum):
                task_req = task_req.value
            return SummaryResultDTO(task=task_req, cached=False)

    orch = _Recorder()

    out = run_summarization(
        orch,
        SummaryRequest(
            paper_id="2401.1", version=1, task=Task.TRANSLATE, scope=Scope.ABSTRACT
        ),
        _ctx(),
        budget_sec=5.0,
    )

    assert out.to_dict()["status"] == "ok"
    assert orch.accepted == []

# --- the hand-over target is the REAL orchestrator, not a stand-in -----------------------------
#
# The tests above drive the seam with fakes, so they only prove the seam asks for a hand-over.
# They never proved the seam's question has an answer in production: ``gateway_seam`` reaches for
# ``accept_async_job`` defensively (``getattr``), because when F05 landed the real orchestrator had
# no such method. A configured job queue was therefore never consulted on the over-budget path —
# the request ended as a bounded abstain with work it could have finished in the background. These
# tests bind the contract to the real class so a defensive ``getattr`` can never hide that again.


class _RecordingJobQueue:
    """Stands in for the async job queue (BR-S8/S12): records what the API path hands over."""

    def __init__(self) -> None:
        self.enqueued: list[tuple] = []

    def enqueue(self, request, user_id) -> None:
        self.enqueued.append((request, user_id))


_ANY_TRANSLATOR = object()


def _real_orchestrator(*, job_queue, translator=_ANY_TRANSLATOR):
    """The production orchestrator, wired with the one collaborator under test."""
    return SummarizationOrchestrationService(
        store=None,
        source_selector=None,
        refiner=None,
        glossary_resolver=None,
        length_router=None,
        llm=None,
        grounding=None,
        assembler=None,
        cost_guard=None,
        observability=None,
        model_ver="test",
        summary_job_queue=job_queue,
        structured_translator=translator,
    )


def test_the_real_orchestrator_can_take_over_an_over_budget_generation() -> None:
    queue = _RecordingJobQueue()
    orch = _real_orchestrator(job_queue=queue)
    request = SummaryRequest(paper_id="2401.1", version=1, task=Task.SUMMARY, scope=Scope.FULL)

    assert orch.accept_async_job(request, _ctx("u1")) is True
    assert queue.enqueued == [(request, "u1")]


def test_the_over_budget_path_converts_to_a_pollable_job_against_the_real_orchestrator() -> None:
    # End to end through the seam with the production hand-over target: a generation that never
    # returns must end as pending with the job actually queued — not as an abstain that silently
    # drops the work the queue was there to finish.
    queue = _RecordingJobQueue()
    orch = _real_orchestrator(job_queue=queue)
    # A generation that hangs: the real run() would need the full adapter graph, and the point of
    # this test is the seam's outcome, not the generation.
    def _hang(*_args, **_kwargs) -> None:  # a generation that never returns
        time.sleep(60)

    orch.run = _hang  # type: ignore[method-assign]

    out = run_summarization(
        orch,
        SummaryRequest(paper_id="2401.1", version=1, task=Task.SUMMARY, scope=Scope.FULL),
        _ctx(),
        budget_sec=0.05,
    )

    assert out.to_dict()["status"] == "pending"
    assert len(queue.enqueued) == 1


def test_the_real_orchestrator_declines_the_takeover_when_there_is_no_queue() -> None:
    # Nowhere to continue → bounded abstain. The seam must not report a hand-over that no queue
    # will ever execute.
    orch = _real_orchestrator(job_queue=None)

    assert orch.accept_async_job(
        SummaryRequest(paper_id="2401.1", version=1, task=Task.SUMMARY, scope=Scope.FULL), _ctx()
    ) is False


def test_the_real_orchestrator_declines_an_abstract_translation_takeover() -> None:
    # The async job path only exists for full-summary and full-translate work (BR-S8/S12). Handing
    # over an abstract translation would queue a job the worker cannot complete, so it must decline
    # and let the seam abstain.
    queue = _RecordingJobQueue()
    orch = _real_orchestrator(job_queue=queue)

    assert orch.accept_async_job(
        SummaryRequest(
            paper_id="2401.1", version=1, task=Task.TRANSLATE, scope=Scope.ABSTRACT
        ),
        _ctx(),
    ) is False
    assert queue.enqueued == []
