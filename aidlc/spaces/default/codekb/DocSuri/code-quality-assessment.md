# DocSuri Code Quality Assessment

## Assessment basis

Standard-depth source scan with Tier 2 graph verification and bounded direct-source fallback. This is not a full security audit, runtime certification or complete test baseline. Findings below separate executed evidence from source inference. Exact deep/shallow scope is in [coverage](reverse-engineering-timestamp.md).

## Priority findings

### Q-01 — Mounted content-job state violates the browser contract

**Source-confirmed boundary mismatch; not a live-browser reproduction.** `backend/wiring.py:495` mounts `summarization.api.router.build_router` with the constructed job service. In `backend/modules/summarization/src/summarization/api/router.py:106–111`, state is serialized as jobId/state plus optional error/resultRef, without seq. `frontend/lib/api/contentJobContracts.ts:143–148` rejects a state without a nonnegative integer seq; `frontend/lib/api/contentJobApi.ts:90` uses that parser. Poll fallback therefore cannot accept the mounted response.

An alternative domain serializer exists at `backend/modules/summarization/src/summarization/domain/job.py:217` and includes seq, but the mounted handler does not call it. Do not mistake the helper for a second functioning HTTP route.

**Test boundary:** `backend/modules/summarization/tests/test_content_job_api.py:193–217` asserts state/error/resultRef without requiring seq. `frontend/test/u1JobContracts.test.ts:28–33` explicitly rejects missing seq; `u1ContentJobApi.test.ts:98` supplies a valid mocked seq. These focused tests describe separate shapes; they do not verify the mounted producer against the real browser parser. No tests for this finding were run in the scan.

**Closure evidence:** one mounted-app state response accepted by the browser contract, including initial seq, later progress, replay and terminal behavior.

### Q-02 — Mounted result route does not supply the prepared result required by the UI

**Source-confirmed mismatch.** Router `api/router.py:175–193` calls `ContentJobService.result_ref` and returns only `{resultRef}`. Service `service/job_service.py:269–282` returns no result for unfinished/expired jobs; handler maps both to 404. Browser `frontend/lib/api/contentJobContracts.ts:310–318` requires a preparedResult object with identity/task/timestamps/content. `contentJobApi.ts:120–134` distinguishes 409 not-ready, 410 expired and 422 unavailable, then parses the full envelope.

`domain/prepared_result.py:317–339` can build the newer envelope, but this domain method is not called by the mounted result route. The source route inventory found one mounted content-job result declaration, not a replacement handler.

**Test boundary:** backend `test_content_job_api.py:309–355` asserts resultRef and 404 for unfinished/expired cases. Frontend `u1PaperJobJourney.test.tsx:60–86,107–143` mocks a complete preparedResult, fake fetch and EventSource, so its “journey” cannot detect the server disagreement. No test for this mismatch was executed.

**Closure evidence:** query-only result retrieval from the actual mounted producer, ownership and exact job identity, prepared summary/translation content, expiry/not-ready/unavailable semantics, and no regeneration on read.

### Q-03 — Mounted durable submit accepts work without connecting queue dispatch

**Source-confirmed composition gap.** `backend/wiring.py:477–481` constructs ContentJobService with `enqueue=lambda job: None`; `service/job_service.py:128–167` invokes the callback and advances to ACCEPTED when it does not throw. Inspected real wiring passes the same service into a ContentJobQueue adapter but does not replace this callback. Direct browser POST /api/content-jobs/submit therefore has no queue dispatch in this composition.

**Distinct path:** `adapters/content_job_queue.py` is an orchestrator adapter: it calls the job service and then sends a queue message. Its existence serves the synchronous orchestrator's long-work path; it does not intercept the mounted submit handler. The adapter also deserves separate idempotency/dispatch-failure review because it tests accepted state after submission before sending. This scan does not claim observed duplicate or lost work.

**Test boundary:** `test_content_job_api.py:74–77` deliberately uses the same no-op callback; `:127–135` asserts the acceptance receipt, not a mounted queue effect. Domain/service tests with injected queues do not establish app composition. No dispatch test was executed.

**Closure evidence:** an isolated mounted submit produces exactly the intended durable dispatch/effect, an idempotent retry preserves identity without duplicate work, and queue failure/restart has a recoverable state.

### Q-04 — SSE framing uses literal backslash-n; an existing isolated regression fails

**Executed local regression failure.** Mounted router `api/router.py:156` yields a string containing literal `\\n` separators rather than newline characters. `test_content_job_api.py:80–102` splits actual newline-delimited SSE; `:236–248` expects ACCEPTED, QUEUED, RUNNING, COMPLETED and received no parsed events.

The parent ran, from `backend/modules/summarization`:

```sh
PYTHONPATH=src:../../../shared/python/src:../../.. ../../.venv/bin/python -m pytest tests/test_content_job_api.py::test_events_streams_from_after_seq -q
```

