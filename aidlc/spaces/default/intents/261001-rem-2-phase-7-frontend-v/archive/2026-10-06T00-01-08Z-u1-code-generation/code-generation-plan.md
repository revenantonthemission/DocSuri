# U1 Integrated Job Skeleton Implementation Plan

## Sources and Completion Target

The confirmed `code-generation-questions.md` selects private staging with a controlled egress helper and authorizes preparation of this plan. Implementation still requires its separate exact-plan approval. Source behavior/authority comes from `../functional-design/{functional-spec,rules,entities}.md`, `../nfr-requirements/`, `../nfr-design/`, `../infrastructure-design/{infrastructure-specification,monitoring-design,cicd-pipeline}.md`, `../../../inception/{requirements-analysis/requirements,user-stories/stories,domain-design/components,contract-design/contract-summary}.md` and `../../../inception/units-generation/{unit-of-work,unit-of-work-story-map}.md`. `baseline-results.md` records the current source/tests; `unit-test-instructions.md` supplies exact U1 command/filter/prerequisite scope.

Deliver the actual summarize → authenticated BFF/gateway → one authoritative dispatch/worker → native SSE → truthful COMPLETED → exact owner/TTL-checked rendered result, with containment, accessible focus/announcements, in-session original-request recovery and safe diagnostics. Shared backend guarantees are implemented/tested for summarize and translate. U2 later completes translation UI/reload/copy/wider resilience; U3 owns asset viewer migration. Do not declare spanning stories or the release complete from U1 alone.

## Source, Runtime and Write Boundaries

- Modify the current user-authored integration in place; preserve unrelated dirty work. No duplicate replacement clients, resetting to HEAD, automatic commit/push, changing live configuration or running the production `docsurictl rebuild`/installer is part of this plan.
- Current baseline: frontend 356 passed; backend 473 passed/7 skipped; summarization 463 passed/3 existing SSE failures/3 skipped; root 194 passed/2 skipped; Ops 342 passed/5 skipped in its own environment. Current scoped frontend lint/typecheck passed. The three SSE failures are assigned corrections, not waived completion failures.
- Keep Next.js 15.5.26/React 19/TypeScript 5.7.3, pnpm 9.15.9 and actual runtime closure. Existing backend Python is 3.13.7; reconcile the Docker Python >=3.13 requirement imposed by Ops and remove unchecked mutable affected build inputs. Image qualification/security remains an actual prerequisite, not a claim that a new pin was tested here.
- Registry metadata checked during planning supplies candidate exact frontend pins: SWR 2.5.1, Sentry Next.js 11.4.0, clsx 2.1.1, tailwind-merge 3.7.0, Tailwind/@tailwindcss/postcss 4.3.3, @vitest/coverage-v8 3.2.6 (matching Vitest), and @axe-core/playwright 4.13.0. Peer declarations fit the retained React/Next/Node versions; frozen installation/build/audit still must pass. Add actual compatible Python coverage tooling and freeze its version in project locks during runner setup, not an ad-hoc global install.
- Restrict stricter new-code lint/type checking to the declared U1 graph without weakening existing checks. Do not falsely claim the current config already enforces every historical rule; no explicit/implicit any or forbidden library is introduced. Avoid broad legacy refactors solely to make new configuration green.
- Backend/browser test code uses owned fixtures, never production credentials/DSNs/queues/buckets. Real tests fail on missing/wrong realm prerequisites; they do not silently skip and count as acceptance. Missing qualified MinIO/image/control/notification prerequisites block their affected run/exposure, not code correctness through a fake pass.

## Concrete Staging Enforcement Treatment

This specifies the mechanism selected in Q1 and the implementation treatment of Infrastructure Design R-01. Its completed finding remains in its original record; no retroactive status or source edit is implied.

| Path/control | Concrete planned implementation | Qualification |
|---|---|---|
| Workload network | Dedicated internal Docker network for staging frontend/API/worker/data/inference/browser; no host networking, extra external attachment, production mount/home or Docker socket | Effective network/mount/credential inventory; direct host/LAN/production and outbound attempts denied |
| Protected ingress | Existing host cloudflared reaches only loopback-published staging frontend port 13000; frontend reaches staging API internally | Preserve production routes/catch-all; staging access before DNS exposure; real HTTPS/session/BFF path |
| Outbound helper | Staging-only explicit HTTPS CONNECT proxy, using a qualified Squid image/configuration, attached to internal and isolated egress networks; no public host-published proxy port | Exact domain allowlist for staging origin and required diagnostic hosts, port 443 only, reject literals/alternate encodings/production domains/unlisted CONNECT |
| TLS service identity | Squid's qualified ClientHello peek-and-splice path binds each CONNECT hostname to the visible client SNI before forwarding; no TLS decryption | Reject missing/mismatched SNI, unqualified TLS versions, ECH/concealed identity and opaque handshake paths; fixed per-host CONNECT/SNI policy, not just membership in the same allowlist |
| Encrypted HTTP authority | Require a verified external HTTPS service boundary that denies domain fronting/inner-authority mismatch for each permitted shared-address destination, including the Cloudflare staging edge | Before admitting traffic, retain operator-bound provider/configuration and controlled shared-IP mismatched SNI/HTTP Host or HTTP/2 :authority results. If the current provider/account cannot prove this boundary, its route remains closed pending a concrete boundary decision |
| Helper destination enforcement | Proxy hostname/destination ACLs plus Linux guest packet filter scoped to helper/staging network identities, complemented by the qualified service-identity boundary above | Deny loopback, link-local, private/host/LAN/production destinations and DNS rebinding; IP ACLs alone cannot distinguish co-hosted HTTPS services |
| Guest enforcement point | Versioned rules in Docker's supported `DOCKER-USER` forwarding path plus required guest host-input controls for staging sources; explicit DNS resolver/established-reply exceptions only | Probe actual container-runtime/firewall backend; missing/different control path blocks installation/start rather than falling back to unrestricted egress |
| Direct bypass prevention | Default-deny for staging-source forwarding/host input; internal peers and the proxy's internal address/port are the only explicit paths; rules precede workload start | Test host-gateway, LAN, broker/store/production targets, public direct egress and helper address-family bypass |
| DNS/address families | Bind actual resolved destinations at connection time; kernel destination denial remains effective after rebinding; equivalent IPv4/IPv6 rules or explicitly disabled/denied unqualified family | Paired public-allowed/private-rebound tests and IPv6/literal/alternate-host negatives |
| Browser/diagnostics | Playwright Chromium proxy configuration and explicit supported server diagnostic proxy transport; internal BFF/API calls bypass only approved internal peers | Native EventSource still browser-native; configured proxies preserve streaming/cancellation/end-to-end TLS; no TLS interception or sensitive request/proxy logging; browser/transport opaque handshake features are denied until qualified |

Full image pins, policy rendering, rule transactions and scripts are implementation outputs in the source footprint. Treat runtime-dependent rule identities/addresses as validated manifest data, not arbitrary shell text. Separate operator-side guest rule application from unprivileged workloads; the proxy does not receive Docker socket or administrative capability. Require actual egress rule/ACL proof before starting destructive fixtures. Unsupported runtime semantics or unavailable qualified image needs the concrete prerequisite decision permitted by Q1; do not silently switch platform or loosen the boundary.

The provider boundary is an explicit dependency, not an assertion that Cloudflare already denies every same-account/co-hosted authority mismatch. The admission manifest lists each permitted destination, CONNECT/SNI binding, provider rule/configuration identity, shared-address negative-test evidence and validity/refresh conditions. Qualify harmless mismatched SNI and encrypted HTTP-authority requests before workload admission; policy/provider changes, expiry or an unsupported handshake withdraw the affected route. A public hostname, successful certificate validation or a 443-only IP rule is insufficient. This retains the selected end-to-end TLS policy; an alternative inspection boundary would require its concrete decision rather than being silently substituted.

Use the resolving provider source `backend/modules/summarization/src/summarization/real_wiring.py`, not the incorrect infrastructure brace expansion (R-02). Preserve all four recorded upstream findings for the U1 checkpoint, including Functional Design R-05 and NFR Requirements R-01.

## Backend Protocol and Integration Decisions

| Concern | Implementation direction | Required proof |
|---|---|---|
| T1–T3 | One atomic owner/key acceptance and dispatch binding; durable NOT_STARTED→SENDING grant; one real adapter send; confirmed, definite rejection/release and ambiguous retention distinguished | Concurrent same-key/first claim; early/late ack; crash before/after send; no recursive legacy second-send |
| T4–T7 | Durable intent before one invocation; current server-time fence/lease; exact T5 binding separate from T6 state/event/expiry; publication-only reconciliation | Both renew/reconcile orders, lost commit acknowledgement, prepared-before-publish, stale writer and no fresh grant from existing intent |
| Payload/queries | Persist final allowlisted returned summary/translation including overlays; private canonical content digest; query-only result dependency | Changed preferences cannot alter content; C2 positive/negative bare DocModel; 401/404/409/410/422/503 precedence and zero extra work |
| Physical authority | Extend existing job/effect/event store with binding/prepared/progress records and indexed eligibility; registered additive migration | Real PostgreSQL, safe legacy/orphan classification; source migration 002 preserved |
| Owner lifecycle | Add explicit content-job coverage to existing inactive-owner/purge integration with child cascades, current owner recheck and no resurrection | Real deletion/publication races; preserve current account policy/lock compatibility |
| Current input/legacy | Strict new caller profile and preserved supported legacy normalization; load input/owner from recorded job, not queue/body identity | No synthetic merging for keyless calls; no invented authority for active old records; unrelated workflows preserved |
| Transport | Native EventSource with real LF frames and opaque job-owned cursor; separate state seq/history; private/no-store, distinct cookie relay, explicit redirect refusal and cancellation | Event ID differs from seq; header precedence; terminal 204; stream body not buffered/truncated by header timeout |
| Runtime | Purpose-bounded pools/control scheduling and supervised generation child/task; capacity-bound receiving | D/Q total 5 s, H/L 15/90 s, V/R 120/30 s, fresh final guard/admission >15 s; actual loaded/cancellation proof |
| Maintenance | Independent 30 s recovery; 20 s/100-row bounded passes, first-send remaining budget >16 s after discovery ≤3 s; hourly root cleanup with ≤60 s continuation | Three eligibility classes including no-effect SENDING/UNKNOWN at 120 s; persisted progress and 24 h post-expiry purge |

