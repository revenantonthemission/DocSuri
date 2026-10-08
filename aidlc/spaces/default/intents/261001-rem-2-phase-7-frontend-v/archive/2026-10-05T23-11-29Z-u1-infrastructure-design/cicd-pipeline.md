# U1 Continuous Delivery Pipeline Design

## Sources

Confirmed `infrastructure-design-questions.md` Q1–Q4 selects server hosting, isolated same-server staging, automatic qualified server-side pull and existing-broker persistence qualification. Upstream obligations come from `../nfr-design/performance-design.md`, `../nfr-design/security-design.md`, `../nfr-design/scalability-design.md`, `../nfr-design/reliability-design.md`, `../nfr-design/observability-design.md`, `../nfr-design/logical-components.md`, `../functional-design/functional-spec.md`, `../../../inception/domain-design/components.md` and `../../../inception/contract-design/contract-summary.md`. `../../../inception/delivery-planning/bolt-plan.md` and affirmed team/project practices supply serial U1→U2→U3, test-after/coverage and automatic-on-merge policy.

Current pipeline/configuration evidence is `.github/workflows/{ci.yml,release.yml,cd.yml,codeql.yml}`, `frontend/{package.json,next.config.mjs,playwright.config.ts}`, `backend/{Dockerfile,docker-compose.yml,elasticmq.conf,migrations/registry.py}` and `ops/server/{install.sh,run.sh,docsurictl,tunnel-setup.sh,README.md}`. `infrastructure-specification.md` supplies IS-1–IS-9 and `monitoring-design.md` supplies MD-1–MD-6. Planned steps below are not already deployed workflow/scripts or passing test receipts.

## CI-1 Current Gates and Required Additions

| Stage | Existing source evidence | Required U1 gate / failure behavior |
|---|---|---|
| Trusted source/lockfiles | CI push/PR main/develop lanes, pinned action SHAs, frozen frontend install | Preserve existing lanes; trusted deployment selects reviewed main commits only; frozen actual runtime/dependency closure |
| Lint/types/contracts | Current frontend lint, direct `tsc --noEmit`, schema/type drift and contract tests; backend/module Ruff | Reconcile actual `next lint` script against pinned Next.js/ESLint; implement runnable mandated lint/typecheck scripts or explicit equivalent; fail on affected errors |
| Unit suites | Current Vitest and backend/module/root suites | Implement each component first, then author meaningful tests; retain all existing suites and record actual counts/failures/skips |
| Coverage | Current frontend workflow runs Vitest without coverage gate | Add actual compatible coverage tooling and at least 80% new-code line coverage, with explicit changed-code ownership/baseline evidence; no floor reduction or untested exclusion |
| Real-store integration | Existing isolated PostgreSQL lane targets a different platform suite | New U1 fixtures exercise its actual store/transactions, both tasks, at least two claimants and declared interruption/orderings; no vacuous skip success |
| Queue persistence/compatibility | No existing U1 broker restart evidence | Isolated pinned-image persistent-volume restart/crash/storage-failure/redelivery/DLQ/legacy cases; distinguish transport duplication from invocation grants |
| Browser/integrated journey | Default Playwright is mock-first; current CI has no Playwright lane | Production build, real authenticated BFF/API/worker/queue/store, summarize→SSE→COMPLETED→exact result; relevant fallback/focus/access controls and both-task backend fixtures |
| Performance/resource/maintenance | No measured U1 acceptance established | Approved 100-sample p95 profile, exact snapshot sizes/resources, independent renewal and recovery/cleanup progress/deadline proof; report failed attempts |
| Security/supply chain | Existing audit/secret/dependency and separate CodeQL workflows | Preserve inherited gates, pin required dependencies/images, focused identity/redirect/cookie/query/telemetry negatives; pending existing audit items are not silently called cleared |
| Package/release | Main release workflow tags/releases; retired AWS CD path | Immutable qualified source/runtime/config/migration/test manifest; tagging alone supplies no production activation authority |

New script names, configurations and tests are Code Generation outputs, not assumed present commands. The same commit's required check manifest must enumerate all relevant workflows/check contexts; a successful CI run cannot hide a failed required security/browser/coverage check. A skipped integration lane cannot satisfy the real skeleton. Existing unrelated tests/workflows are preserved; shared source/registry changes require their regressions.

## CI-2 Qualified Source and Artifact Contract

| Manifest field | Required binding | Purpose |
|---|---|---|
| Repository/ref/source | Fixed trusted repository, main push event, immutable commit/tree and reviewed source identity | Reject fork/PR/event confusion and mutable working-tree deployment |
| Required checks | Exact SHA, workflow/check identity/version, conclusion and complete expected context set | Missing, cancelled, stale or different-SHA checks fail closed |
| Runtime/build closure | Actual Python/Node/package lock and dependency-image identities, frontend build-mode settings | Cross-platform native build differences must be recorded/tested; no unchecked mutable SDK/image upgrade |
| Artifacts/configuration | Content digests, release paths, schema/capability/queue/result versions and environment manifest digest | Bind actual served bytes and configuration; safe path extraction and credential-free artifacts |
| Migration ledger | Registered ordered migration digests and observed schema/readers' compatibility | Additive transition and reproducible restart/resume, not discovery-selected SQL |
| Staging/evidence | Environment/resource identity, tested assertions, actual failures/skips, p95/raw attempts and safety receipts | Mock or wrong-environment evidence cannot qualify the real path |
| Rollback candidate | Last qualified compatible release/configuration with current schema/effect/result readability | An old legacy worker is not a valid rollback for v1 work |

Build/package on hosted CI or a credential-free isolated environment compatible with the target; perform any required native dependency build under the same isolation/trust rules, not inside production's source/venv. Reuse the identical qualified artifact bytes for staging and production; environment-specific public build values create distinct digest-bound variants from the same source. Test the production-intended variant too. Every `NEXT_PUBLIC_*` value is build-time input; a restart cannot change it. Source-map upload tokens and deployment credentials never enter client bundles.

Only trusted successful main commits are candidates for server-side pull; PR/fork testing stays on hosted/isolated infrastructure. Retrieve evidence/artifacts over authenticated verified transport with minimal read permission. Validate manifest schema/digests/repository/commit/path before extraction or execution. Mutable tags, action names alone, stale downloaded manifests and the current dirty develop checkout are insufficient. Hold deployment if a required evidence chain is incomplete.

## CI-3 Server-Side Pull and Staging Qualification

1. A bounded existing-server automation role checks trusted main/check evidence on a proposed 60-second interval. It records qualified candidate identities in a durable release journal and serializes one deployment operation. Do not cancel an in-flight production transition to chase a newer commit.
2. Fetch/validate the immutable candidate into a new restricted release directory outside the working checkout; preserve the prior qualified release. Validate actual target manifests, dependency closure, available disk/memory/connections and IG-1/IG-2 before starting staging. Incomplete temporary downloads cannot become release inputs.
3. Start only isolated staging topology/resources with candidate code and synthetic owned fixtures. Explicit role/environment selection avoids the production `.env` and installer/rebuild side effects. Perform the real migration/authority/queue/resource/browser/security/monitoring checks in CI-1; destructive broker and clock fixtures cannot touch production resources.
4. Produce exact source/artifact/config/schema-bound staging evidence. Prove the production-intended build variant and all C1–C4/C6–C8 capabilities, including both backend tasks, owner purge and no read-side generation. Preserve required U1-delivered accessibility and meaningful error/fallback/focus checks.
5. Qualify latency under the agreed real-staging HTTPS/BFF/gateway path, one active job and 100 sequential samples/metric, recording geography, edge/network overhead, shared-host contention, failures and resource/fixture limits. A local/mock timing pass does not substitute. The human-authorized skeleton command remains separate and cannot be invented by this pipeline design.
6. After exact-commit CI/staging/readiness gates pass, continue automatically into the compatible production sequence below. Missing qualification stops affected activation; initial operator/environment configuration and the skeleton/security checkpoints are retained, not replaced by a per-merge manual production approval.

