# Security Requirements — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests. Sources: confirmed [nfr-requirements-questions.md](nfr-requirements-questions.md) (Q1–Q2), inception [requirements NFR1–NFR6](../../../inception/requirements-analysis/requirements.md), [functional spec](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md).

## Authentication and Authorization

- **NFR1.1** — Owner isolation on every digest read and write path: lists, settings reads/writes, run status, resolution actions and unsubscribe all check the caller's right to the topic on every access (mirrors the built modules' per-path owner checks; BR5.1). [Q1]
- **NFR1.2** — Scheduled preparation, delivery, reconciliation sweeps and lifecycle participation authenticate as the service itself, never as another user; no scheduled path can read or write another owner's data. [Q1]
- **NFR2.1** — Consent gates delivery: the effective consent is re-checked at send time; a consent change recorded before the send stops it (BR4.2), and no digest content beyond what the account consented to is delivered. [Q1]
- **NFR2.2** — Account-lifecycle participation (BR4.3) writes only this module's tables and reports its own disposition; it never reads or writes account records beyond the coordinator's contract. [Q1]

## Data Protection

- Delivery content carries only the digest items and settings the account itself configured; failure records use plain-language categories without secrets, tokens or full recipient addresses. [Q1]
- The topics view renders only the owner's own state; cross-account leakage from failure paths is excluded by the owner checks above. [Q1]

## Reliability and Idempotency (security-adjacent)

- **NFR4.1** — Digest preparation is idempotent per (topic, window) (BR2.4): repeated schedule ticks cannot double-send. [Q1]
- **NFR4.2** — A topic has at most one in-flight send (BR3.1); unknown outcomes reconcile before any further effect (BR3.2), so uncertainty never becomes a duplicate delivery. [Q1]
- **NFR4.3** — Restart recovery moves orphaned `sending` runs into reconciliation rather than leaving a silent permanent block (BR3.4). [Q1]

## Compliance Notes

- Personal-data scope: subscriptions, settings, delivery history. No PCI/HIPAA/SOC2 scope (constraint register C-04). Consent handling rides the built account consent records. [Q1]
- **NFR5.1** — The new screens (topics list, settings form, resolve control) keep the established Korean labels, responsive behavior and WCAG 2.2 AA target: keyboard-operable, visible focus, polite live-region status, contrast. [Q1]
- **NFR6.1** — $0 constraint: no capability here introduces a paid dependency; delivery uses the built free/local email path. [Q2]

## Out of Scope for This Unit

- Owner token protection (NFR3) does not apply: U5 stores no external-service credentials; the Notion token belongs to U6. Recorded as N/A in traceability. [Q1]
