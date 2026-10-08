# Unit Story Map — Phase 7

## Sources and Interpretation

`../user-stories/stories.md` supplies the stable US/AC identifiers; `unit-of-work.md` supplies unit boundaries. All 28 active stories remain Must Have; US4.3 remains excluded. A primary/completion unit is accountable for closing the whole story after all listed contributions are verified. Assignment is not completion evidence. U1 must still test every behavior it delivers even when a spanning story closes in U2.

| Story | Primary/completion Unit ID | Directory | Contributing units and acceptance allocation |
|---|---|---|---|
| US1.1 | U1 | u1-job-skeleton | U1 AC1.1.1–5 summarize path; AC1.1.6 restricts this integration's task scope. U2 adds the translate action under US1.2, never other task types. |
| US1.2 | U2 | u2-job-resilience | U2 AC1.2.1–4 translation; consumes U1 identity and BFF. |
| US1.3 | U1 | u1-job-skeleton | U1 AC1.3.1–5 digest, owner inputs, contract field and controlled hashing failure. U2 reuses and regression-tests it. |
| US1.4 | U2 | u2-job-resilience | U1 AC1.4.1 persistence attempt, basic same-context identity checks and AC1.4.5 no rotation on result reads; U2 completes AC1.4.2–4 reload/corrupt/quota/owner-request reconciliation and full integration coverage. |
| US1.5 | U1 | u1-job-skeleton | U1 AC1.5.1–6 job BFF/cookie/CSP/identity/stream fidelity. U2 exercises recreated-cursor end-to-end cases through that existing contract. |
| US2.1 | U1 | u1-job-skeleton | U1 AC2.1.1–5 live updates, initial cursor behavior and controlled malformed-event/failure handling; U2 extends resume scenarios. |
| US2.2 | U1 | u1-job-skeleton | U1 AC2.2.1–6 actual states, honest progress, terminal outcomes and nonregressing observed history. U2 adds comprehensive replay fixtures under US2.3. |
| US2.3 | U2 | u2-job-resilience | U1 honors verified native resume and suppresses stale observations; U2 closes AC2.3.1–4 recreated connections, missed/duplicate replay and fallback scenarios. |
| US2.4 | U1 | u1-job-skeleton | U1 AC2.4.1–4 two-second SWR polling, degraded indicator, current-state updates and honest stale/offline handling. |
| US2.5 | U2 | u2-job-resilience | U1 implements cleanup for AC2.5.1–5 in its delivered flow; U2 closes the full restoration/terminal/navigation/owner-loss matrix including translation and recreated streams. |
| US2.6 | U1 | u1-job-skeleton | U1 AC2.6.1–5 for summary/translation worker and service fixtures: truthful outcomes, durable binding before completion, persistence interruption, all declared crash/redelivery windows and consistent authorized state/events/results. U2 contributes translation UI integration only. |
| US3.1 | U2 | u2-job-resilience | U1 implements AC3.1.1–6 for summarize and the shared backend owner-safe 401/404/410 contract. U2 completes translation UI and the full result-state interaction matrix without deferring secure skeleton reads. |
| US3.2 | U2 | u2-job-resilience | U2 AC3.2.1–5 authorized supplied ID, keyboard copy, clipboard outcomes and absent/denied ID handling. U3 delivery enforces authorization on subsequent asset use; ID-copy UI is independently testable against authorized result fixtures. |
| US3.3 | U2 | u2-job-resilience | U1 AC3.3.1–3 summary opening, safe formatting and focus return; U2 completes translation and AC3.3.4 expiry/unavailability cases. |
| US3.4 | U1 | u1-job-skeleton | U1 AC3.4.1–6 backend exact-result guarantees for both task fixtures and summarize integration: prepared overlays across settings changes, zero generation/enqueue on every read outcome, controlled legacy references, owner/expiry isolation and no alternate reference-path bypass. U2's translation UI adds integration evidence without owning a missing backend capability. |
| US4.1 | U1 | u1-job-skeleton | U1 AC4.1.1–4 safe inline terminal failure details without restart promises. U2 retains and tests these in extended scenarios. |
| US4.2 | U2 | u2-job-resilience | U1 AC4.2.1–9 for its in-session flow plus backend replay/failed-dispatch-release/executed-terminal fixtures: pre-job handoff, neutral uncertainty, replacement identity and old-job suppression. U2 closes reload/storage/unavailable-original and the wider frontend failure matrix. No changed parameters, forced key rotation or old-terminal restart. |
| US4.3 | U2 | u2-job-resilience | Explicit Won't Have exclusion, not feature implementation. U2 owns exclusion verification through US4.2; no modified-parameter retry is delivered. |
| US5.1 | U3 | u3-secure-assets | U3 AC5.1.1–5 same-origin image route, no presigned fallback, session forwarding, private cache and controlled failures. |
| US5.2 | U3 | u3-secure-assets | U3 AC5.2.1–5 server auth/license check, denial/missing bytes, cookie fidelity and honest cache-hit semantics. |
| US5.3 | U3 | u3-secure-assets | U3 AC5.3.1–5 zoom/pan/reset, keyboard focus/names and no protected-content bypass. |
| US6.1 | U2 | u2-job-resilience | U1 status/submission/recovery/result/fallback announcements and duplicate suppression; U2 completes job/copy matrix; U3 owns asset-load/control feedback in AC6.1.6. Full story closure requires U1, U2 and U3 evidence for AC6.1.1–7. |
| US6.2 | U2 | u2-job-resilience | U1 progress semantics, submission/recovery and result/fallback focus; U2 adds translation/copy/full job matrix; U3 owns asset keyboard navigation and no-trap/focus cases. All three contribute AC6.2.1–5 as applicable. |
| US6.3 | U2 | u2-job-resilience | U1 verifies its visuals; U2 verifies extended job/copy surfaces; U3 verifies assets/controls. AC6.3.1–7 include applicable contrast, real assistive checks, 200% text resize and 320 CSS-pixel reflow across all units. Completion is a release evidence join, not a U2→U3 code dependency. |
| US7.1 | U1 | u1-job-skeleton | U1 AC7.1.1–4 boundary integration, caught render failure, fallback and separate async handling. |
| US7.2 | U1 | u1-job-skeleton | U1 AC7.2.1–4 safe full-page fallback, operable recovery, scrubbed Sentry and usable focus/layout. |
| US7.3 | U2 | u2-job-resilience | U1 original-job tracking-only remount and controlled failure/no submit; U2 closes AC7.3.1–4 with recreated-cursor continuity and duplicate-history cases. |
| US8.1 | U2 | u2-job-resilience | U1 scrubbed error capture and submission/connection timing/events for delivered behavior; U2 closes AC8.1.1–4 full drop/recovery/job lifecycle and diagnostic-delivery failure cases. |
| US8.2 | U2 | u2-job-resilience | U1 supplies job timing points; U2 owns AC8.2.1/3 job measurements; U3 owns AC8.2.2 asset decoded-readiness measurements; both supply AC8.2.4–5 raw staging-profile samples and honest failure reporting. Release closure requires all relevant evidence, not a capability edge between U2 and U3. |

