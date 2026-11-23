"""U2's coverage phase fails below `.coveragerc.u2`'s floor (U8 plan Step 44; the person's
decision of 2026-10-24, "Add U2's coverage phase").

The phase measures U2's five owner layers into one data file in the run root, the first
layer beginning it and the rest appending, and judges the combined report's TOTAL row,
cut to two decimals, against the coveragerc's `fail_under`: below it the phase fails with
`coverage-below-floor` and the figure, at or above it passes, and a report without a
total fails.
"""

import pytest

from scripts import verify_docsuri_u2 as runner

pytestmark = pytest.mark.u2_operations


def passed():
    return {"phase": "coverage", "exitCode": 0, "failureCategory": None}


def table(statements: int, missed: int, shown: str) -> str:
    return (
        "Name                                        Stmts   Miss   Cover   Missing\n"
        "backend/local_host.py                         400    240  40.00%   1-240\n"
        "backend/transactions.py                       200     20  90.00%   1-20\n"
        "backend/modules/plans/local_http.py            50     40  20.00%   1-40\n"
        "backend/empty.py                                0      0 100.00%\n"
        f"TOTAL                                       {statements}   {missed}   {shown}\n"
    )


MEASURED = (
    "backend/artifacts.py",
    "backend/control_restore.py",
    "backend/control_runtime.py",
    "backend/control_worker.py",
    "backend/lifecycle_effects.py",
    "backend/local_browser.py",
    "backend/local_host.py",
    "backend/local_profile.py",
    "backend/modules/accounts/control_confirmation.py",
    "backend/modules/accounts/control_cursor.py",
    "backend/modules/accounts/control_http.py",
    "backend/modules/accounts/control_keys.py",
    "backend/modules/accounts/control_key_recovery.py",
    "backend/modules/accounts/control_policy.py",
    "backend/modules/accounts/control_repository.py",
    "backend/modules/accounts/local_http.py",
    "backend/modules/accounts/services/control_entry.py",
    "backend/modules/accounts/services/control_identity.py",
    "backend/modules/accounts/services/control_lifecycle.py",
    "backend/modules/accounts/services/control_mfa.py",
    "backend/modules/accounts/services/guarded_entry.py",
    "backend/modules/corpus/local_http.py",
    "backend/modules/discovery/guarded_repository.py",
    "backend/modules/discovery/local_http.py",
    "backend/modules/library/control_lifecycle.py",
    "backend/modules/library/control_service.py",
    "backend/modules/library/local_http.py",
    "backend/modules/library/repository/guarded.py",
    "backend/modules/library/restore.py",
    "backend/modules/personalization/activity.py",
    "backend/modules/personalization/control_lifecycle.py",
    "backend/modules/personalization/control_service.py",
    "backend/modules/personalization/guarded_service.py",
    "backend/modules/personalization/local_http.py",
    "backend/modules/personalization/reset_repository.py",
    "backend/modules/personalization/restore.py",
    "backend/modules/plans/control_service.py",
    "backend/modules/plans/guarded_repository.py",
    "backend/modules/plans/local_http.py",
    "backend/modules/summarization/admission.py",
    "backend/modules/summarization/guarded_repository.py",
    "backend/transactions.py",
    "ops/src/docsuri_ops/u2_restore.py",
    "ops/src/docsuri_ops/u2_restore_context.py",
)
TOOLS = (
    "ops/src/docsuri_ops/local_transport.py",
    "scripts/prepare_docsuri_u2_browser.py",
    "scripts/prepare_docsuri_u2_transport.py",
    "scripts/serve_docsuri_u2.py",
    "scripts/verify_docsuri_u2.py",
    "scripts/verify_docsuri_cumulative.py",
    "scripts/u2_browser_fixtures.py",
    "shared/python/tools/export_workspace_contract.py",
)