No queue visibility renewal or publication reconciliation grants another whole-pipeline invocation. Remote exactly-once execution is not asserted. Fail safely with retained binding for ambiguous dispatch/effect; only proven pre-effect non-dispatch may release a key. SDK send attempts are one; cancellation/lost response does not prove rejection. PostgreSQL 16 does not already supply a newer server-wide transaction timeout: implement total handling/cancellation/quarantine and recheck authoritative identity, then qualify the selected budgets.

## Frontend and Compatibility Decisions

- ContentJobApi retains native fetch through the custom Transport at `/bff/api/content-jobs`; use direct Transport operations for jobs so ApiClient's general retry plus SWR's default retry cannot multiply C8. Native stream reconnect and fixed two-second nonoverlapping fallback are separate. Preserve existing unrelated transport consumers/budgets.
- Capture immutable validated input/field order before full UTF-8 owner:paper:task:JSON.stringify hashing. Reserve preparation revision before await and recheck before synchronous memory/storage publication. Retain C4 handles before POST; availability/action/restore guards prevent stale/edited-draft/other-owner resend or old-job overwrite. Persist the approved metadata only; digest is not authentication.
- Use the actual `SessionContext`/`currentSession()` boundary, never a dummy user ID or client-read cookie. Protect refresh/sign-out races and distinguish verified access loss from transient revalidation. Owner/context change clears protected state/capabilities; transient channel loss retains only clearly stale authorized observations.
- JobSubmissionForm owns explicit initial summary-level choice and pre-job uncertainty. JobStatus mounts only after actual returned identity/state. Keep its client projection separate from the parent's immutable authorized history/cursor checkpoint. Native EventSource is owned there; never guess HTTP status from onerror or progress/ETA from lifecycle names.
- SummaryModal's durable-result path accepts query/dismissal capabilities and reads existing prepared content; no mount/persona effect can request generation. Preserve applicable existing display/anchor formatting and initial expert default in the submission form. Enumerate actual legacy consumers; maintain intentionally unrelated paths with an explicit compatibility boundary, not a second durable-result owner or duplicate API client.
- Implement ErrorBoundary then its tests and full-page fallback then its tests. Network/callback/diagnostic failures remain explicitly handled. Focus follows the approved conditional rule; announcements are deduplicated and current-context only. Preserve semantic themes, reduced motion, sticky constrained-layout fallback, 200% text resize and 320 CSS-pixel reflow.
- Keep U3's existing asset/document interfaces and job-proxy regression boundary intact. No new durable-job code consumes presigned/token helpers; U3 owns their viewer migration. Translation backend exactness is U1; translation UI, result-ID copy and the wider reload/replay matrix remain U2.

## Ordered Implementation Steps

All boxes below are Part 2 work and remain unticked before initial Plan Approval. Implement each applicable component/layer fully, then write/run its tests. Existing baseline findings are explicitly repaired; tests are not deferred to Build and Test.

| Step | Work and completion condition | Story / requirement trace |
|---|---|---|
| [x] Step 1 | Recheck approved source binding and the write footprint; preserve pre-existing changes and recorded baseline. Before any application write, the invoking coordinator captures source bytes/digests and absent-path markers using bounded file tools under the record's .aidlc-engine/u1-source-baseline/, bound to the live Planned Source. Stop on unexplained drift; HEAD is not the dirty-source coverage baseline. | NFR11; all U1 stories |
| [ ] Step 2 | Bootstrap complete runner/build/configuration support, exact candidate dependencies/locks, strict U1 checks and coverage tools; verify current exact unit-scoped runner command. Reconcile Python >=3.13 build closure and qualified image prerequisites without global installs or waived findings. | NFR11.1, NFR12; US1.5/US8.1 |
| [ ] Step 3 | Implement typed job/binding/effect/prepared models, safe input/outcome codecs and canonical final-content identity; keep actual legacy/default semantics and browser/server digests distinct. | US1.1/US1.3, US2.6/US3.4; BR1–BR3 |
| [ ] Step 4 | Author/run model/codec tests after Step 3: valid two-task content, invalid wrappers/fields/nonfinite values, legal terminals, keyed/keyless identity and unavailable provenance. | NFR1.4, NFR11.2 |
| [ ] Step 5 | Add ordered registered authority/prepared/progress migration, indexes/constraints and compatible owner-lifecycle schema guards; retain prior migration bytes and safe legacy classification. | US2.6/US3.4; NFR11.4–5 |
| [ ] Step 6 | Author/run only the completed migration/index/constraint/active-owner schema tests against disposable real PostgreSQL; missing realm fails. Full existing-purger T8 integration is not claimed here and runs after its Step 15 bridge, in Step 16. | NFR11.3/11.6 |
| [ ] Step 7 | Implement atomic RDS store and faithful in-memory test adapter, named bounded purpose pools, deadline/cancellation/uncertain-commit handling, exact reads and progress paging. | US2.6/US3.4; T1–T8 |
| [ ] Step 8 | Author/run repository tests after Step 7 and real-store claimant/renew/publication/deletion tests; preserve required failure evidence and consistent event/state/binding. | NFR1.2/1.5, NFR11.2–7 |
| [ ] Step 9 | Implement ContentJobService commands/query capabilities and authoritative accept/dispatch/claim/prepare/publish/reconcile/expiry semantics; no pipeline in read dependency. | US1.1/US4.2, US2.6/US3.4 |
| [ ] Step 10 | Author/run service tests after Step 9 for retained replay, definite release, UNKNOWN retention/120 s settlement, actual state, exact result precedence and zero read-side work. | FR4, C1/C2/C7 |
| [ ] Step 11 | Implement one real bounded queue dispatcher, C6 decoding and legacy ContentJobQueue normalization delegating to that service; remove recursive/independent second send and untrusted abstract source. | US1.1/US2.6; C6/C8 |
| [ ] Step 12 | Author/run dispatcher/compatibility tests after Step 11: early receipt, timeout/late ack/reject, duplicate send claim, supported omitted/keyless callers, invalid/old/unknown-major quarantine. | NFR4.4, NFR11.4 |
| [ ] Step 13 | Implement worker supervisor/grant consumption, isolated pipeline execution, independent lease/visibility renewal, actual DTO inspection/final payload capture, terminal acknowledgement and safe crash/shutdown handling. | US2.6/US3.4; C7 |
| [ ] Step 14 | Author/run worker tests after Step 13 for both tasks and all success/abstain/unavailable/degraded/pending/malformed/thrown outcomes, slow child, redelivery and T4/T5/T6/ack interruptions. | NFR11.2–3, NFR6.2 |
| [ ] Step 15 | Implement independent bounded recovery/cleanup/health observation entry points and progress; current-owner purge/late-write bridge; replace unsafe old sweeper. Adapt tests/accounts/test_purge_real_postgres.py to read-only realm/identity preflight before destructive setup, a separate disposable minimal-schema database and mandatory U1 no-skip mode. | US2.6/US3.4; NFR7.4/11.4–5 |
| [ ] Step 16 | Author/run maintenance and full T8 deletion integration after Step 15, including both publication/deletion orderings. Add missing-DSN/driver, wrong marker/database/role and no-destructive-call fixture negatives; then use the guarded retained purge fixture. Cover all recovery/cleanup classes, progress/restored rows, TTL/24 h and no resurrection. | NFR11.3–7 |
| [ ] Step 17 | Implement compatible job controller/readiness and restricted result route; real LF stream, authorized cursor lookup/seq, terminal 204, safe errors/private headers and actual assembly. | US1.5/US2.1/US3.1/US3.4 |
| [ ] Step 18 | Author/run HTTP/controller tests after Step 17, repair the three existing SSE failures, and verify malformed input/unauth/other-owner/expiry/cursor precedence without side effects. | NFR1, NFR5; C1–C3 |
| [ ] Step 19 | Implement job streaming branch and cancellation in BFF; Cookie/separate Set-Cookie/error fidelity, explicit protected redirect refusal and private/no-store; preserve other routes and GET-only retry budgets. | US1.5/US2.1; C3/C8 |
| [ ] Step 20 | Author/run BFF/transport tests after Step 19, including incremental chunks, header/query forwarding, cancellation/header timeout, 204, multiple cookies/error/redirect and asset/evidence/search regression. | NFR1.1–3, NFR5, NFR12 |
| [ ] Step 21 | Implement ContentJobApi/C4 capabilities and stateless IdempotencyService, allowlisted persisted attempts, typed boundary validation and owner/job/context-scoped query behavior. | US1.3/US1.4/US4.2/US3.4 |
| [ ] Step 22 | Author/run API/identity tests after Step 21: full-prefix Unicode digest, A/B hashing race, edited draft, quota/corruption, restore/no POST, supersession/in-flight/old response and missing originals. | NFR4, BR1.3–5 |
| [ ] Step 23 | Integrate actual session identity and epoch/race/verified-access signals while preserving existing session consumers; job state never treats a transport error as a proved HTTP denial. | US1.1/US1.4/US2.5 |
| [ ] Step 24 | Author/run session-context tests after Step 23 for sign-out/late refresh, owner change, confirmed denial and transient stale observations; run existing session/route guards. | NFR1, NFR5.3/12.2 |
| [ ] Step 25 | Implement complete JobSubmissionForm and shared dialog presentation, initial expert/beginner selection, explicit submit and pre-job original-request recovery. | US1.1/US4.1/US4.2 |
| [ ] Step 26 | Author/run submission tests after Step 25 for no mount/select POST, received/uncertain/error states, actual-job callback, edited draft and conditional focus. | FR1/FR4/FR6 |
| [ ] Step 27 | Implement standalone ErrorBoundary with scrubbed containment callback and authorized reset context. | US7.1; NFR6 |
| [ ] Step 28 | Author/run boundary tests after Step 27 for happy rendering, thrown descendant and reset/context loss; async failures use their separate owner. | AC7.1, BR5.3 |
| [ ] Step 29 | Implement full-page ErrorBoundaryFallback outside the failed subtree with safe return/tracking-only reset and focus/announcement behavior. | US7.2/US7.3 slice |
| [ ] Step 30 | Author/run fallback tests after Step 29 for valid/missing context, repeated crash, zero submit and usable focus/return. | NFR6.1/6.3, NFR10 |
| [ ] Step 31 | Implement JobStatus current-context projection/reducer, native EventSource/opaque history, separate seq watermark, two-second SWR fallback, terminal/context cleanup and truthful accessible status. | US2.1/US2.2/US2.4, US2.5 slice |
| [ ] Step 32 | Author/run status tests after Step 31 for live/fallback/restore/terminal, poll-ahead/older history, duplicate/malformed input, late old job, unknown progress and deduplicated announcements. | NFR5/6/9/10; BR4 |
| [ ] Step 33 | Implement SummaryModal completed-result query-only presentation with exact prepared content, recorded level, transient read retry, safe existing views and dialog focus. | US3.1/US3.3 slices, US3.4 |
| [ ] Step 34 | Author/run result tests after Step 33: zero POST on mount/retry/preferences, loading/available/401/404/409/410/422/503/unsupported, changed settings and conditional focus. | C2/C4, NFR1.5/12.2 |
| [ ] Step 35 | Integrate PaperDetailIsland stable owner/paper/actual-job/received-history context, submission/status/result/fallback composition and hide/show; preserve existing body/translation/document navigation. | US1.1/US2.1/US3.1/US4.2/US7 slices |
| [ ] Step 36 | Author/run parent journey tests after Step 35 for actual receipt before mount, lost response/replacement, obsolete callback and render-only reset with retained history/focus; retain paper tests. | ADR-013, FR4/FR7 |
| [ ] Step 37 | Implement scrubbed Sentry/client connection/mount/lifecycle and backend authority/maintenance signals with bounded nonrecursive diagnostics; actual unknown cause stays unknown. | US8.1 slice; NFR7/9 |
| [ ] Step 38 | Author/run diagnostic tests after Step 37 for captured envelope scrubbing, drops/restoration/latency, explicit recovery versus execution and failed sender without UI crash. | NFR7.1–4 |
| [ ] Step 39 | Implement complete isolated staging compose/manifests, owned fixture setup/teardown, qualified persistence and controlled proxy/guest-policy rendering/preflight; inspect-only default until correct realm/operator application. | Q1, NFR1/11.6–7 |
| [ ] Step 40 | Author/run staging/policy tests after Step 39: both families/bypass/rebinding/CONNECT, mismatched CONNECT/SNI and encrypted HTTP authority on controlled shared-address services, opaque/ECH failure, wrong env/credentials/mounts, safe rule apply/rollback and actual provider-boundary allow/deny proof before route admission. | Infrastructure R-01 treatment, IG-2/IG-5 |
| [ ] Step 41 | Implement server runtime/configuration/role lifecycle, maintenance/observer scheduling, safe immutable pull/release journal, compatible exposure/rollback and existing alert/channel bindings. | NFR7.4/11.4–5; CI-3–CI-6 |
| [ ] Step 42 | Author/run runtime/delivery/monitoring tests after Step 41 for actual config guards, separate roles/cadence/progress, stale check/digest/PR input, interrupted phase and non-destructive rollback. | C8; IG-6–IG-9 |
| [ ] Step 43 | Implement source/build/CI integration, complete Python/frontend/shell collection and ops/server/u1_coverage.py's frozen-baseline changed-executable-line gate for every eligible source-manifest write. Unmeasured files/report identity mismatch fail; no denominator is based on HEAD or pre-existing user changes. Add exact U1 real-store/browser/security/context gates. | NFR11.1/12; continuous delivery |
| [ ] Step 44 | Author/run CI/coverage configuration tests after Step 43 for missing/cancelled/wrong-SHA checks, vacuous skips, omitted controller/pool/wiring/purge/helper files, wrong baseline/source reports, below-80% lines, unqualified pin and source-map secret exclusion. | CI-1/CI-2; NFR7.1 |
| [ ] Step 45 | Implement real U1 integrated verification/performance harness with authenticated gateway/cookies, worker/queue/store/provider, both-task backend fixtures, raw 100-sample timings and qualified resource/deadline evidence. | Full U1 skeleton; NFR9/11 |
| [ ] Step 46 | Author/run harness tests after Step 45: wrong realm/prerequisite fails, no mock-only success, no failed-sample hiding, no command-based generation on reads or unsafe cleanup. | NFR1/9/11.2–7 |
| [ ] Step 47 | Run completed U1 scoped suites/coverage/lint/types/build and required isolated real-store/browser/maintenance/queue evidence; compare existing regression lanes with the baseline and repair regressions without weaker targets. | All delivered U1 AC/BR/NFR |
| [ ] Step 48 | Document exact changed files/decisions/results/deviations and runnable prerequisites; create strict source-manifest.json claiming every application write and coverage targets that exist, retaining later-unit dispositions. | NFR11; traceability contract |
| [ ] Step 49 | Obtain required post-implementation independent code/plan/source review and current receipts; repair within the prescribed flow; no missing evidence or placeholder result. | Required Code Generation review |
| [ ] Step 50 | Present the actual integrated check for its separate human command authorization and verify the completed U1 skeleton/current source for the human checkpoint; no later Unit or production action is inferred from plan approval. | Walking skeleton, NFR8/NFR11 |

