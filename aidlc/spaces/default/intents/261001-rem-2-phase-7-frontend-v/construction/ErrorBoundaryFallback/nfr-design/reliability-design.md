# Reliability Design — ErrorBoundaryFallback

## NFR4.1: Reset Reliability
**Design**: Parent controls remount via `key` prop
- `ErrorBoundaryFallback` receives `reset: () => void`
- Parent: `const [retryKey, setRetryKey] = useState(0);`
- `reset = () => setRetryKey(k => k + 1)`
- **Test**: Error → fallback → retry → success

## NFR4.2: WCAG 2.1 AA Accessibility
**Design**: Semantic HTML + ARIA
```tsx
<div role="alert" className={styles.fallback}>
  <p className={styles.message}>{message}</p>
  <button onClick={reset} autoFocus className={styles.retryButton}>
    Try Again
  </button>
  {errorCode && <p className={styles.errorCode}>Error: {errorCode}</p>}
</div>
```
- `role="alert"` for screen readers
- `autoFocus` on retry button
- Color contrast: Tailwind `text-red-600` on `bg-red-50` (4.5:1)

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR4.1 | Parent key remount via reset callback |
| NFR4.2 | Semantic HTML + role="alert" + autoFocus + contrast |