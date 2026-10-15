# U3 paper and corpus capabilities — code summary

Stage: code-generation. Unit: `u3-paper-corpus-capabilities`. Working branch:
`feature/docsuri-v2-u2-account-personal-controls`. Date: 2026-10-15 (Asia/Seoul).

This summary records what was built, what actually ran, and every gate that
remains open. It claims no real-provider, permission, model or public parity:
all execution below is the owned synthetic realm (`docsuri_u3`,
`corpus-maintenance`, run identity `docsuri-u3-<16 hex>` under
`/tmp/docsuri-u3-run`).

## What was built

| Layer | Files | Substance |
|---|---|---|
| Realm + runner | `scripts/verify_docsuri_u3.py`, `scripts/serve_docsuri_u3.py`, `scripts/u3_browser_fixtures.py`, `backend/pytest.u3-paper-corpus.ini`, `backend/.coveragerc.u3` | Owned environment (ports 15459/18059, private modes, retention), ordered append-only migrations with hash identity, fixture preparation, nine scoped phases, bounded process supervision |
| CorpusContent | `backend/modules/corpus/{u3_schema,u3_guards,u3_watermark_v2}.sql`, `{maintenance,reading,u3_http}.py` | Staged runs with per-effect dispositions, completion/watermark triggers, deterministic identity/dedup, projection batch receipts, CAS publication (terminal withdrawal cannot be resurrected), ordered append-only change facts, restore-boundary replay, exact-version reading with bounded dispositions, opaque asset handles |
| Discovery | `backend/modules/discovery/{u3_schema,u3_grants}.sql`, `{u3_search,citations,u3_http}.py` | Versioned query vocabulary, snapshot-bound windows with signed cursors, disclosed `semantic-unavailable` lexical fallback, completed-search facts through the Library consumer, bounded labelled citation traversal with provider budget |
| PaperAssistance | `backend/modules/summarization/{u3_schema,u3_glossary_v2}.sql`, `{u3_catalog,u3_provider,u3_dispatch,u3_glossary,u3_http}.py` | Reconciled options, durable acceptance via the canonical path, real worker dispatch (`PaperWorker` + guarded payloads), synthetic-fixture executor labelled in provenance and result limitations, glossary normalization/virtual-empty/CAS, withdrawal-tolerant result dispositions |
| Library coordination | `backend/modules/library/{u3_schema}.sql`, `{u3_dispositions,u3_history}.py` | Owner-consume of ordered corpus facts into explicit saved-reference dispositions; producer-verified history handoff |
| Shared seams | `backend/u3_host.py`, `backend/u3_policy.py`, + additive edits to `local_host`, `transactions`, `local_profile`, `local_browser`, `artifacts`, `discovery/local_search`, `discovery/guarded_repository`, `library/repository/guarded`, `summarization/guarded_repository`, `accounts/local_http`, `ops/…/local_transport` | U3 assembly + supervised control loop, finite policy document, realm plumbing; no parallel store, broker or writer (R-01 kept: corpus projections are written only by CorpusContent) |
| Frontend | `frontend/src/u3-corpus/{api.ts,search-reading.tsx,assistance.tsx,corpus-workspace.tsx}`, `frontend/src/App.tsx` | Capability-gated Korean workspace: query/filters/results, reading states, citation explorer, assistance options/progress (EventSource + polling fallback)/results, glossary editor with conflict recovery; authority-generation clearing inherited from the shared Transport |
| Pipeline/docs | `.github/workflows/u3-paper-corpus-capabilities.yml`, `scripts/verify_docsuri_cumulative.py` (U3 layer), `frontend/{vitest,playwright}.u3-corpus.config.ts`, `frontend/package.json` scripts | Scoped read-only CI (owner matrix + browser + evidence job), frozen inputs, no secrets on untrusted PRs |

## Executed evidence (synthetic realm, run `docsuri-u3-204aa60225e512be`)

| Phase | Command (as recorded) | Result |
|---|---|---|
| database | `backend/.venv/bin/python scripts/verify_docsuri_u3.py --phase database …` | 15 tests, 0 failures/errors/skips |
| repository | `… --phase repository …` | 21 tests, 0 failures/errors/skips |
| component | `… --phase component …` | 54 tests, 0 failures/errors/skips |
| integration | `… --phase integration …` | 27 tests, 0 failures/errors/skips |
| operations | `… --phase operations …` | 13 tests, 0 failures/errors/skips |
| browser | `… --phase browser …` | 16 journeys, exit 0 (desktop/tablet/phone, Light/Dark/System, Korean reflow, keyboard order, account switch, citations, glossary conflict, assistance accept→progress→result, reload recovery, expired result, withdrawn content, degradation notices) |
| frontend unit | `corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u3-corpus.config.ts test/u3-paper-corpus-capabilities` | 27 tests passed |
| frontend coverage | same with `--coverage` | **86.4% lines** for `src/u3-corpus/**` (threshold 80 enforced in config) |
| backend coverage | `pytest -c backend/pytest.u3-paper-corpus.ini tests/u3_paper_corpus_capabilities --cov --cov-config=backend/.coveragerc.u3` | **83% lines** across the 15 U3 production modules; component-only alone is 59%, so the combined layer evidence is the reported figure |
| collection readiness | `pytest … component --collect-only -q` | 54 collected, zero skips; executed before the first behavior run |

Backend totals: **130 real-store component/database/repository/integration/operations cases** (≥32 required real-store/API cases satisfied by 63 database+repository+integration cases alone), plus 27 frontend unit and 16 browser journeys. Q-01–Q-04 close through the mounted transport: the job snapshot carries `seq` and revision, ready results are typed and usable, acceptance reaches the supervised worker without manual execution, and SSE frames parse as valid single-line JSON events with polling/reconnect recovery.

## Requirement contribution (lead rows)

| Row | Status | Evidence |
|---|---|---|
| FR1, FR1.1–FR1.3 find/refine | implemented (guest + owner) | `component/test_discovery.py`, `repository/test_discovery_repository.py`, `integration/test_discovery_routes.py`, browser `search-reading.spec.ts` |
| FR2, FR2.1–FR2.2 public reading | implemented, including assets boundedly unavailable | `component/test_content_reading.py`, `repository/test_corpus_repository.py`, `integration/test_corpus_routes.py` |
| FR3, FR3.1–FR3.4 assistance | implemented with labelled synthetic provider; real model path remains `policy_pending` | `component/test_assistance_jobs.py`, `component/test_progress_transport.py`, `repository/test_assistance_repository.py`, `integration/test_assistance_routes.py`, browser `assistance.spec.ts` |
| FR4, FR4.1–FR4.2 glossary | implemented (normalization/CAS/virtual-empty/binding) | `component/test_glossary.py`, `repository/test_assistance_repository.py`, `integration/test_assistance_routes.py`, browser `citations-glossary.spec.ts` |
| FR9, FR9.1–FR9.2 citations | implemented (bounded, labelled, saves through Library) | `component/test_citations.py`, `repository/test_discovery_repository.py`, browser `citations-glossary.spec.ts` |
| FR18, FR18.1–FR18.3 corpus maintenance | implemented (identity/dedup, withdrawal, rebuild/retry, watermark) | `database/*`, `component/test_corpus_maintenance.py`, `operations/test_recovery_restore.py`, `integration/test_corpus_routes.py` |

Support rows touched (not claimed complete): FR5.3/FR18.2 change facts feed the Library disposition consumer (`library/test`-visible via `repository/test_corpus_repository.py::test_change_facts_paging_and_restore_replay` and `component/test_citations.py`); FR6.3/FR8.x current-authority rechecks appear in every owner transaction; FR10.x eligible-source contracts in reading/assistance admission; FR13–FR15/FR17.2 accounting reconciliation is delegated to UsageEntitlements through the existing settlement path (`u3_dispatch` calls `admit`/`settle`; no U3-owned ledger); FR12.2/FR19 safe observations via `local_observation` and `operations/test_diagnostics.py`.

## NFR obligations

- NFR1/NFR3/NFR4/NFR10: mounted contract behavior, CAS/watermark discipline, claim/fence ordering, withdrawal races and final-frame recovery are exercised in the layers above.
- NFR2.2 (numeric service targets): **not proposed** — no baseline measurement was run in this build; the measurement wiring exists in the operations phase evidence files only as bounded durations.
- NFR5/NFR8: the `$0` local stack is unchanged; unresolved permissions yield `SOURCE_INELIGIBLE`/failed effects (`test_unresolved_permission_yields_explicit_failed_effect`); citation provider terms stay synthetic-fixture only.
- NFR6: automated surface checks recorded (live regions, focus order, reflow at 834/390 widths, appearance modes, long-text wrap). **Manual keyboard/screen-reader review was not performed** and is not claimed.
- NFR9: readiness distinguishes observed/unknown/stale in `test_diagnostics.py`; telemetry remains bounded and secret-free (redaction scan over evidence files).

## Honest gates and carried findings

- Real source permissions, model readiness (P1/P2), citation-provider terms, finite accounting/capacity values and public fit remain unresolved; the affected capabilities are explicitly `policy_pending` or labelled synthetic. `assistance.model` never becomes available from the fixture provider.
- Carried design-stage review findings (functional design FR6.3 row/traceability/sections/upstream references/restore path/vocabulary; NFR requirements glossary coverage/technology inventory; NFR design citations/dangling target/count; infrastructure design citations/seven NFR ids/overstated targets/quarantine definition) are **not fixed here** and remain tracked for their own gates; nothing in this summary masks them.
- The cumulative U1/U2/U3 completion invocation (`backend/.venv/bin/python scripts/verify_docsuri_cumulative.py --confirm-recorded-decision`, now covering u1/u2/u7/u3) is prepared but **not run** — it remains the separate recorded decision point before checkpoint verification.
- Process deviations during the build: three private-tree shell writes on the already-owned synthetic run (one `sed -i` column rename, two developer-time recreations/wipes of `/tmp/docsuri-u3-run` before any test evidence existed in its final form; every probe thereafter used the runner). These are recorded in the stage diary.
- Frontend workspace build (`vite build`) was required before browser journeys; `frontend/dist` is an ignored build artifact, not committed.
- Two legacy files (`scripts/verify_docsuri_cumulative.py`, `tests/u1_integrated_paper_journey/component/test_admission_faults.py`) and `frontend/src/api.ts` carried pre-existing working-branch edits from the U2 build; only the cumulative script received a U3-layer insertion from this unit.
