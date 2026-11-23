# Scalability Requirements — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-requirements-questions.md](nfr-requirements-questions.md) (Q2, Q6, Q7, Q9–Q11, Q20, Q21, Q24);
- inception [requirements FR4.1 and NFR6](../../../inception/requirements-analysis/requirements.md);
- this Unit's [functional spec](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md) (BR6.6 above all);
- the [technology stack](../../../../../codekb/DocSuri/technology-stack.md);
- sizes measured on this Mac on 2026-10-22 (nfr-requirements-questions.md § "Follow-up questions (2026-10-22)").

These are the capacity targets of the derived group **NFR8** (FR4.1). The performance targets NFR8.1–NFR8.11 are in [performance-requirements.md](performance-requirements.md). The service runs on one machine and does not scale out: each target is a bound to stay within, with the signal that shows when it is approached.

## Load and accounts (NFR8)

- **NFR8.12** — The service meets its performance targets at 20 concurrent signed-in users.
  - When admission opens, only migrated accounts exist.
  - Once you open registration, the service accepts at most 500 accounts. Sign-up beyond that is refused with AccountAccess's existing answer, and the cap changes only by a new release (BR6.8). [Q10, Q11]

## Storage on the internal disk (NFR8)

- **NFR8.13** — Production storage budget: 8 GiB, counting the production database plus the write-ahead log of v2's PostgreSQL instance, whatever the database is named (BR6.6).
  - storage.capacity shows degraded with capacity-approaching above 80% of it (6.4 GiB).
  - Storage admission closes with the existing capacity-exhausted answer before the budget is crossed, and recovery routes stay open.
  - The write-ahead log is configured to at most 1 GiB (`max_wal_size`), with no archiving, no replication slots and `wal_keep_size` 0.
  - The first dry run measures the real sizes, and the budget can be revised then. [Q7, Q21]
- **NFR8.14** — Internal-disk floors. Each is read as the free space macOS reports to programs, never counting space macOS could reclaim (BR6.6) [Q7, Q20, Q21]:

| Reading | Effect |
|---|---|
| below 20 GiB free | storage.capacity degraded with internal-disk-low. A restore verification or a dry-run import phase starts only if the free space, less what it will write, stays above 20 GiB |
| below 10 GiB free (critical floor) | storage.capacity unavailable with internal-disk-critical. Storage admission closes, scheduled restore verifications and imports stop, and an incident opens at once |

  Before the first dry run, the internal disk must read at least 23 GiB free: the 20 GiB threshold plus the run's own databases. It read 11.7 GiB on 2026-10-22. Deleting Time Machine's local snapshots frees most of the difference.
- **NFR8.15** — Database sizes the internal disk holds at once: the production database, at most two rehearsal databases (the accepted dry run's and the one a newer run builds), one import database and one scratch restore (BR8.11). At today's sizes this is a few GB in all. The guards in NFR8.14 bound them, because they have no budget of their own (BR6.6).

## Storage on the external drive (NFR8)

- **NFR8.16** — The backup volume keeps at least 64 GiB free (the backup floor). Below it, storage.capacity shows degraded with backup-volume-low, and no write runs on the volume. Deletion still runs, because deleting is what frees space (BR6.6).
  - Retention keeps at most 22 live sets (14 daily and 8 Sunday sets) with their ledger copies, plus rehearsal sets during the soak and the migration's file copies. At today's sizes a set is well under 1 GB. At the full 8 GiB budget the live sets stay under 180 GiB.
  - The backup volume shares its APFS container, 784 GB free on 2026-10-22, with SSD01 and the new encrypted volume for v1's stores (Q24). The backup floor is read as the free space the backup volume reports, so it includes their growth. [Q2, Q21, Q24]
- **NFR8.17** — Measured baseline, 2026-10-22, against which growth is judged:
  - v1's database: 0.23 GB. Its search index: 599 documents in 11 MB. Its object store: 25 GB, of which a migration copy takes only the objects the imported papers need (Q6).
  - The models folder: 5.9 GiB, held as APFS clones of your home folder's copies, so it takes no extra space.
  - The first dry run's parity report records the real counts, and its snapshot and rehearsal database record the real sizes (BR8.10, BR9.2 (8)). storage.capacity's observations then show the production footprint against the budget on 운영 (BR3.6).

## Email and monitoring quotas (NFR8)

- **NFR8.18** — Email and monitoring stay within their free plans [Q9]:
  - Email follows NFR6.2: account mail up to 90 a day, digests up to 60 a day, everything up to 2,700 a month.
  - healthchecks.io: v2 uses 3 of its 20 free checks, beside v1's existing 2.
