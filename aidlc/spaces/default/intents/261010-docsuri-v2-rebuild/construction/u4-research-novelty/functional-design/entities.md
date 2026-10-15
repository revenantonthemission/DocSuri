# U4 — Research and novelty · Entity model

Unit: `u4-research-novelty`. Owner component: `ResearchWorkspace`.

This file is the source of truth for the unit's entity shapes. Behaviour
(ordered workflows and state transitions) is the source of truth in
`functional-spec.md`; decision logic is the source of truth in `rules.md`.
Entities owned by other components appear here only as references and are
marked `owned_by`.

```yaml
entities:
  - name: ResearchContext
    owned_by: ResearchWorkspace
    description: >
      A server-assigned private scope that binds an owner to the drafts, private
      attachments, sessions and novelty steps that share one permitted research
      context. It is a protocol resource, not a user-visible product feature, a
      subscription or a job, and it never appears as a public corpus identity.
    attributes:
      - name: researchContextId
        type: identifier
        required: true
        unique: true
        constraints: Server-assigned opaque value; never accepted from the browser.
      - name: accountId
        type: reference
        required: true
        references: Account
        constraints: Server-derived from the authenticated request context; C00 `ownerId`.
      - name: revision
        type: integer
        required: true
        constraints: C00 `revision`; monotonic per context identity.
      - name: purpose
        type: enum
        required: true
        allowed_values: [research, novelty]
        constraints: C00 `purpose`, required by `ResearchContextCreate`; the caller declares it and the server never infers it from content.
      - name: lifecycle
        type: enum
        required: true
        allowed_values: [active, deleting, deleted]
        defaults: active
        constraints: C00 `lifecycle`; a `deleted` context dominates later writes and late results.
      - name: deletionBoundary
        type: timestamp
        required: false
        constraints: Set when deletion is acknowledged; a set boundary dominates later writes and late results.
    entity_constraints:
      - Every dependent read, save, upload, submission and result resolves its own owner and context; a context reference is never sufficient authorization by itself.
    relationships:
      - entity: ResearchSession
        cardinality: one-to-many
        direction: ResearchContext owns ResearchSession
      - entity: DraftRevision
        cardinality: one-to-many
        direction: ResearchContext owns DraftRevision
      - entity: PrivateAttachment
        cardinality: one-to-many
        direction: ResearchContext owns PrivateAttachment

  - name: ResearchSession
    owned_by: ResearchWorkspace
    description: >
      One owner- and context-bound research conversation. Opening a session
      reveals committed turns and authoritative pending state; opening never
      submits work.
    attributes:
      - name: researchSessionId
        type: identifier
        required: true
        unique: true
        constraints: Server-assigned; owner and context are server-derived.
      - name: accountId
        type: reference
        required: true
        references: Account
        owned_by: AccountAccess
      - name: contextReference
        type: reference
        required: true
        references: ResearchContext
      - name: revision
        type: integer
        required: true
        constraints: C00 `revision`; monotonic per session identity.
      - name: committedTurnReferences
        type: reference-list
        required: true
        references: ResearchTurn
        constraints: Append-only; ordered by committed acceptance. C00 `turnIds`.
      - name: pendingJobReferences
        type: reference-list
        required: true
        constraints: Accepted jobs with pending or unknown state that reference this session. C00 `pendingJobIds`.
      - name: lifecycle
        type: enum
        required: true
        allowed_values: [active, deleting, deleted]
        defaults: active
        constraints: C00 `lifecycle`; a `deleted` session is terminal and rejects late writes and reads.
      - name: deletionBoundary
        type: timestamp
        required: false
        constraints: A durable tombstone is written before cleanup; a set boundary rejects late turn, draft and result publication.
    entity_constraints:
      - A deleted session cannot be reopened through a stale direct link or reappear through a stale list snapshot.
    relationships:
      - entity: ResearchTurn
        cardinality: one-to-many
        direction: ResearchSession owns ResearchTurn
      - entity: Account
        cardinality: many-to-one
        direction: ResearchSession references Account
        owned_by: AccountAccess

  - name: ResearchTurn
    owned_by: ResearchWorkspace
    description: >
      One accepted grounded question with its immutable input, scope snapshot,
      evidence and outcome. Turn and novelty identities are distinct.
    attributes:
      - name: researchTurnId
        type: identifier
        required: true
        unique: true
      - name: researchSessionId
        type: reference
        required: true
        references: ResearchSession
      - name: kind
        type: enum
        required: true
        allowed_values: [research-turn]
        constraints: Distinguishes this entity from novelty analysis and discussion jobs.
      - name: inputSnapshot
        type: structured
        required: true
        constraints: Immutable after acceptance; carries the question and the requested source scope.
      - name: inputHash
        type: digest
        required: true
        constraints: Hash of the normalized immutable input; a worker result must present the matching hash.
      - name: draftRevisionReference
        type: reference
        required: false
        references: DraftRevision
        constraints: Present only when the turn was submitted from a draft; identifies the exact consumed revision.
      - name: progress
        type: enum
        required: true
        allowed_values: [accepted, running, succeeded, failed]
        defaults: accepted
      - name: dispatchResponsibility
        type: structured
        required: true
        constraints: Recoverable dispatch obligation recorded atomically with acceptance.
      - name: evidenceReferences
        type: reference-list
        required: false
        references: EvidenceRecord
        constraints: Populated from actually accessible sources only.
      - name: outcome
        type: structured
        required: false
        constraints: Terminal prepared outcome or a typed failure; never a fabricated success.
      - name: usageRecordId
        type: reference
        required: false
        references: UsageRecord
        owned_by: UsageEntitlements
    entity_constraints:
      - One accepted turn consumes at most one draft revision, exactly the submitted one.
      - A turn may be read repeatedly but is never re-executed by a read, restore or reconnect.
    relationships:
      - entity: EvidenceRecord
        cardinality: one-to-many
        direction: ResearchTurn carries EvidenceRecord
      - entity: ResearchArtifact
        cardinality: one-to-one
        direction: ResearchTurn prepares ResearchArtifact

  - name: NoveltyAnalysis
    owned_by: ResearchWorkspace
    description: >
      One accepted topic- or manuscript-based novelty analysis. Distinct from a
      research turn and from its own discussion job.
    attributes:
      - name: noveltyAnalysisId
        type: identifier
        required: true
        unique: true
      - name: accountId
        type: reference
        required: true
        references: Account
        owned_by: AccountAccess
      - name: inputMode
        type: enum
        required: true
        allowed_values: [topic, manuscript]
      - name: inputSnapshot
        type: structured
        required: true
        constraints: Immutable after acceptance; a manuscript mode snapshot references an eligible private attachment.
      - name: inputHash
        type: digest
        required: true
      - name: draftRevisionReference
        type: reference
        required: false
        references: DraftRevision
      - name: progress
        type: enum
        required: true
        allowed_values: [accepted, running, cancel_requested, cancelled, succeeded, failed]
        defaults: accepted
      - name: dispatchResponsibility
        type: structured
        required: true
      - name: cancellationDisposition
        type: structured
        required: false
        constraints: Records the authority that decided the one winning terminal outcome.
      - name: artifactReferences
        type: reference-list
        required: false
        references: ResearchArtifact
      - name: usageRecordId
        type: reference
        required: false
        references: UsageRecord
        owned_by: UsageEntitlements
    entity_constraints:
      - Exactly one terminal outcome (cancelled, succeeded or failed) is ever recorded; no terminal state is overwritten or revived.
      - A cancelled analysis never starts or authorizes an export.
    relationships:
      - entity: ResearchArtifact
        cardinality: one-to-many
        direction: NoveltyAnalysis owns ResearchArtifact
      - entity: Account
        cardinality: many-to-one
        direction: NoveltyAnalysis references Account
        owned_by: AccountAccess

  - name: NoveltyDiscussion
    owned_by: ResearchWorkspace
    description: >
      One accepted discussion job bound to the same owner's eligible immutable
      novelty result. It carries its own durable acceptance, immutable input,
      progress and terminal outcome under the ResearchTurnOrDiscussion machine;
      it never reruns the analysis and never approves or initiates an export.
    attributes:
      - name: noveltyDiscussionId
        type: identifier
        required: true
        unique: true
      - name: accountId
        type: reference
        required: true
        references: Account
        owned_by: AccountAccess
      - name: contextReference
        type: reference
        required: true
        references: ResearchContext
      - name: kind
        type: enum
        required: true
        allowed_values: [novelty-discussion]
        constraints: Distinguishes this job from a research turn and from the novelty analysis it discusses.
      - name: sourceResultReference
        type: structured
        required: true
        constraints: Identifies the same owner's ready novelty result by its immutable artifactId/revision/contentHash tuple; eligibility is rechecked at acceptance.
      - name: inputSnapshot
        type: structured
        required: true
        constraints: Immutable after acceptance; carries the requested discussion scope.
      - name: inputHash
        type: digest
        required: true
        constraints: Hash of the normalized immutable input; a worker result must present the matching hash.
      - name: draftRevisionReference
        type: reference
        required: false
        references: DraftRevision
        constraints: Present only when the discussion was submitted from a draft; identifies the exact consumed revision (BR4.3 applies to this job too).
      - name: progress
        type: enum
        required: true
        allowed_values: [accepted, running, succeeded, failed]
        defaults: accepted
      - name: dispatchResponsibility
        type: structured
        required: true
        constraints: Recoverable dispatch obligation recorded atomically with acceptance.
      - name: artifactReferences
        type: reference-list
        required: false
        references: ResearchArtifact
      - name: usageRecordId
        type: reference
        required: false
        references: UsageRecord
        owned_by: UsageEntitlements
    entity_constraints:
      - Accepts only an eligible, ready, same-owner immutable novelty result; a missing, changed or revoked source refuses SOURCE_INELIGIBLE.
      - Neither reruns the analysis nor authorizes, prepares or initiates an export.
      - Exactly one terminal outcome (succeeded or failed) is ever recorded.
    relationships:
      - entity: ResearchArtifact
        cardinality: many-to-one
        direction: NoveltyDiscussion reads its source ResearchArtifact
      - entity: ResearchArtifact
        cardinality: one-to-many
        direction: NoveltyDiscussion owns its discussion ResearchArtifact
      - entity: Account
        cardinality: many-to-one
        direction: NoveltyDiscussion references Account
        owned_by: AccountAccess

  - name: ResearchArtifact
    owned_by: ResearchWorkspace
    description: >
      Immutable prepared output of one accepted turn or novelty job, plus the
      separate discussion artifacts bound to an eligible novelty result.
    attributes:
      - name: researchArtifactId
        type: identifier
        required: true
        unique: true
      - name: kind
        type: enum
        required: true
        allowed_values: [research-turn, novelty-analysis, novelty-discussion]
        constraints: Must match the accepted operation kind.
      - name: contextReference
        type: reference
        required: true
        references: ResearchContext
      - name: operationReference
        type: reference
        required: true
        references: ResearchTurn, NoveltyAnalysis, NoveltyDiscussion
        constraints: Identifies the accepted turn, novelty analysis or novelty discussion that prepared this artifact; the reference target is one of those three job entities, and the kind attribute must match it.
      - name: revision
        type: integer
        required: true
        constraints: Monotonic per artifact identity; new content becomes a new revision.
      - name: contentHash
        type: digest
        required: true
        constraints: Hash of the versioned canonical serialized prepared output; identifies the immutable bytes.
      - name: preparedContent
        type: structured
        required: true
      - name: discussion
        type: structured
        required: false
      - name: evidenceReferences
        type: reference-list
        required: false
        references: EvidenceRecord
      - name: availability
        type: enum
        required: true
        allowed_values: [ready, expired, deleted, unavailable]
        defaults: ready
      - name: expiresAt
        type: timestamp
        required: false
        constraints: Owner-scoped declared expiry; expiry is disclosed and never regenerates work.
    entity_constraints:
      - The tuple (researchArtifactId, revision, contentHash) never returns different bytes.
      - Eligibility for export is rechecked at read time and can change independently of the stored artifact.
    relationships:
      - entity: NoveltyAnalysis
        cardinality: many-to-one
        direction: ResearchArtifact belongs to NoveltyAnalysis
      - entity: ResearchTurn
        cardinality: many-to-one
        direction: ResearchArtifact belongs to ResearchTurn

  - name: NoveltyAssessment
    owned_by: ResearchWorkspace
    description: >
      The recorded method scale behind any optional novelty score. It binds a
      score to the method that produced it and to the evidence IDs it cites, so a
      score is never shown as an unexplained number and never as proof of
      scientific novelty.
    attributes:
      - name: noveltyAssessmentId
        type: identifier
        required: true
        unique: true
      - name: artifactReference
        type: reference
        required: true
        references: ResearchArtifact
        constraints: The novelty-analysis artifact this assessment belongs to.
      - name: methodScaleId
        type: identifier
        required: true
        constraints: Identity of the recorded method scale; an unrecorded scale cannot produce an assessment.
      - name: method
        type: structured
        required: true
        constraints: The recorded method description and version that produced the score.
      - name: minimum
        type: number
        required: true
      - name: maximum
        type: number
        required: true
        constraints: Greater than or equal to `minimum`.
      - name: score
        type: number
        required: true
        constraints: Must satisfy minimum <= score <= maximum.
      - name: evidenceReferences
        type: reference-list
        required: true
        references: EvidenceRecord
        constraints: The evidence IDs the score cites; an assessment without its evidence set is not rendered.
    entity_constraints:
      - A score outside [minimum, maximum] is invalid and is never rendered.
      - A score is rendered only with its method scale and evidence set, and is never presented as proof of scientific novelty.
    relationships:
      - entity: ResearchArtifact
        cardinality: many-to-one
        direction: NoveltyAssessment belongs to the novelty-analysis ResearchArtifact

  - name: EvidenceRecord
    owned_by: ResearchWorkspace
    description: >
      One claim or literal quotation produced or relied on by an accepted turn or
      novelty job, with the provenance needed to verify it. Retrieved or
      uploaded text is untrusted data, never instruction or authorization.
    attributes:
      - name: evidenceId
        type: identifier
        required: true
        unique: true
      - name: contextReference
        type: reference
        required: true
        references: ResearchContext
      - name: evidenceKind
        type: enum
        required: true
        allowed_values: [claim, quotation]
      - name: sourceIdentity
        type: structured
        required: true
        constraints: Identifies a public paper, a private attachment, or an owner-supplied web reference.
      - name: sourceVersion
        type: reference
        required: false
        references: PaperVersion
        owned_by: CorpusContent
        constraints: Required for public corpus evidence; a public source-only claim cannot cite an unread version.
      - name: location
        type: structured
        required: false
        constraints: Section, page, figure or anchor actually read; absent for an unread web reference.
      - name: quoteOrClaim
        type: text
        required: true
      - name: coverage
        type: enum
        required: true
        allowed_values: [complete, partial, insufficient]
        constraints: Partial and insufficient coverage are disclosed, never rendered as complete support.
      - name: provenance
        type: structured
        required: true
      - name: readState
        type: enum
        required: true
        allowed_values: [read, not-read]
        defaults: not-read
        constraints: A web reference stays not-read unless a permitted retrieval actually happened.
    entity_constraints:
      - A literal quotation requires source text, hash and location that were actually read.
      - Insufficient evidence yields abstention or a partial result, never invented support.
    relationships:
      - entity: ResearchTurn
        cardinality: many-to-one
        direction: EvidenceRecord belongs to ResearchTurn
      - entity: PaperVersion
        cardinality: many-to-one
        direction: EvidenceRecord references PaperVersion
        owned_by: CorpusContent

  - name: PrivateAttachment
    owned_by: ResearchWorkspace
    description: >
      One owner- and context-bound uploaded document and its derived assets.
      Private identity never resolves through public corpus routes.
    attributes:
      - name: privateAttachmentId
        type: identifier
        required: true
        unique: true
      - name: accountId
        type: reference
        required: true
        references: Account
        owned_by: AccountAccess
      - name: contextReference
        type: reference
        required: true
        references: ResearchContext
      - name: contentReference
        type: structured
        required: true
      - name: contentHash
        type: digest
        required: true
        constraints: Verified against the received bytes before extraction is attempted.
      - name: mediaType
        type: enum
        required: true
        allowed_values: [text/plain, application/pdf]
        constraints: An allowlist; other media are refused as unsupported.
      - name: byteSize
        type: integer
        required: true
        constraints: Bounded by the per-owner attachment cap; oversized input is refused before extraction.
      - name: assetReferences
        type: reference-list
        required: false
        constraints: Each asset read is authorized individually and never by path.
      - name: extractionDisposition
        type: enum
        required: true
        allowed_values: [pending, extracted, unsupported, malformed, truncated, protected, failed, deleted]
        defaults: pending
      - name: deletionBoundary
        type: timestamp
        required: false
    entity_constraints:
      - Extraction output is untrusted evidence and can never override owner permissions, secret handling or external-action approval.
      - No private attachment or asset is ever published to the public corpus.
    relationships:
      - entity: ResearchContext
        cardinality: many-to-one
        direction: PrivateAttachment belongs to ResearchContext
      - entity: Account
        cardinality: many-to-one
        direction: PrivateAttachment references Account
        owned_by: AccountAccess

  - name: DraftRevision
    owned_by: ResearchWorkspace
    description: >
      One immutable acknowledged saved revision of owner-written text. Editing
      creates another revision; a submission consumes exactly the submitted one.
      Durable behaviour is suspended with POLICY_UNRESOLVED until the retention,
      erasure, storage and shared-device policy is resolved.
    attributes:
      - name: draftRevisionId
        type: identifier
        required: true
        unique: true
      - name: accountId
        type: reference
        required: true
        references: Account
        owned_by: AccountAccess
      - name: contextReference
        type: reference
        required: true
        references: ResearchContext
      - name: kind
        type: enum
        required: true
        allowed_values: [research-question, novelty-topic, novelty-manuscript, novelty-discussion]
        constraints: C00 `DraftWrite.kind`/`DraftRevision.kind` spellings, unchanged; a submitted draft must match the accepted operation kind.
      - name: parentRevision
        type: reference
        required: false
        references: DraftRevision
        constraints: Null only for a new draft; the base revision for CAS.
      - name: revision
        type: integer
        required: true
      - name: contentHash
        type: digest
        required: true
        constraints: Hash of the exact text; a submission presents the matching hash.
      - name: text
        type: text
        required: true
      - name: saveAcknowledgement
        type: enum
        required: true
        allowed_values: [acknowledged, rejected]
        constraints: Only acknowledged revisions are recoverable; a failed or in-flight UI state promises nothing.
      - name: consumedOperationReference
        type: reference
        required: false
        constraints: Set when an accepted operation consumed this exact revision.
      - name: state
        type: enum
        required: true
        allowed_values: [acknowledged, consumed, discarded, expired, deleted]
        defaults: acknowledged
      - name: deletionBoundary
        type: timestamp
        required: false
    entity_constraints:
      - A consuming submission targets the exact revision; a concurrent newer acknowledged revision survives.
      - A stale discard cannot erase a newer edit, and a session tombstone rejects late draft saves.
    relationships:
      - entity: ResearchContext
        cardinality: many-to-one
        direction: DraftRevision belongs to ResearchContext
      - entity: Account
        cardinality: many-to-one
        direction: DraftRevision references Account
        owned_by: AccountAccess

  - name: JobSnapshot
    owned_by: ResearchWorkspace
    description: >
      The authoritative ordered view of one accepted job's progress returned to
      the owner, distinguishing acknowledged, pending, unknown and terminal work.
    attributes:
      - name: operationReference
        type: reference
        required: true
        constraints: The turn, novelty analysis or discussion job this snapshot describes.
      - name: kind
        type: enum
        required: true
        allowed_values: [research-turn, novelty-analysis, novelty-discussion]
      - name: progress
        type: enum
        required: true
        allowed_values: [accepted, running, cancel_requested, cancelled, succeeded, failed]
      - name: sequence
        type: integer
        required: true
        constraints: Monotonic; an older snapshot never overwrites a newer one.
      - name: artifactReference
        type: reference
        required: false
        references: ResearchArtifact
      - name: failureReason
        type: structured
        required: false
        constraints: Present only for typed failures; never a success stand-in.
    entity_constraints:
      - Worker facts are proposals; only the owning domain commits state, sequence and result visibility.

referenced_entities:
  - name: Account
    owned_by: AccountAccess
    role: Authenticated owner; current authority is checked independently of the stored reference.
  - name: PaperVersion
    owned_by: CorpusContent
    role: Exact public source version for public-corpus evidence; eligibility is rechecked, never assumed.
  - name: UsageRecord
    owned_by: UsageEntitlements
    role: Accounting for the intended accepted turn or novelty job; reconciled once per accepted operation.
  - name: ExecutionLease
    owned_by: execution mechanism
    role: Domain-scoped claim that a worker must hold to publish a completion fact.
```

