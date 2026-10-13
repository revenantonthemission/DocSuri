# U1 code summary

Unit `u1-integrated-paper-journey` — actual implemented runner, commands,
results, measured coverage and remaining limitations. The independent
architecture review, the Construction Verification Command and all completion
gates remain with the conductor and the human; nothing here approves them.

## What is implemented

- **Journey realm and assembly**: explicit synthetic-local profile, owner-scoped
  PostgreSQL roles with guard functions, HTTPS loopback transport, same-origin
  FastAPI assembly (`backend/local_host.py`), observation-derived readiness
  (`backend/local_observation.py`) and the canonical browser boundary
  (`backend/local_browser.py`).
- **Owner adapters and services**: accounts entry/session, corpus identify/read/
  withdraw, discovery lexical search, library saves/queries/history, personalization
  settings + onboarding, usage reservations/settlement, PaperAssistance
  admission/claims/payload/result/history plus the owner-bound glossary token.
- **Korean web workspace** (`frontend/src/`): search/reader/library journey,
  truthful assistance refusal, appearance, usage, accessible focus/status,
  data-testids.
- **Operations**: versioned supervisor `scripts/supervise_docsuri_u1.py`
  (status/start/stop/replace/backup/restore/rollback), procedures
  `ops/local-stack/u1-operations.md`, targeted CI
  `.github/workflows/u1-paper-journey.yml`.

## Actual commands and results (this environment)

```text
python3 scripts/verify_docsuri_u1.py --phase database     ...   # 47 passed
python3 scripts/verify_docsuri_u1.py --phase component    ...   # 200 passed
python3 scripts/verify_docsuri_u1.py --phase repository   ...   # 84 passed
python3 scripts/verify_docsuri_u1.py --phase integration  ...   # 24 passed
python3 scripts/verify_docsuri_u1.py --phase operations   ...   # 5 passed
python3 scripts/verify_docsuri_u1.py --phase frontend     ...   # 18 passed
python3 scripts/verify_docsuri_u1.py --phase browser      ...   # 6 passed (axe clean of serious/critical)
```

`contracts`, `model` and `coverage` phases are not claimed complete here:
contracts tests are not authored in this unit; model quality remains blocked by
the unresolved P1/P2 grounding evidence; the coverage numbers below were
measured with explicit instrumented runs.

## Measured coverage (real numbers, no threshold change)

Backend one shared instrumented run across the U1 test scopes
(`--cov-append`, `coverage json`):

- **28 U1-owned runtime modules measured; every one at or above the 80% line floor.**
- Previously sub-floor modules now measured: `backend/modules/discovery/local_http.py`
  **92.5%** (was 77.5) and `backend/modules/library/local_http.py` **98.5%**
  (was 68.1), both lifted by real mounted tests (guest bounds/snapshot/semantic
  refusals, a deliberate history-relay fault, and the library read/history/saved
  search paths), not by exclusions.
- Operator scripts (`serve_`, `supervise_`, `prepare_…transport`,
  `bootstrap_…`) show 0% in-process because they execute as subprocesses; their
  exercise is evidenced by the operations/browser phases that invoke them, and
  in-process measurement is not possible for them.

Frontend (`vitest --coverage` with the explicit inventory
`src/api.ts, src/ui.tsx, src/paper.tsx, src/App.tsx`):

| Module | Lines |
|---|---|
| `src/App.tsx` | **95.95%** (was 67.7) |
| `src/ui.tsx` | 95.45% |
| `src/paper.tsx` | 87.24% |
| `src/api.ts` | 86.36% |

All frontend inventory modules are at or above the 80% per-file floor; the
threshold was neither lowered nor excluded.

## Limitations carried

- Assistance normal-output readiness remains **false** (P1/P2 grounding
  unresolved); the mounted options/accept paths refuse `503 NOT_READY`, and the
  browser scenarios assert that refusal rather than a fabricated summary or
  translation.
- Semantic search mode is not mounted (lexical only); corpus figures expose
  captions with bounded asset unavailability.
- Numeric service targets await the human-agreed baseline; the exact
  Construction Verification Command remains **UNSET**.
- Step 15 record files `source-manifest.json` and `traceability.json` are not
  produced yet; the full unit path inventory is available from
  `git diff --name-status 2a9a08f66dfb0bc484e270fe2fb26d0ed3503b71..HEAD` plus
  the working-tree changes, and upstream traceability lives in
  `../functional-design/traceability.json`.
