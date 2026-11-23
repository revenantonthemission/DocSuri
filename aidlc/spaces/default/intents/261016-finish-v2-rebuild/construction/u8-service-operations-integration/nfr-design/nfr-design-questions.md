# NFR Design Questions — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Inputs:

- the confirmed NFR requirements: [security](../nfr-requirements/security-requirements.md), [reliability](../nfr-requirements/reliability-requirements.md), [performance](../nfr-requirements/performance-requirements.md), [scalability](../nfr-requirements/scalability-requirements.md) and [observability](../nfr-requirements/observability-requirements.md), the [tech stack decisions](../nfr-requirements/tech-stack-decisions.md) and their [questions](../nfr-requirements/nfr-requirements-questions.md) (Q1–Q25);
- the two points the last [NFR requirements review](../nfr-requirements/reviews/review-04.md) left open for the U8 checkpoint (R-20 and R-21, both about the log rotation job);
- this Unit's [functional spec](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md);
- the built code: the sign-in services (`backend/modules/accounts/services/guarded_entry.py` and `control_entry.py`), the account-controls policy (`backend/modules/accounts/control_policy.py`), the owner transactions (`backend/transactions.py`), the local host (`backend/local_host.py`), U5's Resend adapter (`backend/u5_real_delivery.py`) and the operator tool's authority (`ops/src/docsuri_ops/platform_control/authority.py`);
- measurements on this Mac on 2026-10-22: the model runtime's load times (Ollama 0.40.6, the runtime v1 uses today) and sudo's settings (sudo 1.9.17p2).

This stage turns the approved requirements into a concrete design: how each part of the running service meets its targets, and which parts make up the arrangement. Most of it follows from what you already decided. The four questions below are the gaps no earlier answer covers. Each question offers the design I recommend as A. Answer with a letter, or in your own words under X.

## Settled from the records (no question)

These follow from decisions on record, from the built code or from the measurements. If one should change, say so under X of the closest question.

- **Processes.** v2 runs one host process (FastAPI on Uvicorn, using its thread pool for database and password work), one workers process, one scheduler process and the maintenance server, each one system launch job. Nothing runs a second copy: one machine at 20 concurrent users needs no scaling out (NFR8.12).
- **Database connections.** Connections stay unpooled: each transaction opens its own and closes it, as the built owner transactions do, so an idle process holds none. The 50 connections of v2's instance (NFR8.7) are shared out by per-process limits like the built ones: host 12, workers 8, observations 2, maintenance 2, the scheduler's login 3, the backup agent 3, the operator tool 2, the migration tool 4, and PostgreSQL's 3 reserved for its superuser. That leaves 11 spare.
- **Model work.** The runtime keeps at most two models loaded and serves one request at a time per model (`OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_NUM_PARALLEL=1`), which bounds its memory. v2's workers run one model job at a time, and an import's embedding batches are sized to take about a second, so a search's embedding never waits behind more than one batch. A search whose embedding has not answered within 2 seconds returns lexical results only, with the semantic-search-unavailable limitation (the capability registry's degraded state for search).
- **Caching.** The workspace build's content-hashed files are sent as cacheable for a year (`Cache-Control: public, max-age=31536000, immutable`), so a later visit fetches only the page shell. The shell and every API, event-stream and paper-asset answer keep the built `no-store`, so neither a browser nor Cloudflare stores anything private.
- **Security headers.** The built boundary headers stay: the content security policy (`default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`), `nosniff` and `no-referrer`. Production adds `form-action` limited to this origin and the two sign-in providers, and HSTS for the public origin. The host accepts the host names `docsuri.rvnnt.dev` and `127.0.0.1` only. The maintenance server sends the same headers.
- **Request identifiers.** The host gives every request a fresh identifier and never takes one from a request header. It appears in the error answer's `requestId`, in every log line and in observations (NFR9.11).
- **Logs.** Each line is one JSON object with fixed keys, written with Python's standard library.
  - v2's own processes write through a handler that reopens its file once the file is moved. So the 03:00 job moves those logs aside instead of truncating them, and nothing written to them is lost.
  - Copy-then-truncate stays only for launchd's standard-output and error files and the runtimes' own logs. Lines written between the copy's last read and the truncation can still be lost there; the job records how many bytes that was, so the gap is counted, never hidden (R-21).
  - The job opens every file without blocking and then checks that it is a regular file, so a planted pipe cannot stall it (R-21). Tests cover a log folder, and a folder above it, replaced by a link: each is skipped and recorded, and nothing at the link's target is read, copied, truncated or deleted (R-20).
- **Latency evidence.** The host keeps each route class's server times in memory and every 5 minutes writes a summary (count, median, 95th percentile and maximum) to the profile's evidence folder, kept 14 days. No line is logged per request, because HTTP access logs stay off (BR3.9). The soak's evidence reads these summaries (NFR8.3).
- **Email allowance.** The count lives with the Resend provider's record in the operations ledger (entities.md, ProviderActivation), so a production restore cannot roll it back. Account mail and digests each reserve a send through ServiceOperations before calling Resend. A reservation is refused once the day reaches 60 sends for digests or 90 for all mail, or the month reaches 2,700 (NFR6.2). Each message carries its own Resend idempotency key, as U5's adapter already does. A send Resend refuses releases its reservation, and a send whose outcome is unknown keeps it.
- **Providers' time limits.**
  - Google and ORCID: 10 seconds per call, with no automatic retry; the person simply signs in again.
  - Resend account mail: up to 3 attempts within 30 seconds after a timeout, a 429 or a 5xx answer, always with the same idempotency key.
  - The model runtime: 2 seconds for a search embedding; a job's own deadline for generation.
  - Every provider's capability probe: 5 seconds.
  - Each provider's capability state works as its circuit breaker: while it is unavailable, the features that depend on it say so and do not call it (NFR7.12).
- **The standing job.** One long-running process with a separate lane per task, so a 25-minute backup or a 60-minute restore verification never delays the 5-minute probes, the availability record or the pings. A task still running when its next turn comes is skipped and recorded, never run twice at once.
- **Operator credentials.** A root fixed command reads the operator tool's database login from the System keychain and hands it over through an inherited pipe, never through arguments, the environment or a file (NFR3.2).
- **Start and stop.** v2's start retries its database with a growing wait, from 1 second up to 30 seconds, without restarting (NFR7.4). launchd gives each job 30 seconds to exit. The host stops taking requests and finishes those under way for up to 10 seconds; the workers stop taking work and leave unfinished items to the built lease recovery.

## Q1. How long does a sign-in last for real accounts?

The rule for production admission (BR6.8) says real accounts follow AccountAccess's policy for real operation, and leaves its values open. The built code has only a test policy:

- a sign-in lasts 15 minutes in the account-controls code (1 hour in the earlier entry code) and is never extended while it is used;
- an administrator gives the second factor within 5 minutes of the password;
- the test policy refuses to run anywhere but the synthetic test environment, so production needs a policy of its own.

U6 ends an approved export that has not started when the session that approved it ends (U6 NFR Design Q4), so the session's length also bounds those approvals.

A. Members: 12 hours from sign-in. Administrators: 1 hour. Neither is extended while it is used.
   - A working day needs one sign-in, while administrator sessions, which reach 운영 and recovery requests, stay short.
   - An approved export then stays usable for up to 12 hours instead of 1. U6's rule is unchanged, because it follows the session's end; previews that were never approved keep their 7-day limit.
   - Every other value of the test policy carries over unchanged, and the account cap becomes 500 (NFR1.3).
B. One hour for everyone, never extended: everyone, you included, signs in again every hour.
C. A sign-in that renews while it is used, for up to 30 days. This is the smoothest, but AccountAccess has no renewal (U2 left it out on purpose), so it is new code in the account owner, and a stolen session cookie stays usable for much longer.

X. Other (please specify)

[Answer]: A

## Q2. How is sign-in protected from floods at the public address?

The built entry code admits 20 attempts a minute at sign-in, registration, email verification, password reset and reactivation, for everyone together, and checks one password at a time. That protects the machine. Behind the public address, though, one stranger sending 20 attempts a minute blocks every sign-in for as long as they keep going. Every request reaches v2 from the tunnel on 127.0.0.1, so the host can tell senders apart only by the address Cloudflare stamps on each request it forwards (`CF-Connecting-IP`).

A. Three limits, using that stamped address:
   - per client address: at most 20 attempts a minute;
   - per email address: after 5 failed attempts within 15 minutes, that address waits 15 minutes, with the same answer whether or not an account exists;
   - for everyone together: the shared bound rises from 20 to 120 attempts a minute, still checking one password at a time.

   The host reads the stamped address only on requests for the public origin. A test through the public address confirms that Cloudflare replaces a value the caller sends; if it ever did not, a caller could dodge the per-address limit, and the shared bound would still hold. A program on this Mac could send its own value by connecting to v2's local address, but only to dodge its own per-address limit. Addresses are kept only as keyed digests, for the length of their window, and are never logged.
B. Per email address and the shared bound only, with no client addresses. It is simpler, but one stranger can still fill the shared bound and block everyone's sign-in while the flood lasts.

