# Infrastructure Design Questions — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests (embedded library; no new infrastructure). Inputs: [security design](../nfr-design/security-design.md), [logical components](../nfr-design/logical-components.md), [functional spec](../functional-design/functional-spec.md).
Engine-resolved artifact set for a library unit: the CI/CD pipeline design and traceability (no deployment/services/monitoring documents — U5 adds no infrastructure).

## Q1. How does the U5 contribution enter CI/CD and release?

A. Inherits the existing pipeline: the module's backend tests join the existing backend test invocation and coverage gates; the UI contribution joins the existing frontend checks; nothing new is built, deployed or provisioned — U5 ships inside the shared application release (one PR to develop per CONVENTIONS.md); rollback is reverting the release; no new secrets or environment configuration (U5 stores no credentials)
B. A different pipeline arrangement (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Q1: U5 inherits the existing CI/CD and release: module tests join the existing invocations and gates; nothing new is built or provisioned; it ships in the shared application release through one PR to develop; rollback is reverting the release; no new secrets.

- Looks correct
- Request changes

[Answer]: Looks correct
