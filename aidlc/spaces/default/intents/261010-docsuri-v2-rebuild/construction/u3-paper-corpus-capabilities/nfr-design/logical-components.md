# U3 logical components and failure domains

Date: 2026-10-15 (Asia/Seoul). Unit: `u3-paper-corpus-capabilities`. This is the logical (not deployment) component view of where U3's NFR patterns apply: component responsibilities, isolation, failure domains and blast radius inside CorpusContent, Discovery and PaperAssistance. It bridges the [security design](security-design.md) with Infrastructure Design, which will resolve process placement, storage layout and finite resource envelopes. The shared application baseline (host, PostgreSQL owner transactions, worker control loop, browser transport) is reused, not duplicated (BR2.3, NFR7.1).

## Logical component inventory

| Component | Owner | Responsibility | Durable state | Failure behaviour |
|---|---|---|---|---|
| CorpusMaintenanceRunner | CorpusContent | Accept ingestion/refresh/rebuild/retry runs; execute staged effects with per-effect dispositions; advance watermark only on verified work; produce change facts. | Run headers, stage effects, watermark, recovery evidence. | Run reports partial/failed with outstanding effects; reads keep serving the previous published generation; retry covers only reconciled stages. |
| ProjectionPublisher | CorpusContent | Sole logical writer of derived projection batches; manifest completeness, receipt verification, compatibility checks, CAS publication. | Batch receipts, published generation, manifests. | Refusal keeps the previous complete generation authoritative; no partial publication; watermark does not advance. |
| EligibilityAndChangeFactService | CorpusContent | Persist authoritative eligibility revisions and ordered, replayable change facts; serve them to consumers; drive restore replay. | Eligibility revisions, change facts. | Reads fail closed when current eligibility cannot be established; facts queue durably and replay harmlessly. |
| ContentReadAdapter | CorpusContent | Resolve exact paper/version identity; serve structured sections and opaque asset handles under current eligibility. | None beyond stores. | Explicit absent/building/unsupported/failed/withdrawn/restricted states; no substitution, no fabricated text. |
| QueryService | Discovery | Validate the shared query vocabulary; bind result windows to a snapshot; expose degradation state; produce completed-search facts. | Search executions, facts fenced by admission sequence. | Retrieval failure is an error state, never a successful empty result; expired snapshot is explicit. |
| RetrievalAdapters (lexical, semantic) | Discovery | Execute lexical and (when available) semantic retrieval against the published generation. | Index/projection reads only. | Semantic unavailability degrades to disclosed lexical fallback; incompatible index refuses explicitly. |
| CitationAdapter | Discovery | Bounded cited/citing traversal with provenance, freshness and coverage labels. | Snapshot cache within bounds (advisory). | Provider limits/outage produce labelled partial/unavailable views; existing saves unaffected; no fabricated edges. |
| HistoryFactProducer | Discovery | Emit owner-scoped completed-search facts with producer admission/completion sequence; expose the history checkpoint. | None beyond search executions. | Missing/duplicated delivery is reconciled by Library; replay executes no search. |
| AssistanceAcceptanceService | PaperAssistance | Validate options/eligibility/quota; commit immutable binding, reservation and dispatch responsibility before acknowledgement. | Jobs, bindings, reservations. | Crash after acceptance leaves recoverable responsibility; changed input conflicts; refusal states are explicit. |
| AssistanceExecutorBinding | PaperAssistance | Single claim/renew/reclaim with lease+fence; immutably read input payload; record ordered progress; complete/fail under current authority. | Claims, progress events, terminal state. | Replaced/expired workers cannot publish; stale events rejected; unknown settlement stays reconcilable. |
| ProgressAndResultStore | PaperAssistance | Serve the authoritative job snapshot and prepared results with pending/ready/expired/failed/unauthorized semantics; reads never mutate. | Progress, prepared results, availability. | Reads never generate work; expired results stay expired; partial coverage disclosed. |
| GlossaryService | PaperAssistance | Normalize and CAS-replace owner terminology; serve virtual-empty initial state; bind accepted revisions to jobs. | Glossaries, revisions. | Failed/conflicting writes preserve committed terms; conflicts visible. |
| Shared: Host and Transport | U1/U2 baseline | Session/origin checks, bounded body handling, authority generations, EventSource+polling, static web delivery. | Sessions, csrf. | Stream failures fall back to polling/snapshot; prior-owner state cleared by generation. |
| Shared: OwnerTransactions | U1/U2 baseline | Atomic owner-scoped transactions, revisions, idempotency receipts; finite pool/statement/transaction limits. | All owner tables. | Exhaustion rejects cleanly; no partial effects; recovery procedures documented. |
| Shared: Worker capacity | U1/U2 baseline | Execute accepted work under claims with finite concurrency. | Work records, claims. | Saturation queues with backpressure; progress truthful; no work loss. |
| Shared: Model runtime | U1 baseline (gated) | Local model execution for assistance when evidenced. | None (stateless execution). | Unavailable → assistance refusal/degradation; never a paid fallback. |
| External owners | Library, UsageEntitlements, AccountAccess | Consume change facts/dispositions, settle accounting idempotently, supply current authority. | Their own state. | U3 renders unresolved outcomes safely; never writes foreign records. |

