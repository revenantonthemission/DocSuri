# NFR Design Questions — U6 approved export

Date: 2026-10-20 (Asia/Seoul)
Unit: u6-approved-export (embedded library). Inputs:

- the confirmed [security requirements](../nfr-requirements/security-requirements.md) and [tech stack decisions](../nfr-requirements/tech-stack-decisions.md);
- the open points R-12 to R-15 from the [NFR requirements review](../nfr-requirements/reviews/review-02.md);
- the [functional spec](../functional-design/functional-spec.md);
- the built code: the account-controls keyring (`backend/modules/accounts/control_keys.py`), the local environment profile (`backend/local_profile.py`), the bounded transactions (`backend/transactions.py`) and the sign-in session policy (`backend/modules/accounts/control_policy.py`).

This stage turns the approved requirements into a concrete design: how the Notion token is kept and used, and which parts make up the Unit. Each question offers the design I recommend as A. Answer with a letter, or in your own words under X.

## Settled from the records (no question)

These follow from decisions already on record or from the built code. If one should change, say so under X of the closest question.

- **Library scope.** U6 is a library. This stage produces the security design and the map of its parts. Speed, scaling, availability and monitoring targets stay with the service that hosts it (U8). The design lists the counts U6 offers U8 to watch, without personal data.
- **No Notion call inside a database transaction.** The built transactions are capped at a few seconds, and a Notion write may take up to 90 seconds. So each write runs in three steps:
  - record the attempt and commit;
  - call Notion outside any transaction;
  - record the outcome in a new transaction.

  This is how the requirement "recorded before any write" is met.
- **No error reporter is active today.** The frontend lists `@sentry/nextjs` as a dependency but never starts it, and the backend has no error reporter. U6 adds none. Any reporter added later, in the browser or on the server, must follow the error-reduction requirement (NFR3.6) and must never capture the token field.
- **One mislabelled row (R-15).** The "could-not-check wait" value serves the definite-answers requirement (NFR4.9) and rule BR3.3, not the write deadline (NFR4.4). This design's traceability records it correctly.
- **Stored token format.** It follows the envelope that U2's protected values already use (format tag, key version, nonce, encrypted value), with U6's own tag and the account, connection and revision binding of the sealing requirement (NFR3.1).

## Q1. How is the built keyring's code shared with U6?

Earlier you chose one shared keyring helper taken from the built account-controls keyring (tech stack decisions, the token-sealing row). The review found that the built keyring does less than the token-key requirements (NFR3.2, NFR3.3) ask:

- it is tied to U2's own folder;
- it never creates a first key by itself; an operator command does;
- its rotation only adds a key, and it refuses at three keys;
- a second process that tries to lock fails at once instead of waiting;
- it replaces the key file rather than linking a new one into place.

Where U6's extra behaviour lives decides how much of U2's reviewed code changes.

A. Two layers:
   - **Shared helper.** It holds only what the built keyring already does: the guarded private-file read, the exclusive lock, writing to a temporary file and then publishing it with syncing, the versioned key record (at most three versions) and the initialized marker. It is parameterised by folder, file names, version prefix and environment id.
   - **U2's keyring** becomes a thin setting of that helper with exactly today's behaviour. U2's existing keyring tests must pass unchanged.
   - **U6's own layer, on top, with its own tests.** It adds:
     - creating the first key at first start, linked into place so two processes cannot both create one;
     - a lock that waits a few seconds instead of failing;
     - re-sealing tokens on rotation, with a count per key version;
     - retiring the oldest version only when its count is zero.
B. Put every behaviour, including U6's new ones, into the shared helper behind options, so U2 could adopt them later. There is more shared code to review now, and U2 is still unchanged by default.
C. Leave U2's code untouched and write U6's keyring separately. This was rejected earlier as duplicate custody code.

X. Other (please specify)

[Answer]: A

## Q2. Which folder holds U6's key file?

Earlier you chose a key file in the application's private data folder, never in the repository or the database (NFR requirements Q1). Here is how that applies to the built code:

- Each local environment keeps its private files in its own owner-only folder, `/tmp/docsuri-<unit>-run`. The folder is checked on every start: you own it, it is not a link, and nobody else can open it.
- That folder is kept for at most 24 hours, and the environment's database lives and ends with it.
- The hosted service (U8) will have its own data folder.

A. The setup that assembles each environment gives U6 its key folder:
   - in each local environment, an owner-only subfolder of that environment's own folder (`/tmp/docsuri-u6-run/export-keys/`), checked the same way;
   - in the hosted service, a private data folder outside `/tmp`, chosen at U8.

   The key lives exactly as long as the tokens it seals.
B. One fixed folder outside `/tmp` for every environment, with one subfolder per environment (for example under `~/Library/Application Support/DocSuri/`). Keys then outlive the tokens they sealed and need their own cleanup.
C. A folder path the operator supplies at start-up.

X. Other (please specify)

[Answer]: A

## Q3. How is a lost key told apart from a first start?

The token-key requirement (NFR3.3) relies on the "initialized" marker. That marker sits in the same folder as the key. If the whole folder is deleted, the next start looks like a first start and silently creates a new key. The stored tokens then fail to open: nothing is exposed, but the loss stays hidden until someone uses a connection.

A. Use the database as a second witness. A missing key file counts as a first start only when the marker is absent and U6's store holds no sealed token. Otherwise it is a loss:
   - every connection becomes unavailable;
   - the operator command is needed to create a fresh key.
B. Keep the marker alone, as NFR3.3 is written now.

X. Other (please specify)

[Answer]: A

