# Contract Summary — Durable Content Jobs

## Sources and Authority

The confirmed `contract-design-questions.md` governs this specification, particularly Q10–Q13: bounded backend remediation, preserved failed-dispatch replacement, additive result response, and fail-safe ambiguous generation without regeneration. Upstream: `../units-generation/{unit-of-work,unit-of-work-dependency}.md`, `../domain-design/{components,decisions}.md` (ADR-014–ADR-016), `../requirements-analysis/requirements.md` and `../user-stories/stories.md`.

The confirmed narrow C2 amendment in that questions file corrects summary reproducibility to `shared/dtos/summarization.schema.json#/$defs/Reproducibility`, matching `SummaryDraft` and `SummaryResultDTO.to_dict()` in `backend/modules/summarization/src/summarization/domain/models.py`. The shared definition requires string `code` and `data` and forbids additional fields. This corrects an undeployed specification defect; it does not authorize changing actual prepared content or assume deployed-consumer compatibility. The separately requested PostgreSQL planning handoff is `../../verification/u1-isolated-postgres-bootstrap-plan.md`; operational admission and real-store tests remain prerequisites.

Source observations: `backend/wiring.py`, `backend/modules/summarization/src/summarization/{api/router.py,worker.py,real_wiring.py,service/job_service.py,service/orchestrator.py,domain/job.py,domain/models.py,domain/cache_key.py,adapters/rds_jobs.py,adapters/content_job_queue.py}`, `frontend/app/bff/[...path]/route.ts` and `frontend/lib/api/httpTransport.ts`. These are source checks, not runtime certification. The authored contracts below distinguish required remediation from current implementation.

## Contracts

| # | Provider Unit | Consumer | Mechanism | Owner |
|---|---|---|---|---|
| C1 | U1 | External: authenticated browser; U2 frontend | HTTP submit/state | U1 controller/service |
| C2 | U1 | External: authenticated browser; U2 result UI | HTTP exact prepared result | U1 ContentJobService via restricted controller query |
| C3 | U1 | External: native EventSource in U1/U2 | SSE and cursor/state schemas | U1 controller/service/BFF |
| C4 | U1 | U2 | Shared TypeScript capability model | U1 frontend integration |
| C5 | U3 asset surface; U1 shared context | External: browser; U3 viewer | HTTP image and shared context | U3 asset integration; U1 shared context |
| C6 | U1 service/API runtime | Existing U1 worker runtime | Queue message schema | U1 |
| C7 | U1 ContentJobService | U1 worker/controller | Command/query and durable-state protocol | U1 ContentJobService |
| C8 | U1, with U2/U3 agreement | Existing API/worker/frontend versions | Version compatibility contract | Provider-maintained, consumer-agreed |

U1 owns backend guarantees for both tasks. U2 consumes them and adds UI coverage, not missing backend capability. U3 does not consume job-generation internals. Contracts do not introduce another deployment unit.

## C1, C2 and C5 — HTTP Specification

The following single OpenAPI document defines the three HTTP boundaries together so its local schema references resolve. Paths are browser-facing; BFF strips `/bff` and forwards through the configured gateway. Job controller names map to backend snake-case route parameters without changing URLs. The external DocModel and Reproducibility references resolve from this Markdown file's directory; a validator extracting YAML must retain this base URI.

```yaml
openapi: 3.1.0
info: {title: DocSuri Phase 7 contracts, version: 1.0.0}
servers: [{url: /bff}]
security: [{sessionCookie: []}]
paths:
  /api/content-jobs/submit:
    post:
      operationId: submitContentJob
      requestBody:
        required: true
        content:
          application/json:
            schema: {$ref: '#/components/schemas/SubmitRequest'}
      responses:
        '202':
          description: Durable receipt with actual state; not proof of completion or a fresh execution
          content:
            application/json:
              schema: {$ref: '#/components/schemas/JobReceipt'}
        '400': {$ref: '#/components/responses/Invalid'}
        '401': {$ref: '#/components/responses/Unauthorized'}
        '503': {$ref: '#/components/responses/Unavailable'}
        '504': {$ref: '#/components/responses/Unavailable'}
  /api/content-jobs/{jobId}/state:
    parameters: [{$ref: '#/components/parameters/JobId'}]
    get:
      operationId: readContentJobState
      responses:
        '200':
          description: Authorized snapshot; seq is the same per-job ordering watermark used by events
          content:
            application/json:
              schema: {$ref: '#/components/schemas/JobSnapshot'}
        '401': {$ref: '#/components/responses/Unauthorized'}
        '404': {$ref: '#/components/responses/NotFound'}
        '503': {$ref: '#/components/responses/Unavailable'}
        '504': {$ref: '#/components/responses/Unavailable'}
  /api/content-jobs/{jobId}/result:
    parameters: [{$ref: '#/components/parameters/JobId'}]
    get:
      operationId: readPreparedJobResult
      responses:
        '200':
          description: Exact immutable owner-specific prepared payload; never generated by this read
          content:
            application/json:
              schema: {$ref: '#/components/schemas/ResultResponse'}
        '401': {$ref: '#/components/responses/Unauthorized'}
        '404': {$ref: '#/components/responses/NotFound'}
        '409':
          description: Authenticated owner's job is not COMPLETED; this is not a submission replay status
          content:
            application/json:
              schema: {$ref: '#/components/schemas/SafeError'}
        '410':
          description: Authenticated owner's known prepared result has expired; no content
          content:
            application/json:
              schema: {$ref: '#/components/schemas/SafeError'}
        '422':
          description: Authenticated owner's completed job has unsupported or legacy unresolvable result identity
          content:
            application/json:
              schema: {$ref: '#/components/schemas/SafeError'}
        '503': {$ref: '#/components/responses/Unavailable'}
        '504': {$ref: '#/components/responses/Unavailable'}
  /api/papers/{paperId}/assets/{assetId}:
    parameters:
      - {name: paperId, in: path, required: true, schema: {type: string, minLength: 1}}
      - {name: assetId, in: path, required: true, schema: {type: string, minLength: 1}}
      - {name: version, in: query, required: false, schema: {type: integer, minimum: 1}}
    get:
      operationId: readAuthorizedAsset
      responses:
        '200':
          description: Only validated authorized image bytes are returned by BFF
          headers:
            Cache-Control: {schema: {type: string, const: 'private, max-age=60'}}
            X-Content-Type-Options: {schema: {type: string, const: nosniff}}
          content:
            'image/*': {schema: {type: string, format: binary}}
        '404': {description: Empty no-store image-unavailable response; no redirect or internal upstream body}
        '503': {description: Gateway configuration unavailable; no protected bytes}
components:
  securitySchemes:
    sessionCookie:
      type: apiKey
      in: cookie
      name: session_id
      description: Existing gateway session cookie; backend/middleware/auth.py resolves it to trusted principal
  parameters:
    JobId: {name: jobId, in: path, required: true, schema: {type: string, minLength: 1}}
  responses:
    Invalid:
      description: Invalid input with safe feedback
      content: {application/json: {schema: {$ref: '#/components/schemas/SafeError'}}}
    Unauthorized:
      description: Authentication required; no protected content
      content: {application/json: {schema: {$ref: '#/components/schemas/SafeError'}}}
    NotFound:
      description: Identical status and body for nonexistent and not-owned jobs
      content: {application/json: {schema: {$ref: '#/components/schemas/SafeError'}}}
    Unavailable:
      description: Transient service or gateway failure; no raw exception body
      content: {application/json: {schema: {$ref: '#/components/schemas/SafeError'}}}
  schemas:
    JobState:
      type: string
      enum: [SUBMITTED, ACCEPTED, QUEUED, RUNNING, COMPLETED, FAILED, ABSTAINED]
    JobError:
      type: object
      required: [errorType, message, retryable]
      properties:
        errorType: {type: string}
        message: {type: string}
        retryable: {type: boolean}
        retryAfterSeconds: {type: integer, minimum: 0}
      additionalProperties: true
    SafeError:
      type: object
      properties:
        status: {type: string}
        code: {type: string}
        message: {type: string}
      anyOf: [{required: [status]}, {required: [message]}]
      additionalProperties: true
    JobInput:
      type: object
      required: [paperId, version, targetLang, persona, scope]
      properties:
        paperId: {type: string, minLength: 1}
        version: {type: integer, minimum: 1}
        targetLang: {type: string, enum: [ko]}
        persona: {type: string, enum: [expert, beginner]}
        scope: {type: string, enum: [abstract, full]}
      additionalProperties: false
    SubmitRequest:
      type: object
      required: [taskType, input, idempotencyKey]
      properties:
        taskType: {type: string, enum: [summarize, translate]}
        input: {$ref: '#/components/schemas/JobInput'}
        idempotencyKey: {type: string, pattern: '^[a-f0-9]{64}$'}
      additionalProperties: false
    JobReceipt:
      type: object
      required: [jobId, state]
      properties:
        jobId: {type: string}
        state: {$ref: '#/components/schemas/JobState'}
        error: {$ref: '#/components/schemas/JobError'}
      additionalProperties: true
    JobSnapshot:
      allOf:
        - {$ref: '#/components/schemas/JobReceipt'}
        - type: object
          required: [seq]
          properties:
            seq: {type: integer, minimum: 0, maximum: 9007199254740991}
            resultRef: {type: string}
            abstainReason: {type: string}
    ResultResponse:
      type: object
      required: [resultRef, preparedResult]
      properties:
        resultRef: {type: string, description: Opaque reference retained for compatibility; never a storage URL or capability}
        preparedResult:
          type: object
          required: [schemaVersion, jobId, taskType, preparedAt, expiresAt, content]
          properties:
            schemaVersion: {type: integer, const: 1}
            jobId: {type: string}
            taskType: {type: string, enum: [summarize, translate]}
            submittedLevel: {type: string, enum: [expert, beginner]}
            assetId: {type: string, description: Only an actually supplied authorized result asset identifier}
            preparedAt: {type: string, format: date-time}
            expiresAt: {type: string, format: date-time}
            content:
              oneOf:
                - {$ref: '#/components/schemas/SummaryContent'}
                - {$ref: '#/components/schemas/TranslationContent'}
          additionalProperties: true
      additionalProperties: true
    Anchor:
      type: object
      required: [field, target, span, label]
      properties:
        field: {type: string}
        target: {type: string, enum: [section, table, figure]}
        span: {type: string}
        label: {type: string}
      additionalProperties: true
    SummaryContent:
      type: object
      required: [status, task, summary]
      properties:
        status: {const: ok}
        task: {const: summary}
        summary:
          type: object
          required: [tldr, contributions, method, results, limitations, reproducibility, anchors]
          properties:
            tldr: {type: string}
            contributions: {type: array, items: {type: string}}
            method: {type: string}
            results: {type: string}
            limitations: {type: string}
            reproducibility: {$ref: '../../../../../../../shared/dtos/summarization.schema.json#/$defs/Reproducibility'}
            anchors: {type: array, items: {$ref: '#/components/schemas/Anchor'}}
          additionalProperties: true
      additionalProperties: true
    TranslationContent:
      type: object
      required: [status, task, translation]
      properties:
        status: {const: ok}
        task: {const: translate}
        translation:
          type: object
          required: [docModel, keptTerms]
          properties:
            docModel: {$ref: '../../../../../../../shared/dtos/docmodel.schema.json#/$defs/DocModel'}
            keptTerms: {type: array, items: {type: string}}
          additionalProperties: true
      additionalProperties: true
```

### C1 — Submission and State Semantics

This request schema is the Phase 7 caller profile, not removal of unrelated backend task types or legacy callers. New frontend submissions explicitly supply the existing supported defaults (`version` from the paper, `targetLang: ko`, initial summary persona from selection, summary scope full; translation scope selected). The backend must validate/normalize its supported input without treating caller identity as trusted. Contract tests preserve intentionally supported legacy omitted fields at the existing API; unsupported new UI actions remain absent.

The captured serialized input is fixed before hashing/sending. Compute native SHA-256 of `userId:paperId:taskType:JSON.stringify(params)` with params equal to the captured input object; replay uses identical captured bytes/field order, not a fresh object assembled from current controls. Client key persistence uses `idempotency:{paperId}:{taskType}` and owner/request reconciliation. Backend auth remains gateway-derived regardless of this digest.

Retained bindings return the original job/state, including terminal state. A **definite failed dispatch** may release its binding and a later explicit resend can create a replacement. A timeout with unknown queue acceptance is not proof of non-dispatch: keep identity and reconcile it rather than authorizing duplicate work. The backend must serialize competing dispatch claims; one accepted receipt cannot trigger a second independent send via the legacy adapter. Transport delivery may duplicate queue messages; C7 prevents duplicate execution. The UI never assumes a click means a new execution or a returned 202 means RUNNING.

`seq` is an additive state watermark from the same durable state/event transaction. Apply observations only to the current owner/job/context and never regress below the greatest accepted watermark. A higher-sequence poll may advance the display before SSE history arrives; retain missing event history by event identity without regressing displayed state. `abstainReason` is an additive safe field. No numerical progress or ETA is invented where absent.

### C2 — Result Semantics and Error Precedence

Authorization first: 401 unauthenticated; the exact generic `{status: not_found}` 404 body for unknown/not-owned, including expired other-owner jobs. For an owned record, non-COMPLETED is 409 `result_not_ready`; a known expiry at or before server time is 410 `result_expired`; unsupported version/legacy coarse identity or permanently missing binding/content is 422 `result_unavailable`. A temporary store failure is 503 `unavailable`, never a permanent 422. No content accompanies these failures. None permits generation, enqueue, input reconstruction or result repair by running the pipeline.

The result envelope is additive; keep `resultRef` opaque and compatible for existing consumers. New clients require `preparedResult.schemaVersion=1`; a reference-only old response is unavailable, not rendered as content or passed to a generation endpoint. Envelope job/task must agree with the selected job and content branch (`summarize` maps to `summary`). Render through safe existing views, never execute returned HTML. Optional assetId is absent when not actually supplied; submittedLevel is recorded submission metadata, never the current preference.

`content` is the final allowlisted user-facing payload returned by successful generation, including rendered translation terms/overlays. Preserve compatible display fields such as the existing rendered glossary; additions may not expose model IDs, object keys, credentials, cost or request internals. Persist the owner-specific final output rather than only the shared cached base. The same immutable payload is returned while available; serialization transport fields may differ but content is not recalculated. Server-stored expiry is authoritative, initialized using the existing configured result TTL (currently 3600 seconds), and never extended by reads/retries. Authenticated job/state/result responses use `Cache-Control: private, no-store`; a resultRef obtained from state is not a capability or alternate expiry bypass.

Summary reproducibility preserves the exact existing `{code: string, data: string}` object. Both fields are required and no extra object fields are admitted. A malformed/missing object or legacy flattened string cannot be converted into successful prepared content by concatenation, guessed defaults or re-execution; apply the existing controlled protocol/unavailable behavior as appropriate to capture versus read. This field correction retains preparedResult v1 and the ownership, expiry, task and read-only obligations above.

### C2 — Prepared Summary Contract Fixtures

This synthetic positive envelope includes the exact safe content emitted by an instantiated existing `SummaryResultDTO`, including separate code/data availability statements. It is a DTO/schema fixture, not a running-worker or authorized database result. Each negative case replaces only the nested reproducibility value; validate the complete ResultResponse so the envelope and selected content branch remain part of the check.

```yaml
contract-fixtures: prepared-summary-v1
schema: '#/components/schemas/ResultResponse'
validEnvelope:
  resultRef: opaque-summary-contract-example
  preparedResult:
    schemaVersion: 1
    jobId: job-summary-contract-fixture
    taskType: summarize
    submittedLevel: expert
    preparedAt: '2026-10-05T00:00:00Z'
    expiresAt: '2026-10-05T01:00:00Z'
    content:
      status: ok
      task: summary
      meta: {}
      cached: false
      summary:
        tldr: Synthetic summary
        contributions: [Synthetic contribution]
        method: Synthetic method
        results: Synthetic result
        limitations: Synthetic limitation
        reproducibility:
          code: Synthetic code availability
          data: Synthetic data availability
        anchors: []
rejectReproducibilityReplacements:
  - Flattened legacy text
  - {data: Synthetic data availability}
  - {code: Synthetic code availability}
  - {code: 123, data: Synthetic data availability}
  - {code: Synthetic code availability, data: null}
  - {code: Synthetic code availability, data: Synthetic data availability, extra: unexpected}
  - [Synthetic code availability, Synthetic data availability]
```

Resolve the shared Reproducibility reference and require the positive complete envelope to pass and every substitution to fail. Restore the former `type: string` property in a separate in-memory schema to confirm regression sensitivity: it must reject the actual DTO object and accept the flattened-string substitution. Preserve the shared schema and successful DTO values; fixing their source to fit the former string property is not an alternative.

### C2 — Prepared Translation Contract Fixtures

Translation references the bare DocModel definition, not the root DocModelResponse union containing building/unavailable wrappers. These fixtures validate complete envelopes; negative cases replace only nested docModel. The positive fixture represents synthetic final personalized content, not a running-worker result.

```yaml
contract-fixtures: prepared-translation-v1
schema: '#/components/schemas/ResultResponse'
validEnvelope:
  resultRef: opaque-prepared-result-example
  preparedResult:
    schemaVersion: 1
    jobId: job-contract-fixture
    taskType: translate
    preparedAt: '2026-10-03T00:00:00Z'
    expiresAt: '2026-10-03T01:00:00Z'
    content:
      status: ok
      task: translate
      translation:
        docModel:
          meta:
            paperId: '2401.00001'
            version: 1
            title: '개인 용어가 적용된 번역'
            provenance:
              sourceTier: native_html
              parserVersion: docmodel-parser@4
              schemaVersion: '1'
              generatedAt: '2026-10-03T00:00:00Z'
          fullText: '사용자의 준비 시점 용어를 보존한 번역입니다.'
          sections: []
        keptTerms: []
rejectDocModelReplacements:
  - {status: building, retryAfterMs: 1000}
  - {status: license_unavailable}
  - {status: source_unavailable, reason: missing}
  - {status: ok, docModel: {}}
```

Validate the positive envelope and every negative replacement against the whole ResultResponse with resolved local/external references. Also reject a malformed bare document missing meta.provenance. Schema checks do not establish runtime personalization correctness.

Verification uses Python Draft202012Validator with a local reference registry and format checks against both complete envelope fixtures. Translation checks include all four wrapper substitutions plus a bare document missing provenance. Restoring the prior root reference in an in-memory schema must reject the valid bare-document fixture and accept the three unavailable/building wrappers, confirming sensitivity to that prior defect. Summary checks and their string-property regression are specified above. These are payload-schema checks, not a full OpenAPI/AsyncAPI conformance pass or application execution.

**Executed schema verification (2026-10-05):** `../../verification/verify-prepared-result-contracts.py` parsed all seven YAML blocks, matched the positive summary content to the actual synthetic `SummaryResultDTO.to_dict()` output, accepted both complete positive envelopes and rejected seven summary plus five translation negatives. Both original schema defects were reproduced separately in memory. Against the byte-identical pre-change archive, the OpenAPI structure differs only at the authorized reproducibility property and every existing non-OpenAPI YAML block is preserved. Run from the workspace root with `PYTHONDONTWRITEBYTECODE=1 uv run --no-project --with pyyaml --with jsonschema --with pydantic aidlc/spaces/default/intents/261001-rem-2-phase-7-frontend-v/verification/verify-prepared-result-contracts.py`. This evidence does not establish real-store, worker, browser, authorization or operational acceptance.

### C5 — Asset and Context Semantics

Preserve paperId, assetId and optional version through the BFF to the existing licensed asset service. Omitted version follows the established paper-ID revision fallback; do not silently default a versioned paper to v1. Validate path segments/encoding so identifiers cannot escape their route. Server delivery authenticates, checks paper/version membership and license before bytes. Private namespace refusal remains indistinguishable from absence.

BFF uses explicit redirect refusal (`manual` or `error`, not default-follow), accepts only successful image content, preserves `private, max-age=60` and `nosniff`, and collapses invalid/non-image/denied/missing upstream delivery to empty 404 with no-store. Existing backend license-unavailable JSON must never pass as an image. Session Set-Cookie values from an actual upstream response are relayed separately even on error; a timeout has no fabricated cookies. The browser image-error event does not expose HTTP status, so show generic failure unless verified session information supports more detail. Private cache hits are not new authorization checks.

```typescript
// C5 shared context: internal UI model, not an authorization token.
type PaperAssetContext = Readonly<{
  ownerContextId: string;
  contextGeneration: number;
  paperId: string;
  assetId: string;
  version?: number;
  caption?: string;
  textEquivalent?: string;
}>;
// U1 supplies owner/paper context; U3 supplies authorized document asset identity.
// Missing identity disables loading. Missing meaningful equivalent is a gap,
// not permission to mark the main image decorative. Context changes clear views.
```

## C3 — SSE and Resume Specification

GET `/bff/api/content-jobs/{jobId}/events`, authenticated with the same session. A 200 response is `text/event-stream`, no-store at the BFF, incrementally relayed without JSON buffering. A frame uses real LF delimiters:

```text
id: <opaque-event-id>
data: {"eventId":"<same-id>","jobId":"<selected-job>","seq":3,"state":"RUNNING","timestampUs":1000000}

```

The terminating empty line is mandatory; literal backslash-n bytes are not delimiters. Standard unnamed/message events preserve existing `onmessage` consumption.

```yaml
shared-schema: content-job-events-v1
jsonSchema:
  $schema: https://json-schema.org/draft/2020-12/schema
  type: object
  required: [eventId, jobId, seq, state, timestampUs]
  properties:
    eventId: {type: string, minLength: 1}
    jobId: {type: string, minLength: 1}
    seq: {type: integer, minimum: 1, maximum: 9007199254740991}
    state: {enum: [SUBMITTED, ACCEPTED, QUEUED, RUNNING, COMPLETED, FAILED, ABSTAINED]}
    timestampUs: {type: integer, minimum: 0, maximum: 9007199254740991}
    payload:
      type: object
      properties:
        resultReady: {type: boolean}
        abstainReason: {type: string}
        error:
          type: object
          required: [errorType, message, retryable]
          properties:
            errorType: {type: string}
            message: {type: string}
            retryable: {type: boolean}
            retryAfterSeconds: {type: integer, minimum: 0}
      additionalProperties: true
  additionalProperties: true
cursor:
  precedence: [Last-Event-ID, lastEventId-query]
  initial: absent
  interpretation: opaque authorized-job event lookup to per-job seq
  invalidOrUnknown: 400 cursor_invalid after authentication and job ownership check
  otherOwnerOrUnknownJob: 404 not_found before cursor disclosure
  exhaustedTerminalStream: 204 no content
```

RDS currently exposes database event_id while replay filters per-job seq; do not cast that event ID to seq. Resolve it inside the authorized job's stored history. Preserve emitted legacy IDs when resolvable through that history; adapter-generated `jobId:seq` IDs are accepted only after exact job and corresponding event verification. Cross-job IDs cannot advance another stream. Cursors are lookup handles, not credentials. A malformed/unknown cursor does not silently skip to an arbitrary sequence.

Native EventSource handles its own reconnect header. A newly constructed source supplies the last received cursor in `lastEventId`; the BFF forwards both mechanisms with header precedence. Close on observed terminal state and stop unnecessary polling. If reconnect is already past the terminal event, 204 stops native reconnect; the initial/current authorized state read supplies terminal presentation. SSE errors do not expose HTTP status in browser code. Recover through state polling and authoritative access signals, not guessed 401/404 from onerror. A deliberate fresh replay from absent cursor may recover history while suppressing duplicates; do not clear cursor/identity blindly in an infinite loop.

## C4 — Frontend Capability Contract

```typescript
type TaskType = 'summarize' | 'translate';
type JobState = 'SUBMITTED' | 'ACCEPTED' | 'QUEUED' | 'RUNNING' |
  'COMPLETED' | 'FAILED' | 'ABSTAINED';
type JobIdentity = Readonly<{jobId: string; state: JobState}>;
type OperationContext = Readonly<{
  ownerId: string; paperId: string; contextGeneration: number;
}>;
type RecoveryReference = Readonly<{opaqueId: string}>;
type SubmissionAttempt = Readonly<{attemptId: string}>;
type PreparedAttempt = Readonly<{
  attempt: SubmissionAttempt;
  persistence: 'stored' | 'memory-only';
}>;
type RecoveryUnavailableReason = 'missing-original' | 'owner-mismatch' |
  'invalid-identity' | 'access-unavailable' | 'obsolete-context' |
  'superseded-attempt' | 'request-in-flight';
declare class SubmissionError extends Error {
  readonly category: RecoveryUnavailableReason | 'invalid-input' |
    'hash-unavailable' | 'transport-failure';
}
type RecoveryAvailability =
  | Readonly<{available: true; reference: RecoveryReference}>
  | Readonly<{available: false; reason: RecoveryUnavailableReason}>;
type RestoredAttempt =
  | Readonly<{found: true; attempt: SubmissionAttempt}>
  | Readonly<{found: false; reason: RecoveryUnavailableReason | 'no-stored-attempt'}>;
interface SubmissionCommands {
  prepareAttempt(context: OperationContext, task: TaskType,
    input: Readonly<Record<string, unknown>>, signal: AbortSignal): Promise<PreparedAttempt>;
  submit(context: OperationContext, attempt: SubmissionAttempt,
    signal: AbortSignal): Promise<JobIdentity>;
  recoveryAvailability(context: OperationContext,
    attempt: SubmissionAttempt): Promise<RecoveryAvailability>;
  restoreAttempt(context: OperationContext, task: TaskType): Promise<RestoredAttempt>;
  recover(context: OperationContext, reference: RecoveryReference,
    signal: AbortSignal): Promise<JobIdentity>;
}
interface JobQueries {
  // Raw unknown must be validated against C1/C2 before entering a view model.
  readState(context: OperationContext, jobId: string, signal: AbortSignal): Promise<unknown>;
  readResult(context: OperationContext, jobId: string, signal: AbortSignal): Promise<unknown>;
}
type OnActualJobReceived = (context: OperationContext, job: JobIdentity) => void;
```

