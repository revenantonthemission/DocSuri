# U3 paper and corpus capabilities — entity model

The YAML is authoritative. Entities elaborate the confirmed [questions](functional-design-questions.md), [requirements](../../../inception/requirements-analysis/requirements.md), unit assignments, the [component catalogue](../../../inception/domain-design/components.md) ownership and the canonical C04/C05/C06 contracts. U3 owns these entities inside CorpusContent, Discovery and PaperAssistance; entities of other owners (Account, UsageRecord, SavedPaper, Entitlement) are referenced by identifier only and their authority stays with those owners. Together with [rules](rules.md) and the [functional specification](functional-spec.md) this is the behavioural design, not implementation code or a storage schema.

```yaml
unit: u3-paper-corpus-capabilities
entities:
- name: Paper
  owner: CorpusContent
  description: Canonical public paper identity, independent of any single version or
    source record.
  attributes:
  - name: paperId
    type: opaque-id
    required: true
    unique: true
  - name: canonicalReferences
    type: list<source-identity>
    required: true
    constraints: One entry is the current canonical reference; duplicates across
      sources resolve to this one paper, never a second identity.
  - name: metadata
    type: bounded-object
    required: true
    constraints: Title/authors/venue/year/abstract as far as the eligible source
      provides; absent fields stay absent, never invented.
  - name: currentVersionReference
    type: paperVersionId
    required: true
    constraints: Points at the version the corpus currently designates as current;
      a saved reference may still pin an older version.
  - name: availabilityDisposition
    type: enum
    required: true
    allowed: [available, source-only, restricted, withdrawn]
    default: available
    constraints: Derived from the authoritative eligibility revision; never from a
      cached projection alone.
  constraints:
  - paperId is stable across source updates, canonicalization and version changes.
  - A paper with no eligible readable representation is source-only or restricted,
    not deleted from identity.
  relationships:
  - target: PaperVersion
    cardinality: one-to-many
    direction: Paper owns its versions
- name: PaperVersion
  owner: CorpusContent
  description: A specific eligible version of a paper with its provenance and
    eligibility decision.
  attributes:
  - name: paperVersionId
    type: opaque-id
    required: true
    unique: true
  - name: paperId
    type: paperId
    required: true
  - name: sourceIdentity
    type: source-record
    required: true
    constraints: Source system, record id and retrieval provenance; distinguishes
      reordered/duplicate source records that map to the same version.
  - name: versionLabel
    type: string
    required: true
    constraints: Preserved exactly as recorded (for example an arXiv version
      suffix); never substituted with another version's label.
  - name: provenance
    type: bounded-object
    required: true
  - name: eligibilityDecision
    type: enum
    required: true
    allowed: [eligible, source-only, restricted, withdrawn, unresolved]
    default: unresolved
    constraints: Requires resolved permission evidence before copying, parsing,
      embedding or model use; unresolved blocks affected processing.
  - name: contentReference
    type: content-reference
    required: false
    constraints: Absent when no eligible readable content exists yet, is building,
      or is unsupported.
  constraints:
  - Re-importing the same source record resolves the same paperVersionId; a new
    version label creates a new version under the same paper.
  relationships:
  - target: PublicContent
    cardinality: one-to-one-or-many
    direction: PaperVersion is represented by built content
  - target: CitationSnapshot
    cardinality: one-to-many
    direction: PaperVersion is the root of citation snapshots
- name: PublicContent
  owner: CorpusContent
  description: Built readable representation (sections, figures and assets) for one
    paper version, gated by current eligibility.
  attributes:
  - name: publicContentId
    type: opaque-id
    required: true
    unique: true
  - name: paperVersionId
    type: paperVersionId
    required: true
  - name: sections
    type: ordered<document-section>
    required: false
    constraints: The exact read surface; each anchor resolves to the intended
      section of the intended version.
  - name: assetReferences
    type: list<opaque-read-handle>
    required: false
    constraints: Figures/assets are read only through authorized delivery; never
      arbitrary paths or URLs.
  - name: buildDisposition
    type: enum
    required: true
    allowed: [building, ready, unsupported, failed]
    default: building
  - name: eligibilityRevision
    type: revision
    required: true
    constraints: Every read rechecks the current eligibility revision; a stale
      version cannot serve withdrawn content.
  constraints:
  - Reads are side-effect-free; reading never starts ingestion, embedding or
    model work.
  - Malformed or partially built content yields a bounded, explicit state — never
    endless loading or fabricated text.
  relationships:
  - target: PaperVersion
    cardinality: many-to-one
    direction: content belongs to its exact version
- name: CorpusProcessingRun
  owner: CorpusContent
  description: One accepted ingestion, refresh, rebuild or retry operation over a
    declared source scope, with its committed effects and recovery evidence.
  attributes:
  - name: corpusRunId
    type: opaque-id
    required: true
    unique: true
  - name: sourceScope
    type: bounded-object
    required: true
    constraints: Declared inputs and authoritative sources; a rebuild names its
      authoritative inputs rather than assuming the search index is the data.
  - name: operation
    type: enum
    required: true
    allowed: [ingest, refresh, rebuild, retry]
  - name: progress
    type: bounded-object
    required: true
    constraints: Per-stage state; no stage completes without its verified effect.
  - name: watermark
    type: watermark
    required: false
    constraints: Advances only after every stage effect for the covered window is
      verified; never on a partial or unknown outcome.
  - name: effectDispositions
    type: list<stage-effect>
    required: true
    constraints: Individual object/control/projection/publication outcomes, each
      inspectable; unknown effects cannot count as completed.
  - name: recoveryEvidence
    type: bounded-object
    required: false
  constraints:
  - Acceptance durably records input snapshot and dispatch responsibility before
    acknowledgement; same idempotency key and input return the same run.
  - Retry covers only reconciled retryable stages of the same intended run and
    preserves committed stages.
  relationships:
  - target: CorpusChangeFact
    cardinality: one-to-many
    direction: A run records the source-change facts it produced
- name: CorpusChangeFact
  owner: CorpusContent
  description: Recoverable, ordered fact describing a source change (withdrawal,
    license/access change, canonicalization or version change) and its eligibility
    revision.
  attributes:
  - name: changeFactId
    type: opaque-id
    required: true
    unique: true
  - name: paperId
    type: paperId
    required: true
  - name: paperVersionId
    type: paperVersionId
    required: false
  - name: changeKind
    type: enum
    required: true
    allowed: [withdrawal, license-change, access-change, canonicalization,
      version-change]
  - name: eligibilityRevision
    type: revision
    required: true
  - name: recordedAt
    type: trusted-timestamp
    required: true
  constraints:
  - Facts are ordered and replayable; duplicate delivery is harmless and cannot
    grant cross-owner writes.
  - Reads enforce the recorded eligibility immediately, even before projection or
    cache repair.
  relationships:
  - target: Paper
    cardinality: many-to-one
    direction: fact concerns one paper
- name: SearchExecution
  owner: Discovery
  description: One qualified search with its query context, result window, source
    snapshot, degradation state and history effect.
  attributes:
  - name: searchExecutionId
    type: opaque-id
    required: true
    unique: true
  - name: accountId
    type: accountId
    required: false
    constraints: Absent for guest search; guest search never accepts an owner id
      and produces no personal history.
  - name: queryContext
    type: query-context
    required: true
    constraints: The single shared query shape (mode, filters, ordering) used by
      current search, saved queries and history rerun.
  - name: resultWindow
    type: page<result>
    required: true
    constraints: Snapshot-bound pagination; stable ordering never silently
      duplicates or omits results while the snapshot is unchanged.
  - name: sourceSnapshot
    type: snapshot-reference
    required: true
    constraints: Identifies the publication generation and freshness boundary; an
      expired cursor is explicit, not silently rebased.
  - name: degradation
    type: enum
    required: true
    allowed: [none, semantic-unavailable, partial, provider-limited]
    default: none
    constraints: A disclosed fallback (for example lexical-only) is explicit;
      retrieval failure never appears as a successful empty result.
  - name: historyEffectReference
    type: fact-reference
    required: false
    constraints: Completed qualifying authenticated searches yield durable facts;
      publishing the fact does not write Library data.
  constraints:
  - Same snapshot and cursor yield stable, non-duplicated page identities.
  - Current content eligibility wins over a stale index.
  relationships:
  - target: CitationSnapshot
    cardinality: zero-or-many
    direction: a result can be explored through citation snapshots
- name: CitationSnapshot
  owner: Discovery
  description: Bounded cited/citing relationship view for one root paper version,
    with provenance and freshness.
  attributes:
  - name: citationSnapshotId
    type: opaque-id
    required: true
    unique: true
  - name: paperVersionId
    type: paperVersionId
    required: true
  - name: relationships
    type: bounded<edge>
    required: true
    constraints: Distinct nodes/depth/requests honour the resolved traversal
      policy; cycles and duplicates never create unbounded traversal.
  - name: sourceProvenance
    type: source-record
    required: true
  - name: freshness
    type: enum
    required: true
    allowed: [fresh, stale, unknown]
  - name: coverage
    type: enum
    required: true
    allowed: [complete, partial, unavailable]
  constraints:
  - Unknown, stale or partial provider data is labelled; edges are never
    fabricated and saved references are never erased by a provider failure.
  - Saving a referenced paper calls the Library operation; Discovery does not
    write Library records.
  relationships:
  - target: PaperVersion
    cardinality: many-to-one
    direction: snapshot explores one root version
- name: AssistanceJob
  owner: PaperAssistance
  description: One accepted summary/translation/presentation request with its
    immutable binding, recoverable dispatch responsibility and authoritative
    progress.
  attributes:
  - name: assistanceJobId
    type: opaque-id
    required: true
    unique: true
  - name: accountId
    type: accountId
    required: true
  - name: paperVersionId
    type: paperVersionId
    required: true
    constraints: The exact accepted version; never substituted later.
  - name: requestSnapshot
    type: bounded-object
    required: true
    constraints: Action, language, presentation level, content hash and option
      vocabulary revision; immutable after acceptance.
  - name: glossaryRevision
    type: revision
    required: false
    constraints: Exact accepted glossary snapshot used by the operation.
  - name: acceptedAt
    type: trusted-timestamp
    required: true
    constraints: Committed once; replays and replacements never reset it.
  - name: progress
    type: ordered<progress-event>
    required: false
    constraints: Owner-allocated sequence/revision; terminal state never regresses
      and stale or out-of-order events cannot corrupt it.
  - name: dispatchResponsibility
    type: bounded-object
    required: true
    constraints: Durable acceptance implies recoverable responsibility; an
      accepted job never silently remains abandoned.
  - name: outcome
    type: enum
    required: true
    allowed: [accepted, running, succeeded, failed]
    default: accepted
  - name: usageRecordId
    type: usageRecordId
    required: false
    constraints: Accounting settles idempotently for this intended operation;
      unknown stays reconcilable and is never double-counted.
  constraints:
  - Reads and reconnects never start new work; requesting another result requires
    an explicit new acceptance.
  - Unavailable content or model yields an explicit failure/refusal with safe
    retry, never fabricated output.
  relationships:
  - target: AssistanceResult
    cardinality: zero-or-one
    direction: job produces at most one prepared result per accepted request
- name: AssistanceResult
  owner: PaperAssistance
  description: Prepared, retained output bound to its job, owner and the exact
    accepted source.
  attributes:
  - name: assistanceResultId
    type: opaque-id
    required: true
    unique: true
  - name: assistanceJobId
    type: assistanceJobId
    required: true
  - name: sourceBinding
    type: bounded-object
    required: true
    constraints: Owner, paper/version, content hash, operation/option and glossary
      revision equal the accepted immutable request.
  - name: preparedContent
    type: bounded-document
    required: true
  - name: coverage
    type: enum
    required: true
    allowed: [complete, partial]
  - name: availability
    type: enum
    required: true
    allowed: [ready, expired]
  - name: provenance
    type: bounded-object
    required: true
    constraints: Source sections and model/method identifiers as far as recorded;
      partial coverage is disclosed.
  constraints:
  - Reads distinguish pending, ready, expired, failed and unauthorized; a
    completed read never regenerates work and an expired result explains how to
    request again.
  relationships:
  - target: AssistanceJob
    cardinality: one-to-one
    direction: result belongs to its accepted job
- name: Glossary
  owner: PaperAssistance
  description: Owner terminology preferences with normalization and revision
    control, used by eligible assisted output.
  attributes:
  - name: glossaryId
    type: opaque-id
    required: true
    unique: true
  - name: accountId
    type: accountId
    required: true
  - name: terms
    type: ordered<term-entry>
    required: false
    constraints: Normalized, unique per owner policy; empty/duplicate/oversized
      input is rejected with the previous committed glossary preserved.
  - name: normalizationPolicy
    type: policy-reference
    required: true
  - name: revision
    type: revision
    required: true
    constraints: Compare-and-swap on every replace; concurrent edits are resolved
      visibly rather than silently erasing committed preferences.
  constraints:
  - An absent glossary returns a side-effect-free virtual empty snapshot with a
    non-null owner/policy-bound initial revision; the first write atomically
    compares absent plus that initial token.
  - Only the owning account reads or writes its glossary.
  relationships:
  - target: AssistanceJob
    cardinality: one-to-many
    direction: jobs may bind a glossary revision
external_references:
- entity: Account
  owner: AccountAccess
  relationship: Current authority and owner identity; checked independently of any
    stored reference.
- entity: UsageRecord
  owner: UsageEntitlements
  relationship: Accounting outcome for accepted assisted work.
- entity: SavedPaper
  owner: Library
  relationship: Saved references receive explicit dispositions through
    CorpusChangeFacts; U3 never writes Library records.
```

## Entity summary

| Entity | Owner | Role |
|---|---|---|
| Paper / PaperVersion | CorpusContent | Stable public identity and exact version with provenance and eligibility. |
| PublicContent | CorpusContent | Built readable sections/assets for one version, gated by current eligibility. |
| CorpusProcessingRun | CorpusContent | One accepted ingestion/refresh/rebuild run with committed effects, watermark and recovery evidence. |
| CorpusChangeFact | CorpusContent | Ordered, replayable source-change fact that drives eligibility and saved-reference dispositions. |
| SearchExecution | Discovery | One qualified search: shared query context, snapshot-bound window, degradation and history fact. |
| CitationSnapshot | Discovery | Bounded cited/citing view with provenance, freshness and coverage labels. |
| AssistanceJob / AssistanceResult | PaperAssistance | Immutable accepted request with recoverable dispatch, ordered progress and one prepared result. |
| Glossary | PaperAssistance | Owner terminology with normalization and CAS revisions. |

External references (Account, UsageRecord, SavedPaper) stay owned by AccountAccess, UsageEntitlements and Library; U3 holds identifiers, never duplicate authority.
