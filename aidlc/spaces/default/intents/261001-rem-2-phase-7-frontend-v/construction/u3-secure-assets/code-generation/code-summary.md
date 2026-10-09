# U3 Code Generation Summary — Secure Asset Viewing

## Sources and Evidence Identity

This record descends from the consolidated summary confirmed on 2026-10-08 (`summary_authorization_id` `6bbe4931e3cb90c34d4a287b05da287061efd9041ebe7a5517f9944e4dfb3263`) and the fresh Plan Approval recorded against the current plan/test-instruction bytes on the frozen-bytes stage restart (`sha256:v3:c007f856af86becab2c6f36200b3c19ba9a303959692d3daf5894658eb5c2bad`; the earlier `sha256:v3:d0e82a18…` approval no longer binds these bytes), `testing-posture verify --unit u3-secure-assets` => `ok:true`/`execution_allowed:true`. The plan and unit-test instructions were written after that confirmation and descend from it; the claim authority is this directory's `source-manifest.json` (19 writes for this unit). No lifecycle/approval/review setter was invoked outside the sanctioned flow.

## Implemented

- **Runner lane (Steps 1–2):** `frontend/vitest.u3.config.ts` (u3 + retained asset/viewer compatibility files, coverage → `./coverage/u3`, 80% line threshold scoped to the u3 work products), `frontend/tsconfig.u3.json`, and `package.json` scripts `test:u3`, `test:coverage:u3`, `typecheck:u3`, `lint:u3`; baseline recorded green on the pre-change tree.
- **BFF asset-branch C5 conformance (Steps 3–4):** the asset hop now sets an explicit redirect refusal (`redirect: 'manual'`), forwards GET/HEAD with `cache: 'no-store'` and the session cookie, relays real upstream `Set-Cookie` values even on error (none fabricated on timeout), falls back to `private, max-age=60` when upstream is silent (upstream values preserved), keeps image-only passing with `nosniff`, and collapses 3xx/denied/missing/non-image to an empty no-store 404 with no `Location` or upstream body; a `HEAD` route handler was added; non-canonical path segments (empty/`.`/`..`/slash/backslash/control after decoding) are refused before any upstream fetch and every segment is re-encoded when joined, so a decoded escape cannot rewrite the upstream route.
- **AssetViewer migration (Steps 5–6):** `AssetViewer` renders authorized bytes via `browserAssetSrc('/api/papers/{paperId}/assets/{assetId}')` — no token/redirect flow, offline retry instead of a page reload; `UnsubscribePage` supplies the paper identity (viewer omitted when the verified response carries none); the dangling presigned helpers (`getAssetUrl`, `issueAssetToken`, `AssetTokenResponse`) are deleted from `contentJobApi.ts`.
- **Viewer controls (Steps 7–8):** new `ZoomPanControls` — named buttons (축소/확대/왼쪽/오른쪽/위/아래/원래 크기) with 0.5–4× clamped scale (fit = 1), 0.25× zoom steps, 10%-of-viewport pan steps clamped so content cannot leave view, `+`/`-`/arrows/`0` shortcuts only while the focused group, no Tab trap, and drag panning wired into the overlay with pointer-cancellation safety.
- **Viewer states and overview (Steps 9–10):** figures/tables render through a `FigureImage` surface with skeleton loading + accessible loading text, a bounded decoded-readiness measurement (new `asset` diagnostic kind), and a generic failure state (an image error never invents an HTTP status); the asset identity change clears stale state; the enlarged overlay shows a noninteractive same-image minimap (inert, aria-hidden, pointer-events none) with a viewport rectangle; the overlay transform is parent-owned, cleared on new content, and the open overview is cleared when the asset map or doc-model identity changes (an access loss never retains a previous owner's image); pointer dragging pans only when enlarged and pointer cancellation ends a drag without another action.
- **Accessibility retention (Steps 11–12):** existing D1–D3 locks stay green (structured tables/captions/focus), the new controls are keyboard-operable with named buttons and no trap, and text equivalents remain untouched.
- **Wording cleanup (Step 13):** `useAssets.ts`, `DocModelViewer.tsx`, and `FullTranslationIsland.tsx` no longer describe signed/presigned asset URLs (comment-only); `TranslationView.tsx` had no such wording to change.
- **Security review (Step 16):** the mandated mid-implementation asset security review is recorded as `reviews/asset-security-review-01.md` (verdict READY; U3-SEC-01 and U3-BLD-01 fixed in this pass; U3-SEC-02 and U3-SCOPE-01 dispositioned as accepted-risk deferrals there).

## Tests and Evidence

| Lane | Result | Command |
|---|---|---|
| u3 scoped suite | 13 files / 73 tests green | `vitest run --config vitest.u3.config.ts` |
| u1 scoped suite (combined regression) | 23 files / 104 tests green | `vitest run --config vitest.u1.config.ts` |
| u2 scoped suite (combined regression) | 31 files / 144 tests green | `vitest run --config vitest.u2.config.ts` |
| Full base suite | 86 files / 494 tests green | `vitest run` |
| u3 coverage | 87.16% lines over the u3 include set (threshold 80) | `vitest run --config vitest.u3.config.ts --coverage` |
| Strict types (u3 graph) | 81 pre-existing errors, none on u3-authored lines | `tsc --project tsconfig.u3.json --noEmit` |
| CI typecheck (whole repo) | green | `npm run typecheck` |
| Lint | clean on the u3-touched files | `npm run lint:u3` |

## Deviations

- `frontend/types/wire/dtos.ts` is generated ("DO NOT EDIT", `gen-types.mjs --check`); the stale presigned wording inside it (and the shared schema/backend comment) is deferred as U3-SEC-02 in the security review rather than hand-edited.
- The u3 coverage include is scoped to the u3 work products and names each changed file outside the per-file picture: `app/bff/[...path]/route.ts` (asset branch proven by dedicated branch tests; its whole-file percentage — dominated by shared U1 job-stream code — stays out of the lane floor), `lib/jobDiagnostics.ts` (included; its job-specific branches remain exercised by the u1/u2 lanes, so its whole-file figure is partly foreign), `lib/api/contentJobApi.ts` (excluded: a removal-only legacy file whose remaining branches belong to the u1/u2 lanes; changed-line coverage is owned by the frozen-baseline gate), and the comment-only `TranslationView`/`FullTranslationIsland` files (existing suites/lanes). The changed-line requirement is discharged by that final gate, not by this whole-file report.
- `UnsubscribePage` is not mounted by any current route (U3-SCOPE-01); it is kept compliant by the migration, and the mount decision is deferred to the owner.
- The post-security-review fixes (fail-closed `browserAssetSrc`, `AssetRef` test import) were applied after the reviewer's report and are pinned by tests.

## Known Remaining Obligations (not complete, not counted as done)

- Real-origin E2E/integration evidence and the separately human-authorized skeleton/checkpoint invocation remain outside this unit's dispatch; the recorded Construction Verification Command still covers ops executor + sandbox only.
- `traceability.json` retains an all-GAP allocation over the assigned ids with partial evidence pointers; no row is upgraded without executed acceptance evidence.
- Backend/SQL/realm and staging/collector obligations remain as recorded; no real database or operational evidence is claimed.
