# U8 migration runbook: the consumer inventory, the dry run, the misfit decisions and the final run

Run at the Operation stages, with your decisions (Workflows 9–11, BR8.1–BR8.15, BR9.11,
BR9.14). Every command below is the operator tool's, with one JSON document on standard
input and one JSON result on standard output:

```bash
# On this Mac, in person (your login account; the tool calls `sudo -k` itself where a
# step needs root, and releases its PlatformControl login in person):
/Library/DocSuri/release/.venv/bin/python -I -m docsuri_ops.u8_platform <command> <word> --production
# In the composed realm, for rehearsal:
backend/.venv/bin/python -m docsuri_ops.u8_platform <command> <word> --environment-file /tmp/docsuri-u8-run/environment.json
```

**Your decisions take two calls.** A word that records a decision first answers
`{"state": "shown", "subject": ..., "digest": ...}`: the subject exactly as you are
shown it, and nothing is recorded. Read it, then run the same word again with
`"confirm": "<that digest>"`. The subject is rendered again from the current records;
only when it is unchanged is your decision recorded through `platform.decision.record`
and the word goes on. If the records changed in between, the answer is
`subject-changed` with the new subject and digest: read it and confirm again.

## 1. The consumer inventory, from your Cloudflare export (Workflow 11)

v1 keeps no per-request access records on this Mac, so v1's route use and request rate
come from a request-analytics export you take from Cloudflare's dashboard for
`docsuri.rvnnt.dev`, covering whatever the free plan shows. Nothing on the live site
changes.

1. **Take the export** from Cloudflare (Analytics, for `docsuri.rvnnt.dev`), as CSV or
   as the GraphQL Analytics API's JSON answer, over the longest window the free plan
   offers. Keep it in a file only you can read.
2. **Take the inventory:**

   ```bash
   echo '{"known": [{"clientRef": "integration:notion-import", "routesUsed": ["/api/export"]}]}' \
     | /Library/DocSuri/release/.venv/bin/python -I -m docsuri_ops.u8_platform \
         inventory take --cloudflare-export ~/cloudflare-docsuri.csv --production
   ```

   `known` lists integrations you know of that the export may not show (optional). The
   answer shows each client the export names with its user agent (shown to you once,
   here only), its route families and its request count, then the inventory's window,
   its request count, the busiest interval (`peakRequests` over `intervalSeconds`, at
   `peakAt`) and v1's peak rate, `peakRequestsPerSecond`. That peak rate is what each
   install's performance phase compares the test's pace against.
3. **Decide each consumer's disposition** (`moves-with-v2`, `retired-with-v1`,
   `informed` or `accepted-to-break`), in two calls each:

   ```bash
   echo '{"inventoryId": "<id>", "clientRef": "ua:<16 hex>", "disposition": "moves-with-v2"}' \
     | ... inventory record --production
   echo '{"inventoryId": "<id>", "clientRef": "ua:<16 hex>", "disposition": "moves-with-v2", "confirm": "<digest>"}' \
     | ... inventory record --production
   ```

   The inventory is complete once every consumer has one; a complete inventory is a
   switch precondition (BR9.2), and settlement follows its dispositions (BR9.8).

### The export shapes the reader accepts

Counts only. The reader reads a row's time, its request count and, where present, its
path and user agent; it never reads another field, so an address, a country, a ray
identifier or anything else in the file is dropped unread. A path is reduced to its
route family (no query, identifiers as `{id}`); a user agent is kept in the ledger only
as an opaque reference (`ua:` and 16 hex of its SHA-256). A file over 4 MiB, or of any
other shape, is refused with its reason (`export-too-large`, `export-shape-unknown`,
`export-carries-errors`, `export-empty`, `export-time-unreadable`,
`export-count-unreadable`, `export-interval-unknown`, `export-unreadable`).

- **JSON**: Cloudflare's GraphQL Analytics API answer for one zone and one group list:

  ```json
  {"data": {"viewer": {"zones": [{"httpRequests1hGroups": [
    {"dimensions": {"datetime": "2026-10-20T09:00:00Z", "clientRequestPath": "/api/search",
                    "userAgent": "Mozilla/5.0 ..."}, "sum": {"requests": 42}}
  ]}]}}, "errors": null}
  ```

  The group is `httpRequests1mGroups`, `httpRequests1hGroups`, `httpRequests1dGroups`
  or `httpRequestsAdaptiveGroups`. Each item's `dimensions` has one time key
  (`datetimeMinute`, `datetimeFiveMinutes`, `datetimeFifteenMinutes`, `datetimeHour`,
  `datetime` or `date`), optionally `clientRequestPath` and `userAgent`, and its count as
  `sum.requests` or `count`. A non-empty `errors` list is refused.
