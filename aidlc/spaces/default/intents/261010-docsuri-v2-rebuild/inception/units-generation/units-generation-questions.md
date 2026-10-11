# DocSuri v2 — Units Generation questions and proposed plan

Date: 2026-10-11 (Asia/Seoul). Status: proposed decomposition; awaiting plan approval.

## Existing decisions and evidence

The user approved Domain Design, including its two Minor review findings, on
2026-10-11. [Components](../domain-design/components.md),
[architecture decisions](../domain-design/decisions.md) and
[requirements](../requirements-analysis/requirements.md) constrain this plan.
The approval is recorded in the workflow audit; proposal wording retained in
the reviewed documents does not supersede that decision.

Retain all 20 capability groups and 50 functional subrequirements, with the
paper journey as the first complete product demonstration. Keep the $0 free/local
budget, one human maintainer supported by agents, risk-first evidence work,
public registration, account isolation and the approved integrated Korean web
experience. New feature expansion remains deferred. The
[scope backlog](../../ideation/scope-definition/intent-backlog.md) remains the
source of evidence obligations; a unit assignment does not close them.

The approved 13 components own their entities and business rules. Construction
units are bounded increments within those components: they do not create new
owners for the same account, paper, job or draft. No new product-policy answer is
needed to prepare this proposal. The grouping, unit kinds and granularity below
are new architectural choices for the user to confirm.

## Proposed grouping and deployment model

Recommend eight construction units, with one shared application release and a
separate controlled operator executable. Preserve the 13 internal code
boundaries. This is not a choice of language, framework, vendor, host, physical
store count or worker/process placement. Resource-intensive work may need a
separate execution process within the application release if later measurements
support it; no such arrangement is assumed proven here.

| Unit ID | Directory | Proposed kind | Boundary and delivered outcome | Deployment model |
|---|---|---|---|---|
| U1 | u1-integrated-paper-journey | service | Runnable application foundation: find, read/understand, save and revisit a paper, with real persistence, current owner checks, recoverable accepted work, necessary account/usage controls, shared web composition and essential operational feedback | Shared application executable |
| U2 | u2-account-personal-controls | library | Complete account lifecycle, external identities/MFA, profile/consent, preferences/onboarding, personal library controls and entitlement administration | Embedded application modules and their view contributions |
| U3 | u3-paper-corpus-capabilities | library | Complete corpus refresh/rebuild/recovery, discovery/citations, content availability, assistance choices and glossary behavior | Embedded application modules, execution adapters and their view contributions |
| U4 | u4-research-novelty | library | Research sessions, private attachments, acknowledged durable drafts, evidence, and distinct research and novelty lifecycles | Embedded application modules and their view contributions |
| U5 | u5-topics-digests | library | Topic subscriptions, content windows, delivery reconciliation and unsubscribe | Embedded application modules and their view contributions |
| U6 | u6-approved-export | library | Notion connection, current preview and explicit approval, exact source revision binding and reconciled external effects | Embedded application modules and their view contributions |
| U7 | u7-controlled-platform-protocols | service | Retained operator protocols with independent authority, evidence, preconditions and durable receipts | Standalone controlled operator executable |
| U8 | u8-service-operations-integration | service | Complete application composition, service operations, truthful capability readiness, and integrated recovery/repair verification | Complete shared application executable |

U1 and U8 are successive assemblies of the same application, not two permanent
application services. U2–U6 deliver embedded code rather than independently
deployed executables. Their `library` kind does not waive UI, persistence,
security, recovery, accessibility, observability or integration obligations.
Every unit must be exercised through the applicable real host boundaries.
U7's operator authority is not granted by an application administrator role.

U1 contains enough real behavior to demonstrate the complete anchor journey
without future units. It establishes the host and extension contracts. Later
units extend the existing component owners and supply their module/view
contributions. Each contribution must run in a real integration assembly with
U1; U8 owns the complete application composition and cumulative verification.
The core must not import future implementations merely to start. Production
composition, test composition, registration and source-file responsibility will
be explicit so that a shared workspace does not conceal reverse dependencies.

U1's limited demonstration is not the first-release boundary. For example,
supported actions, languages, filters, identity providers and operational
protocols still require complete parity through their assigned units.

## Proposed dependency structure

