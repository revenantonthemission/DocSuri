"""U8's two coverage reports each floor at 80% and share no file (U8 plan Step 97(f),
(m)-(o); unit-test-instructions "coverage-reports-disjoint").

Each report's include list is expanded with coverage.py's own `GlobMatcher` (coverage
7.10.7) over the repository's listing (`git ls-files --cached --others
--exclude-standard`), minus its omit list. An independent set of U8's files, taken from
the code-generation source manifest's writes and from recursive patterns, must have each
file in exactly one report, apart from a literal leave-out list, each entry with its
reason.
"""

from __future__ import annotations

import configparser
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from coverage.files import GlobMatcher

ROOT = Path(__file__).resolve().parents[3]
U8_RC = "backend/.coveragerc.u8"
MACOS_RC = "backend/.coveragerc.u8-macos"
MANIFEST = ("aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/"
            "u8-service-operations-integration/code-generation/source-manifest.json")
MACOS_ADAPTERS = ("ops/src/docsuri_ops/arrangement/macos.py",
                  "ops/src/docsuri_ops/standing/macos.py",
                  "ops/src/docsuri_ops/isolation_macos.py")
EXPORT_FILES = ("backend/modules/export/lane.py", "backend/modules/export/service.py",
                "backend/modules/export/binding.py")
# U8's files by pattern, so a file without a `u8_` segment is still taken in.
RECURSIVE = (
    "backend/u8_*.py", "backend/**/u8_*.py", "backend/modules/operations/**/*.py",
    *(f"ops/src/docsuri_ops/{folder}/**/*.py" for folder in (
        "arrangement", "backup_agent", "standing", "migration", "cutover", "u8_platform")),
    "ops/src/**/u8_*.py", "scripts/u8_*.py", "scripts/serve_docsuri_u8.py",
)
# Files the independent set leaves out, each with its reason.
LEAVE_OUT = {
    "scripts/verify_docsuri_u8.py":
        "the runner, the measurement harness the instructions leave unmeasured",
    **{f"scripts/verify_docsuri_u{unit}.py":
       "an earlier unit's runner, test tooling U8's helper change reaches (L1-22)"
       for unit in (2, 3, 4, 5)},
    "scripts/verify_docsuri_u1.py":
        "an earlier unit's runner, test tooling that L1-76's helper change reaches, left "
        "out as L1-22 leaves out the runners of U2 to U5 (Step 97(m))",
    "scripts/prepare_docsuri_u2_browser.py":
        "an earlier unit's launcher, test tooling that L1-77's one environment line "
        "reaches, left out as L1-22 and (m) leave out the earlier runners (Step 97(n))",
    "scripts/verify_docsuri_u7.py":
        "an earlier unit's runner, test tooling that L1-77's one environment line "
        "reaches, left out as L1-22 and (m) leave out the earlier runners (Step 97(n))",
    "scripts/bootstrap_docsuri_u1.py":
        "an earlier unit's bootstrap, test tooling that builds only U1's local test "
        "realms, which L1-80's list reaches, left out as L1-22 and (m) do (Step 97(o))",
    "scripts/verify_docsuri_u6.py":
        "an earlier unit's runner, its one DOCKER_HOST line (L1-76) reached as the other "
        "runners' are; left out by your answer \"Leave it out like the others\"",
    # The files of PR #53 (2026-10-19) the manifest claims only for the completion check,
    # which U8 did not change.
    "backend/app.py": "PR #53, claimed for the completion check only",
    "backend/modules/library/validation.py": "PR #53, claimed for the completion check only",
    "backend/modules/personalization/reset_repository.py":
        "PR #53, claimed for the completion check only",
    "backend/modules/summarization/src/**": "PR #53, claimed for the completion check only",
    "backend/modules/summarization/tests/**":
        "PR #53, claimed for the completion check only",
    "backend/tests/**": "PR #53, claimed for the completion check only",
}
# The earlier runners and tooling neither report holds.
IN_NEITHER = ("scripts/verify_docsuri_u8.py", "scripts/verify_docsuri_u1.py",
              "scripts/verify_docsuri_u2.py", "scripts/verify_docsuri_u3.py",
              "scripts/verify_docsuri_u4.py", "scripts/verify_docsuri_u5.py",
              "scripts/verify_docsuri_u6.py", "scripts/verify_docsuri_u7.py",
              "scripts/prepare_docsuri_u2_browser.py", "scripts/bootstrap_docsuri_u1.py")


