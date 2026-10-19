# Security Design — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests. Sources: confirmed [nfr-design-questions.md](nfr-design-questions.md) (Q1–Q2), [security requirements](../nfr-requirements/security-requirements.md), [functional spec](../functional-design/functional-spec.md).

## Authorization Architecture

- **Boundary enforcement**: owner checks live at the module's service boundary on every path — list, read, write, resolve, unsubscribe — mirroring the built modules' per-path pattern (no new middleware; the checks are part of each operation, so a new path cannot silently skip them). [Q1]
- **Send-time consent gate**: the consent check sits inside the delivery step itself (not only at preparation), so a consent change between preparation and send stops the send (BR4.2, NFR2.1). [Q1]
- **Service identity for automated paths**: the scheduler hook, preparation runs, the reconciliation sweep and the lifecycle participant operate under the application's service identity with no user context; they can reach only this module's tables through its repositories (NFR1.2). [Q1]
- **Lifecycle participation**: the participant reports its own disposition and writes only its own tables (BR4.3, NFR2.2); nothing about the account is read beyond the coordinator's contract. [Q1]

## Data Protection Design

- Delivery content: only digest items and settings the account configured; assembly happens in the delivery step, so nothing is cached outside the owner's rows. [Q1]
- Failure records: plain-language category only; no tokens, secrets, or full recipient addresses (testable at the record-creation boundary). [Q1]
- No credentials exist in this module (NFR3 is N/A here): there is no secret store, key material, or token to protect. [Q1]

## Design Decisions and Rationale

| Decision | Rationale |
|---|---|
| Per-path owner checks rather than central middleware | Matches the built modules; a central hook would be a new mechanism and a single point of silent bypass [Q1] |
| Consent inside the delivery step | Only the send-time check can honor a consent change made after preparation (BR4.2) [Q1] |
| Service-identity for automated paths | Scheduled work has no user context; scoping it to this module's tables keeps blast radius minimal (NFR1.2) [Q1] |
| No audit-log additions beyond failure records | The built observability surface records module events; no new logging channel is introduced under $0 [Q1; NFR6.1] |

## Requirement Coverage

Every requirement in security-requirements.md (NFR1.1–NFR1.2, NFR2.1–NFR2.2, NFR4.1–NFR4.3, NFR5.1, NFR6.1) maps to a design element above; traceability.json records the mapping. NFR3 is N/A by requirements (no credentials in this unit).
