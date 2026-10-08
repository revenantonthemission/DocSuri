# Security Requirements — ErrorBoundary

## NFR2.1: Error Sanitization (NFR6)
- **Requirement**: Error messages displayed to user must not leak stack traces, file paths, or internal details
- **Implementation**: 
  - `componentDidCatch(error, info)` extracts user-safe message
  - Production: show generic "Something went wrong" + error code
  - Development: show full error (via `process.env.NODE_ENV`)
- **Validation**: Security review of fallback UI output

## NFR2.2: Sentry Integration (NFR7)
- **Requirement**: All caught errors reported to Sentry with context
- **Implementation**: 
  ```ts
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    Sentry.captureException(error, {
      extra: { componentStack: info.componentStack, boundary: 'ErrorBoundary' },
      tags: { errorBoundary: true }
    });
    this.setState({ error, errorInfo: info });
  }
  ```
- **Data**: No PII in error context; only component stack + error message

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR2.1 | OK |
| NFR7 (Sentry) | NFR2.2 | OK |