## Planned Source Footprint and Blast Radius

Paths are workspace-relative. Existing files are modified minimally in place; proposed new paths are explicit planned locations. The final source manifest must reflect actual writes, including scripts/locks/generators, not merely this preliminary list. Any new unrelated claim needs explicit scope reconciliation. Do not overwrite the pre-existing frontend wire comment changes by indiscriminate regeneration.

| Source area / planned paths | Change / consumers | Impact and tests |
|---|---|---|
| `backend/modules/summarization/src/summarization/domain/job.py`; new `domain/prepared_result.py`, `domain/job_protocol.py` | Authority/model/codec additions, preserve existing task boundaries | High; model/service/store/worker/controller tests |
| `backend/modules/summarization/src/summarization/ports/ports.py`; new `ports/job_protocol.py` | Typed command/query/atomic store/dispatcher capabilities without duplicate owner | High; both store adapters, assembled API/worker and legacy queue |
| `backend/modules/summarization/src/summarization/adapters/{rds_jobs,in_memory_jobs,_pg,settings,content_job_queue,recovery_sweeper}.py`; new `adapters/job_dispatch.py` | Atomic persistence/purposes/real dispatch and safe compatibility/maintenance | High; real-store races/deadlines/queue and existing module regressions |
| `backend/modules/summarization/src/summarization/service/job_service.py`; new `service/job_maintenance.py`, `service/job_diagnostics.py` | T1–T8 authority/query/maintenance semantics | High; exact both-task/read/outcome/expiry and ownership |
| `backend/modules/summarization/src/summarization/{worker,real_wiring}.py`; new `job_maintenance.py` | Supervisor/child and environment-specific actual entry/wiring | High; current worker and pipeline/cache/overlay consumers |
| `backend/modules/summarization/src/summarization/api/router.py`; `backend/wiring.py`; `backend/config.py` | Compatible job controller and actual configured ready path; no no-op queue | High; real gateway/mount/session/cookie and preserved other routes |
| New `backend/modules/summarization/migrations/003_content_job_authority_prepared.sql`; `backend/migrations/registry.py`; `backend/modules/accounts/services/owner_data_purge.py` | Registered additive authority plus active-owner/child lifecycle integration | High; migration registry, inactive owner, purge/deletion races; historical SQL untouched |
| `backend/{Dockerfile,pyproject.toml,uv.lock}`; `backend/modules/summarization/{pyproject.toml,uv.lock}` | Frozen compatible runner/runtime/coverage dependencies and actual build closure | Medium/high; current backend/module CI and supply-chain checks |
| `frontend/lib/api/{contentJobApi,httpTransport,routeHandlerTransport,transport}.ts`; new `lib/api/contentJobContracts.ts`, `lib/idempotencyService.ts` | Existing transport migration/C4/validation; preserve unrelated imports | High; BFF/API/identity and non-job route/cookie/hash regressions |
| `frontend/app/bff/[...path]/route.ts`; `frontend/components/session/SessionContext.tsx` | Stream/relay/owner context integration | High; session/route/app tests, asset/evidence/search/agent relay regressions |
| `frontend/components/{PaperDetailIsland,JobStatus,SummaryModal}.tsx` and their applicable CSS Modules; new `JobSubmissionForm.tsx`, `ErrorBoundary.tsx`, `ErrorBoundaryFallback.tsx`, `JobDialog.tsx` and corresponding modules | Scoped durable summarize journey/presentation | High; existing paper/body/summary compatibility and current delivered focus/visual/error behavior |
| New `frontend/lib/{jobState,jobDiagnostics,cn}.ts`; applicable `frontend/{instrumentation-client.ts,instrumentation.ts,sentry.server.config.ts,next.config.mjs}` | State reducer/diagnostics/Sentry composition | Medium; strict types, real metrics/scrubbing and isolated build |
| `frontend/{package.json,pnpm-lock.yaml,vitest.config.ts,eslint.config.mjs}`; new `vitest.u1.config.ts`, `tsconfig.u1.json`, `postcss.config.mjs`, `playwright.u1.config.ts`; bounded `app/globals.css` | Mandatory dependency/build/coverage/scoped-check and rendered-theme support | Medium/high; actual installed/frozen audits and preserved full frontend suites |
| `ops/server/{run.sh,install.sh,docsurictl}`; new `ops/server/{u1_runtime.py,u1_release.py,u1_monitoring.py}` and `ops/server/u1-staging/` | Complete environment-aware dry-run/config/role/release/policy helpers in existing seam | High shared-host blast radius; dry-run/realm tests before operator application; no live rebuild/restart during development |
| `backend/{docker-compose.yml,elasticmq.conf}`; `.github/workflows/ci.yml`; `ops/{pyproject.toml,uv.lock}` | Approved shared broker/CI/purpose runner integration; preserve every other queue/workflow | High; all-queue transition, owner-qualified files and required gate regressions |
| New `ops/server/u1_verify.py`, frontend U1 E2E/performance and backend U1 integration directories | Runnable isolated evidence/harness, not generic mock readiness | High for execution; explicit correct realm/resources/notifications and separate checkpoint command authorization |
| `tests/accounts/test_purge_real_postgres.py`; new `tests/accounts/test_u1_purge_realm_guard.py` | Guard retained destructive fixture before setup; separate minimal-schema disposable database; required U1 failures rather than skipped success | High for execution; read-only identity probe, wrong-target/missing-prerequisite/no-destructive-call negatives |
| New `ops/server/u1_coverage.py`, `frontend/scripts/u1-coverage.mjs`, `ops/tests/test_u1_coverage.py` and coverage collection configuration | Merge identity-bound eligible-source reports and enforce changed-executable-line coverage against the frozen pre-write baseline | Medium/high; omitted file, wrong source/baseline, empty denominator and <80% negatives; no excluded authority/integration code |
| Existing affected tests plus new files named in `unit-test-instructions.md` | Meaningful test-after assertions, not removed safety tests | Full current suites remain required; documented baseline SSE defects repaired |

