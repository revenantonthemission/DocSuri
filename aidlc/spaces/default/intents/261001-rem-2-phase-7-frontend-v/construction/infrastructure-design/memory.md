<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
2026-10-03T03:23:00Z — Designed infrastructure for all 6 units. BFF proxy routes defined for content-jobs (SSE + REST) and assets (streaming + Range). Next.js standalone output for containerized deployment. Sentry integrated via `@sentry/nextjs` with source map upload. AssetViewer security: BFF-only asset URLs, gateway per-request auth, CSP headers. PDF.js worker served statically.

## Deviations
2026-10-03T03:23:00Z — No separate infrastructure per unit; shared BFF proxy and Next.js deployment. IdempotencyService and ZoomPanControls are client-only (no server infra). ErrorBoundary/ErrorBoundaryFallback client-only with Sentry DSN injection.

## Tradeoffs
2026-10-03T03:23:00Z — Chose Next.js BFF proxy over separate API gateway for simplicity (already in stack). Streaming passthrough avoids buffering large assets. Dynamic import for PDF.js adds chunk but reduces initial bundle.

## Open questions
2026-10-03T03:23:00Z — Confirm Security Review Week 2 passes for AssetViewer; verify gateway Range header support for video/PDF byte-range; confirm Sentry DSN rotation process.
