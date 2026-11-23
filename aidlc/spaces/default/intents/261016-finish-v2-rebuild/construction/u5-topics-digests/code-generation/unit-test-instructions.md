# U5 — unit test instructions

Unit: `u5-topics-digests`. Revised for the human's **Repair and re-review U5**
decision. Testing Contract: test-after, standard strategy, brownfield,
express base. Implement each layer, then write and run its checks. Preserve
existing targets and behavior; no requirement is waived by a synthetic test.

## Framework setup and configuration

- Backend: `pytest` in `backend/.venv`, unit configuration
  `backend/pytest.u5-topics-digests.ini`, and existing owner-scoped realm helpers.
- Frontend: scoped Vitest/React Testing Library and Playwright configurations.
- Coverage: retain `backend/.coveragerc.u5` and
  `frontend/vitest.u5-topics.config.ts` floors. Include the changed production
  paths in measurement; do not omit new preference or delivery code to improve
  the percentage.
- Where each changed path is measured (Build and Test loop-back 1, your
  decisions of 2026-10-28):
  - `backend/.coveragerc.u5` (80%): U5's own modules as before, plus
    `backend/local_observation.py`.
    `backend/modules/accounts/integrations/email.py` is no longer a U5 change:
    Step 19 removed U5's only addition to it, the unused `send_digest_email`.
  - U8's `backend/.coveragerc.u8` (80%): the shared runtime files U5 changed
    (`artifacts.py`, `control_worker.py`, `lifecycle_effects.py`,
    `local_browser.py`, `local_host.py`, `local_profile.py`, `transactions.py`)
    and `ops/src/docsuri_ops/local_transport.py`.
  - U2's `backend/.coveragerc.u2` (80.00%): `backend/modules/accounts/local_http.py`.
  - U3's and U4's lanes: `backend/u3_host.py` and `backend/u4_host.py`.
  - U2's cumulative lane, `vitest.u2-cumulative.config.ts` (80% over all of
    `src/`): the shared shell files `src/App.tsx` and `src/api.ts`.
  - `vitest.u5-topics.config.ts` (80%): `src/u5-topics/**`, as before.
  - `scripts/verify_docsuri_u5.py` is the runner: unmeasured, its behaviour
    tested, as U8's runner is.
- Run Python commands from the repository root. Use the unit runner for
  stateful checks so identity, finite capacity, supervision and evidence remain
  enforced. An expired/missing/consumed realm is a failed prerequisite, not a skip.
- Preserve the failed or consumed realm using `archive-owned` before a fresh
  `setup`, `migrate`, `fixtures` sequence. Never extend its expiry, reset quota,
  rewrite migration receipts, delete failed-run evidence, or broaden DB grants.

## Exact unit-scoped commands

Collect only, before the first repair-layer test execution. This command neither
executes the test suite nor falls through to repository-wide collection:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini --collect-only -q tests/u5_topics_digests
```

The unchanged baseline collected 81 tests. Record the actual repaired count.
The prior unscoped command is superseded; do not run it.

Preserve an existing owned idle realm, then initialize its replacement:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase fixtures --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

Use `archive-owned` only when an existing owned realm is present and its
custody/resource checks pass. Preserve the returned archive path and original
manifest bytes. Active clients must be resolved before preservation. Inspect
available capacity before allocating a replacement; no limit is waived.

Per layer after its implementation:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

These are individual finite passes, not an instruction to reuse one exhausted
realm indefinitely. Preserve/recreate when required. The focused preservation
regression is independently runnable:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini -q tests/u5_topics_digests/operations/test_archive_expiry.py
```

Full backend coverage in its own fresh realm:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

Frontend commands run with `frontend` as the working directory:

```bash
corepack pnpm@9.15.9 exec tsc --project tsconfig.u5-topics.json --noEmit
corepack pnpm@9.15.9 exec vitest run --config vitest.u5-topics.config.ts --coverage
```

