# U2 operations verification — scoped transport and restore evidence

Date: 2026-10-14 KST. This records the transport/restore implementation subset of Step 13. It does not mark all V1–V9 scenarios, U2, public operating feasibility, or the cumulative completion checkpoint complete. The approved test-after methodology and 80% actual-production coverage floor are unchanged.

## Implementation and authority boundaries

- `ops/src/docsuri_ops/local_transport.py` accepts only the explicit U1 and U2 profile/origin/database tuples. U1 keeps `journey-tls.*`; U2 uses `account-controls-tls.*`. Certificate/private-key custody, pair matching, origin/run/expiry binding and private modes are checked. No system trust modification occurs.
- `scripts/prepare_docsuri_u2_browser.py` performs an explicit offline, frozen pnpm 9.15.9 installation and atomically reconciles only source/dependency identity with its ownership marker. Interrupted pairs require explicit rollback recovery. It preserves run identity, expiry and database contents. Its process-group supervisor enforces a finite deadline, sampled 1 GiB process-tree RSS allowance and 16 MiB aggregate private browser-log allowance. The SIGTERM regression found that `InterruptedError` could be swallowed by a selector; the handler now raises `RuntimeError` so child cleanup executes.
- `u2_restore_context.py` defines immutable run/checkpoint/sequence/previous-digest, backup/source/schema/policy/participant-digest and fixed-target bindings. It rejects ambiguous JSON and incomplete, repeated, foreign or unbounded owner fragments. Hashes identify content; the coordinator separately verifies authenticity and currentness.
- `u2_restore.py` uses the current `docsuri_u2` database as the monotonic checkpoint authority. A complete authenticated journal is fsynced before the source anchor is advanced. Callers must hold the existing exclusive fixture lock and stop writers. The application port and owner connections are checked before capture/reconciliation. The fixed target is `docsuri_u2_restore`; no source database drop/overwrite command exists in the coordinator.
- Older custom-format PostgreSQL archives stream between the host and the owned container; they are not staged in the container's 16 MiB `/tmp`. The five-minute experiment includes a seven-second cleanup reserve. Archive client identity is checked before remote termination; local process groups are terminated and reaped. SIGTERM/INT during streaming preserves quarantine and invokes cleanup.
- The target denies runtime-role `CONNECT`. Its private guard binds the exact authenticated starting checkpoint, allowing a fresh target to start from a later source sequence. Subsequent owner receipts remain monotonic and linked. Only six existing schema-owner roles receive the narrow public-schema identity/guard reads needed by their definer functions. The public runtime profile allowlist is unchanged.
- AccountAccess, DiscoveryCitations, Library, Personalization, PaperAssistance and UsageEntitlements reconcile through their actual owner hooks. Exact receipt replay returns before repeating cleanup, preserving later permitted work. Missing/newer private payloads, in-flight work, changed source restrictions, incomplete owners, incompatible metadata and missing/tampered/stale journal/key evidence prevent a successful reconciliation. Even a successful result is `reconciled-quarantined`, with `activated: false`.

## Commands and observed results

All commands below ran from the repository root with the existing `backend/.venv` environment. Process-control tests ran with OS permission to inspect and stop only their own process groups. No test threshold was lowered.

```sh
PYTHONPATH=.:ops/src backend/.venv/bin/python -m pytest \
  -c backend/pytest.u2-account-personal-controls.ini \
  tests/u2_account_personal_controls/operations/test_browser_bootstrap.py -q
```

Result: **23 passed in 0.65 seconds** after correcting SIGTERM. The new external-signal test had first reproduced a seven-second timeout; after the fix it stops the actual wrapper and its child before the ordinary deadline. Existing already-running wrappers need a restart to pick up the correction.

```sh
DOCSURI_U2_ENVIRONMENT_FILE=/tmp/docsuri-u2-run/environment.json \
PYTHONPATH=.:ops/src COVERAGE_FILE=/private/tmp/docsuri-u2-restore-actual.coverage \
backend/.venv/bin/python -m coverage run --source=docsuri_ops.u2_restore -m pytest \
  -c backend/pytest.u2-account-personal-controls.ini \
  tests/u2_account_personal_controls/operations/test_recovery_restore.py::test_actual_old_backup_reconciles_newer_restrictions_and_replay_preserves_work \
  -q --tb=short
```

Result: **1 passed in 2.13 seconds**, real PostgreSQL on run `docsuri-u2-c274e71798431965`. The initial attempt stopped after a real restore because the schema-owner definer lacked `USAGE` on the restored public schema. Its source, archive and journal were retained; only its authenticated quarantine was removed. Narrow identity grants were added after archive ACL replay. The successful attempt used two additional dedicated fixture accounts, leaving four restore-fixture accounts total within the 20-account policy. Other users' fixtures were not repurposed.

The successful test made an actual older dump, then closed/released the open PA admission using the actual PA/Usage owner methods and changed the dedicated fixture's current consent/session, reset/history and erasure restrictions. It recorded two successive checkpoints and restored a fresh target at sequence 4. It first observed the old unrevoked session and erased owner's glossary in that target, demonstrating that the test used the older archive. It then verified all six owner receipts, erased private rows (including a glossary with no admitted job), old event suppression, released reservation identity/original period/quantity, rejection of late acceptance, and denial of the old session. Exact replay preserved a newly created target session, saved query and permitted post-boundary behavior. The original source's post-boundary row survived. Journal tampering and a missing recovery-key copy each refused reconciliation. The authenticated target was dropped only after successful checks; source data and evidence remain.

```sh
PYTHONPATH=.:ops/src COVERAGE_FILE=/private/tmp/docsuri-u2-restore-unit.coverage \
backend/.venv/bin/python -m coverage run --source=docsuri_ops.u2_restore -m pytest \
  -c backend/pytest.u2-account-personal-controls.ini \
  tests/u2_account_personal_controls/operations/test_recovery_restore.py -k 'not actual' -q
COVERAGE_FILE=/private/tmp/docsuri-u2-restore-combined.coverage \
backend/.venv/bin/python -m coverage combine --keep \
  /private/tmp/docsuri-u2-restore-unit.coverage /private/tmp/docsuri-u2-restore-actual.coverage
COVERAGE_FILE=/private/tmp/docsuri-u2-restore-combined.coverage \
backend/.venv/bin/python -m coverage report --show-missing
```

Result: **38 passed, 1 deliberately deselected in 0.70 seconds**; the deselected real test had already run independently. Current-source isolated coordinator coverage: **88%, 408 statements, 51 uncovered**. A combined diagnostic reports 96%, but the real-run data precedes a formatting-only source change; it is not accepted as same-source final coverage. The scheduled combined operations run must recollect both datasets against frozen source. The 88% scoped measurement is not the final all-U2 coverage denominator. The real-test fixture was subsequently adjusted to reuse the inherited session fixture's lock when selected in the combined operations suite; that combined selection still requires its scheduled run. The isolated tests cover custody, authentication, altered/incomplete metadata, resource refusal, process failure/deadline, archive integrity, source-anchor ordering, quarantine-only restore and complete owner receipts.

Shared context verification previously passed **49 tests with 100% of 111 statements**. Narrow transport verification previously passed **26 tests**, with 96% aggregate coverage of transport/prepare/serve at that revision. The later parent-owned U2 admission middleware and serving concurrency changes require their own current verification; those earlier transport numbers are not evidence for the changed middleware. A legacy U1 transport fixture was expired and produced setup errors; no expiry bypass was used and no current U1 regression pass is claimed here.

Ruff passed for the current coordinator, recovery tests, bootstrap helper and bootstrap tests. The final all-source coverage, schema compatibility and cumulative U1/U7/U2 verification remain separate obligations.

## Retained rehearsal footprint

