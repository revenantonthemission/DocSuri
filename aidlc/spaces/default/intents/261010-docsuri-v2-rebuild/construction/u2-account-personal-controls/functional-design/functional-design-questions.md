# DocSuri v2 — U2 Functional Design proposal

Date: 2026-10-13 (Asia/Seoul).
Unit: `u2-account-personal-controls`.

## Context and carried-forward decisions

The resumed workflow selects U2 Functional Design. The local integration branch
contains U1 in commit `1c2cbd5c` (PR #44) and U7 in `5fbccc1f` (PR #45).
This proposal starts from that existing assembly. Those merge records do not
establish full product parity or close the limitations in the unit evidence.
In particular, U1 records unavailable normal assistance output and an unmounted
semantic-search mode; U2 must not claim that its account work resolves them.

The approved unit catalogue assigns U2 the completion of AccountAccess,
Personalization, Library and UsageEntitlements, with their WebWorkspace views.
The shared component owners remain authoritative. U2 is an embedded contribution
to the same application, not another account service or duplicate data store.
U7's operator identity and permissions remain independent of application roles.

The existing question records and U2-scoped answer history were checked. No U2
Functional Design answer is recorded. Earlier answers already establish:

- A multi-user web service with public registration and existing anonymous
  search, retaining every current capability for the first v2 release.
- A $0 budget, free/local choices, one human maintainer with coding agents,
  serial construction, and automatic ordinary completion checkpoints.
- A Korean responsive workspace with inherited blue/neutral colors, Apple HIG
  web adaptations, Light/Dark/System and the WCAG 2.2 AA target.
- Evidence-dependent continuity, retention, provider and capacity decisions;
  numeric quality targets follow baseline measurement and human agreement.
- CONVENTIONS.md governs Git: working branch through a PR into develop;
  fulfilled branches merge, and release promotion to main remains separate.

## Proposed design coverage

| Area | Functional design responsibility |
|---|---|
| Account entry and credentials | Registration, verification/resend, login/logout, password reset/change and email change; purpose-bound challenge states, safe replay, failed delivery, credential/session revocation and preservation of committed saved work. |
| External identities and administration | Google/ORCID sign-in/link/unlink and supported profile access, collision and callback replay handling, administrator MFA enrollment/verification and controlled recovery. Recovery and incomplete primary authentication never grant a full session. |
| Profile and consent | Retained field vocabulary, owner/revision-bound updates, current consent authority and processing boundaries. A delayed consumer or failed cleanup cannot re-enable revoked permission. |
| Account lifecycle | Separate access withdrawal, permitted reactivation and permanent erasure; model policy references, required participants, scoped acknowledgements, pending/failed work, backup/restore dispositions and proof-bound recovery. Completion requires evidence for every required scope. |
| Library and history | Add/list/remove saved papers and searches, explicit rerun, owner-bound pagination, source/canonical dispositions, concurrency and history clear. Pre-clear searches finishing later cannot recreate cleared history. |
| Personalization and onboarding | Explicit defaults versus derived profiles, recent-paper ordering, opt-out/reset/event deletion boundaries, resumable interest selection/skip and optional attributable ORCID suggestions. Keep library data separate. |
| Usage and plans | Truthful mock/administrative plan display, authorized grant/revoke, current allocation and usage inspection, reservation/settlement/reconciliation, and explicit period/reset/refund policies. Unknown accounting is not zero; no paid resource activation. |
| Shared browser behavior | Coherent account/settings/library/admin views, current-owner context, visible conflicts and uncertain writes, permission changes across tabs, safe return after sign-in, focus/status/error behavior and responsive reflow. |

Trace every U2 assignment and contribution in the requirement-to-unit map.
Distinguish U2's own closure evidence from later consumer integration: U3 owns
complete corpus/canonicalization and assistance behavior; U4 owns research and
durable drafts; U5/U6 own digest/export effects; U8 verifies the full assembly.
Do not create reverse construction dependencies to claim premature parity.

## Current evidence and unresolved policy boundaries

The current C02/C03/C13 contracts already require named operations, current
owner authority, browser revision preconditions, safe conflict recovery,
purpose-bound MFA/reactivation flows and complete lifecycle participant evidence.
They are the starting point; any necessary changes must be coordinated with the
canonical contract and consumers before implementation.

A bounded source check found a 30-day default in the legacy account-deletion
service and separate withdrawal/reactivation/purge behavior. This is evidence
of an old implementation default, not a selected v2 retention policy or proof of
the deployed service. The v2 contract requires explicit recovery proofs and
policy-bound restoration; the design must not inherit legacy shortcuts.

Keep these prerequisites explicit, with responsible owner and closure evidence:

- Authoritative users/data, continuity and recoverable backups before any
  migration or claim that existing data can be restored.
- Per-data-class retention, erasure, reactivation and backup treatment, including
  permitted processing and later draft participants, before affected persistence
  or lifecycle enablement. No duration or lawful-retention conclusion is selected
  by this proposal. Missing policy yields a truthful unavailable operation, which
  does not satisfy release capability parity.
- Sustainable public email, Google/ORCID integration, MFA recovery procedure,
  abuse limits and provider terms before public acceptance. A local email sink
  or controlled provider fixture establishes only its limited test path.
- Finite quota/allocation, reset zone, period transition, refund and pending-work
  policies before enforcement; no arbitrary public-service values or unlimited
  fallback. Preserve the original period for accepted-work reconciliation.

The logical design can specify explicit policy inputs and refusal/recovery
states without choosing these unresolved values. If a workflow cannot be
described coherently without a new product decision, ask that focused question
before generating the affected design. No additional interview is needed for
the already-approved component boundaries and contract semantics above.

## Corner-case and validation plan

Sweep each U2 component against malformed/oversized/Unicode inputs, empty and
paginated states, duplicate and stale submissions, concurrent tabs, account
switch/revocation, expired or replayed challenges, provider failure, lost write
acknowledgements, delayed events, interrupted cleanup, restored old snapshots,
and resource/period boundaries. Distinguish failures, unknown effects and
confirmed completion. Do not log secrets or private input.

Produce entities.md and rules.md with authoritative YAML, functional-spec.md
with ordered workflows/state machines and derived diagrams, frontend-components.md
for the embedded UI contributions, and traceability.json. Check identifiers,
ownership, canonical bindings, transitions, dependency direction and requirement
coverage, validate diagrams/escaping, and obtain an independent architecture
review. This stage changes design records, not application behavior or user data.

## Sources

- [UC] [Unit catalogue](../../../inception/units-generation/unit-of-work.md), U2 and component responsibilities.
- [UM] [Requirement-to-unit map](../../../inception/units-generation/unit-of-work-story-map.md), all rows naming U2 and applicable NFRs.
- [RQ] [Requirements](../../../inception/requirements-analysis/requirements.md), especially FR5–FR8, FR10–FR11, FR17 and open policy dependencies.
- [DC] [Component catalogue](../../../inception/domain-design/components.md), AccountAccess, Personalization, Library, UsageEntitlements and lifecycle rules.
- [CT] [Canonical contracts](../../../inception/contract-design/contract-summary.md), C01–C03, C12–C14 and open questions.
- [UX] [Interaction specification](../../../inception/refined-mockups/interaction-spec.md) and [design mapping](../../../inception/refined-mockups/design-system-mapping.md).
- [U1] [U1 code evidence](../../u1-integrated-paper-journey/code-generation/code-summary.md), implemented assembly and carried limitations; historical UNSET/completion wording is not current workflow state.
- [U7] [U7 code evidence](../../u7-controlled-platform-protocols/code-generation/code-summary.md), independent operator boundary and carried limitations; current completion is recorded separately by the workflow.
- [SRC] backend/modules/accounts/services/account_deletion.py:35,154–265. Tier 2 graph/source check, project Users-revenantonthemission-Projects-DocSuri, generation 2026-10-13T10:35:46Z; metadata matched with no recorded gap. This bounded check is not an exhaustive parity or deployed-state audit.
- [Git] CONVENTIONS.md and current local Git history; no main promotion is authorized by this design step.

## Consolidated Summary Confirmation

- Define U2's account and personal controls within the existing application and
  approved owners: accounts, identities/MFA, profile/consent, library/history,
  personalization/onboarding and usage/plan administration. Retain every current
  capability and the $0 free/local constraint.
- Specify complete credential and recovery flows, current owner/session checks,
  protected challenges, callback/replay handling and administrator boundaries.
  Application administration does not confer U7 operator authority.
- Model withdrawal, reactivation and erasure as distinct outcomes. Track every
  required participant and backup/restore obligation; restore only demonstrably
  retained permissible data and never call partial cleanup complete.
- Keep explicit saves, history, preferences and derived behavior separate.
  Clear/reset/consent boundaries must resist delayed events; conflicts and lost
  acknowledgements must preserve committed work and show the actual outcome.
- Define quota inspection, grants/revocation and one intended accounting effect,
  including unknown outcomes and period transitions. Preserve mock plan
  presentation without introducing billing or paid resource activation.
- Extend the approved Korean responsive workspace, inherited colors, Apple HIG
  adaptations, appearance modes and accessibility target across the account,
  settings, library and administration flows. Preserve context safely across
  sign-in, interruption and account changes.
- Keep retention/reactivation periods, authoritative-data continuity, provider
  delivery, MFA recovery, public capacity and quota policy as explicit evidence
  prerequisites. Do not adopt the legacy 30-day default without a separate
  supported decision. Preserve U1's recorded assistance/search limitations;
  full parity still requires later consumer and U8 integration evidence.
- Produce entity/rule models, behavioral and frontend specifications and U2
  traceability, check consistency and obtain independent architecture review.
  Continue serially with automatic ordinary completion and the existing human
  decision points. Merge completed branches through PRs into develop under
  CONVENTIONS.md; main promotion remains separate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]:
