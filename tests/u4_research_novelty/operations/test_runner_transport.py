"""Real filesystem/process checks for the synthetic runner's safety boundaries."""

import json
import hashlib
import os
import stat
import subprocess
import sys
import time
import ssl
from types import SimpleNamespace
from dataclasses import replace
from pathlib import Path

import pytest

from backend.local_profile import LocalProfile
from scripts import verify_docsuri_u4 as runner

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ops/src"))
from docsuri_ops.local_transport import inspect_transport, prepare_transport


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
        {"runId": "docsuri-u4-0123456789abcdef", "container": "owned", "volume": "owned-pgdata"}
    )
    assert command[command.index("--memory") + 1] == "1g"
    assert command[command.index("--memory-swap") + 1] == "1g"
    assert command[command.index("--pids-limit") + 1] == "64"
    assert command[command.index("-p") + 1] == "127.0.0.1:15479:5432"
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


def test_prior_browser_reports_preserve_bytes_modes_and_expiry(owned_root):
    runner.private_json(owned_root / "environment.json", {"expiresAt": 1234})
    report = owned_root / "browser.xml"
    report.write_bytes(b"<testsuite failures='1'/>")
    report.chmod(0o600)
    evidence = owned_root / "browser-evidence"
    evidence.mkdir(mode=0o700)
    nested = evidence / "failed-case"
    nested.mkdir(mode=0o700)
    context = nested / "error-context.md"
    context.write_bytes(b"synthetic failure context")
    context.chmod(0o600)
    report_bytes, context_bytes = report.read_bytes(), context.read_bytes()
    manifest = (owned_root / "environment.json").read_bytes()
    records = runner.preserve_prior_reports("browser")
    assert {r["original"] for r in records} == {"browser.xml", "browser-evidence"}
    assert not report.exists() and not evidence.exists()
    mapping = {r["original"]: owned_root / r["preserved"] for r in records}
    assert mapping["browser.xml"].read_bytes() == report_bytes
    assert (
        mapping["browser-evidence"] / "failed-case/error-context.md"
    ).read_bytes() == context_bytes
    assert stat.S_IMODE(mapping["browser.xml"].stat().st_mode) == 0o600
    assert stat.S_IMODE(mapping["browser-evidence"].stat().st_mode) == 0o700
    assert (owned_root / "environment.json").read_bytes() == manifest
    assert runner.preserve_prior_reports("browser") == []


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink", "mode", "type", "oversized"])
def test_prior_reports_validate_all_candidates_before_any_rename(owned_root, monkeypatch, unsafe):
    report = owned_root / "browser.xml"
    report.write_bytes(b"synthetic report")
    report.chmod(0o600)
    evidence = owned_root / "browser-evidence"
    evidence.mkdir(mode=0o700)
    context = evidence / "error-context.md"
    context.write_bytes(b"synthetic context")
    context.chmod(0o600)
    if unsafe == "symlink":
        (evidence / "link").symlink_to(context)
    elif unsafe == "hardlink":
        os.link(context, evidence / "link")
    elif unsafe == "mode":
        context.chmod(0o644)
    elif unsafe == "type":
        report.unlink()
        report.mkdir(mode=0o700)
    else:
        monkeypatch.setattr(runner, "MAX_LOG", 4)
    with pytest.raises(runner.Refused):
        runner.preserve_prior_reports("browser")
    assert report.exists() and evidence.exists()
    assert not list(owned_root.glob("*-preserved-*"))


def test_prior_report_checksum_change_is_refused_after_rename(owned_root, monkeypatch):
    report = owned_root / "database.xml"
    report.write_bytes(b"synthetic report")
    report.chmod(0o600)
    original = os.rename

    def changed(source, destination):
        original(source, destination)
        destination.write_bytes(b"changed after rename")

    monkeypatch.setattr(runner.os, "rename", changed)
    with pytest.raises(runner.Refused, match="checksum"):
        runner.preserve_prior_reports("database")
    assert len(list(owned_root.glob("database-preserved-*.xml"))) == 1


