# NFR Requirements Questions — JobStatus

## Questions

### Q1: SSE Connection Latency Target
What is the maximum acceptable latency for SSE connection establishment?
- A. ≤200ms
- B. ≤500ms (recommended)
- C. ≤1s
- D. ≤2s
- X. Other (please specify)

[Answer]:

### Q2: Status Update Propagation Target
What is the maximum acceptable delay from gateway emission to UI render?
- A. ≤50ms
- B. ≤100ms (recommended)
- C. ≤200ms
- D. ≤500ms
- X. Other (please specify)

[Answer]:

### Q3: Polling Fallback Interval
What SWR polling interval should be used when SSE fails?
- A. 1s
- B. 2s (mandated)
- C. 5s
- D. 10s
- X. Other (please specify)

[Answer]:

### Q4: Concurrent Job Monitoring Limit
How many concurrent jobs should JobStatus support without degradation?
- A. 5
- B. 10 (recommended)
- C. 20
- D. 50
- X. Other (please specify)

[Answer]:

### Q5: Bundle Size Budget
What is the maximum gzipped size for JobStatus + dependencies?
- A. ≤10KB
- B. ≤15KB (recommended)
- C. ≤25KB
- D. ≤50KB
- X. Other (please specify)

[Answer]:

### Q6: Error Boundary Fallback UX
What should the ErrorBoundary fallback show for JobStatus errors?
- A. Generic "Something went wrong" + retry button
- B. Error code + retry button + timestamp
- C. Full error message (dev) / generic (prod) + retry
- D. Custom per error type
- X. Other (please specify)

[Answer]:

### Q7: Sentry Integration Scope
What Sentry context should be captured for JobStatus errors?
- A. Error only
- B. Error + component stack + jobId (recommended)
- C. Error + full Redux state
- D. Error + user session data
- X. Other (please specify)

[Answer]:

## Traceability
| Inception NFR | Applicable |
|---------------|------------|
| NFR1 (SEC-8) | No |
| NFR2 (SEC-9) | No |
| NFR3 (SECURITY-08) | No |
| NFR4 (Idempotency) | No |
| NFR5 (Polling Fallback) | Yes |
| NFR6 (Error Boundary) | Yes |
| NFR7 (Sentry) | Yes |
| NFR8 (Security Review) | No |