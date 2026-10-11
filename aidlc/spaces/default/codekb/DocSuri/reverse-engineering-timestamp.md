# Reverse Engineering Timestamp

## Run Record

- Date: 2026-10-11
- Commit: fa671f7f6cf9b29a72ca2189b73ec03eb31f3da3
- Branch at scan: fix/aidlc-session-propagation
- Intent: docsuri-v2-rebuild
- Mode: Full rescan replacing the prior nine-document store; Standard depth.
- Coverage: repository-wide application breadth, partial deep source analysis (57 explicit paths: 56 files and the one-file BFF directory). Full rescan is not a claim of whole-repository deep coverage.
- Preparation: synthesized in staging before transactional publication. Publication and commit outcomes are recorded by the parent in the intent's publication receipts and audit evidence; this run record does not certify those outcomes.
- Pre-scan source snapshot: tree:124698c6a40fb40a7d02c22629b15fd4dec2a0d64a206d6a72e063887e9589ae over ./.
- Pre-scan store generation: sha256:282ece22311d81519369fd94abd66f8d188c29072cdf9b588c1358eb1c934ab8.
- Deep-path mint: both the requested --repo DocSuri form and documented project-root form returned literal unknown, exit 0. Simple backend/app.py and ./ probes also returned unknown, so bracket syntax is not established as the cause. All listed paths were verified to exist; cause is not established. No handwritten hash substituted.
- Tests: one existing isolated SSE regression executed by the parent failed; a preceding module-local attempt could not collect due to missing FastAPI. No full suite, live browser, service restart, build, deployment or paid call.
- Process: existing approval retained; $0/free-or-local and CONVENTIONS working branch → PR develop → release main remain authoritative.

## Evidence method and limits

Tier 2 graph verification began at generation 2026-10-10T23:42:10Z. The graph advanced during the scan; every cited exact source path and all eight application scopes were rechecked at generation 2026-10-11T00:31:52Z, metadata recorded 2026-10-11T00:37:30Z, generation_matches and hash_records_complete true. Exact paths reported no_recorded_issue/metadata_match except CODEOWNERS freshness not_tracked; CODEOWNERS was read directly. Clean coverage is a best-effort signal, not completeness proof.

Whole application file inventory, narrowed symbol searches and relevant call traces were completed. Broad exploratory searches with more pages were used only to choose narrower queries, not as exhaustive symbol counts. File inventories/coverage scopes used for breadth had no outstanding pages. Graph route inventory was insufficient, so direct AST extraction covered source HTTP decorators/prefixes; source resolved dynamic wiring and rejected heuristic cross-language edges. Critical paper-job producer/consumer and focused test source was read directly. A later supplemental check at generation 2026-10-11T00:40:25Z (metadata 00:41:18Z) covered the corrected AgentChatScreen path, apiClient, novelty adapters, discovery router and BFF directory: no recorded issues, matching metadata for exact paths, no remaining BFF scope entries. The BFF directory contains one authored route file, already deeply read.

Deep paths below are fully inspected boundaries/configuration/tests. The 13 analyzed component names identify those specific deep boundaries, not a claim that every file in those components was deeply read. Accounts and Identity, Evidence and Research Sessions, Novelty and Notion Export, Ingestion and Corpus Control, and Reliability and Operations remain breadth-only component coverage: selected snippets, declarations, manifests or external composition do not promote their internals to analyzed components. Other source under shallow paths received file/module/route/persistence-declaration inventory and selected snippets, not a complete control-flow review. In particular, SQL stored procedures/privileges, remaining provider adapters, UI internals, operational scripts/CDK and the complete test suite remain shallow.

### Recorded parse gaps

These ranges are not promoted to deep coverage. SQL table-name references were verified by direct literal source extraction only; stored-procedure behavior remains unverified. The two frontend test parse gaps were not relied on for behavioral conclusions. Generated DTO bodies remain excluded.

