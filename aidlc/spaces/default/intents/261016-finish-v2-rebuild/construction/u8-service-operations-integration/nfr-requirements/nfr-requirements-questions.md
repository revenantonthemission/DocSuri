# NFR Requirements Questions — U8 complete service operations and integration

Date: 2026-10-21 (Asia/Seoul)
Unit: u8-service-operations-integration (the service). Inputs: [functional spec](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md), [requirements NFR1–NFR6](../../../inception/requirements-analysis/requirements.md), [technology stack](../../../../../codekb/DocSuri/technology-stack.md).

U8 is the service that hosts every unit, so its availability, recovery, capacity, monitoring and performance targets are set here, together with the values the functional design left as "policy" (functional-spec.md § "Carried to NFR Requirements").

Facts these questions rely on, checked on 2026-10-21:
- This Mac is the server: Apple M4 Pro, 14 cores, 24 GiB memory. The data volume has 39 GiB free of 460 GiB (91% used).
- v1 runs here under launchd with OrbStack containers (PostgreSQL 16, Redis, OpenSearch, MinIO), the local model runtime (Ollama with bge-m3 and qwen3:8b) and the Cloudflare tunnel. Its own backup job runs daily at 03:30.
- v1's object store held about 25 GB in 371,292 objects when it was mirrored in August 2026.
- Resend's free plan allows 100 emails a day (a UTC day, so it resets at 09:00 in Seoul) and 3,000 a month. Sending pauses at the limit; nothing is billed.
- healthchecks.io's free plan monitors up to 20 checks.
- PlatformControl's operator is the verified local OS user, acting under grants with explicit targets; an application administrator never holds operator authority.

Each question offers the design I recommend as A. Answer with a letter, or in your own words under X.

## Q1. What availability should the service aim for?

There is one machine and no standby, so power cuts, network loss, macOS updates and the switch itself all count against availability.

A. 99.0% a month at the public address, which allows about 7 hours 18 minutes of downtime a month, planned maintenance included:
   - measured by an outside heartbeat every 5 minutes (Q9);
   - a crashed process is restarted by launchd within 1 minute;
   - after a power cut or a reboot the service is back within 15 minutes of the machine starting, because auto-login is on;
   - planned work (the switch, a production restore, macOS updates) shows the maintenance notice, with no fixed maintenance window.
B. 99.5% a month (about 3 hours 39 minutes), which needs you to react faster to an outage.
C. Best effort, with no stated target.

X. Other (please specify)

[Answer]: A

## Q2. Which backup and restore values should the service use?

| Value | Proposed |
|---|---|
| Daily backup of the live database | 04:00 Asia/Seoul, after v1's own job at 03:30 |
| Retention | each daily set for 14 days; the Sunday set for 8 weeks |
| Data you can lose if the database is lost | up to 24 hours of writes (the time since the last backup) |
| Restore verification | weekly on Sunday at 05:00, from the newest passed set |
| Erasure verification bound | 24 hours: a waiting erasure gets its verification at the next 05:00 run |
| Recovery start bound | 24 hours: a request not admitted or not started by then expires |
| Production restore time | within 2 hours of your decision, for a database within the storage budget (Q7) |
| During the soak | the same schedule on the rehearsal database |

A. Use the values above.
B. Change some of them (say which under X).

X. Other (please specify)

[Answer]: A

## Q3. Where do backup sets live?

The design keeps backup sets on this machine only, in the production profile's backup folder (BR4.3). That protects against mistakes, corruption and bad releases, but not against losing the machine or its disk. v1's own backups are also copied to iCloud Drive today; that stops when v1 stops.

A. On this machine only, as designed. Losing the disk loses the service's data since the switch; the v1 copies keep v1's data until they are disposed.
B. Also keep an encrypted copy of each passed live set in iCloud Drive, with the passphrase kept only in your password manager. This protects against losing the machine, but it changes the design (the backup location, the retained-copy rules and the erasure disclosure), so U8's design is reopened for those rules. iCloud space beyond the free 5 GB is paid.
C. Copy sets to iCloud Drive unencrypted, as v1 does today. Not recommended: anyone with access to that iCloud account could read the personal data.

X. Other (please specify)

[Answer]: X) On a secured volume in an external drive.

## Q4. Which cutover timing values should the switch use?

| Value | Proposed |
|---|---|
| Soak period | 7 days of the release running cleanly in rehearsal mode |
| Switch time bound | 4 hours from stopping v1 to opening admission; v1 is unavailable for at most this long |
| Rollback window | 14 days after admission opens |
| v1 restart rehearsal window | the rehearsal must have passed within the 7 days before the switch |
| Consumer observation window | v1's traffic over the 14 days before the switch |

A. Use the values above.
B. Change some of them (say which under X).

X. Other (please specify)

