# Integration test instructions

The active test strategy is Standard, so this file covers the key boundaries and the interaction between Units. U8 composes every Unit (U1 to U8) into one application on one database chain. Its integration layer and its complete verification are therefore where the Units meet. The earlier Units' lanes run again because U8 changed shared and owner files they measure (U8 plan, Step 44).

## Sources

- U8: `construction/u8-service-operations-integration/code-generation/unit-test-instructions.md` (Per layer, U2's tests on the composed chain, U2's coverage phase, U7's lane, the complete verification, Environments), `code-generation-plan.md` (Step 44, "Completion and evidence boundaries") and `code-summary.md`.
- U5: `construction/u5-topics-digests/code-generation/unit-test-instructions.md` (Exact unit-scoped commands, Browser and backend isolation), with its `code-generation-plan.md` and `code-summary.md`.
- U6: `construction/u6-approved-export/code-generation/unit-test-instructions.md` (Commands, Browser journeys), with its `code-generation-plan.md` and `code-summary.md`.
- The journey map in `scripts/u8_phases.py` (`J01` to `J14`, `A11Y`, `SEC`).

## Framework setup and configuration

- **Backend:** pytest in `backend/.venv`, one configuration per Unit (`backend/pytest.u8-service-operations-integration.ini`, `backend/pytest.u2-account-personal-controls.ini`, and so on). Each tool phase collects one layer folder, writes a JUnit report and an evidence file into its run root, and fails on zero tests, any skip, any error, a missing report, or a source change during the run.
- **Databases:** a real PostgreSQL 16.14 with pgvector 0.8.7 per realm, in Colima. Owner roles, owner filters, revision compare-and-sets and the session guard `accounts.guard_session` are never mocked.
- **Browser:** Playwright 1.55.1 on Chromium with `@axe-core/playwright` 4.13.0, through each Unit's own configuration (`frontend/playwright.u8-complete.config.ts` and the U5 and U6 equivalents). Journeys run only through a tool's journey phases, never by calling Playwright directly.
- **Stand-ins,** each refusing the production profile: the public stand-in for Cloudflare and the tunnel (`scripts/u8_tunnel_standin.py`), the identity stand-in for Google and ORCID (`scripts/u8_identity_standin.py`), fake transports under the real Resend and Notion adapters, a deterministic model stand-in, a healthchecks.io stand-in, and the realm driver in place of the macOS arrangement.

## Key boundaries and where they are tested

| Boundary | Proven by | Phase |
|---|---|---|
| Every module route, stream and asset behind the session guard; another owner's identifier answers like a missing one | U8 integration tests; J03, J12 and J13 | U8 `integration`, `browser-isolation` |
| U2's account controls on the composed chain of 137 migrations | U2's five layer folders, unchanged | U8 `u2-regression` |
| Current authority and late effects: a revoked session, revoked consent, a withdrawal racing a digest, an export and a job | J04, J05 and J08 | U8 `browser-lifecycle` |
| U5's digests through the scheduler to the fake Resend transport | U5's lanes; J02; `integration/test_u5_seams.py` | U5 lanes, U8 `browser-journeys` and `integration` |
| U6's export to the fake Notion transport, with custody | U6's lanes; J01 | U6 lanes, U8 `browser-journeys` |
| The job lifecycle: accept, progress, cancel, reconcile an unknown outcome | J07 | U8 `browser-journeys` |
| PlatformControl's bound operations and receipts (U7) under U8's operations | U7's lane; U8's operations tests | U7 lane, U8 `operations` |
| Backup and restore verification that does not revive an erased owner | J09; the restore paths | U8 `browser-recovery`, `restore-paths` |
| Migration of the synthetic v1, its misfits and its idempotent second pass | J10 | U8 `browser-migration` |
| Switch, abort, rollback and a cancelled rollback | J11 | U8 `browser-cutover` |
| A defect found, fixed and kept fixed by its regression test | J14 | U8 `repair-exercise` |
| Canonical schemas, generated Python and TypeScript bindings, and the type contract | the shared contract suites and drift checks | `test_operations_contract.py`, `test_export_contract.py`, `test:contracts` |
| v1's Next application, which still serves from this checkout until the switch | its type checks, tests and inventories | the next-app checks |

## How to run the tests

Every command runs from the repository root unless it names a working directory, with `DOCKER_CONFIG` and `DOCKER_HOST` set as `build-instructions.md` says.

### U8's integration layer and the regression of U2

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase u2-regression --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

- `integration` runs as four parts, `integration-1` to `integration-4`, in that order, each under its own 300 s bound (`INTEGRATION_HALVES` in `scripts/verify_docsuri_u8.py`, four parts since Build and Test loop-back 1).
- Run 5 (2026-11-19) used four fresh U8 realms, one after another: realm B for the complete verification, then `compatibility`, `performance` and `capacity-burst`; realm A, set up with `build_realm.py --min-free 15`, for `coverage`, `u2-regression`, `frontend` and `build-gate`; realm C for `operations` alone; and realm D for the plain `database`, `repository`, `component-1` and `component-2`, and `integration-1` to `integration-4`.
- Run 6 (2026-11-23) used the same four realms in the same order, through one chain, `~/.docsuri-u8/lead-scripts/bt6_u8_chain.sh`, run alone from the repository root: `build_realm.py --min-free 22 setup migrate fixtures,--corpus,skip verification-run compatibility performance capacity-burst` for realm B, then `--min-free 15` for realms A, C and D, each ending with `archive-owned`. Three things differ from run 5's chain, none of them a test command: a realm's failure does not stop the later realms (each exit is printed); realm B is read before its archive (below); and Colima's disk is trimmed (`colima ssh -- sudo fstrim -av`), then 90 s pass, after each archive.
- `u2-regression` builds a U2-identity realm for each of U2's five layers from U8's image, migrates it with the full composed chain, runs the layer with U2's configuration unchanged, and archives it. It refuses while U2's own environment exists.

### The complete verification (the Construction Verification Command)

On a fresh U8 realm of its own (realm B), after `setup`, `migrate` and `fixtures --corpus skip`. The `operations` lane runs alone on another fresh realm (realm C), because the disk it uses would leave the recovery journey (J09) too little:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase fixtures --corpus skip --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase verification-run --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

It starts the synthetic v1, runs `restore-paths` and `browser-recovery` (J09) on the small database, loads the production-size corpus, then runs `browser-journeys`, `browser-lifecycle`, `browser-migration`, `browser-cutover`, `browser-isolation`, `security`, the four accessibility phases (`accessibility`, `accessibility-signed-out`, `accessibility-keyboard` and `accessibility-screens`), `repair-exercise`, `restart-host` and `restart-database`, and records a VerificationRun for the commit (`VERIFICATION_ORDER`, `scripts/u8_phases.py:106-114`). `security` has a browser half (`security.spec.ts`) and a backend half: the route inventory, the production headers and forged forwarded headers, the sign-in limits and the cross-site arrival (`SECURITY_TESTS`). The run passes only when every required phase ran and passed. It never runs `compatibility`, `performance` or `capacity-burst`; realm B runs those after it, in that order. The schema compatibility check runs on its own:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase compatibility --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

**Realm B is read before its archive** (since run 6, 2026-11-23). The digest observations around J12's one-day advance live in `operations.observation_record`; the old `operations.observation` table stays empty, and reading it instead is what made U8's build records say those observations "were not read". After `capacity-burst` and before `archive-owned`, with the realm's container `$C` live and Colima's `DOCKER_HOST` set, these SELECTs run through `docker exec "$C" psql -U postgres -d docsuri_u8 -At -F ' | ' -c "<query>"`, and their output is written to a file under `~/.docsuri-u8/final-evidence/` (run 6: `bt6-realm-b-reading-20261123.txt`):

```sql
SELECT 'observation_record', count(*) FROM operations.observation_record UNION ALL SELECT 'observation (old)', count(*) FROM operations.observation
SELECT outcome, coalesce(reason_key,'-'), count(*), to_char(min(observed_at) AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'), to_char(max(observed_at) AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS') FROM operations.observation_record WHERE capability='topics.digest' GROUP BY 1,2 ORDER BY 4
SELECT to_char(observed_at AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'), outcome, coalesce(reason_key,'-'), producer FROM (SELECT *, lag(outcome) OVER (ORDER BY observed_at, revision) AS prev, lag(reason_key) OVER (ORDER BY observed_at, revision) AS prevr FROM operations.observation_record WHERE capability='topics.digest') s WHERE prev IS DISTINCT FROM outcome OR prevr IS DISTINCT FROM reason_key ORDER BY observed_at, revision
SELECT state, count(*), count(*) FILTER (WHERE scheduled_at IS NULL) FROM topics.digest_run GROUP BY 1 ORDER BY 1
SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'), (SELECT count(*) FROM operations.incident)
```

The queries change nothing. They give the observation counts, `topics.digest`'s outcomes with their first and last times, each change of outcome, the digest runs by state with those that have no `scheduled_at`, and the incident count.

### U5's and U6's browser checks

Each runs on a freshly initialized realm of its own tool, with no coverage run before it:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
```

U5's covers follow, settings and unsubscribe, scheduled local delivery, an explicit unknown resolution and a recorded empty digest. U6's covers connect, export, cancel and settle, a keyboard-only pass, a 320 CSS px reflow run and axe on every U6 view and dialog.

### The earlier Units' lanes

Each Unit's tool takes `--phase`, `--profile synthetic-local` and `--environment-file /tmp/docsuri-u<N>-run/environment.json`, and each lane starts on a fresh environment of its own:

| Unit | Phases, in order | Notes |
|---|---|---|
| U1 | `setup`, then `scripts/bootstrap_docsuri_u1.py`, then `scripts/bootstrap_docsuri_u1.py --journey`, then `repository`, `component` and `integration` | `teardown` at the end (`lane_u1` in `final_other_lanes.py`); `repository` and `integration` end with the failures decision L1-80 accepts |
| U2 | `setup`, `migrate`, `coverage`, then `database`, `repository`, `component`, `integration`, `operations` | `teardown` refuses automatic disposal, so the environment is stopped and its run root moved aside; then `u2-regression` can run |
| U2 cumulative frontend | `corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u2-cumulative.config.ts --coverage` | covers all of `src/`, with `test/u8-complete` registered |
| U3 | `setup`, `fixtures`, `migrate`, `database`, `repository`, `component`, `integration`, `operations`, `frontend`, `browser`, `coverage`; then `vitest.u3-corpus.config.ts --coverage` | `teardown` only reports, so the environment is stopped and moved aside |
| U4 | `setup`, `migrate`, `coverage`, `archive-owned`; then `component` and `integration`, each on a fresh environment of its own; then `frontend` and `browser` (after a Vite build) on another; then `tsc --project tsconfig.u4-research.json --noEmit --incremental false`, ESLint and `vitest.u4-research.config.ts --coverage` | a coverage run uses up the environment's synthetic accounts, so later phases on it refuse ("Synthetic account allocation exhausted") |
| U5 | `setup`, `migrate`, `fixtures`, `coverage`, `archive-owned`; then `component` on a fresh environment of its own; the browser check above on another; `database` on another, for the composed chain; then `test_archive_expiry.py`, `tsc --project tsconfig.u5-topics.json --noEmit --incremental false`, `vitest.u5-topics.config.ts --coverage` and the collect-only count (U5's instructions:47, :81, :93-94, :101) | a coverage pass uses up the realm's authentication attempts, so `component` and the browser check need fresh realms. This is the arrangement up to run 5; since run 6 every U5 phase runs on a fresh environment of its own, with the new `repository` lane (below) |
| U6 | `setup`, `migrate`, `coverage`, `frontend`, `archive-owned`; then the browser check above on another fresh environment | `coverage` also reports `scripts/u6_preservation.py` on its own |
| U7 | `setup`, `component`, `database`, `repository`, `integration`, `operations`, `coverage`, `teardown` | U7's files stay as built |

**U5's lanes since run 6** (2026-11-23), as U5's loop-back 4 section writes them: each of U5's phases runs on a fresh environment of its own, and the new `repository` lane joins them. `~/.docsuri-u8/lead-scripts/lb4_u5_lanes.py` does this, in place of the U5 lanes of `cp7_lanes.py`:

```bash
python3 -I ~/.docsuri-u8/lead-scripts/lb4_u5_lanes.py --lanes kept-bytes,u5-database,u5-repository,u5-component,u5-coverage,u5-browser,u5-frontend,u5-eslint,u5-ruff,u5-archive-expiry,u5-collect
```

For each of `database`, `repository`, `component`, `coverage` and `browser` it runs `setup`, confirms the container in Colima, then `migrate`, `fixtures` and the phase, reads the phase's evidence and archives the environment. `kept-bytes` compares the SHA-256 of U5's seven kept files with U5's code summary. Two direct commands follow it, from the repository root. The read of Step 41(c), which checks that `backend/modules/topics/u5_scheduled_instant.sql` sits once in U8's composed chain, between `u5_refusal_detail.sql` and `accounts/u6_lifecycle_guard.sql`, owned by `topics`, and exists:

```bash
backend/.venv/bin/python -c "from backend import u8_migrations as m; f = m.chain_files(); n = 'backend/modules/topics/u5_scheduled_instant.sql'; i = f.index(n); assert f.count(n) == 1 and f[i - 1] == 'backend/modules/topics/u5_refusal_detail.sql' and f[i + 1] == 'backend/modules/accounts/u6_lifecycle_guard.sql' and dict((p, o) for o, p in m.migrations())[n] == 'topics' and (m.ROOT / n).is_file()"
```

It prints nothing when it holds, so its log is empty and its exit 0 is the result. Then the three chain tests:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini -q --tb=short tests/u5_topics_digests/database/test_migration_digests.py::test_the_u5_chain_appends_exactly_the_pinned_files_in_order tests/u5_topics_digests/database/test_migration_digests.py::test_every_applied_u5_file_keeps_its_pinned_bytes tests/u5_topics_digests/operations/test_runner_bindings.py::test_migration_chain_is_append_only_and_present
```

**U8's loop-back 4 additions** (since run 6). U8's static driver `~/.docsuri-u8/lead-scripts/step143_abc.py --only a,b,c,u6` runs U8's static checks, frontend lanes and collection, and its `u6` part runs U6's `setup`, `migrate`, `operations`, `coverage` and `archive-owned` on a fresh U6 environment of its own, because U8's section changed files U6's realm-pair test reads. U8's Vitest run scoped to the two test files its section changed:

```bash
corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u8-complete.config.ts test/u8-complete/notices.test.tsx test/u8-complete/first-sign-in.test.tsx
```

U8's ops Ruff, Prettier list and the kept-bytes reading of the 45 shared paths are in `build-instructions.md`. A command that two drivers run (U6's coverage, Ruff's seven invocations, U8's ESLint and tsc, U4's and U6's tsc and ESLint (three drivers each), U5's tsc and ESLint, the root suite, U2's cumulative lane, U3's and U4's Vitest lanes, the inventories, the collection) is counted once, and both results are stated.

