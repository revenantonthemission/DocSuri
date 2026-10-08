# U1 Platform Monitoring Design

## Sources

Signal requirements and failure domains come from `../nfr-design/performance-design.md`, `../nfr-design/security-design.md`, `../nfr-design/scalability-design.md`, `../nfr-design/reliability-design.md`, `../nfr-design/observability-design.md`, `../nfr-design/logical-components.md`, `../functional-design/functional-spec.md`, `../../../inception/domain-design/components.md` and `../../../inception/contract-design/contract-summary.md`. Confirmed `infrastructure-design-questions.md` selects the existing server and its monitoring seams. `infrastructure-specification.md` supplies IS-1–IS-9 runtime/resource/maintenance mappings; `cicd-pipeline.md` supplies CI and release evidence.

Existing source seams are `ops/server/heartbeat.sh`, `ops/server/README.md`, `ops/server/docsurictl` and the existing backend observability adapters. Public Healthchecks.io Management API documentation, <https://healthchecks.io/docs/api/> (consulted 2026-10-05), documents minimum 60-second period and grace values and explicit channel assignment; this is not evidence of configured account/check/channel availability. Sentry is mandatory planned integration, not an installed SDK/project claim.

## MD-1 Metrics and KPIs

| Metric | Source | Threshold | Why it matters |
|---|---|---|---|
| `job_api_ready` / operation success,error counters | Real gateway/controller/store/queue capability checks and request outcomes | Missing required adapter/capability means not ready; errors separate from successful reads | A 200 health page or no-op enqueue is not real job readiness |
| `worker_ready`, invocation-grant and terminal outcome counters | Existing worker supervisor and authoritative job/effect operations | Only validated current configuration/grants count; mapped success/failed/abstained remain distinct | Truthful outcome and working runtime evidence |
| `connection_latency_ms`, open/drop/restoration/mode counts | Native browser EventSource construction/open and actual connection lifecycle | p95 <300 ms under the approved benchmark; every failed attempt reported | Observes real connection responsiveness and fallback |
| `status_mount_latency_ms` | Requested mount to first committed named status UI | p95 <200 ms under the same profile | Motion/data work cannot conceal a slow mount |
| Submit/recovery/receipt/terminal observations | ContentJobApi and current selected context | Separate initial submit, explicit same-key recovery, observed identity and outcome | A changed ID or click is not proof of new execution/dispatch failure |
| Dispatch start/confirmed/rejected/unknown/settled counters | Service T2/T3 and authoritative evidence | No resend after SENDING/UNKNOWN; eligible ambiguity at 120 s | Distinguishes definite release from retained uncertainty |
| Prepared binding/publication success,error,uncertain counts | T5/T6 and exact-identity reconciliation | Completion requires committed valid binding; read side-effect count 0 | No fabricated successful content or generative read repair |
| Renewal lag, remaining lease and visibility-control failures | Independent supervisor timers and broker responses | Guarded 15 s/90 s lease profile and 30 s/120 s visibility profile; admission margin >15 s | Detects control starvation without equating visibility to authority |
| Fenced-write and reconciliation outcomes | Current database predicates and T7 | Rejected stale writes observed; duplicate whole-invocation grants must remain 0 | Verifies conservative crash/redelivery behavior |
| `recovery_last_success_age_seconds`, duration, eligible/processed/remaining per class | Persisted pass results and independent observer | Warning 90 s, urgent 180 s; pass budget 20 s and nominal interval 30 s | Starting or omitting a class is not successful recovery |
| Dispatch eligible age/settlement lag | Indexed current SENDING/UNKNOWN/no-effect query | 120 s eligibility plus measured bounded pass/backlog margin | Lease-only scans cannot omit still-SUBMITTED ambiguity |
| `cleanup_cycle_last_success_age_seconds`, due/progress/backlog/pass outcome | Persisted fixed-cutoff sweep and SQL observations | Warning 4500 s, urgent 7200 s since successful hourly root-cycle completion | Partial or failed scan cannot reset complete-cycle freshness |
| `oldest_expired_payload_age_seconds` | Independent oldest payload-present expiry query | Warning 43200 s, urgent 64800 s, breach 86400 s | Detects cleanup threat while TTL read denial stays correct |
| Query/pool/lock/commit-response duration and deadline outcomes | Purpose-tagged bounded store operations | Total D=5 s; missed/uncertain outcome is not success | Per-statement timeout alone cannot prove total bound |
| Queue send/renew/delete duration and broker restart/DLQ evidence | Qualified adapter/broker; safe low-cardinality outcomes | Total control Q=5 s; unexplained DLQ/unknown delivery visible | Missing queue data must not authorize another send/invocation |
| CPU/memory/disk, connections and supported payload-byte distributions | Actual environment/resource qualification | Nonempty qualified manifest and aggregate limits; warn before its recorded reserve is consumed | No unlimited capacity or invented payload cutoff |
| Diagnostic delivery failures / monitor observation status | Safe bounded sender and independent observer | Failed/missing delivery is unknown/unhealthy, never an empty healthy scan | Errors cannot recursively report themselves or block the journey |

