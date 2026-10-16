# Alarms — u4-research-novelty Observability

Alarm configuration for the u4-research-novelty unit. All alarms are local-only; no cloud alerting service or external paging is provisioned ($0 budget constraint).

## Alarm Configuration

| Alert | Condition | Severity | Routes to | Escalation |
|---|---|---|---|---|
| Isolation or integrity breach | Observed unauthorized data/effect, duplicate accounting, lost acknowledged state, corrupted published binding | Critical invariant; no rate threshold | Durable local incident for the human and protected ServiceOperations view | The effect owner closes the unsafe boundary; Operations cannot edit its records |
| Required capability unavailable | Required policy, authority guard, store, executor or eligible provider fails its current check | Error for affected scope | Same local view and supervisor status on next local inspection | Safe capability-specific user state; no third-party messages |
| Recovery reserve at risk | Fresh shared-capacity reading reaches configured stop floor/cap, or reservation cannot be honored | Error; stop affected new admission | Local incident with actual bytes/units, affected lane and owner runbook | Preserve already accepted responsibility |
| Accepted work needs intervention | Reconciliation/retry budget exhausted, unknown admission outcome, stale claim cannot safely recover or settlement contradicts owner evidence | Error | Human's local incident queue with original identity references and bounded owner lookup/recovery procedure | Never auto-release merely because work is old |
| Backlog, latency or capacity trend | Baseline-derived condition crosses a future human-agreed service threshold | Warning/error according to approved policy; currently not enabled as a service-rate alarm | Local incident view once an actual policy/window is selected | Raw observations are visible before that selection |
| Evidence stale or lost | Required observation expires, counters report loss, sink is full/unavailable, fallback freshness expires | Warning for optional diagnostics; error where required readiness evidence is missing | Local status and incident projection when possible | Missing delivery/collector evidence remains visibly unknown |
| Restore/current-authority mismatch | Restore lacks current revocation/deletion evidence, coherent artifact binding, recovered key or valid claim treatment | Error; keep restored scope closed | Local incident and isolated restore report for the human | No public exposure or automatic dispatch |
| Unapproved route or potential charge | Provider/runner route exceeds evidenced free configuration or falls outside the allowlist | Error; adapter/run disabled | Local preflight report and incident view | No paid fallback or automatic purchase |

## Alarm Configuration Details

| Property | Value |
|---|---|
| Deduplication | By capability, condition class and policy revision |
| State preserved | First/last seen, occurrence count, responsible owner, protected evidence reference, safe next step, acknowledgement, resolution evidence |
| Acknowledgement meaning | Seen, not resolved |
| Resolution | Only after current owner checks and the affected path pass |
| Recovery | Cannot erase the failed interval |
| Human attention latency | Measured in the local drill; no unattended paging or 24-hour response promise |
| Third-party messaging | None — no email, Slack, webhook or paid paging route |
| Incident refresh | At most one projection refresh per 30 seconds per condition; cap local list at 100/page; overflow summarized with a count |
| Durable incident facts | Follow owner policy; rotating JSON copy and dashboard cache are projections |

## Alarm Guards

- No automatic paging or external notification
- Acknowledgement does not mean resolution
- Recovery cannot erase the failed interval
- Unknown/unknown staleness remains visibly unknown, never reported as healthy
- No automated remediation that could override owner authority
