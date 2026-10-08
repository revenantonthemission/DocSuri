# U1 Code Generation — Partial Implementation and Blocking Handoff

## Sources

The tool-produced approved plan and Testing Contract `sha256:f87c0507a83e45b42705d96d9cdb5a9124962ca7bb56c2fd06fd2061fcc42153`, `unit-test-instructions.md`, `baseline-results.md`, `reviews/implementation-plan-review-02.md`, the current Unit's functional/NFR/infrastructure designs and their declared inception contracts govern this work. All those design inputs were read; sibling Construction content, builder diary and production/operator credentials were not read.

The invoking coordinator completed Step 1 and provided the immutable pre-write dirty-source snapshot at `../../../.aidlc-engine/u1-source-baseline/4b22034726c38f1118e01079cbc5ec7d65a432f7a61549c837a8e2dc24b28ac9/`. Its manifest binds 395 public files to the approved source. It was not overwritten, recaptured or replaced with HEAD. The preserved migration 002 has 5,753 bytes and SHA-256 `8f47c5582aadff04afe2f4cac0f39ad1e9e8985f411dd809528d9a8571a07f7f`; the schema-source test checks those exact coordinator-captured bytes.

This is **NOT-READY** for Unit completion, review approval, integrated verification, exposure or deployment. Local model tests and a build of the unchanged mock-default application are not an integrated skeleton.

## Produced Paths and Decisions

`source-manifest.json` strictly claims the 29 application/test/configuration/lock/generator paths actually written. It does not claim pre-existing dirty router, ports, worker, wiring, adapter/service, worker-test or wire-comment changes that this implementation did not write.

| Area | Actual implementation | Current boundary |
|---|---|---|
| Python value/codec layer | `domain/job_protocol.py`: detached strict browser input; explicit supported legacy normalization, dropped deprecated abstract; keyed/keyless identity separation; canonical UTF-8 private digest; typed dispatch/binding/effect/claim/progress values | Constructors do not grant authority. No queue/database/generation dependency; actual T1–T8 actor/store still pending |
| Final content and outcome inspection | `domain/prepared_result.py`: allowlisted final summary/bare-DocModel translation, rendered standard glossary retention, immutable captured bytes, unavailable provenance, fixed expiry and purge metadata, safe actual DTO classification | Preserves actual `reproducibility` object; authored C2 string-only schema conflict remains unresolved. No current-settings rendering/cache fallback |
| Existing model compatibility | `domain/job.py`: additive authority/input/prepared fields, additive state/event seq, opaque-cursor documentation correction | Existing constructors/legacy paths retained; no automatic legacy authority backfill |
| Schema source | Registered `003_content_job_authority_prepared.sql`: new binding/prepared/progress records, extended nullable effect authority, indexes, deferred consistency, immutability/owner guards, legacy classification | **Not admitted by the existing atomic migration runner; never applied.** No real SQL syntax/constraint/cascade/concurrency pass claimed |
| Required schema fixtures | `tests/u1_integration/`: separate read-only identity probe before any mutation connection; explicit realm/receipt/digest, workload/network/database/role markers; transaction rollback, no DROP/TRUNCATE/reset; source admission before all DDL | Missing real realm fails. Local mocked connections test only guard behavior. Full retained-purger bridge/races remain Steps 15–16 |
| Frontend runner/configuration | Explicit U1 Vitest/coverage, stricter TS graph, scoped no-any/forbidden-import lint rules, real-origin/proxy-only Playwright config, PostCSS | Existing full project check retained. Stricter imported legacy graph still fails; no errors suppressed and no U3 source changed |
| Dependency/runtime closure | Exact approved frontend candidates and matching v8 provider; pinned Python coverage/pytest-cov; fresh backend/module/Ops locks; backend Python >=3.13 | Installs ran only in temporary isolated environments. No production venv or node_modules reinstall |
| Safe development copy | `frontend/scripts/u1-sandbox.mjs` and tests: new outside-workspace target, byte inventory, no .env/.next/dependency trees/symlink following or existing-target deletion; public fixtures and timeout declaration retained | Credential-free development copy, **not** staging/network/provider qualification |
| Container source | Python 3.13.7, required digest inputs for Python/uv/Lambda adapter, frozen actual path-dependency layout including platform-integrity, no mutable boto3 upgrade; Dockerfile-specific deny-by-default context | No container built/pulled/scanned/qualified; missing digest/qualification must not silently use a tag |