The journal records candidate, verified evidence, phase start/result, active/previous release and failed/rolled-back state. After interruption, inspect actual schema/config/runtime state against the journal before resuming; do not replay uncertain migrations/sends or assume a step succeeded from a start marker. Qualified candidates are processed serially with explicit supersession disposition where relevant; never silently call skipped candidate deployment successful.

## CI-4 Compatibility-First Production Activation

| Order | Required action | Gate before the next action |
|---|---|---|
| 1 | Validate IG-1–IG-9 and retain current qualified release, protected configuration and existing backup/recovery evidence | All actual target dependencies, alerts, resource and rollback prerequisites bound to candidate |
| 2 | Coordinate the shared broker transition separately when required: inhibit all affected sends and prove drain/lossless transition for every queue pair | No unaccounted delayed/in-flight/legacy work; no memory-only broker restart shortcut |
| 3 | Apply registered additive job/binding/effect/prepared/progress schema and owner-lifecycle integration | Migration digest ledger, current data/legacy classification and compatible readers verified; no guessed authority backfill |
| 4 | Install compatible restricted API/result/event readers while v1 producers/new UI remain disabled | Cookie/session/redirect/no-store/order/read-only behavior and old consumer tolerance pass |
| 5 | Stop old independent senders/workers from reaching new authority; drain active old work to terminal or isolate it with explicit reconciliation ownership | Old authority cannot consume/mutate v1; unresolved isolation is not a resolved user outcome |
| 6 | Install qualified compatible worker/supervisor and separate maintenance roles | Pool/deadline/timer/queue/durability/owner/notification configuration validated; no blind sweeper or effect release |
| 7 | Enable guarded v1 producer and then digest-bound new frontend exposure only after required capabilities are verified | Real owned receipt→events→exact result smoke and safety/read side-effect assertions succeed |
| 8 | Observe health, error, renewal, progress, deadline and safety counters; record actual serving identity and qualification | CI-5 abort conditions absent; missing observations fail closed rather than healthy-zero |

Represent producer/new-UI exposure as explicit proposed release-manifest switches, disabled by default until their prerequisites pass. They do not authorize changed retry/result behavior or enable unavailable backend features. Frontend public exposure requires the appropriate built artifact; server configuration alone cannot change an inlined flag. Actual configuration names and complete scripts belong to the implementation plan. Existing unrelated request paths and queue consumers require compatibility, not accidental shutdown by `restart all`.

Release strategy is a bounded, serialized compatibility-first replacement of existing processes with a gated exposure boundary, not a claimed zero-downtime blue/green or atomic multi-runtime rollout. Existing single-host topology may interrupt streams; clients must exercise their approved read/poll/reconnect behavior. Do not add a global uptime promise or remove data/network controls to make rollout possible.

## CI-5 Abort and Rollback

| Trigger | Immediate action | Safe rollback/resume condition |
|---|---|---|
| Staging, required check, identity/digest or isolation failure | Stop before production mutation/exposure; retain safe failure evidence | Correct/requalify same or new candidate with fresh bound evidence |
| Migration/schema/read compatibility failure | Hold new producer/UI; preserve committed additive schema and previous qualified reader where compatible | Verify ledger and actual state; no destructive downgrade of prepared/effect records |
| Old consumer/ambiguous work not safely drained/isolated | Keep new authority emission disabled and preserve old work/evidence | Explicit compatible reconciliation; no fresh grant inferred from missing ledger |
| Worker/maintenance/deadline/notification readiness failure | Stop unsupported intake/exposure; preserve supervised current authority and guarded maintenance | Qualified compatible control runtime; no old blind re-executing worker |
| Wrong result, access leak, extra invocation/read-side generation or stale unguarded publish | Disable affected producer/UI exposure and isolate unsafe runtime; contact recorded owner/security reviewer | Last qualified C6/C7-capable reader/worker; preserve binding/fences/exact snapshots and incident evidence |
| Broker persistence/storage/configuration failure | Preserve broker data and inhibit unsupported sends; account for every affected queue | Last proven compatible persistent broker/configuration; do not recreate empty queues/redrive blindly |
| Post-activation smoke/control health failure | Restore qualified application/config pointers in safe dependency order; allow known compatible readers/maintenance to settle existing work | Active release/schema/queue capability identity verified; streams can reconnect without resubmission |

