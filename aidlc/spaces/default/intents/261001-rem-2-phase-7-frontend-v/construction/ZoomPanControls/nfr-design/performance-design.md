# Performance Design — ZoomPanControls

## NFR1.1: Interaction Latency ≤16ms (60fps)
**Design**: Direct DOM `transform` via `requestAnimationFrame`
- No React render cycle during interaction
- `useRef` for transform matrix → `element.style.transform = matrix3d(...)`
- GPU compositor handles transform

## NFR1.2: Sub-Pixel Accuracy
**Design**: Float64 matrix math
- 3x3 matrix for translate + scale
- Periodic re-normalization prevents drift

## NFR1.3: Bundle ≤8KB gzipped
**Design**: Zero dependencies
- ~50 lines matrix math
- Pointer Events (native)
- RAF loop

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR1.1 | RAF + direct DOM transform |
| NFR1.2 | Float64 matrix + re-normalization |
| NFR1.3 | Zero deps, minimal math |