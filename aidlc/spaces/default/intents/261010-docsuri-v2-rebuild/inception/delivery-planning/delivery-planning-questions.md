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

[Answer]:

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

[Answer]:

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

[Answer]:

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