def test_prior_report_phase_and_root_are_not_free_paths(owned_root):
    with pytest.raises(runner.Refused, match="verification phase"):
        runner.preserve_prior_reports("../../foreign")
    owned_root.chmod(0o755)
    with pytest.raises(runner.Refused, match="root custody"):
        runner.preserve_prior_reports("coverage")


def test_bounded_process_records_real_exit_and_private_child_files(owned_root):
    target = owned_root / "child.txt"
    result = runner.bounded_process(
        [
            sys.executable,
            "-c",
            "import pathlib; pathlib.Path(__import__('sys').argv[1]).write_text('synthetic'); print('done')",
            str(target),
        ],
        owned_root / "process.log",
        seconds=5,
    )
    assert result["exitCode"] == 0 and result["processStopped"]
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert (owned_root / "process.log").read_text() == "done\n"


def test_bounded_process_records_failure_without_green_success(owned_root):
    result = runner.bounded_process(
        [sys.executable, "-c", "raise SystemExit(7)"], owned_root / "failure.log", seconds=5
    )
    assert result["exitCode"] == 7


def test_bounded_process_stops_deadline_process(owned_root):
    with pytest.raises(runner.Refused, match="deadline"):
        runner.bounded_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            owned_root / "timeout.log",
            seconds=0.5,
        )


def test_transport_is_bound_to_research_realm_and_retention(owned_root):
    profile = LocalProfile(
        owned_root,
        "docsuri-u4-0123456789abcdef",
        "https://127.0.0.1:18079",
        15479,
        time.time() + 600,
        "docsuri_u4",
        "research-workspace",
    )
    transport = prepare_transport(profile)
    assert inspect_transport(profile) == transport
    assert prepare_transport(profile) == transport
    for path in (transport.key, transport.certificate):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(ValueError):
        inspect_transport(replace(profile, origin="https://127.0.0.1:18069"))
    with pytest.raises(ValueError):
        inspect_transport(replace(profile, run_id="docsuri-u4-fedcba9876543210"))
    with pytest.raises(ValueError):
        inspect_transport(replace(profile, expires_at=time.time() - 1))


def test_transport_refuses_partial_material(owned_root):
    profile = LocalProfile(
        owned_root,
        "docsuri-u4-0123456789abcdef",
        "https://127.0.0.1:18079",
        15479,
        time.time() + 600,
        "docsuri_u4",
        "research-workspace",
    )
    descriptor = os.open(
        owned_root / "research-workspace-tls.key", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    os.close(descriptor)
    with pytest.raises(ValueError, match="partial"):
        prepare_transport(profile)


def test_foreign_resource_is_never_adopted(monkeypatch):
    monkeypatch.setattr(
        runner,
        "require",
        lambda args: subprocess.CompletedProcess(
            args, 0, json.dumps([{"Config": {"Labels": {}}, "HostConfig": {}}])
        ),
    )
    with pytest.raises(runner.Refused, match="foreign"):
        runner.require_resources({"runId": "owned", "container": "foreign", "volume": "foreign"})


def test_memory_allocation_refuses_before_provisioning(owned_root, monkeypatch):
    from collections import namedtuple

    disk = namedtuple("disk", "total used free")(20 * runner.GIB, 0, 20 * runner.GIB)
    monkeypatch.setattr(runner, "headroom", lambda **kwargs: None)
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda path: disk)
    calls = []

    def inspect(args, **kwargs):
        calls.append(args)
        if args[:2] == ["docker", "info"]:
            output = json.dumps({"MemTotal": 2 * runner.GIB})
        elif args[:2] == ["docker", "run"]:
            output = "MemAvailable: 1048576 kB\n"
        else:
            output = "{}"
        return subprocess.CompletedProcess(args, 0, output)

    monkeypatch.setattr(runner, "require", inspect)
    with pytest.raises(runner.Refused, match="available bytes"):
        runner.preflight()
    assert runner.preflight(established=True)["dockerAvailableBytes"] == runner.GIB
    assert not any("volume" in call for call in calls)


