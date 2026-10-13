# U2 security and cross-cutting quality requirements

Date: 2026-10-13. Unit: `u2-account-personal-controls`. Requirements for an embedded module in the shared application, with browser contributions. This document defines obligations and closure evidence; it does not assert implementation, public readiness, policy approval or measured conformance.

## Scope and sources

The confirmed [proposal](nfr-requirements-questions.md) retains all current capabilities, public registration, the $0 free/local budget and one human maintainer. U2 owns contributions through AccountAccess, Library, Personalization and UsageEntitlements; WebWorkspace owns presentation, not duplicate business records. PaperAssistance retains glossary ownership. Application administration never grants PlatformControl operator authority. All ten [inception NFRs](../../../inception/requirements-analysis/requirements.md) apply, including this library's performance, capacity, reliability and observability contributions.

Normative inputs: [functional specification](../functional-design/functional-spec.md), [rules](../functional-design/rules.md), [frontend specification](../functional-design/frontend-components.md), [canonical contracts](../../../inception/contract-design/contract-summary.md), [domain ownership](../../../inception/domain-design/components.md), [unit catalogue](../../../inception/units-generation/unit-of-work.md) and [unit requirement map](../../../inception/units-generation/unit-of-work-story-map.md). The 62 assigned functional rows remain governed by that functional design; this stage adds derived quality requirements, not a replacement capability inventory. [Technology decisions](tech-stack-decisions.md) define evidence boundaries and measurements. IDs below are unit-scoped derivatives of NFR1–NFR10, not claims that tests passed.

The [functional review's R-01](../functional-design/reviews/review-01.md) remains open for contract/design and executable closure. NFR3.3 and NFR10.2 require a concrete read-only reset progress and restart-discovery solution before affected code. Describing that obligation does not amend C03/C13 or close the finding.

## Assets, trust boundaries and threat model

| Boundary / asset | Adversarial or fault condition | Responsible owner and required defense |
|---|---|---|
| Anonymous browser → account entry | Enumeration, credential stuffing, oversized password, challenge flooding, forged return location | AccountAccess: neutral initiation, bounded validation/attempts/work, protected flow and allowlisted return context. |
| Browser → authenticated operation | Stolen/stale session, CSRF, role or owner substitution, concurrent revocation, stale revision, replay | AccountAccess supplies current authority; each operation owner enforces scope, current policy, replay and exact revision at its effect boundary. |
| Identity provider / delivery adapter → account | Callback injection, issuer/subject confusion, replay, timeout or unknown delivery | AccountAccess: configured provider and flow binding, atomic proof consumption/effect, safe reconciliation and truthful capability readiness. |
| Administrator / MFA → app administration | Factor theft, seed/code exposure, role removal during request, recovery bypass | AccountAccess and UsageEntitlements enforce current role and completed MFA; separate U7 authority; protected secret handling and approved recovery procedure. |
| Domain → another domain / durable work | Forged activity sequence, stale consent, duplicate acceptance, late worker, old cleanup acknowledgement | Authoritative owner contracts, trusted admission checkpoints, current generations, durable responsibility and bounded idempotent reconciliation. |
| Persistence / backup → restored service | Lost acknowledgement, interrupted write, disk exhaustion, old authority resurrected | Owning modules plus separately authorized restore executor: durability, restore verification against current restrictions, no serving while authority is uncertain. |
| Shared browser / telemetry / support | Prior owner's cache flash, private query leakage, tokens in URLs/logs, identifier correlation | WebWorkspace clears private state by authority generation; ServiceOperations exposes only permitted bounded evidence. |

Threat model scope includes synthetic local verification and requirements for eventual public operation. Local operator compromise and a fully compromised host cannot be solved by application ACLs alone; infrastructure must define host/key custody and backup access before affected real data is used. No legal regime or retention period is assumed.

## Derived requirements

Every row is normative. Evidence means executable checks unless the row explicitly requires a policy decision or investigation. The evidence gates below apply in addition to each row.

### NFR1 — complete-task correctness

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR1.1 | AccountAccess must complete registration, sign-in/out, credential/email recovery, provider link/unlink, MFA and eligible lifecycle journeys with the specified scope, neutral initiation and authoritative outcome. Fixture delivery must be labelled synthetic. | Mounted API/browser success, rejection, interruption and fresh-authenticated-return cases for each retained flow; assert stored identity, scopes and actual delivery disposition, not just HTTP status. |
| NFR1.2 | Library and Personalization must preserve explicit saves, history clear, preferences, onboarding and reset semantics. Read/view is not rerun, reset or behavior admission. Source withdrawal preserves saved identity with current permitted disposition. | Two-owner scenarios, stale-tab conflicts, same-key lost-reply recovery, delayed activity and fresh reads; compare authoritative state and side-effect counts. |
| NFR1.3 | UsageEntitlements must enforce finite current policy and one intended reserve/commit/release/refund effect per original operation. Grant/revoke uses current administrator MFA and target assignment revision; mock tiers imply no payment. | Concurrent admissions at the boundary, retries, lost replies, period rollover and conflicting settlement; verify ledger/responsibility invariants and truthful unknown state. |

### NFR2 — responsiveness and smooth use

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR2.1 | WebWorkspace must provide visible, accessible progress for account/form/list/status operations; retain appropriate controls and edits on validation/conflict; prevent repeated unintended commands and sign-in/onboarding loops. | Browser tests for delayed, reordered, failed and interrupted responses; count commands and inspect focus, disabled/submitting state and retained context. |
| NFR2.2 | All four owners must measure latency and throughput under the documented cold/warm and contention workloads before numeric service targets are proposed. Separate local processing, queue delay and remote provider time. | Reproducible samples, success/failure counts, latency distributions, environment/workload identity and raw safe evidence using the measurement procedure in technology decisions. |
| NFR2.3 | Status/list recovery must have bounded pages, bounded polling/backoff and a safe stop state on expiry, unavailable authority or exhausted attempts. Reading pending work must not allocate new work or bypass backpressure. | Large-list and pending-work tests, background-tab/resume and offline cases; bounded requests/resources and no writes attributable solely to inspection. |

### NFR3 — durability and interruption recovery

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR3.1 | Each owner must durably acknowledge its intended mutation and replay responsibility together. Current authority precedes replay; matching replay precedes fresh revision validation. Changed intent under an existing key conflicts. Failed and uncertain outcomes remain distinct. | Fault injection before commit, after commit/before reply, during restart and on stale-client retry; exactly one intended effect with original outcome or explicit unresolved responsibility. |
| NFR3.2 | Library clear and Personalization reset must persist their original boundaries and suppress late activity/projections from prohibited generations. Replay must not advance a cutoff or delete newly eligible activity. | Pause an admitted event, commit clear/reset, release old event; admit a new event, replay old mutation, then restart/read; inspect both boundaries and surviving data. |
| NFR3.3 | Personalization must persist owner-bound reset responsibility, expose evolving cleanup status separately from the immutable acknowledgement, and permit authenticated restart rediscovery without resubmitting reset or relying on a browser-retained receipt ID. | Before code, C03/C13 bind concrete discovery/read schemas and routes; then test lost reply, lost browser state, owner return, pending→blocked→complete, duplicate read and cross-owner denial with no second reset or boundary advance. See reset closure below. |
| NFR3.4 | AccountAccess lifecycle completion must aggregate every required policy/manifest-bound participant acknowledgement. Revocation takes effect independently of pending cleanup; retry and replacement participants cannot silently omit scopes or accept stale evidence. | Missing/failed/stale participant tests, duplicate acknowledgements, interruption and replacement; current revocation blocks effects while completion remains pending/blocked. |
| NFR3.5 | Reactivation and restore must reapply current authority, consent, tombstones and policy to demonstrably retained permissible state. Older backup authority cannot restore erased or prohibited data/access. | Isolated restore with current restrictions newer than the backup, missing restriction evidence, old challenge, interrupted cleanup and owner relationships. No serving uncertain restored state. Measure recovery objectives before agreeing targets. |
| NFR3.6 | UsageEntitlements and operation owners must reconcile original accounting/acceptance responsibility across separate commits. An unknown acceptance/settlement cannot be guessed into a refund, fresh debit or new-period reservation. | Crash each inter-owner boundary; restart reconciler with current evidence and inspect original period and eventual single effect or safely unresolved state. No distributed-atomicity claim from a shared database alone. |

### NFR4 — multi-user security

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR4.1 | Every protected read, list, page, mutation, receipt/status, event and participant effect must enforce current actor, owner, scope and source authority. Browser-supplied roles, owner IDs and private object IDs never confer access. | Positive/negative boundary matrix with anonymous, owner A/B, expired/revoked session, admin without MFA, admin with MFA and operator-only identities; include enumeration and race-at-effect cases. |
| NFR4.2 | AccountAccess must keep preauthentication, primary-auth/MFA continuation, reactivation-status continuation and full sessions distinct. Rotate/invalidate applicable credentials on transitions and enforce configured finite expiry, reauthentication and attempt policies. | Stolen/superseded/expired continuation tests, primary-only MFA bypass attempts, fixation, logout/revocation concurrency and clock-boundary tests; full session only after required factors. |
| NFR4.3 | Credential/challenge material must use established cryptographic libraries, appropriate password hashing, protected keys and purpose/flow/owner/revision/expiry binding. Consume proof and its authorized identity change atomically; never log or return secrets in generic receipts. | Concurrent consume, modified/superseded/expired proof, interrupted commit, secret scans and storage inspection; hash cost/verification capacity measured before enabling. Policy parameters are explicit, versioned and finite. |
| NFR4.4 | Identity adapters must validate configured issuer/subject and callback binding, exact allowed redirect, flow correlation and applicable OAuth/OIDC protections; no linking or account merging from matching email alone. Unique external subjects and unlink survivability are enforced. | Provider-specific conformance/negative vectors, swapped account/session/issuer, callback replay, invalid token claims where applicable and timeout/retry tests. Inspect actual provider protocol; do not assume ORCID returns Google-style ID tokens. |
| NFR4.5 | MFA enrollment requires single protected no-store delivery of seed/recovery material and a confirmed factor before activation. No external QR service, ordinary receipt replay, browser-persistent secret or factor-only full login. Approved recovery is a separate audited procedure. | Inspect response/cache/log/browser storage; repeated/lost delivery invalidates old material through a new enrollment, replay cannot reveal it; test seed/code reuse and recovery denial when policy is unresolved. |
| NFR4.6 | WebWorkspace and the shared host must enforce transport, cookie, origin/CSRF, output encoding, safe return-path and cache protections appropriate to every retained flow. Public delivery requires verified HTTPS and deployed cookie/redirect behavior. | Real browser cross-origin and callback tests, injection inputs, cache/back-forward navigation, cookie attributes and headers. Loopback exceptions remain isolated and cannot be silently reused publicly. |
| NFR4.7 | Current application-admin role and MFA must protect grants/revokes and retained admin operations, including replay and target revisions. PlatformControl operator authority remains separately verified. | Cross-role negative tests, role removal concurrent with commit, invalid target/absent assignment revision and duplicate grant; assert audit and no implicit operator capability. |
| NFR4.8 | Resource limits and error responses must resist denial of service and information leaks without enabling account enumeration. Private reads must not reveal foreign revisions/existence through errors, counts, timing policy or pagination tokens. | Bounded malformed/oversized/over-attempt tests; public initiation comparison, cross-owner error shape and paging tests; rate-limit design considers shared networks and recovery abuse. |

### NFR5 — privacy, consent and permitted processing

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR5.1 | Classify profile/identity, proof/session material, library/query/history, explicit preferences, behavioral projections, accounting, receipts, logs and backup data by purpose, access, storage location and deletion obligations before real-data handling. | Data inventory and decision records; investigate applicable privacy/content obligations and provider terms. Unknown permission blocks affected real-data operation, not silent scope removal. |
| NFR5.2 | AccountAccess consent is authoritative; each consumer must recheck permitted purpose at admission/effect. Acknowledged revocation stops future processing while cleanup is pending; regrant does not revive erased data or old forbidden events. | Revoke while events/derivation are delayed, restart/replay, then regrant; prove no prohibited activity/projection and preserve explicit permitted settings. |
| NFR5.3 | Retention, erasure, reactivation, proof/receipt and backup policies must be explicit, versioned and approved for the relevant data. No inherited 30-day reactivation default. Tombstone/reconciliation retention must not expire before it can enforce outstanding obligations. | Resolve policy and backup inventory; test expiry, hold/pending obligations and restore enforcement. Missing policy yields truthful unavailable/blocked state, not a misleading completed deletion. |
| NFR5.4 | Logout, expiry or account switch must clear private UI/cache state and reject late former-authority responses. Retain only safe return context; no automatic mutation on sign-in return. Account/credential forms make no durable-research-draft promise. | Two accounts on one browser, delayed response, reload/restart/back navigation and multiple tabs; no private flash, credentials persisted or old command replay. U4 owns durable research drafts. |

### NFR6 — usable and accessible controls

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR6.1 | WebWorkspace must preserve Korean labels, inherited blue/neutral tokens, Apple HIG-informed web hierarchy and Light/Dark/System while meeting the proposed WCAG 2.2 AA target across U2 flows. | Implemented keyboard/focus, screen-reader labels/status/errors, contrast, zoom/reflow, target sizing and accessible authentication checks at desktop/tablet/phone sizes; manual evidence supplements automation. |
| NFR6.2 | Destructive changes must explain actual scope, preserved data, current restrictions and pending cleanup; success, saved, unknown, failed, blocked and complete must reflect authoritative state and be announced accessibly. | Usability/behavior checks for withdraw/erase/reset/clear and grant/revoke, error recovery, conflict and confirmation; no color-only distinction or premature completion. |
| NFR6.3 | Provider/enrichment failure must leave authorized manual onboarding, skip, explicit settings and available saved-work controls usable. Unsupported preference modes remain visible and truthful without silent rewrite. | Denied/missing/partial provider data, cold-start/disabled/unavailable projections and unsupported-mode cases, including keyboard navigation and no redirect loop. |

### NFR7 — repairability and reproducibility

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR7.1 | Preserve single domain ownership and typed contracts; extend the mounted application rather than create parallel account/library/settings/usage stores or hidden direct cross-owner writes. | Dependency/contract checks and differential source review of integration wiring, owner transactions and data migrations. |
| NFR7.2 | One maintainer must reproduce setup, failures and repair using pinned dependency/build identities, explicit isolated configuration and synthetic fixtures; recovery instructions include safe stop and rollback conditions. | Fresh setup and seeded representative defect exercise with commands, diagnosis/repair/recheck durations and redacted evidence. Artifact-only validation is not runnable parity. |
| NFR7.3 | Dependency and policy changes must have compatibility, vulnerability/license and resource evidence, deterministic configuration validation and rollback/reconciliation consequences documented before use. | Lockfile/build checks, scoped audits and upgrade regression checks; no assumption that installed packages or successful imports prove suitability. |

### NFR8 — sustainable free/local capacity

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR8.1 | All U2 technology/provider choices must operate within $0 and verified free/local permitted use. Public registration, identity and email delivery remain retained capabilities; local sinks and fake callbacks cannot satisfy their public readiness. | Provider terms/limits and actual account eligibility, delivery/callback checks, local resource workload envelope and zero-overage configuration; surface evidenced conflict to the human without paid fallback. |
| NFR8.2 | Bound inputs/pages/proofs, hash workers, DB pools, queues/participants, attempts/retries/deadlines, caches/logs, storage and reconciliation backlog with recovery headroom. Unknown required limits must not enable unlimited work. | Versioned finite policy manifest, boundary/saturation tests, resource samples and restart/cleanup space checks. Limits distinguish synthetic experiment safety from approved operating policy. |
| NFR8.3 | Usage policy must define trusted quantity, period, allocation, reset and commit/release/refund rules, including policy change and already accepted work. Read-only inspection never allocates and missing/unknown balance is not zero or unlimited. | Concurrent last-allowance, absent assignment, rollover, grant/revoke and outage tests; inspect original operation and period references. |

### NFR9 — safe operational evidence

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR9.1 | Each owner must supply safe original-operation, policy/revision, participant, timestamp and disposition evidence for recovery and diagnosis. Logs must distinguish denied, acknowledged, pending, unknown, failed and complete without secret/private text. | End-to-end correlation and redaction tests including exception paths, provider replies, URL query strings and retry histories; expose only authorized diagnostic views. |
| NFR9.2 | Telemetry must be access-controlled, bounded and removable by its approved retention policy. Mandatory authority, tombstone and unresolved-responsibility evidence is durable business state, not expendable log/cache data. | Log saturation/rotation/storage fault and restore checks; recovery remains possible when optional telemetry is missing. |
| NFR9.3 | Capability readiness must identify safe actionable limitations for missing policy, adapter, current authority, participant or store evidence. Liveness, installed routes and fixture success cannot claim public readiness or complete capability parity. | Disable each prerequisite and inspect capability/UI/readiness responses, operator diagnosis and restored state after repair. |

### NFR10 — compatibility and integration

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR10.1 | Coordinate exact browser/module bindings for authority, revision, idempotency, proofs, lifecycle participants and error/recovery behavior before affected code. Existing consumer usage is evidence required before breaking relied-on behavior. | Canonical contract validation, generated-type compatibility, real mounted browser/API tests and consumer inventory; doubles must conform to the same accepted protocol. |
| NFR10.2 | Resolve the functional review's reset recovery gap in C03/C13 before implementing reset persistence/status. Contract must separate immutable command outcome from current cleanup projection and specify authenticated restart discovery, authorization, retention and compatibility. | Schema/browser binding review plus NFR3.3 scenarios. Merely adding an ID to the old acknowledgement or replaying reset is insufficient. |
| NFR10.3 | Required cleanup/reconciliation participants must be installed and compatible before dependent acceptance; later units/U8 must verify the cumulative application and all retained capabilities. | Missing/incompatible participant admission tests, mounted current participants and later full-manifest integration tests. U1's assistance/semantic-search/figure limitations remain open. |

## Reset progress and restart-discovery closure

Personalization is authoritative for reset responsibility and inputBoundary; AccountAccess authorizes current access; WebWorkspace displays the projection. C03/C13 must define a stable owner-local responsibility identity, original action/boundary, immutable accepted outcome, and separately evolving per-scope cleanup evidence and safe current disposition. Status is derived from authoritative acknowledgements; client IDs, elapsed time or a queued request alone cannot establish completion.

After successful authentication, a bounded owner-authorized discovery operation (or an explicitly defined settings-read extension) must return current/recent retained reset responsibilities, without a mutation key or receipt ID surviving in browser storage. Selection reads current progress. If the acknowledgement was lost, discovery still finds accepted work; if no acceptance exists it must not invent one. Reads never advance settings revision/inputBoundary or emit a reset. Unauthorized discovery/inspection returns no foreign identity/status. Define ordering, paging, availability/error semantics and the distinction between immutable acceptance and changing status in canonical schemas before code.

Outstanding responsibilities remain discoverable until their obligations and permitted retention are resolved. Completed-history expiry must not destroy necessary delayed-event suppression or restore restrictions. Approved deletion policy must reconcile minimization with these obligations; an arbitrary TTL is not a solution. Tests must cover two concurrent resets, reordered status reads and responses from a prior account, so the UI cannot show an older responsibility as the current reset's completion. This section establishes design constraints, not a newly invented operation name or route.

## Finite policy and evidence gates

| Gate (functional prerequisite) | Owner / decision evidence | Affected work that cannot claim readiness without it |
|---|---|---|
| G1 (P1) credential/session/challenge/MFA recovery policy | AccountAccess + human policy decision; threat review and bounded hashing/attempt/expiry evidence | Real registration/recovery/admin activation; synthetic tests use explicit test-only policies. No guessed MFA recovery or bypass. |
| G2 (P2) Google/ORCID and email integration | AccountAccess; protocol/terms/free limits, callback configuration, account eligibility, delivery and failure evidence | Public provider/delivery operation. Local simulation proves handling only. |
| G3 (P3) authority, users/data, retention and restore | AccountAccess + every participant + human continuity/policy decision; authoritative inventory and verified backups | Real-data lifecycle, reactivation, migration and affected storage/deployment. No assumed 30 days. |
| G4 (P4) vocabularies and access matrix | Four owners + WebWorkspace; retained field/mode vocabulary and explicit current access rules | Concrete input schemas, permission coverage and user-facing settings readiness. |
| G5 (P5) participant coverage | AccountAccess and Personalization coordinate owner-bound manifests; current contracts and mounted participant evidence | Lifecycle/reset acceptance and completion for the installed application. Full release coverage awaits every required later participant. |
| G6 (P6) quota/accounting policy | UsageEntitlements + operation owners + human policy decision; finite quantities/periods/refunds and accepted-work treatment | Real allocation and work admission/settlement; no unbounded default or assumed refund. |
| G7 (P7) resources and measured targets | Owners + ServiceOperations; isolated capacity/baseline evidence, proposed targets then human agreement | Operating workload claims, service-quality thresholds, public capacity or readiness. |
| G8 (P8 and R-01) canonical coordination | Architecture/contract owners; concrete C03/C13 and affected shared bindings, compatibility validation and executable closure | Affected account/settings/reset implementation. R-01 remains open until design and runtime evidence close it. |

These gates allow documented synthetic experiments and design work to continue; they do not permit unknown policies to leak into real operation or remove retained capabilities. Where evidence cannot establish feasibility within $0, present the concrete conflict to the sole human approver. Numeric quality targets follow measured baselines; security/correctness invariants and finite operating policies still apply before operation.

## Acceptance and verification boundary

Use the [measurement and verification matrix](tech-stack-decisions.md#measurement-and-verification) to implement checks with current owner stores and real mounted routes. Record test fixtures and policy identities, passing/failing assertions and unresolved rows. Security, authority, durability and accounting invariants are pass/fail; distributions and times are observations until targets are agreed. Every applicable row needs evidence or an explicit unresolved gate, never an assumed pass. The already approved U1 command is not full U2 verification; select any required expanded runnable completion check through its existing human decision point.

Independent document review and ID/link validation assess design consistency only. Full public feasibility, supported provider behavior, data continuity, capacity and all-capability release parity remain unproven here.
