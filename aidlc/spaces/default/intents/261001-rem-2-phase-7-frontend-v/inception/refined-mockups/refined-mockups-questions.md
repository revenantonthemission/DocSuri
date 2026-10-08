# Refined Mockups Questions — Phase 7 Frontend Wiring

**Gate:** Product Lead Review (advisory)

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.
- [memory:M1] `aidlc/spaces/default/memory/team.md#Testing Posture`: "Methodology: test-after, Ordering: Test-last per component"
- [memory:M2] `aidlc/spaces/default/memory/team.md#Walking Skeleton`: "Stance: ON — Build a thin end-to-end slice first"
- [memory:M3] `aidlc/spaces/default/memory/team.md#Deployment`: "Continuous deployment to production on merge"
- [memory:M4] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS route all content-job API calls through `/bff/api/content-jobs/*` (SEC-8)"
- [memory:M5] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS generate idempotency keys as SHA-256 hash"
- [memory:M6] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS wrap JobStatus in React Error Boundary"
- [memory:M7] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS use same-origin asset delivery via `/bff/api/papers/{paperId}/assets/{assetId}`"
- [memory:M8] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS integrate Sentry for client-side error tracking"
- [memory:M9] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS conduct security review mid-implementation (Week 2)"
- [requirements] `../requirements-analysis/requirements.md`: approved baseline with FR3.4 copyable asset IDs and FR5.5 accessible zoom/pan.
- [stories] `../user-stories/stories.md`: approved same-key recovery, accurate progress, safe errors, focus/announcement/reflow behavior, and contract prerequisites.
- [source] `frontend/components/SummaryModal.tsx`, `SummaryModal.module.css`, `PaperDetailIsland.tsx`, `AssetViewer.tsx`, and `frontend/app/globals.css`: inspected existing modal, detail-page integration, asset implementation, and semantic light/dark tokens. These are source observations, not runtime verification.

---

## Questions for Refined Mockups Review

### 1. JobStatus Visual Design
**Question:** Does the refined JobStatus visual design match expected UX for job progress tracking?

- A. **Yes, as designed** — Progress bar + state text + live indicator + dismiss + error detail toggle
- B. **Add estimated time remaining** — Show ETA based on progress rate
- C. **Simplify to spinner + text only** — Progress bar not needed
- D. **Show job queue position** — "3 jobs ahead of you" when QUEUED
- X. Other (please specify)

### 2. JobStatus Mount Location
**Question:** Where exactly in PaperDetailIsland should JobStatus render?

- A. **Below action buttons** — Directly under Summarize/Translate buttons (as wireframed)
- B. **Top of page** — Below paper title, above abstract
- C. **Sticky bottom** — Fixed at viewport bottom while scrolling
- D. **Side panel** — Collapsible drawer on right
- X. Other (please specify)

### 3. Failed State UX
**Question:** Is the inline Retry + Error Detail Toggle sufficient for FAILED jobs?

- A. **Yes, inline Retry + Error Detail Toggle** — Re-submits with same idempotency key, expandable error stack
- B. **Add "Report Issue" button** — Link to support with jobId pre-filled
- C. **Auto-retry once** — Attempt one automatic retry before showing button
- D. **Show toast notification** — Global toast in addition to inline
- X. Other (please specify)

### 4. AssetViewer Migration Visual
**Question:** Does the same-origin AssetViewer design address all visual requirements?

- A. **Yes, direct img src** — No visual change, just URL pattern change
- B. **Add loading skeleton** — Show placeholder while asset loads
- C. **Add zoom/pan controls** — For large figures/tables (as designed)
- D. **Show auth status badge** — "🔒 Private" or "🌐 Public" indicator
- X. Other (please specify)

### 5. Error Boundary Fallback
**Question:** Is the error boundary fallback design appropriate?

- A. **Yes, minimal fallback** — "Unable to load" + retry connection button
- B. **Show last known state** — Preserve last SSE state in fallback
- C. **Full page error** — Navigate to error page instead of inline
- D. **Auto-refresh** — Attempt reconnect every 10s automatically
- X. Other (please specify)

### 6. Accessibility Requirements
**Question:** Are the accessibility annotations sufficient for implementation?