## Failure domains and blast radius

| Failure | Blast radius | Containment design |
|---|---|---|
| Corpus run or its source connector fails | No new content/versions appear; existing reads unaffected | Previous published generation keeps serving; run evidence lists outstanding effects; watermark stalled (BR2.2). |
| Projection publication failure (manifest/compatibility/CAS) | New generation not published | Previous generation authoritative; discovery keeps reading it or reports `INCOMPATIBLE_VERSION`; no silent degradation (NFR10.2). |
| Eligibility store unavailable | Reads/commands involving protected content must not guess | Fail closed (`DEPENDENCY_UNAVAILABLE`/refusal) rather than serve uncertain eligibility (BR3.1). |
| Search index/embedding unavailable | Semantic (and worst case lexical) retrieval degraded | Disclosed degradation or actionable unavailability; no fabricated results (BR4.2). |
| Worker pool saturation | New accepted work delayed | Bounded queue with backpressure; acceptance refuses cleanly when capacity policy requires; progress remains truthful (NFR8.2). |
| Single assistance execution failure | That job only | Claim/fence recovery or terminal failure with settlement obligation; other jobs unaffected (BR7.3). |
| Model runtime unavailable | Assistance (and semantic retrieval) only | Explicit unavailable/refusal states; core reading/search continue (BR7.6). |
| Citation provider unavailable | Citation exploration only | Labelled partial/unavailable; saved references and reading unaffected (BR5.1). |
| Transport/stream interruption | One browser view | Snapshot + ordered replay + polling recover the same state (NFR3.2). |
| Telemetry adapter failure | Observability only | Operations continue; evidence retained in durable receipts (NFR9.2). |

## Isolation strategy and shared resources

- **Single writer per store.** Only the owning component writes its tables; readers (including Discovery reading publications) hold read-only access — no cross-owner writers (C04 R-01).
- **Reads are side-effect-free.** Read/inspect paths never enqueue, allocate, settle, clear or advance boundaries (BR2.4, BR7.4).
- **Execution isolation by claims.** Worker concurrency is bounded per owner and per operation class; a runaway or failed worker cannot affect others beyond its claim.
- **Shared resource protection.** Finite page/queue/batch/model limits protect the shared PostgreSQL pool and host resources; exhaustion degrades the affected operation, not the workspace.
- **Model runtime isolation.** The local model runtime is a bounded worker-side dependency; its unavailability cannot take down reading, search or account surfaces.

## Bridge to Infrastructure Design

Infrastructure Design (3.4) resolves what this view deliberately leaves open: process placement (one local application release with its worker and optional model runtime), storage layout (PostgreSQL tables plus protected local files for eligible content/artifacts), finite resource envelopes (pool sizes, queue depths, disk watermarks, model concurrency), backup/quarantine targets for restore, and the measured $0 capacity envelope (NFR8) with evidence per the measurement procedure. No deployment topology or cost decision is made here.
