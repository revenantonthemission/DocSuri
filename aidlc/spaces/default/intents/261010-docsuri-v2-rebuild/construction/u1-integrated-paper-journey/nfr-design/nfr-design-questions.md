# DocSuri v2 — U1 NFR Design proposal and confirmation

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`.
Conversation language: English. Answer mode: Guide me, carried forward.

## Context and inherited decisions

U1 NFR Requirements defines 37 derived requirements across all ten inception NFRs.
Its independent review identifies one Major ownership error: NFR10.2 names
Personalization as initial glossary owner. The approved domain catalogue and C06
assign glossary reads, writes, revisions and snapshots to PaperAssistance.
This proposal preserves that authoritative ownership and explicitly corrects the
downstream design; Personalization retains assistance defaults. The requirement
review remains a historical record, not evidence that the correction is implemented.

All prior product and execution decisions carry forward: retain all current
capabilities across eight units, prove the real paper journey in U1, use $0
free/local resources and one human maintainer, preserve public registration and
owner isolation, and keep numeric quality targets baseline-dependent. The
responsive Korean interface retains existing colors, Apple HIG web adaptations,
Light/Dark/System and the WCAG 2.2 AA target. Durable research drafts remain U4.

## Ambiguity analysis

No additional ordinary product question is needed before this logical pattern
design. Missing provider, hosting, numeric-target and continuity evidence is an
explicit prerequisite, not an invitation to invent a default. The design will
choose concrete ownership, consistency, admission, recovery and observation
patterns while marking their implementation bindings and finite policy values
as unresolved where the required evidence is absent.

The glossary conflict has a determinate answer in the approved domain/C06
contract, so it does not reopen product scope. The design will make the correction
explicit and require a coordinated canonical/type/consumer check before code.

## Proposed design work

| Area | Proposed concrete patterns and decisions |
|---|---|
| Performance and useful interaction | Separate explicit commands from read-only recovery; use bounded asynchronous work for model execution, finite connection/work pools, stable pagination and source/version-aware derived caches where safe. Keep current authorization outside stale cache authority. Specify timing boundaries, useful-output review, latency-budget measurement and the complete mounted P1/P2 plus translation/save/revisit experiment. Preserve truthful pending, uncertain, conflict, expired and degraded states. |
| Security and privacy | Establish same-origin browser/session/CSRF boundaries and current domain authorization at list/read/write/event/asset/payload/result/effect paths. Design trusted executor claims, source-purpose checks, untrusted-content handling, secret/transport/storage protections, account-switch epoch isolation and lifecycle/restore restrictions. Map unresolved privacy, permitted-use, retention and shared-device decisions to the affected operation rather than assuming permissive handling. |
| Finite capacity | Assign per-owner/global admission and work budgets, bounded queues/pools, policy revision and reserved recovery capacity. Separate foreground work from expensive model/processing demand, with explicit exhaustion behavior. Define experiment and operating limit relationships, backlog age and growth triggers. Additional workers/replicas remain conditional on measured free/local fit and unchanged owner/fence semantics. |
| Reliability | Design durable owner acceptance and receipt, recoverable dispatch, atomic claim/replacement/fencing, coherent result binding and a durable idempotent settlement obligation across owners. Specify uncertainty reconciliation, bounded retry/backoff/deadline and dependency isolation, ordered snapshot/event recovery, read-only retained-result discovery, graceful degradation and isolated backup/restore verification. Distinguish restart durability from disaster loss/recovery targets. |
| Observation and repair | Correlate safe request/operation/job/attempt/result/settlement identities, use immutable acceptance time and explicit clock uncertainty, and separate liveness, capability and journey readiness. Design bounded structured evidence, missing/stale signal handling, actionable local/free alerts, operational views and reproducible setup/defect/repair runbooks without making telemetry business authority. |
| Logical components | Map these mechanisms to the approved 13 domain owners and shared application, with logical adapters/stores/execution/observation capabilities, failure domains, shared-resource contention and recovery dependencies. Preserve the separately controlled operator executable. Avoid assigning physical services or duplicating business ownership merely to draw a diagram. |
| Interface coordination | Carry browser revision, worker claim/payload/fence and retained-job-history amendments into explicit design/validation obligations before affected implementation. PaperAssistance owns the initial empty glossary and non-null revision; its C06 read binds the immutable snapshot. Commit original acceptance time once and use it for history ordering/queue age. Existing and later consumers must remain coordinated. |

For every design choice, record the failure it addresses, authoritative owner,
state/transaction boundary, alternatives and tradeoffs, finite policy dependencies,
verification scenario and closure evidence. Pattern names alone are insufficient.
Short pseudocode or interface sketches may clarify a choice; implementation
belongs to Code Generation.

## Technology and operating evidence boundary

The previous technology record compares candidates; it does not select a stack.
This pass must not silently turn installed tools, cached models or generic pattern
examples into mandatory choices or numeric limits. Specify required adapter
guarantees and the concrete experiment that selects an implementation. Preserve
all capabilities and bring any evidenced conflict with quality or $0 to the human.

Existing-user/data authority, recoverable backups, permitted processing,
retention/deletion, public network/email/provider fitness and sustainable capacity
remain required before affected implementation/enablement/continuity decisions.
A synthetic isolated demonstration does not establish public operating feasibility
or authorize migration. Baseline-dependent service targets remain separate from
finite safety limits that must be configured before an experiment or operation.

## Artifacts and verification

After this summary is confirmed, produce `performance-design.md`,
`security-design.md`, `scalability-design.md`, `reliability-design.md`,
`observability-design.md`, `logical-components.md` and `traceability.json`.
Map every one of the 37 derived requirements to a named concrete solution.

Validate ownership against the component catalogue/C06, all requirement targets,
cross-file consistency, recovery and authority ordering, finite-policy dependencies,
local links and diagrams; obtain a fresh independent architecture review.
Keep the previous requirements and their review intact as the input record.
Document/design validation does not close the executable contract findings.

Continue serially with automatic ordinary completion. Enabled summaries/plans,
failures and the exact runnable completion-command approval remain human stops.
Follow CONVENTIONS.md: completed branches merge through PRs into develop under
the interim CI policy; main promotion remains separate.

## Assumptions & Open Questions

No new product decision is assumed. Physical stack/hosting, migration/continuity,
processing obligations, retention/shared-device details, actual finite policy
values and numeric quality targets remain evidence-dependent. Specify responsible
owners, required evidence and consequences where a decision remains unresolved.
The exact runnable v2 completion command remains unset pending its separate
human approval.

## Sources

- [Performance requirements](../nfr-requirements/performance-requirements.md),
  [security/privacy](../nfr-requirements/security-requirements.md),
  [capacity](../nfr-requirements/scalability-requirements.md),
  [reliability](../nfr-requirements/reliability-requirements.md),
  [observability](../nfr-requirements/observability-requirements.md),
  [technology decisions](../nfr-requirements/tech-stack-decisions.md) and
  [traceability](../nfr-requirements/traceability.json).
- [NFR architecture review](../nfr-requirements/reviews/review-01.md).
- [Functional specification](../functional-design/functional-spec.md),
  [rules](../functional-design/rules.md),
  [entities](../functional-design/entities.md) and
  [contract coordination](../functional-design/contract-revision-plan.md).
- [Approved component owners](../../../inception/domain-design/components.md)
  and [canonical contracts](../../../inception/contract-design/contract-summary.md),
  especially C00/C02/C03/C06/C13/C14.

## Consolidated Summary Confirmation

- Design concrete performance, security/privacy, finite-capacity, reliability
  and observability mechanisms for all 37 U1 NFR requirements, with named
  owners, state boundaries, tradeoffs and verification evidence.
- Preserve the real find → understand → save → revisit journey, useful
  source-bound assistance/translation, current owner/source authority, durable
  acknowledgements, fenced accepted work and one intended accounting effect.
- Use bounded work, admission, retries and recovery; define safe derived caches,
  dependency isolation, truthful degraded states and reserved recovery capacity.
  Choose numeric service targets after baseline and human agreement; require
  finite safety policies before affected enablement.
- Correct the glossary ownership inconsistency: PaperAssistance owns the initial
  empty glossary, its non-null revision and immutable C06 read binding;
  Personalization owns assistance defaults. Preserve immutable original
  acceptance time for retained-job ordering and queue age.
- Carry canonical browser/worker/history coordination into concrete designs
  before affected code; read-only rediscovery and reconnect never start new work.
  Keep durable research drafts assigned to U4.
- Map mechanisms, shared resources and failure domains onto the approved owners
  and shared application, preserving the separately controlled operator tool.
  Keep technology/hosting selections and continuity, obligations, retention and
  capacity decisions evidence-dependent within the $0 free/local budget.
- Preserve the approved Korean responsive experience, inherited colors, Apple
  HIG web adaptations, appearance modes and accessibility target. Define safe,
  bounded observation and reproducible recovery/repair for one maintainer.
- Produce six design documents and traceability; validate consistency and
  obtain independent review. Continue serially with automatic ordinary
  completion, preserving enabled summaries/plans, exact verification-command
  approval and failure stops. Merge fulfilled branches through PRs into develop
  under CONVENTIONS.md.

Does this all look correct before I generate the artifact?

[Answer]:

