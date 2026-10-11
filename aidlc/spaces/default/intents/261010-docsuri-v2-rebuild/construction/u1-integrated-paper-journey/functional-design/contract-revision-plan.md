# U1 contract revision coordination plan

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`.

## Status and boundary

This is the intended amendment plan for accepted **Contract R-01** (browser
revision preconditions) and **Contract R-03** (execution claims and payload
retrieval). The [confirmed U1 summary](functional-design-questions.md) and
[delivery plan](../../../inception/delivery-planning/bolt-plan.md) assign their
first resolution to U1. The approved [contract baseline](../../../inception/contract-design/contract-summary.md)
still contains the gaps identified in its [review](../../../inception/contract-design/reviews/review-01.md).
This document does not change that baseline, publish a second usable wire
contract, or claim that either finding is closed.

**Before affected implementation**, amend the canonical C00 definitions,
operation semantics and C13/C14 bindings together, update the contract validator
and examples, and record affected producer/consumer compatibility. U1 code may
not use this prose in place of that coordinated formal revision. Re-run the
schema checks and then demonstrate the executable closure checks below. All
later consumers must adopt the same conventions before their own implementation;
U8 repeats cumulative integration checks. Contract R-02's draft allocation and
restart rediscovery remain U4 work before draft persistence.

The inventory below was derived from the baseline's complete named operation
registries and canonical request shapes, including their C13 bindings. It
describes proposed contracts, not evidence of deployed callers or runtime
behavior. Legacy consumer discovery remains a separate prerequisite before
removing or breaking any existing interface.

## R-01: browser revision convention

For operations requiring optimistic concurrency, the browser sends a required
top-level `expectedRevision` in the operation-specific body. The trusted HTTP
adapter validates it and maps it to the owning command's revision precondition.
Identity, roles, policy authority and session context remain server-derived.
Where a canonical input already has a domain-specific revision field, retain its
meaning and define a single mapping; do not add two independent preconditions
that can disagree without an explicit rule.

1. Reject absent, empty, malformed or unsupported revision values as invalid
   input. Never substitute the current server revision. `null` means
   **must not already exist** only for an explicitly supported create/upsert
   branch; it never means unconditional overwrite or use the latest value.
2. Authenticate and validate the current resource/operation authority before
   exposing a resource or replay result. Validate the normalized intent,
   including its original target and precondition, against the owner-scoped
   idempotency record. A changed intent under the same key conflicts.
3. An authorized same-key, same-intent replay returns the original safe recorded
   outcome before attempting a new compare-and-swap. A revision advanced by
   that original commit must not turn a lost-response retry into a fresh write
   or a false stale-client failure. This does not exempt a replay from current
   read permission, revocation, expiry or secret-response restrictions.
4. For a new intended mutation, compare the expected revision atomically with
   the authoritative revision and commit the write and receipt together, or
   prove an equivalent recoverable protocol. An unmatched revision conflicts
   without overwriting committed values. Two concurrent requests from one
   revision may produce at most one such write.
5. Retain unsaved local edits for comparison while offering a fresh authorized
   read. An intentional retry against newly reviewed state uses a new logical
   identity and the newly read revision; no silent last-write-wins resubmission.

The baseline's common rule 4 currently promises the authorized latest revision
with a conflict, but C00 `Error.details` permits only `fieldNames`. Coordinate
that wording with the chosen **fresh authorized read** behavior: generic error
responses contain the existing safe error shape, and the named read supplies
the current resource and revision. Do not invent `latestRevision` in an error
body. Typed domain conflicts that already explicitly contain a revision keep
their declared schema and authority checks.

### Missing body bindings to repair

All paths below are POST under `/api/v2/`. The first five rows explicitly name
an expected revision in their operation semantics. The remaining five follow
C03's invariant requiring it when a command modifies an existing revision.
Existing-state revisions are non-null. A creation branch is permitted only
where its owner explicitly specifies one during canonical coordination.

| Operation | Path suffix | Current C00 HTTP body | Revision target and read coordination | Earliest affected delivery |
|---|---|---|---|---|
| C02 `access.unlinkIdentity` | `c02/access-unlink-identity` | `AccessUnlinkIdentityInputHttp` | Selected identity-link revision from authorized `access.listIdentityLinks`; unlink policy still prevents lockout. | U2 |
| C02 `access.updateProfile` | `c02/access-update-profile` | `AccessProfileUpdateInputHttp` | `AccessProfile.revision` from `access.readProfile`; `fieldVocabularyRevision` remains a separate vocabulary check. | U2 |
| C03 `library.removeSavedPaper` | `c03/library-remove-saved-paper` | `LibrarySavedPaperInputHttp` | Saved reference revision from `library.readSavedPaper` or its owner list. | U1 when the removal path is implemented |
| C03 `settings.update` | `c03/settings-update` | `SettingsUpdateInputHttp` | `SettingsSnapshot.revision` from `settings.read`; defaults and appearance share the owner's conflict rule. | U1's implemented settings slice; U2 completes controls |
| C03 `usage.grantEntitlement` | `c03/usage-grant-entitlement` | `UsageGrantInputHttp` | Target account's authoritative assignment revision. Specify an administrator-authorized current-assignment read and initial-assignment disposition; self-only `usage.readPlan` is not another account's admin lookup. | U2 |
| C03 `library.removeSavedSearch` | `c03/library-remove-saved-search` | `LibrarySavedSearchInputHttp` | Saved search revision from `library.readSavedSearch` or its owner list. | U1 if implemented, otherwise U2 |
| C03 `library.clearHistory` | `c03/library-clear-history` | `LibraryClearHistoryInputHttp` | Library's current history-clear boundary revision, exposed as proposed `LibraryHistoryPage.clearBoundary`; a page snapshot is a separate value. Discovery still captures the actual admission cutoff on the server. | U1's bounded history-clear slice; U2 completes parity |
| C03 `settings.updateOnboarding` | `c03/settings-update-onboarding` | `SettingsOnboardingInputHttp` | `SettingsSnapshot.revision` from `settings.read`; skip/complete cannot silently replace newer preferences. | U1 for any persisted entry/skip slice; U2 completes variants |
| C03 `settings.reset` | `c03/settings-reset` | `SettingsResetInputHttp` | The same Personalization control revision returned as `SettingsSnapshot.revision` by `settings.read`; reset atomically advances it and the separate input-generation boundary. | U2 |
| C03 `usage.revokeEntitlement` | `c03/usage-revoke-entitlement` | `UsageRevokeInputHttp` | Exact selected `UsageEntitlement.revision`; use the same administrator-authorized read coordinated for assignment. | U2 |

`LibrarySavedPaperInput` and `LibrarySavedSearchInput` are shared by reads and
removals. Split each mutation input and HTTP body into a distinct named type;
adding required fields to the shared read input would incorrectly require a
revision just to read it. Update C03 operation signatures, C00 strict bodies,
C13 request references and its embedded schema copies together. Do not weaken
`additionalProperties: false` to accept arbitrary context.

`library.savePaper` and `library.saveSearch` create or reconcile the same intended
saved reference. They must not secretly update a different acknowledged record.
Keep create/reconcile semantics explicit; if the owner later adds an update
branch for label or contents, it needs the same revision convention before that
branch is implemented. No new editing capability is introduced here.

### Concrete collection and settings read preconditions

For history clear, extend C00 `LibraryHistoryPage` and its C13 copy with required
`clearBoundary: Revision`. `library.listHistory` obtains it from the current
owner's authoritative clear boundary even for an empty list. This token selects
the boundary to compare, not the individual records to erase. It is distinct
from `page.snapshotRevision` and from Discovery's admission sequence/checkpoint.
`library.clearHistory.expectedRevision` compares that token, then the server
captures the Discovery admission checkpoint and commits the new clear boundary
and durable receipt under the same owner-controlled protocol. A race with
another clear conflicts; newly completed history facts do not silently change
which token was supplied. The server-captured cutoff still determines which
facts are suppressed. The result's existing `clearBoundary` returns the new
token. Conflicts trigger an authorized fresh list read; a stale page never
authorizes a browser-selected cutoff. If an empty-history owner has no physical
record, its read supplies a defined owner-controlled initial boundary token,
not a nullable wildcard or successful read that silently mutates history.

For personalization, define `SettingsSnapshot.revision` as the control revision
shared by explicit settings changes, onboarding changes and reset commands.
`settings.read` is the exact read for all three. Each successful control change
advances that revision. A reset compares it atomically before advancing both
the control revision and its separate `inputBoundary`; its existing
`SettingsResetResult.ack.revision` returns the new control revision, while
`inputBoundary` fences old behavior/derived work. Neither value substitutes for
the current consent revision. Concurrent reset and settings update from one
control revision cannot both overwrite newer state. Boundary advancement and
policy-defined cleanup remain distinct from complete reset. Record this
aggregate decision in C03 semantics and response examples during formal
coordination; the approved baseline does not establish it yet.

### Existing revision-bearing browser bindings to preserve

These are already expressible in the baseline and are not evidence that R-01 is
fixed elsewhere. Verify their adapters and corresponding reads alongside the new
convention, preserving operation-specific preconditions.

| C13 POST path suffix | Current body and precondition | Delivery |
|---|---|---|
| `c06/replace-glossary` | `AssistanceGlossaryWriteHttp.expectedRevision` | U3; U1 only if that mutation is included |
| `c07/delete-research-sessions` | `ResearchDeleteHttp.expectedRevision`, selecting one-session or account-session-set boundary | U4; define the all-sessions read boundary explicitly |
| `c07/save-draft` | `DraftWriteHttp.baseRevision`, nullable only for new draft | U4, coordinated with Contract R-02 |
| `c07/discard-draft` | `DraftDiscardHttp.draft` binds the exact `DraftRef.revision` and content hash | U4 |
| `c07/accept-research-turn`, `c07/accept-novelty-analysis`, `c07/accept-novelty-discussion` | Their respective `*Http.submittedDraft` fields optionally bind exact acknowledged draft consumption; this is not a blanket job revision | U4 |
| `c08/upsert-topic-subscription` | `DigestSubscriptionWriteHttp.expectedRevision`, nullable only for new subscription | U5 |
| `c09/configure-notion-connection` | `ExportConnectionConfigureHttp.expectedRevision`, nullable only for new connection | U6 |
| `c09/approve-export-preview` | `ExportApprovalRequestHttp.previewRevision` plus exact `bindingHash` | U6 |
| `c09/cancel-export-approval` | `ExportCancelHttp.expectedRevision` of unconsumed approval | U6 |
| `c11/request-recovery` | `OpsRecoveryRequestHttp.expectedRevision` of the target owned by the named component | U8; any earlier mounted recovery path must follow it |

Source/option references also carry independent validity revisions:
`c04/change-source-eligibility` binds `PaperRef.eligibilityRevision`,
`c06/accept-assistance` binds paper/content/options/glossary revisions,
`c07/accept-novelty-discussion` and `c09/prepare-export-preview` bind immutable
artifact references, and `c09/execute-approved-export` binds the prior approval
and immutable preview hash. These are not interchangeable with a profile,
settings or job revision. Canonical coordination must state their comparison
target explicitly instead of mapping any field named revision into context.

The remaining state/proof transitions require explicit owner serialization but
do not currently declare the same client-observed edit precondition:
`c02/access-update-consent`, account/session/challenge/lifecycle operations,
`c04/retry-corpus-run`, `c07/cancel-novelty-analysis`, `c08/unfollow-topic`,
`c08/unsubscribe-digest-token` and `c09/disconnect-notion`. Their owning units must
document whether the action is an unconditional monotone boundary, a bound
single-use proof, a transition from a specific observed revision, or another
existing atomic condition. Any selection requiring a client revision must be
added to C00/C13 before that implementation. Do not add stale-edit preconditions
to logout or token unsubscribe by analogy, or make loss of a settings revision
silently prevent a permitted revocation. U1 uses only its defined subset; this
open classification is not full parity closure.

## R-03: one domain-owned execution protocol

PaperAssistance owns U1's accepted job, claim, immutable input, transitions,
prepared result and final accounting coordination. A dispatcher transports
references and facts; it cannot issue competing business authority. Logical
method names below are intended additions to the canonical contract, not
callable interfaces until that coordinated revision is made.

| Logical operation | Required binding | Owner outcome |
|---|---|---|
| Acquire execution claim | Trusted executor identity; owner component, operation ID/kind, accepted input revision/hash and payload reference; delivery identity | Atomically grant one current claim for eligible accepted work, or return the existing disposition. The owner issues `leaseId`, monotonically advancing fence, bound worker identity, owner-time expiry, lease revision and current job revision. Duplicate delivery cannot allocate another simultaneous claim. |
| Renew current claim | Same trusted executor and operation/input tuple; `leaseId`, fence and expected lease revision | Renew only the active unexpired claim under approved finite policy. Advance the lease revision; heartbeat renewal does not advance the business job revision or UI progress sequence. |
| Reclaim expired work | Trusted replacement executor and immutable accepted input tuple; owner verifies prior claim expiry/revocation | Atomically supersede the prior claim, issue a strictly newer fence and retain the original operation identity and accounting reservation. Delivery `attempt` alone does not authorize replacement. |
| Read execution payload | Trusted executor plus current claim tuple; exact accepted payload reference/input revision/hash | Return only authorized immutable input, validated against the accepted digest and current account/consent/source permissions. A reference or owner ID is never a bearer credential. Expired/replaced claims receive no new private payload. |
| Record progress | Current executor/claim tuple, original input hash, expected job revision, fact identity and typed progress candidate | Owner validates the transition and assigns the committed job revision/sequence. No worker supplies authoritative sequence or regresses terminal state. |
| Record success or failure | Same claim/input/job-revision binding; fact identity; typed validated prepared result or safe error; original usage identity | Owner validates current authority and result/input binding, commits one terminal disposition with one visible result and one accounting effect, and returns its receipt. |

At the effect linearization point, a claim is usable only when its executor,
operation, input, lease and fence still match the owner's active claim, and the
owner's trusted time is before expiry. Renewal, reclaim, revocation and terminal
commit compete under the same owner authority. Clock values supplied by a worker
cannot extend a lease. A replaced worker cannot renew, read fresh payload,
publish progress, fail the replacement's job or complete the result.

Job revisions and claim revisions are distinct. A progress commit returns the
new business revision for subsequent facts. A completion racing an already
committed progress fact must reread/reconcile the authoritative job under its
still-current claim; it must not force completion using a guessed revision.
Lease renewal must not create that kind of job conflict by itself.

Authenticate before duplicate-fact lookup. An exact already-committed fact may
return its existing safe receipt under current permission even if the original
claim has since expired. This is retrieval of an old disposition, never renewed
authority for another effect. A reused fact identity with different contents
conflicts. A new fact from an expired or replaced claim fails, including a late
failure that would otherwise overwrite a replacement's success.

Acceptance commits the original job and recoverable execution obligation before
acknowledgement. If result storage and accounting cannot commit in one local
transaction, their owner-coordinated recovery protocol must withhold successful
terminal visibility until the required dispositions are durably consistent.
Crash recovery reconciles the same operation/reservation/result identity; it
does not count deliveries or worker replacements as new billable work. Unknown
external outcomes remain unknown until reconciled under policy.

### Canonical shapes and bindings that must change together

| Baseline area | Required coordinated change |
|---|---|
| C00 new execution shapes | Declare acquire/renew/reclaim/read-payload requests and replies, trusted executor binding, claim tuple, separate lease revision, fence/expiry, immutable payload descriptor and typed payload response. Specify errors and bounded behavior. These internal operations must not become browser routes. |
| C00 `DispatchCommand` | Keep durable accepted operation/input identity and payload reference. Specify that delivery identity and `attempt` are transport facts, not a lease. Bind its operation/input tuple to owner claim acquisition. |
| C00 `DispatchFact` | Require exact current claim/fence, input binding and expected job revision for new progress/failure/success proposals. Separate a proposed fact from the committed owner event: existing `revision`/`seq` cannot be arbitrary worker-written authority. Include the typed progress/error/result evidence needed by each outcome. |
| C00 `DispatchAck` | Keep transport disposition separate from acquired claim and business completion. Return the owner's recorded receipt/commit revision; do not treat `committed` as a substitute for result readiness. |
| C00 `AssistanceComplete`, C06 `completeAssistance` | Add or bind the same fence/worker/claim evidence used by C14; keep job/input/prepared/usage binding. Declare owner operations for progress and failure as well as the existing success completion. |
| C14 `deliverAccepted`, `recordCompletion` | Define acquisition and payload retrieval steps explicitly. `recordCompletion` delegates to the authoritative C06 completion/progress/failure validation and commit path for assistance; direct C06 and transported C14 calls cannot have different permissions or fencing rules. |
| C00 `ResearchCompletion`, C07 and later C04/C08/C09 consumers | Adopt the same claim protocol when those units implement durable work, while retaining each owner's lifecycle and external-effect semantics. U4 preserves novelty-specific cancellation; U5/U6 reconcile delivery/export effects without claiming remote exactly-once execution. |
| C03 usage settlement and C11 observation | Settlement retains the original operation and expected accounting revision; observation reports authoritative outcomes without acquiring permission to write them. |
| C13 job GET/result/SSE projections | Remain read-only projections of the same owner snapshot. No browser claim credentials; reconnect, polling and result retrieval never start or reclaim work. |

Paper assistance retains `accepted → running → succeeded | failed`. Closing the
view or dropping a connection does not cancel it. Generic cancellation words in
shared dispatch types do not add a paper-job cancel action. Current account or
source revocation suppresses unauthorized work/results through the resolved
owner lifecycle policy; it does not let an old worker publish a late result.

## LC07: retained assistance discovery after a fresh browser start

**LC07 is a local functional binding gap**, not a new upstream review finding
ID. The approved revisit outcome cannot depend on an in-memory `jobId`: C06
currently reads a job/result only when the caller already knows its identity,
and Library saved-paper records do not expose retained assistance references.
Add one narrowly scoped read to the same PaperAssistance owner before U1 code.
It completes the retained revisit journey without a new research composer,
public API product or result-regeneration action.

Proposed logical operation **C06 `readAssistanceHistory`**:

| Item | Intended canonical semantics |
|---|---|
| Input | Trusted current account context, exact `PaperRef` identifying the requested paper/version, and `PageRequest` with cursor/limit bounded by resolved policy. No caller owner ID, free-form predicate or unbounded global job listing. |
| Selection | Only retained assistance jobs owned by the current account for that exact paper/version. The supplied eligibility revision is a source reference to validate, never proof of current permission. Recheck current account, consent and source access; a later eligibility revision must not silently substitute another paper/version or hide an otherwise authorized original binding. |
| Row | `jobId`, assistance action, accepted option ID/options revision and glossary revision, original paper/version/content revision/hash, current job state/revision/sequence, result disposition, authorized `ResultRef` when ready, and owner-recorded `createdAt`. Keep metadata bounded; no credentials, execution payloads, private prompts, result text or foreign-owner identifiers. |
| Result disposition | Use the existing C06 vocabulary `ready`, `pending`, `failed`, `expired`, `withdrawn` or `restricted`. An expired result can remain a truthful retained job entry when policy permits its metadata; physical deletion need not invent a historical row. Job success and present result availability remain separate facts. Dependency failure is an error, not a successful empty history. |
| Order and page | Descending immutable `createdAt`, then deterministic `jobId` tie-break. The opaque cursor binds verified owner, exact requested paper/version, query/schema identity and a stable membership snapshot; `PageInfo` carries snapshot revision and bounded next cursor. Current authority and result availability are rechecked on every page. Invalid/expired snapshots require a fresh read rather than silently changing pages. |
| Read-only guarantee | Listing does not accept/restart jobs, acquire or renew claims, debit usage, create history or regenerate results. No row is inferred from a client cache. A truly empty authorized list says no retained work was found; it is not an instruction to begin work. |
| Follow-up | The browser chooses a retained row and calls existing `readAssistanceJob` and `readPreparedAssistance` with its exact job/result references. Those operations independently recheck current permission and disposition. A race after listing may yield expired/restricted/not-found; the UI reports it without auto-submitting work. |

Declare C00 `AssistanceHistoryRead`, its strict browser body, history-row and
page response shapes; C06 operation/errors/ownership; and the generated C13
POST binding under the coordinated namespace (proposed
`/api/v2/c06/read-assistance-history`). The proposed path is not present in the
baseline. It uses normal authenticated same-origin/CSRF handling, safe errors
and no-store private responses; it must not mount internal claim methods.
Publish these additions in the same coordinated contract revision, update all
schema copies/references, validator fixtures and capability bindings, and keep
producer/consumer version evidence together. PaperAssistance supplies this read;
Library retains ownership only of the saved paper reference.

Verification must discard all transient browser job/result IDs, authenticate the
same synthetic owner, open the saved exact paper/version, discover the retained
job and read its existing prepared result without a new job or accounting
effect. Repeat with another account, expired/revoked access, missing/expired
result, current withdrawal, source-version differences, equal creation times,
changed/expired cursor and dependency failure. Current permission must prevent
cross-owner enumeration, and an older permitted result must retain its original
source/action bindings rather than masquerade as the newest version.

## Coordination and closure evidence

| Step | Responsible delivery | Required evidence before proceeding |
|---|---|---|
| Publish one formal amendment | U1 with AccountAccess, Library, Personalization, UsageEntitlements and PaperAssistance ownership; record later consumers | Update C00, C02/C03/C06/C14 semantics, exact C13 references/copies, compatibility version/digests, examples and validator as one reviewable change. Include LC07 assistance discovery, the concrete history-clear token read and the Personalization control-revision decision. New required inputs are breaking under baseline version rules; coordinate the major contract revision and consumers, without claiming an existing deployment has upgraded. |
| Close U1 browser integration | U1 | Through real browser/server boundaries: missing/invalid revision rejected, one of two writes from the same revision commits, stale write preserves state, lost response with original key recovers its receipt, changed input/key misuse conflicts, foreign/revoked access denied, authorized fresh read enables deliberate resubmission. Preserve correct reads after mutation-type splitting. |
| Close U1 executor integration | U1 | Crash after acceptance before dispatch; duplicate deliveries; owner claim acquisition and protected payload read; renewal without business revision change; expiry/replacement; late old-worker progress, failure and success rejected; exact committed duplicate reconciled; result/accounting crash and acknowledgement loss recover one logical outcome. |
| Close LC07 retained revisit | U1 | Fresh browser with no job/result IDs rediscovers only the current owner's retained exact-paper work and reads the prepared result without new execution; exercise denied, expired, withdrawn, empty, paginated and failed-read outcomes. |
| Complete browser and executor consumers | U2–U6 as assigned above; U8 cumulative | All required body/read-target definitions and later owner adapters resolved; operation-specific revisions remain distinct; real integration checks cover every installed participant. U4 separately closes draft allocation/discovery and the no-in-memory-ID restart check. |

Before enabling execution, resolve approved finite admission, claim duration,
renewal, deadline, retry/reconciliation and concurrency limits on the measured
$0 free/local configuration. Resolve permitted source/model processing and
affected persistence/retention obligations. No number, broker, database,
framework, public host or paid fallback is selected here. These are existing
evidence gates; unavailable functionality is not accepted as final release
parity. Schema validation and this plan alone close neither accepted finding.
