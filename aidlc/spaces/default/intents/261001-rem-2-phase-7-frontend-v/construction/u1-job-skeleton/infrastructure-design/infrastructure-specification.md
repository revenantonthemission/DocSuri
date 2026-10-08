# U1 Infrastructure Specification

## Sources

The confirmed `infrastructure-design-questions.md` selects the existing server, isolated same-server staging, CI-qualified server-side pull delivery and qualification of persistent ElasticMQ messages. The consumed designs are `../nfr-design/performance-design.md`, `../nfr-design/security-design.md`, `../nfr-design/scalability-design.md`, `../nfr-design/reliability-design.md`, `../nfr-design/observability-design.md`, `../nfr-design/logical-components.md`, `../functional-design/functional-spec.md`, `../../../inception/domain-design/components.md` and `../../../inception/contract-design/contract-summary.md`. Detailed requirement IDs come from `../nfr-requirements/` and the NFR Design traceability map.

Workspace source evidence: `ops/server/{README.md,install.sh,run.sh,tunnel-setup.sh,heartbeat.sh,docsurictl}`, `backend/{docker-compose.yml,elasticmq.conf,Dockerfile}`, `backend/migrations/{registry.py,__init__.py}`, `backend/modules/summarization/{migrations/002_create_content_jobs.sql,migrations/003_content_job_authority_prepared.sql,src/summarization/adapters/_pg.py,src/summarization/adapters/settings.py}`, `backend/modules/accounts/{migrations/013_block_late_writes_during_purge.sql,services/owner_data_purge.py}`, `frontend/{package.json,next.config.mjs,playwright.u1.config.ts}` and `.github/workflows/{ci.yml,release.yml,cd.yml}`. The exact provider-selection anchor is `backend/modules/summarization/src/summarization/real_wiring.py`: its explicit DOCSURI_LLM_PROVIDER=openai branch selects the local-compatible adapter; deployed endpoint/model identity is separately qualified. These establish source arrangements and gaps, not installed or deployed controls. `monitoring-design.md` and `cicd-pipeline.md` supply the corresponding signal and delivery mappings.

The confirmed current amendment consumes these nine inputs and the public recovery handoffs `../../../inception/delivery-planning/bolt-plan.md` and `../../../verification/u1-isolated-postgres-bootstrap-plan.md`. Current owning reviews are `../functional-design/reviews/review-03.md`, `../nfr-requirements/reviews/review-02.md` and `../nfr-design/reviews/review-03.md`. Preserve the original immutable source baseline and partial application; these reviews and source declarations do not supply runtime or operational acceptance.

## Deployment

| Facet | Choice | Rationale |
|---|---|---|
| Compute model | Existing Mac server; native production Next.js/BFF, single-process API and independently supervised worker; bounded one-shot maintenance through launchd | Confirmed Q1; retain existing application boundaries and API rate-limit authority |
| Networking | Existing Cloudflare HTTPS/tunnel ingress to the BFF; production API/data/inference remain loopback-only; separate protected staging origin and data network | Browser reaches authenticated same-origin routes; no public database, queue or management port |
| Storage strategy | Existing PostgreSQL authority and a separate immutable prepared-result record; persistent broker state after Q4 qualification; existing MinIO/Redis remain pipeline dependencies | Exact final content and state/effect fencing remain relational, not a generative cache lookup |
| Environments | Developer/CI isolated fixtures; real staging isolated on the same server; production uses existing serving endpoints | Shared code/contracts and data-engine versions; isolation and shared-host resource measurements are explicit |
| IaC approach | Version-controlled compose/configuration, launchd role definitions, environment manifests and release automation in existing server seams | Full scripts/configuration belong to Code Generation; retired CDK stacks are historical, not deployment inputs |
| Resource sizing | IS-4's bounded qualification profile plus a measured, nonempty per-environment resource manifest | No guessed host RAM/CPU capacity, production throughput, silent payload cap or unqualified autoscaling |
| Delivery | Serialized server-side pull of qualified immutable main releases, compatibility-first staged activation | Confirmed Q3 and C8; release tagging alone is not deployment |
| Availability boundary | Preserve single-host topology and existing recovery arrangements; report host/disk/container/provider failure honestly | No new uptime or disaster-recovery SLA was supplied |

## Infrastructure Services

