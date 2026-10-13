# U2 account and personal controls — business rules

The YAML is authoritative. Rules elaborate the confirmed [questions](functional-design-questions.md), [requirements](../../../inception/requirements-analysis/requirements.md), unit assignments and canonical C02/C03/C13 contracts. Source IDs express U2's contribution; shared requirements still require their lead unit and U8 integration. [Functional specification](functional-spec.md) gives operation ordering and checks. Every finite policy named here is required evidence before affected implementation; these rules do not select retention periods, delivery providers or quota values.

```yaml
unit: u2-account-personal-controls
rules:
- id: BR1.1
  statement: Use current authority at every protected boundary.
  category: authorization
  applies_to: All U2 operations and consuming domains
  trigger: Read, command admission, replay and effect publication
  logic: IF the current session, account, owner, role, MFA, consent or source authority required by an operation is absent
    THEN deny before returning cached outcomes or applying effects. Resolve resource ownership independently of caller
    identifiers.
  violation: Authentication or permission error; foreign resources use the contract-safe absent/denied response.
  source:
  - FR2.3
  - FR4.1
  - FR6.4
  - FR7.2
  - FR8.1
  - FR12.1
  - FR13.2
  - FR14.2
  - FR15.2
  - FR16.1
  - NFR4
- id: BR1.2
  statement: Reconcile the same intended command before creating new work.
  category: constraint
  applies_to: Owner command receipts
  trigger: Duplicate request or lost acknowledgement
  logic: IF current authority holds and owner/operation/key and normalized intent match a receipt THEN return its authorized
    outcome before fresh revision comparison; IF the intent differs THEN conflict. Reconciliation cannot execute another
    effect.
  violation: Conflict for changed intent; unknown outcome remains explicit until evidence resolves it.
  source:
  - FR3.2
  - FR5.1
  - FR6.2
  - FR8.1
  - FR14.1
  - FR15.2
  - FR16.2
  - FR17.2
  - NFR1
  - NFR3
- id: BR1.3
  statement: Use the revision of the exact mutable control.
  category: constraint
  applies_to: Profile, settings, identity unlink, saved-reference removal, history clear and entitlement assignment
  trigger: Browser mutation
  logic: IF the canonical operation requires expectedRevision THEN reject missing/null/empty input and pass the top-level
    HTTP value into trusted context unchanged; compare only after current-authority and same-command replay checks. A
    conflict requires its named authorized read, preserving local edits until a deliberate retry.
  violation: Conflict without leaking another owner or latestRevision in generic errors; no blind overwrite.
  source:
  - FR4.2
  - FR5.3
  - FR8.1
  - FR10.1
  - FR11.1
  - FR17.1
  - NFR2
  - NFR3
- id: BR1.4
  statement: Validate bounded retained vocabularies on the server.
  category: validation
  applies_to: All forms, page requests and provider inputs
  trigger: Before work admission
  logic: IF fields, encoding, lengths, item counts, duplicate fields or vocabulary revisions violate their finite policy
    THEN reject before effects; tolerate valid Korean/Unicode without accidental identity collisions. Page tokens bind
    owner, query, schema and snapshot and contain no private plaintext.
  violation: Field-specific validation or stale-page response; unavailable is not an empty result.
  source:
  - FR1.3
  - FR4.2
  - FR5.2
  - FR6.4
  - FR10.1
  - FR11.1
  - NFR8
- id: BR1.5
  statement: Keep durable success, failed work and unknown outcomes distinct.
  category: constraint
  applies_to: All U2 acknowledgements and observations
  trigger: Write or dependency interruption
  logic: IF durable effect evidence exists THEN acknowledge that effect; IF conclusively rejected THEN show failure;
    ELSE show unknown/pending and reconcile the original identity. Reads do not restart operations.
  violation: No false saved, cleared, revoked, refunded or complete message.
  source:
  - FR5.1
  - FR6.1
  - FR8.1
  - FR17.2
  - FR19.1
  - FR19.2
  - FR19.3
  - NFR1
  - NFR2
  - NFR3
  - NFR9
- id: BR2.1
  statement: Registration and recovery do not disclose account existence.
  category: authorization
  applies_to: Account and IdentityChallenge
  trigger: Register, resend verification, password-reset request or reactivation request
  logic: IF the request passes finite abuse and delivery policy checks THEN give an existence-neutral acknowledgement
    and bind any actual proof to its verified destination, purpose, flow, revision and expiry. Delivery failure is not
    verification success.
  violation: Neutral response with truthful service-wide delivery failure/limits; never reveal active, withdrawn or erased
    status publicly.
  source:
  - FR6.1
  - FR6.3
  - FR6.4
  - NFR4
- id: BR2.2
  statement: Consume proofs once with their intended identity effect.
  category: constraint
  applies_to: IdentityChallenge and Account
  trigger: Verification, reset or email-change completion
  logic: IF proof purpose, owner binding, current revision, expiry and replay checks pass THEN atomically consume it
    with the intended effect or retain recoverable evidence of that same effect. Email changes preserve old identity
    until verified replacement commits and reject collisions.
  violation: Expired, invalid or conflicting proof; same-key reconciliation never reuses the secret for a second effect.
  source:
  - FR6.1
  - FR6.2
  - FR6.4
  - NFR3
  - NFR4
- id: BR2.3
  statement: Issue full access only after every required authentication step.
  category: authorization
  applies_to: AuthenticationSession
  trigger: Password/provider sign-in, MFA and logout
  logic: IF primary authentication and required verification/MFA are current THEN issue the protected full session; ELSE
    only a purpose-limited continuation is available. Logout must revoke server authority before reporting completion.
    Credential changes apply the approved session-revocation policy without deleting committed work.
  violation: No full access from pre-authentication or reactivation cookies; revoked sessions and stale tabs cannot regain
    access.
  source:
  - FR6.1
  - FR6.2
  - FR6.4
  - FR7.2
  - NFR4
- id: BR2.4
  statement: Bind external identity callbacks and keep owners distinct.
  category: authorization
  applies_to: IdentityLink and IdentityChallenge
  trigger: Google/ORCID sign-in, linking and unlinking
  logic: IF provider allowlist, callback, state, issuer/audience, nonce and applicable PKCE checks plus bound flow/purpose
    pass THEN consume once and link only the intended current account. Subject collisions never merge owners. Unlink
    requires current revision and an approved surviving-access policy.
  violation: Denied consent/provider failure remains recoverable; invalid/replayed callback or unsafe last-link removal
    has no identity effect.
  source:
  - FR7.1
  - FR11.2
  - NFR4
  - NFR10
- id: BR2.5
  statement: MFA enrollment material has a single protected delivery.
  category: authorization
  applies_to: MFA enrollment value records
  trigger: Enrollment material retrieval and factor confirmation
  logic: IF current reauthentication and bound unused delivery reference are valid THEN expose seed/URI/recovery codes
    only in the protected no-store one-time response, render QR locally and activate only after confirmed factor. Retrieval
    acknowledgement loss requires a new enrollment invalidating the old material.
  violation: No secret in generic receipts, logs, traces, caches or persisted browser storage; replay is expired, not
    redisplayed.
  source:
  - FR7.2
  - NFR4
  - NFR5
- id: BR2.6
  statement: Administrator and recovery authority never imply operator authority.
  category: authorization
  applies_to: Application administration and controlled MFA recovery
  trigger: Administrative action or recovery
  logic: IF current app-admin role and MFA hold THEN admit only that application operation. MFA recovery requires an
    approved audited proof procedure; unavailable recovery policy blocks recovery. PlatformControl verifies its independent
    operator authority.
  violation: No ordinary-user grant, production bypass, MFA disabling shortcut or U7 privilege inheritance.
  source:
  - FR7.2
  - FR17.1
  - FR19.1
  - NFR4
- id: BR3.1
  statement: Profile updates follow the retained editable field vocabulary.
  category: validation
  applies_to: Account.profile
  trigger: Profile save
  logic: IF a nonempty set of distinct allowed mutable fields matches the current vocabulary, type and revision THEN
    persist those changes only. Identity, credentials and roles use their dedicated operations.
  violation: Validation/conflict preserves acknowledged profile and local edits; no partial unauthorized field update.
  source:
  - FR8
  - FR8.1
  - NFR1
- id: BR3.2
  statement: Acknowledged consent controls later processing immediately.
  category: policy
  applies_to: ConsentRecord and all consumers
  trigger: Consent change or queued effect
  logic: IF a current decision revokes a purpose THEN future admissions and effects for that purpose are denied even
    while cleanup is pending. Consumers recheck the authoritative current decision rather than trusting an old fact.
    Regrant never resurrects erased data or legitimizes old prohibited events.
  violation: Failed consent write leaves prior decision in force and UI says unsaved; failed cleanup never reenables
    processing.
  source:
  - FR8.1
  - FR10.2
  - FR12
  - FR12.2
  - FR13
  - FR13.1
  - FR16
  - FR16.2
  - NFR4
  - NFR5
- id: BR3.3
  statement: Lifecycle acceptance requires policy and a complete participant manifest.
  category: policy
  applies_to: AccountLifecycleRequest
  trigger: Withdraw, erase or reactivate admission
  logic: IF approved policy, current confirmation/reauthentication and complete compatible required participant/scope
    bindings exist THEN accept a durable request and establish its required authority boundary. Otherwise do not claim
    lifecycle acceptance.
  violation: POLICY_UNRESOLVED or explicit unavailable/blocked readiness; no legacy 30-day default or silent omitted
    participant.
  source:
  - FR6.3
  - FR14.2
  - FR18.2
  - NFR3
  - NFR5
  - NFR10
- id: BR3.4
  statement: Complete lifecycle work only from every required acknowledgement.
  category: constraint
  applies_to: AccountLifecycleRequest participant tickets
  trigger: Participant retry and completion
  logic: IF each required scope has current policy/manifest/request-bound evidence and required revocation is effective
    THEN report complete. Participants update only their own records and duplicate acknowledgements converge. Missing,
    failed or stale work keeps the request incomplete.
  violation: Expose pending/blocked/failed scopes safely; no partial purge called complete.
  source:
  - FR6.3
  - FR14.2
  - FR18.2
  - FR19.3
  - NFR3
  - NFR5
- id: BR3.5
  statement: Reactivation restores only permissible retained state.
  category: policy
  applies_to: AccountLifecycleRequest and IdentityChallenge
  trigger: Purpose-bound reactivation
  logic: IF the account is currently withdrawn and verified flow, lifecycle revision and approved retention policy still
    permit recovery THEN consume once and coordinate only demonstrably retained permissible state. Erasure, superseding
    requests and old tombstones prevent resurrection.
  violation: Neutral initiation; after proof, blocked/expired/conflict as appropriate. Completion requires fresh normal
    sign-in and any required MFA.
  source:
  - FR6.3
  - FR7.2
  - NFR3
  - NFR4
  - NFR5
- id: BR3.6
  statement: Restore enforces current lifecycle and consent restrictions.
  category: authorization
  applies_to: All domain participants and separately authorized restore executor
  trigger: Restore or replay from backup/derived artifacts
  logic: IF the latest authority, tombstones, policy and required scopes allow a restore set THEN enforce that decision
    at the actual restore effect and record evidence. Never substitute the older snapshot authority.
  violation: Deny or require reconciliation; no restored private access or delayed work while authority is uncertain.
  source:
  - FR6.3
  - FR8.1
  - FR14.2
  - FR18.2
  - FR19.3
  - NFR3
  - NFR5
- id: BR4.1
  statement: Save eligible stable references under the Library owner.
  category: constraint
  applies_to: SavedPaper and SavedSearch
  trigger: Explicit save and later read
  logic: IF current CorpusContent eligibility and normalized identity or retained query vocabulary are valid THEN persist
    one intended owner reference. Opening saved content is read-only; rerunning a query requires a separate explicit
    Discovery action.
  violation: No browser-invented canonical metadata, duplicate effect, hidden rerun or history deletion.
  source:
  - FR1
  - FR1.1
  - FR5
  - FR5.1
  - FR5.2
  - FR9
  - FR9.1
  - NFR1
- id: BR4.2
  statement: Changed sources preserve original saved identity and truthful disposition.
  category: constraint
  applies_to: SavedPaper
  trigger: Read, source withdrawal or canonicalization
  logic: IF source authority or canonical identity changes THEN retain the original saved reference and display the current
    eligible resolution/disposition; current CorpusContent governs content access. Removing a reference affects only
    that owner and reference.
  violation: Restricted/withdrawn/unavailable stays explicit, not deleted silently or shown as fresh available content.
  source:
  - FR5.3
  - FR9.2
  - FR18
  - FR18.1
  - FR18.2
  - FR18.3
  - NFR1
  - NFR4
- id: BR4.3
  statement: Clear history suppresses late facts admitted before its cutoff.
  category: constraint
  applies_to: SearchHistory and owner clear checkpoint
  trigger: History clear and completion-fact delivery
  logic: IF current authority and same-key replay permit a new clear with the expected clearBoundary THEN capture a trusted
    Discovery admission checkpoint and atomically persist the new clear boundary, logical deletion and receipt. A later
    fact at or below that cutoff is suppressed regardless of finish time; above-cutoff facts remain eligible.
  violation: Client cutoffs rejected; lost-reply replay returns the original cutoff and cannot erase newer searches.
  source:
  - FR5.2
  - FR5.3
  - NFR3
- id: BR5.1
  statement: Explicit settings remain distinct from derived behavior and glossary data.
  category: constraint
  applies_to: PersonalSettings
  trigger: Defaults read/update and consumer use
  logic: IF a retained setting is valid and its revision matches THEN acknowledge explicit values for future intended
    actions. Consumers report unsupported modes without silently rewriting preferences; PaperAssistance alone owns glossary
    data.
  violation: Stale vocabulary/conflict/unsupported feedback preserves prior saved choices and current query controls.
  source:
  - FR1.2
  - FR1.3
  - FR3
  - FR3.1
  - FR4
  - FR4.1
  - FR4.2
  - FR10
  - FR10.1
  - NFR2
- id: BR5.2
  statement: Onboarding progress is resumable and optional.
  category: constraint
  applies_to: PersonalSettings.onboarding
  trigger: Save interests, complete, skip or return
  logic: IF the expected shared settings revision matches THEN store the explicit onboarding action once. Skip preserves
    established choices; next visit respects completed/skipped status. ORCID suggestions retain provenance and never
    auto-enroll an interest.
  violation: Manual selection and skip remain usable when provider data is denied, missing or partial; no redirect loop.
  source:
  - FR11
  - FR11.1
  - FR11.2
  - NFR2
  - NFR10
- id: BR5.3
  statement: Reset boundaries defeat delayed activity and stale projections.
  category: constraint
  applies_to: BehaviorRecord and PersonalProfile
  trigger: Opt-out, delete_behavior, reset_profile, event or projection completion
  logic: IF reset is explicitly confirmed under approved policy THEN advance inputBoundary and shared settings revision
    before accepting later activity, persist cleanup responsibility and reconcile duplicate requests. Events/projections
    from earlier generations or prohibited consent are suppressed. Cleanup never deletes Library records or explicit
    defaults unless separately requested by an authorized retained operation.
  violation: Complete/pending/blocked reflects real affected scopes and restore enforcement; missing cleanup evidence
    cannot mean complete.
  source:
  - FR10.2
  - FR8.1
  - NFR3
  - NFR5
- id: BR5.4
  statement: Recent and personalized views use permitted evidence.
  category: policy
  applies_to: BehaviorRecord, PersonalProfile and recent-paper projection
  trigger: Read recent papers or personalized search inputs
  logic: IF eligible current activity exists THEN expose stable owner-scoped order and source disposition; ELSE distinguish
    cold start, disabled and unavailable. No reading action fabricates or records a new behavior event by itself.
  violation: No inferred results from prohibited/stale activity; explicit defaults remain usable without enrichment.
  source:
  - FR1.2
  - FR10.1
  - FR10.2
  - FR11.2
  - NFR1
  - NFR5
- id: BR6.1
  statement: Plan and quota views report known policy-backed state.
  category: policy
  applies_to: Entitlement and UsageRecord
  trigger: Inspect plan, balance, usage or administrative assignment
  logic: IF current allocation, period and accounting evidence are known THEN display them with their policy; otherwise
    mark unknown. Mock/administrative tiers are labelled and imply no charge or purchase.
  violation: No unknown-as-zero, invented unlimited allocation, payment flow or paid fallback.
  source:
  - FR8.2
  - FR17
  - FR17.1
  - FR17.2
  - NFR8
- id: BR6.2
  statement: Grant and revoke share one auditable target assignment control.
  category: authorization
  applies_to: Entitlement
  trigger: Administrative allocation mutation
  logic: IF current admin MFA, independent target, allowed free/local tier, reason and assignment expectedRevision are
    valid THEN commit one auditable grant/revoke. An absent target assignment uses the initial read revision. Revocation
    follows the policy for already accepted work.
  violation: No body-supplied role or allocation escalation; no cancelling acknowledged work or silently enabling paid
    tiers.
  source:
  - FR17.1
  - FR7.2
  - NFR4
  - NFR9
- id: BR6.3
  statement: Reserve before durable work acceptance under finite current policy.
  category: calculation
  applies_to: UsageRecord
  trigger: Protected operation admission
  logic: IF trusted operation owner, current entitlement, server quantity and acceptance-time period permit the action
    THEN reserve once by operation identity/fingerprint. Concurrent reservations must not overspend the same allocation.
    Unknown balance/policy blocks new acceptance.
  violation: Limit/unavailable/unknown response before acceptance; duplicate reserves cannot consume twice.
  source:
  - FR3.2
  - FR13.3
  - FR14
  - FR14.1
  - FR15
  - FR15.1
  - FR17.2
  - NFR1
  - NFR8
- id: BR6.4
  statement: Settle and reconcile the original accounting responsibility.
  category: calculation
  applies_to: UsageRecord
  trigger: Completion, cancellation, failure, refund or period transition
  logic: IF current bound operation evidence and accounting revision authorize a policy-defined commit, release or refund
    THEN apply it once. Reconciliation reads the original responsibility; a new period does not move old work or create
    compensation.
  violation: Ambiguous effects stay unresolved; no guessed refund, new debit or success.
  source:
  - FR3.2
  - FR13.3
  - FR14.1
  - FR15.2
  - FR17.2
  - NFR3
  - NFR8
- id: BR7.1
  statement: The workspace isolates owner state across interruption and account changes.
  category: authorization
  applies_to: WebWorkspace and all owner-specific views
  trigger: Session expiry, logout, reauthentication, navigation or account switch
  logic: IF authority expires or owner changes THEN clear private render/query caches and transient secrets, reject late
    responses for the former identity, preserve only safe navigation context and reauthenticate before fresh reads. No
    queued action is replayed automatically.
  violation: No previous-owner flash, cached private back-navigation, false autosave or loss of committed work. Durable
    research draft discovery remains U4.
  source:
  - FR6.4
  - FR8.1
  - FR13.2
  - FR14.1
  - FR15.1
  - FR16.1
  - NFR2
  - NFR3
  - NFR4
- id: BR7.2
  statement: Use accessible Korean interaction and truthful progressive feedback.
  category: policy
  applies_to: U2 web components
  trigger: All form and list states
  logic: IF a view loads, fails, conflicts or changes state THEN retain relevant controls/context, identify field errors
    and announce outcome without stealing focus. Preserve keyboard access, reflow, inherited blue/neutral colors, Apple
    HIG web hierarchy and light/dark/system behavior.
  violation: Never rely on color or motion alone; document unverified conformance and numeric targets as later evidence.
  source:
  - FR1.3
  - FR5
  - FR6
  - FR7
  - FR8
  - FR10
  - FR11
  - FR17
  - NFR2
  - NFR6
- id: BR7.3
  statement: Expose capability readiness and safe repair evidence.
  category: constraint
  applies_to: All four U2 domain owners and ServiceOperations integration
  trigger: Readiness inspection, incident or participant failure
  logic: IF a required policy, adapter, authority, participant or durable store is unavailable THEN report the specific
    safe capability limitation with original operation references and bounded recovery evidence. Correlate failures without
    credentials, draft text or private source content in telemetry.
  violation: Liveness and fixture success never stand for public delivery, complete parity or operating feasibility.
  source:
  - FR19
  - FR19.1
  - FR19.2
  - FR19.3
  - NFR7
  - NFR9
  - NFR10
```

