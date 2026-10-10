# DocSuri v2 — Scope document

Date: 2026-10-11 (Asia/Seoul)

Basis: the user confirmed the consolidated scope summary with “Looks correct”.
This document is prepared for Scope Definition review; that confirmation does
not itself approve this stage or establish implementation readiness. [SQ]

## Objective and audience

Rebuild DocSuri for researchers and engineers who need to find and understand
papers. Stable, smooth use is the highest priority. Both file organization and
code must be comprehensible and repairable by one human maintainer supported by
coding agents. The anchor experience is **find → understand → save → revisit**.
The first v2 release must retain **all current product capabilities**. [IC] [CR]

## Scope boundary

| In scope for the rebuild | Completion evidence |
| --- | --- |
| Establish the current product reference | Reconcile behavior, source, tests and documentation into a capability inventory, including failing, disabled and disputed paths; record evidence and dependencies |
| Retain every current capability | Each inventoried capability maps to a v2 requirement, implementation responsibility and verification result; unresolved omissions prevent a full-parity claim |
| Prove the complete paper journey | Repeatable evidence for finding, understanding, saving and returning to a paper, including transitions and representative interruption/recovery paths |
| Improve stability, smoothness and repairability | Baseline measurements followed by agreed numeric targets; later verification against those targets and a representative defect reproduction/repair exercise |
| Resolve continuity using evidence | Establish authoritative users, saved data, ownership and recoverable backups; present transition choices before selecting and implementing the user's policy |
| Establish sustainable operation within $0 | Demonstrate retained capabilities and quality within available local resources or verified sustainable free-service limits, with no paid fallback |
| Account for dependencies and obligations | Verify current integrations and compatibility expectations; investigate privacy, content-licensing, institutional and data-location obligations before related design choices |
| Deliver an operable, maintainable service | Reproducible setup, understandable ownership and boundaries, diagnosis/recovery instructions, verification and release evidence suitable for one maintainer |

Sources: [IC], [FA], [CR], [SQ]. These rows define required outcomes; they do
not assert that the evidence already exists.

| Outside this release boundary | Treatment |
| --- | --- |
| New product feature expansion | Defer until after v2; do not add speculative capabilities to fill a backlog |
| Planned paid services, model/API calls, subscriptions or new hardware | Exclude under the $0 constraint; free trials or automatic billable overages do not demonstrate sustainable fit |
| An assumed fresh-data start or unverified migration policy | No such choice is authorized; the continuity decision remains dependent on inventory and recovery evidence |
| A promised release date, selected stack or fixed numeric quality targets at this stage | Keep these decisions open until their required evidence is available |

Necessary work to meet the confirmed stability, repairability and continuity
outcomes remains in scope even when it changes the implementation substantially.
Conversely, retaining capabilities does not mandate retaining current libraries,
providers, directory structures or known defects. Conflicting evidence about a
capability is recorded for the user's decision, not silently treated as a removal.
[IC] [FA] [CR]

## Release boundary and first demonstration

The first complete outcome to demonstrate is the anchor paper journey. It gives
an early, integrated check of user value and transitions. It is **not sufficient
on its own to establish first-release completeness**: all other current
capabilities remain required before v2 release acceptance. There is no approved
reduced-feature MVP. [IC] [SQ]

The complete capability list is still unknown. The release boundary is fixed by
the retention decision; discovery supplies its detailed membership and evidence.
The [intent backlog](intent-backlog.md) therefore contains provisional work
packages, not a claim that implementation units or every product feature have
already been enumerated.

## Risk-first sequencing and decision dependencies

The user selected risk first. Work order within the approved lifecycle should
resolve the largest uncertainties before committing to an implementation or
transition. These bands express priority and dependencies, not a replacement for
the approved stage sequence. [SQ] [RAID]

| Band | Intended outcome | Evidence needed to proceed with dependent decisions |
| --- | --- | --- |
| 1. Establish the reference and reduce risk | Inventory capabilities/dependencies; reconcile environment, users/data and recovery; investigate obligations; measure the baseline and free/local resource fit | Evidence for the decision in question, with unresolved items and consequences explicit; no claim that all risk disappears |
| 2. Prove an integrated experience | Build maintainable foundations only as required by the verified design, then demonstrate the whole anchor journey | Agreed requirements and quality targets; selected free/local approach; applicable data/continuity decisions resolved |
| 3. Complete parity and release evidence | Implement and verify all remaining current capabilities and cross-cutting behavior, then validate operation and the selected transition | Complete parity mapping, quality results, recoverability, repairability and sustainable $0 operation evidence |

Capability and dependency discovery informs every band. Authority of the current
environment precedes using it as a representative baseline. Data inventory and
recovery evidence precede continuity selection. Obligations precede hosting and
data-handling choices. Baseline measurements precede numeric targets. Capacity,
free-service terms and operating burden precede resource and schedule commitments.
Independent investigation may proceed together where useful; technical
dependencies still constrain implementation order. [FA] [CR] [RAID]

## Value stream map

This map expresses the confirmed target journey and the evidence to collect.
Elapsed time, waiting time, success rate and failure frequency have not yet been
measured. It does not describe verified current performance or select UI controls.