X. Other (please specify)

[Answer]: A

## Q3. How should the shared model runtime keep its two models in memory?

Measured on this Mac on 2026-10-22, on the runtime v1 uses today:

- loading the search model (bge-m3, 1.1 GiB) takes 4.9 seconds, and an embedding then takes 0.04 seconds;
- loading the research model (qwen3:8b, 4.5 GiB in memory) takes 5.1 seconds, and a short answer then takes 0.3 seconds;
- by default the runtime unloads a model after 5 idle minutes. The first search after a quiet spell would then take about 5 seconds, against the 3-second search target (NFR8.4).

A. Keep the search model loaded at all times, and load the research model when a research or novelty job needs it:
   - v2 asks the runtime to keep the search model loaded on every call, and its search probe repeats the request every minute. v1's own calls, which leave a model at the 5-minute default, then cannot unload it;
   - the research model unloads after 5 idle minutes, so the first model job after a quiet spell waits about 5 seconds, in the background;
   - about 1.1 GiB stays in memory, and up to about 5.6 GiB while research runs.
B. Keep both loaded at all times. Research and novelty start without the 5-second wait, but about 5.6 GiB stays in memory permanently, which is tight while v1 still runs beside v2 in the 24 GiB (NFR8.7).
C. The runtime's default for both. Nothing stays loaded while idle, but the first search after 5 quiet minutes takes about 5 seconds.

X. Other (please specify)

[Answer]: A

## Q4. How is "in person" enforced for the operator's commands?