| File | Reported ranges |
|---|---|
| `backend/elasticmq.conf` | 2-7,13-14,20-21,23-23,25-25,27-27,29-29,31-31,32-33 |
| `backend/modules/novelty/migrations/001_create_novelty_tables.sql` | 59-60 |
| `backend/modules/summarization/migrations/002_create_content_jobs.sql` | 81-82 |
| `backend/modules/summarization/migrations/003_content_job_authority_prepared.sql` | 15-16,32-32,34-51,54-54,54-54,54-54,55-56,56-57,57-58,58-58,58-63,64-64,64-65,99-100,118-118,142-142,177-178,178-179,179-179,180-213,221-222,223-224,225-264,273-274,274-275,276-317,326-327,329-330,331-334,335-336,337-338,339-341,342-343,344-377,385-385,386-387,388-389,389-391,403-403,403-420,423-424,425-451 |
| `backend/modules/trends/migrations/002_unique_followed_topic_per_owner.sql` | 9-10 |
| `frontend/test/onboardingGate.test.tsx` | 15-15 |
| `frontend/test/renderMath.test.tsx` | 43-134,149-149,160-160,161-161,162-162,163-164,166-166 |
| `frontend/types/wire/dtos.ts` | 343-343,1171-1171,1747-1747 |
| `ops/local-stack/elasticmq.conf` | 2-7,13-14,20-21,23-23,25-25,27-27,29-29,31-31,32-33 |
| `platform_integrity/migrations/001_control.sql` | 4-4,54-62 |
| `platform_integrity/migrations/002_run_protocol.sql` | 8-14,18-22,30-35,42-48,70-71 |
| `platform_integrity/migrations/003_verification_protocol.sql` | 6-7,29-29,52-52,55-58,61-62,63-79,80-80,85-85,92-93,94-95,96-96,101-103 |
| `platform_integrity/migrations/004_operator_authority.sql` | 12-15,15-15 |
| `platform_integrity/migrations/005_reader_access.sql` | 2-3,5-7,8-8,8-8,9-10,11-11,12-13,18-19,26-28,28-28,28-28,29-30,30-30,30-30,31-71 |
| `platform_integrity/migrations/006_target_effects.sql` | 6-6 |
| `platform_integrity/migrations/007_command_roles.sql` | 10-11,13-15,16-16,16-16,18-19,20-20,21-22,31-31,33-34,42-42,42-44,57-164 |
| `platform_integrity/migrations/008_target_reconciliation.sql` | 12-12,17-17,22-23,27-27,29-32,42-42,46-47,48-49,50-65,66-66,67-68,73-73,74-158 |
| `platform_integrity/migrations/009_operator_role_binding.sql` | 3-4,6-9,10-10,10-10,12-13,14-14,15-16,27-27,32-35,35-35,35-35,37-37,37-38,38-39,39-41,42-42,42-42,42-42,43-44,44-45,45-45,48-53,53-54,54-75,76-79,79-80,80-81,82-82,83-84,87-92,96-99,102-102,106-106,107-110,116-118,124-124,127-129,131-135,137-137,138-138,139-139,142-152,156-159,164-164,169-171,172-173,174-174,175-176 |
| `platform_integrity/migrations/010_control_commands.sql` | 2-3,5-7,8-8,8-8,10-11,12-12,13-17,17-19,19-20,20-20,21-21,22-24,44-44,57-57,60-72,74-74,76-76,76-76,78-84,85-85,86-86,88-88,92-92,96-96,100-100,104-104,105-105,107-112,116-116,119-119,119-119,119-142,142-147,148-148,148-149,149-150,151-152,153-153,155-155,159-164,165-166,167-167,169-169,172-172,173-173,174-174,175-188,189-189,191-191,196-196,196-205,206-206,208-208,214-223,224-224,224-224,229-231,236-236,239-242,244-245,247-247,250-250,250-256,257-257 |
| `platform_integrity/migrations/011_prepared_target.sql` | 6-6,17-18,18-18,19-19,19-19,19-19,24-253 |

