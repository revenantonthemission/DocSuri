# Mob Composition — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02

---

## Mob Programming Approach

**Decision:** No full-time mob. Use **targeted pairing** for high-risk units, individual ownership for others.

| Unit | Approach | Participants | Rationale |
|------|----------|--------------|-----------|
| U1: BFF Routing | Individual | Frontend Eng 2 | Straightforward path updates; low risk |
| U2: JobStatus SSE | **Pair** | Frontend Lead + Frontend Eng 2 | Highest risk; SSE reconnection logic |
| U3: JobStatus Mount | Individual | Frontend Lead | Simple component placement |
| U4: AssetViewer Migration | Individual + Review | Frontend Eng 2 + Security Review | Security-critical; SEC sign-off |
| U5: Idempotency Keys | **Pair** | Frontend Lead + Frontend Eng 2 | Security-sensitive; hash design |
| U6: Inline Retry | Individual | Frontend Lead | Straightforward UX |
| U7: Polling Fallback | Individual | Frontend Eng 2 | SWR pattern; low risk |
| U8: Error Boundary | Individual | Frontend Eng 2 | Standard React pattern |
| U9: Accessibility | Individual | Frontend Eng 2 + QA | axe-core + manual testing |

---

## Pairing Schedule

```
Week 1 (Days 1-3):
  Day 1:  U1 (Eng 2 solo) + U2 kickoff (Pair)
  Day 2:  U2 continues (Pair) → U3 (Lead solo)
  Day 3:  U2 complete → U4 kickoff (Eng 2) + U5 kickoff (Pair)

Week 2 (Days 4-6):
  Day 4:  U4 continues (Eng 2) + U5 continues (Pair)
  Day 5:  U5 complete → U6 (Lead) + U7 (Eng 2)
  Day 6:  U8 (Eng 2) + U9 (Eng 2 + QA)

Week 3 (Day 7):
  Day 7:  Integration testing, security review, PR merges
```

---

## Communication Protocols

### Pair Sessions
- **Duration:** 2-3 hours max per session
- **Rotation:** Driver/navigator switch every 30-45 min
- **Breaks:** 10 min every 90 min
- **Tools:** VS Code Live Share / Tuple / screen share

### Async Coordination
- **Slack:** #phase7-frontend-wiring (dedicated channel)
- **PRs:** Draft PRs opened early for continuous feedback
- **Standup:** 9:30 AM daily (15 min) — blockers only
- **Retro:** End of each week (30 min)

---

## Knowledge Sharing Artifacts

| Artifact | Owner | Due | Audience |
|----------|-------|-----|----------|
| SSE integration guide | Frontend Lead | End of U2 | Team |
| AssetViewer migration notes | Frontend Eng 2 | End of U4 | Team + Security |
| Idempotency key design doc | Frontend Lead | End of U5 | Team + Security |
| Testing patterns (SSE, polling) | QA + Frontend | End of U7 | Team |
| Accessibility checklist | Frontend Eng 2 + QA | End of U9 | Team |

---

## Escalation Path

| Issue | First Responder | Escalation |
|-------|-----------------|------------|
| Technical blocker (SSE) | Frontend Lead | Delivery Lead → Backend |
| Security concern | Security Reviewer | Delivery Lead → CISO |
| Scope creep | Product Owner | Delivery Lead |
| Timeline risk | Delivery Lead | Product Owner |
| Merge conflict | Both Frontend | Delivery Lead |

---

## Definition of Done (Team Level)

- [ ] All PRs approved by at least one other engineer
- [ ] All tests pass (unit + integration + E2E)
- [ ] 80% coverage on new code
- [ ] Lint + typecheck clean
- [ ] Security sign-off for U4
- [ ] Accessibility audit for U9
- [ ] Documentation updated (README, API docs)
- [ ] No TODOs/FIXMEs in merged code