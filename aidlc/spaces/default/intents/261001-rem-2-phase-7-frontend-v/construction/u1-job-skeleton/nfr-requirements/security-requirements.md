# U1 Security and Accessible-Interaction Requirements

## Sources and Scope

Approved inception NFR1/NFR4/NFR8/NFR10/NFR12, FR3/FR4, C1–C4/C6–C8 and the confirmed U1 NFR questions govern these requirements. U1 handles job/result traffic and shared backend authority; U3 owns asset-delivery SEC-9 and presigned-migration acceptance. Current control operation is not certified by this document.

The current confirmed Q3 amendment consumes `../functional-design/functional-spec.md`, `../functional-design/rules.md`, `../../../inception/requirements-analysis/requirements.md`, `../../../inception/contract-design/contract-summary.md` and historical `aidlc/spaces/default/codekb/DocSuri/technology-stack.md`. The corrected payload definition is `shared/dtos/summarization.schema.json#/$defs/Reproducibility`. Current Functional Design review `../functional-design/reviews/review-03.md` verifies optional draft/tracking references and retains current authority/read boundaries; operational prerequisites follow `../../../inception/delivery-planning/bolt-plan.md` and `../../../verification/u1-isolated-postgres-bootstrap-plan.md`.

## Detailed Requirements

| ID | Requirement / pass-fail condition | Verification and source |
|---|---|---|
| NFR1.1 | Every U1 browser submit/state/events/result operation uses the approved same-origin BFF path; trusted principal derives from the existing session/gateway. Client owner fields or forged principal headers cannot grant access. | Destination and forged-identity fixtures, authenticated/unauthenticated integration; NFR1, C1/C3 |
| NFR1.2 | Authentication/ownership checks precede existence, state, cursor and expiry disclosure. Unknown/not-owned jobs have identical generic 404; only the owner of a known expired result receives 410. No protected content accompanies denial/expiry. | Paired unknown/other-owner/expired-owner requests, including state/result/cursor paths; NFR1, FR3.3/FR3.5, C2/C3 |
| NFR1.3 | Cookie forwarding and distinct Set-Cookie relay remain correct on successful and error responses; protected job traffic explicitly refuses unverified redirects and arbitrary proxy destinations. | Real relay fixtures for multiple cookies, errors and redirects; no combined-cookie corruption or credential exposure; NFR1, C8 |
| NFR1.4 | Validate external queue/HTTP/stored payloads and parameterize persistence operations. Malformed IDs/cursors/data cannot select another job, alter query grammar or enter a renderable result as an unavailable/building wrapper. A summary requires the shared C2 reproducibility object with required string code/data and no extra nested fields; values are preserved exactly without flattening, coercion or guessed defaults. | Complete-envelope positive/negative cases for strings, arrays, missing/non-string code/data and extra fields, exact DTO/serialization string preservation and focused injection checks; preserve C1 supported normalization and C2 bare DocModel; NFR1, C1–C3/C6 |
| NFR1.5 | Result handling uses a restricted query capability with zero generation, enqueue, submission or current-settings rendering on every successful/negative/retry read outcome. A reference or key is not authorization. Malformed stored content follows owner/state/known-expiry/unavailable precedence without generative repair. | Positive/401/404/409/410/422/503/504 read-side-effect counters and owner/TTL bypass tests, including malformed/legacy summary content; NFR1, FR3.2/FR3.5, C2/C7 |
| NFR4.1 | Native SHA-256 hashes the exact captured owner:paper:task:JSON.stringify(params) input; original keys remain deterministic and are sent in the existing body field. No random fallback defeats recovery. | Identical/distinct input and hashing-unavailable fixtures; NFR4, BR1.3 |
| NFR4.2 | The saved namespace remains idempotency:{paperId}:{taskType}. Its versioned record contains only approved identity/key/serialized parameter metadata and optional actual job identity. Restore validates owner/schema/allowlist/digest; missing/corrupt originals disable resend. | Inspect persisted bytes, cross-owner/corrupt/quota and restore fixtures; no credentials/document/result text/arbitrary fields; NFR4, Q2 from Functional Design, C4 |
| NFR4.3 | Preparation reserves supersession authority before asynchronous hashing and rechecks it before any memory/storage publication. Action-time owner/context/attempt/in-flight checks prevent obsolete POST and old-job UI overwrite. | Out-of-order A/B preparation, owner switch during hash, edited-draft recovery and supersession-between-lookup-and-action fixtures; NFR4, FR4, C4 |
| NFR8.1 | Retain the 2026-10-14 review with revenantonthemission and its shared trust-boundary evidence. If asset code is not available, retain that review and require completed-implementation follow-up/disposition before asset release. Design-only evidence does not pass implementation review. | Schedule, reviewed scope, findings/actions and accountable disposition in the delivery/release record; NFR8, Delivery Planning Q11 |
| NFR10.1 | Delivered controls have keyboard operation, accessible names, visible focus, accurate determinate/indeterminate progress and meaningful deduplicated announcements. Modal containment/return and conditional recovery focus preserve usable current focus, without background focus theft. | Automated semantic checks plus targeted keyboard/focus/screen-reader scenarios, including user moving focus while recovery/read retry is pending; NFR10, FR6 |
| NFR10.2 | Delivered UI meets applicable WCAG 2.1 AA visual/reflow criteria: normal text 4.5:1, qualifying large text 3:1, meaningful non-text boundaries/focus 3:1 where required, 200% text resize and 320 CSS-pixel reflow. Text/error/success information does not rely on color alone. | Actual rendered light/dark surfaces and affected states, not token-name assertions or DOM-only certification; NFR10, FR6.3 |
| NFR12.1 | Preserve existing authentication/CSRF/CSP, configured data/transport protections and safe content rendering across the integration. No nonce-validation workstream, authentication replacement or unverified certification claim is introduced. | Compare actual configuration/control behavior and negative rendering/CSRF fixtures for changed paths; inspect inherited protections before asserting them; NFR12, C8 |
| NFR12.2 | Authenticated job/result responses use private, no-store handling. Owner/job/context-scoped client state cannot reveal prior-owner or obsolete-job results. U1 shared changes must preserve the separate private 60-second asset cache policy. | Header/cache identity and owner-change tests; the asset cache hit remains distinct from a server recheck; NFR12, C2/C8 |

## Data Classification and Existing Obligations

Prepared content is owner-scoped protected application data even if its source paper is public. Session credentials are secret; client recovery records contain limited identity/parameter metadata, never credentials or generated text. Integrity digests and references are lookup/integrity evidence, not capability tokens. Preserve configured storage/backup/transport protection and restrict access according to actual project controls; do not infer that a configuration is correct from a library name.

No applicable statutory/certification/residency requirement was supplied for this increment. Generic GDPR/HIPAA/PCI/SOC examples do not create requirements or certification here. Existing evidenced project obligations remain binding and must be checked when changing protected data handling.

## Focused Threat and Verification Mapping

| Actual boundary concern | Required evidence |
|---|---|
| Spoofed owner/principal or ID-based cross-owner read | NFR1.1–NFR1.2 deny fixtures |
| Corrupt saved original or stale hash completion | NFR4.2–NFR4.3 record/publication fixtures |
| Coarse legacy reference, flattened/malformed summary reproducibility or translated response wrapper | NFR1.4–NFR1.5 and C2 complete-envelope positive/negative fixtures; no coercion or generation on reads |
| Cookie corruption or protected redirect following | NFR1.3 relay fixtures |
| Rendered-content execution or client-cache leakage | NFR12.1–NFR12.2 negative rendering/context fixtures |

The table is verification scope, not a new security product. Shared telemetry scrubbing requirements are in `observability-requirements.md`. Physical expiry cleanup and late-worker deletion protection are in `reliability-requirements.md`.

## Current Evidence and Qualification Boundaries

The current upstream Functional Design review independently resolves all five carried findings, including R-05's draft optionality. Initial draft and known-job tracking can lack a captured attempt; no fabricated identity record is required to read/track, and unavailable originals cannot authorize resend. This cites the owning review rather than treating the older carry-forward note as current.

Contract Design R-03 remains Accepted risk: the original shape-check environment does not reject malformed date-time fields. Schema-shape/round-trip passes do not establish actual timestamp validation, owner/TTL enforcement or malformed-success application behavior. Require the meaningful boundary/store and read-side-effect tests above and in NFR11.2/NFR11.5. No result existence or expiry may be disclosed before authentication/ownership.

Isolated PostgreSQL acceptance requires admitted artifacts, concrete operational authorization, measured isolation and protected launcher/manifest/receipt/digest/database/role identity before fixture mutation. The full authority and later minimal-purge targets remain distinct. Preserve current-authority/full-script-digest/transaction checks during the narrowly scoped migration repair, and keep wrong/missing proof as failure rather than skipped acceptance. The public bootstrap handoff and existing partial source do not qualify the environment or authorize production access.
