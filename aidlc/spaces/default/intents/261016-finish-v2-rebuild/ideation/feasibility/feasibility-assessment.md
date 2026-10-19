# Feasibility Assessment — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Isolated run feeding the approval-handoff brief. Inputs: [intent statement](../intent-capture/intent-statement.md), [competitive analysis](../market-research/competitive-analysis.md), [market trends](../market-research/market-trends.md), [build-vs-buy](../market-research/build-vs-buy.md); answers in [feasibility-questions.md](feasibility-questions.md).

## Technical Viability

Finishing the v2 rebuild is technically viable on the existing local stack. Five of the eight approved units are already built, verified and merged on that stack; the three remaining units (U5 topics & digests, U6 approved export, U8 complete integration) reuse the approved contracts, component model and patterns those units proved. [Q1] [Q3]

The largest technical risk is U8: it is an assembly unit spanning every service and view, and its verification is only meaningful cumulatively over the whole application. It is feasible because the pieces exist, but it is the unit where hidden integration defects surface. [Q1]

No cloud services or paid accounts are involved; everything runs locally, which removes provider-side feasibility unknowns but concentrates limits on local hardware capacity. [Q6] [Q4]

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| U8 integration defects surface late | Medium | High | Cumulative whole-application verification; per-unit completion checkpoints before assembly |
| Tail redo repeats paperwork-only completion | Medium | High | Build/CI and operation stages must produce real evidence over the complete application; verification command approved before any checkpoint |
| Licensing/API restrictions tighten (per market trends) | Medium | Medium | Ingestion respects licensing; free-tier sustainability verified before dependencies rely on it |
| Local capacity limits (models, browser runs) | Low | Medium | Synthetic realms and bounded runs already proven by U1–U4 verification |
| Scope creep during parity work | Low | Medium | Product boundary fixed: no new features, $0, no unproven migration commitments |

This assessment identifies constraints and risks; it does not prove performance targets or operating capacity — later stages measure those. [intent-statement.md, Success Metrics]

## Conclusion

Feasible: the finish work continues a proven stack with fixed scope, no paid dependencies, and a solo maintainer model. The binding constraints are recorded in [constraint-register.md](constraint-register.md) and tracked in [raid-log.md](raid-log.md).