[Answer]: A

## Q5. When are retained copies of personal data disposed of?

The design gives every copy a disposal point and a backstop date (BR9.12). The dates you approve here become the defaults your decisions confirm at each step.

| Copy | Disposed | Backstop |
|---|---|---|
| A dry run's copy of v1 | when its run ends | 14 days after it was taken |
| A rehearsal database, with its backup sets | when a newer dry run is accepted, when its run fails or is rejected, or right after admission opens | 60 days after it was created |
| A scratch restore a failed check left behind | when the operator removes it | 1 day |
| The v1 final snapshot | 30 days after settlement; for an aborted attempt, 30 days after the abort | 120 days |
| v1's stores (database, search index, object store and its own backup files) | 90 days after admission opens | 180 days |
| A rolled-back v2 database | 30 days after the rollback | 90 days |

Data you decide is archive-only (followed topics, glossary, saved searches and the rest) can be retrieved for a returning user only until v1's stores are disposed, so 90 days is how long people can ask for it.

A. Use the values above.
B. Change some of them (say which under X).

X. Other (please specify)

[Answer]: A

## Q6. How much of v1's object store goes into a migration copy?

A full copy of v1's object store takes about 25 GB. A dry run's copy and the final snapshot cannot both fit in the 39 GiB free, beside a rehearsal database and the backups.

A. Copy v1's database and search index in full. For the object store, record a manifest of every object (key, size, checksum), and copy only the objects the migration reads for the papers it imports. Private uploads and figures are not migrated, so they are not copied; they stay in v1's stores until those are disposed (Q5). Each copy then needs a few GB at most, and less personal data is duplicated. This narrows what the design calls the copy of the object store; the rest of the design is unchanged.
B. Copy the whole object store every time. This needs about 25 GB free per copy, so disk space has to be freed first.

X. Other (please specify)

[Answer]: A

## Q7. What storage budget should the production database have?

Admission closes before the budget is crossed, with the existing capacity-exhausted answer (BR6.6). The footprint counts the production database and the cluster's write-ahead log.

A. A budget of 8 GiB. storage.capacity shows degraded at 80% of the budget, or when the data volume has less than 20 GiB free, so you have time to act before admission closes. The first dry run measures the real size, and the budget can be revised then.
B. A budget of 16 GiB, which needs more free disk first.

X. Other (please specify)

[Answer]: A

## Q8. Which readiness, incident and monitoring timing values should the service use?

| Value | Proposed |
|---|---|
| Renewal interval, required capabilities | 60 seconds |
| Freshness bound, required capabilities | 180 seconds (three missed renewals) |
| Incident tolerance (degraded, unknown or stale) | 10 minutes; an unavailable required capability opens an incident at once |
| Renewal and freshness, providers, platform status and the cutover check | 5 minutes and 15 minutes |
| Incident tolerance, cutover check | 15 minutes |
| Export age bound (degraded) | the oldest unclear or accepted export is older than 24 hours |
| Digest age bound (degraded) | the oldest pending delivery is 2 hours past its scheduled time |
| 운영 dashboard refresh | every 30 seconds, and on demand |
| 작업 list refresh while work is unfinished | every 5 seconds |
| Log retention | 14 days, rotated daily (copy, then truncate) |

A. Use the values above.
B. Change some of them (say which under X).

X. Other (please specify)

[Answer]: A

## Q9. How should email be shared out, and how do you hear about problems?

Email shares Resend's free allowance of 100 a day and 3,000 a month (BR7.4).

A. Email and alerts:
   - Account mail (verification, password reset, email change) may use up to 90 emails a day. Digests stop at 60 a day, so account mail always keeps at least 30. Everything stops at 2,700 a month, leaving a 10% margin.
   - Alerts come from healthchecks.io's free plan. One check takes a heartbeat every 5 minutes covering the public address and the health route, one the daily backup, and one the weekly restore verification. A missing or failed ping emails you. Only check names and pass or fail leave the machine, never error details.
B. The same email allowance, but no outside alerting: problems appear only in 운영, so you notice them when you look.
C. DocSuri emails alerts itself through Resend. This uses the email allowance and says nothing when the machine itself is down.

X. Other (please specify)

[Answer]: A

## Q10. Which performance targets should the service meet on this machine?

| Measure | Target (95th percentile unless stated) |
|---|---|
| Health route, local | under 200 ms |
| First load of the workspace through the public address | under 2 s; under 1 s for later navigation |
| API reads, server time | under 500 ms |
| Search results | under 3 s, including the local embedding of the query |
| Accepting a research, novelty or export request | under 1 s; the work itself runs in the background |
| Start to ready after a restart | under 3 minutes |
| Concurrent signed-in users | 20 |
| Memory for the v2 host and its workers together | under 4 GiB, leaving the rest of the 24 GiB to the local models and data stores |

