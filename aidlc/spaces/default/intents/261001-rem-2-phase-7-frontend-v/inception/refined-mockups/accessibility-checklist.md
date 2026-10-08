# Accessibility Checklist — Phase 7 Frontend Wiring

## Basis and Evidence Status

Target: WCAG 2.1 AA for changed UI, as required by `../requirements-analysis/requirements.md` and `../user-stories/stories.md`. Apply confirmed `refined-mockups-questions.md`, `../practices-discovery/team-practices.md`, `mockups.md`, and `interaction-spec.md`. Historical `../../ideation/rough-mockups/wireframes.md` and `user-flow.md` are reconciled inputs, not conformance evidence.

Every check below is **Pending implementation verification**. Source inspection and this checklist do not certify browser, assistive-technology, or contrast behavior. The 44px control target is a design recommendation; applicable WCAG 2.1 AA requirements remain the conformance baseline.

## Perceivable

- [ ] **1.1.1 / US5.1, US6.3:** Main figures/tables preserve meaningful authorized text equivalents. Verify actual caption/alt/semantic data; a generic Asset label or short caption alone is not evidence of adequate complex-image equivalence. Decorative icons and the redundant noninteractive minimap are hidden from assistive technology.
- [ ] **1.3.1–1.3.2 / US6.1–US6.2:** Headings, named sections, disclosures, buttons and dialog relationships reflect reading order. Static status text is not forced into the tab sequence.
- [ ] **1.3.4:** Portrait/landscape use remains available.
- [ ] **1.4.1 / US2, US4, US7:** State, degraded connectivity, and failures use text/semantics alongside color.
- [ ] **1.4.3:** Normal text meets 4.5:1 and qualifying large text 3:1 in both themes on actual backgrounds. Check muted labels and filled-button combinations rather than trusting token names.
- [ ] **1.4.11:** Meaningful controls, progress graphics and focus indicators meet applicable 3:1 non-text contrast. Decorative borders are not relied on as the only control boundary.
- [ ] **1.4.4:** At 200% text resize, status, long IDs, recovery explanations and all controls remain available.
- [ ] **1.4.10:** At 320 CSS-pixel width/equivalent zoom, surrounding content reflows without two-dimensional page scrolling. Figures/tables may retain localized two-dimensional navigation; sticky status falls back to in-flow when needed.
- [ ] **1.4.12:** User text-spacing overrides do not clip content or controls.
- [ ] **1.4.13 where applicable:** Any hover/focus supplemental content is dismissible, hoverable and persistent. Recovery explanations are persistent text, not tooltip-only.

## Operable

- [ ] **2.1.1 / US3.2, US5.3, US6.2:** Submit, recover, copy, disclosures, zoom, pan, reset and return actions all work from keyboard. Zoom/pan has named clickable buttons as well as optional shortcuts/gestures.
- [ ] **2.1.2:** Tab can leave the asset viewer. An open modal confines interaction appropriately and can be closed by keyboard; no permanent trap is created.
- [ ] **2.1.4:** Character shortcuts apply only while their relevant viewer has focus and never intercept input in editable fields or globally.
- [ ] **2.2.2 where applicable:** Ongoing animated/updating content can be paused, stopped or hidden as applicable. Hide status remains available; decorative movement/pulsing is removed under reduced motion. Do not assume reduced motion alone resolves every auto-update obligation.
- [ ] **2.3.1:** No unsafe flashing is introduced.
- [ ] **2.4.3 / US6.2:** Opening a result focuses its named panel/heading; dismissal returns to the invoking control or specified surviving fallback. Full-page render failure focuses its heading; Return to paper focuses a surviving paper action. Ordinary background status updates never steal focus.
- [ ] **Recovery focus / AC6.2.5:** Successful pre-job handoff or tracking reset moves focus to the status heading only when the current target disappears. If the user moved elsewhere during the pending action and that element survives, retain focus there. Test result-read retry with the equivalent result-heading rule and focus on Close during completion.
- [ ] **2.4.4:** Recovery labels distinguish same-request recovery, tracking recovery, and asset reload. Link/action purpose is understandable in context.
- [ ] **2.4.7:** Focus is visible and not obscured by sticky status, navigation or overlays.
- [ ] **2.5.1:** Multipoint/path gestures have single-pointer button alternatives for zoom/pan/reset; keyboard support alone is not the pointer alternative.
- [ ] **2.5.2:** Pointer cancellation is respected; drag cancellation cannot trigger an unrelated action.
- [ ] **2.5.3:** Visible control wording is included in its accessible name.

