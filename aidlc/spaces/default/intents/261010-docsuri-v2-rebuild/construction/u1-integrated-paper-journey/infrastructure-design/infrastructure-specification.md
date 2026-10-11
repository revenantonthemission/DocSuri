# U1 infrastructure specification

Date: 2026-10-11. Unit: `u1-integrated-paper-journey`. This is the physical design
for an isolated local U1 implementation and its evaluation. It selects a common
PostgreSQL transaction facility on executed primitive evidence. Other bindings
below explicitly distinguish implementation candidates from proven mechanisms.
There is no deployed v2 application, public-host selection, migration decision or
claim of complete operating feasibility in this document.

The [confirmed proposal](infrastructure-design-questions.md), [logical owners](../nfr-design/logical-components.md),
[functional specification](../functional-design/functional-spec.md), [component catalogue](../../../inception/domain-design/components.md)
and [contracts](../../../inception/contract-design/contract-summary.md) remain binding.
All current capabilities remain required across the eight units. No technology
substitution closes a capability requirement without its behavioral checks.

## INFRA01 — Deployment

| Facet | Choice | Rationale |
|---|---|---|
| Compute model | Hybrid local experiment: native application/API, worker and local model process; one isolated PostgreSQL container. One shared application release, with future U7 operator executable separately controlled. | Native inference can use this Mac's GPU; existing Linux container VM has only 2 CPUs and 2,054,840,320 bytes RAM. Model inference does not fit that VM allocation. No VM enlargement, cloud account or public host is selected. |
| Application runtime | Python 3.13.7 with FastAPI/Uvicorn is the implementation candidate; explicit owner packages and constructor composition, one API process and one worker process. | Retains the Python parsing/model/API lineage without copying legacy wiring. Compare the first mounted slice against its contracts and locked dependency closure before relying on the candidate. Existing runtime availability is not that proof. A TypeScript-only backend would reduce languages but add a parser/model integration port; no measured benefit yet justifies it. |
| Web build | React/TypeScript with a static Vite build, served by the same application origin, is the proposed U1 binding. No separate Node server at run time. | The approved workspace does not require a second server to express its state. This reduces operating processes relative to the existing Next server/BFF approach. Deep links, authenticated return, streaming/recovery, all retained page behavior and accessible Korean rendering must pass a mounted comparison before selection; no SEO/SSR capability is silently removed. Node 24.14.0 is present; dependency versions are locked and audited during the build probe, not inherited as safe from the old package file. |
| Networking topology | Browser → loopback application; application/worker → loopback database publication and private local model listener. No VPC, public ingress, tunnel, CDN or load balancer. | Explicit origin/Host allowlist, CSRF protection and server-side owner authorization apply even locally. Private ports are inaccessible to the browser through application routes. A loopback listener is not multi-user host isolation. |
| Storage strategy | One dedicated PostgreSQL database on a persistent Docker volume for owner state, guards, jobs and projections; private local files for immutable source/result artifacts, with authoritative owner metadata in PostgreSQL. | Enables a shared serializable commit boundary without merging business ownership. Persistent volume, file flush/rename and coordinated backup need actual adapter tests; the design does not extrapolate process-crash results over tmpfs to media durability. |
| Environments | Separate experiment namespace with synthetic accounts and purpose-eligible P1/P2 material; isolated restoration namespace. Development uses the same real adapters. Public staging/production remain unselected. | Never seed from an unidentified existing database, reuse service credentials or change current users/data. Fake adapters are visibly diagnostic and cannot satisfy the normal journey. |
| IaC approach | Versioned local manifest/supervisor and Compose description for the database, plus pinned dependency/image/model manifests; implementation belongs to Code Generation. | No paid control plane or large IaC framework is needed for this local assembly. Record exact commands, resource limits, lifecycle and cleanup. Container tags alone are insufficient pins. |
| Resource sizing | Separate probe profiles and a provisional mounted profile in INFRA05. One expensive inference/embedding execution permit. No automatic horizontal scaling. | The 24 GiB host is shared with other work; observed spare capacity is not reserved capacity. Profiles must pass combined-load and recovery checks before enablement. |

