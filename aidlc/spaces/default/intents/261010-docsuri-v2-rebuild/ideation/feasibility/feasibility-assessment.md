# DocSuri v2 — Feasibility assessment

Date: 2026-10-11 (Asia/Seoul)

## Assessment

**Recommendation: proceed with scope definition and evidence gathering, with
delivery feasibility still conditional.** The confirmed objective is coherent:
rebuild for stable, smooth use and a comprehensible, repairable codebase while
retaining all current capabilities. The user has now set a **$0 budget, using
only free or local stacks**. There is no fixed deadline or mandatory provider.
Full capability parity within this budget has not yet been demonstrated: the
capability inventory, available local capacity, authoritative service environment,
user/data inventory and applicable obligations need investigation before an
implementation, migration or delivery date can be committed.
[IC] [FQ] [ENV]

This assessment supports the next definition work. It does not establish that
the complete rebuild has been proven feasible, that the current service is
healthy, or that v2 is ready to build or release. Open items have owners and
closure evidence in the [RAID log](raid-log.md). Confirmed constraints are in
the [constraint register](constraint-register.md).

## Evidence and its limits

| Evidence | What it establishes | What it does not establish |
| --- | --- | --- |
| Approved intent-statement [IC] | Audience, anchor journey, full capability retention, priorities and decision authority | A complete capability inventory or measured success baseline |
| Feasibility questions, confirmed summary and subsequent budget instruction [FQ] | A $0 budget limited to free/local stacks, maintainer capacity, technology freedom within that limit and known/unknown external obligations | A delivery estimate, proof of zero-charge operation or compliance conclusion |
| Repository configuration and local observations [ENV] | An existing implementation and retained local data/backup locations; a responding frontend root and an unavailable documented local backend endpoint at the observation time | The authoritative production environment, current users, healthy backups or a working end-to-end journey |
| CONVENTIONS.md [GIT] | Working branches integrate through a PR into develop; releases promote develop to main | Permission to release before verification |

Market research was not run in this plan. No competitive-analysis, market-trends
or build-vs-buy evidence is claimed. This assessment contains no market-size,
adoption, revenue or comparative-vendor claims.

## Product and technical viability

The existing service provides a concrete reference to investigate, but a
reference implementation is not a verified specification. The first task in
defining parity is to reconcile the service's user-visible behavior, source,
tests and documentation. A failing or disabled path should be recorded with its
intended capability and observed state, rather than silently omitted from v2.
The user retains the decision on any disputed scope boundary. [IC] [ENV]

| Required outcome | Feasibility implication | Evidence needed before a delivery commitment |
| --- | --- | --- |
| Find, understand, save and revisit a paper | Validate the whole journey and its transitions, not just individual screens | A reproducible baseline with successful and interrupted journeys |
| Retain all current capabilities | The anchor journey cannot substitute for the complete parity inventory | Capability-to-evidence mapping, including less common paths and known failures |
| Stable, smooth use | Measure observed behavior before selecting numeric targets | Task-success results, response-time observations and recovery results with environment and method recorded |
| Comprehensible, repairable code | Evaluate whether a maintainer can locate, reproduce and fix a defect | A representative defect exercise recording setup, diagnosis, fix and verification effort |
| One human maintainer with coding agents | Ongoing operation and repair effort matter alongside build effort | A sustainable workload estimate and clear operating/recovery responsibilities |

No new architecture or technology choice is proposed here. Current technology
and provider choices remain open to evaluation under FQ3 within the later $0,
free-or-local constraint. Historical
implementation-specific practices do not establish a mandatory v2 stack;
applicable security and verification requirements must still be accounted for
in subsequent design and delivery work.

## Service landscape and continuity

The hosting runbook describes a local service following AWS decommissioning,
while AWS configuration remains in the repository. The locally observed stopped
containers identify themselves as the development stack. The frontend root
responded as DocSuri, but the documented local backend endpoint did not accept
a connection. These observations must be reconciled before using this machine
as the baseline for a currently served product. No live AWS inventory was
performed; current AWS use and cost remain unverified. [ENV]

Existing users, saved-data categories and authoritative data stores remain
unknown. The existence of local volumes and backup directories is not a restore
test. Establish aggregate counts, ownership relationships, last successful
backup evidence and recoverability without putting private record contents
into the planning documents. Then present the continuity choices and their
consequences to the user. A migration or a fresh-data start is not selected by
the rebuild request. [IC] [FQ] [ENV]

## External obligations

