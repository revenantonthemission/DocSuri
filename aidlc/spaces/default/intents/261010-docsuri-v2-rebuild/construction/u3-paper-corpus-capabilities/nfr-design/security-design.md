# U3 security and cross-cutting design

Date: 2026-10-15 (Asia/Seoul). Unit: `u3-paper-corpus-capabilities`. This document designs the concrete mechanisms that realize U3's derived quality requirements ([security requirements](../nfr-requirements/security-requirements.md) NFR1–NFR10) inside the existing shared application. The canonical contracts (C04–C06, C13, C14) remain authoritative for operation semantics; this design selects enforcement points, patterns and degradation behaviour — not implementation code, numeric targets or policy values. Unresolved evidence gates (source permissions, model readiness, provider terms, capacity policy) appear here as designed refusal/degradation states.

## Design principles

1. **Eligibility dominates every representation.** The authoritative eligibility revision is checked at each content, asset, search and model boundary; caches, indexes, delayed projection generations and restored snapshots are advisory copies that can never re-enable prohibited serving (BR3.1).
2. **One writer, compare-and-swap publication.** CorpusContent is the sole logical projection writer; publications are manifest-verified and CAS-switched; completion and watermarks advance only on verified stage effects (BR2.2–2.3, C04 R-01).
3. **Durable acceptance before acknowledgement.** Every accepted corpus run or assistance request persists its input, responsibility and (where applicable) reservation before the caller hears success; recovery is the default path for interruption (BR7.2).
4. **Single claim, monotonic progress.** One worker-bound lease/fence per intended operation; progress is an owner-allocated ordered sequence; terminal state never regresses; late workers cannot publish (BR7.3, C06).
5. **Bound everything and degrade honestly.** Queues, batches, retries, pages, traversal, model concurrency and storage growth are finite with explicit rejection; unavailability produces truthful states, never fabricated success or paid fallback (BR7.6, NFR8).
6. **Untrusted by default.** Queries, source records, document models, rendered content and provider payloads are untrusted inputs handled with bounded validation; secrets and private material never reach logs, receipts or client-visible content (NFR4.3–4.4).

## Authority and eligibility enforcement

- **Enforcement points.** Request → host/transport (session, origin/CSRF, bounded body) → owner operation admission (current account/role/maintenance authority from trusted context) → store transaction (owner-scoped rows, revision checks) → effect publication (claim/fence, eligibility recheck) → delivery (asset adapter, result read). Browser-supplied identifiers never confer access (NFR4.1).
- **Guest and owner paths.** Guest search/reading runs the separately authorized anonymous surfaces (`search` with no owner identity; no personal facts, tickets or jobs) (BR1.2, C05). Authenticated paths derive the owner from the session and recheck it on every page and effect.
- **Eligibility checks.** `resolvePaper`/`readContent`/`readAsset`/`search`/assistance admission and execution recheck the current eligibility revision and purpose permission; `SOURCE_INELIGIBLE`/`NOT_FOUND`-with-disposition outcomes replace stale content (BR3.1, BR6.1–6.3).
- **Opaque asset delivery.** Figures/assets are served only through authorized handles resolved by the delivery adapter under current eligibility; arbitrary paths, URLs and private identifiers are rejected by construction (BR6.3).
- **Maintenance authority.** Corpus runs/retries/eligibility changes require the explicit corpus-maintenance actor and scope; account membership or role alone is insufficient (C04 operations, BR9.2).

## Projection publication and corpus-run integrity

- A run is accepted with a durable input snapshot and dispatch responsibility; the same idempotency key and input return the same run, changed input conflicts (BR2.4, NFR3.1).
- Stage effects (object/content, control rows, projection batches, publication) each record their outcome; a stage cannot complete without its verified effect; the run read exposes committed watermark plus per-effect dispositions.
- Projection batches are idempotent (`batchId`+hash acknowledge once, changed hash conflicts); publication CAS-verifies manifest completeness, all receipts, current eligibility and version compatibility; failure keeps the previous publication and stalls the watermark (BR2.2–2.3, NFR3.3).
- Rebuild identifies authoritative inputs and verifies durable receipts; restore into a quarantined target replays current withdrawal boundaries before serving (NFR3.4, BR2.4).

## Source-change and disposition propagation

- Eligibility changes persist an authoritative revision plus an ordered, replayable change fact; reads enforce the revision immediately, before any cache/index repair (BR3.1–3.2).
- Consumers (Library) consume facts in order and persist their own explicit dispositions for saved references; duplicate delivery is harmless and creates no duplicate history; U3 never writes Library records (BR3.3, C04 `readSourceChanges`, C05 history facts).

## Assisted-work delivery design (closing Q-01–Q-04)

