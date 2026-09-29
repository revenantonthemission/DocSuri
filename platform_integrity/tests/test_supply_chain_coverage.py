"""PROP-R1-13/14: coverage cannot erase observed findings or invent current approval."""

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from docsuri_platform_integrity.contracts.codec import digest
from docsuri_platform_integrity.contracts.models import (
    AdvisoryObservationSet,
    DependencyInventory,
    Finding,
    GateVerdict,
    InventoryOccurrence,
    ReachabilityException,
    ValidityWindow,
)
from docsuri_platform_integrity.domain.supply_chain import evaluate_inventory, exception_matches

D = digest(b"frozen artifact")
INVENTORY = DependencyInventory(
    artifact=D,
    components=(InventoryOccurrence(
        occurrence="python:pydantic@2.13.5", name="pydantic", version="2.13.5",
        ecosystem="python", artifact=D,
    ),),
    required_scopes=("python",),
)
HIGH = Finding(advisory="CVE-fixture", occurrence=INVENTORY.components[0].occurrence,
               severity="high", source="scanner")


def report(*findings, scope="python", **changes):
    return AdvisoryObservationSet(
        artifact=D, scope=scope, complete=True, observed_at="100", findings=findings,
        report_digest=digest(repr(findings).encode()),
    ).model_copy(update=changes)


def evaluate(reports, inventory=INVENTORY, **clock):
    return evaluate_inventory(inventory, reports, expected_scopes=frozenset({"python"}),
                              **({"lower": 101, "upper": 102} | clock))


def test_conflicting_reports_preserve_every_finding():
    verdict, findings, reasons = evaluate((report(), report(HIGH)))
    assert verdict == GateVerdict.BLOCKED and findings == (HIGH,)
    assert "scanner_coverage_missing_or_conflicting" in reasons


def test_undeclared_scope_cannot_hide_findings():
    verdict, findings, reasons = evaluate((report(), report(HIGH, scope="image")))
    assert verdict == GateVerdict.BLOCKED and findings == (HIGH,)
    assert "scanner_scope_mismatch" in reasons


def test_exact_duplicate_reports_are_idempotent():
    clean = report()
    assert evaluate((clean, clean)) == evaluate((clean,))
    assert evaluate((clean,))[0] == GateVerdict.ELIGIBLE


@pytest.mark.parametrize("reports,clock", [
    ((), {}),
    ((report(complete=False),), {}),
    ((report(artifact=digest(b"other")),), {}),
    ((report(),), {"lower": 99, "upper": 101}),
    ((report(),), {"lower": 100, "upper": 100 + 86400 * 1_000_000}),
    ((report(),), {"lower": True, "upper": 102}),
    ((report(),), {"lower": 102, "upper": 101}),
    ((report(HIGH.model_copy(update={"severity": "unknown"})),), {}),
])
def test_missing_coverage_unknown_severity_or_time_is_not_clean(reports, clock):
    assert evaluate(reports, **clock)[0] == GateVerdict.INCOMPLETE


def test_duplicate_inventory_scope_is_not_accepted():
    inventory = INVENTORY.model_copy(update={"required_scopes": ("python", "python")})
    assert evaluate((report(),), inventory)[0] == GateVerdict.INCOMPLETE


@example(["critical"])
@example(["critical", "critical"])
@given(st.lists(st.sampled_from(("critical", "high", "moderate", "low", "unknown")),
                min_size=1, max_size=12))
def test_report_order_and_duplicates_preserve_observed_finding_set(severities):
    observations = tuple(report(HIGH.model_copy(update={"severity": severity}))
                         for severity in severities)
    expected = {finding for item in observations for finding in item.findings}
    result = evaluate(observations)
    assert set(result[1]) == expected
    assert evaluate(tuple(reversed(observations)) + observations) == result
    if {"high", "critical"} & set(severities):
        assert result[0] == GateVerdict.BLOCKED


@pytest.mark.parametrize("authorized,revoked", [(True, None), (1, False), (True, 0)])
def test_exception_requires_explicit_current_authority(authorized, revoked):
    exception = ReachabilityException(
        exception_id="review-1", artifact=D, closure=D, assumptions=D, policy=D,
        advisory=HIGH.advisory, occurrence=HIGH.occurrence, approver="operator",
        validity=ValidityWindow(valid_from="0", valid_until="200"),
    )
    assert not exception_matches(exception, HIGH, artifact=D, closure=D, assumptions=D,
                                 policy=D, lower=100, upper=100,
                                 authorized=authorized, revoked=revoked)