**After a refused U1 bootstrap** (since run 5, 2026-11-19): keep the refused environment as a failed prerequisite, never relabelled, and rerun U1's lane on a fresh environment through `~/.docsuri-u8/lead-scripts/u1_lane_capture.py`, from the repository root, under umask 077 and with Colima's `DOCKER_HOST`:

```bash
python3 -I ~/.docsuri-u8/lead-scripts/u1_lane_capture.py
```

It runs the same steps as the driver's U1 lane, in the same order, through `final_other_lanes`' own runner (the same logs, the same L1-80 verdict check and the same halt rule). When `scripts/bootstrap_docsuri_u1.py` is refused, it writes `docker container inspect` of the container's state and `docker logs --timestamps` to step logs before the teardown removes the container, so the refusal can be read against the log for the image's init-server restart, as project.md asks. It adds no wait between setup and bootstrap and leaves U1's tool unchanged. When the bootstrap passes, it keeps no container log.

**After a refused U7 setup** (since run 6, 2026-11-23), the same rule applies: keep the refused environment as a failed prerequisite, never relabelled, and rerun U7's lane on a fresh environment, with `final_other_lanes.py --lanes u7` unchanged. U7's tool waits the same way U1's does (`docker exec pg_isready`, then the bootstrap child at once; `scripts/verify_docsuri_u7.py:211-229`, `:280-281`). In run 6 both reruns went through one script, `~/.docsuri-u8/lead-scripts/bt6_rerun_u1_u7.sh`, run alone from the repository root under umask 077: it moves each refused folder into `~/.docsuri-u8/final-evidence/` under a failed-prerequisite name, then tries U1 through `u1_lane_capture.py` and U7 through `final_other_lanes.py --lanes u7`, up to three attempts each, 90 s apart. Beside each U7 attempt, a watcher reads only the driver's own step log; once `u7-setup` has ended with a non-zero exit, it runs `docker inspect` and `docker logs --timestamps` on the U7 container, so a passing attempt is not touched. In run 6 the container was already gone each time, so no U7 container log exists.

