# Code Generation Plan Approval

AI-DLC writes this file when it asks you to approve the plan. To answer here
instead of in chat, write your answer after `[Answer]:` and say done.

## Plan Approval

Approve the code plan for u6-approved-export?

- Builds: the ApprovedExport module and everything it needs. That is schema `export`, the repository, sealed-token custody, the render policy, a Notion adapter (pinned `notion-client` SDK behind a gu...
- Touches: U2's keyring (moved onto a shared custody helper, behaviour unchanged) and its lifecycle projection (A8). The shared C09 contract (A1–A7, A9, A10, A6 extension, as an additive minor releas...
- Tests: five to eight tests per component across the database, repository, component, integration and operations layers. Shared contract tests, Vitest component tests, and browser journeys with keyb...

Full plan: aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u6-approved-export/code-generation/code-generation-plan.md
Test instructions: aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u6-approved-export/code-generation/unit-test-instructions.md

[Approval Fingerprint]: sha256:v3:8f0aa896b7e020b829eccaacf682a95347ac0c83812d40d0a16c8ca1bd3bb337
[Planned Source]: 7e0bce13351b3017390bee902422b8ae1ddbc31c407733f270064a9d13ca462a

- A. Approve Plan
- B. Request Changes
- C. I'll edit the files

[Answer]: A. Approve Plan