A. Use the targets above.
B. Change some of them (say which under X).

X. Other (please specify)

[Answer]: A

## Q11. Who can sign in when admission opens?

A. Only existing accounts, migrated from v1. Registration stays closed until you open it later as its own decision, after AccountAccess's public-activation evidence is recorded (a verified sending domain, working verification mail and the abuse limits U2 built). Once registration opens, the service accepts at most 500 accounts, to stay within the storage budget.
B. Open registration at the same time as admission, if the public-activation evidence is already recorded.

X. Other (please specify)

[Answer]: A

## Q12. Should the migration reuse v1's search vectors?

v2 searches only with vectors made by its pinned model (`bge-m3-1024-pinned-1`). v1's vectors were re-made with bge-m3 in August 2026, but which exact model build and settings produced them cannot be told from the code (BR8.8).

A. Never reuse them: every migrated paper is embedded again locally with the pinned model. It costs nothing, takes minutes for the current corpus, and removes the reuse check from the code.
B. Reuse them where proven: for each paper, embed up to 16 of its chunks again (all of them if fewer), and keep v1's vectors only if every sampled pair has a cosine similarity of at least 0.999; otherwise embed the whole paper again.

X. Other (please specify)

[Answer]: A

## Q13. Which technology should run the service and its operations?

A. No new data stores and no new paid services:
   - **Supervision:** launchd agents for the v2 host, its workers, the scheduler and the maintenance server, as v1 uses today. The production checkout lives at `~/Services/docsuri`, outside the development tree, at a release tag.
   - **Database:** a new database in the existing PostgreSQL 16, with each owner's roles.
   - **Operations ledger:** an append-only JSON Lines file in the profile root, chained with SHA-256, written with fsync and an atomically replaced head file, using the Python standard library only.
   - **Maintenance server:** a static server on the backend's existing ASGI stack, serving only the notice and the two legal pages, with no application or database code.
   - **Tunnel:** the existing cloudflared tunnel with three registered origins; a routing change swaps its configuration and reloads it.
   - **Alerting:** healthchecks.io pings from the existing heartbeat script.
   - **Verification:** the existing pytest and Playwright tooling, in a new GitHub Actions lane.
B. The same, but serve the maintenance notice with Caddy or nginx installed through Homebrew, which adds a dependency.

X. Other (please specify)

[Answer]: A

## Follow-up questions

Your answer to Q3 and two facts checked after it need these follow-ups. Checked on 2026-10-21:
- This Mac already has a secured external volume: `DocSuri_Backup`, an encrypted APFS volume on the external 2 TB USB SSD, with 731 GiB free in its container. It was set up for the earlier platform-integrity work (REM-1, 2026-09-30). It is owned by a dedicated account (`_docsuri_r1t_backup`) with owner-only access, and is written by REM-1's archive tool (`ops/src/docsuri_ops/backup_evidence.py`). That tool writes only when the volume is mounted, writable and encrypted, checks each copy by digest, and cleans up only archives it created. The archives rely on the volume's own encryption password; the tool adds no second key.
- FileVault is now on for this Mac's internal disk, and auto-login is off. Q1's recovery time assumed auto-login, as my notes from August said. After a power cut the Mac waits at the disk-unlock screen, and nothing (v2, the tunnel, the backup volume) starts until someone unlocks it.

## Q14. Follow-up to Q3: how are backup sets written to the external volume?

The design keeps backup sets in the production profile's root on the internal disk (BR4.3, BR6.1, and BR6.10 for the ledger's last good copy beside each set). Moving them to the external volume changes those rules, so U8's design is reopened for them before the NFR files are written.

A. Through REM-1's setup: v2's backup sets, and the ledger's last good copy beside each set, are written to `DocSuri_Backup` by REM-1's archive tool under the dedicated backup account, as the implementation of the database backup operation. The service itself can neither write nor delete them, so a fault or a compromise in the application cannot destroy its own backups.
B. A new folder on `DocSuri_Backup`, written directly by the service user, without the separate account. The same design change applies, but the application can delete its own backups.

X. Other (please specify)

[Answer]: A

## Q15. Follow-up to Q3: can the backups be read if this Mac is lost?

The archives are protected by `DocSuri_Backup`'s own encryption password. If this Mac dies, the drive can be read on another Mac only with that password.

A. The volume's password is also kept outside this Mac (for example in your password manager), so the drive is readable on any Mac. The backup evidence records only that the password is held off-machine, never the password.
B. The password stays only in this Mac's keychain. The backups then protect against mistakes and a failed internal disk while this Mac works, but not against losing this Mac.

X. Other (please specify)

[Answer]: A

## Q16. Follow-up to Q1: recovery after a power cut, now that FileVault is on

