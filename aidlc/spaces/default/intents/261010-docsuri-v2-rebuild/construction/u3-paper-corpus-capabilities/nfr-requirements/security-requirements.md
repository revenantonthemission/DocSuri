# U3 security and cross-cutting quality requirements

Date: 2026-10-15 (Asia/Seoul). Unit: `u3-paper-corpus-capabilities`. Requirements for an embedded module in the shared application, with browser contributions. This document defines obligations and closure evidence; it does not assert implementation, public readiness, policy approval or measured conformance.

## Scope and sources

The confirmed [proposal](nfr-requirements-questions.md) retains all current capabilities, the $0 free/local budget and one human maintainer. U3 owns contributions through CorpusContent, Discovery and PaperAssistance; WebWorkspace owns presentation, not duplicate business records; Library and AccountAccess remain the owners of saved references and account authority. All ten [inception NFRs](../../../inception/requirements-analysis/requirements.md) apply, including this library's performance, capacity, reliability and observability contributions.

Normative inputs: [functional specification](../functional-design/functional-spec.md), [rules](../functional-design/rules.md), [frontend specification](../functional-design/frontend-components.md), [canonical contracts](../../../inception/contract-design/contract-summary.md) (C04–C06, C13, C14), [domain ownership](../../../inception/domain-design/components.md), [unit catalogue](../../../inception/units-generation/unit-of-work.md) and [unit requirement map](../../../inception/units-generation/unit-of-work-story-map.md). The assigned functional rows remain governed by the functional design; this stage adds derived quality requirements, not a replacement capability inventory. [Technology decisions](tech-stack-decisions.md) define evidence boundaries and measurements. IDs below are unit-scoped derivatives of NFR1–NFR10, not claims that tests passed.

