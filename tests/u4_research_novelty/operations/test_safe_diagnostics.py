import json
import sys

import pytest

from scripts import verify_docsuri_u4 as runner


def test_phase_summary_excludes_private_fields():
    evidence = {
        "phase": "browser", "exitCode": 1, "failureCategory": "Refused",
        "missingTestReport": True, "invalidTestReport": False, "sourceChangedDuringRun": False,
        "command": ["secret"], "runId": "private", "rawLog": "secret manuscript",
        "supervision": {
            "reason": "rss-limit", "exitCode": 1, "elapsedSeconds": 2,
            "peakRssBytes": 42, "logBytes": 123, "processStopped": True,
            "payload": "secret manuscript",
        },
    }
    summary = runner.safe_phase_summary(evidence)
    assert "secret" not in json.dumps(summary)
    assert "private" not in json.dumps(summary)
    assert summary["missingTestReport"] is True
    assert summary["supervision"]["reason"] == "rss-limit"
    assert summary["supervision"]["peakRssBytes"] == 42


def test_startup_failure_summary_does_not_invent_metrics():
    summary = runner.safe_phase_summary({
        "phase": "browser", "exitCode": 1, "failureCategory": "Refused",
        "missingTestReport": True,
    })
    assert all(value is None for value in summary["supervision"].values())
    assert "tests" not in summary


@pytest.mark.parametrize("fault,reason", [("rss", "rss-limit"), ("log", "log-limit")])
def test_bounded_failure_preserves_safe_metrics(tmp_path, monkeypatch, fault, reason):
    monkeypatch.setattr(runner, "RUN", tmp_path)
    monkeypatch.setattr(runner, "child_environment", lambda: {})
    if fault == "rss":
        monkeypatch.setattr(runner, "process_rss", lambda *_: runner.MAX_RSS + 1)
    else:
        monkeypatch.setattr(runner, "MAX_LOG", 8)
    with pytest.raises(runner.Refused) as error:
        runner.bounded_process(
            [sys.executable, "-c", "import time; print('synthetic diagnostic',flush=True); time.sleep(2)"],
            tmp_path / "bounded.log", seconds=2,
        )
    metrics = error.value.supervision
    assert metrics["reason"] == reason
    assert metrics["processStopped"] is True
    assert metrics["elapsedSeconds"] >= 0
    assert "synthetic diagnostic" not in json.dumps(metrics)


def test_deadline_failure_reports_stopped_process(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUN", tmp_path)
    monkeypatch.setattr(runner, "child_environment", lambda: {})
    monkeypatch.setattr(runner, "process_rss", lambda *_: 0)
    with pytest.raises(runner.Refused) as error:
        runner.bounded_process(
            [sys.executable, "-c", "import time; time.sleep(2)"],
            tmp_path / "deadline.log", seconds=0.2,
        )
    assert error.value.supervision["reason"] == "deadline"
    assert error.value.supervision["processStopped"] is True