Every in-person step (each step of a production restore and of the switch, disposals on their event, the units' operator commands) runs only after you authenticate at this Mac (rules § Definitions, NFR3.2). The built operator tool records your account name but asks for nothing, so these steps will run through sudo. sudo on this Mac (1.9.17) remembers a password for 5 minutes in each terminal window by default. Within that time, any program started from the same window can run the same commands without asking.

A. Ask every time. DocSuri's in-person commands turn that memory off for themselves only (`timestamp_timeout=0`), so each one asks for your password. A production restore then asks at each of its steps, about 15 times. It works the same in Terminal on this Mac and over SSH, because sudo asks on this Mac either way, and your other sudo use keeps its usual 5 minutes.
B. Keep sudo's 5 minutes. A long procedure asks less often, but you would do operator work in a terminal window of its own, since anything started from that window within the 5 minutes could run the commands too.

X. Other (please specify)

[Answer]: A

## Follow-up questions (2026-10-22, while designing)

While I was writing the performance design, the built code turned out to hold two limits made for the small synthetic test corpus. The real corpus breaks both. Read from the code on 2026-10-22:

- **Search** (`backend/modules/discovery/guarded_repository.py` and `local_search.py`) reads every chunk of every eligible paper on each query and scores the vectors one by one in plain Python. It refuses when the whole corpus holds more than 256 chunks. Its text match also joins each paper's chunks and indexes them during the query, instead of using the stored, indexed `lexical` column.
- **Import** (`backend/modules/corpus/source_parser.py`, `repository.py` and `maintenance.py`) makes one chunk per paragraph, formula, caption, code block or list. It refuses a paper with more than 256 chunks, a block over 8 KB, a page with more than 20,000 HTML elements or nested more than 128 deep, or a parsed text over 2 MiB.
- The 599 migrated papers will hold tens of thousands of chunks: at about 100 a paper, around 60,000. So the first search after the migration would be refused, many real papers would be refused at import, and the 3-second search target (NFR8.4) needs an indexed search either way.
- Vectors are stored today as 1,024 double-precision numbers per chunk, 8 KB each: about 0.5 GB at 60,000 chunks.

The first dry run counts the real chunks and sizes. Whatever you choose, the complete verification also runs on a synthetic corpus of that size, so a limit like these shows up in testing, not in production.

## Q5. How should search reach the whole migrated corpus?

A. Search inside PostgreSQL with the pgvector extension:
   - pgvector is built from its pinned source release and checked against its published checksum, into the same root-owned PostgreSQL folder, the same way PostgreSQL itself is built (Q22). It is the only extension.
   - Chunk vectors move to a single-precision `vector(1024)` column with an HNSW index for cosine distance. The text match uses the stored `lexical` column and its existing index.
   - Each query asks PostgreSQL for the 200 closest chunks by meaning and the 200 best by text, so Python ranks a few hundred rows, as it does now.
   - Single precision halves the vectors' space, and the index takes about as much again, so the total stays about 0.5 GB at 60,000 chunks, inside the 8 GiB budget.
B. No extension: the host keeps every chunk vector in memory with numpy, a new dependency, and rebuilds that copy when the corpus changes. The text match uses the stored index. That is about 250 MB of the host's memory at 60,000 chunks, inside its 4 GiB (NFR8.7), and a few seconds' load at each start.
C. One vector per paper, from its title and abstract, as v1 does. 599 vectors stay fast to scan without an index, but search then matches a paper only by its title and abstract, never by a passage inside it.

X. Other (please specify)

[Answer]: A

## Q6. What size limits should a real paper have?

Each refused paper becomes a misfit in the migration's report for your decision (BR8.9), and its readers lose it from v2.

A. Production limits for real papers:
   - up to 2,000 chunks a paper;
   - a block over 8 KB is split at sentence boundaries into chunks of at most 8 KB, instead of refusing the paper;
   - up to 250,000 HTML elements, nested up to 256 deep;
   - a parsed text up to 16 MiB.

   A paper beyond these is still a misfit, with its reason in the report. The first dry run records the largest real values, and the limits can be revised then. The synthetic test environment keeps its own limits.
B. Keep the test limits. Every paper beyond them becomes a misfit for your decision in the dry run.

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- **Q1 — how long a sign-in lasts:** a member's sign-in lasts 12 hours and an administrator's 1 hour, and neither is extended while it is used.
  - An approved export that has not started stays usable until its session ends, now up to 12 hours; previews that were never approved keep their 7-day limit.
  - Every other value of the test policy carries over, and the account cap becomes 500.
- **Q2 — sign-in floods:** three limits.
  - At most 20 attempts a minute per client address. That is the address Cloudflare stamps, read only on requests for the public origin, kept only as a keyed digest for its window and never logged. A test through the public address confirms Cloudflare replaces a value the caller sends.
  - After 5 failed attempts within 15 minutes, an email address waits 15 minutes, with the same answer whether or not an account exists.
  - At most 120 attempts a minute for everyone together, still checking one password at a time.
- **Q3 — model memory:**
  - The search model stays loaded at all times: v2 asks for that on every call, and its search probe repeats it every minute.
  - The research model loads for research and novelty jobs and unloads after 5 idle minutes.
  - About 1.1 GiB stays in memory, and up to about 5.6 GiB while research runs.
- **Q4 — in person:** each of DocSuri's in-person commands asks for your password every time, with sudo's 5-minute memory turned off for those commands only.
  - That is about 15 prompts in a production restore, the same in Terminal on this Mac and over SSH.
  - Your other sudo use is unchanged.
- **Q5 — search over the whole corpus:** search runs inside PostgreSQL with the pgvector extension.
  - pgvector is built from its pinned source release, checked against its published checksum, into the root-owned PostgreSQL folder. It is the only extension.
  - Chunk vectors move to a single-precision `vector(1024)` column with an HNSW index for cosine distance, and the text match uses the stored, indexed `lexical` column.
  - Each query takes the 200 closest chunks by meaning and the 200 best by text from PostgreSQL, and Python ranks those few hundred rows.
  - The total stays about 0.5 GB at 60,000 chunks, inside the 8 GiB budget.
- **Q6 — real papers' size limits:** up to 2,000 chunks a paper; a block over 8 KB split at sentence boundaries into chunks of at most 8 KB; up to 250,000 HTML elements, nested up to 256 deep; a parsed text up to 16 MiB.
  - A paper beyond these is still a misfit, with its reason in the report.
  - The first dry run records the largest real values, and the limits can be revised then. The synthetic test environment keeps its own limits.
- **With Q5 and Q6:** the complete verification also runs on a synthetic corpus as large as the first dry run measures, so a limit like these shows up in testing.
- **Settled from the records:**
  - one process per job, with no scaling out;
  - unpooled database connections shared out as listed, leaving 11 of 50 spare;
  - at most two models loaded and one request at a time per model, one model job at a time, and lexical-only results when a search embedding takes over 2 seconds;
  - year-long caching for the build's content-hashed files only;
  - the built security headers, plus `form-action` and HSTS;
  - a fresh request identifier for every request;
  - JSON log lines. v2's own logs are moved aside; the rest are copied and then truncated, with any gap counted. Files are opened without blocking, and the link tests are added;
  - 5-minute latency summaries instead of per-request log lines;
  - one shared email count in the ledger, with a reservation before each send and an idempotency key per message;
  - the providers' time limits, with each capability state as that provider's circuit breaker;
  - separate lanes in the standing job;
  - the operator's database logins handed over through a pipe;
  - the start retry and the stop timing.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
