# Rough Mockups Questions — Phase 7 Frontend Wiring

**Gate:** Product Lead Review (advisory)

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.
- [memory:M1] `aidlc/spaces/default/memory/org.md#Way of Working`: "We use **trunk-based development**. All work merges to `main` via short-lived feature branches (typically resolved within 1-2 days)."
- [memory:M2] `aidlc/spaces/default/memory/org.md#Testing Posture`: "`feature` scope adds an 80% line-coverage floor and CI execution before merge."
- [memory:M3] `aidlc/spaces/default/memory/phases/ideation.md#Output Quality`: "All ideation artifacts must be readable by non-technical stakeholders"

---

## Questions for Design Review

### 1. JobStatus Visual Design
**Question:** Does the JobStatus wireframe match expected UX for job progress tracking?

- A. **Yes, as designed** — Progress bar + state text + live indicator + dismiss
- B. **Add estimated time remaining** — Show ETA based on progress rate
- C. **Simplify to spinner + text only** — Progress bar not needed
- D. **Show job queue position** — "3 jobs ahead of you" when QUEUED
- X. Other (please specify)

### 2. JobStatus Mount Location
**Question:** Where exactly in DetailPage should JobStatus render?

- A. **Below action buttons** — Directly under Summarize/Translate buttons (as wireframed)
- B. **Top of page** — Below paper title, above abstract
- C. **Sticky bottom** — Fixed at viewport bottom while scrolling
- D. **Side panel** — Collapsible drawer on right
- X. Other (please specify)

### 3. Failed State UX
**Question:** Is the inline Retry button sufficient for FAILED jobs?

- A. **Yes, inline Retry** — Re-submits with same idempotency key (as wireframed)
- B. **Add error details expandable** — Show full error stack on click
- C. **Add "Report Issue" button** — Link to support with jobId pre-filled
- D. **Auto-retry once** — Attempt one automatic retry before showing button
- X. Other (please specify)

### 4. AssetViewer Migration Visual
**Question:** Does the same-origin AssetViewer wireframe address all visual requirements?

- A. **Yes, direct img src** — No visual change, just URL pattern change
- B. **Add loading skeleton** — Show placeholder while asset loads
- C. **Add zoom/pan controls** — For large figures/tables
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

### 7. Responsive Behavior
**Question:** Is the responsive breakpoint strategy correct?

- A. **Yes, 3 breakpoints** — Mobile/Tablet/Desktop as defined
- B. **Mobile-first only** — Single column stack on all sizes
- C. **Add desktop sidebar** — JobStatus in sidebar on wide screens
- X. Other (please specify)

---

## Assumptions Being Carried Forward

| # | Assumption | Source |
|---|------------|--------|
| 1 | JobStatus component exists (unmounted) | Intent Capture / Feasibility |
| 2 | AssetViewer component exists (presigned URL) | Intent Capture / Feasibility |
| 3 | DetailPage/PaperView is mount target | Intent Capture Q4: A |
| 4 | Idempotency key: hash + localStorage | Intent Capture Q5: B / Feasibility Q2: C |
| 5 | Error UX: Inline Retry button | Intent Capture Q6: A |
| 6 | Asset cache: 60s private | Intent Capture Q7: A |
| 7 | SSE fallback: 2s fixed polling | Feasibility Open Q1: C |
| 8 | Error boundary: wrap JobStatus | Feasibility Open Q4: B |

---

## Open Questions for Refined Mockups

1. **Loading states**: Skeleton screens for JobStatus mount? AssetViewer load?
2. **Animation**: Progress bar transition easing? State change transitions?
3. **Empty states**: No job, no assets — what shows?
4. **Dark mode**: Color token overrides for dark theme?

---

## Confirmation

**Please respond with your choices (A/B/C/D/X) for questions 1-7.**

[Answer]:
1. A
2. A
3. C
4. C
5. B
6. A
7. A

---

## Consolidated Summary Confirmation

**Summary of your choices:**

1. **JobStatus Visual Design**: A — Yes, as designed (progress bar + state text + live indicator + dismiss)
2. **JobStatus Mount Location**: A — Below action buttons (under Summarize/Translate buttons)
3. **Failed State UX**: C — Add error details expandable (show full error stack on click)
4. **AssetViewer Migration Visual**: C — Add zoom/pan controls (for large figures/tables)
5. **Error Boundary Fallback**: B — Show last known state (preserve last SSE state in fallback)
6. **Accessibility Requirements**: A — Yes, ARIA live + progressbar (covers screen readers adequately)
7. **Responsive Behavior**: A — Yes, 3 breakpoints (Mobile/Tablet/Desktop as defined)

**Open Questions for Refined Mockups:**
- Loading states: Skeleton screens for JobStatus mount? AssetViewer load?
- Animation: Progress bar transition easing? State change transitions?
- Empty states: No job, no assets — what shows?
- Dark mode: Color token overrides for dark theme?

**Confirm** — Does this all look correct before I generate the artifact?

- A. **Looks correct** — Generate the artifact from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

[Answer]: Looks correct