ContentJobApi alone resolves RecoveryReference to immutable captured original input/key for the current owner; it is not a server auth token and cannot authorize different parameters. Missing original data disables resend; a hash cannot reconstruct input. Persistence failure with intact in-memory originals is a separate warning. Storage representation remains Functional Design work and may not store secrets.

**Attempt lifecycle:** prepareAttempt validates context/input, captures a detached immutable input snapshot and derived key, attempts safe persistence and returns the attempt handle **before any network submission**. Failure to hash/capture rejects preparation without POST; memory-only persistence is reported honestly. JobSubmissionForm retains the handle before calling submit. submit and recover use captured data exclusively, never accept an editable draft, and serialize actions for the same attempt. Opening a form and preparing an attempt are not themselves submit actions.

recoveryAvailability is a read-only local identity/eligibility lookup for that exact attempt, available after a lost response without a jobId. It returns a recovery reference only if owner, current context, captured original/key and active attempt agree, and no submission is currently in flight. A transient submit rejection does not destroy its handle. Access loss or unresolved original data returns an explicit unavailable reason; later backend authorization still applies. recover rechecks eligibility atomically at activation, so a previously obtained reference cannot bypass owner/context changes, in-flight exclusion or supersession.

Editing the visible draft does not modify or supersede its uncertain original attempt. Preparing a deliberately new attempt for the same owner/paper/task supersedes the prior active handle; old handles and async completions cannot select a new view. The API must check current context/attempt before completing preparation as well as before network actions. Returning from account/paper navigation does not resurrect obsolete-context handles.

restoreAttempt performs no POST: it selects only the safely persisted original attempt in the exact current owner/paper/task namespace, verifies the stored original/key, and binds a new local handle to the current context generation. A surviving key without original parameters yields missing-original; a persisted prior-owner record yields owner-mismatch and cannot be used. Restoring does not overwrite a newer in-memory active attempt. Corrupt identity yields invalid-identity. Storage representation remains deferred; these eligibility outcomes do not.

**Lost-response contract example:** Prepare input A and retain attempt A; submit A rejects after its response is lost. The user edits the visible draft to B without starting a new attempt. recoveryAvailability(context, attemptA) returns a reference for A, and explicit recover(context, referenceA) resends A with its original key, never B. The actual returned backend job/state reaches the parent only if context/attempt A is still current. If the user instead explicitly prepares a new attempt B or switches owner/paper, availability/recover for A returns or throws a typed superseded/obsolete/owner failure without POST. Neither ordinary replay nor permitted failed-dispatch replacement changes the captured original.

Preparation, submit and recover failures expose controlled typed errors classified by RecoveryUnavailableReason or a transport/input category; no raw exception text reaches UI. Required verification includes handle availability after lost response, edited-draft isolation, missing originals on reload, supersession between lookup and recover, owner/context change during preparation, and duplicate activation while submit is pending.

JobSubmissionForm receives commands and owns uncertainty before jobId exists. PaperDetailIsland accepts OnActualJobReceived only for its current context, invalidates old-job subscriptions/cache work, and mounts tracking for the actual returned identity. A late old-job response is invalid even if owner/paper match. SummaryModal receives only JobQueries and dismissal/copy capabilities, never commands. JobStatus's explicit same-request action is distinct from command-free tracking recovery. Result-read retries preserve the exact job; all recovery focus behavior follows the approved refined mockups.

## C6 — Queue Dispatch Message

```yaml
asyncapi: 2.6.0
info: {title: Content job dispatch, version: 1.0.0}
defaultContentType: application/json
channels:
  content-jobs:
    description: Logical existing queue; actual queue address comes from environment configuration
    subscribe:
      operationId: receiveContentJob
      message:
        name: ContentJobDispatchV1
        payload:
          type: object
          required: [schemaVersion, jobId, dispatchId]
          properties:
            schemaVersion: {type: integer, enum: [1]}
            jobId: {type: string, minLength: 1}
            dispatchId: {type: string, minLength: 1}
          additionalProperties: true
x-authority:
  ownerAndInput: load authoritative durable job; never trust message userId or paperId
  taskMapping: {summarize: summary, translate: translate}
  supportedTasks: [summarize, translate]
  transportDelivery: at-least-once
  execution: gated by C7 durable effect and fencing
```

One service dispatch operation connects to the real queue adapter. It does not call ContentJobQueue.enqueue if that recursively creates another submission. DispatchId is a durable correlation/claim identity, not a guarantee that the queue delivers once. Validate it against the job's dispatch record. Unsupported/mismatched messages are quarantined through the existing queue error/redrive policy without running generation or disclosing job data. Never accept message fields as an alternative source when the job is absent.

The new worker also recognizes the existing unversioned payload carrying jobId/userId/paperId/version/task/targetLang/persona/scope/abstract only during the migration window. It verifies supplied identity/parameters against the durable job, maps task values explicitly, ignores deprecated untrusted abstract as a source, and uses authoritative stored input. No jobId means no executable durable-job message. An early message while submission is still SUBMITTED does not drive invalid transitions: defer/retain for dispatch reconciliation. A durable accepted job can advance QUEUED → RUNNING under C7 authority.

Install the compatible worker before emitting v1 messages; drain or isolate old workers first. Do not share new messages with an old worker that assumes the previous fields. Queue acknowledgement follows durable terminal outcome; duplicate terminal messages are no-op acknowledgements, not executions.

## C7 — Durable Outcome and Reconciliation Protocol