Do not change U3 AssetViewer/DocModelViewer/ZoomPanControls implementations, unrelated task execution, account policy or protected framework hooks/memory. A necessary shared regression/import correction is explicitly scoped and claimed; a product or architectural expansion is surfaced rather than hidden in an auxiliary file.

## Measurement, Exposure and Rollback Conditions

- Preserve the selected profile/guards exactly: H/L 15/90 s, V/R 120/30 s, D/Q total 5 s, scan 30 s, ambiguity 120 s, admission >15 s authority and >16 s first-dispatch pass; recovery/cleanup pass 20 s/100 rows, hourly cleanup root/continuation ≤60 s. Verify actual deadlines/cancellation/jitter/queue limits and both race orders; defaults do not prove readiness.
- Immediate fixed-TTL denial and 86,400-second post-expiry live-payload purge; age alerts 12/18/24 h, successful-cleanup freshness 75/120 min and recovery 90/180 s. Keep local 90 s warning distinct from Healthchecks' documented 120 s minimum no-ping backstop; bind/test actual destinations without a new uptime/erasure promise.
- Real 100-sample p95 SSE <300 ms and committed status <200 ms; failed operations/replacements and same-host/edge/runner/resource conditions recorded. U3 asset <500 ms remains later. Characterize final snapshot sizes and larger supported translations without truncation or a new product limit.
- Qualified same-server staging/credential isolation and all affected queue persistence transition precede activation. `sbom-targets.json`'s unavailable MinIO/pending image findings require actual qualified artifacts/disposition; a dev-only substitute is not a release pass.
- Additive registered schema/readers and compatible workers/maintenance precede v1 emission/UI; old authority drained/isolated, no invented ledger from legacy absence. Pull deployment uses exact main/check/artifact identities, serial journal and compatible rollback; no unsafe old worker/empty broker/destructive schema reset.
- Independent implementation-plan scrutiny and protected initial Plan Approval precede source changes. Completed-code review/source manifest/traceability and the separately authorized real integrated command precede skeleton checkpoint. The October 14 security review and actual readiness contact remain assigned.

