# U5 code summary — topics & digests

## Build and Test loop-back 4 (2026-11-22)

Build and Test's fifth run ([test-results.md](../../build-and-test/test-results.md),
Target Verification Matrix, Outcome and Loop-Back Log entry 4) passed every U5 lane and
ruled none of U5's targets Not Met. It left two of U8's targets Not Met, `U8:NFR9.2` and
`U8:NFR9.2:export-digest-degraded`, for a reason only U5's stored data can remove: a
`sending` or `unknown` run whose topic's settings changed after it was prepared cannot
be counted from its scheduled time, because U5 recorded no run's scheduled instant
(group U8-A2). The maintainer chose "Retry with fix" on 2026-11-22, **beyond the bound
of three loop-backs** (the question stated "Loop-backs used: 3/3" and offered that
choice only as an override of the bound), and approved the loop-back plan
(`code-generation-plan.md`, Steps 40–48) with "Approve Plan" on 2026-11-22. The fix is
option 2 of L3-3 in U8's plan, which **reverses the option 1 chosen there**: U5 records
each run's scheduled instant when it prepares the run, and U8's digest producer counts
a re-set run from it. Code Generation is reopened for U5 first and for U8 after it, so
this section records U5's half only: the record, and the contract U8 reads. Unlike
loop-backs 2 and 3, this one changes production code.

### Decisions and scope (Step 40)

L4-1 and L4-7 are the maintainer's choices, made by approving the plan as written;
L4-2 to L4-6 were proposed with the plan and approved with it.

