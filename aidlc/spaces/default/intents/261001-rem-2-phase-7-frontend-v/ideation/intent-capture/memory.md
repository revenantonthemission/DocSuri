<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
2026-10-01T17:30:00Z — Phase 7 frontend wiring scope confirmed as feature scope; backend durable job contract (Phases 1-6) is complete and tested.
2026-10-01T17:30:00Z — BFF routing mandatory for SEC-8 compliance; all content-job calls must go through `/bff/api/content-jobs/*`.
2026-10-01T17:30:00Z — SSE with `Last-Event-ID` resume is the primary progress channel; polling fallback for resilience.

## Deviations
2026-10-01T17:31:00Z — Novelty/evidence/ingest_userdoc job types accepted in API but no worker implementation; frontend will disable these in UI until workers exist.
2026-10-01T17:31:00Z — No job cancellation endpoint; ABSTAINED state is backend-only for now.

## Tradeoffs
2026-10-01T17:32:00Z — Chose client-generated UUID v4 for idempotency keys (simple, stateless) over deterministic hash (survives page reload) for faster implementation.
2026-10-01T17:32:00Z — Same-origin asset delivery with 60s private cache chosen over presigned URLs for SEC-9 compliance.

## Open questions
2026-10-01T17:33:00Z — Confirm Product Lead choices on 7 intent-capture questions (BFF routing, SSE fallback, AssetViewer migration, JobStatus mount, idempotency key, error UX, cache headers).
2026-10-01T17:33:00Z — Backend input needed on: novelty/evidence/ingest job types UI gating, job cancellation endpoint, job list/history endpoint.

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
