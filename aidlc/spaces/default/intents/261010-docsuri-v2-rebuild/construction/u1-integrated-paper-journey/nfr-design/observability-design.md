# DocSuri v2 — U1 observability and repairability design

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`. Status: logical design and verification obligations; no
monitoring deployment, service baseline, clean installation or verified repair is claimed.

## Scope and authoritative inputs

ServiceOperations interprets owner evidence for one human maintainer within $0 free/local operation. Domain producers use
observation adapters; they do not import ServiceOperations business logic. Observations cannot become authorization,
accounting, job state or recovery authority. One shared application can implement these logical boundaries without a separate
tracing service or vendor product.

Sources: [confirmed questions](nfr-design-questions.md), [observation
requirements](../nfr-requirements/observability-requirements.md), [reliability
requirements](../nfr-requirements/reliability-requirements.md), [technology
decisions](../nfr-requirements/tech-stack-decisions.md), [functional workflows](../functional-design/functional-spec.md),
[rules](../functional-design/rules.md), [entities](../functional-design/entities.md), [contract
coordination](../functional-design/contract-revision-plan.md), [approved
owners](../../../inception/domain-design/components.md) and
[C00/C01/C06/C11/C14](../../../inception/contract-design/contract-summary.md).

## Requirement mapping

| Requirement | Solution | Concrete mechanism and verification |
|---|---|---|
| NFR9.1 | OBS01 | Manifest-derived scoped readiness with expiring evidence and bounded probes; missing/stale dependencies cannot pass. |
| NFR9.2 | OBS02 | Validated safe event envelope and explicit correlation graph with clock provenance; cross-boundary fault/redaction checks. |
| NFR9.3 | OBS03 | Cohort-based indicators, denominator ledger, operational views and local actionable alerts; reconcile with owner outcomes. |
| NFR9.4 | OBS04 | Finite observation budgets, bounded loss policy and distinct mandatory owner records; sink-outage/full-storage checks. |
| NFR7.1 | OBS05 | Versioned clean-setup and controlled defect/repair experiment with repeatable evidence and mounted regression. |
| NFR7.2 | OBS06 | Owner/configuration map and concise recovery runbooks with preconditions, stop rules and verified outcomes. |

### OBS01 — Readiness as scoped, expiring evidence

C01 composition supplies installed capabilities, owners, contract revisions, required dependencies, policy references and
lifecycle participants. Each owner provides a bounded current observation of its own port/store/work path. ServiceOperations
assembles these into separate liveness, dependency/capability readiness and mounted-journey readiness records; it cannot
infer one from another.

| View | Passing evidence | Non-passing interpretation |
|---|---|---|
| Process liveness | Bounded local process response with measurement time | No response is failure/unknown; success establishes only process response. |
| Dependency/capability | Required store/read/write guarantee, compatible binding, current permissions/policy, worker/model path and fresh owner checks for the named operation | Missing mandatory registration/policy blocks the affected capability. A reachable model with unusable output is insufficient. |
| U1 journey | Installed prerequisite evidence plus a permitted synthetic mounted find→understand→save→fresh-return run and supported translation check | A green collection of health endpoints cannot replace the actual journey. Stale/failed/unexecuted journey evidence cannot pass. |
| Full release | Later installed capabilities and cumulative verification for the declared release scope | U1 readiness never certifies future units or complete parity. |

Each record includes observation source, scope, contract/policy revision, measurement time, expiry/freshness limit and
evidence reference. Within a scope, a known mandatory failure means unavailable; a permitted partial mode is degraded;
missing evidence is unknown; expired evidence is stale; absent contribution is not_installed. All block a positive claim
where that contribution is mandatory. Evaluate freshness at read time so a disconnected producer cannot stay green.

Probes have finite interval, execution deadline, concurrency and fixture/storage budgets. Synthetic writes use isolated
permitted fixtures and declared accounting treatment; production business reads do not secretly create test work. Probe
timeout records a failed/unknown observation, never a successful empty result. Current relevant checks must pass after
recovery; restarting a process cannot clear stale capability evidence. Korean user feedback exposes the affected safe state
and action; protected operational detail remains in authorized C11 views.

**Verification and tradeoff:** LC12–LC14 remove a required registration, store, worker, model, compatible contract or finite
policy; stop collection until expiry; then recover each path. Compare liveness, capabilities and journey dispositions. Probes
consume capacity, so reserved finite capacity and freshness values precede enablement. Coarse liveness is cheaper but cannot
satisfy journey readiness.

### OBS02 — Safe correlation with explicit identity and clock boundaries

Producers validate a versioned allowlisted envelope before buffering. Reject or sanitize untrusted control characters and
oversized fields; exception paths use stable safe codes, not arbitrary dependency error text. The same redaction applies to
validation, retries, timeouts, success, debug access and telemetry failures.

| Field group | Meaning, access and cardinality rule |
|---|---|
| Schema/owner/capability/event/outcome | Enumerated supported vocabulary; unknown schema quarantined/counts rejected. Safe low-cardinality metric dimensions. |
| Request and parent observation IDs | Fresh opaque non-authorizing correlation references; checked format/size. Caller text is never copied as trusted correlation. |
| Operation/job/result/reservation/settlement references | Explicit restricted links across the same logical work, preserved across restart/retry. No private identifiers as metric labels. |
| Execution evidence | Attempt reference, fence disposition and committed job revision/sequence; no lease credentials or reusable payload locator. Distinguish proposed/rejected fact from committed owner fact. |
| Policy/build/contract identity | Bounded validated revisions tied to a run/configuration manifest. Detailed hashes live in restricted evidence; metrics use a bounded active revision set. |
| Time and source | Producer wall-clock instant, clock source/synchronization uncertainty, local monotonic elapsed duration when valid and observation receipt time. |

Normal telemetry excludes paper/manuscript/result text, prompts, personal search text, email hashes, tokens, cookies, MFA
material, connection secrets, payload URLs and private cursor contents. Restricted evidence stores opaque per-resource
references only where its purpose requires them, under resolved access/retention policy. A client-visible correlation ID
reveals no private existence or authority. Debug collection requires its own bounded approved handling; it is not a redaction
bypass.

Trace the causal chain using explicit parents: browser request → intended operation → owner receipt/job → dispatch delivery →
claim/attempt → committed result → settlement obligation → UsageEntitlements receipt. Duplicate delivery and replacement are
separate observations attached to the original operation. An observation ID or trace parent never acts as an idempotency key.
Owner state/ revision orders business facts, independently of sink arrival or trace ordering.

Elapsed measurements within a process/harness use its monotonic clock. Cross-owner durations require compatible clock
evidence and stated uncertainty; otherwise report unknown or an uncertainty interval. PaperAssistance commits original
acceptance time once for history `createdAt` and queue age. Attempts, renewals and settlement have separate clocks;
restart/replacement cannot reset queue age. Clock regression or negative/uncertain age becomes a visible invalid measurement,
never a clamped zero or an excuse to extend a claim.

**Verification and tradeoff:** LC05/LC09/LC10/LC13 trace a lost ack, replaced worker and delayed settlement from request to
authoritative receipts. Inject secrets/private strings/control characters in all error paths and inspect every enabled sink
and access role. Simulate skew and out-of-order collection. Explicit links cost some restricted storage but allow diagnosis
without logging private payloads. Canonical field/acceptance-time coordination precedes affected code.

### OBS03 — Indicators and local alerts with complete denominators

Every run/window has a manifest: scope, start/cutoff, build/contract/configuration, policy revision, allowed
fixture/source/model digests, measured resource envelope, workload, cold/warm status and expected collection opportunities.
Controlled runs and real traffic remain distinguishable. The measurement ledger records attempted, accepted, rejected,
timed-out, failed, aborted, unexecuted and unresolved outcomes; retries of one intended operation do not inflate its logical
cohort.

| Signal | Source and explicit denominator | Display and missing-data rule |
|---|---|---|
| Useful journey success | Harness and owner receipts; all valid intended P1/P2 journey attempts in the declared run/window | Successful useful source-bound outputs plus required translation/save/fresh-return checks divided by attempts; show failed, aborted, unexecutable and unresolved counts. Transport success alone is insufficient. |
| Responsiveness | Performance-design boundaries on one comparable monotonic harness/client clock; full attempted cohort | Completion quantiles with sample size plus rejected/failed/timeout counts and right-censored in-flight durations at cutoff. Never exclude timeouts from the cohort. |
| Capability availability | Scheduled opportunities in explicit window; passing checks / all scheduled checks | Show failed, degraded, stale/missing and not-executed counts. Zero opportunities means unknown. Gross and explicitly defined adjusted figures retain maintenance/exclusion counts. |
| Queue/execution health | Authoritative accepted nonterminal jobs, original acceptance time and comparable current owner clock | Count, age distribution and oldest age; attempt timings separate. Terminal failures and unresolved obligations remain visible after retry exhaustion. |
| Result/accounting integrity | Reconciliation of accepted-operation cohort against result bindings, reservations and settlement receipts | Pending count/age, missing references, conflicting/duplicate effects and stale-worker rejection counts. Missing telemetry requires owner inspection, not an inferred missing commit. |
| Admission/resources | All admission attempts and timestamped resource readings with units/limits | Report accepted/rejected/exhausted/unknown outcomes and headroom; unknown usage/cost is not zero. Distinguish measured values from estimates. |
| Recovery/repair | Named fault cohort and monotonic milestones through domain-state/journey verification | Detection, recovery, setup/diagnosis/repair/verification time and interventions; preserve failures and censored/unexecutable attempts. RTO/RPO details follow REL04. |
| Evidence quality | Planned opportunities and accepted/rejected/dropped/retried records | Gap counts, last successful observation and stale duration; counters have reset/discontinuity markers and cannot promise coverage during their own outage. |

The authorized operational view groups installed capability/dependency evidence, pending/old work, result/accounting
integrity, admission/resources and incidents. Each value shows source, scope, unit, window/time, freshness and
observed/estimated/ unknown classification. Restricted drill-down follows operation links to owner receipts; aggregate charts
avoid owner/resource labels. Query/page limits and aggregation retention are finite, preventing a diagnostic view from
exhausting work.

Alerts use a deduplication key of capability, condition class and policy revision, with first/last seen, occurrence count,
protected evidence reference, owner, severity, safe next step and current resolution check. Repetition updates one incident
and its count. Finite retry/cooldown rules bound local delivery. A local authorized incident view and tested local/free
notice path are candidates; no third-party message or paid paging path is authorized by this design.

Observed isolation breach, duplicate accounting, lost acknowledged state or unauthorized effect triggers an invariant
incident without a rate threshold. The affected owner blocks unsafe effects via its existing authority boundary;
ServiceOperations does not edit its records. Required dependency/policy failures surface when observed.
Backlog/latency/saturation/error-rate thresholds, cadence and windows require baseline and human-agreed service targets.
Recovery resolves an alert only after current owner and affected-path checks pass, not after silence.

**Verification and tradeoff:** run P1/P2 load/fault cohorts, deliberately reject admission, time out work, omit probes and
delay settlement. Independently compute denominators from harness/owner evidence and compare views/alerts, including the
no-data case. Test local discoverability with the maintainer and measure delay. Bounded sampling is affordable but cannot
establish continuous service availability.

### OBS04 — Bounded telemetry failure without loss of business truth

Before collection, classify each record. Mutation/acceptance receipts, authority dispositions, mandatory audit evidence and
admission/settlement obligations remain durable owner records under REL01–REL03. Where mandatory evidence must precede an
effect, the owner includes it in its durable commit or refuses acknowledgement. Sampling/drop policy never applies to that
authority-bearing record. An optional copy of it in the observation sink is explicitly a projection.

Ordinary observations use finite per-producer buffers and a finite shared budget: bounded event size, queue length/bytes,
batch size, sink wait, retry count/deadline, retention and disk allocation. Under pressure, aggregate low-priority counters
and drop designated oldest ordinary records according to versioned policy; increment loss counters and mark gaps. Limit
high-priority ordinary observations too; reserve bounded capacity, never let a priority flag make storage unlimited. Do not
evict business records or private staged/results to rescue telemetry.

On sink failure, bounded backoff ends in drop/gap accounting for ordinary records. A nonrecursive local health/counter path
reports sink failure if available; it has independent finite limits and an explicit unavailable state. A failed fallback
cannot report its own health reliably, so readers evaluate freshness independently. Restart markers distinguish reset
counters from zero drops. Sink recovery drains only retained bounded data, preserves original timestamps and cannot fabricate
the missing interval. Normal business outcomes remain governed by their owners.

**Verification and tradeoff:** LC12/LC13 disconnect/reject the sink, fill its allocated disk/buffer, crash producers and fail
the fallback. Check finite memory, storage/retry growth, no recursive logging, explicit gaps/staleness, retained owner
receipts and successful reconciliation. Separately fail a mandatory owner-record write and confirm no false ack. Dropping
optional detail sacrifices diagnostics to preserve service capacity; loss must remain visible rather than silently sampled.

### OBS05 — Reproducible setup and defect-to-repair evidence

After technology selection, the versioned U1 delivery package records exact runtime/dependency/model identities, clean
checkout/setup commands, safe example configuration, authoritative policy sources, finite values, fixture provenance/ hashes,
readiness checks, permitted storage paths and isolation/teardown steps. Secrets stay outside examples. A mock or local email
sink names the limited behavior it proves; required normal-path checks use selected actual capabilities. NFR7.3 stack
selection is a cross-reference, owned in the technology/design handoff.

The maintainer starts in the documented clean isolated environment, reproduces a representative lost acknowledgement or
accepted-work/settlement defect across real mounted boundaries, and follows OBS02 correlation to its owner. Preserve the
failing evidence, fix the cause, show a meaningful regression reproduces the original failure before repair and passes after
it, then run affected mounted integration and the cumulative paper journey. A restart alone is not a repair.

Record attempts, exact invocations, configuration/fixture revisions, start/cutoff, active versus elapsed
setup/diagnosis/repair/verification time, manual interventions, assistance needed and unresolved obstacles. Repeat from
recorded inputs to expose undocumented prerequisites. The exact runnable completion command still needs its separate human
approval; design or legacy test output does not substitute for it.

**Verification and tradeoff:** LC13/LC14 evidence includes clean setup, expected failure, owner diagnosis, patch, regression
and mounted result. Failed/unexecutable runs remain recorded. This exercise costs finite isolated resources but supplies
repairability evidence that a directory tree or documentation count cannot. Numeric setup/repair targets follow the measured
baseline and human agreement.

### OBS06 — Owner-directed runbooks and configuration provenance

Each installed module's delivery documentation names its canonical contracts, exclusive data owner, configuration
authority/precedence, active policy revision, lifecycle participation, protected stores and supported recovery operations. An
effective-config view discloses safe limits and their source without secrets. Changing a limit retains
revision/effective-time evidence; absent/conflicting mandatory values block the affected operation. Later modules extend this
same map and cumulative checks; PlatformControl/U7 authority remains independent.

| Runbook | Inspection, authorized action and verification |
|---|---|
| Lost save acknowledgement / stale revision | Authenticate; read original receipt/current Library state; reconcile exact intent or present conflict. Verify one effect and deliberately requested next action. |
| Accepted work without dispatch / replaced worker | Inspect PaperAssistance obligation/current claim; invoke bounded owner recovery/reclaim only when eligible. Verify same job/input, newer fence where appropriate and rejected old-worker facts. |
| Pending admission / settlement | Inspect both owners' original operation/reservation receipts; seal definitive rejection or settle only via owning protocol. Unknown remains pending; verify no duplicate debit or unauthorized release. |
| Unavailable prepared result | Recheck current owner/source permission, original binding and availability. Restore only authorized retained material or report expiry/restriction; read retry cannot regenerate. |
| Required dependency / full storage | Identify capability and finite budget; stop affected admission, preserve accepted obligations, restore evidenced capacity/dependency. Verify owner integrity and mounted affected journey. |
| Failed telemetry | Inspect independent freshness/gap evidence, restore bounded sink path, record lost interval. Verify owner state separately and never replay business effects from logs. |
| Restore / lifecycle suppression | Follow REL04 isolation, keys and current authority reconciliation; stop if evidence is missing. Verify no exposure of revoked/erased material before serving. |

Every runbook records symptoms, access/evidence prerequisites, responsible owner, safe inspection and action, expected
receipt/state, stop/escalation condition, rollback or compensation limits and final user/domain check. Direct cross-owner
database edits are not a recovery procedure. Irreconcilable evidence stays an incident with protected references; no
fabricated outcome or automatic paid fallback.

**Verification and tradeoff:** from a clean checkout, the maintainer identifies the actual source of an effective limit and
resolves a saved-return/job/accounting fault using the installed interfaces and runbook. Record missing steps and failed
actions, then correct the delivery documentation. Concise owner procedures reduce operator ambiguity but remain useful only
when checked against installed behavior.

## Enablement and closure dependencies

Resolve safe fields/access/retention, finite collection/probe/query/alert budgets, free/local viewing and discoverability,
current clock evidence and canonical identity/acceptance-time amendments before enabling their paths. Preserve the
PaperAssistance glossary owner and non-null initial revision; Personalization owns assistance defaults. Research drafts
remain U4. No topology or stack is selected from available tooling. Baseline-dependent service targets remain open; finite
safety policy values cannot remain unset during an experiment or operation.

Implementation evidence must cover LC05/LC06/LC09/LC10/LC12–LC14 with selected adapters and failure-inclusive manifests.
[Reliability design](reliability-design.md) defines business recovery and restore; other NFR designs define performance,
security and resource boundaries. Document checks do not close canonical contract findings, certify full capability,
authorize migration or prove public readiness.
