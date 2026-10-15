<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-10-14T23:11:25Z — [unit u3-paper-corpus-capabilities] No new NFR questions were needed: baseline-first numeric targets, the $0 budget and the evidence gates were already settled upstream, so the confirmed proposal carried directly into the derived requirements (following the U2 precedent). The consolidated summary remained the human stop.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-10-14T23:11:25Z — [unit u3-paper-corpus-capabilities] The summary-confirmation reply failed to register with the workflow record for a stretch (the engine saw no human reply across two attempts; a later reply registered normally). If reply registration stalls again during long unattended stretches, treat it as a session/hook condition, not a design issue; the work state itself stays intact on disk.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
