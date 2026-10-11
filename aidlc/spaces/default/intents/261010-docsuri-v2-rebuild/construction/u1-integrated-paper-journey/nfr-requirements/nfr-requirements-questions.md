# DocSuri v2 — U1 NFR Requirements plan and confirmation

Date: 2026-10-11 (Asia/Seoul). Unit: `u1-integrated-paper-journey`.
Conversation language: English. Answer mode: Guide me, carried forward.

## Context and inherited answers

Functional Design completed under the human's **Continue automatically** choice
and merged through [PR #40](https://github.com/revenantonthemission/DocSuri/pull/40)
into develop at `ee2957bac885549d4b5865e8bb939967f0dfbfb3`.
Its independent review found no Critical/Major concerns and two Minor details
to resolve before affected implementation: initial empty-glossary revision and
immutable acceptance time. Canonical contract changes and executable closure
remain prerequisites, not completed work.

All preceding answered stage questions and their confirmed decisions carry
forward. This pass does not reopen the $0 budget, full-capability scope, public
registration, one-maintainer model, technology freedom, baseline-first target
selection, user/data continuity investigation or approved presentation choices.
Automatic ordinary completion preserves enabled summaries/plans, exact runnable
verification-command approval and failure stops.

## Ambiguity analysis

No new ordinary interview question requires a human judgment before this logical
NFR package. The absent numeric service targets are an **explicitly approved
deferral until measurement**, not an ambiguous promise of “fast enough”.
Each pending value must have an owner, measurement method, required evidence,
decision point and consequence of remaining unresolved.

All ten inception NFRs apply to U1. Detailed requirements will preserve their
parent IDs as `NFRx.y`, identify the relevant workflow/rule/local check, and
separate required invariants from not-yet-selected quantitative thresholds.
None of these documents can claim an unmeasured baseline, selected hosting,
public-service feasibility, verified backup or complete v2 implementation.

## Proposed work

| Area | Proposed requirement and evidence content |
|---|---|
| Performance and correctness | Define usable-search/content, interaction feedback, durable save acknowledgement, fresh authenticated revisit, queue wait, execution and prepared-result timing boundaries. Measure complete-task success and output usefulness as well as latency. Record environment, model/configuration, permitted fixture/source hashes, cold/warm state, workload, sample sizes, distributions and failures. No invented latency or throughput target. |
| Security and privacy | Make trusted actor/owner/session/source checks testable on list/direct read/write/job/event/asset/result and proposed retained-job-history paths. Include A/B/anonymous/revoked cases, purpose-bound proofs, untrusted content, safe errors, account-switch late responses and revocation-versus-effect races. Resolve obligations, retention, deletion, location and shared-device treatment before affected handling; separate service authority from platform authority. |
| Scale and finite resources | Inventory input/output/content limits, page windows, queue/concurrency, model work, cache/storage growth, retries/deadlines/leases and accounting/reset bounds. Name owner/configuration/evidence/rejection/recovery for each. Unresolved policy never means unlimited work. Measure free/local fit and truthful exhaustion without paid fallback or silent feature cuts. |
| Reliability and recovery | Require recoverable acknowledged writes and accepted jobs, visible stale-write conflicts, fenced replacements, one intended result/accounting effect and read-only progress/result recovery. Specify crash/unknown-response/failure tests around acceptance, dispatch, publication and settlement. Measure retained/lost/duplicate work and recovery effort; establish authority and isolated restore evidence before continuity or RTO/RPO claims. |
| Observability and repairability | Define safe correlation across request/operation/job/claim/result/accounting, timestamps, backlog age, rejection/exhaustion and recovery evidence. Distinguish process liveness, capability readiness and complete-journey readiness, and current/stale/unknown/estimated values. Bound telemetry failure and retention; require reproducible clean setup, diagnosis, repair and regression/integration evidence for one maintainer. |
| Technology decisions | Compare candidate categories against these requirements, current source declarations, primary documentation/terms and measured local/free capacity. Record selected, candidate and evidence-blocked decisions explicitly, with rationale and the experiment/permission needed to select. Existing installation or legacy manifest presence is not a v2 selection. No framework/store/broker/provider is chosen merely to fill a document. |
| Cross-cutting user experience | Retain Korean responsive presentation, inherited colors, Apple HIG web adaptations, Light/Dark/System and the WCAG 2.2 AA target. Define keyboard/focus, announcements, reflow/zoom, long-content, contrast and accessible-authentication checks. A design target is not a conformance or user-validation claim. |

## Bounded local observations

Read-only checks on 2026-10-11 observed an Apple M4 Pro with 14 reported physical
and logical CPUs and 25,769,803,776 bytes (24 GiB) memory. The current APFS data
volume reported 13,840,000 KiB available (about 13.2 GiB) and 97% used. This is a
time-sensitive filesystem observation, not an allocation or sustainable working
envelope. No files were removed and no model was downloaded or executed.

The shell resolved Python 3.9.6, Node v24.14.0 and Bun 1.4.2. Docker 29.9.0 and
Ollama 0.40.2 reported versions. This is a command-path sample, not an exhaustive
environment inventory or proof of declared application compatibility. In
particular, the legacy backend declares a different Python minimum.

Ollama listed local `qwen3:8b` (displayed size 5.2 GB) and
`bge-m3:latest` (1.2 GB), plus a cloud-model entry. No model is selected.
Cached local files do not prove supported licensing, permitted processing,
source grounding, translation quality, context limits or throughput. A cloud
entry cannot become an implicit paid fallback. The current workstation is
not thereby chosen as the public host or authoritative data environment.

These observations identify capacity questions for measurement. Model/storage
fit, source and processing permissions, public network/email viability and
the available workload envelope remain open.

## Contract and design closure carried forward

- **Contract R-01/R-03:** coordinate canonical browser revision and worker
  claim/payload/fencing definitions before affected code; retain exact
  idempotent-receipt/current-authorization distinctions. Later bindings and
  cumulative checks remain assigned to their owning units.
- **Retained-result rediscovery:** specify and verify the planned owner-bound
  read-only assistance history, bounded stable pagination and fresh-browser
  recovery without transient job IDs. Reads cannot create a job or debit.
- **Functional Design R-01 (Minor):** define the owner-issued empty-glossary
  snapshot/non-null revision and U1 read/default binding before the first
  assistance request; align logical optionality and preserve result binding.
  Glossary editing remains later-unit work.
- **Functional Design R-02 (Minor):** capture one immutable owner acceptance
  timestamp with original admission, map history `createdAt` and queue-age
  measurements to it, and preserve it across duplicates, replacement and
  recovery. Worker attempt timestamps cannot reorder prior work.
- **Contract R-02:** durable research/manuscript draft allocation/rediscovery
  remains U4 work before its persistence; no U1 composer is added.

These are downstream closure obligations. This pass does not edit frozen
Functional Design outputs or represent document fixes as executable evidence.

## Artifacts and verification

After confirmation, produce `performance-requirements.md`,
`security-requirements.md`, `scalability-requirements.md`,
`reliability-requirements.md`, `observability-requirements.md`,
`tech-stack-decisions.md` and `traceability.json` under this unit's
NFR Requirements directory.

Validate detailed IDs, all ten parent NFR mappings, requirement/workflow/owner
references, measurable evidence plans, decision states, local links and
cross-document consistency. Obtain an independent architecture review.
Document checks and legacy CI cannot replace the separately approved runnable
v2 completion command, which remains unset.

## Assumptions & Open Questions

No new human product decision is assumed. Authoritative users/data/backups,
permitted content/model handling, sustainable public free/local integrations,
retention and shared-device policies, finite operating limits and measured
quality targets remain evidence prerequisites with affected-work boundaries.
The human decides continuity after inventory/restore evidence, numeric targets
after baseline, the exact runnable verification command before its first
completion use, and any evidenced conflict between full parity, quality and $0.

## Sources

- [Functional specification](../functional-design/functional-spec.md),
  [business rules](../functional-design/rules.md),
  [contract coordination](../functional-design/contract-revision-plan.md) and
  [architecture review](../functional-design/reviews/review-01.md).
- [Inception requirements/NFRs](../../../inception/requirements-analysis/requirements.md),
  [canonical contracts](../../../inception/contract-design/contract-summary.md)
  and [dependency evidence register](../../../inception/delivery-planning/external-dependency-map.md).
- [Declared legacy technology stack](../../../../../codekb/DocSuri/technology-stack.md).
- [U1 boundary](../../../inception/units-generation/unit-of-work.md) and
  [delivery plan](../../../inception/delivery-planning/bolt-plan.md).
- Read-only local commands: `sysctl -n hw.memsize hw.physicalcpu hw.logicalcpu machdep.cpu.brand_string`,
  `df -k .`, `uname -m`, `sw_vers -productVersion`, explicit runtime
  `--version` calls and `ollama list`. No inference benchmark was run.

## Consolidated Summary Confirmation

- Define U1's performance, security/privacy, capacity, reliability and
  observability requirements, preserving all ten inception NFRs with derived
  `NFRx.y` IDs and traceability to the real paper journey.
- Specify repeatable measurements for complete-task success, useful output,
  responsiveness, interruption recovery and defect reproduction/repair.
  Numeric service targets follow the measured baseline and human agreement.
- Require current owner/session/source authority, safe public registration,
  acknowledged persistence, fenced accepted work, one intended result/accounting
  effect, read-only recovery and accessible truthful feedback.
- Define finite policy requirements and evidence for input sizes, queues,
  concurrency, model work, storage, deadlines/retries/leases and quota/reset
  behavior. Unknown limits cannot mean unlimited operation; preserve $0 with
  free/local choices and no silent capability cuts.
- Evaluate technology alternatives against reproducibility, repairability,
  permitted use and measured resource fit. Record candidate or evidence-blocked
  decisions honestly. Local hardware/cached models are observations, not stack,
  hosting or operating-feasibility approval.
- Carry canonical contract coordination and retained-result rediscovery into
  affected implementation, including the two Minor details for empty-glossary
  revision and immutable acceptance time. Keep durable research drafts in U4.
- Preserve the Korean responsive, inherited-color, Apple HIG-informed interface,
  appearance modes and WCAG 2.2 AA target. Keep authority/backups, continuity,
  obligations, retention, public integrations and numeric targets evidence-dependent.
- Produce the six requirement/technology documents and traceability, validate
  consistency and obtain an independent review. Continue serially with automatic
  ordinary completion; preserve enabled summaries/plans, exact verification-command
  approval and failure stops. Completed branches merge through PRs into develop
  under CONVENTIONS.md; main promotion remains separate.

Does this all look correct before I generate the artifact?

[Answer]:

