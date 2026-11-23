<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-10-21T16:56:03Z [unit u8-service-operations-integration] — The reopened design carried values no earlier answer set (critical floor, WAL maximum, backup floor, staging and import backstops, the agent's minimum disposal, the isolation check's timing and retention, the stop-record bound, runtime sources, accounts, labels, folders and ports), so they became follow-up questions Q20–Q24 with proposed values instead of being decided silently in the NFR files.
- 2026-10-21T16:56:03Z [unit u8-service-operations-integration] — Measured sizes replaced the earlier estimates: v1's database is 0.23 GB and its search index 11 MB, so v2's databases are small, and the internal-disk threshold Q7 set mostly protects the Mac itself; the 25 GB object store, which the earlier questions treated as the dominant copy, is on the external drive and only its migrated objects are copied (Q6).

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->
- 2026-10-21T17:45:00Z [unit u8-service-operations-integration] — Q25 A named four private folders, but the first review showed that database, tunnel and scheduler logs and the scheduler's and backup agent's credentials would sit outside that list, so Time Machine excludes `/Library/DocSuri/` as a whole. Everything else in that tree is reproduced by the installation, so nothing worth backing up is lost; the change is surfaced at the gate.
- 2026-10-21T17:45:00Z [unit u8-service-operations-integration] — The inception requirements name no availability, performance or monitoring NFR, so those requirements form derived groups NFR7–NFR9 from FR4.1 and FR4.2, and the children of NFR1, NFR3 and NFR4 that implement design rules rather than the upstream text are listed as derived in the trace instead of being counted as coverage.

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
- 2026-10-21T16:56:03Z [unit u8-service-operations-integration] — The internal disk read 11.7 GiB free on 2026-10-22 against 39 GiB the day before, with 82 GiB more held as reclaimable (mostly Time Machine's hourly local snapshots), so the disk checks need a stated reading (Q20); the cause of the drop was not traced beyond that.
- 2026-10-21T16:56:03Z [unit u8-service-operations-integration] — v1's object store, its own database dumps and the 2026-10-10 archive sit on the unencrypted, ownership-ignoring SSD01 volume, which cannot give BR9.12's operator-only reading of v1's stores; where they live is asked as Q24.
