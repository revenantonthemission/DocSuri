# Scalability Design — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-design-questions.md](nfr-design-questions.md) (Q1, Q5, Q6 and the points settled from the records);
- [scalability-requirements.md](../nfr-requirements/scalability-requirements.md) (NFR8.12–NFR8.18), with [performance-requirements.md](../nfr-requirements/performance-requirements.md) (NFR8.7–NFR8.9) and the [tech-stack decisions](../nfr-requirements/tech-stack-decisions.md);
- the [functional spec](../functional-design/functional-spec.md) (the capability registry, Workflows 6, 9 and 19, and amendment A10) and [rules](../functional-design/rules.md) (BR6.6, BR8.11, BR9.17);
- the built code, read on 2026-10-22: the owner transactions and their gates, `backend/transactions.py`; the synthetic capacity admission, `backend/control_runtime.py`; and AccountAccess's account cap, `backend/modules/accounts/services/control_entry.py` (`account_limit`);
- sizes measured on this Mac on 2026-10-22 (nfr-requirements-questions.md, § "Follow-up questions (2026-10-22)").

The service runs on one machine and does not scale out. Each bound below is a limit to stay within, with the signal that shows when it comes near. Speed is in [performance-design.md](performance-design.md).

## 1. Decisions at a glance

| ID | Decision | Source | Serves |
|---|---|---|---|
| S1 | One machine, one copy of each process; every bound has a named signal and a fixed effect | settled | NFR8.12 |
| S2 | One capacity footprint: the current environment's database plus the WAL of v2's instance, observed every 60 seconds | amendment A10 | NFR8.13 |
| S3 | Free space is the space macOS reports to programs, read with `statvfs`, on the internal disk and on the backup volume | NFR Requirements Q20 | NFR8.14, NFR8.16 |
| S4 | Storage admission closes while there is still room for the largest single write | design | NFR8.13 |
| S5 | A request's work does not grow with the corpus: search uses indexes (Q5), and each paper is bounded (Q6) | Q5, Q6 | NFR8.12 |
| S6 | The two costs that grow fastest are tracked against their bounds: an index rebuild during a restore, and a dry run's embedding | design | NFR8.8, NFR8.9 |

## 2. Load and accounts (NFR8.12)

- **20 concurrent users.** One host process, with the per-process connection gates of performance-design.md § 3.1. Past the gates, a request gets the built busy answer, which can be retried, and never an unbounded wait.
- **Work per request** does not grow with the corpus (S5):
  - search asks two indexes for 200 rows each (performance-design.md § 2.4);
  - lists are paged;
  - each paper's import is bounded by the production limits (performance-design.md § 11).

  More papers make the indexes larger, not a single request's work.
- **The account cap.** The production policy's cap of 500 (security-design.md § 3.1) is checked by AccountAccess's built account count when an account is created, and is refused with its existing answer. The cap changes only in a new release.
- **Before registration opens**, only migrated accounts exist. The first dry run's parity report gives their count.

## 3. Storage on the internal disk (NFR8.13–NFR8.15)

### 3.1 The capacity footprint (S2)

- **The definition** (amendment A10): the size of the current environment's database, `pg_database_size`, plus the WAL folder of v2's instance, `pg_ls_waldir()`. The current database is the rehearsal database during the soak and the production database in live mode, whatever it is named. This one definition replaces the three conflicting ones in the built code (BR1.5).
- **Reading the WAL folder.** ServiceOperations' operations login is made a member of `pg_monitor`, which PostgreSQL requires for `pg_ls_waldir()`. That role reads statistics and settings and grants no write. Role memberships belong to the instance, not to a database, so no dump carries them, and restores are unaffected.
- **The producer.** The footprint is storage.capacity's producer, observed every 60 seconds (observability-design.md § 3).

### 3.2 The budget (NFR8.13)

| Footprint | storage.capacity | Effect |
|---|---|---|
| below 6.4 GiB (80%) | available | — |
| from 6.4 GiB | degraded, capacity-approaching | shown on 운영 |
| from 8 GiB less 256 MiB of headroom | unavailable, capacity-exhausted | storage admission closes with the existing capacity-exhausted answer. Recovery routes stay open |

- **The headroom.** The headroom is larger than the largest single admitted write: one paper at its production limits, that is 16 MiB of parsed text with up to 2,000 chunks and their vectors, which is well under 100 MB (S4). So an admitted write can never carry the footprint across the budget.
- **The write-ahead log** is set to `max_wal_size = 1GB`, `wal_keep_size = 0`, `archive_mode = off`, with no replication slots and no WAL senders. The WAL therefore stays near 1 GB at most and is counted in the footprint.
- **Revising.** The first dry run measures the real sizes, and the budget can be revised then.

### 3.3 The internal disk's floors (NFR8.14, S3)

- **The reading.** Free space is `f_bavail × f_frsize` from `statvfs` on the data volume, which is the space macOS reports to programs. It never counts space macOS could reclaim, such as local snapshots and caches.
- **Who reads it.** storage.capacity reads it every 60 seconds. The standing authority reads it again just before it starts a restore verification, and the migration tool before each import batch.

| Free space | storage.capacity | Effect |
|---|---|---|
| 20 GiB or more | — | — |
| below 20 GiB | degraded, internal-disk-low | a restore verification or a dry-run import starts only if the free space, less what it will write, stays above 20 GiB |
| below 10 GiB (the critical floor) | unavailable, internal-disk-critical | storage admission closes. A running import stops at its next batch boundary. A running verification stops and drops its scratch database. No new one starts, and an incident opens at once |

