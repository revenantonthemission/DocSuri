# Team Assessment — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02

---

## Recommended Team Composition

| Role | Count | Rationale |
|------|-------|-----------|
| Frontend Engineer | 2 | Core wiring work (BFF routing, JobStatus SSE, AssetViewer, idempotency, retry) |
| Backend Engineer (part-time) | 1 | Contract clarification, security review coordination |
| QA Engineer (part-time) | 1 | Test coverage verification, E2E SSE testing |
| Security Reviewer | 1 | SEC-8/SEC-9 sign-off for presigned URL removal |

**Total:** ~3.5 FTE for ~6.5 days

---

## Skill Coverage Analysis

| Skill | Required | Available | Gap | Mitigation |
|-------|----------|-----------|-----|------------|
| React 18 / Next.js 14 | Expert | Team has 2 experts | None | — |
| TypeScript | Expert | Team has 2 experts | None | — |
| SSE / EventSource | Proficient | 1 expert, 1 familiar | Minor | Pair programming on SSE integration |
| SWR / TanStack Query | Proficient | Team proficient | None | — |
| BFF / Proxy Configuration | Familiar | 1 familiar | Minor | Platform team support available |
| Security (SEC-8/SEC-9) | Aware | Security reviewer assigned | None | Review scheduled |
| Testing (RTL + Vitest) | Proficient | Team proficient | None | — |
| Accessibility (WCAG) | Aware | Could use audit | Minor | External audit if needed |

---

## Capacity Assessment

| Engineer | Current Allocation | Available for Phase 7 | Notes |
|----------|-------------------|----------------------|-------|
| Frontend Lead | 50% | 50% | Leads U1-U3, U7-U9 |
| Frontend Engineer | 100% | 100% | Leads U4-U6 |
| Backend Engineer | 80% | 20% | Contract clarification only |
| QA Engineer | 60% | 40% | Test review, E2E |
| Security Reviewer | On-demand | On-demand | Sign-off gate |

**Verdict:** Sufficient capacity. Frontend engineers can work in parallel on independent tracks (JobStatus vs AssetViewer).

---

## Risk Areas

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SSE integration complexity | Medium | High | Pair programming; dedicated spike if needed |
| Security review delay | Low | Medium | Schedule early; provide complete migration diff |
| Parallel branch merge conflicts | Low | Low | Trunk-based, small PRs, frequent merges |
| Knowledge silo (SSE) | Medium | Medium | Cross-training; shared ownership |

---

## Recommended Team Structure

```
                    ┌─────────────────────┐
                    │   Delivery Lead     │  (aidlc-delivery-agent)
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│  Frontend     │      │  Frontend     │      │  Shared       │
│  Engineer 1   │      │  Engineer 2   │      │  Resources    │
│  (JobStatus)  │      │ (AssetViewer) │      │               │
├───────────────┤      ├───────────────┤      ├───────────────┤
│ U1, U2, U3    │      │ U4            │      │ Backend (PT)  │
│ U5, U6, U7    │      │ U5 (shared)   │      │ QA (PT)       │
│ U8, U9        │      │ U5 (shared)   │      │ Security      │
└───────────────┘      └───────────────┘      └───────────────┘
```

---

## Communication Plan

| Cadence | Format | Participants | Purpose |
|---------|--------|--------------|---------|
| Daily | Standup (15 min) | Frontend 1, Frontend 2 | Sync progress, blockers |
| 2x/week | Sync (30 min) | All | Cross-track alignment, security review prep |
| End of Phase 1 | Demo | All + PO | BFF routing + JobStatus SSE working |
| End of Phase 2 | Demo | All + PO | AssetViewer + Idempotency + Retry working |
| Pre-merge | PR Review | Frontend pair + QA | Code quality, test coverage |

---

## Decision Authority

| Decision | Authority | Escalation |
|----------|-----------|------------|
| Technical approach (SSE, polling) | Frontend Lead | Delivery Lead |
| Scope changes | Product Owner | — |
| Security compliance | Security Reviewer | Delivery Lead |
| Timeline adjustments | Delivery Lead | Product Owner |

---

## Onboarding Needs

- [ ] SSE EventSource reconnection patterns documentation
- [ ] BFF proxy configuration walkthrough
- [ ] Security requirements (SEC-8/SEC-9) briefing
- [ ] Idempotency key design review
- [ ] Testing strategy alignment (80% coverage target)