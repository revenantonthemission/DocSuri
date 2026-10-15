<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-10-14T17:47:03Z — [unit u3-paper-corpus-capabilities] No new human questions were needed; the approved requirements, component catalogue and C04–C06 contracts already settle U3's behaviours, so the confirmed proposal carried directly into artifact generation (the U2 precedent). The consolidated summary remained the human confirmation stop.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-10-14T17:47:03Z — [unit u3-paper-corpus-capabilities] Added a CorpusChangeFact entity and a PaperVersion eligibility state machine as elaborations inside the CorpusContent owner, derived from C04's changeSourceEligibility/readSourceChanges semantics rather than the component catalogue's shorter entity list; no new authority was introduced.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-10-14T17:47:03Z — [unit u3-paper-corpus-capabilities] Traceability maps one primary rule per upstream FR row (with a single reverse explanation for the guest-anonymity rule) instead of fanning multiple targets per row; keeps the sensor check unambiguous while the rules table still shows the full rule set.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
