# U3 unit test instructions

Unit: `u3-paper-corpus-capabilities`. Methodology: test-after per component/layer, as the unchanged Testing Contract in [the plan](code-generation-plan.md) specifies. Active strategy: Standard. Commands below are explicit U3 targets planned for bootstrap in Step 2; their files do not exist yet and no run is claimed. Before the first executable test, implement/verify the corresponding runner/configuration and record exact output.

## Setup and runner readiness

Work from repository root. Use the existing local Python environment and frozen dependencies; record versions and lockfile hashes. Introduce `backend/pytest.u3-paper-corpus.ini` with explicit U3 testpaths/pythonpath, strict config/markers, finite test timeouts and registered `u3_component`, `u3_database`, `u3_repository`, `u3_integration`, `u3_operations` markers. No broad discovery of historical tests. A missing real store is a failed prerequisite, never a skipped passing suite.

Use dedicated `frontend/vitest.u3-corpus.config.ts` and `frontend/playwright.u3-corpus.config.ts` scoped to the U3 directories below. The new local harness validates `/tmp/docsuri-u3-run/environment.json`, run ID/owner/private modes/expiry, loopback ports, source/lock/policy/participant identity and reserved resources. It must not accept the U1/U2 fixed manifests as aliases for U3.

During bootstrap, verify these U3-only collection commands before the first behavior run:

- `backend/.venv/bin/python -m pytest -c backend/pytest.u3-paper-corpus.ini tests/u3_paper_corpus_capabilities/component --collect-only -q`
- `pnpm --dir frontend exec vitest list --config vitest.u3-corpus.config.ts test/u3-paper-corpus-capabilities`

Collection only proves runner/discovery readiness. Record expected files/test IDs; zero tests or unexpected skips are failures. If the pinned runner does not support an invocation, correct and verify the unit-scoped command before its first test step and preserve any required plan-change decision.

## Unit-scoped execution commands

Each named phase invokes only its declared U3 test files. Setup must precede store/browser phases; stop/restart within a test preserves the same run's state.

| Layer | Exact command after bootstrap | Required behavior |
|---|---|---|
| Components | `backend/.venv/bin/python -m pytest -c backend/pytest.u3-paper-corpus.ini tests/u3_paper_corpus_capabilities/component -q` | Eight groups, at least five meaningful cases each; actual parsing/crypto/library behavior with bounded parameters where relevant. |
| Setup | `python3 scripts/verify_docsuri_u3.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u3-run/environment.json` | Validate ownership/resources, prepare synthetic realm/keys and deterministic corpus/search/assistance fixtures; no reuse of a foreign run. |
| Database | `python3 scripts/verify_docsuri_u3.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u3-run/environment.json` | Only tests/u3_paper_corpus_capabilities/database; real owner-role/constraint/transaction/migration checks. |
| Repositories | `python3 scripts/verify_docsuri_u3.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u3-run/environment.json` | Only tests/u3_paper_corpus_capabilities/repository; actual persistence, conflict, paging, claim/fence and read-only recovery. |
| Mounted APIs | `python3 scripts/verify_docsuri_u3.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u3-run/environment.json` | Only tests/u3_paper_corpus_capabilities/integration; real host/owner stores and explicitly labelled provider fixtures. |
| Frontend unit | `pnpm --dir frontend exec vitest run --config vitest.u3-corpus.config.ts test/u3-paper-corpus-capabilities` | Discovery/reading/assistance/glossary surfaces; typed transport boundary doubles. |
| Browser | `python3 scripts/verify_docsuri_u3.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u3-run/environment.json` | Invokes the U3 Playwright config and only frontend/e2e/u3-paper-corpus-capabilities; actual API/DB, not route mocks replacing behavior. |
| Operations | `python3 scripts/verify_docsuri_u3.py --phase operations --profile synthetic-local --environment-file /tmp/docsuri-u3-run/environment.json` | Only tests/u3_paper_corpus_capabilities/operations; partial writes/crash boundaries, incompatibility, provider limits, saturation, restore rehearsal and seeded defect repair. |
| Coverage | `backend/.venv/bin/python -m pytest -c backend/pytest.u3-paper-corpus.ini tests/u3_paper_corpus_capabilities/component --cov --cov-config=backend/.coveragerc.u3 --cov-report=term-missing -q` | Configuration includes every actual U3 production Python path and excludes tests/generated-only data; combine real-store coverage evidence from their phases before final judgment. |
| Frontend coverage | `pnpm --dir frontend exec vitest run --config vitest.u3-corpus.config.ts test/u3-paper-corpus-capabilities --coverage` | Explicit touched/new U3 production include set, no narrowing to inflate results; retain uncovered behavior. |
| Teardown | `python3 scripts/verify_docsuri_u3.py --phase teardown --profile synthetic-local --environment-file /tmp/docsuri-u3-run/environment.json` | Verify ownership and preserve failed/unknown responsibility evidence first; delete only this synthetic run. |

The cumulative U1/U2/U3 check is a distinct completion obligation defined in the plan, not one of these per-unit commands. Its exact runnable invocation must be presented for the separate recorded approval. Existing U1/U2 commands or these U3-only commands cannot substitute for cumulative verification.

## Planned test files and assertions

| File/group beneath tests/u3_paper_corpus_capabilities | Minimum scope |
|---|---|
| component/test_corpus_maintenance.py | Canonical identity/dedup across duplicate/reordered records, eligibility precedence, staged effects/watermark discipline, publication CAS refusal and retry of reconciled stages only. |
| component/test_content_reading.py | Exact-version resolution, sections/figures/anchors, absent/building/unsupported/failed/withdrawn/restricted states, opaque asset handles, no fabricated text and no endless loading. |
| component/test_discovery.py | Vocabulary validation (empty/Unicode/oversized), lexical/semantic modes with disclosed degradation, snapshot-bound pagination, error-vs-empty truthfulness and history-fact emission/fence. |
| component/test_citations.py | Bounded distinct nodes/depth, cycle/duplicate safety, freshness/coverage labels, provider failure preserving saves, save through Library only. |
| component/test_assistance_jobs.py | Reconciled options, durable acceptance binding/idempotency, claim/fence renew/reclaim, completion validation and replacement-worker rejection. |
| component/test_progress_transport.py | Ordered progress sequences, stale/out-of-order rejection, reconnect/poll recovery, terminal-state non-regression, valid frames without escaped-newline defects, Q-01–Q-04 dispositions. |
| component/test_glossary.py | Normalization/validation, virtual-empty initial revision, CAS conflicts preserving committed terms, accepted-revision binding into jobs. |
| component/test_isolation_redaction.py | Guest anonymity, owner A/B boundaries, opaque handles, secret-free receipts/errors and redaction under fault. |
| database/test_corpus_constraints.py; test_publication_cas.py; test_migrations_restore.py | Owner role denial, uniqueness/receipt atomicity, competing publication, deterministic locked race schedules, schema compatibility and restore boundary enforcement. |
| repository/test_corpus_repository.py; test_discovery_repository.py; test_assistance_repository.py | Actual owner SQL/paging/receipts, zero-write reads, claim/fence ordering, snapshot expiry and stable settlement. |
| integration/test_corpus_routes.py; test_discovery_routes.py; test_assistance_routes.py; test_owner_recovery.py | Mounted typed browser/server interfaces, real persistence and two-owner outcomes; at least 32 total real-store/API cases across database/repository/integration. |
| operations/test_bounded_profile.py; test_recovery_restore.py; test_diagnostics.py | Operational/fault scenario families and evidence, including resource reserve/timeout fencing, key/permission failure, restart without reseeding, isolated restore replaying withdrawal boundaries and seeded defect repair. |

Frontend unit files: `frontend/test/u3-paper-corpus-capabilities/discovery.test.tsx`, `reading.test.tsx`, `assistance.test.tsx`, `glossary.test.tsx`. Browser files: `frontend/e2e/u3-paper-corpus-capabilities/search-reading.spec.ts`, `assistance.spec.ts`, `citations-glossary.spec.ts`, `recovery-isolation.spec.ts`. At least 12 browser journeys span all retained U3 surfaces/states, desktop/tablet/phone and appearance modes. Add meaningful cases beyond minimum counts wherever the required behavior demands them.

## Fixtures, mocks and safety

Use seeded synthetic accounts A/B and a distinct corpus-maintenance administrator, permitted fixture papers with recorded source identity/version/checksums, deterministic fault schedules and bounded provider fixtures. Never read real user data or legacy secrets, and never copy fixture content beyond recorded permissions. Fixtures capture immutable acceptance/period/manifest identity and can pause workers at named transaction boundaries. A restart test keeps its DB, receipts and run identity; deleting/reseeding those invalidates its recovery evidence.

Mocks are allowed for bounded provider adapters, controllable clocks and injected failures. Persistence/owner races, claim/fence behavior, mounted HTTP and browser journeys use their real layer. Contract doubles validate the exact current generated schemas and cannot return impossible success. Synthetic provider success remains distinct from real permission/delivery evidence.

Force crash boundaries around each owner commit (acceptance/dispatch, claim/publish, completion/settlement) and both publication orders. Assert no completion or watermark past unverified work, no serving from stale eligibility, one intended effect per accepted command and truthful unknown states. Redact seeds, tokens, provider URLs and private text from screenshots/traces.

## Coverage and evidence

Retain at least 80% line coverage for new production code as additive testing guidance; never reduce existing configured thresholds or exclude difficult owner logic to pass. Unit coverage alone may miss database/browser behavior; combine layer evidence under the same source identity and report gaps. Historical suite counts in memory are not a current pass claim.

Record exact command, exit code, test count, pass/fail/skip reason, source/lock/policy/fixture/manifest hashes, layer and resource/fault evidence. Baseline timings have denominators and min/median/p95/max/sample count; numeric service targets await measured agreement.

Keyboard/screen-reader/reflow/contrast tasks must record what actually ran and its observed result. Do not mark manual accessibility or real provider tests passed from component automation. Required unresolved evidence stays in code-summary.md and blocks the corresponding readiness claim.

## Ordering and completion

Implement each applicable layer, then write/run that layer's tests per Steps 3–12. Do not defer tests to Build and Test. Run affected shared consumers/cumulative regressions separately at their integration boundary. Compare legacy CI failures to the exact develop base under CONVENTIONS.md; investigate new regressions. Final independent review occurs after implementation, code-summary, traceability and the complete source-manifest exist.
