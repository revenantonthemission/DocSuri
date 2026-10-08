# Units of Work — Phase 7 Frontend Wiring

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.
- [Q8–Q10] `units-generation-questions.md`: three capability increments and the approved backend-amended plan and consolidated summary.
- `../domain-design/components.md` and `decisions.md`, including ADR-013–ADR-016 and fifteen components, govern boundaries and entity ownership. Requirements Q15/Q16 authorize bounded backend remediation and preserve failed-dispatch replacement.
- `../requirements-analysis/requirements.md` and `../user-stories/stories.md` govern behavior and acceptance; refined mockups govern existing presentation choices.
- Active-space team/project rules govern the walking skeleton, test-after ordering, coverage, security review and shared deployment.

## Unit Definitions

| Unit ID | Directory | Name | Kind | Deployment | Complexity |
|---|---|---|---|---|---|
| U1 | u1-job-skeleton | Integrated job skeleton | service | Coordinated changes to existing Next.js/BFF, backend API and worker runtimes | XL |
| U2 | u2-job-resilience | Remaining job capabilities and resilience | ui | Browser surfaces in existing Next.js, consuming U1 backend contracts | L |
| U3 | u3-secure-assets | Secure asset viewing | service | Existing Next.js/BFF asset integration with the authorized asset service | M |

Sizes are qualitative planning judgments, not elapsed-time commitments. U1 rises to XL because its narrow summarize journey now includes durable backend result binding, outcome handling and crash/effect reconciliation. U1 and U3 use `service` to retain server-side obligations. Existing backend API and worker runtimes are not embedded in Next.js and are not assumed to deploy atomically. U2 changes frontend behavior against U1's remediated contracts; a new backend requirement must be explicitly allocated and its kind reassessed rather than hidden behind `ui`.

## U1 — Integrated Job Skeleton

**Boundary:** A runnable summarize journey from initial parameter selection and explicit submission through the authenticated BFF, live progress, completion, and an authorized readable result. It must run without U2 or U3.

**Components established:** PaperDetailIsland, JobSubmissionForm, ContentJobApi, IdempotencyService, JobStatus, SummaryModal, ErrorBoundary, ErrorBoundaryFallback, and the job portion of BffProxy. Existing document viewing remains available without the U3 asset migration.

**Backend components remediated:** ContentJobController, ContentJobService and ContentJobWorker, including required changes to existing persistence/queue integration. ContentJobService remains the sole owner of DurableJob, SubmissionBinding, GenerationEffect and PreparedJobResult. Physical storage/transaction details belong to subsequent design; required adapter changes are U1 work, not an unassigned external prerequisite.

**Responsibilities and deliverables:**
- Preserve initial summary-level choice; opening the form or changing parameters does not submit. Use deterministic owner-bound hashing and attempt identity persistence before sending.
- Implement authenticated submit/state/events/result transport, Cookie and separate Set-Cookie relay, real incremental SSE, actual backend states and progress, fixed two-second SWR fallback, and terminal/unmount/context cleanup.
- Deliver completed summarize content through U1's remediated exact job-bound read-only result path. Include owner-checked 401/indistinguishable 404/owner-only 410, controlled legacy/unresolvable references, and zero generation/enqueue on every read outcome. Exact prepared personalization survives later settings changes; never resolve content from a coarse reference or current defaults.
- Own US2.6/US3.4 backend guarantees for both summary and translation fixtures: durable exact content before COMPLETED, real worker outcome mapping, legal transitions and reconciliation before generation, after generation before binding, after binding before publication, and after publication before acknowledgement. Contract Design must establish feasible mechanisms; current effect claims alone are not proof. All corresponding backend regression tests belong to U1. U2 owns translation UI integration, not deferred backend correctness.
- Verify actual backend SSE delimiters as well as BFF incremental framing, event IDs and cursor relay. Escaped newline text must not masquerade as parseable SSE.
- Deliver the ADR-013 in-session uncertain-submit flow: ContentJobApi captures the original request before sending; JobSubmissionForm owns explicit same-key recovery before a job ID exists; PaperDetailIsland receives the actual recovered job before mounting JobStatus. Missing originals disable recovery; recovered terminal states stay terminal.
- Preserve ADR-016: retained-binding replay returns the original job; failed dispatch can release its binding and permit explicit same-key replacement. Verify these paths and executed terminal failure against the backend. Use actual returned identity/state, neutral wording when cause is unknown, and reject old-job responses even within the same owner/paper context. Never restart the old terminal job or rotate keys to force work.
- Include the standalone rendering boundary, stable parent tracking context, full-page rendering fallback, inline network failures, safe return and tracking-only recovery.
- Implement accessibility, owner isolation, controlled async failures, and scrubbed error/lifecycle instrumentation for this slice as it is built. Include initial connection timing and status mount timing so later benchmark verification has real measurement points.
- Author tests after each implemented component; verify new-code coverage and applicable existing checks. U1 is not a test-free prototype.