Rollback never deletes keys/effect intent/results/history to make work retryable, extends fixed expiry, rerenders a result from current settings, or restores a worker that grants another invocation. Schema contraction and backup restore are separate evidence-backed recovery operations, not automatic app rollback. Preserve actual owner/expiry invariants on isolated restore. Do not erase logs/evidence or overwrite user-owned source changes during rollback.

Before exposure, rehearse failure at each persisted release phase, stale/replayed check evidence, killed deployer, active-worker publication, queue restart and wrong-environment configuration. Record complete runtime/config/schema identities and actual health/read-only smoke outcomes. Recovery from an interrupted deployment is not completion merely because the journal lists a phase start.

## CI-6 Secrets, Permissions and Operational Ownership

| Actor | Credential/access scope | Separation |
|---|---|---|
| Hosted PR/CI test jobs | Repository read and isolated test resources; synthetic fixture credentials | No production credential provider, tunnel/broker or main-only deployment capability |
| Artifact/evidence retrieval | Minimal trusted repository/actions read permission and verified transport | Fixed repository/commit/check identities; never interpolate arbitrary commit text into a shell |
| Server activation | Purpose-scoped qualified release/configuration and registered migration operations | Credential material outside source and releases; explicit environment; no unrestricted Actions runner on production |
| Staging processes/fixtures | Isolated stage identities/resources only | No production mounts, socket, network or secrets; provider/default resolution cannot silently select production/AWS |
| Sentry upload/alerts | Server/CI-only upload/auth capability, safe public client routing identifier where appropriate | No session/auth secret in client bundle/localStorage; verify scrubbed source maps/events |
| Operator | revenantonthemission readiness/security accountability | Bind actual monitoring/escalation and existing backup policy; October 14 review plus U3 implementation follow-up remains required |

Maintain pinned action/tool/dependency/image identities and safe artifact extraction/configuration rendering. The current historical Dockerfile performs a mutable SDK upgrade and has platform-specific dependencies; it is source evidence, not a reproducible U1 build receipt. Reconcile the actual affected build closure in the approved implementation plan and preserve unrelated deployments' compatibility. No direct edits to live credentials, LaunchAgents, cloud configuration or protected workspace source are authorized by this design.

## CI-7 Coverage and Handoff

`traceability.json` maps detailed infrastructure-relevant NFRs to IS/MD/CI sections and retains N/A client-only responsibilities. NFR11.1's existing checks/test-after/new-code floor, NFR8.1's scheduled code-based security disposition, NFR9's raw measured profile and NFR11's both-task crash/result/deletion evidence remain pass/fail gates, not optional delivery notes.

U1 supplies the real protected skeleton and shared backend guarantees; U2/U3 follow only after its verified human checkpoint. Code Generation must author complete application/configuration/automation and tests under its separately approved plan and requested senior-engineering implementation-plan review. Environment/deployment stages verify actual provisioned controls and execute rollout under their own authorization. The exact integrated verification invocation remains unset until separately selected by the human; no CI script name or successful document check fills it.

Functional Design Minor R-05 and NFR Requirements Minor R-01 remain in their upstream records for the U1 checkpoint. Generated infrastructure citations and required tests do not retroactively mark those findings resolved. This delivery design records no application test, staging benchmark, live alert, provisioning or deployment pass.
