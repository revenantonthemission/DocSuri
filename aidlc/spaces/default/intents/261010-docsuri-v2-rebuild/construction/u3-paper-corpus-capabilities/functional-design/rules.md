# U3 paper and corpus capabilities — business rules

The YAML is authoritative. Rules elaborate the confirmed [questions](functional-design-questions.md), [requirements](../../../inception/requirements-analysis/requirements.md), unit assignments and canonical C04/C05/C06 contracts. Source IDs express U3's contribution; shared requirements still require their lead unit and U8 integration. [Functional specification](functional-spec.md) gives operation ordering and checks. Every finite policy named here (permissions, limits, model availability, accounting values) is required evidence before affected implementation; these rules do not select those values.

```yaml
unit: u3-paper-corpus-capabilities
rules:
- id: BR1.1
  statement: Use current authority and ownership at every protected boundary.
  category: authorization
  applies_to: All U3 operations and consuming domains
  trigger: Read, command admission, replay, progress event and result publication
  logic: IF the current session, account, role or source authority required by an operation is absent THEN deny before
    returning cached outcomes or applying effects. Resolve ownership from trusted server context, never from caller-supplied
    identifiers, handles or paths.
  violation: Authentication or permission error; foreign resources use the contract-safe absent/denied response.
  source:
  - FR2.2
  - FR3.4
  - FR4.1
  - FR9.1
  - FR18.2
  - NFR4
- id: BR1.2
  statement: Keep guest search anonymous by construction.
  category: authorization
  applies_to: Search and reading paths
  trigger: Unauthenticated request
  logic: IF no session exists THEN serve only the separately authorized guest search/reading surfaces; never accept an
    owner identifier and never create personal history, behavior or private job records for a guest.
  violation: Reject with the guest-safe response; no owner-bound record may result from a guest request.
  source:
  - FR1.1
  - FR5.2
  - NFR4
- id: BR1.3
  statement: Distinguish unknown from zero and failure from empty on every read.
  category: constraint
  applies_to: All reads, status projections and operational views
  trigger: Any read or capability query
  logic: IF evidence is missing, stale or unavailable THEN report the explicit unknown/unavailable state; only a
    successful retrieval may produce an empty result. Unknown usage or counter values are never displayed as zero and a
    dependency failure never appears as a successful response.
  violation: Explicit error/unavailable state with a safe recovery path; no fabricated defaults.
  source:
  - FR1.3
  - FR3.4
  - FR9.2
  - FR18.3
  - NFR2
  - NFR9
- id: BR2.1
  statement: Resolve one canonical identity per paper and version.
  category: constraint
  applies_to: Corpus ingestion, refresh and rebuild
  trigger: Duplicate, reordered or re-imported source records
  logic: IF two source records describe the same version THEN they resolve to the same paper/paperVersion identity without
    duplicate searchable chunks; IF the version label differs THEN a distinct version is created under the same paper; never
    substitute an unrelated paper for an obsolete identifier.
  violation: Rejected or reconciled record with preserved provenance; no duplicate identity or silent redirection.
  source:
  - FR1.1
  - FR18.1
  - NFR10
- id: BR2.2
  statement: Never advance completion or a watermark past verified work.
  category: constraint
  applies_to: Corpus runs and publication
  trigger: Stage effect uncertainty, interruption or partial batch failure
  logic: IF any covered stage effect is uncommitted, unknown or failed THEN the run cannot report completion and the
    watermark does not advance; interrupted object/control/index effects remain individually inspectable for reconciliation.
  violation: Run reports partial/failed with the exact outstanding effects; false completion is a defect.
  source:
  - FR18.1
  - FR18.3
  - NFR3
- id: BR2.3
  statement: Publish only complete, compatible projection generations.
  category: constraint
  applies_to: Projection publication
  trigger: Publication attempt
  logic: IF the manifest is incomplete, any batch receipt is missing, source eligibility changed, or compatibility
    verification fails THEN publication is refused and the previous published generation remains authoritative; only
    CorpusContent-service publication effects may publish, under compare-and-swap.
  violation: CAS conflict or refusal; consumers keep reading the previous complete generation.
  source:
  - FR18.1
  - FR18.3
  - NFR10
- id: BR2.4
  statement: Retry and rebuild from authoritative inputs only.
  category: recovery
  applies_to: Retry, dead-letter reprocessing and rebuild
  trigger: Operator retry or rebuild request
  logic: IF a run is retried THEN only reconciled retryable stages of the same intended run are re-executed and committed
    stages are preserved; a rebuild names and uses its authoritative inputs and verifies durable receipts rather than assuming
    the search index is the source of truth. Reruns must not corrupt committed records.
  violation: Retry refused for unretryable stages; recovery stays repeatable and non-corrupting.
  source:
  - FR18.3
  - NFR3
- id: BR3.1
  statement: Current eligibility wins over every cached or derived representation.
  category: constraint
  applies_to: Reading, search, assistance, projections and restore
  trigger: Eligibility change, withdrawal or restore
  logic: IF the authoritative eligibility revision marks a paper/version withdrawn, restricted or ineligible THEN every
    content, asset, search and model boundary checks that revision before serving or processing; stale caches, indexes and
    restored snapshots cannot silently restore prohibited content, and restore replays current withdrawal boundaries before
    serving.
  violation: SOURCE_INELIGIBLE/absent-with-disposition response; withdrawn content is never served from a stale copy.
  source:
  - FR2.2
  - FR18.2
  - NFR5
- id: BR3.2
  statement: Emit ordered, replayable source-change facts.
  category: constraint
  applies_to: Source change handling and saved references
  trigger: Withdrawal, license/access change, canonicalization or version change
  logic: IF a source change is recorded THEN it persists an authoritative eligibility revision and a recoverable ordered
    fact; duplicate delivery of a fact is harmless and replay neither grants cross-owner writes nor executes new effects.
  violation: Fact is either recorded exactly once semantically (replay-safe) or the change remains explicitly pending.
  source:
  - FR5.3
  - FR18.2
  - NFR3
- id: BR3.3
  statement: Give saved references explicit dispositions after source change.
  category: policy
  applies_to: Saved papers referencing changed sources
  trigger: Changed-source fact delivered to Library
  logic: IF a saved reference's source is withdrawn, canonicalized or unversioned THEN the reference receives an explicit
    disposition (for example unavailable-with-history, canonicalized-to, or version-superseded) rather than being silently
    redirected, deleted or left ambiguous; the fact informs the disposition and never overwrites Library records directly.
  violation: Disposition is recorded by the owning Library operation; unresolved changes remain visibly pending.
  source:
  - FR5.3
  - FR18.2
- id: BR4.1
  statement: Validate the shared query vocabulary on the server.
  category: validation
  applies_to: Query, refinement, ordering and rerun inputs
  trigger: Search request
  logic: IF query/mode/filter/order values fall outside the versioned, published vocabulary or exceed through server-validated
    bounds (empty, whitespace, Unicode, punctuation, oversized) THEN reject with a defined bounded outcome before retrieval;
    retry preserves the query and filters unchanged.
  violation: INVALID_ARGUMENT with defined copy; inputs are never silently coerced or dropped.
  source:
  - FR1.1
  - FR1.3
  - NFR10
- id: BR4.2
  statement: Disclose lexical/semantic mode and degradation truthfully.
  category: policy
  applies_to: Discovery retrieval
  trigger: Semantic capability unavailable or partially available
  logic: IF the semantic path (embedding/model resources) is unavailable or incompatible THEN the response states the
    disclosed fallback (for example lexical-only) or an actionable unavailability; a degraded result is never presented as a
    normal semantic result.
  violation: Explicit degradation state in the response and view; no silent mode substitution.
  source:
  - FR1.2
  - NFR10
- id: BR4.3
  statement: Bind pagination to an explicit snapshot.
  category: constraint
  applies_to: Result windows and cursors
  trigger: Paged or repeated navigation
  logic: IF the underlying publication/snapshot is unchanged THEN paging yields stable, non-duplicated, non-omitted
    ordering; IF the snapshot expired or data changed THEN the response identifies the boundary (SNAPSHOT_EXPIRED or an
    explicit freshness notice) instead of presenting changed data as a stable window.
  violation: Explicit expired/changed state with an offer to rerun; no silent rebase.
  source:
  - FR1.3
  - NFR10
- id: BR4.4
  statement: Produce history facts only from qualifying completed searches.
  category: constraint
  applies_to: Search history handoff
  trigger: Search completion under an authenticated owner
  logic: IF the search completed successfully under a current authenticated owner THEN a durable, owner-scoped fact with a
    producer-assigned admission/completion sequence becomes readable by Library; failed or guest searches produce no fact;
    reading/replaying facts executes no search and writes no Library record; acknowledgement records only after durable
    Library handling, and duplicates cannot create duplicate history.
  violation: Missing fact surfaces as incomplete history, never as saved-history success.
  source:
  - FR5.2
  - NFR3
- id: BR5.1
  statement: Bound citation traversal and label its data quality.
  category: constraint
  applies_to: Citation exploration
  trigger: Cited/citing request
  logic: IF nodes, depth or request bounds are reached THEN traversal stops at the resolved policy bounds; distinct
    identities prevent cycles or duplicates from creating unbounded traversal; unknown, stale, partial or unavailable
    provider data is labelled and edges are never fabricated.
  violation: Partial/limited view with explicit labels and a recoverable path; no fabricated relationships.
  source:
  - FR9.1
  - FR9.2
  - NFR8
- id: BR5.2
  statement: Save references through the Library operation, never through Discovery.
  category: constraint
  applies_to: Saving a cited/citing paper
  trigger: Save action on an explored node
  logic: IF a node is eligible THEN the save invokes the Library operation with stable paper/version identity; ineligible
    nodes explain the limitation; a provider failure never erases an already saved reference.
  violation: Save failure is explicit with the previous library state preserved.
  source:
  - FR9.1
  - FR9.2
- id: BR6.1
  statement: Serve reading from the exact requested paper version.
  category: constraint
  applies_to: Content and asset reads
  trigger: Open/read/navigate-back
  logic: IF a version was requested THEN sections, figures, anchors and source links resolve to that version; navigating
    away and back never substitutes another paper or version, and a saved reference pinned to an older version is not
    silently served as the current one.
  violation: NOT_FOUND/absent-with-disposition rather than substituted content.
  source:
  - FR2.1
  - NFR10
- id: BR6.2
  statement: Represent content availability states truthfully and boundedly.
  category: policy
  applies_to: Reading surface states
  trigger: Absent/building/unsupported/failed/withdrawn/restricted content or malformed document model
  logic: IF eligible readable content is unavailable or malformed THEN the state is explicit (absent, building, unsupported,
    failed, withdrawn, restricted) with any permitted metadata/source links, bounded errors and usable navigation; no endless
    loading and no invented text.
  violation: Explicit state panel with recovery; fabricated or endless-loading content is a defect.
  source:
  - FR2.2
  - NFR2
- id: BR6.3
  statement: Keep asset reads opaque and authorized.
  category: authorization
  applies_to: Figure/asset delivery
  trigger: Asset read
  logic: IF a read handle is presented THEN only the authorized delivery adapter resolves it under current eligibility;
    arbitrary paths, URLs or private identifiers are rejected; content permissions are rechecked before delivery.
  violation: Safe denial; traversal or foreign-content access is impossible by construction.
  source:
  - FR2.2
  - NFR4
- id: BR7.1
  statement: Present only reconciled, currently supported assistance options.
  category: policy
  applies_to: Assistance option vocabulary
  trigger: Option read or request
  logic: IF an action/language/presentation level is not reconciled as supported or its capability/model evidence is
    unavailable THEN it is not offered as available (or is explicitly marked unavailable); an empty option list never implies
    parity and missing content/model yields an explicit reason and safe alternative.
  violation: Explicit unavailable state; no fabricated success and no hidden fallback.
  source:
  - FR3.1
  - NFR1
- id: BR7.2
  statement: Acknowledge only durable acceptance with recoverable dispatch.
  category: constraint
  applies_to: Assistance acceptance
  trigger: Accept request or lost response retry
  logic: IF acceptance is acknowledged THEN the immutable binding (owner, exact paper/version, content hash, options,
    glossary revision), quota reservation and dispatch responsibility were durably recorded first; same idempotency key and
    input return the original job, changed input conflicts; crash between acceptance and dispatch either recovers the work or
    exposes a terminal actionable failure, and an accepted job is never silently abandoned.
  violation: Conflict or recoverable failure state; no orphaned acknowledgement and no duplicate job.
  source:
  - FR3.2
  - NFR3
- id: BR7.3
  statement: Order progress under owner authority and never regress terminal state.
  category: constraint
  applies_to: Job progress, snapshot and stream
  trigger: Worker progress event, reconnect or poll
  logic: IF a progress/revision sequence is newer THEN it advances the snapshot; stale, repeated or out-of-order events are
    rejected by sequence/claim validation; terminal state never regresses; a replaced worker cannot publish late progress,
    failure or success; reconnect after a known event recovers missed progress without executing new work.
  violation: Rejected stale events recorded; the authoritative snapshot stays monotonic.
  source:
  - FR3.3
  - NFR10
- id: BR7.4
  statement: Bind prepared results to the accepted request; reads never regenerate work.
  category: constraint
  applies_to: Prepared-result reads and history
  trigger: Result read, refresh or revisit
  logic: IF a prepared result is read THEN owner, job, paper/version, content hash and operation/option/glossary binding
    equal the accepted immutable request; reads distinguish pending, ready, expired, failed and unauthorized and never
    generate another result; refresh/revisit returns the same result while retained; an expired result stays expired and
    explains how to request again.
  violation: Explicit state response; silent regeneration or re-binding is a defect.
  source:
  - FR3.4
  - NFR10
- id: BR7.5
  statement: Settle assisted work idempotently for the intended operation.
  category: calculation
  applies_to: Assistance accounting effect
  trigger: Completion, failure or retry of an accepted job
  logic: IF the accepted operation terminates THEN exactly one accounting effect is owed and settled idempotently against
    the original reservation; duplicate completion/delivery/replay does not debit twice; unknown settlement stays reconcilable
    and is never reported as settled.
  violation: Unresolved accounting is visible; no double charge and no paid fallback.
  source:
  - FR3.2
  - FR17.2
  - NFR8
- id: BR7.6
  statement: Refuse honestly when content, model or capacity is unavailable.
  category: policy
  applies_to: Assistance execution and acceptance
  trigger: Missing model, ineligible source, capacity or policy block
  logic: IF permitted model/content use, workload bounds or capacity are unavailable or unresolved THEN the affected
    operation returns an explicit refusal/abstention with a safe retry or alternative; no output is fabricated and no paid
    fallback activates.
  violation: Explicit POLICY_UNRESOLVED/unavailable response; partial coverage is disclosed when output is produced.
  source:
  - FR3.1
  - NFR5
  - NFR8
- id: BR8.1
  statement: Normalize and validate glossary terms; preserve committed values.
  category: validation
  applies_to: Glossary writes
  trigger: Term write
  logic: IF terms are empty, duplicate after normalization, conflicting or oversized THEN the write is rejected with the
    previous committed glossary preserved and usable; Unicode terms follow the documented normalization rules; repeated
    submission has the single documented effect.
  violation: Validation error with unchanged committed state; silent erasure is a defect.
  source:
  - FR4.2
  - NFR10
- id: BR8.2
  statement: Resolve glossary writes by visible compare-and-swap.
  category: constraint
  applies_to: Concurrent glossary edits
  trigger: Two overlapping updates
  logic: IF expected revision no longer matches THEN the write conflicts without overwriting; the difference is shown and
    convergence is the owner's explicit choice; an absent glossary is compared as absent plus the policy-bound initial
    revision token.
  violation: CONFLICT with both versions recoverable; no silent last-write-wins.
  source:
  - FR4.2
  - NFR3
- id: BR8.3
  statement: Use the acknowledged glossary revision in eligible output.
  category: calculation
  applies_to: Assisted output
  trigger: Assistance acceptance
  logic: IF an operation runs with terminology preferences THEN the accepted glossary revision is bound to the job and
    eligible output reflects those preferences; a later glossary change does not silently rewrite an accepted job's record.
  violation: Binding mismatch rejects execution; the recorded output remains attributable to its exact revision.
  source:
  - FR4.1
- id: BR9.1
  statement: Keep every shared surface state distinct, announced and recoverable.
  category: policy
  applies_to: WebWorkspace U3 surfaces
  trigger: Loading, empty, partial, error, conflict, pending, expired or offline states
  logic: IF any of these states occurs THEN it is rendered distinctly with meaningful announcement (ARIA live), visible
    focus and usable recovery; committed context (query, filters, open paper/version, prepared result) survives errors,
    reconnect and sign-in changes; no infinite loading or feedback loop.
  violation: Explicit state panel with retry; state-collapse into a generic success is a defect.
  source:
  - NFR2
  - NFR6
- id: BR9.2
  statement: Keep destructive or externally visible actions explicit.
  category: policy
  applies_to: Retry, rebuild, withdrawal and accepted work triggers
  trigger: Operator or owner action with externally visible effects
  logic: IF an action changes corpus state, starts accepted work or alters saved-reference dispositions THEN it requires
    the applicable current authority, states its scope and consequences, and confirms deliberately; reads, previews and
    navigation never trigger those effects.
  violation: Effect refused without explicit confirmation; no action-by-navigation.
  source:
  - FR3.2
  - FR18.3
  - NFR6
```

