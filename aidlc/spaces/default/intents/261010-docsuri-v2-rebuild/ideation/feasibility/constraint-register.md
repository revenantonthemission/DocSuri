# DocSuri v2 — Constraint register

Date: 2026-10-11 (Asia/Seoul)

## Interpretation and authority

Confirmed constraints below come from the approved [intent-statement](../intent-capture/intent-statement.md)
and the [feasibility answers, confirmed summary and later budget correction](feasibility-questions.md).
“Open” means that the associated decision needs evidence; it does not mean
that a restriction has been invented or waived. The user decides scope and
priorities. This register selects no implementation, hosting or migration policy.

## Confirmed constraints

| ID | Category | Constraint | Source | Consequence / verification |
| --- | --- | --- | --- | --- |
| C-01 | Product | Retain all current product capabilities in the first v2 release | Intent: Initial Scope Signal | Build a complete parity inventory; no silent feature removal |
| C-02 | Product | Defer new feature expansion | Intent: Initial Scope Signal | Distinguish rebuilding existing capabilities from proposed additions |
| C-03 | Experience | Serve researchers and engineers; anchor verification in find → understand → save → revisit | Intent: Target Customer | Verify the complete journey while retaining coverage of C-01 |
| C-04 | Quality | Prioritize stable, smooth use and comprehensible, repairable code | Intent: Problem Statement | Design and verification must address both user experience and maintenance |
| C-05 | Measurement | Establish numeric targets after measuring the baseline | Intent: Success Metrics | Record task success, responsiveness, interruption recovery and defect-repair evidence before agreeing thresholds |
| C-06 | Continuity | Determine existing users and saved data before choosing continuity or migration | Intent: Confirmed Follow-up Decisions | Do not infer that a rebuild permits users or their data to start over |
| C-07 | Capacity | Plan for one human maintainer supported by coding agents | Feasibility Q2 | Include continuing operational and repair effort in option assessment |
| C-08 | Technology | No current technology or provider is mandatory for v2; evaluate free/local replacements against stability and repairability | Feasibility Q3 and later budget instruction | Keep choices open within C-13; preserve capabilities while assessing alternatives |
| C-09 | Obligations | Investigate uncertain privacy, licensing, institutional and data-location requirements before choosing hosting and data-handling rules | Feasibility Q5 | Keep those decisions dependent on the investigation |
| C-10 | Authority | User decides scope and priorities; consider end users and future maintainers, with no other named approvers | Intent: Initial Scope Signal | Record scope tradeoffs for the user's decision |
| C-11 | Collaboration | Concise progress updates and clear summaries at review points | Confirmed intent Q5 | Make evidence, changes and unresolved decisions visible without repeated approval requests |
| C-12 | Git | Working branches → PR into develop → release promotion to main | CONVENTIONS.md; explicit user correction | Use develop as integration target and follow the release promotion path |
| C-13 | Budget | The budget is $0. Only use free or local stacks | User's explicit note, superseding the open-budget portion of Q1 | Verify available local capacity or sustainable zero-charge terms; no planned paid services, APIs, subscriptions, hardware purchases or automatic paid overages |

## Open constraints and boundaries

| ID | Topic | Confirmed status | Required evidence / closure | Needed before |
| --- | --- | --- | --- | --- |
| O-01 | Effort, deadline and resource fit | Budget is fixed at $0 under C-13; no fixed deadline; effort and local/free resource sufficiency remain unknown | Effort estimate, capacity measurements and verified free-offering quotas/terms, with the user's priorities | Schedule and resource choices within the fixed budget |
| O-02 | External integrations | No known commitments beyond current capabilities (Q4) | Inventory actual dependencies, consumers and compatibility requirements | Changing integration behavior |
| O-03 | Existing users and data | Not established; continuity undecided | Authoritative user/data inventory, ownership relationships and backup recovery evidence | Selecting a transition policy |
| O-04 | Regulatory, contractual and content obligations | Uncertain; investigate (Q5) | Applicable source terms, agreements, data/content use and jurisdiction facts; record unresolved items | Hosting and data-handling selection |
| O-05 | Current operating environment / AWS usage | Repository declarations and local observations do not establish authoritative live hosting | Reconcile active service endpoints, resource inventory, data ownership and operating costs | Reliable baseline, hosting comparison and operational change |
| O-06 | Human availability and skills | One maintainer is confirmed; weekly capacity and skill gaps are not measured | Assess availability, current operations burden and learning/support needs against the discovered workload | Delivery schedule |
| O-07 | Organizational restrictions | No change freeze or competing-priority limit has been established | Verify availability and change windows when preparing delivery/release plans | Committing to delivery and release timing |

## Carry-forward checks

- Apply C-01 and C-02 together: an anchor journey is a proof path, not a reduced
  product boundary. Disputed or broken current behavior stays visible in the
  inventory until the user decides its treatment.
- Apply C-07, C-13 and O-01 together: estimate work for one maintainer, demonstrate
  that free/local capacity suffices, and keep new spending at $0.
- Apply C-08 and C-09 together: technology freedom does not settle content or
  data obligations. Investigate first; make the consequential choice afterward.
- Apply C-01 and C-13 together: retain all capabilities within the $0 budget.
  Surface any evidenced conflict rather than assuming paid resources or dropping
  a feature. A free trial or uncapped billable overage is not a sustainable fit.
- Existing project quality and security practices must be reconciled with the
  new design. No historical library choice is treated as a new v2 decision, and
  no quality requirement is silently lowered to make a check pass.
- See the [feasibility assessment](feasibility-assessment.md) for the bounded
  recommendation and the [RAID log](raid-log.md) for owners and closure evidence.

## Sources

- [Approved intent-statement](../intent-capture/intent-statement.md).
- [Intent question record](../intent-capture/intent-capture-questions.md),
  including reporting preference Q5.
- [Feasibility questions and summary confirmation](feasibility-questions.md).
- [Environment observations](environment-observations.md).
- [CONVENTIONS.md](../../../../../../../CONVENTIONS.md).

## Assumptions & Open Questions

O-01–O-07 are unresolved evidence or decision items. Their presence is not
approval of any assumed answer. Investigating them is compatible with continuing
definition work; consequential choices remain conditional on their evidence.
