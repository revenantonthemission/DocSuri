# RAID Log — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Isolated run feeding the approval-handoff brief. Sources: [feasibility-questions.md](feasibility-questions.md), [feasibility assessment](feasibility-assessment.md), [constraint register](constraint-register.md), [market trends](../market-research/market-trends.md).

## Risks

| ID | Risk | Likelihood | Impact | Response |
|---|---|---|---|---|
| R1 | U8 assembly surfaces cross-service integration defects late | Medium | High | Cumulative whole-application verification; per-unit checkpoints first |
| R2 | Tail evidence stages repeat paperwork-only completion | Medium | High | Real evidence required over the complete application; honest-redo is the explicit success criterion |
| R3 | Licensing/API tightening breaks ingestion or free dependencies | Medium | Medium | Verify sustainable terms before reliance; record limitations rather than silently substituting paid services |
| R4 | Local hardware capacity limits model/browser verification runs | Low | Medium | Bounded synthetic-realm runs, already proven by the built units |

## Assumptions

| ID | Assumption | Basis | Status |
|---|---|---|---|
| A1 | Local model runtimes remain viable for the assistance/translation/summary capabilities | Built units already run locally | Unvalidated for long-term availability |
| A2 | Competitor feature expectations (grounded Q&A, translation control, libraries) are stable reference points | General product knowledge, unverified | Unvalidated |
| A3 | Notion token-based integration remains available on free terms | Existing built capability | Unvalidated; verify during export work |

## Issues

| ID | Issue | Status |
|---|---|---|
| I1 | The construction verification command is unset; no unit checkpoint may verify until the human approves the exact command | Open — carried to Delivery Planning |

## Dependencies

| ID | Dependency | Affects |
|---|---|---|
| D1 | Notion token configuration and sustainable terms | U6 approved export |
| D2 | Google/ORCID identity providers reachable from the local environment | U2 account controls (already built; recheck at integration) |
| D3 | Citation/content source availability under licensing terms | U5/U6 content selection and export eligibility |
| D4 | Local model runtime availability | U5 digest generation, U8 whole-application verification |
