# External Dependency Map — Finish the DocSuri v2 rebuild

Date: 2026-10-17 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild. Sources: [feasibility RAID](../../ideation/feasibility/raid-log.md) (isolated check), [delivery-planning-questions.md](delivery-planning-questions.md) Q5, [bolt plan](bolt-plan.md).

| Dependency | Owner | Affects | Lead time / when needed | If it slips |
|---|---|---|---|---|
| Notion token configuration and sustainable free terms | Maintainer (token); terms by Notion | B07 (U6 export effect and reconciliation evidence) | Needed before B07's real-export demo | Halt B07's external-effect work at its checkpoint; bring a human scope decision (alternative destination or recorded limitation) — never silently substitute a paid path |
| Content-source licensing terms for digest selection | Source providers; checked by agents | B06 (U5 content selection eligibility) | Needed before B06's digest-content demo | Restrict digest content to licensed/eligible sources and record the limitation; human decision if parity is affected |
| Local model availability (runtimes, capacity) | Maintainer environment | B06 (digest generation), B08 (whole-application verification) | Ongoing; checked before verification runs | Halt and ask; pin/downgrade runtimes per the recorded recovery pattern (one-symlink revert) rather than improvising |
| Human-approved construction verification command | Maintainer | Every unit completion checkpoint | Before the first checkpoint runs verification | Checkpoints cannot verify; the exact command is presented then (deferred by choice, per Q7) |
| Maintainer review time at gates and checkpoints | Maintainer | All Bolts | Continuous | Work waits; the plan has no deadline (constraint C-09) |
| Google/ORCID reachability | Providers | Built U2 recheck at U8 integration | Before B08 cumulative verification | Record degraded identity evidence; human decision if cumulative verification cannot proceed |

Fully internal (no external dependency): U5's persistence/scheduling machinery, U6's approval/invalidation logic, U8's assembly code and contract checks.
