"""Load acceptance must not be satisfiable by latency alone.

A run that is fast and correct but unobserved must not read as accepted, and a single sample over
the ceiling must fail the run even when the average is comfortable.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from docsuri_ops.load_observation import (
    DEFAULT_LRU_BUDGET,
    DEFAULT_RSS_BUDGET,
    MIB,
    LoadVerdict,
    RssBudget,
    RssObservation,
    verify_no_side_effects,
)

SCRIPT = Path(__file__).resolve().parents[1] / "platform-integrity" / "load_acceptance.py"
_spec = importlib.util.spec_from_file_location("load_acceptance", SCRIPT)
_load = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_load)


class Probe:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.index = 0

    def counts(self):
        value = self.snapshots[min(self.index, len(self.snapshots) - 1)]
        self.index += 1
        return dict(value)


class ExplodingProbe:
    def counts(self):
        raise RuntimeError("probe down")


# -- budget shape ----------------------------------------------------------


def test_default_budget_matches_the_stated_ceiling():
    budget = RssBudget()
    assert budget.total_bytes == DEFAULT_RSS_BUDGET == 512 * MIB
    assert budget.lru_bytes == DEFAULT_LRU_BUDGET == 64 * MIB


def test_budget_rejects_nonsense():
    with pytest.raises(ValueError):
        RssBudget(total_bytes=0)
    with pytest.raises(ValueError):
        RssBudget(total_bytes=-1)
    with pytest.raises(ValueError):
        RssBudget(total_bytes=64 * MIB, lru_bytes=128 * MIB)


# -- observation -----------------------------------------------------------


def test_zero_samples_is_unproven_not_a_pass():
    observation = RssObservation()
    assert not observation.proven
    assert observation.verdict() == "INCOMPLETE"


def test_a_comfortable_average_still_fails_on_one_peak():
    observation = RssObservation()
    for _ in range(50):
        observation.observe(100 * MIB)
    observation.observe(DEFAULT_RSS_BUDGET + 1)
    assert observation.within_budget() is False
    assert observation.verdict() == "OVER_BUDGET"
    assert observation.over_budget == 1
    assert observation.peak_bytes == DEFAULT_RSS_BUDGET + 1


def test_a_run_entirely_within_budget_verifies():
    observation = RssObservation()
    for _ in range(10):
        observation.observe(300 * MIB)
    assert observation.verdict() == "VERIFIED"
    payload = observation.as_dict()
    assert payload["peakMiB"] == 300.0
    assert payload["budgetMiB"] == 512


def test_a_sample_at_exactly_the_budget_is_allowed():
    observation = RssObservation()
    observation.observe(DEFAULT_RSS_BUDGET)
    assert observation.within_budget() is True


def test_a_broken_sample_is_recorded_rather_than_counted_as_small():
    observation = RssObservation()
    observation.observe(-1)
    assert observation.sample_failures == 1
    assert observation.samples == 0
    assert observation.verdict() == "INCOMPLETE"


def test_the_peak_pid_is_reported():
    observation = RssObservation()
    observation.observe(10, pid=11)
    observation.observe(20, pid=12)
    assert observation.as_dict()["peakPid"] == 12


# -- side effects ----------------------------------------------------------


def test_stable_state_reports_no_change():
    result = verify_no_side_effects(Probe([{"runs": 3, "ledger": 9}]))
    assert result["state"] == "STABLE"
    assert result["observed"] == {"runs": 3, "ledger": 9}


def test_a_read_path_that_creates_a_run_is_caught():
    result = verify_no_side_effects(Probe([{"runs": 3}, {"runs": 4}]))
    assert result["state"] == "CHANGED"
    assert result["changed"]["runs"] == {"before": 3, "after": 4}


def test_a_new_key_appearing_mid_run_counts_as_a_change():
    result = verify_no_side_effects(Probe([{"runs": 3}, {"runs": 3, "ledger": 1}]))
    assert result["state"] == "CHANGED"
    assert result["changed"]["ledger"] == {"before": None, "after": 1}


def test_an_unavailable_probe_is_incomplete_not_clean():
    result = verify_no_side_effects(ExplodingProbe())
    assert result["state"] == "INCOMPLETE"
    assert "probe_unavailable" in result["reason"]


def test_an_explicit_before_snapshot_is_used():
    result = verify_no_side_effects(Probe([{"runs": 99}]), before={"runs": 3})
    assert result["state"] == "CHANGED"
    assert result["changed"]["runs"]["before"] == 3


# -- combined verdict ------------------------------------------------------


def _passing_rss():
    observation = RssObservation()
    observation.observe(200 * MIB)
    return observation


def test_a_latency_pass_with_observations_is_accepted():
    verdict = LoadVerdict(
        latency_state="MEASURED_PASS", profile_complete=True,
        rss=_passing_rss(), side_effects={"state": "STABLE"}, dependency_observed=True,
    )
    assert verdict.passed
    assert verdict.as_dict()["state"] == "ACCEPTED"
    assert verdict.as_dict()["blockers"] == []


@pytest.mark.parametrize(
    "field,value,expected_blocker",
    [
        ("latency_state", "BLOCKED", "latency_not_passed"),
        ("profile_complete", False, "profile_incomplete"),
        ("dependency_observed", False, "dependency_unobserved"),
    ],
)
def test_each_missing_observation_blocks_acceptance(field, value, expected_blocker):
    kwargs = dict(
        latency_state="MEASURED_PASS", profile_complete=True,
        rss=_passing_rss(), side_effects={"state": "STABLE"}, dependency_observed=True,
    )
    kwargs[field] = value
    verdict = LoadVerdict(**kwargs)
    assert not verdict.passed
    assert expected_blocker in verdict.as_dict()["blockers"]


def test_an_unobserved_resource_budget_blocks_acceptance():
    verdict = LoadVerdict(
        latency_state="MEASURED_PASS", profile_complete=True,
        rss=RssObservation(), side_effects={"state": "STABLE"}, dependency_observed=True,
    )
    assert not verdict.passed
    assert "rss_incomplete" in verdict.as_dict()["blockers"]


def test_changed_side_effects_block_acceptance():
    verdict = LoadVerdict(
        latency_state="MEASURED_PASS", profile_complete=True,
        rss=_passing_rss(), side_effects={"state": "CHANGED"}, dependency_observed=True,
    )
    assert not verdict.passed
    assert "side_effects_changed" in verdict.as_dict()["blockers"]


# -- integration with the existing script ---------------------------------


def test_combine_drops_the_placeholder_flag_and_adds_acceptance():
    result = {
        "state": "MEASURED_PASS", "profileComplete": True, "requests": 3000,
        "successes": 3000, "failures": [], "metadataP95Ms": 40.0, "healthP95Ms": 5.0,
        "durationSeconds": 601.0, "nativeProviderAndRssAcceptanceRequired": True,
    }
    payload = _load.combine(
        result, _passing_rss(), {"state": "STABLE"}, dependency_observed=True
    )
    assert "nativeProviderAndRssAcceptanceRequired" not in payload
    assert payload["acceptance"]["state"] == "ACCEPTED"
    assert payload["state"] == "MEASURED_PASS"


def test_combine_keeps_a_latency_failure_visible():
    result = {
        "state": "BLOCKED", "profileComplete": True, "requests": 10,
        "successes": 9, "failures": [{"kind": "metadata", "error": "TimeoutError"}],
        "metadataP95Ms": None, "healthP95Ms": None, "durationSeconds": 2.0,
        "nativeProviderAndRssAcceptanceRequired": True,
    }
    payload = _load.combine(
        result, _passing_rss(), {"state": "STABLE"}, dependency_observed=True
    )
    assert payload["acceptance"]["state"] == "BLOCKED"
    assert "latency_not_passed" in payload["acceptance"]["blockers"]


def test_a_short_profile_cannot_be_accepted(tmp_path):
    """5 req/s x 600s is the acceptance profile; a shorter run must not self-certify."""
    verdict = LoadVerdict(
        latency_state="MEASURED_PASS", profile_complete=False,
        rss=_passing_rss(), side_effects={"state": "STABLE"}, dependency_observed=True,
    )
    assert not verdict.passed


def test_the_resource_watcher_observes_a_real_process_tree():
    import os
    import threading

    observation = RssObservation()
    stop = threading.Event()
    watcher = threading.Thread(
        target=_load.observe_resources, args=(os.getpid(), observation, stop), daemon=True
    )
    watcher.start()
    threading.Event().wait(1.2)
    stop.set()
    watcher.join(timeout=5)
    assert observation.samples >= 1
    assert observation.peak_bytes > 0
    assert observation.as_dict()["peakPid"] == os.getpid()


def test_the_watcher_records_a_bad_pid_as_a_failure_not_a_zero():
    import threading

    observation = RssObservation()
    stop = threading.Event()
    watcher = threading.Thread(
        target=_load.observe_resources, args=(2**30, observation, stop), daemon=True
    )
    watcher.start()
    threading.Event().wait(0.4)
    stop.set()
    watcher.join(timeout=5)
    assert observation.samples == 0
    assert observation.sample_failures >= 1
    assert observation.verdict() == "INCOMPLETE"
