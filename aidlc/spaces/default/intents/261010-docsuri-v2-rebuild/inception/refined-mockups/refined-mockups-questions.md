# DocSuri v2 — Refined Mockups questions

Date: 2026-10-11 (Asia/Seoul).

## Context and sources

The user approved [Requirements Analysis](../requirements-analysis/requirements.md). It defines 20 functional groups, 50 subrequirements, 10 non-functional requirements and two representative paper tasks. Preserve their stable IDs when mapping screens and interactions. The user accepted the advisory concern in [the product review](../requirements-analysis/reviews/review-01.md): recovery for unsent research questions and manuscript text still needs a defined outcome before affected implementation.

Rough Mockups and User Stories are skipped in the approved plan. Design directly from the approved requirements; do not claim that earlier wireframes or stories exist. All current capabilities remain in scope for first release, with the paper journey demonstrated first. The $0 free/local constraint, public registration, account isolation, one-maintainer model, evidence-dependent continuity/hosting choices and baseline-before-quality-target decisions are already settled.

The interview asks only for the design preferences and input-recovery policy not settled by those decisions. Screen coverage, navigation, loading/empty/error/success/partial states, safe confirmations, accessible interaction and component mapping will be derived from the requirements and checked in the design artifacts. Existing component/style evidence will inform reuse without selecting the v2 implementation stack. Applicable accessibility standards and responsive behavior will be made explicit in the consolidated proposal; no compliance or usability validation is claimed by drawing mockups.

Follow [CONVENTIONS.md](../../../../../../../CONVENTIONS.md): working branch → PR into develop → release promotion to main. Conversation and review artifacts remain in English. This does not silently change the product's retained language capabilities.

## Q1 — Visual direction

How much of the current interface's visual identity should carry into v2? Every choice retains the approved capabilities and emphasizes readable papers, clear actions and reliable feedback.

A. Fresh visual design, keeping the DocSuri name (Recommended). Rework layout, typography, color and component styling as one coherent system.
B. Evolve the current visual identity. Keep recognizable branding and styling cues while improving layout, consistency and interaction.
X. Other (please specify)

[Answer]: Fresh visual design, keeping the DocSuri name (Recommended): rework layout, typography, colors and components as one coherent system.

## Q2 — Device priority

Which device experience should lead the mockups? Every choice keeps all retained web UI capabilities usable on small and large screens; the choice controls design emphasis rather than feature access. Existing operational command-line tools do not acquire new mobile interfaces through this choice.

A. Desktop/laptop first (Recommended). Optimize deep reading and research on larger screens, then adapt the complete experience for phones and tablets.
B. Equal desktop and phone priority. Give both layouts equal emphasis from the first design pass.
C. Phone first. Lead with small-screen reading and research, then expand the layout for larger screens.
X. Other (please specify)

[Answer]: Desktop/laptop first (Recommended): optimize deep reading and research, then adapt the complete experience for phones and tablets.

## Q3 — Unsent input recovery

How should unsent research questions and manuscript text recover from interruptions? This resolves the open requirements-review concern; the storage mechanism and retention implementation remain design decisions subject to privacy and $0 constraints. Only unsent drafts follow this policy; committed messages, saved work and accepted jobs remain protected by the approved requirements. Neither option may expose a prior account's draft after an account change.

A. Recover after browser restart too (Recommended). Save owner-bound drafts for a later authenticated return; define retention, deletion and shared-device isolation before implementation, and show whether saving succeeded. This adds a durable draft-persistence commitment to protect long inputs.
B. Recover during the current visit. Keep entered text through in-app navigation and sign-in renewal while the tab stays open; warn before deliberate discard. Clear it on confirmed logout/account change. Browser/tab closure or a crash may lose unsent text, and the interface must state that limit.
X. Other (please specify)

[Answer]: Recover after browser restart too (Recommended): save owner-bound drafts for later authenticated return; define retention, deletion and shared-device isolation before implementation, and show whether saving succeeded.

## Assumptions & Open Questions