- **Acceptance.** Binding = owner + exact paper/version + content hash + option ids + glossary revision + reservation; committed with original `acceptedAt` and dispatch responsibility before acknowledgement; same key returns the original job; changed input conflicts (BR7.2, C06 `acceptAssistance`).
- **Execution.** A trusted executor acquires a single claim (lease + fence) against the immutable binding; renew/reclaim advance only the lease revision; expired or replaced claims cannot renew or publish; owner time, not caller time, governs expiry (NFR4.2, C06 claim operations).
- **Progress.** One executable state/event contract through the mounted transport: the job read exposes the authoritative revision/sequence; streamed events carry owner-allocated sequence; stale/repeated/out-of-order events are rejected; snapshot + ordered replay cover reconnect, missed progress, sleeping tabs and polling fallback (Q-01, Q-03, Q-04; BR7.3; C13/C14).
- **Completion.** Success requires a prepared result validated against the accepted binding (source hash, options, glossary) committed with terminal revision/sequence and settlement obligation in one owner transaction; result reads distinguish pending/ready/expired/failed/unauthorized and never regenerate work (Q-02; BR7.4, NFR10.1).
- **Settlement.** UsageEntitlements settles idempotently for the intended operation; unknown settlement stays reconcilable and is never guessed into a refund or a second debit (BR7.5, NFR3.5).

## Degradation, capacity and $0 guardrails

| Condition | Designed behaviour |
|---|---|
| Semantic/embedding capability unavailable or incompatible | Disclosed `semantic-unavailable` degradation with lexical fallback, or actionable unavailability — never fabricated semantic results (BR4.2, NFR8.1). |
| Model runtime unavailable / P1–P2 evidence unresolved | Assistance options mark the affected actions unavailable or refuse admission with `POLICY_UNRESOLVED`/explicit failure; no placeholder output (BR7.1, BR7.6). |
| Citation provider limits, stale or missing data | Labelled freshness/coverage, bounded traversal, existing saves preserved; no fabricated edges (BR5.1). |
| Source permission unresolved | `SOURCE_INELIGIBLE`/`POLICY_UNRESOLVED` at admission/process/deliver boundaries; blocked fixtures recorded honestly (NFR5.1). |
| Queue/pool/retry/page/traversal/model concurrency bounds reached | Explicit rejection or bounded backoff; no false success, no lost committed work, no unbounded retry (NFR2.3, NFR8.2). |
| Storage/disk watermark reached | Refuse new accepted work cleanly with evidence; preserve committed state; recovery procedures documented (NFR8.2, NFR3.3). |

Finite limits (batch size, run concurrency, queue depth, retry counts, page sizes, citation node/depth bounds, model concurrency, retained page/result retention) are configuration with recorded evidence before operation; numeric values are agreed after baseline measurement (NFR2.2).

## Observability, readiness and repairability

- Every accepted operation carries an owner-scoped correlation identifier into its progress, receipts and telemetry; user-visible failures can be traced to capability/job/dependency evidence without exposing private text, queries or credentials (NFR9.1).
- Readiness distinguishes observed, estimated, unknown and stale values across projection, embedding/model, citation-provider and worker paths; recovery flips the reported state only after capability checks succeed (NFR9.2).
- Structured logs record state transitions (admission, stage effects, publication, claims, settlement) with bounded fields; telemetry failure cannot erase required evidence (NFR9.2).
- One maintainer can diagnose a representative corpus/search/assistance defect from a clean checkout using pinned dependencies, isolated synthetic configuration and the recorded runner phases; repairs follow the rollback/reconciliation discipline of migrations and publications (NFR7.1–7.3).

## Input trust and secret handling

- Query, source-record, document-model and provider payload validation is server-side, bounded and vocabulary-checked; malformed/oversized/Unicode-edge inputs produce defined outcomes (BR4.1, NFR4.3).
- Rendered content and document instructions are untrusted evidence; they cannot change authority, approval or external-effect behavior (NFR4.3, NFR5.3).
- Receipts, errors and logs are secret-free; asset handles are opaque; error shapes do not reveal foreign existence, revisions or private identifiers (NFR4.4).

## Requirement mapping

| Requirement | Design section |
|---|---|
| NFR1.1–1.3 | Authority/eligibility, publication integrity, assisted-work delivery |
| NFR2.1–2.3 | Assisted-work delivery, degradation/capacity, observability |
| NFR3.1–3.5 | Publication integrity, change-fact propagation, assisted-work delivery, degradation/capacity |
| NFR4.1–4.4 | Authority/eligibility, input trust and secret handling |
| NFR5.1–5.3 | Authority/eligibility, change-fact propagation, input trust |
| NFR6.1–6.2 | Degradation/capacity (truthful states), assisted-work delivery (announced progress) |
| NFR7.1–7.3 | Observability/readiness/repairability, design principles |
| NFR8.1–8.2 | Degradation/capacity, $0 guardrails |
| NFR9.1–9.2 | Observability/readiness/repairability |
| NFR10.1–10.2 | Assisted-work delivery, publication integrity |

Every mechanism above is exercised through the real mounted boundary in the corresponding evidence phases (NFR10.1); this document claims no implementation or conformance by itself.
