"""Lossless audit normalization: a scanner error or absent coverage is never a clean scan."""

from ..contracts.models import (
    AdvisoryObservationSet,
    DependencyInventory,
    Finding,
    GateVerdict,
    ReachabilityException,
)


def parse_pip_audit(
    report: dict, *, returncode: int, expected: dict[str, str], source: str
) -> tuple[Finding, ...]:
    if returncode not in (0, 1) or not isinstance(report, dict) or "error" in report:
        raise ValueError("scanner did not complete")
    dependencies = report.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies or not expected:
        raise ValueError("scanner coverage missing")
    seen: dict[str, str] = {}
    findings = []
    for dependency in dependencies:
        if (
            not isinstance(dependency, dict)
            or "skip_reason" in dependency
            or "version" not in dependency
            or not isinstance(dependency.get("vulns"), list)
        ):
            raise ValueError("scanner occurrence not audited")
        name, version = dependency["name"], dependency["version"]
        if name in seen or expected.get(name) != version:
            raise ValueError("scanner inventory mismatch")
        seen[name] = version
        for vuln in dependency["vulns"]:
            if not isinstance(vuln, dict) or not isinstance(vuln.get("id"), str):
                raise ValueError("invalid advisory")
            # pip-audit does not supply severity. Preserve unknown, block conservatively.
            findings.append(
                Finding(
                    advisory=vuln["id"],
                    occurrence=f"{name}@{version}",
                    severity="unknown",
                    source=source,
                )
            )
    if seen != expected or (returncode == 1 and not findings):
        raise ValueError("incomplete scanner coverage")
    return normalize(tuple(findings))


def normalize(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    # Exact duplicates only. Differing severities/sources are evidence, not duplicates.
    return tuple(
        sorted(set(findings), key=lambda f: (f.advisory, f.occurrence, f.source, f.severity))
    )


def exception_matches(
    exception: ReachabilityException,
    finding: Finding,
    *,
    artifact: str,
    closure: str,
    assumptions: str,
    policy: str,
    lower: int,
    upper: int,
    authorized: bool,
    revoked: bool,
) -> bool:
    return (
        authorized is True
        and revoked is False
        and exception.artifact == artifact
        and exception.closure == closure
        and exception.assumptions == assumptions
        and exception.policy == policy
        and exception.advisory == finding.advisory
        and exception.occurrence == finding.occurrence
        and exception.validity.contains(lower, upper)
        and int(exception.validity.valid_until) - int(exception.validity.valid_from)
        <= 7 * 86400 * 1_000_000
    )


def evaluate_inventory(
    inventory: DependencyInventory, reports: tuple[AdvisoryObservationSet, ...], *,
    expected_scopes: frozenset[str], lower: int, upper: int,
) -> tuple[GateVerdict, tuple[Finding, ...], tuple[str, ...]]:
    """Coverage/freshness and lossless findings; unknown severity cannot become clean."""
    reasons = set()
    if (
        not expected_scopes or set(inventory.required_scopes) != expected_scopes
        or len(inventory.required_scopes) != len(expected_scopes)
    ):
        reasons.add("inventory_scope_mismatch")
    occurrences = {item.occurrence for item in inventory.components}
    if (
        not occurrences or len(occurrences) != len(inventory.components)
        or any(item.artifact != inventory.artifact for item in inventory.components)
    ):
        reasons.add("inventory_occurrence_mismatch")
    clock_valid = type(lower) is int and type(upper) is int and 0 <= lower <= upper < 2**64
    if not clock_valid:
        reasons.add("clock_unavailable")
    # Deduplicate exact immutable observations, not scope/digest/severity alone. Preserve
    # every finding even when reports conflict or lie outside the requested coverage.
    observations = set(reports)
    normalized = normalize(tuple(finding for report in observations for finding in report.findings))
    if {report.scope for report in observations} - expected_scopes:
        reasons.add("scanner_scope_mismatch")
    if any(sum(report.scope == scope for report in observations) != 1 for scope in expected_scopes):
        reasons.add("scanner_coverage_missing_or_conflicting")
    for report in observations:
        if not report.complete or report.artifact != inventory.artifact:
            reasons.add("scanner_coverage_unverified")
        if not clock_valid or not (
            int(report.observed_at) <= lower <= upper
            < int(report.observed_at) + 86400 * 1_000_000
        ):
            reasons.add("advisory_snapshot_stale")
        if any(finding.occurrence not in occurrences for finding in report.findings):
            reasons.add("finding_outside_inventory")
    if any(finding.severity == "unknown" for finding in normalized):
        reasons.add("severity_unknown")
    if any(finding.severity in {"high", "critical"} for finding in normalized):
        return GateVerdict.BLOCKED, normalized, tuple(sorted(reasons | {"unapproved_findings"}))
    verdict = GateVerdict.INCOMPLETE if reasons else GateVerdict.ELIGIBLE
    return verdict, normalized, tuple(sorted(reasons))
