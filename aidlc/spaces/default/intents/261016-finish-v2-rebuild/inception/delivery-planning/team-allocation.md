# Team Allocation — Finish the DocSuri v2 rebuild

Date: 2026-10-17 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild. Sources: [team assessment](../../ideation/team-formation/team-assessment.md), [mob composition](../../ideation/team-formation/mob-composition.md) (isolated checks), [bolt plan](bolt-plan.md).

## Staffing

Team formation was skipped in the approved plan (solo project); per its rule, all Bolts are executed by **aidlc-developer-agent** with supporting coding agents from this session, coordinated by the delivery lead. The human maintainer reviews and approves at every gate and checkpoint; no teams are composed and no Program Board is needed (one stream).

| Bolt | Execution | Human role |
|---|---|---|
| B06 — U5 topics & digests | aidlc-developer-agent (serial, this session) | Approve designs, plans, checkpoints, merges |
| B07 — U6 approved export | aidlc-developer-agent (serial, this session) | Same |
| B08 — U8 integration + tail | aidlc-developer-agent (serial, this session) | Same, plus production-level operating evidence review |

## Component responsibility across increments

The approved 13-component catalogue keeps authority throughout: TopicsDigests owns U5's digest state, ApprovedExport owns U6's connection/approval state, ServiceOperations owns readiness/incident/recovery records — while U8's application composition is unit-level assembly, not a new business owner. Unit completion transfers no ownership and creates no duplicate store.

## Check-in rhythm

Solo stream: check-ins are the workflow's own gates and per-unit completion checkpoints (one unit at a time, verified before the next). No additional rhythm is needed.
