# U7 scalability and capacity requirements

## Scope and method

U7 is a single-operator local executable; it has no multi-tenant scaling need.
Its capacity obligation (NFR8) is that normal and failure operation fit the
available local resources with bounded work and no paid fallback.

## Requirements

| ID | Requirement | Source | Measure / closure |
|---|---|---|---|
| NFR8.1 | At most one in-flight effect per target under an exclusive target lock; concurrent requests for the same target are serialized or refused, never run in parallel. | NFR8 | Concurrency fixtures: second request waits/refuses, no double effect |
| NFR8.2 | Evidence, receipts and authority records are bounded in size; an oversized input is refused before any effect rather than buffered without limit. | NFR8 | Oversized-input fixture refused |
| NFR8.3 | Queueing is bounded: pending requests beyond the finite bound are refused with the stable error vocabulary, not silently dropped or unbounded-buffered. | NFR8 | Overload fixture returns bounded refusal |
| NFR8.4 | Resource exhaustion (disk full, memory pressure) cannot cause partial success to be reported as `completed`; it settles `failed`/`unknown` (WF7). | NFR8, NFR3 | Exhaustion fixture asserts truthful outcome |
| NFR8.5 | No path activates a paid or cloud service; the $0/local budget is preserved. Cloud-dependent legacy protocols remain recorded dispositions, not runtime dependencies. | NFR8 | Configured/local-only assertion; no paid adapter invoked |
| NFR8.6 | Work decays to zero when idle: a completed operation leaves no background loop, watcher, or polling process consuming resources. | NFR8 | Idle assertion after an operation |

## Capacity boundary

U7 does not promise a numeric concurrency or volume target; its capacity
requirement is **bounded and truthful** — the local operator path operates
within the measured envelope, refuses work beyond the finite bound, and reports
resource limits honestly. Numeric envelopes are recorded after a measured
baseline and agreed by the human.

## Sources

- [functional-spec.md](../functional-design/functional-spec.md) — WF2/WF7, one-effect-per-target
- [requirements.md](../../../inception/requirements-analysis/requirements.md) — NFR8
