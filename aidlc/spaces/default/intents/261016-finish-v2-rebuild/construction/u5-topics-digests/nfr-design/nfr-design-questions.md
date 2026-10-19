# NFR Design Questions — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests (embedded library). Inputs: [security requirements](../nfr-requirements/security-requirements.md), [tech stack decisions](../nfr-requirements/tech-stack-decisions.md), [functional spec](../functional-design/functional-spec.md).
This unit's design scope: security approach and logical components (performance/scalability/reliability/observability designs are owned by the service units).

## Q1. Security design approach for the digest machinery?

A. Enforce owner checks at the module's service boundary on every path (the built modules' pattern); the consent gate is re-checked at send time inside the delivery step; scheduled/reconciliation/lifecycle paths run under the service's own identity, never a user context; the lifecycle participant writes only its own tables; no new security middleware, no credentials stored (nothing to protect beyond account references)
B. A different approach (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q2. Logical components and failure domains for U5?

A. One failure domain inside the existing application process: a scheduler hook (existing worker entry), a preparation service (selection + run creation), a delivery client (built email capability), a reconciliation sweep, a lifecycle participant, and the module's repositories — no separate service or store; blast radius: a digest failure degrades digest sends only (other modules unaffected); shared resources: the shared PostgreSQL and the built email path
B. A different decomposition (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Q1: Security design — owner checks at the module's service boundary on every path; consent re-checked at send time; scheduled/reconciliation/lifecycle paths under the service's own identity; lifecycle participant writes only its own tables; no new middleware, no stored credentials.
- Q2: Logical components — one failure domain inside the existing application process (scheduler hook, preparation service, delivery client, reconciliation sweep, lifecycle participant, repositories); no new service or store; blast radius limited to digest sends.

- Looks correct
- Request changes

[Answer]: Looks correct
