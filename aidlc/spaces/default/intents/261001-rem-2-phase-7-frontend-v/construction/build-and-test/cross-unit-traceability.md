# Cross-Unit Traceability — Build and Test

Aggregate view over the three code-generation units at revision `156fb206` (2026-10-09). Each unit keeps its own machine-readable traceability file; this page links them and summarizes the allocation without upgrading any row.

| Unit | Traceability record | Upstream ids enumerated | Rows | Status allocation |
|---|---|---|---|---|
| u1-job-skeleton | `construction/u1-job-skeleton/code-generation/traceability.json` | 184 | 184 | All GAP/Deferred — no OK row; partial-evidence pointers list the u1 test files |
| u2-job-resilience | `construction/u2-job-resilience/code-generation/traceability.json` | 129 (18 story/quality + 111 acceptance) | 129 | All GAP — advisory; sensor reconciled with `missing_from_upstream_ids` empty |
| u3-secure-assets | `construction/u3-secure-assets/code-generation/traceability.json` | 53 (9 story/quality + 44 acceptance) | 53 | All GAP — advisory; sensor reconciled with `missing_from_upstream_ids` empty |

## Notes

- "GAP" is the honest allocation: unit-level tests exercise the slices, but the acceptance-level evidence (real integration, executed acceptance runs) is deferred as recorded in each `code-summary.md`. No row is upgraded without that evidence.
- The per-unit partial-evidence pointers (test files) are listed inside each traceability file and its `code-summary.md`.
- Cross-unit boundaries verified in this stage: the shared BFF route serves both the u1 job stream (SSE branch, no-store) and the u3 asset branch (image relay) without regressions (combined suite green); the shared PaperDetailIsland composition is exercised by the retained u1/u3 tests; `jobDiagnostics` carries both the u1/u2 latency signals and the u3 asset-readiness signal.
- The 184/129/53 allocations trace to `unit-of-work.md` / `unit-of-work-story-map.md` and the requirements' acceptance ids as enumerated by the stage traceability sensor for each unit.
