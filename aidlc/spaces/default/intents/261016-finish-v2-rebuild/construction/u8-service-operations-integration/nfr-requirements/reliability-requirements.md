# Reliability Requirements — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-requirements-questions.md](nfr-requirements-questions.md) (Q1–Q25);
- inception [requirements FR4.1 and FR4.2](../../../inception/requirements-analysis/requirements.md);
- this Unit's [functional spec](../functional-design/functional-spec.md) (Workflows 1, 5–7, 13, 14 and 20) and [rules](../functional-design/rules.md);
- the [technology stack](../../../../../codekb/DocSuri/technology-stack.md).

The inception requirements name no availability or recovery requirement, so **NFR7** is derived here from FR4.1 ("the finished service runs continuously on this machine with real accounts and real papers"). Every row names the answer that set its value.

## Availability (NFR7)

- **NFR7.1** — Availability objective: 99.0% per calendar month at `https://docsuri.rvnnt.dev`, planned work included, measured from the time admission opens.
  - The error budget is 1% of the month: 7 hours 12 minutes in a 30-day month and 7 hours 26 minutes in a 31-day month, about 7 hours 18 minutes in an average month.
  - The measurement counts scheduled slots, not probes. Every 5-minute slot of the month counts (8,640 in a 30-day month), and a slot is up only if its probe found both the public address and the health route ready. A slot with no recorded result, for example while the Mac is down, counts as down. The availability record of NFR9.13 holds every slot.
  - There is one machine and no standby, so power cuts, network loss, macOS updates, the switch and production restores all count against it. [Q1]
- **NFR7.2** — launchd restarts a crashed long-running process of the arrangement within 1 minute. Every long-running job runs with `KeepAlive`: v2's host, workers, scheduler and maintenance server, the standing job, v2's PostgreSQL instance, the model runtime and the tunnel. The one-shot and interval jobs are the packet filter's loader and the backup volume's unlock. They run without `KeepAlive` (tech-stack-decisions.md). The service is ready again within 3 minutes of the restarted job's start, PostgreSQL's own crash recovery included (NFR8.6). [Q1, Q10]
- **NFR7.3** — Restarts of the Mac [Q16, Q19]:
  - A planned restart uses an authorized restart (`fdesetup authrestart`) and comes back unattended, because every job of the arrangement, the backup volume's unlock included, starts at boot without a login (BR6.11 (6)).
  - An unplanned restart, such as after a power cut, waits at the FileVault unlock screen until you unlock the Mac. A macOS update can stop there as well.
  - From the moment boot completes, after the unlock or an authorized restart, the whole chain is ready within 3 minutes (NFR8.6): v2's PostgreSQL instance, the model runtime, the tunnel and the host. The time spent waiting at the unlock screen counts against NFR7.1.