def report_list(path: Path, key: str) -> list[str]:
    parser = configparser.RawConfigParser()
    parser.read(path)
    return [line.strip() for line in parser.get("report", key, fallback="").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def fail_under(path: Path) -> str:
    parser = configparser.RawConfigParser()
    parser.read(path)
    return parser.get("report", "fail_under")


def listing() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
        capture_output=True, check=True, timeout=60)
    return sorted(set(completed.stdout.decode().split("\0")) - {""})


def expanded(path: Path, files: list[str]) -> set[str]:
    """A report's files: its include list over the listing, minus its omit list."""
    include = GlobMatcher(report_list(path, "include"), "include")
    omit = report_list(path, "omit")
    omitted = GlobMatcher(omit, "omit") if omit else None
    return {name for name in files if include.match(name)
            and not (omitted and omitted.match(name))}


def independent(files: list[str]) -> set[str]:
    """U8's files: the manifest's `.py` writes under `backend/`, `ops/src/` and `scripts/`,
    the recursive patterns, and U6's three export files, less the leave-out list."""
    manifest = json.loads((ROOT / MANIFEST).read_text())
    written = {item["path"] for item in manifest["writes"]
               if item["path"].endswith(".py")
               and item["path"].startswith(("backend/", "ops/src/", "scripts/"))}
    patterns = GlobMatcher(RECURSIVE, "recursive")
    chosen = written | {name for name in files if patterns.match(name)} | set(EXPORT_FILES)
    left_out = GlobMatcher(LEAVE_OUT, "leave-out")
    return {name for name in chosen if not left_out.match(name) and name in files}


def report_problems(u8_rc: Path, macos_rc: Path, files: list[str]) -> list[str]:
    """Each file of the independent set in both reports or in neither, named."""
    u8, macos = expanded(u8_rc, files), expanded(macos_rc, files)
    problems = [f"in both reports: {name}" for name in sorted(u8 & macos)]
    problems += [f"in neither report: {name}" for name in sorted(independent(files))
                 if (name in u8) == (name in macos)
                 and f"in both reports: {name}" not in problems]
    return problems


@pytest.fixture
def runner():
    from scripts import verify_docsuri_u8

    return verify_docsuri_u8


def test_the_two_reports_each_floor_at_80_and_share_no_file(runner, monkeypatch, tmp_path):
    u8_rc, macos_rc = ROOT / U8_RC, ROOT / MACOS_RC
    assert fail_under(u8_rc) == "80" and fail_under(macos_rc) == "80"
    files = listing()
    u8, macos = expanded(u8_rc, files), expanded(macos_rc, files)
    assert u8 and macos and not u8 & macos
    assert sorted(macos) == sorted(MACOS_ADAPTERS)
    assert sorted(report_list(u8_rc, "omit")) == sorted(
        ["scripts/verify_docsuri_u8.py", *MACOS_ADAPTERS])
    # A set from names alone would miss these files without a `u8_` segment.
    chosen = independent(files)
    for name in ("ops/src/docsuri_ops/isolation_check.py", "backend/production_boundary.py",
                 "backend/modules/accounts/entry_limits.py", *EXPORT_FILES):
        assert name in chosen, name
    assert report_problems(u8_rc, macos_rc, files) == []
    for name in IN_NEITHER:
        assert name not in u8 and name not in macos and name not in chosen, name
    # U6's three export files sit under the owner heading of `.coveragerc.u8` (L1-6, L1-7).
    text = u8_rc.read_text()
    owner = text[text.index("# Owner files U8 changes."):text.index("omit =")]
    for name in EXPORT_FILES:
        assert f"\n    {name}\n" in owner, name
    # Every coverage part names `.coveragerc.u8`; so does `coverage-report`.
    for part in runner.COVERAGE_PARTS:
        args, _paths = runner.phase_command(part, tmp_path / f"{part}.xml")
        assert f"--cov-config={U8_RC}" in args, part
    assert f"--rcfile={U8_RC}" in coverage_report_args(runner, monkeypatch, tmp_path)
    assert f"--cov-config={MACOS_RC}" in arrangement_args(runner, monkeypatch, tmp_path)
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    step = ci[ci.index("- name: U8 arrangement suite on macOS"):]
    assert f"--cov-config={MACOS_RC}" in step.split("- name:", 2)[1]


def coverage_report_args(runner, monkeypatch, tmp_path) -> list[str]:
    run = tmp_path / "report"
    run.mkdir()
    monkeypatch.setattr(runner, "RUN", run)
    (run / runner.COVERAGE_DATA).write_text("data")
    monkeypatch.setattr(runner, "prepare_phase", lambda path: ({"runId": "r"}, {}))
    monkeypatch.setattr(runner, "coverage_parts_state", lambda run_, run_id: {
        "parts": {}, "missingParts": [], "staleParts": [], "failedParts": [],
        "runsSinceFirstPart": []})
    monkeypatch.setattr(runner, "source_identity", lambda: {"sha256": "a" * 64})
    monkeypatch.setattr(runner, "private_json", lambda path, value: None)
    seen = []
    monkeypatch.setattr(runner, "bounded_process",
                        lambda args, log, **options: seen.append(args) or {"exitCode": 0})
    runner.run_coverage_report(run / "environment.json")
    return seen[0]


def arrangement_args(runner, monkeypatch, tmp_path) -> list[str]:
    from types import SimpleNamespace

    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import u8_phases

    run = tmp_path / "arrangement"
    run.mkdir()
    monkeypatch.setattr(u8_phases.sys, "platform", "darwin")
    seen = []
    monkeypatch.setattr(u8_phases, "run_child", lambda runner_, phase, args, started, **o: (
        seen.append(args) or {"command": args, "exitCode": 0, "supervision": {}}))
    monkeypatch.setattr(u8_phases, "record", lambda runner_, phase, evidence: evidence)

    def no_command(args, **options):
        raise AssertionError("no sudo or chown runs")

    stand_in = SimpleNamespace(
        RUN=run, PYTHON=runner.PYTHON, PYTEST_INI=runner.PYTEST_INI, Refused=runner.Refused,
        junit_counts=lambda report, evidence: None,
        prepare_phase=lambda path: ({"runId": "r"}, {}),
        require_test_paths=lambda paths, **options: None,
        source_identity=lambda: {"sha256": "a" * 64}, command=no_command)
    u8_phases.run_arrangement(stand_in, run / "environment.json")
    return seen[0]


def configurations(tmp_path: Path) -> tuple[Path, Path]:
    u8_rc, macos_rc = tmp_path / ".coveragerc.u8", tmp_path / ".coveragerc.u8-macos"
    shutil.copyfile(ROOT / U8_RC, u8_rc)
    shutil.copyfile(ROOT / MACOS_RC, macos_rc)
    return u8_rc, macos_rc


def test_a_file_in_both_reports_or_in_neither_fails_the_check(tmp_path):
    files = listing()
    u8_rc, macos_rc = configurations(tmp_path)
    assert report_problems(u8_rc, macos_rc, files) == []
    # An adapter added to `.coveragerc.u8` (named in its include list, and no longer
    # omitted) is in both reports.
    adapter = MACOS_ADAPTERS[0]
    text = u8_rc.read_text()
    omit = f"omit =\n    scripts/verify_docsuri_u8.py\n    {adapter}\n"
    assert omit in text
    u8_rc.write_text(text.replace(omit, "omit =\n    scripts/verify_docsuri_u8.py\n")
                     .replace("include =\n", f"include =\n    {adapter}\n", 1))
    assert report_problems(u8_rc, macos_rc, files) == [f"in both reports: {adapter}"]
    # An include removed: a U8 file without a `u8_` segment is in neither report.
    u8_rc, macos_rc = configurations(tmp_path)
    u8_rc.write_text(u8_rc.read_text().replace(
        "    ops/src/docsuri_ops/logrotate.py\n", ""))
    assert report_problems(u8_rc, macos_rc, files) == [
        "in neither report: ops/src/docsuri_ops/logrotate.py"]
    # A file planted in a subfolder the include list's single-level pattern misses.
    u8_rc, macos_rc = configurations(tmp_path)
    planted = "ops/src/docsuri_ops/u8_platform/sub/x.py"
    assert report_problems(u8_rc, macos_rc, [*files, planted]) == [
        f"in neither report: {planted}"]
