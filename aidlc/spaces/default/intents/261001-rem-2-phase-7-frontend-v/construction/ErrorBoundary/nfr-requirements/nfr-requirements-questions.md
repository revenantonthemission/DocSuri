# NFR Requirements Questions — ErrorBoundary

## Questions

### Q1: Error Boundary Coverage
Which components must be wrapped in ErrorBoundary?
- A. JobStatus only (SSE consumer)
- B. JobStatus + AssetViewer (mandated)
- C. All Phase 7 components
- D. Entire app tree
- X. Other (please specify)

[Answer]:

### Q2: Error Sanitization Level
How much error detail should be shown to users?
- A. Generic "Something went wrong" only
- B. Error code + generic message (recommended)
- C. Full error in dev, generic in prod
- D. Full error always
- X. Other (please specify)

[Answer]:

### Q3: Sentry Integration
Should all caught errors be reported to Sentry?
- A. Yes, all errors (mandated)
- B. Only 5xx / unhandled errors
- C. Only errors with user impact
- D. Opt-in per boundary
- X. Other (please specify)

[Answer]:

### Q4: Recovery Mechanism
How should users recover from boundary errors?
- A. Retry button remounts subtree (recommended)
- B. Auto-retry after 5s
- C. Navigate to error page
- D. Show contact support link
- X. Other (please specify)

[Answer]:

### Q5: Nested Boundary Behavior
Should inner boundaries catch before outer ones?
- A. Yes, standard React behavior (recommended)
- B. No, outer should catch all
- C. Only specific error types bubble
- D. Log at all levels, show at top
- X. Other (please specify)

[Answer]:

## Traceability
| Inception NFR | Applicable |
|---------------|------------|
| NFR1 (SEC-8) | No |
| NFR2 (SEC-9) | No |
| NFR3 (SECURITY-08) | No |
| NFR4 (Idempotency) | No |
| NFR5 (Polling Fallback) | No |
| NFR6 (Error Boundary) | Yes |
| NFR7 (Sentry) | Yes |
| NFR8 (Security Review) | No |