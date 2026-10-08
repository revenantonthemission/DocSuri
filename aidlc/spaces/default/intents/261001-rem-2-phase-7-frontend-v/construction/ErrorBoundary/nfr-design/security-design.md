# Security Design — ErrorBoundary

## NFR2.1: Error Sanitization
**Design**: Production vs Development error display
```ts
componentDidCatch(error, info) {
  const isDev = process.env.NODE_ENV === 'development';
  const userMessage = isDev ? error.message : 'Something went wrong';
  const errorCode = this.props.boundaryName ? `ERR_${this.props.boundaryName.toUpperCase()}` : 'ERR_UNKNOWN';
  
  Sentry.captureException(error, {
    extra: { componentStack: info.componentStack, boundary: this.props.boundaryName },
    tags: { errorBoundary: true }
  });
  
  this.setState({ error, errorInfo: info, userMessage, errorCode });
}
```
- **Production**: Generic message + error code only
- **Development**: Full error + component stack

## NFR2.2: Sentry Integration
**Design**: `@sentry/nextjs` in `ErrorBoundary.componentDidCatch`
- Automatic source map upload via Next.js build
- Error grouping by component stack
- No PII in context

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR2.1 | Env-based sanitization + error codes |
| NFR2.2 | Sentry captureException in componentDidCatch |