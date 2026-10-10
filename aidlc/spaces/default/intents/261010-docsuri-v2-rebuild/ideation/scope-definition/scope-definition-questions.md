# DocSuri v2 — Scope definition questions

## Carried-forward decisions

These decisions are already recorded in the approved intent and feasibility
artifacts. They are not new questions or a smaller release proposal.

| Scope topic | Existing decision | Source |
| --- | --- | --- |
| Release boundary | Retain all current product capabilities in the first v2 release; defer new feature expansion | [Intent questions](../intent-capture/intent-capture-questions.md), Q6; C-01–C-02 |
| First complete outcome to prove | Find a relevant paper, understand it, save it and return to it later, for researchers and engineers | Intent questions Q1–Q2; C-03 |
| Quality | Stable, smooth use and comprehensible, repairable files and code; measure the baseline before setting numeric targets | Intent questions Q3; C-04–C-05 |
| User and data continuity | Determine existing users, saved data and recoverable backups before choosing a transition policy | Intent questions Q7; C-06; feasibility D-02 |
| Budget and capacity | $0; only free or local stacks; one human maintainer supported by coding agents | [Feasibility questions](../feasibility/feasibility-questions.md), Q1–Q2; C-07, C-13 |
| Schedule | No fixed deadline; estimate effort and confirm availability after discovery | Feasibility Q1; O-01, O-06–O-07 |
| Technology and obligations | No mandatory technology/provider within the free/local constraint; investigate obligations before hosting or data-handling selection | Feasibility Q3–Q5; C-08–C-09 |
| Authority and communication | User decides scope and priorities; concise progress and clear review summaries | C-10–C-11 |
| Git flow | Working branch → PR into develop → release promotion to main | C-12; [CONVENTIONS.md](../../../../../../../CONVENTIONS.md) |

C-xx and O-xx refer to the [constraint register](../feasibility/constraint-register.md).
D-xx refers to the [RAID log](../feasibility/raid-log.md).

## Evidence and dependency limits

The [feasibility assessment](../feasibility/feasibility-assessment.md) permits
further definition and investigation while delivery feasibility remains
conditional. A complete inventory of current capabilities and their dependencies
does not yet exist. Reverse engineering will reconcile behavior, source, tests
and documentation, including failing or disabled paths, before detailed parity
requirements and implementation units are finalized.

The anchor journey defines the first complete experience to prove; a successful
demonstration alone does not establish v2 release readiness. Scope work must
carry all retained capabilities and the unresolved evidence items forward.
Prioritization determines work order without silently deferring existing
capabilities beyond the first v2 release. No architecture, migration policy or
numeric quality target is selected by this questionnaire.

## Q1. What should guide the order of the rebuild work?

All choices retain every current capability, the $0 limit and the approved
review points. They differ in what receives attention first; actual technical
dependencies and required evidence still constrain the order.

A. Risk first (recommended): resolve the biggest uncertainties about free/local capacity, data continuity and recovery, then prove the anchor journey and complete remaining parity.
B. User journey first: after essential discovery, prioritize a working find → understand → save → revisit experience, then complete remaining parity.
C. Dependencies first: after essential discovery, rebuild shared foundations and dependent capabilities in the order their verified dependencies require.
X. Other (please specify)

[Answer]: Risk first (Recommended): resolve free/local capacity, data continuity and recovery uncertainties, then prove the paper journey and complete remaining capability parity.

## Assumptions & Open Questions

- Q1 is answered: risk first. Previously settled release, deadline, budget and
  quality decisions remain in force.
- Detailed capability dependencies require investigation, not a guess from the
  user. The scope backlog will identify that work and keep unresolved items
  visible until evidence settles them.
- No RICE or WSJF scores are asserted: measured reach and effort are unavailable.
  Use MoSCoW for the agreed release boundary and an explicit work order for the
  retained capabilities following the risk-first preference selected in Q1.

## Consolidated Summary Confirmation

- The first v2 release retains all current product capabilities for researchers
  and engineers. New feature expansion is deferred.
- Use risk-first sequencing: establish the capability and dependency inventory
  and resolve free/local capacity, existing-user/data continuity and recovery
  uncertainties; then prove the find → understand → save → revisit journey and
  complete remaining capability parity. Actual dependencies and the approved
  review points still apply.
- Treat the anchor journey as the first complete outcome to prove. Release
  readiness also requires verification of every retained capability.
- Keep the budget at $0 with only free or local stacks. Plan for one human
  maintainer with coding agents, no fixed deadline, and effort estimates after
  discovery. Any evidenced conflict between parity, quality and resources comes
  back to the user; it does not authorize spending or silent scope reduction.
- Prioritize stable, smooth use and comprehensible, repairable code. Measure
  task success, responsiveness, interruption recovery and defect reproduction
  and repair before agreeing numeric acceptance targets.
- Investigate authoritative users, saved data and recoverable backups before
  deciding continuity or migration. Investigate privacy, content-licensing,
  institutional and data-location obligations before hosting/data decisions.
  Current integrations and dependencies also need verification.
- Keep technology, hosting, migration, detailed implementation units and the
  delivery schedule open until the required evidence is available. The scope
  document and backlog will identify outcomes, dependencies and closure evidence
  without inventing a complete feature inventory or measured priority scores.
- The user decides scope and priorities, with concise progress and clear review
  summaries. Git follows CONVENTIONS.md: working branch → PR into develop →
  release promotion to main.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]:
