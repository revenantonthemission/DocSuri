# Finish the DocSuri v2 rebuild — Scope document

Date: 2026-10-16 (Asia/Seoul)
Isolated run feeding the approval-handoff brief. Basis: confirmed answers in [scope-definition-questions.md](scope-definition-questions.md); [intent statement](../intent-capture/intent-statement.md); [feasibility assessment](../feasibility/feasibility-assessment.md); [constraint register](../feasibility/constraint-register.md).

## Objective and audience

Finish the interrupted v2 rebuild: build U5 (topics & digests), U6 (approved export) and U8 (complete service integration), then redo build/CI and the seven operation stages honestly over the complete application. The audience is the sole maintainer, working with coding agents. [Q1] [intent-statement.md]

## Scope boundary

| In scope for the finish release | Completion evidence |
| --- | --- |
| Build the three missing units to the approved capability bar | Each unit implemented, real-integration verified, merged to develop |
| Assemble the complete application (U8) | Cumulative whole-application verification, not per-unit checks alone |
| Redo the tail evidence honestly | Build/CI and the seven operation stages produce evidence over the complete application |
| Operate at production level | The finished service runs continuously on this machine as the maintainer's real daily service, with real accounts and real papers; operation-stage evidence (deployment, observability, incident runbooks, performance) honestly covers that real operating mode [Q6] |
| Retain every current capability | Full parity with all eight approved units' capabilities; nothing silently dropped [Q2] |

| Outside this release boundary | Treatment |
| --- | --- |
| New product feature expansion | Excluded — no new features beyond parity [Q2] |
| Paid services, APIs or subscriptions | Excluded under the $0 constraint [constraint-register C-01] |
| Unproven data-migration or continuity commitments | Excluded beyond what evidence supports [intent-statement.md] |
| A reduced-feature release | Excluded — nothing smaller satisfies the intent [Q1] |

## Value stream

The parity bar covers the integrated paper journey — find, understand, save, revisit — plus the surrounding capabilities: topics & digests, approved export, and the assembled whole. Synthetic verification realms remain the test method; the finished service must additionally operate on real data at production level. [Q1] [Q2] [Q6]

## Success and release acceptance

| Outcome | Required evidence |
| --- | --- |
| All eight units merged | Every unit built, verified, merged to develop |
| Whole-application verification | The complete application verified as one experience |
| Honest tail evidence | Real build/CI/operation evidence over the complete application, including the real operating mode [Q6] |
| Regression safety | Existing test suites stay green |
| $0 operation | Sustainable free/local operation with no paid fallback |

## Assumptions & Open Questions

- "Production level" is defined by Q6's answer B (real daily service + honest operation evidence for that mode); concrete numeric targets are not set by this document. [Q6]
- The construction verification command remains unset; its approval is a mandatory human stop before any unit checkpoint verifies. [constraint-register C-10]
