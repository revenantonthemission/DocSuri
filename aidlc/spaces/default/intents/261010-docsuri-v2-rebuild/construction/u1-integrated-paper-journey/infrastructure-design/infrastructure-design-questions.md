# DocSuri v2 — U1 Infrastructure Design proposal

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`.
Conversation language: English. Answer mode: Guide me, carried forward.

## Context and inherited decisions

The completed [NFR design](../nfr-design/logical-components.md) maps all 37 detailed requirements to concrete logical mechanisms. The independent [architecture review](../nfr-design/reviews/review-01.md) found no new issues. This establishes a design basis, not a running application or selected infrastructure.

Keep all current capabilities across eight units, one shared application and a separately controlled operator executable. U1 proves the real paper journey with eligible source-bound assistance, supported translation, real persistence, owner isolation and fresh authenticated return. Keep the $0 free/local budget and one-maintainer model. Public registration remains required for the service; a local synthetic demonstration proves only its declared scope.

## Ambiguity analysis and decision method

The human has selected no mandatory technology or provider. Ordinary technical choices should therefore be evaluated against the approved behavior and repairability goals, rather than returned as preference questions. This stage will evaluate physical bindings and make evidence-backed choices where the needed evidence is available. It must distinguish a selected experiment candidate, a verified implementation binding and an operating environment.

The approved logical design requires a common transactional serialization facility for AccountAccess/CorpusContent authority barriers and protected owner commits. Separate owner accounting transactions use durable reconciliation. A candidate that cannot meet these guarantees is not made acceptable by naming a database or queue.

Existing-user/data authority, recoverable backups, continuity, permitted processing, retention, shared-device treatment and public-service fitness still constrain the affected decisions. Unresolved evidence must identify an owner, closure check and consequence; it cannot silently become a permissive default. No user-data reset or migration is implied by an isolated U1 environment.

## Bounded local observations

Read-only observations on 2026-10-11:

| Observation | Result | Limit of evidence |
|---|---|---|
| Working-volume free space, `df -k /Users/revenantonthemission/Projects/DocSuri` | 12,800,000 KiB, approximately 12.2 GiB; command reported 98% capacity | Snapshot before new experiments, not allocated experiment/backup capacity. Recheck before a resource-consuming action. |
| Physical memory, `sysctl -n hw.memsize` | 25,769,803,776 bytes = 24 GiB | Installed RAM is not presently free RAM or a reservation. |
| Logical CPU count, `sysctl -n hw.ncpu` | 14 | Count alone says nothing about sustained inference throughput or foreground isolation. |

The first sandboxed hardware read was denied; the read-only query then succeeded through the normal permission path. No workload, model download, database change or service exposure was performed by these observations.

Before an experiment, record its fixture/purpose, exact tool/model identities, temporary namespace, finite memory/storage/time/concurrency envelope, stop conditions and cleanup/recovery method. Use synthetic accounts and eligible paper material. Prefer existing compatible installations/caches when verified, without treating their presence as selection. Do not fill the disk, repurpose existing service stores or count ordinary directories as independent capacity.

## Proposed infrastructure work

| Area | Concrete work and required evidence |
|---|---|
| Deployment and environments | Design a reproducible isolated U1 environment, comparing native processes and free/local container bindings against installation, supervision, network isolation, model access and resource overhead. Define application, worker/model and operator boundaries, private ingress/egress, storage and environment identities. Separate local demonstration from any public hosting selection or deployment. |
| Durable data and authority | Compare viable transactional stores against actual multi-process CAS/uniqueness, guarded commit/revocation, claims, receipts and crash behavior. Define owner access, accepted payload/result storage, consistent backup and isolated restoration. Preserve the common authority-ordering requirement and separate accounting reconciliation. |
| Search, work and provider bindings | Evaluate the retained search modes and eligible local model/embedding paths for useful P1/P2 output, translation, footprint and recovery. Map durable acceptance/dispatch and optional caches without adding an unnecessary permanent service. Record exact identities, permitted use, free limits and no-paid-fallback enforcement before selecting a binding. |
| Finite resources | Allocate foreground, expensive work, staging, telemetry and reserved recovery budgets within observed resources; set safe experiment limits before running. Record measured demand and rejected/failed attempts. Service-quality targets remain baseline-first and human-agreed; unknown policy never means unlimited operation. |
| Network, secrets and sensitive data | Specify protected service/store endpoints, credential/key custody and rotation, transport, backup access and permitted recipients. Public DNS/TLS/email and provider fitness need evidence. Bind account/source guards, result delivery and restore restrictions to the actual topology; disclose unresolved obligations and current-data continuity. |
| Monitoring | Map the existing safe correlation, bounded telemetry, readiness, local incidents, dashboards and measurement denominators to concrete free/local facilities. Design missing/stale-data behavior and finite storage/retention. Monitoring cannot authorize business effects or imply that a failed/unrun journey is healthy. |
| Delivery and rollback | Design reproducible build/package, contract checks, tests, security checks, mounted useful-output/recovery checks and cumulative verification. Map PR integration into develop, separate main promotion and explicit deployment/environment gates. Define artifact/config/schema compatibility, graceful drain, rollback and restore limitations without assuming spare blue-green capacity. |
| Contract and ownership coordination | Preserve PaperAssistance glossary ownership, virtual initial revision, immutable acceptance time and retained history. Identify storage/network/config prerequisites for browser revision, worker claim/payload/fence and guard amendments. Canonical changes and executable closure remain required before affected code. |

Evaluate only within current authorization and the $0 constraint. If an experiment exposes a conflict with full capability, quality or available resources, bring the evidence to the human before changing those constraints. Unsupported or not-yet-proven bindings remain explicit; the stage must not mark every physical decision selected merely to reach Code Generation.

## Artifacts and verification

After confirmation, produce:

- `infrastructure-specification.md`: tabular deployment, services, shared resources, ownership/access boundaries, resource allocations and evidence-backed selections.
- `monitoring-design.md`: concrete metrics, logs/traces, bounded storage, readiness, incidents, routes and baseline-dependent service targets.
- `cicd-pipeline.md`: delivery stages, checks/gates, artifacts, environment promotion, secrets and rollback.
- `traceability.json`: infrastructure-relevant detailed requirements mapped to concrete resources/configuration; explicitly justify non-infrastructure requirements.

Validate traceability, owner isolation, topology and dependency consistency, resource/failure domains, zero-cost constraints and handoff prerequisites. Obtain an independent architecture review. This is design work: complete application/IaC/pipeline implementation belongs in its implementation stage. No live deployment or pipeline rewrite occurs merely because the design is written.

Continue serially with automatic ordinary completion; enabled summary/plan confirmations, exact runnable completion-command approval and failures remain human stops. Follow [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md): fulfilled branches merge through PRs into develop under the interim CI policy. Main promotion remains separate.

## Assumptions & Open Questions

No new product preference is assumed. Local isolated verification follows the approved U1 demonstration, not a decision to host the public service on this workstation. Actual technology bindings require evidence; production hosting, existing-data continuity/migration, real sensitive-data policies, public integrations and numeric quality targets remain open where their prerequisites are not met.

The exact runnable completion command stays unset until the human approves a real v2 invocation before checkpoint verification. Neither this design nor legacy CI can substitute for that result.

## Sources

- [Performance](../nfr-design/performance-design.md), [security](../nfr-design/security-design.md), [capacity](../nfr-design/scalability-design.md), [reliability](../nfr-design/reliability-design.md), [observation](../nfr-design/observability-design.md), [logical components](../nfr-design/logical-components.md) and [NFR traceability](../nfr-design/traceability.json).
- [Technology candidates and required evidence](../nfr-requirements/tech-stack-decisions.md).
- [Functional specification](../functional-design/functional-spec.md) and [contract coordination](../functional-design/contract-revision-plan.md).
- [Approved owners](../../../inception/domain-design/components.md), [canonical contracts](../../../inception/contract-design/contract-summary.md) and [unit catalogue](../../../inception/units-generation/unit-of-work.md).

## Consolidated Summary Confirmation

- Map U1's logical design to concrete free/local deployment, storage, search, execution, networking, secrets, monitoring and delivery bindings. Compare alternatives and select only where evidence supports the required guarantees; distinguish experiment candidates from verified bindings.
- Prepare a reproducible isolated local U1 environment for the real paper journey, while retaining public registration and all release capabilities. Local verification does not select public hosting or authorize migration.
- Use bounded experiments with synthetic accounts and eligible paper material. Recheck resources, define finite memory/disk/time/concurrency limits and reserve recovery space before workloads. The current workstation has 24 GiB RAM and about 12.2 GiB free on the working disk; these are observations, not allocated capacity.
- Preserve owner-local receipts, durable acceptance, fenced workers, result/accounting reconciliation and shared ordering between current authority and protected commits. Keep PaperAssistance glossary ownership and read-only result rediscovery; coordinate canonical amendments before affected code.
- Specify safe private networking, key/secret custody, protected artifacts, bounded telemetry and isolated backup/restore. Resolve permitted processing, retention, authoritative data and public-provider evidence before affected choices; no paid fallback or silent capability cuts.
- Design the future build/test/package/promotion/rollback pipeline around CONVENTIONS.md. Continue using the current interim CI policy until replacement checks are implemented; main promotion and deployment remain separate. Keep the exact runnable completion command subject to its agreed human approval.
- Produce the infrastructure specification, monitoring design, delivery-pipeline design and traceability, validate them and obtain independent review. Numeric quality targets follow measured baselines and human agreement.
- Preserve the Korean responsive experience, inherited colors, Apple HIG web adaptations, appearance modes, accessibility target, $0 budget and one-maintainer model. Continue serially with automatic ordinary completion and the existing summary/plan/failure stops.

Does this all look correct before I generate the artifact?

[Answer]: Looks correct
