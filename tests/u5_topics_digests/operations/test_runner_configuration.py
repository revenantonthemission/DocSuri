"""Real filesystem checks for the synthetic U5 runner's configuration and evidence.

Grouped by the runner's parts (decision L2-1): the database command's finite
configuration, private evidence, the phase catalog, content digests and the
bound policy reference.
"""

import json
import stat

import pytest

from scripts import verify_docsuri_u5 as runner
from backend.u5_policy import SYNTHETIC_TOPICS, TopicsPolicy


@pytest.fixture
def owned_root(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "RUN", root)
    return root


def test_database_command_has_finite_private_configuration():
    command = runner.database_command(
        {"runId": "docsuri-u5-0123456789abcdef", "container": "owned", "volume": "owned-pgdata"}
    )
    assert command[command.index("--memory") + 1] == "1g"
    assert command[command.index("--memory-swap") + 1] == "1g"
    assert command[command.index("--pids-limit") + 1] == "64"
    assert command[command.index("-p") + 1] == "127.0.0.1:15489:5432"
    assert "--read-only" in command
    assert "POSTGRES_PASSWORD" in command and not any("PASSWORD=" in item for item in command)
    assert runner.IMAGE in command


def test_private_evidence_preserves_permissions_and_rejects_symlinks(owned_root):
    target = owned_root / "evidence.json"
    runner.private_json(target, {"tests": 3})
    assert json.loads(target.read_bytes()) == {"tests": 3}
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    alias = owned_root / "alias.json"
    alias.symlink_to(target)
    with pytest.raises(runner.Refused):
        runner.private_json(alias, {"tests": 9})
    assert json.loads(target.read_bytes()) == {"tests": 3}


def test_phase_catalog_matches_the_unit_scope():
    assert set(runner.TEST_PHASES) == {
        "database",
        "repository",
        "component",
        "integration",
        "operations",
        "coverage",
    }
    for phase in ("setup", "migrate", "fixtures", "archive-owned", "frontend", "browser", "serve"):
        assert phase in runner.PHASES


def test_digest_is_stable_per_content(owned_root):
    target = owned_root / "bytes.bin"
    target.write_bytes(b"synthetic")
    first = runner.digest(target)
    assert len(first) == 64 and first == runner.digest(target)
    target.write_bytes(b"synthetic!")
    assert runner.digest(target) != first


def test_policy_reference_is_finite_and_bound():
    assert SYNTHETIC_TOPICS.reference() == {"policyId": "u5-synthetic-topics", "revision": "1"}
    assert SYNTHETIC_TOPICS.synthetic_only is True
    assert SYNTHETIC_TOPICS.sends_per_pass == 1
    with pytest.raises(ValueError):
        TopicsPolicy(selection_limit=0)
    with pytest.raises(ValueError):
        TopicsPolicy(sends_per_pass=2)
    with pytest.raises(ValueError):
        TopicsPolicy(delivery_timezone="")