A. Keep FileVault on. After an unplanned restart, the service comes back when you unlock the Mac; the heartbeat alert (Q9) tells you it is down. Planned restarts (macOS updates) use an authorized restart (`fdesetup authrestart`), which skips the unlock screen once, so they come back unattended. The 99.0% target stays, and time waiting for an unlock counts against it.
B. Turn FileVault off to bring back auto-login. Not recommended: the internal disk, with the live database and keys, would no longer be encrypted at rest.

X. Other (please specify)

[Answer]: A

## Q17. Follow-up to Q3: do other copies of personal data go on the backup volume too?

With Q6 A, a dry run's copy of v1 and the v1 final snapshot are files of a few GB each.

A. Yes: every file copy of personal data U8 makes (backup sets, the ledger's last good copies, dry-run copies of v1 and the v1 final snapshot) lives on `DocSuri_Backup`, off the internal disk's 39 GiB of free space. Databases (production, rehearsal and scratch restores) stay in PostgreSQL on the internal disk.
B. No: only the backup sets and the ledger copies beside them go there; the migration copies stay on the internal disk.

X. Other (please specify)

[Answer]: A

## Q18. Follow-up to Q13: which macOS account runs v2?

You were asked this in chat on 2026-10-21, while U8's design was being reviewed. It is recorded here because it replaces Q13's supervision answer.

Any program running as your login account can do whatever the operator tool can without a password. That includes running a backup check that restores an old backup, still holding deleted users' data, into a database it can read.

A. v2 on its own account. v2's host, workers, scheduler and maintenance server run as a dedicated non-login account, started by system launch jobs an administrator installs, like the earlier platform work's backup account. The operator tool stays on your login account, and v2's account can run no operator or backup command. Costs: one-time setup with administrator rights, and the production checkout moves from `~/Services/docsuri` to a system folder.
B. Keep my login account. Everything runs under your login account, as v1 does. The backup agent still blocks early deletion and always keeps the last good backup, but a compromise of the app could act as the operator without a password; that risk would be written into the design as accepted.

X. Other (please specify)

[Answer]: A

## Q19. Follow-up to Q16 and Q18: what keeps running under your login account?

Found while writing the NFR files, and checked on 2026-10-21: PostgreSQL (inside OrbStack), the local models (Ollama) and the tunnel (cloudflared) all run as your login account and start only when you log in. Two of your answers rested on a wrong assumption about that:
- **Q16.** An authorized restart (`fdesetup authrestart`) skips only the disk-unlock screen; the Mac then waits at the login window for your password. So a planned restart does not come back by itself: v2's own jobs start, but without their database, the models or the tunnel until you log in.
- **Q18.** v2 runs on its own account so that a program running as your login account cannot act on v2 without a password. Three paths stay open while these run as your login account: such a program can read or drop v2's database through OrbStack, take over the models' local address and receive the private text v2 sends them, and use the tunnel's credentials in `~/.cloudflared` to serve the public address itself.

A. Move them off your login account:
   - v2's databases (production, rehearsal, scratch and import) run in their own PostgreSQL 16, installed with Homebrew (free), as a system launch job under a non-login account. OrbStack stays only for v1 until it retires.
   - The models and the tunnel each become one system launch job under its own non-login account, shared with v1 at the same addresses, and moved before the soak so the soak and v1's restart rehearsal run on the final arrangement.
   - The tunnel's credentials leave your login account. Cloudflare's account certificate (`cert.pem`) is kept off this Mac and used only to change tunnels.

   Planned restarts with `fdesetup authrestart` then come back unattended (an OS update can still stop at the unlock screen), and Q18's protection also covers the database, the text sent to the models and the public address. Costs: U8's design is reopened for these changes, PostgreSQL 16 is installed beside OrbStack, and the models move to a system folder.
B. Keep them under your login account, as v1 does. Every restart, planned or not, waits for you to log in, so `fdesetup authrestart` is not used, and logging out stops the service. The three paths above are written into the design as accepted risks.

X. Other (please specify)

[Answer]: A

## Follow-up questions (2026-10-22)

U8's design was reopened after Q19, and its new rules left values for this stage (functional-spec.md § "Carried to NFR Requirements"). These questions cover the values no earlier answer set, plus three facts that changed. Checked on 2026-10-22:
- The internal disk has 11.7 GiB free as macOS reports it to programs, down from the 39 GiB measured on 2026-10-21. macOS counts another 82 GiB as reclaimable. That space is held mostly by Time Machine's local snapshots (25 on the disk, taken hourly and kept for 24 hours, so deleted files keep their space for a day) and by caches, and macOS frees it only when it runs short.
- v1's live data is small: its database is 0.23 GB (PostgreSQL 16.14, libc locale), and its search index holds 599 documents in 11 MB. Its object store (25 GB) is on `/Volumes/SSD01` for now, as you said. The object store v1 actually serves (`~/DocSuriData/minio`) is empty.
- `/Volumes/SSD01` and the backup volume are two volumes of one APFS container on the external drive, so they share its 784 GB of free space. SSD01 is not encrypted and does not enforce ownership.
- Homebrew upgraded Ollama to 0.40.7 and cloudflared to 2026.10.3 by itself since 2026-10-21. That is one reason the arrangement runs only root-owned copies, which change only in person.
- The system launch jobs already on this Mac use the label prefix `org.docsuri.`, and the earlier platform work's accounts take UIDs 600–608.

## Q20. Which free-space reading should the internal-disk checks use?

The design reads the internal disk's free space before every restore verification and every dry-run import phase. It shows storage degraded below the 20 GiB threshold you chose in Q7, and it closes storage admission below a critical floor (Q21). At today's 11.7 GiB, those checks would already refuse. v2's own databases will be small: the production database should start near 1–2 GB, and a dry run writes a few GB. So the threshold mostly protects the Mac itself.

A. Use the free space macOS reports to programs, because that is the only space PostgreSQL can write into.
   - Before the first dry run, free enough space for it to read above the threshold plus the run's size, about 23 GiB.
   - Deleting Time Machine's local snapshots (`sudo tmutil deletelocalsnapshots /`) frees most of that at once and leaves the backups on your Time Machine disk untouched.
   - Heavy development use, such as the synthetic test realms, can fill that space again within a day. A low reading shows storage degraded, and an incident opens after the 10-minute tolerance (Q8).
B. Use macOS's reading that counts reclaimable space (93.6 GiB today) for the threshold, and the plain reading for the critical floor only. This gives fewer warnings. But a dry run or restore verification that passes the check can still hit the critical floor midway, because PostgreSQL's writes do not wait for macOS to reclaim space.

X. Other (please specify)

[Answer]: A

## Q21. Which values should the new storage, retention and check rules use?

| Value | Proposed | Why |
|---|---|---|
| Critical floor of the internal disk | 10 GiB free. Below it, storage admission closes, scheduled restore verifications and imports stop, and an incident opens at once (BR6.6) | leaves room for PostgreSQL's write-ahead log and for macOS to work |
| Write-ahead log of v2's PostgreSQL instance | at most 1 GiB (`max_wal_size`, PostgreSQL's default), with no archiving and no replication slots | well under the 20 GiB threshold, as BR6.6 requires |
| Backup floor on the backup volume | 64 GiB free | eight more sets at the full 8 GiB budget still fit after the warning; the container has 784 GB free today |
| Staging backstop | 1 day | the design's starting point |
| Import database backstop | 14 days after it is created | the same as the dry-run copy it is restored from; normally it is removed when its run ends |
| Earliest disposal the backup agent accepts for the v1 final snapshot and for a rolled-back database's copy | 14 days after the copy is written | never inside the 14-day rollback window; your Q5 dates (30 days after settlement, the abort or the rollback) stay valid |
| Runtime isolation check (platform.isolation) | runs every 5 minutes; stale after 15 minutes; an incident opens once it has been failed, unknown or stale for 15 minutes | the same as platform status and the cutover check (Q8) |
| Isolation check results kept | 14 days, deleted by the check itself | the same as logs (Q8) |
| A planned stop's bound | 14 days. You renew a stop in person before it passes, and every check lists each stop's expiry | a forgotten stop shows up as a lapse instead of staying hidden |
| Ledger copies | kept like the daily sets: 14 days, with the Sunday copy kept 8 weeks | follows Q2, as the design states |

