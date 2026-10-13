# U7 reliability requirements

## Scope and method

U7 owns durable operation recovery (NFR3) and proves its retained outcome
through real boundaries (NFR1). Durability is built on the append-only receipt
and the unknown-outcome reconciliation defined in
[functional-spec.md](../functional-design/functional-spec.md).

## Durability and recovery

| ID | Requirement | Source | Measure / closure |
|---|---|---|---|
| NFR3.1 | A receipt and its actor/target/effect binding survive process and container restart unchanged. | NFR3 | Restart fixtures read the same binding |
| NFR3.2 | An interrupted effect whose status is indeterminate settles `unknown`; it is never reported `completed` on liveness alone. | NFR3 | Interrupted-execution fixture yields unknown |
| NFR3.3 | An unknown effect is reconciled from the target without repeating execution; reconciliation records applied / not-applied. | NFR3 | Reconciliation fixtures, no duplicate effect |
| NFR3.4 | A duplicate accepted request replays the recorded receipt; same-key changed input conflicts. | NFR3 | Replay fixtures |
| NFR3.5 | The actor/operation/target/input/evidence/policy binding is recorded atomically before any effect. | NFR3 | Crash-before-effect fixture leaves no orphan effect |
| NFR3.6 | Filesystem permission failure, disk exhaustion or lost connectivity settles `failed` or `unknown`, never `completed`. | NFR3 | Failure fixtures (WF7) |
| NFR3.7 | Receipts are append-only and retained until explicitly reconciled or archived; unresolved unknowns stay operator-visible. | NFR3 | Retention/unresolved-list fixtures |

## Correctness

| ID | Requirement | Source | Measure / closure |
|---|---|---|---|
| NFR1.1 | Evidence validity (current/stale/mismatched/missing) is distinguished on every inspection and projected onto C10's `OperatorEvidence.compatibility`/`checks` (see the internal→wire mapping in tech-stack-decisions.md). | NFR1 | Four-state fixture + wire-projection check |
| NFR1.2 | Wrong actor/target, stale evidence or changed input is rejected before any effect. | NFR1 | Negative fixtures, no effect |
| NFR1.3 | Unsupported or unverified native semantics fail closed. | NFR1 | Unverified-protocol fixture refused |
| NFR1.4 | A destructive/release effect requires its explicit operator authority; design and tests use synthetic targets only. | NFR1, NFR4 | Class fixtures with synthetic targets |

## Sources

- [functional-spec.md](../functional-design/functional-spec.md) — WF4, WF6, WF7 and the state machines
- [rules.md](../functional-design/rules.md) — BR3, BR4
- [requirements.md](../../../inception/requirements-analysis/requirements.md) — NFR1, NFR3
