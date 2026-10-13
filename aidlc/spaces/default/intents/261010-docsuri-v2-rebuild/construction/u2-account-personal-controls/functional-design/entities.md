# U2 account and personal controls — entity model

Confirmed scope: 2026-10-13. This logical model elaborates the approved owners in [components](../../../inception/domain-design/components.md) and C02/C03 in [contracts](../../../inception/contract-design/contract-summary.md). The YAML is authoritative for entity shape; [functional-spec](functional-spec.md) owns transitions and ordered behavior. It selects no new storage technology or public hosting.

Opaque identifiers and revisions are bounded, nonempty values; references never grant access. Variable text, collections, proof attempts and lifetimes require finite approved policies before processing. No omitted bound means unlimited. Required false means optional, not permission to infer a successful value. Nullable wire fields and exact public enums follow the canonical contract. The logical access states below do not replace its transport unions.

MFA enrollment/delivery records, lifecycle tickets and restore decisions, history clear checkpoints, settings reset receipts and entitlement assignment controls are owner-local value records beneath these entities, not new components. A shared command receipt belongs to the operation's authoritative owner and binds current owner, operation, idempotency key, normalized intent, accepted time, outcome reference and any required revision. It contains no replayable secrets. Raw credentials, factor seeds and recovery codes live only behind protected credential references; enrollment delivery is the narrowly permitted one-time response.