- A. **Yes, ARIA live + progressbar** — Covers screen readers adequately
- B. **Add keyboard shortcuts** — `Ctrl+Enter` to submit, `Escape` to dismiss
- C. **Add high contrast mode** — Specific tokens for forced colors
- D. **Reduce motion** — Respect `prefers-reduced-motion` for progress animation
- X. Other (please specify)

### 7. Zoom/Pan Controls (AssetViewer)
**Question:** Are the zoom/pan controls sufficient for large figures/tables?

- A. **Yes, as designed** — Mouse wheel, drag, double-click, keyboard, touch
- B. **Add minimap/overview** — Small thumbnail showing viewport position
- C. **Add measurement tools** — Distance/angle measurement for figures
- D. **Simplify to zoom only** — No pan, just zoom in/out/reset
- X. Other (please specify)

### 8. Design Tokens & Color Contrast
**Question:** Are the design tokens and color contrast sufficient?

- A. **Yes, as defined** — All status colors ≥4.5:1 contrast, progress bar tokens defined
- B. **Add dark mode tokens** — Dark mode overrides for all status colors
- C. **Use semantic color names** — `--color-success`, `--color-warning` instead of status-specific
- D. **Add motion tokens** — `--duration-fast`, `--duration-normal` for consistency
- X. Other (please specify)

### 9. Responsive Breakpoints
**Question:** Is the responsive breakpoint strategy correct?

- A. **Yes, 3 breakpoints** — Mobile/Tablet/Desktop as defined
- B. **Mobile-first only** — Single column stack on all sizes
- C. **Add desktop sidebar** — JobStatus in sidebar on wide screens
- D. **Add 2xl breakpoint** — >1536px for ultra-wide
- X. Other (please specify)

### 10. Animation & Motion
**Question:** Are the animation specifications sufficient?

- A. **Yes, as defined** — Progress bar 300ms, mount 200ms, respect reduced motion
- B. **Add spring physics** — Use Framer Motion for natural feel
- C. **Simplify to CSS transitions only** — No keyframe animations
- D. **Add micro-interactions** — Button hover/tap feedback, state change pulses
- X. Other (please specify)

---

## Assumptions Being Carried Forward

| # | Assumption | Source |
|---|------------|--------|
| 1 | JobStatus mounts below action buttons in PaperDetailIsland | Rough Mockups Q2: A |
| 2 | JobStatus shows full event history with timestamps | Rough Mockups Q1: A |
| 3 | Failed state shows inline Retry + expandable error details | Rough Mockups Q3: C |
| 4 | AssetViewer uses direct img src with paperId+assetId | Rough Mockups Q4: A |
| 5 | Error Boundary wraps JobStatus with fallback UI | Rough Mockups Q5: A |
| 6 | Accessibility: ARIA live + progressbar | Rough Mockups Q6: A |
| 7 | AssetViewer has zoom/pan controls | Rough Mockups Q4: C |
| 8 | Responsive: 3 breakpoints (Mobile/Tablet/Desktop) | Rough Mockups Q7: A |

---

## Open Questions for Domain Design

1. **JobStatus multiple instances:** Can multiple JobStatus components mount simultaneously (e.g., summarize + translate concurrently)? How to manage SSE connections?
2. **JobStatus persistence:** Should JobState persist in URL query params for shareability?
3. **AssetViewer caching:** Should AssetViewer implement client-side caching beyond browser cache?
4. **Sentry integration point:** Where exactly in the component tree should Sentry ErrorBoundary sit?
5. **Walking skeleton verification:** What specific E2E test validates the walking skeleton?

---

## Confirmation

**Please respond with your choices (A/B/C/D/X) for questions 1-10.**

[Answer]:
1. B
2. C
3. A
4. B
5. C
6. A
7. B
8. C
9. A
10. D

---

## Previous Attempt Summary

**Summary of your choices:**

