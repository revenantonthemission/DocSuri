"""A launch-context diagnostic must report failures without executing a target."""

import json
import os
import signal
from pathlib import Path

import pytest
from docsuri_platform_integrity.deployment import launchd

SCRIPT = Path(__file__).resolve().parents[1] / "platform-integrity/diagnose_clock_launch.sh"
PROGRAM = SCRIPT.read_text().split("<<'PYTHON_DIAGNOSTIC'\n", 1)[1].rsplit(
    "\nPYTHON_DIAGNOSTIC", 1,
)[0]


@pytest.fixture
def context(monkeypatch):
    for name, value in (("getuid", 608), ("geteuid", 608), ("getgid", 608), ("getegid", 608)):
        monkeypatch.setattr(os, name, lambda value=value: value)
    monkeypatch.setattr(launchd, "kernel_groups", lambda: (608,))
    monkeypatch.setattr(signal, "alarm", lambda seconds: 0)
    monkeypatch.setattr(signal, "signal", lambda *args: None)


def run_diagnostic(capsys):
    with pytest.raises(SystemExit) as exit_info:
        exec(compile(PROGRAM, str(SCRIPT), "exec"), {})
    return exit_info.value.code, json.loads(capsys.readouterr().out)


def test_diagnostic_intercepts_exec_and_restores_it(context, monkeypatch, capsys):
    def forbidden_exec(*args):
        pytest.fail("diagnostic executed a target")

    monkeypatch.setattr(os, "execve", forbidden_exec)

    def guarded(profile, name, expected):
        assert (profile, name) == ("test", "nts-observer")
        assert expected == "sha256:ac0c16bb5bf6baa5a502464a4a1f0807b0395eabe6a768abd3d06df0c47bdd26"
        os.execve("/frozen/chronyd", ["/frozen/chronyd", "-x"], {})

    monkeypatch.setattr(launchd, "execute", guarded)
    code, report = run_diagnostic(capsys)
    assert code == 0 and report["state"] == "LAUNCH_GUARD_PASSED_NO_EXEC"
    assert report["targetExecuted"] is False and report["accepted"] is False
    assert report["kernelGroups"] == [608] and report["targetBasename"] == "chronyd"
    assert os.execve is forbidden_exec


def test_diagnostic_preserves_native_group_failure(context, monkeypatch, capsys):
    monkeypatch.setattr(launchd, "kernel_groups", lambda: (608, 0))

    def refused(*args):
        raise PermissionError("runtime role boundary not established")

    monkeypatch.setattr(launchd, "execute", refused)
    code, report = run_diagnostic(capsys)
    assert code == 2 and report["state"] == "LAUNCH_DIAGNOSTIC_FAILED"
    assert report["stage"] == "launch_guard" and report["kernelGroups"] == [608, 0]
    assert report["errorType"] == "PermissionError"
    assert report["detail"] == "runtime role boundary not established"
    assert report["targetExecuted"] is False


def test_diagnostic_refuses_root_before_using_the_launcher(context, monkeypatch, capsys):
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(launchd, "execute", lambda *args: pytest.fail("root entered launch guard"))
    code, report = run_diagnostic(capsys)
    assert code == 2 and report["stage"] == "context"
    assert report["errorType"] == "PermissionError" and report["targetExecuted"] is False


def test_diagnostic_requires_the_exec_boundary_and_bounds_error_text(context, monkeypatch, capsys):
    monkeypatch.setattr(launchd, "execute", lambda *args: None)
    code, report = run_diagnostic(capsys)
    assert code == 2 and "without reaching exec boundary" in report["detail"]

    def failed(*args):
        raise OSError("x" * 1000)

    monkeypatch.setattr(launchd, "execute", failed)
    code, report = run_diagnostic(capsys)
    assert code == 2 and len(report["detail"]) == 500
