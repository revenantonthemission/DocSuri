# Delivery Planning Questions — Phase 7 Frontend Wiring

**Gate:** Human approval after delivery-plan and Inception completeness checks.

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.
- [memory:M1] `aidlc/spaces/default/memory/team.md#Walking Skeleton`: "Stance: ON — Build a thin end-to-end slice first"
- [memory:M2] `aidlc/spaces/default/memory/team.md#Testing Posture`: "Methodology: test-after, Ordering: Test-last per component"
- [memory:M3] `aidlc/spaces/default/memory/team.md#Deployment`: "Continuous deployment to production on merge"
- [memory:M4] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS route all content-job API calls through `/bff/api/content-jobs/*` (SEC-8)"
- [memory:M5] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS generate idempotency keys as SHA-256 hash"
- [memory:M6] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS wrap JobStatus in React Error Boundary"
- [memory:M7] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS use same-origin asset delivery via `/bff/api/papers/{paperId}/assets/{assetId}`"
- [memory:M8] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS integrate Sentry for client-side error tracking"
- [memory:M9] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS conduct security review mid-implementation (Week 2)"

---

## Questions for Delivery Planning

### 1. Sequencing Strategy
**Question:** What should be the primary sequencing strategy for the Bolt sequence?

- A. **Walking Skeleton First** — First Bolt delivers the thinnest end-to-end slice (Submit → SSE Progress → Completion); remaining work in parallel
- B. **Risk-First** — Highest-risk components first (SSE reconnection, AssetViewer migration, idempotency); value delivery second
- C. **Value-First** — Most user-visible features first (JobStatus mount, AssetViewer, retry UX); infrastructure later
- D. **Dependency-Order Only** — Pure topological order of the Unit DAG; no economic sequencing
- X. Other (please specify)

### 2. Bolt Granularity
**Question:** How should the 5 units be bundled into Bolts?

- A. **One Bolt per Unit** — 5 Bolts (ContentJobApi, IdempotencyService, JobStatus+ErrorBoundary, AssetViewer, Integration); strict sequential
- B. **Three Bolts** — Bolt 1: API (ContentJobApi + IdempotencyService); Bolt 2: JobStatus + ErrorBoundary; Bolt 3: AssetViewer + Integration
- C. **Two Bolts** — Bolt 1: API + JobStatus (walking skeleton); Bolt 2: AssetViewer + Integration
- D. **Single Bolt** — All 5 units in one Bolt (monolithic feature delivery)
- X. Other (please specify)

### 3. Walking Skeleton Definition
**Question:** Which units constitute the walking skeleton (first Bolt)?

- A. **ContentJobApi + JobStatus + ErrorBoundary** — Submit → SSE Progress → Completion (minimal end-to-end)
- B. **ContentJobApi + IdempotencyService + JobStatus** — Full submit + progress with idempotency
- C. **Full Skeleton** — All 5 units in one Bolt (per user decision in Units Generation)
- X. Other (please specify)

### 4. Parallelism vs Sequential
**Question:** Can Bolts be developed in parallel?

- A. **Strict Sequential** — Each Bolt completes before next starts; strict topological order
- B. **Parallel Where Possible** — Independent Bolts (AssetViewer, Integration) can run in parallel with API/JobStatus
- C. **Sequential with Overlap** — Next Bolt can start when previous reaches "code complete" (not fully verified)
- X. Other (please specify)

### 5. External Dependencies & Risks
**Question:** Are there external dependencies that could block the Bolt sequence?

- A. **No External Dependencies** — All work is internal to frontend; BFF and gateway already stable
- B. **Security Review (Week 2)** — AssetViewer migration requires security sign-off; blocks Bolt with AssetViewer
- C. **Sentry Integration** — Sentry setup/configuration needed; could delay ErrorBoundary Bolt
- D. **Walking Skeleton Verification** — Construction Verification Command needs to be defined/available
- X. Other (please specify)

### 6. Bolt Sizing
**Question:** How large should each Bolt be?

- A. **Single Unit per Bolt** — Maximum granularity; maximum parallelism
- B. **Walking Skeleton + 1-2 Units** — First Bolt larger (walking skeleton); rest 1-2 units each
- C. **Balanced** — ~2 units per Bolt; ~3 Bolts total
- X. Other (please specify)

### 7. Risk Priority
**Question:** What are the top risks to sequence early?

- A. **SSE Reconnection & Polling Fallback** — Highest technical risk; complex async logic
- B. **AssetViewer Migration** — Security-critical (SEC-8/SEC-9); requires security review
- C. **Idempotency Key Logic** — Deterministic retry logic; subtle bugs possible
- D. **Error Boundary + Sentry Integration** — Cross-cutting; affects all Bolts
- X. Other (please specify)

---

## Confirmation

**Please respond with your choices (A/B/C/D/X) for questions 1-7.**

[Answer]:
1. A
2. C
3. C
4. B
5. A
6. B
7. A

---

## Historical Summary Confirmation

**Summary of your choices:**

1. **Sequencing Strategy**: A — Walking Skeleton First (thin end-to-end slice first, then parallel)
2. **Bolt Granularity**: C — Two Bolts (Bolt 1: API + JobStatus walking skeleton; Bolt 2: AssetViewer + Integration)
3. **Walking Skeleton**: C — Full Skeleton (All 5 units in one Bolt, end-to-end happy path)
4. **Parallelism**: B — Parallel where possible (AssetViewer and Integration can run parallel with API/JobStatus)
5. **External Dependencies**: A — No External Dependencies (all internal, BFF/gateway stable)
6. **Bolt Sizing**: B — Walking Skeleton + 1-2 units (first Bolt larger, rest 1-2 units each)
7. **Risk Priority**: A — SSE Reconnection & Polling Fallback (highest technical risk)

**Confirm** — Does this all look correct before I generate the delivery planning artifacts?

- A. **Looks correct** — Generate the delivery planning artifacts from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

[Answer]: Looks correct

## Current Planning Baseline

The historical answers above refer to obsolete component-based units and assumed no external dependencies. They are not authority to skip the approved three-unit plan, backend remediation, real integrated verification or required security review. The current baseline is the approved requirements, 28 active stories, refined mockups, fifteen-component catalogue, three-unit DAG and eight contracts under `../contract-design/contract-summary.md`.

A **Bolt**, one build pass over a piece of work ending in something that runs, will provisionally contain one approved Unit: U1 job skeleton (service, XL), U2 job resilience (ui, L), U3 secure assets (service, M). The walking skeleton is the smallest integrated demonstration: submit → SSE progress → COMPLETED → exact authorized result, including its delivered protection and recovery behavior. U1 must reach real integrated verification and human checkpoint approval before later units. Record internal U1 milestones for persistence/fencing, backend/worker and frontend integration without inventing additional Units or treating a design document as a working skeleton.

Recorded Construction settings are unit-major and serial with checkpoints enabled; keep them unless the human explicitly changes them. No verification command is currently recorded. The old team-formation files describe roles and obsolete units but that stage is marked skipped, so they do not establish named available staff. Do not invent people, capacity, schedule commitments, a working staging environment or Sentry access.

Current `frontend/package.json` exposes `test`, `test:contracts`, `e2e`, `build`, `check:types`, and `lint` (currently next lint), but no test:coverage or typecheck script. These names alone do not prove checks are runnable or cover the full durable-job journey. Construction must reconcile actual tooling with the affirmed checks. The intent-wide integrated verification command requires its own human authorization; never record a placeholder or treat plan approval as command approval.

### Q8. Sequence After the Skeleton

Which economic sequence should the three Bolts follow? Both dependency orderings are valid; this question chooses value/risk priority, not new scope.

- A. **U1 → U2 → U3** — Prove the integrated backend/frontend slice, complete the job workflow while its contracts are fresh, then deliver secure assets. Preserves the current resolved Unit order and serial execution. Use explicit risk/value reasoning, not invented numeric scores.
- B. **U1 → U3 → U2** — After proving the skeleton, prioritize secure assets and their security-sensitive integration before finishing remaining job UI. If selected, reconcile the actual resolved Unit walk with this order before Construction rather than changing only prose.
- X. Other (please specify)

Recommendation: A for integration continuity, with the required Week 2 security review separately scheduled rather than postponed merely because U3 is later.

[Answer]: A. U1 → U2 → U3

### Q9. Construction Staffing

How do you want to staff Construction? I can run the work from this session using the recorded serial settings, or each of your teams can own a Unit and approve its work independently.

- A. **One session** — AI-led serial implementation, with the existing human checkpoints and targeted specialist checks where required. This does not grant automatic approval or authorize deployment.
- B. **Teams own units** — Identify the actual teams/owners; use unit-first independent ownership and agree their approval rhythm in a follow-up.
- X. Other (please specify)

[Answer]: A. One session

### Q10. Schedule, Security Owner and External Access

What is the planned Construction start date, who is accountable for the mandatory Week 2 AssetViewer security review, and are there fixed deadlines or external-access constraints? We need to turn Week 2 into an actual review date and retain findings/disposition before release. Name an actual person/team for accountability; an AI security reviewer can assist but does not invent an available human owner.

Include known owners/availability for real staging gateway/backend/worker/queue/persistence access and Sentry configuration if they could block the skeleton or diagnostics. If dates or owners are not set, say so; record the unresolved prerequisite honestly and resolve it before claiming a scheduled plan. No secrets or credentials are needed in the answer.

[Answer]: Sequence 1, staffing 1; start 10/5, security reviewer revenantonthemission

Interpret 10/5 as 2026-10-05, the upcoming October 5 in this workflow. Security-review accountability is revenantonthemission. No fixed delivery deadline or external-access availability was supplied; do not infer either. One-session staffing retains the absent/solo ownership default, unit-major serial execution, and existing human checkpoints.

### Q11. Calendar and Verification Arrangements

Confirm the following proposed arrangements, or specify corrections:

- Construction starts Monday **2026-10-05**. Calendar Week 2 is **2026-10-12 through 2026-10-18**; schedule the mid-implementation security review for **Wednesday 2026-10-14**, accountable reviewer **revenantonthemission**, with AI security assistance if useful. Review the actual code/design available then, especially SEC-8/SEC-9 and shared result/asset trust boundaries. If AssetViewer implementation is not yet available because U1 runs longer, retain the Week 2 review and require a follow-up on the completed asset implementation before its release; a design-only review is not completion evidence.
- Treat U1/U2/U3 sizes as relative complexity, not dates. The October 5 start and October 14 review do not create an invented feature-completion deadline or allow bypassing U1's verified skeleton checkpoint.
- **Explicitly defer the intent-wide verification-command selection.** The inspected `frontend/playwright.config.ts` explicitly drives the mock-first application and its e2e directory contains hero/agent-chat tests; `playwright.rem1.config.ts` does not establish a real durable-job journey either. No verified existing command demonstrates the new backend/worker/result skeleton. U1 must provide the real integrated check against authenticated BFF/gateway/worker/persistence, and the human must separately authorize its exact runnable invocation before the first checkpoint executes it. Leave the recorded command unset; this is not approval of a placeholder or of a mock-only substitute.
- Propose **revenantonthemission** as the accountable human contact for confirming real staging/gateway/worker/queue/persistence and Sentry readiness/access, with AI implementation and verification support. This assigns follow-up accountability only; access and availability remain unverified. Record a dependency readiness check at kickoff and before the U1 integrated run, with missing access blocking that verification rather than being called ready. If another owner is responsible, name them now.

- A. **Confirm arrangements** — Confirm the date interpretation, October 14 review and accountable contact, and explicitly defer command selection as described.
- B. **Request changes** — Provide different dates, ownership, constraints, or an existing real integrated check to inspect.
- X. Other (please specify)

[Answer]: A. Confirm arrangements

## Historical Delivery Plan Confirmation

- **Sequence and rationale:** Three Bolts, each a build pass over one approved Unit ending in a runnable increment: U1 job skeleton, then U2 job resilience, then U3 secure assets. Use skeleton-first risk reduction, then job-workflow continuity; no invented scoring or duration estimates. The sequence matches the actual Unit DAG and its current resolved order.
- **Staffing:** One-session AI-led implementation with unit-major serial execution and human checkpoints. revenantonthemission is the accountable human contact for readiness coordination and the named security reviewer. Historical team-role placeholders are not named available staff. Use targeted architecture, QA and security assistance according to applicable stages, without implying automatic approval or deployment authority.
- **Calendar:** Construction starts 2026-10-05. Week 2 spans October 12–18; the security review is scheduled for 2026-10-14 with revenantonthemission. If asset implementation is unavailable then, retain that review and add implementation follow-up before asset release. No delivery-completion date is promised.
- **Bolt 1 / U1:** Deliver the full summarize → authenticated BFF/gateway → durable dispatch/worker → SSE progress → COMPLETED → exact authorized result demonstration. Own both tasks' shared backend outcome/result/fencing guarantees, actual dispatch and cursor/framing repairs, in-session pre-job recovery and the preserved dispatch-failure replacement exception. Include protection, accessibility and tests for every delivered behavior. Confidence hypothesis: the real multi-runtime path returns the correct immutable result without generation on reads or duplicate execution during the specified recovery cases. Physical persistence/fencing details and lease tuning must be settled in the applicable design stages before implementation.
- **Bolt 2 / U2:** Complete translation UI, reload/replay/recovery/error/copy states, diagnostics and job accessibility/performance evidence against U1's backend. Confidence hypothesis: users can recover and read the correct job outcome across interrupted connections and reloads without cross-owner or stale-job updates. Do not hide new backend capabilities in this ui unit.
- **Bolt 3 / U3:** Deliver secure same-origin asset integration, authorized document semantics, zoom/pan/reset, minimap, and asset accessibility/performance evidence. Confidence hypothesis: authorized assets remain operable while denied/expired-context requests cannot bypass protections through redirects or alternative URLs. Retain the Week 2 review and final implementation disposition requirement.
- **Definition of done:** Each increment meets its assigned acceptance slice, test-after ordering, ≥80% new-code line coverage, applicable existing-suite/lint/typecheck/E2E checks and truthful evidence limits. Whole stories spanning units close only after all contributions; all 28 active stories remain required and US4.3 excluded. The skeleton checkpoint is a real integrated result, not a design review or mock-only test.
- **Verification command:** Explicitly deferred by the human. U1 supplies the real integrated check; its exact invocation needs separate authorization before the first checkpoint. Keep the field unset, never use an invented command or treat this summary as execution authority. Reconcile current package scripts with required checks rather than assuming historical script names exist.
- **Dependencies:** revenantonthemission confirms readiness/access for real staging, gateway/session authentication, API/worker/queue/persistence, Sentry and required asset data/license/equivalents. Readiness checks occur at kickoff and before dependent verification; availability/lead times remain unverified. Missing prerequisites block the relevant integrated evidence, with explicit escalation/rescheduling rather than fabricated readiness or relaxed tests.
- **Rollout coordination:** Existing Next.js, backend API and worker runtimes are not atomic. Plan compatibility-first persistence/readers/workers before v1 emission/UI exposure, preserve safe legacy-message handling and exact-result readability, and block incompatible old-worker consumption. Delivery planning records constraints and accountable handoffs; concrete environment-specific commands and rollback verification belong to deployment stages. Production-on-merge requires compatible gated exposure, not silent early release of incomplete stories.
- **Outputs and phase audit:** Generate bolt-plan.md, team-allocation.md, risk-and-sequencing-rationale.md and external-dependency-map.md, retaining this questions record. Revalidate all three Inception traceability maps and consolidate the completeness result in verification/phase-check-inception.md. Distinguish accepted upstream requirement wording risks from unresolved coverage gaps and never claim runtime readiness from document checks.

Does this all look correct before I generate the delivery plan and Inception completeness report?

- Looks correct
- Request changes

[Answer]: Looks correct

## Revalidation After the Approved C2 Correction

The human approved the reopened Contract Design after its narrow summary reproducibility correction. `../contract-design/contract-summary.md` now references the existing required `{code: string, data: string}` object and includes complete summary-envelope fixtures. The bare DocModel translation reference and original-request recovery capabilities remain specified. The current Contract Design review's R-03 timestamp-checker gap is **Accepted risk**, as hydrated from the approval ledger; its payload-shape passes are not timestamp, runtime TTL or operational proof. Delivery Planning must carry that disposition accurately rather than calling it resolved or silently changing the approved contract.

All nine declared Inception inputs and the existing delivery artifacts have been read. The prior Q8–Q11 choices still govern: U1 → U2 → U3, one-session unit-major serial Construction, the October 5 planned start, October 14 security review with revenantonthemission, no invented completion deadline, and separately deferred integrated-command selection. Historical team-formation placeholders and package-script observations do not establish current staffing or runner readiness.

The following additional evidence informs the revalidation:

- `../../construction/u1-job-skeleton/code-generation/code-summary.md` preserves the actual partial U1 implementation and failing schema handoff. Its former B-03 string/object contradiction is now corrected at the contract boundary, but application capture/validation conformance still needs current verification. Migration admission, the real PostgreSQL realm, stricter imported TypeScript and supply-chain/runtime qualification remain prerequisites; local model/frontend checks do not demonstrate the skeleton.
- `../../construction/u1-job-skeleton/code-generation/recovery-impact.md` assigns safe migration-admission/source-footprint reconciliation and current implementation authority to the resumed U1 work. It remains a historical recovery proposal, not permission to bypass guards or execute raw rejected SQL.
- `../../verification/u1-isolated-postgres-bootstrap-plan.md` supplies the confirmed 12-step planning handoff, separate disposable authority/purge database identities, protected launcher/manifest/receipt bindings, measured isolation and scoped rollback. The locally present PostgreSQL candidate remains pending qualification with an unresolved High finding; resource/rule application still needs concrete operational authorization.
- `../../aidlc-state.md` retains checkpoints enabled, unit-major serial execution, active U1 in-progress and no authorized integrated verification command. No later Unit or deployed result is inferred from revalidation.
- The three Inception traceability maps have been read. Their existing requirement/story/component/Unit allocation and explicit NFR8/NFR11 process-evidence deferrals remain inputs to a fresh completeness check; the old `../../verification/phase-check-inception.md` does not certify this new attempt.

### Existing Artifacts

| File in this directory | Current purpose |
|---|---|
| `bolt-plan.md` | Three-Unit sequence, runnable slice, definitions of done, demos and compatibility handoff |
| `team-allocation.md` | One-session responsibility, accountable contact and October 14 review |
| `risk-and-sequencing-rationale.md` | Economic ordering, risk register and escalation |
| `external-dependency-map.md` | Readiness dependencies, accountable owners and blocked verification/exposure |
| `delivery-planning-questions.md` | Original answers, historical confirmation and this revalidation decision |

### Proposed Bounded Updates

- Carry the authoritative C2 object shape and its actual evidence limits into U1 result acceptance and consumer compatibility. Preserve preparedResult v1, exact content, ownership/expiry, zero-generation reads, both-task backend responsibility and existing Unit boundaries.
- Add the current U1 recovery milestones: revalidate the affected designs, reconcile migration admission and source footprint/current implementation authority, qualify and obtain operational authorization for the isolated PostgreSQL realm, then rerun required schema checks before later backend/browser layers. Preserve partial source and the original immutable baseline.
- Update dependencies/accountability for the PostgreSQL bootstrap handoff, actual image/isolation/receipt prerequisites, stricter typing and supply-chain gaps. Carry the accepted Contract Design R-03 timestamp-validation limitation into evidence expectations without rewriting its upstream disposition.
- Retain the already selected order, staffing, dates, security implementation follow-up, quality floors, feature-exposure constraints and separately deferred integrated command. Refresh the three-map Inception completeness report against the current contract and delivery documents; distinguish document completeness from actual runtime readiness.

### Q12. Existing Delivery Artifacts

How should we handle the existing delivery plan while reconciling the approved C2 correction and current U1 prerequisites?

- A. **Modify (Recommended)** — Use the existing five artifacts as the starting point and make the bounded updates above. Keep prior decisions and obtain consolidated-summary confirmation before generating the revised delivery artifacts and completeness report.
- B. **Keep** — Retain the existing artifacts as-is and proceed through their revalidation/approval checks. Current contract obligations and implementation/environment blockers still apply; retaining the text does not establish readiness.
- C. **Redo from scratch** — Regenerate the delivery artifacts from the current approved inputs and recorded human decisions, preserving the old work in the archive.
- X. Other (please specify)

[Answer]: A. Modify (Recommended)

The human replied exactly `Modify`. This selects the bounded update of the existing delivery artifacts; it does not authorize resource/rule application, application-code generation or the integrated verification command.

## Consolidated Summary Confirmation

- **Starting point and outputs:** Modify the existing delivery artifacts using the approved current inputs and Q12. Preserve the prior versions in the archive, revise `bolt-plan.md`, `team-allocation.md`, `risk-and-sequencing-rationale.md` and `external-dependency-map.md`, and retain this questions record. Refresh `../../verification/phase-check-inception.md` after checking all three Inception traceability maps; unresolved coverage gaps stop the phase handoff.
- **Sequence and staffing:** Retain three Bolts, each one build pass ending in a runnable increment: U1 job skeleton → U2 job resilience → U3 secure assets. U2 and U3 depend on U1; ordering U2 before U3 is the recorded economic choice, not a new capability dependency. Keep one-session unit-major serial work, checkpoints enabled and the separately verified human U1 skeleton checkpoint before later Units.
- **Calendar and accountability:** Retain the original planned Construction start of 2026-10-05, without describing a new start or promising a completion date. Keep the 2026-10-14 security review with revenantonthemission, with a completed-asset implementation follow-up and disposition before release if only design/partial code is available then. revenantonthemission remains the dependency-readiness and operational-authorization contact.
- **U1 result acceptance:** Carry the approved C2 shared `{code: string, data: string}` shape into both-task backend result capture/validation and consumer compatibility checks, retaining preparedResult v1, exact owner-specific content, fixed expiry, owner-first errors, zero-generation reads and original-request recovery. The real summarize submission → authenticated BFF/gateway → durable worker → SSE → COMPLETED → exact authorized result journey remains the completion boundary; preserved partial source and local passing checks do not satisfy it.
- **U1 recovery order:** Revalidate the affected designs through the returned workflow, reconcile the narrow migration-admission/source-footprint extension and current implementation-plan authority, then run the required schema lane only after its registered SQL and isolated realm are admitted. Preserve the existing partial implementation, original dirty-source baseline, current-authority/digest/transaction protections and test-after ordering. No raw rejected-SQL bypass, synthetic realm proof, required-test skip or transfer of unfinished backend guarantees to U2 is implied.
- **Environment and verification dependencies:** Link `../../verification/u1-isolated-postgres-bootstrap-plan.md` and its separate authority/purge databases, bounded roles, protected launcher/manifest/receipt bindings, measured isolation and scoped reversal. Its PostgreSQL image/runtime qualification and concrete resource/rule authorization remain pending. Track stricter imported TypeScript, dependency/image/control/notification qualification and actual staging/auth/queue/storage/provider/Sentry readiness as evidence prerequisites, not assumed capabilities. Keep the intent-wide integrated command explicitly deferred until U1 supplies a real runnable invocation for separate human authorization.
- **Evidence limitations and upstream dispositions:** Carry Contract Design R-03 as the human's accepted timestamp-validation risk: current schema checks establish payload shape, not malformed-timestamp rejection or runtime TTL correctness. Requirements R-01/R-02 and the historical U1 Functional/NFR/Infrastructure findings keep their recorded statuses; downstream planning does not silently resolve them. Application and runtime expiry validation still need meaningful evidence under the approved acceptance criteria.
- **U2/U3 and release:** Preserve U2's translation UI/reload/replay/result/copy/diagnostic work and U3's secure same-origin assets/viewer/accessibility/performance work. Keep all 28 active stories, US4.3 excluded, applicable accessibility/performance targets, at least 80% new-code line coverage, current suites/lint/types/E2E and actual security dispositions. Preserve compatibility-first persistence/readers/workers before new messages/UI exposure and readable prepared results on rollback across the existing separate runtimes. Production-on-merge remains conditional on the exact release's required CI/staging/compatibility evidence; this planning approval does not grant merge or operational execution.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
