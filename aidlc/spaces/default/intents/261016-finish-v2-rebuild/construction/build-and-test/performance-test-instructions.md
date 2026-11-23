# Performance test instructions

U8 derives the performance and capacity group NFR8 from FR4.1, production-level operation on this Mac: NFR8.1–NFR8.11 for response, resources and bulk work, and NFR8.12–NFR8.18 for load and storage. U5 and U6 set no performance target of their own. This file says how each NFR8 target is measured: on the composed realm here, and, where the design says so, at the installation and during the soak.

## Sources

- U8 `nfr-requirements/performance-requirements.md` and `scalability-requirements.md`.
- U8 `nfr-design/performance-design.md` (§§ 2, 6–10) and `scalability-design.md`.
- U8 `code-generation/code-generation-plan.md` ("Completion and evidence boundaries"), `unit-test-instructions.md` (the performance phase, the build gate) and `code-summary.md`.
- The phase code: `run_performance` and `TARGETS_MS` in `scripts/u8_phases.py`; the realm's database settings in `scripts/verify_docsuri_u8.py`.

## Framework setup and configuration

- **The performance phase** of `scripts/verify_docsuri_u8.py`:
  - 20 concurrent synthetic users (memberA, memberB and memberE, whom no journey ends), for 60 seconds, each acting about every 5 seconds;
  - a real browser first (Playwright on `e2e/u8-complete/navigation.spec.ts`, through the public stand-in), for first load, later navigation and the accepted answer;
  - the host's per-route-class latency summaries for server time, written every 5 minutes with no identifier or path;
  - a readiness sample every second.
- **Targets, 95th percentile in milliseconds** (`TARGETS_MS`): health 200, first load 2,000, navigation 1,000, API read 500, search 3,000, accept 1,000.
- **What fails the phase:** a missed target, any refused request (a 5xx, a refused connection or a limit), a readiness sample that is not ready or has admission closed, a failed browser measurement, or a backup over its protocol's deadline.
- **The corpus:** the production-size synthetic corpus, 600 papers of 100 chunks (60,000 chunks), with the deterministic stand-in embedder. The phase refuses unless the corpus is complete.
- **The database:** PostgreSQL 16.14 with pgvector, with `shared_buffers=512MB` and `max_connections=50`, as in production (NFR8.7). The EXPLAIN check records the meaning query's HNSW plan and the words query's GIN plan with production's planner settings; the plans are recorded, not judged.
- **The backup measurement:** one backup of the realm's production-size database through the standing scheduler and the backup protocol, timed against `platform.database.backup`'s deadline in `ops/src/docsuri_ops/platform_control/inventory.json`.
- **Memory:** each phase's supervisor records the peak resident memory of the realm's process tree and of the companion host's tree, each under its own 1 GiB limit.
- **When the result counts:** the phase records `counts: true` only when an installation runs it from `releases/<tag>/` (cicd-pipeline § 5.1 step 3). Anywhere else it records `counts: false`, and nothing claims the production figures from it.

## How to run

The performance phase needs the corpus that `verification-run` loads, so it runs on realm B straight after the complete verification:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase performance --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

After `performance`, realm B measures capacity under a page-load burst beside open job pages (U8's CP-6, record-only):

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase capacity-burst --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

It loads the shell for 20 users over three accounts at once, beside 0, 4 and 8 open job streams, three runs of each. It records each run's loaded users, refusals by kind, the host's per-route-class times, the owner gates' waits and the memory. It fails only on a prerequisite: no complete corpus, a host that is not ready, or a run that does not reach its size. Its figures are recorded, not judged (U8's code summary, record 102).

The first-load budget runs on realm A:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase build-gate --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

It fails when the composed application's first load passes 300 KB of scripts or 50 KB of styles, compressed.

