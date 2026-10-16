# SLO Report — u4-research-novelty

SLO compliance report for the u4-research-novelty unit. All SLO targets are unset until P1/P2 baseline is measured and human agreement is obtained ($0 budget constraint, synthetic local environment only).

## SLO Compliance Matrix

| SLI | SLO Target | Actual | Status | Evidence |
|---|---|---|---|---|
| Useful complete journey success: successful required useful journeys / all valid intended journeys | Unset until baseline measured | Not measured | Not set — baseline required | operation/performance-validation/test-results.md |
| Capability availability: passing scheduled opportunities / every scheduled opportunity | Unset until baseline measured | Not measured | Not set — baseline required | operation/observability-setup/alarms.md |
| Foreground/search/save/assistance/revisit latency | Unset until baseline measured | Not measured | Not set — baseline required | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Accepted work resolution and oldest nonterminal age | Unset until baseline measured | Not measured | Not set — baseline required | operation/incident-response/incident-plan.md |
| Result/accounting integrity | No contradictory or duplicate effect permitted (invariant) | No contradictory or duplicate effect observed | Invariant — not rate-based | operation/incident-response/incident-plan.md |
| Fault recovery, restore loss and defect-to-repair time | RTO, RPO and repair target unset | Not measured | Not set — baseline required | operation/incident-response/runbooks.md |
| Observation completeness | Target unset; all known loss/gap/reset information must be disclosed | Not measured | Not set — baseline required | operation/observability-setup/dashboards.md |

## SLO Measurement Rules

| Rule | Value |
|---|---|
| Zero eligible samples/opportunities | Means unknown; do not drop failed, aborted, unexecuted, excluded-maintenance or unfinished cases from the recorded denominator |
| Adjusted availability | If later useful, show its declared exclusions alongside the gross figure |
| Cross-process elapsed values | Require clock provenance and measured uncertainty; otherwise report unknown or an interval |
| Owner revisions | Order effects, not trace arrival time |
| Model/runtime/configuration/data changes | Require rebaselining before applying old targets |
| Numerator/denominator | Report offered/admitted/completed/failed/rejected work, logical operations and complete journeys separately from attempts |
| Distribution reporting | Report distributions and sample size; percentiles from small samples remain descriptive |

## SLO Guards

- No SLO target is asserted by this design; all targets are unset until baseline measured and human-agreed
- No numeric service targets are asserted
- No SLO is used as an error budget for automatic remediation
- All measurements record build/configuration/contract/model/fixture identity, resource envelope, cold/warm state, start/cutoff and planned observation opportunities

## SLO Guard Details

| Property | Value |
|---|---|
| SLO target type | Unset — baseline required |
| Measurement window | Unset — baseline required |
| Error budget | Unset — no SLO targets established |
| Burn rate | Unset — no SLO targets established |
| Remediation threshold | Not applicable — no SLO targets established |

## SLO Compliance Status

| Check | Result | Evidence |
|---|---|---|
| SLO targets defined | Not set — baseline required | operation/observability-setup/slo-config.md |
| SLIs measured | Not measured — synthetic local environment only | operation/performance-validation/test-results.md |
| Error budget tracked | Not applicable — no SLO targets established | operation/observability-setup/slo-config.md |
| Alerting configured | Not applicable — no SLO targets established | operation/observability-setup/alarms.md |

## SLO Compliance Conclusion

All SLO/SLI targets are unset until baseline measurement and human agreement. The existing test results (218 tests, 0 failures) confirm functional correctness but do not establish performance service-level targets. Baseline measurement is required before any SLO target can be agreed upon.
