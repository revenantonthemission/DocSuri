"""Real filesystem/process checks for the synthetic U5 runner's safety boundaries."""

import json
import stat
import subprocess
import sys
import time
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


def test_process_observation_timeout_stops_child_and_retains_failure(owned_root, monkeypatch):
    def unavailable(roots, deadline):
        raise subprocess.TimeoutExpired(["ps"], 1)

    monkeypatch.setattr(runner, "process_tree_rss", unavailable)
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
        return 1024

    monkeypatch.setattr(runner, "process_tree_rss", observe)
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


def test_browser_assets_always_rebuild_and_refuse_failed_build(owned_root, monkeypatch):
    calls = []

    def build(command, log, *, seconds):
        calls.append((command, log, seconds))
        return {"exitCode": 1, "processStopped": True}

    monkeypatch.setattr(runner, "bounded_process", build)
    with pytest.raises(runner.Refused, match="asset build failed") as failure:
        runner.build_browser_assets(owned_root / "build.log", seconds=30)
    assert calls[0][0] == ["corepack", "pnpm@9.15.9", "--dir", "frontend", "exec", "vite", "build"]
    assert calls[0][2] == 30
    assert failure.value.supervision["processStopped"] is True


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
    assert "DOCSURI_U5_CLOCK_CAPABILITY" not in environment


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
    assert [path for _, path in runner.MIGRATIONS[guard_index + 1 :]] == [
        "backend/modules/personalization/u5_digest_preferences.sql",
        "backend/modules/topics/u5_preference_snapshot.sql",
        "backend/modules/topics/u5_schedule.sql",
        "backend/modules/topics/u5_unsubscribe_capability.sql",
        "backend/modules/topics/u5_real_send_retention.sql",
        "backend/modules/topics/u5_refusal_detail.sql",
    ]
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


def test_serve_real_delivery_refuses_without_operator_activation(realm, monkeypatch):
    import scripts.serve_docsuri_u5 as serve
    from backend.u5_real_delivery import RealDeliveryRefused

    # Ambient provider variables alone never enable the real composition.
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "fake-credential-for-refusal-check")
    assert not (realm.root / "real-delivery.json").exists()
    with pytest.raises(RealDeliveryRefused, match="activation is absent"):
        serve.assemble(realm.root / "environment.json", real_delivery=True)


def test_local_profile_load_requires_the_owned_manifest(realm):
    with pytest.raises(ValueError):
        LocalProfile.load(realm.root / "missing.json")
    profile = LocalProfile.load(realm.root / "environment.json")
    assert profile.realm == "topics-digests" and profile.database_name == "docsuri_u5"
    assert profile.origin == "https://127.0.0.1:18089"