| Step | User input / need | Useful outcome carried forward | Waiting or failure evidence to collect |
| --- | --- | --- | --- |
| Find | A research or engineering information need | A relevant paper identified for further understanding | Time and success of locating it; distinguish no results, loading and failed retrieval |
| Understand | The selected paper and the user's question or reading need | Understanding supported by the paper and the service's retained capabilities | Time to usable content; unavailable/partial content and interrupted work; assess existing understanding aids after inventory |
| Save | A paper the user wants to keep | A confirmed saved reference associated with the correct user/context | Acknowledged writes, failed or repeated saves, interruption and state consistency |
| Revisit | A later need to return to saved work | The intended saved paper and retained context can be found and used again | Return-visit success, restoration of saved state, access/session interruption where applicable |

Flow: a research need leads to finding a paper, understanding it, saving it and
returning to it later. Evidence follows the same paper and relevant saved state
through the transitions; isolated screen checks cannot prove the whole flow.
Existing capabilities outside this path remain in the parity inventory and
receive their own verification. [IC] [FA]

## Success and release acceptance

Numeric targets remain unset until the baseline is measured. Scope-level
acceptance requires the following evidence, refined into testable requirements
and checks in subsequent stages. No row is marked satisfied by this document.

| Outcome | Required evidence before claiming success |
| --- | --- |
| Full capability retention | Every reference capability has an implementation and a passing verification outcome, or a later explicit user-approved change to scope; no unresolved capability silently disappears |
| Stable, smooth experience | Complete-task, responsiveness and interruption/recovery results against the targets agreed after baseline measurement; environment and method recorded |
| Repairability | A maintainer can set up the service, follow ownership/boundaries, reproduce a representative defect, fix it and verify the result; measured against the agreed repairability criteria |
| Continuity | User-selected policy supported by authoritative inventory, recovery evidence and verified transition/rollback or recovery behavior appropriate to that policy |
| $0 operation | Capacity and full-parity evidence using available local resources or sustainable verified free terms, including behavior at limits; no hidden paid fallback |
| Maintainable release | Integration and operating dependencies accounted for, relevant obligations resolved for the chosen deployment, and setup/diagnosis/recovery/release instructions verified |

## Constraint coverage and ownership

The user is the sole scope and priority approver. Agents investigate, implement
and verify for the one human maintainer; this introduces no additional approval
roles. End-user experience and future maintainers remain stakeholder concerns.
Communicate concise progress and clear evidence, tradeoffs and unresolved items
at review points. [CR]

| Confirmed constraint | Scope treatment / backlog reference |
| --- | --- |
| C-01 Retain all capabilities; C-02 defer expansion | Fixed release boundary; IB-01, IB-07, IB-08, IB-09 |
| C-03 Audience and anchor journey | Objective and value stream; IB-04, IB-07 |
| C-04 Stable, smooth and repairable | Success criteria across implementation; IB-04, IB-06–IB-09 |
| C-05 Baseline before numeric targets | Evidence dependency; IB-04 |
| C-06 Inventory before continuity choice | IB-02 precedes selected transition work in IB-09 |
| C-07 One maintainer with agents | Workload and operational burden considered in IB-05, IB-06, IB-09 |
| C-08 Technology freedom within budget | No selected stack here; IB-05 informs later design |
| C-09 Investigate obligations first | IB-03 precedes hosting/data choices |
| C-10 User authority; C-11 concise communication | Decision ownership above and review points retained |
| C-12 Git flow | Working branch → PR into develop → release promotion to main; IB-09 and every integration |
| C-13 $0, free/local only | Eligibility and measured-fit requirement; IB-05 and IB-09 |

Follow [CONVENTIONS.md](../../../../../../../CONVENTIONS.md) for all Git work.
Scope approval does not itself merge a branch or authorize an unverified release.

## Ambiguities, assumptions and open questions

The confirmed answers contain no demonstrated contradiction. Full parity,
quality and a $0 budget may conflict once measured; that remains an open
feasibility risk rather than grounds to reduce scope now. No fixed deadline
exists, so a scope-versus-date conflict cannot yet be assessed. Estimates and
maintainer availability remain prerequisites for a credible schedule. [FA] [CR]

Carry forward all O-01–O-07, R-01–R-10, A-01–A-04, I-01–I-04 and D-01–D-05
from the feasibility records. Their presence in this scope closes none of them.
The backlog assigns evidence work and dependencies for these gaps. The actual
feature inventory, authoritative environment and user/data counts, backup
recoverability, obligations, resource fit and baseline measurements remain open.

If evidence conflicts with the agreed boundary, present the concrete conflict
and alternatives to the user at the affected decision. Do not assume spending,
lower quality targets, drop a capability or choose migration by default.

## Sources

- [IC] [Approved intent statement](../intent-capture/intent-statement.md).
- [FA] [Approved feasibility assessment](../feasibility/feasibility-assessment.md).
- [CR] [Constraint register](../feasibility/constraint-register.md), C-01–C-13 and O-01–O-07.
- [RAID] [Feasibility RAID log](../feasibility/raid-log.md).
- [SQ] [Scope answers and confirmed summary](scope-definition-questions.md).
- [Backlog](intent-backlog.md), provisional work packages IB-01–IB-09.

## Assumptions & Open Questions

Open evidence and unproven feasibility hypotheses are described above and retain
their upstream identifiers. No stack, migration policy, numeric quality target,
delivery date or exhaustive capability inventory is asserted here.