Result: exit 1, the assertion at line 248 compared an empty list to the four expected states. One test, no skip, in-memory job store/fake requests, no external services. The earlier module-local interpreter attempt exited 4 at collection because FastAPI was missing. These are different outcomes, not two behavioral failures. [Saved test evidence](../../intents/261010-docsuri-v2-rebuild/verification/reverse-engineering-test-evidence.md).

**Test boundary:** this focused server test already detects malformed frames when executed with required dependencies. Browser EventSource tests inject parsed messages, so they cannot establish wire framing. No live browser, reconnect or complete suite was run.

**Closure evidence:** rerun this existing regression and existing resume tests after correction, then verify real BFF/browser-compatible frame boundaries and durable cursor recovery.

### Q-05 — Module presence and readiness can overstate capability availability

`backend/wiring.py:108–127` catches missing imports and other mount exceptions and continues. `backend/health.py:30` reports readiness against a required subset; onboarding, trends, plans and evidence are not in that required set. Configured mounts can also contain memory/mock adapters. Readiness therefore does not prove full capability parity, dependency health or a completed paper journey.

**Impact:** partial startup may look superficially healthy while a retained feature is missing. **Closure:** define critical capabilities/dependencies and exercise mounted routes under missing-dependency/configuration cases; preserve intentional optional/degraded behavior. This is a source assessment, not a reported production outage.

### Q-06 — Authority, deployment and recovery evidence is unresolved

The backend compose and server runbook describe a local serving stack; the separate Colima compose explicitly describes a development stack with different objects/credentials; AWS/CDK material remains. Source does not identify authoritative user data, current queue/store/model endpoints or restore-tested backups. The newer local stack even documents an unwired stand-in object credential path; that comment is an investigation lead, not a fresh runtime result.

**Impact:** migration/cleanup/stack replacement could preserve source while losing essential state or capabilities. **Closure:** read-only deployment and data inventory, owner-approved continuity policy, restore exercise, measured free/local capacity and provider/license review. No data was read or altered here.

### Q-07 — Test/environment and documentation drift reduce reproducibility

The isolated summary module environment lacked FastAPI; module dev dependencies do not declare pytest-asyncio although the focused test uses its marker. The backend environment could execute the test. Root pytest configuration scopes accounts/library, while other packages have separate lanes. Existing test counts and past “green” prose are not a whole-repository baseline.

`shared/README.md` still references aidlc-docs paths and deferred TypeScript generation despite current consumer tooling; CODEOWNERS retains historical three-track assignments. Release workflow prose mentions deployment while its actual deploy job was removed. These are repairability/documentation mismatches; they do not supersede the approved one-human plan or CONVENTIONS Git flow.

### Q-08 — Responsibility concentrations and multiple contract layers warrant bounded simplification

Large wiring/controllers/adapters and handwritten job serializers coexist with shared schemas/generated types. Q-01/Q-02 demonstrate a concrete cost of that separation. Source line counts in [code structure](code-structure.md) are navigation indicators, not measured complexity or proof of unused code. Preserve behavior with boundary checks before reorganizing.

## Strengths observed in source

Owner-scoped repositories/private identities, shared schema tooling, explicit abstention/degraded states, idempotency and event sequence concepts, bounded provider calls, query-only result intent, and preview/approval export gates are valuable existing design constraints. Their presence is not proof every adapter or runtime configuration enforces them correctly.

## Test and CI inventory

| Surface | Existing mechanism inspected / inventoried | Limit |
|---|---|---|
| Python packages | pytest, Hypothesis, coverage; separate backend/discovery/summary/ingestion/ops/shared/platform suites | no aggregate test count or full passing baseline established |
| Frontend | Vitest/jsdom, testing-library, contract/consumer checks; Playwright mobile mock-mode E2E | fake transports do not prove a mounted real backend contract |
| Real persistence | isolated PostgreSQL lane and zero-skip guard in CI; local-store integration tests | configured jobs were not executed here |
| Property/security | nightly higher-example PBT, pip-audit, pnpm audit, Gitleaks and CodeQL | no current vulnerability or recent pipeline outcome queried |
| Lint/build | Ruff scopes, TypeScript strict, ESLint/Next build/schema generation checks | package exclusions and optional dependencies matter |
| Performance | load-test script and reliability evaluation tooling | no task success, responsiveness, recovery or repair-time baseline measured |

`frontend/vitest.config.ts` does not itself establish a universal coverage threshold; unit-specific configurations and CI scopes must be read before claiming one. The CI closure audit has pending-package handling, so audit job existence does not prove the entire dependency closure passed.

## Recommendations for the approved next stages

Carry Q-01–Q-04 as explicit journey risks into requirements and acceptance design. Establish authoritative environment/data and full capability inventory closure before migration/hosting choices. Measure actual task completion, responsiveness, interruption recovery and defect reproduction/repair, then agree numeric targets. Do not interpret this assessment as selecting a stack, reducing parity or authorizing spending. Git remains working branch → PR into develop → release promotion to main.
