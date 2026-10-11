# DocSuri v2 — Initiative brief

Date: 2026-10-11 (Asia/Seoul). Prepared from the confirmed [handoff summary](approval-handoff-questions.md); initiative approval is pending.

## Recommendation

**Proceed to Inception, beginning with Reverse Engineering, under the approved
plan.** Continue discovery and detailed definition while delivery feasibility
remains conditional. Full capability parity within $0 has not yet been
demonstrated. The [phase check](../../verification/phase-check-ideation.md) records
the consistency evidence and remaining conditions.

## Intent and scope

Rebuild DocSuri for researchers and engineers who need to find and understand
papers. Prioritize stable, smooth use and comprehensible, repairable files and
code. Retain **all current product capabilities** in the first v2 release; defer
new feature expansion. The anchor journey is the first complete outcome to
prove, and all remaining capabilities must also be verified before release.
[Intent statement](../intent-capture/intent-statement.md),
[scope document](../scope-definition/scope-document.md).

## Concept and validation

**Find a relevant paper → understand it → save it → return to it later.**
The [value stream map](../scope-definition/scope-document.md#value-stream-map)
describes this experience and its measurement needs. Market Research and Rough
Mockups were skipped in the approved plan; no market validation or approved
screen designs are claimed. Measure task success, responsiveness, interruption
recovery and defect reproduction/repair before agreeing numeric quality targets.

## Risk-first work and open conditions

The [nine-package backlog](../scope-definition/intent-backlog.md) first resolves
the reference, continuity and resource uncertainties, then proves the integrated
journey and completes remaining parity, respecting verified dependencies.

| Decision dependency | Evidence still needed | Backlog |
| --- | --- | --- |
| Full capability retention | Complete behavior/source/test/document inventory, including failing or disputed paths | IB-01, IB-08 |
| Continuity and recovery | Authoritative environment, users, saved data, ownership and verified backups | IB-02, IB-09 |
| Eligible hosting and data handling | Actual integrations and applicable privacy, content, institutional and location obligations | IB-03 |
| Quality and repairability | Representative baseline, agreed targets and later verification | IB-04, IB-06, IB-07, IB-09 |
| Sustainable delivery within $0 | Local capacity or verified free limits, workload fit, effort and maintainer availability | IB-05, IB-09 |

Agents gather evidence and carry out mitigation work; the user decides material
scope and priority tradeoffs. Risks remain open until their recorded closure
evidence exists. See the [feasibility assessment](../feasibility/feasibility-assessment.md)
and [RAID log](../feasibility/raid-log.md).

## Resources, authority and delivery boundaries

Budget: **$0; free or local stacks only**. Plan for one human maintainer supported
by coding agents. No fixed deadline, paid fallback, new paid subscription or
hardware purchase is planned. Estimate effort after discovery. Team Formation
was skipped; no additional staffing or scheduled human teams are asserted.

The user is the sole scope and priority approver. Consider end users and future
maintainers without claiming their independent endorsement. Keep concise progress
updates and clear review summaries. Technology, hosting, migration policy and
numeric targets remain open until evidence supports their selection.
[Stakeholder map](../intent-capture/stakeholder-map.md),
[constraint register](../feasibility/constraint-register.md).

Follow [CONVENTIONS.md](../../../../../../../CONVENTIONS.md): working branch →
PR into develop → release promotion to main. An evidenced conflict between full
parity, quality and resources returns to the user; it does not authorize spending,
silent feature removal or weaker targets. This handoff does not perform a release.

## Assumptions & Open Questions

Carry forward the feasibility record's O-01–O-07, R-01–R-10, A-01–A-04,
I-01–I-04 and D-01–D-05. No evidence gap is closed by this brief.
The [decision log](decision-log.md) preserves the governing choices and the
superseded open-budget answer.