The Dockerfile-specific context file and development-copy helper/self-tests are necessary build/runner support additions, not a new deployment architecture. They are explicitly claimed. The existing root `.dockerignore` was not edited. All remaining runtime/staging helpers in the plan are still pending; these additions do not pretend to supply them.

## Plan Progress

| Steps | Actual status |
|---|---|
| 1 | Completed by the invoking coordinator before application writes; retained |
| 2 | Runner/dependency/configuration source and frozen local installations implemented; exact existing and U1 frontend filters verified; isolated frontend build and ordinary project check pass. Stricter imported graph, residual audit finding and actual image qualification remain open; **not ticked complete** |
| 3–4 | Value/codec/prepared-content implementation and meaningful test-after tests written and run. Local model lane passes at >=80%. C2 summary schema reconciliation is still required before claiming all specified model conformance; **left unticked rather than claiming a specification pass** |
| 5 | Additive SQL and ordered registry entry written; historical SQL preserved. Actual inherited admission fails, so **not complete** |
| 6 | Complete runnable initial schema fixtures authored; execution returned an admission failure and required realm failures, **not skips or an acceptance pass** |
| 7–47 | Not implemented/executed beyond this blocking schema handoff. No later component or Unit substituted for the required ordered schema verification |
| 48 | This partial summary, source manifest and explicit gap traceability written; final-stage documentation obligation not complete |
| 49–50 | Independent completed-code review, protected receipts and separate real checkpoint command/approval remain the invoking orchestrator's responsibilities; none forged or requested here |

The prescribed methodology remained test-after: runner support before model tests; model/content implementation before its tests; migration/fixture implementation before its tests. Failed first test runs were ordinary implementation defects (including a missing Persona import and missing public fixture files in the temporary copy), corrected and rerun, not a manufactured Red/Green cycle. No threshold or required assertion was weakened.

## Tests and Evidence

Commands used clean temporary HOME/environment, `ENV=test`, disabled AWS metadata and no inherited production credential/DSN variables. Python `UV_PROJECT_ENVIRONMENT` was explicitly the temporary backend or Ops environment, never production `.venv`. Frontend installation/build/test ran in the public-source copy under the pre-approved temporary directory. The original serving `.next` was not a build target.

| Command/lane | Actual result | Interpretation |
|---|---|---|
| Initial exact frontend five-file filter | 19 passed | Rechecks current runner before dependency changes |
| Initial backend four-file filter, old and new isolated closure | Same three recorded SSE failures | Literal escaped delimiters remain assigned Step 18; not waived or fixed by models |
| `uv sync --project backend --frozen` with isolated environment and Python 3.13.7 | 68 packages installed, including actual current path/runtime closure | No global or live-venv install; SDK locked at boto3/botocore 1.43.101 |
| `uv sync --project ops --frozen` with its own isolated environment | 23 packages installed | Correct own closure, including platform-integrity |
| Frontend frozen pnpm 9.15.9 installation | Passed in isolated public-source copies | Candidate SWR/Sentry/clsx/Tailwind/coverage/axe pins installed; retained Next 15.5.26/React 19/TS 5.7.3 |
| `pytest tests/test_u1_job_model.py tests/test_job_contract.py` with coverage | **94 passed; 523/584 executable statements, 89.55%** | `job_protocol.py` 258/276 (93%); `prepared_result.py` 192/215 (89%); whole legacy `job.py` 73/93 (78%). This is the explicit model lane, not the final changed-source gate |
| Ruff on new model/codec/prepared and initial integration files | Passed after repairs | No application behavior suppressed |
| `node --test frontend/scripts/u1-sandbox.test.mjs` | 7 passed, zero skips | Copy fidelity, hidden credentials/runtime exclusions, source/parent scope, reuse, symlink and missing-manifest negatives |
| `vitest run --config vitest.u1.config.ts` in corrected copy | 39 passed across 9 files | Exact affected compatibility filter, not the unfiltered full suite accidentally merged into U1 |
| Frontend full existing suite in copy 02 | 355 passed / 1 failure: missing copied public timeout YAML | Copy-support defect, not a product regression; public timeout declaration added to copy support, final refresh recorded below |
| Final full existing frontend suite in corrected copy 03 | **59 files / 356 passed, zero failed/skipped** | Existing baseline count retained after actual frozen dependency/config changes; JSON report saved here |
| `pnpm typecheck` / `pnpm lint:u1` | Passed | Existing project flags and declared current source lint preserved |
| `tsc --project tsconfig.u1.json --noEmit --incremental false` | Failed on exact-optional/indexed-access diagnostics in U1 and imported legacy sources | No flags lowered, facade/stub/suppression substituted or forbidden viewer edited |
| Isolated `pnpm build` in copy 02 | Passed, optimized Next production-mode build | Current default API selection, **not** authenticated real-API staging or journey evidence |
| `pnpm audit --audit-level high` after compatible transitive pins | Still fails: 1 high, 4 moderate, 1 low | Initially 19 findings (14 high); patched brace-expansion/js-yaml where compatible. Residual high has no patched version according to registry advisory; no waiver |
| Final `pytest tests/u1_integration` | **1 failed, 15 passed, 10 errors, zero skips** | Admission failure plus ten missing-realm schema cases; two registry/history-byte checks and thirteen local guard cases pass. Required live-schema lane explicitly fails before destructive work |
| Existing `backend/tests/test_migration_registry.py` | 6 passed | Inherited readonly/admission regressions retained; does not turn the new positive admission failure into a pass |
| Partial-handoff/source validator | 29 manifest writes; all 395 captured bytes verified; 12 existing byte changes, all claimed; 184 trace rows =124 AC+35 detailed NFR+25 BR | No unexplained public-source drift or omitted declared ID; partial paths exist; no Unit completion inferred |
| `git diff --check` | Existing router EOF blank-line finding | Router is pre-existing user work not edited by this execution; not indiscriminately cleaned up |

