"""Real capture parser boundaries; scanner output is never trusted from its exit code alone."""

import runpy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "ops/platform-integrity/scan_sbom.py"


@pytest.fixture
def classify():
    return runpy.run_path(str(SCRIPT))["classify_report"]


def report(*matches, **changes):
    return {
        "matches": list(matches), "ignoredMatches": [],
        "descriptor": {"name": "grype", "version": "0.119.0",
                       "configuration": {}, "db": {"status": {"valid": True}}},
    } | changes


def match(severity="High"):
    return {"vulnerability": {"id": "CVE-fixture", "severity": severity},
            "artifact": {"id": "occurrence-1", "name": "component", "version": "1"}}


def test_capture_reports_explicit_blocking_reason(classify):
    result = classify(report(match()))
    assert result["state"] == "BLOCKED" and result["blockingFindings"] == 1
    assert "unapproved_high_or_critical_findings" in result["reasons"]


@pytest.mark.parametrize("severity", ["Unknown", "unexpected", None])
def test_unknown_or_new_severity_is_incomplete(classify, severity):
    result = classify(report(match(severity)))
    assert result["state"] == "INCOMPLETE" and result["blockingFindings"] == 1
    assert "severity_unknown" in result["reasons"]


def test_ignored_matches_remain_visible_and_blocking(classify):
    result = classify(report(ignoredMatches=[match("Critical")]))
    assert result["state"] == "BLOCKED" and result["findings"] == 1
    assert result["ignoredFindings"] == 1


@pytest.mark.parametrize("changes", [{"matches": None}, {"descriptor": {}},
                                    {"ignoredMatches": "unavailable"}])
def test_incomplete_report_is_not_scanned(classify, changes):
    with pytest.raises(ValueError):
        classify(report(**changes))


def test_invalid_database_or_filtered_results_do_not_claim_complete_capture(classify):
    raw = report()
    raw["descriptor"]["db"]["status"]["valid"] = False
    with pytest.raises(ValueError):
        classify(raw)
    raw = report()
    raw["descriptor"]["configuration"]["only-fixed"] = True
    with pytest.raises(ValueError):
        classify(raw)


def test_zero_matches_is_capture_only_not_release_eligibility(classify):
    result = classify(report())
    assert result["state"] == "SCANNED"
    assert result["reasons"] == ["role_closure_and_trusted_freshness_acceptance_required"]
