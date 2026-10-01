"""Declared, reverse-aligned generation time budgets (FD-Q3 / NFR-Q11, LC-R2-09).

A generation crosses five boundaries — the model call, the worker, the API, the BFF, the browser —
and each must clear the one it wraps, or a response the API still intends to return gets cut into a
504 by an outer layer. NFR-Q11's answer (AA) fixes the shape of the table: each layer's timeout is
the layer below it plus a margin, and the sync→async threshold is derived from model p95 latency.

The numbers are declared once, here, and mirrored in ``ops/platform-integrity/timeouts.yaml`` (the
LC-R2-09 config the operator tunes). ``tests/test_timeout_budget.py`` fails if the two diverge, so
the declaration cannot drift from the behaviour. Neither location is a hard-coded constant inside a
service: this module is the single place the policy is expressed, and ops can retune a threshold per
task at deploy time through ``DOCSURI_SYNC_THRESHOLD_CHARS_<TASK>``.

Before this unit the sync→async boundary was a token count buried in the orchestrator
(``> 6_000 tokens`` ≈ 24k chars), unrelated to the approved 8k/12k/16k char thresholds: a 10k-char
summary was considered "small" and generated inline, blowing the browser budget while the client
had no poll handle to wait on.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .models import Task

# Client re-poll hint after work was dispatched to the background job (BR-S6/BR-S8). Declared next
# to the budget table because it is part of the same chain: a poll cadence has to leave the browser
# room for several attempts inside ``browser_sec``, or the client gives up before the worker lands.
POLL_BACKOFF_MS = 3000

# Minimum gap between consecutive layers of the reverse table (NFR-Q11 AA: "여유 2~4초"). The
# margin is what keeps an outer boundary from expiring while the inner one is still working.
MIN_LAYER_MARGIN_SEC = 2


@dataclass(frozen=True, slots=True)
class TimeoutProfile:
    """One task's budget: where sync stops being viable, and each layer's own bound.

    ``sync_threshold_chars`` is the measured cost of the INPUT (FD-Q3: DocModel/derived text char
    count), so the decision is made before any LLM spend. ``model_p95_sec`` is what that threshold
    is calibrated against; the remaining fields are the outward chain.
    """

    task: str
    sync_threshold_chars: int
    model_p95_sec: int
    worker_sec: int
    api_sec: int
    bff_sec: int
    browser_sec: int

    def __post_init__(self) -> None:
        if self.sync_threshold_chars < 1:
            raise ValueError(f"{self.task}: sync_threshold_chars must be positive")
        previous_name, previous = None, None
        for field in ("model_p95_sec", "worker_sec", "api_sec", "bff_sec", "browser_sec"):
            value = getattr(self, field)
            if value < 1:
                raise ValueError(f"{self.task}: {field} must be positive")
            if previous is not None and value - previous < MIN_LAYER_MARGIN_SEC:
                raise ValueError(
                    f"{self.task}: {field} ({value}s) must exceed {previous_name} "
                    f"({previous}s) by at least {MIN_LAYER_MARGIN_SEC}s — otherwise the inner "
                    "boundary is abandoned while still working"
                )
            previous_name, previous = field, value

    def with_sync_threshold(self, chars: int) -> TimeoutProfile:
        return TimeoutProfile(
            task=self.task,
            sync_threshold_chars=chars,
            model_p95_sec=self.model_p95_sec,
            worker_sec=self.worker_sec,
            api_sec=self.api_sec,
            bff_sec=self.bff_sec,
            browser_sec=self.browser_sec,
        )


# The declared table. Values are the approved FD-Q3 defaults and NFR-Q11 AA reverse alignment;
# ops/platform-integrity/timeouts.yaml carries the same numbers for the platform side.
PROFILES: dict[str, TimeoutProfile] = {
    "SUMMARIZE": TimeoutProfile(
        task="SUMMARIZE",
        sync_threshold_chars=8_000,
        model_p95_sec=6,
        worker_sec=8,
        api_sec=10,
        bff_sec=12,
        browser_sec=15,
    ),
    "TRANSLATE": TimeoutProfile(
        task="TRANSLATE",
        sync_threshold_chars=12_000,
        model_p95_sec=6,
        worker_sec=8,
        api_sec=10,
        bff_sec=12,
        browser_sec=15,
    ),
    "NOVELTY": TimeoutProfile(
        task="NOVELTY",
        sync_threshold_chars=16_000,
        model_p95_sec=10,
        worker_sec=14,
        api_sec=18,
        bff_sec=22,
        browser_sec=30,
    ),
    "EVIDENCE": TimeoutProfile(
        task="EVIDENCE",
        sync_threshold_chars=20_000,
        model_p95_sec=12,
        worker_sec=16,
        api_sec=20,
        bff_sec=24,
        browser_sec=30,
    ),
}

_TASK_BY_ENUM = {Task.SUMMARY: "SUMMARIZE", Task.TRANSLATE: "TRANSLATE"}
# Fallback for a caller outside the summarization vocabulary (novelty/evidence ask for their own
# profiles); an unrecognized task is NOT silently given another task's threshold for its own field.
_DEFAULT_TASK = "SUMMARIZE"
_FALLBACK_THRESHOLD_CHARS = 16_000


def profile_for(task: object) -> TimeoutProfile:
    """The budget for ``task``, with an optional per-task env override.

    ``DOCSURI_SYNC_THRESHOLD_CHARS_<TASK>`` (e.g. ``..._SUMMARIZE``) lets ops retune one threshold
    without a code change. A malformed value is ignored rather than allowed to break every request
    on that task — the declared default stays in force and the mistake is visible in the value.
    """
    name = _TASK_BY_ENUM.get(task, _DEFAULT_TASK if not isinstance(task, str) else task.upper())
    profile = PROFILES.get(name, PROFILES[_DEFAULT_TASK])
    if not isinstance(task, str) and task not in _TASK_BY_ENUM:
        # Novelty/evidence call with their own vocabulary; an unknown non-Task caller still needs
        # a threshold, and the most permissive declared one is the safe answer (never converts a
        # request to a job that would have been fast).
        profile = profile.with_sync_threshold(_FALLBACK_THRESHOLD_CHARS)
    raw = os.environ.get(f"DOCSURI_SYNC_THRESHOLD_CHARS_{profile.task}")
    if raw is None:
        return profile
    try:
        override = int(raw)
    except ValueError:
        return profile
    return profile.with_sync_threshold(override if override > 0 else profile.sync_threshold_chars)
