# NFR Requirements Questions — AssetViewer

## Questions

### Q1: Asset Delivery Method (SECURITY-08)
Must ALL assets be delivered via same-origin BFF endpoint (no presigned URLs)?
- A. Yes, strict same-origin only (mandated)
- B. Allow presigned URLs for large assets (>50MB)
- C. Hybrid: BFF for auth, presigned for delivery
- D. Presigned URLs with short TTL
- X. Other (please specify)

[Answer]:

### Q2: Auth Re-Check at Delivery Time (SEC-9)
Must gateway re-validate auth on EVERY asset request?
- A. Yes, every request (mandated)
- B. Cache auth decision for 5 min
- C. Cache auth decision for 1 hour
- D. Trust BFF auth only
- X. Other (please specify)

[Answer]:

### Q3: Maximum Asset Size for Streaming
What is the maximum asset size that must stream without buffering?
- A. 10MB
- B. 50MB
- C. 100MB (recommended)
- D. 500MB
- X. Other (please specify)

[Answer]:

### Q4: PDF.js Worker Strategy
How should PDF.js worker be managed?
- A. Single shared worker (recommended)
- B. Per-instance worker
- C. Lazy-load on first PDF
- D. Preload at app start
- X. Other (please specify)

[Answer]:

### Q5: Security Review Timeline (NFR8)
When should the AssetViewer security review occur?
- A. Week 1 (before Code Generation)
- B. Week 2 (mid-implementation, mandated)
- C. Week 3 (before Build and Test)
- D. Post-launch
- X. Other (please specify)

[Answer]:

### Q6: Range Request Support
Should BFF proxy support HTTP Range requests for resume?
- A. Yes, full Range support (recommended)
- B. Yes, but only for video
- C. No, not needed
- D. Defer to gateway
- X. Other (please specify)

[Answer]:

## Traceability
| Inception NFR | Applicable |
|---------------|------------|
| NFR1 (SEC-8) | Indirect |
| NFR2 (SEC-9) | Yes |
| NFR3 (SECURITY-08) | Yes |
| NFR4 (Idempotency) | No |
| NFR5 (Polling Fallback) | No |
| NFR6 (Error Boundary) | Yes |
| NFR7 (Sentry) | Yes |
| NFR8 (Security Review) | Yes |