```yaml
model: u2-account-personal-controls
entities:
- name: Account
  owner: AccountAccess
  description: Authoritative identity, editable profile and current access boundary.
  attributes:
  - name: accountId
    type: opaque identifier
    required: true
    unique: true
  - name: email
    type: normalized email identity
    required: true
    unique: true
    constraints:
    - Uniqueness/collision is enforced under approved email normalization policy; do not invent provider-specific
      folding.
  - name: credentialReference
    type: protected credential reference
    required: false
    unique: false
  - name: profile
    type: typed retained field values
    required: true
    unique: false
    constraints:
    - Vocabulary revision and mutability govern every field; excludes credentials, email, roles and identity links.
  - name: verification
    type: verification disposition
    required: true
    unique: false
  - name: lifecycle
    type: logical access state
    required: true
    unique: false
    allowed_values:
    - unverified
    - active
    - withdrawn
    - erased
  - name: authorityRevision
    type: opaque revision
    required: true
    unique: false
  - name: profileRevision
    type: opaque revision
    required: true
    unique: false
  - name: roleAssignments
    type: approved application role references
    required: true
    unique: false
  constraints:
  - Profile and authority revisions are independent.
  - Erased is terminal for this account identity; withdrawal does not itself mean erasure.
  - Never return credential material or infer operator privileges from application roles.
  relationships: []
- name: AuthenticationSession
  owner: AccountAccess
  description: Revocable authenticated session or purpose-limited continuation.
  attributes:
  - name: sessionId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: authorityRevision
    type: opaque revision
    required: true
    unique: false
  - name: authenticationContext
    type: primary proof and MFA assurance reference
    required: true
    unique: false
  - name: purpose
    type: logical purpose
    required: true
    unique: false
    allowed_values:
    - full_session
    - primary_mfa_continuation
    - reactivation_status
  - name: flowBinding
    type: protected flow reference
    required: false
    unique: false
  - name: expiresAt
    type: server time
    required: true
    unique: false
  - name: revocation
    type: revocation disposition
    required: true
    unique: false
  constraints:
  - Session identifiers in the browser are protected transport credentials, not JSON response values.
  - A continuation never authorizes ordinary protected resources.
  - Expiration and revocation are checked against current account authority.
  relationships:
  - target: Account
    cardinality: many to one
    direction: outbound reference
    meaning: Session belongs to one account; anonymous initiation has no full session.
- name: IdentityLink
  owner: AccountAccess
  description: Google or ORCID subject linked to one account.
  attributes:
  - name: identityLinkId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: provider
    type: enumeration
    required: true
    unique: false
    allowed_values:
    - google
    - orcid
  - name: providerSubject
    type: provider-scoped subject
    required: true
    unique: false
  - name: profileProvenance
    type: source and revision
    required: false
    unique: false
  - name: credentialReference
    type: protected provider credential reference
    required: false
    unique: false
  constraints:
  - The provider and subject pair is globally unique; never merge accounts by coincident email.
  - Unlink requires the current revision and an approved remaining-access policy.
  relationships:
  - target: Account
    cardinality: many to one
    direction: outbound reference
    meaning: Link owner.
- name: IdentityChallenge
  owner: AccountAccess
  description: Bound, expiring single-use credential, identity, MFA or reactivation proof.
  attributes:
  - name: challengeId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: false
    unique: false
    references: AccountAccess.Account.accountId
  - name: purpose
    type: registered purpose
    required: true
    unique: false
  - name: verificationBinding
    type: purpose, recipient, flow, relevant identity/lifecycle revision and callback binding
    required: true
    unique: false
  - name: useDisposition
    type: logical disposition
    required: true
    unique: false
    allowed_values:
    - issued
    - consumed
    - expired
    - invalidated
  - name: credentialReference
    type: protected proof reference
    required: true
    unique: false
  - name: expiresAt
    type: server time
    required: true
    unique: false
  - name: attemptBoundary
    type: finite policy reference
    required: true
    unique: false
  constraints:
  - Anonymous initiation can precede account resolution; no caller-supplied owner is authority.
  - Proof consumption and intended identity effect reconcile as one outcome.
  - Expired, superseded or differently bound proofs cannot become valid through retry.
  relationships:
  - target: Account
    cardinality: many to zero or one
    direction: outbound reference
    meaning: Resolved target account, where initiation permits it.
- name: ConsentRecord
  owner: AccountAccess
  description: Purpose-specific acknowledged processing decision.
  attributes:
  - name: consentId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: purpose
    type: registered consent purpose
    required: true
    unique: false
  - name: decision
    type: enumeration
    required: true
    unique: false
    allowed_values:
    - granted
    - revoked
  - name: policyReference
    type: approved policy revision
    required: true
    unique: false
  - name: effectiveAt
    type: immutable server time
    required: true
    unique: false
  constraints:
  - One current decision per account and purpose; retain only policy-permitted evidence.
  - Acknowledgement follows durable decision; revocation governs future effects independently of cleanup progress.
  relationships:
  - target: Account
    cardinality: many to one
    direction: outbound reference
    meaning: Consent owner.
- name: AccountLifecycleRequest
  owner: AccountAccess
  description: Coordination evidence for withdrawal, reactivation or erasure, without owning feature records.
  attributes:
  - name: lifecycleRequestId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: requestedAction
    type: enumeration
    required: true
    unique: false
    allowed_values:
    - withdraw
    - reactivate
    - erase
  - name: state
    type: enumeration
    required: true
    unique: false
    allowed_values:
    - accepted
    - running
    - complete
    - blocked
    - failed
  - name: policyReference
    type: approved lifecycle policy revision
    required: true
    unique: false
  - name: participantManifest
    type: immutable participant, contract revision and required-scope set
    required: true
    unique: false
  - name: participantDispositions
    type: per participant and scope evidence references
    required: true
    unique: false
  - name: revocation
    type: disposition
    required: true
    unique: false
  - name: completionEvidence
    type: protected evidence reference
    required: false
    unique: false
  - name: acceptedAt
    type: immutable server time
    required: true
    unique: false
  constraints:
  - Complete requires every declared participant and required scope, including backup and restore obligations, to
    have acceptable current evidence.
  - Later retry resumes unresolved tickets for the same request; it does not replace the manifest silently.
  - Revoked access and completed cleanup are separate facts.
  relationships:
  - target: Account
    cardinality: many to one
    direction: outbound reference
    meaning: Lifecycle subject.
- name: PersonalSettings
  owner: Personalization
  description: Explicit defaults, appearance and resumable onboarding, separate from inferred behavior.
  attributes:
  - name: settingsId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: searchDefaults
    type: retained query vocabulary values and revision
    required: true
    unique: false
  - name: assistanceDefaults
    type: retained action, language, level values and revision
    required: true
    unique: false
  - name: appearance
    type: enumeration
    required: true
    unique: false
    allowed_values:
    - light
    - dark
    - system
  - name: onboarding
    type: enumeration
    required: true
    unique: false
    allowed_values:
    - not_started
    - in_progress
    - completed
    - skipped
  - name: interestIds
    type: set of retained interest identifiers
    required: true
    unique: false
    constraints:
    - Unique and policy bounded.
  constraints:
  - Settings, onboarding and reset controls share the SettingsSnapshot revision.
  - No inferred profile update overwrites explicit defaults; skip preserves established preferences.
  - Defaults cannot silently activate an unavailable search or assistance capability.
  relationships:
  - target: Account
    cardinality: zero or one to one
    direction: outbound reference
    meaning: Exactly one settings authority per account; virtual initial read is permitted by contract.
- name: BehaviorRecord
  owner: Personalization
  description: Permitted deduplicated activity fact, distinct from a saved paper or query.
  attributes:
  - name: behaviorRecordId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: producerEventId
    type: trusted event identity
    required: true
    unique: false
  - name: paperVersionId
    type: opaque identifier
    required: true
    unique: false
    references: CorpusContent.PaperVersion
  - name: activity
    type: retained activity vocabulary
    required: true
    unique: false
  - name: consentRevision
    type: opaque revision
    required: true
    unique: false
  - name: authorityRevision
    type: opaque revision
    required: true
    unique: false
  - name: inputBoundary
    type: opaque reset generation
    required: true
    unique: false
  - name: occurredAt
    type: server-validated time
    required: true
    unique: false
  - name: erasureDisposition
    type: policy disposition
    required: true
    unique: false
  constraints:
  - Producer and event identity deduplicate effects.
  - Current consent, lifecycle and reset boundary are checked before recording and deriving a projection.
  - Client timestamps cannot override a server reset boundary.
  relationships:
  - target: Account
    cardinality: many to one
    direction: outbound reference
    meaning: Activity subject.
  - target: CorpusContent.PaperVersion
    cardinality: many to one
    direction: outbound reference
    meaning: Activity paper context.
- name: PersonalProfile
  owner: Personalization
  description: Rebuildable permitted projection; not the editable account profile.
  attributes:
  - name: profileId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: inputBoundary
    type: opaque reset generation
    required: true
    unique: false
  - name: consentRevision
    type: opaque revision
    required: true
    unique: false
  - name: preferencesProjection
    type: permitted derived interest values
    required: true
    unique: false
  - name: disposition
    type: enumeration
    required: true
    unique: false
    allowed_values:
    - ready
    - cold_start
    - disabled
    - unavailable
  - name: resetDisposition
    type: enumeration
    required: true
    unique: false
    allowed_values:
    - complete
    - pending
    - blocked
  constraints:
  - A stale projection is not usable simply because it exists.
  - Reset clears only its approved scope and never Library or committed research work.
  - Reset input boundary changes precede consumption of later events; old work cannot rebuild deleted behavior.
  relationships:
  - target: Account
    cardinality: zero or one to one
    direction: outbound reference
    meaning: Projection subject.
  - target: BehaviorRecord
    cardinality: one to many
    direction: outbound reference
    meaning: Derives only from currently eligible activity.
- name: SavedPaper
  owner: Library
  description: Durable explicit reference retaining original identity and a current source disposition.
  attributes:
  - name: savedPaperId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: paperId
    type: opaque identifier
    required: true
    unique: false
    references: CorpusContent.Paper
  - name: paperVersionId
    type: opaque identifier
    required: true
    unique: false
    references: CorpusContent.PaperVersion
  - name: savedMetadata
    type: permitted metadata snapshot
    required: false
    unique: false
  - name: resolvedPaper
    type: current canonical reference
    required: false
    unique: false
  - name: sourceDisposition
    type: enumeration
    required: true
    unique: false
    allowed_values:
    - available
    - source_only
    - canonicalized
    - withdrawn
    - unavailable
    - restricted
  constraints:
  - Original saved identity is immutable; canonical resolution does not substitute private or unrelated content.
  - Account plus normalized eligible paper identity is the deduplication boundary defined by CorpusContent.
  - Removing a saved reference does not delete the public paper.
  relationships:
  - target: Account
    cardinality: many to one
    direction: outbound reference
    meaning: Saved-reference owner.
  - target: CorpusContent.Paper
    cardinality: many to one
    direction: outbound reference
    meaning: Original stable paper.
  - target: CorpusContent.PaperVersion
    cardinality: many to one
    direction: outbound reference
    meaning: Original version context.
- name: SavedSearch
  owner: Library
  description: Explicit query context and optional label; opening it does not execute it.
  attributes:
  - name: savedSearchId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: queryContext
    type: retained query, filters, order, mode and vocabulary revision
    required: true
    unique: false
  - name: label
    type: bounded Unicode text
    required: false
    unique: false
  constraints:
  - Normalize only as specified by the search vocabulary; preserve meaningful Unicode.
  - A retry of a save is not an edit of another saved search.
  - Deleting this record is independent of clearing search history.
  relationships:
  - target: Account
    cardinality: many to one
    direction: outbound reference
    meaning: Saved-query owner.
- name: SearchHistory
  owner: Library
  description: Eligible completed-search fact with ordering and clear-generation evidence.
  attributes:
  - name: historyId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: searchExecutionId
    type: opaque identifier
    required: true
    unique: false
    references: Discovery.SearchExecution
  - name: queryContext
    type: retained normalized query context
    required: true
    unique: false
  - name: admissionSequence
    type: nonnegative integer
    required: true
    unique: false
    min: 0
  - name: completionSequence
    type: nonnegative integer
    required: true
    unique: false
    min: 0
  - name: clearBoundary
    type: opaque clear-control revision
    required: true
    unique: false
  - name: recordedAt
    type: server time
    required: true
    unique: false
  constraints:
  - At most one history record per owner and search execution.
  - Admission at or before the last cleared cutoff is suppressed even when completion arrives later.
  - Clear-control revision, pagination snapshot and admission cutoff have distinct meanings.
  relationships:
  - target: Account
    cardinality: many to one
    direction: outbound reference
    meaning: History owner.
  - target: Discovery.SearchExecution
    cardinality: zero or one to one
    direction: outbound reference
    meaning: Completed execution fact.
- name: Entitlement
  owner: UsageEntitlements
  description: Configured free/local allocation with administrative assignment provenance.
  attributes:
  - name: entitlementId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: allocation
    type: finite allowed actions and quantities
    required: true
    unique: false
  - name: assignmentSource
    type: actor, reason and approved policy references
    required: true
    unique: false
  - name: effectivePeriod
    type: server-defined period reference
    required: true
    unique: false
  - name: assignmentRevision
    type: opaque control revision
    required: true
    unique: false
  constraints:
  - An absent assignment still has a non-null initial read revision without creating an entitlement.
  - No browser value grants a role, allocation or paid tier.
  - Grant/revoke use the same owner-target assignment boundary.
  relationships:
  - target: Account
    cardinality: many to one
    direction: outbound reference
    meaning: Allocation target.
- name: UsageRecord
  owner: UsageEntitlements
  description: One recoverable accounting responsibility for one intended operation.
  attributes:
  - name: usageRecordId
    type: opaque identifier
    required: true
    unique: true
  - name: accountId
    type: opaque identifier
    required: true
    unique: false
    references: AccountAccess.Account.accountId
  - name: revision
    type: opaque revision
    required: true
    unique: false
  - name: operationOwner
    type: registered component
    required: true
    unique: false
  - name: operationReference
    type: stable operation identity
    required: true
    unique: false
  - name: requestFingerprint
    type: normalized intended action and server quantity
    required: true
    unique: false
  - name: periodReference
    type: acceptance-time server period
    required: true
    unique: false
  - name: accountingDisposition
    type: logical disposition
    required: true
    unique: false
    allowed_values:
    - reserved
    - committed
    - released
    - refunded
  - name: quantity
    type: nonnegative finite quantity
    required: true
    unique: false
    min: 0
  - name: policyReference
    type: approved accounting policy revision
    required: true
    unique: false
  - name: effectEvidence
    type: protected evidence reference
    required: false
    unique: false
  constraints:
  - Owner, operation and accounting key uniquely identify one effect.
  - Unknown is an observation state, not a fabricated ledger settlement.
  - Period rollover never silently moves an existing reservation; refund requires the agreed policy and evidence.
  relationships:
  - target: Account
    cardinality: many to one
    direction: outbound reference
    meaning: Accounting subject.
  - target: Entitlement
    cardinality: many to zero or one
    direction: outbound reference
    meaning: Policy-backed allocation applicable at acceptance.
```

## Entity summary

| Owner | Entities | Responsibility |
|---|---|---|
| AccountAccess | Account, AuthenticationSession, IdentityLink, IdentityChallenge, ConsentRecord, AccountLifecycleRequest | Current authority and lifecycle evidence. |
| Library | SavedPaper, SavedSearch, SearchHistory | Explicit references and completion history. |
| Personalization | PersonalSettings, BehaviorRecord, PersonalProfile | Explicit choices, permitted events and resettable projections. |
| UsageEntitlements | Entitlement, UsageRecord | Auditable allocation and one intended accounting effect. |

No entity here owns glossary entries, research drafts/messages, digest subscriptions, export approvals or PlatformControl credentials. Their current authority/lifecycle interactions cross the published contracts.