## Complete Coverage and Destructive-Fixture Gate

The final line gate is `ops/server/u1_coverage.py`, consuming the coordinator's immutable pre-write source snapshot, actual source-manifest writes and version-bound report set. New files use all executable lines; modified files use added/changed executable lines relative to those captured bytes, not HEAD. Capture existing dirty files as they are and mark new paths absent, so earlier user work is neither overwritten nor misattributed. Every eligible runtime program path must have current executable/covered-line evidence; an omitted controller, shared pool, assembly, purge bridge, helper or shell write fails. Combine same-version reports by canonical source path and executable-line identity, never by adding percentages. Require covered eligible new/changed lines / eligible new/changed executable lines ≥80%, with per-file omissions visible and no healthy empty denominator.

Collect Python across the full summarization and backend graph in module and root integration lanes, including `api/router.py`, `_pg.py`, ContentJobQueue, real_wiring, backend wiring/config and owner_data_purge; combine their coverage data. Collect exact frontend U1/changed source through the v8 configuration and a canonical line report. Collect changed shell behavior through qualified kcov fixture runs of the three source wrappers without live operations; declarative configuration has explicit execution/negative tests and cannot hide executable program code. The instructions name the collection, owner-purge no-skip runner and aggregate gate. Unsupported collection/attribution is an unresolved quality gap, not an 80% pass.

