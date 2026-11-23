"""No U8 floor, bound, budget or target is lowered, and no file leaves a coverage list
(U8 plan Step 97(e); the testing contract's no-weakening rule).

Every value checked here is a literal, so a change that lowers one fails this test. The
first-load budget and the performance verdict are each shown failing just past their
limit. The planted first-load cases of build batch 9a's fix pass (a budget passed and a
missing file, each leaving no manifest) stay in `operations/test_u8_tool.py`, where they
were written, so each runs exactly once.
"""

from __future__ import annotations

import configparser
import random
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]

# `.coveragerc.u8`'s include list as it stands on 2026-11-11, frozen: the plan's 105
# patterns with Step 53(h)'s `u8_mail_outbox.py`, and Steps 51(d) and 81(b)'s
# `backend/modules/export/lane.py`, `service.py` and `binding.py`.
FROZEN_INCLUDE = (
    "backend/u8_*.py", "backend/production_boundary.py", "backend/log_events.py",
    "backend/request_context.py", "backend/maintenance_server.py",
    "backend/modules/operations/*.py", "backend/modules/operations/migration/*.py",
    "backend/modules/accounts/entry_limits.py",
    "backend/modules/accounts/integrations/email_allowance.py",
    "backend/modules/accounts/integrations/identity_providers.py",
    "backend/modules/accounts/integrations/account_mail.py",
    "backend/modules/accounts/integrations/provider_gate.py",
    "backend/modules/accounts/integrations/u8_digest_mail.py",
    "backend/modules/accounts/u8_verifier_key.py",
    "backend/modules/accounts/u8_control_policy.py", "backend/modules/accounts/u8_entry.py",
    "backend/modules/accounts/u8_mail_outbox.py", "backend/modules/accounts/u8_mfa.py",
    "backend/modules/accounts/u8_identity.py", "backend/modules/accounts/u8_lifecycle.py",
    "backend/modules/accounts/u8_control_http.py",
    "backend/modules/accounts/u8_local_http.py", "backend/modules/plans/u8_usage.py",
    "backend/modules/accounts/services/v2_rollback_apply.py",
    "backend/modules/accounts/services/rollback_outcomes.py",
    "backend/modules/research/control_lifecycle.py", "backend/modules/research/job_list.py",
    "backend/modules/discovery/u8_search.py", "backend/import_parity.py",
    "backend/modules/accounts/repository/imports.py",
    "backend/modules/accounts/services/first_sign_in.py", "backend/modules/corpus/limits.py",
    "backend/modules/library/repository/imports.py",
    "backend/modules/personalization/import_repository.py",
    "backend/modules/summarization/model_runtime.py",
    "backend/modules/summarization/u8_assistance_sources.py",
    "backend/modules/corpus/paper_import.py", "backend/modules/accounts/services/v1_import.py",
    "ops/src/docsuri_ops/backup_agent/*.py", "ops/src/docsuri_ops/standing/*.py",
    "ops/src/docsuri_ops/arrangement/*.py", "ops/src/docsuri_ops/migration/*.py",
    "ops/src/docsuri_ops/cutover/*.py", "ops/src/docsuri_ops/u8_platform/*.py",
    "ops/src/docsuri_ops/u8_platform/drivers/*.py", "ops/src/docsuri_ops/isolation_check.py",
    "ops/src/docsuri_ops/logrotate.py", "ops/src/docsuri_ops/backup_unlock.py",
    "ops/src/docsuri_ops/pf_loader.py", "ops/src/docsuri_ops/release.py",
    "ops/src/docsuri_ops/production_tool.py", "ops/src/docsuri_ops/production_wiring.py",
    "ops/src/docsuri_ops/research_review.py",
    "scripts/serve_docsuri_u8.py", "scripts/u8_*.py",
    "backend/local_profile.py", "backend/transactions.py", "backend/local_browser.py",
    "backend/local_host.py", "backend/artifacts.py", "backend/control_worker.py",
    "backend/control_runtime.py", "backend/lifecycle_effects.py",
    "ops/src/docsuri_ops/local_transport.py", "ops/src/docsuri_ops/u2_restore.py",
    "backend/modules/accounts/local_http.py", "backend/modules/accounts/control_http.py",
    "backend/modules/accounts/services/control_lifecycle.py",
    "backend/modules/accounts/control_policy.py", "backend/modules/accounts/control_keys.py",
    "backend/modules/accounts/services/guarded_entry.py",
    "backend/modules/accounts/services/control_entry.py",
    "backend/modules/accounts/services/control_mfa.py",
    "backend/modules/accounts/services/control_identity.py",
    "backend/modules/accounts/integrations/digest_email.py",
    "backend/modules/personalization/guarded_service.py", "backend/modules/research/jobs.py",
    "backend/modules/research/service.py", "backend/modules/research/http.py",
    "backend/modules/research/repository.py", "backend/modules/discovery/local_search.py",
    "backend/modules/discovery/local_embedding.py", "backend/modules/corpus/source_parser.py",
    "backend/modules/corpus/maintenance.py", "backend/modules/corpus/repository.py",
    "backend/modules/export/notion_session.py", "backend/modules/export/lane.py",
    "backend/modules/export/service.py", "backend/modules/export/binding.py",
    "backend/u6_real_export.py", "backend/u6_policy.py", "backend/modules/topics/scheduler.py",
    "backend/modules/topics/repository.py", "backend/modules/discovery/guarded_repository.py",
    "backend/modules/library/local_http.py", "backend/modules/library/repository/guarded.py",
    "backend/modules/personalization/local_http.py",
    "backend/modules/plans/control_service.py", "backend/modules/plans/guarded_repository.py",
    "backend/modules/plans/local_http.py", "backend/modules/summarization/admission.py",
    "backend/modules/summarization/guarded_repository.py",
    "backend/modules/summarization/payload.py", "backend/modules/summarization/requests.py",
    "backend/modules/summarization/u3_catalog.py", "backend/modules/summarization/u3_http.py",
    "backend/modules/summarization/u3_dispatch.py",
    "ops/src/docsuri_ops/platform_control/executor.py",
    "ops/src/docsuri_ops/platform_control/native_adapter.py",
)
MACOS_ADAPTERS = ("ops/src/docsuri_ops/arrangement/macos.py",
                  "ops/src/docsuri_ops/standing/macos.py",
                  "ops/src/docsuri_ops/isolation_macos.py")


