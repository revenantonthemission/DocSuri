# U2 data-model and database checks

Observed 2026-10-14 on the owned `docsuri_u2` realm through real owner roles. These are isolated database assertions, not a completion claim.

```sh
DOCSURI_U2_ENVIRONMENT_FILE=/tmp/docsuri-u2-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls/database -q
```

Result: **24 passed, zero failures/errors/skips.**

## Coverage against the Step 4 obligations

- Uniqueness: provider-subject uniqueness across owners, proof-hash uniqueness, per-account provider link uniqueness, one-time MFA delivery hash, reset confirmation prepare key, per-reset input boundary.
- Owner role denial: cross-owner writer refused, limited continuation cannot use the owner guard, administration requires current administrator role plus fresh MFA. Runtime-role denial of receipt and rejection-ledger deletes is verified live in `restriction-checks.md`.
- Proof consumption: a consumed proof without an operation binding is refused by construction.
- Session/authority serialization: a live guarded owner transaction holds the session row share-lock; a concurrent revocation times out (`LockNotAvailable`) until the effect commits, after which the old session is refused. Current withdrawal denies an old session even before any effect.
- Reset acceptance and status revisions: acceptance timestamp is immutable; a status change without a strictly greater `status_revision` is refused; `complete` cannot regress to `pending`.
- Ledger constraints: quota cannot be unlimited; reservation disposition and settlement are mutually exclusive; operation generation must be positive.
- Both admission race orders with real PostgreSQL locks: the first committed owner transition wins; the competing transition observes the committed state under the same row lock and cannot take the opposite terminal state (`CheckViolation`).
- Crash boundaries: losing the connection before commit leaves the admission `open` with no closure; commit-then-lose preserves the exact closure reference and time.
- Stale closure/generation evidence: a closed operation cannot be re-generation'd or have its closure reference rebound; a missing admission yields no closure evidence.
- Migration/restart identity (`test_migration_identity.py`): a fresh connection observes the same run id and hash record (no reseed), and every applied migration file's current bytes still match the retained SHA-256 — an edited applied migration is refused by construction.
- Current restrictions defeating older restore state: exercised end-to-end by the actual older-backup rehearsal (`operations-verification.md`), which observed prohibited old rows in the quarantined copy before reconciliation and then verified revocation, delayed-acceptance suppression and original-period reservation retention after it.