- **CSV**: a header row naming one time column (`datetime`, `timestamp`, `time`, `date`,
  `datetimeHour`, `datetimeMinute`, …, any case) and one count column (`requests`,
  `count` or `total requests`), and optionally a path column (`path`,
  `clientRequestPath`, `request path`) and a user-agent column (`userAgent`,
  `user agent`, `user-agent`).

The interval is the group's or the time key's (one minute, five, fifteen, an hour, a
day); with a plain time column it is the smallest gap between two distinct times. The
peak rate is the busiest interval's requests over that interval (the earliest, on a
tie). The counts over time and by route family are kept beside the inventory in an
owner-only evidence file.

## 2. The dry run (Workflow 9)

### Before the first dry run: v1's stores move to their encrypted volume (NFR3.6, D8)

- Before the first dry run, v1's object store, its own database dumps and the
  2026-10-10 archive move from `/Volumes/SSD01` into a new encrypted APFS volume on the
  same drive (for example `DocSuri_v1`), with ownership enabled and its folders
  owner-only for your login account, and v1's object store is served from there
  (security-design § 6.6, lines 287-289).
- You create the volume in person, in Disk Utility as "APFS (Encrypted)" or with
  `diskutil apfs addVolume <container> APFS DocSuri_v1 -passprompt`, which asks for the
  passphrase; a passphrase is never written into a command's arguments.
- Its passphrase is yours alone, kept in your login keychain and your password manager.
  It is never put in the System keychain, in a file under `/Library/DocSuri/`, in a
  launch job's definition, in an environment file or in the installation log, and no
  DocSuri program asks for it, reads it or generates it. The installer's only volume
  passphrase is the backup volume's, `DocSuri_Backup` (the installation runbook).
- The move itself is NFR3.6's, made in person and owed to Deployment Execution with its
  two rows.

### Running the dry run

Preconditions the tool checks at the start: no switch, abort or rollback running, the
runtime arrangement installed (the installation runbook), and the latest isolation
evidence passed within its 15-minute freshness. The isolation evidence is read again at
every phase boundary and during long phases; a lapse interrupts the run.

1. **Your go-ahead, then the run:**

   ```bash
   echo '{}' | ... migration dry-run --production
   echo '{"confirm": "<digest>"}' | ... migration dry-run --production
   ```

   The subject shows the source (`v1`), the tool's commit and the digest of the
   decisions current now. Once confirmed, the run goes through preparing (a new
   rehearsal database, recorded as a retained copy), copying (the copy of v1 onto the
   backup volume through the backup agent), importing (the import database, the disk
   guard, the owners' imports) and verifying (the parity report and the idempotency
   pass, which must import and update nothing), and answers `reported`,
   `interrupted` with its phase and reason, or `failed`.
2. **An interrupted run** resumes exactly its recorded phase, against a re-verified
   snapshot:

   ```bash
   echo '{"runId": "<run>"}' | ... migration resume --production
   ```

   Or abandon it: it fails, and its copies are disposed through their records.

   ```bash
   echo '{"runId": "<run>"}' | ... migration abandon --production
   ```
3. **Your decision on the report** (two calls each). Read the parity report the subject
   names (`reportRef` in the evidence folder): per kind, the source count, imported,
   unchanged, updated, skipped by reason and excluded by decision, with no password,
   hash, token, email or content.

   ```bash
   echo '{"runId": "<run>"}' | ... migration accept --production
   echo '{"runId": "<run>", "confirm": "<digest>"}' | ... migration accept --production
   ```

   `reject` takes the same input. An accepted dry run becomes the cutover's accepted
   dry run, its rehearsal database the soak's database; a rejected one's copies are
   disposed. On acceptance the profile is set to the run's rehearsal database and v2's
   three roles restart on it, with the readiness wait; only then is the rehearsal
   database it replaces removed, with its rehearsal backup sets disposed after it. After
   a rollback (the record is `rolled-back`), the profile is set but v2 stays stopped
   until the soak starts (your decision of 2026-10-25, "Follow the design").

   A dry run's start is refused with `rehearsal-database-limit`, before anything is
   written, while two rehearsal databases are open; the next acceptance or the disposal
   pass frees one.

### The production migration platform, and its first real read

`migration … --production` and the switch's final run take the production migration
platform (`docsuri_ops.migration.production`). It reads v1 **read-only**, at the
addresses the operator's environment file names and at no other:

- **The environment file** is `/Library/DocSuri/control/effects/operator/driver.json`,
  written by the installer from `installation.json`'s `v1Sources` (addresses and paths,
  never a secret):

  ```json
  "v1Sources": {
    "database": {"host": "127.0.0.1", "port": 5432, "database": "docsuri"},
    "index": {"url": "http://127.0.0.1:9200", "name": "<v1's index name>"},
    "objects": {"url": "http://127.0.0.1:9000", "bucket": "<v1's bucket>",
                "credentials": "/Users/<you>/.docsuri-v1-objects.json"}
  }
  ```

  Every address must be plain `http` on `127.0.0.1` with its port; v2's database port
  (15432) is refused as v1's. The credentials file is yours, 0600, never a link:
  `{"accessKey": "…", "secretKey": "…"}` for v1's object store (v1's own `.env` holds
  them; copy them there by hand). Anything else refuses with `POLICY_UNRESOLVED` and
  the reason, before anything is read.
- **v1's database** is dumped by the backup agent's in-person `snapshot`, through its
  read-only login (`pg_read_all_data`). The word carries the named address: the agent
  refuses (`v1-source-not-named`) before it connects when its own v1 login reaches any
  other, and the dump's receipt names where it read, which is checked again.
- **v1's search index** is read through the scroll API only: any other method or path,
  or any other origin, is refused before it is sent (`v1-write-refused`,
  `v1-address-not-named`).
- **v1's object store** is read with `GET` and `HEAD` only, the named bucket only.
- **v2's side**: the rehearsal and import databases are created by
  `docsuri-production-tool create-disposable` as the disposable-databases role, which
  owns them (a rehearsal database is `docsuri_v2_template` copied whole; the release's
  `migrate` keeps the template on the chain); the dump is restored into the import
  database by `restore-import`; the owners' imports run as the service account through
  `docsuri-migration-import`; a final run's production database is the template copied
  whole by `prepare-production`. Each asks for your password (`sudo -k`).

**The first real read of v1 is the first dry run, with you present, at the Operation
stages.** Before it:

1. Check `v1Sources` in the operator's `driver.json` against v1's own configuration (its
   `.env`: database port and name, the search index's address and index, the object
   store's address and bucket); correct `installation.json` and run the installer again
   if any differs.
2. Write the object store's credentials file, and check its mode is `-rw-------`.
3. Take the isolation check (the installation runbook), then start the dry run above
   and stay with it to its report. If it stops `interrupted`, `resume` it; if it
   `failed` with an address reason, correct the environment file, not v1.
4. Read the parity report before you accept it. v1's stores are only read: nothing in v1
   changes, and v1 keeps serving throughout.

The same words run in full on the composed realm, where
`integration/test_production_migration_platform.py` runs this platform against the
synthetic v1's addresses: its dry run reports the same parity as the realm's platform,
v1's three stores' checksums are equal before and after, an address the file does not
name is refused, and the final run takes it.

## 3. The misfit decisions (Workflow 10)

1. **List what the latest run met:**

   ```bash
   echo '{"runId": "<run>"}' | ... migration decide --production
   ```

   Each kind and reason with its count, its source identifiers (identifiers only), the
   proposed decision and mapping rule, and the current decision.
2. **Decide each one** (`map` with its stated rule, `archive-only` or `drop`), in two
   calls:

   ```bash
   echo '{"kind": "account", "reasonKey": "locked-in-v1", "decision": "map"}' | ... migration decide --production
   echo '{"kind": "account", "reasonKey": "locked-in-v1", "decision": "map", "confirm": "<digest>"}' | ... migration decide --production
   ```

Decisions apply from the next dry run onward. A decision changed after the latest
accepted dry run started needs a new dry run, accepted, before the switch can start.
While a final run's freeze holds, a decision is refused (`decisions-frozen`). Kinds
outside Q13 default to archive-only.

## 4. The final run

The final run is reachable only inside the switch (`cutover start`, the cutover
runbook): it needs the cutover in `switching`, every required kind and reason decided,
and an accepted dry run under the current decisions. It freezes the decisions, takes the
final snapshot, imports into the production database recreated empty, and its report
is decided inside the switch. Anything it meets for the first time takes archive-only
and needs your explicit approval in its report.