A. Use the values above.
B. Change some of them (say which under X).

X. Other (please specify)

[Answer]: A

## Q22. Where does each root-owned program come from?

Every program in v2's arrangement runs from a root-owned copy outside Homebrew's folder. Each copy is checked against its publisher's checksum, and `otool -L` confirms it loads only its own and system libraries (BR6.5, BR6.11). Homebrew's copies cannot be used: its folder belongs to your login account, and its Ollama loads libraries from there.

A. Each publisher's own release, pinned:
   - **PostgreSQL 16.14**, the release v1 runs. Built from the PostgreSQL project's source release, checked against its published SHA-256, with the Xcode tools already on this Mac, and linked only to system libraries. It is built without ICU and without TLS: v1's database uses the libc locale and no ICU collation, nothing in v2's schema needs ICU, and the instance accepts only SCRAM logins over loopback.
   - **Ollama 0.40.7**: the official macOS release archive from Ollama's GitHub releases, checked against the release's published checksum.
   - **cloudflared 2026.10.3**: the official `darwin-arm64` archive from Cloudflare's GitHub releases, checked the same way.
   - **v2's Python 3.13.7 and its dependencies**: CPython installed by uv into the release folder, with every download checked against uv's recorded hash, and the dependencies installed from the lockfile (`uv sync --frozen`), each checked against its lock hash. The workspace's static build ships inside the release, so no Node.js runs in production.

   Upgrading any of them is an in-person step. For v2's own code, an upgrade is a new release.