| Service | Role | Configuration | Notes |
|---|---|---|---|
| Existing PostgreSQL | Database; job/binding/effect/result/event authority | PostgreSQL 16 source arrangement; persistent volume, owner/job indexes, atomic guarded transactions and dedicated control budgets; isolated bootstrap target qualified separately | The production compose pin is superseded/rejected, not a test fallback; candidate admission, effective version/protection and durability require IS-9 evidence |
| Existing ElasticMQ | Queue and DLQ | Current summary-job queue/DLQ; qualified `messages-storage` and persistent broker data; 120-second active visibility with renewal | Metadata-only `queues-storage` does not establish message persistence; no FIFO/exactly-once claim |
| Existing MinIO | Pipeline document/base-artifact storage | Existing protected production buckets; staging-only synthetic source/cache buckets and scoped credentials | Not the immutable prepared-result reader; no production bucket/root credentials in staging |
| Existing Redis | Sessions and pipeline cache | Preserve actual production configuration; isolated staging session/cache authority and credentials | Logical prefix alone is not an access-control boundary; session loss must preserve inherited fail-closed behavior |
| Existing Ollama-compatible inference | Existing generation dependency | Explicit `DOCSURI_LLM_PROVIDER=openai`, configured local-compatible endpoint/model identity; isolated staging inference execution with representative fixtures | Source permits local-provider selection; actual model/version/capacity is verified, not inferred from defaults |
| Existing OpenSearch | Existing surrounding corpus dependency | Preserve production configuration; any required staging corpus is synthetic and isolated | No U1 index migration or tuning of existing disk watermarks |
| Existing Cloudflare DNS/tunnel | DNS, TLS and ingress | Existing production BFF route; separate staging route after its access/isolation checks; retain final unmatched-host refusal | No shared-cache delivery of authenticated job/result content |
| Existing Sentry and monitoring integrations | Diagnostics and alerts | Safe environment-specific routing, verified operator-owned destinations, bounded delivery | No new dashboard product; actual project/channel/plan availability is not established here |

## Shared Infrastructure

| Shared Resource | Owner Unit | Consumer Units | Access Boundary |
|---|---|---|---|
| Frontend/BFF and shared parent integration | U1 change steward; existing server operator | U2, U3 | Serial source/release changes; authenticated gateway; preserve separate private asset policy |
| Job/result/effect schema and service | U1 | U2 through U1 APIs | Owner-first queries and explicit commands; U2 receives no direct database or queue grant |
| Summary-job queue and maintenance | U1; existing broker operator | U2 indirectly through U1 | C6/C7 identities; old consumers drained/isolated before v1; other queue pairs protected during broker transition |
| Existing document/asset storage | Existing data authority; U1 coordinates its pipeline use | U2 through U1, U3 through asset service | Scoped environment credentials; U3 remains responsible for licensed asset delivery |
| Host/container resources and monitoring | U1 configuration steward; revenantonthemission operational accountability | U2, U3 | Per-environment manifests, measured aggregate budgets and verified alert destinations |

## IS-1 Runtime and Environment Mapping

| Runtime | Production source seam | Staging mapping | Required activation evidence |
|---|---|---|---|
| Frontend/BFF | `dev.docsuri.web`, standalone output, configured `DOCSURI_GATEWAY_URL` | Separate immutable release and origin; proposed host BFF port 13000, never a production default fallback | Real API mode, intended gateway, cookie/header fidelity, source-map scrubbing and C1–C4 capabilities |
| API/controller/service | `dev.docsuri.api`, loopback port 8000, one uvicorn worker | Separate API instance inside the staging isolation boundary; no public host API port required | Trusted session authentication, actual relational store/queue and compatible result/state/event readers |
| Summarization worker | `dev.docsuri.worker-summarization`, existing module entry | Staging queue/store/provider only, one initial qualification generation slot | One invocation grant, independent renewal, exact final binding and truthful outcomes for both tasks |
| Recovery maintenance | Existing interval-capable installer and recovery seam | Separate environment-specific one-shot recovery role | IS-6 eligibility, cadence, progress, deadline and interruption evidence |
| Payload cleanup | Same existing backend maintenance assembly | Separate one-shot cleanup role with hourly root-cycle eligibility and sub-minute continuation | Fixed expiry denial, persistent sweep progress and measured 24-hour drainage |
| Pull deployer/monitoring | Existing server automation seam | Qualified release controller and safe status delivery, outside application callbacks | Trusted commit/check evidence, serialized activation, no production secrets in staging execution |

All added role labels and port 13000 are proposed configuration, not installed facts. Keep existing production labels/endpoints until qualified changes are applied. The current `run.sh` unconditionally sources production `backend/.env`; it must not be reused unchanged for staging. Environment-aware assembly must require the selected manifest and purpose-scoped credentials and refuse a missing/mismatched environment instead of silently loading production defaults. Record actual Python, Node, container-engine and model versions; a runbook mentioning Colima and a compose comment mentioning another runtime do not prove either installed runtime.

## IS-2 Staging and Ingress Isolation

Use a dedicated staging compose project and private container network under the existing local container runtime, with launchd-owned orchestration. Replicate the existing logical frontend/API/worker/data/inference topology using the same qualified source release and dependency engines. Execute staging workloads and destructive fixtures within that boundary, not under the production application's credential-bearing shell. Native-production versus sandbox execution differences require recorded compatibility/resource evidence; container presence alone is not parity proof.