FastAPI's [ASGI deployment documentation](https://fastapi.tiangolo.com/deployment/manually/)
supports a native Uvicorn process; Vite's [static build documentation](https://vite.dev/guide/static-deploy.html)
supports the proposed browser packaging. Those sources establish packaging options,
not compatibility, security or DocSuri performance. These candidates require the
first clean locked build and mounted contract/UI slice before broader application
implementation depends on them. If the slice fails, repair or reassess within
the same capability and $0 constraints rather than declaring selection by prose.

## INFRA02 — Infrastructure Services

| Service | Role | Configuration | Notes |
|---|---|---|---|
| PostgreSQL 16.15 | Common database and serialization facility | Cached arm64 image `postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6`; checksums, fsync, synchronous_commit and full_page_writes on; bounded pools/timeouts; separate migration credential | Selected for implementation on [storage evidence](evidence/storage-evaluation.md). Eight synthetic checks passed. Role grants, full race matrix and persistent-volume conformance remain required. Single primary, no replica/failover promise. |
| Owner repository adapters | Durable state, receipts, jobs, reservations and required incidents | Owner schemas and typed APIs; account/source guard participants in the same transaction facility; application identity cannot perform arbitrary cross-owner writes | Business ownership remains with each approved component. A database superuser was used only in the disposable primitive test and is prohibited as a normal runtime credential. |
| PaperAssistance durable queue/outbox | Accepted work, delivery, claims and recovery | PostgreSQL owner tables, atomic acceptance + durable relay intent; bounded polling of eligible rows, exclusive current claim/fence and original acceptedAt; ordered event cursor | No Redis/SQS/broker dependency in initial assembly. Delivery retries do not create a new accepted operation. In-process tasks cannot be the sole queue. |
| Corpus projection | Lexical and dense semantic retrieval candidate | PostgreSQL text index plus normalized searchable fields and stored versioned 1,024-dimensional vectors; bounded native exact cosine ranking over eligible candidates | CorpusContent is sole writer/rebuilder/withdrawer; Discovery reads. PostgreSQL `simple` tokenization is not assumed adequate Korean analysis. BGE dense retrieval and exact ranking require multilingual relevance, filters, cursor and full retained-mode checks. No claim of OpenSearch/BM25/ANN equivalence. |
| Private artifact files | Immutable eligible source, prepared output and backup bundles | Dedicated mode-0700 root, opaque generated paths, mode-0600 files; bounded temporary write → flush → immutable publication → owner metadata commit; hash/length/type/revision bound | Application-mediated current authorization on every read; no public file URL, directory traversal or symlink-following. Orphans are owner-reconciled, not blindly deleted. Partial files cannot be returned as acknowledged results. |
| Local inference | Qwen3 8B candidate for bounded source assistance/translation | Ollama 0.40.2; cloud disabled in isolated server; exact model identity, one active model/call, finite context/output/deadline, explicit allowlist, no pull/fallback during execution | [Eligibility](evidence/model-source-eligibility.md) and [executed evaluation](evidence/model-evaluation.md) delimit actual usefulness and remaining failures. Normal U1 readiness requires complete useful P1/P2 and supported translation, not model reachability. |
| Local embeddings | BGE-M3 dense candidate | Exact cached identity and revisioned chunk policy; `truncate:false`; explicit context; one shared expensive-work permit with generation | A short diagnostic cannot establish Korean recall, corpus capacity or all source lengths. Missing embeddings never masquerade as semantic search. |
| Optional cache | Bounded per-process read cache, initially disabled unless measured useful | No authority, quota, claim or durable receipt solely in cache; source/policy/revision-aware keys; finite size/age | Avoid an extra cache daemon for an unmeasured benefit. Recovery and correctness must work without it. |
| Observation | Local structured events, finite aggregates and protected operations view | [MON01–MON06](monitoring-design.md), 64 MiB optional evidence budget plus separate mandatory owner records | No external account, telemetry export or paid paging. |
| DNS/CDN/load balancing/email | Public-service bindings unselected; local test mail sink only when account flow needs it | No public DNS or cloud provisioning; never deliver real mail through an unverified free quota | A captured verification/reset message is a local flow test, not evidence of public email delivery, anti-abuse capacity or public registration readiness. |

PostgreSQL [text search](https://www.postgresql.org/docs/16/textsearch-intro.html)
and [pattern matching](https://www.postgresql.org/docs/16/functions-matching.html)
offer primitives, not a complete DocSuri search policy. The exact-vector candidate
avoids downloading an extension for the tiny first corpus and exposes an honest
finite corpus limit. pgvector or the retained OpenSearch adapter remains an
alternative if measured relevance/filtering/update/capacity requirements cannot
be met. An experiment corpus cap does not reduce eventual product parity.

## INFRA03 — Shared Infrastructure

| Shared Resource | Owner Unit | Consumer Units | Access Boundary |
|---|---|---|---|
| Shared application composition/release | U1 establishes; U8 completes | U2–U6 contributions; U8 integration | Register only installed capabilities and lifecycle participants. Initial core cannot import future modules. U1/U8 are successive assemblies, not duplicate services. |
| PostgreSQL transaction facility | U1 provisioner; each component owns its records | U2–U6 and U8 through their assigned components | Technical sharing grants no business write permission. U7 operator scope/credentials are separately controlled and do not inherit application superuser access. |
| Account/source authority guards | AccountAccess/CorpusContent established in U1 | Every protected component as its unit is installed | Guard participant locks and evaluates current authority inside the protected commit transaction. Only its authority owner mutates its barrier. |
| Corpus projections and eligible artifact storage | CorpusContent in U1, completed by U3 | Discovery, assistance, research, topics, approved export as authorized | Exact source/version/purpose and current owner policy on query, dispatch, publication and read. Derived caches are withdrawable and rebuildable. |
| Execution resource permit | U1 executor; ServiceOperations allocation | U3–U6 work as added, U8 cumulative validation | Shared finite CPU/RAM/storage/model budget; no module invents a private unaccounted worker pool. Owner job/accounting responsibilities stay separate. |
| Observation and lifecycle registry | U1 initial ServiceOperations; U8 complete | All installed units; U7 exposes only its authorized interface | Read-only evidence aggregation; owner commands perform repair. Unknown mandatory participant blocks scoped readiness. |

## INFRA04 — Transactions, worker fencing and durable artifacts

| Boundary | Concrete binding and failure behavior | Required implementation proof |
|---|---|---|
| Protected owner mutation | PostgreSQL SERIALIZABLE transaction; stable account/session/consent → source/version → target lock order. Read/lock existing owner guard records, evaluate current permission, perform target-only conditional mutation + receipt, commit. | Both revocation/effect orders over all actual participants; missing authority rejects; deadlock/serialization retry uses same intent and finite budget. Never substitute an unguarded cached boolean. |
| Authority mutation | Authority owner's barrier update serializes against the same locks. Stable missing-row guard strategy is provisioned by the owner; an absent session/source cannot mean allow. | Account deletion, consent change, source withdrawal/version change, current read and payload grant; no foreign owner barrier update. |
| Replay and CAS | Durable operation identity binds caller, normalized original intent and expected revision. Current authorization precedes exact receipt replay; fresh commands then check CAS. | Same intent returns original receipt after later state changes; changed intent conflicts. Required browser preconditions and canonical types must be amended together before code. |
| Admission/accounting | PA durable admission intent/capacity hold, Usage reservation, PA authoritative acceptance, durable reconciliation across separate owner commits | Unknown outcome retains obligation; release requires closed intent fencing late acceptance. Recovery capacity cannot be loaned to new admission. Do not claim a single cross-owner exactly-once transaction. |
| Execution | Owner-issued bounded claim and leaseRevision/fence, worker identity, immutable payload hash; expensive work outside guard transaction; current grant at payload/dispatch boundary | Replacement rejects stale progress/result/failure; durable acceptance and original acceptedAt survive crash; duplicated delivery alone has no effect. |
| Winning completion | Private immutable staged output, then current authority/current claim owner transaction publishes exact result binding, terminal state, fact receipt and durable settlement obligation; Usage idempotently settles, PA records receipt | Late worker cannot win; lost settlement reply reconciles. File corruption/write failure/unknown permission never gives a success acknowledgement. |
| Empty glossary/history | PA owns virtual immutable non-null empty revision and accepted snapshot; Personalization only supplies preferences/defaults. Retained history reads exact owner/paper/version with stable acceptedAt/jobId cursor. | No read-side create, no U1 glossary edit UI; later first edit CAS protects absent creation. Refresh/read does not start work or charge. |

The [storage probe](evidence/storage-evaluation.md) established relevant database
primitives, not these full application boundaries. The ten browser mutation
bindings, claims/payload/fence types and retained-result discovery still need the
[canonical amendment plan](../functional-design/contract-revision-plan.md).
Contract R-02 draft allocation/rediscovery remains U4. Existing accepted findings
are not closed by this infrastructure document.

## INFRA05 — Finite resource and policy envelopes

| Profile | Allocation and stop behavior | Evidence/status |
|---|---|---|
| Observed host | 24 GiB RAM, 14 logical CPUs. Available filesystem space changed from roughly 11.8 GiB to 16.1 GiB during this session; Docker VM 2 CPUs/~1.91 GiB. | Dated shared-machine readings, not reserved resources or a public-server specification. Remeasure each run. No unrelated process/data was removed to create headroom. |
| Storage primitive probe | ≤512 MiB container memory, 0.5 CPU, 64 PIDs, read-only root, no network, 256 MiB tmpfs, ≤55 seconds | Completed; PostgreSQL final sample 72.27 MiB, not peak. SQLite separately ≤64 MiB files and ≤45 seconds. |
| Model probe | One model/call, context 2,048, output ≤224 tokens, 90-second generation /60-second embedding client deadline, 2 CPU threads, start only ≥35% memory-pressure free reading and ≥8 GiB disk; abort process group below 20% or disk floor | Experimental values, not SLOs. This is sampled supervisory enforcement, not a native process hard-RAM/GPU reservation. Between-call floor initially stopped a run; preserve that evidence. No concurrent application workload was measured. |
| Combined mounted candidate | PostgreSQL container ≤512 MiB/0.5 CPU; native API ≤256 MiB target, worker excluding inference ≤256 MiB target, observation ≤36 MiB working set; one model with an 8 GiB sampled resident ceiling; browser/harness allowance 1 GiB; host headroom floor as above | Approximately 11.5 GiB planned working envelope including Docker VM overhead (VM total replaces, does not add to, its database allocation). Native ceilings need measured supervisor enforcement; browser and GPU memory can exceed estimates. Do not admit the mounted workload until fresh combined-load measurement supports it. |
| Incremental probe disk | Total ≤512 MiB physical growth: database/WAL/staging 128 MiB, artifact/input/output 64 MiB, optional observation 64 MiB, backup/restore 128 MiB, build/probe scratch 64 MiB, recovery reserve 64 MiB | Existing model/image bytes are inventoried separately; model probes use APFS copy-on-write copies, not duplicate downloads. Measure actual growth and stop before shared 8 GiB free floor. Logical ledger is not a filesystem quota or guarantee against unrelated writers. |
| Mounted disk candidate | Dedicated persistent volume and file roots; choose manifest caps after the clean build measures actual dependency/build/database/backup sizes | The 512 MiB probe cap is not asserted sufficient to install/build the application. No install is authorized to silently exceed available space. Reuse audited caches only by identity; present an evidenced capacity conflict before expanding scope, spending or deleting user data. |

All effective admission limits must be finite. Candidate starting values for the
small synthetic mounted experiment are two accounts, two eligible papers, at most
256 projection chunks, page size 20/max 100, query 2 KiB, JSON request 16 KiB,
two accepted outstanding jobs per owner/four global, one model execution,
result ≤128 KiB, source fixture ≤2 MiB each, model context/output/deadlines as
above. These are evaluated policy revisions, not public-service product limits.
Larger approved capability cases require another recorded finite profile.

Database candidate limits: 12 connections including two reserved recovery/admin
slots; app pool four, worker two, observation one, maintenance one, spare two;
32 MiB shared_buffers, 2 MiB work_mem, 5-second statement/idle-transaction timeout,
2-second lock timeout; at most two transaction retries inside a 10-second total
request deadline. Long model calls cannot hold database transactions. Finite
claim policy candidate: 30-second lease, renew every 10 seconds, authoritative
database time, 90-second execution deadline, two replacement attempts within a
five-minute job recovery window; expired recovery becomes visible intervention,
never silent deletion or automatic release of unknown reservations. Validate
pause/sleep, clock changes, real load and fencing before enabling these values.

No admitted job may depend on unspecified reset, retention or reconciliation
semantics. Synthetic fixture quota is four logical work reservations per account
per experiment with no automatic reset; explicit fixture teardown only after
settlement/unknown disposition is recorded. This is not a replacement for the
retained subscription/quota/reset behaviors delivered in later units. Required
receipts/audit cannot be evicted for optional logs or new requests.

## INFRA06 — Access, secrets, permitted processing and lifecycle

| Concern | Concrete design | Closure boundary |
|---|---|---|
| Network and execution trust | Same-origin browser API, strict trusted Host/origin, CSRF, authenticated owner checks; no public raw database/model listeners. Database port published only loopback with SCRAM credentials; isolated model port never used directly by browser. | Test hostile origin/Host and raw-port exposure. Native loopback cannot distinguish other local users; until OS account/network isolation is proved, synthetic local experiment only. |
| Secrets | New experiment-only generated secrets in excluded mode-0600 files; process-specific reads, no browser/env bundle/log/PR; migration credential separate from runtime; startup refuses default/reused credentials | File access/rotation/revocation and redaction canaries required. No current `.env`, cloud credentials or production keys are copied. |
| Model routing | Dedicated local model server with OLLAMA_NO_CLOUD=1 verified in logs, explicit cached digest/allowlist, no request-selected host/model or fallback, no runtime model pull | Cloud disable is observed, network-denied execution not yet proved. Model documentation/license/notice gaps and allowed recipients remain in evidence; no remote private-material processing. |
| Paper eligibility | Exact P1/P2 versions, section/span/hash and local research purpose bound in fixture manifest; private extracted inputs/outputs only for the bounded assessment | arXiv research-use basis does not authorize public full-text/translation redistribution. Public serving/other purposes remain disabled until rights established. Prefer links/eligible metadata for unapproved content. |
| Account/browser data | Synthetic separate owners; HttpOnly session policy, volatile account-scoped client state; clear on switch/logout, fresh authorization after return | No real private browser persistence pending policy. U4 durable draft retention/deletion/conflict/shared-device rules remain prerequisites. |
| Experiment retention | Raw source/model outputs under protected `/tmp/docsuri-u1-infra-*` roots; remove within 24 hours or earlier at verified evidence extraction; retain compact hashes/outcomes and permitted minimal excerpts in the record | These dates/caps do not set production retention. Never remove unknown user files, unresolved owner receipts or backups to make room. |
| Current restrictions | Lifecycle registry requires every installed owner's withdrawal/revocation/deletion/backup participation; guarded current checks at read, payload, dispatch and commit | Processed bytes already delivered/in-flight may be irreversible; no promise of undoing external effects. Restrict new effects, dispose eligible staged results and record limitations. |

## INFRA07 — Backup, restoration and recovery

| Step | Local binding and required evidence |
|---|---|
| Capture | Stop new mutations/execution for the small experiment, drain or record every accepted unresolved responsibility; capture database logical dump, schema/role manifest, immutable artifact hashes and required keys in a single owner-coordinated checkpoint. Include receipts, claims and accounting obligations. |
| Destination | Protected separate restore directory/volume within its finite allocation. Same-disk copies test restoration only and are not disaster recovery. A physically independent permitted backup destination and real users/data authority remain unresolved. |
| Verify | Restore into a new namespace with serving/dispatch/external effects disabled; compare acknowledgement ledger, hashes, permissions, schema, obligations and exact source/result references; preserve failures. |
| Reconcile authority | Obtain current revocation/consent/withdrawal/erasure facts; invalidate restored sessions and claims and reconcile accepted work through owners. Missing current authority keeps affected reads/effects closed. An older allow in backup is not current permission. |
| Reopen | Owner consistency checks and fresh scoped mounted journey pass; human-visible recovery report records loss, duration, unresolved cases and intervention. No numeric RPO/RTO claim until measured and agreed. |
| Fault matrix | Process crash, container replacement, VM restart over intended volume, filesystem full/partial/denied, artifact corruption, lost reply, worker replacement, late settlement, backup during declared state and host sleep/wake. True power/media loss remains separately evidenced. |

Rollback follows [PIPE06](cicd-pipeline.md): stop/replace the small single-instance
release only after compatibility/preflight. Do not restore an old database as a
routine code rollback or resurrect revoked permissions. Destructive migration
reversal and irretrievable external effects need separate explicit treatment.

## INFRA08 — Observability and delivery bindings

| Design area | Binding | Verification |
|---|---|---|
| Local observation | [MON01–MON06](monitoring-design.md): bounded JSONL/aggregates, mandatory owner incidents separately durable, freshness and drop evidence | Saturation/redaction/stale-clock/fallback tests; no content/prompts/secrets in optional logs. |
| User-visible measurement | Monotonic browser milestones + owner operation/claim/result/settlement correlation; complete planned cohorts | Useful outputs, rejected/failed/unresolved attempts and missed opportunities remain visible. No baseline-derived SLO invented here. |
| Delivery | [PIPE01–PIPE06](cicd-pipeline.md): clean lock/build, actual adapter checks, mounted normal-model path, artifact provenance, same-build promotion and recovery | Current legacy CI is evidence only within its actual reach. Exact runnable v2 completion invocation remains **UNSET** until the human approves it. |
| Git | [CONVENTIONS.md](../../../../../../../../CONVENTIONS.md): working branch → PR into develop; fulfilled branch removed; next branch from develop; main separate release promotion | Compare exact base/head inherited failures and verify changed work. No CI rewrite or main deployment performed by these documents. |

## INFRA09 — Decision closure and remaining prerequisites

| Decision / owner | Status after this pass | Next required evidence |
|---|---|---|
| Common transaction facility / architecture + owners | PostgreSQL selected for implementation; SQLite credible alternative with narrower writer concurrency and simpler administration | Real roles/guards/repos, persistent storage and actual-worker fault matrix; no production migration implied |
| Application/browser packaging / WebWorkspace + ServiceOperations | Python/FastAPI and React static build proposed; runtime availability and documented packaging verified | First clean locked build and mounted contract/UI slice before depending on framework choice; exact dependency licenses/security and resource use |
| Retrieval/model / CorpusContent + Discovery + PaperAssistance | Bounded local candidates evaluated; useful-output gaps and operating limits in evidence | Complete eligible P1/P2 search/understanding/translation, Korean relevance, extraction math fidelity, exact prompt/model manifest and combined-load capacity |
| Authoritative users/data / owners + human | Unresolved | Establish service/data/backups and consumers before continuity/migration choice; no inferred empty service |
| Public hosting and integrations / ServiceOperations + each adapter owner | Unselected | $0 DNS/TLS/network/security/abuse, delivery email, provider terms/quotas/outage behavior, operating capacity and permitted content/data handling |
| Privacy/retention/shared device / owners + human where policy choice needed | Local synthetic research envelope only | Resolve real data and U4 draft policy before affected persistence or processing |
| Baseline and completion / quality + human | Primitive experiments do not establish U1 success or service targets | Mounted real journey/fault/repair baseline; human-selected numeric targets and separately approved exact completion command |

These remaining checks are implementation/operating entry conditions. They do
not prohibit reversible experiments that generate the missing evidence. No
candidate is reported ready for public operation while its condition is open.

## INFRA10 — Traceability and verification boundary

[traceability.json](traceability.json) maps all 37 derived NFR identifiers to
concrete sections in this package. `OK` means the design obligation has an
explicit resource/configuration and closure condition, not a passed runtime test.
The [storage evidence](evidence/storage-evaluation.md), [source eligibility](evidence/model-source-eligibility.md)
and [model evaluation](evidence/model-evaluation.md) preserve executed outcomes and
limitations independently from proposed configuration.

Inputs: [performance](../nfr-design/performance-design.md),
[security](../nfr-design/security-design.md), [scalability](../nfr-design/scalability-design.md),
[reliability](../nfr-design/reliability-design.md), [observability](../nfr-design/observability-design.md),
[logical components](../nfr-design/logical-components.md), [technology comparison](../nfr-requirements/tech-stack-decisions.md),
[functional behavior](../functional-design/functional-spec.md), [components](../../../inception/domain-design/components.md),
[canonical contracts](../../../inception/contract-design/contract-summary.md) and
[unit catalogue](../../../inception/units-generation/unit-of-work.md).

Validation checks document structure, links, exact requirement coverage and
consistency. Independent review challenges implementability and claims. Neither
is a mounted application test or evidence that all current capabilities work.