The user knows of no integration commitments beyond current product
capabilities. That answer is not evidence that there are no external consumers
or provider dependencies. Inventory actual integrations and compatibility
expectations during discovery. [FQ4]

Privacy, content-licensing, institutional and data-location requirements are
explicitly unresolved. Identify the data and content actually handled, their
sources and permissions, relevant user/institution locations, provider terms
and any existing agreements. Record the evidence and remaining uncertainty
before choosing hosting or data-handling rules. This stage makes no claim that
a particular law, certification or license applies, and no compliance clearance
is implied. [FQ5]

## Capacity, cost and schedule

Plan for one human maintainer with coding agents. The human's weekly capacity,
current operational workload and availability for release support have not
been measured. Full parity may require substantial work; a smaller release
must not be substituted without an explicit scope decision. [FQ2] [IC]

The budget is fixed at $0. Only free or local stacks are eligible. No fixed
deadline is set, and a defensible effort estimate is not yet available. Assess
the available local resources and truly free offerings after the capability,
data and environment inventories are available, separating:

- one-time discovery, rebuilding, verification and transition effort;
- hosting, storage, backup, data/API and model needs that must fit available
  local resources or verified zero-charge offerings;
- recurring maintenance, incident recovery and dependency-update effort;
- uncertainty from unverified capabilities, obligations and restore/migration work.

Do not plan paid cloud capacity, paid model/API calls, new paid subscriptions or
hardware purchases. A nominally free tier is eligible only after checking its
current terms, quotas and billing behavior; automatic paid overages or an
expiring trial are not a sustainable $0 solution. No particular free offering
has been verified or selected in this assessment. Local operation also requires
capacity and maintenance evidence; it is not proof that every operating input
has no cost. Record existing resource assumptions explicitly rather than adding
unapproved purchases to make an option work.

If a current capability cannot meet the agreed quality goals within free/local
resources, present the measured conflict and options to the user. Do not
silently remove the capability, lower a target or introduce a paid dependency.
No organizational freeze or competing-project constraint has been established;
confirm availability when scheduling rather than assuming unrestricted capacity.
[FQ1] [FQ2]

## Conditions for subsequent decisions

| Condition | Completion evidence | Decision it enables |
| --- | --- | --- |
| Complete capability inventory | Each current capability has a source/behavior reference and observed status; disputed cases have user disposition | A parity-preserving product scope and effort estimate |
| Authoritative environment and data inventory | Running service/data ownership reconciled with configuration; aggregate user/data inventory and backup recovery evidence | A continuity proposal and representative baseline environment |
| Measured baseline | Reproducible task, responsiveness, interruption and defect-repair observations | Numeric quality targets agreed with the user |
| Obligations investigated | Source/terms/data-flow evidence and an explicit record of unresolved obligations | Hosting and data-handling choices |
| Sustainable resource plan within $0 | Effort estimate, available local capacity, verified free-offering limits and maintenance burden; full parity demonstrated within the constraint | Schedule and resource choices without new spending |

These are decision dependencies, not a new workflow sequence or permission to
skip reviews. Carry them into the already approved plan and keep the actual
stage ordering under that plan.

## Answer consistency and open concerns

The user's later $0 instruction supersedes the earlier open-budget answer.
Full capability retention under that limit is a material feasibility risk, not
a demonstrated contradiction: the necessary inventory and resource measurements
do not yet exist. One human maintainer adds a capacity risk. Technology freedom
permits evaluation of free/local choices; it does not require replacing every
dependency. “Uncertain” in FQ5 directs investigation, not an assumption that no
obligations apply.

No hard blocker to further definition has been demonstrated. Delivery confidence
remains limited by the evidence gaps above; approval of this assessment should
carry those gaps forward, not convert them into satisfied requirements.

## Sources

- [IC] [Approved intent-statement](../intent-capture/intent-statement.md).
- [FQ] [Feasibility questions and confirmed summary](feasibility-questions.md);
  FQ1–FQ5 refer to Q1–Q5 in that file, not the earlier intent questions.
- [ENV] [Dated environment observations](environment-observations.md), including
  the repository sources and bounds of each live check.
- [GIT] [CONVENTIONS.md](../../../../../../../CONVENTIONS.md).

## Assumptions & Open Questions

Open questions concern evidence to investigate, not unanswered selections in
the confirmed summary and subsequent budget instruction. See A-01–A-04,
I-01–I-04 and D-01–D-05 in the
[RAID log](raid-log.md). No adoption, production-data count, cost or recovery
capability is assumed to be established.