The recorded controlled-egress choice maps to a staging-only qualified Squid HTTPS CONNECT helper attached to the internal workload network and a separately enforced egress network. All application/data/inference/browser/test workloads have only the internal attachment; they cannot gain external connectivity by adding a network, host mode, NET_ADMIN, container socket or production mount. Only the helper has the outbound attachment; its proxy listener is internal, with no public host-published proxy port. The browser reaches the actual protected staging HTTPS origin through that explicit proxy; diagnostic transports use the same permitted route. Cloudflare ingress reaches only the staging BFF's loopback port 13000 through the protected tunnel, independently of this workload-egress path.

| Boundary | Enforced configuration | Verification |
|---|---|---|
| Staging data authority | Separate PostgreSQL database/role, Redis session/cache authority, broker/queue/DLQ and MinIO fixture/cache storage | Paired identity checks; wrong-environment DSNs, credentials and resource identities fail before work |
| Container/host separation | Private internal data network; no host networking, production mounts, home directory, container socket or production credential provider | From staging, production loopback/data ports and host-gateway/LAN access are refused; namespace naming alone is insufficient |
| Inference | Staging-only instance/configuration of the same existing compatible pipeline; only approved model material may be reused read-only | No production generation/cache/glossary writes; resource qualification includes inference footprint |
| Browser ingress | Publish only staging BFF bytes through a distinct protected HTTPS hostname to the proposed loopback port; API/data stay internal | Real session cookies, separate session authority, secure Web Crypto context, no direct browser/API route |
| External diagnostics and benchmark | Browser and diagnostic clients explicitly use the internal Squid listener; exact staging-origin/required-diagnostic HTTPS host allowlist, CONNECT port 443 only | Permitted routes require helper/TLS/provider/guest qualification below; no direct workload egress or arbitrary CONNECT destination |
| Fixtures and cleanup | Synthetic owned accounts/papers/results, versioned staging resource manifest and scoped teardown | Test cleanup cannot delete production jobs/buckets/queues or user-owned workspace records |

| Enforcing point | Selected control | Admission and failure evidence |
|---|---|---|
| Helper request/destination boundary | Default-deny exact CONNECT hostname/443 and DNS-rebinding policy; reject literals, alternate encodings, production/unlisted hosts and prohibited resolved destinations; validate DNS answers on each new connection | Allowed staging/diagnostic routes plus denied arbitrary port/host, private/loopback/LAN/link-local and rebinding probes; failure closes the affected route |
| Visible TLS service identity | Qualified ClientHello peek-and-splice binds the requested CONNECT hostname to that connection's visible SNI, retaining end-to-end TLS without decryption | Reject missing/mismatched SNI, unsupported TLS or opaque/ECH/concealed identity; certificate/hostname checks remain enabled in clients |
| Encrypted HTTP authority at external service | Independently verified provider/account/configuration boundary rejects shared-address SNI versus HTTP Host or HTTP/2 :authority mismatch | Controlled paired allowed/mismatched-authority results bound to each destination, provider rule identity and validity/refresh conditions; no assumed Cloudflare guarantee or silent interception substitute |
| Linux guest forwarding and host-input boundary | Supported Docker DOCKER-USER forwarding path plus required guest INPUT protection, scoped to actual staging workload/helper identities; default deny with narrowly qualified DNS/resolver/established-reply exceptions | Inspect actual firewall/backend and pre/post-NAT identities; reject direct bypass, host-gateway/host/LAN/production/link-local access. Enforce IPv4/IPv6 equivalently or deny unsupported-family paths |
| Operator application and rollback | Versioned resource/rule/host/CIDR/allowlist/provider manifest, protected credentials and preserved original rule/workload inventory | Concrete separate authorization before application; paired wrong-environment/mount/credential tests, identity-scoped reversal and original-inventory reconciliation |

Qualification binds actual image/runtime/source/network/rules, per-destination CONNECT/SNI/provider evidence, measured allow/deny outcomes and expiry/refresh conditions. Naming an internal network, supplying proxy settings, trusting a public certificate or writing verified flags is not proof. Relevant identity/policy/provider change, stale proof, missing enforcement or unsupported handshake withdraws the route. Full proxy/firewall/launcher policies and tests belong to the current Code Generation plan; these mappings neither install controls nor authorize privileged operations.

The database-only bootstrap in `../../../verification/u1-isolated-postgres-bootstrap-plan.md` uses a fresh dedicated private cluster with separate authority and later minimal-purge databases/roles, protected operator-owned read-only realm markers and independently measured launcher/receipt/digest identity before fixture mutation. It needs no diagnostic/benchmark/provider egress helper. Admit its own resource/rule/credential scope and protected proof; later integrated staging separately qualifies the full topology above. Do not execute the retained destructive purge fixture before its guard/bridge adaptation and distinct target admission.

