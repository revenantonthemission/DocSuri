# DocSuri v2 — U1 Functional Design plan and confirmation

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`.
Conversation language: English. Answer mode: Guide me, carried forward.

## Context and established answers

Delivery Planning is approved and merged into develop through PR #39. The human
then selected **Continue automatically** for ordinary Construction completion
checkpoints. This preserves enabled summary and plan confirmations, separate
verification-command approval, required checks and failure stops. Execution
remains serial and unit-major; no separate walking-skeleton ceremony is added.

All eleven preceding stage question files were read with their questions and
answers. The later $0 budget, inherited blue/neutral palette, CONVENTIONS.md Git
flow and automatic-completion choice supersede only their earlier conflicting
statements. No new ordinary interview question is needed for this logical design.
The proposals below elaborate settled outcomes; they do not select a stack or
pretend unresolved operating evidence has been collected.

| Topic | Inherited decision | U1 consequence |
|---|---|---|
| Release scope | All current capabilities remain required; eight approved units | U1 demonstrates the whole paper journey while later units finish retained variants and full parity |
| Demonstration | P1 Transformer and P2 retrieval-augmented generation tasks; real boundaries and permitted fixtures | Research-query discovery, useful source-bound understanding, saved paper/query and fresh authenticated revisit; no mocked answer or no-op dispatch as completion evidence |
| Composition | One shared application; 13 authoritative components; U7 separately controlled | Define U1 slices and host registration without duplicating business owners or importing future implementations |
| Access | Public registration, current anonymous search, private owner isolation, separate administrator/operator authority | Explicit actor/state matrix and current checks at reads, admission and effects; no broader guest entitlement inferred |
| Recovery | Acknowledged saves, recoverable accepted work and prepared-result reads remain distinct | Lost responses reconcile the same logical operation; reads never start work; stale responses and replaced workers cannot overwrite authoritative state |
| Presentation | Korean UI, desktop-first complete responsive experience, inherited colors, Apple HIG web adaptations, Light/Dark/System, WCAG 2.2 AA target | One coherent workspace with retained context, accessible feedback and bounded failures |
| Resources and continuity | $0 free/local only; one human maintainer; no fixed deadline; evidence before affected choices | No paid fallback, invented operating limits, migration/reset or readiness claim |
| Git | Working branch → PR into develop; completed branches merged and removed; main promoted separately | Continue on `docs/docsuri-v2-u1-functional-design` from the completed Delivery Planning merge |

## Proposed design work

Specify technology-independent logical entities, rules and ordered workflows for
the U1 contribution within AccountAccess, CorpusContent, Personalization,
Discovery, Library, UsageEntitlements, PaperAssistance, ServiceOperations and
WebWorkspace. Preserve the domain catalogue's ownership; supporting value shapes
and execution metadata do not become competing business authorities.

Describe the complete synthetic-account and permitted-public-paper demonstration:
registration/verification and safe entry, research-query search, identified
paper/version reading and assistance, acknowledged paper/query save, logout or
restart, fresh authentication and revisit. Include a supported translation check
from the representative acceptance procedure; keep the remaining action, level,
language and provider variants assigned to later units. Reading a prepared result
must use its original owner, operation and paper/version binding without starting
another job. Existing users/data are not altered to make this demonstration run.

Keep browser form values separate from the submitted search context and request
identity. Reject stale responses, preserve query/filter controls during loading,
empty and error states, identify changed pagination snapshots, and distinguish
partial/fallback results from complete normal results. Reauthentication restores
only authorized context and never automatically replays a mutation.

Elaborate Contract R-01 with a concrete browser revision-precondition convention
and trusted mapping into the internal command context. Specify missing, invalid,
stale, creation and replay behavior, current-owner checks and visible conflict
recovery. Coordinate the affected formal contract bindings before implementation;
do not leave a contradictory parallel browser contract in this unit's prose.

Elaborate Contract R-03 with domain-owned execution claims, protected payload
retrieval, renewal/expiry/replacement and fencing. Bind a claim to the logical
operation, immutable intended input and current attempt. Accepted work retains a
durable execution obligation; only a current authorized claim may publish a
result or settle its accounting effect. Duplicate or late replaced-worker facts
cannot duplicate effects or regress authoritative state. Recheck current account,
consent and source eligibility at the relevant effect boundary. Transport delivery
and operational observation never become alternative business-state authorities.

Specify job acceptance, progress, success, failure, result expiry and unknown-
outcome reconciliation separately. Apply cancellation/revocation only where the
owning operation and existing lifecycle contract support it; generic shared
vocabulary does not add a new user-facing paper-job cancellation feature.
Connection loss or closing a view does not cancel accepted work. Where supported,
a confirmed cancellation prevents later effects; a cancellation request alone
does not claim that outcome. Explicit new work uses a new logical identity while
uncertain submission recovers its original receipt.

Describe minimal real-host registration, installed lifecycle participants and
truthful capability reporting. Include only participants actually present, require
new owners to join before they persist data, and never claim complete deletion or
healthy capabilities from missing contributions. Keep account revocation separate
from policy-dependent cleanup and recovery.

## Corner analysis

| Applicable surface | Disposition to specify and verify later |
|---|---|
| Text, parsed content, paths and assets | Server-validated empty/Unicode/oversized or malformed input, safe rendering, bounded parsing, exact identity/version and eligible asset access; no path escape or private orphan publication |
| Lists and search state | Empty versus failed versus degraded outcomes, stable ordering/cursors, source changes, duplicates, current submitted context and late-response rejection |
| Storage and concurrent mutation | Acknowledgement follows durable commit, prior committed state survives failed writes, ambiguous outcomes reconcile, stale revisions conflict without silent overwrite |
| Jobs, time and resources | Trusted time/expiry boundaries, monotonic state/attempt ordering, bounded admission, explicit unknown versus zero, recoverable dispatch, stale-claim fencing and one accounting effect |
| Identity and lifecycle | Public-entry versus owner access, session expiry/revocation, same-owner authenticated return, account-switch isolation, owner acknowledgements and policy-dependent cleanup |
| AI and external dependencies | Permitted source/input binding, validated useful output, explicit unsupported/insufficient/unavailable states, hostile content treated as evidence only, no fabricated successful model result |
| Screens and interaction | Retained context, precise start/read/retry labels, visible save states, meaningful announcements, keyboard/focus recovery, responsive long-content reflow and all appearance modes |
| Configuration and operations | Required capability/policy missing is explicit, finite configuration requirements, safe correlation, reproducible fixtures and repair evidence; liveness alone is not readiness |

The generic corner checklist is adapted to this product: records without a
verified private owner are rejected or quarantined for controlled maintenance,
never displayed in a public unattributed bucket. Durable research/manuscript
drafts and their restart rediscovery remain U4 work; U1 adds no research composer
solely for this demonstration. Contract R-02 stays assigned there before affected
persistence. This does not weaken the approved draft-recovery commitment.

## Artifacts and traceability

After confirmation, produce `entities.md` and `rules.md` with their authoritative
YAML models, `functional-spec.md` with authoritative workflows/state machines and
derived entity/rule views, `frontend-components.md` for U1's actual UI contribution,
and `traceability.json`. The unit map names U1 as a partial contributor on 29 FR
rows: eight parent rollups and 21 subrequirements. Use those stable upstream FR
IDs and their actual acceptance-text locators; User Stories was skipped, so do
not invent approved upstream AC IDs. Local design/check IDs may decompose compound
criteria but must be labeled local. Distinguish U1 design coverage from later-
unit full requirement closure, and separately retain all applicable NFR/evidence
obligations.

Validate internal references, model/rule consistency, Mermaid syntax, ownership
and traceability, then obtain the required independent architecture review. A
proposed resolution or document check does not close the three accepted contract
findings' required executable evidence. U1 prepares R-01/R-03; U2 and subsequent
consumers complete their bindings, U4 resolves R-02, and U8 repeats cumulative checks.

## Assumptions & Open Questions

No additional human product choice is required to write the logical design.
The following evidence remains open and blocks the affected choice or behavior:
authoritative users/data and recoverable backups before continuity; source and
model permissions before processing; retention/deletion/shared-device obligations
before affected persistence; available free/local capacity, sustainable public
email and provider behavior before claiming those paths; measured baseline before
numeric quality targets. A finite approved admission/timeout/retry policy is
required before enabling each affected operation; the design will not invent its
values. Technology, hosting, physical schemas, migration and schedule remain open.

The construction verification command stays unset until a runnable cumulative
v2 check exists and the human approves its exact invocation. Automatic ordinary
completion does not bypass that decision or evidence prerequisites.

## Sources

- [Intent answers](../../../ideation/intent-capture/intent-capture-questions.md),
  [feasibility answers](../../../ideation/feasibility/feasibility-questions.md),
  [scope answers](../../../ideation/scope-definition/scope-definition-questions.md)
  and the approved handoff, rescan and requirements question records.
- [Requirements and P1/P2 procedure](../../../inception/requirements-analysis/requirements.md).
- [Unit catalogue](../../../inception/units-generation/unit-of-work.md),
  [requirement map](../../../inception/units-generation/unit-of-work-story-map.md)
  and [domain owners](../../../inception/domain-design/components.md).
- [Contracts](../../../inception/contract-design/contract-summary.md) and their
  [accepted review](../../../inception/contract-design/reviews/review-01.md).
- [Interaction specification](../../../inception/refined-mockups/interaction-spec.md),
  [design mapping](../../../inception/refined-mockups/design-system-mapping.md)
  and their approved question records.
- [Delivery plan](../../../inception/delivery-planning/bolt-plan.md) and
  [delivery answers](../../../inception/delivery-planning/delivery-planning-questions.md).
- Human choice on 2026-10-11: Continue automatically; recorded by the Construction
  autonomy setter. [Integration evidence](../../../maintenance/develop-integration.md).

## Consolidated Summary Confirmation

- Define U1's logical entities, rules and workflows for a real find → understand
  → save → revisit demonstration with synthetic accounts, eligible P1/P2 papers,
  useful source-bound assistance, a supported translation check, real persistence
  and fresh authenticated return. All current capabilities remain required across
  the eight units; U1 is the first complete journey, not the release boundary.
- Keep the approved component owners and one shared application. Specify the
  necessary account, corpus, discovery, library, usage, assistance, presentation
  and operations slices without duplicating stores or depending on future modules.
- Preserve public registration and existing anonymous search; enforce current
  owner/session/source checks. Separate reading, explicit work submission,
  acknowledged saves and new execution. Keep context through reauthentication
  without silently replaying actions or exposing another account's work.
- Resolve the U1 design portions of browser revision preconditions and worker
  claims/payload retrieval/fencing. Specify stale-client conflict and replaced-
  worker rejection, durable acceptance, ordered recovery and one intended result/
  accounting effect. Update affected contract bindings coherently before code;
  later executable checks are still required to close the findings.
- Cover malformed input, empty/degraded/error states, failed or uncertain writes,
  duplicate requests, concurrent tabs, interruption, supported cancellation/
  revocation and expiry, without adding a new paper-job action.
  Keep query controls visible and prepared-result reads free of new work.
- Carry the approved responsive Korean workspace, inherited colors, Apple HIG
  web adaptations, Light/Dark/System and WCAG 2.2 AA target into component and
  interaction specifications. Durable research drafts remain assigned to U4.
- Produce entity/rule models, behavioral and frontend specifications and honest
  U1 requirement traceability, validate consistency and obtain an independent
  architecture review. Design checks do not establish working application parity.
- Keep the $0 free/local constraint and all evidence prerequisites explicit.
  Stack, hosting, continuity, retention and numeric limits/targets remain subject
  to their required evidence and decisions. Continue serially with automatic
  ordinary completion; still ask for enabled summaries, plans, the exact runnable
  verification command and failures. Merge completed branches through PRs into
  develop under CONVENTIONS.md; main promotion remains separate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]:
