# Scalability Design — AssetViewer

## NFR3.1: 5 Concurrent Asset Views
**Design**: Independent fetches per instance
- Browser HTTP/2 multiplexing handles 5+ connections
- Each `<img>`/`<video>`/`PDF.js` independent

## NFR3.2: 100MB Streaming
**Design**: BFF `ReadableStream` passthrough
- No buffering in BFF or gateway
- Native elements consume incrementally

## NFR3.3: Shared PDF.js Worker
**Design**: Single worker initialized at app start
```ts
// lib/pdf-worker.ts
import * as pdfjsLib from 'pdfjs-dist';
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';
```
- Worker ~2MB shared across instances

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR3.1 | Independent fetches, HTTP/2 multiplexing |
| NFR3.2 | ReadableStream passthrough, no buffering |
| NFR3.3 | Single PDF.js worker at app init |