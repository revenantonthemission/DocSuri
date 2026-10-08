# Observability Requirements — ZoomPanControls

## NFR5.1: Interaction Analytics (Optional)
- **Target**: Track zoom/pan usage for UX optimization
- **Events**: `zoom.changed`, `pan.changed`, `reset.clicked`
- **Fields**: `zoomLevel`, `panX`, `panY`
- **Sampling**: 10% (low priority)
- **Destination**: Custom analytics (not Sentry)

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| N/A | NFR5.1 | OK |