### The shared contract and the next-app checks

```bash
shared/python/.venv/bin/python shared/python/tools/export_workspace_contract.py --check
PATH="$PWD/shared/python/.venv/bin:$PATH" shared/python/.venv/bin/python shared/python/tools/generate.py --check
shared/python/.venv/bin/python shared/python/tools/inventory_consumers.py
corepack pnpm@9.15.9 --dir frontend run check:types
corepack pnpm@9.15.9 --dir frontend run check:consumers
corepack pnpm@9.15.9 --dir frontend run test:contracts
corepack pnpm@9.15.9 --dir frontend run test
corepack pnpm@9.15.9 --dir frontend audit --prod --audit-level high
```

From working directory `shared/python`:

```bash
.venv/bin/python -m pytest -o addopts='' -q --tb=short tests/test_operations_contract.py tests/test_export_contract.py
```

The inventories are checked, not rewritten: `--write` is for a deliberate refresh only.

**When the root suite fails** (since run 6, 2026-11-23): the failing run stays a failure on record. The suite (`corepack pnpm@9.15.9 --dir frontend run test`) runs again, alone, three more times, with its output kept (run 6: `bt6-chain-20261123/root-suite-alone-1.log` to `-3.log` under `~/.docsuri-u8/lead-scripts/final-lanes/`). Every run of the suite on the same source is counted, the drivers' runs included, and the result is stated as failures out of runs, never as the last run alone.

