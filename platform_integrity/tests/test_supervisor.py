import sys
from pathlib import Path

import pytest

from docsuri_platform_integrity.application.supervisor import RunBlocked, Supervisor, Tool
from docsuri_platform_integrity.contracts.codec import digest


def supervisor(tmp_path, script, **options):
    executable = Path(sys.executable).resolve()
    tool = Tool(
        (str(executable), "-c", script), digest(executable.read_bytes()), timeout_s=3, **options
    )
    (tmp_path / "heavy.lock").touch(mode=0o600)
    return Supervisor(tmp_path, {"test-tool": tool})


def test_tool_runs_once_with_bounded_output_and_releases_slot(tmp_path):
    runner = supervisor(tmp_path, "print('result')")
    result = runner.run("test-tool")
    assert result.returncode == 0 and result.stdout == b"result\n"
    assert not (tmp_path / "holder.json").exists()
    assert result.peak_rss < 2 * 1024**3


def test_failed_tool_keeps_conservative_holder_witness(tmp_path):
    runner = supervisor(tmp_path, "print('a' * 10000)", output_limit=100)
    with pytest.raises(RunBlocked, match="output"):
        runner.run("test-tool")
    assert (tmp_path / "holder.json").exists()
    with pytest.raises(RunBlocked, match="reconciliation"):
        runner.run("test-tool")
