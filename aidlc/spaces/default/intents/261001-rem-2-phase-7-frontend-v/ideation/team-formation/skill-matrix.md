# Skill Matrix — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02

---

## Technical Skills

| Skill | Frontend Lead | Frontend Eng 2 | Backend (PT) | QA (PT) | Security |
|-------|---------------|----------------|--------------|---------|----------|
| **React 18** | ⭐⭐⭐ Expert | ⭐⭐⭐ Expert | — | ⭐⭐ Proficient | — |
| **Next.js 14 App Router** | ⭐⭐⭐ Expert | ⭐⭐⭐ Expert | — | ⭐⭐ Proficient | — |
| **TypeScript** | ⭐⭐⭐ Expert | ⭐⭐⭐ Expert | ⭐⭐ Proficient | ⭐⭐ Proficient | — |
| **SSE / EventSource** | ⭐⭐⭐ Expert | ⭐⭐ Proficient | ⭐⭐ Proficient | ⭐ Aware | — |
| **SWR / TanStack Query** | ⭐⭐⭐ Expert | ⭐⭐⭐ Expert | — | ⭐⭐ Proficient | — |
| **BFF / Proxy Config** | ⭐⭐ Proficient | ⭐ Aware | ⭐⭐⭐ Expert | — | — |
| **Web Crypto API (hashing)** | ⭐⭐ Proficient | ⭐⭐ Proficient | — | — | — |
| **localStorage / Session Mgmt** | ⭐⭐⭐ Expert | ⭐⭐⭐ Expert | — | — | — |
| **React Error Boundaries** | ⭐⭐⭐ Expert | ⭐⭐ Proficient | — | — | — |
| **Accessibility (WCAG 2.1)** | ⭐⭐ Proficient | ⭐ Aware | — | ⭐⭐ Proficient | — |
| **Testing (RTL + Vitest)** | ⭐⭐⭐ Expert | ⭐⭐⭐ Expert | — | ⭐⭐⭐ Expert | — |
| **E2E Testing (Playwright)** | ⭐⭐ Proficient | ⭐⭐ Proficient | — | ⭐⭐⭐ Expert | — |
| **Security (SEC-8/SEC-9)** | ⭐ Aware | ⭐ Aware | ⭐⭐ Proficient | — | ⭐⭐⭐ Expert |
| **Git / Trunk-based Dev** | ⭐⭐⭐ Expert | ⭐⭐⭐ Expert | ⭐⭐⭐ Expert | ⭐⭐ Proficient | — |
| **CI/CD (GitHub Actions)** | ⭐⭐ Proficient | ⭐⭐ Proficient | ⭐⭐⭐ Expert | ⭐⭐ Proficient | — |

---

## Domain Knowledge

| Domain | Frontend Lead | Frontend Eng 2 | Backend (PT) | QA (PT) | Security |
|--------|---------------|----------------|--------------|---------|----------|
| **Content Job Contract** | ⭐⭐ Proficient | ⭐ Aware | ⭐⭐⭐ Expert | ⭐ Aware | ⭐ Aware |
| **Job State Machine** | ⭐⭐ Proficient | ⭐ Aware | ⭐⭐⭐ Expert | — | — |
| **SSE Event Format** | ⭐⭐⭐ Expert | ⭐⭐ Proficient | ⭐⭐ Proficient | — | — |
| **Asset Delivery Flow** | ⭐⭐ Proficient | ⭐⭐ Proficient | ⭐⭐⭐ Expert | — | ⭐⭐ Proficient |
| **Idempotency Patterns** | ⭐⭐ Proficient | ⭐⭐ Proficient | ⭐⭐ Proficient | — | — |
| **Presigned URL Migration** | ⭐⭐ Proficient | ⭐⭐ Proficient | ⭐⭐ Proficient | — | ⭐⭐⭐ Expert |

---

## Soft Skills & Process

| Skill | Frontend Lead | Frontend Eng 2 | Backend (PT) | QA (PT) | Security |
|-------|---------------|----------------|--------------|---------|----------|
| **Pair Programming** | ⭐⭐⭐ Expert | ⭐⭐ Proficient | — | — | — |
| **Code Review** | ⭐⭐⭐ Expert | ⭐⭐⭐ Expert | ⭐⭐ Proficient | ⭐⭐ Proficient | ⭐⭐ Proficient |
| **Mentoring** | ⭐⭐⭐ Expert | ⭐⭐ Proficient | — | — | — |
| **Cross-team Communication** | ⭐⭐⭐ Expert | ⭐⭐ Proficient | ⭐⭐ Proficient | ⭐⭐ Proficient | ⭐⭐ Proficient |
| **Incident Response** | ⭐⭐ Proficient | ⭐ Aware | ⭐⭐ Proficient | ⭐⭐ Proficient | ⭐⭐⭐ Expert |

---

## Skill Gaps & Development Plan

| Gap | Owner | Priority | Plan |
|-----|-------|----------|------|
| SSE reconnection edge cases | Frontend Eng 2 | High | Pair with Lead on U2; spike if needed |
| Security compliance depth | Both Frontend | Medium | Security reviewer briefing; review SEC-8/SEC-9 docs |
| Accessibility testing | Frontend Eng 2 | Low | axe-core integration; manual testing with screen reader |
| E2E SSE test patterns | Frontend Lead | Medium | Research Playwright SSE testing; document patterns |

---

## Cross-Training Opportunities

| Skill | Teacher | Learner | Timeline |
|-------|---------|---------|----------|
| SSE EventSource deep dive | Frontend Lead | Frontend Eng 2 | Week 1 (during U2) |
| BFF proxy internals | Backend (PT) | Both Frontend | Week 1 (during U1) |
| Security review process | Security | Both Frontend | Week 1 (pre-migration) |
| Playwright E2E for SSE | QA (PT) | Both Frontend | Week 2 (during U7) |
| Idempotency design patterns | Frontend Lead | Frontend Eng 2 | Week 2 (during U5) |

---

## Staffing Recommendation

**Current team is sufficient** for Phase 7 feature scope. No additional hiring needed.

**Recommended pairing:**
- Frontend Lead + Frontend Eng 2 pair on U2 (SSE integration) — highest risk
- Frontend Eng 2 owns U4 (AssetViewer) with Lead review
- Both collaborate on U5 (idempotency) and U6 (retry)
- QA joins for U7-U9 testing phase
- Security reviewer engaged early for U4 sign-off