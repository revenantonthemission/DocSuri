# U1 Business Rules

## Sources

The confirmed U1 design summary, approved requirements/story acceptance and contracts C1–C4/C6–C8 govern these rules. YAML is authoritative; the summary below is derived. Logical rules do not claim implemented transactions or passing runtime checks.

Current resolving inputs are `../../../inception/units-generation/unit-of-work.md`, `../../../inception/units-generation/unit-of-work-story-map.md`, `../../../inception/requirements-analysis/requirements.md`, `../../../inception/domain-design/components.md` and `../../../inception/contract-design/contract-summary.md`. The confirmed Q3 amendment makes the approved C2 shared code/data object explicit in existing capture/read rules, while retaining their IDs and current Unit responsibility.

## Rule Catalogue

```yaml
rules:
  - id: BR1.1
    statement: Authenticate before protected operations and derive principal through the trusted gateway.
    category: authorization
    applies_to: job commands and queries
    trigger: incoming protected operation
    logic: IF no trusted owner THEN return authentication-required; ELSE constrain operation to that owner's records.
    violation_behaviour: No protected writes or content; ignore forged client principal fields.
    source: [FR1.2, NFR1, C1, C2]
  - id: BR1.2
    statement: Validate supported input and start submission only from explicit activation.
    category: validation
    applies_to: SubmissionDraft and job input
    trigger: prepare or submit
    logic: IF input is valid under C1 and current context remains authorized THEN capture it; only an explicit command may send it.
    violation_behaviour: Controlled input failure; no success, extra task types or automatic submit/hash/idempotency-record creation on selection/mount. An editable initial draft requires no captured attempt.
    source: [FR1.1, FR1.2, C1, C4]
  - id: BR1.3
    statement: Derive deterministic identity from the original owner and exact captured serialized request.
    category: calculation
    applies_to: IdempotencyKey
    trigger: prepareAttempt
    logic: IF identity and hashing are available THEN SHA-256 hashes userId:paperId:taskType:JSON.stringify(params); identical serialized inputs yield identical key.
    violation_behaviour: Controlled hashing/identity failure; never random-key fallback or cached different-owner key.
    source: [FR1.3, NFR4, C4]
  - id: BR1.4
    statement: Persist only the versioned allowlisted original-request metadata and validate it before restore.
    category: validation
    applies_to: IdempotencyKey persistence
    trigger: write or restore record
    logic: IF namespace/schema/owner/input/digest match THEN restore immutable originals; ELSE mark recovery unavailable. Storage failure with intact memory is a reported memory-only outcome.
    violation_behaviour: No guessed defaults, arbitrary fields, credentials or result/document content; no false persistence success.
    source: [FR1.4, NFR4, Q2, C4]
  - id: BR1.5
    statement: Attempt handles precede POST and action eligibility is rechecked for exact current context and attempt.
    category: policy
    applies_to: submission recovery
    trigger: preparation completion, availability lookup, submit or recover
    logic: Reserve a preparation revision before async work; publish memory/storage only after a current owner/context/revision check in the serialized local publication section. IF owner/context/attempt is current and no action is in flight THEN use captured originals; ELSE reject without POST. Draft editing does not mutate originals; explicit new preparation supersedes old attempt authority.
    violation_behaviour: Typed unavailable reason; stale async completion cannot select a current job or overwrite a newer saved attempt.
    source: [FR4.1, FR4.3, C4]
  - id: BR1.6
    statement: Accept atomically under an owner-scoped retained binding and preserve actual returned identity/state.
    category: constraint
    applies_to: DurableJob and SubmissionBinding
    trigger: initial submission or same-key resend
    logic: IF owner/key binding exists THEN return its original job/state; ELSE create one durable job and binding atomically. Retained mismatched input cannot alter the original request.
    violation_behaviour: No duplicate job/execution or terminal-state reset; inconsistent replay input produces controlled failure, not another dispatch.
    source: [FR1.2, FR1.3, FR4.2, C1]
  - id: BR1.7
    statement: Serialize dispatch and release a binding only for proven non-dispatch before generation.
    category: policy
    applies_to: SubmissionBinding dispatch outcome
    trigger: send result or recovery
    logic: IF a new-protocol retained binding is NOT_STARTED THEN initial submit, explicit replay or recovery actor may contend for its one T2 first-send claim. IF trusted send confirms delivery THEN settle acceptance; definite rejection with no accepted message/effect fails/releases atomically; SENDING/UNKNOWN never grants another send.
    violation_behaviour: Unknown send cannot become a released key. Repeated queue delivery cannot grant repeated execution.
    source: [FR1.2, FR4.2, C1, C6]
  - id: BR1.8
    statement: All browser job operations retain same-origin BFF routing and session/response fidelity.
    category: authorization
    applies_to: job transport and stream relay
    trigger: submit/state/events/result traffic
    logic: Route through the approved BFF/gateway; forward Cookie and separate Set-Cookie values on success and error; retain stream framing/cursors and existing protections.
    violation_behaviour: No bypass, arbitrary proxy destination, protected redirect following or raw internal error body.
    source: [NFR1, NFR12, C1, C3, C8]
  - id: BR2.1
    statement: Only a durable authorized job/dispatch may grant initial worker execution.
    category: authorization
    applies_to: worker queue input
    trigger: queue receipt
    logic: IF message/version/dispatch identity agree with an existing new-protocol job THEN load authoritative owner/task/input; defer execution until acceptance is durable. Terminal legacy messages are acknowledgement-only. Active legacy work without new authority is drained/isolated before cutover, never automatically adopted or granted generation from ledger absence alone.
    violation_behaviour: Quarantine unsupported/mismatched input; never trust duplicated message owner or deprecated abstract as a source.
    source: [FR2.5, C6]
  - id: BR2.2
    statement: Commit effect-start intent before one whole-pipeline invocation and fence all publication operations.
    category: constraint
    applies_to: GenerationEffect
    trigger: claim, renewal, persist or publish
    logic: Serialize on current job/effect authority using server time. A first valid claim commits INTENT before invocation; existing intent never grants another invocation. Only current unexpired fence may renew or write.
    violation_behaviour: Fenced/deferred outcome, no blind effect deletion or second invocation after ambiguity.
    source: [FR2.5, C7]
  - id: BR2.3
    statement: Bind exact validated final prepared content durably before completion.
    category: constraint
    applies_to: PreparedJobResult
    trigger: persistPrepared
    logic: IF current fence and job/owner/task match successful C2-validated final payload, including the required summary code/data string object or bare translated document, THEN commit immutable snapshot and binding in the same authority; preserve final string values exactly and require repeats to match existing content identity.
    violation_behaviour: No overwrite, base-cache substitution, invalid translation wrapper or completion on failed persistence. Missing/malformed/flattened reproducibility is a safe protocol failure, never guessed conversion or another generation invocation.
    source: [FR2.5, FR3.5, Q1, C2, C7]
  - id: BR2.4
    statement: Publish only legal truthful outcomes with state and event committed together.
    category: policy
    applies_to: DurableJob lifecycle
    trigger: publishOutcome
    logic: Successful validated bound payload becomes COMPLETED; explicit abstain becomes ABSTAINED; unavailable, degraded, unexpected pending, malformed or failed execution becomes safe FAILED according to C7. Recheck current authority and expected state.
    violation_behaviour: No fabricated success/reference or terminal regression; use safe mapped error/reason.
    source: [FR2.1, FR2.5, C7]
  - id: BR2.5
    statement: Reconcile expired execution without regenerating and without failing a renewed active lease from stale evidence.
    category: policy
    applies_to: GenerationEffect reconciliation
    trigger: expired authority or duplicate delivery
    logic: Atomically recheck lease/fence; still-active remains active. Otherwise revoke authority and publish from committed exact snapshot, or fail uncertain when no recoverable result exists. Never invoke generation or release the ambiguous-effect binding.
    violation_behaviour: Controlled unresolved/fenced result; no assumption of provider exactly-once completion.
    source: [FR2.5, C7, contract-Q13]
  - id: BR3.1
    statement: Authorize queries before existence, state, cursor or expiry disclosure.
    category: authorization
    applies_to: owned job reads
    trigger: state/event/result request
    logic: IF unauthenticated THEN 401; IF missing/not-owned THEN identical 404; only an owned job proceeds to result/cursor predicates.
    violation_behaviour: No other-owner content, existence or expiry oracle.
    source: [FR3.3, FR3.5, NFR1, C2, C3]
  - id: BR3.2
    statement: Apply result-read precedence and zero-generation query capabilities.
    category: policy
    applies_to: result delivery
    trigger: authorized result read or retry
    logic: Owned non-COMPLETED yields 409; expired completed result yields 410; unsupported/unresolvable prepared identity or permanently malformed C2 content yields 422; temporary store failure yields 503; valid exact unexpired payload yields 200. Summary reproducibility must preserve the shared required code/data strings without coercion. Query capability never invokes commands/generation/render-from-current-settings.
    violation_behaviour: No generation/enqueue/POST/key rotation on any read outcome; safe unavailable feedback and no guessed storage URLs.
    source: [FR3.1, FR3.2, FR3.3, FR3.5, C2]
  - id: BR3.3
    statement: Fixed expiry and owner deletion govern both content and reference availability.
    category: constraint
    applies_to: prepared results and lifecycle cleanup
    trigger: completion, read, purge or late write
    logic: Set expiry once at completion with configured TTL; reads/redelivery never extend it. Delete owner/job and dependent records without late resurrection; expired payload cleanup preserves owned expiry disclosure while job exists.
    violation_behaviour: No alternate TTL bypass, purged-job recreation or post-expiry protected content.
    source: [FR3.3, FR3.5, C2, C7]
  - id: BR4.1
    statement: Resolve event IDs only inside the authorized job history and preserve actual framing/order.
    category: validation
    applies_to: SSE replay
    trigger: stream open or reconnect
    logic: Prefer Last-Event-ID header then lastEventId query; absent starts at beginning. Lookup opaque ID in current job events; invalid/unknown cursor yields 400 after ownership. Exhausted terminal history yields 204. Frames use actual line/event delimiters.
    violation_behaviour: No ID-to-sequence cast, cross-job cursor jump or malformed escaped delimiter delivery.
    source: [FR2.3, C3]
  - id: BR4.2
    statement: Reconcile current state by watermark and history separately by event identity.
    category: constraint
    applies_to: JobState
    trigger: event or poll observation
    logic: Validate owner/job/context and seq; apply state only at nonregressing watermark. Fill missing earlier history in order without regressing state; suppress duplicate IDs and unchanged announcements.
    violation_behaviour: Drop obsolete responses; inconsistent equal-sequence data is a controlled protocol error, not a guessed state transition.
    source: [FR2.1, FR2.2, FR2.3, C1, C3]
  - id: BR4.3
    statement: Keep connection state separate, use fixed fallback, and release obsolete tracking work.
    category: policy
    applies_to: tracking lifecycle
    trigger: connect, failure, restoration, terminal, hide or context change
    logic: Native live stream and nonoverlapping two-second fallback reads share validated state. Restore live stops fallback; terminal/context loss stops unnecessary subscriptions/reads. Temporary network loss marks authorized observations stale; known access loss clears protected data.
    violation_behaviour: No stale-as-live claims, guessed HTTP status from EventSource errors, cancellation or durable offline queue.
    source: [FR2.4, NFR5, C3, C8]
  - id: BR4.4
    statement: Display only observed lifecycle/progress and preserve actual recovered identity.
    category: policy
    applies_to: status and submission feedback
    trigger: render or recovery completion
    logic: Display supported actual backend state and safe reason; no supplied progress means indeterminate. A replacement switches context and invalidates old-job work; uncertain recovery cause uses neutral wording.
    violation_behaviour: No invented percentage/ETA, fabricated ID, old-terminal restart promise or unsupported execution cause.
    source: [FR2.1, FR2.2, FR4.2]
  - id: BR5.1
    statement: Result presentation receives query capability only and preserves prepared submission metadata.
    category: constraint
    applies_to: SummaryModal
    trigger: open, read retry or render
    logic: Open selected authorized result, validate envelope/task/content including the exact required summary code/data object, show recorded submitted level read-only and preserve safe formatting. Unsupported versions/wrappers or malformed/flattened reproducibility become controlled unavailable state.
    violation_behaviour: No mount/selection submission, current-default substitution, unsafe content execution or arbitrary URL resolution.
    source: [FR3.1, FR3.2, FR3.5, C2, C4]
  - id: BR5.2
    statement: Controls, status messages and focus follow the approved accessible interaction rules.
    category: policy
    applies_to: delivered U1 surfaces
    trigger: interaction or meaningful asynchronous change
    logic: Named keyboard-operable controls and visible focus, meaningful deduplicated announcements, accurate progress semantics, modal containment/return and conditional recovery focus. Preserve surviving focus; move to resulting heading only when current target disappears.
    violation_behaviour: No color-only feedback, focus theft/traps, inaccessible disabled-only explanation or fabricated determinate progress.
    source: [FR6.1, FR6.2, FR6.3, NFR10]
  - id: BR5.3
    statement: Contain rendering failures while handling asynchronous errors explicitly.
    category: policy
    applies_to: status boundary and stable parent
    trigger: render failure or network/callback error
    logic: Render failure notifies stable parent for full-page fallback with authorized tracking context; network/callback failure uses inline handling. Tracking reset and safe return never submit.
    violation_behaviour: Safe fallback; no raw stack or loss of all recovery context inside failed subtree.
    source: [FR7.1, FR7.2, NFR6]
  - id: BR5.4
    statement: Report scrubbed diagnostics and real timing without disrupting the user journey.
    category: policy
    applies_to: instrumentation
    trigger: submit/recovery/outcome or connection/render failure
    logic: Report safe Sentry events, connection drops/recovery and construction-to-open milliseconds; retain real identity and distinguish explicit recovery from inferred execution. Diagnostic-delivery failure never recursively reports itself or blocks controls.
    violation_behaviour: No cookies/credentials/document/result/parameter contents in telemetry; no invented latency or cause.
    source: [FR7.3, NFR7, NFR9]
  - id: BR5.5
    statement: Preserve approved visual accessibility and reproducible performance acceptance for delivered surfaces.
    category: constraint
    applies_to: delivered U1 UI and measurement handoff
    trigger: layout or verification planning
    logic: Require applicable text/non-text contrast, visible focus, 200 percent text resize and 320 CSS-pixel reflow. Keep approved staging p95 limits and raw-sample/failure reporting; instrumentation must not count failed operations as successful fast samples.
    violation_behaviour: Surface failed acceptance; do not weaken budgets or claim application conformance from this design.
    source: [FR6.3, NFR9, NFR10]
```