Counters/metrics use bounded environment/task/outcome/operation labels. Job/request/dispatch/connection IDs may be safe trace/log correlation, not high-cardinality metric labels; omit unnecessary owner identity. No cookies, DSNs, ping capabilities, parameters, document/results or raw SQL/provider exceptions are serialized. Inspect actual emitted events, not merely the configured scrubber.

## MD-2 Alerts

| Alert | Condition | Severity | Routes to |
|---|---|---|---|
| Recovery freshness warning | No successful complete-class recovery pass for 90 s | Warning | Verified existing operator notification integration; revenantonthemission |
| Recovery freshness urgent | Same condition for 180 s | Urgent | Operator-owned urgent destination; inspect role/store/cadence, not blind resend |
| Dispatch settlement backlog | Current no-effect SENDING/UNKNOWN is eligible at 120 s and persists beyond qualified pass/backlog margin | Warning, urgent on continuing missed settlement | Same owner; guarded evidence/fence settlement only |
| Cleanup freshness warning | No successful hourly root-cycle completion for 75 min | Warning | Existing notification destination; inspect due/progress and store/scheduler |
| Cleanup freshness urgent | Same condition for 120 min | Urgent | Operator-owned urgent destination; resume guarded continuation |
| Expired payload age warning | Oldest unpurged expired live payload age ≥12 h | Warning | revenantonthemission; investigate failure/backlog/headroom |
| Expired payload age urgent | Same age ≥18 h | Urgent | Same owner; six-hour margin remains before requirement breach |
| Expired payload deadline breach | Same age ≥24 h | Breach | Same owner; retain actual breach/recovery evidence, reads remain denied |
| Safety/access/result invariant | Extra whole-pipeline grant, unguarded stale publication, read-side generation or protected-content disclosure observed | Critical; release abort | Owner and recorded security-review contact; disable affected exposure and follow CI-5 rollback |
| Resource/control deadline | Qualified reserve exceeded, control deadline missed, prolonged renewal error or unhealthy broker/store | Warning/urgent according to authority/deadline risk | Owner; stop unsupported new work safely, preserve existing authority/evidence |
| Monitor/diagnostic failure | Observer query/delivery fails, check channel absent or external watchdog stale | Unhealthy/unknown | Independent existing external destination; never success-ping a failed observation |

All routes above must bind real existing channel/project identifiers in protected operator configuration and pass controlled-delivery tests before activation. No email, phone, Slack account or available backup person is invented. revenantonthemission is the accountable primary contact; the owner must record the actual escalation destination/acknowledgement arrangement before urgent monitoring is called operational. Recovery actions are existing guarded operations, not alert-triggered generation/key rotation.

## MD-3 Observation and Off-Machine Watchdogs

Use an independently scheduled, bounded observer in the existing server monitoring seam, initially every 15 seconds, to read actual last-success/progress/age and emit the 90/180-second and payload/deadline grades. It must not consume generation's thread/pool or reset timestamps itself. A failed database observation immediately reports unknown/failure, not zero backlog. Keep observer work/delivery outside recovery's 20-second pass and protected from recursive diagnostics.

| External check / seam | Proposed configuration | Meaning and qualification |
|---|---|---|
| Existing host heartbeat | Preserve documented five-minute period/five-minute grace unless separately changed | Existing whole-host absence detection; not the new recovery-freshness implementation |
| Recovery watchdog | Separate successful-pass heartbeat; period 60 s, grace 60 s | Documented provider minimum makes its no-ping backstop 120 s, not the selected 90 s local warning; failed/stale observations send safe explicit failure |
| Recovery urgent watchdog | Period 120 s, grace 60 s, fed only from genuine successful recovery | Nominal 180 s no-success backstop; verify actual service evaluation/notification delay |
| Hourly cleanup warning/urgent checks | Period 3600 s with grace 900 s / 3600 s respectively; heartbeat only for completed root cycle | Nominal 75/120 min external freshness; continuation progress alone cannot keep a failed cycle healthy |
| Expired-payload threat status | Independent observer evaluates 12/18/24 h grades and sends explicit safe failure through existing integration | No success heartbeat after failed/omitted age query; off-machine observer/watchdog detects loss of reporting |
| Sentry | Environment-specific owned project/routing and verified error/alert delivery | Client render/async errors and scrubbed lifecycle/timing evidence; auth/source-map credentials server-side only |

Healthchecks.io's 60-second minimum period and grace cannot implement a 90-second whole-host no-ping alarm. Preserve the actual 90-second recovery-age warning in the independent observer and report the separate 120-second external absence bound accurately; do not relabel it 90 seconds. Validate failure-mode coverage and delivery delays against the selected warning/urgent/deadline policy. If an off-machine 90-second warning is required to cover loss of the entire observer/host, that unmet capability needs a concrete existing-monitoring/configuration decision before affected activation, rather than silently reducing the threshold. No new general host-availability SLA is inferred.

