# U1 owner database evidence

Date: 2026-10-11. Steps 3–4. This is database-layer evidence, not application, model or operating readiness.

## Installation boundary

`backend/.venv/bin/python scripts/bootstrap_docsuri_u1.py` verifies the exact private environment marker, container/volume labels, selected PostgreSQL 16.15 and database name before any DDL. It refuses unidentified schemas. The initial schema transaction creates eight non-login owner roles, eight bounded runtime roles, component schemas and a protected identity ledger. Runtime roles have no superuser, database/role creation, bypass-RLS or owner-role membership. Migration credentials stay in a separate private file; application profiles reject an inline administrator password.

Each owner's local SQL file lives in that owner's existing source boundary, with a clearly named CorpusContent facade where no single facade existed. These files are not added to the legacy automatic migration registry. Explicit append-only amendments preserve applied source hashes; changing already applied bytes is refused. An initial bootstrap DDL parameter-type error rolled back; after using a SQL literal for the fixed check expression, installation succeeded without residual role/table collisions. No existing service database was migrated or reset.

Accounts and CorpusContent own fixed-purpose SECURITY DEFINER guard functions, fixed `pg_catalog` search paths and non-login function owners. Public execution is revoked. Consumers receive only named execution rights. Guard locks remain on the target caller's transaction connection. Runtime direct foreign table writes and credential reads are denied. The API's later possession of multiple owner credentials remains an application trust boundary; these grants do not claim protection against a fully compromised API process.

## Executed verification

Exact command: `python3 scripts/verify_docsuri_u1.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json`.

Final observed run: **47 collected, 47 passed, 0 skipped, 0 failures, 0 errors, 1.68s**. Source HEAD was `3b7ad02bf91bd3a7130be506f7b0eb235c0952c4`; actual application/config/test byte inventory digest was `edfdb2d35fe88430c8c1be55e17e3c54f25b3687d507fb54798c0347f4a2be18`. The source inventory was unchanged during the run. The private manifest contains expanded commands and per-file hashes.

| Boundary | Executed evidence |
|---|---|
| Selected store | PostgreSQL 16.15; fsync, synchronous_commit, full_page_writes and checksums enabled; inspected named persistent Docker volume mount |
| Real principals | All eight runtime roles denied a foreign owner UPDATE and committed their own receipt positive control; separate UPDATE/DELETE, credential SELECT, SET ROLE and schema/public CREATE denials |
| Narrow guards | Unknown purpose, wrong account/session binding and ungranted operations role denied; function metadata confirms four fixed-search-path, non-login SECURITY DEFINER owners |
| Same-transaction serialization | Eight two-connection cases cover account, session, consent and source revocation, each in both effect-first and revocation-first order. Tests inspect actual `pg_blocking_pids` edges, not a sleep-only inference. The effect-first target commits before revocation; revocation-first prevents the target write |
| Receipt/CAS | Absent create, later revision update, exact original receipt replay after the update, stale create rejection, changed-intent rejection and current-authority denial before replay |
| Atomic rollback | Guarded saved reference and its receipt both disappear on transaction rollback |
| Immutable identities | Source parent/hash/path/content cannot be rebound; a saved paper cannot reference another paper's version; acceptedAt, payload and glossary snapshot binding remain immutable |
| Worker state | Complete active claim constraint; null claim inputs and null/wrong authority revisions denied; replacement increments the fence and rejects old guard/renew calls; lease revision changes independently of job revision/sequence |
| Read-only glossary | Stable owner-bound empty token/snapshot across repeated reads with no glossary insertion |
| History | Clear advances generation/cutoff; a delayed old fact is suppressed, a new positive-control fact is accepted, and original clear receipt remains replayable |

Two nullable-input issues identified during implementation review were fixed before the final run: account execution revisions now fail closed on NULL, and execution claims require non-null complete fields and expiry. Claim acquisition samples authoritative time after acquiring its row lock. Corpus version-parent immutability prevents the previously identified unlocked-parent/rebinding hazard. Fixes are explicit schema amendments with regression cases, not guard bypasses.

## Review finding and limits

Infrastructure review R-01's **database privilege/guard mechanism** now has positive, negative, rollback and two-connection ordering evidence under real runtime grants. This is the requested Step 4 closure evidence; the independent finished-work review must assess it with the later repository/API bindings. Contract R-01/R-03 still require mounted browser/worker contract tests; these SQL checks alone do not close those wider findings.

Fixture password/session strings are intentionally unusable for actual login; they establish isolated database state only. Expired worker lease state is an explicit fault injection on an owned fixture job. No fake store, tmpfs substitute, canned model output, or current service authority is used. Container replacement, shared-VM-safe restart strategy, backups/restoration, aggregate pool limits, settlement reconciliation, full end-to-end usefulness and per-module coverage remain unexecuted requirements for later steps. A persistent-volume mount is not a restart or backup proof.
