# Intent Capture Questions — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild (custom plan `docsuri-v2-finish` on the express base, Standard depth)

## Sources

- [desc] Initial description: "Finish thw whole v2 rebuild plan"
- [scope] Workflow-selected scope: `express`.
- [memory:M1] `aidlc/spaces/default/memory/project.md#Corrections`: "The budget should be $0. Only use free or local stacks."

## Q1. What problem is this work solving?

Context: the previous v2 rebuild workflow closed early — units U1 (paper journey), U7 (operator protocols), U2 (account controls), U3 (paper & corpus) and U4 (research & novelty) were built, but U5 (topics & digests), U6 (approved export) and U8 (complete service integration) were never built, and the build/CI and operation stages after U4 ran as paperwork about U4 only.

A. Complete the v2 rebuild as planned: build the three missing units (U5, U6, U8) and redo build/CI and the seven operation stages honestly over the finished application
B. Only build the three missing units; leave the existing build/CI and operation records as they are
C. Go beyond the recorded plan with additional work (describe under Other)
D. Not yet defined — treat this as open exploration

X. Other (please specify)

[Answer]: A

## Q2. Who benefits from finishing this, and what pain does it remove?

A. You, the sole maintainer — a complete, comprehensible codebase where every planned v2 capability actually exists and the release evidence can be trusted
B. DocSuri's end users (researchers and engineers who find, understand, save and revisit papers) — they get the finished capabilities
C. Both you as maintainer and the end users, in that order of priority
D. Not identified — no specific beneficiary in mind

X. Other (please specify)

[Answer]: A

## Q3. What does success look like for this work?

A. All eight planned units built and merged to develop; the complete application verified as one experience; honest build/CI/operation evidence over that whole application; existing test suites stay green
B. Same as A, plus agreed numeric quality targets (responsiveness, coverage) measured and met
C. Just the three missing units merged to develop; evidence quality is secondary
D. Not yet defined

X. Other (please specify)

[Answer]: A

## Q4. What triggered this work now?

A. The previous workflow closed early with three units missing and paperwork-only tail stages — it should be finished properly before the service is used
B. An external deadline or commitment
C. A change in priorities or resources
D. None — no particular trigger

X. Other (please specify)

[Answer]: A

## Q5. Who are the key stakeholders, and what does each care about?

A. You alone: sole scope and priority approver and the one human maintainer; coding agents do the work; there are no other approval roles
B. Others are involved too (name them and what they care about under Other)
C. Not applicable
D. Not identified

X. Other (please specify)

[Answer]: A

## Q6. Who decides scope and priority, and how should progress be communicated?

A. You decide scope and priority; concise progress with clear evidence, tradeoffs and unresolved items at each review point (as in the previous workflow)
B. You decide scope and priority; no special cadence — just the approval gates
C. Someone else also influences scope (describe under Other)
D. Not yet defined

X. Other (please specify)

[Answer]: A

## Q7. What should this finished v2 release NOT include?

Context: the workflow scope is already chosen; this question is about the product boundary of the finished v2 release. The recorded constraints so far: retain all current capabilities, defer new feature expansion, and keep the budget at $0 (free or local stacks only).

A. No new product features beyond current capability parity; no paid services, subscriptions or billable APIs; no data-migration or continuity commitments beyond what the evidence supports
B. Only the $0/no-paid-services rule; feature expansion decisions stay open
C. A different or additional boundary (describe under Other)
D. Not applicable — nothing to exclude

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Q1: Complete the v2 rebuild as planned — build the three missing units (U5 topics & digests, U6 approved export, U8 complete service integration) and redo build/CI and the seven operation stages honestly over the finished application.
- Q2: You, the sole maintainer, benefit first — a complete, comprehensible codebase where every planned capability exists and the release evidence can be trusted.
- Q3: Success is all eight planned units built and merged to develop, the complete application verified as one experience, honest build/CI/operation evidence over that whole application, and existing test suites staying green.
- Q4: Trigger — the previous workflow closed early with three units missing and paperwork-only tail stages; it should be finished properly before the service is used.
- Q5: You alone are the key stakeholder — sole scope and priority approver and the one human maintainer; coding agents do the work; no other approval roles.
- Q6: You decide scope and priority; concise progress with clear evidence, tradeoffs and unresolved items at each review point.
- Q7: Boundary — no new product features beyond current capability parity; no paid services, subscriptions or billable APIs; no data-migration or continuity commitments beyond what the evidence supports.

- Looks correct
- Request changes

[Answer]: Looks correct