Evidence artifacts already written here: `u1-model-results.xml`, `u1-model-coverage.json`, `u1-schema-results.xml`, `u1-frontend-regression.json`. Temporary copies have `public-source.json` inventories. These reports do **not** carry a completed version-bound aggregate report set or native completion/review/checkpoint receipt. `ops/server/u1_coverage.py` and the full Python/frontend/shell/SQL attribution gate are not implemented; no overall new-code-floor pass is claimed. Executable PL/pgSQL must not be excluded merely because its file ends in `.sql`.

## Runnable Local Commands

For Python, use the qualified isolated environment created in this execution, not the serving venv. These are scoped implementation checks, not the separately authorized integrated checkpoint. Environment must be sanitized as in the test table; no production credential providers or DSNs are permitted. The full initial real-schema command intentionally fails while B-01/B-02 are open.

Working directory `backend/modules/summarization`, with `UV_PROJECT_ENVIRONMENT=/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-backend-venv`:

```sh
uv run --project ../.. --frozen python -m pytest tests/test_u1_job_model.py tests/test_job_contract.py -q -rs -p no:cacheprovider -o addopts='' --cov=summarization.domain.job --cov=summarization.domain.job_protocol --cov=summarization.domain.prepared_result --cov-report=term-missing --cov-fail-under=80
uv run --project ../.. --frozen python -m pytest tests/u1_integration -q -rs -p no:cacheprovider -o addopts=''
uv run --project ../.. --frozen --no-sync ruff check src/summarization/domain/job_protocol.py src/summarization/domain/prepared_result.py tests/test_u1_job_model.py tests/u1_integration
```

Working directory the **temporary public-source frontend copy**, never the serving `.next` source, after frozen installation:

```sh
corepack pnpm@9.15.9 exec vitest run --config vitest.u1.config.ts
corepack pnpm@9.15.9 typecheck
corepack pnpm@9.15.9 lint:u1
corepack pnpm@9.15.9 exec tsc --project tsconfig.u1.json --noEmit --incremental false
```

The unchanged approved full U1 instructions still name the later files/collectors; their absence is explicitly pending work, not permission to invoke them and label missing paths successful. Set `DOCSURI_U1_SOURCE_BASELINE` to the coordinator's original immutable root when that final aggregate gate exists; do not recapture it.

## Issues and Blockers

### B-01 — Existing Migration Admission Cannot Execute the Planned Authority Schema

The actual positive test `test_registered_authority_script_is_admitted_by_the_actual_migration_runner` raises `backend.migrations.MigrationBlocked: script is not admitted as ATOMIC_STEP`. `backend/migrations/__init__.py:24–36` scans executable SQL for BEGIN/END/EXECUTE (among other unsafe top-level operations) without distinguishing procedural function bodies/trigger syntax. The newly registered authority/owner/immutability migration requires that syntax. This is an executed correctness failure, not an inferred missing privilege.

No guard was relaxed, raw SQL executed around it or existing executor source changed. A safe transactional admission treatment must preserve rejection of top-level transaction escape/external execution and its current-authority guard. The executor is an existing source file outside the captured exact footprint; any necessary source extension requires the coordinator's explicit reconciliation and pre-write baseline capture for that path, without overwriting the original 395-file snapshot. A registered filename alone cannot complete Step 5.