1. **JobStatus Visual Design**: B — Add estimated time remaining (ETA based on progress rate)
2. **JobStatus Mount Location**: C — Sticky bottom (fixed at viewport bottom while scrolling)
3. **Failed State UX**: A — Yes, inline Retry + Error Detail Toggle (re-submits with same idempotency key, expandable error stack)
4. **AssetViewer Migration Visual**: B — Add loading skeleton (show placeholder while asset loads)
5. **Error Boundary Fallback**: C — Full page error (navigate to error page instead of inline)
6. **Accessibility Requirements**: A — Yes, ARIA live + progressbar (covers screen readers adequately)
7. **Zoom/Pan Controls**: B — Add minimap/overview (small thumbnail showing viewport position)
8. **Design Tokens & Color Contrast**: C — Use semantic color names (--color-success, --color-warning instead of status-specific)
9. **Responsive Breakpoints**: A — Yes, 3 breakpoints (Mobile/Tablet/Desktop as defined)
10. **Animation & Motion**: D — Add micro-interactions (button hover/tap feedback, state change pulses)

**Assumptions Confirmed:** All 8 assumptions from rough mockups carry forward.

**Open Questions for Domain Design:**
- JobStatus multiple instances: Can multiple JobStatus components mount simultaneously?
- JobStatus persistence: Should JobState persist in URL query params for shareability?
- AssetViewer caching: Should AssetViewer implement client-side caching beyond browser cache?
- Sentry integration point: Where exactly in the component tree should Sentry ErrorBoundary sit?
- Walking skeleton verification: What specific E2E test validates the walking skeleton?

**Confirm** — Does this all look correct before I generate the final refined mockups artifacts?

- A. **Looks correct** — Generate the artifact from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

**Previous confirmation:** Looks correct

## Reconciled Design Plan

The user selected Modify. Existing choices are carried forward below, with behavior constrained by the subsequently approved requirements and stories. The old raw-stack, fabricated-progress, changed-parameter retry, and weaker latency examples are superseded.

- Preserve the selected sticky-bottom JobStatus presentation (Q2: C) on the paper-detail page, with safe-area/bottom-navigation clearance and layout adaptation so it does not obscure controls at narrow widths or browser zoom. Modal overlays remain above it and background updates never steal focus.
- Preserve the ETA preference (Q1: B), but display an explicitly approximate estimate only when actual contract-supported progress samples justify it. Show an unavailable estimate/indeterminate progress otherwise; never derive a fictional percentage from SUBMITTED/ACCEPTED/QUEUED states or promise a completion time.
- Keep inline same-key submission recovery with expandable user-safe details (Q3: A, constrained by FR4 and US4.2). Remove raw stack traces and Retry with changes. Distinguish submission recovery, tracking reconnection, and asset reload in labels and behavior.
- Preserve asset loading skeletons (Q4: B), authorized asset-ID copying with success/failure feedback, and accessible zoom-in/out, pan, and reset-to-fit. Retain the minimap/overview preference (Q7: B) as a presentation of the same authorized image, not a new asset endpoint or access path.
- Preserve the full-page error presentation preference (Q5: C) for a rendering-boundary failure, with a route back to the paper and tracking-only recovery when authorized job context survives. This is not a job failure, cancellation, or permission to resubmit; it must retain a recoverable reading workflow and meaningful focus. Network/SSE errors use their explicit connection states instead of automatically invoking the render-error page.
- Provide an explicit unavailable-recovery state when only an idempotency key survives reload but original parameters cannot be reconstructed: explain that the original request details are unavailable, prevent resend with guessed parameters, and keep view/dismiss navigation available as authorized context permits. Functional Design will pin reconstruction/storage details.
- Use the existing summary/translation modal pattern. The inspected component is a centered dialog, not the old draft's new radio-option form or mandatory full-screen phone modal. Result viewing must read the existing completed result and must not reuse a mount path that submits another job. Specify focus entry/containment/return and the authorized resultRef contract prerequisite.
- Retain semantic color naming (Q8: C), using the real existing light/dark CSS variables as the starting point. Mark any new token as proposed and verify contrast rather than claim the old palette already passes.
- Retain mobile/tablet/desktop layout coverage (Q9: A), reconciling component breakpoints with existing styles rather than globally changing the application breakpoints. Cover 320 CSS-pixel reflow, 200% text resize, long identifiers, and accessible localized asset navigation.
- Retain micro-interactions (Q10: D) with reduced-motion alternatives. Motion must not delay committed status UI beyond the approved budgets or repeatedly announce unchanged polling data.
- Apply full WCAG 2.1 AA obligations (Q6 and approved stories), including text alternatives, focus visibility, no keyboard traps, meaningful nonterminal status/error announcements, and copy feedback. Existing image captions/equivalents must be verified; do not invent content metadata.
- Preserve all three staging p95 targets and their confirmed measurement profile: SSE under 300 ms, decoded asset under 500 ms, and JobStatus mount under 200 ms. Remove conflicting historical 500 ms/1 s timing budgets and unapproved reconnect-count guarantees.
- Deliver revised `mockups.md`, `interaction-spec.md`, `design-system-mapping.md`, and `accessibility-checklist.md` with state/interaction coverage tied to the approved story IDs. These are design specifications; runtime conformance and measured performance still require implementation testing.

