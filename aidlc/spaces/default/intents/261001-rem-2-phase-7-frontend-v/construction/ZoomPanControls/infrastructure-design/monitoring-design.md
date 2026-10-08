# Monitoring Design — ZoomPanControls

## Optional Analytics (10% Sampling)
```ts
if (Math.random() < 0.1) {
  analytics.track('zoom.changed', { zoomLevel });
  analytics.track('pan.changed', { panX, panY });
  analytics.track('reset.clicked', {});
}
```
- Low priority, not sent to Sentry
- For UX optimization only

## Traceability
| NFR Design | Monitoring Solution |
|------------|---------------------|
| NFR5.1 (Interaction Analytics) | 10% sampled custom analytics |