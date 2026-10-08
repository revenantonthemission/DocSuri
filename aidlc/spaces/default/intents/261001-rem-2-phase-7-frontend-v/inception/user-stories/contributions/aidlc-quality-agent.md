**Collaborator:** aidlc-quality-agent

## Contribution

### Independent round-1 assessment and limits

Reviewed the current `stories.md`, `personas.md`, `user-stories-questions.md`, and `../requirements-analysis/requirements.md` against the User Stories stage and ensemble protocol. This contribution supersedes my historical contribution, including its unsupported approval, invented contracts, and test-pass symbols. No other contributor was read. The draft contains 26 active stories and excluded US4.3; it is substantially testable, with the targeted coverage gaps below.

This is specification review, not implementation verification. No tests, sensors, staging benchmark, backend-contract inspection, or automated identifier validation were run. Existing assessment/traceability artifacts were deliberately not evaluated: the lead will rebuild them after integration. Shared and quality-agent methodology knowledge was loaded; the two corresponding active-space knowledge directories are absent. Rules/persona were supplied in context.

### Expert issues to integrate

**QA-01 — FR1.1's negative scope is not an executable acceptance criterion.** US1.1/US1.2 cover summarize and translate, but omit the explicit prohibition on executable novelty, evidence, and ingest_userdoc actions. A test suite could satisfy these stories while exposing forbidden actions. Append **AC1.1.6**: “Given the paper-detail workflow, when available job actions are inspected and exercised, then summarize and translate are the only executable task actions in this release; novelty, evidence, and ingest_userdoc cannot initiate jobs.” This does not prescribe whether non-executable informational UI is hidden or disabled.

**QA-02 — FR4.3 needs a general negative criterion, not only an error-path restriction.** US4.3 says the prohibition is verified under US4.2, but AC4.2.5 puts no parameter changes/key rotation inside a network-or-authorization-failure fixture. Append **AC4.2.6**: “Given the inline recovery workflow, when its controls and outgoing requests are inspected across successful and failed recovery, then no Retry with changes action is offered, original parameters remain unchanged, and keys are not rotated to force new execution.” Keep US4.3 excluded and do not allocate new ACs beneath it.

**QA-03 — Full WCAG coverage and error announcements need explicit test obligations.** FR6.3/NFR10 apply WCAG 2.1 AA to all changed UI, not only US6.3's visual subset; FR6.2 includes error changes beyond terminal FAILED. Existing keyboard/progress/contrast criteria are useful but do not alone establish that full obligation. Append **AC6.3.5**: “Given all changed UI in its loading, success, failure, and recovery states, when applicable WCAG 2.1 AA checks are performed, then automated checks and targeted keyboard, focus, and screen-reader checks demonstrate conformance; results identify tested states and applicable criteria.” Append **AC6.1.6** for meaningful submission, connection-loss, polling-failure, result-read, asset-load, and recovery errors to be announced accessibly without fabricating a job-state change. Use representative fixtures for each relevant flow; do not require a new announcement framework. DOM live-region assertions alone are not evidence of actual screen-reader behavior.

These are expert coverage corrections grounded in existing requirements, not requests to expand scope. If disputed, use the revised draft in round 2. No new human product decision is needed to preserve these already approved obligations.

### Requirement coverage accounting for lead integration

The following is a manual map, not a replacement for the rebuilt element-level JSON. Group rows inherit their listed children; every FR group and child must still have its own JSON entry.

| Approved requirements | Draft story coverage / disposition |
|---|---|
| FR1; FR1.1, FR1.2, FR1.3, FR1.4 | US1.1–US1.5; FR1.1 partial until QA-01 is integrated |
| FR2; FR2.1, FR2.2, FR2.3, FR2.4 | US2.1–US2.5; replay contract remains an explicit technical prerequisite |
| FR3; FR3.1, FR3.2, FR3.3, FR3.4 | US3.1–US3.3; authorized read, missing/expired results, exact copy and clipboard failures covered |
| FR4; FR4.1, FR4.2, FR4.3 | US4.1–US4.2; FR4.3 needs QA-02, not an OK mapping solely to excluded US4.3 |
| FR5; FR5.1, FR5.2, FR5.3, FR5.4, FR5.5 | US5.1–US5.3; includes cookie relay, license checks, private cache, controlled errors, keyboard/pointer transforms |
| FR6; FR6.1, FR6.2, FR6.3 | US6.1–US6.3 and control-specific stories; QA-03 completes explicit breadth |
| FR7; FR7.1, FR7.2, FR7.3 | US7.1–US7.3, US2.1/US2.4, US8.1; render and asynchronous failures distinguished |
| NFR1, NFR2, NFR3 | US1.5, US5.2, US5.1 respectively |
| NFR4, NFR5, NFR6 | US1.3/US1.4/US4.2; US2.1–US2.5; US7.1–US7.3 respectively |
| NFR7 | US8.1 and AC7.2.3; Sentry remains mandatory |
| NFR8 | Deferred evidence to Delivery Planning for named reviewer/schedule; actual review and findings disposition required before release |
| NFR9 | US8.2, with the staging acceptance profile retained |
| NFR10 | US6.1–US6.3 plus cross-cutting controls; QA-03 applies |
| NFR11 | Deferred verification evidence to Build and Test; tests authored in Code Generation, not deferred past merge |
| NFR12 | AC1.5.4, AC5.1.4 and AC5.2.5 |

### Downstream test design and staging realism

- Use unit/component tests for hashes, storage reconciliation, display states, duplicate events, copy outcomes and boundary behavior; integration tests for BFF cookies/identity, state/event races, and same-key recovery. Use real hashing with known input/output vectors, not a mocked digest as proof of SHA-256 correctness. Isolate storage, SWR caches, clocks and event sources between tests.
- Exercise all three terminal states; SSE-to-polling and polling-to-SSE transitions; older in-flight poll responses after a newer event; job switch/unmount while requests remain pending; malformed events; owner/account changes; corrupt/quota-denied storage; denied result reads after earlier authorized access; and license-denied asset delivery. Confirm no new submit during read or tracking recovery. These elaborate existing ACs rather than add new product features.
- Mocked EventSource tests cannot verify browser reconnect headers or actual replay support. Contract Design must pin event identity/order, recreated-connection cursor behavior, and fallback/recovery triggers before these integration tests can be finalized. Do not invent retry counts, query parameters, state ordering by enum rank, or configurable EventSource headers.
- Keep a thin real-browser/full-stack walking-skeleton test for submit → SSE → COMPLETED → result, then targeted fallback and secure-asset journeys. API interception can prove UI responses but not gateway authorization or real BFF behavior. Persona archetypes are not authorization roles.
- US8.2 correctly preserves the binding staging benchmark rather than substituting a mocked/local timing test or a load test. Collect **100 sequential measurements per metric** under the approved profile; pin build/browser/runner versions, cache conditions, timing instrumentation and percentile algorithm before execution. Keep each connection trial isolated and close its stream; record failures/timeouts separately without dropping/replacing them silently. An uncached browser fixture must be demonstrated, not assumed from a changed filename. Keep private production cache policy intact.
- For JobStatus mounting, measure the first committed status UI, not backend execution completion. For assets, measure decoded readiness, not just HTTP headers. Record raw samples and target-versus-actual results for all three strict p95 limits. These single-job measurements establish neither concurrency capacity nor availability/auto-scaling; no new load target is implied. Technical measurement details belong in the verification plan; any threshold/profile relaxation is a human scope/risk judgment, never an expert workaround.
- Preserve test-after per component and ≥80% **line** coverage for new code. Do not invent additional branch/function percentage gates, equate file coverage with changed-code coverage, or treat historical suite counts as current evidence. Existing suites, lint, typecheck and relevant E2E must pass before merge. NFR8 review evidence and NFR7/NFR9 acceptance are not optional/advisory implementation checks.

### Identifier and provenance checks

Manual inspection found story IDs and three-segment AC IDs internally consistent, with no visible duplicate active identifiers. Preserve existing IDs and append the proposed ACs; do not renumber to fill US4.3's gap. Historical ID semantics were not independently diffed. Rebuild traceability after integration and validate uniqueness, targets, all FR parent/child rows and NFR1–NFR12. Do not mark accepted upstream R-01/R-02 fixed: the draft's skeleton path and connection-latency elaboration are downstream specifications, not upstream repairs or executed verification.

### Round-1 positions (historical; superseded by round-2 positions below)

