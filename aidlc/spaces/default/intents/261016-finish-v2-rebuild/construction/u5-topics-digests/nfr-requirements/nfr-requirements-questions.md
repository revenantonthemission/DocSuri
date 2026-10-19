# NFR Requirements Questions — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests (embedded library). Inputs: [functional spec](functional-design/functional-spec.md) (sibling stage dir), [rules](functional-design/rules.md), [requirements NFR1–NFR6](../../../inception/requirements-analysis/requirements.md), [technology stack](../../../../codekb/DocSuri/technology-stack.md).
This unit's NFR scope: the digest machinery touches personal data (subscriptions, reading behavior via digests), external delivery, and shared stores — security and stack decisions apply; performance/scalability/reliability/observability targets are owned by the service units this library runs inside.

## Q1. Security requirements for digest state and delivery?

A. Owner isolation on every digest read/write (NFR1, enforced per path like the built modules); consent honored for delivery (NFR2/BR4.2); no sensitive data in delivery content beyond what the account consented to; lifecycle participation writes only its own tables (BR4.3); delivery failures never leak other accounts' data; scheduled and reconciliation paths authenticate as the service, never as another user
B. A different set (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q2. Technology-stack decisions for U5?

A. No new stack choices: U5 joins the built backend as a module (Python/FastAPI patterns, SQLAlchemy-style repositories against the shared PostgreSQL, delivery through the built email capability); no new frameworks, providers or paid services; frontend contribution uses the established Next.js/SWR/CSS-Modules patterns (detail belongs to code generation, not this record)
B. A different choice (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Q1: Security set — owner isolation per path (NFR1); consent honored for delivery (NFR2); no unconsented sensitive data in delivery content; lifecycle participation writes only its own tables; no cross-account leakage from failures; service paths authenticate as the service.
- Q2: Stack — no new choices; U5 joins the built backend module patterns and shared PostgreSQL; delivery through the built email capability; no new frameworks, providers or paid services.

- Looks correct
- Request changes

[Answer]: Looks correct
