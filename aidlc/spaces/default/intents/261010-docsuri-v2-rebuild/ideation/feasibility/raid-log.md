# DocSuri v2 — RAID log

Date: 2026-10-11 (Asia/Seoul)

## Reading this log

RAID means risks, assumptions, issues and dependencies. A risk is a possible
future problem; an issue is an observed gap or condition. Priority below is
qualitative investigation priority, not a measured probability or approved
service target. All entries are open unless their status says otherwise.

“Agent team” names work carried out for the one human maintainer, not an
additional approver or a staffing commitment. The user retains scope and
priority decisions. Stage names indicate where evidence should be carried;
they do not alter the approved stage order.

## Risks

| ID | Risk and consequence | Priority | Owner | Mitigation / closure evidence | Decision dependency |
| --- | --- | --- | --- | --- | --- |
| R-01 | Incomplete inventory could drop existing capabilities during the rebuild | High | Agent team; user resolves scope disputes | Reconcile user-visible behavior, source, tests and docs; map each capability to a parity check and record known failures | Scope and release completeness; C-01 |
| R-02 | Incorrect assumptions about users or data could cause loss or an unusable transition | High | Agent team investigates; user chooses continuity | Establish authoritative data ownership, aggregate inventory and tested recovery; document transition alternatives and consequences | Migration/continuity; C-06 |
| R-03 | Baseline checks against a development or incomplete environment could produce misleading quality targets | High | Agent team | Identify the authoritative environment, then measure complete journeys with repeatable conditions | Numeric targets; C-05, O-05 |
| R-04 | Unknown content or data obligations could invalidate a hosting or data-handling choice | High | Agent team investigates; user provides any agreements | Collect source/terms, data-use and jurisdiction evidence; record uncertainty and resolve material obligations before selection | Hosting/data rules; C-09 |
| R-05 | Full parity and ongoing operations could exceed one maintainer's capacity | High | User and agent team | Estimate workload after inventory, identify operational burden and present sequencing tradeoffs without silently reducing parity | Schedule and priorities; C-01, C-07 |
| R-06 | Full parity and quality may not fit available local capacity or sustainable free quotas; paid fallback would violate the $0 budget | High | Agent team investigates; user decides any evidenced scope/resource conflict | Measure demand and local capacity, verify free terms/quotas and billing controls, and demonstrate each retained capability within the constraint; no paid fallback or silent feature removal | Resource choices; C-01, C-13, O-01 |
| R-07 | A frontend-only or happy-path check could miss interruption, retry and return-visit failures | High | Agent team | Baseline and later verify the complete paper journey under representative interruptions, including saved-state recovery | Experience verification; C-03–C-05 |
| R-08 | A tidier directory tree could leave diagnosis and repair just as difficult | High | Agent team | Measure a representative defect reproduction/fix exercise and evaluate whether future maintainers can follow the relevant behavior | Repairability evidence; C-04 |
| R-09 | Unobserved external consumers or provider dependencies could break when existing behavior changes | Medium | Agent team | Inventory integrations and usage; make compatibility changes explicit for affected capabilities | Integration changes; O-02 |
| R-10 | Historical operational and implementation notes could be mistaken for current facts or v2 decisions | Medium | Agent team | Date and verify evidence; reconcile legacy practices with the confirmed technology freedom and CONVENTIONS.md | Scope, design and release planning; C-08, C-12 |

## Assumptions to validate