## Rules summary (derived)

| ID | Decision |
|---|---|
| BR1.1 | Use current authority at every protected boundary. |
| BR1.2 | Reconcile the same intended command before creating new work. |
| BR1.3 | Use the revision of the exact mutable control. |
| BR1.4 | Validate bounded retained vocabularies on the server. |
| BR1.5 | Keep durable success, failed work and unknown outcomes distinct. |
| BR2.1 | Registration and recovery do not disclose account existence. |
| BR2.2 | Consume proofs once with their intended identity effect. |
| BR2.3 | Issue full access only after every required authentication step. |
| BR2.4 | Bind external identity callbacks and keep owners distinct. |
| BR2.5 | MFA enrollment material has a single protected delivery. |
| BR2.6 | Administrator and recovery authority never imply operator authority. |
| BR3.1 | Profile updates follow the retained editable field vocabulary. |
| BR3.2 | Acknowledged consent controls later processing immediately. |
| BR3.3 | Lifecycle acceptance requires policy and a complete participant manifest. |
| BR3.4 | Complete lifecycle work only from every required acknowledgement. |
| BR3.5 | Reactivation restores only permissible retained state. |
| BR3.6 | Restore enforces current lifecycle and consent restrictions. |
| BR4.1 | Save eligible stable references under the Library owner. |
| BR4.2 | Changed sources preserve original saved identity and truthful disposition. |
| BR4.3 | Clear history suppresses late facts admitted before its cutoff. |
| BR5.1 | Explicit settings remain distinct from derived behavior and glossary data. |
| BR5.2 | Onboarding progress is resumable and optional. |
| BR5.3 | Reset boundaries defeat delayed activity and stale projections. |
| BR5.4 | Recent and personalized views use permitted evidence. |
| BR6.1 | Plan and quota views report known policy-backed state. |
| BR6.2 | Grant and revoke share one auditable target assignment control. |
| BR6.3 | Reserve before durable work acceptance under finite current policy. |
| BR6.4 | Settle and reconcile the original accounting responsibility. |
| BR7.1 | The workspace isolates owner state across interruption and account changes. |
| BR7.2 | Use accessible Korean interaction and truthful progressive feedback. |
| BR7.3 | Expose capability readiness and safe repair evidence. |