**Completion boundary:** Demonstrate actual submit → SSE progress → COMPLETED → authorized rendered result against real integrated services, with the protections above. Delivery Planning specifies the demo; Construction separately obtains and runs the human-authorized verification command and requires skeleton checkpoint approval. Mocked unit tests alone do not prove this result. The entire release's story set is not declared complete at this checkpoint.

## U2 — Remaining Job Capabilities and Resilience

**Boundary:** Extend U1's frontend job surfaces with translate and remaining job acceptance cases. Depends on U1, not U3. No new backend controller/service/worker capability is assigned here; consume U1's tested shared summary/translation backend guarantees.

**Components extended:** JobSubmissionForm, ContentJobApi, JobStatus, SummaryModal, PaperDetailIsland and the error-containment surfaces. IdempotencyService's ownership-free digest contract remains unchanged.

**Responsibilities and deliverables:**
- Complete translate parameter selection/submission and readable translation results using the verified contract.
- Complete reload recovery, corrupt/unavailable/quota-limited storage behavior, owner/request reconciliation and unavailable-original recovery feedback. Preserve U1's in-session pre-job owner and immutable request boundary.
- Complete replay ordering/deduplication and recreated-EventSource recovery across the verified BFF cursor contract; exercise channel restoration, obsolete timers/responses and access-loss cleanup across the full job flow.
- Complete expanded frontend result-state coverage for translation and the full interaction matrix, authorized asset-ID copy, safe formatting and conditional focus continuity. U1 already implements owner/expiry/unsupported/read-only guarantees and safe handling in its delivered summarize UI; U2 does not gate secure skeleton reads.
- Complete full job telemetry/connection latency/drop/recovery scenarios and diagnostic-delivery failure handling. Complete applicable job performance and accessibility evidence across all resulting states.
- Extend the relevant tests and run combined U1/U2 regressions. U1-delivered fallback, security, accessibility and tests already exist; they are not postponed to this unit.

**Completion boundary:** All assigned job acceptance criteria pass, including the cross-cutting cases shared with U1. Exact interface types, SWR cache identity and storage reconstruction belong to Functional Design; server compatibility is a prerequisite, not an assumed implementation result.

## U3 — Secure Asset Viewing

**Boundary:** Asset delivery and document-view integration, including the local server proxy. Depends on U1's established authenticated BFF conventions and stable paper/owner composition; does not require U2's translation or result-copy controls.

**Components delivered/extended:** AssetViewer, ZoomPanControls, DocModelViewer; asset routes of BffProxy and the narrowly scoped PaperDetailIsland document integration.

**Responsibilities and deliverables:**
- Use same-origin `/bff/api/papers/{paperId}/assets/{assetId}` image delivery with server authentication/authorization/license recheck, cookie fidelity, safe byte/content handling and `private, max-age=60` caching. A private cache hit is not a new server check.
- Preserve authorized captions/text/table equivalents; absence is a real accessibility gap, not permission to invent OCR or content services. Image error events alone cannot identify HTTP denial status.
- Provide skeleton loading, controlled unavailable/failure states, same-image noninteractive minimap, parent-owned transforms and keyboard/pointer zoom/pan/reset without traps or alternate delivery URLs.
- Clear obsolete owner-context views, measure decoded readiness, and test denied/missing delivery and accessible navigation with real integration evidence as applicable.
- Retain the mandatory mid-implementation Week 2 asset security review, with owner/date assigned by Delivery Planning and disposition evidence before release.

**Completion boundary:** US5.1–US5.3 and asset-specific cross-cutting criteria are verified; joint release evidence includes every applicable unit. SummaryModal's supplied-result asset-ID copy belongs to U2; asset viewing accepts authorized IDs from document context independently.

## Shared Component Change Responsibility

| Component | Initial work | Later scoped work |
|---|---|---|
| PaperDetailIsland | U1 job orchestration and stable context | U2 job scenarios; U3 document/asset composition |
| JobSubmissionForm | U1 summarize and pre-job recovery | U2 translate and reload recovery |
| ContentJobApi | U1 job transport and captured recovery identity | U2 remaining job scenarios |
| IdempotencyService | U1 stateless digest | U2 regression verification of existing contract |
| JobStatus | U1 real progress, fallback and cleanup | U2 full replay/reconnection scenarios |
| SummaryModal | U1 read-only summary result | U2 translation, expanded errors and ID copy |
| ErrorBoundary, ErrorBoundaryFallback | U1 containment and recovery | U2 remaining failure scenarios |
| BffProxy | U1 job streaming/authenticated transport | U3 asset-specific handling; U2 consumes verified job routes |
| ContentJobController | U1 job wire/SSE boundary and owner-safe result responses | U2 consumes; any new backend need requires explicit reassessment |
| ContentJobService | U1 durable result/binding/effect ownership, restricted reads and dispatch exception | U2 consumes shared summary/translation guarantees |
| ContentJobWorker | U1 truthful outcome capture and crash/redelivery coordination | U2 adds translation UI integration, not new worker semantics |
| Backend persistence/queue adapters | U1 changes required by the approved result/effect contracts | No implicit owner transfer to U2/U3 |
| DocModelViewer, AssetViewer, ZoomPanControls | Existing document context preserved by U1 | U3 asset migration and controls |

This table assigns change scope, not duplicate entity ownership. Shared filenames are not independent work areas: preserve serial Construction and coordinate any future shared-file edits explicitly. A U3 proxy change must preserve U1 job-stream regression checks.

## Existing Runtime Boundaries and Rollout Handoff

U1 spans existing frontend/BFF, backend API and queue-worker runtimes. Preserve the existing deployment architecture and configuration; do not create a fourth unit or new microservice implicitly. Contract Design pins cross-version response, queue payload, result-schema and persistence compatibility. Delivery Planning and deployment stages define exposure, rollout sequencing, smoke/integration verification and rollback under the affirmed production-on-merge practice. A coordinated increment does not imply an atomic cross-runtime release. New prepared results must remain safely handled across the agreed mixed-version window; exact compatibility strategy is a downstream decision, not asserted here.

## Constraints and Verification

- Contract Design must pin remediated exact-result delivery, effect reconciliation/outcome mapping, persistence/completion ordering, native/recreated cursors and relevant asset semantics before implementation. Backend remediation is now allocated to U1, not assumed already available. Escalate infeasible guarantees or scope beyond the authorized bound before implementation; never silently weaken the runnable skeleton.
- All units preserve established native fetch/Transport, strict TypeScript, SWR, native EventSource and crypto, CSS Modules/Tailwind and existing CSP. No new nonce-validation workstream is introduced.
- Test-after/test-last per component, ≥80% new-code line coverage, existing-suite health, lint/typecheck and relevant E2E apply to delivered changes. Historical test totals are not fresh passing evidence.
- U1 includes backend regression evidence for exact identity across changed settings, prepared overlays, authorization/TTL across reference and content paths, zero generation/enqueue during reads, outcome accuracy, all declared crash windows and failed-dispatch replacement. Test both supported backend task types even while the first browser demo is summarize.
- NFR9 targets stay fixed: p95 SSE construction-to-open <300 ms, uncached 100 KiB asset request-to-decoded-readiness <500 ms, status mount-request-to-first-commit <200 ms. Use production build, real staging BFF/gateway, same-region authenticated unthrottled desktop Chromium, one active job and 100 sequential samples per metric. Include network/gateway overhead and report failures without hiding them as fast successes.
- U1/U2 own job metrics; U3 owns asset readiness; the release combines evidence. All changed UI must meet applicable WCAG 2.1 AA, 200% text resize and 320 CSS-pixel reflow. No conformity or measured performance is asserted by this plan.

## Rationale and Alternatives

The selected three increments give an integrated checkpoint while keeping secure assets and remaining job behavior bounded. The cost is splitting story acceptance across changes to some of the same components; the story map names the completion unit and contribution boundaries to prevent premature completion claims.

Alternatives considered: two full-feature units reduce shared job edits but inflate the first checkpoint; one unit per component creates non-runnable layers and conflicts with the selected skeleton. Neither independent deployment nor component ownership changes are required. Delivery Planning chooses economic sequencing within the dependency constraints.

## Assumptions & Open Questions

No additional product assumptions. Detailed storage/props and integration contracts remain assigned downstream work, not unresolved unit ownership. Relative sizes remain conditional on verified backend compatibility. No unit implementation, runtime test, or deployment has been completed by these documents.
