"""U6's environment tool: its phases, chain, key folder, refusals and completeness checks."""

import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest
from scripts import verify_docsuri_u5 as u5_runner
from scripts import verify_docsuri_u6 as runner

ROOT = Path(__file__).resolve().parents[3]
LAYERS = ("database", "repository", "component", "integration", "operations")
# R-06: every realm-exact name of U5's environment and its U6 counterpart.
REALM_PAIRS = {
    "topics-digests": "approved-export",
    "docsuri_u5": "docsuri_u6",
    "127.0.0.1:18089": "127.0.0.1:18099",
    "/tmp/docsuri-u5-run": "/tmp/docsuri-u6-run",
    '"u5"': '"u6"',
}


@pytest.fixture
def owned_root(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "RUN", root)
    return root


def test_phase_catalog_and_constants():
    assert runner.PHASES == (
        "setup",
        "migrate",
        "fixtures",
        "archive-owned",
        "database",
        "repository",
        "component",
        "integration",
        "operations",
        "coverage",
        "frontend",
        "browser",
        "serve",
        "teardown",
        "create-key-after-loss",
        "rotate-key",
        "retire-key",
        "key-counts",
    )
    assert (runner.UNIT, runner.REALM, runner.DATABASE) == (
        "u6-approved-export",
        "approved-export",
        "docsuri_u6",
    )
    assert (runner.APPLICATION_PORT, runner.DATABASE_PORT) == (18099, 15499)
    assert (runner.LABEL, runner.POLICY, runner.PHASE_SECONDS) == (
        "dev.docsuri.u6.run",
        "u6-synthetic-v1",
        300,
    )
    assert runner.RUN == Path("/tmp/docsuri-u6-run").resolve()
    assert runner.OWNERS == u5_runner.OWNERS | {"export"}


def test_migrations_are_u5s_chain_then_the_four_u6_files():
    assert runner.MIGRATIONS[: len(u5_runner.MIGRATIONS)] == u5_runner.MIGRATIONS
    assert runner.MIGRATIONS[len(u5_runner.MIGRATIONS) :] == (
        ("accounts", "backend/modules/accounts/u6_lifecycle_guard.sql"),
        ("export", "backend/modules/export/u6_schema.sql"),
        ("export", "backend/modules/export/u6_custody.sql"),
        ("export", "backend/modules/export/u6_maintenance.sql"),
    )
    for owner, relative in runner.MIGRATIONS:
        assert owner in runner.OWNERS and (ROOT / relative).is_file(), relative


def test_setup_creates_an_empty_private_key_folder(owned_root):
    runner.create_key_folder()
    folder = owned_root / runner.KEY_FOLDER
    info = folder.lstat()
    assert stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700
    assert list(folder.iterdir()) == []
    runner.require_key_folder()
    with pytest.raises(runner.Refused, match="already exists"):
        runner.create_key_folder()
    folder.chmod(0o750)
    with pytest.raises(runner.Refused, match="key folder custody"):
        runner.require_key_folder()


def test_teardown_refuses_while_a_key_file_exists(owned_root, monkeypatch):
    from backend.modules.export.token_keyring import KEY_FILE

    monkeypatch.setattr(runner, "manifest", lambda path: (None, {"runId": "docsuri-u6-x"}))
    folder = owned_root / runner.KEY_FOLDER
    folder.mkdir(mode=0o700)
    assert runner.teardown(owned_root / "environment.json")["state"] == "preserved"
    (folder / KEY_FILE).write_bytes(b"{}")
    with pytest.raises(runner.Refused, match="archive-owned"):
        runner.teardown(owned_root / "environment.json")
    assert (folder / KEY_FILE).exists()


def test_serve_never_passes_the_real_export_flag(owned_root, monkeypatch):
    path = owned_root / "environment.json"
    assert "--real-export" not in runner.serve_command(path)
    calls = []

    def bounded(args, log, **options):
        calls.append((args, options))
        return {"exitCode": 0, "reason": "bounded-stop"}

    monkeypatch.setattr(runner, "bounded_process", bounded)
    monkeypatch.setattr(runner, "source_identity", lambda: {"sha256": "0" * 64})
    result = runner.run_serve(path, {"runId": "docsuri-u6-x", "locks": {}}, {})
    assert result == {"state": "experiment-ended", "completionVerification": False}
    assert calls[0][0] == runner.serve_command(path)
    assert "--real-export" not in calls[0][0] and calls[0][1]["allow_bounded_stop"] is True
    assert [p.name for p in owned_root.glob("serve-evidence-*.json")]


