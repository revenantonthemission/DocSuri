# DocSuri v2 — U1 reliability requirements

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`.
Status: requirements derived from the confirmed summary; no execution, restore,
availability or durability result is claimed.

## Scope and authoritative sources

These requirements elaborate inception **NFR3** for the real find → understand
→ save → revisit journey, supporting NFR1, NFR4, NFR5, NFR8, NFR9 and NFR10.
The domain owners retain their responsibilities across U1 and later units;
ServiceOperations coordinates evidence and invokes owner recovery without
rewriting their data.

Sources are the [confirmed NFR proposal](nfr-requirements-questions.md),
[inception NFRs and FR acceptance criteria](../../../inception/requirements-analysis/requirements.md),
[functional workflows and local checks](../functional-design/functional-spec.md),
[business rules](../functional-design/rules.md),
[entity ownership](../functional-design/entities.md),
[contract revision plan](../functional-design/contract-revision-plan.md), and
[canonical contracts](../../../inception/contract-design/contract-summary.md)
(common acknowledgement rules; C03, C06, C11 and C14). Local WF, BR and LC
identifiers reference the functional design, not additional upstream requirements.

The canonical browser revision, worker claim/payload/fencing and retained-job
history amendments remain prerequisites before affected implementation. This
document supplies reliability acceptance conditions for that coordination; it
does not create a competing wire contract or close the accepted findings.

## Derived requirements

| ID | Requirement and accountable owner | Observable verification and prerequisite |
|---|---|---|
| NFR3.1 | **Recover acknowledged writes and reconcile uncertain effects.** AccountAccess, Library and Personalization acknowledge their U1 persistent transitions only after the owning durable state and required recoverable receipt exist. In the documented ordinary-fault envelope, an acknowledgement survives browser, service and worker restart. An uncommitted failure retains prior committed state; an unknown reply remains unknown until owner reconciliation. Required revision checks are atomic, and an idempotent replay cannot overwrite a newer state. | WF1, WF2, WF7; BR1.1–BR1.5, BR3.5, BR4.1–BR4.6; LC01, LC07–LC09. Inject write rejection, lost acknowledgement, restart after commit, two same-revision writes, duplicate/reordered history facts and a clear/history-delivery race. Compare original owner receipts and fresh authenticated lists, including account B denial. Record every missing or duplicate acknowledged effect. Browser revision amendment and selected storage durability/fault guarantees must be evidenced before implementation acceptance; no promise extends silently to unrecoverable media loss. |
| NFR3.2 | **Preserve accepted work and reject replaced workers.** PaperAssistance binds an accepted operation to immutable input, original acceptance time, reservation reference and durable execution/recovery obligation before acknowledgement. Claim acquisition/replacement is atomic; current worker, lease, fence, input and job revision authorize every new progress or terminal fact. Lease renewal has a separate revision. No transport disconnect or view closure cancels a job or changes its business outcome. | WF4–WF6; BR5.2–BR5.3, BR5.5–BR5.8, BR5.10; LC05, LC06, LC09. Crash before dispatch, redeliver, renew, expire/reclaim, restart and submit old-worker progress/failure/success. Recover the original job and reject stale new effects; duplicate committed facts may recover their original authorized receipt. Resolve canonical worker contracts, owner-time behavior and finite retry/lease/deadline policy before execution. The immutable acceptance-time detail must be coordinated before code. |
| NFR3.3 | **Recover one intended accounting effect across owners.** PaperAssistance and UsageEntitlements retain one operation/reservation identity through admission, result publication and settlement. PaperAssistance commits the validated result/terminal state coherently with a durable settlement obligation; UsageEntitlements settles idempotently under the resolved accounting policy. Pending settlement and uncertain admission are explicit and recoverable. No cross-owner database transaction or exactly-once transport is assumed. | WF4–WF5, WF8; BR5.2–BR5.4, BR5.8; LC05, LC10. Inject faults after reservation, after acceptance, before/after result commit, before/after settlement and after acknowledgement loss. Reconcile authoritative owner outcomes and count jobs, visible results, reservations and logical debits/refunds. A browser timeout cannot release an uncertain reservation. Definitive rejection/failure releases or refunds only under resolved owner policy; concurrent admission/reset cases preserve its documented window semantics. |
| NFR3.4 | **Define the fault envelope, verify isolated restoration and preserve continuity.** Each data owner documents authority, protected state, rebuildable derivatives, durability assumptions and recovery dependencies. ServiceOperations coordinates an isolated restore drill covering owner relationships, protected artifacts, accepted work, settlement and current revocation/withdrawal/erasure obligations. The human selects existing-user continuity after inventory and recoverable-backup evidence. | WF9; BR7.1–BR7.4; LC12–LC14; functional prerequisites E1–E4 and E6. Inventory users/data/keys and actual backup media before any migration or reset. Inject ordinary faults and separately simulate media/environment loss in an isolated synthetic environment. Measure recovery time and actual unrecovered acknowledged state against a known source ledger. Backup existence or matching row counts alone is insufficient. RTO, RPO, availability and retention targets remain pending baseline evidence and human agreement; restore must not serve data until current authority and lifecycle restrictions have been reconciled. |
| NFR3.5 | **Rediscover retained prepared results through read-only recovery.** PaperAssistance owns the planned bounded, stable, owner-bound assistance history; Library owns saved references. A fresh authenticated browser with no transient job/result identifiers can select the exact saved paper/version, discover permitted retained work and read its original result. Reconnect, replay, polling, history and result reads create no new job or usage debit. | WF6–WF7; BR5.7, BR5.9–BR5.10, BR6.1–BR6.2; LC06, LC07, LC09. Discard browser IDs, restart and reauthenticate; verify exact source/options/result binding and unchanged execution/accounting counts. Exercise expired/withdrawn/missing result, failed reads, cursor expiry/change, equal original acceptance times and account switch. Unknown, empty and expired states remain distinct. Canonical history contract, immutable acceptance time, retention/cursor policy and current permission checks precede implementation; durable research drafts remain U4. |

These rows define U1 contributions, not full release parity. Their invariant
checks must pass for implementation acceptance. Baseline-first numeric targets
do not make owner isolation, truthful acknowledgement, bounded recovery or
duplicate-effect prevention optional.

## Fault model and acknowledgement boundary

| Fault class | Required behavior | Evidence boundary |
|---|---|---|
| Browser offline, response loss, sleep, refresh or restart | Preserve acknowledged server state; recover the same original receipt/job; invalidate stale private presentation state on account switch. Explicit new actions remain explicit. | Use real browser/service boundaries and discard volatile IDs for the fresh-return case. Unsaved input is not falsely described as acknowledged; durable research drafts are outside U1. |
| Application or worker process termination with the selected durable store intact | Recover acknowledged writes, accepted execution obligations and pending settlement without new intended identities. Fence abandoned/replaced claims. | State the actual storage durability acknowledgement and restart configuration. Deliberately terminate at named commit/delivery boundaries; a graceful shutdown alone is insufficient. |
| Temporary dependency outage, storage rejection, full disk or unavailable policy | Reject new work safely when it cannot be accepted durably; preserve committed data; expose the affected degraded/unavailable capability and actionable pending recovery. | Inject before and after the owner commit boundary. Do not infer “not committed” from timeout. Bounded queues/retries and a finite recovery policy are prerequisites; a full store must not trigger destructive cleanup of protected work. |
| Whole machine power loss or abrupt storage disruption | Claim protection only where the chosen persistence system and configuration provide evidenced durability; reconstruct effects from owner records where recovery is supported. | A process-restart test does not establish power-loss durability. Select the actual failure envelope and execute a suitable non-production drill before making that claim. |
| Media loss, corruption or loss of the authoritative environment | Restore from identified recoverable sources, reconcile integrity and current authority, then measure loss and elapsed restoration. Report unrecoverable state explicitly. | No zero-loss disaster guarantee exists from the current evidence. Backup location, consistency, key recovery, recoverable scope, RPO/RTO and disaster procedure remain unresolved until inspected and tested. |
| Revocation, withdrawal or approved deletion during work/recovery | The owner's linearization and current policy prevent prohibited payload access, publication or resumed serving; a restored or late record does not reauthorize itself. | Test races at reads and effect commits, and reconcile post-backup restrictions before restored data can be exposed. Physical deletion and retention claims require their own approved policy and evidence. |

Publication and accounting are different owner commits. The recovery record must
identify the phase and the next authorized owner operation. A retry count,
telemetry event or message-delivery acknowledgement is not the authoritative
business receipt. Staged result bytes remain inaccessible until the valid
committed binding exists. Success cannot reference a missing or mismatched
prepared result; later legitimate expiry affects availability without rewriting
the historical terminal job outcome.

Finite retries may end automatic attempts, but they must not erase the durable
obligation. Exhaustion leaves a classified, discoverable failure or pending
reconciliation with a named maintainer procedure. Already accepted work receives
an authoritative outcome or an explicit unresolved incident, never silent loss.
The policy governing retry exhaustion, release/refund and operator intervention
must be settled before enabling that path.

## Recovery measurement protocol

Use permitted P1/P2 fixtures and synthetic A/B accounts in an isolated environment.
Capture the build/configuration and contract revisions, persistence mode,
resource limits, input/source hashes and protected expected-state ledger before
each fault. Store only the necessary synthetic evidence under the resolved
access/retention policy.

| Measurement | Clock, population and denominator | Report and decision |
|---|---|---|
| Acknowledged-state retention | Population: all owner acknowledgements in the named run before fault injection, taken from the independent test ledger. After recovery, reread each intended current effect through its owner. | Report acknowledged total, correctly retained/reconciled total, missing effects, unintended extra effects and unresolved inspections. An intentional later removal is compared with its receipt, not called data loss. Inspection failure is unresolved, never excluded as success. |
| Accepted-work recovery | Cohort: every accepted operation in the faulted run, with immutable owner acceptance time and original identity. Record claimed/terminal/settlement milestones and observation cutoff. | Report succeeded, failed, still pending, inaccessible and unknown counts separately; retries are not new logical attempts. A failed but correctly accounted operation demonstrates recovery behavior, not useful journey success. |
| Duplicate effects | Compare visible domain/result/accounting effects with unique intended operation/reservation identities for the entire cohort, including crash and retry cases. | Report duplicate jobs/results/debits and unintended release/refund effects separately. Duplicate transport delivery is expected test input, not itself a duplicate business effect. |
| Recovery duration | Record injection, observed detection, recovery start, verified usable capability and verified domain-state reconciliation. Use one monotonic harness clock for elapsed intervals; preserve owner wall-clock instants plus clock-source/uncertainty metadata for correlation. | Report each interval and unresolved right-censored attempt at the observation cutoff. Do not subtract wall clocks from unrelated machines without established synchronization/uncertainty. Availability recovery and complete data reconciliation can have different endpoints. |
| Restore RTO/RPO baseline | Start RTO at the declared disaster/drill disruption point and end only when required usable capability and integrity/authority checks pass. Compare a known source acknowledgement ledger with restored consistent state; report last protected source point and actual loss interval/count. | Record setup/manual/key-recovery time, missing references/artifacts, lost acknowledgements and restrictions reapplied. A clean row count is not proof of RPO. Human-agreed targets follow this baseline; the drill establishes only its tested scope. |

Record the fault/run count, repetitions, cold/warm condition, workload and
resource envelope. Preserve failures, aborted and unexecutable attempts in the
results. A planned test outside U1 is labeled deferred, not omitted from an
applicable denominator. For each scenario, show individual results and suitable
distributions with sample sizes; unobserved recovery has no fabricated duration.

## Availability, degradation and target decisions

No availability SLA/SLO, RTO or RPO number is selected. ServiceOperations and the
domain owners must collect capability and journey availability over an explicit
window and schedule, then present proposed targets and resource consequences to
the human. The [observability requirements](observability-requirements.md) define
the measurement basis and handling of unknown, stale and failed probes. A
workstation being available during one demonstration does not establish a
public-service availability commitment.

Degrade at the affected boundary: a failed history write may leave useful search
results visible with “history not saved”; an unavailable model preserves reading
where currently permitted but blocks new model work truthfully; a failed result
read offers read-only retry; a failed store prevents a false save acknowledgement.
No fallback changes source permissions, introduces payment or silently removes a
retained release capability. Restored readiness requires fresh relevant checks,
not merely a process restart.

## Prerequisites and completion evidence

| Decision/evidence | Responsible delivery | Consequence while unresolved |
|---|---|---|
| Canonical browser/worker/history coordination and immutable acceptance time | U1 architecture and owning components; later consumers complete their bindings | Affected code and executable finding closure wait; logical requirements can proceed. |
| Persistence acknowledgement/fault guarantees; finite admission, retry, deadline, lease, quota/reset and settlement policy | U1 component owners with the measured free/local configuration | Affected operation is not enabled under unbounded or guessed defaults. |
| Authoritative users/data, recoverable backups, key access, current restrictions and continuity | Owning units and ServiceOperations; human continuity decision, U8 cumulative verification | No existing-user reset, migration or continuity assertion. Isolated synthetic work does not mutate existing data. |
| Retention, deletion, result/cursor lifetime, shared-device handling and source/model rights | AccountAccess, CorpusContent, PaperAssistance and relevant policy owners | Affected persistence/cleanup/processing and restore exposure remain blocked. |
| Availability/recovery measurements and quantitative proposals | ServiceOperations with domain owners; human target agreement | Report evidence and unknown targets without a service guarantee. |

Completion evidence includes LC05–LC10 and LC12–LC14 fault records, original
receipts and outcome reconciliation, fresh authenticated revisit, A/B isolation,
and a documented restore scope. Preserve the $0 budget and one-maintainer model.
The exact cumulative runnable v2 verification command still requires its separate
approval before first completion use; document validation and legacy CI do not
substitute for it.
