#!/bin/sh
# One-shot launchctl-debug program for the installed r1t-clock-20260927 observer.
# Ignores the original env program's arguments; never executes the observer target.
exec /usr/bin/env -i PATH=/usr/bin:/bin LANG=en_US.UTF-8 HOME=/var/empty \
  "/Library/Application Support/DocSuri/rem-1-test/toolchains/r1t-clock-20260927/runtime/bin/python3.13" \
  -I -B - <<'PYTHON_DIAGNOSTIC'
import json
import os
import signal
import time


class ExecBoundary(Exception):
    pass


def expired(signum, frame):
    raise TimeoutError("launch diagnostic deadline")


report = {
    "state": "LAUNCH_DIAGNOSTIC_FAILED",
    "diagnostic": "r1t-clock-launch-v1",
    "accepted": False,
    "pid": os.getpid(),
    "uid": os.getuid(), "euid": os.geteuid(),
    "gid": os.getgid(), "egid": os.getegid(),
    "monotonicNs": str(time.monotonic_ns()),
    "stage": "context",
    "targetExecuted": False,
}
launcher = None
original_execve = None
previous_handler = signal.signal(signal.SIGALRM, expired)
signal.alarm(15)
try:
    if 0 in (report["uid"], report["euid"]):
        raise PermissionError("diagnostic must run as the launchd service user, not root")
    report["stage"] = "import_installed_launcher"
    from docsuri_platform_integrity.deployment import launchd as launcher

    report["stage"] = "kernel_groups"
    report["kernelGroups"] = list(launcher.kernel_groups())

    def stop_before_exec(path, argv, env):
        report["stage"] = "exec_boundary"
        report["targetBasename"] = os.path.basename(path)
        raise ExecBoundary()

    original_execve = launcher.os.execve
    launcher.os.execve = stop_before_exec
    report["stage"] = "launch_guard"
    launcher.execute(
        "test", "nts-observer",
        "sha256:ac0c16bb5bf6baa5a502464a4a1f0807b0395eabe6a768abd3d06df0c47bdd26",
    )
    raise RuntimeError("launcher returned without reaching exec boundary")
except ExecBoundary:
    report["state"] = "LAUNCH_GUARD_PASSED_NO_EXEC"
except Exception as error:
    report["errorType"] = type(error).__name__
    report["detail"] = str(error)[:500]
finally:
    if launcher is not None and original_execve is not None:
        launcher.os.execve = original_execve
    signal.alarm(0)
    signal.signal(signal.SIGALRM, previous_handler)

print(json.dumps(report, sort_keys=True), flush=True)
raise SystemExit(0 if report["state"] == "LAUNCH_GUARD_PASSED_NO_EXEC" else 2)
PYTHON_DIAGNOSTIC