## Rules Summary

| Group | Rules | Purpose |
|---|---|---|
| Submission | BR1.1–BR1.8 | Trusted identity, explicit commands, immutable original request, safe restore and authoritative dispatch |
| Worker | BR2.1–BR2.5 | Durable authorization/intent/fencing, exact binding, truthful outcome and conservative reconciliation |
| Results | BR3.1–BR3.3 | Owner-first query semantics, zero generation, fixed expiry and deletion |
| Events | BR4.1–BR4.4 | Opaque replay, nonregressing observation, connection lifecycle and honest display |
| UI/diagnostics | BR5.1–BR5.5 | Query-only results, accessible focus/messages, containment, instrumentation and binding visual/performance targets |

## Enforcement and Precedence

Authorize first, then validate identity/context, then evaluate operation-specific predicates. Never allow an expired or wrong-owner query to fall through to a generative cache-miss path. For commands, job and binding/effect checks serialize in one authoritative lock order; physical adapters must satisfy the atomic boundaries described in `functional-spec.md`. Rules do not authorize an implementation that merely checks in memory and writes later without revalidation.

All retry metadata is descriptive of the failure cause, not a lifecycle edge. Connection recovery is a query/stream restart; same-request submission recovery is an explicit command using a captured reference. Their rules and controls are intentionally distinct. NFR tuning may refine operational values, never remove these invariants.
