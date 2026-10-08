# U1 Integrated Job Skeleton Implementation Plan

## Sources and Completion Target

The current confirmed `code-generation-questions.md` Q5 selects Modify and Q6 selects Escaped JSON in TEXT. Its current summary authorizes this planning amendment; implementation requires separate current-attempt exact Plan Approval. Inputs are `../functional-design/functional-spec.md`, `../functional-design/rules.md`, `../functional-design/entities.md`, `../nfr-design/performance-design.md`, `../nfr-design/security-design.md`, `../infrastructure-design/infrastructure-specification.md`, `../../../inception/contract-design/contract-summary.md`, `../../../inception/units-generation/unit-of-work.md` and `../../../inception/requirements-analysis/requirements.md`. The six NFR Requirements documents, all NFR/Infrastructure designs, `../../../inception/units-generation/unit-of-work-story-map.md`, `../../../inception/user-stories/stories.md` and `../../../inception/delivery-planning/bolt-plan.md` retain detailed allocation and quality obligations.

Current owning reviews are `../functional-design/reviews/review-03.md`, `../nfr-requirements/reviews/review-02.md`, `../nfr-design/reviews/review-03.md` and `../infrastructure-design/reviews/review-02.md`. Functional/NFR findings and Infrastructure R-01/R-02 are Resolved in those records. Infrastructure R-03 remains New: the direct JSONB payload cannot represent all valid C2 strings. Contract Design R-03 independently remains Accepted risk for its original missing timestamp checker. Planning the TEXT repair does not resolve either record or certify application/store behavior.

`unit-test-instructions.md` supplies exact U1 commands. `code-summary.md`, `source-manifest.json` and `traceability.json` preserve actual partial work/GAPs; `baseline-results.md` is the historical pre-write baseline, not a fresh run. `recovery-impact.md` and `../../../verification/u1-isolated-postgres-bootstrap-plan.md` pin recovery/operational boundaries. Four original planning/handoff documents are preserved under `../../../archive/2026-10-06T00-01-08Z-u1-code-generation/`, with their exact Git blob hashes verified before amendment.

Deliver actual summarize submission → authenticated BFF/gateway → one authoritative dispatch/worker → native SSE → truthful COMPLETED → exact owner/TTL-checked result, with containment, accessible focus/announcements, original-request recovery and safe diagnostics. Shared backend guarantees apply to summarize and translate. U2 adds wider translation/reload/copy UI; U3 owns assets. U1 engineering completion is not full spanning-story or release completion.

## Preserved Partial Work and Execution Boundary

- Retain the original immutable 395-file/2,983,766-byte dirty-source capture at `../../../.aidlc-engine/u1-source-baseline/4b22034726c38f1118e01079cbc5ec7d65a432f7a61549c837a8e2dc24b28ac9/`. Historical 002 remains 5,753 bytes with SHA-256 `8f47c5582aadff04afe2f4cac0f39ad1e9e8985f411dd809528d9a8571a07f7f`; HEAD is not its baseline. Preserve the source manifest and unrelated user/framework changes; `source-manifest.json` in this directory is the claim authority (40 claims retained and approved under this attempt's Plan Approval — 29 original +9 +2 Q8-A; 69 current after the completion pass's 29 claimed writes).
- Historical local evidence: 94 model tests/89.55% model-lane coverage, 39 scoped frontend tests, seven sandbox tests and final 356 existing frontend tests. Required schema lane returned one admission failure, 15 local passes and ten missing-realm errors, zero skips. The stricter imported TS graph and residual dependency finding remain unresolved. None is current all-source, real-store or skeleton acceptance.
- Keep Next 15.5.26/React 19/TS 5.7.3, Node 24.14.0/pnpm 9.15.9 and frozen compatible closures unless a concrete scoped decision is required. Current package scripts/dependencies and frozen/nonroot Dockerfile are source declarations, not installed/build/image/CI qualifications.
- Reconcile current live source and the exact write footprint before new application writes. Capture supplemental unchanged original executor bytes or new-path absence against the original approved full source listing; never recapture modified bytes or overwrite the original snapshot. A separate immutable supplemental manifest must identify original source, paths/hashes/modes/absence and be consumed by the final coverage collector.
- Local installs/builds/tests use credential-free isolated development copies/environments. No production `.env`, serving `.next`, venv, installer/rebuild/restart, protected credential or shared-broker operation is part of development. Concrete resource/rule application requires its separate operator authorization and measured qualification.

## Lossless Prepared-Content Contract

| Boundary | Planned mechanism | Required proof |
|---|---|---|
| Successful capture | Validate exact required summary code/data object with no extra nested fields; bare DocModel/final translation personalization; allowlisted final payload only | Real synthetic DTO parity, malformed-success safe FAILED, no string fallback, coercion/defaults or dropped extra reproducibility fields |
| Canonical content | New pure `domain/result_storage_codec.py` implements private canonical-json-ascii-v2: detached finite JSON, sorted keys, compact separators and ASCII escaping of string values, preserving arrays and decoded content | Complete C2-domain/property and exact-value fixtures, including U+0000 versus literal backslash-u, empty/decomposed/astral strings, whitespace and escaping |
| Integrity and versions | SHA-256 of the content-specific canonical ASCII bytes; explicit content_encoding/canonical_version metadata and matching preparation identity | No digest over database-coerced content; missing/unknown versions, corrupt JSON, noncanonical bytes or digest mismatch are unavailable; no guessed version adoption |
| Input identity separation | Retain existing server-input canonical policy and browser full owner:paper:task:JSON.stringify UTF-8 hash | Representative non-ASCII input/replay hashes unchanged; do not replace shared canonical_json/content_digest globally |
| Relational representation | Unapplied 003 uses nullable prepared_content TEXT plus fixed internal encoding/version metadata; store canonical JSON characters through bound TEXT parameters | No payload JSON/JSONB cast/function/operator or implicit driver JSON adapter; SQL NULL only for guarded expired-payload purge |
| SQL invariants | Replace representation-specific object/status/task JSONB checks with encoding/text-presence/lifecycle checks; preserve typed job/owner/task/schema/digest/expiry metadata, FKs, legal states, immutable payload/identity and guarded deletion | Application validates full C2/task before binding and on reads; SQL guards remain effective, not removed merely because payload is opaque |
| Preparation/publication | T5 assigns fresh database preparedAt and commits exact immutable binding; T6 separately initializes fixed expiry once, terminal state/event/reference | Current owner/state/fence/fresh time and remaining-authority checks; lost acknowledgement reconciles exact identity, never generation |
| Authorized reads | Owner/state/trusted-known-expiry checks precede encoding/decode/C2/digest validation; public preparedResult v1 returns decoded content | 401/generic404/409/trusted410/422/503/504, changed settings/configuration and before/at/after expiry; zero generation/enqueue/submit/current-settings rendering |

The storage version is private, not a public envelope-version change or a new data service. Unknown legacy/coarse bindings remain controlled unavailable; supported verified compatibility must be explicit and tested. Timestamp validity and actual TTL are separate from string encoding: require active RFC 3339/calendar/offset validation for preparedAt/expiresAt/DocModel generatedAt, missing-checker negatives and real store boundaries. Do not normalize valid values, repair content through generation, renew TTL or expose protected payloads in diagnostics.

## Narrow Migration Admission and Realm Readiness

Implement `backend/migrations/u1_atomic_admission.py` as an explicit reviewed owner/identity/full-script-digest-bound treatment for the final revised 003 only. Its expected digest is an independently reviewed fixed policy input, never simply recomputed from whichever file happens to be registered at startup. Require matching actual registered definition and bytes; unknown/changed scripts retain conservative rejection. `_atomic_sql` may accept verified definition context for this branch, while the default conservative path stays intact.

Integrate definition-aware admission inside the existing `apply_migrations` same-connection authority guard and step transaction without changing inspection/baseline/adoption semantics, canonical lock, byte/digest recheck, ledger or before_commit. Update schema fixtures and admission tests to pass actual verified definitions, pre-admitting every script before DDL; no raw procedural execution around a refusal. Retain top-level transaction/nontransactional/external COPY/program/CALL/DO/role/database/system rejection outside the exact reviewed script.

After actual 003/policy implementation and local negative tests, the coordinator obtains focused independent source/security review of the pair and inherited guarded-commit integration before any procedural SQL execution. The developer yields the actual source/test handoff for that review; it does not review itself or call lifecycle/approval tools. This focused review is separate from the requested pre-implementation plan scrutiny and final completed-code review. No fabricated policy review or digest receipt is allowed.