def lines_of(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def test_the_measured_scope_is_u2s_product_code():
    """By the person's decision of 2026-10-24 ("Move, scope tools, test U2"): test
    tooling is not product code, so the eight tool files are out; U2's own restore code
    stays in; the floor and its precision do not change."""
    import configparser

    parser = configparser.ConfigParser()
    parser.read(runner.COVERAGE_RC)
    include = lines_of(parser["report"]["include"])
    assert tuple(include) == MEASURED
    assert not set(TOOLS) & set(include)
    assert not any(path.startswith(("scripts/", "shared/python/tools/")) for path in include)
    assert "ops/src/docsuri_ops/u2_restore.py" in include
    assert "ops/src/docsuri_ops/u2_restore_context.py" in include
    root = runner.COVERAGE_RC.resolve().parents[1]
    assert all((root / path).is_file() for path in include)
    assert lines_of(parser["run"]["source_dirs"]) == ["backend", "ops/src/docsuri_ops"]
    assert parser["report"]["fail_under"] == "80" and parser["report"]["precision"] == "2"
    assert runner.coverage_floor() == 80.0
    assert "Move, scope tools, test U2" in runner.COVERAGE_RC.read_text()


def test_the_floor_is_read_from_the_coveragerc():
    assert runner.coverage_floor() == 80.0
    assert runner.COVERAGE_RC.name == ".coveragerc.u2"
    # Component first: in one realm its worker test needs no other layer's open requests.
    assert runner.COVERAGE_LAYERS == (
        "component", "database", "repository", "integration", "operations"
    )
    assert "coverage" in runner.PHASES


def test_a_report_below_the_floor_fails_with_the_figure_and_the_lowest_files():
    evidence = runner.judge_coverage(passed(), table(2297, 468, "79.63%"))
    assert evidence["exitCode"] == 1
    assert evidence["failureCategory"] == "coverage-below-floor"
    assert (evidence["coverageTotalPercent"], evidence["coverageFloorPercent"]) == (79.62, 80.0)
    assert [row["file"] for row in evidence["lowestFiles"]] == [
        "backend/modules/plans/local_http.py", "backend/local_host.py", "backend/transactions.py"
    ]


@pytest.mark.parametrize("statements,missed,total", [(1000, 200, 80.0), (2000, 300, 85.0)])
def test_a_report_at_or_above_the_floor_passes(statements, missed, total):
    evidence = runner.judge_coverage(passed(), table(statements, missed, "99.00%"))
    assert (evidence["exitCode"], evidence["failureCategory"]) == (0, None)
    assert evidence["coverageTotalPercent"] == total


def test_the_figure_is_cut_never_rounded_up_to_the_floor():
    # 79.995% would round to 80.00; cut to two decimals it stays below.
    evidence = runner.judge_coverage(passed(), table(20000, 4001, "80.00%"))
    assert evidence["coverageTotalPercent"] == 79.99 and evidence["exitCode"] == 1


def test_a_report_without_a_total_fails():
    for text in ("no coverage table at all\n", table(0, 0, "100.00%"), ""):
        evidence = runner.judge_coverage(passed(), text)
        assert evidence["exitCode"] == 1
        assert evidence["failureCategory"] == "coverage-total-missing"
        assert evidence["coverageTotalPercent"] is None


def test_an_earlier_failure_keeps_its_own_category():
    failed = {"phase": "coverage", "exitCode": 1, "failureCategory": "Refused"}
    evidence = runner.judge_coverage(failed, table(1000, 500, "50.00%"))
    assert evidence["exitCode"] == 1 and evidence["failureCategory"] == "Refused"


def test_the_first_layer_begins_the_run_root_data_file_and_the_rest_append(tmp_path):
    first = runner.coverage_layer_command("component", tmp_path / "component.xml")
    later = runner.coverage_layer_command("operations", tmp_path / "operations.xml")
    for command in (first, later):
        assert command[:2] == ["/usr/bin/env", f"COVERAGE_FILE={runner.RUN / '.coverage-u2'}"]
        assert "--cov-config=backend/.coveragerc.u2" in command
        assert "--maxfail=1" in command and "--cov-fail-under=0" in command
        assert "backend/pytest.u2-account-personal-controls.ini" in command
    assert "--cov-append" not in first and "--cov-append" in later
    assert "tests/u2_account_personal_controls/operations" in later


def test_coverage_refuses_an_environment_a_layer_already_ran_in(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUN", tmp_path)
    monkeypatch.setattr(runner, "COVERAGE_DATA", tmp_path / ".coverage-u2")
    runner.require_fresh_for_coverage()  # a fresh run root passes
    (tmp_path / "component.xml").write_text("<testsuite/>")
    with pytest.raises(runner.Refused, match="fresh U2 environment"):
        runner.require_fresh_for_coverage()
    (tmp_path / "component.xml").unlink()
    (tmp_path / ".coverage-u2").write_text("")
    with pytest.raises(runner.Refused, match="fresh U2 environment"):
        runner.require_fresh_for_coverage()


def test_a_layer_report_with_no_tests_or_a_skip_is_not_a_pass(tmp_path):
    missing = runner.junit_counts(tmp_path / "absent.xml")
    assert missing == {"missingTestReport": True, "passed": False}
    empty = tmp_path / "empty.xml"
    empty.write_text("<testsuite></testsuite>")
    assert runner.junit_counts(empty)["passed"] is False
    skipped = tmp_path / "skipped.xml"
    skipped.write_text('<testsuite><testcase name="a"><skipped/></testcase></testsuite>')
    assert runner.junit_counts(skipped) == {
        "tests": 1, "failures": 0, "errors": 0, "skipped": 1, "passed": False
    }
    good = tmp_path / "good.xml"
    good.write_text('<testsuite><testcase name="a"/><testcase name="b"/></testsuite>')
    assert runner.junit_counts(good)["passed"] is True