- AGREE: The 26 active stories and excluded US4.3 preserve confirmed scope and broadly testable Given/When/Then outcomes; no blanket approval or execution claim is warranted.
- AGREE: Same-key recovery must retain actual terminal outcomes, native EventSource must follow a verified resume contract, and private-cache hits must not be described as fresh server authorization checks.
- AGREE: The strict staging 300/500/200 ms p95 limits, mandatory Sentry, ≥80% new-code line coverage, and named downstream process evidence remain binding.
- AGREE: Preserve stable IDs and accepted upstream R-01/R-02 provenance; rebuild assessment/traceability only after integration.
- OBJECT: QA-01 — Expert coverage issue: FR1.1's prohibited executable task actions lack a negative acceptance criterion.
- OBJECT: QA-02 — Expert coverage issue: FR4.3's no-changed-parameter recovery prohibition needs a criterion covering successful as well as failed recovery.
- OBJECT: QA-03 — Expert testability issue: all-changed-UI WCAG conformance and nonterminal error announcements need explicit acceptance obligations beyond the current visual/status subset.

### Round-2 verification of the integrated draft

Read the revised `stories.md` and `personas.md`, rebuilt `user-stories-assessment.md` and `traceability.json`, and the design/developer round-1 contributions now permitted by the dispatch. Compared them against the approved requirements and confirmed questions loaded in round 1. The preceding round-1 findings and map remain as provenance, not current unresolved objections.

| Finding | Current evidence | Round-2 disposition |
|---|---|---|
| QA-01 | AC1.1.6 limits executable tasks in this integration to summarize/translate while preserving unrelated workflows and the backend task union. FR1.1 maps to US1.1/US1.2. | Resolved in the story specification. |
| QA-02 | AC4.2.6 explicitly covers successful and failed recovery without changed parameters, key rotation, or Retry with changes. FR4.3 maps to active US4.2, not excluded US4.3. | Resolved in the story specification. |
| QA-03 | AC6.1.6 covers meaningful nonterminal feedback, AC6.1.7 suppresses unchanged polling/replay announcements, and AC6.3.5–7 require full changed-UI checks plus resize/reflow evidence. FR6.2/FR6.3/NFR10 map to the relevant accessibility stories. | Resolved in the story specification. |

**Coverage mapping:** Manual comparison finds all 45 approved requirement identifiers represented: 7 parent FRs, 26 FR children, and NFR1–NFR12. Each appears once in `upstream_ids` and once in `coverage`; no missing or extraneous identifier was observed. The 43 `OK` rows point to existing active story IDs with corresponding acceptance obligations; the two `Deferred` rows are NFR8 and NFR11 with named accountable downstream stages and mandatory evidence conditions. All 26 active stories appear among coverage targets. US4.3 is not used as an active coverage target. No coverage defect was identified in the current map. Here `OK` means specification coverage, not fulfilled requirements or verified implementation.

**IDs and dependencies:** Manual inspection found no duplicate story/AC definitions or malformed three-segment AC IDs. Existing story identifiers, including excluded US4.3, remain intact. The listed dependency layering agrees with the declared story edges and is acyclic on manual inspection; it is appropriately not represented as an execution schedule or Unit DAG. No deterministic parser, graph checker, or historical identifier diff was run.

**Other contributors' positions:** The integrated AC6.2.5 adds observable focus continuity and freedom to leave the viewer; AC6.3.6–7 operationalize the design resize/reflow concerns without adding a new mobile product. AC1.5.6 and the skeleton handoff explicitly require BFF streaming/cursor preservation. AC2.4.4/AC2.5.5 correctly distinguish transient connectivity from known access loss/account change. The resultRef prerequisite makes US3.1/US3.3 sizing conditional and prohibits guessing a reference's meaning. These refinements address the specification concerns I can assess; they do not certify the developer's source observations or close actual contract investigations on that contributor's behalf.

**Remaining technical work, not current dissent:** Contract Design still must establish reference-to-content delivery/expiry, native/recreated SSE resume behavior, and actual authenticated request/response shapes. Detailed design must establish safe unchanged-request reconstruction after reload; the assessment correctly warns that a hash alone cannot reconstruct parameters. Refined Mockups and Contract Design must establish accessible asset equivalents and exact focus destinations. Their absence from runtime evidence is explicitly disclosed rather than hidden by story coverage. Tests must eventually use real-browser/BFF/gateway evidence for those seams, alongside isolated fixture-based cases.

**Performance and quality gates:** US8.2 and the assessment retain the actual staging profile and all three strict p95 limits, not a mocked performance substitute. The inherited profile requires 100 sequential measurements per metric. The round-1 guidance on raw samples, failures/timeouts, uncached decoded-image readiness, percentile choice and stream cleanup still applies to the downstream verification plan. No concurrency, availability or auto-scaling claim follows from this single-job benchmark. NFR8 review evidence, NFR11 current-suite/coverage evidence and Sentry remain mandatory. R-01/R-02 remain accepted upstream risks; only my three local specification findings are marked resolved.

**Human judgment:** No immediate human judgment question or maintained QA dissent. If technical investigation proves the approved result/replay/accessibility outcome impossible within existing scope, the lead must surface that demonstrated scope/risk decision before implementation; do not silently downgrade acceptance or invent a new service. Existing priorities, retry semantics and latency limits need not be re-asked.

**Exact verification limits:** This round performed manual document/JSON-text comparison only. No JSON parser, automated ID/traceability sensor, dependency checker, test suite, lint/typecheck, coverage measurement, browser/screen-reader exercise, network or security test, staging benchmark, backend/source inspection, or lifecycle command was executed. Developer source claims were read as attributed evidence, not independently reproduced. No upstream artifacts, lead artifacts, state, audit, implementation, or sibling contribution were changed. Only this contribution was updated. No release readiness, implemented compatibility, measured latency, or walking-skeleton verification is asserted.

### Historical positions — superseded by the current amended-baseline assessment below

- AGREE: QA-01 is resolved by AC1.1.6 and the FR1.1 mapping — the scoped prohibited-task boundary now has explicit acceptance coverage.
- AGREE: QA-02 is resolved by AC4.2.6 and FR4.3 → US4.2 — successful and failed recovery share the unchanged-parameter/no-forced-execution restriction while US4.3 stays excluded.
- AGREE: QA-03 is resolved by AC6.1.6–7 and AC6.3.5–7 — nonterminal feedback and full changed-UI accessibility now have explicit verification obligations.
- AGREE: The rebuilt map covers all 45 approved FR/NFR identifiers on manual inspection, with valid active-story targets and mandatory named process-evidence deferrals; no current coverage defect was identified.
- AGREE: Focus continuity, owner-change cleanup, BFF streaming and resultRef handoffs improve testability without pretending unresolved technical compatibility has been proven.
- AGREE: Stable story/AC identities, strict staging limits, mandatory quality gates and accepted upstream R-01/R-02 provenance are retained; no current QA dissent or immediate human judgment question remains.

### Current amended-baseline assessment — independent round 1

This section supersedes the historical 26-story/45-requirement assessment and its positions above. Reviewed the current stories, personas, questions, assessment, traceability JSON and approved requirements supplied in this dispatch. The current baseline is **28 active Must Have stories, excluded US4.3, and 47 requirement IDs**. Read my existing file before updating it; did not open any other collaborator's file or use its historical positions as current evidence. Active rules and persona were natively supplied; shared/quality methodology and the stage/protocol modules were loaded. The active-space knowledge directory is empty.

**Conclusion:** No fixable requirement-coverage or acceptance-testability defect identified in this amended draft. The new backend obligations are expressed as observable outcomes without pretending exact DTOs, persistence design, or runtime compatibility are already settled. No immediate human-judgment question is required. This is a document review, not a reviewer verdict or release approval.

### Coverage and acceptance findings

Manual comparison of the requirement definitions and JSON text finds all 7 parent FRs, 28 FR children and NFR1–NFR12 represented, each with a coverage row. The 45 OK rows name existing active story targets; NFR8 and NFR11 are the two named process-evidence deferrals. All 28 active stories appear among the targets. US4.3 is correctly excluded from active coverage, while FR4.3 is verified through US4.2. This is semantic/manual inspection, not an automated sensor result; OK denotes specification coverage only.