The existing tunnel setup rewrites its entire ingress file. U1 must preserve verified production/other routes when adding staging, apply access controls before publishing that hostname, validate the resulting configuration and retain its catch-all refusal. Do not run the existing installer or rebuild command as a staging shortcut: it reloads production roles. A host unable to support this isolation and the approved workload needs the concrete resource/environment follow-up allowed by Q2, not an unprotected staging fallback.

For job routes, configure private/no-store delivery and bypass shared edge caching. Preserve incremental SSE, opaque resume headers/query, actual LF framing and upstream cancellation. Use transport-only comment keepalives at an initially proposed 15-second interval when otherwise idle; comments do not create state/events or alter cursors. Verify tunnel/edge buffering, header/idle behavior and cancellation with a prolonged real stream. C8's 15-second header acquisition is not a healthy-body total timeout. HTTPS/session/CSRF/CSP behavior and separate error-response Set-Cookie values remain mandatory; U3's private 60-second asset policy is independently preserved.

## IS-3 Relational Authority and Lifecycle Placement

| Resource/change | Physical design | Required constraint/evidence |
|---|---|---|
| Existing `content_jobs` | Add compatible internal authority/dispatch/result-binding metadata; retain legal state, owner/key and seq | Existing active legacy rows do not acquire invented NOT_STARTED/grant evidence |
| SubmissionBinding | Proposed `content_job_submission_bindings`, job/owner and immutable input/key binding; monotonic dispatch fence/start/outcome | Single initial send permission; definite rejection release distinct from retained ambiguous failure |
| GenerationEffect | Extend existing `content_job_effect_ledger` with durable intent/status, publication fence/lease and exact binding | Existing intent is never deleted to buy another invocation; queue visibility is not publication authority |
| PreparedJobResult | Proposed `content_job_prepared_results`, unique job-bound immutable final JSON payload/digest and minimal expiry/purge metadata | T5 commits exact owner-specific content before T6; staged binding is not a public resultRef |
| JobEvent | Existing event table and unique job/seq; opaque event-ID lookup within job/owner | State and event commit together; database event_id is not cast to per-job seq |
| Maintenance progress | Small service-owned environment/class/cycle/cutoff/cursor records | Bounded recovery/cleanup can resume and reach backlog; progress never grants send/generation authority |
| Indexes | Owner/job prepared lookup; expiry/payload-present sweep; authority-version/dispatch-outcome/start and lease-expiry eligibility; existing event/job/seq indexes | Explain/volume checks and pagination under foreground/renewal load; no table-wide payload read for state |
| Owner lifecycle | Existing account ACTIVE/invalidation/purge seam plus job-child cascades and guarded writes | Include content-job records in inactive-owner protection and owner-data purge; no late recreation after deletion |

Source `backend/modules/summarization/migrations/002_create_content_jobs.sql` supplies job/event/effect basics. Preserved partial source now includes registered `backend/modules/summarization/migrations/003_content_job_authority_prepared.sql`, with bindings/prepared/progress tables and owner/immutability guards; existence does not establish admission or real constraints. The inherited `backend/migrations/__init__.py` rejects its procedural constructs. Reconcile current implementation-plan/source-footprint authority and supplemental original-byte capture before a narrowly reviewed registered-script repair; retain full-script identity/digest, same-connection current authority, locking, per-step transaction/ledger and guarded commit. No raw rejected-SQL bypass, general procedural exemption or rewriting of historical 002 is admitted. Required real-schema/owner-lifecycle proof follows qualified independent realm preflight. Unknown/orphan legacy ownership remains explicit quarantine/reconciliation, not guessed owners or unsafe backfill.

The current inactive-owner trigger list and `OWNER_SCOPED_TABLES` in `backend/modules/accounts/services/owner_data_purge.py` omit content jobs. U1 must close this assigned T8 integration: guarded active-owner writes, explicit content-job purge with child cascades and deletion-race tests. Merely storing owner_id or declaring a new child FK does not prove the existing account purge reaches it. Preserve existing account lifecycle policy; do not rewrite its historical migration or create a new deletion product.

Fixed expiry is initialized once by T6 using the configured result TTL, currently 3600 seconds. After expiry, deny reads immediately; purge final payload and unnecessary preparation-content metadata while retaining only needed owned expiry/binding metadata while the job exists. Digest/reference is not authorization. State/result queries remain separate from generation caches and restricted to owned-query capabilities. Existing backup protection/retention and restore-time owner/expiry enforcement require IS-9 proof; the 24-hour live-payload bound is not backup erasure.

Prepared JSON retains the shared required `{code: string, data: string}` reproducibility object with no extra nested fields, exact allowed Unicode/whitespace/escaping/empty strings and final translation personalization/bare DocModel. Canonical integrity hashing and JSONB/wire round-trips preserve string values; capture cannot flatten/coerce/default malformed content into success. Apply the current SD-2/RD-4 instant contract to preparedAt/expiresAt/DocModel provenance.generatedAt: available timezone-aware RFC 3339/calendar/offset checking, fresh authoritative database time for T5 preparation and T6's one-time expiry, and validated binding/publication metadata. A format annotation or permissive parser alone is not validation; required evidence detects missing checker support.