def test_phase_test_paths_list_files_and_unlisted_paths_refuse():
    for phase in (*runner.TEST_PHASES, "frontend", "browser"):
        _, paths = runner.phase_command(phase, Path("/tmp/report.xml"))
        runner.require_test_paths(paths)
    # Ignored (the coverage data file and folder) and absent paths list nothing.
    for name in (".coverage", "frontend/coverage", "tests/u6_approved_export/absent"):
        with pytest.raises(runner.Refused, match="lists no"):
            runner.require_test_paths((name,))


def test_every_synthetic_phase_refuses_beside_real_export_settings(owned_root):
    assert runner.SYNTHETIC_PHASES == {
        "fixtures",
        *runner.TEST_PHASES,
        "frontend",
        "browser",
        "serve",
    }
    assert not runner.SYNTHETIC_PHASES & {"archive-owned", "teardown", *runner.KEY_PHASES}
    (owned_root / runner.ACTIVATION_FILE).write_text("{}")
    for phase in sorted(runner.SYNTHETIC_PHASES):
        with pytest.raises(runner.Refused, match="real-export settings"):
            runner.dispatch(phase, owned_root / "environment.json")


def test_only_retire_key_takes_a_version(owned_root):
    with pytest.raises(runner.Refused, match="--version"):
        runner.dispatch("key-counts", owned_root / "environment.json", "u6-" + "0" * 32)
    with pytest.raises(runner.Refused, match="--version"):
        runner.dispatch("retire-key", owned_root / "environment.json")
    with pytest.raises(runner.Refused, match="--version"):
        runner.dispatch("teardown", owned_root / "environment.json", "u6-" + "0" * 32)


def test_every_layer_folder_collects_at_least_one_test(realm):
    """R-08: beside the tool's refusal of zero tests, each layer collects tests."""
    environment = {**os.environ, "DOCSURI_U6_ENVIRONMENT_FILE": str(realm.root / "environment.json")}
    for layer in LAYERS:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-c",
                "backend/pytest.u6-approved-export.ini",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
                f"tests/u6_approved_export/{layer}",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, layer
        collected = [line for line in result.stdout.splitlines() if "::test_" in line]
        assert collected, layer


def listed_python() -> list[Path]:
    names = runner.listed_files("backend", "ops/src")
    return [
        Path(name)
        for name in names
        if name.endswith(".py")
        and not name.startswith("backend/modules/topics/")
        and not (name.startswith("backend/u5_") and "/" not in name[len("backend/") :])
    ]


def test_every_file_naming_the_u5_environment_names_its_u6_counterpart():
    """R-06 completeness: a realm-exact U5 allowlist without its U6 entry fails."""
    files = listed_python()
    assert len(files) > 100
    gaps = []
    for path in files:
        text = (ROOT / path).read_text(errors="replace")
        gaps += [
            (str(path), name)
            for name, counterpart in REALM_PAIRS.items()
            if name in text and counterpart not in text
        ]
    assert gaps == []
    assert "backend/local_profile.py" in {str(path) for path in files}


def test_private_json_and_runner_lock(owned_root):
    target = owned_root / "evidence.json"
    runner.private_json(target, {"tests": 3})
    assert json.loads(target.read_text()) == {"tests": 3}
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    alias = owned_root / "alias.json"
    alias.symlink_to(target)
    with pytest.raises(runner.Refused):
        runner.private_json(alias, {"tests": 9})
    with runner.exclusive():
        with pytest.raises(runner.Refused, match="active"):
            with runner.exclusive():
                pass


def test_child_environment_binds_the_manifest_and_browser_report(owned_root):
    environment = runner.child_environment()
    assert environment["DOCSURI_U6_ENVIRONMENT_FILE"] == str(owned_root / "environment.json")
    assert environment["PLAYWRIGHT_JUNIT_OUTPUT_FILE"] == str(owned_root / "browser.xml")
    assert environment["COREPACK_ENABLE_NETWORK"] == "0"
    assert runner.CLOCK_CAPABILITY not in environment


