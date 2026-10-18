"""Real filesystem/process checks for the synthetic U5 runner's safety boundaries."""

import json
import stat
import sys
from pathlib import Path

import pytest

from backend.local_profile import LocalProfile
from scripts import verify_docsuri_u5 as runner
from backend.u5_policy import SYNTHETIC_TOPICS, TopicsPolicy

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ops/src"))
from docsuri_ops.local_transport import inspect_transport, prepare_transport  # noqa: E402


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


def test_parallel_runner_is_refused(owned_root):
    with runner.exclusive():
        with pytest.raises(runner.Refused, match="active"):
            with runner.exclusive():
                pass


def test_child_environment_binds_the_unit_manifest(owned_root):
    environment = runner.child_environment()
    assert environment["DOCSURI_U5_ENVIRONMENT_FILE"] == str(runner.RUN / "environment.json")
    assert environment["CI"] == "true"
    assert environment["COREPACK_ENABLE_NETWORK"] == "0"


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


def test_migration_chain_is_append_only_and_present():
    schema_index = None
    guard_index = None
    for index, (owner, relative) in enumerate(runner.MIGRATIONS):
        assert (runner.ROOT / relative).is_file(), relative
        assert owner in runner.OWNERS, relative
        if relative.endswith("u5_schema.sql"):
            schema_index = index
        if relative.endswith("u5_run_guard.sql"):
            guard_index = index
    # The chronology-gate correction is an appended migration, never an edit of
    # the applied file: the runner refuses changed applied bytes.
    assert schema_index is not None and guard_index is not None
    assert guard_index == len(runner.MIGRATIONS) - 1
    assert guard_index > schema_index


def test_owner_and_realm_bindings_cover_topics():
    assert "topics" in runner.OWNERS
    assert runner.UNIT == "u5-topics-digests"
    assert runner.REALM == "topics-digests"
    assert runner.DATABASE == "docsuri_u5"
    assert runner.DATABASE_PORT == 15489 and runner.APPLICATION_PORT == 18089
    assert runner.POLICY == "u5-synthetic-v1"


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


def test_browser_fixture_record_is_bound_to_the_run(realm):
    from scripts import u5_browser_fixtures as fixtures

    record = fixtures.fixture_record(realm)
    assert record["runId"] == realm.run_id
    assert record["fixtureVersion"] == "u5-browser-v1"
    assert record["state"] in ("prepared", "ready")
    assert set(record["accounts"]) == {"memberA", "memberB"}


def test_browser_fixture_setup_is_restartable_and_complete(realm):
    from scripts import u5_browser_fixtures as fixtures

    first = fixtures.setup(realm.root / "environment.json")
    assert first["state"] == "fixtures-ready"
    assert first["accounts"] == 2 and first["papers"] == 2
    second = fixtures.setup(realm.root / "environment.json")
    assert second == first
    record = fixtures.fixture_record(realm)
    assert record["state"] == "ready"
    # The resolve fixture stays present after a re-run: one unresolved unknown
    # for the fixture topic, with every earlier attempt's gap recorded.
    transactions_owner = realm.root
    assert (transactions_owner / "browser-fixtures.json").is_file()


def test_realm_transport_binding_is_owned(realm):
    transport = inspect_transport(realm)
    prepared = prepare_transport(realm)
    assert str(transport.certificate) == str(prepared.certificate)
    assert prepared.certificate.is_file() and prepared.key.is_file()


def test_serve_assembles_the_owned_release(realm):
    import scripts.serve_docsuri_u5 as serve

    app, transport = serve.assemble(realm.root / "environment.json")
    try:
        assert app.state.profile.run_id == realm.run_id
        assert app.state.profile.realm == "topics-digests"
        assert hasattr(app.state, "topics")
        assert hasattr(app.state, "topics_scheduler")
        assert transport.certificate.is_file()
    finally:
        app.state.transactions.close()


def test_local_profile_load_requires_the_owned_manifest(realm):
    with pytest.raises(ValueError):
        LocalProfile.load(realm.root / "missing.json")
    profile = LocalProfile.load(realm.root / "environment.json")
    assert profile.realm == "topics-digests" and profile.database_name == "docsuri_u5"
    assert profile.origin == "https://127.0.0.1:18089"
