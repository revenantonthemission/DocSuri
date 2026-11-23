"""U6:code-generation-plan:testing-contract-coverage-backend: the coverage floor is the
rcfile's alone (L1-10).

`backend/.coveragerc.u6` holds the floor and the fourteen-pattern include list; the
runner passes no `--cov-fail-under`; the second report measures
`scripts/u6_preservation.py` on its own; no U6 test or migration names U2-only schema;
and the coverage phase records the total and, when it passes, the second report.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from coverage import Coverage
from coverage.config import CoverageConfig

from scripts import verify_docsuri_u5 as u5_runner
from scripts import verify_docsuri_u6 as runner

ROOT = Path(__file__).resolve().parents[3]
INCLUDE = (
    "backend/modules/export/*.py",
    "backend/u6_policy.py",
    "backend/u6_host.py",
    "backend/u6_real_export.py",
    "backend/key_custody.py",
    "backend/modules/accounts/control_keys.py",
    "backend/modules/accounts/services/control_lifecycle.py",
    "backend/modules/accounts/services/guarded_entry.py",
    "backend/modules/personalization/guarded_service.py",
    "backend/u3_host.py",
    "scripts/serve_docsuri_u6.py",
    "scripts/u6_browser_fixtures.py",
    "scripts/u6_preservation.py",
    "scripts/u6_real_export.py",
)
U6_MIGRATIONS = {
    "backend/modules/accounts/u6_lifecycle_guard.sql",
    "backend/modules/export/u6_schema.sql",
    "backend/modules/export/u6_custody.sql",
    "backend/modules/export/u6_maintenance.sql",
}


@pytest.fixture
def owned_root(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "RUN", root)
    return root


def test_the_rcfile_holds_the_floor_and_the_fourteen_patterns():
    config = Coverage(config_file=str(ROOT / "backend/.coveragerc.u6")).config

    assert config.fail_under == 80.0
    assert config.source == ["backend", "scripts"]
    assert config.report_include == list(INCLUDE)
    assert config.report_omit == ["scripts/verify_docsuri_u6.py"]
    assert config.show_missing is True
    assert config.exclude_list == CoverageConfig().exclude_list


def test_the_rcfile_floor_fails_a_shortfall_without_cov_fail_under(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "logic.py").write_text(
        "def covered():\n    return 1\n\n\ndef uncovered():\n    return 2\n"
    )
    (package / "test_logic.py").write_text(
        "from pkg.logic import covered\n\n\ndef test_covered():\n    assert covered() == 1\n"
    )
    strict = tmp_path / "strict.rc"
    strict.write_text("[run]\nsource = pkg\n\n[report]\nfail_under = 100\n")
    lax = tmp_path / "lax.rc"
    lax.write_text("[run]\nsource = pkg\n\n[report]\nfail_under = 1\n")

    def run(config):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "pkg/test_logic.py",
                "--cov=pkg",
                f"--cov-config={config}",
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    failed, passed = run(strict), run(lax)

    assert failed.returncode != 0
    assert "Coverage failure: total of" in failed.stdout
    assert passed.returncode == 0


def test_the_coverage_phase_and_the_second_report_use_the_rcfile_alone(
    owned_root, monkeypatch
):
    args, paths = runner.phase_command("coverage", owned_root / "report.xml")

    assert paths == (runner.TEST_ROOT,)
    assert "--cov" in args and "--cov-config=backend/.coveragerc.u6" in args
    assert "--maxfail=1" in args
    assert not any(argument.startswith("--cov-fail-under") for argument in args)

    captured = {}

    def bounded(command, log, **options):
        captured["command"] = command
        return {"exitCode": 0}

    monkeypatch.setattr(runner, "bounded_process", bounded)
    report = runner.preservation_report(time.monotonic())

    assert "--rcfile=backend/.coveragerc.u6" in captured["command"]
    assert "--include=scripts/u6_preservation.py" in captured["command"]
    assert "--fail-under=80" in captured["command"]
    assert report["exitCode"] == 0 and report["linePercent"] is None


def test_no_u6_test_or_migration_names_u2_only_schema():
    pairs = (
        ("control", "_receipt"),
        ("control", "_proof"),
        ("current", "_restriction"),
        ("lifecycle", "_state"),
        ("flow", "_id"),
    )
    identifiers = [prefix + suffix for prefix, suffix in pairs]
    identifiers.append("u2" + "_controls.sql")
    inspected = [
        *sorted((ROOT / "tests/u6_approved_export").rglob("*.py")),
        ROOT / "backend/pytest.u6-approved-export.ini",
    ]
    for path in inspected:
        text = path.read_text(errors="replace")
        for identifier in identifiers:
            assert identifier not in text, (path.name, identifier)
    u5_paths = {relative for _, relative in u5_runner.MIGRATIONS}
    u6_paths = {relative for _, relative in runner.MIGRATIONS}
    assert all(not relative.endswith(identifiers[-1]) for relative in u6_paths)
    assert u6_paths - u5_paths == U6_MIGRATIONS


def test_the_coverage_evidence_records_the_total_and_the_second_report(
    owned_root, monkeypatch
):
    state = {"code": 1}

    def bounded(command, log, **options):
        Path(log).write_text("TOTAL  4000  500  87.50%\n")
        Path(log).chmod(0o600)
        return {"exitCode": state["code"]}

    monkeypatch.setattr(runner, "bounded_process", bounded)

    _, failing = runner.execute_phase(
        "coverage", owned_root / "environment.json", {}, ["true"], time.monotonic()
    )
    assert failing["coverageTotalPercent"] == 87.5 and "preservationReport" not in failing

    state["code"] = 0
    _, passing = runner.execute_phase(
        "coverage", owned_root / "environment.json", {}, ["true"], time.monotonic()
    )
    assert passing["coverageTotalPercent"] == 87.5 and "preservationReport" in passing