Actual store/read tests prove authentication 401, identical missing/not-owned 404, owned non-COMPLETED 409, trusted known-expiry 410, permanently malformed/legacy unavailable 422, transient store 503 and gateway 504 with no protected content on failure. Test just before, exactly at and after fixed expiry, duplicate publication, changed settings/configuration, malformed timestamps and purge/deletion/restore races; every read/retry has zero generation/enqueue/submit/current-settings rendering. Contract Design R-03 remains Accepted risk: synthetic format/shape checks do not repair the original helper or prove these actual application/store outcomes.

## IS-4 Resource and Deadline Qualification Profile

The following connection/slot allocations are concrete starting qualification settings, not measured production capacity or a product concurrency limit. Actual CPU/memory/disk limits and aggregate database headroom must be filled from representative supported fixtures in the activation manifest before runtime starts.

| Resource | Starting allocation / policy | Why / qualification |
|---|---|---|
| API | Keep one uvicorn worker; dedicated job-control pool maximum 4 | Preserve process-local rate-limit authority; prove state/SSE/result handling does not block the event loop |
| Worker authority | Dedicated control pool maximum 2; one connection/task reserved for renewal, one for claim/publication | Generation and encoding cannot borrow renewal capacity |
| Generation | One initial qualification slot; separate pipeline-query pool maximum 2; isolated supervised child/task | Receive at most available slots; no unsupervised ten-message prefetch; report tested slot/fixture range |
| Recovery and cleanup | Separate roles; each maximum 1 dedicated database connection; bounded discovery/pages/passes | Neither generation nor the other maintenance role can monopolize its budget |
| Per-environment ceiling | These U1 purposes total at most 10 connections, plus separately inventoried existing application/administrative usage | Require sum across production, staging, child processes, existing modules and operator reserve within actual server limit |
| CPU/memory | Record peak supported fixture use plus explicit operator reserve; enforce qualified child/container limits and control scheduling | Reject missing/insufficient manifest; no memory limit selected by silently truncating translation content |
| Disk | Require free capacity for qualified result/WAL growth, broker state, staging seeds, backup spool, migrations and retained rollback releases plus operator reserve | Source historical disk pressure is not a current measurement; no automatic deletion of source/user documents |
| Scaling | Explicitly qualified slot/pool changes within existing runtimes; no autoscaling/new database/platform | Rerun timing/race/resource evidence when changing the profile |

The current `_pg.py` uses one DSN-keyed pool with maximum 8 and can fall back to unbounded direct connection creation. It does not provide these purpose reservations or total deadlines. U1's approved implementation must supply real bounded purpose separation and acquisition/cancellation behavior; missing required authority pooling cannot silently use that fallback. Existing non-U1 adapters retain compatibility and are included in aggregate measurement.

| Timing/configuration | Selected value / guard | Concrete enforcement and evidence |
|---|---|---|
| Heartbeat H / publication lease L | 15 s / 90 s | Independent renewal; fresh database time and current unrevoked fence |
| Active queue visibility V / renewal R | 120 s / 30 s | Explicitly maintained on supervised receipt; actual broker limits verified |
| Persistence D / queue control Q / jitter J | Total 5 s / total 5 s / allowance 5 s | Include acquisition/lock/statement/commit-response handling; queue SDK uses one send attempt and an overall deadline |
| Lease margin | L > 3H + 2D + J: 90 >60 | Startup guard plus loaded delay/crash/cancellation fixtures |
| Visibility margin | V > 2R + Q + J: 120 >70 | Redelivery never grants another invocation |
| T5/T6 admission | Remaining valid authority >2D+J =15 s | Renew first; fresh final guarded write and uncertain-commit reconciliation |
| Dispatch ambiguity | 120 s from T2 dispatchStartedAt; 120 >Q+2D+scan+J =50 | Never reset by reads; at bound settle actual evidence or retained-binding uncertain failure |
| Backend ordinary response / BFF hop | 8 s / 10 s | Remaining phase budgets; return committed SUBMITTED when a safe first send cannot fit |
| SSE headers / healthy body | 15 s / no total deadline | Real incremental relay, comment keepalive and cancellation; verify intermediary constraints |
| Ordinary GET retry / client fallback | At most one retry after 1.5 s / fixed 2 s nonoverlapping polling | Retry belongs to BFF only; no automatic POST retry or layered multiplication |

PostgreSQL 16 must not be described as already providing a newer server-wide transaction-timeout feature. Use bounded pool acquisition, remaining statement/lock budgets, watchdog cancellation and poisoned-connection quarantine, with fresh fenced write predicates. A missed/lost commit response is uncertain, not proof of rollback or a reason to generate again. Prove total handling and stale-publication behavior under real storage stalls; if the selected budgets cannot be enforced, stop for a concrete tuning/implementation decision and revalidate before activation.

