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

All rows below were re-run after the review repair round (2026-10-15); the
outcomes are the repaired state.

| Phase | Command (as recorded) | Result |
|---|---|---|
| database | `backend/.venv/bin/python scripts/verify_docsuri_u3.py --phase database …` | 15 tests, 0 failures/errors/skips |
| repository | `… --phase repository …` | 21 tests, 0 failures/errors/skips |
| component | `… --phase component …` | 54 tests, 0 failures/errors/skips |
| integration | `… --phase integration …` | 29 tests, 0 failures/errors/skips |
| operations | `… --phase operations …` | 13 tests, 0 failures/errors/skips |
| browser | `… --phase browser …` (after `corepack pnpm@9.15.9 --dir frontend exec vite build`) | 16 journeys, exit 0 (desktop/tablet/phone, Light/Dark/System, Korean reflow, keyboard order, account switch, citations, glossary conflict, assistance accept→progress→result, reload recovery, expired result, withdrawn content, degradation notices, guest session boundary) |
| frontend unit | `corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u3-corpus.config.ts test/u3-paper-corpus-capabilities` | 31 tests passed (incl. the U3 shell composition suite) |
| frontend coverage | same with `--coverage` | `src/u3-corpus/**` **86.89% lines** (80% floor enforced per glob); `src/App.tsx` 48.62% in-lane with a 48% no-regression floor (see Coverage below) |
| backend coverage | `backend/.venv/bin/python -m pytest -c backend/pytest.u3-paper-corpus.ini tests/u3_paper_corpus_capabilities --cov --cov-config=backend/.coveragerc.u3` | **74% lines across every U3-touched path**; the 15 U3-authored modules alone are **84.2%** (≥80% new-code floor) and the 10 U3-extended shared modules are 63% whole-file (see Coverage below) |
| collection readiness | `pytest … component --collect-only -q` | 54 collected, zero skips; executed before the first behavior run |

Backend totals: **132 real-store component/database/repository/integration/operations cases** (≥32 required real-store/API cases satisfied by 65 database+repository+integration cases alone), plus 31 frontend unit tests and 16 browser journeys. Q-01–Q-04 close through the mounted transport: the job snapshot carries `seq` and revision, ready results are typed and usable, acceptance reaches the supervised worker without manual execution, and SSE frames parse as valid single-line JSON events with polling/reconnect recovery.

### Review repair round (review-01, NOT-READY → repaired)

The independent review's six findings were repaired without widening scope,
and every previously passing suite re-ran green:

| Finding | Repair | Re-verified by |
|---|---|---|
| R-01 citations path | `/api/v2/c05/read-citations` mounted (C13 `C05_readCitations`); frontend client, unit double, integration tests and journey coverage updated | integration 29, frontend unit 31, browser 16 |
| R-02 admin surface | `/api/v2/c04/change-source-eligibility` renamed; `/api/v2/c04/retry-corpus-run` mounted as its own C04 operation (retry of reconciled retryable stages, original inputs re-read server-side, committed stages retained); the undocumented accept-corpus-run reprocess fold was removed | integration `test_retry_corpus_run_*` (replay, completed-refusal, unknown-refusal) |
| R-03 reads boundary | `resolve-paper` and `read-content` require a current session again (C04/C13/U1); guest search stays anonymous; frontend shows the sign-in requirement instead of guessing content; guest journeys and unit cases updated | integration `test_reading_requires_an_authenticated_session`; browser guest journey |
| R-04 traceability | every OK row names exactly one existing workspace-relative file; all 139 upstream-resolved IDs declared and covered; the sensor now reports 0 invalid targets / 0 undeclared ids / 0 invalid entries, with only the honest GAPs [`FR6.3`, `NFR2.2`, `NFR6.1`] | `aidlc engine sensor-traceability` (findings_count 3) |
| R-05 coverage scope | `.coveragerc.u3` now includes all 10 U3-extended shared modules; the frontend lane includes `src/App.tsx` with per-glob thresholds; numbers re-measured and reported below | backend combined coverage run; frontend `--coverage` run |
| R-06 instructions | the `migrate` phase is documented between setup and every store/test phase; runner rows now use the frozen `backend/.venv/bin/python` and the CI build/frontend commands verbatim (the approved plan's Step 13 wording is frozen — only tick marks may change there — so the runner phase list stays as approved while the instructions carry the full reproducible sequence) | `unit-test-instructions.md`

## Requirement contribution (lead rows)

| Row | Status | Evidence |
|---|---|---|
| FR1, FR1.1–FR1.3 find/refine | implemented (guest + owner) | `component/test_discovery.py`, `repository/test_discovery_repository.py`, `integration/test_discovery_routes.py`, browser `search-reading.spec.ts` |
| FR2, FR2.1–FR2.2 public reading | implemented, including assets boundedly unavailable | `component/test_content_reading.py`, `repository/test_corpus_repository.py`, `integration/test_corpus_routes.py` |
| FR3, FR3.1–FR3.4 assistance | implemented with labelled synthetic provider; real model path remains `policy_pending` | `component/test_assistance_jobs.py`, `component/test_progress_transport.py`, `repository/test_assistance_repository.py`, `integration/test_assistance_routes.py`, browser `assistance.spec.ts` |
| FR4, FR4.1–FR4.2 glossary | implemented (normalization/CAS/virtual-empty/binding) | `component/test_glossary.py`, `repository/test_assistance_repository.py`, `integration/test_assistance_routes.py`, browser `citations-glossary.spec.ts` |
| FR9, FR9.1–FR9.2 citations | implemented (bounded, labelled, saves through Library) | `component/test_citations.py`, `repository/test_discovery_repository.py`, browser `citations-glossary.spec.ts` |
| FR18, FR18.1–FR18.3 corpus maintenance | implemented (identity/dedup, withdrawal, rebuild/retry, watermark) | `database/*`, `component/test_corpus_maintenance.py`, `operations/test_recovery_restore.py`, `integration/test_corpus_routes.py` |

Support rows touched (not claimed complete): FR5.3/FR18.2 change facts feed the Library disposition consumer (`library/test`-visible via `repository/test_corpus_repository.py::test_change_facts_paging_and_restore_replay` and `component/test_citations.py`); FR8.x current-authority and eligible-source rechecks appear in every owner transaction; FR10.x eligibility dominance at every read; FR13–FR15/FR17.2 accounting reconciliation is delegated to UsageEntitlements through the existing settlement path (`u3_dispatch` calls `admit`/`settle`; no U3-owned ledger); FR12.2/FR19 safe observations via `local_observation` and `operations/test_diagnostics.py`. **FR6.3 is not claimed:** the functional-design finding (U3 lifecycle participation — read/acknowledge outstanding lifecycle work and suppress queued work on withdrawal) is carried unfixed, so `traceability.json` labels it GAP rather than repeating the rejected BR1.1 basis.

## Coverage evidence

- Backend, all U3-touched paths (`backend/.coveragerc.u3`, 25 modules incl. the 10 shared modules U3 extended): **74% lines** (2 979 statements, 765 missed) measured across every U3 layer.
- The 15 U3-authored modules alone: **84.2%** lines — above the 80% new-code floor.
- The 10 U3-extended shared modules alone: 63% whole-file. Their U3 diffs are 159 added/30 changed lines; the missing lines are pre-existing paths owned by other units (e.g. `local_host.py` U1/U2/U7 routes, `library/repository/guarded.py` saved-paper paths, `summarization/guarded_repository.py` job paths). Their full-file coverage remains with their owning units' lanes; nothing is excluded to raise the reported number.
- Frontend (`vitest.u3-corpus.config.ts`): `src/u3-corpus/**` **86.89% lines** with the 80% floor enforced per glob; `src/App.tsx` — the only U3-extended shared frontend file (11 added lines: the capability-gated corpus-workspace branch) — measures **48.62% whole-file in this lane** with a 48% no-regression floor, exercised by the new `shell.test.tsx` composition suite plus the 16 browser journeys. The shell lanes own the file's full floor (`vitest.u2-account-controls.config.ts` reports `src/**` at 80.2% aggregate with `App.tsx` at 54.5% whole-file).

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
- Review state: code-generation review-01 returned NOT-READY with six findings (R-01…R-06); all six were repaired in this round with re-run evidence above, and a fresh independent review pass remains required before acceptance (plan step 56, unticked).
- Plan step 48 (finite-limit ingestion/projection/worker/model footprint measurement before load) remains unticked: no baseline measurement ran; the bounded-profile phase evidence holds only bounded durations, and the numeric service targets stay baseline-dependent. It remains a conductor/human-owned gate and is not claimed here.
- Plan step 57 (PR into develop under CONVENTIONS.md) remains unticked by instruction: this repair is committed locally on the existing working branch only — no push, no PR, no merge, no main promotion.
- Repair-round process deviations: none — every write used the file tools, and the executed commands were the documented runner phases, the CI build command and the scoped vitest invocations.
- Process deviations during the build: three private-tree shell writes on the already-owned synthetic run (one `sed -i` column rename, two developer-time recreations/wipes of `/tmp/docsuri-u3-run` before any test evidence existed in its final form; every probe thereafter used the runner). These are recorded in the stage diary.
- Frontend workspace build (`vite build`) was required before browser journeys; `frontend/dist` is an ignored build artifact, not committed.
- Two legacy files (`scripts/verify_docsuri_cumulative.py`, `tests/u1_integrated_paper_journey/component/test_admission_faults.py`) and `frontend/src/api.ts` carried pre-existing working-branch edits from the U2 build; only the cumulative script received a U3-layer insertion from this unit.
