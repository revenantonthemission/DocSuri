# U1 Entity Model

## Sources and Scope

The confirmed `functional-design-questions.md` Q1/Q2 and consolidated summary, approved Domain Design catalogue and contracts C1–C4/C6–C8 govern this model. Upstream paths are beneath `../../../inception/`. ContentJobService owns backend authority; client projections and recovery identity do not own backend resources. AssetViewState belongs to U3 and is not redesigned here.

The current confirmed Q3 amendment consumes `../../../inception/units-generation/unit-of-work.md`, `../../../inception/units-generation/unit-of-work-story-map.md`, `../../../inception/requirements-analysis/requirements.md`, `../../../inception/domain-design/components.md` and approved `../../../inception/contract-design/contract-summary.md`. The shared payload definition is `shared/dtos/summarization.schema.json#/$defs/Reproducibility`. The current delivery recovery handoff is `../../../inception/delivery-planning/bolt-plan.md`; isolated-realm preparation is documented in `../../../verification/u1-isolated-postgres-bootstrap-plan.md`. Prior entity/rule/spec/map bytes remain under `../../../archive/2026-10-05T16-19-42Z-u1-functional-design/`.

The YAML below is authoritative for logical shapes and relationships. Physical migration syntax and complete implementations belong to Code Generation. Storage placement is the existing relational authority for backend snapshots; client persistence contains only the selected parameter metadata. Numeric worker timing and payload-volume validation are assigned to U1 NFR Design before implementation approval.

## Entity Catalogue