- **L4-1 (the maintainer's choice, option 1): the scheduled instant is a new column,
  `topics.digest_run.scheduled_at`,** added by a new U5 migration,
  `backend/modules/topics/u5_scheduled_instant.sql`, of three statements: the column
  (`timestamptz`, nullable, no default, no backfill, no CHECK); `CREATE OR REPLACE` of
  `topics.guard_preparation_snapshot()` with its header, message and ERRCODE word for
  word and `scheduled_at` added to both sides of the compared tuple; and `REVOKE ALL …
  FROM PUBLIC`. It adds no table, function, sequence, index or grant. Turned down:
  option 2, a `scheduledAt` key inside the run's `preference_snapshot` (the snapshot is
  the owner's preferences and the instant depends on the topic's settings; untyped JSON
  text U8 would cast inside a required capability's statement; no place for it on a run
  with no snapshot; shown under "preferenceSnapshot" by the operator's preview); a side
  table or settings-history table; a new SQL function U8 calls; the database or
  `prepare_run` computing the instant; storing the delivery time; and the
  `presentation` or `digest_content` fields.
- **L4-2, what is stored, and a run with no value.** The value is the `due_at` that
  `topics.next_occurrence` returned for the occurrence whose `window_day` is the run's
  `window_end`: the first valid instant at which the owner's confirmed zone reads that
  day at the topic's delivery time, across a missing or a repeated wall minute. The
  scheduler hands it to `DigestPreparation.prepare`, which hands it to
  `TopicsRepository.prepare_run`, as a new keyword argument `scheduled_at` that defaults
  to none; nothing copies the rule. `prepare_run` accepts an instant only together with
  `expected_preferences` and refuses one that has no zone or is not a date-time, with
  `INVALID_ARGUMENT` on `scheduledAt`. It is set once: an adopted run keeps its own row
  and its first instant, a run prepared again after a discard is a new row with its
  own, and with the replaced guard any `UPDATE` that changes the column raises 23514, a
  change from none to a value included. A run no due occurrence prepared holds SQL NULL
  and nothing fills it in later: the operator's on-demand prepare, the browser
  fixtures' seeded run, a direct `prepare_run` call or insert in a test, and every row
  stored before the file. Production starts empty and prepares only through the
  scheduler, so it holds no such run. No CHECK on the column (the scheduler's clock may
  run ahead of the database's; a gap can skip a whole calendar date). It is not shown
  to the owner: `RUN_COLUMNS` gains the column, the owner's two reads keep their
  explicit column lists, and `http.py` does not change. The name is `scheduled_at`.
- **L4-3, the one file of another Unit.** `backend/u8_migrations.py` gains one entry,
  `("topics", "backend/modules/topics/u5_scheduled_instant.sql")`, in `LATER_UNITS`
  after `u5_refusal_detail.sql` and before `u6_lifecycle_guard.sql`, with a short
  comment above it; nothing else in that file changes. It is in U5's build because
  U5's checkpoint is U8's `verification-run` on U8's composed chain, a written list:
  without the entry the realm migrates cleanly, has no such column, and J02's first
  preparation fails. It is inserted in U6's applied order, not appended, so a U8 realm
  migrated before this build is set up fresh, never migrated in place. U5's manifest
  claims the path too, so any later U8 edit of that file stales U5's review. Kept
  bytes: `backend/u5_policy.py`, `backend/modules/topics/delivery.py`,
  `backend/u5_real_delivery.py`, `backend/.coveragerc.u5`,
  `frontend/vitest.u5-topics.config.ts`, `backend/modules/topics/http.py` and
  `backend/u5_host.py` do not change. If anything needs another change in a file of
  another Unit, the build stops and the finding goes to the maintainer.
- **L4-4, the tests: five to eight per changed component,** counted as L3-1 counts
  them: `database/test_preference_schema.py` 6, then 7; a new
  `repository/test_scheduled_instant.py`, 8; `component/test_topics_scheduler.py` 5,
  then 8 (`DigestPreparation.prepare` only passes the instant on and is counted with
  the scheduler); `database/test_chain_upgrade.py`, `database/test_migration_digests.py`
  and `operations/test_runner_bindings.py`, 5 each, extended under their own names. The
  composed chain's one entry has no U5 test: Step 41's realm-free read checks it, and it
  is counted in U8's volume. 12 new test functions, 18 collected items; the collect-only
  total is expected to go from 331 to 349.
- **L4-5, the lanes follow the reach rule (U8's L2-18).** Step 48 runs all of U5's
  lanes, each test phase on its own fresh realm; U6's `coverage` and `browser` on two
  fresh U6 environments with U6's own tool (its `component` and `integration` phases are
  not run as lanes of their own); and U8's `database` phase once on a fresh U8 realm.
  Every other U8 lane runs in U8's reopened build. U1's to U4's and U7's lanes, U6's
  `frontend` phase, type check and ESLint, the shared contract checks and next-app's
  dependency check stand, because no file they reach changes.
- **L4-6, the contract U8 consumes.** Recorded word for word, with the list owed to
  U8's plan, under "Records (Step 47)" below.
- **L4-7 (the maintainer's choice): U5's browser-only checks (U5-C2) are not built
  here.** `U5:NFR5.1` (the list's and the resolve control's live-region messages and
  the Korean names of their buttons), the frontend states and the defaults label of
  the preference inheritance stay Unverified for their browser-only clauses and are
  said at Build and Test's gate again.

**Design correction.** `functional-design/entities.md`'s DigestRun gains `scheduledAt`:
a timestamp, optional; the due instant of the occurrence the run was prepared for; set
once; absent for a run no schedule prepared. The approved file is not edited; this
record carries the correction.

**What this build does not show.**

- No U8 target changes until U8 is rebuilt: `U8:NFR9.2` and
  `U8:NFR9.2:export-digest-degraded` keep their verdicts, and U8's digest producer still
  reads what it read before.
- The bounded real send that Steps 13 and 14 name is not repeated, because this plan
  authorizes no external message. Its evidence (`traceability.json` >
  `real_delivery_evidence`) is of the source before this change.

**First reading of the seven kept files (L4-3), taken 2026-11-22T06:08:31Z, before any
edit** (`shasum -a 256`, from the repository root):

| File | SHA-256 |
|---|---|
| `backend/u5_policy.py` | `5bb52c4c198035f7de5c6e685c9a0fab8ce246670733dae0571b980a7f91246b` |
| `backend/modules/topics/delivery.py` | `16680a8a6cd14d1c881544c1ff760066fe8494151e54c04157d9974e2def0095` |
| `backend/u5_real_delivery.py` | `a114e9332910317141d6e16a4066aa17cfbb84189c321e96d404d4a023ebd56b` |
| `backend/.coveragerc.u5` | `82719aa662846316da910756c97a255173b39ef00b8fa2e52dcec0f49b8182d5` |
| `frontend/vitest.u5-topics.config.ts` | `856a400fc49cf9219812ae3c1b1b2af224d8c91c98c733fcf497311c0ed826d0` |
| `backend/modules/topics/http.py` | `a5e172d60c9c535cbcf52578c0413f87483e8fa6f1b5db6a2e4982ea3a34927b` |
| `backend/u5_host.py` | `618c859516db4c6a88b784b51625e2180d0786becb6c056049a7bc90c1cf03f2` |

**First collect-only run, 2026-11-22T06:08:33Z, before any edit and before any new
test was written:** `backend/.venv/bin/python -m pytest -c
backend/pytest.u5-topics-digests.ini --collect-only -q tests/u5_topics_digests`
collected **331 tests** (0.74 s), the count loop-back 3 left.

### What was built (Steps 41–46, 2026-11-22)

- **Step 41, data model.** (a) `backend/modules/topics/u5_scheduled_instant.sql` (new,
  SHA-256 `49982d27a43cad0bbc9c0e7cf03744bd3fa38ca97d53b9fff9eda38d0c639c12`): the
  three statements of L4-1, with the first-line comment that NULL marks a run no
  schedule prepared, never an invented instant. No applied file changed. (b)
  `scripts/verify_docsuri_u5.py`: `MIGRATIONS` gains the file last. (c)
  `backend/u8_migrations.py`: `LATER_UNITS` gains the same entry after
  `u5_refusal_detail.sql`, with a three-line comment above it (four lines added in
  all); nothing else in that file changed. **Step 41(c) changed a file that only U8's manifest claimed until this
  build; U5's manifest now claims it too.** The realm-free read of the instructions
  exited 0, and a fresh U5 realm migrated 66 files in order.
- **Step 42, its tests.** `database/test_preference_schema.py` gains
  `test_a_runs_scheduled_instant_is_set_once_and_never_changes`;
  `database/test_migration_digests.py` pins the new file's bytes and the
  `newest-repair` case names it; `database/test_chain_upgrade.py` holds seven repairs
  and 66 migrations, reads the new column on the eight old runs and tries to set an old
  run's instant; `operations/test_runner_bindings.py` lists the file last.
- **Step 43, repository.** `backend/modules/topics/repository.py`: `RUN_COLUMNS` gains
  `scheduled_at`; `prepare_run` takes `scheduled_at=None`, refuses with
  `INVALID_ARGUMENT` on `scheduledAt` an instant that is not a date-time, has no zone or
  comes without `expected_preferences`, and writes the value in its insert. The
  adoption paths, the owner's two reads and every state move are as they were.
- **Step 44, its tests.** `repository/test_scheduled_instant.py` (new): the eight
  tests of the plan, 12 collected items.
- **Step 45, business logic.** `DigestPreparation.prepare` takes `scheduled_at=None`
  and passes it on; `TopicsScheduler._evaluate_due` passes the due row's `due_at`. No
  other caller changed.
- **Step 46, its tests.** `tests/u5_topics_digests/calendar_flow.py` (new) holds the
  nine calendar helpers and constants, moved unchanged from
  `component/test_schedule_preferences.py`, which imports them (its seven tests are
  unchanged); `component/test_topics_scheduler.py` gains the three tests of the plan
  (five items), last in the file.

### Records (Step 47)

**Each changed component's tests, before and after** (functions; collected items in
brackets where they differ), from the collect-only run on the source as Step 46 left
it (2026-11-22T06:27:26Z, **349 tests collected**, 331 before):

| Component | File | Before | After |
|---|---|---|---|
| Additive preparation evidence | `database/test_preference_schema.py` | 6 | 7 |
| Chain upgrade | `database/test_chain_upgrade.py` | 5 | 5 (2 extended) |
| Applied migration bytes | `database/test_migration_digests.py` | 5 [6] | 5 [6] (pins extended) |
| Runner bindings | `operations/test_runner_bindings.py` | 5 | 5 (1 extended) |
| A run's scheduled instant (`TopicsRepository`) | `repository/test_scheduled_instant.py` | new | 8 [12] |
| The due path: scheduler and preparation | `component/test_topics_scheduler.py` | 5 [6] | 8 [11] |
| Calendar occurrence rules | `component/test_schedule_preferences.py` | 7 | 7 (helpers moved out) |
| U8's composed chain, one entry | U8's `database/test_composed_chain.py` | U8's (15) | U8's (15), no U5 test |

12 new test functions, 18 collected items: 1 database, 8 [12] repository, 3 [5]
scheduler.

**Order of work (test-after; each layer's implementation finished before its tests
were written).** Times are UTC on 2026-11-22, from `date -u`.

| Step | Finished | Evidence |
|---|---|---|
| 40, first kept-bytes reading | 06:08:31 | seven digests above |
| 40, collect-only before any new test | 06:08:33 | 331 collected |
| 41, migration and both chain entries | 06:12:59 | realm-free read of the composed chain, exit 0 |
| 41, applied on a fresh realm | 06:13:44 | realm `docsuri-u5-b46b8e0d42f246aa`: `setup`, `migrate` exit 0, 66 migrations |
| 42, database tests written, first run | 06:15:29 | `--phase database` on that realm: exit 1, 24 run, 1 failed (see deviations) |
| 42, realm-free chain tests | 06:21:13 | 3 passed, exit 0 |
| 42, database phase | 06:22:54 | fresh realm `docsuri-u5-f469cec76b5b59ce`: exit 0, **34 passed**, 0 failed, 0 errors, 0 skipped |
| 43, repository | 06:23:18 | Ruff clean |
| 44, repository tests | 06:24:37 | `--phase repository` on `docsuri-u5-f469cec76b5b59ce`: exit 0, **51 passed**, 0 skipped |
| 45, preparation and scheduler | 06:24:56 | Ruff clean |
| 46, component tests | 06:27:09 | `--phase component` on `docsuri-u5-f469cec76b5b59ce`: exit 0, **141 passed**, 0 skipped |
| 46, collect-only on the source as left | 06:27:26 | 349 collected |

Both realms' containers were confirmed through Colima's socket after `setup`
(`docker ps --filter label=dev.docsuri.u5.run`), and every tool command carried
Colima's pair and ran under umask 077. These are development runs; the recorded lanes
on fresh realms are Step 48(b)'s.

**Deviations in Steps 41–46.**

- The first `--phase database` run (realm `docsuri-u5-b46b8e0d42f246aa`) failed in the
  new test itself: its catalog read sorted the function's grants with `ORDER BY 1`,
  which orders by a constant inside an aggregate, so the two grants came back in the
  catalog's order and the comparison failed. The refusals and the function's settings
  had passed. The test now sorts the grants in Python. The realm is kept as a failed
  attempt, preserved at
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-b46b8e0d42f246aa-6e7dbfb5`, and the
  phase was rerun on a fresh realm; it is not relabelled.
- That first realm also had `fixtures` run before `database`, as the instructions'
  fresh-realm list has it; so did the second.
- `ruff format --check` would reformat `backend/modules/topics/repository.py` at
  `begin_send`'s signature, lines this build did not write. It is recorded, not fixed
  (CI runs `ruff check` only; project rule of 2026-10-28). The files this build
  created are formatted.
- **`tests/u5_topics_digests/repository/test_scheduled_instant.py` changed after its
  `--phase repository` run, and no whole `repository` phase has run on its final bytes
  yet.** The 51-passed run of 06:24:37 was of the file at SHA-256
  `8883f71e99cae39c326042eb811493d61770122746b8c737a9d3e26c0f4b9fe2` (the digest the
  independent review gives for those bytes). Two formatter line joins followed at
  06:26:42–43 (line 83, the set comprehension in `wall_instants`; line 87, the first
  test's signature), giving
  `a10265d372c8db1d7c5a91dc038bf5efd99a2fd098aa925c3485fc61fe78e0a9`; the withheld
  checks W4, W5 and W6 ran the whole file directly at those bytes. A review fix at
  07:04:03 then removed three lines from `test_a_run_prepared_without_an_instant_holds_none`
  (a comment and two assertions that were always true once the value was required to
  be None, one of which compared the stored instant with `created_at`, against the
  instructions' Clock rule), giving the final
  `976e5ef562a99b759a055bfc2c0cb27d7af35b1147d86a8705e0bd6b1cc99ac4`. The item names
  are unchanged (12; collect-only still 349, Ruff clean), and W5's recorded failure
  line (`:108`) is unchanged. Step 48(b)'s `repository` lane on a fresh realm is the
  first whole run of the final file.

**The contract U8 consumes (L4-6), word for word.** `topics.digest_run.scheduled_at`, a
`timestamptz`: the due instant of the occurrence the run was prepared for, set once at
insert and never changed. It is not NULL for every run U5's scheduler prepared, whatever
happens to the topic's settings or the owner's zone afterwards, and whatever state the
run is in. It is NULL for a run no due occurrence prepared and for a row older than the
file; production cannot hold one. It may be later than the run's `created_at`. U8 reads
it in its own statement under the topics login, as it reads `state` and `updated_at`
today (`backend/modules/operations/producers.py:188-212`, `:251`), and writes nothing.
For a NULL row U8 states its own fallback; today's arms of `DIGEST_RUNS` are that
fallback.

**Owed to U8's plan** (the privilege pin's result is added by Step 48):

- the producer's statement and its comments;
- the M and P cases of U8's Step 146 and a NULL case for the fallback;
- the withdrawal of U8's correction 184 and record 113;
- U8's coverage of the new lines in the two files its report measures
  (`backend/modules/topics/scheduler.py` and `repository.py`);
- U8's records of a chain entry inserted mid-list;
- that both manifests now claim `backend/u8_migrations.py`, so any further U8 edit of
  it stales U5's review (L4-3);
- that nothing compares U8's copy of U5's files with U5's `MIGRATIONS`, so a missing
  entry fails only in a journey;
- that every U8 environment set up before U5's build is archived and set up again,
  none migrated in place;
- that U6's `component` and `integration` phases were not run as lanes of their own in
  U5's build (L4-5);
- the realm privilege pin, added by Step 48(d): U8's `database` phase passed on a fresh
  U8 realm with the new chain entry, `test_every_realm_logins_privileges_equal_the_pinned_inventory`
  among its 51 tests, so the pin did not move and nothing is owed for it.

Noted for U8's plan, not owed by this build: `backend/u8_registry.py` derives the
`topics-digests` contribution's schema digest from its chain files, so that derived
value changed with the chain entry. Nothing pins it and no file needed an edit.

### Withheld-behaviour checks (Step 48(a), 2026-11-22)

Each new or extended test ran once with the behaviour it awaits withheld, outside any
recorded run, in the direct form of the instructions (Colima's pair, umask 077,
`DOCSURI_U5_ENVIRONMENT_FILE`). The five files the checks edit were copied once, at
06:30:54, before the first check, to `~/.docsuri-u8/lead-scripts/l4-records/withheld/`.
Each check made one edit by content, ran the tests keeping their exit code, copied the
file back from that backup whatever the result, and confirmed the SHA-256 below. No restore was confirmed by `git diff`. Times are UTC.

| File restored after each check | SHA-256 before the edit and after the restore |
|---|---|
| `backend/modules/topics/repository.py` | `742cbcbbe8b9b93291c3dfe83e05adc90cc7d5849d842027a65c25bd61ccae6e` |
| `backend/modules/topics/scheduler.py` | `d80e9b4cd1c521ca3ecfc13a9d5a73dcd8fd1c4351d0b5a6b492be99e5230790` |
| `backend/modules/topics/preparation.py` | `3bf0ccc2996bc3223763095f5f3378038d4b7d76b8625b4096892486193a6699` |
| `backend/modules/topics/u5_scheduled_instant.sql` | `49982d27a43cad0bbc9c0e7cf03744bd3fa38ca97d53b9fff9eda38d0c639c12` |
| `scripts/verify_docsuri_u5.py` | `5778f710a00a208e880da81077938039d6d3f1e5cdc2254ce016e4d19626454c` |

W4 to W8 ran on the development realm `docsuri-u5-f469cec76b5b59ce` (`setup`,
`migrate`, `fixtures`; it had already run the three layer phases of Steps 42, 44 and
46), archived afterwards.

| Check | Withheld | Expected | The failure it gave | As expected |
|---|---|---|---|---|
| W1a (scratch realm `docsuri-u5-5a56ee2bc08868b9`, `setup` and `migrate` with the withheld bytes, 66 migrations, no fixtures), 06:37:02 | the migration fills old rows from `created_at` and its guard does not compare the instant; its header unchanged | the new database test fails at its first refused change; the two extended upgrade tests fail | 3 failed, 9 passed over `database/test_preference_schema.py` and `database/test_chain_upgrade.py`: `test_a_runs_scheduled_instant_is_set_once_and_never_changes` (`:108`, the first refused change), "DID NOT RAISE CheckViolation"; `test_the_upgrade_keeps_every_pre_repair_row_and_receipt` (`:355`), the eight old runs hold their creation times, not None; `test_old_rows_keep_their_constraints_and_guards` (`:418`), "DID NOT RAISE CheckViolation". `test_migration_digests.py` was not run on that realm, which was archived and not used again | yes |
| W1b (scratch realm `docsuri-u5-3dcc0e10bfe3a22e`, `setup` and `migrate` with the withheld bytes, 66 migrations, no fixtures), 06:39:59 | the migration's guard compares the instant but is written without `SET search_path=pg_catalog` | the new database test passes its refusals and fails at its read of the function's settings | 1 failed, 6 passed over `database/test_preference_schema.py`: `test_a_runs_scheduled_instant_is_set_once_and_never_changes` (`:124`, the catalog read, after every refusal and state move had passed): the function's settings are None, not `['search_path=pg_catalog']`; owner, definer flag and grants equal. The realm was archived and not used again | yes |
| W2 (no realm), 06:32:57 | `MIGRATIONS` without the new entry | the two chain tests fail | `test_the_u5_chain_appends_exactly_the_pinned_files_in_order` (`test_migration_digests.py:118`) and `test_migration_chain_is_append_only_and_present` (`test_runner_bindings.py:49`): AssertionError, "Right contains one more item", the new file; 2 failed | yes |
| W2 (scratch realm `docsuri-u5-d54f7c922897d078`, `setup` and `migrate` by the old chain, 65 migrations, no fixtures), 06:34:57 | the same | the receipts test fails at its first comparison; the `newest-repair` case fails with a KeyError before the runner's refusal | `test_the_realm_receipts_equal_the_pins_and_every_chain_file` (`:129`, its first comparison): the realm's receipt for the new file is None, not the pin; `test_the_runner_refuses_an_applied_file_whose_bytes_differ[newest-repair]` (`:149`, `before[relative]`): `KeyError: 'backend/modules/topics/u5_scheduled_instant.sql'`; 2 failed. No other test ran on that realm | yes |
| W3 (no realm), 06:32:34 | one byte added to `u5_scheduled_instant.sql` (957 bytes for 956) | the pinned-bytes test fails | `test_every_applied_u5_file_keeps_its_pinned_bytes` (`:123`): the file's digest `094b8b28…` is not the pin `49982d27…`; 1 failed | yes |
| W4, 06:31:10 | `prepare_run` takes the instant and does not store it | repository tests 1, 5, 6 (three cases), 7 and 8 fail; 2, 3 and 4 pass | 7 failed, 5 passed: tests 1, 5, 6 `[a_new_delivery_time]`, `[a_weekly_cadence]`, `[another_zone]`, 7 and 8, each an AssertionError finding `scheduled_at` None where the handed instant was expected; tests 2, 3 (three cases) and 4 passed | yes |
| W5, 06:31:28 | `prepare_run` stamps the present time when handed no instant and checks nothing it is handed | repository tests 2 and 3 (three cases) fail | 4 failed, 8 passed: test 2 (`:108`), the returned instant is the present time, not None; test 3 `[no_zone]`, `[a_string]` and `[no_preference_fence]` (`:144`), each "DID NOT RAISE TopicsError" | yes |
| W6, 06:31:46 | `prepare_run` skips its comparison with `expected_preferences` | repository test 4 fails | 1 failed, 11 passed: `test_an_instant_from_a_due_read_made_before_a_zone_change_is_refused` (`:162`), "DID NOT RAISE TopicsError" | yes |
| W7, 06:31:57 | the scheduler hands in the pass's clock | the three component tests fail, each case with its own instants | 5 failed of 5: daily (stored 2026-11-23 23:17, occurrence 23:00); three days late (stored 2026-11-27 01:00, occurrence 2026-11-23 23:00); weekly on the next local day (stored 2026-11-30 03:00, occurrence 2026-11-28 23:00); the day with no 02:30 (stored 2027-03-14 07:10, occurrence 07:00); the day with two 01:30s (stored 2027-11-07 06:35, occurrence 05:30); all UTC, each stored value equal to the pass clock | yes |
| W8, 06:32:09 | the preparation drops the instant | the three component tests fail, each finding none stored | 5 failed of 5, each "stored None" beside its own occurrence and pass clock | yes |

One run made before W3 is not a withheld run and is not counted: a first edit that
added only a trailing space was not applied by the editing tool, so the test ran on
the unchanged file and passed (06:32:22). W3 was then made with a visible byte.

All nine checks (W1a, W1b, W2 to W8) ran and each failed where the instructions said
it would; none is recorded as not run. After the last check every edited file was
compared byte for byte with its backup (`cmp`) and holds the digest in the table
above. Every restore was made by copying the backup back; no hook refused a copy, so
none was made with the editing tool.

**Realms set up in this build** (all confirmed through Colima's socket after `setup`,
all archived with `archive-owned`; `/tmp/docsuri-u5-run` is absent afterwards):

| Realm | Used for | Preserved at |
|---|---|---|
| `docsuri-u5-b46b8e0d42f246aa` | Step 41's `setup` and `migrate`; `fixtures`; the first `database` run, failed (a failed attempt, kept) | `/private/tmp/docsuri-u5-preserved-docsuri-u5-b46b8e0d42f246aa-6e7dbfb5` |
| `docsuri-u5-f469cec76b5b59ce` | `database` 34, `repository` 51, `component` 141, all passed; W4 to W8 | `/private/tmp/docsuri-u5-preserved-docsuri-u5-f469cec76b5b59ce-bdf5b4cd` |
| `docsuri-u5-d54f7c922897d078` | W2 (old chain, 65 migrations) | `/private/tmp/docsuri-u5-preserved-docsuri-u5-d54f7c922897d078-a4d78222` |
| `docsuri-u5-5a56ee2bc08868b9` | W1a | `/private/tmp/docsuri-u5-preserved-docsuri-u5-5a56ee2bc08868b9-41e83cdb` |
| `docsuri-u5-3dcc0e10bfe3a22e` | W1b | `/private/tmp/docsuri-u5-preserved-docsuri-u5-3dcc0e10bfe3a22e-3564525e` |

### An independent check before the recorded runs (2026-11-22)

Before any recorded run, four read-only reviewers read the build against the plan (the
migration and the chains; the Python path from the due read to the insert; the tests;
scope and records), and a second reader challenged each finding. They found no defect in
the migration, the two chain entries, the three pins or the Python path, and confirmed
that exactly the 14 listed paths changed and the seven kept files did not. Four points
stood, all Minor, and were fixed at 07:04, before the recorded runs: the two always-true
assertions removed from repository test 2 (see the deviations above), and three record
corrections (the chain comment's line count, the test file's three digests, and when the
withheld checks' backups were taken). One point was turned down on challenge: the
registry's derived digest, noted above for U8's plan.

### Recorded runs (Step 48(b) to (e), 2026-11-22)

Run by the coordinator on the final source, after the review fix of 07:04:03, with no
editor-hook marker pending, under umask 077 and with Colima's pair on every tool
command. Times are UTC.

One driver ran U5's and U6's lanes in sequence, from 07:05:43 to 07:19:24: 68 steps
passed, 2 were not needed (no left environment to archive first) and none failed. Its
logs are in `~/.docsuri-u8/lead-scripts/final-lanes/lb4-run-20261122-160543-47637/`.
After each `setup` the environment's container was listed by Colima's Docker before
anything else ran; each environment was archived with `archive-owned` after its phase,
and 90 s passed before the same tool's next `setup`. Every preserved folder is kept in
`~/.docsuri-u8/final-evidence/`.

**U5's lanes (Step 48(b)).** The five test phases report one source digest,
`677ff8c8ba406225dd30b436a3e3418095806ef96eab6b91bd9952bd6303de92`, so no source changed
between them.

| Lane | Environment | Result |
|---|---|---|
| `database`, its own fresh realm | `docsuri-u5-46db7ef218d872ba` | exit 0; 34 tests, 0 failures, 0 errors, 0 skipped |
| `repository`, its own fresh realm | `docsuri-u5-358d8b3b8bc2d6d2` | exit 0; 51 tests, 0 failures, 0 errors, 0 skipped. The first whole run of `repository/test_scheduled_instant.py` at its final bytes (`976e5ef5…`) |
| `component`, its own fresh realm | `docsuri-u5-999dbe9bd60477dc` | exit 0; 141 tests, 0 failures, 0 errors, 0 skipped |
| `coverage`, its own fresh realm | `docsuri-u5-4fb6b608fdbe0be1` | exit 0; 349 tests, 0 failures, 0 errors, 0 skipped; 85.27% (floor 80.0) |
| `browser`, its own fresh realm | `docsuri-u5-c51a7a231e4d49c3` | exit 0; 9 tests, 0 failures, 0 errors, 0 skipped; among them "a follow reaches a delivered digest through the scheduler and local sink" |
| Vitest, `vitest.u5-topics.config.ts --coverage` | — | exit 0; 36 passed in 5 files; `src/u5-topics/**` 98.47% of lines (floor 80) |
| `tsc --project tsconfig.u5-topics.json --noEmit --incremental false` | — | exit 0 |
| ESLint, U5's CI step (`src/u5-topics src/App.tsx src/api.ts test/u5-topics e2e/u5-topics-digests` and the two configs) | — | exit 0 |
| Ruff check `--no-cache`, U5's CI list | — | exit 0, all checks passed |
| Ruff check `--no-cache backend/u8_migrations.py` | — | exit 0, all checks passed |
| `operations/test_archive_expiry.py` | — | exit 0; 31 passed |
| collect-only | — | exit 0; 349 tests |

`integration/test_real_delivery.py::test_operator_tool_prepares_and_previews_without_sending`
ran in the `coverage` lane and passed, as contract evidence only; nothing was sent.

**U6's lanes (Step 48(c)),** with U6's own tool and no U6 file changed. Both report the
source digest `1768c2930559e60b85d5463839bb3f5ff2e54b043e5494a641e8beb82bf2ba06`.

| Lane | Environment | Result |
|---|---|---|
| `coverage`, a fresh U6 environment | `docsuri-u6-95e11476dcb2d837` | exit 0 under U6's own floors; 949 tests, 0 failures, 0 errors, 0 skipped; 90.0% in total |
| `browser`, a second fresh U6 environment | `docsuri-u6-9663859e2188872c` | exit 0; 14 tests, 0 failures, 0 errors, 0 skipped |

U6's `component` and `integration` phases were not run as lanes of their own (L4-5):
`coverage` ran their folders.

**U8's `database` phase (Step 48(d)),** on a fresh U8 realm, `docsuri-u8-0db0a9d69269e682`,
from 07:20:17 to 07:20:25. Free disk read 30.75 GiB by `df` before `setup`, above the
22 GiB working floor; the container was listed by Colima's Docker after `setup`; the
log is `~/.docsuri-u8/lead-scripts/final-lanes/lb4-u8-database-20261122.log`.

- `setup` exit 0; `migrate` exit 0 with 138 migrations, so the composed chain applies
  with the new file.
- `database` exit 0: 51 tests, 0 failures, 0 errors, 0 skipped, among them the 15 of
  `database/test_composed_chain.py` and
  `test_every_realm_logins_privileges_equal_the_pinned_inventory`. The realm privilege
  pin did not move.
- As the plan says, this pass does not show that the chain entry is present: Step 41's
  read does (exit 0 at 06:12:59, and exit 0 again on the final source at 07:22:54), and
  J02 at the checkpoint will.
- The realm was archived; its preserved folder,
  `docsuri-u8-preserved-docsuri-u8-0db0a9d69269e682-e9eea715`, is kept in
  `~/.docsuri-u8/final-evidence/`.

**Second reading of the seven kept files (Step 48(e)),** taken at 07:05:43 as the
driver's first step: all seven SHA-256 values equal the first reading above.

**What these runs do not show.**

- U8's `verification-run` is the checkpoint's and runs through AI-DLC's checkpoint
  verifier after the review. Every other U8 lane runs in U8's reopened build.
- U1's to U4's and U7's lanes, U6's `frontend` phase, type check and ESLint, the shared
  contract checks and next-app's dependency check were not run: by the reach rule no
  file they reach changed. That rests on an import search, not on a run.
- No U8 target changes until U8 is rebuilt, and the bounded real send of Steps 13 and
  14 was not repeated.

### The plan's boxes in this attempt

The developer ticked Steps 40–47 after their runs. Step 48 is ticked with this record,
before the review and the checkpoint, as its own text says. This attempt's Plan
Approval cleared the boxes of Steps 1–39; their work stands and Step 48's runs exercise
it again, so they are ticked again, as the plan says. Steps 14, 15, 27, 33 and 39 ask
for a review and a checkpoint of their own attempts; those passed, and this attempt's
review and checkpoint stand in for them. Step 48's review and checkpoint run through
AI-DLC after the ticks.

## Build and Test loop-back 3 (2026-11-17)

Build and Test's fourth run ([test-results.md](../../build-and-test/test-results.md),
Target Verification Matrix, Outcome and Loop-Back Log entry 3) passed every U5 lane
but left `U5:code-generation-plan:testing-contract-strategy-volume` Not Met (eight
changed-component files outside five to eight for reasons other than races), and
NFR5.1 and the preference inheritance Unverified for clauses no test checked: no
settings-form control was found by its Korean name, the populated topic list had no
axe, reflow or focus check in a real browser, and no test read the `usesDefaults`
marker through the topic settings route. The maintainer chose "Retry with fix" on
2026-11-17 and approved the loop-back plan (`code-generation-plan.md`, Steps 34–39)
with "Approve Plan". Every step adds, moves or merges tests; Step 37 found no
settings-form control without a Korean accessible name, so no production file
changes. This section records the decision and scope (Step 34), the moves, merges
and new tests (Steps 35–38), the withheld-behaviour checks, local and realm-based, and
Step 39's fresh-realm lanes, all passed on 2026-11-17 UTC. The architecture review and
the checkpoint follow through AI-DLC after this record.

### Decisions and deviations (Step 34)

- **L3-1, every changed component holds five to eight tests (proposed with the plan,
  approved with it).** L2-1 split the runner's tests by part and merged nothing; the
  other changed components outside the range were `database/test_schema.py` 10,
  `repository/test_repository.py` 9, `repository/test_preferences.py` 10,
  `component/test_topics_logic.py` 13, `component/test_real_composition.py` 18
  functions (43 items), `integration/test_http.py` 11, `operations/test_phase_verdicts.py`
  4, and in `frontend/test/u5-topics/`, `announcements.test.tsx` 10, `topics.test.tsx`
  14 and `settings-dialog.test.tsx` 13. The fix runs in this order: (1) a file that
  checks several components is split, its tests moved unchanged, one file per
  component, as L2-1 did; (2) a component still above eight merges its same-rule cases
  into one test each, keeping every assertion and case (`pytest.mark.parametrize`
  over the original test bodies in Python, so each case stays its own collected item;
  in Vitest one test per rule that runs every case, since each `it.each` row counts as
  a test); (3) a component below five gains tests. No assertion or case is dropped or
  weakened. Merged tests fail less specifically, the trade-off L2-1 turned down for
  the runner; each merged Vitest test names the failing case in its message to soften
  it. The rejected alternative, amending U5's instructions to U8's rule (a component
  above eight carries its reason and is kept), would relax a defined target, which
  the stage file says is never an acceptable fix.
- **Shared test helpers (deviation from L2-1's repetition).** L2-1 repeated the one
  `owned_root` fixture in each new runner file. The files split here share far more
  (the mounted HTTP app and its six request helpers, the topics flow's eleven helpers,
  three transport doubles and the realm-quieting fixture, the real composition's
  activation builders and fake client), so they move, unchanged, into three helper
  modules beside the existing `real_send.py` and `source_scan.py`:
  `tests/u5_topics_digests/http_mount.py`, `topics_flow.py` and
  `real_composition_kit.py`. Each split file declares its own small fixture that calls
  the shared builder, as U6's `http_flows.py` does; the test bodies are unchanged.
- **Targets that stay as they are, and why.**
  - `U5:code-generation-plan:testing-contract-methodology-layers` and
    `U5:code-generation-plan:testing-contract-runner-step` (Unverified, owned by Build
    and Test) ask whether each layer was implemented before its tests and whether the
    unit-scoped command was recorded before the first test. No test can show the order
    of past work; only Code Generation's records do (the plan's ticked steps and Step
    2's recorded command, with "Process evidence (Step 24)"). This loop-back adds tests
    only and leaves those records as they are.
  - `U5:tech-stack-decisions:verification-notes-real-delivery` (Unverified, owned by
    deployment-execution) needs a bounded, authorized real send through the configured
    free adapter. Code Generation's record holds one (`traceability.json` >
    `real_delivery_evidence`); a later stage verifies it, and no change here can.
  - **The frontend states' remaining gap is browser-only.** The loading, empty,
    read-failure and degraded states, the stale-revision offer, the honest default
    labels, the late answer after an account switch and focus returning after the
    dialog closes stay checked in jsdom only (`topics-view.test.tsx`,
    `digest-settings.test.tsx`, `preferences.test.tsx`), and NFR5.1's remaining gap is
    likewise browser-only: the topic list's and resolve control's live regions and
    Korean names in Chromium. This plan adds neither (Build and Test's predicate
    exception covers browser-only gaps).

### Moves, merges and new tests (Steps 35–38, 2026-11-18)

- **Step 35, one file per component.** Every test moved with its body unchanged;
  the collect-only total stayed 327 and the Vitest total 49 after the moves. The new
  names keep each moved test's place in pytest's collection order (realm state carries
  from one file to the next): `test_http_owner_topics.py` before
  `test_http_settings_routes.py`, where `test_http.py` was; the three `test_topics_*`
  files where `test_topics_logic.py` was, with the participant's erasure last.
  - `integration/test_http.py` (11) → `test_http_owner_topics.py` (topics routes, 5)
    and `test_http_settings_routes.py` (C03 settings routes, 6); the unused `W1`
    constant was not carried over.
  - `component/test_real_composition.py` (18 functions, 43 items) →
    `test_real_activation.py` (activation and adapter, `u5_real_delivery.py`: 8, 33
    items), `test_real_host_binding.py` (host binding and policy, `u5_host.py` and
    `u5_policy.py`, with the operator's outcome view: 4) and
    `test_cancellation_origin.py` (`unsubscribe.py`'s public cancellation boundary: 6).
  - `component/test_topics_logic.py` (13 functions, 16 items) →
    `test_topics_scheduler.py` (scheduler: 5, 6 items),
    `test_topics_delivery_outcomes.py` (delivery outcomes with the owner's resolution
    and watermark: 7, 9 items) and `test_topics_withdraw_and_erase.py` (the lifecycle
    participant's disposition test: 1). The participant's six tests stay counted across
    files, as Step 33 counted them: 3 in `repository/test_lifecycle_participant.py`, 1
    each in `repository/test_lifecycle_isolation.py`, `integration/test_email_unsubscribe.py`
    and `test_topics_withdraw_and_erase.py`.
  - `frontend/test/u5-topics/topics.test.tsx` (14) and `settings-dialog.test.tsx` (13)
    → `topics-view.test.tsx` (10: states, follow and unsubscribe, resolution, last-digest
    copy) and `digest-settings.test.tsx` (17: topics.test.tsx's 'digest settings form'
    block and all 13 dialog tests). The dialog tests now share the file's
    `afterEach` that clears `localStorage`, which they never read.
- **Step 36, the inherited-defaults marker through the route.** Two tests in
  `test_http_settings_routes.py`: the second owner, with only its saved language and
  level removed for the test and the row put back exactly afterwards, reads
  `usesDefaults` true with `en` and `standard`; the first owner, after explicitly
  choosing `en` and `standard` (the default values), reads `usesDefaults` false. The
  settings routes now hold 8 tests. Both passed in Step 39's coverage lane, and each
  failed with its own behaviour withheld (below).
- **Step 37, NFR5.1.** (a) `digest-settings.test.tsx` finds the dialog by its Korean
  name and the cadence, window and (once weekly) day selects and the four buttons by
  role and Korean name; a time field has no ARIA role of its own, so both tests find
  it by its Korean label. It passed on the unchanged code: every control already
  had its Korean accessible name, so `digest-settings.tsx` did not change. (b)
  `frontend/e2e/u5-topics-digests/populated-list-accessibility.spec.ts` (2 tests, run
  after `journey.spec.ts`): axe, 320 CSS px reflow and focus over memberA's populated
  topic list in the four theme settings, and the settings form's controls by role and
  Korean name. Both passed in Step 39's browser lane (9 tests), and each failed with
  its own behaviour withheld (below).
- **Step 38, merges and additions.** Python merges parametrize over the original test
  bodies, now private case functions whose names give the case ids, so each case is
  still its own collected item. Vitest merges run the original tests as named cases
  through `frontend/test/u5-topics/cases.ts` (`eachCase`: each case renders alone, is
  unmounted before the next, and a failure is prefixed with its case's name).
  - `database/test_schema.py`: `test_a_followed_topic_keeps_one_row_with_a_fixed_identity`
    (one row per account and key; identity and follow time immutable) and
    `test_a_topic_holds_one_live_run_per_window_and_one_sending_run` (window uniqueness;
    single flight).
  - `repository/test_repository.py`: `test_an_unknown_outcome_pauses_until_reconciled_or_resolved_once`
    (unknown pause and reconcile; owner resolve).
  - `repository/test_preferences.py`: `test_unsent_preparation_follows_the_effective_preference_fingerprint`
    (language change discards; appearance-only keeps; zone change discards).
  - `topics-view.test.tsx`: the empty, read-failure and degraded states, one test.
  - `announcements.test.tsx`: the two resolutions (one body from one loop), one test;
    the Korean names of the list and of the resolve control, one test.
  - `digest-settings.test.tsx` (18 after Step 37) to 8: acknowledged saves (2 cases),
    field validation (3), failed reads and saves (4), the readout's sources (3), the
    readout refresh, keyboard and confirmation (2), the Korean names, and the
    delivery-path labels (2).
  - Added: `operations/test_phase_verdicts.py`'s fifth test, a source change during the
    run fails a phase whose report shows only passing tests (`sourceChangedDuringRun`,
    which the four did not check); `component/test_real_host_binding.py`'s fifth (L3-1
    (3)), a fixture clock binds only with synthetic delivery and is refused beside real
    delivery (`u5_host.topics_contribution`).

**Each changed component's tests, before and after** (functions; collected items in
brackets where they differ):

| Component | File(s) | Before | After |
|---|---|---|---|
| Topics schema rules and guards | `database/test_schema.py` | 10 | 8 [10] |
| `TopicsRepository` transitions, isolation, windows, watermark | `repository/test_repository.py` | 9 | 8 [9] |
| `TopicsRepository` preference fencing | `repository/test_preferences.py` | 10 | 8 [10] |
| Scheduler | `component/test_topics_scheduler.py` | in `test_topics_logic.py` (13 [16]) | 5 [6] |
| Delivery outcomes, resolution, watermark | `component/test_topics_delivery_outcomes.py` | in `test_topics_logic.py` | 7 [9] |
| Lifecycle participant | 4 files, `component/test_topics_withdraw_and_erase.py` among them | 6 | 6 |
| Real activation and adapter | `component/test_real_activation.py` | in `test_real_composition.py` (18 [43]) | 8 [33] |
| Host binding, policy, outcome view | `component/test_real_host_binding.py` | in `test_real_composition.py` | 5 (4 moved, 1 new) |
| Public cancellation boundary | `component/test_cancellation_origin.py` | in `test_real_composition.py` | 6 |
| Topics routes | `integration/test_http_owner_topics.py` | in `test_http.py` (11) | 5 |
| C03 settings routes | `integration/test_http_settings_routes.py` | in `test_http.py` | 8 (6 moved, 2 new) |
| Runner phase verdict and evidence | `operations/test_phase_verdicts.py` | 4 [11] | 5 [12] |
| Topics view | `frontend/test/u5-topics/topics-view.test.tsx` | in `topics.test.tsx` (14) | 8 |
| Topics view announcements and names (NFR5.1) | `frontend/test/u5-topics/announcements.test.tsx` | 10 | 8 |
| Digest settings form | `frontend/test/u5-topics/digest-settings.test.tsx` | in `topics.test.tsx` and `settings-dialog.test.tsx` (13) | 8 |

Totals: collect-only 327 → 331 (Step 36's two, Step 38's two); Vitest 49 → 36 (the
merges; no assertion or case dropped). Every other file keeps the counts Step 24 and
Step 33 recorded. Not in Build and Test's list and left as they are: the single-purpose
files whose components are counted across files or are source scans
(`test_zone_isolation.py` 2, `test_message_content.py` 2, `test_no_logging.py` 2,
`test_failure_domain.py` 1, `repository/test_lifecycle_isolation.py` 1) and
`frontend/test/u5-topics/stack.test.ts` 4, a source scan of the views' imports.

### Withheld-behaviour checks (Step 39, first part, 2026-11-18, outside the recorded runs)

Each check edited the named source, ran the test, and restored the source exactly; every
restore was confirmed by SHA-256 against the digest taken before the first edit
(`digest-settings.tsx` `b7d7810e…`, `topics-view.tsx` `8ec0117d…`,
`verify_docsuri_u5.py` `e7685f8f…`, `u5_host.py` `618c8595…`, `u5_schema.sql`
`c63aff0a…`). Where several withholds sat in one file at once, each touched a
different merged test, and each test failed in its withheld case only.

- F1, the cadence select's label reads `Cadence` (`digest-settings.tsx`): the Korean
  names test failed (`Unable to find an accessible element with the role "combobox"
  and name "발송 주기"`); the other seven passed.
- F2–F7, in `digest-settings.tsx` at once, each failing its merged test in the withheld
  case: the unchanged-save message → `[case: reports an unchanged acknowledged save
  truthfully]`; the weekday kept when daily → `[case: drops a stale weekday when the
  cadence returns to daily]`; no `onError` on the initial read failure → `[case:
  surfaces an initial read failure to the owner and stays in loading]`; no unconfigured
  zone status → `[case: states an unconfigured owner zone instead of assuming a
  location]`; Escape ignored → `[case: closes on Escape and keeps Tab focus inside the
  dialog]`; the local-sink label changed → `[case: labels a local-sink send as local,
  never as email delivery]`.
- F8 and F9, in `topics-view.tsx` at once: no degraded marker → `[case: marks the
  partial state when the capability is degraded]`; the not-delivered message changed
  → `[case: announces the not-delivered resolution in the status line]`.
- F10, the not-delivered button reads `Mark not delivered`: the merged names test
  failed in `[case: names both controls of the resolve control in Korean]` (and the
  resolution test, which clicks that button by name).
- B1, the runner no longer compares the source identity after the child
  (`verify_docsuri_u5.py`): the new phase-verdict test failed (`isinstance({'state':
  'passed', ...}, Refused)` false).
- B2, the fixture-clock guard disabled (`u5_host.py`): the new host-binding test failed
  (`DID NOT RAISE ValueError`).
- D1 and D2, on scratch realm `docsuri-u5-e76725f9f6d6e4ad` migrated with two guards
  withheld in `u5_schema.sql` (the identity guard comparing only id and account; the
  single-flight index not unique), the file restored right after the migrate:
  `test_schema.py` failed exactly in
  `[topic_identity_and_follow_time_are_immutable]` (`DID NOT RAISE CheckViolation`) and
  `[single_flight_allows_one_sending_run_per_topic]` (`DID NOT RAISE UniqueViolation`);
  its other eight items, the sibling cases among them, passed.
- The developer's archive of that scratch realm was refused at the permission prompt;
  the coordinator archived it at the start of the realm-based checks below.

**Realm-based checks (the coordinator, 2026-11-17 17:13–17:30 UTC).** Each ran on its
own fresh realm through `~/.docsuri-u8/lead-scripts/u5_withheld.py <label> <phase>`
(archive any left realm, settle 90 s, setup, the container confirmed in Colima,
migrate, fixtures, the phase, archive-owned, the preserved folder kept in
`~/.docsuri-u8/final-evidence/`), with one behaviour withheld in the source for the
run. Every restore was confirmed by SHA-256 against the digests taken before the first
edit (`http.py` `a5e172d6…`, `repository.py` `1f3ed6fc…`, `topics-view.tsx`
`8ec0117d…`, `digest-settings.tsx` `b7d7810e…`). The phase stops at its first failure,
so each withheld behaviour was chosen to reach only the test it checks; the tests
before it passed.

- `marker`, the route's view no longer carries `usesDefaults` (`http.py`), integration
  phase: `test_topic_settings_route_marks_inherited_defaults_without_a_saved_choice`
  failed (`KeyError: 'usesDefaults'`).
- `marker-true`, the route's view always reports `usesDefaults` true (`http.py`),
  integration phase, 24 tests: the inherited-defaults test passed, and
  `test_topic_settings_route_clears_the_defaults_marker_once_the_owner_chooses` failed
  (`assert True is False`).
- `resolve`, `resolve_run` no longer refuses an outcome other than sent or failed
  (`repository.py`), repository phase, 38 tests:
  `test_an_unknown_outcome_pauses_until_reconciled_or_resolved_once[owner_resolve_action]`
  failed (the invalid outcome reached the run guard: `CheckViolation`, not
  `INVALID_ARGUMENT`); its sibling case passed.
- `fence-zone`: setup refused (`owned prerequisite unavailable`, 0.7 s after the
  previous realm's archive). Kept as a failed prerequisite, not relabelled; the driver
  now settles 90 s before every setup, and `fence-zone-2` reran on a fresh realm.
- `fence-zone-2`, the preparation fence compares language and level only
  (`repository.py`), repository phase, 8 tests:
  `test_unsent_preparation_follows_the_effective_preference_fingerprint[zone_change_discards_preparation]`
  failed (`begin_send` returned the stale run instead of `None`); the language and
  appearance cases before it passed.
- `list-hidden`, each topic row's actions marked `aria-hidden` (`topics-view.tsx`),
  browser phase: the accessibility, credentials and journey specs passed, and the
  populated-list test failed with axe's `aria-hidden-focus` on each row.
- `name-english`, the cadence label reads `Cadence` (`digest-settings.tsx`), browser
  phase: the populated-list test passed, and the Korean-names test failed (no combobox
  named `발송 주기` in the dialog).

The logs are under `~/.docsuri-u8/lead-scripts/final-lanes/u5-withheld-<label>-*`.

### Local lanes (Step 39, first part, 2026-11-18)

| Lane | Result |
|---|---|
| Vitest, `vitest.u5-topics.config.ts --coverage` | exit 0; 36 passed in 5 files; `src/u5-topics/**` 98.47% of lines (floor 80) |
| `tsc --project tsconfig.u5-topics.json --noEmit --incremental false` | exit 0 |
| ESLint, U5's CI step (`src/u5-topics src/App.tsx src/api.ts test/u5-topics e2e/u5-topics-digests` and the two configs) | exit 0 |
| Ruff check `--no-cache`, U5's CI list | exit 0, all checks passed |
| collect-only | exit 0; 331 tests |
| Realm-free backend files run directly | 56 passed before Step 38's additions (`test_real_activation.py`, `test_real_host_binding.py`, `test_cancellation_origin.py`, `test_phase_verdicts.py`); 17 passed for the two files after them |

`ruff format --check` on the touched Python files reports one pre-existing drift in
`operations/test_phase_verdicts.py` (lines from Step 20, none this step wrote),
recorded and not fixed: CI runs `ruff check` only.

### Fresh-realm lanes (Step 39, 2026-11-17 17:31–17:36 UTC)

Run with `~/.docsuri-u8/lead-scripts/cp7_lanes.py` under umask 077 and Colima's
`DOCKER_HOST` and `DOCKER_CONFIG`, after every source was restored, each test phase on
its own fresh realm: `cp7-run-20261118-023131-72776` (coverage, component, browser; 27
steps passed) and `cp7-run-20261118-023548-74432` (database and the realm-free lanes; 15
steps passed).

| Lane | Result |
|---|---|
| `coverage` | exit 0; 331 tests, 0 failures; 85.26% (floor 80.0) |
| `component`, its own fresh realm | exit 0; 136 tests, 0 failures |
| `browser`, its own fresh realm | exit 0; 9 tests, 0 failures (the 7 before, and Step 37 (b)'s 2) |
| `database`, its own fresh realm | exit 0; 33 tests, 0 failures |
| Vitest, `vitest.u5-topics.config.ts --coverage` | exit 0; 36 passed; `src/u5-topics/**` 98.47% of lines (floor 80) |
| `tsc --project tsconfig.u5-topics.json --noEmit --incremental false` | exit 0 |
| ESLint, U5's CI step | exit 0 |
| Ruff check `--no-cache`, U5's CI list | exit 0 |
| `test_archive_expiry.py` | exit 0 |
| collect-only | exit 0; 331 tests |

### The plan's boxes in this attempt

The developer ticked Steps 34, 35 and 38 after their runs. Steps 36, 37 and 39 are
ticked after the runs above. This attempt's Plan Approval cleared the boxes of Steps
1–33; their work stands and Step 39's runs exercise it again, so they are ticked again,
as the plan says. Step 39's review and checkpoint run through AI-DLC after the ticks.

## Build and Test loop-back 2 (2026-11-15)

Build and Test's re-run of 2026-11-15 ([test-results.md](../../build-and-test/test-results.md),
Target Verification Matrix and "Loop-back 2") passed every U5 lane but left one
U5 target Not Met, `U5:code-generation-plan:testing-contract-strategy-volume`
(the lifecycle participant had 3 tests, `local_observation.py`'s topics probe 4,
and the runner 28 test functions in one file), and NFR5.1's two clauses unchecked
(the polite live-region status of the topics list's and resolve control's
messages, and the Korean names of those two surfaces' controls). The maintainer
chose "Retry with fix" on 2026-11-15 and approved the loop-back plan
(`code-generation-plan.md`, Steps 28–33) with "Approve Plan". No production code
changes in this loop-back: every step adds or moves tests. This section records
the decision and scope (Step 28); Step 33's withheld-behaviour checks, lane runs,
per-file counts, review and checkpoint are added when they have run.

### Decisions and deviations (Step 28)

- **L2-1, the runner's tests are grouped by the runner's parts (proposed with the
  plan, approved with it).** `tests/u5_topics_digests/operations/test_runner.py`
  held 28 test functions, one per safety boundary of `scripts/verify_docsuri_u5.py`,
  where the Testing Contract's standard strategy asks for five to eight per
  component. The runner has five distinct parts, so Step 31 splits the file into
  one test file per part, each holding five to eight of the existing tests, moved
  byte for byte with the imports, fixture and helpers each uses: no test is
  merged, weakened or dropped, and the collect-only total does not change because
  of the split. The files: `test_runner_supervision.py` (8: measured memory, the
  observation timeout, the browser snapshot per tick, the process-tree snapshot's
  union and its deadline, proportional bytes, PSS on Linux, the proportional
  budget), `test_runner_clock.py` (5: the clock advance, the refused parallel
  runner, the browser clock child, the delegation's refusals, its revocation),
  `test_runner_configuration.py` (5: the database command's configuration,
  private evidence, the phase catalog, content digests, the policy reference),
  `test_runner_bindings.py` (5: the child environment's manifest, the migration
  chain, owner and realm bindings, the transport binding, the local profile's
  manifest) and `test_runner_serving.py` (5: browser assets, the fixture record,
  its setup, serving the owned release, the refused real delivery). The rejected
  alternatives were merging the 28 into at most eight parametrized functions,
  which would bundle unrelated boundaries into one test, and keeping the file,
  which would leave the target Not Met. The `owned_root` fixture the old file
  defined once is repeated in the four new files that use it, since the step adds
  no shared test module.
- **Targets that stay as they are, and why.**
  - `U5:code-generation-plan:testing-contract-methodology-layers` and
    `U5:code-generation-plan:testing-contract-runner-step` (Unverified, owned by
    Build and Test) ask whether each layer was implemented before its tests and
    whether the unit-scoped command was recorded before the first test. No test
    can show the order of past work; only Code Generation's records do (the plan's
    ticked steps in layer order and Step 2's recorded command, with this summary's
    "Process evidence (Step 24)"). This loop-back adds tests only and leaves those
    records as they are.
  - `U5:tech-stack-decisions:verification-notes-real-delivery` (Unverified, owned
    by deployment-execution) needs a bounded, authorized real send through the
    configured free adapter. Code Generation's record holds one such send
    (`traceability.json` > `real_delivery_evidence`); a later stage verifies it,
    and no change here can.

### Withheld-behaviour checks (Step 33, 2026-11-15, before the recorded runs)

Each new test was run once with the behaviour it checks withheld (edit, run,
restore exactly), outside the recorded runs, and every restore was confirmed by
SHA-256. The record is `~/.docsuri-u8/final-evidence/u5-l2-failchecks.json`.

- **Frontend**, `frontend/test/u5-topics/announcements.test.tsx`: its 10 tests
  passed on the unchanged code.
  - F1, `StatusLine` in `frontend/src/ui.tsx` renders a polite notice as
    `role="alert"`: the five polite-announcement tests failed, the other five passed.
  - F2, it renders an alert as `role="status"`: the three alert tests failed.
  - F3, the follow button reads `Follow topic`: "names every control of the topic
    list in Korean" failed, with the two tests that click that button by its name.
  - F4, the resolve button reads `Mark delivered`: "names both controls of the
    resolve control in Korean" failed, with the two tests that click it by its name.
  - Restored: `ui.tsx` `c5b0aed6…`, `topics-view.tsx` `8ec0117d…`; all 10 passed again.
- **Backend**, on a scratch realm (`docsuri-u5-2ba5dd5295f3cb8d`, archived
  afterwards), each test run directly with `DOCSURI_U5_ENVIRONMENT_FILE`: the nine
  tests of the two files passed on the unchanged code.
  - B1, a reactivation takes the withdrawal branch (`control_lifecycle.py`): the
    reactivation test failed at `:163`, its rows changed.
  - B2, a withdrawal no longer unsubscribes: the withdrawal test failed at `:192`.
  - B3, the `pending_work` scope no longer discards: the erasure test failed at `:239`.
  - B4, a denied store maps to `observation.probeFailed` (`local_observation._reason`):
    the denied-store test failed at `:126`, after its `finally` had restored the grant.
  - B5, the topics probe gains a fifth count: the four-counts test failed at `:152`.
  - Restored: `control_lifecycle.py` `5c1f7da2…`, `local_observation.py` `835472c4…`;
    the nine tests passed again.

### Fresh-realm lanes (Step 33, 2026-11-15 06:42–06:49 UTC)

Run through the lead's lane driver (one subprocess per step, Colima's
`DOCKER_HOST` and `DOCKER_CONFIG`, each environment confirmed in Colima, then
archived and its preserved folder copied to `~/.docsuri-u8/final-evidence/`).
Every U5 phase recorded the source digest `0830d806…` over 2,033 files, which
includes this loop-back's test files. No failure, error or skip anywhere.

| Lane | Environment | Result |
|---|---|---|
| coverage | `docsuri-u5-70bfabfa1277533c` | 327 passed; 85.21% over `backend/.coveragerc.u5` (floor 80) |
| component | `docsuri-u5-0547844164ad5fbf`, its own | 135 passed |
| browser | `docsuri-u5-f43279546d0fac71`, its own | 7 passed |
| database | `docsuri-u5-0e133fc6c5a62886`, its own | 33 passed |
| Vitest, `vitest.u5-topics.config.ts --coverage` | — | 49 passed in 5 files; `src/u5-topics/**` 98.47% of lines (floor 80) |
| `tsc --project tsconfig.u5-topics.json --noEmit --incremental false` | — | clean |
| ESLint, `src/u5-topics src/App.tsx src/api.ts` | — | clean |
| Ruff, U5's CI list | — | all checks passed |
| collect-only | — | 327 tests (322 before, plus Steps 29 and 30's five) |

### Each changed component's tests (Step 33)

| Component | Tests | Collected items | Files |
|---|---|---|---|
| Lifecycle participant, `control_lifecycle.py` | 6 | 6 | 3 new in `repository/test_lifecycle_participant.py`; 1 each in `repository/test_lifecycle_isolation.py`, `component/test_topics_logic.py` and `integration/test_email_unsubscribe.py` |
| Topics probe, `local_observation.py` | 6 | 6 | `component/test_owner_observation.py` (4 existing, 2 new) |
| Runner, supervision | 8 | 9 | `operations/test_runner_supervision.py` |
| Runner, clock | 5 | 11 | `operations/test_runner_clock.py` |
| Runner, configuration | 5 | 5 | `operations/test_runner_configuration.py` |
| Runner, bindings | 5 | 5 | `operations/test_runner_bindings.py` |
| Runner, serving | 5 | 5 | `operations/test_runner_serving.py` |
| Topics view announcements and names (NFR5.1) | 10 | 10 | `frontend/test/u5-topics/announcements.test.tsx` |

- The runner's counts are test functions, as L2-1 groups them; two functions are
  parametrized, so the supervision and clock files collect 9 and 11 items.
- `announcements.test.tsx` is above eight and kept, as Step 24 kept files with one
  check per distinct rule: one check per NFR5.1 clause, five acknowledged changes
  announced politely, three failures announced as alerts, and the Korean names of
  two surfaces. The topics view's other behaviour stays in `topics.test.tsx`.
- Every other component's counts are as Step 24's table below records them; this
  loop-back changed none of them.

### The plan's boxes in this attempt

- The approval of 2026-11-15 cleared every box. Steps 1–13, 16–26 and 29–32 were
  ticked again only after the lanes above had passed, since those runs exercise
  their work again.
- Steps 14, 15 and 27 ask for a review and a checkpoint of their own attempts.
  Those passed (2026-10-19, and 2026-10-28 for Step 27), and this attempt's review
  and checkpoint stand in for them.
- Step 33 is ticked with this record, before its review and checkpoint, which
  follow as the stage's own handoff. The engine routes a Unit to completion only
  once every box is ticked, and any edit to the plan after the review would void
  that review's receipt, so the box cannot wait for them. If the review or the
  checkpoint fails, the Unit returns to Code Generation and the box with it.

## Build and Test loop-back 1 (2026-10-28)

Build and Test's target check ([test-results.md](../../build-and-test/test-results.md),
Target Verification Matrix and Loop-Back Log) left 4 of U5's targets Not Met and
20 that no test in a passed lane checked in full, although every U5 suite passed.
The maintainer chose "Retry with fix" on 2026-10-27, decided L1-1 to L1-3 on
2026-10-28 and approved the loop-back plan (`code-generation-plan.md`, Steps
16–27) with "Approve Plan". This section records the decisions and deviations
(Step 16), the process evidence (Step 24), the two fixes the new checks found
(Steps 25 and 26) and the fresh-realm lane results (Step 27); the sections below
keep their own dates. Steps 16–27 are built and ticked: Step 22's three checks
pass since Step 25 fixed the settings form's dark-theme contrast, and Step 26
freed `test_schedule_preferences.py` from its pinned dates. Step 27's review and
checkpoint remain with the coordinator; a build was interrupted by a session
restart between Steps 24 and 25, and this attempt's lanes ran after it.

### Decisions and deviations (Step 16)

- **L1-1, refusal detail kept (the maintainer's decision).** This deviates from
  `security-requirements.md` > Data Protection, "failure records use
  plain-language categories without secrets, tokens or full recipient
  addresses", which Build and Test read as a plain-language category only
  (target `U5:security-requirements:data-protection-failure-records`, Not Met). A
  definite provider refusal keeps, beside its plain-language category (`failed`,
  `delivery-path-refused`), the provider's HTTP status from the fixed set 400,
  401, 403, 404, 413, 422 and 429, and the provider's error name when it matches
  `^[a-z][a-z0-9_]{0,63}$`, otherwise the fixed `name-unavailable`. It never keeps
  free text, a secret, a payload or an address. That is what
  `backend/modules/topics/u5_refusal_detail.sql` built (CHECK
  `delivery_outcome_provider_refusal`; the replaced `guard_outcome_update` makes
  both values immutable) and what `backend/modules/accounts/integrations/digest_email.py`
  returns (`REFUSED_STATUSES`, `PROVIDER_ERROR_NAME`).
  `repository/test_refusal_store.py` and `component/test_refusal_detail.py` check
  it. The decision amends the requirement here and in the plan rather than in the
  approved requirements file, so the stages built on that file are not flagged
  for a re-check. Both refusal-detail entries of `traceability.json` cite L1-1.
- **L1-2, the shared shell files are counted by U2's cumulative lane (the
  maintainer's decision).** `frontend/src/App.tsx` and `frontend/src/api.ts` are
  measured by `frontend/vitest.u2-cumulative.config.ts` under its 80% line floor
  over all of `src/`, not by U5's lane. `vitest.u5-topics.config.ts` keeps
  measuring `src/u5-topics/**` (97.93% of lines in Step 22's run). This deviates
  from Build and Test's planned fix, which put both files in a U5 coverage set
  (target `U5:unit-test-instructions:framework-setup-frontend-coverage`, Not
  Met). `unit-test-instructions.md` records it (Step 23).
- **L1-3, the two unmeasured backend files join U5's report (the maintainer's
  decision).** `backend/local_observation.py` is on `backend/.coveragerc.u5`'s
  include list under its unchanged 80% floor (Step 23).
  `backend/modules/accounts/integrations/email.py` is not: after Step 19 it is no
  longer a U5 change (L1-4). Step 23's coverage run (realm
  `docsuri-u5-a0fd3d87849495b7`: 314 passed, 0 failures, errors or skips)
  measured 84.69% in total (2,097 statements, 321 missed) and 86% for
  `local_observation.py` (71 statements, 10 missed); evidence
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-a0fd3d87849495b7-f1b14a19/coverage-evidence-1793124510581879000.json`.
  The other files U5 changed stay with the reports that already measure them
  under their floors: U8's `.coveragerc.u8` for `backend/artifacts.py`,
  `control_worker.py`, `lifecycle_effects.py`, `local_browser.py`,
  `local_host.py`, `local_profile.py`, `transactions.py` and
  `ops/src/docsuri_ops/local_transport.py`; U2's `.coveragerc.u2` for
  `backend/modules/accounts/local_http.py`; U3's `.coveragerc.u3` for
  `backend/u3_host.py`; U4's `.coveragerc.u4` for `backend/u4_host.py`. The
  plan's L1-3 calls these "the other twelve", but the files it names are these
  eleven: Build and Test's twelve were the backend files outside the include
  set, `email.py` and `local_observation.py` among them, and `local_transport.py`
  is under `ops/`. U5's runner, `scripts/verify_docsuri_u5.py`, stays unmeasured
  as before (deviation 4 below), as U8's runner does; the `operations/` tests
  check its behaviour. Target `U5:unit-test-instructions:expected-coverage-backend`
  (Not Met).
- **L1-4, the unused seam is removed.** `send_digest_email` on the account email
  client had no caller anywhere (target
  `U5:code-generation-plan:testing-contract-integration-boundaries`, Not Met).
  Step 19 removed it. `backend/modules/accounts/integrations/email.py` is again
  byte-identical to its content before U5 (blob `50f8586c`, as at
  `8ba35b90~1`), and only the module docstring of
  `backend/modules/topics/delivery.py` changed, to name `digest_email.py`.
  In U5's compositions digests go through the account-owned `digest_email.py`
  adapter alone, the "adjacent account-owned adapter" plan Step 7 allowed (U8's
  production adapters in `u8_digest_mail.py` build on it). `email.py` left
  `source-manifest.json` and L1-3's include list. The `DigestDelivery` line of
  "What was built" and the `email.py` entry of deviation 10 below describe the
  removed seam; they are kept as history.

Other deviations in Steps 17–23:

- Step 17 (d) upgrades a populated chain from the chain's current bytes. A realm
  holding the first-build receipt of `backend/modules/corpus/u5_digest_read.sql`
  (digest `41c0ec32…`, before `ac55d423`'s comment correction) is refused by the
  runner by design, as "Migration and remaining evidence" below records;
  `database/test_migration_digests.py` now tests that refusal.
- Step 20 (d) compares the guest search answer before and after the failing
  digest step, not a signed-in one. On U5's assembled host a signed-in
  `POST /api/v2/c05/search` answers 409 by inherited design:
  `GuardedDiscoveryRepository.admit` (`backend/modules/discovery/guarded_repository.py`)
  admits only the account-controls, corpus-maintenance, service-operations and
  production realms.

### Process evidence (Step 24)

**Collect-only total.** Run from the repository root at 2026-10-28 04:25 KST,
exit 0:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini --collect-only -q tests/u5_topics_digests
```

It collected **322 tests** in 0.68 s, all from the 30 test files under
`tests/u5_topics_digests`: database 33, repository 36, component 133,
integration 36, operations 84. That is the 269 Build and Test ran plus 53 added by
Steps 17 (17), 18 (1), 20 (27) and 21 (8). Its only other output is one
third-party deprecation warning (`fastapi.testclient`). The command is the one
Step 2 recorded in `unit-test-instructions.md`, unchanged; Step 2's baseline
collected 81.

**Each component's tests, file by file.** Items are collected tests, each
parametrized case counted; functions are test functions. The standard strategy
asks for five to eight per component.

| Layer | File | Component it checks | Items | Functions | Against five to eight |
|---|---|---|---|---|---|
| Database | `database/test_schema.py` | topics schema rules and guards | 10 | 10 | above: one check per schema rule |
| Database | `database/test_preference_schema.py` | preference read grants, preparation snapshot | 6 | 6 | within |
| Database | `database/test_owner_grants.py` (new) | owner grants in and out of `topics` | 6 | 6 | within |
| Database | `database/test_migration_digests.py` (new) | U5's applied migration bytes and receipts | 6 | 5 | within |
| Database | `database/test_chain_upgrade.py` (new) | upgrade of the 59-migration chain | 5 | 5 | within |
| Repository | `repository/test_repository.py` | `TopicsRepository` transitions, isolation, windows, watermark | 9 | 9 | above by one |
| Repository | `repository/test_preferences.py` | `TopicsRepository` preference fencing | 10 | 10 | above: one check per fencing case |
| Repository | `repository/test_real_retention.py` | `TopicsRepository` real-send retention | 6 | 6 | within |
| Repository | `repository/test_refusal_store.py` | `TopicsRepository` refusal detail | 10 | 5 | above by items (6 inconsistent-detail cases of one rule); functions within |
| Repository | `repository/test_lifecycle_isolation.py` (new) | lifecycle participant's withdraw and erase | 1 | 1 | below: one targeted check |
| Component | `component/test_topics_logic.py` | service, preparation, delivery, scheduler and participant together | 16 | 13 | above: the business flow's components share this file |
| Component | `component/test_schedule_preferences.py` | schedule occurrence rules | 7 | 7 | within |
| Component | `component/test_zone_isolation.py` (new) | scheduler, per-owner zones | 2 | 2 | below |
| Component | `component/test_message_content.py` (new) | presentation through delivery and the Resend adapter | 2 | 2 | below |
| Component | `component/test_digest_transport.py` | `digest_email.py` transport results | 16 | 6 | above by items (5 statuses, 4 lost or malformed responses, 4 capability links); functions within |
| Component | `component/test_refusal_detail.py` | `digest_email.py` refusal detail, operator outcome | 28 | 7 | above by items (7 statuses, 9 name forms, 8 inconsistent results); functions within |
| Component | `component/test_real_composition.py` | real composition, policy, cancellation origin | 43 | 18 | above (17 activation-field, 3 missing- or extra-field and 8 environment refusal cases; 18 functions) |
| Component | `component/test_no_secrets.py` (new) | configuration, activation record, store, environment reads | 5 | 5 | within |
| Component | `component/test_no_logging.py` (new) | every U5 production module (source scan) | 2 | 2 | below: a scan and its control |
| Component | `component/test_failure_domain.py` (new) | the assembled host's digest step | 1 | 1 | below |
| Component | `component/test_owner_observation.py` (new) | `local_observation.py`'s topics probe | 4 | 4 | below |
| Component | `component/test_account_settings_regression.py` | inherited account and settings paths | 7 | 7 | within |
| API | `integration/test_http.py` | topics routes (5) and C03 settings routes (6) | 11 | 11 | above |
| API | `integration/test_email_unsubscribe.py` | one-click unsubscribe route and capability | 11 | 8 | above by items (4 malformed-form cases); functions within |
| API | `integration/test_real_delivery.py` | assembled real composition on the store | 6 | 6 | within |
| API | `integration/test_mounted_surface.py` (new) | U5's mounted surface | 8 | 8 | within |
| Operations | `operations/test_runner.py` | runner safety boundaries | 35 | 28 | above: one check per boundary |
| Operations | `operations/test_archive_expiry.py` | expired-realm preservation | 31 | 5 | above by items (5 and 4 units, 8 retention and 13 custody or busy-realm defects); functions within |
| Operations | `operations/test_phase_verdicts.py` (new) | the runner's phase verdict and evidence | 11 | 4 | above by items (7 failing reports, 2 phases); functions below |
| Operations | `operations/test_coverage_floor.py` (U8's file, U8 plan Step 44) | the coverage phase's floor judgment | 7 | 6 | within |

By items, 11 of the 30 files fall within five to eight, 13 above and 6 below. By
functions, 16 fall within, 7 above (`test_schema.py` 10, `test_repository.py` 9,
`test_preferences.py` 10, `test_topics_logic.py` 13, `test_real_composition.py`
18, `test_http.py` 11, `test_runner.py` 28) and 7 below (the six new
single-purpose files and `test_phase_verdicts.py`). The counts are recorded as
found; no test was merged or dropped to fit the range. The files below it are
single-purpose checks this loop-back added. Counted across files, two
components stay below five: the lifecycle participant
(`control_lifecycle.py`) has 3 tests, one each in
`repository/test_lifecycle_isolation.py`, `component/test_topics_logic.py` and
`integration/test_email_unsubscribe.py`, and `local_observation.py`'s topics
probe has the 4 in `component/test_owner_observation.py`.
`operations/test_coverage_floor.py` sits in U5's tree and is collected here, but
U8 wrote it and U8's source manifest claims it.

**The 81 baseline checks.** Step 2's baseline is the collection at `1e35045b`,
whose tests are as `8ba35b90` left them (`1e35045b` changed only records). The
same collect-only command, run on that commit's files exported to a scratch
folder (with pytest's cache plugin off), collects 81 tests in six files. Every one of the 81 ids is collected today under the same
id; none was renamed, split or removed. All 81 passed in Step 23's coverage run
(realm `docsuri-u5-a0fd3d87849495b7`, JUnit report of 314 tests, 0 failures,
errors or skips). Compared with today's source, 34 of the 55 test functions (41
items) are unchanged, 17 (36 items) were only reformatted in `ac55d423` (the
same syntax tree and comments), and 4 changed with the repairs, as the table
says. Five shared helpers they use also changed in `ac55d423`: `conftest.py`'s
`_make_authority`, `test_topics_logic.py`'s `build`, `RefusingMail` and
`UnobservedMail`, and `test_http.py`'s `mounted`.

| Baseline test at `1e35045b` | Items | Today | Body since the baseline |
|---|---|---|---|
| `component/test_topics_logic.py::test_due_window_boundaries_and_late_firing` | 1 | same id | changed in `ac55d423`: its topic carries an explicit `timeZone`, as owner-zone scheduling requires |
| `component/test_topics_logic.py::test_refire_idempotence_and_chronological_ordering` | 1 | same id | changed in `ac55d423`: reads the scheduler's injected clock instead of the wall clock |
| `component/test_topics_logic.py::test_empty_window_is_recorded_not_failed` | 1 | same id | unchanged |
| `component/test_topics_logic.py::test_send_outcomes_sent_failed_unknown` | 1 | same id | unchanged |
| `component/test_topics_logic.py::test_unknown_pause_and_evidence_reconciliation` | 1 | same id | unchanged |
| `component/test_topics_logic.py::test_owner_resolve_watermark_and_redelivery_bound` | 1 | same id | reformatted only (`ac55d423`) |
| `component/test_topics_logic.py::test_orphan_sweep_via_scheduler` | 1 | same id | unchanged |
| `component/test_topics_logic.py::test_unsubscribe_queued_versus_midflight` | 1 | same id | unchanged |
| `component/test_topics_logic.py::test_consent_stop_and_restore` | 1 | same id | unchanged |
| `component/test_topics_logic.py::test_reactivation_never_repeats_delivery` | 1 | same id | reformatted only (`ac55d423`) |
| `component/test_topics_logic.py::test_lifecycle_disposition_reporting` | 1 | same id | unchanged |
| `database/test_schema.py::test_one_subscription_row_per_account_and_key` | 1 | same id | unchanged |
| `database/test_schema.py::test_topic_identity_and_follow_time_are_immutable` | 1 | same id | reformatted only (`ac55d423`) |
| `database/test_schema.py::test_settings_shape_and_revision_advance` | 1 | same id | reformatted only (`ac55d423`) |
| `database/test_schema.py::test_run_stamps_current_settings_revision_and_keeps_chronology` | 1 | same id | unchanged |
| `database/test_schema.py::test_window_uniqueness_excludes_discarded_runs` | 1 | same id | unchanged |
| `database/test_schema.py::test_run_state_machine_and_content_immutability` | 1 | same id | reformatted only (`ac55d423`) |
| `database/test_schema.py::test_single_flight_allows_one_sending_run_per_topic` | 1 | same id | unchanged |
| `database/test_schema.py::test_send_log_and_outcome_follow_the_run_state` | 1 | same id | reformatted only (`ac55d423`) |
| `database/test_schema.py::test_watermark_requires_a_sent_run_of_the_same_topic` | 1 | same id | reformatted only (`ac55d423`) |
| `database/test_schema.py::test_owner_isolation_and_no_delete` | 1 | same id | unchanged |
| `integration/test_http.py::test_follow_duplicate_notice_and_reactivation` | 1 | same id | unchanged |
| `integration/test_http.py::test_revision_conflict_response` | 1 | same id | unchanged |
| `integration/test_http.py::test_owner_denial_indistinguishable_from_missing` | 1 | same id | unchanged |
| `integration/test_http.py::test_anonymous_refusal` | 1 | same id | reformatted only (`ac55d423`) |
| `integration/test_http.py::test_resolve_guards_and_assumption` | 1 | same id | reformatted only (`ac55d423`) |
| `operations/test_archive_expiry.py::test_expired_normal_profiles_remain_refused` `[u1]` `[u2]` `[u3]` `[u4]` `[u5]` | 5 | same ids | unchanged |
| `operations/test_archive_expiry.py::test_normal_profiles_retain_the_future_retention_bound` `[u2]` `[u3]` `[u4]` `[u5]` | 4 | same ids | unchanged |
| `operations/test_archive_expiry.py::test_preservation_requires_finite_original_retention` `[changes0]` to `[changes7]` | 8 | same ids | reformatted only (`ac55d423`) |
| `operations/test_archive_expiry.py::test_expired_owned_idle_realm_is_preserved_without_renewal` | 1 | same id | unchanged |
| `operations/test_archive_expiry.py::test_invalid_or_busy_expired_realms_never_stop_or_move` `[hash]` `[custody]` `[symlink]` `[unit]` `[port]` `[image]` `[policy]` `[container-name]` `[volume-name]` `[container-label]` `[volume-label]` `[database-identity]` `[active-client]` | 13 | same ids | reformatted only (`ac55d423`) |
| `operations/test_runner.py::test_available_memory_requires_exact_measured_field` | 1 | same id | unchanged |
| `operations/test_runner.py::test_database_command_has_finite_private_configuration` | 1 | same id | unchanged |
| `operations/test_runner.py::test_private_evidence_preserves_permissions_and_rejects_symlinks` | 1 | same id | unchanged |
| `operations/test_runner.py::test_parallel_runner_is_refused` | 1 | same id | unchanged |
| `operations/test_runner.py::test_child_environment_binds_the_unit_manifest` | 1 | same id | changed in `ac55d423`: also asserts the clock capability is absent from the child environment |
| `operations/test_runner.py::test_phase_catalog_matches_the_unit_scope` | 1 | same id | unchanged |
| `operations/test_runner.py::test_migration_chain_is_append_only_and_present` | 1 | same id | changed in `ac55d423` and `18c8d903`: the run guard is no longer last; the six repair migrations must follow it in order |
| `operations/test_runner.py::test_owner_and_realm_bindings_cover_topics` | 1 | same id | unchanged |
| `operations/test_runner.py::test_digest_is_stable_per_content` | 1 | same id | unchanged |
| `operations/test_runner.py::test_policy_reference_is_finite_and_bound` | 1 | same id | unchanged |
| `operations/test_runner.py::test_browser_fixture_record_is_bound_to_the_run` | 1 | same id | unchanged |
| `operations/test_runner.py::test_browser_fixture_setup_is_restartable_and_complete` | 1 | same id | unchanged |
| `operations/test_runner.py::test_realm_transport_binding_is_owned` | 1 | same id | unchanged |
| `operations/test_runner.py::test_serve_assembles_the_owned_release` | 1 | same id | unchanged |
| `operations/test_runner.py::test_local_profile_load_requires_the_owned_manifest` | 1 | same id | unchanged |
| `repository/test_repository.py::test_follow_duplicate_and_reactivation` | 1 | same id | unchanged |
| `repository/test_repository.py::test_cross_owner_denial` | 1 | same id | reformatted only (`ac55d423`) |
| `repository/test_repository.py::test_settings_revision_conflict_and_discard` | 1 | same id | reformatted only (`ac55d423`) |
| `repository/test_repository.py::test_window_order_and_adoption` | 1 | same id | reformatted only (`ac55d423`) |
| `repository/test_repository.py::test_begin_send_guards` | 1 | same id | reformatted only (`ac55d423`) |
| `repository/test_repository.py::test_unknown_pause_and_reconcile` | 1 | same id | unchanged |
| `repository/test_repository.py::test_send_watermark_exclusion` | 1 | same id | reformatted only (`ac55d423`) |
| `repository/test_repository.py::test_owner_resolve_action` | 1 | same id | unchanged |
| `repository/test_repository.py::test_orphan_sweep_records_evidence_gap` | 1 | same id | reformatted only (`ac55d423`) |

**Layer order, as the plan's ticked steps show it.**

- Steps 1–15 (the repair). The plan as last committed (`4ec8ab10`) ticks all
  fifteen, in this order: configuration (1); the runner command, recorded before
  any layer's tests (2); each layer implemented, then tested: data model and
  database (3, 4), repository (5, 6), business logic (7, 8), API (9, 10),
  frontend (11, 12); then environment (13), documentation and review (14) and
  the reopened attempt's confirmation (15). In the working tree, the loop-back's
  version of the plan shows these fifteen boxes unticked, although its loop-back
  section says Steps 1–15 "stay as built". This record leaves them as they are.
- Steps 16–27 (this loop-back). All ticked. The work ran in plan order: database
  tests (17), repository tests (18), the loop-back's one production change (19,
  business logic) and then its tests (20), API tests (21), configuration and
  measurement (23, whose coverage run came after Step 20's tests), these records
  (16, 24); then, after the session restart, the frontend fix (25) and the
  browser lane that checks it (22 (a), through Step 27), the test-only clock
  change (26) and the component lane that runs it (27). Steps 17, 18 and 21 test
  code built in Steps 3, 5 and 9; Step 25's stylesheet change was followed by
  its check (Step 22's settings-form spec) and no production file changed after
  the tests written for it. The files' modification times agree (2026-10-28,
  KST; each shows the last write): Steps 17 and 18 at 02:15–02:27, Step 19's
  `email.py` and `delivery.py` at 02:45, `.coveragerc.u5` at 02:46, Step 20's
  files at 02:56–03:04, Step 21's at 03:43, Step 22's at 03:48–04:13, Step 25's
  `topics.css` and Step 26's `test_schedule_preferences.py` at 10:03–10:05, and
  Step 27's lanes ran 10:06–10:11.

**New test files in this loop-back** (paths under `tests/u5_topics_digests/`
unless given in full; all are in `source-manifest.json`):

| Step | File | Tests | What it checks |
|---|---|---|---|
| 17 (a)–(c) | `database/test_owner_grants.py` | 6 | the topics login's reads outside `topics`, that the functions it reaches change no rows, its writes refused on 66 other tables, other logins refused on the 8 topics tables, the schema's eight tables |
| 17 (e) | `database/test_migration_digests.py` | 6 | the 15 pinned U5 files in chain order, their bytes and the realm's receipts, the runner refusing changed applied bytes (2 cases), one lifecycle definition |
| 17 (d) | `database/test_chain_upgrade.py` | 5 | a 59-migration chain with pre-repair rows, upgraded by the six repairs: rows and receipts kept, catalog equal to a fresh install, old rows' constraints and guards, no invented zone, erasure reaching every topics table |
| 18 | `repository/test_lifecycle_isolation.py` | 1 | withdraw and erase change only the owner's topics rows |
| 20 (a), (b) | `component/test_message_content.py` | 2 | the submitted message is exactly the stored presentation; the subject follows each owner's language |
| 20 (c) | `component/test_zone_isolation.py` | 2 | a missing or refused zone leaves other owners due; a weekly topic falls due exactly at its local wall time |
| 20 (d) | `component/test_failure_domain.py` | 1 | a failing digest step leaves the other worker steps and the accounts, library, research and guest-search answers unaffected |
| 20 (e) | `component/test_no_secrets.py` | 5 | no key material in configuration, the activation record or the store; the key read from the environment once at assembly; only the real composition reads the provider environment, with its control |
| 20 (f) | `component/test_no_logging.py` | 2 | no logger, `print` or standard-stream write in U5's production modules, with its control |
| 20 (i) | `component/test_owner_observation.py` | 4 | `local_observation.py`'s topics probe |
| 20 (g), (h) | `operations/test_phase_verdicts.py` | 11 | a phase fails on zero tests, a skip, an error, a failure, or a missing, malformed or wrongly owned report (7) and passes an all-passing one (1); evidence keeps the command, digests and counts without private output (2); the source identity digests (1) |
| 21 | `integration/test_mounted_surface.py` | 8 | U5's routes, middleware, state, transactions, threads, port, database and folders are exactly the listed ones |
| 22 (c) | `frontend/test/u5-topics/stack.test.ts` (Vitest) | 4 | U5's views import only React, SWR, the shared `ui` and `api` modules, their siblings and `topics.css`; passes |
| 22 (a) | `frontend/e2e/u5-topics-digests/accessibility.spec.ts` (Playwright) | 1 | the resolve control: axe, 320 CSS px reflow and visible focus in four theme settings; passes, and runs before `journey.spec.ts`, whose resolve journey uses the fixture's only open unknown |
| 22 (a) | `frontend/e2e/u5-topics-digests/settings-accessibility.spec.ts` (Playwright) | 1 | the settings form, the same checks; failed on the contrast defect until Step 25, passes in Step 27's browser lane |
| 22 (b) | `frontend/e2e/u5-topics-digests/credentials.spec.ts` (Playwright) | 1 | no credential in browser storage, the page or the served bundle; passes |

Helpers without tests: `realm_catalog.py` (Step 17), `real_send.py` and
`source_scan.py` (Step 20), `frontend/e2e/u5-topics-digests/a11y.ts` (Step 22).
Outside the collect-only run, U5's Vitest files hold 39 tests
(`preferences.test.tsx` 8, `settings-dialog.test.tsx` 13, `topics.test.tsx` 14,
`stack.test.ts` 4), as Step 22's Vitest run counted, and its Playwright specs 7
(`journey.spec.ts` 4 and the three new specs one each).

### Fixes the new checks found (Steps 25 and 26)

- **Step 25, the settings form's dark-theme contrast (NFR5.1, WCAG 1.4.3).**
  Step 22's settings-form spec had failed axe `color-contrast` on all 11 controls
  in both dark settings: `frontend/src/u5-topics/topics.css` fell back to
  `--surface`, `--text`, `--muted` and `--border`, which nothing defines, so its
  `#111` text sat on the workspace's dark `#131519` (1.03:1) and the `#b3261e`
  unsubscribe button on the same (2.80:1); the topics list's `#555` muted text
  shared the cause (evidence in the preserved browser realm
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-a9b63241520b0185-ad2115ff`).
  The stylesheet now takes every colour from the workspace tokens
  `--color-text-muted`, `--color-border`, `--color-surface`, `--color-text` and
  `--color-danger`, with no fallback, as U4's `research.css` and U6's
  `export.css` do; `frontend/app/globals.css` defines them for light, dark and
  both `data-theme` overrides. No selector, size or layout rule changed. The
  tokens' ratios on `--color-surface`: dark text 14.85:1, dark muted 6.48:1,
  dark danger 6.50:1; light text 16.71:1, light muted 4.55:1, light danger
  5.19:1. Step 27's browser lane then ran `settings-accessibility.spec.ts` with
  zero axe, reflow or focus findings in the four theme settings (light while the
  system prefers dark, dark while it prefers light, system light, system dark).
- **Step 26, the date-pinned test.** `component/test_schedule_preferences.py`
  pinned 2026-11-01, 2027-03-14 and 2027-01-01 while `topics.next_occurrence`
  honours a boundary stamped by the realm's `clock_timestamp()` (the follow, the
  settings save, the zone confirmation), so from 2026-11-01 05:30 UTC its fold,
  weekly, same-instant, due-filter and zone-confirmation cases would have found
  no occurrence. The file now reads that clock once per test (`run_clock`) and
  derives every date from it: the next autumn fold and spring gap of
  America/New_York after it (`next_transition`), the next Sunday two or more
  days ahead, and the next calendar days; expected instants come from
  `first_valid_instant`, which states `next_occurrence`'s rule in Python (a
  missing wall minute is due at the first valid minute after the gap, a repeated
  one at its first occurrence). Each case keeps its meaning: fall fold (one
  occurrence through the repeated hour), spring gap (02:30 is due at 03:00
  local), weekly wall time with next-day recovery, the same instant across owner
  local dates, an unconfigured owner not due, no past scheduling at zone
  confirmation, and the due filter ahead of the page limit. Three cases gained a
  control assertion (the fold's second occurrence an hour later, the gap's
  missing wall minute, the zone-confirmation case's due instant). Still 7 tests;
  no production change. Ruff check and format pass on the file.

### Fresh-realm lanes (Step 27, 2026-10-28 10:06–10:11 KST)

Run from the repository root (frontend commands from `frontend`), each realm
preserved with `archive-owned` before its replacement; no limit, floor or
timeout changed. Review and checkpoint remain with the coordinator.

- **Collect-only**, `backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini --collect-only -q tests/u5_topics_digests`:
  **322 tests** in 0.61 s, the same count as Step 24.
- **Coverage lane**, realm `docsuri-u5-f36e022f36ec0f2d` (`setup`, `migrate`,
  65 migrations, `fixtures`, `coverage`): **322 passed, 0 failures, 0 errors, 0
  skipped**; **85.02%** aggregate (the pytest-cov report rounds the same figures
  to 85.03%: 2,097 statements, 314 missed) against the 80% floor; 24.29 s; peak
  RSS 290.6 MiB (304,676,864 B). Files under 80% individually, as before:
  `backend/modules/personalization/local_http.py` 35% (103 statements, 67
  missed), `backend/modules/accounts/services/guarded_entry.py` 79% (221, 46),
  `scripts/u5_browser_fixtures.py` 73% (148, 40). Files this loop-back changed:
  `backend/local_observation.py` 86% (71, 10), `backend/modules/topics/delivery.py`
  83% (52, 9). Evidence
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-f36e022f36ec0f2d-2d1019cd/coverage-evidence-1793149660736342000.json`
  (with `coverage.xml`, the JUnit report, and the phase log beside it).
- **Component lane.** On the coverage realm, "in a later minute", the lane was
  **refused**: 1 failure in the 4 tests run before pytest stopped,
  `component/test_account_settings_regression.py::test_verification_recovery_uses_private_local_mail`
  raising `Busy: local authentication attempt allocation exhausted`. The coverage
  pass, which runs every component test, had spent the realm's finite
  authentication-attempt allocation; this is a failed prerequisite, not a code
  defect, and the instructions' note that the phases are individual finite
  passes covers it. Its log is preserved with that realm
  (`u5-phase-component-1793149…log`). On a fresh realm
  `docsuri-u5-2d32323f00dbc0d7` (`setup`, `migrate`, `fixtures`, `component`):
  **133 passed, 0 failures, 0 errors, 0 skipped**, Step 26's 7 among them;
  12.64 s; peak RSS 226.7 MiB (237,666,304 B); preserved at
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-2d32323f00dbc0d7-3cbc464e`.
- **Browser lane**, fresh realm `docsuri-u5-128a29a71ec191d0` prepared as CI's
  browser job does (`setup`, `migrate`, `browser`; the phase loads its own
  browser fixtures and refuses a realm holding prior evidence): **7 specs passed,
  0 failures, 0 skipped**: `journey.spec.ts` 4 (follow, settings save and
  unsubscribe; scheduler and local-sink delivery; empty digest without a send;
  unknown resolution), `accessibility.spec.ts` 1, `settings-accessibility.spec.ts`
  1, `credentials.spec.ts` 1; 13.06 s; peak RSS **980.3 MiB** (1,027,948,544 B)
  of the 1,024 MiB bound. Evidence
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-128a29a71ec191d0-516d0acd/browser-evidence-1793149828495638000.json`
  with `browser.xml` and the build, host and phase logs beside it. This is an
  exploratory run of the authorized command, not the checkpoint receipt.
- **Frontend**, from `frontend`:
  `corepack pnpm@9.15.9 exec tsc --project tsconfig.u5-topics.json --noEmit`
  passed;
  `corepack pnpm@9.15.9 exec vitest run --config vitest.u5-topics.config.ts --coverage`:
  **39 passed** in 4 files (`settings-dialog` 13, `topics` 14, `preferences` 8,
  `stack` 4), **97.93%** lines of `src/u5-topics` (`api.ts` 100, `digest-settings.tsx`
  99.69, `owner-preferences.tsx` 100, `topics-view.tsx` 95.5) against the 80%
  floor; ESLint on the CI target list (`src/u5-topics src/App.tsx src/api.ts
  test/u5-topics e2e/u5-topics-digests vitest.u5-topics.config.ts
  playwright.u5-topics.config.ts`) passed.
- **Ruff**, on the CI workflow's target list: `ruff check` passed.
  `ruff format --check` would reformat 16 files, none changed by this attempt
  and all already so before it (`backend/control_worker.py`, `local_browser.py`,
  `local_profile.py`, `transactions.py`, `modules/accounts/integrations/email.py`,
  `modules/accounts/local_http.py`, `modules/topics/repository.py`,
  `scripts/verify_docsuri_u5.py`, and U5's `component/test_no_secrets.py`,
  `database/test_chain_upgrade.py`, `database/test_owner_grants.py`,
  `operations/test_phase_verdicts.py`, `operations/test_runner.py`,
  `realm_catalog.py`, `repository/test_lifecycle_isolation.py`, `source_scan.py`).
  CI runs `ruff check` only; the shared files belong to other units' lanes and
  `email.py` must keep its pre-U5 bytes (L1-4), so they were left as they are.
  The two files this attempt changed pass both.

**Still open** (nothing here changes them):

- U8's `tests/u8_service_operations_integration/built_files.py` pins the bytes of
  `backend/modules/topics/delivery.py` and `backend/.coveragerc.u5`; three U8
  tests would fail until those pins move with Steps 19 and 23.
- Two low findings from Step 17: `topics.revoke_email_unsubscribe()` keeps
  PostgreSQL's default PUBLIC EXECUTE (a trigger function in a schema only the
  topics login and its owner can use; a fix needs an appended migration, which
  also changes U8's composed chain), and the runner's per-schema `ALTER DEFAULT
  PRIVILEGES … REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` changes nothing, so each
  function's own `REVOKE` carries that protection.
- `.github/workflows/u5-topics-digests.yml` still lists `email.py` among U5's
  lint targets, and `unit-test-instructions.md` still names it "while it remains
  a U5 change".
- The browser phase's peak RSS is near the runner's 1,024 MiB bound: 980.3 MiB
  this run, 897–993 MiB in earlier runs.
- The `component` lane cannot follow the `coverage` lane on the same realm: the
  coverage pass spends the realm's finite authentication-attempt allocation. The
  instructions' sequence "`coverage`, then `component` in a later minute" needs a
  fresh realm between them, as Step 27 ran it.
- The checkpoint's browser run needs a fresh realm: every realm of this attempt
  is preserved, so `setup` and `migrate` must precede it at
  `/tmp/docsuri-u5-run/environment.json`.

## Change after approval — two CI browser-job fixes — 2026-10-21

Commit `992862a4` (branch `feature/u6-approved-export`, PR #54) changed three
U5 paths after U5 was approved. No U5 product behaviour changed; the change is
to the verification runner, one test fixture and the runner's tests.

- `scripts/verify_docsuri_u5.py`: the runner keeps the 1 GiB memory budget, but
  on Linux it now enforces that budget on the sum of each process's
  proportional set size, read from `/proc/<pid>/smaps_rollup`. A process that
  has exited, or that cannot be read, counts its full RSS. macOS keeps the
  stricter RSS sum. Every supervision record and the summary carry
  `peakPssBytes` beside `peakRssBytes`, and the stop reason keeps its
  `rss-limit` label. Linux counts the pages Chromium's processes share once per
  process, which had pushed U6's browser phase over the budget on GitHub's
  runner; U5 uses the same accounting.
- `scripts/u5_browser_fixtures.py`: `advance-clock` now moves the fixture
  clock exactly one day (`advanced_clock(now) = now + 1 day`). Before, it moved
  the clock to 12:00 UTC on the next UTC date. Whenever the journey ran between
  00:00 and 09:00 KST, that instant fell before the next daily 00:00 KST
  delivery, so the newly followed topic was never due and the digest journey
  failed. Digest scheduling is unchanged: it still excludes delivery times
  before the follow (BR1.2).
- `tests/u5_topics_digests/operations/test_runner.py`: the memory monkeypatches
  now target `process_tree_memory`. New tests cover the rollup read and its RSS
  fallback, Linux-only use, enforcement on the proportional sum, and
  `advanced_clock` at 05:00, 16:00 and 23:59 UTC staying inside the host's
  accepted clock bound.

Evidence: GitHub Actions run 39528978335 ("U5 topics and digests") on
`992862a4` passed its frontend, backend and browser jobs (browser job
118990476821). The local environment-backed phases were not re-run after this
change, because the local Docker context points at the production container
runtime; CI ran them in its own environment.

## Step 15 — reopened attempt confirmation — 2026-10-19

Code Generation was reopened for this Unit only so Step 14 could be marked
complete after its final review (review-08, READY) froze the plan; the person
approved the plan with this confirmation step added. No application source
changed in this attempt. All 131 paths claimed in `source-manifest.json` exist.
Step 14 is complete: the real digest was accepted by Resend and confirmed in the
recipient's inbox, the mail client's one-click unsubscribe worked, and the
browser confirmation path was fixed and is covered by automated tests but has not
been re-run live (details below). Steps 1–13 outputs are unchanged from the
previous attempt. A fresh architecture review for this attempt and the
authorized AI-DLC browser checkpoint follow.

## Step 14 — second real send, browser-confirmation fix (R-15) — 2026-10-19 (current; supersedes every status below)

**Real delivery: sent and reached the inbox.** Realm
`docsuri-u5-95df9983c1b017e4`, run `bdc65d9f-c805-4dbc-bd20-a2a5e650f91c`,
sender `no-reply@mail.rvnnt.dev`, recipient `c***@icloud.com` (the one permitted
recipient), `pathKind: real`, state `sent`. Attempted 2026-10-19 05:11:26.544 UTC,
acknowledged 05:11:26.918 UTC, provider receipt SHA-256
`f17b05558fa8cc6c336532267eb17a19b13934d90513317ebe5566f62e0e9064` (plaintext
kept only in the preserved realm), evidence retained until 2026-11-18 05:11:26
UTC, allocation 1 of 1 spent. These were re-read with the read-only `outcome`
action before the realm was preserved with `archive-owned` at
`/private/tmp/docsuri-u5-preserved-docsuri-u5-95df9983c1b017e4-b5081e79`
(volume `docsuri-u5-95df9983c1b017e4-pgdata`). The person confirmed inbox
arrival; provider acceptance plus that confirmation is the recorded inbox
delivery. The mail app's built-in one-click unsubscribe worked. Afterwards the
tunnel change was rolled back and the U5 host stopped. Register:
[`../../../maintenance/u5-real-delivery-evidence.md`](../../../maintenance/u5-real-delivery-evidence.md).

**Browser confirmation failed, now fixed (R-15).** Pressing "구독 해지 확인" on
the public page returned `403 request.origin` from the host boundary. Root cause,
reproduced locally against the real `local_host` boundary: the boundary writes
`Referrer-Policy: no-referrer` (and its CSP) over every response, and the Fetch
standard serializes a non-CORS, non-GET request's `Origin` as `null` under
`no-referrer`. `PublicCancellationOrigin` removed only the exact approved origin,
so `null` reached the boundary. Earlier endpoint checks used header-less POSTs.
The same reproduction showed the page's own strict CSP never reached the browser
either.

Fix, in `backend/modules/topics/unsubscribe.py` only: the cancellation `HEADERS`
declare `Referrer-Policy: same-origin`. `PublicCancellationOrigin` (real
composition only, outermost, exact 43-character path, GET and POST only) now also
replaces the boundary's values with the page's own headers on the response. A
same-origin form POST then carries `Origin: https://docsuri.rvnnt.dev`, which it
already admits. Why this option rather than accepting `Origin: null`: `null` is
also what sandboxed and opaque contexts send, so admitting it would loosen the
boundary for any such context. The referrer-policy change keeps the boundary
unchanged and keeps the token URL from ever being sent as a cross-origin
referrer (`same-origin` sends none cross-origin; the CSP loads no subresources
and allows form posts to this origin only). Not widened: `null`, foreign origins,
other paths, other methods, the synthetic host and `local_host`.

Tests (no network):
- `tests/u5_topics_digests/fetch_origin.py` (new helper) implements the Fetch
  "append a request `Origin` header" rule, so tests derive the browser's `Origin`
  from the `Referrer-Policy` actually served.
- `component/test_real_composition.py` (5 new cases, real `local_host` boundary,
  no database): the rule itself; the page carries exactly its own referrer
  policy and CSP while other paths keep the boundary's; the browser confirmation
  under the served policy passes; the old `no-referrer` page yields the refused
  `null`; only the exact origin on the exact path and methods is admitted, and a
  header-less one-click POST still works.
- `integration/test_real_delivery.py`: the assembled `assemble_u5_real` case now
  checks the served headers, refuses `null`, foreign origins and another path,
  confirms with the browser-derived origin, and unsubscribes a second topic with
  a header-less one-click POST, all against the realm store.
- `integration/test_email_unsubscribe.py`: the router's header assertion changed
  from `no-referrer` to `same-origin` plus the CSP.

**Verification:** archived the delivery realm first (`archive-owned`, nothing
deleted), then a fresh realm `docsuri-u5-5302ce36da2f4551` (`setup`, `migrate`
65 migrations, `fixtures` 2 accounts and 2 papers). Collection **255 tests**.
Coverage phase **255 passed, 0 failures/errors/skips, 85.01% aggregate** (80%
floor), 16.8s, peak RSS 249,397,248 bytes, process stopped. Evidence
`/tmp/docsuri-u5-run/coverage-evidence-1792387423998293000.json`, source
SHA-256 `51c5e1925a58496f984c8b0da73ef3bbc756d3dc688ca63787d279720cf7f20f`
(bound `unsubscribe.py` digest
`99a11fc5eb122fb24e0d6fc5a2b89ab29859154d3ef908f1eee21e1d60d8b4ed`).
`unsubscribe.py` 92%; every new middleware line is covered (the misses are
pre-existing error branches). `u5_real_delivery.py` 97%, `u5_policy.py` 95%.
ruff check, ruff format and `git diff --check` pass on all changed Python.

**Not re-run live.** The fixed browser path has automated coverage only. The
sending realm has no allocation left, and the tunnel is rolled back. The runbook
(section 8) now has a dummy-token live check for the next real host.

**Documentation findings folded in:** R-11 (older sections below marked
historical), R-13 (real-delivery wiring section below; delivery-configuration.md
brought up to the decided configuration; traceability rows added), R-14 ("one
real attempt per realm database", with the erasure and fresh-realm resets, in
`backend/u5_policy.py`, `backend/u5_real_delivery.py`, the runbook and
delivery-configuration.md), R-15 (runbook endpoint gate), R-16 (preview sender),
R-17 (runbook run order).

**Known gaps (unchanged, accepted for now):**
- R-10: unsubscribing from the settings dialog asks for confirmation twice (the
  in-dialog confirm, then the outer `confirmTopic` dialog). No frontend file was
  changed in this step.
- R-12: four files are below 80% line coverage individually:
  `personalization/local_http.py` 35%, `scripts/serve_docsuri_u5.py` 71%,
  `scripts/u5_browser_fixtures.py` 73%, `accounts/services/guarded_entry.py` 79%.
  The aggregate floor is met.
- The synthetic host still serves the boundary's `no-referrer` on the
  cancellation page, so a browser confirmation there would be refused. Synthetic
  realms are loopback-only and their journeys unsubscribe through the signed-in
  UI, not the email link; the synthetic boundary was deliberately left unchanged.

**Still open:** the AI-DLC browser checkpoint receipt (needs its own fresh
fixtures-only realm; the current realm `docsuri-u5-5302ce36da2f4551` ran the
coverage suite, so preserve it first); a fresh independent review; a live re-run
of the browser confirmation path at the next real-host opportunity.

## Real-delivery wiring (R-13)

| Piece | Where | Behaviour |
|---|---|---|
| Real composition | `backend/u5_real_delivery.py` → `assemble_u5_real` | Resend adapter (`digest_mail_binding(synthetic=False)`), policy `REAL_DEMONSTRATION_TOPICS` (`u5-real-demonstration`, limit 1 per realm database, 30-day retention), `EmailUnsubscribe` bound to the public origin with an explicit aware expiry, and `PublicCancellationOrigin`. Refuses on any missing or invalid input; no fallback. |
| Host flag | `scripts/serve_docsuri_u5.py --real-delivery` | Without it the host is synthetic and never reads provider variables. |
| Activation file | `<realm>/real-delivery.json` (owner-only, run-bound, at most 4 KiB) | Exactly `runId`, `sender`, `permittedRecipient`, `unsubscribeOrigin`, `capabilityExpiresAt`, `freePlanVerified`, `unsubscribeEndpointVerified`; the gates must be `true`. Never holds the credential. |
| Credential | process environment | `EMAIL_PROVIDER=resend`, `RESEND_API_KEY` with the `re_…` shape; never written or logged. |
| Retention | `backend/modules/topics/u5_real_send_retention.sql` + scheduler sweep | `evidence_retain_until = attempted_at + 30 days` (DB maximum); afterwards a settled run's receipt is cleared and the row kept, so the allocation is not replenished. |
| Scheduler recipient filter | `backend/modules/topics/scheduler.py`, `repository.py` | The real composition reads only the permitted recipient's due topics and queued runs, before the bounded page. |
| Origin middleware | `backend/modules/topics/unsubscribe.py` → `PublicCancellationOrigin` | Exact origin, exact path, GET/POST; restores the page's own headers (R-15). |
| Refusal detail | `backend/modules/topics/u5_refusal_detail.sql`, `digest_email.py` | Provider status and error name on a refusal, set once; local reasons separate. |
| Operator tool | `scripts/u5_real_delivery.py` | `check`, `provision`, `prepare`, `preview`, `outcome`; never constructs the adapter or reads the key's value. |

Results with evidence: real wiring first verified **207 passed, 84.52%**
(realm `docsuri-u5-482869d6a89fa6c3`,
`/private/tmp/docsuri-u5-preserved-docsuri-u5-482869d6a89fa6c3-9efdf694/coverage-evidence-1792384373649846000.json`);
refusal detail 250 passed, 84.93% (realm `docsuri-u5-287134e8035e6532`, below);
R-15 fix 255 passed, 85.01% (above). All use fake transports.

## Step 14 — first real attempt and refusal detail — 2026-10-19 (historical; superseded by the current section above)

**First authorized real send: failed, real delivery still not done.** Realm
`docsuri-u5-a4ed677392fc22d7`, run `2ea6c002-f993-4cc6-9add-36a7867cb911`,
attempted **2026-10-19 04:49:59 UTC**, `pathKind: real`, outcome `failed` /
`delivery-path-refused`, no provider receipt and no acknowledgement. The realm's
single allocation is spent (`spent 1`, `remaining 0`). These facts were read
from the realm with the read-only `outcome` action before any change. The cause
is **most likely an unverified sending domain, not proven**: the sender was
`no-reply@docsuri.rvnnt.dev`, while a later read-only `GET /domains` (status
200, so the key is valid) listed only `mail.rvnnt.dev` as verified. The
transport then discarded the status code, and the same reason also covered
local pre-network refusals. The realm was preserved with `archive-owned`
(container stopped; nothing deleted) at
`/private/tmp/docsuri-u5-preserved-docsuri-u5-a4ed677392fc22d7-fe26b52f`.

**Refusal detail.** `ResendDigestMail.send` now returns, for 400/401/403/404/
413/422/429, the HTTP status and Resend's error `name` (`[a-z][a-z0-9_]{0,63}`,
else the fixed `name-unavailable`). It reads nothing else from the body, and a
malformed body cannot turn a refusal into `unknown`. Local pre-network refusals
return `recipient-not-permitted` or `unsubscribe-url-invalid`.
`DigestMailResult` rejects detail on non-refusals and inconsistent detail.
`DigestDelivery` records the reason and detail through
`TopicsRepository.finish_send`, which validates them before writing. The
appended migration `backend/modules/topics/u5_refusal_detail.sql` (owner
`topics`, 65th in the runner order) adds `provider_status`/`provider_error` to
`topics.delivery_outcome`. A CHECK allows them only on a `failed` /
`delivery-path-refused` outcome with a refusing status and a valid name or the
placeholder. The replaced `guard_outcome_update` makes them immutable. Not
recorded: the key, request headers, the response body, Resend's free-text
`message`, or any extra recipient data. Unchanged: refused → `failed`;
408/409/5xx/transport errors → `unknown`; no retry; allocation and retention.
`scripts/u5_real_delivery.py --action outcome` prints a `refusal` object:
`decidedBy` (`provider`, `local` or `unclassified`), `reachedProvider`,
`httpStatus`, `errorName` and `detailRecorded`. Legacy rows like the first
attempt show `detailRecorded: false` instead of a guess.

**Sender domain.** No code change was needed. `parse_activation` validates the
sender as one bare address and the unsubscribe origin separately, and
`ResendDigestMail` binds the cancellation link to the origin only. A new test
covers `no-reply@mail.rvnnt.dev` with `https://docsuri.rvnnt.dev`: activation,
send payload, preview, and refusal of a link on the sender's host.

**Verification (fake transport only, zero network; fresh realm
`docsuri-u5-287134e8035e6532`, 65 migrations):** collection 250 tests. Coverage
phase **250 passed, 0 failures/errors/skips, 84.93% aggregate** (80% floor),
16.4s, peak RSS 251,461,632 bytes. Changed files: `digest_email.py` 98%,
`delivery.py` 83%, `repository.py` 87%, `backend/u5_real_delivery.py` 97%,
`scripts/u5_real_delivery.py` 83%; every new line is covered. The first
coverage invocation in this realm stopped at collection (two new test modules
shared the basename `test_refusal_detail.py`; nothing executed); the repository
module was renamed `test_refusal_store.py` and the rerun passed. New checks:
`component/test_refusal_detail.py` (each refused status, placeholder cases,
local refusals with zero calls, result validation, outcome rendering),
`repository/test_refusal_store.py` (persisted detail, local reason, refusal
before write, immutability, schema CHECK), a refusal-detail case in
`component/test_topics_logic.py`, the sender-domain case in
`component/test_real_composition.py`, the persisted 422 detail in the real
allocation test, and an end-to-end provision → prepare → refused fake send →
`outcome` case in `integration/test_real_delivery.py`. ruff check and format
pass on the changed files.

**Still open:** real email delivery (needs a fresh realm, the runbook's
`GET /domains` check and the person's approval of a new preview); the AI-DLC
browser checkpoint receipt (needs its own fresh fixtures-only realm, because
the current realm ran the coverage suite); a fresh independent review.

## Steps 12–13 verification — 2026-10-19 (historical for real delivery; its mounted-browser result supersedes the status below)

**Browser supervision repair.** Browser verification observed two process trees
(Playwright and the companion host) by taking a separate `ps -A` snapshot per
root in every 50 ms tick. That doubled the process-table scans and measured the
trees at different instants; prior attempts stopped on `TimeoutExpired` from that
observation. `scripts/verify_docsuri_u5.py` now takes ONE bounded snapshot per tick
(`process_tree_rss(roots, deadline)`) and sums the union of both trees, so a shared
descendant cannot be counted twice. The 1-second per-observation limit
(`OBSERVATION_SECONDS`), the 1 GiB aggregate RSS budget, the 300-second phase bound,
log limits and the fresh-realm refusal are unchanged. Supervision records now add
`observations` and `slowestObservationSeconds` for diagnosis. The passing run below
shows the repaired path works; it does not prove the earlier timeouts had no
host-load component.

**Mounted browser checkpoint (exact authorized command, fresh realm
`docsuri-u5-bbedf7e857ba1c5d`, 63 migrations, fixtures only):** 4 tests, 0
failures/errors/skips, exit 0. Playwright 7.8s; supervision 8.17s, 121 observations,
slowest 0.0229s, peak RSS 909,737,984 bytes (within, but close to, the 1 GiB
budget), process stopped. Journeys: follow/preferences/settings/unsubscribe 1.32s;
scheduler → local-sink delivery with Korean/Asia/Seoul propagation 4.99s; recorded
empty digest with no send 0.50s; explicit unknown resolution 0.46s. Source
SHA-256 `2097abb709a6be4bbb2645474755e309f1540bae6b5f1d5e73a014541a5f38f5`.
Realm preserved at `/private/tmp/docsuri-u5-preserved-docsuri-u5-bbedf7e857ba1c5d-a52f4219`.
This direct run is not the AI-DLC checkpoint receipt; that must still be produced
through the checkpoint verifier on a fresh realm.

**Frontend (Step 12):** new `frontend/test/u5-topics/settings-dialog.test.tsx`
(13 cases: unconfigured zone, Korean non-default readout, unreadable preferences,
preference-save refresh, weekly day gate with day/window body, stale weekday
dropped, unchanged save, initial read failure, reload failure, Escape and Tab
trap, in-dialog unsubscribe confirm/cancel, local-sink vs real path labels).
Scoped Vitest: **35 passed**, U5 lines **97.93%** (floor 80%); typecheck, CI lint
command, Prettier and Vite build pass. `topics.test.tsx` was Prettier-formatted
only.

**Backend (fresh realm `docsuri-u5-272f4bac81e78719`):** coverage phase **158
passed, zero failures/errors/skips, 82.94% aggregate** (80% floor), 13.2s, peak
RSS 243,924,992 bytes. Three new runner regressions: one snapshot per tick for both
roots, union without double counting under the unchanged limit, refusal after the
deadline. Per-file gaps remain below 80%: `personalization/local_http.py` 35%,
`scripts/u5_browser_fixtures.py` 73%, `scripts/serve_docsuri_u5.py` 70%,
`accounts/services/guarded_entry.py` 79%.

**Static and inherited checks:** ruff (CI file list plus `digest_email.py`)
passes; canonical schema and generated-binding drift checks pass; shared contract
suite 161 passed; U1 transport/records regression 13 passed; U2 transport/runtime
regression 39 passed.

**Still open:** real email delivery (no sender, recipient, or authorized message;
nothing sent); the AI-DLC browser checkpoint receipt; a fresh independent review.

## Repair status — 2026-10-19 (historical baseline)

> **Historical baseline evidence (R-11).** This section and "Repair
> verification" below are kept as recorded before Steps 12–14. Their statements
> that mounted acceptance is unverified, and that no sender, recipient or real
> send exists, are superseded: the mounted browser run passed (Steps 12–13), and
> a real digest was sent and reached the inbox (Step 14, current section).

This section superseded the earlier implementation account below. Local repairs
are implemented; completion and merge remain pending.
Resend is selected, but the human confirms no sender address or test recipient
exists. No external email was sent and no provider account or domain was created.
See [external evidence prerequisites](../../../maintenance/u5-real-delivery-evidence.md).

The repair adds authoritative C03 language/standard-level/IANA-zone settings,
owner-authorized background reads, actual English/Korean presentation, immutable
preference snapshots and send-admission fencing. The schedule filters due owners
before pagination, retains intended weekly dates after late execution, uses one
aware instant, and handles DST gaps/folds with finite searches. Appearance-only
changes preserve prepared work; effective preference changes discard only unsent
work. Account bootstrap and logout retain account-control authority after research
consent withdrawal; research delivery still requires consent.

The account-owned digest adapter returns accepted/refused/unknown with actual
receipt and acknowledgement time. Local profiles cannot access the network;
real composition requires explicit free Resend configuration and a finite durable
send budget. Initial requests use immutable idempotency keys; reconciliation
never sends again. A hash-only, run-bound cancellation capability supports an
inert confirmation GET and bounded cookie-free RFC8058 POST; existing browser
authorization remains unchanged. The assembled middleware/store test uses actual
lifespan and a real capacity refresh; it proves the route boundary, not startup
readiness. Public HTTPS, DKIM, proxy logging and real delivery remain unverified.

### Repair verification (historical baseline)

Stable-source backend verification at the time: **155 passed, zero failures/errors/
skips, 82.94% aggregate coverage**, retaining the 80% floor. Runtime was 93.61s,
peak RSS 215,433,216 bytes, and the process stopped. Immutable evidence:
`/private/tmp/docsuri-u5-preserved-docsuri-u5-68f00b6ee0bcf67a-aa7edb82/coverage-evidence-1792342925464628000.json`.
This supersedes the earlier 148/146-check backend results below.

The browser fixture helper now derives absolute interpreter/script/root paths
from its source URL. Both repository-root and frontend working-directory path
checks, scoped and explicit helper TypeScript checks, and formatting pass.
A mounted attempt reached one passing journey before exposing a nested runner
lock in synthetic clock advancement. The repair retains the parent's exclusive
phase lock and delegates only clock advancement through a private run-bound,
short-lived capability. Only the Playwright process receives its plaintext
token; persistent metadata holds its hash. The child validates run, expiry,
live lock owner and active lock. Setup/unrelated phases still require exclusive
ownership. Capability metadata is removed on success/failure; broad child
environment construction is unchanged. Seven focused checks pass, including an
actual spawned child, refusal cases and cleanup; they also pass in the 155-test suite.

Mounted acceptance remains **unverified**. The final attempt stopped on recurring
process-observation TimeoutExpired before a test report: exit 1, supervision-error,
37.712s, 625,885,184-byte peak RSS and stopped process. No causal claim about
host load is established, and monitoring/time/resource bounds remain unchanged.
No more retries were made. The complete four-journey mounted proof and real
provider demonstration remain prerequisites for unit completion and merge.
Final browser evidence is preserved at
`/private/tmp/docsuri-u5-preserved-docsuri-u5-87dd16122f1ae63d-a65cdc86/browser-evidence-1792343092561092000.json`.
The current Vite build passed in 7.921s, peak RSS 571,785,216 bytes. Browser
execution began (34 log bytes), then supervision failed; this attempt is not
described as a startup failure. Source SHA-256:
`4f6e3d10f17129f4352175e262775b63770b184ea2dbd6f4170befab6914cd6d`.
The database is stopped and its volume retained.

Subsequent scheduling repair filters consent-stopped owners and topics with
prepared/sending/unknown work before the bounded due page. Queued sending,
reconciliation and consent cleanup remain separate phases; admission still
rechecks authority. Two new real-store cases seed 51 blocked topics ahead of
two eligible topics, exercise three finite passes and assert no additional
attempts for blocked topics. The first supervised component attempt stopped on
process-observation TimeoutExpired after five progress markers, before a report:
`/tmp/docsuri-u5-run/component-evidence-1792341362321630000.json`.
The failed process was stopped and its realm preserved at
`/private/tmp/docsuri-u5-preserved-docsuri-u5-eddddd3bf264167a-ff27e224`.
After a separate bounded host startup diagnostic passed, one fresh coverage
retry completed: **148 passed, zero failures/errors/skips, 83.08% aggregate**,
88.60 seconds, 232,833,024-byte peak RSS, stopped process. Both 51-blocked-topic
cases passed, including repeated finite passes and no new blocked-owner sends.
Evidence: `/tmp/docsuri-u5-run/coverage-evidence-1792341719463695000.json`, realm
`docsuri-u5-dd539733ed2faf50`. This verifies the subsequent scheduling change;
the 146-check result below remains historical. Mounted browser verification is
coordinated separately after preserving this backend realm.

The prior stable-source coverage command in unit-test-instructions.md completed with
**146 passed, zero failures/errors/skips, 83.33% aggregate coverage**. The runner
recorded 83.20 seconds, 219,004,928-byte peak RSS and a stopped process. Evidence:
`/tmp/docsuri-u5-run/coverage-evidence-1792339838010455000.json`, realm
`docsuri-u5-dbef52eaa00ced76`. Exact scoped collection also found 146 tests.
This includes both final runner regressions; no coverage threshold was lowered.
Individual gaps remain (for example fixture helper74%); aggregate passage does
not establish untested real transport or mounted browser behavior.

- Scoped initial collection: 81 baseline tests. Repaired backend coverage:
  **144 passed, zero failed/errors/skips, 83.33% aggregate**, with changed inherited
  account/personalization files included. Evidence is preserved under
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-d11d5b70b57c1935-9f68eda7/coverage-evidence-1792338687405729000.json`.
  This historical repair pass predates the final runner regressions; the final
  146-check result above supersedes it.
- Earlier repair aggregate: 137 passed but 75.68% coverage, correctly failed.
  Seven meaningful inherited session/settings checks added; they exposed and
  verified the consent-independent logout fix. Component pass: 41 checks.
- Frontend: approved scoped typecheck passes; Vitest 22 passed, 92.27% lines.
  Shared canonical export check and Python binding check pass.
- Browser: four journeys prepared, including empty/no-send. First clean-realm
  attempt stopped on host process-observation timeout before any product assertion;
  logs/volume preserved at
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-5a9c245c5a5e48a2-06f63a09`.
  The one-second observation limit remains unchanged. Runner now records
  subprocess supervision failures and stops children; focused regression passes.
  One accidental direct full operations-file invocation had 11 passes and five
  missing-manifest setup errors; it is not counted as a suite pass.
- A subsequent browser attempt produced one failure and three not-run journeys:
  the host served old static assets without the new preference controls. That
  failed realm is preserved at
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-5cc14ee5470b8ed8-2dd9b197`.
  The runner now rebuilds the current Vite entry before serving, records build
  command/log/supervision, and refuses failed builds within the original total
  300-second bound. The focused failed-build regression passes. Final mounted
  verification remains blocked: the corrected run built successfully in 5.75s
  (581,877,760-byte peak RSS), then host startup observation raised TimeoutExpired
  before tests began. The failure has no test report and no fabricated process
  metrics. Preserve its full evidence at
  `/private/tmp/docsuri-u5-preserved-docsuri-u5-5aeb407c0268ad99-1e66dc21/browser-evidence-1792339535341341000.json`.
  No further browser retry was made before rechecking process observation. The empty-state mounted proof and
  Step12 remain open pending a complete mounted run under the original bounds.

All stateful phases use the exact commands in unit-test-instructions.md. Earlier
layer passes were database16, repository19, component34, integration22 and
operations46 before the seven inherited regressions. The backend/browser realms
are independent; a consumed or failed realm is archived, never cleared or extended.

### Migration and remaining evidence

Fresh corrected **63-migration** installations and the additive **62→63** path
were exercised. These do not prove adoption of the original failed 59-migration
realm: its selection-comment bytes differ, so immutable ledger checks refuse drift.
Preserve that original realm and create the fresh synthetic replacement; never
rewrite its receipts. No existing-user migration is authorized or claimed.

The scoped runner, selection comment, preference inheritance and owner-zone
scheduling repairs are implemented and locally tested. Typed real delivery and
cancellation are implemented, but actual external acceptance and correlated
recipient evidence remain unavailable. The four mounted browser journeys still
need a completed pass under the original process/resource bounds.

The source manifest enumerates existing U5 contributions and all repair source,
tests and generated bindings. Existing account/corpus/research boundaries are
exercised through the real assembled store; no whole-release parity claim is made.
Historical results below remain historical evidence, not the repaired-source proof.

Date: 2026-10-18 (Asia/Seoul)
Unit: u5-topics-digests. Branch: `feature/u5-topics-digests`. Contract: AIDLC-TESTING-CONTRACT `sha256:0b3bdbd990d6def665d447995282ba760f054c761c3ccf40dbbb9fc1b114553b` (methodology test-after, 80% line floor, existing suites stay green).

## What was built

TopicsDigests joins the one assembled release as an embedded module: topic
follow/unsubscribe/reactivate, per-topic digest settings with revision-checked
saves, a bounded scheduler (due evaluation, idempotent preparation, single send
attempt per pass, orphan sweep, evidence-based reconciliation), digest email
through the built accounts seam, and lifecycle participation under the shared
coordinator contract.

- **Schema (Step 3)** — `topics` owner schema: `followed_topic` (identity
  immutable, one row per (account, normalized key), reactivation reuses the
  row), `digest_settings` (weekly⇔delivery-day CHECK, monotonic revision),
  `digest_run` (state machine `prepared→sending→sent|failed|unknown` plus
  `empty|discarded`; window uniqueness excluding discarded; single-flight
  partial index; unknown-pause and sending-age indexes; deterministic empty
  content), `delivery_outcome`, `send_log_entry`, `topic_delivery_watermark`,
  `lifecycle_evidence`, nine guard functions with triggers, grants mirroring
  the research owner (no DELETE, no cross-schema writes).
- **Repository (Step 5)** — `TopicsRepository`: every owner path rechecks live
  authority (`guard`), worker units run in bounded system transactions,
  multi-step flows are atomic (settings save discards prepared runs BR1.3;
  send start enforces active/consent/pause in the checked transition
  BR3.1/3.2/4.2; terminal sends append the watermark from the run's own
  content BR2.2; reconcile applies the watermark exactly like a direct send).
- **Business logic (Step 7)** — `TopicsService` (normalized keys, shaped
  payloads, resolve that names its assumption), `DigestPreparation`
  (eligible-corpus selection in the inclusive window, watermark excluded,
  bounded by policy), `DigestDelivery` (single send per attempt through the
  additive `send_digest_email` seam; transport facts land before the outcome,
  so a crash leaves an unknown that evidence can still reconcile; unobserved
  transports pause as unknown; failures record a plain reason and are never
  re-sent), `TopicsScheduler` (sweep → reconcile → consent-stop drop → due
  evaluation → send, each bounded), `TopicsDigestsLifecycleParticipant`
  (withdraw unsubscribes + drops queued work; erase removes every digest fact;
  evidence written by the shared `apply_owner_effect` writer).
- **HTTP (Step 9)** — literal REST `/api/v2/topics…` on the owned HTTPS origin
  with the shared error vocabulary (`DUPLICATE→CONFLICT`, revision
  `CONFLICT→STALE_REVISION`), owner checks on every access, foreign and
  nonexistent identifiers indistinguishable (404).
- **Frontend (Step 11)** — `src/u5-topics/**`: TopicsView (h1, SWR with a 4s
  pipeline refresh), FollowedTopicsSection/TopicList/TopicRow
  (TopicSummary with icon+text last-digest indicator, DigestSettingsLink,
  ResolveUnknownControl, UnsubscribeButton), FollowTopicAction,
  DigestSettingsForm (cadence/time/day/window, inherited-level note,
  acknowledged save states, stale-revision reload offer — never a blind
  retry), ConfirmationDialog (focus trap, Escape, focus return), Korean
  labels throughout. Transport gained `put`/`del` (DELETE carries CSRF without
  a body) and a topics route pattern in `safeApiPath`.
- **Environment (Step 13)** — `scripts/verify_docsuri_u5.py` (phases
  setup/migrate/fixtures/archive-owned/{database,repository,component,
  integration,operations,coverage}/frontend/browser/serve/teardown),
  `scripts/serve_docsuri_u5.py`, `scripts/u5_browser_fixtures.py` (two
  synthetic accounts, two dated papers, and a guaranteed unresolved-unknown
  fixture case for the resolve journey), `backend/.coveragerc.u5`,
  `frontend/{vitest.u5-topics.config.ts,tsconfig.u5-topics.json,
  playwright.u5-topics.config.ts}`, scoped CI lane
  `.github/workflows/u5-topics-digests.yml`.

## Recorded verification evidence before environment recovery

The following results predate the expiry-preservation repair described below.
The old realm is expired and these results do not verify the changed source or
the current completion checkpoint.

Realm `docsuri-u5-3617b2afe7ed52de` (`/tmp/docsuri-u5-run/environment.json`,
LABEL `dev.docsuri.u5.run`, ports 15489/18089, policy `u5-synthetic-v1`):

- `--phase setup` → base-installed; `--phase migrate` →
  `{"state": "u5-migrated", "migrationCount": 59}` (8 base schemas + 22
  amendments + 29 migrations including the appended correction below).
- `--phase database` → 10 passed; `--phase repository` → 9 passed (re-run
  twice against accumulated state); `--phase component` → 11 passed (twice);
  `--phase integration` → 5 passed (twice, mounted TestClient over the real
  realm); `--phase operations` → 15 passed; `--phase coverage` → 50 passed,
  **87.86%** line coverage against the 80% floor.
- `--phase frontend` → 14 Vitest/RTL tests passed; `--phase browser` → 3
  mounted Playwright journeys passed (twice): follow → settings → unsubscribe;
  follow → scheduler pass → local-sink delivery with the indicator updating;
  the resolve control closing a real unresolved unknown.
- Local-sink delivery evidence: the scheduler journey's digest send is recorded in
  `topics.send_log_entry` with `path_kind='local-sink'` and acknowledged
  transport facts (`acknowledged_at`), and the delivery outcome row records
  `sent`. No send anywhere claims `pathKind='real'`: the synthetic policy is
  synthetic-only, so the capability stays truthfully degraded
  (`u5-synthetic-topics`, `synthetic-only: true`).

## Expired-environment recovery checks

Normal execution correctly refuses the original expired realm. Archival formerly
used that execution loader too, preventing preservation after expiry.
`LocalProfile.preservation_identity` now validates custody, identity and finite
original timestamps without granting an executable profile. `archive-owned`
retains the exact resource, private-file, idle-process and active-database-client
checks before stopping and preserving the owned resources. It does not extend
expiry, reset quotas or delete the database volume.

The new archival regression suite contributes 31 checks. Together with the
existing U4 profile-binding suite, the focused run passed **48 tests** with one
warning. Ruff on the three changed files and `git diff --check` passed.

Actual archival preserved the old files and database volume without changing
expiry. Fresh Colima realm `docsuri-u5-bbf3b6a7f306e989` then applied 59 migrations
and loaded two synthetic accounts and two papers. The coverage phase passed
**81 tests, zero failures/errors/skips, 87.87% aggregate coverage** against the
unchanged 80% aggregate gate. The first attempt was blocked before tests by the
sandbox's denial of `ps` memory supervision; the identical command passed with
scoped escalation. Both attempts' evidence was retained. The current browser
completion checkpoint is still required; the original realm's browser counts
above remain historical evidence.

## Decisions and deviations

1. **Appended corrective migration.** The database probes caught the
   chronology gate firing on same-window duplicates (`<=` instead of `<`),
   masking the unique index's `UniqueViolation` with a `CheckViolation`. The
   runner refuses changed applied migrations ("append a new migration"), so
   `backend/modules/topics/u5_run_guard.sql` (CREATE OR REPLACE with the
   strictly-earlier gate) was appended to MIGRATIONS — the realm stays
   append-only and fresh realms apply both files.
2. **Lifecycle chain composition.** `u2_controls.sql` was NOT imported: it
   collides with `u3_session_authority.sql` (both `ALTER accounts.session ADD
   COLUMN purpose` with different CHECK sets) and would flip the inherited
   `guard_session` semantics. Instead `u5_lifecycle_tables.sql` carries the
   lifecycle DDL verbatim, the canonical `u2_lifecycle_effect.sql` /
   `u2_lifecycle_action.sql` are imported, and `u5_lifecycle_guard.sql`
   mirrors the owner-grants for `topics`. `accounts.entry_receipt` comes from
   the U1 amendment `local_entry.sql`, already in the base.
3. **SCHEMAS vs OWNERS (plan Step 13 wording).** The plan said "SCHEMAS
   extended with topics"; the shipped runner keeps `SCHEMAS` as the frozen U1
   receipt-bearing base and adds `topics` through `OWNERS` + MIGRATIONS — the
   same effect with no topics receipt table. Recorded as the deliberate
   resolution of the plan conflict.
4. **Coverage denominator.** `backend/.coveragerc.u5` measures the production
   surface (topics modules, policy, host, serve, fixtures) at 87.86%; the
   verification runner itself is excluded. U4 measured its runner because its
   operations suite (≈1,200 lines) exercised it; U5's runner is the
   measurement harness — self-measuring it needs nested coverage data files —
   and its safety boundaries are locked by the 15 operations tests. Recorded
   as the deliberate U5 deviation from the U4 include shape.
5. **Scheduler paging.** The first paging draft (oldest-first page over active
   topics) starved new topics once the persistent realm accumulated actives.
   Due-ness moved into the SQL read (`due_topics(zone, limit)`) with a
   separate `consent_stopped_runs` sweep, so every returned row is work the
   pass can attempt.
6. **Rolling windows.** Windows are the settings' rolling bound
   (`[today-(days-1), today]` in the one stated zone `Asia/Seoul`); the
   watermark, not window tiling, prevents repeats. This makes BR3.3's clause
   ("a failed window's content is re-delivered by a later window while inside
   its bounds") reachable and keeps BR2.4's watermark rationale intact.
7. **Shared error vocabulary.** The wire enum has no DUPLICATE code: a
   duplicate follow surfaces as `409 CONFLICT`; a revision-checked save
   refused on a stale revision surfaces as `STALE_REVISION` so the client can
   reload; a second resolution attempt on a closed run is `409 CONFLICT`.
8. **One writer per table.** Lifecycle evidence is written by the shared
   `apply_owner_effect` contract like every other participant; the
   repository's planned lifecycle methods were removed rather than duplicating
   that writer.

   **Eight tables, not six (Build and Test loop-back 1, Step 17).** The design's
   "six owned entities" (`functional-design/entities.md`) are `followed_topic`,
   `digest_settings`, `digest_run`, `delivery_outcome`, `send_log_entry` and
   `topic_delivery_watermark`. The design predates the other two tables in the
   `topics` schema: `lifecycle_evidence`, the participant's disposition record
   that `apply_owner_effect` writes (in `u5_schema.sql` since the first build),
   and `email_unsubscribe`, the one-click unsubscribe capability the repair added
   (`u5_unsubscribe_capability.sql`). Both belong to TopicsDigests alone.
   `database/test_owner_grants.py` pins the eight tables and checks that the
   topics login is their only writer.
9. **Digest item shape** (resolved at Step 5): `{versionId, paperId, title,
   publishedOn}` — opaque jsonb to the repository, rendered by the email
   assembler and available to the API reads.
10. **Wiring additions beyond the plan's named files** (all in-service chain
    edits the unit required): `backend/artifacts.py` (u5 run root whitelist),
    `ops/src/docsuri_ops/local_transport.py` (U5 realm binding),
    `backend/local_profile.py`/`backend/transactions.py` (u5 realm pair plus
    the `DeadlineConnection.transaction()` savepoint seam),
    `backend/local_browser.py` (TOPICS_ORIGIN),
    `backend/local_observation.py` (topics observation probe),
    `backend/u3_host.py`/`backend/u4_host.py` (factory plumbing),
    `backend/modules/accounts/local_http.py` (the entry surface accepts the
    topics origin), `backend/modules/accounts/integrations/email.py`
    (additive `send_digest_email` seam), `backend/lifecycle_effects.py` +
    `backend/control_worker.py` (participant registration — the shared
    manifest was deliberately not extended, so coordinator realms without the
    topics schema never dispatch TopicsDigests tickets).
11. **`archive-legacy` dropped** from the runner: no superseded U5 prototype
    exists to preserve (the idle U4 prototype was stopped by the orchestrator,
    not by this unit).
12. **Local-only note:** the `frontend` phase's first invocation failed on a
    cold corepack cache (a pnpm download attempt while
    `COREPACK_ENABLE_NETWORK=0`); the warm cache cleared it. The CI lane
    installs pnpm explicitly, so the lane is unaffected.
13. **Realm-persistent test design:** every suite re-runs against accumulated
    realm state (unique follow keys, membership-based corpus assertions,
    stable uuid5 accounts, the fixtures' forward-window resolve case). The
    repository/coverage passes were each verified twice.

## Known limits (historical, 2026-10-18; see the current Step 14 section for today's gaps)

- The synthetic profile's email path is the local sink; a real configured
  path (`pathKind='real'`) stays unimplemented by policy until a maintainer
  configures a free provider — the capability row stays `degraded`.
- The current digest preparation does not read account language/level
  preferences. The email content is Korean and the UI's inheritance note
  overstates the implemented behavior. The synthetic policy also uses one
  `Asia/Seoul` delivery zone. FR1.2's preference inheritance and owner-timezone
  behavior remain incomplete; preserving these requirements is not evidence
  that they have been implemented.
- The delivery plan requires real delivery evidence. Local-sink acknowledgement
  is useful integration evidence but does not meet that completion condition.
- The list read carries each topic's latest non-discarded run and last
  outcome; the settings read carries the per-run history (bounded 10).
- The resolve control keys off the latest non-discarded run, which real
  chronology (BR2.4) guarantees is the open unknown; the fixture seeding
  respects that invariant.
