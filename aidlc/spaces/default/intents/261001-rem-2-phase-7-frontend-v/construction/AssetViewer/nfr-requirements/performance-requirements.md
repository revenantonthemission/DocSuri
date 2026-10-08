# Performance Requirements — AssetViewer

## NFR1.1: Asset Load Latency
- **Target**: First byte of asset within 1s of request (via BFF)
- **Measurement**: `fetch` start → first response byte
- **Rationale**: PDFs/images can be large; streaming via BFF must start quickly

## NFR1.2: BFF Proxy Overhead
- **Target**: BFF adds ≤100ms overhead for asset streaming
- **Implementation**: Node.js `fetch` streaming response; no buffering
- **Rationale**: Large assets; proxy must not buffer entire file

## NFR1.3: Zoom/Pan Responsiveness
- **Target**: 60fps during zoom/pan interactions
- **Implementation**: CSS `transform` + `will-change`; GPU acceleration
- **Validation**: Chrome DevTools Performance tab — no jank frames

## NFR1.4: Bundle Size
- **Target**: AssetViewer + ZoomPanControls ≤25KB gzipped
- **Measurement**: Bundle analyzer
- **Rationale**: Heavier component due to PDF.js / image handling

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR2 (SEC-9) | NFR1.1, NFR1.2 | OK |
| NFR3 (SECURITY-08) | NFR1.1, NFR1.2 | OK |