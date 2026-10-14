# U2 repository and read-projection checks

Observed 2026-10-14 on the owned `docsuri_u2` realm through actual owner roles and the real transaction facility. No in-memory substitute is used; a missing store fails.

```sh
DOCSURI_U2_ENVIRONMENT_FILE=/tmp/docsuri-u2-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls/repository -q
```

Result: **14 passed, zero failures/errors/skips.**

## Implementation evidence (Step 5)

- Owner-first parameterized queries: every repository call runs inside `transactions.run(owner, ...)` with the owner derived from the installed class (never browser input) and psycopg parameter binding. Cross-owner denial is enforced by least-privilege roles (`restriction-checks.md`).
- Stable bounded keyset pages/cursors: `ControlCursor` is HMAC-signed over owner+view, expires in 300 s, and refuses a token replayed against another view or a different limit. Reset history pages carry a snapshot revision; usage-record pages carry a timestamp cutoff plus `(accepted_at,id)` keyset position.
- Exact receipt/intent replay: `accounts.control_receipt` and per-owner `receipt` rows bind `(account, kind, operation)` to a normalized intent digest; a matching key returns the original outcome, a changed intent raises `operation identity conflict`, and a conflict cannot be repaired by re-sending.
- Immutable original acknowledgements: profile/consent/reset/usage receipts return their originally committed outcome after later revisions; the U1 rejection ledger remains append-only to runtime roles.
- Fresh reset reads: `ResetRepository.list/inspect` read `personalization.reset_responsibility` directly, return zero items for an empty owner without allocating a row, and expose the per-reset `status_revision` that only increase via `record_scope`.
- Assignment inspection: `GuardedUsageRepository.inspect_assignment` returns a non-null initial revision derived from `uuid5(account, ':assignment-empty:1')` for an absent entitlement and never inserts one.
- Participant claim/evidence: `ControlLifecycleService.claim` requires a registered (participant, scope), the exact current lifecycle revision and manifest revision, then fences by claim generation and lease; `apply_owner_effect` re-checks `accounts.lifecycle_effect_action` and stores per-owner `lifecycle_evidence`. No unrestricted cross-owner writer exists; exports run as each owner role under the maintenance process and the restore reconcilers demand the quarantined database and `postgres` session.

## Behavior established by the run (Step 6)

- Reset survives a brand-new repository instance and discovery (restart needs no prior browser storage); two accepted resets page without duplicates and share one snapshot revision.
- Lost acknowledgement replays the immutable outcome; a changed intent conflicts; a stale settings revision fails.
- Absent and foreign reset IDs both refuse without revealing state; a session for another supplied owner is denied by the guard.
- Cursor cannot change view or page size; acceptance-scope fencing leaves the acknowledgement and monotonic status revision intact for a stale worker.
- All reset list/inspect operations leave the row `xmin` unchanged — reads never enqueue, allocate, settle, clear or update a boundary. Assignment inspection leaves the entitlement count unchanged (no implicit allocation).
- Usage records return a reservation's original `original-acceptance-period` and the read leaves every reservation row untouched (`xmin` comparison).
- No missing store silently substitutes success: a closed owner facility raises `closed or unknown owner pool` rather than answering from an in-memory fallback, and every read runs `transactions.run` against its owner pool so an absent/denied store fails loudly.