| ID | Assumption / hypothesis | Status and basis | Owner | Validation or consequence if false |
| --- | --- | --- | --- | --- |
| A-01 | Existing implementation, documents and available runtime evidence can together establish current capability parity | Working hypothesis, not an exhaustive inventory; intent requires investigation | Agent team | Reconcile evidence during reverse engineering; put unresolved capability boundaries to the user |
| A-02 | At least one trustworthy source can establish the authoritative user/data state and recovery position | Unproven; local volumes/directories exist but their authority and recoverability are unknown | Agent team | Verify authority and recovery; if unavailable, surface the evidence loss before choosing continuity |
| A-03 | The single maintainer will have capacity for the resulting workload | One maintainer is confirmed; capacity adequacy is unproven | User and agent team | Estimate workload and available time before agreeing schedule or operating commitments |
| A-04 | Available local resources and sustainable free offerings can support all current capabilities and the eventual quality targets | Unproven; $0 is a confirmed constraint, not proof that free/local capacity suffices | Agent team | Measure resource needs and available capacity; validate free terms/quotas before choosing an option; surface any conflict without assuming spending permission |

## Observed issues and evidence gaps

| ID | Issue | Evidence / limit | Owner | Resolution evidence |
| --- | --- | --- | --- | --- |
| I-01 | The authoritative currently served environment has not been established | Runbook describes local hosting after AWS decommissioning; AWS config remains; observed containers are development services [ENV] | Agent team | Reconciled live environment/resource inventory with data authority and cost sources |
| I-02 | Documented local backend health endpoint was unavailable during the observation | Connection failure at local port 8000; frontend root at port 3000 responded as DocSuri [ENV] | Agent team | Explain which environment/process should serve the backend and obtain a reproducible journey baseline; this observation alone is not proof of a public outage |
| I-03 | Existing user/data counts and backup restorability are unverified | Directory/volume existence only [ENV] | Agent team | Aggregate authoritative inventory and recovery verification, without private contents in planning files |
| I-04 | No measured quality baseline, defensible effort estimate or demonstrated fit within free/local capacity is available | Targets follow measurement; later user instruction sets a $0 budget [IC] [FQ] | Agent team | Baseline, effort estimate and resource-fit evidence within C-13, with assumptions and uncertainty explicit |

## Dependencies and decision boundaries

| ID | Needed evidence or decision | Owner | Needed by | Acceptance evidence |
| --- | --- | --- | --- | --- |
| D-01 | Full capability inventory and disposition of conflicting evidence | Agent team; user decides disputed scope | Requirements and parity commitment | Every capability mapped to observed/reference evidence and a planned verification outcome |
| D-02 | Authoritative environment, users, saved data and recovery position | Agent team investigates; user decides transition | Continuity/migration choice | Inventory, ownership and recovery evidence; selected policy with user-visible consequences |
| D-03 | Applicable content, privacy, institutional and data-location obligations | Agent team investigates; user supplies known agreements | Hosting/data-handling choice | Evidence-backed obligations and explicitly unresolved items; no unsupported compliance assertion |
| D-04 | Representative journey and repairability baseline | Agent team | Numeric acceptance targets | Reproducible measurements covering task success, responsiveness, interruption recovery and defect repair; user-agreed targets afterward |
| D-05 | Effort estimate, human availability and a resource plan within the fixed $0 budget | Agent team investigates; user sets priorities | Delivery and free/local resource choices | Available local capacity, verified sustainable free terms/quotas, operating burden and parity evidence without new spending |

## Follow-up discipline

At subsequent review points, update each relevant entry with newly collected
evidence, retain its identifier, and close it only when the stated evidence is
present. A passing narrow check must not close a broader risk: a responding page
does not close journey reliability, and an existing backup file does not close
recovery. Material unresolved items should be brought to the user at the
decision they constrain, with concrete alternatives.

## Sources

- [IC] [Approved intent-statement](../intent-capture/intent-statement.md).
- [FQ] [Feasibility answers and confirmed summary](feasibility-questions.md).
- [ENV] [Dated environment observations](environment-observations.md).
- C-xx and O-xx identifiers refer to the [constraint register](constraint-register.md).
- The recommendation and its boundaries are in the [feasibility assessment](feasibility-assessment.md).

## Assumptions & Open Questions

The assumptions are A-01–A-04 above. Open evidence and decisions are I-01–I-04
and D-01–D-05. No entry is silently accepted as fact by inclusion in this log.
