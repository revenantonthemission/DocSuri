# U1 pre-implementation regression baseline

## Source and environment

Captured 2026-10-11 before application changes, on infrastructure documentation head `2068a59a69fa6606dd80a49d844d1fc99cd3cd16`. Parent owns merge/baseline reconciliation against develop. Python 3.13.7, pytest 9.1.0 in backend/.venv; Node v24.14.0; actual pnpm 11.9.0 (manifest declares 9.15.9); Vitest 3.2.6. No existing PostgreSQL service migrations or fixture provisioning performed. This is a bounded regression baseline, not complete readiness or coverage evidence.

## Commands and results

Commands run from repository root except the frontend command, run in frontend/.

| Command | Observed result |
|---|---|
| `backend/.venv/bin/python -m pytest backend/tests/test_app_shell.py backend/tests/test_u1_atomic_admission.py -q -p no:cacheprovider` | Exit 1; 45 passing and 1 failing. `test_fixture_preadmits_every_definition_before_any_ddl` cannot import `tests.u1_integration`. |
| `backend/.venv/bin/python -m pytest tests/accounts tests/library backend/tests/test_db.py backend/tests/test_personalization.py backend/tests/test_onboarding.py backend/tests/test_plans.py backend/tests/test_user_docmodel.py -q -p no:cacheprovider` | Exit 0; 298 passed, 2 skipped, 8.65s. Skips are real PostgreSQL tests without the required DSN. |
| `pnpm exec vitest run --config vitest.config.ts --maxWorkers 2 --minWorkers 1` | Exit 0; 86 files and 494 tests passed, 34.21s. Existing default configuration excludes separate contract-generator/consumer-inventory suites. No browser or coverage claim. |
| `backend/.venv/bin/python -m pytest backend/modules/discovery/tests -q -o addopts='' -p no:cacheprovider` | Exit 0; 124 passed, 3 skipped, 0.68s. |
| `backend/.venv/bin/python -m pytest backend/modules/summarization/tests -q -o addopts='' -p no:cacheprovider --tb=no` | Exit 1; 665 passed, 3 failed, 3 skipped, 31 errors, 2.39s; separate collection found 702 tests. |
| `backend/.venv/bin/python -m pytest ops/tests -q -o addopts='' -p no:cacheprovider --tb=short` | Exit 2 during collection; six missing-import errors using backend environment, 0.47s. Ops-specific closure not yet tested. |

Summarization failures: `test_content_job_api.py::test_events_streams_from_after_seq`, `::test_events_resume_from_last_event_id_header`, and `::test_events_resume_from_last_event_id_query_param`: parsed event states are empty instead of expected states. Thirty-one setup errors under existing u1_integration migration/lifecycle/text-result suites require a U1 realm manifest/receipt and its trusted SHA-256; they were not bypassed. An earlier equivalent run inherited suppressed pytest summaries; the listed rerun obtained explicit denominators.

Ops collection errors: backup_evidence, clock_launch_diagnostic, issue_receipt and preflight_receipts lack `docsuri_platform_integrity`; u1_colima_executor and u1_db_bootstrap lack `server`. This describes the attempted backend environment, not a proven defect in the intended ops environment.

## Remaining evidence

Additional pre-application-change binding baseline: `shared/python/.venv/bin/python -m pytest shared/python/tests -q -p no:cacheprovider` exited 0 with all tests passing; separate `--collect-only -o addopts='' -q -p no:cacheprovider` confirmed 145 collected tests. In frontend/, `pnpm exec vitest run --config vitest.contracts.config.ts --maxWorkers 2 --minWorkers 1` passed 32 tests in two files (883 ms). These supplement the default frontend scope without implying mounted coverage.

No U1 implementation suite exists or passed from these runs. New code must compare the same affected scopes and investigate every new regression. Real role enforcement, persistent-volume recovery, useful real model output, mounted journeys, frontend accessibility, per-file coverage, resource measurements and the separately approved completion command remain outstanding. These baseline commands do not authorize any completion checkpoint.

## Integration reconciliation

Infrastructure PR #43 merged to develop at `2a9a08f66dfb0bc484e270fe2fb26d0ed3503b71`. The implementation branch starts there; maintenance record commit `23344448` follows it. Parent verified `git diff --name-only 2068a59a69fa6606dd80a49d844d1fc99cd3cd16 23344448` contains only the audit shard and maintenance/develop-integration.md. Application, configuration and test bytes therefore match the captured baseline. No historical green count substitutes for these observations.