def test_resource_configuration_checks_exact_finite_bindings(monkeypatch):
    value = {"runId": "docsuri-u4-0123456789abcdef", "container": "owned", "volume": "owned-pgdata"}
    container = {
        "Config": {"Image": runner.IMAGE, "Labels": {runner.LABEL: value["runId"]}},
        "HostConfig": {
            "Memory": runner.DB_MEMORY,
            "MemorySwap": runner.DB_MEMORY,
            "NanoCpus": 1_000_000_000,
            "PidsLimit": 64,
            "ReadonlyRootfs": True,
            "PortBindings": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "15479"}]},
        },
        "State": {"Running": True},
        "Mounts": [
            {"Type": "volume", "Name": "owned-pgdata", "Destination": "/var/lib/postgresql/data"}
        ],
    }
    volume = {"Labels": {runner.LABEL: value["runId"]}}
    monkeypatch.setattr(
        runner,
        "require",
        lambda args: subprocess.CompletedProcess(
            args, 0, json.dumps([container if args[1] == "container" else volume])
        ),
    )
    runner.require_resources(value)
    container["HostConfig"]["Memory"] = 0
    with pytest.raises(runner.Refused, match="bounds"):
        runner.require_resources(value)
    container["HostConfig"]["Memory"] = runner.DB_MEMORY
    container["Mounts"][0]["Name"] = "foreign-data"
    with pytest.raises(runner.Refused, match="volume"):
        runner.require_resources(value)


def legacy_files(root):
    value = {
        "runId": "docsuri-u4-0123456789abcdef",
        "unit": runner.UNIT,
        "profile": "synthetic-local",
        "repository": str(runner.ROOT),
        "realm": "research-novelty",
        "databasePort": 15469,
        "applicationPort": 18069,
        "container": "docsuri-u4",
        "expiresAt": 12345,
    }
    path = root / "environment.json"
    runner.private_json(path, value)
    runner.private_json(
        root / "ownership.json",
        {"runId": value["runId"], "manifestSha256": hashlib.sha256(path.read_bytes()).hexdigest()},
    )
    return path


def test_archive_preserves_bytes_expiry_and_never_touches_database(owned_root, monkeypatch):
    path = legacy_files(owned_root)
    original = {p.name: p.read_bytes() for p in owned_root.iterdir()}
    calls = []
    monkeypatch.setattr(runner, "require_stopped", lambda port: calls.append(("port", port)))
    monkeypatch.setattr(
        runner,
        "command",
        lambda args, **kw: calls.append(args) or subprocess.CompletedProcess(args, 1, ""),
    )
    result = runner.archive_legacy(path)
    target = Path(result["path"])
    assert not owned_root.exists()
    assert {p.name: p.read_bytes() for p in target.iterdir()} == original
    assert result["expiresAt"] == 12345 and result["containerUnchanged"]
    assert all(call[0] != "docker" for call in calls)


def test_archive_refuses_open_directory(owned_root, monkeypatch):
    path = legacy_files(owned_root)
    monkeypatch.setattr(runner, "require_stopped", lambda port: None)
    monkeypatch.setattr(
        runner,
        "command",
        lambda args, **kw: subprocess.CompletedProcess(args, 0, "active open file"),
    )
    with pytest.raises(runner.Refused, match="in use"):
        runner.archive_legacy(path)
    assert path.exists()


@pytest.mark.parametrize(
    "xml, exit_code, changed, passed",
    [
        ("<testsuite><testcase/></testsuite>", 0, False, True),
        ("<testsuite/>", 0, False, False),
        ("<testsuite><testcase><skipped/></testcase></testsuite>", 0, False, False),
        ("<testsuite><testcase><failure/></testcase></testsuite>", 0, False, False),
        (None, 0, False, False),
        ("<testsuite>", 0, False, False),
        ("<testsuite><testcase/></testsuite>", 0, True, False),
        ("<testsuite><testcase/></testsuite>", 2, False, False),
    ],
)
def test_phase_evidence_cannot_certify_missing_skipped_or_changed_work(
    owned_root, monkeypatch, xml, exit_code, changed, passed
):
    value = {
        "runId": "owned",
        "locks": {name: runner.digest(runner.ROOT / name) for name in runner.LOCKS},
        "policy": runner.POLICY,
    }
    path = owned_root / "environment.json"
    runner.private_json(path, value)
    monkeypatch.setattr(runner, "manifest", lambda p: (None, value))
    monkeypatch.setattr(runner, "require_resources", lambda value: None)
    monkeypatch.setattr(runner, "preflight", lambda **kwargs: {"observed": True})
    monkeypatch.setattr(runner, "require_stopped", lambda: None)
    identities = iter([{"sha256": "before"}, {"sha256": "after" if changed else "before"}])
    monkeypatch.setattr(runner, "source_identity", lambda: next(identities))

    def process(args, log):
        if xml:
            report = owned_root / "database.xml"
            descriptor = os.open(report, os.O_WRONLY | os.O_CREAT, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                stream.write(xml)
        return {"exitCode": exit_code}

    monkeypatch.setattr(runner, "bounded_process", process)
    if passed:
        assert runner.run_phase("database", path)["state"] == "passed"
    else:
        with pytest.raises(runner.Refused, match="phase failed"):
            runner.run_phase("database", path)
    (evidence_path,) = owned_root.glob("database-evidence-*.json")
    evidence = json.loads(evidence_path.read_bytes())
    assert (evidence["exitCode"] == 0) is passed
    assert stat.S_IMODE(evidence_path.stat().st_mode) == 0o600


class SqlRecorder:
    """Capture bootstrap statements; separate real-store tests prove execution."""

    def __init__(self, *, schemas=(), version="16.15", installed=False):
        self.schemas, self.version, self.installed = schemas, version, installed
        self.statements = []
        self.last = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params=None, **kwargs):
        text = statement if isinstance(statement, str) else statement.as_string()
        self.statements.append((text, params))
        self.last = text
        return self

    def fetchall(self):
        return self.schemas

    def fetchone(self):
        if self.last == "SHOW server_version":
            return (self.version,)
        if "to_regclass" in self.last:
            return ("docsuri_local_identity" if self.installed else None,)
        raise AssertionError("unexpected bootstrap read")


def test_bootstrap_role_plan_keeps_research_owner_separate():
    conn = SqlRecorder()
    credentials = {"roles": {owner: "synthetic-only-test-value" for owner in runner.OWNERS}}
    runner.install_base(conn, {"runId": "synthetic-run"}, credentials, {"base": "identity"})
    statements = [statement for statement, _ in conn.statements]
    owner_role = next(s for s in statements if s.startswith('CREATE ROLE "docsuri_research_owner"'))
    runtime_role = next(s for s in statements if s.startswith('CREATE ROLE "docsuri_research"'))
    assert "NOLOGIN NOSUPERUSER" in owner_role and "NOBYPASSRLS" in owner_role
    assert "LOGIN NOSUPERUSER" in runtime_role and "CONNECTION LIMIT 2" in runtime_role
    research_grants = [
        s for s in statements if s.startswith("GRANT") and s.endswith('TO "docsuri_research"')
    ]
    assert any("accounts.guard_session(uuid,uuid,text)" in s for s in research_grants)
    assert any("corpus.guard_version(text,text)" in s for s in research_grants)
    assert not any("ALL TABLES" in s or "CREATE" in s for s in research_grants)
    assert len([s for s in statements if s.startswith("CREATE ROLE")]) == 18


@pytest.mark.parametrize("clients,foreign", [(0, False), (1, False), (0, True)])
def test_owned_rotation_preserves_bytes_and_refuses_live_or_foreign_resources(
    owned_root, monkeypatch, clients, foreign
):
    value = {
        "runId": "docsuri-u4-0123456789abcdef",
        "container": "docsuri-u4-0123456789abcdef",
        "volume": "docsuri-u4-0123456789abcdef-pgdata",
        "expiresAt": 100,
    }
    runner.private_json(owned_root / "environment.json", value)
    runner.private_json(owned_root / "failed-evidence.json", {"failed": True})
    expected = {p.name: p.read_bytes() for p in owned_root.iterdir()}
    monkeypatch.setattr(runner, "manifest", lambda path: (None, value))
    monkeypatch.setattr(runner, "require_stopped", lambda: None)

    def resources(_):
        if foreign:
            raise runner.Refused("foreign resource")

    monkeypatch.setattr(runner, "require_resources", resources)
    monkeypatch.setattr(runner, "command", lambda *a, **k: subprocess.CompletedProcess(a, 1, ""))

    class IdleConnection(SqlRecorder):
        def fetchone(self):
            return (
                (clients,) if "pg_stat_activity" in self.last else (value["runId"], runner.DATABASE)
            )

    monkeypatch.setattr(runner, "connect_admin", lambda value: IdleConnection())
    calls = []

    def require(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, json.dumps([{"State": {"Running": False}}]))

    monkeypatch.setattr(runner, "require", require)
    if clients or foreign:
        with pytest.raises(runner.Refused):
            runner.archive_owned(owned_root / "environment.json")
        assert not calls
        assert {p.name: p.read_bytes() for p in owned_root.iterdir()} == expected
    else:
        result = runner.archive_owned(owned_root / "environment.json")
        preserved = Path(result["path"])
        assert not owned_root.exists()
        assert result["expiresAt"] == 100 and result["volumePreserved"] == value["volume"]
        assert {p.name: p.read_bytes() for p in preserved.iterdir()} == expected
        assert calls == [
            ["docker", "stop", "--time", "10", value["container"]],
            ["docker", "container", "inspect", value["container"]],
        ]


def test_bootstrap_refuses_unknown_schema_before_mutation():
    conn = SqlRecorder(schemas=[("foreign",)])
    with pytest.raises(runner.Refused, match="unrecognized schema"):
        runner.install_base(conn, {}, {}, {})
    assert len(conn.statements) == 1 and conn.statements[0][0].startswith("SELECT")


def test_setup_creates_private_identity_once_and_never_reseeds(owned_root, monkeypatch):
    monkeypatch.setattr(runner, "preflight", lambda **kw: {"reserve": True})
    monkeypatch.setattr(runner, "check_ports", lambda: None)
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "synthetic-head\n" if args[0] == "git" else "")

    monkeypatch.setattr(runner, "require", run)
    monkeypatch.setattr(runner, "command", run)
    monkeypatch.setattr(runner, "migrate", lambda path, **kwargs: calls.append(["migrate", kwargs]))
    path = owned_root / "environment.json"
    first = runner.setup(path)
    assert first["state"] == "base-installed"
    value = json.loads(path.read_bytes())
    assert value["container"] == value["runId"]
    assert value["expiresAt"] - value["createdAt"] == 86400
    assert "databaseAdminPassword" not in value
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in owned_root.iterdir())
    created = {p.name: p.read_bytes() for p in owned_root.iterdir()}
    monkeypatch.setattr(runner, "manifest", lambda path: (None, value))
    monkeypatch.setattr(runner, "require_resources", lambda value: None)
    previous_calls = list(calls)
    assert runner.setup(path)["state"] == "preserved"
    assert calls == previous_calls
    assert {p.name: p.read_bytes() for p in owned_root.iterdir()} == created


def test_migration_checks_pinned_server_before_any_schema_work(owned_root, monkeypatch):
    value = {"runId": "synthetic-run"}
    monkeypatch.setattr(runner, "manifest", lambda path: (None, value))
    monkeypatch.setattr(runner, "require_resources", lambda value: None)
    monkeypatch.setattr(runner, "require_stopped", lambda: None)
    conn = SqlRecorder(version="17.1")
    monkeypatch.setattr(runner, "connect_admin", lambda value: conn)
    with pytest.raises(runner.Refused, match="version"):
        runner.migrate(owned_root / "environment.json", base_only=True)
    assert len(conn.statements) == 1


