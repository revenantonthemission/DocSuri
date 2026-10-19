# Delivery Planning Questions — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild. Inputs: [requirements](../requirements-analysis/requirements.md), [unit catalogue](../units-generation/unit-of-work.md), [dependency DAG](../units-generation/unit-of-work-dependency.md), [story map](../units-generation/unit-of-work-story-map.md).
A **Bolt** here means one build pass over a piece of work, ending in something that runs and merges.

## Q1. What should we build first?

A. Risk-first, as confirmed in scope definition: U5 (topics & digests — scheduling, consent and delivery reconciliation carry the most behavior), then U6 (approved export), then U8 (assembly and the honest tail) — matching the approved catalogue's B06 → B07 → B08 numbering for continuity
B. A different order (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q2. Should the work be scored and ranked with a formal model (WSJF-style: value + urgency ÷ size)?

A. No — three units with a fixed dependency shape and no deadline; a qualitative risk-first rationale is recorded instead
B. Yes — score them (weights under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q3. How big should one Bolt be?

A. One unit per Bolt — three build passes (U5, U6, U8), each ending in a runnable, merged increment, as in the approved plan
B. Bundle related units (say how under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q4. Serial or parallel?

A. Serial — one Bolt at a time (the workflow's recorded execution setting; U5 and U6 could run concurrently but one reviewer and one session make serial the honest choice)
B. Parallel (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q5. Is anything outside this session going to hold us up?

A. The known externals: Notion token configuration and sustainable terms (blocks U6 verification), content-source licensing terms (blocks U5 content selection), local model availability (blocks U5 digest generation and U8 verification), and the human-approved construction verification command (blocks every unit checkpoint)
B. Something else too (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q6. What worries you most, so we tackle it early?

A. U8's assembly spanning every service — mitigated by verifying each unit through real boundaries first and keeping U8 last with cumulative verification
B. A different worry (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q7. The construction verification command — propose one now or defer again?

Context: no unit checkpoint may verify until a human approves the exact command. U5's runnable check doesn't exist until U5 is built; the built units' checks (verify_docsuri_u1/u3/u4.py) verify finished work, not the new units.

A. Defer again — leave it unset; the first unit completion checkpoint will present the exact command for approval once U5's real check exists (same pattern as the approved plan)
B. Propose a candidate now (say which under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Q1: Risk-first build order — U5 (topics & digests), then U6 (approved export), then U8 (assembly + honest tail), numbered B06 → B07 → B08 for continuity with the approved plan.
- Q2: No formal WSJF scoring — a qualitative risk-first rationale is recorded instead.
- Q3: One unit per Bolt — three build passes, each ending in a runnable, merged increment.
- Q4: Serial execution — one Bolt at a time.
- Q5: Known externals — Notion terms (U6), content licensing (U5), local model availability (U5/U8), and the human-approved verification command (all checkpoints).
- Q6: Biggest worry is U8's assembly spanning every service — mitigated by per-unit real-boundary verification first and cumulative verification last.
- Q7: Verification command deferred again — the first unit checkpoint presents the exact command for approval.

- Looks correct
- Request changes

[Answer]: Looks correct