## Q4. How long does an approval stay usable before its export starts?

Two records disagree:

- The retention requirement (NFR1.5) says an approval that never started keeps its rendered copy for at most 7 days and then cannot be continued.
- The approval rule (BR3.5) says approvals have no time limit.

The 7-day end also has no state or reason that the history could show. Two facts from the built code bear on this:

- Sign-in sessions last at most one hour (15 minutes in the account-controls policy) and are never extended.
- An approval can be continued only under the session that made it.

A. Drop the 7-day clause for approvals:
   - BR3.5 stays as it is: no time-based expiry, and the contract's "expired" state is never used.
   - The approving session's end, at most one hour later, is the bound. On its next pass, housekeeping marks the approval invalidated (authority-revoked) and trims its copy in the same step.
   - The 7-day limit stays for previews that were never approved.
B. Keep 7 days as an extra time limit. This adds a new end reason (for example approval-aged-out) to the contract amendments and overrides BR3.5 for approvals not yet started.

X. Other (please specify)

[Answer]: A

## Q5. How long may each kind of Notion read take?

The read rule (NFR4.6) retries a read only "within the operation's own time budget", but no budget is set. Each budget below covers the wait for the pace slot, the retries and the requests themselves.

| Read | Budget | When it runs out |
|---|---|---|
| Checking a token (connect, replace) | 30 s | "Notion에 연결할 수 없습니다"; nothing stored |
| Listing shared pages | 30 s | the list is shown as partial, with a refresh action |
| Reading one page (destination check, pre-write check) | 30 s | could-not-check |
| Reading back a page after a "saved but busy" answer | 60 s | the export becomes unknown |
| One reconciliation scan | 5 min | listing-incomplete; the export stays unknown |

A. Use these values.
B. Change some of them (say which under X).

X. Other (please specify)

[Answer]: A

## Q6. Where is each connection's request pace kept?

The read rule (NFR4.6) keeps all calls of one connection under 2 requests per second on average. Calls for one connection come from two places:

- the web process: checking, listing and previews;
- the worker: writes and scans.

Each operation also uses its own short-lived client (NFR3.5), so the pace cannot live in a client.

A. In the database:
   - Each connection has a pace record.
   - Before each Notion request, the caller reserves the next free slot in a tiny transaction that uses the database clock.
   - The caller then waits for its slot outside the transaction.

   Both processes, and any number of workers, share the pace exactly.
B. In memory in each process, splitting the allowance, for example 1 request per second for the web process and 1 for the worker. This is simpler, but the split must be redone whenever the number of processes changes.

X. Other (please specify)

[Answer]: A

## Q7. What should the connect screen ask you to allow when you create the Notion integration?

When you create an integration, Notion lets you choose what it may do. DocSuri cannot check those choices in advance: it learns about a missing one only when a write is refused.

A. Ask for the least that is needed: read content and insert content only. No update content, no comment access, no user information.
   - A leaked token could then read the pages shared with it and add new content, but not edit, move or delete what is already there. Checked against Notion's capability documentation on 2026-10-20: creating a page needs only insert content, reading needs read content, and DocSuri's token check (Notion's "retrieve your token's bot user") needs no user information.
   - The connect help text names these settings.
B. Give no capability guidance. Show the refusal hints only when a write is refused, as already designed.

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- **Q1:** Two layers:
  - a shared custody helper keeps only what the built keyring already does: the guarded private-file read, the exclusive lock, publishing through a temporary file with syncing, at most three key versions and the initialized marker. It is parameterised by folder, file names, version prefix and environment id;
  - U2's keyring becomes a thin setting of it with exactly today's behaviour, shown by U2's existing keyring tests passing unchanged;
  - U6's own layer adds the first key at first start (linked into place), a lock that waits, re-sealing on rotation with a count per key version, and retiring a version only at zero, each with its own tests.
- **Q2:** The setup that assembles each environment gives U6 its key folder:
  - in each local environment, `/tmp/docsuri-u6-run/export-keys/`, owner-only and checked like the environment's own folder;
  - in the hosted service, a private data folder outside `/tmp`, chosen at U8.

  The key lives exactly as long as the tokens it seals.
- **Q3:** The database is a second witness. A missing key file is a first start only when there is no marker and U6's store holds no sealed token. Otherwise it is a loss: every connection becomes unavailable until the operator creates a fresh key.
- **Q4:** The 7-day clause for approvals is dropped, and BR3.5 stands: no time-based expiry, and the contract's "expired" state is never used.
  - The approving session's end, at most one hour later, bounds the approval. Housekeeping then invalidates it (authority-revoked) and trims its copy in the same step.
  - Previews that were never approved keep the 7-day limit.
- **Q5:** Read time budgets, each covering the pace wait, the retries and the requests:
  - token check 30 s;
  - listing shared pages 30 s;
  - reading one page 30 s;
  - read-back after a "saved but busy" answer 60 s;
  - one reconciliation scan 5 min.

  Each spent budget has the stated outcome.
- **Q6:** The pace lives in the database. Each connection has a pace record. Before each Notion request, the caller reserves the next slot in a tiny transaction on the database clock, then waits outside it.
- **Q7:** The connect help asks for read content and insert content only: no update content, no comment access, no user information.
- **Settled from the records:**
  - Notion calls never run inside a database transaction.
  - No error reporter is active, and any future one must never capture the token.
  - The could-not-check wait serves NFR4.9 and BR3.3.
  - The stored token uses U2's envelope shape with U6's own tag and binding.

- Looks correct
- Request changes

[Answer]: Looks correct
