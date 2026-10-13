# U2 NFR Requirements — proposal and confirmation

Date: 2026-10-13. Unit: `u2-account-personal-controls`, an embedded library with web contributions inside the existing application. This is a proposal for the requirements pass, not the generated requirements or an implementation approval.

## Sources

| ID | Source | Consequence for this pass |
|---|---|---|
| FD | [Functional specification](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md) | Current authority, proof and revision ordering, lifecycle participants, saved work/history, reset boundaries and one intended accounting effect. |
| REVIEW | [Independent functional design review](../functional-design/reviews/review-01.md) | One Major finding: pending reset cleanup lacks a concrete read-only progress and restart-rediscovery binding. It must be resolved before affected implementation. |
| REQ | [Inception requirements](../../../inception/requirements-analysis/requirements.md) | All ten NFRs remain applicable. Numeric task, latency and recovery/repair targets follow the measured baseline and human agreement. |
| UNIT | [Unit catalogue](../../../inception/units-generation/unit-of-work.md) and [requirement assignment map](../../../inception/units-generation/unit-of-work-story-map.md) | U2 extends one shared application; full parity remains distributed across the approved eight units and U8 integration. |
| CONTRACT | [Canonical contracts](../../../inception/contract-design/contract-summary.md) | C02/C03/C13 pin owner, transport, proof, revision, history/reset, accounting and lifecycle semantics. Contract coordination precedes affected code. |
| UI | [Frontend specification](../functional-design/frontend-components.md) and [approved visual mapping](../../../inception/refined-mockups/design-system-mapping.md) | Korean responsive controls, inherited colors, Apple HIG web adaptations, appearance modes and WCAG 2.2 AA target. |
| TECH | [CodeKB technology inventory](../../../../../codekb/DocSuri/technology-stack.md) | Dated manifest evidence only; it does not establish current runtime, security support, public capacity or v2 selection. |
| U1 | [Existing application infrastructure design](../../u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md) | U1 selected the common PostgreSQL transaction facility for local implementation and proposed native Python/API plus static React/TypeScript web bindings. Verify actual current adapters/versions and incremental fit before extending them; historical design statements are not live operating proof. |
| HUMAN | Confirmed rebuild constraints and functional summary | Retain every current capability; $0 free/local only; one human maintainer with agents; no fixed deadline; public registration; no implicit migration, retention or paid fallback. |
| GIT | [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md) | Completed branches merge by PR into develop under the interim CI policy; main promotion remains separate. |

## Resolved decisions and ambiguity analysis

- The user already selected baseline-first numeric quality targets. Do not ask for arbitrary latency, availability or recovery numbers now. Define the measurement, environment, workloads, evidence and decision checkpoint; finite admission policies must still exist before operation.
- The user already selected the $0 free/local budget, one human maintainer, public multi-user registration, full-capability scope and risk-first order. None is reopened by this pass.
- Ordinary completion is automatic; enabled summary/plan confirmations and verification/failure decisions still apply. This summary is the remaining human decision before generation.
- P1–P8 in the functional specification name real evidence prerequisites, not assumed approved policies. In particular, do not adopt legacy 30-day reactivation behavior, invent MFA recovery, claim free public email delivery, assume an absent quota is unlimited, or infer a public host from local hardware.
- U1 physical choices provide the existing integration baseline. This pass will distinguish observed implementation, selected earlier bindings, candidate extensions and evidence-blocked choices. It will not relabel all technology as unselected or claim all earlier candidates are proven.
- The reset-recovery finding needs a specific design/contract solution and executable closure. A generic promise of recovery or replaying the original mutation cannot substitute for a read-only evolving status and restart rediscovery path.

## Proposed assessment and evidence