| Risk/requirement | Current acceptance evidence | QA assessment |
|---|---|---|
| FR2.5 truthful outcomes | AC2.6.1–5: durable binding before completion, actual abstention/unavailable outcomes, failed persistence, crash/redelivery, consistency of reads | Sufficient story-level coverage; exact existing-outcome/legal-transition mapping correctly assigned to Contract Design. |
| FR3.5 exact result | AC3.4.1 and AC3.4.6: changed settings and colliding coarse references cannot substitute content | Testable with immutable prepared-content fixtures, not merely equal reference strings. |
| FR3.2/FR3.5 read-only behavior | AC3.1.5, AC3.3.4, AC3.4.2–3: successful and failed reads, repeat/retry, unsupported references | Explicit zero generation AND zero enqueue is stronger than only observing absence of a browser submit. |
| FR3.3 owner/expiry privacy | AC3.1.6, AC3.4.4–5 | Correctly requires current unknown/not-owned 404 behavior and newly required owner-verified expiry 410; another owner's expired result remains indistinguishable 404. No current implementation claim. |
| FR4 recovery identity | AC4.2.3–4, AC4.2.8–9 and AC1.1.4 | Retained replay, failed-dispatch replacement and executed terminal failure are separate fixtures; lost response does not establish dispatch cause. |
| FR1.4/FR4 unavailable original | AC1.4.2–4 and AC4.2.7–8 | Stored key alone is not recovery authority or request reconstruction; unavailable/corrupt original parameters disable resend accessibly. |
| Cross-cutting security/accessibility | AC1.5.6, AC2.5.5, US5/US6/US7 | Streaming, owner-change cleanup, private-cache distinction, asynchronous errors and accessible feedback remain explicit obligations. |

The earlier local QA-01/02/03 specification fixes remain present in AC1.1.6, AC4.2.6 and AC6.1.6–7/AC6.3.5–7. They are not reopened. No visible duplicate story/AC definitions or dependency cycle was found manually; no automated identifier/graph check or historical-ID diff was performed.

### Downstream fixture and oracle recommendations

These operationalize existing acceptance criteria; they are not requests for new product scope or tests to write during User Stories.

1. **Exact prepared-result identity (US2.6/US3.4).** Seed distinguishable summary and translation payloads for jobs sharing a paper/version but differing in applicable persona, glossary, model, prompt or source identity. Change current settings after completion. Assert the returned prepared content and its job binding, not just a coarse resultRef. Include missing content despite a stored reference, legacy/incomplete/unsupported references and repeated reads. Do not use a generation endpoint to prepare a result as part of the read under test.
2. **Zero work on every read (AC3.4.2).** Observe backend generation and enqueue boundaries in addition to browser submit requests. Snapshot counters after fixture setup and assert zero deltas for successful, unauthenticated, not-owned, unknown, expired, missing and unsupported-reference reads, repeated reads and explicit transient read retry. Result-view mount, reopen and tracking recovery must also remain read-only. A mocked frontend fetch cannot establish this server-side property.
3. **Ownership and TTL matrix (AC3.4.4–5).** Use owners A/B, an unknown job, A's available job and A's known expired job. Anonymous reads return 401; B receives the same public 404 response for unknown, A's available and A's expired job; A receives 410 for its known expired result with no protected content. Compare public error payload/disclosure as well as status. Include references acquired before expiry and a controlled clock just before, at and after the contract-defined expiry boundary. Pin equality/retention semantics in Contract Design rather than inventing them here. Exercise owner changes while a result response is in flight and verify previous content is removed.
4. **Truthful outcomes and crash/redelivery (AC2.6.1–5).** For both tasks, provide successful prepared content, explicit abstention, unsuccessful and unavailable worker outcomes. Inject binding-write failure; interruption before durable binding; and interruption after binding commit but before terminal publication. Redeliver and race concurrent attempts with deterministic barriers. Observe generation counts, durable binding, legal state changes, terminal stability and state/events/result consistency. The after-generation/before-binding crash window needs an explicit design proof: a simulated exception with surviving in-memory state is not evidence of process-crash safety. Do not weaken the approved no-duplicate-generation obligation if its mechanism proves difficult; surface any demonstrated incompatibility.
5. **Recovery identities (AC4.2.7–9).** Independently seed retained binding, failed-dispatch released binding and retained executed-terminal failure. For replacement, assert old job remains terminal and tracking uses the actual new returned ID/state; for replay, preserve the returned original ID/state. Exercise response loss before any ID is known, delayed obsolete responses, authorization failure and repeated explicit clicks. No automatic retry loop, edited-request substitution, key rotation or inferred dispatch cause is permitted. For corrupt/missing original parameters and owner mismatch, assert the accessible unavailability explanation and zero resend requests, even if a key remains in storage.
6. **Lifecycle/accessible UI fixtures.** Isolate SWR caches, storage, fake clocks and EventSource instances per test. Cover out-of-order event/poll responses, duplicate replay, all terminal outcomes, unmount/job switch, owner loss, malformed events and render versus callback errors. Use real browser/BFF tests for incremental streaming and native reconnect; DOM mocks do not prove Last-Event-ID behavior. Preserve targeted keyboard, focus and actual screen-reader checks alongside automated accessibility checks.

### Sizing, evidence gates and human judgment

- Agree with the assessment's conditional medium-to-large sizing for US2.6/US3.4. Split technical work into outcome mapping, durable identity/binding, crash/concurrent reconciliation, owner/TTL read delivery and failure-injection verification. This is task decomposition under the stable story IDs, not five newly approved features. Do not double-count shared backend work under US3.1/US3.3.
- US4.2 spans pre-ID recovery, in-session recovery and reload eligibility; retain separate fixtures and technical tasks despite one user outcome. A hash-only persistence implementation cannot satisfy request reconstruction.
- The first integrated submit -> SSE -> COMPLETED -> result slice needs the successful durable-binding/read-only path from US2.6/US3.4, not a frontend fixture passed off as working integration. Failure paths remain mandatory release coverage; no skeleton checkpoint or verification command is approved by this contribution.
- Maintain test-after ordering, at least 80% new-code line coverage, current backend/frontend suite evidence, lint/typecheck and relevant E2E before merge. Standard test strategy does not remove the explicit backend regression obligations. NFR8 security-review ownership/scheduling and findings disposition remain mandatory downstream evidence.
- Retain NFR9's real staging production-build profile and 100 sequential samples per metric, strict p95 limits of 300/500/200 ms, decoded-image readiness, raw failures/timeouts and a pinned percentile calculation. Do not infer load capacity, auto-scaling or availability from this single-job benchmark. Preserve the accepted upstream R-01/R-02 provenance without claiming those findings were repaired upstream.
- **Fixable defects:** None identified in the current specification. Fixture detail and exact schema/state mapping are technical design/verification work, not missing product decisions at this stage.
- **Human judgment:** None needed now. If design demonstrates that required crash-safe duplicate-work protection or exact authorized read delivery cannot be achieved within the approved bounded remediation, present that evidenced scope/risk tradeoff to the human rather than relaxing acceptance. Do not re-ask the already approved replacement exception, read-only behavior, priorities or latency targets.

**Verification limits:** Manual document/JSON-text review only. No application tests were run or written; no traceability sensor, parser, source inspection, browser/security exercise, benchmark, coverage measurement or workflow/state command was run. Only this contribution file was changed. Historical source observations in the lead assessment remain attributed observations, not independently reproduced evidence. The lead should run the read-only traceability check on the final integrated map before gate presentation; this contribution claims no sensor pass.

## Positions

- AGREE: The amended draft covers 28 active stories and all 47 requirement identifiers on manual review; NFR8/NFR11 deferrals retain mandatory named downstream evidence, and excluded US4.3 supplies no active coverage.
- AGREE: US2.6 makes successful durable binding, truthful worker outcomes and crash/redelivery duplicate-work protection testable without prematurely fixing storage or state mappings.
- AGREE: US3.4 explicitly requires exact prepared content and zero generation/enqueue for all read outcomes, with unknown/not-owned 404 versus owner-verified expired 410 and no reference-based TTL bypass.
- AGREE: US4.2 distinguishes retained replay from failed-dispatch replacement, preserves terminal outcomes, and disables recovery when original request/owner context is unavailable rather than guessing.
- AGREE: Conditional sizing, fixture independence, strict quality gates and the real integrated skeleton are appropriate; technical contract details remain downstream obligations, not runtime readiness claims.
- AGREE: No current QA objection or immediate human-judgment question remains; the fixture recommendations refine verification of existing requirements without expanding scope.