Mounted browser check, using another freshly initialized realm with no prior
coverage-test topic backlog:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
```

The browser invocation above remains the exact human-authorized construction
verification command. At the actual unit completion checkpoint, invoke it
through AI-DLC's checkpoint verifier so the proof binds to the current source.
A direct exploratory browser run does not create that checkpoint receipt.

## Browser and backend isolation

Coverage fixtures may enqueue scheduled work. They must never precede browser
acceptance in the same realm. Preserve the backend realm and create a new
browser realm at the same manifest path, or use separately owned realms under a
documented runner binding that leaves the authorized command intact.
CI already uses distinct backend and browser jobs; preserve that separation.

Keep the existing 20-second browser expectation and delivery/resource limits.
Test scheduler backlog separately with explicit bounded expectations. Do not
clear state, skip queued work, enlarge timeouts, or mark a failure as a pass.
Preserve every failed attempt, command, log, report and source digest.

## Required repair verification

| Area | Required cases and observable evidence |
|---|---|
| Migration and ownership | Fresh install and upgrade from the current U5 chain; targeted additions avoid duplicate U2 columns/tables; cross-owner grants refused; original migration hashes/receipts remain immutable. |
| Preference inheritance | Two owners select `en` and `ko`; inspect actual persisted presentation and email subject/body, not just stamps. Consume supported `standard`; reject unsupported vocabulary. Label missing-settings defaults honestly. |
| Timezone | Explicit confirmed zones; missing/invalid zone affects only its owner. Same UTC instant across local midnight; daily and weekly before/at/after due time; next-day late weekly execution; DST gap/fold; first confirmation and later zone changes; bounded catch-up. |
| Queued changes | Preference changes racing preparation/admission discard unsent work; sending finishes once; unknown and terminal evidence remain unchanged. Appearance-only edits do not discard an otherwise valid digest. |
| Settings authority | C03 routes mounted; current owner, revision CAS and receipt replay enforced. Manual settings remain editable after research/behavior consent revocation; delivery still stops. |
| Transport contract | Accepted response retains actual receipt/time; definite refusal fails; timeout, connection loss, ambiguous server error or malformed success remains unknown. Sanitized categories never expose secret/recipient/provider payload. |
| Recovery | Crash after receipt persistence reconciles without another send; absent evidence remains unknown. Stable initial request identity, duplicate/concurrent calls, changed payload and expired provider keys never justify automatic resend. |
| Configuration | Local/test profiles make zero real network calls with fake ambient credentials. Missing/unsupported real configuration refuses; no implicit SES, paid, or mock-success fallback. Actual adapter identity determines `pathKind`. |
| Existing behavior | Owner isolation, source eligibility, watermark, unknown pause, unsubscribe/consent changes, single-flight, orphan recovery and lifecycle disposition stay effective. |
| Frontend | Loading/empty/error/ready/partial states; acknowledged save, stale revision, honest inherited settings, account switch, keyboard/focus, Korean responsive light/dark/system UI. |
| Browser journeys | At least four: follow/settings/unsubscribe; scheduled local-sink delivery; explicit unknown resolution; recorded empty digest with no send. Add owner-preference propagation assertions through the actual mounted API/store. |

Use five to eight focused tests per changed component and integration checks for
every changed boundary; add cases where distinct races require them. After
shared preference/email code changes, run the relevant existing account,
Personalization, profile-binding and U3/U4 integration regressions with exact
file scopes and their own valid realm prerequisites. Record the selected
commands/results in the code summary. Do not run a bare project-wide pytest or
reuse U5 credentials in another unit's realm.

## Expected coverage targets

- Preserve the configured 80% aggregate backend coverage floor and any existing
  stricter targets. Report individual file coverage honestly.
- Baseline evidence is 81 backend checks and 87.87% aggregate coverage, followed
  by a failed browser checkpoint. These results are not repaired-source results.
- Existing suites must remain green. Historical 473 backend/356 frontend counts
  are references to prior work, not verified present suite sizes.
- Zero tests, skipped mandatory checks, missing evidence or missing required
  external prerequisites cannot be described as success.

## Mocking and stubbing guidance

Prefer the real mounted boundary and owner-scoped PostgreSQL. Never mock away
an authority, consent, revision or ownership check. Inject one UTC instant
through both SQL selection and Python window calculations; do not combine it
with independent database time.

Adapter contract tests use fake HTTP responses and fake credentials. A
real-adapter fixture may assert its trusted identity with a fake transport,
but that is explicitly simulated contract evidence. Synthetic assembled
application runs always remain network-disabled and record `local-sink`.
Do not label a local acknowledgement as external delivery.

## Real-delivery evidence

Prepare one bounded demonstration with the configured existing free adapter,
run identity, permitted paper content, verified sender, confirmed $0 plan and
available quota. Keep credentials in inherited server configuration; never put
them in this document, client state, error text or evidence.

Obtain explicit authorization for the recipient and exact test message before
any external send. Record the actual `pathKind=real`, provider acknowledgement,
and correlated recipient-side evidence. Provider acceptance alone proves
acceptance, not inbox placement or reading. An unconfigured or unauthorized
path remains an open prerequisite. No synthetic or mock pass closes R-06's
real-delivery condition.

## Test data management

Use synthetic accounts and eligible public-paper fixtures for automated tests.
Include different confirmed owner zones, an unresolved zone, supported
language/level values, eligible/fully-watermarked/empty windows, stale prepared
runs, sending/unknown states with and without receipts, consent/unsubscribe
races, and timezone-change boundaries.

Real delivery is a separately authorized demonstration and cannot reuse
synthetic fixtures as authority to contact someone. Evidence must record exact
commands, identities, source digests, counts and outcomes while redacting
private content and recipient addresses.

## Build and Test loop-back 4 (2026-11-22)

These additions belong to the plan's Steps 40–48 (decisions L4-1 to L4-7) and extend the sections above; where a sentence below replaces one above, the replacement governs. They are written for L4-1's option 1, the new column. If you choose option 2 at Plan Approval, this section is changed and approved again with the plan before any build step.

Build and Test's fifth run left U8's two digest targets Not Met (`U8:NFR9.2` and `U8:NFR9.2:export-digest-degraded`). You chose "Retry with fix" on 2026-11-22, beyond the bound of three loop-backs. U5's part: each digest run records its scheduled instant when the scheduler prepares it, so that U8 can count a pending run from that instant whatever happens to the topic's settings afterwards.

No bound, floor or target changes:
- every phase keeps its 300 s and its 1 GiB;
- `backend/.coveragerc.u5` keeps `fail_under = 80` and its include list, and its bytes do not change;
- `backend/u5_policy.py`, `backend/modules/topics/delivery.py`, `backend/u5_real_delivery.py` and `frontend/vitest.u5-topics.config.ts` do not change either. U8's tests pin the bytes of these five files;
- `backend/modules/topics/http.py` (pinned by `shared/python-consumers.json`) and `backend/u5_host.py` (claimed by U6) do not change;
- no applied migration changes a byte.

- **Framework setup and configuration.**
  - New migration: `backend/modules/topics/u5_scheduled_instant.sql`, appended last in the runner's `MIGRATIONS`, and listed in U8's composed chain, `backend/u8_migrations.py`, after `u5_refusal_detail.sql`. An environment migrated before either entry existed is archived and set up again; it is never migrated in place. Only U8's tool refuses such an environment (`scripts/verify_docsuri_u8.py:1725-1727`). U5's and U6's tools would apply the new file in place (`scripts/verify_docsuri_u5.py:730-754`; `scripts/verify_docsuri_u6.py:640-660`), for U6 after its own four files, so for those two the rule is kept by archiving before every `setup` and is not checked by the tool.
  - New test file: `repository/test_scheduled_instant.py`. Its basename is unique across the layer folders.
  - New shared helper module: `tests/u5_topics_digests/calendar_flow.py`. It holds `run_clock`, `utc_date_after`, `next_transition`, `wall_exists`, `first_valid_instant`, `schedule` and `occurrence`, with `NEW_YORK` and `FAR_AHEAD`, moved unchanged from `component/test_schedule_preferences.py`, which now imports them. That file's seven tests do not change.
  - No new configuration, no new production module and no frontend file.
  - Where each changed path is measured: `backend/modules/topics/repository.py`, `scheduler.py` and `preparation.py` by `backend/.coveragerc.u5`, as before; U8's `backend/.coveragerc.u8` also measures the first two. The migration is SQL: the database tests check it, and no report measures it. `scripts/verify_docsuri_u5.py` stays unmeasured, its behaviour tested. `backend/u8_migrations.py` is measured and tested by U8's lanes.
  - On this Mac every tool command below carries Colima's pair, `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config`, written out in each command. After each `setup`, the environment's container is confirmed through Colima's socket before anything is recorded:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config docker ps --filter label=dev.docsuri.u5.run --format '{{.Names}} {{.Status}}'
    ```

    The label is `dev.docsuri.u6.run` for U6's environments and `dev.docsuri.u8.run` for U8's. Wait 90 s after each `archive-owned` before the same unit's next `setup`.
  - Kept bytes: before the first edit (Step 40) and after the last (Step 48(e)), from the repository root:

    ```bash
    shasum -a 256 backend/u5_policy.py backend/modules/topics/delivery.py backend/u5_real_delivery.py backend/.coveragerc.u5 frontend/vitest.u5-topics.config.ts backend/modules/topics/http.py backend/u5_host.py
    ```

    The two readings must be equal, and the code summary records both.

