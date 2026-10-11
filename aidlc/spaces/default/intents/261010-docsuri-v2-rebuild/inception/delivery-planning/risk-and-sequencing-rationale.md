# DocSuri v2 — Risk and sequencing rationale

Date: 2026-10-11 (Asia/Seoul). Based on the human's
[confirmed Delivery Planning summary](delivery-planning-questions.md),
[risk-first scope backlog](../../ideation/scope-definition/intent-backlog.md),
[unit DAG](../units-generation/unit-of-work-dependency.md) and
[accepted Contract Design findings](../contract-design/reviews/review-01.md).

## Decision and heuristic

A **Bolt** is one build pass over a piece of work, ending in something that runs.
Use eight serial Bolts, one per approved unit, in the order
U1 → U7 → U2 → U3 → U4 → U5 → U6 → U8. The same session's coding agents do the
work; the human retains the recorded review and completion decisions.

The heuristic is **risk first**: investigate consequential uncertainty before
dependent work relies on it. This matches the user's approved priority and the
local [Workflow Planning Guide](../../../../../../../.codex/knowledge/aidlc-delivery-agent/workflow-planning-guide.md)
description of Boehm's risk-first approach. It is applied qualitatively here.
No measured cost-of-delay, duration, market value or urgency inputs exist for a
numeric ranking model. Inventing scores would disguise the uncertainty. All
current capabilities remain mandatory for the first release regardless of order.

The plan distinguishes code prerequisites from evidence prerequisites. A unit
with no code prerequisite still needs permitted inputs, current authority and
a viable resource approach before affected choices. An isolated synthetic
development task may proceed while production continuity is investigated; it
cannot choose continuity, migrate existing data or prove public-service fit.

## Why this order

| Bolt | Economic reason | Dependency constraint and proof sought |
|---|---|---|
| B01 / U1 | Expose the largest combined product risks before investing in breadth: useful understanding, acknowledged persistence, real execution and a coherent user journey within $0 | Independent root; actual browser/service/store/executor demonstration, including interruption and another account's denial |
| B02 / U7 | Expose native-platform, credential and controlled-operation constraints early enough to avoid discovering an incompatible operator tool at final integration | Independent root, scheduled after the first product demonstration; real native evidence, authority checks and durable receipts |
| B03 / U2 | Stabilize account, personal-data, consent and entitlement behavior before additional private/scheduled/external effects | Depends on U1; supplies the complete current-authority and lifecycle coordination contracts used by later units |
| B04 / U3 | Complete the corpus/retrieval/assistance foundation before research and digests consume it | Depends on U1/U2; tests actual source changes against Library, full retained modes and recoverable processing |
| B05 / U4 | Address private manuscripts, durable drafts and grounded research before exporting their artifacts | Depends on U1/U2/U3; tests privacy, restart recovery and immutable artifact identity |
| B06 / U5 | Prove scheduled delivery, late consent and uncertain sends as a bounded contribution before final composition | Depends on U1/U2/U3; no dependency on U4, but serial runtime currently walks it afterward |
| B07 / U6 | Verify explicit external-effect approval against already implemented research artifact and account authority | Depends on U1/U2/U4; U5 is not a prerequisite. This slot matches the runtime without introducing a false edge |
| B08 / U8 | Consolidate all capabilities, repairability and operational/continuity evidence once all contributors exist | Depends on every preceding unit; cumulative verification cannot substitute for each unit's earlier mounted checks |

Alternative valid orders exist: U7 could occur later before U8, and U6 could
follow U4 before U5. Early U7 better exposes operator uncertainty under the
approved risk-first stance. The selected U5/U6 order is compatible with the
runtime and avoids inventing unsupported priorities; neither is removed or
given a date. No economic claim of globally optimal scheduling is made.

All 19 DAG edges point to an earlier completed unit in this plan. The runtime's
fresh unit-major walk flattens sorted dependency levels; editing this prose
cannot override it. Any desired incompatible order requires a real routing or
approved decomposition change, never a fabricated dependency. The longest
unweighted dependency chain is U1 → U2 → U3 → U4 → U6 → U8. Time-based critical
path and effort estimates remain unavailable until discovery and measured work
supply credible inputs.

## Risk assessment and response

Likelihood and impact below are planning judgments about unresolved evidence,
not measured probabilities. Unknown means the relevant evidence has not yet been
established. Each closure trigger is tied to affected work rather than a date.

| ID | Risk | Likelihood / impact | Earliest handling and mitigation | Closure or escalation condition |
|---|---|---|---|---|
| DP-01 | Full public-service capability set cannot fit sustainable free/local resources | Unknown / Critical | B01 investigates local/model/store fit; every pass verifies its integrations and overload behavior; B08 measures the complete configuration | Actual capacity, free terms and limits, recovery and workload evidence; if incompatible, present the evidenced conflict without paid fallback or silent cuts |
| DP-02 | Unknown authoritative data or unusable backups makes continuity unsafe | Unknown / Critical | Start inventory and ownership/isolated-restore work in B01; revisit each owned data class as units land | Human-selected continuity after inventory and recoverability evidence, before any existing-data transition |
| DP-03 | Content, privacy, institutional or location obligations invalidate copying, model processing or hosting choices | Unknown / High | Resolve applicable source/data/permission facts before each affected adapter, sensitive store or public operation | Documented eligibility and handling decisions for the affected path; unresolved cases remain blocked on that path |
| DP-04 | Browser mutations silently overwrite concurrent changes | Known contract gap / High | R-01 convention in B01, specific account/personal bindings in B03 and other affected consumers as introduced | Correct wire-to-domain revision mapping plus real stale-client, missing/invalid and applicable create/null checks |
| DP-05 | Accepted work cannot safely claim payloads or reject replaced workers | Known contract gap / High | R-03 in B01 before execution implementation, then B04/B05 domain extensions | Domain claim/payload/fence definitions plus actual replacement/late-fact/duplicate tests with one result and accounting effect |
| DP-06 | Acknowledged draft survives storage but cannot be found after restart | Known contract gap / High | R-02 before B05 persistence; settle storage/retention/shared-device policy at the same affected design boundary | Empty-memory restart and authenticated owner discovery, including pre-session/job drafts, deletion/consumption/conflict and wrong-owner cases |
| DP-07 | Subtle legacy capabilities or external consumers are omitted | Medium / High | Reconcile each unit's fine-grained source/test behavior and provider modes; maintain all 70 FR rows and capability variants | Full parity and compatibility evidence in B08; disputed scope returns to the human instead of being silently dropped |
| DP-08 | Clean logical modules integrate poorly through shared UI, persistence and jobs | Medium / High | B01 proves real composition; embedded B03–B07 supply mounted checks and consistent UI; preserve single business ownership | Actual cross-boundary success/error/recovery and participant-manifest evidence; isolated unit tests alone cannot close it |
| DP-09 | Native platform assumptions fail despite portable unit tests | Medium / High | B02 validates the retained actual command/platform matrix and safe fixture behavior | Native filesystem/credential/authority evidence; incompatible targets remain unsupported pending explicit resolution |
| DP-10 | Existing CI failures conceal new regressions or create false confidence | Known baseline failures / High | Use changed-work verification and exact-base comparison under CONVENTIONS.md; retain failed/skipped/unreached results; later CI Pipeline owns replacement checks | Reproducible v2 checks and a separately approved cumulative command; legacy failure matching does not establish readiness |
| DP-11 | One maintainer cannot reproduce or repair the resulting service | Medium / High | Each pass documents ownership, setup and failure evidence; B08 performs clean-checkout diagnosis/repair with regression checks | Repeated documented maintainer procedure using observed results; no ungrounded time-to-repair target |