def test_migration_replay_and_changed_bytes_fail_closed(owned_root, monkeypatch):
    value = {"runId": "synthetic-run"}
    monkeypatch.setattr(runner, "manifest", lambda path: (None, value))
    monkeypatch.setattr(runner, "require_resources", lambda value: None)
    monkeypatch.setattr(runner, "require_stopped", lambda: None)
    conn = SqlRecorder(installed=True)
    monkeypatch.setattr(runner, "connect_admin", lambda value: conn)
    monkeypatch.setattr(runner, "amend", lambda conn, value, hashes: dict(hashes))
    result = runner.migrate(owned_root / "environment.json", base_only=True)
    assert result["state"] == "base-verified"
    assert len(conn.statements) == 2
    changed = {path: "changed" for _, path in runner.MIGRATIONS}
    monkeypatch.setattr(runner, "amend", lambda conn, value, hashes: changed)
    with pytest.raises(runner.Refused, match="applied migration changed"):
        runner.migrate(owned_root / "environment.json")


def test_source_identity_includes_runtime_tests_and_pipeline(monkeypatch):
    monkeypatch.setattr(runner, "base_source_identity", lambda: {"files": {}, "sha256": "old"})
    name = "tests/u4_research_novelty/runtime/test_profile_binding.py"
    calls = []

    def listed(args):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, name + "\0")

    monkeypatch.setattr(runner, "require", listed)
    result = runner.source_identity()
    assert result["files"][name] == runner.digest(runner.ROOT / name)
    assert ".github/workflows/u4-research-novelty.yml" in calls[0]
    assert result["sha256"] != "old"


@pytest.mark.parametrize("changed", [None, "databaseImage", "policy", "container", "volume"])
def test_manifest_binds_policy_image_and_resource_identity(owned_root, monkeypatch, changed):
    profile = LocalProfile(
        owned_root,
        "docsuri-u4-0123456789abcdef",
        "https://127.0.0.1:18079",
        15479,
        time.time() + 600,
        "docsuri_u4",
        "research-workspace",
    )
    value = {
        "databaseImage": runner.IMAGE,
        "policy": runner.POLICY,
        "container": profile.run_id,
        "volume": profile.run_id + "-pgdata",
    }
    if changed:
        value[changed] = "foreign"
    path = owned_root / "environment.json"
    runner.private_json(path, value)
    monkeypatch.setattr(runner.LocalProfile, "load", lambda path: profile)
    if changed:
        with pytest.raises(runner.Refused):
            runner.manifest(path)
    else:
        assert runner.manifest(path) == (profile, value)


def test_main_keeps_teardown_preservative_and_rejects_other_paths(owned_root, monkeypatch, capsys):
    path = owned_root / "environment.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--phase",
            "teardown",
            "--profile",
            "synthetic-local",
            "--environment-file",
            str(path),
        ],
    )
    monkeypatch.setattr(runner, "manifest", lambda path: (None, {"runId": "synthetic-run"}))
    assert runner.main() == 0
    assert json.loads(capsys.readouterr().out)["state"] == "preserved"
    sys.argv[-1] = str(owned_root / "foreign.json")
    with pytest.raises(runner.Refused, match="explicit U4"):
        runner.main()


def test_child_environment_excludes_ambient_credentials(monkeypatch, owned_root):
    monkeypatch.setenv("DATABASE_URL", "must-not-propagate")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-propagate")
    environment = runner.child_environment()
    assert "DATABASE_URL" not in environment and "AWS_SECRET_ACCESS_KEY" not in environment
    assert environment["DOCSURI_U4_ENVIRONMENT_FILE"] == str(owned_root / "environment.json")
    assert environment["PLAYWRIGHT_JUNIT_OUTPUT_FILE"] == str(owned_root / "browser.xml")
    assert environment["COREPACK_ENABLE_NETWORK"] == "0"