## IS-5 Broker Persistence and Safe Shared Transition

| Area | Selected mapping | Evidence before change/exposure |
|---|---|---|
| Image | Current digest-pinned `softwaremill/elasticmq-native`; preserve unless a supported-image adjustment is explicitly decided | Determine actual version/features; isolated persisted-message, forced-process-restart and storage-failure tests |
| Message storage | Candidate `messages-storage.enabled=true`; protected persistent volume at the supported database path, expected `/data` | Upstream H2-file feature is a candidate, not image support or acknowledgement-durability proof |
| Identity/configuration | Keep verified summary-job queue/DLQ identities; staging has its own broker/resources | Persisted attributes can override startup definitions; read back effective visibility/redrive/retention and restore behavior |
| SDK behavior | C6 v1 minimal jobId/dispatchId message; one SendMessage attempt; total queue-control budget; capacity-bound receive | Trusted durable job input/owner, no retry after UNKNOWN; compatible consumers only |
| Shared-broker change | Inventory all six existing queue pairs/producers/consumers; stop new production sends and prove drain, or prove a lossless transition | Do not restart the current memory-only broker merely to turn persistence on; queue depth zero alone misses delayed/in-flight work |
| Activation | Qualified storage, preserved queues/attributes, compatible worker and guarded v1 producer | Real publish/receive/restart/redelivery and no-second-invocation evidence |
| Rollback | Keep verified persistent state and a compatible broker reader; restore previous qualified configuration only | Never replace with an empty broker or blindly reconstruct accepted messages from database absence |

Quiescence includes visible, delayed and in-flight messages, producer confirmations and consumer terminal outcomes. Record the inventory and transition evidence; an unresolved legacy job/message remains unresolved even when physically isolated. Invalid/unknown-major messages follow verified quarantine/DLQ policy without generation. DLQ movement/redrive is observable and authority-checked; no automatic redrive that bypasses C7. A broker restart test must distinguish repeated transport delivery from a repeated invocation grant. Supported legitimate long work and visibility maximum/receipt expiry behavior are qualified explicitly.

## IS-6 Scheduled Recovery and Cleanup

| Proposed role | Scheduling | Work and runtime bound | Safe continuation |
|---|---|---|---|
| `dev.docsuri.content-job-recovery` | launchd StartInterval 30 s, environment-specific one-shot entry | Independent 20-second pass, maximum 100 candidates/page; discovery capped at 3 s; fair persisted progress across three eligibility classes | Next qualified tick; overlapping/manual actors use database predicates, not a host-only lock |
| `dev.docsuri.content-job-cleanup` | StartInterval 30 s as a wake-up; new root sweep is due once per 3600 s in persisted server-time progress | Independent 20-second pass, maximum 100 rows/page; fixed cycle cutoff and expiry/job keyset cursor | Due unfinished work continues next tick, within the selected 60-second continuation bound; no wait for another hour |
| Existing worker supervisor | Independent 15-second lease and 30-second visibility timers | Reserved control resources while generation runs separately | Revoked/expired authority never renews or publishes; only exact stored identity can reconcile uncertainty |

The cleanup timer is a continuation carrier, not a new 30-second retention/cleanup policy: root-cycle eligibility remains hourly. Failed/overdue progress stays due, with bounded backoff inside the required continuation margin. Do not allow cleanup's 20 seconds to consume the recovery role's separate cadence. launchd coalesces missed/sleep-time invocations and skips overlapping instances; validate actual startup delay, pass intervals, sleep/reboot dependencies and schedule jitter. A missed pass is unhealthy, not a successful cadence. No minute-only two-pass runner is selected for this interval-capable target.

Recovery pages explicitly cover authorityVersion 1 NOT_STARTED first dispatch, SUBMITTED SENDING/UNKNOWN without effect at the 120-second ambiguity bound, and expired execution fences. Recheck job/owner/fence/time inside each short operation. Dispatch and execution cursors/progress must not starve newly eligible older/restored rows; complete/reset bounded cycles and monitor eligible age/settlement lag. Legacy missing markers never become fresh grants.

Before a first T2 claim require actual remaining pass budget >2D+Q+1 s finish margin =16 s. The 3-second discovery cap leaves nominal space in the 20-second pass; slow discovery/admission defers NOT_STARTED safely and is reported as unmet work. A send that becomes uncertain preserves its durable T2 evidence/binding. At/after 120 seconds, authoritative confirmation wins if already present; otherwise current pre-effect ambiguity is fenced and fails safely with binding retained. An expired execution fence publishes only an exact prepared result or safe uncertain failure, never generation.

