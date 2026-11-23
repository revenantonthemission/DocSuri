"""The coverage phase fails below `.coveragerc.u5`'s floor (U8 plan Step 44; your decision
of 2026-10-24, "Fix the three tools").

The phase reads the TOTAL row of the report it wrote and judges the figure, cut to two
decimals, against the coveragerc's `fail_under`: below it the phase fails with
`coverage-below-floor` and the figure, at or above it passes, and a report without a
total fails.
"""

import os

import pytest

from scripts import verify_docsuri_u5 as runner


def report(folder, text: str):
    log = folder / "u5-phase-coverage.log"
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(text)
    return log


def passed():
    return {"phase": "coverage", "exitCode": 0, "failureCategory": None}


def table(statements: int, missed: int, shown: str) -> str:
    return (
        "Name                         Stmts   Miss  Cover   Missing\n"
        "backend/u5_policy.py            40      0   100%\n"
        f"TOTAL                        {statements}   {missed}   {shown}\n"
        "FAIL Required test coverage of 80% not reached. Total coverage: 79.63%\n"
    )


def test_the_floor_is_read_from_the_unchanged_coveragerc():
    assert runner.coverage_floor() == 80.0
    assert runner.COVERAGE_RC.name == ".coveragerc.u5"


def test_a_report_below_the_floor_fails_the_phase_with_the_figure(tmp_path):
    # 79.63% prints as "80%" at the coveragerc's precision: the counts decide.
    evidence = runner.judge_coverage(passed(), report(tmp_path, table(2297, 468, "80%")))
    assert evidence["exitCode"] == 1
    assert evidence["failureCategory"] == "coverage-below-floor"
    assert (evidence["coverageTotalPercent"], evidence["coverageFloorPercent"]) == (79.62, 80.0)
    assert runner.safe_phase_summary(evidence)["coverageTotalPercent"] == 79.62


@pytest.mark.parametrize("statements,missed,total", [(1000, 200, 80.0), (2000, 300, 85.0)])
def test_a_report_at_or_above_the_floor_passes(tmp_path, statements, missed, total):
    evidence = runner.judge_coverage(passed(), report(tmp_path, table(statements, missed, "99%")))
    assert (evidence["exitCode"], evidence["failureCategory"]) == (0, None)
    assert evidence["coverageTotalPercent"] == total


def test_the_figure_is_cut_never_rounded_up_to_the_floor(tmp_path):
    # 79.995% would round to 80.00; cut to two decimals it stays below.
    evidence = runner.judge_coverage(passed(), report(tmp_path, table(20000, 4001, "80%")))
    assert evidence["coverageTotalPercent"] == 79.99 and evidence["exitCode"] == 1


def test_a_report_without_a_total_fails(tmp_path):
    for text in ("no coverage table at all\n", table(0, 0, "100%")):
        folder = tmp_path / str(len(text))
        folder.mkdir()
        evidence = runner.judge_coverage(passed(), report(folder, text))
        assert evidence["exitCode"] == 1
        assert evidence["failureCategory"] == "coverage-total-missing"
        assert evidence["coverageTotalPercent"] is None
    unreadable = runner.judge_coverage(passed(), tmp_path / "missing.log")
    assert unreadable["failureCategory"] == "coverage-total-missing"


def test_an_earlier_failure_keeps_its_own_category(tmp_path):
    failed = {"phase": "coverage", "exitCode": 1, "failureCategory": None}
    evidence = runner.judge_coverage(failed, report(tmp_path, table(1000, 500, "50%")))
    assert evidence["exitCode"] == 1 and evidence["failureCategory"] is None
    assert evidence["coverageTotalPercent"] == 50.0
