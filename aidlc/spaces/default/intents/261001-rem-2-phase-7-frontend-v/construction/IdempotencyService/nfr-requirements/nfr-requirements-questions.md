# NFR Requirements Questions — IdempotencyService

## Questions

### Q1: Key Generation Algorithm
Should idempotency keys use SHA-256 as mandated?
- A. Yes, SHA-256 (mandated)
- B. SHA-1 (faster, less secure)
- C. MD5 (fastest, not cryptographically secure)
- D. Custom algorithm
- X. Other (please specify)

[Answer]:

### Q2: Key Material Composition
What should be included in the hash input?
- A. userId:paperId:taskType:params (mandated)
- B. paperId:taskType:params (no userId)
- C. userId:paperId:taskType (no params)
- D. Random UUID (non-deterministic)
- X. Other (please specify)

[Answer]:

### Q3: localStorage Key Format
Is the mandated format `idempotency:{paperId}:{taskType}` acceptable?
- A. Yes (mandated)
- B. Prefer `idempotency:{userId}:{paperId}:{taskType}`
- C. Prefer flat key with hash
- D. Use IndexedDB instead
- X. Other (please specify)

[Answer]:

### Q4: Key Expiry Duration
How long before keys are considered stale?
- A. 24 hours (server TTL)
- B. 7 days
- C. 30 days (recommended)
- D. Never expire
- X. Other (please specify)

[Answer]:

### Q5: Quota Exceeded Fallback
What to do when localStorage quota is exceeded?
- A. Purge oldest keys and retry (recommended)
- B. Use in-memory Map (session only)
- C. Throw error to user
- D. Skip idempotency for this request
- X. Other (please specify)

[Answer]:

## Traceability
| Inception NFR | Applicable |
|---------------|------------|
| NFR1 (SEC-8) | No |
| NFR2 (SEC-9) | No |
| NFR3 (SECURITY-08) | No |
| NFR4 (Idempotency) | Yes |
| NFR5 (Polling Fallback) | No |
| NFR6 (Error Boundary) | No |
| NFR7 (Sentry) | Yes |
| NFR8 (Security Review) | No |