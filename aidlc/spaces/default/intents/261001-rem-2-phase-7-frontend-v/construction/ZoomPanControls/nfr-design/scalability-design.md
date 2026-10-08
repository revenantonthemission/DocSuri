# Scalability Design — ZoomPanControls

## NFR3.1: Multiple Instances
**Design**: Independent state per instance
- `useRef` per component instance
- No shared globals
- Memory: ~1KB/instance

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR3.1 | Per-instance useRef state |