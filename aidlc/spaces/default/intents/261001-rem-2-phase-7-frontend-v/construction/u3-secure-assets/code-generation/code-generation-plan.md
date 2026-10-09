# U3 Secure Asset Viewing — Code Generation Plan

Authority: current attempt of `code-generation` for unit `u3-secure-assets`; this plan descends from the consolidated summary confirmed on 2026-10-08 (`summary_authorization_id` `6bbe4931e3cb90c34d4a287b05da287061efd9041ebe7a5517f9944e4dfb3263`). Basis: the delivered and approved U1/U2 frontend surfaces, `unit-of-work.md` (U3), `contract-summary.md` (C5, SEC-8/SEC-9), `requirements.md`, the refined mockups/interaction spec/accessibility checklist for viewer controls, and `../AssetViewer/nfr-requirements/security-requirements.md` plus `../AssetViewer/infrastructure-design/infrastructure-specification.md`. No new backend controller/service/worker capability is added; the backend's auth/license re-check and same-origin manifest paths (commit `77ae7de0`) are consumed. Fresh Plan Approval precedes generation.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "team",
  "ordering": "** Test-last per component — Implement component fully, then write its tests.",
  "scope": "feature",
  "test_strategy": "standard",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    },
    {
      "layer": "team",
      "text": "**Methodology:** test-after\n**Ordering:** Test-last per component — Implement component fully, then write its tests.\n\n**Scope floors (feature scope):**\n- 80% line-coverage floor for new code\n- CI execution before merge\n- Existing test suites must remain green (473 backend + 356 frontend)\n\n**Evidence from reverse-engineering:**\n- Current coverage: ~65% overall, but Phase 7 target components at 0% (JobStatus, contentJobApi BFF routing)\n- 356 frontend tests passing (Vitest + React Testing Library)\n- 473 backend tests passing\n- Playwright E2E configured (~25 tests, ~30% coverage)\n- CI runs lint, typecheck, test:coverage, test:e2e\n- **Gap:** Phase 7 components (JobStatus, AssetViewer migration, contentJobApi BFF routing) completely untested\n- **Gap:** No Error Boundary tests, no SSE polling fallback tests, no idempotency key tests\n\n**Affirmed posture for Phase 7:**\n- Maintain test-after methodology (team default)\n- Ordering: Test-last per component (implement fully, then test)\n- 80% coverage floor for new code enforced in CI\n- All existing tests must remain green\n\n---"
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Meet an 80% line-coverage floor.",
      "Run the selected tests in CI before merge."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "test-after",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Data model / database behavior - implement.",
      "Data model / database behavior - write and run its tests after implementation.",
      "Repository / data access - implement.",
      "Repository / data access - write and run its tests after implementation.",
      "Business logic - implement.",
      "Business logic - write and run its tests after implementation.",
      "API / endpoint - implement.",
      "API / endpoint - write and run its tests after implementation.",
      "Frontend behavior - implement.",
      "Frontend behavior - write and run its tests after implementation.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:47a0413847b87a1c376dc0475c75fdb4bb92763764f6800b049333b085452793",
  "contract_sha256": "sha256:f87c0507a83e45b42705d96d9cdb5a9124962ca7bb56c2fd06fd2061fcc42153"
}
```

## Ordered Implementation Steps

U3 is an API/endpoint-plus-frontend-behavior unit: the BFF asset branch (endpoint layer) and the viewer surfaces (frontend behavior) are implemented and tested per step; data-model/repository/business layers are consumed as delivered backend guarantees. Every step implements its component fully before its tests (test-after).

| Step | Work and completion condition | Story / requirement trace |
|---|---|---|
| [x] Step 1 | Add the u3 unit-scoped runner and strict-type configuration: `frontend/vitest.u3.config.ts` (jsdom, `test/u3*.test.{ts,tsx}` plus the retained asset/viewer compatibility files), `frontend/tsconfig.u3.json`, and `package.json` scripts `test:u3`, `test:coverage:u3`, `typecheck:u3`, `lint:u3`; record the exact commands in `unit-test-instructions.md`. | NFR11; runner step |
| [x] Step 2 | Author/run the runner-config checks: the u3 config selects the u3 + retained tests; `test:u3` green on the pre-change tree (baseline); scripts resolve. | NFR11; runner step |
| [x] Step 3 | Conform the BFF asset branch in `frontend/app/bff/[...path]/route.ts` to C5: set explicit redirect refusal on the upstream fetch (never default-follow), relay session Set-Cookie values from actual upstream responses even on error (none fabricated on timeout), use `private, max-age=60` as the fallback cache when upstream is silent (upstream values preserved), keep image-only passing, `nosniff`, empty no-store 404 collapse for denied/missing/non-image, and add HEAD handling under the 10 s timeout. | US5.1–US5.3; C5/SEC-8/9 |
| [x] Step 4 | Author/run BFF asset-branch tests: bytes fidelity; cookie forwarded; redirect (302 to a presigned host) → empty 404 with no Location; non-image → 404; denied/missing relay; fallback and preserved cache headers; Set-Cookie relayed from an error response and absent on timeout; HEAD 200/404 without a body; no internal upstream body leaks. | C5; SEC-8/9 |
| [x] Step 5 | Migrate the legacy `AssetViewer` and its `UnsubscribePage` mount to same-origin delivery (`/bff/api/papers/{paperId}/assets/{assetId}` via the BFF path); remove the token/redirect props, and remove the dangling presigned helpers (`getAssetUrl`, `issueAssetToken`) from `contentJobApi.ts`. | US5.1–US5.3; SECURITY-08 |
| [x] Step 6 | Author/run AssetViewer tests: renders through `browserAssetSrc`-style same-origin routing with the paper identity; loading failure/degraded states; no token/redirect or alternate delivery URLs anywhere; the `UnsubscribePage` mount works without a token. | US5.1; SEC-8/9 |
| [x] Step 7 | Implement `ZoomPanControls` and wire it into the document-viewer surfaces: keyboard and pointer zoom/pan/reset with parent-owned transforms, bounded scales/offsets, no keyboard traps, focus preserved, controls operable at 200% text resize and 320 CSS-pixel reflow. | US5.2; NFR9/10 |
| [x] Step 8 | Author/run ZoomPanControls tests: keyboard pan/zoom/reset, pointer drag, bounds clamping, parent transform ownership, focus retention, no trap; no alternate delivery URLs introduced by the controls. | NFR9/10; AC7.1 |
| [x] Step 9 | Implement the noninteractive same-image minimap (hidden from assistive technology, no independent network fetch) and the viewer readiness/failure surfaces: decoded-readiness measurement (bounded metric), skeleton loading, controlled unavailable/failure states (an image error event alone cannot report HTTP denial), and clearing of obsolete owner-context views. | US5.2/US5.3; NFR5/7 |
| [x] Step 10 | Author/run minimap/readiness/state tests: minimap renders the same authorized image noninteractively and is hidden from AT; readiness metric bounded; skeleton → ready/failure transitions; owner-context change clears obsolete views. | US5.2/US5.3; NFR5/10 |
| [x] Step 11 | Preserve and lock the accessibility equivalents for document viewing under the new controls: captions/table equivalents retained, focus order across viewer controls, no traps; extend the existing D1–D3 checks to the new surfaces. | US5.3; NFR9/10 |
| [x] Step 12 | Author/run the accessibility extension tests (focus order, equivalents retained, controls reachable, no traps). | NFR9/10; AC7.1 |
| [x] Step 13 | Clean the stale presigned-era wording in touched surfaces (`useAssets.ts`, `DocModelViewer.tsx`, `TranslationView.tsx`, `FullTranslationIsland.tsx`, `types/wire/dtos.ts` notes) so no surface describes presigned delivery as current; comment/wording only. | SECURITY-08; traceability |
| [x] Step 14 | Extend the combined regressions: run the u3 suite with the u1 and u2 suites and the full base suite; repair any cross-suite regressions without weakening expectations, and re-run the existing asset-relay tests (`assetDelivery.test.ts`) to confirm no job-stream regression in the shared BFF route. | all U3 slices; NFR12.2 |
| [x] Step 15 | Verify the coverage floor: `test:coverage:u3` reports ≥80% lines over new/changed u3 sources; surface and close gaps. | scope floor |
| [x] Step 16 | Conduct the mandated mid-implementation asset security review (SEC-8/SEC-9): record the review of the delivered asset path (BFF refusal/cookie/cache semantics, no presigned URLs, auth re-check preserved) as `reviews/asset-security-review-01.md` before completion. | SEC-8/9 mandate |
| [x] Step 17 | Record the actual files, decisions, results and deviations; write `code-summary.md`, `source-manifest.json` claims and `traceability.json` rows for this unit. | NFR11 |
| [ ] Step 18 | Obtain the fresh current-attempt review; repair findings through the required flow; present completion. | required review |

## Planned Source Footprint and Blast Radius

Planned additions/changes (all frontend; nothing claimed until written and recorded in `source-manifest.json`):

| Planned source area | Change and consumers | Impact / tests |
|---|---|---|
| `frontend/vitest.u3.config.ts`; `frontend/tsconfig.u3.json`; `frontend/package.json` scripts | Unit-scoped runner/strict config, same pattern as u1/u2 | Config checks; no source weakening |
| `frontend/app/bff/[...path]/route.ts` | Asset-branch C5 conformance (redirect refusal, cookie-on-error relay, cache fallback, HEAD); shared with U1 job streaming — regression tests required | High; BFF branch tests + u1 regressions |
| `frontend/components/AssetViewer.tsx`; `frontend/components/UnsubscribePage.tsx`; `frontend/lib/api/contentJobApi.ts` | Same-origin migration; dangling presigned helpers removed | High; AssetViewer/mount tests |
| `frontend/components/ZoomPanControls.tsx` (new); `frontend/components/DocModelViewer.tsx` | Controls, minimap, readiness metric, skeleton/failure states, owner-view clearing | High; controls/minimap/state tests |
| `frontend/test/u3*.test.{ts,tsx}` | New unit tests for every changed component and the BFF branch | Standard strategy floors |
| `frontend/lib/useAssets.ts`; `frontend/components/TranslationView.tsx`; `frontend/components/FullTranslationIsland.tsx`; `frontend/types/wire/dtos.ts` | Comment/wording cleanup only (no behavior change) | Low; lint/type checks |

## Exact Test Files and Commands

Planned test files (each authored/run after its component is complete): `frontend/test/u3BffAssetBranch.test.ts` (BFF asset-branch contract: redirect refusal, cookie/error fidelity, cache headers, HEAD, denied/missing), `frontend/test/u3AssetViewer.test.tsx` (same-origin migration, failure states, no alternate URLs), `frontend/test/u3ZoomPanControls.test.tsx` (keyboard/pointer controls, bounds, focus, no traps), `frontend/test/u3ViewerMinimap.test.tsx` (minimap noninteractive/hidden-from-AT, readiness metric, skeleton→ready/failure, owner-view clearing), plus retained compatibility files selected by the u3 config (`assetDelivery.test.ts`, `docModelViewer.test.tsx`, `useAssets.test.ts`, `classifyAssets.test.ts`).

Commands (recorded in `unit-test-instructions.md`): `vitest run --config vitest.u3.config.ts`; `vitest run --config vitest.u3.config.ts --coverage`; `tsc --project tsconfig.u3.json --noEmit`; `eslint <changed files>`; combined regressions `vitest run`, `vitest run --config vitest.u1.config.ts`, `vitest run --config vitest.u2.config.ts`.

## Authority and Limits

No implementation may begin before the fresh exact Plan Approval is recorded against these bytes. No real deployment, operational or measured-performance evidence is claimed; the backend/SQL/staging obligations remain as recorded. Actual partial source/evidence and coverage obligations remain binding; the security review recorded under Step 16 is a project-mandated mid-implementation review, not a substitute for independent operational authorization.
