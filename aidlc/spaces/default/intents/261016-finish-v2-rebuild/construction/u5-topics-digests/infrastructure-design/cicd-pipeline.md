# CI/CD Pipeline — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests. Confirmed answer: [infrastructure-design-questions.md](infrastructure-design-questions.md) Q1 = A. Sources: [security design](../nfr-design/security-design.md), [logical components](../nfr-design/logical-components.md), [functional spec](../functional-design/functional-spec.md), [tech stack decisions](../nfr-requirements/tech-stack-decisions.md).

## Pipeline Integration

U5 provisions nothing: no compute, no storage, no networking, no new environment configuration. It ships inside the shared application release, and its pipeline work is exactly the module's contribution to the existing checks.

| Contribution | Where it enters | Gate it must pass |
|---|---|---|
| Backend module sources + tests | Existing backend test invocation | Coverage floor for new code; all existing backend tests stay green |
| UI contribution (topics/digests surfaces) | Existing frontend checks | Lint, typecheck, frontend tests |
| Shared types / contracts touched | Existing typecheck | Repo-wide typecheck |

## Delivery and Release

- **Delivery path**: one PR to `develop` per CONVENTIONS.md; the module merges inside the shared application build — there is no U5-specific artifact, image, or deploy step. [Q1]
- **Promotion**: inherits the established develop → main promotion; no U5-specific environment steps. [Q1]
- **Rollback**: revert the release — the module has no independently deployed component, so the application rollback procedure covers it unchanged. [Q1]

## Secrets Management

None new. U5 stores no credentials (see [security design](../nfr-design/security-design.md) — NFR3 is N/A); the delivery path uses the application's existing email capability, whose configuration already lives in the existing environment configuration. [Q1]
