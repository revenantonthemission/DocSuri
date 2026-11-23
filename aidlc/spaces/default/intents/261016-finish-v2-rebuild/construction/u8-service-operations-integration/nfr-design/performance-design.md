# Performance Design — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-design-questions.md](nfr-design-questions.md) (Q3, Q5, Q6 and the points settled from the records);
- [performance-requirements.md](../nfr-requirements/performance-requirements.md) (NFR8.1–NFR8.11), with the load of [scalability-requirements.md](../nfr-requirements/scalability-requirements.md) (NFR8.12) and the [tech-stack decisions](../nfr-requirements/tech-stack-decisions.md);
- the [functional spec](../functional-design/functional-spec.md) (Workflows 1, 3, 5–7 and 9) and [rules](../functional-design/rules.md);
- the built code, read on 2026-10-22:
  - the owner transactions, `backend/transactions.py` (`NullConnectionPool`, the process gates, `DeadlineConnection`);
  - the host's health routes, `backend/local_host.py`;
  - the password checks, `backend/modules/accounts/services/guarded_entry.py` (`_credential_work`);
  - search, `backend/modules/discovery/guarded_repository.py` (`snapshot`) and `local_search.py` (`build`);
  - chunking and storage, `backend/modules/corpus/source_parser.py` and `local_schema.sql` (`corpus.projection`, its stored `lexical` column and GIN index);
- measurements on this Mac on 2026-10-22, on the model runtime v1 uses today (Ollama 0.40.6):
  - the search model, bge-m3, loads in 4.9 s from a cold start, and in 1.7 s once its file is in the disk cache;
  - it then embeds a short query in 0.04 s, and about 17 chunks a second of paragraph-sized text (a batch of 16 takes 0.94 s);
  - the research model, qwen3:8b, loads in 5.1 s, answers briefly in 0.3 s, and holds 4.5 GiB in memory.

Every target below holds on this Mac at 20 concurrent signed-in users, with v1 running beside v2 until the switch and sharing the model runtime (NFR8.12). Capacity bounds are in [scalability-design.md](scalability-design.md), and what happens when a part fails is in [reliability-design.md](reliability-design.md).

## 1. Decisions at a glance

| ID | Decision | Source | Serves |
|---|---|---|---|
| P1 | Search picks its candidates inside PostgreSQL: pgvector's HNSW index by meaning and stored text indexes by words, 200 of each, which the built ranking orders in Python | Q5 A | NFR8.4 |
| P2 | The search model stays loaded at all times, and the research model loads when a job needs it | Q3 A | NFR8.4, NFR8.7 |
| P3 | The model runtime holds at most two models and serves one request at a time per model. v2 runs one model job at a time, sends imports' embeddings in batches of about a second, and answers a search with words only if its embedding takes over 2 seconds | settled | NFR8.4, NFR8.5, NFR8.7 |
| P4 | Each transaction opens its own database connection, under per-process limits that add up to 39 of the 50 | settled | NFR8.3, NFR8.7 |
| P5 | One process per job. The host is asynchronous, with a thread pool for blocking work | settled | NFR8.1–NFR8.3 |
| P6 | The build's content-hashed files are cached for a year and sent precompressed; nothing private is cached | settled | NFR8.2 |
| P7 | Readiness answers from the capabilities' recorded state and never probes a dependency during a request | design | NFR8.1, NFR8.6 |
| P8 | A request that starts work records it and answers; the workers do the work | built pattern | NFR8.5 |
| P9 | Real papers get production size limits, and the complete verification runs on a corpus of the real size | Q6 A | NFR8.4, NFR8.8 |
| P10 | The host writes 5-minute latency summaries per route class, with no per-request log line | settled | NFR8.3, § 10 |

## 2. Response targets (NFR8.1–NFR8.6)

### 2.1 The health route, under 200 ms (NFR8.1)

- `/health/live` answers from memory.
- `/health/ready` reads the latest observation of each required capability in one short transaction (the built `local_observation.readiness`), and derives each state from its age (BR3.2). It never calls a provider, the model runtime or the backup volume while the request waits: producers observe on their own schedule (observability-design.md § 3).

### 2.2 Loading the workspace: first load under 2 s, later navigation under 1 s (NFR8.2)

- **What the first load fetches.** The shell (HTML, `no-store`), the entry script, the styles and one navigation request. The build splits its code by route, so the first load carries only the shell's and the first view's code.
- **Budget.** The first load's scripts stay under 300 KB and its styles under 50 KB, both measured compressed. The release's build checks these sizes, and a breach fails the complete verification.
- **Fewer bytes over the upload.** The build's files are compressed once, when the release is built (gzip, from Python's standard library), and the host sends the compressed copy to browsers that accept it. Every byte goes up this Mac's connection to Cloudflare, so this matters most for the first load.
- **Later visits.** Content-hashed files are cacheable for a year (P6), so a later visit downloads only the shell.
- **Later navigation.** It stays inside the page. The destination's code is fetched once and then reused from the cache, and its data comes from API reads (§ 2.3).

### 2.3 API reads, under 500 ms of server time (NFR8.3)

- Each read is one short serializable transaction with the built statement timeout and an absolute deadline (`DeadlineConnection`). Pages are bounded: 50 rows for lists, 100 for search.
- Each transaction opens its own connection (P4). A SCRAM login over loopback costs a few milliseconds. The performance phase of the complete verification measures it; if its 95th percentile ever passes 20 ms, a pool per owner login is reconsidered.
- Each owner's queries use that owner's own indexes. At 20 users, the 95th percentile per route class is read from the latency summaries (§ 10).

### 2.4 Search, under 3 s including the query's embedding (NFR8.4)

**The embedding.** The search model stays loaded (P2), so a query's embedding takes about 0.04 s. If it has not answered within 2 s, the search answers by words only, with the semantic-search-unavailable limitation (the capability registry's degraded meaning for search).

**Candidates, inside PostgreSQL (P1, Q5).** The built search reads every chunk of the corpus on each query and refuses past 256. Production replaces that read with two bounded queries in the same transaction:

| By | Index | Query | Returns |
|---|---|---|---|
| meaning | an HNSW index (cosine distance) on a single-precision `vector(1024)` column of `corpus.projection` | the query's vector against eligible chunks of papers not withdrawn, closest first, `LIMIT 200` | up to 200 chunks |
| words | a stored, per-paper text column with its own GIN index, written with the paper's chunks at import | `plainto_tsquery('simple', …)` against eligible papers, ranked with `ts_rank_cd`, `LIMIT 200` | up to 200 papers, with their best-matching chunks |

- **Meaning.** The transaction sets `hnsw.ef_search = 200`, because an HNSW scan returns no more rows than that setting, and turns on pgvector's iterative index scan, so the eligibility filter never leaves fewer than 200 rows while more exist. The index uses pgvector's defaults (`m = 16`, `ef_construction = 64`).
- **Words.** The built text match requires every term within one paper version, not within one chunk ("chunk boundaries must not turn a matching paper into no-match"). So the word candidates come from a per-paper text column, and the existing per-chunk `lexical` column and its GIN index pick each paper's best-matching chunks for display.
- **Ranking.** The two sets, at most 400 rows, go to the built ranking in `local_search.build`: the best chunk per version, the requested order and the signed cursor. The per-query bound becomes 400 instead of 256.
- **Estimated cost.** At 60,000 chunks: a few tens of milliseconds for the two index queries and a few for the ranking, well inside 3 s even if the embedding uses its whole 2 seconds. The performance phase measures it on the production-size corpus (P9).

### 2.5 Accepting a research, novelty or export request, under 1 s (NFR8.5)

- The request's transaction records the job and its idempotency, and the answer goes back at once (P8).
- No model, provider or Notion call runs inside the request. The workers pick the job up on their next pass.

### 2.6 Start to ready, under 3 minutes (NFR8.6)

- **The chain**, after boot or a crashed job:
  - PostgreSQL's start, with crash recovery bounded by `max_wal_size` (1 GB), replayed in seconds on this disk;
  - the model runtime's start;
  - the tunnel's connection;
  - the host's assembly.
- **The host's wait.** It retries its database with a growing wait from 1 to 30 seconds (reliability-design.md § 4), so it never waits more than 30 seconds after the database answers.
- **First observations.** Every producer observes once as soon as it starts, then on its interval, so readiness never waits for the first 60-second renewal.
- **The search model.** The search probe's first call loads it, which takes 1.7 to 4.9 s as measured.
- **Where it is measured:** the installation's authorized restart, v1's restart rehearsal, and the complete verification for a crashed host and for a crashed PostgreSQL.

## 3. Concurrency and pooling

### 3.1 Database connections (P4)

The built owner transactions use `NullConnectionPool`: each transaction opens its own connection and closes it, so an idle process holds none. Per-process gates (bounded semaphores) cap how many may be open at once. Production sets these gates for v2's instance (`max_connections = 50`):

| Who | Limit | Used for |
|---|---|---|
| the host | 12 | requests |
| the workers | 8 | background work |
| observations | 2 | producers' observation writes |
| maintenance | 2 | the production environment tool's administrative paths |
| the scheduler's login | 3 | restore verifications' checks, scratch database removal and disposals |
| the backup agent | 3 | one dump, or one restore with two parallel jobs |
| the operator tool | 2 | in-person operations |
| the migration tool | 4 | imports through the owners' operations |
| PostgreSQL's superuser | 3 | its default reserved connections |
| **total** | **39** | 11 left for bursts and for inspection in person |

Each owner's login also gets `CONNECTION LIMIT 4`, two each for the host and the workers, matching the built pool size of two per owner and process. The gates make sure the totals hold before a connection opens.

### 3.2 Threads and password checks

- The host runs on Uvicorn's event loop, with AnyIO's thread pool for blocking database and password work. The host's gate of 12 keeps database work well below that pool's size.
- Password checks run one at a time per process, waiting up to 2 seconds for their turn (the built `_credential_work`). So a burst of sign-ins queues, and cannot use up the CPU. The sign-in limits come first (security-design.md § 3.2).

### 3.3 The model runtime (P2, P3)

- **Settings.** `OLLAMA_MAX_LOADED_MODELS=2` and `OLLAMA_NUM_PARALLEL=1` bound the runtime's memory: two models at most, and one request at a time per model.
- **The search model.**
  - Every embedding call v2 makes passes `keep_alive: -1`.
  - The search probe repeats a one-word embedding with `keep_alive: -1` every 60 seconds. v1's calls, which leave the model at the runtime's 5-minute default, are therefore overridden within a minute and cannot unload it.
  - It holds about 1.1 GiB.
- **The research model.** It loads when a research or novelty job needs it, using the default `keep_alive` of 5 minutes. A job after a quiet spell waits about 5 seconds for it, in the background.
- **One model job at a time.** v2's workers run one model job at a time, in a lane of one. Two research turns never share the research model's memory. A search's embedding goes to the other model, so it never queues behind a research turn.
- **Imports.** Embeddings for imports go in batches of about a second (16 paragraph-sized chunks, as measured), so a search's embedding waits at most one batch.

## 4. Caching (P6)

| What | Cached | Why |
|---|---|---|
| The build's content-hashed scripts and styles | `public, max-age=31536000, immutable`, sent precompressed | their names change with their content |
| The shell (HTML) | `no-store` | a new release takes effect on the next load |
| API answers, event streams and paper assets | `no-store` (built) | private, and checked again on every delivery |
| The maintenance notice | `no-store` | the switch back is immediate |
| Capability state | not cached: derived from the latest observations on each read (BR3.2) | the observation table is small and indexed by capability |
| The operations ledger's current state | in the ledger component's memory, rebuilt from the chain on open | the file is the truth |
| The search model | resident in the model runtime (P2) | a cold load breaks the search target |

Cloudflare's edge may also cache the content-hashed files under their `public` headers. Nothing else is cacheable (security-design.md § 4).

## 5. Background work (P8)

- Research, novelty, export, digests, imports, lifecycle effects and corpus maintenance run in the workers, each in its owner's job loop as built. U8 adds only the one-model-job lane (§ 3.3).
- The workers' control loop runs a pass every 2 seconds with its built work deadline, so an accepted job starts within a few seconds when its lane is free.
- 작업 shows progress from the job event stream, with its refresh as the fallback (observability-design.md § 4).

## 6. Memory (NFR8.7)

| Part | Budget | How it is held |
|---|---|---|
| v2's host and workers together | under 4 GiB resident at 20 users | no corpus in memory, since search runs in PostgreSQL (P1); measured in the performance phase and the soak |
| v2's PostgreSQL instance | `shared_buffers = 512MB`, at most 50 connections, `work_mem = 16MB`, `maintenance_work_mem = 256MB` | the HNSW index, about 0.25 GB at 60,000 chunks, is read through shared buffers and the system's file cache |
| The model runtime | about 1.1 GiB always, up to about 5.6 GiB while research runs | P2, P3 |
| v1's data plane and application, and macOS | the rest of the 24 GiB | v1 until it retires |

At its peak, v2's side uses about 4 + 1 + 5.6 ≈ 10.6 GiB, leaving about 13 GiB for v1, macOS and your own applications.

## 7. Bulk operations (NFR8.8, NFR8.9)

### 7.1 A dry run within 2 hours (NFR8.8)

Estimated at today's sizes (599 papers, about 60,000 chunks):

| Step | Estimate | What bounds it |
|---|---|---|
| Snapshot of v1's database, index and the selected objects (Q6 of NFR Requirements) | minutes | a few GB, written to the backup volume |
| Restore of v1's dump into the import database | minutes | 0.23 GB |
| Accounts, settings and saved papers through their owners' import operations | minutes | hundreds of records |
| Paper conversion within the production limits (§ 11) | about 10–20 minutes | parsing 599 papers |
| Embedding every chunk with the pinned model | about 60 minutes | 60,000 chunks at 17 a second, as measured |
| Building the HNSW index after the import | minutes | `maintenance_work_mem` of 256 MB |
| The parity report | minutes | counts and checksums per kind |

- **Total.** About 1.5 hours, inside the 2 hours. Every dry run records its duration and each step's, and the accepted run's are shown with your switch-start decision.
- **The final run** does the same work inside the switch's 4 hours (NFR7.15).
- **The risk.** Embedding dominates. Above about 85,000 chunks, at the measured speed, a run would pass its 2 hours. The first dry run counts the real chunks. If its duration passes the bound, the run's report says so, and the remedy (reusing the accepted dry run's own vectors in the final run, which the pinned model made under the same policy) is put to your decision then. Until then, no vector is reused (NFR4.4).

### 7.2 Backups, restores and verifications (NFR8.9)

| Operation | Bound at the 8 GiB budget | Design |
|---|---|---|
| Backup | 25 minutes | `pg_dump` in custom format, one job, as the backup agent |
| Restore into a database | 45 minutes | `pg_restore -j 2`. The HNSW index is rebuilt during the restore, with `maintenance_work_mem = 1GB` and `max_parallel_maintenance_workers = 2` for that session; v2 is stopped during a production restore, so the memory is free |
| Restore verification, with its checks and the scratch database's removal | 60 minutes | the same restore, but with the instance's own `maintenance_work_mem` of 256 MB, since v2 keeps running; then the tombstone replay, the integrity check and the drop |

- At today's sizes, each of these takes minutes. The index rebuild is the one step that grows faster than the data, so the soak's restore verification records its duration separately.
- scalability-design.md § 5 turns that measurement into a warning before the database grows to a size whose rebuild would pass the bound.

## 8. The isolation check, within 60 seconds (NFR8.10)

- Its items are local checks: owners, modes and digests, `launchctl print` per job, the filter's anchor, `tmutil isexcluded` twice, the socket owners and the stop records.
- The library check (`otool -L`) is the slowest. Its result is kept per program digest, so only a changed program is checked again.
- Each item has its own time limit. An item that hangs fails as unknown, and the whole check still ends within 60 seconds.

## 9. Pinned versions (NFR8.11)

- Every measurement records the versions it ran on: PostgreSQL 16.14 with pgvector, Ollama 0.40.7, cloudflared 2026.10.3, Python 3.13.7 and the release tag.
- The model timings above were taken on v1's Homebrew runtime, 0.40.6. The installation measures them again on the pinned 0.40.7.
- An upgrade measures NFR8.1–NFR8.6 again before its release reaches production.

## 10. How performance is measured (P10)

- **Latency summaries.**
  - The host keeps a fixed-bucket histogram per route class in memory, with no per-request record.
  - Every 5 minutes it writes one JSON line per class to the profile's evidence folder: the window's start, the class, the count, the median, the 95th percentile, the maximum and the count of 5xx answers.
  - It writes no identifier and no path beyond the class's name. Lines are kept 14 days, so they cover the 7-day soak.
- **Route classes.** A fixed list: health, navigation, read, search, accept, stream, asset, static and administration. Each route gets its class when it is registered, and a route without one fails the assembly check.
- **The performance phase** of the complete verification drives 20 concurrent synthetic users against the composed realm, on a production-size synthetic corpus (§ 11). It checks NFR8.1, NFR8.3, NFR8.4 and NFR8.5 from these summaries, and NFR8.2 from a real browser's timings.
- **The soak** records the same summaries on the production profile. Its evidence shows each measure's 95th percentile with your switch-start decision.
- **NFR8.6** is measured from the times the standing job records: when a job starts or relaunches, and when readiness turns true.

## 11. Real papers and a production-size test corpus (P9, Q6)

CorpusContent and its parser get production limits, selected by the production profile in the same way as the account policy (security-design.md § 3.1). The synthetic realms keep theirs:

| Limit | Synthetic (built) | Production |
|---|---|---|
| Chunks per paper | 256 | 2,000 |
| A block over 8 KB | the paper is refused | split at sentence boundaries into chunks of at most 8 KB |
| HTML elements per page | 20,000 | 250,000 |
| Nesting depth | 128 | 256 |
| Parsed text per paper | 2 MiB | 16 MiB |
| Candidates per search | 256 for the whole corpus | 400 per query (§ 2.4) |

- **Split blocks.** Each piece keeps its block's anchor with a piece number, so citations still lead to the block.
- **Misfits.** A paper beyond these limits is still a misfit, with its reason in the migration's report (BR8.9).
- **Revising.** The first dry run records the largest real values of each limit, and the limits can be revised then.
- **The test corpus.** The complete verification generates a synthetic corpus at the first dry run's measured size: the paper count, the spread of chunks per paper and the largest values. So search, import and every other limit run at the real scale before the soak.