Cleanup persists the fixed root-cycle eligibility cutoff and keyset progress, deletes only rechecked expired live payloads, and cycles back to catch newly restored/backdated rows. Query oldest eligible payload independently so progress cannot hide deadline risk. Qualify drainage with foreground queries, renewal, failures and overlap against 86,400 seconds after expiry. Empty, partially processed, omitted-backlog and failed scans remain distinct. Owner deletion uses the existing lifecycle integration, not the TTL sweep as a substitute.

## IS-7 Permission and Data Protection Mapping

| Principal/purpose | Minimum access | Explicit restriction / evidence |
|---|---|---|
| BFF | Configured environment gateway and session relay; public diagnostic routing identifier | No database/queue/provider secret, arbitrary upstream host or trusted caller principal header |
| Job query adapter | Required owned job/event/result reads | No enqueue/generation/current-settings capability; owner filter and TTL/error-precedence tests |
| Job command/worker authority | Required job/binding/effect/prepared/event writes and current owner checks | Legal state/fence guards; no arbitrary table/admin privilege or effect-intent deletion for retry |
| Generation child | Validated invocation input and scoped existing pipeline dependencies | No alternative publication fence or duplicate grant; cannot borrow supervisor capacity |
| Recovery | Guarded first-send capability only for proven NOT_STARTED; reconciliation/progress access | No send for SENDING/UNKNOWN, no pipeline capability |
| Cleanup/account purge | Required expiry/progress/delete or existing owner-purge integration | No key release for re-execution; owner-scoped child removal and no late upsert |
| Migration/deployer | Registered migration and qualified release activation operations | Separate from application credentials; restricted repository evidence and environment-bound paths |
| Staging/test roles | Only staging database/session/broker/bucket and fixture authorities | Production credentials/network/storage denied; broker SDK credential fields alone are not IAM enforcement |

Keep purpose-scoped credential files outside source with verified ownership/permissions and environment-specific providers; do not print values/DSNs/ping URLs in artifacts, logs or receipts. The existing shell-loading seam requires protected files and safe role/environment selection; no default production credentials or shared root MinIO credential in staging. Effective local ACL/container/network controls replace no AWS IAM claim: a loopback SQS-compatible broker is not an IAM-authorized cloud queue.

Preserve verified HTTPS/tunnel security, existing session/CSRF/CSP and safe content rendering; document local trusted-transport boundaries accurately rather than claiming TLS on plaintext loopback links. Record actual disk/volume/backup protection and access settings before asserting protection. Changes must not remove inherited safeguards. Session credentials are secret; owner-specific prepared content remains protected even for public source papers. Diagnostics omit credentials, parameter/document/result bodies and unnecessary identity data.

## IS-8 Decision Tradeoffs

| Decision | Selected approach | Alternative considered | Consequence |
|---|---|---|---|
| Hosting | Existing Mac/launchd target confirmed in Q1 | Another verified existing environment supplied by the human | Low infrastructure churn, but measured single-host capacity/isolation and outage limits remain explicit |
| Delivery | Server-side verified pull, Q3 | Restricted authenticated remote delivery from Actions | Outbound-only management; needs durable release/check journal and cannot trust tagging or a mutable working checkout |
| Queue persistence | Qualify existing broker, Q4 | A verified existing durable compatible queue | Preserves endpoints/runtime, but image support and shared-broker transition must be proved before restart |
| Maintenance | Separate bounded recovery/cleanup roles in existing seam | Combine both into worker or one timer callback | Protects renewal/recovery cadence from generation and cleanup pressure; adds configured one-shot roles, not a new application service |
| Snapshots | Approved relational exact final payload | Immutable object snapshot with relational binding, rejected upstream | Simpler authority/deletion consistency; requires payload/WAL/storage qualification |

## IS-9 Readiness Evidence Before Activation

| Evidence ID | Required proof | Owner / consequence when missing |
|---|---|---|
| IG-1 | Actual qualified artifacts/host/runtime versions, resource manifest, one-worker API and restart/login/container/inference readiness | revenantonthemission; source presence or old qualification cannot supply current admission/capacity |
| IG-2 | Concrete authorized IS-2 resource/rule/secret scope, measured protected realm identity and staging helper/guest/provider enforcement, teardown isolation and real authenticated route | U1 implementation and operator; wrong/missing/expired proof fails before mutation; database-only and integrated scopes are separate |
| IG-3 | Current implementation/source-footprint authority, narrowly admitted registered additive schema, current owner purge/late-write guards, both-task exact code/data/personalization, actual timestamp/expiry and real-store races | U1; no v1 authority/UI exposure or required-live-test skip counted as success |
| IG-4 | Total deadline/cancellation, reserved renewal capacity, actual queue limits and loaded timing guards | U1; no affected worker activation |
| IG-5 | Pinned broker persistent-message/crash/restore support and safe all-queue transition | Operator/U1; no shared broker restart or accepted-message durability claim |
| IG-6 | Measured 30-second recovery, hourly root cleanup, continuation/progress/drainage and threatened-deadline recovery | U1/operator; no claimed maintenance operation |
| IG-7 | Scrubbed Sentry capture, real backend metrics, verified destinations and failure/no-ping alert evidence | revenantonthemission; missing monitoring is unknown/unhealthy |
| IG-8 | Exact-commit CI/staging evidence, compatible runtime order, safe exposure and rollback/smoke rehearsal | U1/operator; no production activation |
| IG-9 | Existing backup protection/retention/pruning/restore configuration and owner/expiry enforcement after isolated restore | Operator; no invented backup recovery or erasure promise |

