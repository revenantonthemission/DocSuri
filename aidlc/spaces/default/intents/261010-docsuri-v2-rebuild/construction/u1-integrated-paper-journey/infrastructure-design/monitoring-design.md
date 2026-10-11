# U1 monitoring design

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`.
Status: infrastructure design for an isolated local experiment. Collection, alarms,
readiness, usefulness and recovery have not been implemented or measured by this
document. The [infrastructure specification](infrastructure-specification.md)
controls the physical binding and shared resource envelope.

The [confirmed proposal](infrastructure-design-questions.md) preserves one shared
application, a separately controlled operator executable, all eventual release
capabilities, one human maintainer and $0 operation. This design binds OBS01–OBS06
from [observability design](../nfr-design/observability-design.md) to a small local
observation facility. Public hosting, real sensitive-data retention and numeric
service-quality targets remain separate unresolved operating decisions.

## MON01 — Local observation facility and ownership

| Resource / interface | Concrete design binding | Access, failure and ownership boundary |
|---|---|---|
| Event producers | Versioned allowlisted structured JSON events from the application, executor and mounted verification harness; validate before buffering | Domain adapters emit observations without importing ServiceOperations business logic. Rejected/oversized records increment bounded rejection counters; do not log the rejected value. |
| Local collection | One lightweight collector role in the installed release, supervised with the local application; bounded local IPC or protected file handoff; JSONL rotation and finite aggregate files | Runtime/IPC identity and access restrictions must pass the selected native/container binding tests. No public metrics listener, external telemetry account or paid service is needed. A readable directory by itself is not an access or capacity boundary. |
| Owner evidence | Owner ports expose bounded, authorized receipt, queue, claim, result and settlement summaries to ServiceOperations | Observation is read-only. PaperAssistance, UsageEntitlements and other owners retain business authority and mandatory records. A log cannot authorize replay, settlement, cleanup or repair. |
| Incident/readiness view | A protected local ServiceOperations view in the shared application, with a local read-only status export for service-down diagnosis | The human has observation permission; owner recovery commands require the separate effect permission. PlatformControl credentials and its future U7 controls remain independent. No anonymous diagnostics endpoint or implicit operator grant. |
| Incident authority | ServiceOperations stores incident identity, deduplication, acknowledgement and current resolution evidence through its own bounded owner repository | Mandatory incident/audit facts use the protected owner-store allocation. The rotating JSON copy and dashboard cache are projections; deleting one cannot resolve an incident. |
| Collection health | Supervisor-readable bounded heartbeat and drop/reset counters, independently checked for freshness | This fallback has its own finite allocation and never calls the broken logging path recursively. Missing fallback evidence is unknown/stale, never zero loss. |
| Local dashboard groups | Capability/dependency readiness; active and old accepted work; result/accounting reconciliation; shared resource headroom; incidents and evidence gaps | Each value shows scope, source, observed/estimated/unknown, unit, time/window, freshness and build/policy identity. Restricted drill-down follows opaque links to authorized owner evidence, with finite page and query bounds. |

A separate monitoring database, time-series service and distributed tracing server
are unnecessary for the proposed small experiment. Reconsider them only if measured
diagnostic needs exceed this design within the same $0 and one-maintainer constraints.

The local integration profile places the application, executor, model and this
collector in controlled native roles. PostgreSQL 16.15 in one isolated database
is the selected transaction binding for U1 implementation and its next mounted
experiment: the [storage evaluation](evidence/storage-evaluation.md) passed the
eight modeled PostgreSQL primitive checks, including correct owner guard ordering.
Those probes used tmpfs. The intended dedicated persistent Docker volume still
requires container/VM restart, coherent backup and mounted owner-role conformance
before acceptance. Observation readers use owner ports, not privileged database
access. PaperAssistance's durable dispatch/claim records live in PostgreSQL; no
Redis, SQS or OpenSearch service is an initial monitoring dependency. The candidate
model binding remains local Ollama with exact verified cached Qwen3/BGE-M3 identities;
the collector neither loads a model nor calls generation/embedding as a background
health probe. The final infrastructure manifest controls version/digest and
selection status; this profile is design pending conformance evidence.

## MON02 — Metrics & KPIs

| Metric | Source | Threshold | Why it matters |
|---|---|---|---|
| Useful complete P1/P2 journeys | Mounted harness plus authorized owner receipts and competent output review; unique intended journey cohort | Every required checkpoint case must pass; operational percentage target remains unset | HTTP success cannot stand in for grounded assistance, supported translation, durable saves or fresh return. |
| Action feedback, usable search/content, save ack, admission ack, rendered result and revisit elapsed time | One monotonic browser/harness clock per boundary; owner correlation for components | Report sample count, distribution, failures and censored/incomplete work; latency target requires baseline and human agreement | Preserves the full user-visible critical path and slow/failed attempts. |
| Accepted queue count/bytes, oldest age and age distribution | PaperAssistance authoritative nonterminal jobs and immutable original acceptance time | Admission compares effective finite owner/global count/byte limits; age alert threshold remains unset until baseline | Attempts and claim replacement cannot reset accumulated waiting time or manufacture throughput. Invalid clock age is reported invalid. |
| Active claims, model load/resident memory and execution elapsed | Current owner claims plus supervised executor/model measurements | Enforce the infrastructure experiment allocation and one configured execution permit; stop unsafe new admission before reserve is consumed | File size is not inference memory. Measure model loading, replacement overlap, process peaks and shared pressure. |
| Pending admission/reservation/settlement count and age | Bounded owner reconciliation reads, linked by original operation identity | Any contradictory/duplicate effect is an invariant incident; age escalation follows a configured finite reconciliation deadline | A timeout does not prove rejection or authorize reservation release. Unresolved obligations remain visible. |
| Binding/receipt integrity | Owner evidence for acknowledged saves, accepted input/result hashes, terminal facts and settlement receipts | Any lost acknowledged state, wrong binding or unauthorized effect triggers an invariant incident | Optional telemetry gaps must not be interpreted as missing business commits. |
| Offered/admitted/rejected/completed/failed/unresolved work | Harness ledger reconciled with authoritative admission and job dispositions | Boundaries use enforced policy; report all categories and duplicate attempts separately | Prevents apparent capacity increases from hiding rejection or counting retries as new successful work. |
| Shared RAM/CPU/storage, per-lane bytes and free headroom | Supervisor/process measurements plus allocation ledger and actual filesystem free-space observation | Compare the single combined allocation, enforced caps and recovery floor in the infrastructure specification; stale/unknown capacity stops affected new admission | Owner directories or logical pools alone cannot reserve physical capacity. Include logs, staging, backup/restore and cached/model residency. |
| Dependency/authority/required-policy disposition | Current bounded owner probes and assembly/configuration manifest | Any required unavailable, unknown, stale or not-installed contribution blocks positive readiness for that scope | A responding process cannot prove authority ordering, permitted processing or useful output. |
| Observation rejected/dropped/retried records and scheduled gaps | Producer/collector counters with reset markers; independent expected-opportunity ledger | Any loss or stale collection is visible; saturation applies MON05's finite drop rule | Zero events during a sink outage does not mean no failures. |
| Restore loss, recovery time and repair effort | Isolated drill acknowledgement ledger, monotonic milestones and intervention log | Report observed loss/count, elapsed/active time and unresolved cases; target values await baseline and human agreement | A restart is different from a coherent authority-safe restore or a repaired defect. |
| Provider/routing disposition | Effective allowlist and provider evidence manifest | Any unknown recipient, terms, quota or potential paid fallback blocks the affected adapter | Unknown cost is not zero; a local sink does not prove public email delivery. |

Metric labels use a bounded vocabulary for component, capability, outcome and active
policy/build class. Owner IDs, job IDs, paper IDs, URLs, raw queries and hashes do
not become labels. Detailed opaque references exist only in restricted evidence.
Every measurement run records build/configuration/contract/model/fixture identity,
resource envelope, cold/warm state, start/cutoff and planned observation opportunities.

## MON03 — Alerts and local response

| Alert | Condition | Severity | Routes to |
|---|---|---|---|
| Isolation or integrity breach | Observed unauthorized data/effect, duplicate accounting, lost acknowledged state, corrupted published binding | Critical invariant; no rate threshold | Durable local incident for the human and protected ServiceOperations view. The effect owner closes the unsafe boundary; Operations cannot edit its records. |
| Required capability unavailable | Required policy, authority guard, store, executor or eligible provider fails its current check | Error for affected scope | Same local view and supervisor status on next local inspection; safe capability-specific user state. No third-party messages. |
| Recovery reserve at risk | Fresh shared-capacity reading reaches configured stop floor/cap, or reservation cannot be honored | Error; stop affected new admission | Local incident with actual bytes/units, affected lane and owner runbook; preserve already accepted responsibility. |
| Accepted work needs intervention | Reconciliation/retry budget exhausted, unknown admission outcome, stale claim cannot safely recover or settlement contradicts owner evidence | Error | Human's local incident queue with original identity references and bounded owner lookup/recovery procedure. Never auto-release merely because work is old. |
| Backlog, latency or capacity trend | Baseline-derived condition crosses a future human-agreed service threshold | Warning/error according to approved policy; currently not enabled as a service-rate alarm | Local incident view once an actual policy/window is selected. Raw observations are visible before that selection. |
| Evidence stale or lost | Required observation expires, counters report loss, sink is full/unavailable, fallback freshness expires | Warning for optional diagnostics; error where required readiness evidence is missing | Local status and incident projection when possible. Missing delivery/collector evidence remains visibly unknown. |
| Restore/current-authority mismatch | Restore lacks current revocation/deletion evidence, coherent artifact binding, recovered key or valid claim treatment | Error; keep restored scope closed | Local incident and isolated restore report for the human; no public exposure or automatic dispatch. |
| Unapproved route or potential charge | Provider/runner route exceeds evidenced free configuration or falls outside the allowlist | Error; adapter/run disabled | Local preflight report and incident view. No paid fallback or automatic purchase. |

Deduplicate by capability, condition class and policy revision. Preserve first/last
seen, occurrence count, responsible owner, protected evidence reference, safe next
step, acknowledgement and resolution evidence. Acknowledgement means seen, not
resolved. Resolve only after current owner checks and the affected path pass.
Recovery cannot erase the failed interval. Human attention latency is measured in
the local drill; this design offers no unattended paging or 24-hour response promise.

## MON04 — SLIs / SLOs

| SLI | SLO target | Measurement window |
|---|---|---|
| Useful complete journey success: successful required useful journeys / all valid intended journeys | Unset until eligible P1/P2 and translation baseline plus human agreement; checkpoint cases have explicit pass criteria | Each bounded run's declared start/cutoff initially; an operating rolling window remains unset |
| Capability availability: passing scheduled opportunities / every scheduled opportunity | Unset; show failed, degraded, unknown, stale and missed checks | Explicit experiment window and cadence; no claim about unsampled periods or future public service |
| Foreground/search/save/assistance/revisit latency | Unset; report completion distribution and full failure/timeout counts | Per declared cold/warm workload cohort; one intended operation is distinct from attempts |
| Accepted work resolution and oldest nonterminal age | Unset; safety deadlines remain separately finite | Original-acceptance cohort through cutoff, including unresolved/censored work |
| Result/accounting integrity | No contradictory or duplicate effect permitted; an invariant, not a rate-based error budget | Every tested operation and current authorized reconciliation scope; disclose missing evidence |
| Fault recovery, restore loss and defect-to-repair time | RTO, RPO and repair target unset | Named isolated fault/drill from disruption through verified useful recovery and reconciliation |
| Observation completeness | Target unset; all known loss/gap/reset information must be disclosed | Planned collection opportunities versus observed records for each run/window |

Zero eligible samples/opportunities means unknown. Do not drop failed, aborted,
unexecuted, excluded-maintenance or unfinished cases from the recorded denominator.
If adjusted availability is later useful, show its declared exclusions alongside
the gross figure. Cross-process elapsed values require clock provenance and measured
uncertainty; otherwise report unknown or an interval. Owner revisions order effects,
not trace arrival time. Material model/runtime/configuration/data changes and later
units require rebaselining before applying old targets.

## MON05 — Logs & Tracing, retention and finite experiment policy

| Record class | Concrete format and protection | Retention / failure treatment |
|---|---|---|
| Ordinary event/trace | UTF-8 JSONL allowlist: schema, event, owner/capability, safe outcome, opaque correlation/parent, attempt and committed sequence references, bounded policy/build identity, producer time, receipt time and local monotonic elapsed when valid | Rotate within the optional observation allocation; expiry and byte limits both apply. Oldest eligible optional records may drop with explicit loss/gap counters. |
| Causal trace | Explicit request → intended operation → receipt/job → delivery → claim/attempt → result → settlement obligation → accounting receipt links | Same protected finite retention as ordinary evidence. Never use a trace ID as a credential, idempotency key or recovery command. |
| Aggregates/dashboard | Small bounded interval files and restricted incident projection; no identity labels or private payload | Reconstruct where possible from permitted owner summaries; missing historical observations remain gaps. |
| Mandatory owner facts | Durable mutation/acceptance/fact receipts, obligations, required audit and mandatory incident state in the owner's protected store | Retention follows owner reconciliation/lifecycle policy. Never sampled, rotated or evicted to make log space. A required record write failure prevents the dependent acknowledgement/effect. |
| Fixture/output review evidence | Isolated synthetic/eligible-content run record; exact source/model hashes and necessary approved output evidence | Separate protected verification allocation and declared experiment expiry, not routine telemetry. Real-source permissions and evidence retention must be resolved before capture. |

Exclude source/result/manuscript text, prompts, personal queries, email or email
hashes, tokens/cookies, MFA material, secrets, payload URLs and private cursors from
ordinary logs. Use safe enumerated failure codes; arbitrary exception text is not
an exemption. Bound field length and reject control characters before serialization.
Apply the same rules to debug, retry, validation, collector-failure and CI outputs.
Sensitive debug capture needs its own resolved purpose/access/expiry and cannot
silently enable payload logging.

The following `u1-observation-experiment-v1` values are proposed safety bounds for a
synthetic isolated run, subject to the infrastructure envelope and preflight. They
are not service-quality targets, public retention policy or permission to handle
existing private data. No collection starts with an unset effective bound.

| Bound | Candidate experiment value | Enforcement / stop behavior |
|---|---|---|
| Optional observation disk, shared total | 64 MiB total: 32 MiB JSONL (four 8 MiB segments), 16 MiB aggregates/traces, 8 MiB incident projection, 8 MiB fallback/rotation scratch | Collector checks total bytes before write and rotation; allocation joins the single shared filesystem ledger. Mandatory owner incidents count against owner storage separately. |
| Ordinary evidence age | At most 24 hours, or declared experiment teardown sooner | Protected expiry job removes only this experiment's optional records; no generic store/backup cleanup. Preserve permitted compact outcome/gap manifests in the separately budgeted verification record. |
| Producer memory/event size | At most 256 events and 1 MiB per producer; at most 4 KiB/event; no more than four enabled producers | Count/byte enforcement before enqueue; global producer buffers ≤4 MiB. Reject unsupported extra producers at composition. No business receipt is placed only in this buffer. |
| Optional event rate | At most 25 events/second per producer and 100/second across the collector, with at most one second of burst; 10 of the global slots reserved for high-priority ordinary evidence | Rate-limit before expensive serialization; coalesce/drop eligible ordinary detail with bounded counters. Priority cannot exceed the total, and mandatory owner records never depend on this allowance. |
| Collector/query memory | 32 MiB observation working-memory ceiling; at most 64 aggregate series, 100 records/page, one query and one flush in progress | Count bounded working sets plus producer buffers against the infrastructure memory lane. Hitting a query bound returns partial/limit disposition; never scan the full log unbounded. |
| Sink retry and wait | 64-event maximum batch, 100 ms attempt wait, at most two retries within a 2-second total deadline | Bounded asynchronous sink work; after deadline drop only eligible optional detail and mark a gap. No foreground transaction waits on sink recovery. |
| Probe cadence/deadline | One bounded probe in progress; every 30 seconds while the experiment is running; 2-second deadline; observation expires after 90 seconds | Evaluate expiry at read time. Resource readings use the tighter supervisor cadence specified by the infrastructure allocation. No continuous model generation probe. |
| Incident refresh and recurrence | At most one projection refresh per 30 seconds per condition; cap the local list at 100/page; overflow summarized with a count | Durable required incident facts follow owner policy; repeated optional notices coalesce. No email, Slack, webhook or paid paging route. |

Before execution, reserve these bytes/working sets inside the physical envelope;
verify filesystem permissions, write/rotation caps and measured shared free-space
floor. For the current candidate, the 64 MiB disk allowance and at most 36 MiB
combined observation working set are part of the shared experiment totals, not
additional allowances: the experiment has at most 512 MiB incremental disk growth,
an 8 GiB host free-space floor and one expensive model call at a time. Final
preflight remeasures and enforces the sibling specification's full allocation.
Directory separation does not stop an unrelated process filling a shared
volume. On lost headroom, stop affected new admission and keep surviving recovery
evidence. Logical reservations cannot guarantee writes after complete media failure.

## MON06 — Readiness expiry, recovery and verification

| Check / scope | What the installed check must inspect | Pass/expiry rule and recovery evidence |
|---|---|---|
| Liveness | Bounded application/supervisor response and collector freshness | A response proves only process response. Probe timeout is failed/unknown. |
| Assembly/capability | Installed owner/operation manifest; supported contract/schema versions; required lifecycle participants; current finite policy and provider evidence; actual binding identities | Missing/conflicting required values fail the affected scope. Later absent U2–U8 contributions are `not_installed`, not certified by U1. |
| Protected state paths | Owner-backed bounded PostgreSQL/store check, compatible schema/owner permissions, dedicated persistent-volume identity, writable reserved probe namespace where permitted, authority-guard participant availability and valid enforcement configuration | Use synthetic probe records with an explicit cleanup/accounting rule; no user request triggers a hidden business write. Conformance/race/persistence evidence must match this installed build/binding. The tmpfs primitive probe or a successful ping is insufficient. |
| Work/result/accounting | Owner relay/claim/reconciliation heartbeat, current eligible model identity, protected artifact access/integrity and durable settlement-obligation path | Reachability establishes only a dependency observation. Useful-output and fault evidence must exist for the current bound model/configuration. No canned response upgrades normal-path readiness. |
| U1 mounted journey | Fresh permitted synthetic browser→application→worker→actual stores run: P1/P2 retrieval/useful understanding, supported translation, durable paper/query saves, authenticated fresh return and A/B isolation | Evidence names environment/build/configuration/contract/fixture/model and start/cutoff. Proposed experiment expiry is 24 hours or any relevant identity/policy change, whichever occurs first; not a public uptime window. |
| Recovery after a fault | Current owner consistency/authority, original job/result/accounting identities, affected-path checks and fresh scoped journey evidence | Clear an incident only after verification. Restart, silence, an empty queue or vanished logs do not establish recovery. |
| Restore readiness | Isolated backup consistency, keys, current revocation/consent/withdrawal/erasure evidence, superseded sessions/claims and reconciled obligations before exposure | Keep dispatch/external effects/public serving off until owner checks pass. Missing current restrictions keep the affected restored scope unavailable. |

Every readiness record carries scope, source, build/contract/policy identity,
measurement time, expiry and protected evidence reference. Compute freshness when
read. Use unavailable for known mandatory failure, degraded for an explicitly
permitted partial mode, unknown for missing evidence, stale for expired evidence
and not_installed for absent contributions. None passes a required contribution.
Keep Korean user states actionable and free of protected operational details.

Verify collector outage/full-allocation/restart, fallback failure, stale probes,
clock regression, redaction canaries, missing registrations/policies, owner A/B
denial, lost acknowledgement, replaced worker, late settlement and isolated restore.
Inspect all enabled sinks and retained owner receipts; independently recompute run
denominators. Measure one maintainer's detection, diagnosis, repair and final useful
recovery using a controlled defect and a meaningful regression. The exact runnable
completion command remains `UNSET` pending its separate human approval.

## Sources and remaining decisions

Inputs: [performance](../nfr-design/performance-design.md),
[security](../nfr-design/security-design.md),
[capacity](../nfr-design/scalability-design.md),
[reliability](../nfr-design/reliability-design.md),
[observability](../nfr-design/observability-design.md),
[logical components](../nfr-design/logical-components.md),
[technology candidates](../nfr-requirements/tech-stack-decisions.md) and
[NFR traceability](../nfr-design/traceability.json). Physical resource, storage,
model and supervision bindings are resolved in the sibling infrastructure
specification; this design adds no separate database/model selection.

ServiceOperations and each data owner must establish actual resource enforcement,
permitted evidence handling, production retention/collection policy, baseline and
human-agreed quality targets before the affected operating scope is enabled.
Public readiness, unattended response, backup fitness and full release parity
cannot be inferred from local observation or document validation.
