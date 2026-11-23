# Security Requirements — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-requirements-questions.md](nfr-requirements-questions.md) (Q1–Q25);
- inception [requirements NFR1–NFR6, FR3 and FR4](../../../inception/requirements-analysis/requirements.md);
- this Unit's [functional spec](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md), which own the behaviour these requirements constrain;
- the [technology stack](../../../../../codekb/DocSuri/technology-stack.md);
- facts read on this Mac on 2026-10-22: disk and volume state, accounts, launch jobs, listening ports, Time Machine settings, and v1's data sizes (nfr-requirements-questions.md § "Follow-up questions (2026-10-22)" and Q25).

U8 hosts every unit, so this file carries the security, consent, idempotency, accessibility and $0 requirements of the whole application. U5's and U6's own requirements still apply inside it unchanged. Each requirement cites the rules it constrains; where it fixes a value the rules left as "policy", the value comes from the answer cited.

## Owner isolation and authorization (NFR1)

- **NFR1.1** — Every route, event stream and asset enforces the caller's current authority on the server. Navigation visibility is never the authorization check, and the browser keeps no access list of its own (BR5.1). Another owner's identifier answers exactly like a missing one. A signed-out caller reads only the minimal public capability projection: state and reason key, with no age, limitation, count or producer (BR5.9). An owner change or session end clears private rendering state (BR5.5).
- **NFR1.2** — The operator surface (운영, incidents and recovery requests) answers only administrators with completed, current MFA. Everyone else gets the same safe denial as any protected resource, with no counts or identifiers (BR3.8). An administrator's MFA is checked again when the operator starts the request (BR4.2).
- **NFR1.3** — Admission:
  - While admission is maintainer-only, only administrator accounts can sign in, and every page except `/privacy` and `/terms` shows the maintenance notice (BR6.4).
  - When admission opens, only migrated accounts sign in. Registration stays closed until AccountAccess's public-activation evidence is recorded and you open it as its own decision. After that, the service accepts at most 500 accounts (BR6.8). [Q11]
- **NFR1.4** — Your decisions are recorded only through PlatformControl's decision operation, bound to you, the step, the subject reference and the digest of exactly what you were shown. The web application and any administrator can read decisions but never create one (BR9.14).
- **NFR1.5** — Separation of OS authority [Q18, Q19, Q23]:
  - The service account `_docsuri_v2` holds no operator authority. It can run no operator-tool, backup-agent or service-control command, and is granted only PlatformControl's bounded evidence reader (BR4.2, BR6.1).
  - The scheduler account `_docsuri_v2_sched` alone holds the unattended grants: the backup agent's five unattended commands, the ledger component's fixed command, the standing operations and the read-only isolation check (BR4.2, BR6.12).
  - The operator account (your login account) reaches another account only after interactive authentication at this Mac (rules § Definitions).
  - The database, models and tunnel accounts (`_docsuri_v2_db`, `_docsuri_models`, `_docsuri_tunnel`) each run one system launch job and nothing else (BR6.11).
- **NFR1.6** — Every fixed command accepts only a name from its closed set (a label, an origin or a command word), checks it again itself, and runs with sudo's cleaned environment. No caller-supplied variable, path or library reaches it. The rules live in `/etc/sudoers.d/docsuri-v2`, owned by root, mode 0440 (BR6.11 (0)). [Q23]
- **NFR1.7** — The v2 host listens only on `127.0.0.1:18200` and the maintenance server only on `127.0.0.1:18201`. The host accepts a request only for its public origin, `https://docsuri.rvnnt.dev` (through the tunnel), or its loopback origin, with origin and CSRF checks bound to the public origin (BR6.4). [Q23]

## Consent (NFR2)

- **NFR2.1** — A migrated account gives v2's own consents at its first sign-in, before any personal feature runs. Consent is never carried over from v1 or inferred (BR8.1, BR8.6).
- **NFR2.2** — While the profile is in rehearsal mode, which covers every dry run and the soak, email goes only to your verified address and Notion only through your own connection. Any other recipient is held as not permitted and recorded (BR7.5).
- **NFR2.3** — U5's single-test bound lifts only after Resend becomes active in live mode, and digests then go only to subscribers who consented under U5's rules (BR7.6). Withdrawal and consent revocation stop digests and exports, including work already in flight, with no effect after the revocation (BR2.4). The complete verification proves the race (BR10.3).

## Credentials, keys and data at rest (NFR3)

- **NFR3.1** — Key material: the export token keyring, the account control keyring with its recovery snapshots, the account verifier key and the search cursor key live only in the profile's key folders. They are never in the repository, `/tmp`, a backup set or a Time Machine backup (BR4.8, BR6.2, BR6.11 (8)). A missing key is replaced only through its owner's operator command, with that owner's stated consequence. A key is never regenerated silently (BR6.2). U6's sealing and one-client-per-use requirements apply unchanged. [Q25]
- **NFR3.2** — Secrets:
  - The service's secrets come from the profile's private environment, never from the repository (BR6.7).
  - A missing service secret refuses the start, naming it. A missing provider secret leaves only that provider unconfigured and unavailable (BR6.7, BR7.2).
  - v2's database passwords, the Resend key and the Google and ORCID client secrets are issued for production. Each is held only by the account that uses it, never copied from the development keys in your login account (BR6.11 (7)).
  - Credentials the operator tool uses, its logins in v2's PostgreSQL instance among them, are not held by your login account at all.
    - They are kept root-only in the System keychain.
    - The operator tool gets them only through its fixed command, after you authenticate at this Mac with your password; no password-less grant releases them.
    - They are never stored in your login keychain, in an environment file or in any file your login account can read. So a program you run cannot use them unattended (rules § Definitions, Operator account).
- **NFR3.3** — v2's PostgreSQL instance [Q19, Q22, Q23]:
  - It listens only on `127.0.0.1:15432` and accepts only SCRAM logins over TCP (`password_encryption = scram-sha-256`, and `scram-sha-256` for every host line in `pg_hba.conf`).
  - Its superuser is reachable only by the database account, through the private socket folder `/Library/DocSuri/postgres/socket/`. The superuser role has no password, and `pg_hba.conf` rejects it over TCP before its general line, so a TCP login as the superuser always fails.
  - Every client (v2, the backup agent, the scheduler's login and the operator tool) connects with `require_auth=scram-sha-256` through libpq 16 or later. v2's start fails unless its own connection authenticated through SCRAM (BR6.11 (1)).
  - Each owner keeps its own schema and owner and login roles (BR1.4). Scratch, import and rehearsal databases are owned by the disposable-databases role, and the scheduler's login is a member of that role alone, so it cannot drop the production database (rules § Definitions, BR9.17).
- **NFR3.4** — The tunnel's credentials sit in `/Library/DocSuri/tunnel/credentials/`, readable only by the tunnel account. Its three registered configurations are root-owned. After the installation, no Cloudflare account certificate is valid and the old tunnel is deleted. A later tunnel change issues a fresh certificate in person and revokes it the same way (BR6.11 (3), (7)). The configurations keep the `ssh.rvnnt.dev` route unchanged. [Q19]
- **NFR3.5** — The backup volume `DocSuri_Backup` [Q3, Q14, Q15, Q17]:
  - It is encrypted APFS with ownership enforced, owned by the backup account `_docsuri_r1t_backup`.
  - Its passphrase is in the System keychain and in your password manager, and no longer in the login keychain (BR6.11 (5)).
  - Only the backup agent writes, reads back or deletes in U8's folder `docsuri-v2`, on its own catalogue's terms (BR4.3, BR9.17).
  - The status check fails closed if the earlier tool's cleanup marker sits in that folder or any folder above it (BR6.6).
- **NFR3.6** — v1's stores: before the first dry run, v1's object store, its own database dumps and the 2026-10-10 archive move from the unencrypted, ownership-ignoring `/Volumes/SSD01` into a new encrypted APFS volume on the same drive (for example `DocSuri_v1`).
  - That volume enforces ownership, its folders are owner-only for your login account, which v1 runs as, and its passphrase is in your login keychain and your password manager.
  - v1's object store is served from there.
  - Its locations, the iCloud copies of v1's backups and the Time Machine backups that hold v1's data are recorded as v1's stores, with the disposal dates of Q5 (BR9.12). [Q24, Q25]
- **NFR3.7** — Time Machine [Q25]:
  - As root, at installation, Time Machine is told to exclude two fixed absolute paths:
    - `/Library/DocSuri/` as a whole. That folder holds every account's private folder (the profile root, the PostgreSQL folder with its logs, the models' state, the tunnel's credentials, and the scheduler's and the backup agent's credentials and logs), beside programs and configuration the installation reproduces.
    - OrbStack's data folder, `/Users/revenantonthemission/Library/Group Containers/HUAQ24HBR6.dev.orbstack/`.
  - Excluding the whole folder means no private file can be placed outside the exclusion by mistake. This goes beyond Q25's list of four folders, and it loses nothing Time Machine should keep: the release, the runtimes and the models are reproduced from their sources.
  - The installation log records both exclusions, and the runtime isolation check confirms them every renewal interval as its backups item (`isolation-backups`, BR6.12).
  - Local snapshots can keep a deleted file on the internal disk for up to 24 hours. So every date erasure evidence shows for a copy on the internal disk (a rehearsal, import or scratch database) is its removal or backstop date plus 24 hours (BR2.5, BR6.11 (8)).
- **NFR3.8** — Runtime isolation (BR6.11, BR6.12) [Q19, Q21, Q22, Q23]:
  - Every program the non-login accounts or a fixed command run, and every file they read to decide what they do, comes from a root-owned folder under `/Library/DocSuri/` or `/etc` that no other account can write, never from a home folder or Homebrew's prefix.
  - The packet filter, loaded at boot by `org.docsuri.v2.pf` from `/etc/pf.anchors/org.docsuri.v2`, lets a connection reach `127.0.0.1:18200` or `:18201` only while the service account's socket listens there. The same holds for `:11434` and the models account, and `:15432` and the database account.
  - The isolation check runs every 5 minutes and completes within 60 seconds. It is stale after 15 minutes and opens an incident after 15 minutes failed, unknown or stale. Its results are kept 14 days in `/Library/DocSuri/evidence/isolation/`, readable by every account and written only by root (NFR9.9). A planned stop is valid for 14 days (NFR7.19).
- **NFR3.9** — Logging (BR3.9):
  - Production logs carry identifiers, states, timestamps and fixed reason keys at informational level. Transport libraries stay at WARNING or above, the Notion SDK keeps U6's null logger, and HTTP access logs stay off.
  - No credential, token, password or password hash, email address, private text, request body or private query is ever logged.
  - This holds for every log on this Mac, not only v2's own:
    - PostgreSQL's server log runs with `log_min_messages = log`, which keeps its own operational messages but drops every error a client causes, since such an error can quote the rejected input. It also runs with `log_error_verbosity = terse`, `log_min_error_statement = panic`, `log_statement = 'none'`, `log_min_duration_statement = -1` and `log_parameter_max_length_on_error = 0`. So it records no statement, parameter, row value or rejected input; v2 logs its own database errors with fixed reason keys.
    - The model runtime keeps its default level, which records request lines and never prompt text.
    - The tunnel logs at `warn`; v2's addresses never carry private input (BR5.5).
    - Every log lives under `/Library/DocSuri/`, which Time Machine excludes (NFR3.7).
  - The installation log records that a step handling a secret ran, never the secret (functional-spec.md, Workflow 20).
- **NFR3.10** — Nothing about the service's errors leaves the machine in this release:
  - No external error reporter runs. One added later must follow U6's rules: no local variables, no default personal data, no request bodies, the export adapter's frames scrubbed and browser input masked (BR3.10).
  - healthchecks.io receives only check names and pass or fail (NFR9.6). [Q9]
- **NFR3.11** — The software supply chain [Q22]:
  - Each runtime is pinned and taken from its publisher: PostgreSQL 16.14 built from the PostgreSQL project's source release, Ollama 0.40.7 and cloudflared 2026.10.3 from their official GitHub release archives, and CPython 3.13.7 installed by uv.
  - Each download is checked against its publisher's published SHA-256 before installation. Every Python dependency is installed from the lockfile (`uv sync --frozen`) and checked against its lock hash.
  - `otool -L` confirms that each program loads only its own folder's libraries and system libraries (BR6.5, BR6.11).
  - An upgrade is an in-person administrator step. A model change, or a new digest for a pinned model, is a new release (BR6.11 (2)).

## Retention and erasure (derived from FR4.1, numbered with NFR3)

- **NFR3.12** — Every copy of personal data outside the live service is recorded as a retained copy before anything is written to it, with its disposal point and backstop date (BR9.12). The values are Q5's, plus Q21's:

| Copy | Disposed | Backstop |
|---|---|---|
| A dry run's copy of v1 | when its run ends | 14 days after it was taken |
| An import database | when its run ends | 14 days after it was created |
| A rehearsal database, with its backup sets | when a newer dry run is accepted, when its run fails or is rejected, or right after admission opens | 60 days after it was created |
| A scratch restore a failed check left behind | when the operator removes it | 1 day |
| The v1 final snapshot | 30 days after settlement; for an aborted attempt, 30 days after the abort | 120 days |
| v1's stores (including their Time Machine and iCloud copies) | 90 days after admission opens | 180 days |
| A rolled-back v2 database | 30 days after the rollback | 90 days |
| A staging file on the backup volume | when its write ends | 1 day |

- **NFR3.13** — The backup agent refuses a decided disposal date for the v1 final snapshot or a rolled-back database's copy that falls earlier than 14 days after the copy was written. It accepts a date only with its decision's receipt and subject digest (BR4.3). A caller can only extend a disposal time, and the retention floor always keeps the newest passed set and the newest verified ledger copy (BR9.17). [Q21]
- **NFR3.14** — Erasure:
  - An erasure reports complete only when every scope has evidence (BR2.2), including a live restore verification whose register head covers the owner's tombstone. That verification starts within 24 hours of the tombstone, at the next 05:00 run, and completes within 60 minutes of its start (NFR7.8, NFR8.9, BR2.6) [Q2].
  - The backups evidence names every undisposed set and copy that may hold the owner's data, with the latest date by which each is gone (BR2.5).
  - Archive-only data can be retrieved for a returning user only until v1's stores are disposed of [Q5].

## Integrity, idempotency and reconciliation (NFR4)

- **NFR4.1** — Recovery requests:
  - Each deliberate submission has its own identity, and only its retries recover it (BR4.9).
  - Conflicting production-affecting operations never overlap, and a waiting request holds nothing and expires after 24 hours (BR4.4) [Q2].
  - An unknown outcome is reconciled from PlatformControl's receipt and evidence before any other production-affecting operation, and is never re-run blindly (BR4.4).
- **NFR4.2** — Every switch, abort, rollback, restore, disposal and decision effect is a bound PlatformControl operation that binds actor, target and input before the effect and leaves a receipt. No generic command, path or shell execution is admitted (BR9.10).
- **NFR4.3** — The operations ledger and the tombstone register (BR4.6, BR6.10):
  - They are append-only and digest-chained, synced to disk before their head is replaced atomically.
  - On open, entries a crash left beyond the head are adopted or discarded as the rules state, and any other break stops dependent writes and opens an incident.
  - A ledger copy reaches the backup volume with every set and at least daily.
- **NFR4.4** — Migration:
  - Target identities are deterministic, and a second pass over the same snapshot imports and updates nothing (BR8.3).
  - Every run's parity report reconciles counts and checksums per kind and holds no password, hash, token, email address or content (BR8.10).
  - v1's vectors are never reused: every migrated paper is embedded again with the pinned model, so BR8.8's reuse check is never offered and no sample size or tolerance applies. [Q12]
- **NFR4.5** — Outward providers:
  - Each outward provider's first live effect is held until your decision approves the digest of its recorded preview (BR7.3).
  - Real Google and ORCID sign-in are verified by you before admission opens (BR7.8).
  - An abort or a rollback clears these approvals.
- **NFR4.6** — Digest and export effects keep U5's and U6's idempotency and reconciliation unchanged in the composed application (NFR4 of those Units). Their unit bounds lift only in live mode after the first approval (BR7.6).

## Accessibility (NFR5)

- **NFR5.1** — Every screen U8 adds or changes uses Korean labels and meets WCAG 2.2 AA (BR5.8): navigation in every state, 작업, 운영, the legal pages, the sign-in and moved-version notices and the maintenance notice. The complete verification records keyboard, focus, screen-reader announcement, 320 CSS px reflow and contrast evidence for every screen of the complete application, and a failed check fails the run (BR10.6).

| Criterion | What is checked |
|---|---|
| 1.4.3 Contrast (minimum) | text at least 4.5:1, large text at least 3:1 |
| 1.4.10 Reflow | no two-dimensional scrolling at 320 CSS px |
| 2.1.1 Keyboard | every action works from the keyboard |
| 2.4.3 Focus order and 2.4.7 Focus visible | focus follows the flow and is always visible |
| 2.5.8 Target size (minimum) | targets at least 24×24 CSS px |
| 4.1.3 Status messages | capability, job and incident state changes are announced through one polite live region |

- **NFR5.2** — The maintenance notice and the static `/privacy` and `/terms` copies are readable without scripts (BR5.6, BR9.10).

## $0 operation (NFR6)

- **NFR6.1** — No paid service, licence or paid fallback (BR7.2). Production uses only free or local components: the local PostgreSQL, Ollama and cloudflared builds; Cloudflare's free tunnel; Resend's free plan; healthchecks.io's free plan (20 checks; v2 uses 3); Notion's free plan through each owner's own token; GitHub Actions for the public repository's CI. [Q9, Q13, Q22]
- **NFR6.2** — Email allowance (BR7.4):
  - Account mail may use up to 90 emails a day, and digests stop at 60 a day, so account mail always keeps at least 30.
  - All email stops at 2,700 a month, a 10% margin under Resend's free 3,000.
  - At either limit the email capability is degraded with allowance-exhausted, digests wait and account mail fails with a plain message.
  - The daily count resets at 00:00 UTC (09:00 in Seoul). [Q9]

## Required verification

These security-relevant behaviours are proven by tests in Code Generation and by the complete verification (BR10.3):

- The service account is refused every backup-agent, operator and service-control command, and the scheduler account every in-person and service-control command (NFR1.5).
- A fixed command refuses any argument outside its closed set and runs with a cleaned environment (NFR1.6).
- A database connection that did not authenticate through SCRAM fails v2's start, a stand-in listener on `127.0.0.1:15432` completes no login, and a TCP login as the superuser fails (NFR3.3).
- Without you authenticating at this Mac, a program running as your login account can read none of the operator tool's database passwords and cannot log in to v2's instance as the operator (NFR3.2).
- A forced unique violation on an email, an invalid-input error carrying a test value, and a failed statement leave no row value, rejected input, statement or parameter in PostgreSQL's server log (NFR3.9).
- A listener of another account on 18200, 18201, 11434 or 15432 receives no connection, even while the owning service is stopped (NFR3.8).
- With a Time Machine exclusion removed, the isolation check reports `isolation-backups` and platform.isolation becomes unavailable (NFR3.7).
- After forced failures, no secret, token, password, hash, email address or private text appears in logs, observations, incidents, parity reports or the installation log (NFR3.9, NFR4.4).
- A signed-out caller reaches no private route, stream or asset, and another owner's identifiers behave as missing (NFR1.1).
- The backup agent refuses a decided date earlier than 14 days after the copy was written, and a forged ledger record deletes nothing early (NFR3.13).
- The idempotent second migration pass imports and updates nothing (NFR4.4).
- After the log rotation job runs, no log under `/Library/DocSuri/` keeps a rotated copy older than 14 days, PostgreSQL's dated files included. Every copy keeps its log's owner and mode 0600 (NFR9.8).
- A symbolic or hard link planted in a log folder, pointing at a root-only file, is skipped by the rotation job and leaves that file unchanged and unread (NFR9.8).

## Threats considered

| Threat | Example | Covered by |
|---|---|---|
| Spoofing | A program listening on v2's database or host address; a forged decision or ledger record | NFR3.3, NFR3.8, NFR1.4, NFR4.3 |
| Tampering | A swapped program, library, model or rule file; a changed backup file | NFR3.8, NFR3.11, NFR3.5 |
| Repudiation | Disputing who approved a restore, a disposal or the switch | NFR1.4, NFR4.2 |
| Information disclosure | Keys or data in Time Machine, logs, an unencrypted drive or another account's reach | NFR3.1, NFR3.6, NFR3.7, NFR3.9 |
| Denial of service | A full internal disk; email allowance exhausted; a stopped job nobody renews | NFR8.13, NFR8.14, NFR6.2, NFR3.8 |
| Elevation of privilege | The running application using operator authority or the backup agent; a link planted as a log to steer a root job | NFR1.5, NFR1.6, NFR9.8 |

## Residual risks

Each of these is accepted in the design and stays visible at the U8 checkpoint:

- v1 and its data plane run as your login account until v1 retires, so what the migration reads from v1 is only as trustworthy as that account (BR6.11).
- Time Machine backups taken before the installation may hold v1's data until v1's stores are disposed of (NFR3.6, NFR3.12). This Mac's Time Machine settings record their disk, "무제", as last seen unencrypted, so anyone who holds that disk can read those backups until then. Encrypting that disk, which Time Machine can do in place, or deleting its old backups removes the exposure. That is your decision, outside this design.
- The backup account is the earlier work's test-realm account (UID 607) until a dedicated production account replaces it. The profile names it, so the change needs no design change (functional-spec.md § "What this design relies on"). [Q23]
- A macOS update can still stop at the FileVault unlock screen, and that wait counts against availability (NFR7.3).
