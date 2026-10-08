# Personas — Phase 7 Frontend Wiring

## Sources and Evidence Limits

The three archetypes were selected in `user-stories-questions.md` Q1. Their feature boundaries come from `../requirements-analysis/requirements.md`, including FR3.4 and FR5.5. `aidlc/spaces/default/codekb/DocSuri/business-overview.md` and `component-inventory.md` describe the existing paper-detail workflow; `../practices-discovery/team-practices.md` supplies the quality constraints.

The names and contexts below are illustrative personas, not verified user interviews. Previous draft job-count estimates are not workload requirements. Mobile browser use does not add a native app, and a pain point does not authorize a feature outside the approved requirements.

The approved backend amendment adds no persona or access role. All readers need truthful worker outcomes (US2.6) and the exact completed result (US3.4). Recovery feedback must distinguish retained-job replay from an evidenced replacement after dispatch failure; uncertainty is not evidence that a prior job failed dispatch or restarted.

## Persona Definitions

### Researcher — Primary

**Illustrative name:** Dr. Maria Santos. **Role:** Frequent research-paper reader.

- **Goals:** Summarize/translate accessible papers, follow real job progress, recover uncertain submissions without duplicates, inspect large figures, and reference authorized asset IDs.
- **Pain points:** Lost submission responses, stale progress, missing results, and hard-to-read figure details.
- **Context:** Desktop browser, potentially revisiting a paper after reload. Technical expertise is not required to understand recovery limits.
- **Relevant stories:** Submission/progress/results/recovery groups, US5.1–US5.3, accessibility and containment groups, US8.1–US8.2.

### Student — Secondary

**Illustrative name:** Alex Chen. **Role:** Reader using papers for study.

- **Goals:** Obtain summaries/translations, understand pending/failure states, open results, and recover tracking accessibly.
- **Pain points:** Technical status labels, unclear errors, and uncertainty about whether a retry starts new work.
- **Context:** Desktop or mobile web browser. Keyboard and screen-reader use are possible; responsive web access does not require a native app.
- **Relevant stories:** US1.1–US1.5, progress/results/recovery groups, US5.1–US5.2, accessibility and containment groups, US8.2.

### Casual Reader — Tertiary

**Illustrative name:** Jordan Kim. **Role:** Occasional paper reader.

- **Goals:** Read available results, view authorized figures/tables, inspect them with zoom/pan, and understand loading/failure feedback.
- **Pain points:** Silent asset failures, inaccessible controls, and visually dense status displays.
- **Context:** Desktop or mobile web browser; prefers plain-language feedback. Offline access is not a requirement of this release.
- **Relevant stories:** US3.1–US3.4, US2.6, US5.1–US5.3, accessibility and containment groups, US8.2.

## Cross-Cutting Accessibility and Authorization

Keyboard-only, screen-reader, and low-vision use are contexts of all three personas, not separate user roles requiring new permissions. All job/result/asset access remains authenticated and authorized by the existing contract. Persona priority does not weaken those boundaries or make accessibility optional.

## Relationships and Priority

Researcher, Student, and Casual Reader share the same paper-detail integration and secure delivery paths. They differ in goals and frequency of use, not in newly invented roles or access rights. The priority ranking guides UX attention; all confirmed release stories remain mandatory. No persona requires the excluded US4.3 parameter-changing retry workflow.
