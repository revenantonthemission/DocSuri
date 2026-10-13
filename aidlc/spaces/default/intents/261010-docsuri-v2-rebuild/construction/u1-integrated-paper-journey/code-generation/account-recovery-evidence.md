# Account transport prerequisites and diagnostic history bounds

## Owner session recovery

AccountAccess derives session CSRF from the opaque session cookie using a
distinct protected HMAC purpose. Fresh service instances recover the same CSRF
without cross-tab rotation, after checking the persisted verifier and current
session/account authority. Revoked, expired or old non-derivable synthetic
sessions fail closed; this is not migration of existing service users.

Login now takes an optional operation identity and flow binding. It verifies
the current password/account before reading an exact matching public receipt,
then checks the recorded session authority and token/CSRF verifiers. The opaque
cookie is derived under another HMAC purpose from operation plus normalized
intent (including the flow); raw passwords and cookies are not persisted in
receipts. A lost reply after commit recovers the same session, without another
rotation. Changed flow conflicts and revoked-session replay is denied.

An append-only `local_login_receipts.sql` amendment extends the owned receipt
kind constraint; both explicitly owned databases were amended through the
existing bootstrap. No applied migration was rewritten. Verification and logout
return typed owner acknowledgements with purpose-separated terminal-state
revision tokens. Logout retries do not bypass revoked authority to obtain an Ack.

The verifier key requires private regular single-link custody, and its directory
is fsynced before use, including on restart. Fault tests prove a failed directory
sync prevents acknowledgement and a retry preserves the key bytes.

Anonymous entry context is signed and bound to run/database/origin, a random
flow ID and a maximum 15-minute lifetime within environment retention. Its CSRF
uses a separate HMAC purpose. Substitution, changed realm/origin, expiry, future
issuance, oversized and Unicode signature/CSRF inputs refuse normally. These are
prerequisites for the HTTP adapter; no mounted browser proof is claimed here.

## Preserved unsuccessful attempts

- Component attempt 96797: 183 passed, 5 failed in 4.47 seconds. The newly
  registered amendment had not yet been explicitly applied, so the old receipt
  constraint rejected login. Exact result/source/JUnit retained as
  `/tmp/docsuri-u1-run/login-before-amendment-component-{result.json,junit.xml}`.
  Applying the amendment in both owned realms resolved that cause.
- Repository attempt 95702: 26 passed, 58 fixture errors in 7.42 seconds when
  retained diagnostic admissions exceeded the old 1024-row enumeration guard.
  Exact evidence retained as `/tmp/docsuri-u1-run/admission-cap-repository-{result.json,junit.xml}`.
  These are fixture errors, not passing product checks.

## Measured fixture repair

Read-only measurements before repair found 1026 repository-family admissions
(378434 PostgreSQL row bytes), 54 unmarked diagnostic admissions (9126), 809
repository-family jobs (590099), 54 unmarked diagnostic jobs (24156), 258 results
(100168), and no library history rows. These are storage measurements, not decoded
memory bounds. Database sizes were 19840023 and 11770903 bytes; the whole owned
PostgreSQL volume used 87236 KiB. Host free space was 14840000 KiB, above the
8 GiB floor. Non-model run files were approximately 38160 KiB; together with the
volume, approximately 122.5 MiB remained within the 1 GiB runtime allocation,
leaving approximately 901 MiB and the separately planned 1 GiB recovery reserve.
The separately inventoried APFS model clone is not interpreted as exclusive
physical allocation. No unrelated data was removed.

The diagnostic inventory now permits at most 2048 rows per selected family,
keyset pages of 256, and 2 MiB aggregate UTF-8 serialized selected rows across
jobs, admissions, related reservations and results. A server-side 2049-row
sentinel bounds sizing input and detects row overflow. Repeatable-read snapshots
measure `row_to_json` bytes before decoding payloads; decoded bytes/counts must
match. At most nine page queries plus one sizing query per selection (40 total)
are possible. Fixed queries and identity/provenance checks remain test-owned.
All inventories and validation finish before reconciliation mutates anything.
Overflow, changed snapshots, foreign-owner rows or unrecognized results refuse
without partial cleanup. The 2 MiB bound covers selected logical rows, not total
historical storage or all Python object overhead.

Admission/job/result history remains retained. Existing explicitly authorized
diagnostic reservation cleanup remains fixture behavior; journey reservations,
normal accounts and accepted work are not cleaned by this fixture. Live limits
of two accounts and four usage slots are unchanged. The original 1024 guard was
an implementation enumeration limit, not a relaxed product quality target.

## Final executed evidence

- `python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json`: 195 collected/passed in 4.73 seconds.
- `python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json`: 84 collected/passed in 24.62 seconds.
- Zero failures/errors/skips, exit 0, unchanged source fingerprint
  `3ca7bd7c0b7fb811ebf4401b1db0cc5f20e205fc31b5f8fd7039fd32cc38618e` for both.
- Protected final records/JUnit:
  `/tmp/docsuri-u1-run/account-recovery-final-{component,repository}-{result.json,junit.xml}`.
- Scoped Ruff passed. Per-module coverage remains for the planned cumulative
  measured pass; no new coverage-completion claim is made.

The real login lost-reply test confirms exactly one persisted session and no
raw password/cookie in the receipt; generated Ack validation passes. Fixture
overflow/aggregate/snapshot tests use deliberate diagnostic adapters; actual
PostgreSQL repository runs exercise the repaired paging and retained history.
Canonical HTTP/CSRF/cookie integration, browser journeys and normal model
usefulness remain unfinished. No model experiment ran in this checkpoint.
