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

[Answer]: Request Changes: inherit DocSuri’s current colors and apply Apple’s Human Interface Guidelines.

The original answer chose a fresh visual design retaining the DocSuri name. After reviewing the first mockups, the user revised the color and design-reference direction with the answer above. Keep the DocSuri name and improve layout, typography and component consistency; carry forward the current blue/neutral palette instead of the first mockups' green palette. The goal is a stable, smooth, integrated experience.

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

Q1 is revised by the user's explicit feedback after reviewing the first mockups: inherit current DocSuri colors and apply Apple's Human Interface Guidelines (HIG). Q2 and Q3 remain unchanged: desktop/laptop design priority with the complete web experience adapted for smaller screens, and durable owner-bound draft recovery. Apply HIG principles to the web experience with documented platform adaptations. Preserve the approved appearance controls and accessibility target. The requirements' existing evidence gaps remain open. Draft retention, deletion, shared-device isolation and storage implementation must be defined before affected implementation. Confirm the revised consolidated summary before regenerating the mockups and interaction specifications.

## Reference checks informing the proposal

- Current source has semantic colors, light/dark overrides and system-theme fallback, with the manual choice stored per browser rather than synchronized to an account. Preserve the supported appearance behavior; do not assume there is already a visible three-choice picker. Sources: [global styles](../../../../../../../frontend/app/globals.css), [theme context](../../../../../../../frontend/components/theme/ThemeContext.tsx), [theme utilities](../../../../../../../frontend/lib/theme.ts).
- The current palette is blue/neutral: light accent `#2f6df6`, background `#ffffff`, surface `#f7f8fa` and text `#16181d`; dark accent `#5b8bff`, background `#131519`, surface `#1c1f25` and text `#f1f3f6`. Keep these as the inherited brand and appearance basis, including current semantic warning/danger families. Bounded direct inspection of global styles and the [landing](../../../../../../../frontend/components/HeroLanding.module.css), [search](../../../../../../../frontend/components/SearchScreen.module.css) and [header](../../../../../../../frontend/components/AppHeader.module.css) styles found those components using the shared tokens. This is not an exhaustive inventory of every color in the repository.
- Accessibility needs semantic variants for some inherited pairings. An sRGB relative-luminance calculation gives the light accent against white approximately 4.53:1, but against the light surface 4.26:1; current light border against white is 1.36:1 and dark border against dark surface is 1.26:1. Preserve decorative separators while defining stronger text/control-boundary variants where required; verify actual foreground/background pairs in the revised mockups. These calculations do not establish rendered accessibility conformance.
- Apple's [Layout](https://developer.apple.com/design/human-interface-guidelines/layout) guidance supports hierarchy through alignment, grouping and progressive disclosure. Web adaptation: a consistent research workspace with predictable navigation, retained search/paper context, readable content widths and responsive panels.
- Apple's [Materials](https://developer.apple.com/design/human-interface-guidelines/materials) guidance separates controls/navigation from content and calls for restrained effects. Web adaptation: keep paper text on stable reading surfaces, distinguish navigation and toolbars through spacing, tone and restrained depth, and provide solid fallbacks wherever transparency is used. Do not make native rendering effects or an Apple-only implementation a dependency.
- Apple's [Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode) guidance favors system appearance and testing both modes. Its recommendation against an app-specific appearance setting is not adopted because the approved parity scope preserves DocSuri's light/dark/system behavior. Default to system preference while retaining explicit overrides. Apple HIG references were checked on 2026-10-11; web adaptations are design judgments, not claims of native-platform conformance.
- Apple's [Typography](https://developer.apple.com/design/human-interface-guidelines/typography) guidance supports clear text hierarchy, limited typeface variation and layouts that accommodate larger text. Web adaptation: use Korean-capable system fonts, consistent heading/body/metadata roles, wrapping and browser zoom/reflow. Native point sizes and Dynamic Type APIs are not CSS requirements.
- Apple's [Buttons](https://developer.apple.com/design/human-interface-guidelines/buttons) guidance supports selective emphasis and clear actions with interaction feedback. Web adaptation: reserve the inherited blue for important actions and selected states; give search, save, job submission and novelty analysis precise labels and visible keyboard, pressed and progress states.
- Apple's [Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility) guidance supports adequate contrast, keyboard operation and conveying meaning beyond color. Apply those principles alongside the web-specific WCAG target, semantic HTML, accessible names, focus behavior and status announcements. Any chosen CSS target size is a web design decision, not a conversion of an Apple point measurement.
- Navigation and several form/result labels currently use Korean. The new mockups must account for this existing user-facing language and long/translatable text; English review prose does not authorize removing Korean support. Sources: [header](../../../../../../../frontend/components/AppHeader.tsx), [compact navigation](../../../../../../../frontend/components/BottomNav.tsx), [authentication field](../../../../../../../frontend/components/AuthField.tsx).
- Existing [job tracking](../../../../../../../frontend/components/JobStatus.tsx) and [result viewing](../../../../../../../frontend/components/SummaryModal.tsx) are useful behavioral references. The inspected result component reads an existing job result; its retry rereads rather than submits new work. The redesign must explicitly cover reconnect, access loss, failure, abstention, expiry, focus management and return to source. Source presence does not prove these interactions work end to end.
- Current [package metadata](../../../../../../../frontend/package.json) and styles describe a phone-first implementation. Q2 supersedes that design emphasis for v2. Existing libraries are reference inventory, not selected v2 technologies.
- Proposed accessibility design target: WCAG 2.2 AA, using the [W3C overview of changes](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/) and criterion guidance for [accessible authentication](https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html) and [target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html), checked 2026-10-11. Distinguish standard criteria from additional design preferences and later empirical performance targets. Checklist coverage and implementation testing will be recorded separately from any conformance claim.