@pytest.mark.parametrize("outcome", ["ready", "exited", "rss"])
def test_server_start_checks_certificate_readiness_and_bounds(owned_root, monkeypatch, outcome):
    profile = LocalProfile(
        owned_root,
        "docsuri-u4-0123456789abcdef",
        "https://127.0.0.1:18079",
        15479,
        time.time() + 600,
        "docsuri_u4",
        "research-workspace",
    )
    prepare_transport(profile)
    monkeypatch.setattr(runner.LocalProfile, "load", lambda path: profile)
    monkeypatch.setattr(runner, "require_stopped", lambda: None)
    process = SimpleNamespace(pid=1234, poll=lambda: 1 if outcome == "exited" else None)
    launches, stopped = [], []

    def launch(args, **kwargs):
        launches.append((args, kwargs))
        return process

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner, "stop", lambda process: stopped.append(process.pid))
    monkeypatch.setattr(
        runner, "process_rss", lambda *args: runner.MAX_RSS + 1 if outcome == "rss" else 1
    )

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def request(url, **kwargs):
        assert url == "https://127.0.0.1:18079/health/ready"
        assert kwargs["context"].verify_mode == ssl.CERT_REQUIRED
        assert kwargs["context"].check_hostname
        return Response()

    monkeypatch.setattr(runner.urllib.request, "urlopen", request)
    log = owned_root / "startup.log"
    if outcome == "ready":
        assert runner.start_server(owned_root / "environment.json", log) is process
        assert stopped == []
    else:
        with pytest.raises(runner.Refused):
            runner.start_server(owned_root / "environment.json", log)
        assert stopped == [1234]
    assert launches[0][1]["umask"] == 0o077 and launches[0][1]["start_new_session"]
    assert stat.S_IMODE(log.stat().st_mode) == 0o600


@pytest.mark.parametrize("phase", ["setup", "migrate", "archive-legacy", "component"])
def test_main_dispatch_stays_with_explicit_profile(owned_root, monkeypatch, phase):
    path = owned_root / "environment.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--phase",
            phase,
            "--profile",
            "synthetic-local",
            "--environment-file",
            str(path),
        ],
    )
    calls = []
    handler = {
        "setup": "setup",
        "migrate": "migrate",
        "archive-legacy": "archive_legacy",
        "component": "run_phase",
    }[phase]
    monkeypatch.setattr(runner, handler, lambda *args: calls.append(args) or {"state": "observed"})
    assert runner.main() == 0
    assert calls == ([(phase, path)] if phase == "component" else [(path,)])


def test_serving_entrypoint_keeps_owned_identity_tls_and_socket_bounds(owned_root, monkeypatch):
    from scripts import serve_docsuri_u4 as server

    profile = LocalProfile(
        owned_root,
        "docsuri-u4-0123456789abcdef",
        "https://127.0.0.1:18079",
        15479,
        time.time() + 600,
        "docsuri_u4",
        "research-workspace",
    )
    transport = prepare_transport(profile)
    monkeypatch.setattr(server.LocalProfile, "load", lambda path: profile)
    app = SimpleNamespace(state=SimpleNamespace(profile=profile))
    monkeypatch.setitem(
        sys.modules, "backend.u4_host", SimpleNamespace(assemble_u4=lambda profile: app)
    )
    launches = []
    monkeypatch.setattr(server.uvicorn, "run", lambda app, **kwargs: launches.append((app, kwargs)))
    monkeypatch.setattr(
        sys, "argv", ["serve", "--environment-file", str(owned_root / "environment.json")]
    )
    server.main()
    actual_app, config = launches[0]
    assert actual_app is app
    assert config["host"] == "127.0.0.1" and config["port"] == 18079 and config["workers"] == 1
    assert config["ssl_certfile"] == str(transport.certificate) and config["ssl_keyfile"] == str(
        transport.key
    )
    assert not config["access_log"] and not config["proxy_headers"]
    assert config["limit_concurrency"] == 32 and config["backlog"] == 16
    assert config["timeout_keep_alive"] == 5 and config["timeout_graceful_shutdown"] == 10
    app.state.profile = replace(profile, run_id="foreign")
    with pytest.raises(ValueError, match="identity"):
        server.assemble(owned_root / "environment.json")
    monkeypatch.setattr(
        server.LocalProfile, "load", lambda path: replace(profile, realm="corpus-maintenance")
    )
    with pytest.raises(ValueError, match="owned research"):
        server.assemble(owned_root / "environment.json")
