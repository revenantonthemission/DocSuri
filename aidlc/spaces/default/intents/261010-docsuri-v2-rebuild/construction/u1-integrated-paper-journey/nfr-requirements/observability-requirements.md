# DocSuri v2 — U1 observability and repairability requirements

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`.
Status: derived requirements and measurement plan; no monitoring deployment,
baseline, demonstrated repair or service-readiness claim.

## Scope and authoritative sources

This document elaborates inception **NFR9** and **NFR7** for one human maintainer
with coding agents, within the $0 free/local constraint. Observation must explain
the integrated journey and recovery while respecting each domain owner. It does
not require a telemetry vendor, distributed deployment or network tracing stack.

Sources are the [confirmed proposal](nfr-requirements-questions.md),
[inception requirements](../../../inception/requirements-analysis/requirements.md),
[U1 workflows and local checks](../functional-design/functional-spec.md),
[rules](../functional-design/rules.md),
[entity model](../functional-design/entities.md),
[contract coordination](../functional-design/contract-revision-plan.md), and
[canonical contracts](../../../inception/contract-design/contract-summary.md)
(common error/identity rules; C01, C06, C11 and C14). Related measurements are
defined in [performance](performance-requirements.md),
[reliability](reliability-requirements.md) and
[capacity](scalability-requirements.md) requirements; handling restrictions belong
to [security/privacy](security-requirements.md).

## Derived requirements

| ID | Requirement and accountable owner | Observable verification and prerequisite |
|---|---|---|
| NFR9.1 | **Report liveness, capability readiness and journey readiness separately.** ServiceOperations assembles timestamped, scope-labeled observations from registered domain owners. Missing required stores, modules, contracts, workers, policies or permitted source/model paths block affected readiness. Unknown/stale evidence cannot become healthy, and missing future units cannot imply complete release parity. Recovery readiness requires current relevant checks. | WF9; BR7.1–BR7.2; LC12–LC14. Inject missing registration/store/model/worker, incompatible binding, unresolved policy and observation expiry; inspect authorized operational views and appropriate Korean user feedback. A green process check must not mask a broken saved-return or assistance path. Check intervals, freshness limits and bounded probe/resource policy are resolved before monitoring enablement; no availability target is invented. |
| NFR9.2 | **Correlate failures safely across logical operations.** Each domain owner emits safe identity, outcome and timing evidence for request → intended operation → accepted job → execution claim/attempt → result → accounting reconciliation. Preserve original identities across retries/restarts, distinguish request correlation from idempotency authority, and relate evidence through explicit parent/reference fields. ServiceOperations permits only authorized, purpose-scoped access. | WF4–WF9; BR5.2–BR5.8, BR7.3; LC05, LC09, LC10, LC13. Trace an injected failure and replaced-worker event end to end without raw prompts, paper/manuscript text, personal search text, credentials or bearer/session material in normal telemetry. Verify redaction and access across normal/error/timeout paths. Resolve evidence classification, fields, access and retention before collection. Immutable original acceptance time and canonical identities must align before code. |
| NFR9.3 | **Measure actionable service indicators and alerts without concealing failures.** ServiceOperations and relevant owners define each signal's event source, clock, unit, workload, observation window, denominator and missing-data treatment. Dashboards distinguish observed, estimated, unknown and stale values. Alerts identify affected capability, evidence, owner and safe next step; numerical thresholds/SLOs follow baseline and human agreement. | WF9; BR7.2–BR7.4; LC10, LC12–LC14. Run permitted P1/P2 tasks and controlled load/fault scenarios; verify the measurement matrix below against authoritative outcomes. Include rejected, failed, timed-out, aborted and unknown attempts as classified counts. Exercise backlog, exhausted admission, missing work/settlement and dependency recovery. Probe/alert cadence and finite resource bounds are set before enablement; no paid paging service is assumed. |
| NFR9.4 | **Bound telemetry failures and preserve business truth.** ServiceOperations applies a finite, documented buffering/retry/drop policy with missing-evidence counters and freshness state. Ordinary observation transport failure cannot change a domain outcome, cause an infinite retry/log loop, expose private data or exhaust protected storage. Durable business receipts and recovery obligations remain owned separately by their domains. | WF5, WF8–WF9; BR5.8, BR7.2–BR7.3; LC10, LC12–LC13. Disconnect the sink, reject writes and exhaust its allocated space; verify bounded memory/storage/retries, truthful unknown/stale indicators, recoverable owner state and recovery after the sink returns. Resolve which evidence is mandatory before an effect and its durable owner; if mandatory evidence cannot be committed, that effect cannot be falsely acknowledged. Required evidence is not silently reclassified as droppable telemetry. |
| NFR7.1 | **Reproduce setup, a defect and a verified repair.** U1 delivery provides versioned setup, dependency/runtime resolution, permitted synthetic fixtures and configuration examples for a clean checkout on the selected evidenced environment. One maintainer must reproduce a representative cross-boundary defect, locate the responsible owner, repair it and run a meaningful regression plus affected mounted integration checks. | BR7.3, BR7.5; LC13–LC14. Record clean-environment setup, diagnosis, repair and verification attempts/times, manual steps and obstacles; repeat from recorded inputs and compare the expected failure then repaired behavior. Use source/model hashes and actual configured free/local paths. No historical passing count, source presence or document validator proves the repair. Stack/permission/capacity decisions and the separate exact completion-command approval remain prerequisites where applicable. |
| NFR7.2 | **Keep ownership, configuration and recovery comprehensible.** Each installed module documents its contracts, data owner, current configuration authority, policy dependencies, lifecycle participant and authorized recovery procedures. ServiceOperations offers concise runbooks with evidence collection, safe owner operations, expected results, rollback/reconciliation conditions and verification. Adding later units updates the same owners and cumulative checks. | WF1, WF5, WF9; BR7.1–BR7.5; LC12–LC14. From a clean checkout, a maintainer identifies the source of a configured limit and the owner of a failed saved-return/job/accounting transition, then follows the relevant runbook without undocumented cross-owner writes. Verify examples against the installed runtime and current interfaces. Record gaps; do not claim readability from a file count or invent setup/repair-time targets before baseline. |

Every row requires real later evidence. NFR9 monitoring readiness and NFR7
reproducibility are U1 contributions; full capability/operator coverage remains
assigned to later units and cumulative U8 verification.

## Evidence and correlation contract

Each recorded observation needs its schema/version, producing owner, observed
capability, authoritative outcome or observation classification, and a timestamp
with clock source. Carry a safe correlation identifier to user-visible error
feedback where authorized. Relevant operation evidence additionally relates the
original intended-operation ID, job ID, result reference, settlement identity
and execution attempt/fence disposition; a transport request has its own ID.
Record only the fields necessary for the evidence's declared purpose.

Identifiers used in telemetry are non-authorizing references. Do not log raw
claim credentials, reusable payload locators, tokens, cookies, verification/MFA
proofs, connection secrets or cursors with private contents. Plain or hashed
emails, prompts and queries are not a substitute for opaque correlation IDs:
predictable hashes can retain identifying meaning. Per-account/resource IDs
belong only in restricted evidence when required; avoid them as unbounded metric
labels. Aggregate views disclose neither private resource existence nor another
account's state.

Use versioned low-cardinality labels for operation class, component, outcome,
dependency class and configured policy revision where useful. Validate and bound
all untrusted error text, including log separators/control characters; normal
logs use stable safe codes. Redaction applies to success, validation, exception,
retry and diagnostic paths. Debug evidence has its own explicit handling policy
and cannot silently relax these rules.

**Clock rules:** elapsed time within one process/harness uses a monotonic clock;
cross-process evidence carries owner wall-clock instants and stated synchronization
or uncertainty. The original owner acceptance instant is immutable across
delivery retries, lease replacement, restart and settlement. It supplies history
`createdAt` and backlog age only after the accepted Functional Design detail is
coordinated before implementation. Attempt start/heartbeat/completion instants
remain separate. Where comparable clocks are unavailable, report duration
unknown or bounded by the actual uncertainty; do not fabricate negative/precise
intervals. Owner-issued job sequence/revision, not telemetry arrival time, orders
business state.

No new application endpoint or implementation technology is selected here.
Canonical schema changes and compatibility checks precede emitting new required
fields across actual consumers. The common error schema's existing safe
correlation field does not authorize private error detail.

## SLI and measurement matrix

Use one versioned run manifest for configuration/build/contract and policy
revisions, allowed source/model/fixture hashes, hardware/resource envelope,
workload/concurrency, cold/warm state, start/end instants and observation cutoff.
Separate synthetic controlled runs from observations of real user traffic.
Neither kind silently substitutes for the other.

| Signal | Source, clock and denominator | Failure/missing treatment and use |
|---|---|---|
| Complete useful journey | Harness steps plus authoritative reads/receipts for P1/P2: valid intended journey attempts in a named run/window; success requires useful source-bound assistance, supported translation check, correct save and fresh authorized revisit as applicable to the declared task. | Count failed, aborted, unresolved and unexecutable attempts separately with cause; never count only completed runs. Report output review failures alongside transport success. Numerical success target follows baseline. |
| Interaction and operation latency | Defined boundaries in the performance document for usable search/content, feedback, acknowledged save/reopen and accepted-job completion. Monotonic client/harness timing where it spans the measured path; owner timing only for its comparable milestones. | Report distributions/sample sizes for observed completions and separate timeout/failure/censored counts for the full cohort. A timeout cannot disappear from the report because no latency value exists. |
| Capability availability | Bounded scheduled checks with an explicit window, planned check opportunities and tested capability path. Report passing opportunities / all scheduled opportunities, plus failure, degraded, stale/missing and not-executed counts. | No-data windows are unknown, not 100% available. Any exclusion, such as announced maintenance, is explicitly defined and reported in both gross and adjusted figures; outages are not removed retrospectively. Sampling does not establish continuous availability between probes. |
| Journey readiness | Required installed capability evidence plus bounded synthetic complete-journey checks with safe fixtures and accounting treatment. A check must exercise the actual mounted path; test accounts and any generated work remain scoped. | A missing required component/policy, failed task or stale check blocks a positive claim for its scope. Liveness and component readiness remain separately visible. Future capabilities cannot be counted as passed. |
| Queue age and execution recovery | Owner's immutable original acceptance time to current comparable owner time; report accepted nonterminal count, oldest age and age distribution by safe operation class. Attempt/claim timings are separate. | Unknown time basis is labeled; negative/clock-invalid values are incidents, not zero. Replacements cannot reset age. Terminal failed/succeeded counts and unresolved accepted obligations remain visible after retries exhaust. |
| Result/accounting integrity | Reconcile authoritative accepted operations, published result bindings, reservation IDs and settlement receipts for the named cohort/window. | Expose unresolved age, orphaned obligations, duplicate logical effects and rejected stale-worker facts separately. Missing sink events alone cannot prove a missing business commit; inspect the owner before recovery. |
| Resource pressure and admission | Timestamped actual resource observations and authoritative admission outcomes, with units, configured limits, policy revision and observation scope. Report rejected/exhausted/unknown admissions over all attempts in the window. | Unknown usage/cost is not zero. Limits measure finite configured headroom; readings from one device do not prove public-host capacity. Estimates state method and uncertainty. |
| Recovery and repair | Monotonic controlled-fault harness milestones, owner-state reconciliation and maintainer work log as defined in reliability requirements and the repair exercise below. | Preserve unsuccessful/unexecutable attempts and remaining work; process restart does not equal repaired behavior. Report time distributions with sample counts and manual interventions, then propose targets. |
| Telemetry quality | Planned collection/probe counts, accepted/dropped/retried evidence, sink failures, last successful observation and configured freshness limit. | Report gaps and stale intervals explicitly even when the main sink is unavailable; any bounded secondary signal has its own health/failure behavior. No infinite recursive error logging. |

The performance document owns detailed responsiveness boundaries; reliability
owns recovery/RTO/RPO boundaries. This matrix requires consistent run identity,
cohorts and failure accounting between documents, not separate competing SLOs.

## Operational views, alerts and recovery

The authorized maintainer view must show the installed capability/dependency
map, current versus stale/unknown checks, pending/old accepted work, result and
accounting reconciliation, admission/resource pressure, protected incident
references, and missing observation coverage. Each value includes its unit,
measurement time/window and source. Korean user feedback exposes only the
relevant safe capability state and recovery action; it does not expose operator
controls or sensitive infrastructure details.

Alerting is a requirement for actionable evidence, not a paid notification
product. A free/local authorized channel and its discoverability must be tested
within the one-maintainer model. No messages to third parties are authorized by
this specification. Each enabled alert names its predicate, observation window,
owner, severity/action, deduplication identity, finite retry/cooldown policy and
resolution check. Repeated failures aggregate without concealing their counts;
recovery clears an alert only when the relevant current check passes.

| Condition | Required response and target status |
|---|---|
| Owner-isolation breach, observed unauthorized effect, duplicate accounting effect or lost acknowledged state | Record an actionable invariant violation with protected evidence and the affected owner; prevent further unsafe effects through its authorized boundary and verify recovery. These are failures without needing a selected rate threshold. |
| Required component failure or missing finite/permitted policy | Expose the affected unavailable state immediately when observed. Observation/probe/delivery delays must be measured; no unselected notification-time guarantee is implied. |
| Backlog age, saturation, repeated failures or stale checks | Candidate numerical trigger, cadence and observation window remain pending measured workload and human-agreed targets. Enable monitoring only with finite configured sampling and failure bounds. |
| Missing/failed telemetry | Surface observation uncertainty through a tested bounded fallback/health path where available; retain authoritative domain receipts. An absent notification cannot certify health. |

Before enabling a telemetry path, classify required business/audit evidence
versus operational observations. Owner receipts, admission/settlement obligations
and authority-dependent effect records cannot be dropped under a telemetry
sampling policy. Ordinary metrics may be buffered/aggregated/dropped only under
the documented finite policy with counts/gaps. Missing mandatory durable evidence
prevents acknowledgement at that boundary, while an ordinary sink outage must
not rewrite an already committed outcome. Reconcile their distinction in code
and fault tests before acceptance.

## Reproducible diagnosis and repair exercise

The U1 delivery record must include the actual setup commands after technology
selection, pinned compatible runtime/dependency versions, permitted synthetic
fixture acquisition/provenance and hashes, configuration keys with a single
authoritative source, finite policy values, launch/readiness instructions and a
teardown that protects existing data. Secrets are supplied through the selected
protected mechanism and never embedded in examples. A local email sink or model
mock is labeled with exactly what it proves; required normal-path integration
uses the actual selected free/local capability.

The maintainer exercise starts from a clean checkout and the documented permitted
environment. Reproduce a controlled fault spanning the browser, service or worker
and persistence boundary; use safe correlation to locate the owning component;
apply a repair; demonstrate the original failure with a meaningful regression
check; then verify affected mounted integration and the cumulative journey.
Record start/end milestones, elapsed active/setup/diagnosis/repair/verification
time, manual steps, failed attempts, assistance required and unresolved obstacles.
The human agrees numerical setup/repair targets after these measurements.

Each runbook names symptoms, evidence/access prerequisites, affected owner,
authorized inspection/reconciliation, when to stop, expected state, rollback or
compensation limits, and final user/domain checks. Cover at least lost save
acknowledgement, stale revision conflict, accepted work without dispatch,
replaced-worker rejection, pending settlement, unavailable result, required
dependency failure, full storage and failed telemetry for U1. Recovery invokes
domain operations; it does not encourage manual cross-owner database edits or
restore revoked material into service. Platform operations retain U7's separate
authority.

Module/contract/configuration documentation must describe the actual installed
application after code is written; a proposed directory tree alone cannot prove
comprehensibility. The repair exercise supplies observable evidence of the
user's repairability goal. Full parity and all later-unit runbooks remain part
of cumulative delivery.

## Open decisions and completion evidence

The domain owners and ServiceOperations must settle finite telemetry budgets,
sampling/freshness/alert policy, permitted fields/access/retention and the chosen
free/local collection/viewing path before enabling it. Technology and operating
capacity selection remain evidence-dependent. Numerical service, availability,
latency, recovery and repair targets wait for measured baseline and human
agreement; these approved deferrals do not permit unbounded monitoring.

Required later evidence includes LC12–LC14 and their LC05/LC06/LC09/LC10
correlations, a clean-setup/repair record, a sink-outage/resource-exhaustion test,
authorization/redaction checks and the SLI manifest with failures included.
Resolve the immutable acceptance-time detail and coordinated canonical contracts
before affected code. Durable research drafts and their recovery remain U4.
The exact runnable cumulative v2 completion command remains separately approved;
these documents, legacy CI and a green dashboard do not prove a completed unit.
