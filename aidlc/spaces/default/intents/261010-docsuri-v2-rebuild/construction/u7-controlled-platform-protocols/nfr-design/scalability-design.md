# U7 scalability design

## Scope

Maps the U7 capacity requirements (NFR8.x) to concrete design solutions. U7 is a
single-operator local executable; scaling is boundedness, not horizontal scale.

## Design solutions

| Requirement | Design solution |
|---|---|
| NFR8.1 one in-flight per target | a durable in-flight target lease acquired in the pre-effect transaction refuses a second same-target request while held |
| NFR8.2 bounded records | evidence/receipt/authority rows are size-bounded; an oversized input is refused before any effect |
| NFR8.3 bounded queue | pending requests beyond a finite bound are refused with the stable error vocabulary (no unbounded buffer, no broker dependency) |
| NFR8.4 exhaustion is truthful | disk/memory exhaustion settles `failed`/`unknown`, never `completed`/`succeeded` |
| NFR8.5 no paid fallback | local process + local PostgreSQL only; cloud-dependent protocols remain recorded dispositions |
| NFR8.6 idle decay | no background loop/watchdog after completion; the executor is spawned per effect |

## Capacity boundary

The design promises a **bounded and truthful** local operator path: work within
the measured envelope, refusal beyond the finite bound, and honest resource
reporting. Concrete bounds (queue depth, record size, resource caps) are named
values filled with the retained-inventory reconciliation and a measured
baseline; no numeric target is invented here.

## Failure domain

The bounded child process is the blast-radius unit for a single effect; the
operator process and the `PlatformControl` schema remain available across an
effect failure. One effect cannot consume the operator process's resources
unboundedly.

## Sources

- [NFR scalability requirements](../nfr-requirements/scalability-requirements.md)
- [performance-design.md](performance-design.md)
