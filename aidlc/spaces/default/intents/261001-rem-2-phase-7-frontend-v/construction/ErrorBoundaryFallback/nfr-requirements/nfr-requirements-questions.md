# NFR Requirements Questions — ErrorBoundaryFallback

## Questions

### Q1: Fallback Variants Needed
What fallback UI variants are required?
- A. Inline (within component) only
- B. Inline + Page-level + Modal (recommended)
- C. Page-level only
- D. Single universal fallback
- X. Other (please specify)

[Answer]:

### Q2: Error Code Display
Should technical error codes be shown to users?
- A. Yes, for support reference (recommended)
- B. No, only user-friendly message
- C. Only in development
- D. Copy-to-clipboard button for error code
- X. Other (please specify)

[Answer]:

### Q3: Accessibility Requirements
What WCAG level must fallback meet?
- A. WCAG 2.1 AA (recommended)
- B. WCAG 2.1 AAA
- C. WCAG 2.0 AA
- D. Basic semantic HTML only
- X. Other (please specify)

[Answer]:

### Q4: Retry Analytics
Should retry attempts be tracked?
- A. Yes, Sentry + custom analytics (recommended)
- B. Sentry only
- C. Custom analytics only
- D. No tracking
- X. Other (please specify)

[Answer]:

### Q5: Dismiss Action
Should users be able to dismiss (not retry) errors?
- A. Yes, dismiss button + retry
- B. Retry only (mandated recovery)
- C. Dismiss navigates away
- D. Auto-dismiss after 30s
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