## Rules summary

| Rule | Statement | Category | Primary sources |
|---|---|---|---|
| BR1.1 | Current authority and ownership at every boundary | authorization | FR2.2/3.4/4.1/9.1/18.2, NFR4 |
| BR1.2 | Guest search stays anonymous | authorization | FR1.1/5.2, NFR4 |
| BR1.3 | Unknown ≠ zero; failure ≠ empty | constraint | FR1.3/3.4/9.2/18.3, NFR2/9 |
| BR2.1 | One canonical identity per paper/version | constraint | FR1.1/18.1, NFR10 |
| BR2.2 | No completion or watermark past verified work | constraint | FR18.1/18.3, NFR3 |
| BR2.3 | Publish only complete compatible generations | constraint | FR18.1/18.3, NFR10 |
| BR2.4 | Retry/rebuild from authoritative inputs | recovery | FR18.3, NFR3 |
| BR3.1 | Eligibility wins over caches/indexes/restores | constraint | FR2.2/18.2, NFR5 |
| BR3.2 | Ordered replayable source-change facts | constraint | FR5.3/18.2, NFR3 |
| BR3.3 | Explicit saved-reference dispositions | policy | FR5.3/18.2 |
| BR4.1 | Server-validated query vocabulary | validation | FR1.1/1.3, NFR10 |
| BR4.2 | Disclosed lexical/semantic degradation | policy | FR1.2, NFR10 |
| BR4.3 | Snapshot-bound pagination | constraint | FR1.3, NFR10 |
| BR4.4 | History facts only from qualifying searches | constraint | FR5.2, NFR3 |
| BR5.1 | Bounded, labelled citation traversal | constraint | FR9.1/9.2, NFR8 |
| BR5.2 | Reference saves go through Library | constraint | FR9.1/9.2 |
| BR6.1 | Reading serves the exact version | constraint | FR2.1, NFR10 |
| BR6.2 | Truthful bounded content availability states | policy | FR2.2, NFR2 |
| BR6.3 | Opaque authorized asset reads | authorization | FR2.2, NFR4 |
| BR7.1 | Only reconciled supported assistance options | policy | FR3.1, NFR1 |
| BR7.2 | Durable acceptance with recoverable dispatch | constraint | FR3.2, NFR3 |
| BR7.3 | Ordered progress; terminal state never regresses | constraint | FR3.3, NFR10 |
| BR7.4 | Results bound to acceptance; reads never regenerate | constraint | FR3.4, NFR10 |
| BR7.5 | Idempotent settlement for the intended operation | calculation | FR3.2/17.2, NFR8 |
| BR7.6 | Honest refusal when inputs or capacity are unavailable | policy | FR3.1, NFR5/8 |
| BR8.1 | Glossary validation preserves committed values | validation | FR4.2, NFR10 |
| BR8.2 | Visible CAS glossary convergence | constraint | FR4.2, NFR3 |
| BR8.3 | Accepted glossary revision binds output | calculation | FR4.1 |
| BR9.1 | Distinct announced recoverable surface states | policy | NFR2/6 |
| BR9.2 | Explicit scope and confirmation for effectful actions | policy | FR3.2/18.3, NFR6 |
