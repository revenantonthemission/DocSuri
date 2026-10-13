# DocSuri v2 — U7 NFR Design questions

Date: 2026-10-13 (Asia/Seoul). Basis: the U7 NFR requirements
([performance](../nfr-requirements/performance-requirements.md), [security](../nfr-requirements/security-requirements.md),
[scalability](../nfr-requirements/scalability-requirements.md), [reliability](../nfr-requirements/reliability-requirements.md),
[observability](../nfr-requirements/observability-requirements.md), [tech stack](../nfr-requirements/tech-stack-decisions.md)),
the [functional specification](../functional-design/functional-spec.md) and contract C10
([contract-summary.md](../../../inception/contract-design/contract-summary.md)).

## Context and established answers

| Topic | Established | Design consequence |
|---|---|---|
| Execution posture | One in-flight effect per target, finite deadline, no auto-retry; unknown reconciled (NFR2.2, NFR8.1) | Design a bounded executor and a reconciliation path, not a retry/queue system |
| Store | Shared local PostgreSQL with a dedicated PlatformControl schema/role (NFR tech stack; Q5) | Receipts/authority/evidence persist in the shared local store with owner isolation |
| Authority | Local OS identity + target-scoped grants; app admin never an operator; destructive-release separate (NFR4) | Enforce authority as a data-level guard plus a local provisioning subcommand |
| Privacy | No credentials/private text in evidence, receipts, logs (NFR5) | Structured, field-validated records; safe correlation only |
| Budget | $0/local; no paid telemetry; no AWS runtime (NFR8.5) | Local process + local store; no managed queue/broker |
| Contract | C10 local JSON envelope with an internal→wire mapping (NFR10) | U8 reads evidence/receipts; observations stay a recorded coordination item |

## Proposed design work

Produce `performance-design.md`, `security-design.md`, `scalability-design.md`,
`reliability-design.md`, `observability-design.md`, `logical-components.md` and
`traceability.json` mapping every `NFRx.y` to its design solution.

## Q1 — Execution isolation for the native effect

The effect runs real native filesystem/credential semantics and must be bounded (NFR2.2) and contained (NFR4.9).

- A. Run each effect in a separate bounded child process with its own deadline, resource limit and exit-status capture; a crash or hang is contained and settles `unknown`.
- B. Run the effect in-process with a thread/async deadline; simpler, but a hang is harder to contain.
- C. Decide at implementation; record only that the effect must be bounded and contained.
- X. Other (please specify)

[Answer]: A

## Q2 — Enforcement of authority and preconditions

Authority, target scope and preconditions must be re-checked atomically before the effect (NFR4.8, NFR3.5).

- A. Enforce with owner-scoped PostgreSQL guard functions/roles (the pattern proven in U1): a single transaction holds the target lock, re-checks authority/evidence, writes the receipt binding, then the effect runs; failure rolls the whole transaction back.
- B. Enforce entirely in the application layer with application-level locking; the database only stores rows.
- C. Split: application checks first, database constraint as a backstop.
- X. Other (please specify)

[Answer]: A

## Q3 — Reconciliation trigger

An unknown outcome must be reconciled from the target without re-executing (NFR3.3).

- A. Reconciliation runs on demand at a receipt read/reconcile, plus an operator `reconcile` subcommand; no always-on background reconciler.
- B. A supervised background reconciler retries reconciliation periodically until resolved.
- C. Reconciliation is manual only (operator re-runs the read command).
- X. Other (please specify)

[Answer]: A

## Q4 — Evidence production

Evidence must be current, bound and finite-lived (NFR1.1).

- A. Produce evidence on demand when `inspectEvidence` is called, persist the generation with its observation time, and never serve a superseded generation as current.
- B. Maintain a periodically refreshed evidence cache and serve the latest cached generation.
- C. Decide at implementation; record only the binding and finite-life requirements.
- X. Other (please specify)

[Answer]: A

## Q5 — Observability emission path

Push observations to the ops view need a registered provider contract (NFR9.3); pull-only works today via C10.

- A. U8 pulls U7's evidence/receipts through C10 now; record U7's registration as a C11 `recordObservation` provider as a contract-coordination item, and add push emission only when that lands.
- B. Add a new U7→U8 push observation boundary in this design (requires a contract amendment).
- C. Emit observations to a local log file only; no ops-view integration.
- X. Other (please specify)

[Answer]: A

## Assumptions & Open Questions

- Assumption: the local PostgreSQL PlatformControl schema and guard functions follow the U1 owner-isolation pattern; concrete DDL belongs to infrastructure design/code generation.
- Assumption: no paid/managed queue or broker; any queue is a bounded table with a finite bound.
- Open: the exact per-protocol deadlines and resource caps are filled with the retained-inventory reconciliation.

## Sources

- [functional-spec.md](../functional-design/functional-spec.md), [rules.md](../functional-design/rules.md)
- NFR requirement files under `../nfr-requirements/`
- [contract-summary.md](../../../inception/contract-design/contract-summary.md) — C10
- [project memory](../../../../../memory/project.md) — $0 budget

## Consolidated Summary Confirmation

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
