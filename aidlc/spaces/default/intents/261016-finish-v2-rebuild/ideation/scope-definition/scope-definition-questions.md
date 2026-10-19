# Scope Definition Questions — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Isolated run: feeds the approval-handoff brief. Inputs: [intent statement](../intent-capture/intent-statement.md), [feasibility assessment](../feasibility/feasibility-assessment.md), [constraint register](../feasibility/constraint-register.md).

## Q1. What is the minimum scope that delivers value for this finish release?

A. The three missing units (U5 topics & digests, U6 approved export, U8 complete integration) plus the honest tail redo — the full approved plan; nothing smaller satisfies "finish the whole v2 rebuild plan"
B. Something smaller (say what under Other — note the intent statement rules out a reduced-feature release)
C. Not applicable

X. Other (please specify)

[Answer]: X. A, and the full service should be able to use in production level.

## Q2. Which capabilities are must-have vs nice-to-have in the finished release?

A. Must-have: full parity with all eight approved units' capabilities (including topics & digests, approved export, and the integrated whole). Nice-to-have: none — no new features are in scope
B. A different split (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q3. What dependencies govern the build order?

A. The approved dependency graph: U5 and U6 need U1–U3 (U6 also needs U4); U8 needs everything; U4 must merge before U6 and U8 verify against it
B. A different order (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q4. What sequencing preference applies?

A. Risk-first: prove each remaining unit through its real verification, then assemble U8 and redo the tail over the complete application
B. Value-first (say what ships first under Other)
C. Dependency-first strictly by graph order

X. Other (please specify)

[Answer]: A

## Q5. Are there hard deadlines tied to specific capabilities?

A. None — no fixed deadline exists
B. There is one (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q6. Follow-up to Q1: what does "usable at production level" mean for the finished v2?

Context: you added to Q1 that "the full service should be able to use in production level." This sets the release bar, so it needs a precise meaning.

A. Usable as my real daily service: it runs continuously on this machine and works with real accounts and real papers — synthetic verification realms remain the test method, but the finished service must operate on real data
B. Same as A, and the operation-stage evidence (deployment, observability, incident runbooks, performance) must honestly cover that real operating mode
C. It only means the tail evidence stages must be real — no stronger runtime requirement than the plan already has
D. Something else (describe under Other)

X. Other (please specify)

[Answer]: B