The service owns all four backend entities; the worker owns no alternate persistence. Operations below are normative atomicity/authority boundaries, not a choice of database tables. Internal field names do not become public HTTP fields.

```yaml
shared-schema: content-job-worker-ports-v1
interfaces:
  query:
    readOwnedState: {input: [trustedOwner, jobId], output: 'snapshot | not_found'}
    readOwnedResult: {input: [trustedOwner, jobId, serverNow], output: 'prepared | not_found | not_ready | expired | unavailable | transient_failure'}
    listOwnedEvents: {input: [trustedOwner, jobId, opaqueCursor], output: 'ordered_events | cursor_invalid | not_found'}
    forbiddenSideEffects: [enqueue, generation, new_submission, current_settings_render]
  worker:
    claimExecution:
      input: [jobId, dispatchId, workerId, serverNow]
      output: 'active_with_fence | defer | terminal | reconciliation_required'
      guarantees: [authorized_durable_job, legal_state_CAS, single_active_publication_fence, durable_effect_intent_before_generation]
    renewExecution:
      input: [jobId, fence, serverNow]
      output: 'renewed | fenced'
    persistPrepared:
      input: [jobId, fence, finalSafePayload, preparationIdentity, serverNow]
      output: 'immutable_binding_committed | existing_same_binding | fenced | failure'
      guarantees: [owner_bound, exact_payload, no_settings_recompute, durability_before_success]
    publishOutcome:
      input: [jobId, fence, outcome, preparedResultId, serverNow]
      output: 'terminal_committed | already_terminal | fenced | failure'
      guarantees: [legal_state_CAS, event_and_state_consistency, completed_requires_committed_result, no_terminal_regression]
    reconcileExpiredExecution:
      input: [jobId, observedFence, serverNow]
      output: 'still_active | completed_from_prepared | failed_uncertain | already_terminal'
      guarantees: [atomic_fence_revocation, no_generation, no_key_release_for_ambiguous_effect]
```

Claim, renewal, snapshot publication and reconciliation serialize on the same authoritative job/effect fence. Server time governs lease validity. Worker heartbeats renew before expiry; message visibility alone is not publication authority. Reconciliation rechecks the live lease/fence atomically so it cannot fail a renewed active worker based on a stale observation. A revoked/expired fence cannot bind content or publish outcomes. The heartbeat/lease/visibility configuration must be bounded and validated together before execution; numerical tuning is not a product SLA and belongs to NFR/Functional Design.

PersistPrepared records immutable final content and an owner/job-bound identity durably. For separate blob and metadata stores, only a completed durable blob plus committed exact metadata binding counts as prepared; an orphan blob is not permission to guess content or rerun generation. Repeated writes with the same job/fence must match the existing prepared identity; conflicting content is an error, never overwrite. Publication checks that binding before committing COMPLETED, expiry and the corresponding event. Expiry is fixed once, not renewed on redelivery. Account deletion/owner invalidation prevents late worker recreation of purged records.

| Actual pipeline outcome | Required job outcome | Retry interpretation |
|---|---|---|
| Valid `status: ok`, matching task and final prepared payload | COMPLETED only after durable binding | Read-only result access |
| Explicit `abstain` with safe reason | ABSTAINED | Retain binding; no terminal restart |
| `cost_degraded` or `source_unavailable` | FAILED with safe classified error | No automatic same-job execution; condition may be transient but terminal job stays terminal |
| `pending` despite worker enqueue-disabled mode, malformed/mismatched success or thrown error | FAILED with safe protocol/execution error | Retain binding; no blind release/re-execution |
| Ambiguous generation and no durable exact prepared result | FAILED with `generation_outcome_uncertain`, retryable false | Keep job/key binding; no generation again |

A source/unavailable status is not automatically a success; explicit AbstainDTO remains abstention even where its reason names upstream unavailability. Public error messages come from a safe mapping, not exception text. A terminal retryable flag is descriptive of a cause and never authorizes reopening the job.

| Interruption window | Reconciliation behavior |
|---|---|
| Before durable effect-start intent | Only a fresh valid claim may invoke generation; no unrecorded invocation is allowed |
| Intent committed, before invocation or while invocation/outcome is uncertain | No second invocation. Wait for valid active worker or, after atomic fencing/reconciliation, fail safely if no durable exact result exists |
| Generation returned, before exact binding committed | Same conservative rule; a memory-only result lost on crash cannot be reconstructed from current cache/settings |
| Exact binding committed, before terminal publication | Reconcile from that binding and publish completion without invoking generation |
| Terminal publication committed, before queue acknowledgement | Acknowledge duplicate delivery without work or state regression |

This provides conservative at-most-one worker generation invocation per retained job execution authority, not an exactly-once guarantee for a remote provider. Existing pipeline-internal chunking/validated retries are distinct from blindly restarting the whole job after a worker crash. A durable claim with no recoverable result can legitimately end FAILED under the human-selected policy. Queue-dispatch failure before an effect starts is the separate preserved key-release case; it must not be used to bypass ambiguous-generation protections.

## C8 — Compatibility and Transport Policy