Source: private `restore-evidence/rehearsal-be665731-9cf4-4ca5-8cfd-eb723d3ba01a.json`, not committed because the directory also contains synthetic private data. These are measured reconciliation snapshots, not worst-case growth or peak-RSS guarantees.

| Measurement | Observed bytes | Safety ceiling |
|---|---:|---:|
| Current source database | 11,140,119 | Live DB plus WAL: 536,870,912 |
| Current WAL | 33,554,432 | Included in live allowance |
| Restored database | 11,238,423 | 536,870,912 |
| Successful archive | 264,719 | All archives: 268,435,456 |
| Both retained archives | 527,457 | 268,435,456 |
| Journal/evidence at reconciliation | 39,216 | 268,435,456 |
| Journal/evidence after report | 41,303 | 268,435,456 |
| Unspent required recovery reserve | 2,617,245,696 | 2,496 MiB reserved within 4 GiB |

Successful archive digest: `b3d7affd21649ae6dd50fdad9cb17b660187341344bb886d6b0de238d452f39c`. Schema digest: `b0c38de36b4ea0ff2f0dedeceff7a4cc624730670474267bdfb0c631909909d4`. Source-tree digest captured for that attempt: `eb0e645ad562dc902318262575bf217a7c9913ab0a099ac4129b3eb9ec61500b`. The private authenticated metadata also records policy and the six-owner restore-participant digest. This restores six owner datasets; it is not an assertion that all lifecycle scopes are complete.

The coordinator samples DB/WAL/restore and owned archive/evidence occupancy while streaming; verifies the container's 1 GiB hard memory setting; checks separate archive/evidence caps and physical reserve; and refuses overruns. API/browser RSS, build headroom, aggregate diagnostics, 80% admission cutoff, maximum allowed in-flight/WAL maintenance growth and the complete combined resource experiment are not established by this small rehearsal. Its 2.13-second total pytest duration is a single sample, not an agreed RTO/RPO or service target.

## Remaining evidence boundaries

- The paired HMAC journal keys are private and checked on every journal read. This rehearsal predates the separate account-control keyring rotation test. A complete backup-specific verifier/keyring recovery bundle, rewrap/old-key retirement evidence and host-loss recovery are not proved by this coordinator run.
- This is same-host synthetic recovery, with current authority outside the older archive. It does not establish independently durable off-host restriction evidence, choose production retention, authorize restored reads/effects, or migrate real users.
- Capture relies on the caller's exclusive fixture lock and stopped writers; the owner export transactions are not a cross-owner PostgreSQL snapshot. Runtime compatibility and source hashes are checkpoint bindings, not permission to substitute a full current database for owner reconciliation.
- A future full operations run must retain its finite account allocation and rerun the actual test in the combined suite. Failed checkpoints/archives are retained; repeated diagnostics cannot allocate unlimited new accounts or discard mandatory evidence to fit a ceiling.

## 2026-10-14 later — full supervised operations phase and current footprint

All runner phases were then executed under their own supervision on run `docsuri-u2-c274e71798431965`; every phase returned `{"state": "passed"}` with exit code 0:

| Phase | Result |
|---|---|
| `component` | passed; 111 tests, zero failures/errors/skips |
| `database` | passed; 24 tests (incl. the new migration/restart identity checks) |
| `repository` | passed; 14 tests |
| `integration` | passed; 38 tests |
| `frontend` | passed; 92 Vitest tests |
| `browser` | passed twice; 13 journeys, 90.4 s phase, 910 MB peak supervised browser RSS inside the 1 GiB budget |
| `operations` | passed; **194 tests, zero failures/errors/skips**, including the actual older-backup rehearsal |

The browser phase now performs its own fixture preparation (idempotent corpus and identity fixtures, admin-side discard of only its disposable rotated identities, MFA recovery rows included), clears the finite entry-admission window, starts the owned host, and stops it afterwards. A real defect was found and repaired along the way: a fixture-discard sweep could leave `accounts.mfa_recovery` rows orphaned when it removed enrollments, which then made every `pg_restore` of a dump fail on foreign-key validation. Both discard helpers now remove recovery rows first, the realm is orphan-free (checked across every foreign key), and the actual restore rehearsal passes again.

### Current measured footprint (same source identity)

| Measurement | Observed bytes | Safety ceiling |
|---|---:|---:|
| Source database (`operations.capacity_footprint().database_bytes`) | 15,580,183 | Live DB plus WAL: 536,870,912 |
| Current WAL | 33,554,432 | Included in live allowance |
| Successful archive (latest rehearsal `e3e37d71`) | 5,639,752 | All archives: 268,435,456 |
| Owned evidence at reconciliation | 6,729,388 | Archive/evidence allocation |
| Supervised browser process-tree RSS peak | 910,000,000 (approx.) | 1 GiB |

The latest rehearsal reconciled all six owners at sequence 26 with `activated: false`; `capacity_footprint` reports the same `database_bytes` the rehearsal recorded. Admission stayed at the PIPE2-04 bounds (8 normal + 2 recovery HTTP, 5/2/1 DB pools, 64 KiB bodies, 512 MiB 80% live cutoff); no threshold was lowered.

### V1–V9 operational/fault families — where each is established

| Family | Establishing evidence |
|---|---|
| V1 Account/proof journeys | `integration/test_accounts_http` + `component/test_credentials` (registration, verification, login, reset/email change, identity fixtures, expiry/replay/lost acknowledgement) |
| V2 Owner/admin/MFA | `component/test_mfa`, `test_transport_isolation`, `integration` admin/MFA journeys, `database/test_constraints` (role/session denial, single delivery, replay) |
| V3 Library/history | `component/test_library`, `integration/test_library_personal_http` (saved references, clear checkpoints, delayed events, no rerun on read) |
| V4 Reset recovery | `repository/test_controls`, `component/test_personalization`, `integration` reset journeys (zero writes on list/inspect, two resets, cursor expiry, restart discovery) |
| V5 Lifecycle/restore | `component/test_lifecycle`, `test_owner_lifecycle`, `test_current_owner_cleanup`, `operations/test_recovery_restore` (actual older backup, revoked authority before cleanup, no restored erased data) |
| V6 Usage | `component/test_usage`, `database/test_admission_races`, `integration` usage journeys (both race orders, original period, no negative-read release) |
| V7 Bounds | `operations/test_control_runtime`, `test_browser_bootstrap`, `test_runtime_store`, `database` + `operations` resource measurements (saturation, recovery slots, no worker multiplication, RSS budget) |
| V8 UI/accessibility | `frontend-verification.md`: 13 browser journeys, three viewports, three appearance modes, Tab order, reflow, protected-material clearing; screen-reader/manual WCAG review remains outstanding |
| V9 Repair/integration | Frozen setup from pinned artifacts (`test_browser_bootstrap` identity/frozen-install suites), seeded defect diagnosis/repair recorded above (orphaned recovery rows → restore refusal → repair → rerun), cumulative invocation prepared separately (`cumulative-check.md`) |

### Packaging, migration order and rollback

- Ordered migrations are the `MIGRATIONS` sequence in `scripts/verify_docsuri_u2.py` (accounts → personalization → library → usage → assistance, then amendments in recorded order). Applied bytes are SHA-256-hashed into `public.docsuri_local_identity`; editing an applied file is refused and requires a new ordered amendment. `database/test_migration_identity.py` re-verifies every applied file hash on each run.
- Stop → migrate → start: the runner refuses to migrate while the application listener is up, and `teardown` is intentionally disabled (an owned realm is preserved until evidence is archived). Rollback is a new ordered amendment plus the quarantined restore protocol; the original realm is never named for drop.
- The release artifact identity is the frozen source tree plus the three lockfiles (`backend/uv.lock`, `frontend/pnpm-lock.yaml`, `shared/python/uv.lock`), recorded in every phase's evidence. No public deployment or real-data migration was performed or is authorized by this record.
