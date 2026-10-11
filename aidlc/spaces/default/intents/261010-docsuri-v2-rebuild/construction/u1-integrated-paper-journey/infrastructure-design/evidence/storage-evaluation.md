# U1 PostgreSQL and SQLite storage evidence

Date: 2026-10-11 (Asia/Seoul). Status: executed synthetic primitive evidence and
experiment-binding recommendation; no assembled-service conformance, public
hosting, migration, or production durability decision.

## Result and binding recommendation

Use **PostgreSQL 16.15 in one transactional database** as the strongest supported
binding for the next isolated U1 integration experiment. Keep owner repositories
and authority participants separate in code and privileges while placing their
ordered guard records and protected commits in that common database. Its
serializable transactions, explicit row locks, conditional updates, unique keys,
WAL recovery and logical restore all have both relevant documented support and
the bounded executed evidence below. This is an architecture judgment for the
next experiment, not a measured throughput advantage.

SQLite 3.54.0 remains a credible single-host candidate: the executed tests show
that its database-wide writer serialization can order the modeled guard and
effect correctly. It is not rejected for being multi-user, and it is not used as
a substitute test store for PostgreSQL. PostgreSQL's row-scoped locking offers a
stronger fit for multiple owner write lanes without requiring every unrelated
write to take the same database-wide writer slot; the amount of benefit under
DocSuri's real workload remains unmeasured. PostgreSQL adds an actual server,
role/configuration maintenance and backup administration for the single maintainer.
SQLite reduces those operating components at the cost of a shared writer lane.
[PostgreSQL row locks](https://www.postgresql.org/docs/16/explicit-locking.html),
[SQLite isolation](https://www.sqlite.org/isolation.html).

**The PostgreSQL test used tmpfs. Its successful database-process crash recovery
does not establish persistence across container, VM, host, power or media loss.**
The next experiment must bind and verify the intended persistent volume, storage
headroom, backup destination and restoration protocol. Search, pgvector,
OpenSearch, model work, actual owner permissions and mounted API/browser/worker
behavior were outside this probe. No production database or user data was read.

## Requirements and inspected evidence

The evaluated mechanisms come from
[LOG03 and INF02/INF03](../../nfr-design/logical-components.md),
[REL01–REL04](../../nfr-design/reliability-design.md),
[SC01–SC04](../../nfr-design/scalability-design.md), and
[T02/E03](../../nfr-requirements/tech-stack-decisions.md):

- One owner mutation/revision/receipt transaction and unique operation identity.
- Shared serialization of current authority and protected owner effects, with
  only the authority owner changing its barrier and expensive work outside it.
- Conditional claims/fences, immutable acceptance time, and recoverable receipts.
- Separate owner commits for reservations, acceptance and settlement, with durable
  reconciliation; unknown admission cannot be released merely because time passed.
- A consistent database backup plus isolated restoration, followed by current
  authority reconciliation before any serving or execution.

Graph context: Tier 2, project `Users-revenantonthemission-Projects-DocSuri`,
generation `2026-10-11T08:48:14Z`; coverage check recorded
`2026-10-11T09:33:09Z` returned `metadata_match` and `no_recorded_issue` for all four
documents. They were read directly as design documents. This coverage signal is
best effort and does not claim code completeness. No application structure was
inferred from the graph or from these synthetic helpers.

## Exact available runtimes and isolation

The first inventory used `command -v` for `psql`, `postgres`, `pg_ctl`, `initdb`,
`pg_dump`, `pg_restore`, `sqlite3`, `python3`, `timeout` and `gtimeout`. Only
`/usr/bin/sqlite3` and `/usr/bin/python3` resolved. Additional known PostgreSQL
executable checks covered `/opt/homebrew/bin`, `/usr/local/bin`, Homebrew
`postgresql@14` through `postgresql@18`, and
`/Applications/Postgres.app/Contents/Versions/latest/bin/postgres`; none of those
checked server executables existed. This is a bounded native inventory, not an
exhaustive claim that PostgreSQL is absent from the machine.

The parent then identified a cached official `postgres:16` Docker image and
authorized the bounded isolated container below. No image was downloaded.

| Item | Exact observed identity/settings |
|---|---|
| Python | `/usr/bin/python3`, 3.9.6; built Aug 25 2026; Clang 21.0.0 |
| SQLite CLI/runtime | 3.54.0; source ID `2026-04-09 12:25:13 8fa8248e303219400c646a885e36dfc52eae33d83f4412e3f369b2be5373aapl`; Python binding 2.6.0 |
| SQLite effective configuration | WAL; `synchronous=FULL` (2), `fullfsync=1`, `checkpoint_fullfsync=1`, `foreign_keys=1`, `busy_timeout=2000` ms, page size 4096, max pages 1024, memory temp store, 1024 KiB suggested page cache |
| Docker executable | `/opt/homebrew/bin/docker`; existing daemon and cache supplied by parent inventory |
| Cached PostgreSQL image | `postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6` |
| Executed PostgreSQL | `postgres (PostgreSQL) 16.15 (Debian 16.15-1.pgdg13+2)`, aarch64 Linux |
| PostgreSQL effective configuration | `fsync=on`, `synchronous_commit=on`, `full_page_writes=on`; data checksums enabled by final `initdb`; `shared_buffers=32MB`, max connections 12, statement timeout 5000 ms, lock timeout 2000 ms, idle-in-transaction timeout 5000 ms |
| Network/authentication | `--network none`, no published ports, `listen_addresses=''`; private Unix socket only; synthetic local trust and host authentication reject inside this disposable container. These are not production authentication settings. |

The finite envelope was sent to the parent before execution:

| Probe | Hard or procedural limits and stop/cleanup |
|---|---|
| SQLite | `/tmp/docsuri-u1-infra-storage/run-*`; 45 s process alarm and 8 s child alarms; at most two child processes plus the parent; 4 MiB OS per-file limit and 4 MiB per-database page ceiling; fixed small row set, memory temp store and sampled total-storage assertion ≤64 MiB. Total byte sampling is not a filesystem quota. No network, packages, services or existing databases. |
| PostgreSQL | Unique `docsuri-u1-storage-*` container, cached image with `--pull never`; 0.5 CPU, 512 MiB RAM with memory-swap also 512 MiB, PID limit 64, read-only root filesystem; one 256 MiB tmpfs at `/var/lib/postgresql/data` holding data/socket/log/dump; Docker's separate 64 MiB `/dev/shm` is inside the container memory limit. No host bind mounts or ports. Up to three simultaneous client subprocesses; server subprocesses bounded by the container PID cap. 55 s whole-probe alarm, finite subprocess/SQL waits, and container lifetime 55 s. Cleanup removes only the probe's uniquely named container. |

Database sizes and row counts were deliberately tiny. Neither cap is a selected
service allocation; neither timing is a latency, throughput, RPO or RTO baseline.

## Executed assertions

PostgreSQL's concurrency cases used separate `psql` sessions at `SERIALIZABLE`.
The first transaction held its lock open; a third observer confirmed that the
second session was waiting on a database lock before the first committed. A
`40001` serialization failure received at most one retry of the whole original
transaction. SQLite used separate forked processes/connections and
`BEGIN IMMEDIATE`; synchronized starts tested CAS/uniqueness, and a held first
transaction established each guard ordering. This proves no exhaustive set of
interleavings, fairness, or sustained contention capacity.

| Check | PostgreSQL final run | SQLite final run | Practical boundary |
|---|---|---|---|
| Same-revision CAS and receipt | Second session blocked, then `40001`; retry left entity revision 1 and exactly one receipt | Affected row counts `[1,0]`; revision 1, one receipt | Revision update and receipt are in the same transaction. |
| Absent-row creation uniqueness | One glossary row; competing insert returned `23505` | One `created`, one `conflict` | Unique owner key protects first physical creation; virtual glossary-token semantics remain application work. |
| Revocation commits first | Effect waited; `40001` then retry read denied; current authority false, zero effects | `revoked`, then `denied`; false, zero effects | Current authority is read inside the committing order. |
| Protected effect commits first | Revocation waited; effect committed once, then authority false; no serialization retry required | `committed`, then `revoked`; one effect, current authority false | Historical effect survives; current permission denies later reads. No actual read API was mounted. |
| Replaced worker and duplicate terminal write | Stale worker/fence affected 0 rows, current worker/fence 1, duplicate 0; fence 2, revision 1, original acceptance time unchanged | Same `0,1,0` counts and immutable timestamp | Lease expiry/renewal, executor authentication, clocks and payload access were not exercised. |
| Commit before domain reply / crash | Independent observer saw receipt after commit; client reply withheld. An immediate database shutdown killed sessions; subsequent startup performed WAL redo. Committed state/receipt survived; observed uncommitted write/receipt disappeared. Receipt stayed at original intent/revision after a later entity edit. | Child exited with code 23 after commit and zero reply bytes; fresh connection recovered state/receipt. Code-24 exit before commit left original state and no receipt. | PostgreSQL restarted database processes over surviving tmpfs; SQLite reopened surviving local temporary files. Neither tests media loss. |
| Reservation reconciliation | One logical debit, exact duplicate matched, contradictory requested disposition did not match. Durable rejection then release barred late acceptance; missing admission remained pending. Original period/policy persisted. | Same semantic outcomes, including explicit duplicate replay/conflict results | Separate owner commits were modeled even in one database. No queue worker, timeout policy, billing system, reset race or full admission race matrix. |
| Backup/restoration | `pg_dump -Fc`, new database, `pg_restore --exit-on-error`; all rows in ten modeled tables matched, including receipts/fences/obligations | SQLite backup API, finalized independent file, read-only reopen; ten tables matched, integrity check `ok`, zero foreign-key errors | Quiescent synthetic database snapshots only; no external artifacts, keys, roles, grants, in-flight backup writes or full restore runbook. |
| Stale backup authority | Backup retained an allow; source subsequently revoked it. Restored allow and current deny were explicitly observed | Same | Serving remained disabled. This demonstrates the need for post-backup authority reconciliation; it does not implement that coordinator. |

The corrected PostgreSQL guard shape was:

```sql
BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT allowed FROM authority WHERE id = :guard_id FOR UPDATE;
-- The typed authority participant evaluates this guarded row.
-- The protected owner changes only its own target/receipt when allowed.
-- A revocation instead updates the authority owner's barrier in this same order.
COMMIT;
```

No protected effect in the final run updated the authority record. The one-row
example proves a locking primitive; real account/session/consent then
source/version then aggregate ordering, absent barriers, owner-scoped database
permissions and typed participants still require implementation and conformance.
The probe ran with a synthetic PostgreSQL superuser and cannot prove least
privilege. A raw `SELECT` outside the ordered transaction would not be equivalent.

Reservation checks model one debit obligation, a committed debit whose
confirmation is delayed, and reconciliation by original identity. The PostgreSQL
probe's duplicate insert uses a unique key plus subsequent disposition comparison;
`ON CONFLICT DO NOTHING` by itself is not evidence that intent matches. Contradictory
dispositions must become a typed conflict in the eventual adapter. The orphan case
sealed rejection before release and rejected a subsequent late accept; concurrent
late acceptance versus sealing and the complete REL03 fault matrix remain open.

## Measured runs, failures and reproducibility

Final SQLite run: **9/9 recorded cases passed**, elapsed 0.201079 s; largest sampled
data-file total before writing its report 237,568 bytes; 241,257 bytes after the
report. Backup API call took 0.001972 s. These are one-shot observations, not
comparative performance measurements or a measured peak between sampling points.

Final PostgreSQL run: **8/8 recorded cases passed**, elapsed 3.877211 s including
initialization, crash/restart, dump/restore and container removal. Combined
database/dump/log tmpfs use at the end was 42,328 KiB. The final Docker sample was
72.27 MiB / 512 MiB memory, eight processes and 0 B network I/O. It is an end
sample, not peak RAM. Dump/create/restore took 0.184636 s. The extra Docker VM,
cached image and host client costs are not included in container memory or data
usage. SQLite and PostgreSQL setups/faults differ; these numbers are not a fair
head-to-head benchmark.

Failure and revision record:

1. The first SQLite attempt passed its eight preceding checks but failed its
   ninth check when reopening a WAL-mode backup read-only:
   `sqlite3.OperationalError: unable to open database file`. The probe was repaired
   to finalize the independent backup with `PRAGMA journal_mode=DELETE` before
   closing and reopening it. A new isolated run passed. No root cause beyond
   this observed WAL/read-only interaction is claimed; production backup opening
   must be checked on its selected filesystem/runtime.
2. The first PostgreSQL probe passed eight assertions in 4.050287 s, but its
   protected effect also advanced a guard revision. That was too permissive for
   LOG03's authority-owner-only writes. The final helper removed that write and
   reran all cases. It also required observing the uncommitted transaction asleep
   after its write before inducing the crash, and enabled data checksums. Use
   the final run for binding evidence.
3. The initial lack of native PostgreSQL executables was resolved by the
   parent-authorized cached container. There was no install, image pull, service
   restart, existing-container change or substitute-store equivalence claim.

Temporary retained helpers and raw records:

| Item | Path / SHA-256 |
|---|---|
| SQLite helper | `/tmp/docsuri-u1-infra-storage/probe.py` |
| SQLite helper digest | `d860fb6d58235e7016a3805364aa3f7c076d4ecf90ba6ec36c4abeb82df8a59a` |
| SQLite passing raw report | `/tmp/docsuri-u1-infra-storage/run-38r1niba/results.json` |
| PostgreSQL helper | `/tmp/docsuri-u1-infra-storage/postgres_probe.py` |
| PostgreSQL final helper digest | `32ce9ec8ecb8a7314e26fe9882e9e9ec17ba3067916ebe299c65ca8a6ec8fadb` |
| PostgreSQL final raw report | `/tmp/docsuri-u1-infra-storage/postgres-run-p9b_rk32/results.json` |
| Earlier PostgreSQL raw report | `/tmp/docsuri-u1-infra-storage/postgres-run-nx8z5ioj/results.json`; earlier helper digest `05472611c744d8255865eb18ae24358c9d3dfe649db3273e1bc9d0c1ea548f30` |

The helper invocation for each was `/usr/bin/python3 <helper-path>`. Helpers use
synthetic schema and assertions, not imported DocSuri services. Temporary files
are not guaranteed durable archives; this document preserves the consequential
settings, results, failures and limits. An expired temporary helper requires
reconstruction/review before rerunning; its digest identifies the original run.

Both owned containers, `docsuri-u1-storage-bc400b36de` and final
`docsuri-u1-storage-d3ecbdfb22`, returned successful removal. An exact-name filtered
container listing subsequently returned no matching container for each. Their
tmpfs data and synthetic dumps were discarded with the containers. Local helper,
SQLite synthetic files and reports remain only under the stated temporary root;
no automatic deletion of unrelated temporary files occurs.

## Documented guarantees and remaining proof

Primary official documentation was consulted on **2026-10-11**. PostgreSQL sources
below are pinned to major version 16. SQLite documentation describes upstream
semantics; the exact Apple-suffixed runtime above remains the tested identity.

| Guarantee | Official basis and implication |
|---|---|
| Serializable committed history | PostgreSQL requires whole-transaction handling of serialization failures; a read from an aborted transaction is not usable authority. Our `40001` observations make finite retry/reconciliation mandatory. [Transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html). |
| Guard lock order | PostgreSQL row locks last through transaction completion; conflicting writers/lockers wait. Consistent multi-object ordering prevents many deadlocks. The adapter must acquire every required owner guard through the same transaction; per-process locks or independently committed databases are insufficient. [Explicit locking](https://www.postgresql.org/docs/16/explicit-locking.html). |
| Unique identities | Non-null primary/unique keys constrain duplicate owner/operation records; application intent comparison and permission checks remain separate. [Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html). |
| Commit acknowledgement | With `fsync=on` and synchronous commit enabled, PostgreSQL waits for the relevant local WAL flush; physical guarantees still depend on the actual storage stack. The probe's tmpfs cannot establish nonvolatile persistence despite these settings. [WAL settings](https://www.postgresql.org/docs/16/runtime-config-wal.html). |
| Consistent database backup | `pg_dump` captures an internally consistent database snapshot; it does not capture cluster-wide roles/tablespaces, external artifacts or newer revocations. Real recovery needs a manifest and protected configuration/role records as well. [SQL dump and restoration](https://www.postgresql.org/docs/16/backup-dump.html). |
| SQLite serialization | Separate connections/processes serialize writes. `BEGIN IMMEDIATE` takes the writer position before read/check/update, which fits a same-file authority/effect guard. This does not prove workload fit. [Isolation](https://www.sqlite.org/isolation.html). |
| SQLite WAL placement and durability | WAL requires processes on the same host and is not a shared network-filesystem design. WAL plus synchronous FULL is the documented durability mode evaluated here; filesystem/device flush behavior still needs verification. [WAL](https://www.sqlite.org/wal.html), [synchronous pragma](https://www.sqlite.org/pragma.html#pragma_synchronous). |
| SQLite backup | The backup API supplies a consistent database snapshot; copying live files independently is not the evaluated method. External immutable bytes/current authority still need coordination. [Backup API](https://www.sqlite.org/backup.html). |

Before any capability is enabled, close the following material gaps in the
selected assembled binding: real adapter/schema and owner-role conformance;
account/session/consent/source-purpose guard combinations; replay authorization
and altered-intent conflicts; claim expiry/clock/reclaim/renew races; full
admission/settlement/reset fault matrix; finite recovery and receipt horizons;
mixed foreground/model/search contention; storage exhaustion and recovery
headroom; external artifact hash/metadata consistency; backup key/role access;
current lifecycle restriction reconciliation; and persistent-volume crash,
power/corruption/media-loss drills appropriate to the claimed envelope. Public
hosting, pgvector/search quality, RPO/RTO targets and user-data continuity remain
separate decisions. Passing these primitives closes none of those obligations.
