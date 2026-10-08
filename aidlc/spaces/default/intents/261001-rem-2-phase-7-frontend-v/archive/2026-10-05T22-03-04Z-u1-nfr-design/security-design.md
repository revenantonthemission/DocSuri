# U1 Security Design

## Sources

`../nfr-requirements/security-requirements.md`, `../nfr-requirements/reliability-requirements.md`, `../nfr-requirements/tech-stack-decisions.md`, `../functional-design/functional-spec.md`, `../../../inception/contract-design/contract-summary.md` and confirmed `nfr-design-questions.md` govern this design. Actual control operation remains to be verified. Logical patterns below retain existing runtime boundaries rather than replacing authentication or adding certification scope.

## SD-1 — Session Relay and Owner-First Queries

Cross-cutting resource and monitoring constraints also consume `../nfr-requirements/performance-requirements.md`, `../nfr-requirements/scalability-requirements.md` and `../nfr-requirements/observability-requirements.md`: lease/query isolation and diagnostic scrubbing must remain consistent with those targets. These are resolving citations to the actual upstream artifacts, not claims of installed/runtime controls.

Browser calls only the approved same-origin BFF paths. Relay the existing session_id cookie server-side to the configured gateway; remove/untrust caller principal fields and never accept a caller-selected upstream host. Gateway verification supplies trusted request identity. Controller commands/queries use that identity rather than the browser's persisted owner metadata.

Restrict job/state/event/result lookups by trusted owner. Unknown and other-owner records use the same generic not_found 404 body, including expired other-owner jobs. Authentication precedes access; owned result state/expiry validation follows C2's 409/410/422/503 precedence. A reference or key never bypasses owner/TTL checks. Covers **NFR1.1–NFR1.2**.

## SD-2 — Explicit Capability and Serialization Boundaries

The result controller receives an owned-query interface only. Its dependency path has no generation/enqueue/submit/current-settings-render operation. Persisted exact prepared content is read directly; cache misses, legacy references and transient read retries do not call the pipeline. Expose resultRef and preparedResult v1 only through allowlisted serialization; validate job/task/content branch consistency and bare DocModel, including the complete-envelope negative wrappers from Contract Design.

Validate IDs, cursor/input/schema and queue messages at their trust boundary; use bound persistence parameters and explicit typed domain outcomes. Map safe messages instead of raw exception/SQL/provider text. Unknown serialized fields cannot introduce public server metadata or executable content. Covers **NFR1.4–NFR1.5**, with RD-4 enforcing exactness.

## SD-3 — Cookie, Redirect and Existing-Protection Fidelity

Forward required Cookie context and relay separate Set-Cookie values for every actual upstream response, including errors. Never fabricate cookies after a timeout. Protected relay requests use explicit redirect refusal; unexpected redirects become safe failures rather than browser/object-host disclosure. Preserve actual existing CSRF/CSP/header/data/transport controls and safe content rendering; verify changed paths against their baseline before asserting them preserved.

Do not broaden CORS, proxy destinations or read cache scope to make integration tests pass. Authenticated job/result responses remain private/no-store; the independent asset private 60-second policy is preserved by shared relay changes. Actual storage/backup protection and permissions are checked in Infrastructure Design, not claimed from generic standards. Covers **NFR1.3, NFR12.1–NFR12.2**.

## SD-4 — Immutable Browser Attempt Registry

ContentJobApi captures a detached approved input and computes native crypto.subtle SHA-256 over the UTF-8 text `userId:paperId:taskType:JSON.stringify(params)`, with userId from the current authenticated owner context, paperId/taskType from that validated captured attempt, and params equal to its immutable captured input. The key is the lowercase hex digest of the complete prefixed text, not a digest of payload serialization alone. It is sent in the existing body field; a local attempt handle is separate and never a random idempotency fallback.

Reserve preparation revision before asynchronous hashing. After hash completion, a serialized publication section rechecks owner/context/revision **before** any memory or synchronous localStorage publication; no async yield occurs within that publication section. A genuine storage failure publishes memory-only state and warning, while stale completion writes nothing. Returned job metadata follows the same guard.

Store only schemaVersion, attemptId, ownerId, paperId, taskType, key, captured serialized allowlisted paperId/version/targetLang/persona/scope input and optional actual jobId under idempotency:{paperId}:{taskType}. Restore treats it as untrusted, validates namespace/owner/schema/allowlist/digest, and performs no POST. Missing originals cannot be inferred from a hash or current defaults. Editing the visible draft does not mutate the captured attempt; explicit new preparation or owner/context change invalidates old action authority. Recheck availability on activation, not merely when rendering a control.

Account/context invalidation clears active capabilities and prior protected views. Cross-tab changes trigger revalidation/invalidation rather than turning storage into a trusted authentication or transaction service. Backend binding/effect authority remains the final duplicate-work/owner defense. Covers **NFR4.1–NFR4.3**.

Preparation, explicit recovery and restore use this same full prefixed derivation. Restore verifies schema/owner/namespace/task/input first, then reproduces the captured input's original JSON.stringify form and its complete original prefix before comparing the expected key. It never hashes today's edited draft/defaults, trusts a saved owner in place of the current owner, or hashes only serializedRequest. Different owner, paper or public taskType must differ for representative fixtures even where params are identical; hash failure or mismatch makes recovery unavailable. Recheck context/attempt after asynchronous digest work and before publication or POST.

## SD-5 — Accessible Capability Composition

Submission receives explicit command capabilities; result view receives query/dismissal capabilities only and shows submitted-level metadata read-only. Tracking receives validated current observations and separate explicit original-request recovery. Render containment reports to the stable parent, which owns full-page failure presentation and authorized history/cursor checkpoints. Network errors stay inline.

Use native named operable controls, visible focus, accurate unknown-progress semantics and concise live messages. Deduplicate unchanged polling/replay announcements. Result dialog contains keyboard focus and restores a surviving invoking control on close. Successful recovery/read retry moves focus to its resulting heading only when the current target disappears; otherwise preserve the user's current focus. Verify actual light/dark contrast, 200% text resize, 320 CSS-pixel reflow and reduced-motion states through automated plus targeted keyboard/screen-reader evidence. Covers **NFR10.1–NFR10.2**.

## SD-6 — Review and Evidence Responsibilities

Retain the October 14, 2026 review by revenantonthemission and record actual reviewed scope/findings/actions/disposition. If asset implementation is not yet available, retain that review and add code-based follow-up before asset release. Focused tests cover forged identity, cross-owner/expiry/cursor disclosure, incorrect wrappers, stale preparation and command-free result reads. No project compliance certification or passing runtime security review is claimed here. Covers **NFR8.1**; OD patterns own safe telemetry and infrastructure work owns actual permission/transport verification.