def report_list(path: Path, key: str) -> list[str]:
    """One multi-line `[report]` list of a coverage configuration, comments left out."""
    parser = configparser.RawConfigParser()
    parser.read(path)
    return [line.strip() for line in parser.get("report", key, fallback="").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def fail_under(path: Path) -> str:
    parser = configparser.RawConfigParser()
    parser.read(path)
    return parser.get("report", "fail_under")


@pytest.fixture
def runner():
    from scripts import verify_docsuri_u8

    return verify_docsuri_u8


@pytest.fixture
def phases(runner):
    scripts = str(Path(runner.ROOT) / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import u8_phases

    return u8_phases


@pytest.fixture
def gate(phases):
    import u8_build_workspace

    return u8_build_workspace


def coverage_report_args(runner, monkeypatch, tmp_path) -> list[str]:
    """The arguments `run_coverage_report` builds, its seams stubbed."""
    tmp_path.mkdir(mode=0o700, exist_ok=True)
    monkeypatch.setattr(runner, "RUN", tmp_path)
    (tmp_path / runner.COVERAGE_DATA).write_text("data")
    monkeypatch.setattr(runner, "prepare_phase", lambda path: ({"runId": "r"}, {}))
    monkeypatch.setattr(runner, "coverage_parts_state", lambda run, run_id: {
        "parts": {}, "missingParts": [], "staleParts": [], "failedParts": [],
        "runsSinceFirstPart": []})
    monkeypatch.setattr(runner, "source_identity", lambda: {"sha256": "a" * 64})
    monkeypatch.setattr(runner, "private_json", lambda path, value: None)
    seen = []

    def bounded(args, log, **options):
        seen.append(args)
        return {"exitCode": 0}

    monkeypatch.setattr(runner, "bounded_process", bounded)
    runner.run_coverage_report(tmp_path / "environment.json")
    (args,) = seen
    return args


def arrangement_args(runner, phases, monkeypatch, tmp_path) -> list[str]:
    """The arguments `run_arrangement` builds, read from a stubbed `run_child`, with
    `sys.platform` patched to `darwin` and every other seam it calls stubbed, so neither
    sudo nor chown runs."""
    monkeypatch.setattr(phases.sys, "platform", "darwin")
    seen = []

    def child(runner_, phase, args, started, **options):
        seen.append(args)
        return {"command": args, "exitCode": 0, "supervision": {}, "failureCategory": None}

    def no_command(args, **options):
        raise AssertionError("no sudo or chown runs")

    stand_in = SimpleNamespace(
        RUN=tmp_path, PYTHON=runner.PYTHON, PYTEST_INI=runner.PYTEST_INI,
        Refused=runner.Refused, junit_counts=lambda report, evidence: None,
        prepare_phase=lambda path: ({"runId": "r"}, {}),
        require_test_paths=lambda paths, **options: None,
        source_identity=lambda: {"sha256": "a" * 64}, command=no_command)
    monkeypatch.setattr(phases, "run_child", child)
    monkeypatch.setattr(phases, "record", lambda runner_, phase, evidence: evidence)
    phases.run_arrangement(stand_in, tmp_path / "environment.json")
    (args,) = seen
    return args


def ci_arrangement_step() -> str:
    """The U8 arrangement step of `ci.yml`, up to the next step or the file's end."""
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    start = text.index("- name: U8 arrangement suite on macOS")
    end = text.find("- name:", start + 1)
    return text[start:] if end < 0 else text[start:end]


def test_no_u8_floor_bound_budget_or_target_is_lowered_and_no_file_leaves_a_coverage_list(
        runner, phases, gate, monkeypatch, tmp_path):
    import u8_fixtures
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from tests.u8_service_operations_integration import conftest

    u8_rc, macos_rc = ROOT / "backend/.coveragerc.u8", ROOT / "backend/.coveragerc.u8-macos"
    assert fail_under(u8_rc) == "80" and fail_under(macos_rc) == "80"
    report = coverage_report_args(runner, monkeypatch, tmp_path / "report")
    assert "--precision=2" in report and "--fail-under=80" in report
    (tmp_path / "arrangement").mkdir()
    arrangement = arrangement_args(runner, phases, monkeypatch, tmp_path / "arrangement")
    assert "--cov-fail-under=80" in arrangement
    assert "--cov-fail-under=80" in ci_arrangement_step()
    vitest = (ROOT / "frontend/vitest.u8-complete.config.ts").read_text()
    assert re.findall(r"thresholds: (\{.*\}),", vitest) == [
        "{ 'src/u8-*/**/*.{ts,tsx}': { lines: 80 } }"]
    included = re.search(r"include: \[\n(.*?)\n\s*\],", vitest, re.S).group(1)
    # Today's eight entries, frozen: none may leave U8's Vitest coverage.
    assert set(re.findall(r"'([^']+)'", included)) >= {
        "src/u8-*/**/*.{ts,tsx}", "src/account-controls.tsx", "src/u4-research/api.ts",
        "src/u4-research/composer.tsx", "src/u4-research/evidence.tsx",
        "src/u4-research/jobs.tsx", "src/u6-export/history.tsx", "src/u6-export/copy.ts"}
    include = report_list(u8_rc, "include")
    assert len(FROZEN_INCLUDE) == len(set(FROZEN_INCLUDE)) == 109
    assert set(include) >= set(FROZEN_INCLUDE)
    assert sorted(report_list(u8_rc, "omit")) == sorted(
        ["scripts/verify_docsuri_u8.py", *MACOS_ADAPTERS])
    assert sorted(report_list(macos_rc, "include")) == sorted(MACOS_ADAPTERS)
    assert gate.SCRIPT_BUDGET == 300000 and gate.STYLE_BUDGET == 50000
    assert phases.TARGETS_MS == {"health": 200, "first-load": 2000, "navigation": 1000,
                                 "api-read": 500, "search": 3000, "accept": 1000}
    assert phases.USERS == 20 and phases.ACT_SECONDS == 5.0
    # NFR8.3's SCRAM measurement and the users' GET reads (Step 134; L2-3, L2-5).
    assert phases.SCRAM_RECONSIDER_MS == 20.0 and phases.SCRAM_LOGINS_PER_OWNER == 20
    assert phases.SCRAM_SECONDS == 20
    assert phases.LOAD_TURNS == ("settings-read", "search", "session-read", "search")
    assert runner.PHASE_SECONDS == 300 and runner.MAX_RSS == 1024**3
    assert conftest.MAX_SYNTHETIC_ACCOUNTS == u8_fixtures.MAX_ACCOUNTS == (
        U8_SYNTHETIC_POLICY.max_accounts) == 20
    assert phases.RESTART_READY_SECONDS == 180 and phases.RESTART_MARGIN_SECONDS == 30


def first_load_page(dist: Path, script: str, style: str | None = None) -> None:
    head = f'<script type="module" src="/{script}"></script>'
    if style:
        head += f'<link rel="stylesheet" href="/{style}">'
    (dist / "index.html").write_text(f"<!doctype html><html><head>{head}</head></html>")


def test_a_first_load_over_its_budget_is_refused(gate, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    script, style = "assets/index-AbCdEf12.js", "assets/index-GhIjKl34.css"
    first_load_page(dist, script, style)
    assert gate.first_load(dist, {script: 300_000, style: 50_000})["withinBudget"] is True
    assert gate.first_load(dist, {script: 300_001, style: 50_000})["withinBudget"] is False
    assert gate.first_load(dist, {script: 300_000, style: 50_001})["withinBudget"] is False

    frontend = tmp_path / "frontend"

    def fake(folder: Path) -> None:
        built = folder / "dist"
        (built / "assets").mkdir(parents=True)
        first_load_page(built, script)
        for page in ("privacy.html", "terms.html", "maintenance.html"):
            (built / page).write_text("<!doctype html><html><body></body></html>")
        (built / script).write_bytes(random.Random(20261101).randbytes(310_000))

    with pytest.raises(gate.BuildRefused, match="the first load passes its budget"):
        gate.build(frontend, run=fake)
    assert not (frontend / "dist" / gate.MANIFEST).exists()


def passing() -> dict:
    # One millisecond under each target: every target is stated as "under" (NFR8.1-NFR8.5).
    return {"p95": {name: float(value - 1) for name, value in {
                "health": 200, "first-load": 2000, "navigation": 1000, "api-read": 500,
                "search": 3000, "accept": 1000}.items()},
            "refusals": {}, "readiness": {"samples": 5, "notReady": 0, "admissionClosed": 0},
            "rate_check": None, "browser_exit": 0,
            "backup": {"outcome": "succeeded", "seconds": 1800, "deadlineSeconds": 1800},
            "scram": {"measured": True, "failedLogins": 0, "p95Ms": 4.0,
                      "reconsiderPool": False},
            "read_check": None}


def verdict(phases, value: dict) -> dict:
    return phases.performance_verdict(value["p95"], value["refusals"], value["readiness"],
                                      value["rate_check"], value["browser_exit"],
                                      value["backup"], scram=value["scram"],
                                      read_check=value["read_check"])


def failing_cases(phases) -> list[dict]:
    cases = []
    for name, target in phases.TARGETS_MS.items():
        # At the target itself, and half a millisecond past it: neither is "under".
        for figure in (float(target), target + 0.5):
            value = passing()
            value["p95"][name] = figure
            cases.append(value)
    none = passing()
    none["p95"]["search"] = None
    refused = passing()
    refused["refusals"] = {"search:503:capacity.exhausted:": 1}
    not_ready, closed, unsampled = passing(), passing(), passing()
    not_ready["readiness"]["notReady"] = 1
    closed["readiness"]["admissionClosed"] = 1
    unsampled["readiness"]["samples"] = 0
    rate, browser, backup, late = passing(), passing(), passing(), passing()
    rate["rate_check"] = "v1-rate-higher"
    browser["browser_exit"] = 1
    backup["backup"]["outcome"] = "failed"
    late["backup"]["seconds"] = 1801
    # Step 135(e): a SCRAM measurement that never ran, one failed login, and a host that
    # counted fewer reads than its users were answered (L2-3, L2-5), last, in that order.
    unmeasured, failed_login, short = passing(), passing(), passing()
    unmeasured["scram"] = {"measured": False, "failedLogins": 0, "p95Ms": None,
                           "reconsiderPool": False}
    failed_login["scram"]["failedLogins"] = 1
    short["read_check"] = "read-class-short"
    return [*cases, none, refused, not_ready, closed, unsampled, rate, browser, backup, late,
            unmeasured, failed_login, short]


def test_a_missed_target_or_a_refusal_fails_the_performance_phase(phases):
    cases = failing_cases(phases)
    assert len(cases) == 24
    for value in cases:
        assert verdict(phases, value)["exitCode"] == 1, value
    assert [verdict(phases, value)["failedChecks"] for value in cases[-3:]] == [
        ["scram-logins-unmeasured"], ["scram-logins-failed"], ["read-class-short"]]
    for name, target in phases.TARGETS_MS.items():
        value = passing()
        value["p95"][name] = float(target)
        assert verdict(phases, value)["missedTargets"] == [name]
    assert verdict(phases, passing()) == {"missedTargets": [], "refusedRequests": 0,
                                          "failedChecks": [], "exitCode": 0}
    # A p95 past 20 ms is where a pool per owner login is reconsidered, not a target.
    reconsider = passing()
    reconsider["scram"] = {**reconsider["scram"], "p95Ms": 25.0, "reconsiderPool": True}
    assert verdict(phases, reconsider)["exitCode"] == 0
    assert verdict(phases, reconsider)["failedChecks"] == []
