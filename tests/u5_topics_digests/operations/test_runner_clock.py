"""Real filesystem/process checks for the synthetic U5 runner's clock and exclusivity.

Grouped by the runner's parts (decision L2-1): the clock advance, the refused
parallel runner, the browser clock child, the delegation's refusals and its
revocation.
"""

import datetime as dt
import json
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


@pytest.mark.parametrize("hour", ["05:00", "16:00", "23:59"])
def test_advance_clock_moves_one_day_whatever_the_hour(hour):
    from scripts import u5_browser_fixtures as fixtures

    now = dt.datetime.fromisoformat(f"2026-10-20T{hour}:00+00:00")
    instant = fixtures.advanced_clock(now)
    assert instant == now + dt.timedelta(days=1)
    # Inside the host's accepted window for the delegated clock (u5_host).
    assert now - dt.timedelta(hours=1) <= instant <= now + dt.timedelta(days=2)


def test_parallel_runner_is_refused(owned_root):
    with runner.exclusive():
        with pytest.raises(runner.Refused, match="active"):
            with runner.exclusive():
                pass


def test_browser_clock_child_preserves_exclusive_parent(owned_root, monkeypatch):
    value = {"runId": "owned-clock", "expiresAt": time.time() + 120}
    with runner.exclusive(), runner.browser_clock_delegation(value, 60) as token:
        monkeypatch.setenv("DOCSURI_U5_CLOCK_CAPABILITY", token)
        runner.authorize_clock_child(value)
        environment = runner.child_environment()
        environment["DOCSURI_U5_CLOCK_CAPABILITY"] = token
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json,sys; from pathlib import Path; "
                "from scripts import verify_docsuri_u5 as runner; "
                "runner.RUN=Path(sys.argv[1]); "
                "runner.authorize_clock_child(json.loads(sys.argv[2]))",
                str(owned_root),
                json.dumps(value),
            ],
            env=environment,
            capture_output=True,
            timeout=5,
            check=True,
        )
        assert child.stdout == b"" and child.stderr == b""
        with pytest.raises(runner.Refused, match="active"):
            with runner.exclusive():
                pass
        assert token not in (owned_root / "browser-clock-delegation.json").read_text()
        assert "DOCSURI_U5_CLOCK_CAPABILITY" not in runner.child_environment()
    assert not (owned_root / "browser-clock-delegation.json").exists()


@pytest.mark.parametrize("invalid", ["missing", "wrong", "foreign", "expired", "malformed"])
def test_clock_delegation_rejects_unrelated_inputs(owned_root, monkeypatch, invalid):
    value = {"runId": "owned-clock", "expiresAt": time.time() + 120}
    with runner.exclusive(), runner.browser_clock_delegation(value, 60) as token:
        monkeypatch.setenv("DOCSURI_U5_CLOCK_CAPABILITY", token)
        checked = value
        if invalid == "missing":
            monkeypatch.delenv("DOCSURI_U5_CLOCK_CAPABILITY")
        elif invalid == "wrong":
            monkeypatch.setenv("DOCSURI_U5_CLOCK_CAPABILITY", "different")
        elif invalid == "foreign":
            checked = dict(value, runId="foreign")
        else:
            path = owned_root / "browser-clock-delegation.json"
            grant = json.loads(path.read_text())
            grant["expiresAt"] = "invalid" if invalid == "malformed" else time.time() - 1
            runner.private_json(path, grant)
        with pytest.raises(runner.Refused):
            runner.authorize_clock_child(checked)


def test_clock_delegation_revokes_on_failure_and_refuses_inactive_owner(owned_root, monkeypatch):
    value = {"runId": "owned-clock", "expiresAt": time.time() + 120}
    with runner.exclusive():
        with pytest.raises(RuntimeError), runner.browser_clock_delegation(value, 60) as token:
            saved = json.loads((owned_root / "browser-clock-delegation.json").read_text())
            monkeypatch.setenv("DOCSURI_U5_CLOCK_CAPABILITY", token)
            raise RuntimeError("test interruption")
        assert not (owned_root / "browser-clock-delegation.json").exists()
    runner.private_json(owned_root / "browser-clock-delegation.json", saved)
    with pytest.raises(runner.Refused, match="inactive"):
        runner.authorize_clock_child(value)
