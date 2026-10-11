# DocSuri v2 — Delivery Planning questions

Date: 2026-10-11 (Asia/Seoul). Mode: Guide me, carried forward from Intent Capture.
Contract Design was approved with three Major findings accepted, and its branch
was merged through [PR #38](https://github.com/revenantonthemission/DocSuri/pull/38)
into develop. This stage plans construction; it does not certify implementation
readiness or resolve the accepted findings by recording them.

## Established decisions

| Topic | Existing answer or evidence | Planning consequence |
|---|---|---|
| Priority | Approved Scope Definition: risk first | Resolve free/local capacity, user/data continuity and recovery uncertainties before affected choices; prove the complete paper journey and then finish all remaining parity |
| Scope | Approved requirements and eight-unit decomposition | Retain all 20 capability groups and 70 functional requirement IDs; the first paper demonstration is not the complete release |
| Capacity and cost | One human maintainer with coding agents; $0; no fixed deadline | Free or local choices only; estimate effort after discovery rather than inventing dates, paid fallback or extra human teams |
| Construction order | Recorded checkpoints enabled, unit-major, serial | Complete each unit's applicable designs and code serially, with its verified completion checkpoint; no parallel execution is inferred |
| Unit boundaries | Eight units, 19 dependency edges; U1 and U7 are independent roots | Preserve approved ownership and actual prerequisites; do not add false edges just to force a preferred order |
| First working result | U1 integrated paper journey | Demonstrate find → understand → save → revisit with actual permitted processing, persistence, owner checks and recovery; the approved plan adds no separate walking-skeleton ceremony |
| External commitments | No known commitments beyond retained product capabilities; actual dependencies and consumers remain to be verified | Track source/model/email/identity/export integrations, local capacity and existing data with owners, affected work and closure evidence; unknown lead times remain unknown |
| Primary concerns | Stable, smooth use, understandable and repairable code; approved risk-first scope | Treat capacity, continuity, recoverable work and the three contract findings as explicit planning dependencies |
| Git | CONVENTIONS.md and the user's interim CI instruction | Merge completed working branches through PRs into develop, delete them and start fresh branches; compare legacy CI failures to the exact base; main promotion stays separate |

The proposed ranking method is a qualitative risk-first argument using the
approved priorities and dependency constraints. No fabricated numeric value,
urgency or duration scores are needed. The consolidated summary will make this
proposal explicit before artifact generation.

## Q1 — Size of a build pass

For Delivery Planning, a **Bolt** is one build pass over a piece of work, ending
in something that runs. How large should each Bolt be? The eight approved units
and their dependencies stay intact; this choice sets the planning grouping, and
recorded execution remains one unit at a time and serial.

- A. One approved unit per Bolt (Recommended): eight reviewable build passes,
  each with a runnable demonstration and a clear completion boundary.
- B. Bundle related units into fewer Bolts: larger planning milestones spanning
  several serial unit checkpoints.
- C. Plan thin slices across units: smaller cross-feature milestones requiring
  reconciliation with the approved unit boundaries and runtime order.
- X. Other: describe the grouping you prefer.

[Answer]: One approved unit per Bolt (Recommended): eight build passes, each with a runnable demonstration and clear completion boundary.

## Q2 — Construction staffing

How do you want to staff Construction? I can run the work from this session
using the execution settings you chose, or each of your teams can own a Unit
and approve its work independently. You previously planned for one human
maintainer with coding agents.

- A. Run from this session (Recommended): coding agents perform the work here;
  you remain the sole approver at the recorded review points.
- B. Independently owned team units: identify teams that own units and approve
  their work independently; define ownership and check-in rhythm before starting.
- X. Other: describe how you want responsibility assigned.

[Answer]: Run from this session (Recommended): coding agents perform the work here; you remain the sole approver at the recorded review points.

## Q3 — Selecting the construction verification command

The v2 implementation and its integrated verification command are not defined
yet. The existing contract validator checks documents, and legacy CI does not
prove a working v2 unit. When should we select the command that verifies each
completed unit and the cumulative working application?

- A. Defer until a runnable v2 check exists (Recommended): keep the command
  unset now; present the exact command for your approval before the first unit
  completion checkpoint runs verification. This does not waive any check.
- B. Propose a candidate now: provide a real existing command or test entrypoint
  to evaluate; selection still needs a separate exact-command approval.
- X. Other: describe a verification approach or constraint.

[Answer]: Defer until a runnable v2 check exists (Recommended): leave the command unset now and approve the exact command before the first unit completion checkpoint runs verification.

## Accepted contract findings to carry into the plan

These are unresolved follow-ups from the approved
[architecture review](../contract-design/reviews/review-01.md), not new scope
or fixes claimed by this planning document.

- R-01: specify browser-supplied revision preconditions and their server mapping
  before affected mutation bindings are implemented. Preserve server-derived
  identity and verify concurrent stale-client conflict behavior.
- R-02: make acknowledged owner-bound drafts discoverable after restart,
  including drafts created before a research session or novelty job. Resolve
  identity allocation and required retention/shared-device policy before the
  affected research implementation; verify recovery without in-memory IDs.
- R-03: define domain-owned worker claims, payload retrieval and fencing before
  the initial accepted-work executor path. Verify replacement workers, late
  old-worker facts and duplicate delivery without duplicate effects.

Delivery Planning will assign earliest affected units, responsible component
owners and closure evidence. Integration at U8 repeats the relevant checks; it
must not become the first point at which earlier units' required behavior works.

## Sources and next step

- [Requirements](../requirements-analysis/requirements.md) and
  [approved mockups](../refined-mockups/mockups.md).
- [Component ownership](../domain-design/components.md).
- [Unit catalogue](../units-generation/unit-of-work.md),
  [dependency graph](../units-generation/unit-of-work-dependency.md) and
  [requirement mapping](../units-generation/unit-of-work-story-map.md).
- [Contracts](../contract-design/contract-summary.md) and their accepted review.
- [Approved scope](../../ideation/scope-definition/scope-document.md) and
  [evidence backlog](../../ideation/scope-definition/intent-backlog.md).
- [Branch integration evidence](../../maintenance/develop-integration.md).

After these answers, present one consolidated planning summary for confirmation
before generating the delivery plan, responsibility allocation, sequencing
rationale and external dependency map. Traceability at the Inception boundary
will be checked separately; a coverage pass cannot close a contract defect or
an operating-feasibility evidence gap.

## Answer analysis and proposed sequence

The three human answers are consistent with the existing eight-unit grouping,
one-maintainer model and recorded unit-major/serial settings. Single-session
staffing preserves the default solo unit ownership and existing review points;
it does not authorize automatic approval. The verification command remains
unset. Deferral is explicit, not approval of a placeholder or a waiver of checks.

The proposed order is U1 → U7 → U2 → U3 → U4 → U5 → U6 → U8. It respects all
19 dependency edges and the current runtime's fresh serial walk. U1 provides the
first complete paper demonstration; early U7 exposes controlled-operator and
native-platform constraints before completing the remaining application breadth.
The two roots remain independent. Account/personal controls then supply the
authority needed for full corpus, research, digest and export contributions;
U8 consolidates full integration. This economic rationale uses the approved
risk-first priority without invented numeric scores or a calendar commitment.

| Build pass | Approved unit | Expected working outcome to detail in the plan |
|---|---|---|
| B01 | U1 — integrated paper journey | Real find → understand → save → revisit with persistence, current owner checks and recoverable accepted work |
| B02 | U7 — controlled platform protocols | Independently executable operator protocols with separate authority and truthful, recoverable receipts |
| B03 | U2 — account and personal controls | Complete retained account, library, preferences and usage controls through the shared application |
| B04 | U3 — paper/corpus capabilities | Complete retained corpus, retrieval, citation and paper-assistance behavior through the real application |
| B05 | U4 — research and novelty | Private research, manuscripts, acknowledged drafts and novelty with owner-bound recovery |
| B06 | U5 — topics and digests | Topic subscriptions and digest delivery with current consent and interrupted-send reconciliation |
| B07 | U6 — approved export | Explicitly approved Notion export bound to the exact artifact revision and destination |
| B08 | U8 — service operations and integration | Complete application, capability parity and cumulative recovery, resource and maintainer evidence |

Read-only runtime verification on 2026-10-11 called the actual `parseBoltDag`
against the approved dependency document. It returned dependency groups
`[[U1,U7],[U2],[U3],[U4,U5],[U6],[U8]]`.
`.codex/tools/aidlc-orchestrate.ts` flattens those groups in
`emitUnitMajorRunStage` (lines 11615–11664) and `unitMajorWalkStep`
(lines 10959–10981) walks each unit's active stages and checkpoint.
This establishes fresh order, not a promise about resuming explicitly set-aside
or already-running work. A planning-file reorder alone cannot change the runtime
walk, and no false dependency has been added to force the proposal.

## Consolidated Summary Confirmation

- Plan eight Bolts, each one build pass over an approved unit ending in a
  working demonstration. Use the proposed serial order: integrated paper
  journey → controlled platform protocols → account/personal controls → full
  paper/corpus capabilities → research/novelty → topics/digests → approved
  export → complete operations/integration. Preserve the approved dependency
  graph and one shared application plus the separately controlled operator tool.
- Run Construction from this session with coding agents and one human
  maintainer. You remain the sole approver. Keep one unit's applicable designs,
  implementation and completion checkpoint together before the next unit;
  retain the existing review points and add no separate walking-skeleton ceremony.
- Follow the approved risk-first priorities. Resolve evidence prerequisites
  before affected decisions, prove the real paper journey first, then finish
  every retained capability. Define each pass's completion conditions, expected
  demonstration, what it will prove and responsibility; use qualitative
  rationale rather than invented numeric scores or dates.
- Carry the three accepted contract findings into their earliest affected work:
  browser revision conventions and worker claims/payload/fencing in U1,
  completed affected browser bindings in U2 and later consumers, and draft
  allocation/rediscovery before U4 persistence. Require executable closure
  evidence and cumulative checks in U8; approval did not fix these findings.
- Leave the construction verification command unset until a runnable v2 check
  exists. Present its exact invocation for your separate approval before the
  first completion checkpoint runs verification. Document validation and legacy
  CI cannot substitute for the cumulative working-application check.
- Keep all current capabilities, the $0 free/local budget, one-maintainer model
  and no fixed deadline. Preserve public registration, account isolation, the
  approved Korean interface, inherited colors, Apple HIG web adaptations,
  responsive layouts, appearance modes and accessibility target.
- Map integrations, authoritative users/data, backups, permitted processing,
  retention/shared-device rules and free/local capacity to affected work,
  responsible owners and closure evidence. Verify unknown lead times rather
  than inventing them. Stack, hosting, migration and numeric quality targets
  remain evidence-dependent; no paid fallback or silent feature removal.
- Produce the delivery plan, responsibility allocation, sequencing rationale,
  external dependency map and Inception traceability check. Coverage checks
  establish planning consistency, not implementation readiness. Follow
  CONVENTIONS.md: merge completed branches through PRs into develop under the
  interim CI policy; release promotion to main remains separate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