Q1–Q3 are answered without a detected contradiction: fresh visual design retaining the DocSuri name, desktop/laptop design priority with the complete web experience adapted for smaller screens, and durable owner-bound draft recovery. The approved requirements' existing evidence gaps remain open. Draft retention, deletion, shared-device isolation and storage implementation must be defined before affected implementation. A consolidated summary will be confirmed before mockups and interaction specifications are generated.

## Reference checks informing the proposal

- Current source has semantic colors, light/dark overrides and system-theme fallback, with the manual choice stored per browser rather than synchronized to an account. Preserve the supported appearance behavior while redesigning the palette and components; do not assume there is already a visible three-choice picker. Sources: [global styles](../../../../../../../frontend/app/globals.css), [theme context](../../../../../../../frontend/components/theme/ThemeContext.tsx), [theme utilities](../../../../../../../frontend/lib/theme.ts).
- Navigation and several form/result labels currently use Korean. The new mockups must account for this existing user-facing language and long/translatable text; English review prose does not authorize removing Korean support. Sources: [header](../../../../../../../frontend/components/AppHeader.tsx), [compact navigation](../../../../../../../frontend/components/BottomNav.tsx), [authentication field](../../../../../../../frontend/components/AuthField.tsx).
- Existing [job tracking](../../../../../../../frontend/components/JobStatus.tsx) and [result viewing](../../../../../../../frontend/components/SummaryModal.tsx) are useful behavioral references. The inspected result component reads an existing job result; its retry rereads rather than submits new work. The redesign must explicitly cover reconnect, access loss, failure, abstention, expiry, focus management and return to source. Source presence does not prove these interactions work end to end.
- Current [package metadata](../../../../../../../frontend/package.json) and styles describe a phone-first implementation. Q2 supersedes that design emphasis for v2. Existing libraries are reference inventory, not selected v2 technologies.
- Proposed accessibility design target: WCAG 2.2 AA, using the [W3C overview of changes](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/) and criterion guidance for [accessible authentication](https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html) and [target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html), checked 2026-10-11. Distinguish standard criteria from additional design preferences and later empirical performance targets. Checklist coverage and implementation testing will be recorded separately from any conformance claim.

These are bounded source and standards checks, not a rendered-interface audit, an exhaustive component inventory or evidence of usability validation. The requirements' current-source parity and evidence obligations still apply.

## Consolidated Summary Confirmation

- Create a fresh, coherent visual design while keeping the DocSuri name. Prioritize readable papers, clear actions, consistent components and understandable feedback.
- Design desktop/laptop layouts first, then adapt every retained web UI capability for phones and tablets. Specify responsive navigation, content reflow, long-text and zoom behavior without inventing new mobile interfaces for operational command-line tools.
- Map all 20 capability groups and their stable requirements to screens, interactions or the appropriate existing operational interface. Anchor the design in finding → understanding → saving → revisiting a paper, while retaining public registration, account isolation, administration and the remaining capabilities.
- Preserve unsent research questions and manuscript text as durable, owner-bound drafts recoverable after browser restart and authenticated return. Show saving, saved, failed and recovered states; define discard, account-switch/logout isolation and conflict behavior. Retention/deletion rules, storage and privacy implications must be resolved before implementation. This elaborates the accepted unsent-input concern and does not weaken protection for committed work or accepted jobs.
- Account for the current Korean-facing UI and preserve supported light/dark/system appearance behavior in the fresh design. Write review documents in English; keep product-language and component-reuse decisions explicit.
- Use WCAG 2.2 AA as the proposed accessibility design target, covering keyboard and focus behavior, readable contrast, reflow, status/error announcements, target sizing and accessible authentication. Produce a checklist and later verification plan without claiming that mockups establish conformance or user validation.
- Produce reviewable screen mockups, interaction specifications, design-system mapping and an accessibility checklist. Cover loading, empty, success, error, partial/degraded, interrupted, unauthorized and expired states. Keep reading a result separate from starting work and exporting separate from preview/approval.
- Keep the $0 free/local constraint and one-maintainer model. Technology, hosting, continuity/migration, privacy/content obligations, numeric service-quality targets and schedule remain subject to their existing evidence and decisions. Follow CONVENTIONS.md: working branch → PR into develop → release promotion to main.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
