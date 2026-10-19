# Decision Log — Finish the DocSuri v2 rebuild (Ideation)

Date: 2026-10-16 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild

| # | Decision | Where made | Notes |
|---|---|---|---|
| 1 | Finish the v2 rebuild as a follow-up workflow under the composed custom plan `docsuri-v2-finish` (express base, standard depth, strict guard policy, adversarial reviews) | Plan approval gate, 2026-10-16 | Chosen after the closed 261010 workflow was found to have closed early with three units unbuilt |
| 2 | Tail paperwork committed and U4 merged to develop via PR #51 before the plan started; work runs on a fresh branch off develop | Person's instruction, 2026-10-16 | Follows CONVENTIONS.md Git workflow (project.md Corrections) |
| 3 | Intent confirmed: build U5, U6, U8 and honestly redo build/CI and the seven operation stages over the complete application | Intent capture Q1 | Option A |
| 4 | Primary beneficiary: the sole maintainer — complete, comprehensible codebase with trustworthy release evidence | Intent capture Q2 | |
| 5 | Success: all eight planned units merged; complete application verified as one experience; honest tail evidence; existing suites green | Intent capture Q3 | |
| 6 | Trigger: the previous workflow closed early with three units missing and paperwork-only tail stages | Intent capture Q4 | |
| 7 | Stakeholders: the maintainer alone decides; coding agents build; no other approval roles; concise evidence at each review point | Intent capture Q5–Q6 | |
| 8 | Product boundary: no new features beyond parity; no paid services; no migration/continuity commitments beyond evidence; $0 budget | Intent capture Q7 | |
| 9 | Standing priority recorded as a durable practice: stable, smooth, integrated user experience; comprehensible, repairable codebase | Learnings, intent capture | Person's words, persisted to project.md Corrections |
| 10 | Risks acknowledged with mitigations; budget/resources confirmed ($0, free/local only) | Approval & Handoff Q2–Q3 | |
| 11 | Q4 corrected at the gate: the precise answer was to re-run the ideation groundwork — an in-flight plan reshaping was not possible, so the person chose isolated runs | Approval & Handoff gate revision, 2026-10-16 | Market research, feasibility, scope definition, team formation, rough mockups each ran as an isolated single-stage check; the main plan's stage list is unchanged |
| 12 | New release bar from the scope re-run: the finished v2 runs continuously on this machine as the real daily service on real data, and the operation-stage evidence honestly covers that real operating mode | Scope definition (isolated) Q1+Q6 | Stronger than the original finish plan's evidence bar |
| 13 | Design conventions bind: built Korean responsive workspace, WCAG 2.2 AA target; new screens (U5 topics/digests, U6 export panel, U8 assembled navigation) extend, not replace | Rough mockups (isolated) Q1–Q5 | Advisory review READY with minor polish notes carried to design stages |

## Open Items Carried Forward

- The construction verification command remains unset; presented for separate human approval before the first unit completion checkpoint verifies anything.
- R-01 (intent statement unit-label enrichment) was accepted at the intent-capture gate; later stages inherit the closed record's unit catalogue names.
- Rough-mockups advisory polish notes (accessibility note completeness, flow fidelity, status vocabulary, per-screen states) carry into the per-unit functional design stages.
