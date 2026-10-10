# DocSuri v2 — Ideation decision log

Date: 2026-10-11 (Asia/Seoul)

This log consolidates decisions from the approved intent, feasibility and scope
records and the confirmed handoff summary. DEC identifiers belong to this log;
they are distinct from the feasibility RAID log's D identifiers. References point
to the original answers or approved artifacts. No new product choice is made by
restating a decision here.

## Governing decisions

| ID | Decision | Effect on subsequent work | Source |
| --- | --- | --- | --- |
| DEC-01 | Rebuild DocSuri with stable, smooth use as the highest priority and comprehensible, repairable files and code | Judge the result by user experience and ability to diagnose/repair, not directory tidiness alone | [Intent statement](../intent-capture/intent-statement.md), Problem Statement |
| DEC-02 | Serve researchers and engineers who need to find and understand papers | Use their paper work as the principal experience context; do not infer actual adoption or user counts | [Intent questions](../intent-capture/intent-capture-questions.md), Q1 |
| DEC-03 | Anchor verification in find → understand → save → revisit | Prove a complete journey and its transitions | Intent questions Q2 |
| DEC-04 | Retain all current product capabilities in the first v2 release; defer new feature expansion | Inventory and verify the whole product; an anchor-only demonstration is insufficient release scope | Intent questions Q6; [scope document](../scope-definition/scope-document.md), Release boundary and first demonstration |
| DEC-05 | Measure task success, responsiveness, interruption recovery and defect reproduction/repair before setting numeric targets | Establish reproducible baselines and agree targets afterward | Intent questions Q3 |
| DEC-06 | The user decides scope and priorities; consider end users and future maintainers, with no additional named approvers | Preserve decision authority without claiming independent stakeholder endorsement | Intent questions Q4; [stakeholder map](../intent-capture/stakeholder-map.md) |
| DEC-07 | Provide concise progress updates and clear summaries at review points | Communicate evidence, changes and material unresolved decisions | Intent questions Q5 |
| DEC-08 | Determine existing users and saved data before choosing continuity or migration | Rebuild authorization does not select a fresh-data start; authoritative inventory and recovery evidence precede transition selection | Intent questions Q7; [constraint register](../feasibility/constraint-register.md), C-06, O-03 |
| DEC-09 | Plan for one human maintainer supported by coding agents | Include operating burden, availability and repair effort in delivery choices | [Feasibility questions](../feasibility/feasibility-questions.md), Q2 |
| DEC-10 | No fixed deadline; estimate effort after discovery | Do not promise a delivery date or assume unlimited maintainer availability | Feasibility Q1; constraint register O-01, O-06–O-07 |
| DEC-11 | Budget is $0; only free or local stacks | Verify sustainable terms/limits or available local capacity; no paid fallback or silent overage | Feasibility Q1 as corrected; [budget note](../feasibility/feasibility-note-record.md); constraint register C-13 |
| DEC-12 | No fixed technology/provider; evaluate eligible replacements against stability and repairability | Keep stack decisions open within DEC-11; historical library choices are not automatic v2 selections | Feasibility Q3; constraint register C-08 |
| DEC-13 | No known external integration commitments beyond current capabilities | Verify actual dependencies and consumers before compatibility changes; do not equate unknown with absent | Feasibility Q4; constraint register O-02 |
| DEC-14 | Privacy, licensing, institutional and data-location requirements are uncertain; investigate first | Establish applicable evidence before hosting and data-handling rules | Feasibility Q5; constraint register C-09, O-04 |
| DEC-15 | Use CONVENTIONS.md for Git flow | Working branches merge through PRs into develop; releases promote develop to main; follow its branch naming and tag conventions | [CONVENTIONS.md](../../../../../../../CONVENTIONS.md); [recorded user correction](../../../../memory/project.md), Corrections |
| DEC-16 | Use risk-first sequencing | Resolve free/local capacity, continuity and recovery uncertainties, then prove the anchor journey and complete remaining parity; respect actual dependencies and review points | [Scope questions](../scope-definition/scope-definition-questions.md), Q1 |
| DEC-17 | Carry the approved nine provisional work packages into further definition | Retain outcomes and evidence dependencies; discover detailed capabilities and implementation units later | [Intent backlog](../scope-definition/intent-backlog.md), IB-01–IB-09; Scope Definition approval |
| DEC-18 | Recommend proceeding to Inception beginning with Reverse Engineering while delivery feasibility remains conditional | Continue evidence gathering under the approved plan; do not claim complete feasibility or implementation readiness | [Handoff questions](approval-handoff-questions.md), confirmed summary |

