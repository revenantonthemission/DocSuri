"""Real filesystem/process checks for the synthetic U5 runner's process supervision.

Grouped by the runner's parts (decision L2-1): measured memory, the observation
timeout, one snapshot per tick, the process-tree snapshot and its deadline,
proportional bytes, PSS on Linux and the proportional budget.
"""

import subprocess
import sys
import time

import pytest

from scripts import verify_docsuri_u5 as runner


@pytest.fixture
def owned_root(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "RUN", root)
    return root


def test_available_memory_requires_exact_measured_field():
    assert runner.memory_available("MemTotal: 500 kB\nMemAvailable: 123 kB\n") == 123 * 1024
    with pytest.raises(runner.Refused):
        runner.memory_available("MemFree: 500 kB\n")


def test_process_observation_timeout_stops_child_and_retains_failure(owned_root, monkeypatch):
    def unavailable(roots, deadline):
        raise subprocess.TimeoutExpired(["ps"], 1)

    monkeypatch.setattr(runner, "process_tree_memory", unavailable)
    with pytest.raises(subprocess.TimeoutExpired) as failure:
        runner.bounded_process(
            [sys.executable, "-c", "import time; time.sleep(20)"],
            owned_root / "supervision.log",
            seconds=5,
        )
    assert failure.value.supervision["reason"] == "supervision-error"
    assert failure.value.supervision["exitCode"] == 1
    assert failure.value.supervision["processStopped"] is True


def test_browser_supervision_takes_one_snapshot_per_tick_for_both_roots(owned_root, monkeypatch):
    companion = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    companion_log = owned_root / "companion.log"
    companion_log.write_bytes(b"")
    snapshots = []

    def observe(roots, deadline):
        snapshots.append(tuple(roots))
        return 1024, None

    monkeypatch.setattr(runner, "process_tree_memory", observe)
    try:
        result = runner.bounded_process(
            [sys.executable, "-c", "import time; time.sleep(0.3)"],
            owned_root / "browser.log",
            seconds=5,
            companion=companion,
            companion_log=companion_log,
        )
    finally:
        companion.kill()
        companion.wait()
    assert snapshots, "supervision never observed the process trees"
    assert all(len(roots) == 2 for roots in snapshots)
    assert {roots[1] for roots in snapshots} == {companion.pid}
    assert result["observations"] == len(snapshots)
    assert result["exitCode"] == 0
    assert result["peakRssBytes"] == 1024


def test_process_tree_snapshot_unions_trees_without_double_counting(monkeypatch):
    table = "\n".join(["10 1 100", "11 10 200", "12 11 300", "20 1 400", "21 20 500", "30 1 9999"])
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs["timeout"]))
        return subprocess.CompletedProcess(args, 0, stdout=table)

    monkeypatch.setattr(runner.subprocess, "run", run)
    deadline = time.monotonic() + 30
    assert runner.process_tree_rss((10, 20), deadline) == (100 + 200 + 300 + 400 + 500) * 1024
    # A root listed twice, or one inside another's tree, is still counted once.
    assert runner.process_tree_rss((10, 11, 10), deadline) == (100 + 200 + 300) * 1024
    assert len(calls) == 2
    assert all(timeout == runner.OBSERVATION_SECONDS for _, timeout in calls)


def test_process_tree_snapshot_refuses_after_its_deadline(monkeypatch):
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *a, **k: pytest.fail("snapshot after deadline")
    )
    with pytest.raises(runner.Refused, match="process deadline reached"):
        runner.process_tree_rss((1,), time.monotonic() - 1)


def test_proportional_bytes_reads_pss_and_falls_back_to_rss(tmp_path, monkeypatch):
    (tmp_path / "7").write_text("Rss:  900 kB\nPss:  300 kB\nShared_Clean: 600 kB\n")
    (tmp_path / "8").write_text("Rss:  900 kB\n")
    monkeypatch.setattr(runner, "SMAPS_ROLLUP", str(tmp_path / "{pid}"))
    assert runner.proportional_bytes(7, 900) == 300 * 1024
    # No Pss line, or a process that exited before the read: its full RSS counts.
    assert runner.proportional_bytes(8, 900) == 900 * 1024
    assert runner.proportional_bytes(9, 900) == 900 * 1024


def test_process_tree_memory_enforces_pss_only_on_linux(monkeypatch):
    table = "\n".join(["10 1 100", "11 10 200", "30 1 9999"])
    monkeypatch.setattr(
        runner.subprocess, "run", lambda args, **k: subprocess.CompletedProcess(args, 0, stdout=table)
    )
    monkeypatch.setattr(runner, "proportional_bytes", lambda pid, kib: kib * 1024 // 4)
    deadline = time.monotonic() + 30
    monkeypatch.setattr(runner.sys, "platform", "darwin")
    assert runner.process_tree_memory((10,), deadline) == (300 * 1024, None)
    monkeypatch.setattr(runner.sys, "platform", "linux")
    assert runner.process_tree_memory((10,), deadline) == (300 * 1024, 75 * 1024)
    assert runner.enforced_bytes(300 * 1024, 75 * 1024) == 75 * 1024
    assert runner.enforced_bytes(300 * 1024, None) == 300 * 1024


@pytest.mark.parametrize("over", ["pss", "rss"])
def test_supervision_enforces_the_proportional_budget_where_measured(owned_root, monkeypatch, over):
    big = runner.MAX_RSS + 1
    reading = (1024, big) if over == "pss" else (big, 1024)
    monkeypatch.setattr(runner, "process_tree_memory", lambda roots, deadline: reading)
    command = [sys.executable, "-c", "import time; time.sleep(0.3)"]
    if over == "pss":
        with pytest.raises(runner.Refused) as refused:
            runner.bounded_process(command, owned_root / "pss.log", seconds=5)
        assert refused.value.supervision["reason"] == "rss-limit"
        assert refused.value.supervision["peakPssBytes"] == big
    else:
        # Shared pages inflate the RSS sum; the proportional sum is under budget.
        result = runner.bounded_process(command, owned_root / "rss.log", seconds=5)
        assert result["exitCode"] == 0
        assert (result["peakRssBytes"], result["peakPssBytes"]) == (big, 1024)
