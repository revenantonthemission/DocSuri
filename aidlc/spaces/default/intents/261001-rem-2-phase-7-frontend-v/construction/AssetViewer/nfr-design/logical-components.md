# Logical Components — AssetViewer

## Component Inventory

| Component | Type | Responsibility | Failure Domain |
|-----------|------|----------------|----------------|
| `AssetViewer` | UI | Orchestrates asset rendering by type | Render, network |
| `PDFRenderer` | UI | PDF.js integration, page navigation | PDF.js, memory |
| `ImageRenderer` | UI | `<img>` with BFF src, lazy load | Network |
| `VideoRenderer` | UI | `<video>` with BFF src, streaming | Network, codec |
| `ZoomPanControls` | UI (separate unit) | Zoom/pan for PDF/images | GPU, input |
| `ErrorBoundary` | UI (shared) | Containment, retry | Subtree |

## Failure Domains & Blast Radius

```
AssetViewer
├── PDFRenderer
│   ├── PDF.js parse error → ErrorBoundary → fallback
│   ├── OOM (large PDF) → worker crash → fallback
│   └── Blast Radius: This asset only
├── ImageRenderer
│   ├── Network error → retry → fallback
│   └── Blast Radius: This asset only
├── VideoRenderer
│   ├── Network error → retry → fallback
│   ├── Codec unsupported → fallback
│   └── Blast Radius: This asset only
└── ZoomPanControls
    └── Isolated; no crash propagation
```

## Isolation Strategy
- Each renderer independent; no shared state
- PDF.js worker shared but crash-contained (worker process)
- ErrorBoundary per AssetViewer instance

## Shared Resources
| Resource | Owner | Consumers |
|----------|-------|-----------|
| PDF.js Worker | App init | All PDFRenderer instances |
| BFF Asset Endpoint | Next.js | All renderers |
| Gateway Auth | Gateway | All requests |

## Infrastructure Handoff
| Logical Component | Infrastructure Need |
|-------------------|---------------------|
| BFF Asset Route | `app/bff/api/papers/[paperId]/assets/[assetId]/route.ts` |
| Gateway Asset Endpoint | `GET /papers/{paperId}/assets/{assetId}` with auth + Range |
| Object Storage | S3/GCS with internal signed URLs (gateway only) |
| PDF.js Worker | Static file `/pdf.worker.min.mjs` |

## Traceability
| NFR Requirement | Logical Component |
|-----------------|-------------------|
| NFR1.1-1.4 | AssetViewer, renderers, BFF proxy |
| NFR2.1-2.5 | AssetViewer, BFF proxy, CSP, code scan |
| NFR3.1-3.3 | Renderers, PDF.js worker |
| NFR4.1-4.4 | AssetViewer, renderers, ErrorBoundary, BFF proxy |
| NFR5.1-5.3 | Gateway audit, Sentry, AssetViewer |