B. The same, except PostgreSQL 16 comes from EDB's signed macOS installer, in its own root-owned folder with ICU and OpenSSL bundled, after removing the service account and launch job the installer adds.

X. Other (please specify)

[Answer]: A

## Q23. Which names, folders and addresses should the arrangement use?

| Item | Proposed |
|---|---|
| Accounts (non-login, no shell, no home), each with the same UID and group ID | `_docsuri_v2` service (610), `_docsuri_v2_sched` scheduler (611), `_docsuri_v2_db` database (612), `_docsuri_models` models (613), `_docsuri_tunnel` tunnel (614). The backup account stays `_docsuri_r1t_backup` (607), which owns the backup volume (Q14) |
| System launch jobs | `org.docsuri.v2.host`, `org.docsuri.v2.workers`, `org.docsuri.v2.scheduler` and `org.docsuri.v2.maintenance` (service account); `org.docsuri.v2.standing` (scheduler account); `org.docsuri.v2.postgres` (database account); `org.docsuri.models` and `org.docsuri.tunnel` (shared with v1); `org.docsuri.v2.pf`, which loads the packet filter rules at boot, and `org.docsuri.v2.backup-unlock`, which unlocks the backup volume, both run as root |
| Root-owned folders, under `/Library/DocSuri/` | `release/` (the production checkout, with its Python runtime and dependencies), `runtimes/postgresql-16.14/`, `runtimes/ollama-0.40.7/`, `runtimes/cloudflared-2026.10.3/`, `tunnel/config/` (the three registered configurations and the active choice), `control/stops/` (stop records), `evidence/isolation/` (readable by every account) |
| Account-owned folders (0700), under `/Library/DocSuri/` | `profile/` (service account; the profile root), `postgres/data/` and `postgres/socket/` (database account), `models/` and `models-state/` (models account), `tunnel/credentials/` (tunnel account) |
| Root-owned rule files | the fixed-command rules in `/etc/sudoers.d/docsuri-v2`, and the packet filter rules in `/etc/pf.anchors/org.docsuri.v2` |
| Local addresses | v2 host `127.0.0.1:18200`, maintenance server `127.0.0.1:18201`, v2's PostgreSQL instance `127.0.0.1:15432`. The model runtime stays at `127.0.0.1:11434`. The composed verification realm follows the synthetic profiles' pattern, at `127.0.0.1:18109` and `127.0.0.1:15509` |

A. Use these.
B. Change some of them (say which under X).

X. Other (please specify)

[Answer]: A

## Q24. Where do v1's own stores live until they are disposed of?

`/Volumes/SSD01` holds three sets of v1 data:
- v1's object store (`DocSuriData/minio`, 25 GB, the papers' full texts);
- v1's own database dumps (`Backups/docsuri/postgres`, 402 MB, daily dumps from July to September 2026);
- the 2026-10-10 archive (`DocSuri-archive`, 866 MB, which includes historical database snapshots).

That volume is not encrypted and does not enforce ownership. Any account on this Mac can read it, and so can anyone who has the drive. The design reads v1's object store in every dry run and in the final run. It also records v1's stores, including v1's own backup files, as a retained copy that only the operator can read (BR9.12).

A. Before the first dry run, move v1's object store, its database dumps and the archive into a new encrypted APFS volume on the same drive (for example `DocSuri_v1`).
   - The volume enforces ownership, and its folders are owner-only for your login account, which v1 runs as. Its passphrase is kept in your login keychain and your password manager.
   - v1's object store is then served from there, so the dry runs, v1's restart rehearsal, an abort and a rollback all use it.
   - These locations, together with the iCloud copies of v1's backups, are recorded as v1's stores with their disposal dates (Q5).
   - The new volume shares the drive's 784 GB of free space with the backup volume.
B. Keep them on SSD01 as they are, and record the exposure as an accepted risk: every account on this Mac, v2's included, can read them, and so can anyone who has the drive. This is an exception to the design's operator-only rule for retained copies (BR9.12), so U8's design is reopened to record it.

X. Other (please specify)

[Answer]: A

## Q25. Should Time Machine copy v2's or v1's data?

Found while writing the security requirements, and checked on 2026-10-22:
- Time Machine's automatic backups are on.
- Its disk, "무제", has not mounted today, so for now Time Machine only takes local snapshots.
- Its backups include `/Library`, where v2's folders will live (Q23), and OrbStack's data folder, which holds v1's database and search index.