These are bounded source and standards checks, not a rendered-interface audit, an exhaustive component inventory or evidence of usability validation. The requirements' current-source parity and evidence obligations still apply.

## Consolidated Summary Confirmation

- Keep the DocSuri name and inherit the current blue/neutral colors: blue accents `#2f6df6` in light mode and `#5b8bff` in dark mode, with the existing neutral surfaces. Add accessible semantic variants where measured contrast requires them.
- Apply Apple's Human Interface Guidelines to the web experience: clear hierarchy, readable typography, consistent navigation, grouped controls, progressive disclosure and restrained depth. Aim for one stable, smooth, integrated research workspace that preserves context across finding → understanding → saving → revisiting a paper. Document web adaptations explicitly.
- Keep desktop/laptop priority, with all retained web capabilities usable on phones and tablets. Preserve the Korean-facing experience and light/dark/system behavior. Retain all 20 capability groups, public registration, account isolation, administration and operational interfaces; defer new feature expansion.
- Keep durable, owner-bound drafts recoverable after browser restart and authenticated return. Describe recovery only for acknowledged saves; show saving, saved, failed, recovered and conflict states accurately. Define retention, deletion, storage and shared-device isolation before implementation, while preserving committed work and accepted jobs.
- Fix the three existing review findings: retain query/filter controls during search loading, empty and error states; make draft helper text agree with the actual save/recovery state; label the novelty action as starting analysis.
- Revise the screen atlas, mockups, interaction specifications, design-system mapping and accessibility checklist. Preserve WCAG 2.2 AA as the design target, keyboard/focus support, responsive reflow and clear status/error feedback. Cover degraded and interrupted states, keep result viewing separate from starting work, and keep export preview separate from explicit export approval. Verify the revised prototype and obtain a fresh product review without claiming conformance or user validation.
- Keep the $0 free/local constraint, one-maintainer model and existing evidence-dependent technology, hosting, continuity/migration, obligations, numeric quality targets and schedule decisions. Git follows CONVENTIONS.md: working branch → PR into develop → release promotion to main.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
