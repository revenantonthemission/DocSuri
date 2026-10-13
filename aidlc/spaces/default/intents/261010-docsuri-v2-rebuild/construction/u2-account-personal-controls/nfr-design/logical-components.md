# U2 logical components, resource bounds and failure recovery

Date: 2026-10-13. Unit: `u2-account-personal-controls`. Logical design for the embedded library and its browser contribution; no independent U2 deployment or new paid service is selected.

## Sources and architecture boundary

Use the [confirmed summary](nfr-design-questions.md), [security requirements](../nfr-requirements/security-requirements.md), [technology decisions](../nfr-requirements/tech-stack-decisions.md), [functional specification](../functional-design/functional-spec.md), [canonical contracts](../../../inception/contract-design/contract-summary.md), [component catalogue](../../../inception/domain-design/components.md) and [unit catalogue](../../../inception/units-generation/unit-of-work.md). [Security design](security-design.md) owns SD2-01–09, including exact reset-discovery proposals. [Traceability](traceability.json) covers all 39 derived NFRs.

Carry forward the [U1 local infrastructure integration](../../u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md): shared Python/API host, static React/TypeScript workspace and common PostgreSQL transaction facility. This is a local assembly binding, not public hosting or capacity evidence. U7 remains independently controlled. Future units add registered participants through contracts rather than core imports of future implementations.

## LC2-01 — Component inventory and ownership

| Logical component | Owned state / behavior | Boundary, dependency and isolation |
|---|---|---|
| AccountAccess | Accounts, identity links, proofs, scoped sessions, MFA, roles/consent, lifecycle coordination and authority guards | C02; typed authority read/guard to owners, provider/delivery ports, participant manifest from composition. Application authority has no U7 operator grant. |
| Library | Saved paper/search references, history, original clear checkpoints, its receipts and lifecycle tickets | C03; current authority and CorpusContent disposition; trusted Discovery admission checkpoints. No direct writes to corpus or Personalization. |
| Personalization | Explicit defaults/onboarding, permitted activity/projection, input boundaries, reset responsibilities and scope evidence | C03; AccountAccess consent, trusted producer events and permitted ORCID suggestions. Does not own PaperAssistance glossary or research drafts. |
| UsageEntitlements | Assignment revisions, finite balances/periods, reservations/settlement and reconciliation | C03; current admin/owner authority; accepting operation contracts provide durable outcome. Never infer acceptance from logs. |
| WebWorkspace | Transient forms, owner-scoped read projections, selected reset and accessible progress | C13; typed owner clients. No domain store, cross-owner cache or browser-persistent credential material. |
| Shared application composition | Versioned operation registrations, bounded pools, validated policy/participant bindings | C00/C01 and mounted adapters; rejects duplicate ownership or missing required participants. Does not implement domain policy in routing glue. |
| ServiceOperations integration | Safe owner capability observations, bounded diagnostic projections and published recovery invocation | Observes evidence from each owner; neither fabricates acknowledgements nor directly modifies owner rows. |
| Provider/delivery adapters | Google/ORCID protocol exchange and approved email dispatch | AccountAccess ports, finite network budgets, isolated secret handling. Synthetic adapters explicitly labelled. |

Text architecture: browser → shared host → owning module; owning module → typed AccountAccess current-authority guard and its own persistence; AccountAccess → provider/delivery adapters; each owner → its durable responsibility runner; all owners → safe ServiceOperations observations. Cross-owner operations use published contracts and reconciliation. Shared physical storage does not transfer write ownership. This text is the complete diagram fallback; no Mermaid diagram is needed for this bounded inventory.

## LC2-02 — Transaction and asynchronous failure domains

Each module's effect, receipt and local responsibility share one owner transaction. SD2-01 defines guard serialization and lock order. Callbacks, secret delivery and worker completion use the same ownership rules. No remote call is held inside a long database transaction. Prepare durable responsibility first, perform a bounded external attempt, then reconcile evidence in a fresh guarded transaction.

