# Scalability Requirements — AssetViewer

## NFR3.1: Concurrent Asset Views
- **Target**: Support 5 concurrent AssetViewer instances (different assets)
- **Implementation**: Each instance independent `fetch` / `<img>` / `<iframe>` / PDF.js
- **Browser Limit**: 6 connections/hostname (HTTP/2 multiplexing helps)

## NFR3.2: Large Asset Streaming
- **Target**: Stream assets up to 100MB without memory pressure
- **Implementation**: BFF streams response; `<video>`/`<img>`/`PDF.js` consume incrementally
- **No Buffering**: BFF proxy uses `ReadableStream` passthrough

## NFR3.3: PDF.js Worker
- **Target**: Single PDF.js worker shared across instances
- **Implementation**: `pdfjsLib.GlobalWorkerOptions.workerSrc` set once at app init
- **Memory**: Worker ~2MB; shared avoids duplication

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR2 (SEC-9) | NFR3.1, NFR3.2 | OK |
| NFR3 (SECURITY-08) | NFR3.2 | OK |