# U7 observability design

## Scope

Maps the U7 observability requirements (NFR9.x, NFR6.1) to concrete design
solutions. U7's primary observable artifact is the durable receipt; there is no
telemetry vendor and no always-on exporter.

## Design solutions

| Requirement | Design solution |
|---|---|
| NFR9.1 receipt as evidence | every operation writes an `OperationReceipt` with the actor/operation/target/input/evidence binding, outcome and reconciliation state; exposed via C10's `OperatorReceipt` through the internal→wire mapping |
| NFR9.2 truthful classification | evidence/inspection results carry an explicit `current`/`stale`/`mismatched`/`missing` label; unknown/stale values are never presented as healthy |
| NFR9.3 observation path | U8 pulls evidence/receipts via C10; push observations into the ops view use C11 `recordObservation` and require U7 provider registration — a recorded C10/C11 coordination item; emission failure never changes an outcome and is bounded |
| NFR9.4 correlation | a user-visible failure links to its receipt via a safe correlation identifier; no credentials/private text |
| NFR9.5 retention/access | receipt/log retention and access limits are documented; logs exclude secrets and unnecessary private input |
| NFR6.1 accessible text feedback | the operator CLI prints a distinct, plain-text result for each terminal state |

## Metrics and SLI/SLO posture

No numeric SLI/SLO is selected. The observability guarantee is **classification
correctness** (observed vs unknown vs stale vs missing) and bounded telemetry
behaviour. Metrics are derived from receipt counts and outcome categories when a
measured baseline exists; adding a vendor or numeric target is out of scope for
the $0 budget.

## Correlation and privacy

- Correlation identifiers are opaque and safe; the receipt is the join key.
- Structured logging emits event names and safe references only; observation
  payloads exclude credentials and private source text.

## Sources

- [NFR observability requirements](../nfr-requirements/observability-requirements.md)
- [rules.md](../functional-design/rules.md) — BR6.3
- [contract-summary.md](../../../inception/contract-design/contract-summary.md) — C10/C11