- **NFR7.4** — A v2 start that finds its PostgreSQL instance not yet answering keeps the host live and not ready, and retries without restarting in a loop (BR3.1, BR6.11 (6), functional-spec.md Workflow 1).
- **NFR7.5** — Planned work (the switch, a production restore, an installation's authorized restart) routes the public address to the static maintenance server, which serves the notice and the legal pages and depends on no application or database (BR9.10). There is no fixed maintenance window. [Q1]

## Backup and restore (NFR7)

- **NFR7.6** — A backup of the current environment's database is taken daily at 04:00 Asia/Seoul, after v1's own 03:30 job. That is the rehearsal database during the soak and the production database in live mode.
  - A ledger copy goes with every set, and on its own at the same time on any day no set was taken.
  - A set counts only after its integrity check passes (BR4.3, BR6.10). [Q2]
- **NFR7.7** — Up to 24 hours of writes can be lost if the production database is lost.
  - Daily sets and ledger copies are kept 14 days, and Sunday sets and ledger copies 8 weeks.
  - The retention floor always keeps the newest passed set of each database that still exists and the newest verified ledger copy (BR9.17). [Q2, Q21]
- **NFR7.8** — Restore verification:
  - Every Sunday at 05:00, the newest passed live set (the rehearsal set during the soak) is restored into a scratch database.
  - On any other day, the standing job also runs one at 05:00 when an erasure is waiting for a verification.
  - The 24-hour erasure verification bound applies to the start: a waiting erasure's verification starts at the next 05:00, within 24 hours of its tombstone, and completes within 60 minutes of that start (NFR8.9).
  - It passes only when integrity passes and no erased owner survives the replay of every tombstone up to the recorded register head, and only once the scratch database is removed (BR2.6, BR4.5). [Q2]
- **NFR7.9** — A production restore completes within 2 hours of the operator starting it on your decision, for a database within the 8 GiB budget. v2 starts only after the request records its start authorization (BR4.7). [Q2] Its steps fit that bound:

| Step | Bound at the full budget |
|---|---|
| Route to the maintenance server and stop v2 | 5 minutes |
| Pre-restore backup (skipped by a successor) | 25 minutes |
| Recreate the database and restore the chosen set | 45 minutes |
| Replay tombstones and check integrity | 10 minutes |
| Post-restore backup | 25 minutes |
| Start v2, reach readiness and route back | 10 minutes |

  At today's sizes, a few GB, every step takes minutes. The soak's restore verification records the restore and checks' durations, and a measurement that would break a bound is shown with your switch-start decision.
- **NFR7.10** — A recovery request not admitted, or admitted and not started, within 24 hours expires (BR4.4). [Q2]
- **NFR7.11** — Losing storage or the machine [Q15, Q24]:
  - A backup volume lost for good is retired and replaced only on your decision, and a backup and a ledger copy are then taken on the replacement at once (BR4.10).
  - If this Mac is lost, the external drive's encrypted volumes can be read on another Mac with the passphrases kept in your password manager.
  - Rebuilding the service from them is an Operation-stage procedure.

## Degradation (NFR7)

- **NFR7.12** — No provider makes the service unready. Google, ORCID, Resend, the model runtime and Notion each degrade on their own capability, and dependent features show that state and never claim an effect happened. Nothing switches to another or a paid provider (BR3.11, BR7.2).
- **NFR7.13** — A missing or unfit backup volume never stops the start. storage.capacity shows degraded with its reason until the volume is back (BR6.1, BR6.6).

## Cutover (NFR7)

- **NFR7.14** — The switch starts only when BR9.2's preconditions hold [Q4, Q21]:
  - a soak of 7 days clean on the release tag;
  - a verified rehearsal restore;
  - v1's restart rehearsal within the 7 days before the switch;
  - a consumer inventory covering v1's traffic over the 14 days before it;
  - backup-volume free space of at least the 64 GiB floor plus the accepted dry run's measured snapshot and backup sizes;
  - runtime isolation evidence passed within the last 15 minutes.
- **NFR7.15** — The switch has 4 hours from stopping v1 to opening admission. Passing that bound, a failed step or your decline aborts it, and v1 serves again before anything of v2's is removed (BR9.4, BR9.5). [Q4]
- **NFR7.16** — A rollback is possible for 14 days after admission opens. v2's withdrawals and erasures reach v1 through v1's own account code before v1 serves. v2's database is copied before it is emptied, unless your decision waives the copy (BR9.7, BR9.13). [Q4]

## Arrangement health (NFR7)

- **NFR7.17** — A lapse in the runtime arrangement makes platform.isolation unavailable and opens an incident once it lasts 15 minutes. An isolation check that is unknown or stale for 15 minutes does the same. Such an incident keeps the soak from counting as clean and blocks the switch (BR3.7, BR9.2, BR9.3). [Q21]
- **NFR7.18** — The internal-disk floors of NFR8.14 keep PostgreSQL's write-ahead log from running out of room. Below the critical floor, storage admission closes and restore verifications and imports stop before the disk fills (BR6.6). [Q7, Q20, Q21]
- **NFR7.19** — A planned stop's record is valid for 14 days (BR6.12). [Q21]
  - You renew it in person before it passes, by stopping the job again through service control.
  - Every isolation check lists each record's expiry, and the operator tool shows it whenever it lists stops.
  - A lapsed record counts as an isolation lapse (NFR7.17). v2's own jobs, stopped from the installation until the soak, are renewed this way.
