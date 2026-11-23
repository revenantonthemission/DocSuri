"""U6's environment tool: its phases, chain, key folder, refusals and completeness checks."""

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import verify_docsuri_u5 as u5_runner
from scripts import verify_docsuri_u6 as runner

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "docsuri-u6-0123456789abcdef"
SOURCE_A = {"head": "0" * 40, "sha256": "a" * 64, "files": {"backend/u6_host.py": "1" * 64}}
SOURCE_B = {"head": "0" * 40, "sha256": "b" * 64, "files": {"backend/u6_host.py": "2" * 64}}
PASSING_REPORT = (
    '<testsuites><testsuite><testcase classname="u6" name="passes"/></testsuite></testsuites>'
)
FRESH_REALM = "browser verification requires a fresh realm; preserve this realm before replacement"
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


def private_text(path: Path, text: str, mode: int = 0o600) -> None:
    path.write_text(text)
    path.chmod(mode)


@pytest.fixture
def phase_rig(owned_root, monkeypatch):
    """A real key folder and manifest file over the owned run; the manifest read, resource
    check, preflight, port check, source identity, a report-writing `bounded_process` and
    the fixtures setup are stood in and recorded. `require_key_folder`,
    `require_test_paths`, `preserve_prior_reports`, `junit_counts` and `private_json`
    stay real."""
    runner.create_key_folder()
    path = owned_root / "environment.json"
    private_text(path, json.dumps({"unit": runner.UNIT, "runId": RUN_ID}))
    value = {
        "runId": RUN_ID,
        "policy": runner.POLICY,
        "locks": {name: runner.digest(runner.ROOT / name) for name in runner.LOCKS},
    }
    rig = SimpleNamespace(
        path=path,
        value=value,
        calls=[],
        fixtures=[],
        reads=[],
        after=SOURCE_A,
        report=PASSING_REPORT,
    )

    def source_identity():
        rig.reads.append(len(rig.calls))
        return rig.after if rig.calls else SOURCE_A

    def bounded_process(args, log, **options):
        rig.calls.append(list(args))
        if rig.report is not None:
            for arg in args:
                if arg.startswith("--junitxml="):
                    private_text(Path(arg.removeprefix("--junitxml=")), rig.report)
        return {
            "exitCode": 0,
            "reason": "process-exit",
            "elapsedSeconds": 0.1,
            "peakRssBytes": 1024,
            "peakPssBytes": None,
            "logBytes": 0,
            "processStopped": True,
            "observations": 1,
            "slowestObservationSeconds": 0.0,
        }

    def fixtures_setup(fixture_path):
        rig.fixtures.append(fixture_path)
        return {"state": "fixtures-ready"}

    monkeypatch.setattr(runner, "manifest", lambda manifest_path: (None, value))
    monkeypatch.setattr(runner, "require_resources", lambda manifest_value: None)
    monkeypatch.setattr(runner, "preflight", lambda *, established=False: {"hostFreeBytes": 1})
    monkeypatch.setattr(runner, "require_stopped", lambda port=runner.APPLICATION_PORT: None)
    monkeypatch.setattr(runner, "source_identity", source_identity)
    monkeypatch.setattr(runner, "bounded_process", bounded_process)
    monkeypatch.setattr("scripts.u6_browser_fixtures.setup", fixtures_setup)
    return rig


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
    environment = {
        **os.environ,
        "DOCSURI_U6_ENVIRONMENT_FILE": str(realm.root / "environment.json"),
    }
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
    monkeypatch.setattr(runner, "process_tree_memory", lambda roots, deadline: (1024, None))
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


def test_proportional_bytes_reads_pss_and_falls_back_to_rss(tmp_path, monkeypatch):
    (tmp_path / "7").write_text("Rss:  900 kB\nPss:  300 kB\n")
    monkeypatch.setattr(runner, "SMAPS_ROLLUP", str(tmp_path / "{pid}"))
    assert runner.proportional_bytes(7, 900) == 300 * 1024
    # A process that exited before the read counts its full RSS.
    assert runner.proportional_bytes(8, 900) == 900 * 1024