Runners claim a finite batch using owner-issued generations/leases; a replacement must obtain a higher generation, and stale workers are fenced at effect/evidence commit. Retry preserves original acceptance, identity, scope, period and policy. Lease expiry permits new execution authority, not deletion of the responsibility or presumed failure of a remote action. Unknown external results require authoritative inspection or blocked recovery. Reads never create work or claim leases.

| Failure domain | Containment | Remaining blast radius and recovery |
|---|---|---|
| Expensive password work | Dedicated bounded execution pool and admission queue, input bounds before hashing | Shared CPU/memory remains a host risk; reject new expensive work before exceeding reserved budget. Status/recovery routes retain separate capacity. |
| Identity/email provider outage | Per-adapter timeout, finite concurrent calls, bounded retries, circuit state | Affected flow unavailable/unknown; local authorized reads/manual settings continue. No cross-provider identity substitution or paid fallback. |
| Cleanup/reconciliation backlog | Separate bounded owner queues/batches and current-generation claims | Dependent acceptance stops at capacity; accepted responsibilities survive. Readiness identifies owner/scope; inspect remains read-only. |
| Owner control conflict | Short transactions, deterministic lock order, bounded deadlock retry of unchanged identity | Return conflict after safe reconciliation; no automatic latest-revision overwrite. |
| Shared PostgreSQL outage | Bounded connections and waits; fail closed on authority/durability | All store-dependent capabilities affected. Static shell may render unavailable status; no in-memory acknowledged saves. Restart/recover only after authoritative validation. |
| Shared process/host or disk failure | Process supervision, durable records, reserved cleanup/restore space; binding deferred to Infrastructure Design | All local owners can fail together. Pool isolation is not high availability or a multi-host failover promise. Restore in isolation with current restrictions. |
| Optional logs/metrics full | Bounded buffers and safe rotation/drop counters | Diagnosis may degrade; business responsibility cannot be evicted or rolled back with logs. |

Circuit state counts configured transport/provider failures in a bounded window, opens until a finite probe time, then admits bounded probes. Authentication denial is a user/provider outcome, not automatically an infrastructure failure. Values require G1/G2/G7 evidence. Restart cannot cause unbounded retry storms: durable next-attempt/deadline state and current claim fences still apply. Cleanup/settlement that exceeds an automatic retry budget becomes inspectable blocked work, not discarded work.

## LC2-03 — Performance and scalability strategy

Optimize the chosen shared application before adding services. Owner-scoped indexes support session/proof lookup, unique receipt keys, stable library/history pages, reset acceptedAt/ID traversal, participant pending work and original-operation reservations. Exact indexes/query plans belong to implementation evidence. No cross-owner full-table read is justified by later filtering.

Use bounded keyset pages; authenticate owner/view/authority-bound cursors and reject expired cursors with an explicit refresh path. Canonical mutation revisions remain separate from paging tokens. Cache only public immutable assets or immutable public vocabulary by version. Private read projections, authority and cleanup completion are not served from stale shared caches. Optional per-request memoization cannot outlive the authoritative guard/effect.

Separate hash execution, provider calls, database connections, normal request admission and background cleanup/reconciliation into explicitly budgeted pools. A global process ceiling constrains their sum. Reserve capacity for authority checks, read-only recovery and already accepted responsibility; a pool's spare slots do not permit another pool to exceed the global safety envelope. No fixed thread/connection count is invented in this stage.

The chosen local database permits durable coordination across future multiple workers, but horizontal scaling is not assumed. Any later replicas must preserve shared sessions/receipt uniqueness/authority guards/claims, validate callback/session routing and fit the $0 budget. Do not introduce sharding, a broker, Redis, CDN or automatic provisioning absent measured need and approved evidence.

Baseline workload follows upstream V1–V9: cold/warm single actor, conflicting tabs/owners, finite ascending contention, provider delay, queue and storage pressure. Record build/lockfile/policy, fixture cardinality, resource allocation, concurrency and faults; report task success with denominator, UI feedback, queue/local/provider timings, min/median/p95/max with sample counts, resource peaks and rejected/unknown outcomes. Failed attempts remain in evidence. Targets are proposed after measurements for human agreement; correctness/security invariants remain mandatory now.

## LC2-04 — Finite policy and backpressure

Infrastructure Design must bind a versioned policy manifest with owner, units/range, selected environment, source of approval and evidence for each row below. Missing, negative, internally inconsistent or unbounded required values reject affected activation. Synthetic test values are explicitly test-only and cannot silently become public policy.

| Policy family | Required finite bounds | Exhaustion and recovery behavior |
|---|---|---|
| Inputs/vocabularies/pages | Request bytes, password/profile/query strings, list limit, cursor life, result bytes, manifest scope count | Validate before expensive work; reject rather than truncate meaningful input/evidence. |
| Credential and proof work | Hash memory/cost/workers/queue, per-flow/identity/network attempts and windows, proof/enrollment/session expiry | Neutral bounded rejection and recovery; layered limits avoid one shared IP locking every account indefinitely. G1 chooses policy and tests abuse. |
| Pools and networking | Total and per-purpose DB connections, waits/transactions, provider concurrency/connect/read/total deadlines | Safe unavailable/backpressure response; no long transaction across remote exchange. |
| Work and reconciliation | Pending responsibilities, batch/concurrency, lease, deadline, attempts/backoff/jitter, poll budget | Stop new admission while preserving accepted work, durable next step and read-only inspection. Exhaustion becomes blocked with safe reason. |
| Storage, caches and logs | Data/receipt/queue capacity, cache/log buffers, rotation/retention, backup footprint and recovery reserve | Before exhaustion stop unsafe growth; optional diagnostics drop safely; mandatory current restrictions and unresolved work persist. |
| Usage | Trusted quantity, allocation, period, grant/revoke, settlement/refund and accepted-work policy | Unknown policy/balance cannot mean unlimited or zero. Reconcile original period and effect; do not guess refund. |
| Provider free use | Actual eligible account, scope/terms/allowance, no-overage behavior, retry/delivery budget | Capability unavailable at verified limit; no payment or silent provider substitution. |

The reserve must cover the measured worst permitted in-flight commit/receipt plus bounded cleanup, database maintenance and an isolated restore/rollback operation for the selected dataset. If the available disk/memory cannot meet that reserve, reduce the *experiment* dataset/admission within its declared scope or surface an operating-feasibility conflict; never silently reduce retained product capabilities. Current hardware or free space is not an allocation. Physical paths, thresholds and exact reserve calculation are Infrastructure Design evidence.

## LC2-05 — Privacy and recovery integration

SD2-05 supplies stable reset responsibilities and fresh-owner discovery; SD2-06 supplies lifecycle/restore. Their tickets include original request/policy/manifest and current work generation. Each participant owns its live/derived/pending/external/backup scope. Completion is an aggregation of actual evidence, not a timeout or queued-message count. Optional UI refresh can stop without stopping owned cleanup.

Restore must preserve an independently validated current restriction set and compare it to backup contents before serving. Infrastructure Design binds where that set and keys survive a host failure, how backup integrity is tested and who is separately authorized to restore. If current restriction evidence cannot be recovered, keep service unavailable for affected private data; do not bless an older snapshot by timestamp alone. Rollback of code/config cannot roll back authority or replay externally completed actions.

Privacy inventory links each field/category to purpose, consent where required, approved lifetime, backup treatment and responsible module. G3 decisions settle deletion, reactivation and evidence minimization before real use. No arbitrary lifetime, cloud backup or assumption that deleting a live row deletes external/synced copies is made. Keys, proofs and tokens never enter ordinary diagnostics or defect fixtures.

## LC2-06 — Observability, readiness and repairability

The owners expose safe capability observations with observedAt, policy/build identity, state and bounded reason. ServiceOperations distinguishes process liveness, local synthetic capability readiness and real integration/public readiness. A missing policy, authority/key/store, installed participant or provider evidence disables the specific dependent operation. Unknown status must not render as zero backlog, completion or a healthy capability.

Metrics include admitted/rejected/failed/unknown commands by bounded operation kind, latency components, outstanding/blocked responsibility counts and age, stale-claim rejection, reconciliation outcome, pool saturation and optional telemetry drops. Avoid account/paper/query IDs as unbounded metric labels. Authorized diagnostic references link to owner status; public readiness does not expose private IDs, secrets, internal paths or provider details.

Before service targets exist, correctness violations, unavailable required authority/durability and resource safety limits produce actionable stop/degraded observations. SLO alerts await measured baselines and agreed targets. Operator response is inspect owner evidence → preserve unresolved work → repair prerequisite → retry/reconcile via owner contract → verify current readiness. This does not grant app administrators direct database or U7 access.

Fresh setup and a seeded defect exercise must record reproducible commands, safe fixtures, setup/diagnosis/repair/recheck timing, dependency versions and rollback boundaries. Keep one operations path per owner; no undocumented manual row editing. Review dependency/license/security evidence and compatibility before pin/upgrade. Document what evidence cannot be reproduced while provider or real-data gates are open.

## LC2-07 — Browser interaction and capability degradation

WebWorkspace uses current-authority-tagged requests and clears private state on expiry/switch/logout; it rechecks authority before back/forward/focus restoration. Settings, library, usage and reset pages use owner clients with no business authority in the view. Unknown writes retain distinct feedback; fresh sign-in restores a safe view only. Credentials/MFA material never receive a durable-draft promise.

Korean labels, inherited tokens, appearance modes, desktop-first responsive reflow and accessible controls remain the approved design. Preserve query/list/form controls during delay/errors, announce status, retain authorized non-secret edits on conflict, and explain destructive scope. Enrichment failure preserves manual selection/skip; unsupported modes are explicit. V8 must combine browser automation with manual keyboard/screen-reader evidence; no document or screenshot establishes conformance.

## LC2-08 — Contract coordination, verification and delivery

Before affected code, coordinate C02 authority-guard/session/proof/lifecycle details and C03/C13 revision/error/reset types and browser routes. SD2-05 is the exact proposed reset delta; upstream R-01 remains open until canonical and executable closure. Use canonical schema/type validation and actual consumer inventory; all doubles must implement the same accepted protocol. Do not treat an added required result field as automatically compatible.

Validate installed participant versions/scopes at composition and again against the accepted manifest during work. U2 must demonstrate its actual contribution in the same mounted application. Later U3–U6 and U8 must verify expanded manifests and retained capability parity; no placeholder participant can certify future cleanup. U1 limitations remain visible through current readiness.

| Scenario | Design mechanism to test | Evidence / completion boundary |
|---|---|---|
| V1 account/proof journeys | SD2-01–04, dedicated hash/provider pools | Real owner stores and mounted routes; separately labelled synthetic and real delivery evidence. |
| V2 isolation/admin/MFA | SD2-01–03/09 | Revocation at commit, cross-owner reads/errors/cursors, single secret delivery, role removal and no operator grant. |
| V3 library/history | SD2-04/06 | One original receipt/cutoff; old delayed fact suppressed, newer permitted work survives replay/restart. |
| V4 reset recovery | SD2-05, LC2-03/07 | Lost reply/browser state, fresh discovery, two resets/reordered responses, pending/blocked/complete, no writes on inspect. |
| V5 lifecycle/restore | SD2-06, LC2-02/05 | Missing/replaced participants, current revocation, stale backup restrictions and truthful non-completion. |
| V6 accounting | SD2-07 | Concurrent allowance, duplicate/unknown acceptance/settlement, original period and current admin assignment revision. |
| V7 bounded saturation | LC2-02–04/06 | Measured finite pools/queues/pages/disk, reserved recovery capacity and no lost acknowledged responsibility. |
| V8 accessible browser | SD2-09, LC2-07 | Korean desktop/tablet/phone and themes, focus/reflow/contrast, shared-device return and truthful fallback. |
| V9 reproduce and integrate | SD2-08, LC2-06/08 | Fresh isolated setup, seeded repair, exact contracts/consumers/pins and cumulative participant readiness. |

This document does not run these tests or select a new completion command. The approved U1 invocation does not prove U2; present any expanded runnable cumulative verification command at its existing human decision point. G1–G8 evidence gates remain explicit, with numeric service targets after baseline and agreement. Commit completed stage artifacts and merge through a PR into develop under [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md), documenting legacy CI failures and investigating new regressions. Main promotion is separate.
