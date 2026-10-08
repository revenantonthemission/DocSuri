# Observability Design — ZoomPanControls

## NFR5.1: Interaction Analytics (Optional, 10% Sampling)
**Design**: Low-priority custom analytics
```ts
const track = (event: string, data: object) => {
  if (Math.random() < 0.1) analytics.track(event, data);
};
// Usage:
track('zoom.changed', { zoomLevel });
track('pan.changed', { panX, panY });
track('reset.clicked', {});
```
- Not sent to Sentry (not errors)
- 10% sampling for UX optimization

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR5.1 | 10% sampled custom analytics |