# U7 observability requirements

## Scope and method

U7 emits truthful, privacy-aware operator evidence (NFR9) and accessible text
feedback (NFR6). Its primary observable artifact is the durable receipt; it also
emits bounded domain observations for the operations view (for U8) without
making telemetry a dependency.

## Requirements

| ID | Requirement | Source | Measure / closure |
|---|---|---|---|
| NFR9.1 | Every operation records a durable receipt with actor/operation/target/input/evidence binding, outcome and reconciliation state; it is exposed through C10's `OperatorReceipt` with the internal state projecting onto the wire `outcome` and `reconciliationEvidence[]` (see the mapping in tech-stack-decisions.md). | NFR9 | Receipt fixtures + wire-projection check |
| NFR9.2 | Observations and feedback distinguish **observed**, **unknown**, **stale** and **missing**; never present an unknown or stale value as healthy. | NFR9 | Labelling fixtures |
| NFR9.3 | U7 exposes operation outcomes through its C10 read interface (`inspectEvidence`, `readReceipt`); any push of bounded, privacy-safe operation observations into the operations view uses the operations owner's existing observation contract and requires U7 to be a registered provider — a recorded C10/C11 contract-coordination item. Observation emission or its failure never changes an operation outcome and is bounded. | NFR9 | Sink-failure fixture: outcome unchanged, bounded behaviour; coordination item recorded |
| NFR9.4 | A user-visible failure links to its receipt/operation using a safe correlation identifier. | NFR9 | Correlation fixture end to end |
| NFR9.5 | Logs/metrics carry documented retention/access limits and omit secrets and unnecessary private input. | NFR9, NFR5 | Content fixtures |
| NFR6.1 | The operator surface provides accessible text feedback for each terminal state (loading, refusal, failure, completion, unresolved), understandable without a GUI. | NFR6 | Text-feedback fixture; the operator CLI is the accessible surface |

## SLI/SLO posture

No numeric SLI/SLO is selected. The observability requirement is correctness of
classification (observed vs unknown vs stale vs missing) and bounded telemetry
behaviour; numeric indicators are added after a measured baseline and human
agreement. This aligns with NFR9's "no particular telemetry vendor is selected".

## Sources

- [functional-spec.md](../functional-design/functional-spec.md) — WF4, WF7, WF8
- [rules.md](../functional-design/rules.md) — BR6.3
- [requirements.md](../../../inception/requirements-analysis/requirements.md) — NFR6, NFR9
