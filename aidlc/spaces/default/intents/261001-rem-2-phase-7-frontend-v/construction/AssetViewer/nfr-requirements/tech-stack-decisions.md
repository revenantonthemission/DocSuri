# Tech Stack Decisions — AssetViewer

## NFR6.1: Asset Fetching — Native `fetch` via BFF
- **Decision**: `fetch('/bff/api/papers/{paperId}/assets/{assetId}')` for all asset types
- **Rationale**: 
  - Mandated: ALWAYS use same-origin via BFF
  - Native fetch streams response; no buffering
  - Works with `<img src>`, `<video src>`, `PDF.js` data URI

## NFR6.2: PDF Rendering — PDF.js (mozilla/pdfjs-dist)
- **Decision**: PDF.js v4.x via npm
- **Rationale**: 
  - Industry standard; maintained by Mozilla
  - WASM backend for performance
  - Worker offloads parsing to background thread
- **Configuration**: 
  ```ts
  import * as pdfjsLib from 'pdfjs-dist';
  pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';
  ```

## NFR6.3: Image/Video — Native HTML Elements
- **Decision**: `<img>`, `<video>` with BFF `src`
- **Rationale**: Zero deps; browser handles streaming, caching, decode

## NFR6.4: Zoom/Pan — Custom `ZoomPanControls` (separate unit)
- **Decision**: Compose `ZoomPanControls` component
- **Rationale**: Separation of concerns; reusable; testable

## NFR6.5: Styling — CSS Modules + Tailwind
- **Decision**: Mandated pattern
- **No**: styled-components, @emotion (forbidden)

## NFR6.6: TypeScript — Strict
- **Decision**: Full strict mode

## NFR6.7: Testing — Vitest + RTL + Playwright
- **Decision**: Unit tests mock BFF; E2E tests real asset flow
- **Coverage Target**: ≥80% line coverage

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR2 (SEC-9) | NFR6.1 | OK |
| NFR3 (SECURITY-08) | NFR6.1 | OK |
| NFR6 (Error Boundary) | NFR6.1 | OK |
| NFR7 (Sentry) | NFR6.1 | OK |
| NFR8 (Security Review) | NFR6.1 | OK |