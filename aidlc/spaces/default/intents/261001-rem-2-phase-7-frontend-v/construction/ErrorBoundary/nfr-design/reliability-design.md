# Reliability Design — ErrorBoundary

## NFR4.1: Error Containment
**Design**: React 16+ error boundary semantics
- Errors bubble to nearest boundary
- Ancestors/siblings unaffected
- **Test**: Inject error in deep child → only that boundary's fallback shows

## NFR4.2: Recovery via Retry
**Design**: `key` prop remount pattern
```tsx
// Parent
<ErrorBoundary key={retryKey} fallback={<ErrorBoundaryFallback onRetry={() => setRetryKey(k => k + 1)} />}>
  <JobStatus jobId={jobId} />
</ErrorBoundary>
```
- Retry increments key → React remounts subtree
- Fresh component = fresh SSE connection + fresh state

## NFR4.3: Nested Boundary Priority
**Design**: Innermost catches first
- Standard React behavior
- **Test**: Nested boundaries → inner catches, outer unaffected

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR4.1 | React error boundary bubbling |
| NFR4.2 | Key-based remount on retry |
| NFR4.3 | Standard React nesting behavior |