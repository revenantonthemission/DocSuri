# U1 Initial Tranche — Local Verification and Source-Review Handoff

## Authority and Limits

This is developer-produced source/test evidence, not an independent review, operational authorization, isolation receipt, CI receipt or skeleton checkpoint. The dispatch supplied the current protected Plan Approval and unchanged Testing Contract `sha256:f87c0507a83e45b42705d96d9cdb5a9124962ca7bb56c2fd06fd2061fcc42153`. Components were implemented first, then tests authored/run; existing baseline failures were not called TDD Red or waived. No conductor/lifecycle/review/approval command, nested delegation or diary access occurred.

The actual source is restricted to the approved initial Steps2–6 tranche. Steps3–4 are locally complete. Step2 remains partial (stricter imported frontend graph/audit qualifications); Step5 remains unchecked pending focused scrutiny and concrete operator-launcher integration; Step6 is incomplete before independent review and qualified real schema. No Step7+ implementation, production `.env`/venv/`.next`, resource/provisioning/privileged rule, database/procedural SQL, Docker/image/package fetch, shared broker or retained destructive purge was used.

## Exact Source and Supplemental Binding

- Original capture: `../../../.aidlc-engine/u1-source-baseline/4b22034726c38f1118e01079cbc5ec7d65a432f7a61549c837a8e2dc24b28ac9/`; all395 raw files,2,983,766 bytes and read-only captured files reverified before writes and at publication.
- Original manifest SHA-256: `a57fbe1e60374dd48a0e83dae0648d537dbea6d039a1f26116bb3a5bca8d5c92`.
- Original full listing: `../../../.aidlc-engine/source-review/code-generation/workspace-4b22034726c3.tsv`; exact-byte SHA-256 `9b6bcacda2f5e05ec3a573d5aae19fe959e2e2bf86b6ebfd29ac6f75d8a21080` (distinct from the framework's source-binding ID).
- Separate immutable supplement: `../../../.aidlc-engine/u1-source-supplements/2148418e4b2b574cdafcede2b247e727864de99ba56c18a9b1575f3113516aa2/manifest.json`; exact SHA-256 `2148418e4b2b574cdafcede2b247e727864de99ba56c18a9b1575f3113516aa2`. Three original preimages (executor plus two untouched inherited tests), eight absent paths, original-listing modes/digests. Executor preimage100644/`6a4f59b0402d6cd756a0677cb86918f8abf11447a0e1e473541b3d1d35d4c74f`. No original overwrite, HEAD baseline or recaptured changed bytes.
- Original002 remains5753 bytes/SHA-256 `8f47c5582aadff04afe2f4cac0f39ad1e9e8985f411dd809528d9a8571a07f7f`.
- Actual003 candidate remains25701 bytes/SHA-256 `918ed4ab3c54535c1802a157bb6efb9c9b3b4021ef98603431d5e3e49f923f95`, pinned literally by the admission policy; this is a candidate review input, NOT a reviewed receipt.
- `source-manifest.json`: original29 retained plus nine new actual claim paths =38; no speculative or untouched inherited-test claim. `traceability.json`:184 rows, unchanged GAP/Deferred allocation.
- Final publication checks: all277 files in the retained frontend public-copy inventory match both current workspace public-source bytes and copied bytes. The frozen package/lock are unchanged. No captured baseline-byte change is unclaimed. `tranche-source-evidence-02.json` records current claim/report hashes; the first snapshot/reports remain historical after the final narrow executor negative/import grouping correction.

The supplement and these observations still require independent review and the final collector's original-baseline-plus-supplement binding. They do not implement Step43 or supply full changed-executable-source coverage.

## Isolated Runner

Existing isolated environments were reused, with no sync/install/fetch. Backend and own Ops both ran Python3.13.7, pytest9.1.1, pytest-cov7.0.0 and coverage7.10.7. Backend also observed Pydantic2.13.5, psycopg3.3.6 and Hypothesis6.168.1. Ops' actual `docsuri_platform_integrity` path dependency imported from this workspace. The frontend copy observed Node24.14.0, Next15.5.26, React19.0.0, TypeScript5.7.3, Vitest/coverage-v83.2.6 and cached corepack pnpm9.15.9.

For every Python command below, the exact clean environment prefix was:

```bash
env -i PATH="/Users/revenantonthemission/.local/bin:/opt/homebrew/bin:/usr/bin:/bin" HOME="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-home" ENV=test AWS_EC2_METADATA_DISABLED=true PYTHONDONTWRITEBYTECODE=1 UV_OFFLINE=true UV_CACHE_DIR="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/uv-cache" UV_PROJECT_ENVIRONMENT="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-backend-venv"
```

Ops substituted only its own `UV_PROJECT_ENVIRONMENT=/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-ops-venv`. Coverage files and Hypothesis storage were directed to the already verified temporary `u1-tranche-evidence/` directory. Pytest used `-p no:cacheprovider`. No credential/DSN/service/options/passfile environment was inherited. These controls establish local development isolation, not qualified guest/network isolation.

## Actual Commands and Results

### Runner/Baseline Before New Tests

Working directory `backend/modules/summarization`:

```bash
uv run --project ../.. --frozen --no-sync python -m pytest tests/test_u1_job_model.py tests/test_job_contract.py -q -rs -p no:cacheprovider
uv run --project ../.. --frozen --no-sync python -m pytest tests/test_job_contract.py tests/test_rds_job_store.py tests/test_content_job_api.py tests/test_summary_worker.py -q -rs -p no:cacheprovider --junitxml="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-evidence/before-backend.xml"
```

First:94 passed. Second:93 cases,90 passed/three existing SSE failures/zero errors/skips, exit1. These are before-write observations; the preserved older full-suite `baseline-results.md` was not replaced.

### Model/C2/Codec/Instant Component

Working directory `backend/modules/summarization`, after implementing the model/codec layer:

```bash
uv run --project ../.. --frozen --no-sync python -m pytest tests/test_u1_job_model.py tests/test_u1_result_storage_codec.py tests/test_u1_result_timestamps.py tests/test_job_contract.py -q -rs -p no:cacheprovider --junitxml="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-evidence/model-results.xml" --cov=summarization.domain.job --cov=summarization.domain.job_protocol --cov=summarization.domain.prepared_result --cov=summarization.domain.result_storage_codec --cov-report=term-missing --cov-report=json:"/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-evidence/model-coverage.json"
```

Initial179 passed/zero failures/errors/skips, exit0. The final combined run below contains180 model/contract cases after adding actual translation DTO/final-assembler parity. Both tasks preserve C2 strings, NUL versus literal escape, empty/decomposed/astral/unpaired-surrogate fixtures, final translation metadata and rendered personalization.120 Hypothesis examples validate exact code/data detachment/identity. Malformed successful capture fails safely; corrupt/noncanonical/unknown-version/digest/preparation-identity records are unavailable. RFC3339 calendar/time/offset/valid UTC/fraction/known leap-second strings and deliberately absent/nonchecking checker negatives pass. This is local domain evidence, not actual store timestamps/TTL/owner query acceptance.

### Admission/Inherited Executor Component

Working directory `backend/modules/summarization`:

```bash
uv run --project ../.. --frozen --no-sync python -m pytest ../../tests/test_u1_atomic_admission.py ../../tests/test_migration_registry.py -q -rs -p no:cacheprovider --junitxml="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-evidence/admission-results.xml" --cov=backend.migrations --cov-report=term-missing --cov-report=json:"/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-evidence/admission-coverage.json"
```

35 passed,zero failures/errors/skips, exit0. Local fake connections record Python call order; they do not interpret or execute SQL. Final negatives additionally ensure a changed reserved003 cannot evade the literal pin by replacing its body with nonprocedural SQL. Default context-free benign behavior, original procedural/external refusals, deny-only privileged-operation cases, actual registry/path/owner/digest/bytes, same-connection authority/transaction/ledger/before_commit, revoked authority, canonical lock, byte drift and marker/baseline/adoption refusal are retained. Fixture admission for all four registered scripts precedes first DDL; a refusal performs zero fake DDL calls.

### Final Combined Backend Local Run

Working directory `backend/modules/summarization`:

```bash
uv run --project ../.. --frozen --no-sync python -m pytest tests/test_u1_job_model.py tests/test_u1_result_storage_codec.py tests/test_u1_result_timestamps.py tests/test_job_contract.py ../../tests/test_u1_atomic_admission.py ../../tests/test_migration_registry.py tests/u1_integration/test_realm_preflight.py tests/u1_integration/test_migrations.py::test_registered_additive_authority_script_follows_unchanged_002 tests/u1_integration/test_migrations.py::test_historical_002_retains_the_coordinators_prewrite_bytes_not_head tests/u1_integration/test_migrations.py::test_registered_authority_script_is_admitted_by_the_actual_migration_runner tests/u1_integration/test_text_result_schema.py::test_local_registered_payload_column_is_opaque_text_with_no_json_payload_operations tests/u1_integration/test_text_result_schema.py::test_local_full_schema_preadmission_retains_owner_immutable_and_lifecycle_guards -q -rs -p no:cacheprovider --junitxml="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-evidence/tranche-backend-02-results.xml" --cov=summarization.domain.job --cov=summarization.domain.job_protocol --cov=summarization.domain.prepared_result --cov=summarization.domain.result_storage_codec --cov=backend.migrations --cov=tests.u1_integration.realm --cov=tests.u1_integration.conftest --cov-report=term-missing --cov-report=json:"/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-evidence/tranche-backend-02-coverage.json"
```

250 passed,zero failures/errors/skips, exit0. Coverage944/1119 statements =84.36%; model subset651/714 =91.18%; codec41/43 =95.35%; admission policy13/15 =86.67%. Inherited executor94/126 =74.60%, realm126/160 =78.75%, conftest20/35 =57.14%; untouched migration CLI is0/22. Deliberately uninvoked live branches are NOT hidden. These percentages are line evidence for this local collection, not the complete changed-source/SQL ≥80% acceptance gate.

The35 guard/source cases use explicit mocks/synthetic documents only: constructed realms/workload-owned proof do not grant admission; source/rule/launcher/marker and role/connection/privilege mismatch, absent/expired/changed proof, inherited DSN indirection and pre-admission refusals fail before mutation. The real schema/owner/TEXT fixtures exist but were NOT invoked. Selecting only local tests respects the required pre-execution review boundary; it is not a required-live skip/pass.

### Early Bootstrap Component

Working directory `ops`, using its own frozen/no-sync environment:

```bash
uv run --frozen --no-sync python -m pytest tests/test_u1_db_bootstrap.py -q -rs -p no:cacheprovider --junitxml="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-evidence/tranche-bootstrap-02-results.xml" --cov=server.u1_db_bootstrap --cov-report=term-missing --cov-report=json:"/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-evidence/tranche-bootstrap-02-coverage.json"
uv run --frozen --no-sync ruff check --no-cache --config pyproject.toml server/u1_db_bootstrap.py tests/test_u1_db_bootstrap.py
```

35 passed,zero failures/errors/skips, exit0;234/259 statements =90.35%; owning Ops lint passes. Initial34-pass/one-failure Boolean-version coercion was repaired; its actual failure XML is retained. An Ops-owned import grouping correction was followed by this rerun, not a weakened lint rule. Configuration/inspect/reversal/action sequencing is complete; concrete privileged effects depend explicitly on a separately qualified operator executor. No Docker/guest/SQL executor was provided or run. Synthetic admission objects are test fixtures, never written as real receipts. The CLI exposes inspect only and reports no application/realm admission.

### Backend/Module Lint

Workspace root, isolated backend environment:

```bash
uv run --project backend --frozen --no-sync ruff check --no-cache --config backend/pyproject.toml backend/migrations/__init__.py backend/migrations/u1_atomic_admission.py backend/tests/test_u1_atomic_admission.py backend/modules/summarization/src/summarization/domain/job_protocol.py backend/modules/summarization/src/summarization/domain/prepared_result.py backend/modules/summarization/src/summarization/domain/result_storage_codec.py backend/modules/summarization/tests/test_u1_result_storage_codec.py backend/modules/summarization/tests/test_u1_result_timestamps.py backend/modules/summarization/tests/u1_integration/conftest.py backend/modules/summarization/tests/u1_integration/realm.py backend/modules/summarization/tests/u1_integration/test_migrations.py backend/modules/summarization/tests/u1_integration/test_realm_preflight.py backend/modules/summarization/tests/u1_integration/test_text_result_schema.py
git diff --check -- "backend/migrations/__init__.py"
```

Both exit0.13 backend/module Python files plus the two Ops-owned files above cover every Python file changed in this tranche. No weaker flags, ignored import graph or suppression was added. The Python3.11-compatible implicit JSON type alias preserves the standalone module's declared lower interpreter bound; no PEP695-only syntax was introduced.

### Frontend Relevant Baseline and Stricter Graph

Working directory `/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-frontend-dev-03/frontend`; exact environment prefix:

```bash
env -i PATH="/Users/revenantonthemission/.nvm/versions/node/v24.14.0/bin:/opt/homebrew/bin:/usr/bin:/bin" HOME="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/u1-tranche-home" COREPACK_HOME="/var/folders/59/1zr18zjd30n_w8nnxdq2r_qm0000gn/T/opencode/corepack-u1" COREPACK_ENABLE_NETWORK=0 ENV=test AWS_EC2_METADATA_DISABLED=true
```

```bash
corepack pnpm@9.15.9 exec vitest run test/summaryModal.test.tsx test/paperDetailBody.test.tsx test/paperDetailSource.test.tsx test/bffRoute.test.ts test/httpTransportPayloadHash.test.ts
corepack pnpm@9.15.9 exec tsc --project tsconfig.u1.json --noEmit --incremental false
```

Vitest:19 passed/5 files,zero failures/skips, exit0. TypeScript:exit2, unresolved exactOptionalPropertyTypes/noUncheckedIndexedAccess errors across BFF/transports and imported document/summary/translation/API/agent/math/mock consumers. These are actual current-source copy errors; all277 public inventory files match. No frontend source, flags, exclusions or U3 product code was changed. No new audit/build/browser/installation occurred; historical residual dependency findings remain unqualified, not cleared.

### Backend Compatibility After Changes

The exact earlier four-file command was rerun with JUnit output `after-backend-regression.xml`:90 passed/three failed/zero skipped, exit1, exactly the same failures as before:

- `test_events_streams_from_after_seq`
- `test_events_resume_from_last_event_id_header`
- `test_events_resume_from_last_event_id_query_param`

These framing defects remain assigned to Step18. No failure was suppressed, assertion weakened or later-step router work started. Broader historical473/356/backend/root/Ops suite counts remain historical until the planned final regression stages.

## Coordinator Handoff — Required Before Procedural Execution

1. Obtain focused independent source/security review of actual003 + literal policy + inherited guarded executor, actual supplement/footprint and tests. Review must include unchanged inspection/baseline/adoption semantics, pre-admission and the reserved-candidate fallback negative. Developer source checks are not that review.
2. Qualify actual PostgreSQL/runtime/launcher and concrete operator executor, exact resources/headroom/rules/credential channel and owned reversal; obtain separate concrete operator authorization. PostgreSQL High CVE-2026-85091/other-image findings and MinIO UNOBTAINABLE stay visible; no risk exception or substitute was selected.
3. Independently measure the private guest/network, source/image/rule/launcher identity, allowed database and denied external/host/LAN/production/unsupported-family paths, role/marker-write/cross-database behavior. Supply protected operator-owned read-only manifest/receipt/digests and validity through a channel the workload cannot replace. No self-authored verified flags qualify a realm.
4. Only then run the approved required rollback-only schema/owner/TEXT command with zero skips. It is NOT production migration-ledger/adoption, full purger, store/API/worker/browser acceptance. No Step7+ work until that schema acceptance passes.
5. Retain later Steps15–16 distinct minimal-purge admission/adaptation, complete changed-source coverage, final implemented-code review, October14 security disposition and separately authorized real integrated command/human skeleton checkpoint. No Unit/stage/release/skeleton completion is claimed here.