```yaml
shared-schema: phase7-compatibility-v1
specVersion: 1.0.0
resultEnvelopeVersion: 1
queueMessageVersion: 1
newClientRequires: [prepared_result_v1, state_event_seq, authorized_cursor_resolution]
legacyResultResponse: controlled_unavailable_without_generation
unknownResultEnvelopeVersion: controlled_unsupported_without_generation
unknownQueueMajorVersion: quarantine_without_execution
breakingChange: consumer_agreement_and_explicit_version_boundary
additiveChange: optional_fields_with_consumer_compatibility_tests
transport:
  ordinaryGatewayTimeoutMs: 10000
  assetGatewayTimeoutMs: 10000
  sseHeaderTimeoutMs: 15000
  sseBodyTotalTimeoutMs: null
  ordinaryGetRetry:
    maxRetries: 1
    delayMs: 1500
    statuses: [502, 503, 504]
    networkFailure: true
  automaticPostRetry: false
  swrFallbackIntervalMs: 2000
```

U1/U3 maintain provider specifications; consumers define acceptance needs and approve breaking changes. Semantic spec versioning does not make an incompatible unversioned HTTP mutation safe. Preserve old reference consumers with additive fields and actual tests; do not expose the new UI against a backend lacking required capabilities. A legacy state snapshot without seq cannot be merged as if ordered; use controlled compatibility failure rather than a fabricated watermark.

Ordinary GET retry is at the BFF relay only; avoid layered retries multiplying attempts. Polling interval is fixed configuration, not a promise to finish a slow request every two seconds. Do not overlap pending fallback reads; cancel/ignore obsolete ones. Native SSE reconnect is a separate mechanism; its header timeout does not truncate a healthy stream body. Propagate browser cancellation to upstream transport where supported and clean up server stream resources. Existing search/evidence budgets are untouched.

Forward session Cookie to the configured gateway, relay every upstream Set-Cookie separately on successful/error responses, and preserve CSRF/CSP controls. Never accept a caller-selected proxy host or pass client principal headers as trust. Use explicit redirect refusal for protected job as well as asset traffic to avoid following a redirect into unverified destinations. Unknown JSON/errors become safe UI failures rather than raw internal text. NFR9's 300/500/200 ms measurements remain separate from timeout budgets; telemetry includes construction-to-open latency in milliseconds with content/credential scrubbing.

Rollout compatibility constraints: additive persistence first; reader-capable backend and compatible workers before new-message emission; all workers consuming new messages must support C6/C7; enable new UI only after the prepared-result and ordering contracts are available. Delivery Planning specifies concrete rollout/exposure and rollback commands across existing runtimes. Rollback must retain readable prepared records and may not reintroduce an old worker that blindly regenerates or publishes coarse results for in-flight v1 jobs. Exact deployment gates belong to the owning stages; no atomic multi-runtime deploy is assumed.

## Verification and Requirement Coverage

| Contract | Principal coverage | Required proof |
|---|---|---|
| C1 | FR1, FR4, US1.1–US1.5, US4.2 | Authenticated receipt, real dispatch, immutable same-key replay, definite failure replacement, concurrent/ambiguous dispatch handling |
| C2 | FR3, FR3.5, US3.1–US3.4 | Both payload branches, exact personalized identity after settings changes, 401/404/409/410/422/503, no generation/enqueue on reads, no TTL bypass |
| C3 | FR2.1–FR2.4, US2.1–US2.5 | Real LF framing, multiple jobs with different event-id/seq values, cursor precedence/replay, terminal 204, state watermark, obsolete-response suppression |
| C4 | FR4/FR6/FR7 | Pre-job handoff, missing originals, replacement identity, read-only capabilities, recovery focus and owner-context changes |
| C5 | FR5, US5.1–US5.3 | Authorized/denied/versioned delivery, no redirects, cookie/error fidelity, image metadata/equivalents and private-cache distinction |
| C6/C7 | FR2.5, US2.6, US3.4 | Actual DTO mapping, legacy/new queue schemas, real dispatch wiring, fenced crash windows, prepared binding before completion and no second invocation |
| C8 | NFR1–NFR12 as applicable | Cross-version tests, timeout/retry ownership, scrubbed telemetry, existing protection and release-evidence checks |

No current application tests or staging measurements are claimed. U1 must verify these backend guarantees for both tasks even when its browser demo is summarize; U2 verifies translation UI and broader recovery cases. U3 verifies assets. A passing schema check is not proof of authorization, atomicity or crash safety. NFR11 requires test-after ordering, ≥80% new-code coverage and current suites/CI; NFR8's Week 2 review remains a named Delivery Planning obligation.

## Open Questions

| Contract | Question | Blocks |
|---|---|---|
| C7 | Choose physical prepared-payload persistence, atomic fence/binding/publication operations and orphan/account-deletion cleanup in Functional Design; prove the protocol under crash/concurrency fixtures | U1 implementation approval |
| C7 | Pin lease/heartbeat/visibility/reconciliation timing and maximum legitimate pipeline execution behavior together in NFR/Functional Design; no active-worker false failure | U1 worker execution |
| C8 | Validate actual gateway authentication/CSRF wiring for the existing session_id cookie identified in backend/middleware/auth.py:71 | U1 integration verification |
| C8 | Pin mixed-version deployment, queue drain/exposure and rollback procedures against actual environment configuration | U1 release/exposure |
| C5 | Verify actual authorized captions/text/table equivalents; resolve absent equivalents without invented OCR scope | U3 accessibility completion |

These are assigned implementation/environment parameters, not permission to defer approved user outcomes. If they demonstrate the specified guarantees cannot be achieved within scope, stop for a concrete design/scope decision before coding. No new product assumptions are introduced.