### The three umask-only tests of `ci.yml`'s suites, at CI's umask 022

This stage runs `ci.yml`'s suite jobs under umask 077, in the sandbox and clean environment of `~/.docsuri-u8/lead-scripts/bt_rung1_checks.py`. Three tests check for mode 0o755, which umask 077 masks to 0o700, so they fail there and not on CI, which runs at 022. Since run 5 (2026-11-19, the maintainer's choice "Run the three at 022 (Recommended)"), the driver runs them once more at umask 022, in the suites' sandbox profile and clean environment, from each suite's own `.venv` (its steps `platform-integrity-umask022` and `ops-umask022`, listed in `UMASK_022_STEPS`; every other step keeps 077, and each step's log header records its umask):

```bash
# from platform_integrity, at umask 022
.venv/bin/pytest -p no:cacheprovider tests/test_protected_receipts.py::test_publication_writes_readonly_receipts_and_leaves_no_temporary tests/test_protected_receipts.py::test_publication_refuses_to_overwrite_a_foreign_receipt
# from ops, at umask 022
.venv/bin/pytest -p no:cacheprovider -p no:anyio tests/test_u1_colima_executor.py::test_prepared_executor_refuses_context_executable_and_rule_digests
```

At 022 all three pass, as on CI.

## Expected coverage

Integration tests carry no coverage floor of their own; their lines count toward each Unit's floor:

- U8's backend and ops at least 80% (`backend/.coveragerc.u8`), and `src/u8-*/**` at least 80%;
- U2's coverage phase at least 80.00% at two decimals, and U2's cumulative frontend lane at least 80% of all of `src/`;
- U3's and U4's lanes keep `src/App.tsx` at or above 48%; U4's backend at least 80%;
- U5 and U6 at least 80% each; U7 with every file of `docsuri_ops.platform_control` at or above 80%;
- every journey of BR10.3 (J01 to J14, A11Y, SEC) passes in the VerificationRun.

No floor is lowered, no file is removed from a measured list, and no bound is raised to make a run pass.

## Test data and environments

- **U8's fixtures** (`scripts/u8_fixtures.py`, version `u8-fixtures-v1`): memberA for the cross-unit journeys, memberB for isolation, an administrator with a second factor, eligible public papers with research and novelty results made through U4's own service, the synthetic v1 dataset with every misfit kind and account state, the production-size corpus (600 papers of 100 chunks), and the fake providers' scenario files. Since loop-back 4, every fixtures run except `--corpus only` also adds one ready paper-assistance job for memberA, with its result, through `scripts/u8_fixture_assistance.py`, and records it in `fixtures/browser.json` under `assistanceJob`.
- **Per-run identity:** operation keys, submission identifiers and message keys are unique per run, and every secret is generated per run. No real provider key, token, account, email address or v1 data appears in any test.
- **Isolation of environments:** coverage runs straight after `migrate` on its own realm, never after `fixtures` (it refuses with `coverage-after-fixtures`). The complete verification uses a second fresh realm, set up after the first is archived. Browser checks never share a realm with a coverage run.
- **Closing:** `archive-owned` stops the realm, deletes its key files and keeps the stopped containers; the archived copies are then removed with the maintainer's approval. An expired, consumed or foreign environment is a failed prerequisite, never a skip.
- **Chain outputs** (since run 6): every chain's own output is kept under `~/.docsuri-u8/final-evidence/` (run 6: `bt6-u8-chain-output-20261123.txt`, `bt6-lanes-chain-output-20261123.txt` and `bt6-rerun-output-20261123.txt`), and every driver's JSON lines, stderr and direct-command logs under `~/.docsuri-u8/lead-scripts/final-lanes/bt6-chain-20261123/`, not under `/tmp`, which a restart empties.