def test_clock_delegation_is_bounded_owned_and_revoked(owned_root, monkeypatch):
    value = {"runId": "owned-clock", "expiresAt": time.time() + 120}
    with pytest.raises(runner.Refused, match="ownership"):
        with runner.browser_clock_delegation(value, 60):
            pass
    with runner.exclusive(), runner.browser_clock_delegation(value, 60) as token:
        monkeypatch.setenv(runner.CLOCK_CAPABILITY, token)
        runner.authorize_clock_child(value)
        assert token not in (owned_root / runner.CLOCK_DELEGATION).read_text()
        monkeypatch.setenv(runner.CLOCK_CAPABILITY, "different")
        with pytest.raises(runner.Refused, match="differs"):
            runner.authorize_clock_child(value)
        with pytest.raises(runner.Refused, match="differs"):
            monkeypatch.setenv(runner.CLOCK_CAPABILITY, token)
            runner.authorize_clock_child(dict(value, runId="foreign"))
    assert not (owned_root / runner.CLOCK_DELEGATION).exists()
    monkeypatch.delenv(runner.CLOCK_CAPABILITY)
    with pytest.raises(runner.Refused, match="unavailable"):
        runner.authorize_clock_child(value)


def test_browser_supervision_watches_the_host_and_stops_at_its_exit(owned_root, monkeypatch):
    monkeypatch.setattr(runner, "process_tree_rss", lambda roots, deadline: 1024)
    companion = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.2)"])
    log = owned_root / "host.log"
    log.write_bytes(b"")
    try:
        with pytest.raises(runner.Refused) as failure:
            runner.bounded_process(
                [sys.executable, "-c", "import time; time.sleep(20)"],
                owned_root / "browser.log",
                seconds=10,
                companion=companion,
                companion_log=log,
            )
    finally:
        companion.wait()
    assert failure.value.supervision["reason"] == "companion-exit"
    assert failure.value.supervision["processStopped"] is True


def test_serve_bound_ends_normally_and_other_phases_fail_at_it(owned_root, monkeypatch):
    monkeypatch.setattr(runner, "process_tree_rss", lambda roots, deadline: 1024)
    sleeper = [sys.executable, "-c", "import time; time.sleep(30)"]
    stopped = runner.bounded_process(
        sleeper, owned_root / "serve.log", seconds=1, allow_bounded_stop=True
    )
    assert (stopped["reason"], stopped["exitCode"]) == ("bounded-stop", 0)
    with pytest.raises(runner.Refused, match="deadline") as failure:
        runner.bounded_process(sleeper, owned_root / "phase.log", seconds=1)
    assert failure.value.supervision["reason"] == "deadline"


def test_prior_browser_evidence_is_preserved_with_its_inventory(owned_root):
    report = owned_root / "browser.xml"
    report.write_text("<testsuites/>")
    report.chmod(0o600)
    evidence = owned_root / "browser-evidence"
    evidence.mkdir(mode=0o700)
    (evidence / "result.txt").write_text("synthetic")
    (evidence / "result.txt").chmod(0o600)
    preserved = runner.preserve_prior_reports("browser")
    assert {item["original"] for item in preserved} == {"browser.xml", "browser-evidence"}
    assert not report.exists() and not evidence.exists()
    with pytest.raises(runner.Refused, match="verification phase"):
        runner.preserve_prior_reports("serve")


def test_coverage_figures_are_read_from_the_report_lines(owned_root):
    log = owned_root / "coverage.log"
    log.write_text(
        "Name  Stmts  Miss  Cover  Missing\n"
        "scripts/u6_preservation.py  120  6  95%  10-12\n"
        "TOTAL  4000  500  87.50%\n"
    )
    log.chmod(0o600)
    assert runner.coverage_percent(log) == 87.5
    (owned_root / "empty.log").write_text("nothing\n")
    (owned_root / "empty.log").chmod(0o600)
    assert runner.coverage_percent(owned_root / "empty.log") is None
    assert runner.coverage_percent(owned_root / "absent.log") is None