## Process decisions and superseded interpretations

| Topic | Governing interpretation | History / consequence |
| --- | --- | --- |
| Original plan approval | The user's “Approve” starts this piece of rebuild work | It did not request creation of a reusable scope; the correction is saved under project Corrections |
| Git conflict | DEC-15 governs this project | The user explicitly chose CONVENTIONS.md after the conflicting direct-to-main convention was presented; do not reopen that settled choice |
| Budget correction | DEC-11 governs all later work | The earlier answer left budget and deadline open. The later $0 instruction supersedes only the open-budget portion; no fixed deadline remains |
| Reusable budget note | The user classified the $0 instruction as Interpretation | The confirmed note was persisted to project Corrections; no new note is inferred here |
| Scope note capture | The user chose “Nothing to add” after Scope Definition | This adds no reusable rule and does not itself approve the stage |
| Skipped Ideation work | Market Research, Team Formation and Rough Mockups are skipped in the approved plan | Their absent artifacts are not evidence of market validation, staffing, scheduled human teams or approved screen designs |

Sources: [project Corrections](../../../../memory/project.md),
[feasibility question history](../feasibility/feasibility-questions.md),
[budget note classification](../feasibility/feasibility-note-record.md),
[workflow state](../../aidlc-state.md) and the
[decision audit](../../audit/mac-mini-eab026d8eae1.md).

## Approval record and limits

| Stage | Verified decision | Evidence / limit |
| --- | --- | --- |
| Intent Capture | Approve | Recorded GATE_APPROVED event; audience, journey, full parity, quality and decision authority established |
| Feasibility & Constraints | Approve | Recorded GATE_APPROVED event; conditional further definition approved, unresolved evidence retained |
| Scope Definition | Approve | Recorded GATE_APPROVED event; scope and risk-first backlog approved |
| Approval & Handoff summary | Looks correct | Confirmed summary authorizes preparation of the brief, log and phase check; it is not the initiative gate approval |
| Approval & Handoff gate | Pending | No approval or phase completion is asserted in this prepared document |

These statuses were checked against the audit at preparation time. Later gate
decisions remain authoritative in the workflow state and audit; this table does
not grant approval by itself.

## Deferred decisions and evidence owners

| Decision still open | Evidence / responsible work | Decision authority |
| --- | --- | --- |
| Detailed capability membership and disputed reference behavior | Agents reconcile behavior, source, tests and docs under IB-01; retain D-01 and R-01 | User decides unresolved scope disputes |
| Continuity and migration | Agents establish authoritative environment, users/data, ownership and recovery under IB-02; retain D-02 | User chooses the transition policy after consequences are clear |
| Hosting and data handling | Agents investigate actual integrations and obligations under IB-03; retain D-03 | User resolves material policy/scope choices with the evidence |
| Numeric quality targets | Agents measure the four baseline dimensions under IB-04; retain D-04 | User agrees targets after measurement |
| Resource approach, stack and schedule | Agents assess free/local fit, effort and operating burden under IB-05 and later design; retain D-05 | User decides priorities and any evidenced conflict within the $0 limit |
| Detailed implementation units and release readiness | Subsequent requirements/design decompose IB-06–IB-09 and supply implementation, test and operating evidence | Approved lifecycle review points govern progression |

## Assumptions & Open Questions

No initial user/data count, performance level, available capacity, legal
obligation, delivery duration or resource-fit conclusion is presumed. The
[RAID log](../feasibility/raid-log.md) remains the source of open risks and closure
criteria. The [phase consistency check](../../verification/phase-check-ideation.md)
verifies the handoff's traceability without closing those evidence gaps.
