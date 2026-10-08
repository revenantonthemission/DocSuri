# Decision Log — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02

---

## Ideation Phase Decisions

| Stage | Decision Point | Choice | Rationale | Date |
|-------|---------------|--------|-----------|------|
| Intent Capture | BFF Routing | Route all calls through `/bff/api/content-jobs/*` | SEC-8 compliance mandatory | 2026-10-01 |
| Intent Capture | SSE Fallback | Implement 2s fixed polling fallback | Resilient UX, simpler than exponential backoff | 2026-10-01 |
| Intent Capture | AssetViewer Migration | Migrate to same-origin delivery | SEC-9 compliance, SECURITY-08 fix | 2026-10-01 |
| Intent Capture | JobStatus Mount | Detail page only (below action buttons) | Proximity to trigger actions | 2026-10-01 |
| Intent Capture | Idempotency Key | Hash(userId+paperId+task+params) | Deterministic, survives page reload | 2026-10-01 |
| Intent Capture | Error UX | Inline "Retry" button | Re-submits with same idempotency key | 2026-10-01 |
| Intent Capture | Asset Cache | 60s private cache acceptable | Backend controls freshness via auth re-check | 2026-10-01 |
| Market Research | Skipped | Internal wiring task | No external market positioning or build-vs-buy | 2026-10-02 |
| Feasibility | SSE Fallback Strategy | Fixed 2s polling interval | Simpler, predictable server load | 2026-10-02 |
| Feasibility | Idempotency Storage | localStorage | Survives page reload, cleared on explicit action | 2026-10-02 |
| Feasibility | Asset Cache Policy | 60s private cache sufficient | Backend auth re-check controls freshness | 2026-10-02 |
| Feasibility | Error Boundary | Wrap JobStatus | Preserve last SSE state on error | 2026-10-02 |
| Scope Definition | Minimum Viable Scope | Full scope + observability | All 6 success criteria + SSE metrics | 2026-10-02 |
| Scope Definition | MoSCoW Prioritization | Must: SSE, Retry; Should: BFF, Last-Event-ID, AssetViewer, Idempotency; Could: Polling, Cache headers | Security Must, resilience Should, polish Could | 2026-10-02 |
| Scope Definition | Sequencing Strategy | Risk-first (SSE → AssetViewer → BFF → Polish) | Mitigate highest technical risk first | 2026-10-02 |
| Scope Definition | NFRs in Scope | Performance (80% coverage, lint/typecheck) | Org standard for feature scope | 2026-10-02 |
| Scope Definition | Out-of-Scope | All confirmed out | Novelty workers, novelty SSE, cancellation, history, mobile, batch | 2026-10-02 |
| Team Formation | Team Composition | 2 FE, 1 BE PT, 1 QA PT, 1 Security | Matches available resources | 2026-10-02 |
| Team Formation | Pairing Strategy | Targeted pairing (U2 SSE, U5 idempotency) | High-risk units only | 2026-10-02 |
| Team Formation | Security Review Timing | Mid (Week 2, after U4) | Review implementation after AssetViewer complete | 2026-10-02 |
| Team Formation | Cross-Training Priority | Playwright E2E first | QA teaches SSE testing patterns | 2026-10-02 |
| Team Formation | Timeline Confidence | Yes, confident (6.5 days) | Team velocity supports estimate | 2026-10-02 |
| Rough Mockups | JobStatus Visual | Progress bar + state + live indicator + dismiss | Complete UX as designed | 2026-10-02 |
| Rough Mockups | JobStatus Mount | Below action buttons | Directly under Summarize/Translate | 2026-10-02 |
| Rough Mockups | Failed State UX | Inline Retry + error details expandable | User control + debugging | 2026-10-02 |
| Rough Mockups | AssetViewer Visual | Direct img src + zoom/pan controls | Large figures/tables need zoom | 2026-10-02 |
| Rough Mockups | Error Boundary | Preserve last SSE state | Graceful degradation | 2026-10-02 |
| Rough Mockups | Accessibility | ARIA live + progressbar | Covers screen readers adequately | 2026-10-02 |
| Rough Mockups | Responsive | 3 breakpoints (Mobile/Tablet/Desktop) | Standard responsive approach | 2026-10-02 |

---

## Inception Phase Decisions (To Be Made)

| Stage | Decision Point | Status |
|-------|---------------|--------|
| Reverse Engineering | Codebase scan scope | Pending |
| Practices Discovery | Team practices affirmation | Pending |
| Requirements Analysis | FR/NFR/Constraint finalization | Pending |
| User Stories | Story format & acceptance criteria | Pending |
| Refined Mockups | High-fidelity designs | Pending |
| Domain Design | Entity relationships, aggregates | Pending |
| Units Generation | Unit decomposition from backlog | Pending |
| Contract Design | API contracts, DTOs, events | Pending |
| Delivery Planning | Bolt sequencing, sprint plan | Pending |

---

## Construction Phase Decisions (To Be Made)

| Stage | Decision Point | Status |
|-------|---------------|--------|
| Functional Design | Component specs, business logic | Pending |
| NFR Requirements | Performance, security, reliability targets | Pending |
| NFR Design | Patterns, implementations | Pending |
| Infrastructure Design | Deployment topology, config | Pending |
| Code Generation | Implementation approach per unit | Pending |
| Build & Test | Test strategy execution | Pending |
| CI Pipeline | Pipeline configuration | Pending |

---

## Operation Phase Decisions (To Be Made)

| Stage | Decision Point | Status |
|-------|---------------|--------|
| Deployment Pipeline | Strategy, environments | Pending |
| Environment Provisioning | Infrastructure as code | Pending |
| Deployment Execution | Release process | Pending |
| Observability Setup | Metrics, logs, traces | Pending |
| Incident Response | Runbooks, escalation | Pending |
| Performance Validation | Load testing, benchmarks | Pending |
| Feedback & Optimization | Continuous improvement | Pending |