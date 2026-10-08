# Security Requirements — ErrorBoundaryFallback

## NFR2.1: Safe Error Display (NFR6)
- **Requirement**: Never render raw error.message or error.stack
- **Implementation**: 
  - Predefined error codes map to user-friendly messages
  - Unknown errors show generic "Something went wrong"
  - Error code (e.g., `ERR_JOBSTATUS_SSE_FAILED`) shown for support reference

## NFR2.2: No PII in Fallback
- **Requirement**: Fallback UI never displays user IDs, paper IDs, or sensitive params
- **Validation**: Code review of fallback component

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR2.1, NFR2.2 | OK |