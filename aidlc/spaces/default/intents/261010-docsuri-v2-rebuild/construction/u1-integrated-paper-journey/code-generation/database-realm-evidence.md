# Separate diagnostic and journey databases

## Purpose and boundary

The diagnostic suites retain explicitly owned source fixtures for receipt,
withdrawal and recovery tests. Their two-version corpus allocation must not
displace the real P1/P2 journey. A second empty database,
`docsuri_u1_journey`, now shares the existing positively identified disposable
PostgreSQL 16.15 container and persistent volume. No diagnostic or accepted
work was copied, reset or removed. Existing service databases are untouched.

This is test-data separation, not stronger credential isolation. Both databases
use the same bounded owner roles and credentials. Transactions explicitly bind
the database name, realm and run identity. All repository instances in one
process share the same admission semaphore across both databases; PostgreSQL
runtime role connection limits remain two cluster-wide, and max_connections
remains twelve. Cross-process supervision and ongoing storage enforcement still
require the planned operations work.

The provisioner requires its private ownership marker and a matching unique
non-login database-owner role/comment before adopting an existing database.
Unknown targets and mismatched identities are refused. Provisioning uses an
immediate advisory try-lock, a five-second statement timeout and a two-second
lock timeout. Replay verifies the installed schema and explicit amendment
hashes. The observed combined database size before the final replay was
20,715,566 bytes. Admission retains a 128 MiB combined database allocation,
16 MiB schema allowance and the absolute 8 GiB host free-space floor; no new
unbounded allocation or independent per-database budget was introduced.

Private profile/credential records use bounded no-follow, nonblocking reads
and require an owned regular file with mode 0600. A substituted FIFO cannot
block profile loading. The original diagnostic profile remains the default;
selecting the journey requires its ready marker explicitly.

## Executed checks

Commands ran serially against the existing owned environment:

```text
backend/.venv/bin/python scripts/bootstrap_docsuri_u1.py --journey
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

- Initial journey provisioning installed the owner schemas successfully.
- Final component phase: 71 passed in 3.05 seconds, including five private-record
  tests for exact permissions, bounds, FIFO, symlink/directory and ready-marker
  identity. No skipped cases.
- Final repository phase: 25 passed in 46.47 seconds, including real database
  identity/separation, shared admission, wrong-target/run denial, held-lock
  refusal and successful provisioner replay. No skipped cases. The previously
  executed intermediate repository run had 24 passing cases before the final
  lock/replay regression was added.
- Scoped Ruff formatting/lint and `git diff --check` passed.

Protected expanded commands, collection/execution counts and tested-source
digests are in `/tmp/docsuri-u1-run/component-result.json` and
`/tmp/docsuri-u1-run/repository-result.json`; corresponding JUnit reports remain
beside them. These runs are component/repository evidence, not an approved
Construction completion check. Per-file cumulative coverage will be refreshed
with the integrated implementation; the 80% completed-module requirement is
unchanged. Real P1/P2 publication, mounted journeys, operations and useful
model output remain unfinished.
