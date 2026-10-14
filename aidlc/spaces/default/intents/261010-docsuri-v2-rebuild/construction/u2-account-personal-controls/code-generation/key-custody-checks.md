# U2 key custody and owner restore checks

These scoped results precede the final unchanged-source coverage and cumulative check. They do not authorize public activation, real-data migration or host-loss recovery.

## Implemented custody

`backend/modules/accounts/control_keys.py` retains a bounded versioned encryption ring. `services/control_entry.py`, `services/control_mfa.py` and `services/control_identity.py` bind protected records to the actual envelope version. Startup checks all retained version references and refuses missing verifier custody when account data exists. Legacy encryption remains readable.

`backend/modules/accounts/control_key_recovery.py` captures the paired verifier and current ring into an immutable digest-addressed file in a private directory outside database/package contents. Recovery requires the exact run, generation and digest. It repairs absent members only, refuses divergent/newer current files, and provides no key-removal capability. A post-rotation capture is explicit; recovery snapshots share the current disk, so G3 host-loss evidence remains open.

## Executed checks

1. `backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls/operations/test_control_key_recovery.py tests/u2_account_personal_controls/operations/test_control_keys.py tests/u2_account_personal_controls/operations/test_browser_fixture_lock.py -q` — **24 passed**, 0 failed, 0 skipped, 0.35 seconds. Temporary filesystem/AES-GCM checks never connect to the owned database. They cover retained and legacy keys, restart, purpose binding, missing material, crash boundaries, finite rotations, private file/directory custody, stale recovery refusal, exact-version restoration and delivery-file access while the application lock is held.
2. `env DOCSURI_U2_ENVIRONMENT_FILE=/tmp/docsuri-u2-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls/operations/test_keyring_store.py tests/u2_account_personal_controls/operations/test_owner_restore.py -q` — **10 passed**, 0 failed, 0 skipped, 0.62 seconds on run `docsuri-u2-c274e71798431965`. Real PostgreSQL proof retention, controlled rotation, startup decryption, four owner exports and live-runtime denial were checked.
3. After adding explicit recovery-bundle capture and exact-identity checking, reran the same invocation restricted to `test_keyring_store.py` — **1 passed**, 0 failed, 0 skipped, 0.43 seconds. Generation stayed at 2 and the existing prior key remained retained. The test created a private recovery snapshot and verified it before entry restart; it did not delete live key material.

An initial four denial checks failed because they expected a custom error string. The live source database denies access to its public restore metadata before the custom target gate. The tests now assert PostgreSQL `InsufficientPrivilege`; no production permission was widened.

Focused Ruff checks passed for the key modules, their consumers, owner restore adapter, fixture helper and these test modules. Final source inventory includes their full statements; the 80% floor is unchanged and the scoped checks do not claim it has been met.

## Traceability additions

- NFR4.1–NFR4.8 and FR6/FR7 contributions: protected material, current custody, version binding, missing-key denial and controlled recovery. Source: `control_keys.py`, `control_key_recovery.py`, `services/control_entry.py`, `services/control_identity.py`, `services/control_mfa.py`. Evidence: `test_control_keys.py`, `test_control_key_recovery.py`, `test_keyring_store.py`.
- NFR7/NFR8/NFR9 recovery contributions: `backend/control_restore.py` and append-only owner restore migrations. Evidence: `test_owner_restore.py` plus the separately recorded Operations older-backup rehearsal. Six-owner actual restore remains quarantined and does not establish all lifecycle backup obligations.
- Browser interruption prerequisite: `scripts/u2_browser_fixtures.py` protected proof reads use an independent file lock; `test_browser_fixture_lock.py` verifies that a running application does not prevent retrieving an already delivered synthetic proof.
