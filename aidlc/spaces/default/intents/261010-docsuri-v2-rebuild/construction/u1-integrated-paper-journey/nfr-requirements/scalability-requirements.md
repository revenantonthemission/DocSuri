# U1 capacity and scalability requirements

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`.
Status: finite-resource and capacity-evidence requirements; hosting, workload
capacity and stack selection remain open.

## Scope and authority

The [confirmed proposal](nfr-requirements-questions.md) and inception NFR8 require
the complete retained service to use only free or local resources within a $0
budget. This document specifies U1's account, corpus/search, saved-work,
assistance, usage and service-observation contributions. Future units must add
their actual resource and integration demand before full-release acceptance.
Local success alone cannot prove public registration/email or sustainable public
service operation. No growth forecast, concurrent-user count or hosting choice
has been approved.

## Detailed requirements

| ID | Accountable owner and scope | Observable obligation | Verification and source mapping | Status / prerequisite |
| --- | --- | --- | --- | --- |
| NFR8.1 | ServiceOperations coordinates evidence; each domain/provider owner accounts for its resources and external dependencies. All U1 normal and failure paths. | Fit permitted, useful full U1 behavior within an evidenced free/local envelope, with no paid fallback, billable overage or automatic purchase. Record model/search/storage/network/email/runtime needs and the real cost-control configuration. Unavailable capacity or an unverified free integration remains explicit; retain the full release scope and escalate evidenced conflicts. | Measure P1/P2 and failure workload resource/cost demand, inspect actual adapters/configuration, validate current applicable provider terms where used, and test denied/exhausted external calls. Distinguish local fixtures/sink from public delivery. BR5.1, BR5.4, BR7.2/BR7.4; WF1–WF7; LC10/LC12/LC14 and FUI-10. | Binding $0 constraint; operating fit unproven. Processing rights, selected runtime/hosting, public network/email and integration terms/capacity require evidence before affected enablement. |
| NFR8.2 | Owning domains in the finite-policy inventory; ServiceOperations verifies effective configuration. Every admitted input, persisted growth source and recovery loop. | Require versioned finite limits, units, scope, accounting boundary, trusted timing and typed rejection/recovery behavior before enabling each affected operation. Unknown, invalid, missing or stale mandatory policy cannot mean unlimited admission. Enforce current policy server-side and coherently across concurrent requests, retries and reset windows. | Boundary and concurrent tests at permitted maximum, just over it, malformed/missing configuration, duplicate intended identity and period transition; inspect effective configuration and reservation state. BR1.1/BR1.3, BR3.1, BR5.2–BR5.4, BR7.4; WF1–WF5/WF7; LC01/LC02/LC05/LC10. | Inventory required now; numeric values evidence-blocked until measured/policy-approved. Finite experiment safety bounds are required even before service quality targets are selected. |
| NFR8.3 | ServiceOperations owns envelope evidence; WebWorkspace/Discovery/PaperAssistance/CorpusContent and storage owners supply workload observations. Normal mixed load, spikes and sustained growth. | Define a reproducible workload envelope covering simultaneous readers/searches/saves and model work, source/corpus sizes and accumulated records. Measure throughput, wait time, useful task completion, resource headroom and saturation behavior. Base scaling triggers and concurrency targets on that evidence; proposed growth scenarios are experiments, not demand forecasts. | Execute the bounded load/growth matrix below and the performance protocol with resource samples, raw results and outcome classes; repeat after material runtime/model/data/configuration changes. BR3.2–BR3.3, BR5.4, BR7.2–BR7.4; WF2–WF7; LC10/LC14. | Measurement design only. Capacity and numeric scaling triggers unset; human quality targets follow baseline. New replicas, hardware or providers require demonstrated $0 fit and unchanged ownership/recovery semantics. |
| NFR8.4 | Every persistent owner protects its committed data; PaperAssistance/UsageEntitlements reconcile accepted work; ServiceOperations coordinates exhaustion recovery. Queue, storage, memory, dependency and telemetry pressure. | Reject new work truthfully before unsafe overcommit, preserve acknowledged saves/accepted obligations and recover their original effects within finite policy. Report pending/unknown/unavailable explicitly. Retention/cleanup cannot silently discard protected work, recreate withdrawn data or claim success. Capacity restoration never blindly replays user mutations or restarts terminal jobs. | Inject bounded queue exhaustion, disk-full/write/permission failure, memory/model unavailability, provider limits and recovery-log pressure in isolation. Inspect retained records, claims/reservations, duplicate/loss counts and post-restoration behavior; verify no automatic billing or data deletion. BR4.1–BR4.3, BR5.2–BR5.10, BR7.2–BR7.4; WF4–WF7; LC05–LC10/LC12–LC14. | Binding; fault tests and restore evidence pending. Approved retention/cleanup, reserved recovery capacity, thresholds and owner procedures are prerequisites before affected persistence/admission is enabled. |

## Finite policy inventory

Each row requires a configured finite value before its affected operation is
enabled. The owner records policy revision, units, per-account/global scope,
measurement/permission evidence, effective time, atomic enforcement point,
boundary behavior, current-value visibility and recovery procedure. Values are
unselected here. A disabled operation must explain its unavailable disposition;
it cannot be counted as successful parity.

| Policy area | Authoritative owner | Required finite dimensions and evidence | Exhaustion / recovery behavior |
| --- | --- | --- | --- |
| Registration/session/proofs | AccountAccess | Request/credential field sizes, registration and proof-delivery admission/rate windows, outstanding challenges, proof/session lifetimes, retry bounds; abuse and free-email fit evidence | Existence-neutral bounded error/delivery state; no verification or paid-provider fallback inferred from delivery attempt. |
| Search and page windows | Discovery; CorpusContent for published data | Query/filter length and complexity, page/window bounds, cursor/snapshot lifetime, concurrent requests, request deadlines and retries; realistic corpus/relevance evidence | Reject unsupported/oversize queries; expose unavailable/degraded mode; changed/expired snapshot requires explicit restart, not mixed pages. |
| Content and assets | CorpusContent | Source/representation bytes, section/asset counts and sizes, processing complexity, fetch timeouts/retries, staged publication and projection space; eligibility/provenance evidence | Bounded local error/unsupported disposition; no silently truncated content represented as complete or unrelated source substitution. |
| Assistance inputs/outputs | PaperAssistance | Input/context/output units appropriate to selected runtime, per-operation work ceiling, source/option/glossary binding, result shape/size, model-load/residency budget; useful-output evidence | Explicit rejection/limitation/failure; context reduction, if supported, must disclose coverage and preserve source semantics. No fabricated success. |
| Queue and active execution | PaperAssistance; UsageEntitlements for reservations | Per-owner/global outstanding operations and active claims, queue depth/age, dispatch retries, active model work and admission reservations; simultaneous-load evidence | Admission refuses before unsafe capacity is accepted. Already accepted obligations remain recoverable and visible; policy exhaustion becomes an owner-recorded outcome with settlement reconciliation. |
| Deadline, lease and reconnect | Each operation owner; PaperAssistance for worker claims; WebWorkspace consumes declared recovery policy | Request/operation/attempt deadlines, lease duration/renewal/replacement, finite retry attempts/backoff/total elapsed budget, progress replay/poll/reconnect bounds; restart and dependency-outage evidence | Preserve original acceptance identity/time; old fences cannot publish; unknown outcome is reconciled rather than assumed absent. Closing UI is not cancellation. |
| Quota and reset | UsageEntitlements | Meter unit, per-account/global allocation, reservation maximum, trusted reset boundary/time zone, carryover and settlement/release/refund rules, late completion disposition | Concurrent reservations remain bounded and tied to original period/operation; unknown is not zero or unlimited; no double debit or reset-race bypass. |
| Library/history/settings | Library and Personalization | Stored field sizes, per-owner/global record growth, list page sizes, cursor windows, receipt/history eligibility retention and approved deletion/clear semantics | Refuse new persistence truthfully when required; preserve acknowledged work and revision fences; no automatic removal of saved work to make space. |
| Jobs, results and recovery receipts | PaperAssistance; UsageEntitlements for accounting records | Metadata/payload/result bytes, retained-result/history/receipt windows, stable page bounds, staged output cleanup, recovery backlog storage; permitted retention and restart evidence | Recovery metadata must survive the longest allowed retry/replay/reconciliation window or provide a contractually explicit non-replayable disposition; no new effect from an aged-out duplicate. Expiry of readable results does not erase accepted-job truth. |
| Caches and projections | Owning data domain; CorpusContent alone publishes corpus projections | Entry/byte/age limits, invalidation and publication generations, rebuild temporary space, eligibility withdrawal handling | Evict only policy-permitted derived data; misses degrade truthfully, cannot republish withdrawn content or erase authoritative records. |
| Telemetry and backups | ServiceOperations coordinates; each domain retains data authority | Log/metric cardinality, byte/rate/retention/access bounds, buffers under outage, backup/restore working space and retention; privacy and isolated-restore evidence | Bounded instrumentation cannot consume recovery headroom or hide business failure. Do not delete authoritative data/backups automatically to rescue a test. |

Cross-policy consistency is required: input admission fits executable model work;
reserved persistence covers accepted payload/result and recovery metadata;
retry/lease/receipt retention and quota settlement windows are mutually compatible;
owner/global limits cannot be bypassed with multiple tabs/accounts or duplicate
delivery. Refresh policy safely between operations; a policy change must not
silently rewrite immutable accepted intent or invalidate responsibility for it.
Any transition affecting in-flight work needs an explicit owner disposition.

## Workload envelope, load projections and scaling triggers

Begin with an explicitly bounded experiment manifest: selected environment,
permitted fixtures/corpus size and bytes, runtime/model versions, actual allocated
CPU/memory/storage/network, safety stop conditions, effective finite policy,
synthetic account count, operation mix, arrival rate, duration and cold/warm state.
The first envelope is a measurement plan, not a claim of supported user capacity.

| Scenario | Measurements and purpose |
| --- | --- |
| Single complete P1/P2 journey | Establish useful-output and persistence correctness plus per-operation and full-task resource/time baselines. Record model load separately from warm work. |
| Mixed foreground/background use | Vary bounded simultaneous reading, search, save/revisit and assistance within the declared experiment limit. Measure interactive latency while model work runs, accepted/completed/rejected throughput, queue age and CPU/memory/storage pressure. |
| Admission spike and duplicate delivery | Increase arrival within safe bounds to each configured owner/global boundary; include concurrent reservations and same-key retry bursts. Prove backpressure, finite retries and no extra logical work/accounting effects. |
| Record/corpus growth | Vary documented permitted corpus/representation size, saved/history/job/result count and payload lengths. Measure query/list/revisit cost, bytes per category, projection/cache/temporary growth and retention cleanup behavior. |
| Dependency outage and restart | Hold a required dependency unavailable within approved fault bounds, then restore. Measure accumulated obligations, drain rate, worst queue age, memory/storage peak and recovery; require preserved identities and truthful foreground feedback. |
| Resource boundary | Use isolated quota/fault mechanisms to simulate low disk, exhausted queues, write failure, model unavailability and telemetry outage without filling or damaging the real workstation. Verify safe refusal and successful recovery checks. |

Report offered, admitted, active, completed, failed and rejected work separately;
report task usefulness alongside throughput. Queue length alone cannot establish
capacity: track age from original immutable acceptance, not latest retry. Record
peak and sustained memory, CPU pressure, model-resident memory, available storage,
data/log/temp growth and network use with units and observation intervals.
Estimate storage demand as measured category bytes and observed growth plus
temporary publication/rebuild, recovery, backup/restore and safety headroom; retain
the assumptions and uncertainty. Do not infer projected user demand from two paper
fixtures or cached model file size.

After baseline, propose a tested operating envelope and finite safety thresholds
with evidence. A scaling trigger is reached when the selected workload can no
longer meet agreed task/latency requirements or configured resource headroom;
the actual thresholds remain unselected. Investigate bottlenecks and verify
free/local remedies under the same useful-output/recovery checks. If available
resources cannot meet the retained scope, show the measured conflict to the human.
Additional replicas, workers or machines cannot bypass the single logical
authority, fencing, reservation, permitted-use or $0 requirements.

## Local observations and unresolved fit

The confirmed proposal records a read-only 2026-10-11 sample: Apple M4 Pro,
14 reported physical/logical CPUs, 24 GiB memory, approximately 13.2 GiB available
on the current data volume at 97% used. This is neither a reserved resource pool
nor a public-host selection; filesystem availability is time-sensitive. Recheck
before any experiment and use explicit isolation/safety bounds. Do not download
or execute a model merely because it is listed in local tooling.

Cached `qwen3:8b` and `bge-m3:latest` entries are not licensing, context-window,
translation-quality or sustainable-capacity evidence. The recorded cloud entry
does not authorize remote processing or a paid fallback. Candidate comparison and
selection evidence belong in [technology decisions](tech-stack-decisions.md).

## Prerequisites and acceptance evidence

ServiceOperations and each owner must provide the bounded workload/configuration
manifest, resource samples, raw outcome/timing data, finite-policy boundary tests,
exhaustion/recovery results and required integration terms/permission evidence.
The human agrees numeric quality targets after baseline and decides any evidenced
scope/resource conflict. Required operational bounds must be in place before the
experiment or service operation that needs them; deferred quality targets do not
remove that condition.

Authority/backup/continuity, source/model use, retention/shared-device treatment,
public delivery and finite limit values remain open prerequisites. Failed or
blocked evidence is recorded explicitly. The performance protocol is in
[performance requirements](performance-requirements.md); durability and safe
instrumentation are in [reliability](reliability-requirements.md) and
[observability](observability-requirements.md). This document does not select the
separately approved cumulative verification command or claim release capacity.

## Sources

- [Confirmed NFR proposal and bounded local observations](nfr-requirements-questions.md).
- [Inception requirements](../../../inception/requirements-analysis/requirements.md),
  NFR8, all-NFR measurement policy, P1/P2 and IB-04/IB-05.
- [Functional specification](../functional-design/functional-spec.md),
  WF1–WF7, LC10/LC14 and E1–E7 prerequisites.
- [Business rules](../functional-design/rules.md),
  BR1.1/BR1.3, BR3.1, BR5.2–BR5.10 and BR7.2–BR7.5.
- [Frontend specification](../functional-design/frontend-components.md),
  declared limit/usage/recovery states and FUI-10/FUI-13.
