# U1 finite capacity and scalability design

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`.
Status: logical patterns selected; physical stack, hosting, finite values and
operating capacity require evidence. No load or exhaustion experiment ran here.

## Scope, ownership and requirement mapping

The [confirmed proposal](nfr-design-questions.md) preserves all capabilities over
eight units, the shared application and all 13 [domain owners](../../../inception/domain-design/components.md#component-summary),
a separately controlled operator executable, $0 free/local resources and one
human maintainer. U1's smaller demonstration does not remove downstream demand.
[Capacity requirements](../nfr-requirements/scalability-requirements.md),
[technology decisions](../nfr-requirements/tech-stack-decisions.md),
[workflows](../functional-design/functional-spec.md) and
[rules](../functional-design/rules.md) govern these mechanisms.

| Requirement | Solution | Accountable owner / designed outcome |
|---|---|---|
| NFR8.1 | SC01 | ServiceOperations and integration owners establish a finite free/local allocation with hard spending prevention. |
| NFR8.2 | SC02 | Each domain enforces versioned finite policies; PaperAssistance and UsageEntitlements coordinate bounded admission and reservations. |
| NFR8.3 | SC03 | ServiceOperations measures workload/growth and permits only evidence-backed free/local scaling. |
| NFR8.4 | SC04 | Persistent owners preserve committed data and accepted obligations through safe exhaustion and bounded recovery. |

Provider selection under NFR8.5 is coordinated in
[logical components](logical-components.md); this document defines the resource
and failure behavior every eligible adapter must support. No technology label
substitutes for a transaction, concurrency or zero-cost guarantee.

## Concrete solutions

### SC01 — Explicit free/local resource allocation

ServiceOperations maintains one versioned allocation manifest with owner-supplied
budgets for foreground reads/writes, model work, content processing, persistent
data, derived data, telemetry and recovery. Record allocated CPU/memory/storage/
network, runtime/model identity, measured residency/peak usage, known provider
quota/reset behavior, configuration revision and observation freshness. Available
workstation resources are remeasured and explicitly allocated before experiments;
the dated inventory is neither a reservation nor a hosting decision.

Enable an external adapter only when its owner has recorded permitted use,
free/local terms, applicable limits and a configuration preventing billable
fallback/overage. Its routing has an allowlisted eligible destination and finite
request/response, concurrency, retry and elapsed budgets. Unknown terms/quota or
credential routing make that affected capability unavailable. A configured local
email sink is labeled demonstration evidence; public registration/delivery and
network/TLS remain separate fitness obligations. No automatic replica purchase,
provider switch, paid endpoint or silent capability removal is an exhaustion path.

Allocation keeps distinct foreground, expensive-work and recovery lanes even if
one process/store serves them. Reserve finite connection/write slots, memory,
storage and dispatch throughput for reconciliation and required foreground reads;
new expensive work cannot borrow that reserve. Sum shared usage rather than
counting the same memory/disk allowance once per owner. Model loading and residency
consume the execution allocation, including replacement overlap and temporary
output. An adapter unable to enforce bounded occupancy stays unselected.

Tradeoff: separate services/brokers could isolate contention, but add operating
surface for one maintainer. Start evaluation with logical lanes and compare
physical layouts using the same workload and failure checks; no process layout is
mandated. Verify effective routing with exhausted/disconnected adapters, real
eligible integration evidence and resource samples. A controlled fake tests refusal
only; it cannot establish actual provider quality, public delivery or $0 fitness.

### SC02 — Versioned policy and atomic bounded admission

Each policy record names owner, revision, units, scope, effective interval,
trusted clock/reset authority, finite value, evidence, enforcement transaction,
typed disposition and recovery path. Load/validate mandatory policy before
exposing the affected capability; missing, stale, invalid or unknown values
produce policy-unresolved/unavailable behavior, never unlimited admission.
Resolve concrete values from safe experiments and applicable policy; numerical
service targets still await baseline and human agreement.

| Bound family | Authoritative enforcement and required dimensions |
|---|---|
| Account entry | AccountAccess: field sizes, proof/session lifetimes, per-owner/global registration/delivery windows, outstanding proofs and retries; existence-neutral response. |
| Query/list | Discovery and each list owner: query/filter complexity, page size, snapshot/cursor lifetime, concurrent requests, bounded scan/work and elapsed deadline. |
| Source/representation | CorpusContent: bytes/sections/assets, parsing/fetch work, attempts/deadlines, staging/rebuild temporary space and publication generation. |
| Assistance | PaperAssistance: input/context/output units, result/metadata bytes, model load/residency, per-operation execution ceiling and options/source/glossary binding. |
| Queues/pools | PaperAssistance and adapter owners: pending-admission and accepted backlog counts/bytes, per-owner/global outstanding work, active claims, waiters, connection/worker limits and queue age. |
| Usage/resets | UsageEntitlements: owner/global units and reservations, trusted period/time zone, reset/carryover, settlement/release/refund rules and late-completion treatment. |
| Retry/recovery | Operation owners: attempt count, backoff, total elapsed budget, lease/renewal/replacement, reconnect/replay and reconciliation windows. |
| Private persistent growth | Library/Personalization/PaperAssistance: per-owner/global records/bytes, acknowledged settings, job/result/receipt retention and permitted deletion; PaperAssistance also owns glossary bounds. |
| Derived data | Owning domains: cache entries/bytes/age, projection generations, rebuild waiters and temporary space; CorpusContent alone publishes corpus projections. |
| Evidence/recovery | ServiceOperations with data owners: log/metric rate/cardinality/bytes, buffer/retention, backup/restore space, repair capacity and access policy. |

Admission uses one immutable operation identity and input digest with an owner
state machine. Its states before acceptance are internal admission states, not
new public job lifecycle states. Coordinate this protocol with the
[canonical amendment plan](../functional-design/contract-revision-plan.md)
before affected code; public errors stay within the agreed contract vocabulary.

1. Authenticate current owner, validate source-purpose/options and finite policy;
   under PaperAssistance authority, reconcile an existing same-key intent first.
   Changed intent conflicts. Same intent recovers the original state even when
   allocation changed; it cannot restart terminal work or allocate twice.
2. PaperAssistance atomically creates a bounded durable admission intent and
   capacity hold, testing owner/global outstanding counts, queue/byte budget and
   persistence allowance together. Uniqueness/CAS prevents concurrent overcommit;
   an approximate telemetry counter cannot grant a hold. Pending intents themselves
   consume finite admission/recovery space.
3. UsageEntitlements atomically checks owner/global allowance and reserves against
   that identity, binding original policy revision and trusted period. Reservation
   creation and both allowance updates form one owner transaction. No browser
   balance or client timestamp authorizes allocation; a reset cannot remap an
   in-flight reservation into free allowance or debit two periods.
4. PaperAssistance records the reservation reference and, only while the held
   admission generation is valid and current authority remains permitted, commits
   immutable acceptance time/input, receipt and durable dispatch obligation in
   one owner transaction. A closed/fenced hold cannot become accepted. Acknowledge
   only after this commit; runtime worker-slot acquisition is a later bounded step.
5. If reserve/accept replies are lost, reconcile the same identities. A hold or
   reservation is not released from timeout/age alone. The authoritative admission
   state must be atomically closed against acceptance, then an idempotent release
   obligation reconciles UsageEntitlements; already accepted work retains its
   original responsibility. An unknown owner outcome remains reserved and visible
   within the finite unresolved-work budget, reducing new admission safely.

These are owner-local atomic boundaries plus durable coordination, not a presumed
distributed transaction. Required store guarantees are unique operation identity,
conditional revision/fence update, durable commit/receipt, consistent allowance
updates and crash-recoverable pending obligations. Owner adapters must prove them
using the selected storage/process topology; in-memory locks across replicas are
insufficient. Shared physical storage does not merge domain ownership.
Protected acceptance/publication serializes its short ordered authorization guard
and owner commit against current AccountAccess/CorpusContent barriers; admission
prechecks or stale caches alone cannot win a revocation race. Model execution
stays outside that guard. Accounting remains its separate owner protocol.

The input ceiling must bound the permitted execution/output/storage demand. If a
runtime cannot predict usage exactly, reserve its finite maximum and settle actual
permitted usage through the resolved accounting policy; never run unreserved
excess or claim truncated output as complete. Prepared-result publication and
durable settlement responsibility use [reliability design](reliability-design.md).
Resource-capacity release follows safe artifact cleanup and owner disposition;
accounting settlement is an independent idempotent owner action.

Policy refresh is atomic/versioned for new admissions. Existing work preserves
accepted input, period and obligations. A tighter policy that affects in-flight
work requires a named owner disposition; it cannot silently rewrite intent or
release unknown work. Concurrency/retry/receipt windows must fit each other, with
enough recovery truth to reject aged-out replays without creating a new effect.

Verification: concurrent owner/global boundary admissions, duplicate intents,
reset races, changed input, stale policy, crash at each numbered boundary, expired
hold versus acceptance race and lost release/settlement acknowledgements. Inspect
all durable states and prove admitted/reserved counts remain bounded and each
intended operation has at most one accepted identity/accounting effect.

### SC03 — Measured workload, fair dispatch and conditional scaling

Dispatch only durably accepted eligible operations. Use bounded owner queues and
a fair round-robin or equivalent bounded-share scheduler over active owners, with
finite per-owner/global active permits. The selected fairness policy is explicit;
one owner cannot occupy all waiting/active capacity by opening more tabs. Active
claim CAS/fences remain PaperAssistance authority, independent of transport or
scheduler. Backlog age uses immutable original acceptance time; retries/replacement
cannot move old work to the back by resetting its age.

Before every experiment, record eligible fixture identities, selected environment,
allocated resources, finite policies, synthetic accounts, workload mix/arrival/
duration, corpus/record sizes, cold/warm state, temporary location and stop/cleanup
conditions. Increase only inside those finite bounds. Abort before headroom is
consumed; simulate resource failures through isolated quotas/adapters instead of
filling the real disk or exhausting the workstation.

| Experiment | Required observation and decision |
|---|---|
| Complete P1/P2 plus translation | [Performance P01–P03](performance-design.md): real useful task outcomes, model-load/warm costs and durable save/fresh revisit. |
| Mixed readers/searches/saves/model work | Foreground wait/latency while execution runs, per-owner fairness, active permits and recovery reserve availability. |
| Admission spike/duplicate burst | Offered/admitted/rejected work, pending intents, retry load and bound enforcement without extra accepted/accounting effects. |
| Corpus and record growth | Query/list plan work, bytes by owner/category, projection/cache/staging cost and stable cursor behavior under permitted record sizes. |
| Outage/restart/backlog drain | Original oldest age, reconciliation throughput, wasted replacement compute, storage/memory peaks and preserved identities. |
| Isolated pressure | Queue/write/model/telemetry fault disposition, committed records, original effects and fresh recovery checks. |

Record offered, admitted, active, completed, failed, rejected and unresolved work
separately, plus duplicate deliveries and execution attempts. Admission is durable
acceptance, not entry into the internal admission-intent phase. Measure completed
useful journeys alongside operations, queue age and foreground latency. Record
CPU pressure, sustained/peak/resident memory, available allocated storage, data/
temporary/log/backup growth and network, with units and sampling interval.
Completed denotes a successful terminal logical operation; failed denotes a
terminal failure. Offered attempts include refused and unfinished arrivals;
report unique intended identities alongside total arrivals so retries cannot
inflate logical throughput. Active and unresolved counts are timestamped states.

Estimate storage from measured category sizes and observed growth plus concurrent
staging/rebuild, result, receipt/recovery, backup/restore and safety allocations.
Retain uncertainty and assumptions. P1/P2 fixtures do not forecast public demand;
model file size does not establish runtime memory or throughput. Rebaseline after
material model/runtime/configuration/data changes and each added unit's demand.

Scaling triggers compare measured queue age, useful completion/latency and resource
headroom against configured safety policies and later human-agreed targets. On a
trigger, stop unsafe new admission and diagnose the constrained resource. Evaluate
bounded indexing/cache/pool/scheduling changes under the same quality/recovery
checks; no silent semantic-search, language or accessibility reduction qualifies.
Additional workers/replicas are conditional on measured free/local fit, distributed
permit enforcement, durable fenced claims and shared authority. No automatic
purchase, unverified provider migration or uncontrolled autoscaling is enabled.

Logical data partitioning remains owner/account and exact source-version keyed.
This enables selective access and bounded lists without selecting shards. A future
physical split requires compatible transaction/backup/lifecycle evidence first.
Web views may be replaceable, but jobs, reservations and acknowledgement truth
cannot live solely in a replica or browser session. Unmet $0/scope/quality fit is
reported with measurements for human resolution, not recast as successful parity.

### SC04 — Safe exhaustion with reserved recovery capacity

Use pressure states normal, constrained, admission-stopped and recovering as
operational interpretation of owner/resource facts, not new public job outcomes.
Each transition uses configured finite thresholds and freshness bounds. Unknown
capacity stops only the affected new admission; retained authorized reads and
reconciliation continue if their dependencies and reserved capacity are available.
Distinct restore thresholds prevent repeated open/close oscillation; values await
measurement, and fresh capability checks are required before reopening admission.

| Pressure/fault | Safe owner action and recovery ordering |
|---|---|
| Queue/model memory exhausted | Refuse before acceptance; retain accepted obligations and visible state. Bound active claims and replacements; no retry storm or browser-generated replacement work. |
| Storage/write/permission failure | Stop new persistence requiring the failed resource before remaining reserve is consumed. An uncommitted save is failed/unknown, never acknowledged; already acknowledged records retain authority. Reconcile uncertain commits through original identities. |
| Output/staging capacity | Keep partial artifacts private and bounded; success requires coherent durable result binding. Owner records an explicit failure/limitation only under supported semantics and settles the original reservation. |
| Dependency/provider exhaustion | Keep truthful pending/unavailable/unknown state and bounded original-operation recovery; never switch to paid processing or assume a remote effect did not occur. |
| Telemetry pressure | Bound/drop permitted diagnostic detail with a visible lost-evidence signal; preserve independent business/receipt records and recovery headroom. Telemetry cannot decide settlement or erase accepted work. |
| Retention/backup pressure | Evict only permitted reconstructible derived data or owner-approved expired material. Protect recovery/tombstone truth and restore consistency; no automatic saved-work deletion, backup disposal or store reset. |

Recovery lane work has its own finite queue, permits, retries and storage budget;
priority does not mean unlimited work. Its tasks reconcile already-owned admission,
dispatch, result and settlement obligations rather than create new user work.
When physical storage fails completely, reserved logical capacity cannot promise
a successful write: remain unavailable/uncertain, preserve surviving evidence,
and use the owner recovery/isolated restore procedure before claiming repair.

On restoration, verify owner-store consistency and authority, reconcile pending
intents/reservations and stale claims, process recoverable original obligations
under current eligibility, then verify foreground reads and reopen bounded new
admission. Terminal jobs never restart automatically; source/account revocation
still fences forbidden effects. Restart durability differs from disaster recovery;
backup coverage, loss/recovery targets and continuity authority remain unresolved.

Verify isolated full-queue, simulated low-space/write failure, model unavailable,
provider limit and recovery-log pressure. Compare acknowledged records, original
identities, reservations and resulting effects before/after repair. No test fills
real disk, resets a store or disposes of existing user material. A restart alone
is insufficient evidence of capacity restoration or preserved work.

## Prerequisites and implementation handoff

| Open binding | Owner / required closure evidence | Consequence until resolved |
|---|---|---|
| Physical stack and topology | Architecture/data owners: transaction/permit/fence tests, observed contention and one-maintainer setup/repair; technology E03/E06 | Do not depend on unproven adapter guarantees. |
| Finite values and operating allocation | ServiceOperations plus each policy owner: dated actual allocation, safe experiment manifest, boundary tests and effective policy revision | Affected operation stays explicitly unavailable; no unlimited default. |
| Quota/retention/recovery policy | UsageEntitlements and data owners: period, settlement, release/refund, receipt lifetime, retention/deletion and backup obligations | No ambiguous accounting or protected-data cleanup. |
| Permissions/public integration | CorpusContent, AccountAccess and integration owners: source/model use, shared-device/location policy, free/local terms and real public-delivery/network evidence | Isolated local success does not enable affected public processing. |
| Canonical coordination | PaperAssistance/UsageEntitlements and browser owners: original acceptance clock, claims/history, glossary ownership, revision bindings and consumer checks | Amend C00/C02/C03/C06/C13/C14 together before affected code; findings remain open. |
| Continuity and targets | Data owners/ServiceOperations: authoritative inventory, isolated recoverable backups, measured useful capacity and human target/continuity decisions | No data reset/migration or release-capacity claim. |

The [performance design](performance-design.md), [reliability design](reliability-design.md)
and [observation design](observability-design.md) supply timing, durable recovery
and safe evidence mechanisms. The exact cumulative completion command remains
separately unapproved. Document checks do not establish operational conformance.