### B-02 — Required Real PostgreSQL Realm and Isolation Proof Are Absent

All ten actual schema/active-owner cases fail at fixture setup with `U1 realm manifest/receipt and its trusted SHA-256 are required`. No real connection, DDL, deletion, broker mutation or old retained destructive purge fixture was invoked. The guards require trusted metadata, qualified Linux workload/egress proof, a distinct disposable authority database and role, matching server/marker identity and a separate minimal-schema purge database. Missing prerequisites are not skipped acceptance.

To execute this scoped lane, the operator must provide `DOCSURI_U1_TEST_REALM_MANIFEST`, `DOCSURI_U1_TEST_REALM_SHA256`, `DOCSURI_U1_ISOLATION_RECEIPT`, `DOCSURI_U1_ISOLATION_RECEIPT_SHA256` and the bounded-role `DOCSURI_U1_AUTHORITY_DSN` through the authorized isolated launcher. Never source production `.env`. These digest bindings validate supplied receipts, not mint or prove them. The selected guest controls/provider boundary still require actual operator qualification before fixture admission.

### B-03 — Authored C2 Summary Shape Conflicts With Actual Returned Content

The authored C2 SummaryContent declares `reproducibility: string`, but the actual `SummaryResultDTO.to_dict()` returns `{code, data}`. Shared SSOT `shared/dtos/summarization.schema.json:94–108,137–150` and the existing viewer use that object. `test_summary_capture_preserves_reproducibility_and_filters_internal_metadata` executes the real DTO serialization and retains the exact object. Flattening would silently change the promised final prepared payload/display semantics; returning it unchanged does not conform to the authored string-only schema. The model can retain both validated shapes pending the compatibility decision, but this is **not** a current C2 conformance claim. The contract owner must reconcile this before exact summary HTTP/result completion.

### B-04 — Stricter Imported Frontend Graph Needs Bounded Resolution

The new exact TS command genuinely checks transitive sources and currently reports optional/indexed-access errors in BFF/transport/parent plus imported legacy ApiClient/agent/math/summary/translation/document-view files. Some U1 errors are assigned the later implementation steps, while broad fixes to U3's viewers are explicitly forbidden. Retain the existing green full project check and reconcile how to qualify the declared stricter U1 boundary without suppressing U1 errors or silently expanding into a legacy refactor. This does not justify a successful strict-type receipt today.

### B-05 — Residual Supply-Chain/Runtime Qualification

Audit still reports high `braces@3.0.3` through retained `eslint-config-next@15.5.26 → @next/eslint-plugin-next → fast-glob → micromatch`, GHSA-vfj7-8cjw-p6xm, with no patched version in the observed advisory. No package/security waiver or unapproved Next replacement was made. Required image digest inputs and image/control/provider/notification evidence are still unavailable/unverified. `sbom-targets.json`'s MinIO UNOBTAINABLE and pending affected image findings remain unchanged. A frozen native install or development-only S3 substitute cannot satisfy them.

## Not Implemented

Atomic RDS/in-memory authority stores and purpose pools; ContentJobService T1–T8/query-only integration; single real dispatcher/legacy bridge; supervised worker/renewal/visibility and independent maintenance; retained-purger adaptation; controller readiness/read/error/SSE fixes; BFF streaming/cookie/cancellation fidelity; C4/browser identity/session integration; submission/status/boundary/fallback/result/parent composition; actual Sentry/monitoring; staging proxy/guest/provider controls and owned bootstrap; runtime/release/rollback helpers; full source/CI/coverage collection; real verification/performance harness, completed-code review and checkpoint.

These remain U1 obligations. They are not transferred to U2/U3, replaced with generic stubs or described as done because types/SQL source exist. U2 translation UI/reload/copy/wider replay and U3 asset migration remain genuinely later-unit responsibilities. All four upstream finding records remain unchanged, as do the October 14 security-review assignment and actual readiness contact.

## Next Action

Return this blocking handoff to the invoking coordinator. Resolve B-01's safe existing migration admission/source-footprint prerequisite and B-03's contract conflict; provide B-02's real isolated realm evidence. Rerun the exact initial schema lane until it passes, then continue the approved implement-then-test sequence at Step 7 while retaining the remaining strict/supply-chain qualification obligations. Do not invoke later Unit routing, production installer/rebuild/restart, native completion/review setters or an unauthorized integrated checkpoint command.
