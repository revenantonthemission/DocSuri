# NFR Requirements Summary — Phase 7 Frontend Wiring

## Consolidated NFR Coverage

### Units & Inception NFR Mapping

| Unit | NFR1 (SEC-8) | NFR2 (SEC-9) | NFR3 (SECURITY-08) | NFR4 (Idempotency) | NFR5 (Polling) | NFR6 (Error Boundary) | NFR7 (Sentry) | NFR8 (Sec Review) |
|------|--------------|--------------|--------------------|--------------------|----------------|----------------------|---------------|-------------------|
| JobStatus | | | | | ✅ | ✅ | ✅ | |
| ContentJobApi | ✅ | | | ✅ | | | ✅ | |
| IdempotencyService | | | | ✅ | | | ✅ | |
| AssetViewer | | ✅ | ✅ | | | ✅ | ✅ | ✅ |
| ErrorBoundary | | | | | | ✅ | ✅ | |
| ErrorBoundaryFallback | | | | | | ✅ | ✅ | |
| ZoomPanControls | | | | | | ✅ | | |

### Key Decisions Confirmed

1. **BFF Routing (SEC-8)**: All content-job API calls route through `/bff/api/content-jobs/*` — ContentJobApi enforces this
2. **Same-Origin Assets (SECURITY-08)**: AssetViewer uses `/bff/api/papers/{paperId}/assets/{assetId}` — no presigned URLs
3. **Auth Re-Check (SEC-9)**: Gateway validates auth on every asset request via BFF cookie forwarding
4. **Idempotency Keys**: SHA-256 of `userId:paperId:taskType:params` stored in localStorage
5. **Polling Fallback**: SWR 2s fixed interval when SSE fails (JobStatus)
6. **Error Boundaries**: Class component wrapping JobStatus + AssetViewer; ErrorBoundaryFallback for UI
7. **Sentry**: @sentry/nextjs integrated in ErrorBoundary; all caught errors reported
8. **Security Review**: Week 2 gate for AssetViewer migration

### Artifacts Generated (42 + 6 questions = 48 files)

Per unit (7 artifacts × 6 units = 42):
- performance-requirements.md
- security-requirements.md
- scalability-requirements.md
- reliability-requirements.md
- observability-requirements.md
- tech-stack-decisions.md
- traceability.json

Plus questions files (6):
- nfr-requirements-questions.md per unit

## Summary Confirmation

**Do you approve these NFR Requirements and want to proceed to NFR Design stage?**

- A. **Approve** — Proceed to NFR Design
- B. **Request Changes** — Specify what should change

[Answer]: