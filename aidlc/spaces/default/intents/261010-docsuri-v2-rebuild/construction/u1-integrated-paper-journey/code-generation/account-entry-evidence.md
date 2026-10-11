# U1 AccountAccess component evidence

Date: 2026-10-11. Step 7 component implementation followed by Step 8 tests.
This is the isolated synthetic composition, not public registration readiness.

The existing AccountAccess Argon2id/password-policy implementation remains the
credential authority. The guarded entry service adds durable ordinary-account
registration receipts, bound single-use verification, an explicitly private
local mailbox, recoverable verification reissue, current-session lookup, rotation,
CSRF comparison and server-side logout. Opaque proof/session/CSRF values use a
protected keyed verifier. Raw values exist only in the trusted transport object
or private local mailbox, not public JSON responses or committed evidence.

The finite local policy is `synthetic-local-entry-1`: two active synthetic
accounts, 20 entry attempts per database-clock minute, one concurrent Argon2id
operation with two-second admission wait, fifteen-minute verification proof and
one-hour session. The existing Argon2id parameters are 64 MiB, three passes and
four lanes. These are local experiment bounds; no public-service capacity,
retention or delivery claim follows. Runtime profile expiry also fences access.

Registration checks capacity independently of address existence for every fresh
operation; an exact original receipt can still reconcile at capacity. A parent
spot-check identified the earlier address-dependent capacity path, and the
existing/new-address comparison at the full bound now covers its correction.

The append-only `local_entry.sql` amendment was applied only through the owned
synthetic bootstrap. It adds entry receipts, private-mail metadata, challenge
flow binding and a finite attempt ledger. Existing schema bytes were unchanged.

The component phase collected and passed **27 tests** in 4.36 seconds: nine new
AccountAccess cases plus eighteen prior component/harness checks, with zero
skips/errors/failures. The cases cover verified entry, session/CSRF/rotation/logout,
duplicate and changed intent, wrong/expired/replayed proof, proof reissue,
unknown registration reply, concurrent single-use consumption, unverified/invalid
credentials, attempt admission and equal capacity disposition.

```bash
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

One initial fault-injection test intercepted the connection context manager's
empty second commit instead of the registration commit: 25 passed, one failed.
The test now counts only active transactions. The next run passed 26; adding the
capacity regression produced the final 27 above. This was a test injection error,
not claimed evidence of successful unknown-outcome recovery until corrected.

A preceding focused eight-case instrumentation run measured 167/182 executable
lines (92%) in the new service. The subsequent capacity change and ninth case
require the next cumulative coverage measurement; this earlier denominator is
not asserted as the final file's coverage. Scoped Ruff checks passed.

Account fixtures retire only known database diagnostic identities or accounts
under the dedicated `@entry.fixture.invalid` namespace, after rejecting any
unknown active identity. The test-owned attempt ledger is reset between cases.
This permits the two-account experiment across repeatable test cases without
resetting normal accepted work or implying production account lifecycle support.

Still pending: canonical HTTP/cookie and anonymous bootstrap binding, mounted
origin/Host checks, accessible browser forms, delivery fault/recovery at the
mounted boundary, complete participant registration and final source inventory.
Later-unit account capabilities remain retained in their existing implementation;
this component does not claim full account parity or close broader U1 readiness.
