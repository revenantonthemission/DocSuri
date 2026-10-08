# NFR Requirements Questions — ContentJobApi

## Questions

### Q1: BFF Proxy Latency Budget
What is the maximum acceptable overhead added by BFF proxy?
- A. ≤25ms
- B. ≤50ms (recommended)
- C. ≤100ms
- D. ≤200ms
- X. Other (please specify)

[Answer]:

### Q2: Idempotency Key Generation Time
What is the maximum acceptable time for SHA-256 hash computation?
- A. ≤2ms
- B. ≤5ms (recommended)
- C. ≤10ms
- D. ≤20ms
- X. Other (please specify)

[Answer]:

### Q3: Idempotency Key Storage TTL
How long should idempotency keys persist in localStorage?
- A. 7 days
- B. 30 days (recommended)
- C. 90 days
- D. Never expire
- X. Other (please specify)

[Answer]:

### Q4: Concurrent Submission Limit
How many concurrent job submissions should be supported?
- A. 10
- B. 50 (recommended)
- C. 100
- D. Unlimited (browser limit)
- X. Other (please specify)

[Answer]:

### Q5: Retry Policy for Network Errors
How many retries with exponential backoff for network failures?
- A. 0 (no retry)
- B. 1 retry (1s, 2s) (recommended)
- C. 2 retries (1s, 2s, 4s)
- D. 3 retries
- X. Other (please specify)

[Answer]:

### Q6: Request/Response Validation
Should all requests be validated against Zod schemas before BFF forwarding?
- A. Yes, strict validation (recommended)
- B. Yes, but warn only in dev
- C. No, trust BFF/gateway validation
- D. Validate responses only
- X. Other (please specify)

[Answer]:

## Traceability
| Inception NFR | Applicable |
|---------------|------------|
| NFR1 (SEC-8) | Yes |
| NFR2 (SEC-9) | No |
| NFR3 (SECURITY-08) | No |
| NFR4 (Idempotency) | Yes |
| NFR5 (Polling Fallback) | No |
| NFR6 (Error Boundary) | No |
| NFR7 (Sentry) | Yes |
| NFR8 (Security Review) | No |