## Understandable and Robust

- [ ] **3.1.1–3.1.2:** Preserve the actual page language and mark language changes when necessary; do not assume scientific source/result text is always the same language as UI chrome.
- [ ] **3.2.1–3.2.2:** Focus/background updates do not cause unexpected navigation or submission. View result, Return to paper and Recover tracking never trigger a new job POST.
- [ ] **3.3.1–3.3.3:** Submission, connection, copy and asset errors use safe understandable explanations and available actions. No raw stack traces, credentials or undocumented retry promises appear.
- [ ] **4.1.1–4.1.2:** Validate actual rendered structure, names, roles and values. React/TypeScript alone does not establish correct semantics.
- [ ] **4.1.3 / US6.1:** Meaningful submission/connectivity/result/asset/recovery/copy messages are announced without requiring focus movement. Replayed events and unchanged polling do not repeatedly announce.
- [ ] **Progress:** Known progress exposes an accurate value/range. Unknown progress omits fabricated aria-valuenow; ETA is explicitly approximate or unavailable and never inferred from guessed state percentages.
- [ ] **Unavailable recovery:** A surviving key with missing original parameters produces an understandable explanation and prevents guessed resend. Distinguish it from storage failure when exact in-memory context still permits recovery.
- [ ] **Submission/result separation:** Initial level/parameter selection is operable and never auto-submits; result view shows submitted-level metadata without an editable submission toggle. No result open/read/retry/copy interaction causes generation or submission.
- [ ] **Recovery semantics:** Announce actual returned state, distinguish retained-job replay from an evidenced failed-dispatch replacement, and use neutral wording when the cause is unknown. Do not claim a lost response proves failed dispatch or an old terminal job restarted.
- [ ] **Result states / US3.4:** Loading, 401, generic unknown/not-owned 404, owner-expired 410, unsupported/legacy reference, and transient read failure keep Close usable and announce safe messages. Only transient read retry is offered; it cannot generate/enqueue. No other-owner existence/expiry information appears.
- [ ] **Owner/access changes:** Remove protected prior-owner content and prevent late responses from repopulating it. Keep safe navigation and meaningful focus when a protected control disappears.

## Verification Matrix

| Surface | Required representative states | Evidence |
|---|---|---|
| Job status | Initial, indeterminate, actual progress, live, polling, offline, all terminal states | Component/semantic checks, keyboard and screen-reader session |
| Recovery | Pre-job uncertainty, retained job, evidenced replacement, unknown cause, same terminal job, missing originals, storage failure, owner change, stale old-job response | Request/identity assertions and focus tests including user moving focus while pending |
| Result dialog | Loading, exact prepared content, 401/404/410, unsupported legacy reference, transient retry, read-only metadata, open/close, late response | Focus trap/conditional return tests, safe announcements, zero-submit/generation assertions and real-browser keyboard use |
| Asset-ID copy | No ID, ready, pending, success, clipboard denial, long ID | Clipboard outcome tests plus live-message and reflow checks |
| Asset viewer | Skeleton, loaded, failed, access lost, zoom/pan bounds, reset, new asset | Keyboard/single-pointer operation, equivalents assessment, localized navigation |
| Full-page fallback | Render failure, tracking recovery, repeated failure, missing context, return | Correct focus destinations and absence of submission side effects |
| Themes/layout | Light/dark, mobile/tablet/desktop, 320px, 200% text resize, reduced motion | Measured contrast and manual/browser layout evidence |

Use the project's actual automated accessibility tooling where available, plus targeted keyboard and screen-reader checks. Do not invent package scripts or treat a DOM live-region assertion as proof of audible screen-reader behavior. Record tested browsers, assistive technologies, view states and findings during implementation verification. Application tests, benchmarks, and live authorization checks have not been run at this design stage.

## Outstanding Technical Evidence

Contract Design must confirm resultRef resolution and available asset equivalents. Functional Design must define request reconstruction, exact ETA validity, and parent/boundary recovery state. These do not relax the already-approved outcomes or performance profile; any demonstrated incompatibility requiring new scope must be surfaced before implementation.