### Exclusions

AI-DLC workspace/install/generated contributions (`aidlc/`, `.codex/`, `.claude/`, `.kiro/`, `.cursor/`, `.opencode/`, `.aidlc/`, `.aidlc-rule-details/`, generated .agents/.github contributions and marked root blocks); dependencies/environments; caches; build outputs including .next; generated contract implementation bodies; ignored environment/secret files; databases/user objects and external disks. No excluded content was used to establish application behavior. Runbooks are historical evidence to verify, not live authority.

## Scope of Analysis

```yaml
scope_version: 1
kind: partial
intent: docsuri-v2-rebuild
fingerprint: unknown
analyzed:
  paths:
    - CONVENTIONS.md
    - backend/app.py
    - backend/wiring.py
    - backend/health.py
    - backend/middleware/auth.py
    - backend/middleware/wiring.py
    - backend/modules/library/controller.py
    - backend/modules/citation_graph/controller.py
    - backend/modules/onboarding/controller.py
    - backend/modules/plans/controller.py
    - backend/modules/personalization/controller.py
    - backend/modules/user_docmodel/coordinator.py
    - backend/modules/summarization/src/summarization/api/router.py
    - backend/modules/summarization/src/summarization/service/job_service.py
    - backend/modules/summarization/src/summarization/domain/job.py
    - backend/modules/summarization/src/summarization/real_wiring.py
    - backend/modules/summarization/src/summarization/adapters/content_job_queue.py
    - backend/modules/summarization/tests/test_content_job_api.py
    - backend/modules/summarization/tests/conftest.py
    - frontend/app/bff/
    - frontend/lib/api/contentJobApi.ts
    - frontend/lib/api/contentJobContracts.ts
    - frontend/lib/jobState.ts
    - frontend/test/u1ContentJobApi.test.ts
    - frontend/test/u1JobContracts.test.ts
    - frontend/test/u1PaperJobJourney.test.tsx
    - platform_integrity/src/docsuri_platform_integrity/api/app.py
    - platform_integrity/src/docsuri_platform_integrity/application/evidence.py
    - platform_integrity/src/docsuri_platform_integrity/domain/compatibility.py
    - backend/pyproject.toml
    - backend/modules/discovery/pyproject.toml
    - backend/modules/summarization/pyproject.toml
    - ingestion/pyproject.toml
    - ops/pyproject.toml
    - platform_integrity/pyproject.toml
    - shared/python/pyproject.toml
    - frontend/package.json
    - frontend/tsconfig.json
    - frontend/vitest.config.ts
    - frontend/playwright.config.ts
    - frontend/next.config.mjs
    - .github/workflows/ci.yml
    - .github/workflows/release.yml
    - .github/workflows/codeql.yml
    - .github/workflows/branch-name-check.yml
    - .github/CODEOWNERS
    - .github/PULL_REQUEST_TEMPLATE.md
    - backend/docker-compose.yml
    - ops/local-stack/colima-stack.compose.yaml
    - ops/server/README.md
    - shared/README.md
    - ingestion/README.md
    - ops/README.md
    - pytest.ini
    - backend/modules/discovery/src/discovery/api/router.py
    - backend/modules/trends/controller.py
    - backend/modules/mypage/controller.py
  components:
    - Application Shell and Middleware
    - Frontend and BFF
    - Discovery
    - Library and History
    - Summarization and Content Jobs
    - Citation Graph
    - Personalization
    - Onboarding
    - Trends and Digests
    - My Page and Plans
    - Private Document Coordinator
    - Platform Integrity
    - Shared Contracts and Build Governance
shallow:
  paths:
    - backend/
    - frontend/
    - ingestion/
    - ops/
    - platform_integrity/
    - shared/
    - tests/
```