def test_process_tree_memory_enforces_pss_only_on_linux(monkeypatch):
    table = "\n".join(["10 1 100", "11 10 200", "30 1 9999"])
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda args, **k: subprocess.CompletedProcess(args, 0, stdout=table),
    )
    monkeypatch.setattr(runner, "proportional_bytes", lambda pid, kib: kib * 1024 // 4)
    deadline = time.monotonic() + 30
    monkeypatch.setattr(runner.sys, "platform", "darwin")
    assert runner.process_tree_memory((10,), deadline) == (300 * 1024, None)
    monkeypatch.setattr(runner.sys, "platform", "linux")
    assert runner.process_tree_memory((10,), deadline) == (300 * 1024, 75 * 1024)
    assert runner.process_tree_rss((10,), deadline) == 300 * 1024


@pytest.mark.parametrize("over", ["pss", "rss"])
def test_supervision_enforces_the_proportional_budget_where_measured(owned_root, monkeypatch, over):
    big = runner.MAX_RSS + 1
    reading = (1024, big) if over == "pss" else (big, 1024)
    monkeypatch.setattr(runner, "process_tree_memory", lambda roots, deadline: reading)
    command = [sys.executable, "-c", "import time; time.sleep(0.3)"]
    if over == "pss":
        with pytest.raises(runner.Refused) as refused:
            runner.bounded_process(command, owned_root / "pss.log", seconds=5)
        assert refused.value.supervision["reason"] == "rss-limit"
        assert refused.value.supervision["peakPssBytes"] == big
    else:
        # Shared pages inflate the RSS sum; the proportional sum is under budget.
        result = runner.bounded_process(command, owned_root / "rss.log", seconds=5)
        assert result["exitCode"] == 0
        assert (result["peakRssBytes"], result["peakPssBytes"]) == (big, 1024)


def test_serve_bound_ends_normally_and_other_phases_fail_at_it(owned_root, monkeypatch):
    monkeypatch.setattr(runner, "process_tree_memory", lambda roots, deadline: (1024, None))
    sleeper = [sys.executable, "-c", "import time; time.sleep(30)"]
    stopped = runner.bounded_process(
        sleeper, owned_root / "serve.log", seconds=1, allow_bounded_stop=True
    )
    assert (stopped["reason"], stopped["exitCode"]) == ("bounded-stop", 0)
    with pytest.raises(runner.Refused, match="deadline") as failure:
        runner.bounded_process(sleeper, owned_root / "phase.log", seconds=1)
    assert failure.value.supervision["reason"] == "deadline"


def test_junit_counts_reports_totals_and_the_per_class_table(owned_root):
    report = owned_root / "report.xml"
    report.write_text(
        "<testsuites><testsuite>"
        '<testcase classname="classA" name="one"/>'
        '<testcase classname="classA" name="two"/>'
        '<testcase classname="classA" name="three"><failure/></testcase>'
        '<testcase classname="classB" name="four"><skipped/></testcase>'
        "</testsuite></testsuites>"
    )
    report.chmod(0o600)
    evidence = {"exitCode": 0}

    runner.junit_counts(report, evidence)

    assert (evidence["tests"], evidence["failures"], evidence["skipped"], evidence["errors"]) == (
        4,
        1,
        1,
        0,
    )
    assert evidence["testsByClass"] == {"classA": 3, "classB": 1}
    assert evidence["exitCode"] == 1
    summary = runner.safe_phase_summary(evidence)
    assert summary["tests"] == 4 and "testsByClass" not in summary

    empty = owned_root / "empty.xml"
    empty.write_text("<testsuites/>")
    empty.chmod(0o600)
    empty_evidence = {"exitCode": 0}
    runner.junit_counts(empty, empty_evidence)
    assert (empty_evidence["tests"], empty_evidence["testsByClass"]) == (0, {})
    assert empty_evidence["exitCode"] == 1

    missing = {"exitCode": 0}
    runner.junit_counts(owned_root / "absent.xml", missing)
    assert missing["missingTestReport"] is True and missing["exitCode"] == 1

    malformed = owned_root / "broken.xml"
    malformed.write_text("<testsuites>")
    malformed.chmod(0o600)
    invalid = {"exitCode": 0}
    runner.junit_counts(malformed, invalid)
    assert invalid["invalidTestReport"] is True and invalid["exitCode"] == 1


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


@pytest.mark.parametrize(
    "prior",
    [
        "database-evidence-1.json",
        "coverage-evidence-1.json",
        "serve-evidence-1.json",
        "browser-evidence-1.json",
    ],
    ids=["development", "coverage", "serve", "earlier-browser"],
)
def test_browser_refuses_an_environment_holding_evidence_before_any_child(
    phase_rig, owned_root, monkeypatch, prior
):
    rig, hosts = phase_rig, []

    def no_child(args, log, **options):
        rig.calls.append(list(args))
        raise AssertionError("no child starts")

    def no_host(path, log):
        hosts.append(path)
        raise AssertionError("no host starts")

    monkeypatch.setattr(runner, "bounded_process", no_child)
    monkeypatch.setattr(runner, "start_server", no_host)
    recorded = {"phase": prior.split("-")[0]}
    runner.private_json(owned_root / prior, recorded)

    with pytest.raises(runner.Refused) as refused:
        runner.dispatch("browser", rig.path)

    assert str(refused.value) == FRESH_REALM
    assert (rig.calls, hosts, rig.fixtures, rig.reads) == ([], [], [], [])
    assert sorted(p.name for p in owned_root.iterdir()) == sorted(
        [prior, "environment.json", runner.KEY_FOLDER]
    )
    assert json.loads((owned_root / prior).read_text()) == recorded
    assert stat.S_IMODE((owned_root / prior).stat().st_mode) == 0o600
    assert runner.prepare_phase("database", rig.path) == (rig.value, {"hostFreeBytes": 1})
    assert rig.fixtures == []
    (owned_root / prior).unlink()
    assert runner.prepare_phase("browser", rig.path) == (rig.value, {"hostFreeBytes": 1})
    assert rig.fixtures == [rig.path]


@pytest.mark.parametrize("after", [SOURCE_A, SOURCE_B], ids=["unchanged", "changed"])
def test_a_phase_fails_when_its_source_changes_during_the_run(phase_rig, owned_root, capsys, after):
    rig = phase_rig
    rig.after = after
    changed = after is SOURCE_B

    if changed:
        with pytest.raises(runner.Refused) as refused:
            runner.run_phase("database", rig.path)
        assert str(refused.value) == "U6 phase failed; evidence preserved"
    else:
        assert runner.run_phase("database", rig.path) == {"state": "passed", "phase": "database"}

    assert rig.calls == [runner.phase_command("database", owned_root / "database.xml")[0]]
    assert rig.reads == [0, 1]
    [record] = owned_root.glob("database-evidence-*.json")
    assert stat.S_IMODE(record.stat().st_mode) == 0o600
    evidence = json.loads(record.read_text())
    summary = json.loads(capsys.readouterr().out)
    assert evidence["source"] == SOURCE_A
    counts = tuple(evidence[key] for key in ("tests", "failures", "errors", "skipped"))
    assert counts == (1, 0, 0, 0)
    assert evidence["supervision"]["exitCode"] == 0 and evidence["failureCategory"] is None
    assert "missingTestReport" not in evidence and "invalidTestReport" not in evidence
    if changed:
        assert (evidence["sourceChangedDuringRun"], evidence["exitCode"]) == (True, 1)
        assert (summary["sourceChangedDuringRun"], summary["exitCode"]) == (True, 1)
    else:
        assert evidence["exitCode"] == 0 and summary["exitCode"] == 0
        assert "sourceChangedDuringRun" not in evidence
        assert "sourceChangedDuringRun" not in summary


def test_source_identity_sees_a_changed_or_added_listed_file_only(tmp_path, monkeypatch):
    """A temporary repository stands in for the checkout; no real file is edited."""
    git = shutil.which("git")
    assert git is not None
    repository = tmp_path / "repository"
    repository.mkdir()
    isolated = [
        "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
        "-c", "tag.gpgsign=false", "-c", "init.templateDir=",
        "-c", "user.email=u6@test.invalid", "-c", "user.name=u6",
    ]  # fmt: skip

    def run(*args: str) -> None:
        subprocess.run(
            [git, *isolated, *args], cwd=repository, check=True, capture_output=True, timeout=60
        )

    def plant(relative: str, text: str) -> None:
        target = repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    run("init", "-q")
    plant("backend/module.py", "one = 1\n")
    plant(".gitignore", "backend/ignored.py\n")
    run("add", "-A")
    run("commit", "-q", "--no-verify", "-m", "planted")
    real = runner.command
    monkeypatch.setattr(runner, "ROOT", repository)
    monkeypatch.setattr(
        runner, "command", lambda args, **options: real(args, **{**options, "cwd": repository})
    )

    first = runner.source_identity()
    assert set(first["files"]) == {"backend/module.py"}
    plant("backend/module.py", "one = 2\n")
    tracked = runner.source_identity()
    assert tracked["sha256"] != first["sha256"] and tracked["head"] == first["head"]
    added_path = "tests/u6_approved_export/operations/test_added.py"
    plant(added_path, "def test_added():\n    pass\n")
    added = runner.source_identity()
    assert added_path in added["files"] and added["sha256"] != tracked["sha256"]
    plant("backend/ignored.py", "ignored = True\n")
    plant("aidlc/note.md", "outside the listed folders\n")
    assert runner.source_identity()["sha256"] == added["sha256"]


VERDICT_CASES = {
    "skip-alone": (
        "<skipped/>",
        {"exitCode": 1, "tests": 2, "failures": 0, "errors": 0, "skipped": 1},
    ),
    "error-alone": (
        "<error/>",
        {"exitCode": 1, "tests": 2, "failures": 0, "errors": 1, "skipped": 0},
    ),
    "failure-alone": (
        "<failure/>",
        {"exitCode": 1, "tests": 2, "failures": 1, "errors": 0, "skipped": 0},
    ),
}


@pytest.mark.parametrize("case", [*VERDICT_CASES, "wrongly-moded"])
def test_each_junit_verdict_alone_fails_the_phase(owned_root, case):
    report = owned_root / "report.xml"
    if case == "wrongly-moded":
        private_text(report, PASSING_REPORT, 0o644)
        expected = {"exitCode": 1, "invalidTestReport": True}
    else:
        child, counts = VERDICT_CASES[case]
        private_text(
            report,
            "<testsuites><testsuite>"
            '<testcase classname="classA" name="one"/>'
            f'<testcase classname="classA" name="two">{child}</testcase>'
            "</testsuite></testsuites>",
        )
        expected = {**counts, "testsByClass": {"classA": 2}}
    evidence = {"exitCode": 0}

    runner.junit_counts(report, evidence)

    assert evidence == expected