```yaml
model_version: 1
types:
  identifier: nonempty opaque text; never authorization
  instant: authoritative UTC instant
  sequence: integer within 0 through 9007199254740991
  safe_error: allowlisted errorType/message/retryable and optional nonnegative retryAfterSeconds
  job_input: validated paperId/version/targetLang/persona/scope from C1
  prepared_content: final safe summary or translated bare document payload validated by C2; summary reproducibility is exactly the shared required string code/data object with no extra fields
entities:
  - name: DurableJob
    owner: ContentJobService
    identifier: jobId
    description: Authoritative lifecycle and durable input of one accepted submission.
    attributes:
      - {name: jobId, type: identifier, required: true, unique: true}
      - {name: ownerId, type: identifier, required: true, constraints: trusted authenticated owner; immutable}
      - {name: taskType, type: text, required: true, allowed_values: [summarize, translate], constraints: U1 profile; unrelated backend task types remain unchanged}
      - {name: input, type: job_input, required: true, constraints: immutable validated execution input; not copied into status telemetry}
      - {name: inputIdentity, type: text, required: true, constraints: stable identity of normalized durable input; not a client authentication fact}
      - {name: authorityVersion, type: integer, required: false, constraints: 1 for new-protocol T1 records; absent legacy records cannot acquire a new generation grant automatically}
      - {name: state, type: text, required: true, default: SUBMITTED, allowed_values: [SUBMITTED, ACCEPTED, QUEUED, RUNNING, COMPLETED, FAILED, ABSTAINED]}
      - {name: eventSequence, type: sequence, required: true, default: 0}
      - {name: preparedResultId, type: identifier, required: false, references: PreparedJobResult.preparedResultId, constraints: internal staging binding; public resultRef remains absent before COMPLETED}
      - {name: resultRef, type: text, required: false, constraints: opaque public lookup reference only for committed completion}
      - {name: resultExpiresAt, type: instant, required: false, constraints: fixed once on completion; consistent with result record}
      - {name: safeError, type: safe_error, required: false}
      - {name: abstainReason, type: text, required: false, constraints: safe mapped reason; not raw exception text}
      - {name: createdAt, type: instant, required: true}
      - {name: updatedAt, type: instant, required: true}
    constraints:
      - Terminal states have no outgoing lifecycle transition.
      - Completion requires the exact committed prepared binding for this job and owner.
      - One committed state transition increments eventSequence and records its event atomically.
  - name: SubmissionBinding
    owner: ContentJobService
    identifier: bindingId
    description: Owner/key binding and authoritative dispatch decision for a job.
    attributes:
      - {name: bindingId, type: identifier, required: true, unique: true}
      - {name: ownerId, type: identifier, required: true}
      - {name: idempotencyKey, type: text, required: false, constraints: required for Phase 7 browser profile; unique with owner among retained non-null bindings; legacy keyless callers remain one new job per explicit submission}
      - {name: originalRequestIdentity, type: text, required: true, constraints: immutable task and durable input identity}
      - {name: jobId, type: identifier, required: true, references: DurableJob.jobId}
      - {name: dispatchId, type: identifier, required: true, unique: true}
      - {name: dispatchOutcome, type: text, required: true, default: NOT_STARTED, allowed_values: [NOT_STARTED, SENDING, CONFIRMED, REJECTED, UNKNOWN]}
      - {name: dispatchFence, type: sequence, required: true, default: 0, constraints: monotonic claim authority for one send decision}
      - {name: dispatchStartedAt, type: instant, required: false}
      - {name: dispatchEvidence, type: structured_metadata, required: false, constraints: trusted queue acknowledgement or receipt evidence; no credentials}
      - {name: releasedAt, type: instant, required: false}
    constraints:
      - Replays never replace a retained binding's original task/input.
      - A released binding remains historical but does not claim the owner/key uniqueness slot.
      - Only definite non-dispatch before generation permits release; unknown send does not.
      - Failed dispatch terminal publication and binding release commit together.
  - name: GenerationEffect
    owner: ContentJobService
    identifier: effectId
    description: Durable intent, publication fence and evidence for one whole-pipeline invocation.
    attributes:
      - {name: effectId, type: identifier, required: true, unique: true}
      - {name: jobId, type: identifier, required: true, references: DurableJob.jobId}
      - {name: attempt, type: positive_integer, required: true, default: 1, constraints: no terminal restart or ambiguous-intent reset}
      - {name: effectName, type: text, required: true, default: generate}
      - {name: effectStatus, type: text, required: true, allowed_values: [INTENT, PREPARED, TERMINAL]}
      - {name: fence, type: sequence, required: true, constraints: positive current publication authority; increments on revocation/reconciliation}
      - {name: workerId, type: identifier, required: false}
      - {name: leaseUntil, type: instant, required: false}
      - {name: intentAt, type: instant, required: true}
      - {name: preparedResultId, type: identifier, required: false, references: PreparedJobResult.preparedResultId}
      - {name: reconciliationEvidence, type: structured_metadata, required: false, constraints: observed fence and outcome evidence; not provider output or secret}
    constraints:
      - Unique job/attempt; relabeling an effect cannot grant another invocation.
      - Committed INTENT is never deleted to permit generation again.
      - Lease renewal and all writes serialize against current job/effect authority.
      - New publication authority for reconciliation cannot invoke generation.
  - name: PreparedJobResult
    owner: ContentJobService
    identifier: preparedResultId
    description: Exact immutable final owner-specific payload, separate from shared artifact cache.
    attributes:
      - {name: preparedResultId, type: identifier, required: true, unique: true}
      - {name: jobId, type: identifier, required: true, unique: true, references: DurableJob.jobId}
      - {name: ownerId, type: identifier, required: true, constraints: must equal durable job owner}
      - {name: taskType, type: text, required: true, allowed_values: [summarize, translate]}
      - {name: schemaVersion, type: integer, required: true, allowed_values: [1]}
      - {name: preparedContent, type: prepared_content, required: true, constraints: immutable while retained; nullable only after authorized expiry cleanup}
      - {name: contentDigest, type: text, required: true, constraints: SHA-256 over canonical final payload identity; private integrity field}
      - {name: personalizationIdentity, type: structured_metadata, required: true, constraints: preparation-time context if available plus final content digest; never synthesized from current settings}
      - {name: generationIdentity, type: structured_metadata, required: true, constraints: captured preparation identity and digest; private fields only}
      - {name: sourceIdentity, type: structured_metadata, required: true, constraints: validated paper/version and available generation provenance}
      - {name: createdAt, type: instant, required: true, constraints: preparedAt in public envelope}
      - {name: expiresAt, type: instant, required: false, constraints: absent during staging; fixed once with completion publication}
      - {name: contentPurgedAt, type: instant, required: false}
    constraints:
      - Stored in the same existing relational authority as the job/effect binding.
      - A repeated binding must match identity/digest/content; no overwrite from another fence or current defaults.
      - Summary reproducibility preserves the separate required code and data strings exactly; no flattening, coercion or guessed defaults.
      - Missing, malformed or flattened reproducibility is not successful prepared content; capture and reads follow the controlled protocol/unavailable outcomes.
      - Only COMPLETED and unexpired records with validated content may be delivered.
      - Cleanup can remove expired content but retains expiry metadata while the job remains, so its owner receives 410.
  - name: JobEvent
    owner: ContentJobService
    identifier: eventId
    description: Existing append-only lifecycle event; distinct global ID and per-job sequence.
    attributes:
      - {name: eventId, type: identifier, required: true, unique: true, constraints: opaque public cursor; do not parse as sequence}
      - {name: jobId, type: identifier, required: true, references: DurableJob.jobId}
      - {name: ownerId, type: identifier, required: true}
      - {name: seq, type: sequence, required: true, min: 1, constraints: unique per job; ordered in durable transaction}
      - {name: state, type: text, required: true, constraints: existing job lifecycle vocabulary}
      - {name: payload, type: structured_safe_payload, required: true, default: empty, constraints: safe error/reason/resultReady only as actually supplied}
      - {name: createdAt, type: instant, required: true}
    constraints: [event/state commit together, ownership checked before cursor resolution, no generated result content in event history]
  - name: IdempotencyKey
    owner: ContentJobApi
    identifier: key
    description: Client recovery record; the digest key names request identity, while attemptId names the local attempt.
    attributes:
      - {name: attemptId, type: identifier, required: true, unique: true, constraints: local handle; not the idempotency key or server credential}
      - {name: key, type: text, required: true, constraints: 64 lowercase hex SHA-256 of original owner/paper/task/serialized input; logical request identity distinct from local attempt discriminator}
      - {name: ownerId, type: identifier, required: true}
      - {name: paperId, type: identifier, required: true}
      - {name: taskType, type: text, required: true, allowed_values: [summarize, translate]}
      - {name: schemaVersion, type: integer, required: true, allowed_values: [1]}
      - {name: serializedRequest, type: text, required: true, constraints: exact immutable original serialization of allowlisted validated job input}
      - {name: originalRequestAvailable, type: boolean, required: true}
      - {name: persistenceStatus, type: text, required: true, allowed_values: [stored, memory-only]}
      - {name: jobId, type: identifier, required: false, constraints: last actual returned job; not inferred from hash}
      - {name: contextGeneration, type: sequence, required: true, constraints: in-memory only; rebound on verified restore}
      - {name: preparationRevision, type: sequence, required: true, constraints: in-memory reservation before async capture/hash; rechecked before publishing memory or storage}
      - {name: inFlight, type: boolean, required: true, default: false, constraints: in-memory action exclusion}
    constraints:
      - Persist only schemaVersion/attemptId/ownerId/paperId/taskType/key/serializedRequest and optional jobId.
      - Namespace remains idempotency:{paperId}:{taskType}; validate owner and original digest before reuse.
      - Secrets, document/result content, arbitrary input fields and stale context authority are never persisted.
      - Domain key identity remains key; attemptId is the local record discriminator and cannot grant another backend execution.
  - name: TrackingContext
    owner: PaperDetailIsland
    identifier: contextId
    description: Stable current selection and recovery checkpoint outside status render containment.
    attributes:
      - {name: contextId, type: identifier, required: true, unique: true}
      - {name: ownerId, type: identifier, required: true}
      - {name: paperId, type: identifier, required: true}
      - {name: jobId, type: identifier, required: true}
      - {name: taskType, type: text, required: true}
      - {name: attemptId, type: identifier, required: false, references: IdempotencyKey.attemptId}
      - {name: submittedLevel, type: text, required: false, allowed_values: [expert, beginner]}
      - {name: lastEventId, type: identifier, required: false}
      - {name: historyCheckpoint, type: ordered_event_collection, required: false, constraints: immutable recovery checkpoint supplied by JobStatus; not a second mutable projection owner}
      - {name: contextGeneration, type: sequence, required: true}
      - {name: returnFocusTarget, type: focus_reference, required: false}
    constraints: [created only from actual job identity, invalidate on owner or selected-job change, tracking reset never submits]
  - name: SubmissionDraft
    owner: JobSubmissionForm
    identifier: draftId
    description: Editable initial choices, never a substitute for captured recovery input.
    attributes:
      - {name: draftId, type: identifier, required: true, unique: true}
      - {name: ownerId, type: identifier, required: true}
      - {name: paperId, type: identifier, required: true}
      - {name: taskType, type: text, required: true}
      - {name: params, type: job_input, required: true}
      - {name: submissionStatus, type: text, required: true, default: idle, allowed_values: [idle, preparing, submitting, uncertain, recovering, received, unavailable]}
      - {name: attemptId, type: identifier, required: false, references: IdempotencyKey.attemptId}
      - {name: safeError, type: safe_error, required: false}
    constraints: [initial draft is valid without a captured attempt, mount and selection do not hash or submit or fabricate an idempotency record, edits do not mutate captured originals]
  - name: JobState
    owner: JobStatus
    identifier: contextId
    description: Observed client projection, not backend state authority.
    attributes:
      - {name: contextId, type: identifier, required: true, references: TrackingContext.contextId}
      - {name: jobId, type: identifier, required: true}
      - {name: backendState, type: text, required: false}
      - {name: acceptedSeq, type: sequence, required: true, default: 0}
      - {name: history, type: ordered_event_collection, required: true, default: empty}
      - {name: lastEventId, type: identifier, required: false, constraints: cursor of last accepted history event; not poll watermark}
      - {name: connectionStatus, type: text, required: true, allowed_values: [connecting, live, polling, offline, terminal, access-unavailable]}
      - {name: progress, type: optional_observation, required: false, constraints: only actual validated supplied progress}
      - {name: eta, type: optional_observation, required: false, constraints: no numeric estimate without supported samples}
      - {name: safeError, type: safe_error, required: false}
      - {name: observedAt, type: instant, required: false}
    constraints: [state watermark never regresses, older history may fill gaps without regressing state, no cross-context cache updates]
  - name: ResultViewState
    owner: SummaryModal
    identifier: contextId
    description: Read-only content/view status for the selected job.
    attributes:
      - {name: contextId, type: identifier, required: true, references: TrackingContext.contextId}
      - {name: resultRef, type: text, required: false}
      - {name: content, type: prepared_content, required: false}
      - {name: submittedLevel, type: text, required: false}
      - {name: suppliedAssetId, type: identifier, required: false}
      - {name: readStatus, type: text, required: true, allowed_values: [loading, available, authentication-required, not-ready, unavailable, expired, transient-failure]}
      - {name: safeError, type: safe_error, required: false}
    constraints: [no command capability, absent metadata never filled from current preferences, obsolete reads cannot publish]
  - name: RenderFailure
    owner: ErrorBoundary
    identifier: failureId
    description: Safe containment notification, not a job failure.
    attributes:
      - {name: failureId, type: identifier, required: true, unique: true}
      - {name: contextId, type: identifier, required: true, references: TrackingContext.contextId}
      - {name: safeMessage, type: text, required: true}
      - {name: occurredAt, type: instant, required: true}
    constraints: [no raw exception content, fallback context retained by stable parent]
relationships:
  - {from: DurableJob, to: SubmissionBinding, cardinality: one-to-one, direction: job has one dispatch/binding record in the U1 keyed profile; retained key may move only after definite release}
  - {from: DurableJob, to: GenerationEffect, cardinality: one-to-zero-or-one, direction: one whole-pipeline intent for this no-restart job}
  - {from: DurableJob, to: PreparedJobResult, cardinality: one-to-zero-or-one, direction: staged snapshot before completion; exact prepared result for delivered success}
  - {from: DurableJob, to: JobEvent, cardinality: one-to-many, direction: authoritative ordered history}
  - {from: IdempotencyKey, to: TrackingContext, cardinality: optional-one-to-many-over-time, direction: local recovery may select a replacement; tracking may exist without recoverable attempt data; at most one active context per current view}
  - {from: IdempotencyKey, to: SubmissionDraft, cardinality: optional-one-to-many-over-time, direction: each draft references zero or one captured attempt; each attempt may be referenced by zero or multiple drafts over time; editable choices remain separate}
  - {from: TrackingContext, to: JobState, cardinality: one-to-zero-or-one, direction: observed tracking projection}
  - {from: TrackingContext, to: ResultViewState, cardinality: one-to-zero-or-one, direction: selected read-only dialog state}
  - {from: TrackingContext, to: RenderFailure, cardinality: one-to-many-over-time, direction: contained rendering failure notifications}
```

