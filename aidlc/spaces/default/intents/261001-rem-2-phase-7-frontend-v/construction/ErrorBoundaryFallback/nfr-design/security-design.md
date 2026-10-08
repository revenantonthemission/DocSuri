# Security Design — ErrorBoundaryFallback

## NFR2.1: Safe Error Display
**Design**: Error code map → user-friendly messages
```ts
const ERROR_MESSAGES: Record<string, string> = {
  ERR_JOBSTATUS_SSE_FAILED: 'Unable to connect to job updates. Your job is still running.',
  ERR_ASSETVIEWER_LOAD_FAILED: 'Unable to load the asset. Please try again.',
  ERR_CONTENTJOBAPI_SUBMIT_FAILED: 'Failed to start the job. Please try again.',
  DEFAULT: 'Something went wrong. Please try again.',
};
```
- Unknown errors → `DEFAULT`
- Error code shown for support reference

## NFR2.2: No PII in Fallback
**Design**: Never render `error.message` or `error.stack` directly
- Only `errorCode` (non-sensitive) + mapped message
- No userId, paperId, params in UI

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR2.1 | Error code map + generic messages |
| NFR2.2 | Never render raw error, only code + mapped message |