The current legacy CI comparison is recorded in
[develop integration evidence](../../maintenance/develop-integration.md#approved-contract-design-branch-integration).
Its 11 failures matched the exact base. That supports the interim merge decision,
not claims that the implementation or security checks passed.

## Contract findings: closure responsibility

These IDs are scoped to **Contract Design review-01**, not the earlier Domain
Design review whose R-01/R-02 concern different interfaces. Acceptance permits
continuing the lifecycle with these tasks explicit; it does not supply missing
interfaces or waive their requirements. Detailed corrections must follow the
applicable design/contract change process and update affected producers and
consumers coherently, rather than silently altering the approved baseline.

| Finding | Design/implementation responsibility | Evidence needed before claiming affected behavior complete |
|---|---|---|
| Contract R-01 | B01 host/C13 convention; B03 AccountAccess/Library/Personalization/UsageEntitlements bindings; each later affected domain | Reconcile all affected HTTP/internal shapes. Keep identity server-derived, carry the browser-observed revision, define missing/invalid/create/null behavior, and prove that the stale second writer cannot overwrite the first |
| Contract R-02 | B05 ResearchWorkspace, using B01 host and B03 current-authority/lifecycle interfaces | Allocate and rediscover owner/context/kind identity without remembered browser IDs; only acknowledged retained unconsumed owner drafts recover; failed saves never promise recovery and restore never auto-submits |
| Contract R-03 | B01 PaperAssistance and execution adapter; B04 full paper variants; B05 ResearchWorkspace variants | Domain-issued acquire/renew/reclaim and payload binding; progress/failure/success share current fencing; old-worker and duplicate facts cannot bypass C06/C07 authority through C14 |

B08 repeats full integrated cases. It is not the first implementation of these
corrections. Earlier Domain Design projection-writer and immutable export-binding
clarifications are specified in Contract Design but still need implementation
evidence in B04 and B05/B07 respectively. Do not confuse specification closure
with runtime closure.

## Scope metrics, coordination and unresolved decisions

The decomposition retains eight units, 13 components, 42 entity shapes, 20
capability groups, 70 functional IDs, ten NFRs and nine evidence backlog outcomes.
Those are planning/inventory counts, not completed implementations. Source
authority and coverage limits remain those of the approved reverse-engineering
and requirements artifacts. The
[requirement map](../units-generation/unit-of-work-story-map.md) controls
parent/child and cross-unit acceptance; [allocation](team-allocation.md) controls
who prepares the evidence, while domain owners control data and operations.

Shared source/configuration changes need explicit file responsibility and
compatible producer/consumer updates. Initial U1 interfaces cannot import future
feature implementations merely to satisfy the initial journey. Later modules
register their participation; final composition verifies the whole manifest.

The [external dependency map](external-dependency-map.md) identifies unknown
lead times, owners, blocked work and fallback handling. No fixed dates, stack,
hosting, migration, retention periods or numeric targets are selected here.
Measure the baseline and estimate remaining effort after discovery; public
provider evidence and a local-only test result must remain distinguishable.

## Replanning and success criteria

Revisit the affected plan if evidence reveals a true new code dependency, an
unaffordable or impermissible retained path, an authoritative data/consumer
conflict, or failure of a Bolt's confidence hypothesis. Record the observed
constraint, affected requirements, alternatives and consequences; seek the
human's scope/policy decision where required. Independent authorized work may
continue, but no blocked mandatory behavior is declared complete.

This stage chooses no new lifecycle stages or approval cadence. The recorded
unit-major/serial execution and review points remain. Its verification command
is explicitly deferred until a runnable v2 check exists; the exact command
requires separate human approval before checkpoint verification.

Success means all retained capabilities and agreed quality/continuity obligations
are demonstrated in the implemented service, with repeatable recovery and repair
within sustainable $0 limits. The current
[Inception phase check](../../verification/phase-check-inception.md) establishes
only planning traceability. Delivery Planning approval, a CI comparison or a
document commit cannot establish that final outcome. Completed branches merge
through develop PRs under CONVENTIONS.md; main promotion and deployment retain
their separate applicable decisions.
