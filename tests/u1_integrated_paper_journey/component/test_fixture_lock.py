"""A second process must not mutate the active synthetic test environment."""

import subprocess
import sys

import pytest

pytestmark = pytest.mark.u1_component


def test_active_fixture_lock_rejects_another_process(exclusive_fixture_environment):
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import fcntl,sys; f=open(sys.argv[1],'r+'); "
            "fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)",
            str(exclusive_fixture_environment),
        ],
        capture_output=True,
        text=True,
        timeout=3,
    )
    assert probe.returncode != 0
    assert "BlockingIOError" in probe.stderr
