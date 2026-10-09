# U3 Unit Test and Verification Instructions

## Contract, Current Authority and Ordering

Use the complete unchanged Testing Contract in `code-generation-plan.md`, hash `sha256:f87c0507a83e45b42705d96d9cdb5a9124962ca7bb56c2fd06fd2061fcc42153`: test-after/test-last per component, Standard five–eight meaningful tests with happy path and at least two error/edge cases, plus required real-integration evidence and ≥80% complete changed-source line coverage. Verify the unit-scoped runner/configuration before executable tests; implement each component/layer then author/run its tests. Existing failures are baseline defects to repair, not waived acceptance.

This plan and these instructions descend from the consolidated summary confirmed on 2026-10-08 (`summary_authorization_id` `6bbe4931e3cb90c34d4a287b05da287061efd9041ebe7a5517f9944e4dfb3263`). They are current proposals, not implementation permission: the fresh exact Plan Approval precedes developer writes. The plan is not current implementation or execution authority.

## Unit-Scoped Commands

- `vitest run --config vitest.u3.config.ts` — the u3 scoped suite.
- `vitest run --config vitest.u3.config.ts --coverage` — coverage gate (≥80% lines over the u3 include set).
- `tsc --project tsconfig.u3.json --noEmit` — strict types for the u3 graph.
- `eslint <changed u3 files>` — lint on changed files.
- Combined regressions: `vitest run --config vitest.u1.config.ts`, `vitest run --config vitest.u2.config.ts`, and the full base suite `vitest run`.

## Required Test Suites (authored after each component is complete)

| Test file | Required behaviors |
|---|---|
| `frontend/test/u3BffAssetBranch.test.ts` | Authorized image bytes delivered verbatim (never JSON-parsed); inbound cookie forwarded server-side; redirect (e.g., 302 to a presigned host) refused → empty 404 with no Location; non-image body refused → 404; upstream denied/missing relayed as empty no-store 404; `private, max-age=60` fallback when upstream is silent and upstream values preserved when present; `nosniff` on every asset response; session Set-Cookie relayed from a real upstream error response and none fabricated on timeout; HEAD returns no body under the 10 s timeout; no internal upstream body leaks. |
| `frontend/test/u3AssetViewer.test.tsx` | The migrated viewer requests the same-origin `/bff/api/papers/{paperId}/assets/{assetId}` path with the paper identity; loading → ready/failure states render; no token/redirect flow and no alternate delivery URL in the component; the `UnsubscribePage` mount renders without a token. |
| `frontend/test/u3ZoomPanControls.test.tsx` | Keyboard zoom in/out, pan (arrows) and reset; pointer drag pan; scale/offset bounds clamped; parent-owned transform state (controls never own URLs or fetch); focus preserved across operations; no keyboard trap; operable at 200% text resize / 320 px reflow. |
| `frontend/test/u3ViewerMinimap.test.tsx` | Minimap renders the same authorized image noninteractively (no independent fetch) and is hidden from assistive technology; decoded-readiness measurement emits a bounded value once; skeleton → ready/failure transitions; an image error alone does not fabricate an HTTP denial status; owner-context change clears obsolete views. |
| Retained compatibility files (selected by `vitest.u3.config.ts`) | `assetDelivery.test.ts`, `docModelViewer.test.tsx`, `useAssets.test.ts`, `classifyAssets.test.ts` must stay green with no expectation weakening; the BFF asset change must not regress U1 job-stream checks (`bffRoute.test.ts` family run in combined regressions). |

## Evidence Obligations

- The mandated mid-implementation asset security review (SEC-8/SEC-9) is recorded as `reviews/asset-security-review-01.md` before the fresh unit review.
- Traceability rows and the source-manifest claims list every created/changed file, including comment-only cleanup edits.
- No deployment or operational evidence is claimed; real integration evidence is supplied as applicable where the runner can exercise the real path.