For `tests/accounts/test_purge_real_postgres.py`, perform a non-destructive read-only connection/marker/current_database/current_user check first, matched to the trusted U1 realm manifest. Only a validated distinct minimal-schema disposable database grants its later DDL/delete connection; the full authority/race schema has a different database identity. Missing SDK/DSN/manifest, wrong marker/role/host/database or skipped required tests fails the scoped U1 runner. Add the fixture adaptation at Step 15 and its no-destructive-call negatives plus full purge bridge proof at Step 16. The baseline's optional skips are not U1 acceptance; do not invoke its destructive setup unguarded.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "team",
  "ordering": "** Test-last per component — Implement component fully, then write its tests.",
  "scope": "feature",
  "test_strategy": "standard",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    },
    {
      "layer": "team",
      "text": "**Methodology:** test-after\n**Ordering:** Test-last per component — Implement component fully, then write its tests.\n\n**Scope floors (feature scope):**\n- 80% line-coverage floor for new code\n- CI execution before merge\n- Existing test suites must remain green (473 backend + 356 frontend)\n\n**Evidence from reverse-engineering:**\n- Current coverage: ~65% overall, but Phase 7 target components at 0% (JobStatus, contentJobApi BFF routing)\n- 356 frontend tests passing (Vitest + React Testing Library)\n- 473 backend tests passing\n- Playwright E2E configured (~25 tests, ~30% coverage)\n- CI runs lint, typecheck, test:coverage, test:e2e\n- **Gap:** Phase 7 components (JobStatus, AssetViewer migration, contentJobApi BFF routing) completely untested\n- **Gap:** No Error Boundary tests, no SSE polling fallback tests, no idempotency key tests\n\n**Affirmed posture for Phase 7:**\n- Maintain test-after methodology (team default)\n- Ordering: Test-last per component (implement fully, then test)\n- 80% coverage floor for new code enforced in CI\n- All existing tests must remain green\n\n---"
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Meet an 80% line-coverage floor.",
      "Run the selected tests in CI before merge."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "test-after",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Data model / database behavior - implement.",
      "Data model / database behavior - write and run its tests after implementation.",
      "Repository / data access - implement.",
      "Repository / data access - write and run its tests after implementation.",
      "Business logic - implement.",
      "Business logic - write and run its tests after implementation.",
      "API / endpoint - implement.",
      "API / endpoint - write and run its tests after implementation.",
      "Frontend behavior - implement.",
      "Frontend behavior - write and run its tests after implementation.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:47a0413847b87a1c376dc0475c75fdb4bb92763764f6800b049333b085452793",
  "contract_sha256": "sha256:f87c0507a83e45b42705d96d9cdb5a9124962ca7bb56c2fd06fd2061fcc42153"
}
```