## Local Story Implementation Order

These are within-unit dependency hints, not a global Bolt sequence. Test each implemented component after its implementation, per the affirmed methodology.

- **U1:** Identity and authenticated transport foundations (US1.3/US1.5 and U1's US1.4 slice); implement backend outcome/binding/read contracts (US2.6/US3.4) before claiming the browser result path works; submission/pre-job recovery (US1.1/US4.2 slice); containment before tracking exposure (US7.1/US7.2); live state/fallback/cleanup and real frame parsing (US2.1/US2.2/US2.4); authorized summarize result opening (US3.1/US3.3 slices). Test both backend task types and all declared effect windows. Accessibility and safe diagnostics accompany each surface.
- **U2:** Extend identity/reload recovery before translate and remaining resend scenarios; complete stream replay/recovery before the full cleanup/fallback matrix; complete result error/copy behaviors; gather combined job accessibility, diagnostics and performance evidence. U3's independent evidence is joined at release closure, not needed to implement U2.
- **U3:** Establish secure asset delivery and document integration (US5.1/US5.2) before zoom/pan/reset (US5.3); verify accessibility and timing of those delivered surfaces. Maintain job-proxy regression checks on shared-server edits.

## Coverage Verification and Process Obligations

All 29 historical identifiers are listed: 28 active stories and one excluded story. Every unit has active implementation responsibilities. `traceability.json` uses one primary unit per active story; US4.3 remains N/A, with U2 assigned only to verify its exclusion under US4.2. US2.6/US3.4 are assigned to U1; later translation UI evidence remains part of US1.2/US3.1/US3.3 completion. Cross-unit accessibility and performance joins must not be declared complete merely because their primary unit finished.

NFR8's review scheduling belongs to Delivery Planning, with U3 providing asset security evidence and disposition before release. NFR11's current-suite/lint/typecheck/E2E/coverage evidence belongs to Build and Test; every unit supplies tests and must meet its own applicable quality obligations. The real skeleton checkpoint is separate from story completion and requires the later human-authorized integrated verification command.
