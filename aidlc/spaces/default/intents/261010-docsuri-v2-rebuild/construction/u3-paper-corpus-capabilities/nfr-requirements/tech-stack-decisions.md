# U3 technology decisions and evidence boundaries

Date: 2026-10-15 (Asia/Seoul). Unit: `u3-paper-corpus-capabilities`, an embedded library with browser contributions inside the shared application. This document records the integration baseline, candidate choices, evidence gates and measurement obligations for U3's corpus, discovery and assistance work. It selects nothing that lacks evidence and authorizes no spending: the $0 free/local budget remains binding, and unresolved permissions, terms or capacity leave the affected behaviour explicitly unavailable (BR7.6, NFR5.1, NFR8.1).

## Integration baseline (existing, to verify)

| Area | Baseline in the shared application | Required verification before extending |
|---|---|---|
| Backend/host | Python modules under `backend/` mounted by the local host with the shared owner-transaction facility (PostgreSQL) established by U1 and extended by U2; job/worker control loop (`backend/control_worker.py`, `backend/control_runtime.py`) with durable acceptance and settlement. | Current interpreter/package versions, lockfile identity, host wiring and worker behaviour against C06/C14; historical design statements are not live proof. |
| Persistence | PostgreSQL via the shared OwnerTransactions facility (real store; finite pool/statement/transaction limits). | Current schema/migration state, owner roles and restriction evidence for the corpus/search/assistance tables U3 extends. |
| Browser | Static React/TypeScript workspace (`frontend/`), strict TypeScript, native `fetch` Transport with authority generations, native `EventSource` (SSE) with `Last-Event-ID` and SWR polling fallback; Korean responsive shell from U1/U2. | C13 binding conformance for U3 routes and the C14 ordered-progress contract through the real transport. |
| Tests/tooling | Python venv + pytest, Ruff, coverage; pnpm + Vitest + Playwright; scoped U1/U2 runner scripts as the pattern for U3's runner. | Runner scoping, fixture isolation and bounded resource use for U3's phases. |

## Candidate decisions and evidence gates

| Decision area | Candidates under $0 | Constraints and gates |
|---|---|---|
| Corpus storage and parsing | PostgreSQL rows plus local filesystem for eligible content bytes; parsing with the legacy-inventoried free library family (for example pdfplumber/lxml/defusedxml equivalents) with hardened, bounded input handling. | Verify current dependency availability, licenses and security posture; input is untrusted (NFR4.3). No real-data copying before per-source permission evidence (NFR5.1). |
| Retrieval projection | PostgreSQL-backed lexical search (full-text/trigram-class) as the dependable baseline; semantic retrieval via a free/local embedding path only when capacity and compatibility are verified. | Snapshot-bound windows and stable ordering are behavioural requirements (BR4.3) independent of the engine chosen; provider/heavy-engine choices (for example a search cluster) need a measured capacity case under NFR8 before selection. |
| Embeddings and semantic mode | Free/local embedding runtime; alternatively an explicit `semantic-unavailable` disclosure with lexical fallback. | Compatibility vectors for index/model versioning (NFR10.2); unavailability is a designed state (BR4.2), never a fabricated result; resource envelope measured (NFR8.2). |
| Local model execution (assistance) | Free/local model runtime carried from U1's execution path, with bounded workload parameters. | The P1/P2 grounding evidence remains unresolved; normal summary/translation output stays gated until model readiness and permitted use are evidenced (NFR5.1, NFR8.1). Refusals must be explicit and recoverable. |
| Citation data | Local fixture provider for development plus an optional real metadata provider only when its terms and rate limits are verified free/local-compatible. | Freshness, partial coverage and unknown data are labelled (BR5.1); no paid fallback; traversal bounded (NFR8.2). |
| Job delivery and worker | The existing durable acceptance + owner-claim + progress path (C06/C14) on the shared worker; PostgreSQL-backed work records, no new broker. | One claim/fence with monotonic ordered progress and idempotent settlement (NFR4.2, NFR3.2, NFR3.5); closing the four recorded defects is a contract-conformance obligation (NFR10.1). |
| Corpus maintenance interface | Privileged maintenance operations under explicit corpus-maintenance authority (C04), consistent with U2's administrator separation. | Account membership alone is insufficient (BR1.1); run scope, idempotency and CAS publication verified. |

## Measurement requirements (before numeric targets)

- Measure at least: time to usable search result, time to readable content, first job progress, job acceptance, prepared-result read, and bounded-page reads; plus ingestion/embedding throughput and storage growth per source window.
- Record environment identity (machine, versions, configuration), workload description, dataset/corpus identity, sample size, cold/warm state, success/failure counts, and latency distributions (min/median/p95/max) with raw safe evidence.
- Contention cases: publication or refresh concurrent with reads; concurrent accepted assistance under finite capacity; citation provider rate-limit schedules.
- Exhaustion cases: bounded pool/queue/retry/model-concurrency limits, disk watermark and provider limits; confirm clean rejection/degradation without false success or lost committed data.
- Numeric service targets are proposed only after this evidence and human agreement (NFR2.2, NFR8.2).

## Contract coordination and compatibility

- C04–C06 own the operation semantics; C13 the browser binding; C14 the accepted-work delivery contract. U3 must verify existing U1/U2 consumers before changing relied-on behaviour and must not create a parallel writer or delivery mechanism (R-01, NFR7.1).
- Index/model/payload compatibility must be explicit and versioned before implementation; incompatible generations refuse publication or execution explicitly (NFR10.2), and test doubles are conformance-checked against the same contract.
- Every schema/version change carries compatibility and rollback/reconciliation consequences; the projection publication CAS and quarantine discipline is reused, not reinvented.

## Repairability

One maintainer must be able to reproduce U3's setup (pinned dependencies, isolated synthetic configuration, deterministic fixtures), diagnose representative corpus/search/assistance failures and verify a repair, using commands recorded with the evidence and redacted where needed (NFR7.2). Dependency, license and compatibility evidence accompanies any change to the lockfile or runtime (NFR7.3). Rollback instructions accompany migrations and publication changes.

## Explicitly not selected

No paid provider, paid model endpoint, new hardware, new broker or duplicated store is selected by this document. No numeric latency/throughput/retention value is selected. Source permissions, citation-provider terms, model readiness and workload policy remain evidence gates; until they close, the affected operations report truthful unavailability or degradation.