## Amendment Reconciliation Plan

Source authority: amended Requirements Analysis Q15/Q16, FR2.5/FR3.5, and the approved 28 active User Stories, especially US2.6, US3.4, AC4.2.7–9 and AC6.2.5. Preserve the selected visual direction above while replacing obsolete recovery/result assumptions. The following is the proposed current summary for confirmation, not runtime evidence.

- **Separate submission and reading:** Explicitly show initial summary-level selection in the submission surface and preserve supported initial translation parameters. Only explicit Submit starts work. The centered SummaryModal result surface shows the submitted level as read-only metadata; opening, changing display state, copying or retrying a read cannot submit. This carries the previously selected component split into visible UI behavior and addresses the earlier summary-level omission.
- **Pre-job uncertainty and recovery:** Place the uncertain-outcome recovery UI in JobSubmissionForm before a job ID exists. Use neutral copy such as “Resend the unchanged request to check its outcome.” Explain that ordinary recovery finds the original job, while a released key after failed dispatch can produce a replacement; never promise every resend recovers the same identity. Render the actual returned job/state. Say a dispatch-failure replacement occurred only with authoritative evidence; a lost response or an unexplained ID alone does not prove the cause. Retain a clear unavailable-recovery explanation when originals cannot be reconstructed.
- **Truthful outcomes:** Preserve actual backend states and safe reasons. Do not invent frontend COMPLETED while content/binding is not ready; a read failure after actual completion is result unavailability, not a fabricated transition of the job. The new backend guarantees remain implementation prerequisites.
- **Exact read-only result states:** Show the prepared result tied to the selected job without recalculating it from current settings. Specify loading, available, authentication-required (401), generic unavailable (unknown/not-owned 404), owner-expired (410), unsupported/legacy-reference unavailable and transient read failure. Keep Close available throughout. Offer Retry result read for transient failure only; it repeats the read, never generation or submission. Do not reveal ownership/existence through 404 wording.
- **Focus continuity:** Preserve the current focused element when it survives recovery. If the focused recovery action disappears, move focus to the resulting status heading; if the user moved elsewhere while recovery was pending, do not steal it back. Apply to pre-job handoff and full-page tracking recovery. Preserve dialog focus containment/return, and suppress stale UI updates from an old job after replacement.
- **Component input detail:** Expand the interaction specification with conceptual input type, required/optional status, default or absence behavior, and composition examples for submission, status, result, assets and fallback. Clearly label these as UI design interfaces, not invented wire fields. Missing meaningful image equivalents are a gap, not decorative-image permission. This addresses the earlier input/default/example and transient-result-state omissions.
- **Visual and verification continuity:** Keep sticky-bottom status with constrained-layout fallback, conditional ETA, semantic light/dark tokens, reduced motion, asset skeleton/minimap/zoom/pan, and full-page rendering-failure presentation. Update the accessibility checklist for new recovery/result states, including no focus theft after asynchronous completion. Preserve NFR9's staging budgets and mark all implementation/runtime checks pending.

## Consolidated Summary Confirmation

The Reconciled Design Plan supplies the preserved visual choices; the Amendment Reconciliation Plan above governs the updated submission/recovery/result semantics, focus rules and input documentation. Where they differ, the amendment applies. Generate the four revised design documents and this questions record, then obtain independent product-lead review, carrying prior finding IDs forward for evidence-based disposition.

Does this all look correct before I generate the revised refined-mockup artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