| Category | U2 requirements to derive | Verification evidence to require |
|---|---|---|
| Complete-task correctness | End-to-end registration/recovery, account/profile changes, saves/history, onboarding/reset and quota administration; distinguish acknowledgement, accepted work and completed cleanup | Real mounted positive, negative and recovery scenarios with authoritative state/effect assertions; synthetic providers clearly distinguished from public behavior. |
| Responsiveness and capacity | Time to form feedback, authentication, save/reopen, bounded list pages and safe status reads; contention between history clear, reset, revocation and quota admission | Cold/warm distributions, sample sizes and representative/concurrent boundary workloads; finite pools, queues, sizes, retries, proof attempts and storage with recovery headroom. |
| Security and privacy | Current owner/session/source authority, neutral public initiation, purpose-bound proofs, provider callback/replay checks, protected MFA material and recovery, role separation, consent and account-switch isolation | Positive/negative access matrix at every applicable boundary, expired/replayed/superseded proof tests, concurrent revocation/effect checks, secret-redaction and shared-device checks. |
| Durability and recovery | One intended write/accounting effect, lost acknowledgement reconciliation, delayed-event suppression, all-participant lifecycle completion, permissible reactivation and restore enforcement | Store/connection/restart/clock/late-event fault injection; unchanged clear/reset boundary on recovery; isolated restore validates current authority, tombstones and owner relationships. |
| Reset rediscovery | A durable owner-bound reset responsibility with immutable acknowledgement and a separately evolving safe cleanup projection, readable after authenticated restart without resubmitting reset | Define and coordinate concrete C03/C13 identity/read/list or equivalent discovery bindings before code; lost-reply, restart, cross-owner, pending-to-complete and no-second-reset-boundary checks. This is a closure requirement, not a claim the contract already provides it. |
| Accessibility and smooth interaction | Korean labels, focus, errors/status, deliberate destructive scope, keyboard/zoom/reflow, readable inherited colors and Light/Dark/System | Implemented browser and assistive-technology matrix; safe return context, no former-owner cache flash or automatic command replay; no conformance claim from design prose. |
| Repairability and observability | One-maintainer reproducible setup/repair; exact dependency/configuration identities; safe original operation and participant evidence; truthful capability readiness | Clean setup and representative defect/recovery exercise; safe correlation without credentials/private text, bounded telemetry and mandatory evidence protected from eviction. |
| Technology and integration | Reuse/extend the existing application through owner contracts; evaluate needed free/local identity, delivery, storage and protection choices against required guarantees | Current source/configuration/lockfile checks, focused compatibility and capacity evidence, verified permitted use and free limits before selection. No new paid fallback or separate service by assumption. |

## Artifact plan

For this library unit the applicable outputs are:

1. `security-requirements.md`: owner/session/admin/MFA, credential/proof, browser/provider, data/consent/lifecycle and threat requirements, with explicit cross-cutting correctness, recovery, accessibility, capacity and observation requirements for this unit's interfaces.
2. `tech-stack-decisions.md`: existing integration baseline, alternatives and evidence-backed decisions or unresolved choices, bounded measurement requirements, contract coordination and one-maintainer repairability. Performance, scalability, reliability and observation obligations remain covered here and in the security requirements even though this unit has no separate service deployment.
3. `traceability.json`: NFR1–NFR10 to unit-scoped derived `NFRx.y` IDs, with no unexplained exclusions. IDs indicate requirement coverage, not test completion.

Validate IDs, references, cross-contract consistency and unresolved prerequisites, then obtain the required independent architecture review. No implementation or public deployment follows merely from this document generation.

## Assumptions & Open Questions

No new product assumption is adopted. Required evidence/decisions remain: authoritative users/data and backups; permitted processing and retention/deletion/reactivation; MFA recovery and credential/session policy; sustainable free public email/identity integration; finite quotas/reset/refund policy and resource fit; current dependencies; quantitative targets after baseline. Resolve each before its affected choice or implementation. The reset-recovery finding is an explicit additional design/contract closure task, not a silent exception.

## Consolidated Summary Confirmation

- Define U2 quality and security requirements for accounts, Google/ORCID identities, administrator MFA, profile/consent, lifecycle, saved work/history, settings/onboarding and quota/plan controls, preserving all ten inception NFRs and all current capabilities.
- Require current authority and protected proofs at every affected boundary, owner isolation across account switches, truthful acknowledged/unknown/pending/complete states and one intended write/accounting effect. Preserve delayed-event suppression and current policy during cleanup, reactivation and restore.
- Require a concrete read-only reset-cleanup progress and restart-rediscovery path, with stable owner-bound responsibility and evolving completion evidence. Coordinate C03/C13 before affected code; verify lost acknowledgements, authenticated return and progress without starting another reset.
- Define repeatable measurements for complete-task success, responsiveness, interruption recovery and defect reproduction/repair. Numeric service targets follow the baseline and your agreement. Finite limits for inputs, challenges, lists, queues, concurrency, retries, storage and quotas remain mandatory before operation.
- Build on the existing shared application and verify its current bindings. Evaluate needed free/local extensions against security, permitted use, resource fit and repairability; distinguish selected, candidate and evidence-blocked choices. Preserve the $0 budget and one-maintainer model without paid fallback or silent feature cuts.
- Keep retention/reactivation, existing-data continuity, backup/restore, MFA recovery, public provider/delivery and quota policies as explicit prerequisites. Do not adopt the legacy 30-day default. U1's recorded assistance/search limitations and later-unit integration obligations remain open.
- Preserve the Korean responsive workspace, inherited colors, Apple HIG web adaptations, Light/Dark/System and WCAG 2.2 AA target. Specify observable and accessible failure/recovery behavior without claiming conformance from prose.
- Produce the library unit's security requirements, technology decisions and traceability, covering its performance/capacity/reliability/observability contributions; validate them and obtain independent review. Continue serially with automatic ordinary completion and the existing human decision points. Follow CONVENTIONS.md: fulfilled branches merge through PRs into develop; main promotion remains separate.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]:
