# Units Generation Questions — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild. Inputs: [requirements](requirements.md) (this workflow, FR1–FR4), the closed record's approved [unit catalogue](../../../261010-docsuri-v2-rebuild/inception/units-generation/unit-of-work.md) (context, rechecked) and [component catalogue](../../../261010-docsuri-v2-rebuild/inception/domain-design/components.md) (context, rechecked).

## Q1. Unit boundary strategy for this finish workflow?

A. Re-emit exactly the three remaining approved units — U5 (u5-topics-digests), U6 (u6-approved-export), U8 (u8-service-operations-integration) — keeping the five built units as satisfied context, not re-declared work
B. A different decomposition (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q2. Unit granularity and kinds?

A. As approved: U5 and U6 are embedded libraries (business modules with their UI contributions), U8 is the shared application assembly (service)
B. A different split (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q3. How should the dependency DAG treat the built units?

A. Declare only the three new units in the DAG block: U8 depends on U5 and U6; U5 and U6 carry no in-workflow dependencies because their prerequisites (U1–U4, U7) are already built and merged to develop — recorded in prose as satisfied prerequisites, not re-declared edges
B. Re-declare the full eight-unit graph (risks re-running built units)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q4. Which integration points bind the new units?

A. U5 and U6 register as account-lifecycle participants (withdrawal stops digests; export authority dies with the account); U6 consumes U4's immutable artifact revision identity for approval binding; U8 consumes every unit's contribution and verifies the assembled whole
B. A different set (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q5. Deployment model?

A. Unchanged from the approved catalogue: one shared application (browser/server/store/worker with U5/U6 embedded) plus the separately controlled operator executable already built as U7
B. A different model (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Q1: Re-emit exactly the three remaining approved units — U5 (u5-topics-digests), U6 (u6-approved-export), U8 (u8-service-operations-integration); the five built units are satisfied context, not re-declared work.
- Q2: U5 and U6 are embedded libraries (business modules with UI contributions); U8 is the shared application assembly (service).
- Q3: The DAG block declares only the three new units — U8 depends on U5 and U6; built-unit prerequisites (U1–U4, U7) are recorded in prose as satisfied.
- Q4: U5 and U6 register as account-lifecycle participants; U6 consumes U4's immutable artifact revision identity; U8 consumes and verifies everything.
- Q5: Deployment model unchanged: one shared application plus the separately controlled operator executable (U7).

- Looks correct
- Request changes

[Answer]: Looks correct
