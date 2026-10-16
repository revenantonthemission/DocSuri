# SLO Configuration — u4-research-novelty Observability

SLO/SLI configuration for the u4-research-novelty unit. All SLO targets are unset until P1/P2 baseline is measured and human agreement is obtained. SLOs are not service-quality targets; they are descriptive measurements for the synthetic local experiment.

## SLI/SLO Configuration

| SLI | SLO target | Measurement window | Status |
|---|---|---|---|
| Useful complete journey success: successful required useful journeys / all valid intended journeys | Unset until eligible P1/P2 and translation baseline plus human agreement; checkpoint cases have explicit pass criteria | Each bounded run's declared start/cutoff initially; an operating rolling window remains unset | Not set — baseline required |
| Capability availability: passing scheduled opportunities / every scheduled opportunity | Unset; show failed, degraded, unknown, stale and missed checks | Explicit experiment window and cadence; no claim about unsampled periods or future public service | Not set — baseline required |
| Foreground/search/save/assistance/revisit latency | Unset; report completion distribution and full failure/timeout counts | Per declared cold/warm workload cohort; one intended operation is distinct from attempts | Not set — baseline required |
| Accepted work resolution and oldest nonterminal age | Unset; safety deadlines remain separately finite | Original-acceptance cohort through cutoff, including unresolved/censored work | Not set — baseline required |
| Result/accounting integrity | No contradictory or duplicate effect permitted; an invariant, not a rate-based error budget | Every tested operation and current authorized reconciliation scope; disclose missing evidence | Invariant — not rate-based |
| Fault recovery, restore loss and defect-to-repair time | RTO, RPO and repair target unset | Named isolated fault/drill from disruption through verified useful recovery and reconciliation | Not set — baseline required |
| Observation completeness | Target unset; all known loss/gap/reset information must be disclosed | Planned collection opportunities versus observed records for each run/window | Not set — baseline required |

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