These are assigned verification work, not new product assumptions or fabricated approvals. Code Generation creates the complete implementation/configuration and test plan; actual environment/deployment work supplies runtime receipts. If evidence refutes a chosen mechanism, resolve that concrete decision rather than silently changing platform, deadline or result semantics. The separately authorized real skeleton command and human checkpoint remain required.

Current `ops/platform-integrity/sbom-targets.json` records the nonroot PostgreSQL candidate as CANDIDATE_PENDING_OPERATOR_MAINTENANCE_WINDOW with unresolved High CVE-2026-85091, other service-image findings pending and MinIO UNOBTAINABLE. Preserve actual existing qualification/disposition requirements: availability, prior tests and local-only substitute storage do not qualify a U1 production-intended release or provide independent realm proof. Admit exact artifacts/launcher/resources and obtain operational authorization before resource/rule application; no replacement image/provider/platform or risk exception is selected here.

## IS-10 Cost and Capacity Model

| Environment/driver | Estimate method | Current evidence / control |
|---|---|---|
| Production host | Existing hardware/storage/electricity plus incremental CPU hours, payload/WAL bytes and broker persistence I/O | No new AWS compute resource selected; no invented zero total cost or monthly dollar budget |
| Same-host staging | Measured peak replica/model/fixture resources, retained release bytes and test execution duration | Seed only isolated fixtures, not a clone of the production corpus; stop/clean only owned staging resources after needed evidence |
| CI | Actual runner/build/test minutes and artifact retention under the repository's plan | Existing workflows plus required real-store/browser/coverage lanes; no priced plan or quota assumed |
| Sentry/healthchecks/tunnel | Actual project plan, event/check volume, retention and egress | Verify current quota/channel availability before enabling; avoid high-cardinality/payload diagnostics |
| Prepared content | Measured successful final payload bytes, arrival/expiry distribution, fixed readable TTL and cleanup backlog | Include larger supported translations and the 24-hour cleanup allowance; no guessed jobs/month or payload cap |
| Backup/rollback | Existing verified dump/retention policy and measured migration/rollback artifact needs | Keep usable compatible rollback and restore evidence; no automatic deletion of user/source records |

Report resource distributions/errors and the tested concurrency/fixture range rather than derive production capacity from a single-job p95 pass. Insufficient current host headroom or funded monitoring capacity is an activation prerequisite to resolve, not permission to lower quality or add unapproved cloud infrastructure.

## Infrastructure Relevance and Upstream Findings

`traceability.json` explicitly covers all 35 detailed NFR IDs. OK means a designed infrastructure/configuration mapping, not runtime acceptance. N/A rows retain client-only implementation responsibilities; CI still verifies those obligations. U3 owns asset decoded-readiness/migration; shared U1 changes preserve its transport boundary. Current Functional Design review resolves all five findings, including draft optionality; current NFR Requirements review resolves its citation finding and current NFR Design review retains both Resolved findings with no new concern. Their resolving owning-review paths are in Sources. These dispositions supersede historical carry-forward notes without erasing history or certifying partial source. Contract Design R-03 remains Accepted risk with separate actual timestamp/store proof required.

## Static Checks and Execution Evidence

**Executed current document/source checks (2026-10-05):** All four archive copies were compared byte-identical before revision. The read-only `validate_u1_infrastructure_design.py` helper in the approved temporary work directory checked three prose documents, 26 well-formed tables, all 35 IDs/30 mappings/five client-only N/A rows, 57 resolving section targets and the same 23 IS/MD/CI IDs. Eleven unaffected pattern sections and traceability bytes remain identical; selected resource/timing/maintenance/alert values and IG-1–IG-9 are preserved. All 109 explicit file references resolve, including 55 workspace-source occurrences with brace citations expanded. The exact provider anchor and explicit openai selection were checked; a deliberately wrong former path is detected. Current frontend scripts/CI, frozen/nonroot Dockerfile/context, migration registry and pending artifact statuses were checked against source. Traceability, explicit nine-input coverage on every prose output, required-section and scoped whitespace checks passed with zero findings. There are zero code blocks; TS/JS linter/type-check matches are inapplicable to these Markdown/JSON designs.

These executed checks establish document consistency only. No application build/test, real-store race, staging isolation, queue crash/restore, host resource, scheduler, live alert, backup restore or deployment acceptance has been performed by this stage. Their actual evidence remains required under IS-9.