- **Exact unit-scoped commands.** The realm commands, the layer phases, the collect-only command, the preservation regression, `tsc` and Vitest below are the commands above, the tool commands with Colima's pair, in this loop-back's order, and `tsc` with `--incremental false`, as loop-back 3 ran it (`code-summary.md:260`). Four commands below are not in the sections above: the read of Step 41(c), the direct run of the three chain tests, Ruff and ESLint. Ruff and ESLint are the steps of U5's own workflow (`.github/workflows/u5-topics-digests.yml:97-104` and `:70-76`), as loop-back 3 ran them (`code-summary.md:261-262`). The withheld form further down is new too.
  - Collect only, before the first new test runs and again on the final source. It collected 331 after loop-back 3; 349 are expected (one database test, twelve repository items, five component items). Record the actual count, and the time of the first run:

    ```bash
    backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini --collect-only -q tests/u5_topics_digests
    ```

  - A fresh U5 realm. Run `archive-owned` only when an owned realm is present:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase fixtures --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
    ```

  - With Step 41(c), a read that needs no realm, from the repository root. It is a check, not a test. It exits 0 only when U8's composed chain holds the new file once, between `u5_refusal_detail.sql` and `u6_lifecycle_guard.sql`, under the `topics` owner, and the file exists; a missing entry ends it with an error:

    ```bash
    backend/.venv/bin/python -c "from backend import u8_migrations as m; f = m.chain_files(); n = 'backend/modules/topics/u5_scheduled_instant.sql'; i = f.index(n); assert f.count(n) == 1 and f[i - 1] == 'backend/modules/topics/u5_refusal_detail.sql' and f[i + 1] == 'backend/modules/accounts/u6_lifecycle_guard.sql' and dict((p, o) for o, p in m.migrations())[n] == 'topics' and (m.ROOT / n).is_file()"
    ```

    `backend/u8_migrations.py` imports only `hashlib` and `pathlib` (`:30-31`), so the read touches no database and no other module.
  - Per layer, after its implementation, on a prepared realm: `database` after Step 42, `repository` after Step 44, `component` after Step 46:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
    ```

    With Step 42, the three chain tests that need no realm also run directly:

    ```bash
    backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini -q --tb=short tests/u5_topics_digests/database/test_migration_digests.py::test_the_u5_chain_appends_exactly_the_pinned_files_in_order tests/u5_topics_digests/database/test_migration_digests.py::test_every_applied_u5_file_keeps_its_pinned_bytes tests/u5_topics_digests/operations/test_runner_bindings.py::test_migration_chain_is_append_only_and_present
    ```

  - The recorded runs (Step 48(b)), on the final source after every temporary edit is restored, each test phase on its own fresh realm prepared as above: `database`, `repository` and `component` by the three commands above, then `coverage` and `browser`:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json
    ```

    `coverage` also runs the integration and operations folders, under the unchanged 80% floor. `browser`'s scheduled local-sink journey prepares a run through the changed path on U5's own chain. Each realm is archived with `archive-owned` after its phase.
  - Without a realm, from the repository root: the collect-only command, the focused preservation regression, because the runner file changes, and Ruff, as the workflow step "Lint topics and shared runtime changes" runs it, with `--no-cache`. The last line lints the one changed file that list does not hold:

    ```bash
    backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini -q tests/u5_topics_digests/operations/test_archive_expiry.py
    backend/.venv/bin/ruff check --no-cache backend/modules/topics backend/u5_*.py backend/local_profile.py backend/transactions.py backend/local_browser.py backend/artifacts.py backend/local_observation.py backend/lifecycle_effects.py backend/control_worker.py backend/modules/accounts/local_http.py backend/modules/accounts/integrations/email.py scripts/verify_docsuri_u5.py scripts/serve_docsuri_u5.py scripts/u5_browser_fixtures.py tests/u5_topics_digests
    backend/.venv/bin/ruff check --no-cache backend/u8_migrations.py
    ```

  - The frontend commands, with `frontend` as the working directory. No frontend file changes; they run so that the earlier frontend steps' boxes rest on runs of this source:

    ```bash
    corepack pnpm@9.15.9 exec tsc --project tsconfig.u5-topics.json --noEmit --incremental false
    corepack pnpm@9.15.9 exec vitest run --config vitest.u5-topics.config.ts --coverage
    corepack pnpm@9.15.9 exec eslint src/u5-topics src/App.tsx src/api.ts test/u5-topics e2e/u5-topics-digests vitest.u5-topics.config.ts playwright.u5-topics.config.ts --parser-options '{"project":"./tsconfig.u5-topics.json"}'
    ```

- **Other Units' lanes this loop-back reaches (Step 48(c) and (d)).** They run once, in Code Generation. They are not U5's unit-scoped commands, and Build and Test does not run them as U5's.
  - U6's lanes (Step 48(c)), with U6's own tool, on two fresh U6 environments. No U6 file changes. Run U6's `archive-owned` first only when an owned U6 environment is present:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
    ```

    `coverage` runs every backend layer of U6 in one pass under U6's own floor: the database, repository, component, integration and operations folders (`scripts/verify_docsuri_u6.py:1120`), as U6's workflow does. So `component` and `integration` are not run as lanes of their own, as Build and Test's run 5 ran them (decision L4-5). `browser` refuses an environment that holds any phase's evidence, so it has its own.
  - U8's `database` phase (Step 48(d)), on a fresh U8 realm, to show that the composed chain applies with the new file and to read the realm privilege pin's test. Run U8's `archive-owned` first only when an owned U8 realm is present, and read the free disk before `setup` (see the checkpoint below):

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
    ```

    The phase's result is recorded either way. A failure is recorded with the test and what it showed, and goes to you before the checkpoint. If it is `test_every_realm_logins_privileges_equal_the_pinned_inventory`, the rows that moved are recorded and owed to U8's plan; U8's pin is not taken again in U5's build. Anything else may mean the chain entry is wrong. A pass does not show that the entry is present: `database/test_composed_chain.py` compares the realm's receipts with the same list that built the realm (`:69-75`). The read of Step 41(c) and J02 show that.

- **The checkpoint.** Replace "The browser invocation above remains the exact human-authorized construction verification command" and the two sentences after it with: the checkpoint's verification is the Construction Verification Command this piece of work records, U8's `verification-run`. It is U8's tool, not a U5 unit-scoped command. AI-DLC's checkpoint verifier runs it, on a fresh U8 realm. Run U8's `archive-owned` first only when an owned U8 realm is present; then prepare the realm by:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase fixtures --corpus skip --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
    ```

    The command the verifier runs:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase verification-run --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
    ```

  - Its journey J02, a followed topic reaching a delivered digest through the scheduler, prepares a run through the changed path on the composed chain. It asserts nothing about the stored instant: U5's own lanes do. A direct run of the command is not the checkpoint's receipt, and it leaves evidence the verifier's run then refuses. U5's `--phase browser` stays one of U5's recorded lanes.
  - Disk. Before this realm is set up, the free disk less the realm's database stays above J09's 20 GiB guard, which is never lowered. Read the free bytes of the repository's volume before Step 48(d)'s `setup` and again before the checkpoint's `setup` (`df -k .` from the repository root; the tool's own preflight reads the same volume, `scripts/verify_docsuri_u8.py:715`), together with macOS's own available capacity, with purgeable space, and what fills the disk (project.md, 2026-11-17). About 22 GiB free is the working floor U8's instructions use before a `setup` (U8's `unit-test-instructions.md:1094`). If it is short, stop and ask: only with your approval are stopped `docsuri-u8-<id>` containers and volumes removed and Colima's `fstrim` run twice; a restart of the Mac is yours to make, after the preserved folders are copied out of /tmp (project.md, 2026-11-14).

- **Required repair verification.** Add this row:

  | Area | Required cases and observable evidence |
  |---|---|
  | Run schedule | A run the scheduler prepares stores the due instant the due read gave for it: daily; weekly; prepared late (the instant is the occurrence's, never the pass's clock or the row's creation time); on a day with a missing wall minute (the first valid minute) and with a repeated one (its first occurrence). The stored instant never changes: not on a later change of the topic's delivery time or cadence, not on a change of the owner's zone, not on a state move, not on a re-fire that adopts the run. It is there while the run is prepared, sending or unknown. An instant is stored only together with the preference fence, and one read before a zone change is refused. A run prepared by a direct call that hands in no instant, and every run stored before this migration, hold no instant, and none is ever filled in later. |

- **Required repair verification > the tests.**
  - Database, in `database/test_preference_schema.py` (6 tests, 7 after): `test_a_runs_scheduled_instant_is_set_once_and_never_changes`. Through the topics login, on two topics: a run inserted with an instant refuses a change to another instant and to none; a run inserted without one holds none and refuses a later instant; a state move leaves both as they were. Then, read from `pg_proc`: the replaced `topics.guard_preparation_snapshot()` still has `search_path=pg_catalog`, is not a definer function, and is executable by the topics login and its owner only. The chain-upgrade catalog comparison cannot show a lost search path, because it compares two installs of the same file (`database/test_chain_upgrade.py:79-82`, `:356-366`).
  - Database, extended under their own names:
    - `database/test_migration_digests.py`: `U5_CHAIN` gains the new file with the SHA-256 of its built bytes, and the `newest-repair` case names the new file;
    - `database/test_chain_upgrade.py`: `REPAIRS` gains the new file (seven repairs, 66 migrations); `test_the_upgrade_keeps_every_pre_repair_row_and_receipt` also reads the new column on the eight old runs and finds none set; `test_old_rows_keep_their_constraints_and_guards` also tries to set an old run's instant and is refused;
    - `operations/test_runner_bindings.py::test_migration_chain_is_append_only_and_present`: the list after `u5_run_guard.sql` gains the new file.
  - Repository, new file `repository/test_scheduled_instant.py` (8 tests, 12 items), on the real realm:
    1. `test_a_prepared_run_keeps_the_scheduled_instant_it_is_handed`: the returned row and a fresh read hold the same instant; an instant given at another offset reads back as the same instant.
    2. `test_a_run_prepared_without_an_instant_holds_none`: not the creation time, not the window's day at the current delivery time.
    3. `test_an_instant_that_is_naive_mistyped_or_unfenced_is_refused`, three cases: no zone; a string; given without `expected_preferences`. Each is `INVALID_ARGUMENT` on `scheduledAt`, and no run is created.
    4. `test_an_instant_from_a_due_read_made_before_a_zone_change_is_refused`: `CONFLICT`, and no run holds the instant.
    5. `test_a_refire_adopts_the_run_and_keeps_its_first_instant`: a second preparation of the same window with another instant adopts the run and changes nothing.
    6. `test_a_later_change_leaves_a_started_runs_instant`, three cases: the owner saves a new delivery time; the owner changes the cadence to weekly; the owner changes the zone. Each change is made after the send started, through the owner's real save with its revision, and the instant is read again while the run is sending and after it turns unknown.
    7. `test_no_state_move_changes_the_instant`: prepared, sending, unknown and the owner's resolution, and a prepared run that is discarded, each read through the topics login with the states U8's statement names.
    8. `test_a_run_prepared_again_after_a_discard_holds_its_own_instant`: the discarded row keeps the first instant, and the new row holds the second.
  - Business logic, in `component/test_topics_scheduler.py` (5 tests, 8 after; 6 items, 11 after), each through `TopicsScheduler.run_once` on the real realm, last in the file:
    1. `test_a_daily_run_records_its_occurrence_not_the_pass_clock`: the pass runs some minutes after the due minute.
    2. `test_a_late_pass_records_the_occurrence_it_catches_up`, two cases: a daily topic whose pass runs three days late; a weekly topic whose pass runs on the next local day. The run's window ends on the delivery day and its instant is that day's.
    3. `test_a_run_due_in_a_clock_change_records_the_first_valid_minute`, two cases in America/New_York: the spring day with no 02:30 (03:00 is recorded) and the autumn day with two 01:30s (the first is recorded). In each case the pass runs later than the recorded instant: ten minutes after 03:00 on the spring day, and after the second 01:30 on the autumn day, so that a pass's clock handed in as the instant (W7) cannot equal it.
  - Changed boundaries: the scheduler, the preparation, the repository and the store are checked together by the three component tests, on the real store. The composed chain's entry is checked by the read of Step 41(c), by U8's `database/test_composed_chain.py` in Step 48(d) and by J02 at the checkpoint. U8's side of the read is checked in U8's lane when U8 is reopened.

- **Expected coverage targets > Test volume.** Five to eight tests per changed component, counted as decision L3-1 counts them (functions; collected items in brackets):

  | Component | File | Before | After |
  |---|---|---|---|
  | Additive preparation evidence | `database/test_preference_schema.py` | 6 | 7 |
  | Chain upgrade | `database/test_chain_upgrade.py` | 5 | 5 (2 extended) |
  | Applied migration bytes | `database/test_migration_digests.py` | 5 [6] | 5 [6] (pins extended) |
  | Runner bindings | `operations/test_runner_bindings.py` | 5 | 5 (1 extended) |
  | A run's scheduled instant (`TopicsRepository`) | `repository/test_scheduled_instant.py` | new | 8 [12] |
  | The due path: scheduler and preparation | `component/test_topics_scheduler.py` | 5 [6] | 8 [11] |
  | Calendar occurrence rules | `component/test_schedule_preferences.py` | 7 | 7 (helpers moved out) |
  | U8's composed chain, one entry | U8's `database/test_composed_chain.py`, run in Step 48(d) | U8's (15) | U8's (15), no U5 test |

  `database/test_schema.py`, `repository/test_repository.py` and `repository/test_preferences.py` already hold eight and gain nothing. `DigestPreparation.prepare` only passes the instant on and is counted with the scheduler (decision L4-4). The entry in `backend/u8_migrations.py` is counted in U8's volume; a test comparing U8's list with U5's `MIGRATIONS` is owed to U8's plan (decision L4-6). The code summary records the count of each U5 file above from the collect-only run.

- **Mocking and stubbing guidance > Never mocked.** Add, for the run schedule:
  - the due read (`TopicsRepository.due_topics` and `topics.next_occurrence`) and the preparation (`DigestPreparation.prepare`, `TopicsRepository.prepare_run`): no stub, spy or replacement stands between the scheduler and the store, and every assertion reads the stored row;
  - the run guards: the instant's immutability is shown by the real refused `UPDATE`;
  - the settings save and the zone change in the "later change" and "zone change" tests: the owner's real `save_settings` with its authority and revision, and `GuardedSettingsService.update`, never `topics_flow.make_due`'s direct `UPDATE`;
  - the state moves in the repository tests: `begin_send`, `finish_send` and the owner's resolution, never an `UPDATE` of `state`;
  - the time zone rules: the clock-change days are found from the zone database for the first transition after the run clock, and no offset is faked.
- **Mocking and stubbing guidance > Clock.** The one injected value is the pass's instant: `scheduler._now` is assigned, as `topics_flow.build` already does, and the same instant reaches the SQL selection and the Python window. No assertion compares the stored instant with `created_at`, `updated_at` or `clock_timestamp()`: a run is "late" by the injected pass clock only, and the stored instant may be later than the row's creation.

- **Test data management.**
  - The component tests take every date from one reading of the realm's clock (`calendar_flow.run_clock`), as `test_schedule_preferences.py` does, so none can fall behind the calendar. They need no paper: a window with no content records an empty digest, and the instant is stored at the insert either way.
  - No test puts a zone back. The new component tests change an owner's zone through `calendar_flow.schedule`, as the calendar tests do. The owner fixtures set each owner's zone to UTC before every test that takes them (`tests/u5_topics_digests/conftest.py:83-87`), which stamps a new zone boundary; a test that takes no owner fixture meets the zones as `test_schedule_preferences.py` already leaves them today.
  - The repository tests prepare explicit past windows, as `repository/test_preferences.py` does, with content given directly so that a send can start, and hand in an instant that differs from the window's day at the topic's current delivery time in the owner's zone, so that a reading worked out from the current settings cannot pass by coincidence. They read the owner's preferences through the topics login for the fence.
  - Other tests leave pending runs in a shared realm, and the browser fixtures leave a seeded unknown run with no instant. Every assertion names its own run identifiers.
  - The browser fixtures' seeded run is an insert that names no instant (`scripts/u5_browser_fixtures.py:274-278`), the path the database test's second run takes. The operator's on-demand prepare hands in none (`scripts/u5_real_delivery.py:267`), the path of repository test 2 one call further in. No test reads those two rows' column, and the "Run schedule" row above does not claim them.
  - The new tests add no account: they use the two conftest owners.

- **Withheld checks (Step 48(a)).** Each new or extended test runs once with the behaviour it awaits withheld, outside any recorded run, before the recorded runs.
  - The form is the direct one, scoped to the files or nodes named, on a development realm that is archived with `archive-owned` afterwards. It carries Colima's pair, because some of the named nodes call the runner in the test's own process (`database/test_migration_digests.py:149` calls `runner.migrate`, which runs `docker … inspect`, `scripts/verify_docsuri_u5.py:704`, `:254-256`):

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config DOCSURI_U5_ENVIRONMENT_FILE=/tmp/docsuri-u5-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini -q --tb=short <files or nodes>
    ```

    A runner phase stops at its first failure and fails on a source change during its run, so a phase is used for a withheld run only with one behaviour withheld per fresh realm.
  - Every restore is unconditional. Each check copies the file it edits to `~/.docsuri-u8/lead-scripts/l4-records/withheld/`, records its SHA-256, makes the one edit by content (a replacement that asserts exactly one occurrence), runs the tests keeping their exit code, copies the file back whatever the result and confirms an equal SHA-256. No restore is confirmed by `git diff`.
  - The checks, each recorded with the failure it gave:
    - W1a, the migration with old rows filled from `created_at` and its guard not comparing the instant, its header unchanged: a scratch realm is set up and migrated while `u5_scheduled_instant.sql` holds those bytes, and `database/test_preference_schema.py` and `database/test_chain_upgrade.py` run directly before the file is restored. The new database test fails at its first refused change, and the two extended upgrade tests fail. `test_migration_digests.py` is not run on that realm, where it would fail for the wrong reason. The realm is archived and never used again.
    - W1b, the migration with its guard comparing the instant but written without `SET search_path=pg_catalog`: a second scratch realm is set up and migrated while the file holds those bytes, and `database/test_preference_schema.py` runs directly before the file is restored. The new database test passes its refusals and fails at its read of the function's settings. The realm is archived and never used again.
    - W2, the old chain (`MIGRATIONS` without the new entry): `test_the_u5_chain_appends_exactly_the_pinned_files_in_order` and `test_migration_chain_is_append_only_and_present` fail, with no realm. On a third scratch realm, set up and migrated by the old chain and given no fixtures, `test_the_realm_receipts_equal_the_pins_and_every_chain_file` and the `newest-repair` case fail. The receipts test fails at its first comparison (`database/test_migration_digests.py:124`), and the `newest-repair` case at `before[relative]` (`:144`) with a KeyError, before the runner's refusal it awaits, because the old chain recorded no receipt for the file. That is the expected failure here: it shows the case reads the new file's receipt. No other test runs on that realm, which is archived.
    - W3, one byte added to `u5_scheduled_instant.sql`: `test_every_applied_u5_file_keeps_its_pinned_bytes` fails, with no realm.
    - W4, `prepare_run` takes the instant and does not store it: repository tests 1, 5, 6, 7 and 8 fail, test 6 in each of its three cases; tests 2, 3 and 4 pass.
    - W5, `prepare_run` stamps the present time when it is handed no instant, and no longer checks what it is handed: repository tests 2 and 3 fail, test 3 in each of its three cases.
    - W6, `prepare_run` skips its comparison with `expected_preferences`: repository test 4 fails.
    - W7, the scheduler hands in the pass's clock instead of the due instant: the three component tests fail, each case with its own instants in the message.
    - W8, the preparation drops the instant: the three component tests fail, each finding none stored.

    W4 to W8 run on one development realm prepared with `setup`, `migrate` and `fixtures`.
  - A test whose withheld run has not happened is recorded as not run and is not said to catch its defect. A withheld run that passes, or fails somewhere other than expected, is recorded as found.

- **What never counts as success.**
  - A test that only finds the instant present: each one compares it with an instant worked out independently of the code under test.
  - An instant read from `created_at`, from the pass's clock or from the topic's current settings.
  - An old run, a fixture run or a demonstration run given an instant it never had.
  - U8's `verification-run` passing, taken as proof that the instant is stored: it shows only that preparation still works on the composed chain.
  - U8's `database` phase passing, taken as proof that the chain entry is present.
  - A phase with a skip, an error, zero tests or a missing report, or a run on an environment whose container was not confirmed in Colima.
  - A lowered floor, a longer bound, a changed byte in an applied migration or in a kept file, or an environment migrated in place across the new chain entry. U5's and U6's tools do not refuse that last one; the rule does.
