# U2 unit test instructions

Unit: `u2-account-personal-controls`. Methodology: test-after per component/layer, as the unchanged Testing Contract in [the plan](code-generation-plan.md) specifies. Active strategy: Standard. Commands below are explicit U2 targets planned for bootstrap in Step 2; their files do not exist yet and no run is claimed. Before the first executable test, implement/verify the corresponding runner/configuration and record exact output.

## Setup and runner readiness

Work from repository root. Use the existing local Python environment and frozen dependencies; record versions and lockfile hashes. Introduce `backend/pytest.u2-account-personal-controls.ini` with explicit U2 testpaths/pythonpath, strict config/markers, finite test timeouts and registered `u2_component`, `u2_database`, `u2_repository`, `u2_integration`, `u2_operations` markers. No broad discovery of historical tests. A missing real store is a failed prerequisite, never a skipped passing suite.

Use dedicated `frontend/vitest.u2-account-controls.config.ts` and `frontend/playwright.u2-account-controls.config.ts` scoped to the U2 directories below. The new local harness validates `/tmp/docsuri-u2-run/environment.json`, run ID/owner/private modes/expiry, loopback ports, source/lock/policy/participant identity and reserved resources. It must not accept the U1 fixed manifest as an alias for U2.

During bootstrap, verify these U2-only collection commands before the first behavior run:

- `backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls/component --collect-only -q`
- `pnpm --dir frontend exec vitest list --config vitest.u2-account-controls.config.ts test/u2-account-personal-controls`

Collection only proves runner/discovery readiness. Record expected files/test IDs; zero tests or unexpected skips are failures. If the pinned runner does not support an invocation, correct and verify the unit-scoped command before its first test step and preserve any required plan-change decision.

## Unit-scoped execution commands

Each named phase invokes only its declared U2 test files. The runner creates no real accounts and never loads ambient service credentials. Setup must precede store/browser phases; stop/restart within a test preserves the same run's state.

| Layer | Exact command after bootstrap | Required behavior |
|---|---|---|
| Components | `backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls/component -q` | Eight groups, at least eight meaningful cases each; actual crypto/library behavior with bounded parameters where relevant. |
| Setup | `python3 scripts/verify_docsuri_u2.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json` | Validate ownership/resources, prepare synthetic realm/keys and deterministic fixture identities; no reuse of a foreign run. |
| Database | `python3 scripts/verify_docsuri_u2.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json` | Only tests/u2_account_personal_controls/database; real owner-role/constraint/transaction/migration checks. |
| Repositories | `python3 scripts/verify_docsuri_u2.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json` | Only tests/u2_account_personal_controls/repository; actual persistence, conflict, paging and read-only recovery. |
| Mounted APIs | `python3 scripts/verify_docsuri_u2.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json` | Only tests/u2_account_personal_controls/integration; real host/owner stores and explicitly labelled provider fixtures. |
| Frontend unit | `pnpm --dir frontend exec vitest run --config vitest.u2-account-controls.config.ts test/u2-account-personal-controls` | Account, personal-control and authority-isolation components; typed transport boundary doubles. |
| Browser | `python3 scripts/verify_docsuri_u2.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json` | Invokes Playwright U2 config and only frontend/e2e/u2-account-personal-controls; actual API/DB, not route mocks replacing behavior. |
| Operations | `python3 scripts/verify_docsuri_u2.py --phase operations --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json` | Only tests/u2_account_personal_controls/operations; finite saturation, restore, race/crash and repair schedules. |
| Coverage | `backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls/component --cov --cov-config=backend/.coveragerc.u2 --cov-report=term-missing -q` | Configuration includes every actual U2 production Python path and excludes tests/generated-only data; combine real-store coverage evidence from their phases before final judgment. |
| Frontend coverage | `pnpm --dir frontend exec vitest run --config vitest.u2-account-controls.config.ts test/u2-account-personal-controls --coverage` | Explicit touched/new U2 production include set, no narrowing to inflate results; retain uncovered behavior. |
| Teardown | `python3 scripts/verify_docsuri_u2.py --phase teardown --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json` | Verify ownership and preserve failed/unknown responsibility evidence first; delete only this synthetic run. |

The cumulative U1/U7/U2 check is a distinct completion obligation defined in the plan, not one of these per-unit commands. Its exact runnable invocation must be presented for the separate recorded approval. Existing U1 commands or these U2-only commands cannot substitute for cumulative verification.

## Planned test files and assertions

