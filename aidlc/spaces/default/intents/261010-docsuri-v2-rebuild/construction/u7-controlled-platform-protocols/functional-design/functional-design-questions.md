# DocSuri v2 — U7 Functional Design questions

Date: 2026-10-13 (Asia/Seoul). Basis: the approved eight-unit plan,
[unit definition](../../../inception/units-generation/unit-of-work.md),
[requirement-to-unit map](../../../inception/units-generation/unit-of-work-story-map.md),
[requirements](../../../inception/requirements-analysis/requirements.md),
[component catalogue](../../../inception/domain-design/components.md) and
[contract summary](../../../inception/contract-design/contract-summary.md).

## Context and established answers

| Topic | Established answer or evidence | Design consequence |
|---|---|---|
| Unit boundary | U7 delivers the retained operator executable with independent actor/target authority, platform evidence/compatibility, precondition validation and durable outcome receipts; it is independently executable and its graph has no application prerequisite ([unit-of-work.md](../../../inception/units-generation/unit-of-work.md#u7--controlled-platform-protocols)) | Design the operator as a standalone controlled executable over local transport; do not add dependency edges or a privileged application surface |
| Requirements | FR20 with FR20.1 (platform evidence/compatibility; bounded authenticated reads; evidence never substitutes for journey readiness) and FR20.2 (wrong actor/target, stale precondition or changed input rejected before unsafe effect; interrupted/duplicate execution recoverable; permission/disk/connectivity failure never reported as completed; destructive/release effects need explicit operator authority) ([requirements.md](../../../inception/requirements-analysis/requirements.md)) | Every rule and workflow must trace to FR20.1/FR20.2 acceptance statements |
| Owned component | `PlatformControl` owns `PlatformEvidence`, `OperatorAuthority`, `ControlledOperation`, `OperationReceipt`; no dependencies; `ServiceOperations` consumes evidence and authorized operation outcomes read-only ([components.md](../../../inception/domain-design/components.md)) | Artifacts define these four entities and the read-only evidence interface U8 consumes |
| Contract C10 | Controlled platform evidence and effects: local stdin/stdout JSON transport; operation vocabulary comes from the retained protocol inventory; no generic arbitrary command/path/shell execution; receipts preserve actor/target/effect binding across restart; replay with changed input under the same key conflicts; interrupted effect with unknown outcome is reconciled without duplicate execution; app administrator alone never grants operator privileges ([contract-summary.md](../../../inception/contract-design/contract-summary.md)) | The design formalizes C10's `inspectEvidence` / `executeControlled` / `readReceipt` semantics without re-deciding them |
| Budget | $0 — free or local stacks only ([project memory](../../../../memory/project.md) corrections) | No paid infrastructure; any cloud-dependent legacy protocol needs an explicit recorded disposition |
| Git | CONVENTIONS.md: working branches merge into develop through a PR ([project memory](../../../../memory/project.md) corrections) | No release-merge behavior inside this design |
| Not authorized | This design does not authorize running real destructive or release operations; safe fixtures only (FR20.2 statement; C10 invariant) | All destructive/release behavior is specified and fixture-tested with synthetic targets; real execution stays with the human operator |

## Proposed design work

Produce, under `construction/u7-controlled-platform-protocols/functional-design/`:

- **entities.md** — the four owned entities with attributes, constraints and relationships (evidence generation/binding, authority scope, operation preconditions, receipt outcome/reconciliation).
- **rules.md** — numbered business rules (`BRx.y`) for evidence validity, authority evaluation, precondition checking before effects, receipt binding, replay/conflict and unknown-outcome reconciliation; each traced to FR20.1/FR20.2.
- **functional-spec.md** — the ordered workflows (inspect evidence, execute a controlled operation, read/reconcile a receipt) and the lifecycle state machines for evidence, authority, operation and receipt.
- **traceability.json** — FR20.1/FR20.2 (and any assigned acceptance rows) mapped to `BRx.y` targets in `rules.md`.

## Q1 — Retained protocol membership in this design

The contract requires the actual retained operator protocol membership to be reconciled from the reference before parity is claimed, and the reference includes legacy cloud deployment artifacts (for example the AWS CDK stacks under `ops/cdk/`) that cannot run under the $0/local budget. Before artifacts can define the operation vocabulary, this design must decide how completely that membership is reconciled now.

- A. Reconcile the complete retained set from the reference now and record every protocol with an explicit disposition (retained-local, compatibility-dependent, or not-implemented-under-$0), even where the behavior is not implemented in this unit.
- B. Design only the generic evidence/authority/execution/receipt envelope now; leave the per-protocol membership inventory as a tracked follow-up before any parity claim.
- C. Design the envelope plus only the subset required to exercise the safe acceptance fixtures (wrong actor/target, stale evidence, changed input, interrupted/duplicate execution, disk/permission failure).
- D. Limit the design to a named protocol subset (please name it).
- X. Other (please specify)

[Answer]: A

## Q2 — Operator authority model

C10 requires current, independent operator authority for the exact target; an application administrator is never automatically an operator, and native credential semantics must be preserved. This design must fix how authority is established, bound and revoked.

- A. Local OS user identity plus a locally stored, target-scoped authority grant (actor → target scope → permitted operation), provisioned and revoked through a controlled local procedure; every execution re-validates the current grant.
- B. Signed local operator credentials/tokens issued by a local authority store, verified per operation.
- C. Interactive presence at execution time (a human at the terminal confirms each effect) with no standing grant.
- D. A standing grant (A or B) for routine operations, plus per-effect interactive confirmation for destructive/release operations.
- X. Other (please specify)

[Answer]: A

## Q3 — Destructive/release effect gating

FR20.2 states destructive/release effects require the applicable explicit operator authority, beyond ordinary controlled-operation authority. The design must say exactly what makes that authority explicit so no unsafe effect can be reached without it.

- A. A separate authority grant naming that exact operation and target scope, established before the request; the routine grant never covers destructive/release operations.
- B. A per-effect recorded confirmation at request time (the operator confirms this exact target and input), without a separately provisioned grant.
- C. Both a separate grant and a per-effect confirmation.
- D. Keep the rule generic in this design and decide per protocol during implementation.
- X. Other (please specify)

[Answer]: A

## Q4 — Evidence validity and the U8 read interface

FR20.1 requires current, stale, mismatched and missing evidence to be distinguishable, restricted reads to stay bounded and authenticated, and evidence never to be substituted for application readiness. The design must define when evidence may authorize an effect and exactly what U8 may read.

- A. Evidence carries its target/input/environment binding, a generation and an observation time; it is stale when a finite, per-protocol maximum age is exceeded, mismatched when target/input/environment no longer match, and missing when absent. U8 reads a read-only evidence snapshot plus authorized operation/receipt outcomes and can never execute.
- B. Only binding mismatch invalidates evidence; no time-based staleness at all.
- C. Staleness is judged case by case by the consuming operator at request time; U8 reads only receipt outcomes.
- D. Other structure (please describe below).
- X. Other (please specify)

[Answer]: A

## Q5 — Disposition of cloud/paid-dependent legacy protocols

The $0 budget excludes paid or cloud-dependent infrastructure, while the parity obligation requires every retained protocol to be accounted for rather than forgotten. The design must fix how those protocols are disposed of.

- A. Record each with an explicit disposition: a local equivalent is implemented only where a genuine $0/local path exists; cloud-dependent operations are recorded as compatibility-dependent/not-implemented with their consumer impact noted.
- B. Drop them from the design entirely, recorded only as out of scope.
- C. Implement local equivalents for all of them regardless of consumer evidence.
- D. Defer every disposition to U8's cumulative parity ledger.
- X. Other (please specify)

[Answer]: A

## Q6 — Compatibility target for existing consumers

The contract keeps dedicated authenticated evidence HTTP bindings compatibility-dependent rather than a public admin bypass, and the actual existing-consumer matrix is still unknown (IB-01/IB-03). The design must state what compatibility it promises.

- A. The canonical v2 envelope (local stdin/stdout JSON with the retained operation vocabulary) is the only supported interface; legacy command compatibility is preserved only where the reference shows a real external consumer, recorded in the consumer matrix.
- B. Command-for-command and flag-for-flag parity with the legacy CLI.
- C. A named compatibility subset (please name it).
- D. Defer the promise: the design records the interface and leaves the matrix to be completed from actual reference inspection during implementation.
- X. Other (please specify)

[Answer]: A

## Q7 — Unknown/partial outcomes and reconciliation

C10 states an interrupted effect with an unknown outcome is reconciled without duplicate execution, a replay with changed input under the same key conflicts, and FR20.2 forbids reporting permission, disk or connectivity failures as completed. The design must define the outcome states and the reconciliation window.

- A. Receipt states: authorized → executing → completed | failed | unknown; unknown stays unknown until a reconciliation read establishes disposition from the target; same-key same-input replay returns the recorded receipt without repeating effects; same-key changed-input is rejected; receipts are retained until explicitly reconciled or archived, with an operator-visible list of unresolved unknowns.
- B. Same states, but an unknown may be manually re-executed after operator confirmation, without a reconciliation read.
- C. Simpler: completed | failed only; interrupted executions are reported as failed.
- D. Other structure (please describe below).
- X. Other (please specify)

[Answer]: A

## Assumptions & Open Questions

- Assumption: the C10 local stdin/stdout JSON transport is the design's only execution interface; any HTTP evidence binding stays compatibility-dependent and is not designed as a new admin surface here.
- Assumption: safe fixtures use synthetic targets and inputs; this design authorizes no real destructive or release operation.
- Assumption: receipt storage technology remains open (decided in NFR/infrastructure design); this design fixes only the semantic binding and lifecycle.
- Open: the complete retained protocol inventory and existing-consumer matrix are not yet reconciled from the reference (C10 open question; IB-01/IB-03); Q1/Q6 fix the reconciliation policy.
- Open: receipt retention duration and the unresolved-unknown review cadence depend on operations policy; Q7 fixes the reconciliation semantics, not a numeric window.

## Sources

- [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) — U7 boundary and acceptance
- [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md) — FR20/FR20.1/FR20.2 assignments
- [requirements.md](../../../inception/requirements-analysis/requirements.md) — FR20 acceptance statements
- [components.md](../../../inception/domain-design/components.md) — PlatformControl ownership and entities
- [contract-summary.md](../../../inception/contract-design/contract-summary.md) — C10 controlled platform evidence and effects
- [project memory](../../../../memory/project.md) — $0 budget and CONVENTIONS.md corrections

## Consolidated Summary Confirmation

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