## Entity set summary

U4 owns eleven entities. `ResearchContext` is the server-assigned private scope that
binds every draft, private attachment, session and novelty step to one owner and
one permitted context; it is deliberately not a user-visible feature. `ResearchSession`
and `ResearchTurn` carry the grounded-question lifecycle, `NoveltyAnalysis` carries
the distinct topic/manuscript analysis lifecycle, and `NoveltyDiscussion` carries
the separate discussion job bound to an eligible immutable result. `ResearchArtifact`
holds the immutable prepared output, and `NoveltyAssessment` records the method
scale behind any optional score so a score is never an unexplained number.
`EvidenceRecord` is the provenance record that makes every claim and literal
quotation verifiable, and its `readState` keeps an unread web reference from being
presented as evidence. `PrivateAttachment` and `DraftRevision` hold the owner's
private inputs and acknowledged text. `JobSnapshot` is the authoritative read model
for progress, so that pending, unknown and terminal work are never confused with a
successful result.

Owned elsewhere and referenced only: `Account` (AccountAccess), `PaperVersion`
(CorpusContent), `UsageRecord` (UsageEntitlements) and the execution mechanism's
lease. The unit never stores another component's authority as its own.

Three structural invariants recur across the model and are enforced by the rules
in `rules.md`: owner **and** context are checked on every read and write; the
`(artifactId, revision, contentHash)` tuple is immutable; and every terminal
outcome is decided once, with tombstones and cancellations dominating late work.