| File/group beneath tests/u2_account_personal_controls | Minimum scope |
|---|---|
| component/test_credentials.py | Neutral initiation, valid single proof, expiry, concurrent/replayed proof, lost response, credential replacement/session revocation and bounded admission. |
| component/test_identity.py | Google/ORCID distinct protocols, state/nonce/PKCE binding as applicable, denied callback, collision, replay, uncertain exchange, safe unlink and attributed profile fallback. |
| component/test_mfa.py | Inactive enrollment, one-time material, lost display, invalid/reused factor, atomic recovery-code use, wrong/missing key, approved recovery gate and no admin bypass. |
| component/test_profile_lifecycle.py | Editable field limits, consent future effect, complete manifest, withdrawal vs erase, missing scope, replacement claim, permissible reactivation and restore denial. |
| component/test_library_history.py | Stable paper/query references, duplicate/lost reply, foreign owner, source disposition, no rerun on read, clear cutoff, late old event and newer surviving history. |
| component/test_personalization.py | Defaults preserve onboarding/interests, skip preserves choices, consent/input boundary, stale projection, cold start/manual fallback, reset original receipt, complete scope and restart discovery. |
| component/test_usage_admission.py | Absent assignment read, admin/MFA assignment revision, finite allowance, duplicate identity, original period, unknown outcome, accept-versus-close and terminal-proof-only release. |
| component/test_transport_isolation.py | Limited/full scope, authority-generation clearing, safe return, CSRF/origin, secret redaction/no-store, expired flow, foreign cursor and no mutation replay. |
| database/test_owner_constraints.py; test_authority_admission_races.py; test_migrations_restore.py | Owner role denial, uniqueness/receipt atomicity, deterministic locked race schedules, schema compatibility and current restriction enforcement. |
| repository/test_account_controls.py; test_personal_controls.py; test_usage_controls.py | Actual owner SQL/paging/receipts, fresh reset list/inspect with zero writes, exact revisions and stable settlement. |
| integration/test_account_routes.py; test_personal_routes.py; test_usage_routes.py; test_owner_recovery.py | Mounted typed browser/server interfaces, real persistence and two-owner outcomes; at least 32 total real-store/API cases across database/repository/integration. |
| operations/test_bounded_profile.py; test_recovery_restore.py; test_diagnostics.py | Nine V1–V9 operational/fault scenario families and evidence, including resource reserve/timeout fencing, key custody, restart without reseeding and seeded defect repair. |

Frontend unit files: `frontend/test/u2-account-personal-controls/accountFlows.test.tsx`, `personalControls.test.tsx`, `authorityIsolation.test.tsx`. Browser files: `frontend/e2e/u2-account-personal-controls/accounts.spec.ts`, `personal-controls.spec.ts`, `recovery-isolation.spec.ts`. At least 12 browser journeys span all retained U2 screens/states, desktop/tablet/phone and appearance modes. Add meaningful cases beyond minimum counts wherever the required behavior demands them.

## Fixtures, mocks and safety

Use seeded synthetic accounts A/B and a distinct administrator, synthetic proof/delivery sink, permitted paper references and deterministic fault schedules. Never read real user data or legacy secrets. Fixtures capture immutable command/acceptance/period/manifest identity and can pause workers at named transaction boundaries. A restart test keeps its DB, receipts and run identity; deleting/reseeding those invalidates its recovery evidence.

Mocks are allowed for bounded provider adapters, controllable clocks and injected failures. Persistence/owner races, callback/session binding, mounted HTTP and browser journeys use their real layer. Contract doubles validate the exact current generated schema and cannot return impossible success. Synthetic provider success remains distinct from real permission/delivery evidence.

Force both accounting orders and crashes around each owner commit. Assert no delayed acceptance after terminal close/release, no release after accepted effect, one settlement and original-period accounting. For reset, clear browser state then authenticate as the original owner and discover outstanding/history; list/inspect must cause zero writes/claims/new boundaries. Another owner and stale-generation response must never reveal or modify prior work.

Use PIPE2-04 finite limits. A required capacity/preflight failure stops the run with evidence rather than silently shrinking assertions or skipping safety checks. Preserve failed-case outputs with bounded secret-free diagnostics; redact seeds, codes, tokens, identity/private text and provider callback URLs from screenshots/traces.

## Coverage and evidence

Retain at least 80% line coverage for new production code as additive testing guidance; never reduce existing configured thresholds or exclude difficult owner logic to pass. Unit coverage alone may miss database/browser behavior; combine layer evidence under the same source identity and report gaps. Historical suite counts in memory are not a current pass claim.

Record exact command, exit code, test count, pass/fail/skip reason, source/lock/policy/fixture/manifest hashes, layer and resource/fault evidence. Baseline timings have denominators and min/median/p95/max/sample count; numeric service targets await measured agreement.

Keyboard/screen-reader/reflow/contrast tasks must record what actually ran and its observed result. Do not mark manual accessibility or real provider tests passed from component automation. Required unresolved evidence stays in code-summary.md and blocks the corresponding readiness claim.

## Ordering and completion

Implement each applicable layer, then write/run that layer's tests per Steps 3–12. Do not defer tests to Build and Test. Run affected shared consumers/cumulative regressions separately at their integration boundary. Compare legacy CI failures to exact develop base under CONVENTIONS.md; investigate new regressions. Final independent review occurs after implementation, code-summary, traceability and complete source-manifest exist.