- **What a run will write:**
  - for a restore verification, the source database's size when its set was dumped (Workflow 6);
  - for a dry-run import, the rehearsal database's expected size: the last accepted dry run's measured size, or 4 GiB before the first one.
- **Before the first dry run**, the disk must read at least 23 GiB free: the 20 GiB threshold plus the run's own databases. It read 11.7 GiB on 2026-10-22. Deleting Time Machine's local snapshots frees most of the difference.

### 3.4 Databases held at once (NFR8.15)

- At most these are on the internal disk at once:
  - the production database;
  - two rehearsal databases: the accepted dry run's, and the one a newer run builds;
  - one import database;
  - one scratch restore.
- PlatformControl's database operations refuse to create a third rehearsal database, or a second import or scratch database, while one exists. They count the existing databases by their fixed name patterns.
- These databases have no budget of their own: the floors of § 3.3 bound them together.

## 4. Storage on the external drive (NFR8.16)

- **The backup floor.** The backup agent's status check reads the backup volume's own free space with `statvfs` on its mount point, as the backup account. Below 64 GiB:
  - storage.capacity is degraded with backup-volume-low;
  - nothing is written to the volume;
  - deletion still runs, because deleting is what frees space.
- **What the volume holds:**
  - at most 22 live sets (14 daily and 8 Sunday sets), each with its ledger copy;
  - the rehearsal sets during the soak;
  - the migration's file copies, each disposed of on its own terms (security-design.md § 9).
- **Set sizes.**
  - With every chunk's vector in the database (Q5), a set at today's size is about 0.3–0.5 GB, still well under 1 GB. Vectors compress poorly, so they make up most of it.
  - At the full 8 GiB budget, the 22 live sets stay under 180 GiB.
- **Shared space.** The volume shares its APFS container (784 GB free on 2026-10-22) with SSD01 and v1's new volume. The floor reads the backup volume's own free space, so it includes their growth.

## 5. Baseline and growth (NFR8.17, S6)

**The baseline**, measured on 2026-10-22:

- v1's database: 0.23 GB;
- its search index: 599 documents in 11 MB;
- its object store: 25 GB, of which a migration copy takes only the objects the imported papers need;
- the models folder: 5.9 GiB, held as APFS clones of your home folder's copies, so it takes no extra space.

**The first dry run records:**

- the real counts (the parity report);
- the chunk count and the largest value of each paper limit (performance-design.md § 11);
- the rehearsal database's size;
- a set's size;
- the embedding time;
- the HNSW index's build time.

**Growth signals:**

| What grows | Measured by | Shown | Before it matters |
|---|---|---|---|
| The footprint against the budget | storage.capacity, every 60 seconds | 운영 | degraded at 80% (§ 3.2) |
| The HNSW index's rebuild time inside a restore | every restore verification, recorded with its result | 운영, beside the 45-minute restore bound (NFR8.9) | the record also shows the rebuild time projected to the full 8 GiB budget. If that projection passes the bound, the next soak or release decision sees it |
| A dry run's embedding time | every dry run's step durations | the run's report, and your switch-start decision | above about 85,000 chunks, at the measured speed, a run would pass its 2 hours (performance-design.md § 7.1) |
| Accounts against the cap | AccountAccess's account count | the refusal at 500 | — |

## 6. Email and monitoring quotas (NFR8.18)

- **Email** follows NFR6.2 through the shared count in the operations ledger (security-design.md § 13): account mail up to 90 a day, digests up to 60 a day, both counted in one daily total, and everything up to 2,700 a month.
- **healthchecks.io.** v2 uses 3 of the free plan's 20 checks, beside v1's existing 2.

## 7. Bounds and signals

| Bound | Value | Signal | Effect |
|---|---|---|---|
| Concurrent signed-in users | 20 | the latency summaries (performance-design.md § 10) | none automatic. Measured in the performance phase and the soak |
| Database connections | 39 of 50 in use at most | the gates' busy answers | the request answers busy and can be retried |
| Accounts | 500 | AccountAccess's count | sign-up is refused with the existing answer |
| The footprint | 6.4 GiB | storage.capacity degraded, capacity-approaching | shown on 운영 |
| The footprint | 8 GiB less 256 MiB | storage.capacity unavailable, capacity-exhausted | storage admission closes. Recovery routes stay open |
| Internal disk free | under 20 GiB | internal-disk-low | verifications and imports need their write plus 20 GiB free |
| Internal disk free | under 10 GiB | internal-disk-critical, with an incident | admission closes, and verifications and imports stop |
| Backup volume free | under 64 GiB | backup-volume-low | no write. Deletion continues |
| Email | 60 a day for digests, 90 a day in all, 2,700 a month | provider.resend degraded, allowance-exhausted | digests wait, and account mail fails with a plain message |
| The model runtime | one request at a time per model | queueing | a search's embedding gets 2 seconds, then the search answers by words only |
| Paper size | the limits of performance-design.md § 11 | the migration report's misfits | the paper waits for your decision |

## 8. Beyond these bounds

Outgrowing this Mac is not designed here. A second machine would need its own tunnel origin, a database replica and a shared backup volume. The account cap and the storage budget are the brakes that keep the service inside one machine. Raising either needs a new release with a measured baseline, and a check that the bounds in § 7 still hold.
