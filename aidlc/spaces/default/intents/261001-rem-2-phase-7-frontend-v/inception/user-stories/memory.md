<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-10-03T07:02:23Z — Treat historical CodeKB readiness claims as evidence to recheck against the current code and contracts before planning integration work; source spot-checks found BFF streaming and result-reference gaps that the old inventory described as ready, so the story handoff now names those prerequisites instead of claiming compatibility.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-10-03T07:02:23Z — Contract Design must verify BFF content-job SSE framing/cursor propagation and the authorized resultRef-to-content path before implementation; functional design must define a controlled unavailable-recovery state when the original request cannot be reconstructed after reload.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