Once Time Machine backs up again, v2's database, its key folders and its ledger, and v1's data, land on that disk with no disposal date. That breaks two rules already in the design: no backup holds key material (BR4.8), and every copy of personal data is recorded with a disposal point (BR9.12). Backups taken before today may already hold v1's data.

A. Exclude these from Time Machine, set as root at installation: v2's private folders (`profile/`, `postgres/`, `models-state/`, `tunnel/credentials/`) and OrbStack's data folder.
   - The installation log records each exclusion. The runtime isolation check confirms them every 5 minutes, as a new item that U8's design gains; the U8 checkpoint re-checks that change.
   - Time Machine backups already on "무제" are listed as part of v1's stores, with Q5's dates.
   - Local snapshots keep deleted data on this disk for at most 24 hours. That is shorter than any backup set's retention, so the dates erasure evidence shows do not change.
B. Turn Time Machine's automatic backups off on this Mac. Nothing on this Mac is copied by Time Machine any more, your own files included, and local snapshots stop, which frees about 82 GiB. Backups already on "무제" are listed as in A.

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- **Q1, with Q16 and Q19 — availability:**
  - 99.0% a month at the public address (about 7 hours 18 minutes of downtime, planned work included), measured by an outside heartbeat every 5 minutes.
  - launchd restarts a crashed process within 1 minute.
  - A planned, authorized restart comes back unattended, because v2's jobs and everything they need start at boot without a login (an OS update can still stop at the unlock screen).
  - After an unplanned restart, the Mac waits at the FileVault unlock screen until you unlock it, and that wait counts against the target.
  - Planned work shows the maintenance notice, with no fixed window.
- **Q2 — backup and restore:**
  - Daily backup at 04:00, after v1's 03:30 job.
  - Daily sets kept 14 days, Sunday sets 8 weeks; up to 24 hours of writes can be lost.
  - Restore verification every Sunday at 05:00, from the newest passed set.
  - Erasure verification bound and recovery start bound of 24 hours each; a production restore within 2 hours of your decision.
  - The same schedule runs on the rehearsal database during the soak.
- **Q3 and Q14–Q17 — where copies live:**
  - Backup sets and every other file copy of personal data U8 makes (ledger copies, dry-run copies of v1, the v1 final snapshot) live on the encrypted `DocSuri_Backup` volume.
  - Only the backup agent writes them, as the dedicated backup account, so the service can neither write nor delete them.
  - The volume's password is also kept off this Mac, so the drive can be read on another Mac.
  - FileVault stays on. Databases stay in PostgreSQL on the internal disk.
- **Q4 — cutover timing:** soak 7 days; switch time bound 4 hours; rollback window 14 days; v1's restart rehearsal within the 7 days before the switch; consumer observation window 14 days.
- **Q5 — disposal of retained copies:**
  - A dry run's copy of v1: when its run ends (backstop 14 days).
  - A rehearsal database with its sets: when a newer dry run is accepted, when its run fails or is rejected, or right after admission opens (60 days).
  - A scratch restore: when the operator removes it (1 day).
  - The v1 final snapshot: 30 days after settlement or the abort (120 days).
  - v1's stores: 90 days after admission opens (180 days).
  - A rolled-back v2 database: 30 days after the rollback (90 days).
  - Archive-only data can be retrieved for a returning user until v1's stores are disposed of.
- **Q6 — migration copy:** v1's database and search index are copied in full. From the object store, the copy takes a manifest of every object and only the objects the imported papers need; private uploads and figures are not copied.
- **Q7, with Q20 — storage budget:**
  - 8 GiB for the production database plus the write-ahead log.
  - Storage shows degraded at 80% of the budget, or when the internal disk has less than 20 GiB free, read as the free space macOS reports to programs.
  - The first dry run measures the real sizes, and the budget can be revised then.
- **Q8 — readiness, incidents and monitoring:**
  - Required capabilities renew every 60 s and are stale after 180 s. An incident opens after 10 minutes degraded, unknown or stale, and at once when unavailable.
  - Providers, platform status and the cutover check renew every 5 minutes and are stale after 15 minutes; the cutover check's incident tolerance is 15 minutes.
  - Export shows degraded past 24 hours; digests show degraded 2 hours past schedule.
  - 운영 refreshes every 30 s and on demand, and 작업 every 5 s while work is unfinished.
  - Logs are kept 14 days, rotated daily.
- **Q9 — email and alerts:**
  - Account mail: up to 90 emails a day. Digests stop at 60 a day. Everything stops at 2,700 a month.
  - Alerts come from healthchecks.io's free plan: a 5-minute heartbeat of the public address and the health route, the daily backup, and the weekly restore verification. Only check names and pass or fail leave the machine.
  - Because nothing of v2's runs as your login account (Q18), the scheduler account's standing job sends these pings, reusing the existing heartbeat script's checks.
