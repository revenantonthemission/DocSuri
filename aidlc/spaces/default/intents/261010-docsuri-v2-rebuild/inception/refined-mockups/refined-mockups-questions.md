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

[Answer]:

## Q2 — Device priority

Which device experience should lead the mockups? Every choice keeps all retained web UI capabilities usable on small and large screens; the choice controls design emphasis rather than feature access. Existing operational command-line tools do not acquire new mobile interfaces through this choice.

A. Desktop/laptop first (Recommended). Optimize deep reading and research on larger screens, then adapt the complete experience for phones and tablets.
B. Equal desktop and phone priority. Give both layouts equal emphasis from the first design pass.
C. Phone first. Lead with small-screen reading and research, then expand the layout for larger screens.
X. Other (please specify)

[Answer]:

## Q3 — Unsent input recovery

How should unsent research questions and manuscript text recover from interruptions? This resolves the open requirements-review concern; the storage mechanism and retention implementation remain design decisions subject to privacy and $0 constraints. Only unsent drafts follow this policy; committed messages, saved work and accepted jobs remain protected by the approved requirements. Neither option may expose a prior account's draft after an account change.

A. Recover after browser restart too (Recommended). Save owner-bound drafts for a later authenticated return; define retention, deletion and shared-device isolation before implementation, and show whether saving succeeded. This adds a durable draft-persistence commitment to protect long inputs.
B. Recover during the current visit. Keep entered text through in-app navigation and sign-in renewal while the tab stays open; warn before deliberate discard. Clear it on confirmed logout/account change. Browser/tab closure or a crash may lose unsent text, and the interface must state that limit.
X. Other (please specify)

[Answer]:

## Assumptions & Open Questions

Q1–Q3 are unanswered. No visual direction, device priority or draft policy is selected by this file. The approved requirements' existing evidence gaps remain open. A consolidated summary will be confirmed before mockups and interaction specifications are generated.