The database-only bootstrap follows `../../../verification/u1-isolated-postgres-bootstrap-plan.md`: dedicated private cluster, distinct full-authority and later minimal-purge databases/roles, protected operator-owned read-only markers, independent measured isolation and launcher/source/image/rule/identity/digest/validity bindings. Plan complete inspect-by-default `ops/server/u1_db_bootstrap.py` and its tests before Step 6; its real application remains separately authorized. No production/default DSN, guessed purge variable, writable proof or synthetic verified flag grants admission.

Missing focused review, qualified artifact, concrete authorization or actual protected realm proof causes a coordinator handoff before mutation. If required tests are run, missing/wrong/expired prerequisites fail rather than skip. Step 6 proves schema/constraint/owner behavior in forced-rollback fixtures; it does not claim full production migration-ledger execution, adopted baseline, complete store/result API or the later retained purger. Those guarantees need their own current scoped tests. Later store/worker/browser work follows passed required schema acceptance.

## Concrete Staging Enforcement Treatment

| Path/control | Recorded implementation | Qualification |
|---|---|---|
| Workloads/ingress | Internal-only staging frontend/API/worker/data/inference/browser; host cloudflared exposes only protected loopback BFF port 13000 | No host mode, external attachment, production mount/home/credentials/socket; preserve production routes/catch-all |
| Egress helper | Qualified staging-only Squid CONNECT on internal and isolated egress networks; no public proxy port | Exact permitted hostname/443, deny literals/alternate/unlisted/private/production destinations and DNS rebinding |
| TLS identity | Qualified ClientHello peek/splice binds CONNECT hostname to visible SNI without decryption | Missing/mismatched/ECH/concealed/unsupported handshakes denied; client certificate/hostname validation retained |
| Encrypted HTTP authority | Verified provider/account/configuration boundary denies shared-address SNI versus HTTP Host/HTTP2 authority mismatch | Per-host paired negative evidence and validity/refresh; no guessed Cloudflare guarantee; unproved route closed |
| Guest/bypass | Supported DOCKER-USER forwarding and guest host-input rules scoped to measured pre/post-NAT identities; narrow resolver/reply exceptions | Direct egress/host/LAN/link-local/production denial; IPv4/IPv6 enforcement or unsupported-family refusal |
| Clients/reversal | Browser/diagnostics explicit proxy; internal API peers only through approved paths; operator-side reviewed rule application | Real streaming/cancellation/TLS tests, credential/mount/wrong-env/bypass/rebinding probes and identity-scoped rollback |

Actual image/runtime/policy/provider support and host headroom remain qualifications. Database-only bootstrap needs no external helper; integrated staging separately proves this complete route. A configured proxy or private network is not its receipt. Preserve exact main/check/artifact identities, qualified pull delivery, compatible readers/workers before new-message/UI exposure, all-queue safe broker transition and readable prepared records on rollback.

## Backend and Frontend Integration Decisions

- T1–T3: immutable owner/key/job/input binding; one guarded NOT_STARTED→SENDING permission and one real send. Definite non-dispatch may release; SENDING/UNKNOWN retention and 120-second safe settlement cannot resend or restart a terminal job. Eliminate recursive legacy second-send/no-op dispatch.
- T4–T8: durable intent before one invocation, independent publication/visibility renewal, separate exact T5/T6, publication-only reconciliation, legal state/event consistency and existing owner-purge/late-write bridge. Visibility or missing legacy markers never grant generation. Preserve supported keyless/omitted-field normalization and unrelated tasks.
- Job transport uses native fetch/custom Transport through `/bff/api/content-jobs`; GET retry only at BFF, no automatic POST/layered retries. Native EventSource uses real LF frames, authorized opaque cursor/header precedence and separate state/history watermarks. Two-second fallback never overlaps; terminal/context/access changes cancel obsolete work.
- ContentJobApi retains original captured input/order and guarded async publication, C4 handle-before-POST, validated owner/namespace/schema/digest restore and action-time supersession. Actual SessionContext/currentSession identity, not dummy user or client cookie. Temporary network loss retains only clearly stale authorized observations.
- Separate JobSubmissionForm initial choice/pre-job uncertainty from query-only SummaryModal. Parent mounts tracking only for actual current returned identity and retains immutable authorized history/cursor recovery context, not another mutable state owner. Render failures reach stable-parent full-page fallback; network failures stay inline. No generation on result mount/preferences/read retry or tracking reset.
- Preserve existing compatible presentation consumers, semantic themes/reduced motion/sticky fallback, conditional focus, deduplicated live announcements, 200% resize and 320px reflow. U2 owns wider translation/copy/reload UI and U3 owns asset/viewer migration; shared relay changes preserve private asset caching and unrelated consumers.

## Ordered Implementation Steps

Only Step 1 records the completed original capture. All remaining steps require current verification; historical partial implementation is reused and corrected rather than counted complete. Implement each applicable component/layer fully, then author/run its tests. No authored test is deferred to Build and Test.

| Step | Work and completion condition | Story / requirement trace |
|---|---|---|
| [x] Step 1 | Preserve the verified original 395-file pre-write capture/absent-path markers and unchanged 002; retain the claim manifest lineage approved under this attempt (29→38→40; the two Q8-A claims are `ops/server/u1_colima_executor.py` and `ops/tests/test_u1_colima_executor.py`; 69 current after the completion pass's 29 claimed writes) and unrelated user work. This historical capture is not current plan/execution authority. | NFR11; all U1 stories |
| [ ] Step 2 | Reconcile current source/footprint and supplemental original executor/policy/test/early-bootstrap preimages or absence against the original full listing; verify isolated frozen runner/config/closure and actual stricter imported graph without waived findings or live installs. | NFR11.1/12; US1.5/US8.1 |
| [x] Step 3 | Correct/reuse typed models and successful capture for shared code/data object; implement pure content-specific canonical-json-ascii-v2/TEXT codec, explicit version/digest and timestamp validation, keeping server input/browser identity policies separate. | US1.1/US1.3, US2.6/US3.4; BR1–BR3 |
| [x] Step 4 | Author/run model/codec/C2 tests after Step 3: both tasks, NUL versus literal escapes, Unicode/empty values, extra/missing/non-string reproduction, corrupt/unknown/noncanonical/digest cases, timestamp checker/invalid dates and unchanged input identity. | NFR1.4/11.2; Infrastructure R-03 treatment |
| [ ] Step 5 | Revise unapplied registered 003 to TEXT/encoding/lifecycle guards; implement narrow fixed-digest definition-aware admission and fixture integration, preserving inherited guarded apply. Implement complete inspect-by-default database-only bootstrap/launcher configuration and owned reversal support. | US2.6/US3.4; NFR11.4–5; B-01/B-02 |
| [ ] Step 6 | Author/run admission/bootstrap/realm negatives after Step 5; yield actual 003/policy for focused independent review. After qualified artifacts, separate concrete operator authorization and measured protected realm admission, run required real schema/owner/TEXT-column tests with zero skips. No later store work until passed; full purger waits for Steps 15–16. | NFR11.3/11.6; registered-script and realm boundary |
| [ ] Step 7 | Implement atomic real/in-memory stores, bounded purpose pools/deadlines/uncertain commits, parameter-bound TEXT writes/exact decoding, fresh time and progress paging; no payload JSON cast or generative read capability. | US2.6/US3.4; T1–T8 |
| [ ] Step 8 | Author/run repository and real-store tests after Step 7: complete two-task NUL/escape capture-persist-read, corruption/version/digest cases, both claimant/renew/publication/deletion orders and actual expiry/deadline boundaries. | NFR1.2/1.5, NFR11.2–7 |
| [ ] Step 9 | Implement authoritative ContentJobService commands/restricted queries, exact acceptance/claim/prepare/publication/reconciliation/expiry semantics and verified compatibility. | US1.1/US4.2, US2.6/US3.4 |
| [ ] Step 10 | Author/run service tests after Step 9: retained/definite/unknown settlement, legal state/events, TEXT exact-result precedence including malformed/legacy/time fields and zero query side effects. | FR4; C1/C2/C7 |
| [ ] Step 11 | Implement one bounded real queue dispatcher/C6 decoder and legacy adapter delegating to the service; remove recursive/independent second send and untrusted abstract source. | US1.1/US2.6; C6/C8 |
| [ ] Step 12 | Author/run dispatch/compatibility tests after Step 11: early/late ack/reject/receipt, timeout, duplicate claim, supported omitted/keyless callers and invalid/old/unknown-major quarantine. | NFR4.4/11.4 |
| [ ] Step 13 | Implement worker supervisor/grant consumption, isolated enqueue-disabled pipeline child, independent renewals, actual outcome inspection/TEXT preparation and durable terminal acknowledgement. | US2.6/US3.4; C7 |
| [ ] Step 14 | Author/run worker tests after Step 13: both valid result tasks and abstain/unavailable/degraded/pending/malformed/thrown outcomes, slow child/redelivery and all intent/preparation/publication/ack crash windows. | NFR11.2–3/6.2 |
| [ ] Step 15 | Implement independent recovery/cleanup/observer entry points and existing owner-purge/late-write bridge; replace blind sweeper. Adapt retained purge fixture to read-only preflight, distinct minimal-schema realm and mandatory no-skip U1 mode. | US2.6/US3.4; NFR7.4/11.4–5 |
| [ ] Step 16 | Author/run maintenance/full T8 tests after Step 15: both publication/deletion orders, missing/wrong driver/DSN/marker/role/no-destructive-call negatives, all eligibility classes, persisted progress/restored rows, TEXT purge and TTL/deadline/no resurrection. | NFR11.3–7 |
| [ ] Step 17 | Implement actual controller/readiness/assembly and restricted C2 result route, RFC3339 response validation, real LF stream/opaque authorized cursor/seq/terminal204, safe errors and private headers. | US1.5/US2.1/US3.1/US3.4 |
| [ ] Step 18 | Author/run HTTP/controller tests after Step 17, repair three baseline SSE failures and prove C2 decoded TEXT/owner/state/expiry/codec/cursor/401–504 precedence with zero read work. | NFR1/5; C1–C3 |
| [ ] Step 19 | Implement BFF incremental job stream/cancellation, Cookie/separate Set-Cookie/error/redirect/no-store fidelity; preserve GET-only retry and other routes. | US1.5/US2.1; C3/C8 |
| [ ] Step 20 | Author/run BFF/transport tests after Step 19: chunk/header/query/cancellation/header-timeout/204/cookie/error/redirect and asset/evidence/search regressions. | NFR1.1–3/5/12 |
| [x] Step 21 | Implement C4 ContentJobApi/IdempotencyService, approved captured registry/current owner-context guards and typed exact C2/instant validation; no hidden retry layers or storage-wrapper presentation. | US1.3/US1.4/US4.2/US3.4 |
| [x] Step 22 | Author/run API/identity tests after Step 21: full-prefix Unicode digest, A/B/owner hashing races, edited draft, corrupt/quota/missing originals, no restore POST and stale/in-flight/replacement suppression. | NFR4; BR1.3–5 |
| [ ] Step 23 | Integrate actual session identity/epoch and verified-access signals, preserving session consumers and distinguishing transient revalidation from denial. | US1.1/US1.4/US2.5 |
| [ ] Step 24 | Author/run session tests after Step 23 for sign-out/late-refresh/owner/access and transient stale state; retain session/route guards. | NFR1/5.3/12.2 |
| [x] Step 25 | Implement complete initial-selection/pre-job recovery JobSubmissionForm and shared dialog shell, submit only on explicit action and return actual identity. | US1.1/US4.1/US4.2 |
| [x] Step 26 | Author/run submission tests after Step 25: no mount/select POST, actual callback, uncertainty/original/missing/error states, default/level and conditional focus. | FR1/4/6 |
| [x] Step 27 | Implement standalone ErrorBoundary with scrubbed containment and authorized tracking-only reset. | US7.1; NFR6 |
| [x] Step 28 | Author/run boundary tests after Step 27: happy/render-error/reset/context; async failures retain explicit owners. | AC7.1; BR5.3 |
| [x] Step 29 | Implement stable-parent full-page fallback with safe return/tracking reset, focus and deduplicated announcement. | US7.2/US7.3 slice |
| [x] Step 30 | Author/run fallback tests after Step 29: available/missing context, repeated crash, zero submission and usable return/focus. | NFR6.1/6.3/10 |
| [x] Step 31 | Implement JobStatus projection/history/watermark, native stream, nonoverlapping two-second fallback, terminal/context cleanup and honest accessible status. | US2.1/US2.2/US2.4/US2.5 slice |
| [x] Step 32 | Author/run status/reducer tests after Step 31: live/fallback/restored/terminal, poll-ahead/older history, duplicate/malformed/obsolete input and unknown progress/announcements. | NFR5/6/9/10; BR4 |
| [x] Step 33 | Implement query-only completed-result SummaryModal with decoded exact content/recorded metadata, transient reads, safe existing views and dialog focus. | US3.1/US3.3 slices; US3.4 |
| [x] Step 34 | Author/run result tests after Step 33: no command on mount/retry/preferences, all controlled result states, string fidelity/changed settings and conditional focus. | C2/C4; NFR1.5/12.2 |
| [x] Step 35 | Integrate stable owner/paper/actual-job/history parent composition and hide/show/fallback while preserving body/translation/document navigation. | US1.1/US2.1/US3.1/US4.2/US7 slices |
| [x] Step 36 | Author/run parent tests after Step 35: receipt-before-mount, original/replacement/obsolete callbacks, render-only reset/history/focus and current paper regressions. | ADR-013; FR4/7 |
| [x] Step 37 | Implement scrubbed client/server/Sentry latency/lifecycle/authority/maintenance signals and bounded nonrecursive diagnostics; decoded/serialized code/data never logged. | US8.1 slice; NFR7/9 |
| [x] Step 38 | Author/run diagnostic tests after Step 37: actual captured scrubbing including NUL/escape/nested failures, real action/cause/timing semantics and failed sender without UI crash. | NFR7.1–4 |
| [ ] Step 39 | Implement full isolated staging topology/manifests/owned fixtures, qualified persistence and controlled helper/guest/provider policy/preflight, reusing database-only bootstrap boundaries; inspect-only until authorized. | Q1; NFR1/11.6–7 |
| [ ] Step 40 | Author/run staging tests after Step 39: both families/bypass/rebinding/CONNECT-SNI/encrypted-authority/opaque-ECH negatives, wrong env/credential/mount and scoped apply/rollback/provider evidence. | IG-2/IG-5 |
| [ ] Step 41 | Implement environment-aware roles, independent maintenance/observer, immutable qualified pull/journal/exposure/rollback and actual channel bindings. | NFR7.4/11.4–5; CI-3–CI-6 |
| [ ] Step 42 | Author/run runtime/delivery tests after Step 41: valid/config/role/cadence/progress, stale/wrong-SHA/PR/digest inputs, interrupted phases and safe rollback/notification failures. | C8; IG-6–IG-9 |
| [ ] Step 43 | Implement full source/build/CI/coverage collection and baseline-plus-supplement changed-executable-line gate, including executor/policy/codec/bootstrap/controller/pool/assembly/purge/frontend/helper/shell/SQL. | NFR11.1/12 |
| [ ] Step 44 | Author/run collector/CI tests after Step 43: missing/cancelled/wrong-SHA checks, vacuous skips, omitted new sources, wrong baseline/supplement/source/report identity, empty/<80% denominator and unqualified pins/secrets. | CI-1/CI-2; NFR7.1 |
| [ ] Step 45 | Implement real integrated/performance harness with actual auth/BFF/gateway/worker/queue/store/provider, decoded TEXT both-task fixtures and qualified raw100-sample/resource/deadline evidence. | U1 skeleton; NFR9/11 |
| [ ] Step 46 | Author/run harness tests after Step 45: wrong/missing realm/prerequisite failure, no mock-only success, hidden failed samples, command-generating reads or unsafe cleanup. | NFR1/9/11.2–7 |
| [ ] Step 47 | Run completed scoped suites/full-source coverage/lint/strict types/isolated build and required real store/browser/maintenance/queue evidence; refresh affected regression baselines and repair without weaker targets. | All delivered U1 AC/BR/NFR |
| [ ] Step 48 | Record actual files/decisions/results/deviations/current prerequisites and strict actual source manifest/traceability; distinguish planning/reused partial work from current implemented evidence. | NFR11; 124 AC/35 NFR/25 BR |
| [ ] Step 49 | Obtain final independent implemented-code/plan/source review and native current receipts; repair through required flow without forged completion or retrospective risk resolution. | Required final Code Generation review |
| [ ] Step 50 | Propose runnable real integrated invocation for separate human authorization; verify actual current U1 source/journey and obtain human skeleton checkpoint before U2/U3. | Walking skeleton; NFR8/11 |

## Planned Source Footprint and Blast Radius

Actual `source-manifest.json` claims only writes already made. The paths below are planned additions/changes, not new claims or authority to modify unrelated files. Existing user changes and untouched U3 interfaces are preserved; every eventual write, lock/generator/SQL/helper included, must be claimed and measured.

| Planned source area | Change and consumers | Impact / tests |
|---|---|---|
| `backend/modules/summarization/src/summarization/domain/{job.py,job_protocol.py,prepared_result.py,result_storage_codec.py}` | Correct current C2/instant models; new pure content-only ASCII-v2/TEXT codec, separate input identity | High; exact DTO/domain/version/corruption/identity regressions |
| `backend/modules/summarization/migrations/003_content_job_authority_prepared.sql`; `backend/migrations/{__init__.py,registry.py}`; new `backend/migrations/u1_atomic_admission.py`, `backend/tests/test_u1_atomic_admission.py` | Unapplied TEXT schema and exact-definition/digest admission; preserve guarded apply/default/inspection/adoption | High; supplemental preimages/absence, focused pair review and inherited migration tests |
| `backend/modules/summarization/tests/u1_integration/{conftest.py,realm.py,test_migrations.py,test_owner_lifecycle.py,test_realm_preflight.py,test_text_result_schema.py,test_text_result_storage.py}` | Actual definition-aware pre-admission, early rollback-only schema/TEXT and later store/realm tests | High execution; independent protected real realm, no raw bypass or skips |
| `backend/modules/summarization/src/summarization/ports/{ports.py,job_protocol.py}`; `backend/modules/summarization/src/summarization/adapters/{rds_jobs,in_memory_jobs,_pg,settings,content_job_queue,recovery_sweeper,job_dispatch}.py` | Typed command/query stores, TEXT parameter/decoder, bounded purposes/dispatch/compatibility | High; real races/expiry/codec/queue and current consumers |
| `backend/modules/summarization/src/summarization/service/{job_service,job_maintenance,job_diagnostics}.py`; `backend/modules/summarization/src/summarization/{worker,real_wiring,job_maintenance}.py` | T1–T8, truthful outcomes, independent supervisor/maintenance/diagnostics | High; both-task and all crash/order/deadline tests |
| `backend/modules/summarization/src/summarization/api/router.py`; `backend/{wiring.py,config.py}`; `backend/modules/accounts/services/owner_data_purge.py` | Actual ready assembly/owned results/SSE and existing T8 bridge | High; baseline SSE, session/owner/query/purge and other-route regressions |
| `backend/{Dockerfile,Dockerfile.dockerignore,pyproject.toml,uv.lock}`; `backend/modules/summarization/{pyproject.toml,uv.lock}`; `ops/{pyproject.toml,uv.lock}` | Reuse frozen public-context/nonroot sources; qualify actual target closure | Medium/high; isolated build/dependencies/context/pins; no production sync |
| `frontend/lib/api/{contentJobApi,httpTransport,routeHandlerTransport,transport,contentJobContracts}.ts`; `frontend/lib/{idempotencyService,jobState,jobDiagnostics,cn}.ts` | C4/current-context transport/validation without layered retry or duplicate owner | High; API/hash/codec/date/relay/compatibility tests |
| `frontend/app/bff/[...path]/route.ts`; `frontend/components/session/SessionContext.tsx`; `frontend/components/{PaperDetailIsland,JobStatus,SummaryModal,JobSubmissionForm,JobDialog,ErrorBoundary,ErrorBoundaryFallback}.{tsx,module.css}` | Real summarize journey and query-only exact result/focus/containment; proposed scoped styles only where applicable | High; actual-job/history/error/accessibility and preserved paper/session/asset relay |
| `frontend/{package.json,pnpm-lock.yaml,vitest.config.ts,eslint.config.mjs,vitest.u1.config.ts,tsconfig.u1.json,postcss.config.mjs,playwright.u1.config.ts,instrumentation-client.ts,instrumentation.ts,sentry.server.config.ts,next.config.mjs}`; `frontend/app/globals.css`; `frontend/scripts/{u1-sandbox.mjs,u1-sandbox.test.mjs,u1-coverage.mjs}` | Existing scoped strict/coverage/E2E/sandbox setup, instrumentation and complete source collector | Medium/high; no weaker flags/U3 refactor or source-map/client secret |
| `ops/server/{run.sh,install.sh,docsurictl,u1_db_bootstrap.py,u1_runtime.py,u1_release.py,u1_monitoring.py,u1_verify.py,u1_coverage.py}`; `ops/server/u1-staging/`; `ops/tests/test_u1_db_bootstrap.py` | Early complete database-only inspect-by-default launcher and later full staging/role/delivery/measurement boundaries | High shared-host; independent proof/explicit operator application and scoped reversal |
| `ops/server/u1_colima_executor.py`; `ops/tests/test_u1_colima_executor.py` (existing Q8-A claims, Step 5 launcher/admission owner) | Concrete `ColimaExecutor` implementing the protected `bootstrap.OperatorExecutor` port for all 17 plan actions, digest-only CLI, and its 12 negative tests | High shared-host; byte-stable `config.launcher_digest` binds the bootstrap launcher; executed and measured by the ops pytest/coverage command and the final coverage gate below |
| `backend/{docker-compose.yml,elasticmq.conf}`; `.github/workflows/ci.yml`; exact backend/frontend/Ops tests in `unit-test-instructions.md` | All-queue safe transition, actual CI/real journey/full-source measurement | High; qualified artifacts/topology, exact commit/source/reports and no vacuous success |
| `tests/accounts/test_purge_real_postgres.py`; new `test_u1_purge_realm_guard.py`; all exact tests in instructions | Later guarded retained fixture in distinct minimal-schema realm | High destructive boundary; read-only preflight/no-destructive-call and real T8 races |

Concrete inherited and new executor/policy/codec/bootstrap/runtime paths are explicitly listed above; the instructions expand their exact test paths. Necessary shared-import/type repairs must be minimal, declared and claimed; do not silently expand into U3 viewer/product refactors. Unresolved imported graph or source attribution is a qualification gap, not permission for suppression/exclusion.

## Measurement, Coverage and Operational Handoff

Keep H/L15/90s, V/R120/30s, D/Q/J5s, scan30s, dispatch ambiguity120s, T5/T6 remaining authority >15s and first-send pass >16s after discovery≤3s. Recovery/cleanup passes20s/100rows; hourly root cleanup/continuation≤60s; immediate fixed expiry denial and live-payload purge≤86,400s. Keep 12/18/24h payload grades,75/120min cleanup freshness,90/180s recovery and accurate120s external watchdog versus90s local warning. These defaults require loaded real enforcement and notification proof.

Retain real authenticated production-build/same-region/unthrottled Chromium/one-active-job/100 sequential successful samples: strict SSE/status p95<300/<200ms, failures/replacements reported; at least two real-store competing actors/both orders. Include complete encoded TEXT bytes/larger supported translations under actual pool/memory/WAL/deadline pressure. No result cutoff, new capacity/SLA/backup-erasure claim or U3 asset timing completion.

The collector uses original immutable baseline plus reviewed supplemental preimages/absence and actual claims, never HEAD/recaptured changed bytes. Measure every new/changed executable source, including narrow migration executor/policy, content codec, bootstrap, controller/shared pool/wiring/purger/frontend/helper/shell and PL/pgSQL. Combine same-source line evidence, not percentages; omitted/unmeasured files, wrong source/baseline/supplement/report identity, empty denominator or <80% fail. Required live skips cannot be acceptance. Adapt destructive purger only at Steps15–16 with separate validated target.

The original senior-engineering reviews are historical; fresh pre-implementation scrutiny of this plan/instructions precedes current exact Plan Approval. Focused actual SQL/policy source review precedes procedural execution, and final implemented-code review/source/trace/coverage precede separate real-command/skeleton authorization. October14 security review with revenantonthemission and completed-asset follow-up/disposition remain assigned. Pending image/runtime/provider/control/channel/MinIO findings stay visible; no operator exception or live operation is inferred from this plan.

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
