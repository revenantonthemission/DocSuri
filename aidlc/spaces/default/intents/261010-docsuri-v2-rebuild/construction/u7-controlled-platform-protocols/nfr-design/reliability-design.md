# U7 reliability design

## Scope

Maps the U7 durability/correctness requirements (NFR3.x, NFR1.x) to concrete
design solutions. Durability rests on the append-only receipt and the
unknown-outcome reconciliation defined in the functional design.

## Resilience patterns

| Pattern | Design solution | Requirement |
|---|---|---|
| Atomic binding before effect | one guarded transaction acquires a durable target lease and writes the operation binding + receipt stub, then commits **before** the effect; a crash before the effect leaves no orphan effect (the lease is reclaimed as unknown) | NFR3.5 |
| Crash containment | the effect runs in a `bounded-executor` child; a child crash/hang is captured by exit status + the typed settlement channel and settles `unknown` (deadline) or `failed` | NFR2.2, NFR3.2 |
| Durable, append-only receipt | `OperationReceipt` rows in the `PlatformControl` schema are append-only; binding survives process/container restart | NFR3.1, NFR5.4 |
| Reconciliation, no re-execution | an `unknown` outcome is reconciled from the target (on demand at read + an operator `reconcile` subcommand); reconciliation records applied/not-applied without repeating the effect | NFR3.3 |
| Fail-closed | unsupported/unverified native semantics and failed precondition re-checks yield no effect | NFR1.3, NFR3.5 |
| Truthful failure | permission/disk/connectivity failure settles `failed`/`unknown`, never `completed`/`succeeded`; the wire outcome is never `succeeded` on liveness alone | NFR3.6 |
| Idempotent replay | same-key same-input replay returns the recorded receipt; same-key changed input conflicts | NFR3.4 |

## Settlement channel and stale in-flight recovery

- **Settlement channel.** The `bounded-executor` child writes a **bounded, typed
  result** (structured JSON: effect applied / not applied / unknown plus effect
  evidence refs) to a pipe or staging file that the parent reads; the parent then
  settles the receipt — `completed`/wire `succeeded` only with effect evidence,
  otherwise `failed` or `unknown`. Exit status alone is never treated as proof of
  a successful effect.
- **Stale in-flight recovery.** A crash between the pre-effect binding commit and
  the effect leaves the operation in-flight. A bounded staleness check (on startup
  and on receipt read) promotes an over-deadline in-flight operation to `unknown`
  and reclaims its target lease — **never** to `succeeded` or `failed` on liveness
  alone. `receipt-reconciler` (WF4) then resolves the `unknown` from the target
  without re-execution.

## No automatic retry

There is deliberately **no retry library, circuit breaker, or backoff loop**:
retrying a native effect is unsafe. Recovery is the receipt + reconciliation path;
an operator may re-issue an operation with a new key. This keeps the design simple
and prevents duplicate effects.

## Health and recovery

- Liveness of the operator process is separate from operation outcome truth; a
  green process check never implies an effect succeeded.
- Restart reads the same receipt binding; the unresolved-unknown list is
  operator-visible and is never silently cleared (NFR3.7).
- Retention: receipts are retained until explicitly reconciled or archived;
  nothing is auto-deleted by age.

## Sources

- [NFR reliability requirements](../nfr-requirements/reliability-requirements.md)
- [functional-spec.md](../functional-design/functional-spec.md) — WF4/WF6/WF7 and state machines