Edges below mean that the consuming unit needs the producer's stated contract
or implementation. They do not prescribe a single economic build order.

| Consumer | Direct prerequisites | Reason |
|---|---|---|
| U1 | None | Supplies the runnable journey and initial host/domain contracts |
| U2 | U1 | Extends current account, library, personalization and usage owners through the host contracts |
| U3 | U1, U2 | Uses the host plus completed account-lifecycle, consent and entitlement contracts for corpus, assistance and discovery behavior |
| U4 | U1, U2, U3 | Uses authenticated private-work boundaries and complete eligible-source/retrieval contracts |
| U5 | U1, U2, U3 | Uses current consent/subscription eligibility and complete corpus/discovery content-window inputs |
| U6 | U1, U2, U4 | Uses current owner/connection authority and the authorized novelty artifact revision |
| U7 | None | Retained platform execution has independent actor/target authority; no application dependency is invented for scheduling |
| U8 | U1, U2, U3, U4, U5, U6, U7 | Composes completed capabilities and consumes application/platform evidence for service-wide operations and verification |

U2's completed lifecycle/consent/entitlement contracts are substantive
prerequisites, not priority-only edges. If generation locates a required complete
contract in U1 instead, refine that edge and its rationale explicitly rather
than duplicating authority. The final documents must validate the actual DAG
and distinguish real prerequisites from preferred scheduling.

U7 can be investigated independently; U4 and U5 have no edge between them, and
U5 and U6 have no edge between them. This describes possible independence,
not a staffing commitment or a change from the recorded serial construction
execution. Delivery Planning chooses the economic sequence and work batches.

The active classic scope has the walking-skeleton ceremony off. The earlier
team note enabling it refers to the previous Phase 7 feature intent. This plan
does not invent a new skeleton approval or force a false dependency to select a
root. It still preserves the approved complete paper-journey demonstration and
the risk-first evidence obligations.

## Alternatives and tradeoffs

- **Eight focused increments (recommended):** the proposed plan keeps review and
  repair boundaries visible while sharing one application release. It requires
  disciplined ownership of extension contracts and application composition.
- **Four coarse increments:** journey foundation, remaining researcher
  capabilities, platform protocols, and complete operations/integration, all
  executable increments. This reduces handoffs but makes researcher completion
  a very large unit and hides more integration risk until its review.
- **Separately deployed domain services:** independent runtime boundaries could
  isolate resource use, but add deployments, inter-service failure handling and
  operational burden. Current $0 capacity evidence does not justify choosing
  them by default. Later measured needs may justify a focused extraction.

## Conditions carried forward

- Carry the accepted Domain Design review findings into Contract Design: U3
  must make search-projection write/rebuild and withdrawal propagation ownership
  explicit; U4 and U6 must specify the immutable source revision/content identity
  bound by export approval. These assignments do not claim the findings are fixed.
- Establish authoritative users/data, recoverable backups and continuity choices
  before affected migration. Resolve source/privacy obligations before affected
  processing/storage/hosting choices. Resolve draft retention/deletion and
  shared-device isolation before implementing draft persistence.
- Measure available free/local resources and public registration/email/model/
  export viability before choosing affected technologies. A local sink or mocked
  model does not prove the required normal public-service path. Bring evidenced
  conflicts to the user without spending or removing capabilities.
- Carry baseline measurements and user-agreed numeric targets into delivery and
  acceptance. This plan selects neither service-quality numbers nor a schedule.
- Generate the unit catalogue with relative complexity, dependency DAG,
  requirement map and traceability. Map every one of the 70 FR IDs; no user-story
  artifact was produced. Preserve all NFR and evidence obligations alongside it.
- Follow [CONVENTIONS.md](../../../../../../../CONVENTIONS.md): working branch
  to PR into develop, then separate release promotion to main. Domain Design
  merged in PR #36; this stage uses a fresh branch from develop.

## Q1 — Decomposition plan approval

Does the proposed eight-unit decomposition, including unit kinds and the shared
application/separate operator deployment grouping, fit the rebuild?

A. Approve Plan — retain this decomposition for the subsequent confirmed summary and artifact generation.
B. Revise Plan — change the grouping, granularity, kinds or dependency approach before generation.
X. Other (please specify)

[Answer]:
