# U7 performance design

## Scope

Maps the U7 performance/capacity requirements (NFR2.x, NFR8.1) to concrete design
solutions. U7 is a local single-operator executable: the design optimizes for
boundedness and truthful degradation, not throughput. Numeric targets remain
baseline-deferred.

## Design solutions

| Requirement | Design solution |
|---|---|
| NFR2.1 evidence inspection bounded | `evidence-producer` computes evidence on demand and returns within a per-protocol bound; an exceedance returns a labelled failure, never a silent wait |
| NFR2.2 execution deadline | each effect runs in a `bounded-executor` child process with a per-protocol deadline and a resource cap; exceeding the deadline terminates the child and settles the operation `unknown` for reconciliation |
| NFR2.3 bounded reads | `readReceipt` is a bounded store read; it never triggers an effect |
| NFR2.4 no infinite wait / no repeated effect | one in-flight effect per target (target row lock); no automatic retry; a replay returns the recorded receipt |
| NFR2.5 distinct feedback | each terminal state returns a distinct, stable text result (loading/refusal/failure/completion/unresolved) |
| NFR8.1 one in-flight effect | enforced by a durable in-flight **target lease** acquired in the pre-effect transaction; a second same-target request is refused while the lease is held (see security-design.md); the lock is not a transaction held open across the effect |

## Performance budgets

- Per-protocol execution deadline and evidence-inspection bound are **declared per
  admitted protocol** (no implicit default); the values are filled with the
  retained-inventory reconciliation.
- No unbounded loop, queue drain, or polling cycle runs after an operation
  completes (NFR8.6).
- The child-process boundary keeps a slow or hanging native effect from blocking
  the operator process or the guarded transaction's logical checks.

## Sources

- [NFR performance requirements](../nfr-requirements/performance-requirements.md)
- [functional-spec.md](../functional-design/functional-spec.md) — WF2/WF7
