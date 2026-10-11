# U1 logical entity model

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`.

## Scope and source of truth

This YAML is authoritative for logical data shapes and relationships. The [functional specification](functional-spec.md) owns ordered workflows and state transitions; [business rules](rules.md) own decisions. Shapes elaborate the approved owners in the [domain catalogue](../../../inception/domain-design/components.md), [U1 boundary](../../../inception/units-generation/unit-of-work.md), [requirements](../../../inception/requirements-analysis/requirements.md) and [confirmed proposal](functional-design-questions.md). They do not select physical stores, frameworks or migration. A shape can be transient or embedded and does not imply a new table or component.

Every attribute states its logical type, required/unique flags and constraints. `unique: false` means not individually unique; composite uniqueness is stated on the entity. Optional fields have `required: false`. Values have no implicit default except an explicit `default`. Input sizes, durations, retention and capacity have no guessed numeric minima/maxima: finite validated policy must exist before the affected operation is enabled. An opaque revision is compared for equality; an ordered fence/sequence is owner-issued and monotonic.

## Authoritative entity definitions

```yaml
unit: u1-integrated-paper-journey
model_kind: logical
entities:
  - name: "Account"
    owner: "AccountAccess"
    description: "Authoritative local account identity and current ability to use protected capabilities."
    attributes:
      - {"name":"accountId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"profile","type":"bounded account profile","required":true,"unique":false,"constraints":["Validated identity fields; public responses avoid account enumeration."]}
      - {"name":"verification","type":"verification disposition","required":true,"unique":false,"allowed":["unverified","verified"],"constraints":[]}
      - {"name":"lifecycle","type":"account lifecycle disposition","required":true,"unique":false,"constraints":["Allowed transitions follow AccountAccess policy; revoked access is distinct from erasure or reactivation eligibility."]}
      - {"name":"authorityRevision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
      - {"name":"credentialReference","type":"protected credential reference","required":true,"unique":false,"constraints":["Never expose credential material to browser, telemetry or other owners."]}
    constraints: ["Public signup cannot select administrator or operator authority.","Authority revision changes fence old sessions and work at required effects."]
    relationships: []
  - name: "AuthenticationSession"
    owner: "AccountAccess"
    description: "Protected login session carrying an authenticated identity, not independent account authority."
    attributes:
      - {"name":"sessionId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"authorityRevision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
      - {"name":"authenticationContext","type":"verified authentication context","required":true,"unique":false,"constraints":["Server established; includes required authentication strength and issuance context."]}
      - {"name":"expiresAt","type":"authoritative instant","required":true,"unique":false,"constraints":["Chosen under approved session policy."]}
      - {"name":"revocation","type":"revocation disposition","required":true,"unique":false,"allowed":["current","revoked"],"constraints":[]}
    constraints: ["An unexpired token still requires current account authority.","Session material is protected; browser-supplied account/role fields never authenticate."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Every session belongs to exactly one account."}
  - name: "IdentityChallenge"
    owner: "AccountAccess"
    description: "Single-purpose verification challenge and recoverable delivery status."
    attributes:
      - {"name":"challengeId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"purpose","type":"challenge purpose","required":true,"unique":false,"constraints":["U1 uses email verification; later purposes remain separately scoped."]}
      - {"name":"verificationBinding","type":"protected intended-identity binding","required":true,"unique":false,"constraints":["Binds exact intended address, account, purpose and authority revision."]}
      - {"name":"useDisposition","type":"challenge disposition","required":true,"unique":false,"allowed":["pending","consumed","expired","revoked"],"constraints":[]}
      - {"name":"expiresAt","type":"authoritative instant","required":true,"unique":false,"constraints":["Finite approved challenge policy required."]}
      - {"name":"deliveryDisposition","type":"delivery status","required":true,"unique":false,"allowed":["pending","acknowledged","failed","unknown"],"constraints":[]}
      - {"name":"credentialReference","type":"protected challenge proof reference","required":true,"unique":false,"constraints":["Neither challenge receipt nor delivery success proves verification."]}
    constraints: ["Consume valid challenge once under current binding; expired/replayed proof cannot authenticate.","Unknown email delivery is reconciled; local test sink proves only a local path."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Challenge identifies one intended account."}
  - name: "ConsentRecord"
    owner: "AccountAccess"
    description: "Current decision for a defined processing purpose."
    attributes:
      - {"name":"consentId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"purpose","type":"registered purpose identifier","required":true,"unique":false,"constraints":["Meaning and required consent are fixed by resolved obligations."]}
      - {"name":"decision","type":"consent decision","required":true,"unique":false,"allowed":["granted","denied","withdrawn"],"constraints":[]}
      - {"name":"revision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
      - {"name":"effectiveAt","type":"authoritative instant","required":true,"unique":false,"constraints":["Effect checks use current policy and decision, not only accepted snapshot."]}
    constraints: ["Unique current decision per account and purpose; preserve lawful audit per approved policy."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Consent belongs to one account."}
  - name: "AccountLifecycleRequest"
    owner: "AccountAccess"
    description: "Coordinates revocation and owner-specific cleanup acknowledgements without writing other owners' data."
    attributes:
      - {"name":"lifecycleRequestId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"requestedAction","type":"supported lifecycle action","required":true,"unique":false,"constraints":["Only actions enabled under resolved retention/recovery policy."]}
      - {"name":"policyReference","type":"immutable policy revision","required":true,"unique":false,"constraints":["Required before policy-dependent cleanup/reactivation."]}
      - {"name":"participantManifest","type":"LifecycleParticipantManifest","required":true,"unique":false,"constraints":["Snapshot includes every installed owner with applicable persisted state."]}
      - {"name":"participantDispositions","type":"owner acknowledgement map","required":true,"unique":false,"constraints":["Pending, failed and unknown stay distinct from completed disposition."]}
      - {"name":"completionEvidence","type":"owner disposition references","required":false,"unique":false,"constraints":["Must name all required participants and verified outcome."]}
    constraints: ["Immediate access revocation and eventual cleanup are separate facts.","Missing acknowledgement cannot count as complete; irreversible erasure cannot promise reactivation."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Request coordinates lifecycle for one account."}
  - name: "Paper"
    owner: "CorpusContent"
    description: "Canonical public-paper identity, distinct from saved references and individual source versions."
    attributes:
      - {"name":"paperId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"canonicalReferences","type":"nonempty source identity set","required":true,"unique":false,"constraints":["Every alias carries verified equivalence/provenance; no arbitrary redirect."]}
      - {"name":"metadata","type":"bounded bibliographic fields","required":true,"unique":false,"constraints":["Unknown fields remain unknown; retain permitted identity metadata."]}
      - {"name":"currentVersionReference","type":"opaque reference","required":false,"unique":false,"references":"PaperVersion","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"availabilityDisposition","type":"public-paper disposition","required":true,"unique":false,"constraints":["Distinguish eligible metadata, withdrawal, restriction and unresolved identity."]}
    constraints: ["Canonical aliases do not change the meaning of a pinned version.","CorpusContent alone changes public identity and withdrawal disposition."]
    relationships:
      - {"target":"PaperVersion","cardinality":"one-to-many","direction":"outbound","description":"A paper has zero or more known versions; currentVersionReference selects at most one of its own."}
  - name: "PaperVersion"
    owner: "CorpusContent"
    description: "Immutable source/version binding with separately evolving eligibility."
    attributes:
      - {"name":"paperVersionId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"paperId","type":"opaque reference","required":true,"unique":false,"references":"Paper","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"sourceIdentity","type":"source-qualified identifier","required":true,"unique":false,"constraints":["Exact source and version; unique in that source."]}
      - {"name":"versionLabel","type":"source version label","required":true,"unique":false,"constraints":["Pinned for P1/P2 fixtures, never silently replaced by current."]}
      - {"name":"provenance","type":"source/hash acquisition evidence","required":true,"unique":false,"constraints":["Binds source content hash and lawful acquisition evidence."]}
      - {"name":"eligibilityDecision","type":"purpose-scoped permission decision","required":true,"unique":false,"constraints":["Read, store, translate and model processing permissions can differ; include revision and reason."]}
      - {"name":"contentReference","type":"opaque reference","required":false,"unique":false,"references":"PublicContent","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
    constraints: ["Unique sourceIdentity plus versionLabel; current eligibility may deny previously permitted content."]
    relationships:
      - {"target":"Paper","cardinality":"many-to-one","direction":"outbound","description":"Version belongs to exactly one canonical paper."}
      - {"target":"PublicContent","cardinality":"one-to-zero-or-one","direction":"outbound","description":"Version resolves at most one current authoritative content representation."}
  - name: "PublicContent"
    owner: "CorpusContent"
    description: "Eligible structured public content and its bounded asset catalogue."
    attributes:
      - {"name":"publicContentId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"paperVersionId","type":"opaque reference","required":true,"unique":false,"references":"PaperVersion","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"sections","type":"ordered bounded section records","required":true,"unique":false,"constraints":["Stable anchors, text and source locations; untrusted content cannot execute instructions."]}
      - {"name":"assetReferences","type":"scoped figure/asset records","required":true,"unique":false,"constraints":["Identity and allowed access bound to this content; no unrestricted path resolution."]}
      - {"name":"buildDisposition","type":"content disposition","required":true,"unique":false,"allowed":["absent","building","available","unsupported","failed","withdrawn","restricted"],"constraints":[]}
      - {"name":"eligibilityRevision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
      - {"name":"contentHash","type":"immutable representation digest","required":true,"unique":false,"constraints":["Changed content is a new identified representation, not hidden mutation."]}
      - {"name":"projectionBinding","type":"published projection identity and generation","required":false,"unique":false,"constraints":["CorpusContent is sole publisher/rebuilder/withdrawer; missing or stale is explicit."]}
    constraints: ["Availability does not independently grant access.","Malformed content/asset failures are bounded and never substitute another source."]
    relationships:
      - {"target":"PaperVersion","cardinality":"many-to-one","direction":"outbound","description":"Every representation resolves its exact source version."}
  - name: "PersonalSettings"
    owner: "Personalization"
    description: "Explicit owner defaults for supported search/assistance plus safe entry state."
    attributes:
      - {"name":"settingsId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"searchDefaults","type":"supported default values","required":true,"unique":false,"constraints":["Apply only when user has not explicitly selected the action's value."]}
      - {"name":"assistanceDefaults","type":"supported assistance default values","required":true,"unique":false,"constraints":["Snapshot at explicit submission; never rewrite an accepted request."]}
      - {"name":"onboarding","type":"recorded entry disposition","required":true,"unique":false,"constraints":["Absent optional enrichment permits default/manual entry; full controls remain U2."]}
      - {"name":"revision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
    constraints: ["Unique settings record per account; failed/conflicting writes preserve prior committed settings."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Settings belong to one account."}
  - name: "BehaviorRecord"
    owner: "Personalization"
    description: "Consent-governed activity fact supporting recent-paper identity and ordering."
    attributes:
      - {"name":"behaviorRecordId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"paperVersionId","type":"opaque reference","required":true,"unique":false,"references":"PaperVersion","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"activity","type":"bounded activity fact","required":true,"unique":false,"constraints":["Approved activity type, originating effect identity and authoritative ordering metadata."]}
      - {"name":"consentRevision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
      - {"name":"erasureDisposition","type":"processing boundary","required":true,"unique":false,"constraints":["Delayed facts cannot recreate opted-out, erased or reset projections."]}
    constraints: ["Retain only under resolved behavior policy; cold-start absence is a usable default.","Deduplicate activity by originating effect; recent views recheck source eligibility."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Activity belongs to one account."}
      - {"target":"PaperVersion","cardinality":"many-to-one","direction":"outbound","description":"Activity preserves exact version."}
  - name: "SearchExecution"
    owner: "Discovery"
    description: "Submitted query and authoritative retrieval outcome; transient anonymous scope never becomes an account."
    attributes:
      - {"name":"searchExecutionId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":false,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"queryContext","type":"QueryContext","required":true,"unique":false,"constraints":["Frozen at explicit submission."]}
      - {"name":"resultWindow","type":"ordered paper/version references and cursor","required":true,"unique":false,"constraints":["Bound to source snapshot; includes mode actually used and result disposition."]}
      - {"name":"sourceSnapshot","type":"projection generation and retrieval context","required":true,"unique":false,"constraints":["Stable snapshot or explicit changed/expired response."]}
      - {"name":"degradation","type":"truthful outcome limitations","required":true,"unique":false,"constraints":["Distinguish complete, partial, fallback and unavailable; never infer no match from failure."]}
      - {"name":"historyEffectReference","type":"durable completed-search fact reference","required":false,"unique":false,"constraints":["Present only for qualifying authenticated search under applicable current policy."]}
    constraints: ["Anonymous search receives no private history, settings or library ownership.","History delivery belongs to Discovery until consumed by Library; replay keeps original fact identity."]
    relationships:
      - {"target":"Account","cardinality":"many-to-zero-or-one","direction":"outbound","description":"Only authenticated qualifying search has an account."}
      - {"target":"PaperVersion","cardinality":"many-to-many","direction":"outbound","description":"Result references preserve source version without owning it."}
  - name: "SavedPaper"
    owner: "Library"
    description: "Owner's durable saved identity/version and truthful changed-source disposition."
    attributes:
      - {"name":"savedPaperId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"paperId","type":"opaque reference","required":true,"unique":false,"references":"Paper","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"paperVersionId","type":"opaque reference","required":true,"unique":false,"references":"PaperVersion","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"savedMetadata","type":"permitted identity snapshot","required":true,"unique":false,"constraints":["Enough to identify a withdrawn/unavailable reference without retaining prohibited content."]}
      - {"name":"sourceDisposition","type":"current resolved source disposition","required":true,"unique":false,"constraints":["Canonical alias verified; withdrawn/missing/restricted never becomes unrelated content."]}
      - {"name":"revision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
      - {"name":"mutationReceipt","type":"OperationReceipt","required":true,"unique":false,"constraints":["Durable acknowledgement and uncertain replay use the same intended operation."]}
    constraints: ["Unique active entry per account and intended paper/version save key; repeat save returns same intended entry.","Removal preserves required replay/tombstone evidence under approved retention; no silent recreation by old commands."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Saved entry belongs to one account."}
      - {"target":"Paper","cardinality":"many-to-one","direction":"outbound","description":"References canonical identity without changing it."}
      - {"target":"PaperVersion","cardinality":"many-to-one","direction":"outbound","description":"Revisit preserves the version the user saved."}
  - name: "SavedSearch"
    owner: "Library"
    description: "Owner's acknowledged query/refinements for explicit later rerun."
    attributes:
      - {"name":"savedSearchId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"queryContext","type":"QueryContext","required":true,"unique":false,"constraints":["Stored canonical intent, supported refinements/mode/order."]}
      - {"name":"label","type":"bounded Unicode text","required":true,"unique":false,"constraints":["Display text does not alter query identity."]}
      - {"name":"revision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
      - {"name":"mutationReceipt","type":"OperationReceipt","required":true,"unique":false,"constraints":["Same logical save cannot create unintended duplicate entries."]}
    constraints: ["Unique active saved query for account plus normalized query context; alternate display labels do not duplicate intent.","Loading or listing a saved query does not execute it."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Saved query belongs to one account."}
  - name: "SearchHistory"
    owner: "Library"
    description: "Deduplicated qualifying completed-search history constrained by a clear boundary."
    attributes:
      - {"name":"historyId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"searchExecutionId","type":"opaque reference","required":true,"unique":false,"references":"SearchExecution","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"queryContext","type":"QueryContext","required":true,"unique":false,"constraints":["Immutable submitted context from authenticated completed-search fact."]}
      - {"name":"clearBoundary","type":"HistoryClearBoundary","required":true,"unique":false,"constraints":["Owner monotonic clear generation and fact eligibility marker prevent late replay resurrection."]}
      - {"name":"recordedAt","type":"authoritative instant","required":true,"unique":false,"constraints":["Stable tie-break uses history identity."]}
      - {"name":"revision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
    constraints: ["Unique account plus searchExecutionId within eligible history boundary.","Clear affects only history and its late-fact eligibility, never saved papers/searches."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"History belongs to one account."}
      - {"target":"SearchExecution","cardinality":"many-to-one","direction":"outbound","description":"Each row derives from one original completed execution."}
  - name: "Entitlement"
    owner: "UsageEntitlements"
    description: "Authoritative applicable free/local allocation and assignment provenance."
    attributes:
      - {"name":"entitlementId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"allocation","type":"bounded resource policy","required":true,"unique":false,"constraints":["Approved units, permitted actions and finite bounds; unknown is not unlimited."]}
      - {"name":"assignmentSource","type":"authorized assignment reference","required":true,"unique":false,"constraints":["Client cannot grant or select administrative tier."]}
      - {"name":"revision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
      - {"name":"effectivePeriod","type":"policy period with time basis","required":true,"unique":false,"constraints":["Approved reset/time-zone semantics; no assumed daily boundary."]}
    constraints: ["Every permitted allocation remains within $0 policy; no paid fallback is enabled.","U1 consumes applicable allocation; complete tier administration remains later work."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Allocation applies to one account."}
  - name: "UsageRecord"
    owner: "UsageEntitlements"
    description: "Single accounting authority for a logical operation's reservation and settlement."
    attributes:
      - {"name":"usageRecordId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"operationOwner","type":"registered component name","required":true,"unique":false,"constraints":["PaperAssistance for U1 understanding."]}
      - {"name":"operationReference","type":"opaque reference","required":true,"unique":false,"references":"AssistanceJob","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"periodReference","type":"immutable accounting-period binding","required":true,"unique":false,"constraints":["Pinned at admission under approved policy; reset cannot double debit."]}
      - {"name":"accountingDisposition","type":"reservation/settlement disposition","required":true,"unique":false,"allowed":["reserved","settlement_pending","committed","released"],"constraints":[]}
      - {"name":"policyReference","type":"immutable accounting policy revision","required":true,"unique":false,"constraints":["Defines charge, failure release/refund and reset semantics before enablement."]}
      - {"name":"reservationBinding","type":"immutable operation/input/resource-unit binding","required":true,"unique":false,"constraints":["Unique owner plus operation; amount and unit finite and policy-defined."]}
      - {"name":"revision","type":"revision token","required":true,"unique":false,"constraints":["Owner issued; equality precondition; never synthesized or silently replaced with latest."]}
    constraints: ["One intended accounting effect per operationOwner plus operationReference; duplicate settlement returns original receipt.","Never release an uncertain reservation merely because a timeout elapsed; reconcile authoritative acceptance/outcome.","Job/result commit and accounting settlement may be recoverably coordinated without a cross-owner transaction."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Reservation and debit belong to one account."}
      - {"target":"AssistanceJob","cardinality":"one-to-zero-or-one","direction":"outbound","description":"Reservation can precede acceptance; same operation identity resolves accepted job or definitive rejection."}
  - name: "AssistanceJob"
    owner: "PaperAssistance"
    description: "Durably accepted owner-bound summary/translation operation with recoverable execution responsibility."
    attributes:
      - {"name":"assistanceJobId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"accountId","type":"opaque reference","required":true,"unique":false,"references":"Account","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"paperVersionId","type":"opaque reference","required":true,"unique":false,"references":"PaperVersion","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"requestSnapshot","type":"immutable intended request","required":true,"unique":false,"constraints":["Action, option vocabulary revision, requested language/level, source content hash, eligible input revision and source scope."]}
      - {"name":"glossaryRevision","type":"optional acknowledged glossary snapshot reference","required":false,"unique":false,"constraints":["U1 does not add glossary editing; absent is explicit."]}
      - {"name":"operationReceipt","type":"OperationReceipt","required":true,"unique":false,"constraints":["Owner/kind/key/input bind original acceptance; replay never restarts terminal work."]}
      - {"name":"progress","type":"authoritative business snapshot","required":true,"unique":false,"constraints":["State accepted/running/succeeded/failed; owner sequence, business revision, phase and safe failure reason."]}
      - {"name":"dispatchResponsibility","type":"durable execution/recovery obligation","required":true,"unique":false,"constraints":["Accepted work persists until authoritative terminal outcome; mechanism cannot be no-op."]}
      - {"name":"executionClaim","type":"ExecutionClaim","required":false,"unique":false,"constraints":["Current attempt metadata is owned only here."]}
      - {"name":"payloadBinding","type":"PayloadBinding","required":true,"unique":false,"constraints":["Immutable request retrieval requires current claim and source/account authority."]}
      - {"name":"outcome","type":"result or terminal failure binding","required":false,"unique":false,"constraints":["Success requires validated durable prepared result; no unsupported cancellation state."]}
      - {"name":"usageRecordId","type":"opaque reference","required":true,"unique":false,"references":"UsageRecord","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"usageSettlementObligation","type":"durable desired usage outcome","required":true,"unique":false,"constraints":["Result/terminal commit records one settlement intent; retries reconcile original UsageRecord."]}
    constraints: ["Owner+operation kind+idempotency identity uniquely bind normalized input hash.","Claim renewal revision is separate from business progress revision.","Replaced, expired or revoked claims cannot mutate progress/results or release/commit accounting.","Terminal progress cannot regress; result availability can later expire independently."]
    relationships:
      - {"target":"Account","cardinality":"many-to-one","direction":"outbound","description":"Job belongs to one current-authority account."}
      - {"target":"PaperVersion","cardinality":"many-to-one","direction":"outbound","description":"Job binds exact source version."}
      - {"target":"UsageRecord","cardinality":"one-to-one","direction":"outbound","description":"Every accepted job has one original reservation/settlement identity."}
      - {"target":"AssistanceResult","cardinality":"one-to-zero-or-one","direction":"outbound","description":"Success has exactly one prepared result; other states have none published."}
  - name: "AssistanceResult"
    owner: "PaperAssistance"
    description: "Immutable prepared content bound to one successful intended assistance operation."
    attributes:
      - {"name":"assistanceResultId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"assistanceJobId","type":"opaque reference","required":true,"unique":false,"references":"AssistanceJob","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"sourceBinding","type":"exact owner/operation/paper/version/input binding","required":true,"unique":false,"constraints":["Matches accepted request content hash, options and glossary snapshot."]}
      - {"name":"preparedContent","type":"validated source-associated output","required":true,"unique":false,"constraints":["Useful summary or supported translation, safe content and source locations."]}
      - {"name":"coverage","type":"evidence scope and limitations","required":true,"unique":false,"constraints":["Partial coverage and uncertainty disclosed; unsupported output cannot be success."]}
      - {"name":"availability","type":"result availability disposition","required":true,"unique":false,"allowed":["retained","expired","withdrawn","restricted"],"constraints":[]}
      - {"name":"provenance","type":"generation/validation evidence","required":true,"unique":false,"constraints":["Actual free/local model/configuration and immutable input/output digests; private material protected."]}
    constraints: ["Unique assistanceJobId; reads never generate output, debit usage or extend retention implicitly.","Availability/eligibility is checked on every read and may deny content after historical job success."]
    relationships:
      - {"target":"AssistanceJob","cardinality":"many-to-one","direction":"outbound","description":"Result cannot be detached from its original job."}
  - name: "CapabilityObservation"
    owner: "ServiceOperations"
    description: "Evidence-qualified availability/resource observation for an installed capability."
    attributes:
      - {"name":"capabilityObservationId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"capability","type":"registered capability identity","required":true,"unique":false,"constraints":["Bound to actual module and declared required checks."]}
      - {"name":"observedAt","type":"authoritative observation instant","required":true,"unique":false,"constraints":["Freshness policy required; unknown/stale explicit."]}
      - {"name":"evidenceReference","type":"safe evidence locator","required":true,"unique":false,"constraints":["No credentials or unnecessary private text."]}
      - {"name":"availability","type":"capability disposition","required":true,"unique":false,"allowed":["ready","degraded","unavailable","unknown","stale","not_installed"],"constraints":[]}
      - {"name":"limitations","type":"bounded evidence limitations","required":true,"unique":false,"constraints":["Observed values distinguish estimates, unknowns and failed checks."]}
    constraints: ["Process liveness cannot imply healthy storage, model work or complete parity."]
    relationships: []
  - name: "ServiceIncident"
    owner: "ServiceOperations"
    description: "Safe correlation and reproducible diagnosis/recovery record."
    attributes:
      - {"name":"serviceIncidentId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"affectedCapabilities","type":"registered capability identities","required":true,"unique":false,"constraints":["Name affected outcome, not just process."]}
      - {"name":"correlationReferences","type":"safe operation/evidence identifiers","required":true,"unique":false,"constraints":["Authorized views only; no secret or private-content dumping."]}
      - {"name":"diagnosis","type":"bounded observation and causal evidence","required":true,"unique":false,"constraints":["Separate observed fact from hypothesis."]}
      - {"name":"recoveryActions","type":"authorized owner-procedure outcomes","required":true,"unique":false,"constraints":["Invoke domain authority; do not rewrite another owner's state."]}
      - {"name":"verificationEvidence","type":"post-recovery user/domain checks","required":true,"unique":false,"constraints":["An attempted repair or restarted process is not verified recovery."]}
    constraints: ["Recording or telemetry failure remains visible; retention/access policy required before storing affected evidence."]
    relationships: []
  - name: "NavigationContext"
    owner: "WebWorkspace"
    description: "Untrusted presentation state for coherent navigation, distinct from persisted business facts."
    attributes:
      - {"name":"navigationContextId","type":"opaque identifier","required":true,"unique":true,"constraints":["Stable and owner allocated; identifiers do not grant authority."]}
      - {"name":"view","type":"supported view identifier","required":true,"unique":false,"constraints":["Only registered routes/capabilities."]}
      - {"name":"queryContext","type":"editable and submitted query contexts","required":false,"unique":false,"constraints":["Separate form edits, submitted request identity and displayed snapshot."]}
      - {"name":"selectedPaperVersion","type":"opaque reference","required":false,"unique":false,"references":"PaperVersion","constraints":["Resolve through authoritative owner; never infer current access from stored identity."]}
      - {"name":"returnLocation","type":"validated local destination","required":false,"unique":false,"constraints":["No external redirect or automatic mutation replay."]}
      - {"name":"focusTarget","type":"logical focus restoration target","required":false,"unique":false,"constraints":["Accessible fallback if prior target no longer exists."]}
      - {"name":"appearance","type":"appearance choice","required":true,"unique":false,"allowed":["light","dark","system"],"default":"system","constraints":[]}
      - {"name":"accountBoundary","type":"ephemeral verified presentation partition","required":false,"unique":false,"constraints":["Clear private rendering, subscriptions and cached responses on logout/switch; never authentication proof."]}
    constraints: ["Browser state cannot authorize private content, mutation or worker activity.","Storage failure does not claim preference persistence; all appearance modes remain usable."]
    relationships:
      - {"target":"PaperVersion","cardinality":"many-to-zero-or-one","direction":"outbound","description":"Selected reader retains exact version context."}
value_objects:
  - {"name":"QueryContext","owner":"Discovery","fields":["queryText: bounded Unicode text","filters: supported typed refinements","mode: supported lexical/semantic choice","order: supported stable ordering","normalizationRevision: approved interpretation version"],"constraints":["Server validation and normalized identity preserve meaningful user intent; bounds selected before enablement."]}
  - {"name":"OperationReceipt","owner":"the entity's domain owner","fields":["logicalOperationId: stable intended-operation identity","operationKind: registered action","ownerId: trusted account identity","inputHash: canonical submitted-intent digest including expected revision","expectedRevision: exact owner token, or null only for declared create-if-absent","outcome: rejected, accepted/committed or unknown reconciliation disposition","outcomeReference: original authoritative object/receipt"],"constraints":["Same key plus same input returns original outcome after current authorization; different input conflicts.","Transport correlation is separate; terminal retry cannot allocate new work implicitly."]}
  - {"name":"ExecutionClaim","owner":"PaperAssistance","fields":["operationId: original AssistanceJob","workerPrincipal: authenticated domain-scoped execution actor","leaseId: unique claim identity","fence: owner-issued monotonically increasing replacement generation","attempt: owner-issued execution attempt","inputHash: original intended payload binding","expiresAt: authoritative claim expiry","leaseRevision: owner-issued renewal precondition distinct from job revision"],"constraints":["Atomic acquisition/reclaim allows only one current claim; renew cannot restore an expired/replaced claim.","Finite lease/retry policy and authoritative time precede enabling execution; no worker-supplied fence authority."]}
  - {"name":"PayloadBinding","owner":"PaperAssistance","fields":["payloadReference: protected immutable payload locator","operationId: original job","inputHash: intended input digest","sourceContentHash: exact permitted content representation","sourceEligibilityRevision: admitted revision, rechecked when used","optionsRevision: supported option snapshot"],"constraints":["Reference and account ID are not bearer credentials.","Current worker principal, claim/fence, job, input and account/source permission all match before payload release."]}
  - {"name":"HistoryClearBoundary","owner":"Library","fields":["generation: monotonically advancing owner boundary","eligibleAfter: authority-defined search fact cut","revision: clear-operation revision","clearReceipt: original OperationReceipt"],"constraints":["Clear atomically advances boundary with visibility; qualifying late facts cannot reappear after clear.","Compare fact's captured eligibility boundary, not delayed delivery timestamp."]}
  - {"name":"LifecycleParticipantManifest","owner":"AccountAccess","fields":["manifestRevision: installed-owner version","participants: required owner and supported action pairs","ownerDispositions: acknowledgement references for the same lifecycleRequestId"],"constraints":["Registration before any owner persists account-linked data; mandatory participant absent blocks completion.","Host supplies registrations; AccountAccess owns coordination and each participant owns disposition."]}
  - {"name":"CapabilityPolicy","owner":"the capability's existing domain owner","fields":["policyRevision: immutable approved policy","inputBounds: finite supported input limits","admissionBounds: finite concurrency/work/storage allowances","timeoutAndRetry: finite durations, retry classification, attempts and recovery responsibility","retentionAndDeletion: resolved policy where applicable","resourceEvidence: measured local capacity or verified sustainable free terms"],"constraints":["Unset values mean unresolved/unavailable, not zero, unlimited or a guessed default.","No payment activation or hidden fallback; numbers are chosen from evidence in later design."]}
```

## Entity summary

| Owner | U1 entity shapes | Responsibility |
| --- | --- | --- |
| AccountAccess | Account, AuthenticationSession, IdentityChallenge, ConsentRecord, AccountLifecycleRequest | Identity, current authority, verified entry, lifecycle coordination |
| CorpusContent | Paper, PaperVersion, PublicContent | Canonical/source identity, eligible content and projection publication |
| Personalization | PersonalSettings, BehaviorRecord | Explicit defaults and permitted recent activity |
| Discovery | SearchExecution | Submitted query, stable result window and recoverable history fact |
| Library | SavedPaper, SavedSearch, SearchHistory | Acknowledged owner references and history boundaries |
| UsageEntitlements | Entitlement, UsageRecord | Resource admission, unique reservation and accounting settlement |
| PaperAssistance | AssistanceJob, AssistanceResult | Accepted work, current execution claim, prepared output and recovery |
| ServiceOperations | CapabilityObservation, ServiceIncident | Truthful readiness and verified diagnosis/recovery |
| WebWorkspace | NavigationContext | Non-authoritative presentation context |

The 21 shapes are U1 contributions to the existing catalogue. Seven supporting value shapes stay embedded under their named owners; they introduce no competing identity, execution, projection or accounting authority. All foreign references describe identity relationships rather than permission or direct storage access.

## Ownership and consistency constraints

A successful assistance commit binds one prepared result and a durable usage-settlement obligation. UsageEntitlements settles the uniquely keyed original reservation idempotently. A crash between those owner commits leaves recoverable pending settlement; it cannot authorize a second debit or cause an uncertain reservation to be released. No cross-component atomic storage transaction is assumed. Before acceptance, reservation/operation identity is durable enough to reconcile a crash into the original accepted job or an authoritative rejection and policy-allowed release.

Search history uses the original completed-search fact and its captured clear eligibility boundary. Library preserves that owner boundary even when no history rows remain; it is owner metadata, not an extra business authority. A delayed delivery timestamp cannot bypass a later clear. Corpus changes can alter current visibility without changing the saved identity or successful job's historical outcome. Private records with no verified owner are rejected or quarantined for controlled maintenance, never placed in a public bucket.

## Deferred detail and evidence prerequisites

Complete account controls, policy-dependent cleanup/reactivation, enrichment and glossary variants retain their later-unit assignments. Research sessions, private attachments and durable research/manuscript drafts, including allocation and restart rediscovery, remain ResearchWorkspace/U4 and are absent from this U1 model. This does not remove those release requirements.

Contract R-01 and R-03 need coherent formal contract bindings before code; design and schema agreement do not close executable findings. Source/model permissions, data authority and recoverable backups, lawful retention/deletion, available free/local capacity and finite execution/accounting policy still gate affected implementation. Existing users/data are not reset or migrated to make a synthetic demonstration pass.