Sending a ping does not prove notification: capture configured channel assignment and a received test alert. Provider documentation says new checks have no integrations by default. Ping URLs/read-write management tokens are capabilities and stay outside source/logs. Actual plan limits, status evaluation timing, channels and retention must be recorded; documentation is not a live configuration receipt.

## MD-4 SLIs and SLOs

| SLI | SLO target | Measurement window |
|---|---|---|
| SSE construction-to-open | p95 strictly <300 ms; report every failed/replacement attempt | Approved run: 100 sequential successful samples, one active job, real authenticated staging, production frontend, unthrottled desktop Chromium in the same geographic deployment region |
| Status requested mount-to-first commit | p95 strictly <200 ms with complete attempt log | Same 100-sample profile; nearest-rank p95 at sample 95 |
| Read-side extra work / competing grant correctness | 0 read-triggered generation/enqueue; at most one whole-pipeline invocation grant per retained job | 100% of declared real-store/race/crash qualification cases; operational violation counters also observed |
| Owned expiry/deletion isolation | 100% of tested expiry/deletion/other-owner cases preserve denied content and required 401/404/410 precedence | Each qualification run and isolated restore rehearsal |
| Physical live-payload cleanup | 100% of expired live payloads within the 86,400-second deadline; report every breach | Per-row expiry-to-purge plus rolling 24-hour backlog/oldest-age observation |
| Maintenance/control scheduling | Selected intervals/budgets/guards met over the qualified loaded test; misses explicitly unhealthy | Qualification duration and actual per-pass/start/finish/freshness series, not an invented monthly uptime target |
| Diagnostic scrubbing | 100% of captured positive/negative delivered diagnostic fixtures exclude prohibited fields | Each relevant CI/staging release check, including sender failure cases |

These targets do not assert general production availability, RPO/RTO, throughput or a job-completion SLA. No traffic, missing observations or skipped live tests cannot produce a successful denominator. U3's separate image-decoding measure is retained for its own delivered asset slice.

## MD-5 Logs, Tracing and Retention

| Surface | Configuration/design | Evidence |
|---|---|---|
| Application/server logs | Structured safe event/outcome/environment/release/purpose fields; bounded volume; existing local log tooling | Source documents 50 MB, three generations and daily rotation, not time-based retention; measure worst growth between rotations and disk reserve |
| State/effect correlation | Safe job/request/dispatch/connection IDs in access-controlled logs/traces only | Observe actual T2–T7 outcomes and unknown commit/delivery classification without protected content |
| Sentry capture | Allowlisted before serialization; client error/timing/lifecycle scope, controlled sampling and bounded sender failure | Captured delivered event and alert proof; sampling must not hide required failure/deadline evidence |
| Notification payload | Grade, environment, operation category, timestamp and runbook/evidence reference | No ping URL/token, input/result, raw exception or guessed replacement cause |
| Retention/access | Preserve and record actual existing Sentry/log/backup policies | No generic 30/90-day framework retention substituted for project policy; verify access and pruning |
| Monitoring loss | Last-success separate from last-start; unknown/stale explicit | Missing config/delivery/query cannot masquerade as a successful empty pass |

Use the existing backend monitoring/status surface for safe aggregate state and access-controlled drilldown; do not create a new dashboard product or expose a public maintenance API. Native/browser UTC and monotonic timing have distinct roles: elapsed browser durations use a monotonic clock; database time governs leases/expiry; reconcile clock/observer health before interpreting wall-time freshness.

## MD-6 Response and Release Evidence

| Symptom | Response within existing authority | Evidence to retain |
|---|---|---|
| Stale recovery / uncertain dispatch | Check role/store/timing and resume bounded eligible scanning; preserve SENDING/UNKNOWN binding | Actual fence/evidence settlement, start age and no additional send/grant |
| Expired execution | Guarded revocation and exact-snapshot completion or safe retained-binding failure | Both renew/reconcile orderings and stale-worker rejection |
| Cleanup threat | Inspect progress/backlog/store, resume bounded continuation and qualify drainage | Per-row deadline/age, failed/complete cycles, actual purge/owner outcomes |
| Queue/DLQ/restore incident | Keep old/new authority isolated; preserve broker state; validate receipt/job before any operation | Transport duplicate versus grant count, all affected queue inventory, no blind redrive |
| Safety/security breach | Disable affected producer/UI exposure, preserve compatible readers/effects and use CI-5 rollback | Exact release/config/schema IDs, safe incident record and security-review disposition |
| Host/observer loss | External no-ping path contacts the operator; reconcile persisted progress after restart | Actual detection/delivery delay, missed deadlines and restart readiness, not a fabricated 90-second alarm |

U1 Code Generation authors/implements these adapters/configuration and tests. Runtime monitoring readiness requires IG-7 receipts, not these tables. Carry the October 14 review and upstream minor findings to their assigned checkpoints without changing their recorded disposition.
