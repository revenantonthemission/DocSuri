# DocSuri v2 — U7 NFR Requirements questions

Date: 2026-10-13 (Asia/Seoul). Basis: the U7
[functional specification](../functional-design/functional-spec.md) and
[rules](../functional-design/rules.md), the
[requirements](../../../inception/requirements-analysis/requirements.md),
contract C10
([contract-summary.md](../../../inception/contract-design/contract-summary.md))
and the reverse-engineered
[technology stack](../../../../codekb/DocSuri/technology-stack.md).

## Context and established answers

| Topic | Established answer or evidence | NFR consequence |
|---|---|---|
| Unit behaviour | Independent controlled operator executable: platform evidence, target-scoped authority, precondition-checked effects, durable receipts, unknown-outcome reconciliation (functional-spec.md) | NFRs must preserve fail-closed behaviour, durable receipts and reconciliation, not invent throughput |
| Budget | $0, free or local only (project memory corrections) | No paid telemetry/queue/store; local persistence and local transport only |
| Numeric targets | Requirements: no numeric targets until a measured baseline; the user agrees numeric targets after baseline (requirements.md; delivery-planning) | Do not invent latency/throughput/availability numbers; record qualitative bounds and mark numbers to-be-agreed |
| Technology available | Python 3.13 stack; existing local PostgreSQL 16 compose; existing operations/local-transport work from U1; no provisioned infrastructure (technology-stack.md) | Tech-stack decisions should reuse the proven local Python/PostgreSQL path; AWS CDK-era deployment is a cloud-dependent disposition, not a U7 runtime |
| C10 invariants | local stdin/stdout JSON transport; retained inventory vocabulary; no arbitrary command/path/shell; receipts bind across restart; changed-input replay conflicts (contract-summary.md) | Reliability/security NFRs formalize these as measurable, checkable bounds |

## Proposed NFR coverage

Produce, under `construction/u7-controlled-platform-protocols/nfr-requirements/`:
`performance-requirements.md`, `security-requirements.md`,
`scalability-requirements.md`, `reliability-requirements.md`,
`observability-requirements.md`, `tech-stack-decisions.md` and
`traceability.json`. Detailed requirements inherit their inception NFR ID with a
sub-number (for example `NFR4.3`).

## Q1 — Numeric targets now or baseline-deferred

The requirements deliberately defer numeric service targets to a measured baseline, and the budget forbids invented figures. Before writing NFR targets, this must be confirmed.

- A. Defer all numeric targets (latency, throughput, availability percentages) to a measured baseline; this stage records qualitative, checkable bounds (finite, fail-closed, bounded) and marks every number as to-be-agreed after measurement.
- B. Set proposed baseline numeric targets now for the human to adjust.
- C. Defer everything numeric, including qualitative bounds; leave the NFR files minimal.
- X. Other (please specify)

[Answer]: A

## Q2 — Controlled-operation execution limits

The functional design fixes an exclusive target lock and one effect per accepted operation but sets no execution timeout. The NFR requirements need a bounded posture.

- A. At most one in-flight effect per target (exclusive target lock); a finite, per-protocol execution deadline; no automatic retry (a replay returns the recorded receipt and an unknown is reconciled, never re-run).
- B. Allow parallel operations on the same target with per-operation deadlines.
- C. Leave deadlines and concurrency to be decided per protocol during implementation.
- X. Other (please specify)

[Answer]: A

## Q3 — Evidence validity windows

Evidence carries a finite maximum age per protocol (BR1.2), but the default when a protocol does not declare one is open.

- A. Every admitted protocol MUST declare its explicit finite `maxAge`; a protocol with no declared window is not admitted (no implicit default).
- B. A single global default window applies when a protocol does not declare one.
- C. Validity windows are decided per protocol at implementation with no admission rule here.
- X. Other (please specify)

[Answer]: A

## Q4 — Receipt retention and unresolved work

Receipts are append-only and an unknown effect stays operator-visible until reconciled (BR4.7), but the retention duration is open.

- A. Retain receipts until an operator explicitly reconciles or archives them; an unresolved unknown can never be silently removed, and nothing is auto-deleted by age.
- B. Bounded retention (a finite window) with automatic archival after it, provided unresolved unknowns are reported before removal.
- C. Retention is decided by operations policy later; this stage records only the append-only rule.
- X. Other (please specify)

[Answer]: A

## Q5 — Local durable store for U7

U7 needs durable receipts, authority grants and evidence. Two local options are consistent with the $0 budget.

- A. Reuse the application's local PostgreSQL with a dedicated PlatformControl schema and its own bounded role, matching the owner-isolation pattern already proven in U1.
- B. Use a separate embedded local store (for example a dedicated SQLite file) owned by the operator executable only.
- C. Decide at implementation; this stage records only the durability requirement.
- X. Other (please specify)

[Answer]: A

## Q6 — Operational observations

U8's operations view consumes privacy-safe evidence. Whether U7 also emits operation observations affects the observability requirements.

- A. Emit bounded, privacy-safe operation/outcome observations through the same observation path U1 uses (for U8's ops view) in addition to the durable local receipts; observation failure never changes an operation outcome.
- B. Keep durable local receipts only; emit no observations.
- C. Emit observations only when an operator opts in per run.
- X. Other (please specify)

[Answer]: A

## Q7 — Authority provisioning mechanism

BR2.6 requires grants to be minted only through the controlled local procedure. The exact mechanism is open.

- A. The controlled local procedure is a subcommand of the U7 executable that verifies the invoking local OS user and writes or revokes the grant in the local store, relying on normal file ownership/permissions with no extra elevation.
- B. Provisioning requires OS-level elevation (for example `sudo`) for every grant change.
- C. Provisioning is an interactive confirmation at each execution instead of a stored grant.
- X. Other (please specify)

[Answer]: A

## Assumptions & Open Questions

- Assumption: numeric service targets remain deferred to a measured baseline per the requirements; this stage records checkable qualitative bounds only.
- Assumption: the U7 runtime is Python, reusing the shared project code and the proven local transport; the AWS CDK-era deployment remains a recorded cloud-dependent disposition from functional design.
- Open: the concrete per-protocol execution deadlines, evidence windows and the receipt retention duration are recorded as named values to be filled with the protocol inventory; Q2/Q3/Q4 fix their governance.
- Open: if Q5 chooses the shared PostgreSQL, schema/role provisioning details pass to infrastructure design.

## Sources

- [functional-spec.md](../functional-design/functional-spec.md) and [rules.md](../functional-design/rules.md) — U7 behaviour and rules
- [requirements.md](../../../inception/requirements-analysis/requirements.md) — FR20/NFR context and the no-invented-targets rule
- [contract-summary.md](../../../inception/contract-design/contract-summary.md) — C10 invariants
- [technology-stack.md](../../../../../codekb/DocSuri/technology-stack.md) — available local technology
- [project memory](../../../../../memory/project.md) — $0 budget and corrections

## Consolidated Summary Confirmation

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