The [functional review's findings](../functional-design/reviews/review-01.md) remain open closure tasks for that stage (FR6.3 lifecycle participation row, traceability completeness, section floors, upstream references, eligibility-restore path, vocabulary). Describing obligations here does not close them.

## Assets, trust boundaries and threat model

| Boundary / asset | Adversarial or fault condition | Responsible owner and required defense |
|---|---|---|
| Anonymous browser → discovery/reading | Enumeration, unbounded query/traversal, hostile input, fabricated relevance | Discovery: server-validated vocabulary/bounds, snapshot-bound windows, explicit degradation; CorpusContent: eligibility before serving. |
| Browser → corpus maintenance (operator scope) | Role confusion, unscoped run, duplicate/competing publication, watermark overreach | CorpusContent: explicit maintenance authority, idempotent run identity, CAS publication, stage-effect evidence. |
| Source/provider → corpus | Reordered/duplicate/malformed records, license/access change, withdrawal, provider limits, incompatible model/index | CorpusContent: canonicalization with provenance, classification of bad records, ordered change facts, eligibility-dominance and repeatable recovery. |
| Worker/executor → assistance job | Late/replaced worker, forged progress, replay, lease expiry, unknown settlement | PaperAssistance: immutable accepted binding, single claim/fence, monotonic ordered progress, idempotent settlement; UsageEntitlements settles separately. |
| Private vs public content | Private identifiers probed via public routes; asset paths/URLs; unsafe rendered content | CorpusContent/Discovery: opaque authorized read handles, no arbitrary paths/URLs, current eligibility at every delivery. |
| Restored snapshot → served state | Withdrawn content resurrected; stale projections defeat the decision | CorpusContent: restore replays current withdrawal boundaries and verifies receipts before serving; caches/indexes never overrule eligibility. |
| Shared browser / telemetry | Prior owner cache flash, private query leakage, over-detailed job failure evidence | WebWorkspace clears by authority generation; ServiceOperations consumes bounded, secret-free observations. |

Threat model scope includes synthetic local verification and requirements for eventual public operation. Local operator compromise and a fully compromised host are not solvable by application ACLs alone; host/key custody and backup access must be defined before affected real data is used. No legal regime, corpus permission or provider term is assumed; unresolved permission blocks the affected processing (BR1.1, BR3.1, BR7.6).

## Derived requirements

Every row is normative. Evidence means executable checks unless the row explicitly requires a policy decision or investigation. The evidence gates in [technology decisions](tech-stack-decisions.md) apply in addition to each row.

### NFR1 — complete-task correctness

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR1.1 | Discovery and CorpusContent must complete find/refine, read (including figures/anchors/source links) and citation exploration for eligible fixtures with stable paper/version identity, truthful empty/error/degraded outcomes and no fabricated content or edges. | Mounted browser/service cases for query → result → open → navigate-back → citations; eligibility, withdrawal and malformed-content fixtures; assert persisted/observed identities, not just HTTP status. |
| NFR1.2 | PaperAssistance must accept, execute, progress and expose results for the complete supported summary/translation/presentation set, closing the four recorded job defects (ordering field, result shape/semantics, real dispatch, valid frames) through the mounted transport. | Real browser→service→worker→result checks; duplicate/lost-response, crash-after-acceptance, reconnect after missed events and expired-result cases; reads never start work. |
| NFR1.3 | CorpusContent must complete ingestion, refresh, rebuild, canonicalization, version handling, deduplication and withdrawal propagation with stage/watermark evidence; reruns and retries apply the planned fix only to reconcilable stages. | Source-scope fixtures with duplicate/reordered records, partial batch failure, interruption between object/control/index writes and withdrawal during publication; inspect authoritative rows and receipts. |

### NFR2 — responsiveness and smooth use

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR2.1 | WebWorkspace must render distinct loading, empty, partial, degraded, error, pending, expired and offline states for discovery/reading/assistance surfaces; retain query, filters, open version and acknowledged results across errors and reconnect; no infinite loading or repeated unintended submission. | Browser tests for delayed, reordered, failed and interrupted responses; count commands; inspect focus, live announcements and retained context. |
| NFR2.2 | U3 must measure time to usable search/content, first progress, accepted work and prepared-result read under documented cold/warm and contention workloads before numeric service targets are proposed; separate local processing, queue delay, embedding and remote provider time. | Reproducible samples with environment/workload identity, success/failure counts, latency distributions and raw safe evidence using the measurement procedure in technology decisions. |
| NFR2.3 | Pages, polling/backoff, progress replay and traversal must be bounded with safe stop states on expiry, ineligible content or exhausted attempts; status reads never allocate work or bypass backpressure. | Large-window, pending-work, background-tab/resume and provider-limit cases; bounded requests/resources and no writes attributable solely to inspection. |

### NFR3 — durability and interruption recovery

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR3.1 | Acknowledged corpus effects and accepted assistance work must have recoverable dispatch responsibility; failed and uncertain outcomes remain distinct; matching replay returns the original outcome and changed intent conflicts. | Fault injection before commit, after commit/before reply, during restart and on stale-client retry; exactly one intended effect with original outcome or explicit unresolved responsibility. |
| NFR3.2 | Job progress must be ordered and monotonic under one authoritative revision/sequence; late, repeated or out-of-order events cannot corrupt or regress terminal state; reconnect and polling recover the same snapshot. | Reconnect after known/missed events, sleeping tab, replaced worker, duplicate delivery and out-of-order schedules; assert authoritative snapshot and no regression. |
| NFR3.3 | No completion flag or source watermark may advance past verified stage effects; interrupted object/control/projection effects remain individually inspectable with repeatable non-corrupting recovery. | Interrupt each stage boundary; verify outstanding-effect listing, retry of reconciled stages only and rebuild from identified authoritative inputs with verified receipts. |
| NFR3.4 | Withdrawal and eligibility changes must propagate through ordered facts; stale caches, indexes, delayed projection generations and restored snapshots cannot restore prohibited content; saved references receive their dispositions through Library. | Withdrawal racing reads/publication/restore; delayed generation delivery; restore with newer restrictions than the backup; assert no prohibited serving and explicit dispositions. |
| NFR3.5 | Assistance accounting must settle idempotently for the intended operation across separate owner commits; unknown settlement stays reconcilable and never double-debits or silently disappears. | Crash each inter-owner boundary; duplicate completion/delivery; inspect original reservation/period and eventual single effect or safely unresolved state. |

### NFR4 — multi-user security

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR4.1 | Every protected read, list, page, command, event and asset delivery must enforce current actor, owner, source eligibility and scope from trusted context; browser-supplied roles, owner IDs, handles or locators never confer access. | Positive/negative boundary matrix with guest, owner A/B, expired/revoked session, maintenance-actor without scope; enumeration and effect-race cases; guest search accepts no owner identity. |
| NFR4.2 | Worker/executor events must authenticate current worker, unexpired lease/fence and expected revisions; expired or replaced claims cannot publish progress, failure or success. | Forged/expired/replaced claim tests, concurrent claimants, late success after replacement and same-worker duplicate delivery; assert one authoritative outcome. |
| NFR4.3 | Query, source-record, document model, citation and asset inputs are untrusted: bounded server-side validation, no fabricated content/edges, no traversal or arbitrary URL/path resolution, and rendered content cannot escape the permitted scope. | Malformed/oversized/Unicode/punctuation fixtures, traversal attempts, hostile markup/instruction fixtures and provider oddities; assert bounded errors and no fabricated output. |
| NFR4.4 | Private material must stay out of client-visible content, generic receipts and logs; asset delivery is opaque and capability-checked; error responses do not reveal foreign existence or private identifiers. | Inspect responses/cache/logs; cross-owner error-shape tests; handle guessing and replay attempts; secret-free diagnostics under fault. |

### NFR5 — privacy and permitted processing

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR5.1 | Source copying, storage, parsing, embedding, model use and asset delivery require resolved per-paper/provider permission evidence; unresolved permission yields a truthful ineligible/`POLICY_UNRESOLVED` outcome, never silent processing. | Permission-decision records per fixture and provider; blocked-fixture behaviour; no processing attributable to unresolved sources; public access is not assumed to permit every use. |
| NFR5.2 | Current eligibility revision dominates cached/indexed/projected/restored representations at every content, asset, search and model boundary; delayed contexts cannot re-enable prohibited processing. | Eligibility change with cached reads, in-flight jobs and stale generations; assert enforcement immediately from the authoritative revision. |
| NFR5.3 | Private and public identities stay separated: private identifiers never resolve via public corpus routes, and private material never appears in public projections, exports or fixtures. | Cross-boundary probes on resolve/read/search/asset routes; projection inspection; fixture hygiene checks. |

### NFR6 — usable and accessible controls

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR6.1 | WebWorkspace must preserve Korean labels, inherited blue/neutral tokens, Apple HIG-informed hierarchy and Light/Dark/System while meeting the proposed WCAG 2.2 AA target across discovery/reading/assistance surfaces, including long Korean text and compact reflow. | Implemented keyboard/focus, screen-reader labels/status/errors, contrast, zoom/reflow, target sizing checks at desktop/tablet/phone; manual evidence supplements automation; no conformance claim from prose. |
| NFR6.2 | States, degradations and failures must be distinguishable and announced (not color-only); retry, rebuild, withdrawal and accepted-work triggers state their scope and consequences and confirm deliberately; reads never trigger effects. | Behavior checks across loading/empty/partial/degraded/error/pending/expired/conflict states, destructive confirmations and recovery flows; assert announced state and skipped-effect counts. |

### NFR7 — repairability and reproducibility

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR7.1 | Preserve single domain ownership and typed contracts; extend the mounted application and C04–C06 owners rather than creating parallel corpus/search/job stores or hidden direct cross-owner writes. | Dependency/contract checks and differential source review of integration wiring, projection writer authority and migration paths. |
| NFR7.2 | One maintainer must reproduce setup, corpus/search/assistance failures and their repair using pinned dependency/build identities, explicit isolated configuration and synthetic fixtures; recovery instructions include safe stop and rollback conditions. | Fresh setup and seeded representative defect exercise with commands, diagnosis/repair/recheck durations and redacted evidence; artifact-only validation is not runnable parity. |
| NFR7.3 | Projection, embedding, parsing, model and citation-provider choices require compatibility, vulnerability/license and resource evidence, deterministic configuration validation and rollback/reconciliation consequences before use. | Lockfile/build checks, scoped audits, compatibility vectors and upgrade regression checks; no assumption that installed packages or successful imports prove suitability (see technology decisions). |

### NFR8 — sustainable free/local capacity

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR8.1 | All U3 technology/provider choices must operate within $0 and verified free/local permitted use; semantic search, embedding, local-model and citation paths that cannot meet this remain an explicit degraded/unavailable state, never a paid fallback. | Provider terms/limits and eligibility checks, local resource workload envelope and zero-overage configuration; surface evidenced conflict to the human without silent fallback. |
| NFR8.2 | Batch sizes, concurrent jobs, queues, retries, embedding/model workload, page and traversal limits and storage growth must be finite and reject or degrade cleanly at exhaustion without false success or lost committed data. | Boundary/exhaustion schedules for ingestion, citation provider limits, concurrent assistance, disk/pool saturation and recovery; record observed envelope and backpressure behaviour. |

### NFR9 — actionable, privacy-aware observability

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR9.1 | A user-visible discovery/reading/corpus/assistance failure must be traceable to capability/job/dependency evidence with safe identifiers and timestamps; logs/metrics omit credentials, private text and unnecessary query content. | Injected paper-job, ingestion, projection and provider failures traced end to end; secret/private-text scans; retention/access notes. |
| NFR9.2 | Readiness and status must distinguish observed, estimated, unknown and stale values; unavailable model/index/provider cannot appear healthy or zero-cost; recovery changes reported state only after capability checks succeed. | Controlled outage/unavailability of projection, embedding/model and provider paths; readiness inspection before/after recovery; labelled unknowns. |

### NFR10 — contract and integration consistency

| ID | Requirement and owner | Required evidence |
|---|---|---|
| NFR10.1 | Browser, service and workers must agree on identity, states, errors and compatibility per C04–C06/C13/C14: one executable state/event contract for job progress, valid frames, prepared-result shapes and distinct pending/ready/expired/failed/unauthorized semantics. | Real mounted contract/integration checks incl. stream framing/reconnect, prepared-result reads, dispatch and error mapping; existing U1/U2 consumers verified before changing externally relied-on behaviour. |
| NFR10.2 | Schema/version and index/model compatibility policy must be explicit before boundary implementation; incompatible generations refuse publication/degradation explicitly; test doubles are checked against the same contract and cannot return impossible success. | Compatibility vectors for publication and payload codecs, double-conformance checks and rollback/recovery paths; no silently reused legacy wire assumptions. |