- **Q10 — performance, 95th percentile unless stated:**
  - Health route under 200 ms locally.
  - First workspace load through the public address under 2 s, later navigation under 1 s.
  - API reads under 500 ms server time; search under 3 s, including the local query embedding.
  - Accepting a research, novelty or export request under 1 s.
  - Start to ready under 3 minutes after a restart.
  - 20 concurrent signed-in users, with v2's host and workers under 4 GiB of memory together.
- **Q11 — admission:** only migrated accounts sign in when admission opens. Registration stays closed until you open it after AccountAccess's public-activation evidence is recorded, and then allows at most 500 accounts.
- **Q12 — vectors:** v1's vectors are never reused. Every migrated paper is embedded again locally with the pinned model, so no sample size or tolerance applies.
- **Q13, as replaced by Q18, Q19, Q22 and Q23 — technology:**
  - No new paid services.
  - The operations ledger is an append-only, SHA-256-chained JSON Lines file with an atomically replaced head.
  - A static maintenance server on the backend's ASGI stack serves only the notice and the two legal pages.
  - The tunnel runs on cloudflared with three registered configurations, and alerting goes through healthchecks.io.
  - Verification uses pytest and Playwright in a new GitHub Actions lane.
- **Q18 — accounts:**
  - v2's host, workers, scheduler and maintenance server run as a dedicated non-login service account, under system launch jobs.
  - The operator tool stays on your login account, and v2's account can run no operator or backup command.
  - The production checkout lives in a system folder.
- **Q19 — runtimes off your login account:**
  - v2's databases run in their own PostgreSQL 16 instance, as a non-login database account.
  - The model runtime and the tunnel each run as their own non-login account, shared with v1 at the same addresses.
  - The tunnel's credentials leave your login account, and no Cloudflare certificate stays valid after the installation (the design's reading of Q19).
- **Q20 — free-space reading:** the internal-disk checks read the free space macOS reports to programs. Before the first dry run, you free enough room for it to read about 23 GiB; deleting Time Machine's local snapshots does most of that.
- **Q21 — storage, retention and check values:**
  - Critical floor 10 GiB; write-ahead log at most 1 GiB, with no archiving and no replication slots; backup floor 64 GiB.
  - Staging backstop 1 day; import database backstop 14 days.
  - The backup agent accepts disposal of the v1 final snapshot or a rolled-back database's copy no earlier than 14 days after writing it.
  - The isolation check runs every 5 minutes, is stale after 15 minutes, and opens an incident after 15 minutes; its results are kept 14 days.
  - A planned stop stays valid for 14 days.
  - Ledger copies are kept like the daily sets.
- **Q22 — program sources:**
  - PostgreSQL 16.14, built from source without ICU or TLS.
  - Ollama 0.40.7 and cloudflared 2026.10.3, from their official GitHub releases.
  - Python 3.13.7 and the dependencies, installed by uv into the release folder from the lockfile.
  - Every download is checked against its publisher's checksum, and every upgrade happens in person.
- **Q23 — names, folders and addresses:**
  - Accounts: `_docsuri_v2` (610), `_docsuri_v2_sched` (611), `_docsuri_v2_db` (612), `_docsuri_models` (613) and `_docsuri_tunnel` (614). The backup account stays `_docsuri_r1t_backup` (607).
  - Jobs: `org.docsuri.v2.host`, `.workers`, `.scheduler`, `.maintenance`, `.standing`, `.postgres`, `.pf` and `.backup-unlock`, plus `org.docsuri.models` and `org.docsuri.tunnel`.
  - Folders under `/Library/DocSuri/`; rule files in `/etc/sudoers.d/docsuri-v2` and `/etc/pf.anchors/org.docsuri.v2`.
  - Addresses: host 18200, maintenance server 18201, PostgreSQL 15432, models 11434 and the verification realm 18109/15509, all on 127.0.0.1.
- **Q24 — v1's stores:**
  - Before the first dry run, v1's object store, its database dumps and the 2026-10-10 archive move from SSD01 into a new encrypted APFS volume (for example `DocSuri_v1`). It enforces ownership, with owner-only folders for your login account.
  - v1's object store is served from there.
  - These locations, with the iCloud copies of v1's backups, are recorded as v1's stores with Q5's dates.
- **Q25 — Time Machine:**
  - Root excludes v2's private folders (`profile/`, `postgres/`, `models-state/`, `tunnel/credentials/`) and OrbStack's data folder from Time Machine at installation.
  - The installation log records each exclusion, and the runtime isolation check confirms them every 5 minutes, as a new item in U8's design, re-checked at the U8 checkpoint.
  - Time Machine backups already on "무제" are listed as part of v1's stores, with Q5's dates.
  - Local snapshots hold deleted data for at most 24 hours, so the dates erasure evidence shows do not change.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