Time-based capacity behaviour (freshness, windows, retention, the isolation check's interval) runs in U8's component and operations phases with the injected clock, never with real waits.

### Q5's vector storage at 60,000 chunks (read-only, since run 5)

Q5 (U8 `nfr-design-questions.md`) puts the single-precision vectors and their HNSW index at about 0.5 GB at 60,000 chunks, inside the 8 GiB budget. No phase measured it before run 6, so since run 5 (2026-11-19) it is read directly. On a fresh U8 realm, run `setup`, `migrate` and `fixtures`, then `fixtures --corpus only` until it reports `fixtures-ready` with 600 papers. In run 5 the first `--corpus only` pass was refused on the database's time limit and the second completed. Run 5 set the realm up with `build_realm.py --min-free 15 --keep-live` at 21.19 GiB free, below the tool's 22 GiB default. That default guards J09's restore check, which needs free disk less the realm database above 20 GiB; this realm runs no J09 phase, so a lower floor serves, as for realm A. Free disk fell to 19.42 GiB during the refused load. Then read the sizes with one read-only query against the realm's `docsuri_u8` database, through Colima's socket (`DOCKER_HOST` as `build-instructions.md` sets it):

```sql
SELECT count(*), count(embedding_vector), sum(pg_column_size(embedding_vector)), pg_relation_size('corpus.projection_embedding_hnsw'), pg_total_relation_size('corpus.projection'), pg_database_size('docsuri_u8') FROM corpus.projection
```

The first two columns must both read 60,000. The third (the vectors) plus the fourth (the index) is the figure Q5 names; the last is the whole database, against the 8 GiB budget. Synthetic vectors give the same sizes as real ones, because `vector(1024)` is fixed width. The query changes nothing; afterwards archive the realm with `archive-owned`.

**Since run 6 (2026-11-23) the performance phase measures it itself.** U8's loop-back 4 (decision L4-2 (a)) added a `vectorStorage` block to the phase's evidence, with two checks (`scripts/u8_phases.py:837`, `:862-881`, `:1157-1160`): `vector-storage-past-its-figure` fails when the vectors plus the index pass 105% of (12,292 B per chunk × chunks + 8,192 B), 774,404,601 B at 60,000 chunks, the maintainer's corrected figure recorded in U8's records without editing the approved design file; and `footprint-past-its-budget` fails when the database plus the write-ahead log pass 8 GiB (NFR8.13). So run 6 read Q5 from realm B's performance evidence, and the separate read-only realm above did not run. The phase passing does not make Q5's original "about 0.5 GB" Met: the matrix judges that figure on its own.

In run 6, realm B ran `performance` and then `capacity-burst` each by its own command, after `verification-run` and `compatibility`, in one `build_realm.py` call of the U8 chain (`integration-test-instructions.md`).

## Where each target is measured

| Target | On the composed realm (this stage) | Counted measurement, and the stage that owns it |
|---|---|---|
| NFR8.1 health under 200 ms | the performance phase, local probe | each installation's performance phase and the soak: Deployment Execution, Performance Validation |
| NFR8.2 first load under 2 s, later navigation under 1 s | the performance phase's browser, through the public stand-in | a real browser through `docsuri.rvnnt.dev` at the installation and the soak: the same stages |
| NFR8.3 API reads under 500 ms, server time | the host's summaries during the load. Since loop-back 2 (L2-2) each real route records under its own class: the `read` class counts GET and POST reads, and job streams and assets have their own `stream` and `asset` classes. In run 5 the host counted 147 requests in the `read` class against the 120 reads its users were answered (60 GET session reads and 60 POST settings reads), and 6 in `static`; the read class's p95 was 200 ms, `readClassCheck` passed (null), with `counts: false`. In run 6 the counts were the same (147 in `read`, 6 in `static`), the read class's p95 was 100 ms, `readClassCheck` passed (null), again with `counts: false` | each installation's performance phase and the soak, as for NFR8.1: Deployment Execution, Performance Validation |
| NFR8.4 search under 3 s, including the local embedding with the pinned `bge-m3` | the load's search requests, with the stand-in embedder in place of the real model | the installation and the soak, with the pinned model: the same stages |
| NFR8.5 accepting a request under 1 s | the browser's accepted answers | the same |
| NFR8.6 start to ready under 3 minutes | not measured on the realm | the installation's authorized restart (Workflow 20 step 10) and v1's restart rehearsal, from the times the standing job records: Environment Provisioning, Performance Validation |
| NFR8.7 under 4 GiB for the host and workers; `shared_buffers` 512 MiB; at most 50 connections | the supervisors' peaks under 1 GiB per tree; the realm's database settings | the soak at 20 users: Performance Validation |
| NFR8.8 a dry run within 2 hours | not measured on the realm | every dry run on real v1 data records its duration: the Operation stages |
| NFR8.9 backup within 25 minutes, restore within 45, restore verification within 60, at the 8 GiB budget | one backup of the synthetic production-size database; the restore paths and J09 at the realm's size | the soak's backups and restore verification: Performance Validation |
| NFR8.10 the isolation check within 60 seconds | `operations/test_isolation_check.py` with recorded tool output | the installation's step 11 and every 5 minutes after it: Environment Provisioning |
| NFR8.11 pinned versions in every measurement | the phase records the Python version | every installation's measurement records PostgreSQL, Ollama, cloudflared, Python and the tag |
| NFR8.12 20 concurrent users; at most 500 accounts after registration opens | the performance phase's 20 users; AccountAccess's account cap in U8's component tests | the soak |
| NFR8.13–NFR8.16 the storage budget, the internal-disk floors, the database count and the backup floor | storage.capacity's tests with injected readings; NFR8.15's limits in the cutover and migration tools' tests | the first dry run measures the real sizes: the Operation stages |
| NFR8.17 the measured baseline | not applicable on the realm | the first dry run's parity report and snapshot |
| NFR8.18 email and monitoring within their free plans | the email allowance tests (U5, U8 component); the monitoring configuration's three checks | live mode after the first approval |

## Expected results

- Every target in `TARGETS_MS` met at the 95th percentile, `missedTargets` empty, no refused request, every readiness sample ready.
- The backup within its protocol's deadline.
- The first load within 300 KB of scripts and 50 KB of styles.
- The load's own request rate recorded beside v1's. Before an installation, v1's rate is recorded as not yet available; at the installation the phase fails if v1's rate is higher or missing.

No target is relaxed, no bound is raised and no user count is lowered to make the phase pass.

## Test data and environment

- Realm B: `setup`, `migrate`, `fixtures --corpus skip`, `verification-run` (which loads the corpus), `compatibility`, `performance`, then `capacity-burst`. The operations lane runs alone, on realm C.
- The load uses only accounts no journey has ended, so it measures the service, not a fixture account.
- The phase's evidence file, `performance-evidence-<time>.json`, stays in the realm's run root and is kept in the preserved folder after `archive-owned`.
- Before the run, free disk on this Mac should be above 25 GiB, because the corpus and the recovery journey share the realm's database volume.
