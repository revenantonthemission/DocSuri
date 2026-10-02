# Stakeholder Map — Phase 7 Frontend Wiring

## Primary Stakeholders

| Role | Name | Interest | Influence |
|------|------|----------|-----------|
| Product Owner | — | Acceptance of user-facing job flow | High |
| Frontend Lead | — | Component architecture, SSE integration | High |
| Backend Lead | — | API contract stability, BFF routing | High |
| Security Reviewer | — | SEC-8/SEC-9 compliance, no presigned URLs | High |
| QA Lead | — | Test coverage, SSE reconnection scenarios | Medium |

## Technical Owners

| Component | Owner | Notes |
|-----------|-------|-------|
| `contentJobApi.ts` | Frontend | API client, needs BFF routing |
| `JobStatus.tsx` | Frontend | SSE consumer, needs mounting |
| `AssetViewer.tsx` | Frontend | Must switch to same-origin delivery |
| `DetailPage` / `PaperView` | Frontend | Mount points for JobStatus/AssetViewer |
| `/bff` proxy | Backend | Routes content-job calls |
| `ContentJobService` | Backend | Already implemented |
| SSE endpoint | Backend | Already implemented with `Last-Event-ID` |

## External Dependencies

| Dependency | Version | Notes |
|------------|---------|-------|
| React 18 | ^18.2 | Suspense for SSE fallback |
| SWR / TanStack Query | Latest | For polling fallback if SSE fails |
| Next.js 14 | ^14.2 | App router, BFF proxy config |

## Decision Makers

- **Frontend Architecture**: Frontend Lead
- **API Contract Changes**: Backend Lead (must approve any contract changes)
- **Security Compliance**: Security Reviewer (must sign off on presigned URL removal)
- **Release Decision**: Product Owner