## Entity Summary and Validation

Five backend shapes share one owner: DurableJob, SubmissionBinding, GenerationEffect, PreparedJobResult and the existing JobEvent history. Six frontend shapes preserve declared owners. The attempt discriminator refines local bookkeeping, not backend request identity. The backend event is explicit because C3 requires its persisted ID/seq relationship.

The C1 input validator enforces nonempty paperId, positive integer version, supported task profile, ko target language, expert/beginner persona and abstract/full scope; summary is full scope. Existing intentionally supported legacy omissions are normalized at their boundary, not by rewriting an existing captured request. Input, owner and snapshot relationships must agree before persistence. All external/stored payloads are validated before entering this model.

Prepared content identity uses a deterministic, versioned canonical JSON representation: object keys sorted, array order and string contents preserved, JSON number semantics retained, no nonfinite numbers. Hash the resulting UTF-8 representation. This private integrity digest is independent of the browser's mandated JSON.stringify request hash and must not alter its derivation. The full safe payload is retained; metadata is preparation-time evidence only, not permission to recompute content. Missing pipeline metadata is recorded as unavailable rather than invented; exactness derives from the actual committed payload.

The logical prepared-content type uses C2's shared required `{code: string, data: string}` reproducibility object, not a second independent schema or a string-only variant. Strings retain their actual Unicode, whitespace and escaping through capture/serialization/reads; canonical hashing may order object keys but never alter their values. A malformed successful summary cannot become valid by concatenating the two values, manufacturing a missing value or rerunning the pipeline. Existing controlled capture/read outcomes are defined in `functional-spec.md` and do not change owner/expiry precedence.

SubmissionDraft and TrackingContext each permit an absent attempt reference. A draft exists before preparation; a known authorized job can be tracked/read without recoverable originals. No placeholder IdempotencyKey with fabricated required input is created to satisfy a diagram. The derived ER edges must encode this optional parent cardinality in both cases.

Deleting an owner/job removes its effects, binding, prepared content and events through the same authoritative lifecycle. Writes lock/revalidate the still-existing job and owner; there is no upsert that recreates a purged job. Expiry is an availability boundary, not an instruction to restart work. Cleanup may purge expired content asynchronously while retaining enough job/expiry metadata for the owned 410 response. A result still staged when its authority is revoked can only be reconciled according to the behavioural specification, never silently exposed.
