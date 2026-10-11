# U1 logical components and implementation bindings

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`.
This design implements the [confirmed proposal](nfr-design-questions.md). It
selects logical mechanisms and their required guarantees. Physical technology,
hosting, policy values and operating feasibility still require evidence.

## Requirement mapping

| Requirement | Design solution | Evidence that will verify the implementation |
|---|---|---|
| NFR7.3 | LOG01 | Reproduce one pinned assembly, installation, upgrade/rollback and repair using its recorded adapter/configuration identities. |
| NFR8.5 | LOG02 | Verify effective provider routes, permitted/free use, finite resource allocation and exhaustion behavior without paid fallback. |
| NFR10.1 | LOG03 | Canonical types, browser/worker bindings and generated consumers agree; mounted revision, claim, payload, recovery and race checks pass. |
| NFR10.2 | LOG04 | PaperAssistance's first-use empty glossary read and immutable acceptance time survive duplicate admission/replacement/restart; source/options remain bound. |
| NFR10.3 | LOG05 | Required participant/version checks and existing-consumer compatibility evidence pass for U1 and subsequent cumulative assemblies. |
| NFR10.4 | LOG06 | Real P1/P2 and translation/save/revisit checks plus fault/owner cases pass through the separately approved runnable completion command. |

### LOG01 — One explicit assembly with replaceable infrastructure bindings

Use the approved application composition root to install only named, compatible
domain modules and their adapters. Business owners expose typed ports; adapters
translate transport/storage/provider failures into those contracts. A module
cannot access another owner's repository simply because both use one database.
An adapter replacement is acceptable only if its declared transaction, ordering,
durability, authority and failure guarantees satisfy the same conformance suite.

The versioned assembly manifest records module/contract versions, adapter
identities, runtime/lockfile/model digests, permitted fixture revisions, effective
policy revisions, required lifecycle participants and configuration schema.
Secret values are references to protected configuration, never manifest content.
Startup validates this manifest before claiming capability readiness. Missing
required bindings fail the affected capability; optional later modules remain
absent without inventing U1 dependencies on their implementations.

Keep one shared application release and its controlled execution roles. The
operator executable remains separately controlled. Separate logical roles can
be colocated or isolated physically only after resource and threat evidence;
this table does not prescribe twelve new deployed services. Compare native and
container bindings using the same clean setup, restart and recovery exercises.
Record the failed alternatives and manual steps as well as the selected result.

Alternative: keep implicit framework defaults and discover configuration during
incidents. Rejected because reproducing the effective service would then depend
on a maintainer's machine. The manifest introduces upkeep; validate it in the
same installation and cumulative checks that consume it.

### LOG02 — Explicit free/local capability enablement

Each external or local provider binding has a capability evidence record:
owner, endpoint identity, purpose/data classes, source/model terms and provenance,
permitted recipients/location, finite quota/reset and workload policies,
allocated resources, tested failure behavior and verification date. The
composition root combines it with the owner policy; an absent required record
produces an explicit unavailable capability, never an automatic fallback.

The effective provider allowlist contains only evidenced free/local choices.
Disable discovery of unrelated provider credentials or model aliases as a
fallback path. On provider failure, the owner reads/reconciles existing accepted
work and reports its actual state; a new provider or model cannot silently change
the immutable accepted intent. Synthetic sinks/fakes have distinct capability
labels and cannot satisfy a public email or real inference readiness claim.

This design prevents a configured paid fallback, but does not establish that a
provider's terms or runtime behavior are free. Infrastructure selection must
verify those terms and effective routes, then measure the workload envelope.
If full capability and useful outcomes cannot fit $0, present the measured
conflict to the human. Unknown cost is not zero; disabling a capability preserves
an open obligation rather than satisfying release parity.

### LOG03 — One coordinated contract and ordered authority boundary

Publish the amendments in the [contract coordination plan](../functional-design/contract-revision-plan.md)
as one canonical versioned change before affected code. Update C00 strict types,
C02/C03/C06 owner semantics, C13 browser copies and C14 worker messages together.
Keep reads distinct from revision-bearing mutation inputs; do not relax schemas
to accept arbitrary trusted context from browsers. Initial and later consumers
use the same convention and version evidence.

The authority/effect bridge has an additional required adapter guarantee:
AccountAccess account/session/consent barriers and CorpusContent source-purpose
barriers must be ordered against each protected owner effect. Authority owners
alone write those barriers. An owner command invokes their typed guard
participants within a shared serializable unit of work, then commits its own
state/receipt while those decisions are still ordered with revocation. The
guard does not copy account or source ownership into the job module.

For the initial binding, require a common transactional serialization facility
for these guard records and protected commits. Use a stable guard ordering
(account/session/consent, then source/version, then target aggregate); abort and
retry only within the original operation's finite budget on contention. A
revocation/withdrawal changes its owning barrier through the same facility. If
revocation wins, a later effect fails; if the effect wins, future reads still
check current authority. Holding a cached Boolean or a previously issued token
outside this order is insufficient. Guard duration is short and bounded:
network/model calls and expensive parsing occur outside the transaction.

This is a required logical capability, not an assertion that arbitrary separate
databases can commit atomically. Infrastructure candidates lacking the common
facility are ineligible for this initial binding unless an equivalent ordered
protocol is designed and proved. A process-local mutex is insufficient when
another process can change authority. Canonical internal interfaces must specify
the guard context and ordering before implementation; no new browser-controlled
authority field or public API is introduced.

Usage reservation and final settlement remain separate owner operations with
durable reconciliation; this guard requirement does not turn every operation
into a cross-store transaction. The settlement obligation records the committed
outcome and policy binding, and a duplicate cannot create a fresh debit. Resolve
revocation-versus-settlement treatment in the same canonical update and fault
matrix. The [security](security-design.md) and [reliability](reliability-design.md)
designs specify the boundary checks and recovery stages.

Alternative: asynchronously invalidate per-owner authority caches after a
revocation. Rejected as authorization for protected effects because it permits
a stale window. Such invalidation may accelerate cache cleanup but cannot grant
permission. The chosen ordering increases contention and coupling at a narrow
infrastructure boundary; bounded transactions, explicit participants and race
tests make that cost visible.

### LOG04 — PaperAssistance glossary snapshots and original acceptance time

**Ownership correction:** PaperAssistance owns the initial empty glossary,
normalization policy binding, non-null revision and C06 read/snapshot semantics.
Personalization owns assistance defaults. This corrects the owner assignment in
NFR Requirements NFR10.2 in accordance with the approved
[component catalogue](../../../inception/domain-design/components.md) and C06.
The prior [review finding](../nfr-requirements/reviews/review-01.md) remains the
provenance; it is not evidence of an implemented fix.

Select a side-effect-free initial read: when no glossary row exists,
PaperAssistance returns a virtual empty immutable snapshot with an opaque,
owner-scoped initial revision bound to the normalization-policy version. The
owner defines the token format canonically; its value is not a credential or a
nullable wildcard. Repeated reads of the same initial state return the same
revision. A policy change that changes the snapshot has explicit revision
semantics; it cannot silently change an accepted snapshot.

U1 reads this snapshot through C06 before submitting assistance. At acceptance,
PaperAssistance validates the revision and persists the exact normalized empty
terms/policy/revision in immutable accepted input. Later glossary changes cannot
rewrite that input or result binding. U3's first edit compares the supplied
initial revision with the still-absent aggregate and creates the first physical
row atomically; competing first edits cannot both succeed. No read allocates
mutable glossary state and no U1 glossary-editing surface is added. Coordinate
C00 request/result optionality, C06 read behavior, entity representation and
consumer examples before code; test first use and first-write concurrency.

At the durable acceptance commit, PaperAssistance records one original
acceptance timestamp alongside the operation identity and immutable input.
It never updates that value on replay, claim renewal/replacement or settlement.
History exposes it as `createdAt`; stable ordering uses it plus job ID as a
tie-breaker. Attempt timestamps and elapsed monotonic timers are separate.
Queue age uses a comparable owner clock with uncertainty handling; no worker
may supply or reset original acceptance time. The timestamp is acceptance
metadata, not proof of a monotonic wall clock or a substitute for job sequence.

Alternative: create an empty glossary during every first read. Rejected because
it turns recovery into a hidden mutation and adds first-use write uncertainty.
The virtual snapshot needs careful absent-row CAS tests when editing arrives.
Alternative: use the latest attempt time for history. Rejected because replacing
a worker would reorder old work and hide its accumulated wait.

### LOG05 — Compatibility and lifecycle composition

The composition manifest includes installed modules, provided/required contract
versions and lifecycle responsibilities. Before starting, reject conflicting
owners, duplicate operation registration, unsupported versions, missing required
participants and dependency cycles. Every write-owning module joins applicable
account consent/revocation/deletion/restore handling before its first writes.
The initial assembly does not claim readiness for absent U2–U8 capabilities.

Lifecycle coordination sends one idempotent request identity to each installed
owner and tracks their dispositions. A missing or failed participant keeps
completion pending. Immediate serving restrictions precede physical cleanup;
restoration reapplies current restrictions before exposure or job resumption.
Operations invokes owner recovery APIs; it does not repair private records by
writing across repositories. Tests omit, duplicate, fail and reorder participants.

Inventory actual external consumers before removing relied-on behavior.
Required-input changes need coordinated major contract versioning and a recorded
consumer transition; internal schema validation alone is insufficient. Keep
old/new compatibility handling explicit where evidence requires it. Full parity
and all lifecycle participants are verified cumulatively at U8; no silent
deletion of a capability to make U1 startup green.

### LOG06 — Real assembly verification and incremental evidence

Maintain a verification manifest mapping every installed operation and design
solution to its positive, denied and failure/recovery checks. Pin fixtures,
source/model permissions, runtime/policy/contract identities and experiment
resource limits. Execute P1 and P2 useful-output checks, a supported translation,
durable save and fresh authenticated rediscovery with the real browser, server,
worker and stores. Fault injection can simulate a failing dependency but cannot
replace the normal model/retrieval/persistence path with a canned success.

Use the same installed adapters for conformance, fault and mounted checks.
Include current-authority races, absent/foreign resources, stale revisions,
lost responses, claim replacement, result/settlement recovery, first glossary
read, equal-time history pagination and account switching. Capture useful-output
review and actual domain effects, not merely HTTP success or screenshots.

The human still approves the exact runnable completion invocation before the
first unit checkpoint uses it. No invocation is selected here. Later units add
their checks to the cumulative manifest; stable U1 evidence is rerun when their
changes affect its boundaries. A failed or unexecuted required case remains
visible. Document checks establish traceability only, not implementation parity.

## Approved business owners and U1 participation

| Component | U1 responsibility / later boundary |
|---|---|
| AccountAccess | Current account/session/proof and authority/lifecycle guard; U2 completes account controls. |
| CorpusContent | Exact eligible source/version and purpose barrier; sole corpus projection writer/rebuilder/withdrawer; U3 completes corpus variants. |
| Personalization | Explicit assistance/search/appearance defaults and allowed U1 control slices; owns no glossary. |
| Discovery | Bounded source-eligible query and stable result context; supplies server history admission facts. |
| Library | Saved paper/query references and owner history/clear boundaries; no assistance-result ownership. |
| UsageEntitlements | Finite reservations and idempotent accounting settlement; no competing job authority. |
| PaperAssistance | Assistance job, immutable input/result, glossary snapshot, claim/fence, retained history and settlement coordination. |
| ResearchWorkspace | Absent from initial U1 assembly; U4 owns research/novelty/private attachments/durable drafts. |
| TopicsDigests | Later U5 module; no U1 delivery placeholder counted as parity. |
| ApprovedExport | Later U6 module; no implicit external export from analysis completion. |
| PlatformControl | Separate U7 operator executable and authority; no privilege inherited from application admin. |
| ServiceOperations | Scoped readiness/evidence and owner-invoked recovery; U8 completes operations/integration. |
| WebWorkspace | Korean integrated presentation, explicit commands, read-only recovery and current-session rendering; no durable domain authority. |

## Logical infrastructure inventory and failure domains

These are capabilities inside the approved assembly, not additional business
components. Their physical grouping is an Infrastructure Design decision.

| ID / capability | Bound owners and isolation | Failure impact and recovery dependency |
|---|---|---|
| INF01 composition and browser adapter | WebWorkspace/host routes validated requests to registered owners; internal worker methods never become generic browser routes. | Invalid binding blocks affected startup/readiness. Restore compatible manifest before serving; no fallback to a different owner. |
| INF02 owner repositories | Each domain controls its aggregates, atomic receipts and indexes; separate access ports even when one transactional store is shared. | Store failure affects all colocated owners; admission refuses where durability cannot be obtained. Recover from validated owner records/restore, not cache truth. |
| INF03 authority serialization | AccountAccess/CorpusContent guard participants plus protected target commit as LOG03. | Unavailable or unresolved guard denies affected private/effect paths; no stale grant. Bounded transactions protect resources; restoration reconciles barrier freshness first. |
| INF04 accepted-work relay | PaperAssistance durable dispatch records; relay carries identities only. | Lost/duplicate delivery recovers from owner records and fences. A broker outage cannot erase accepted work or create a second business job. |
| INF05 bounded executor | Trusted executor identity, owner claim/payload protocol and finite model/processing pool. | Slow/crashed workers consume only configured allocations; replacement uses newer fence. Foreground pools remain separately budgeted, with shared-memory/CPU contention still measured. |
| INF06 protected artifact store | CorpusContent source artifacts and PaperAssistance staged/prepared results under separate owner namespaces and permissions. | Partial/corrupt/missing bytes cannot become visible success. Validate identity/hash, preserve recovery metadata and restore metadata/content consistently. |
| INF07 derived search/cache | CorpusContent publishes projection generations; Discovery reads queries; other owners cache only their permitted derived views. | Stale/missing projections degrade truthfully; current eligibility wins. Rebuild uses finite temporary space and owner-authorized source; cache loss cannot remove committed work. |
| INF08 provider adapters | Each owner binds only evidenced endpoints/models/email and finite policy. | Timeouts/circuit state affect named capability. Preserve reading/saves where independent; no paid or unapproved recipient fallback. |
| INF09 observation collector | Bounded safe events/metrics with restricted operational storage; optional telemetry separated from mandatory domain receipts. | Sink loss produces stale/unknown and bounded drops; cannot erase recovery obligations or exhaust reserved business capacity. |
| INF10 lifecycle/restore coordination | AccountAccess lifecycle participant registry; ServiceOperations recovery records and owner invocations. | Partial completion stays pending. Restore remains isolated until identities, relationships, restrictions and queued effects reconcile. |
| INF11 operator boundary | PlatformControl executable has independent credentials, approvals and protocol receipts. | Application failure does not grant operator privilege. U1 records absence; U7 proves its independent controls. |

Shared resources include transactional store locks/connections, storage bytes and
backup workspace, CPU/memory used by both foreground and inference, and network
capacity. A logical pool alone does not reserve physical CPU or memory; measured
process/resource enforcement must show the promised isolation. Separate storage
directories alone do not protect against a full shared volume. SC policies and
INF02/INF06/INF09 allocations must account for the shared failure domain.

## Infrastructure selection handoff and unresolved evidence

| Required binding decision | Owner / prerequisite evidence | Consequence before evidence |
|---|---|---|
| Transaction/guard/claim storage | Architecture and data owners prove CAS, uniqueness, authority ordering, owner-time expiry and crash/restore semantics for the actual process topology. | No affected stateful execution or claim of protected commits. |
| Model/search/runtime fit | Assistance/Corpus/Discovery with Operations measure eligible P1/P2 workloads, useful output, translation, relevance, cold/warm resource demand and bounded mixed load. | Candidate remains unselected; no parity claim from model cache presence. |
| Public integration/security | AccountAccess/provider owners verify free email/network/TLS, endpoint authority, secrets, transport and current terms. | Synthetic/local readiness only; no public-service fitness claim. |
| Privacy, retention and continuity | Data owners establish permissions, per-class lifecycle, shared-device recovery, authoritative users/backups and isolated restoration; human chooses continuity after evidence. | No permissive sensitive persistence or migration/reset default. |
| Finite policy and numeric targets | Owners set evidenced finite safety values before experiment/enablement; human agrees service targets after baseline. | Missing policy blocks affected operation; unknown service target remains explicit. |

## Sources

- [Confirmed design proposal](nfr-design-questions.md), [NFR traceability](../nfr-requirements/traceability.json) and [technology requirements](../nfr-requirements/tech-stack-decisions.md).
- [Functional specification](../functional-design/functional-spec.md), [rules](../functional-design/rules.md), [entity model](../functional-design/entities.md), [coordination plan](../functional-design/contract-revision-plan.md).
- [Approved domain owners](../../../inception/domain-design/components.md), [canonical contracts](../../../inception/contract-design/contract-summary.md), [unit catalogue](../../../inception/units-generation/unit-of-work.md).
- [Performance](performance-design.md), [security](security-design.md), [scalability](scalability-design.md), [reliability](reliability-design.md) and [observability](observability-design.md) patterns define the detailed category mechanisms and checks.

## Assumptions & Open Questions

No application, infrastructure or model has been selected or executed by this
document. Canonical amendments, actual adapter conformance, permission/retention,
finite limits, public capacity, continuity and numerical service targets remain
required evidence. The designs do not reopen full scope or $0, and do not claim
an unresolved operating condition is met. The owner correction and initial
snapshot/time design become executable closure only after coordinated types and
mounted tests prove them.
