# Finish the DocSuri v2 rebuild — Intent statement

Date: 2026-10-16 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild

## Problem Statement

The previous v2 rebuild workflow closed early: of the eight approved units, U1 (integrated paper journey), U7 (controlled platform protocols), U2 (account and personal controls), U3 (paper and corpus capabilities) and U4 (research and novelty) were built, while U5 (topics and digests), U6 (approved export) and U8 (complete service integration) were never started. The build/CI and operation stages recorded after U4 document that unit only, so the recorded release evidence does not describe the finished application. This work finishes the recorded plan: build the three missing units and redo build/CI and the seven operation stages honestly over the finished application. [Q1] [Q4] [desc]

## Target Customer

You, the sole maintainer, benefit first: a complete, comprehensible codebase in which every planned v2 capability actually exists and the release evidence can be trusted. [Q2]

## Success Metrics

| Dimension | Outcome to evaluate | Source |
|---|---|---|
| Unit completion | All eight planned units built and merged to develop. | [Q3] |
| Whole-application verification | The complete application verified as one experience. | [Q3] |
| Honest tail evidence | Build, CI and the seven operation stages produce evidence over the complete application, not over one unit. | [Q1] [Q3] |
| Regression safety | Existing test suites stay green. | [Q3] |

## Initiative Trigger

The previous workflow closed early with three units missing and paperwork-only tail stages; it should be finished properly before the service is used. [Q4]

## Initial Scope Signal

**Workflow-selected scope:** `express` — this identifies the selected development process (the custom plan `docsuri-v2-finish` on the express base), not a product feature boundary. [scope]

**User-confirmed product boundary:** no new product features beyond current capability parity; no paid services, subscriptions or billable APIs; no data-migration or continuity commitments beyond what the evidence supports. [Q7] [memory:M1]

**User-confirmed decision authority:** you alone decide scope and priority as the one human maintainer; coding agents do the work; there are no other approval roles. [Q5]

## Assumptions & Open Questions

None.
