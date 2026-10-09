# U3 Secure Asset Viewing — Code Generation Questions

## Sources and Current Status

This pass completes the presigned-to-same-origin asset migration for `u3-secure-assets`, derived from `unit-of-work.md` (U3), `contract-summary.md` (C5, SEC-8/SEC-9, `assetGatewayTimeoutMs` 10000, explicit redirect refusal at line 628), `requirements.md`, the refined mockups/interaction spec/accessibility checklist for the viewer controls and minimap, and `../AssetViewer/nfr-requirements/security-requirements.md` + `../AssetViewer/infrastructure-design/infrastructure-specification.md` (GET and HEAD on the BFF asset route). Commit `77ae7de0` (F07) already landed the backend same-origin manifest paths, the backend bytes-endpoint auth/license re-check and a first BFF asset-image relay branch consumed by `DocModelViewer` via `browserAssetSrc`. What remains: the BFF asset-branch contract conformance (explicit redirect refusal, Set-Cookie relay on real error responses, `private, max-age=60` fallback, HEAD), the legacy `AssetViewer`/`UnsubscribePage` migration off the dangling presigned helpers (`getAssetUrl`, `issueAssetToken`), the `ZoomPanControls`/noninteractive-minimap/decoded-readiness/skeleton-and-failure work, tests, and the mandated mid-implementation asset security review. No open functional question was identified; every choice is mandated upstream, so none is asked.

## Plan Approval

Approve this exact Code Generation plan?

This current-attempt decision covers `code-generation-plan.md`, its embedded complete native Testing Contract and `unit-test-instructions.md` for `u3-secure-assets`. Actual partial source/evidence and coverage obligations remain binding; the Step 16 asset security review is a mandated mid-implementation review, not an operational authorization.

The current tool-produced approval/source tags are recorded here before presentation.

[Approval Fingerprint]: sha256:v3:c007f856af86becab2c6f36200b3c19ba9a303959692d3daf5894658eb5c2bad
[Planned Source]: f15e575aa90973275e732081a343b46014dda8f9f5be35f17d14b6c4bffa64fc

- Approve Plan — Authorize developer implementation of this exact current plan and scoped test instructions through its protected receipt.
- Request Changes — Revise the plan or test instructions before implementation.

[Answer]: Approve Plan

## Consolidated Summary Confirmation

- **Scope and basis:** U3 extends the landed same-origin asset delivery with BFF asset-branch contract conformance and the document-viewer migration; it adds no new backend controller/service/worker capability and preserves U1's job-stream regressions in the shared BFF route and PaperDetailIsland composition.
- **Delivery contract (C5):** the BFF asset route refuses redirects explicitly; accepts only successful image content; preserves `private, max-age=60` (fallback when upstream is silent) and `X-Content-Type-Options: nosniff`; collapses denied/missing/non-image to an empty 404 with no-store and no internal body; relays session Set-Cookie values from actual upstream responses even on error, with no fabricated cookies on timeout; supports GET and HEAD under the 10 s gateway timeout.
- **Viewer work:** migrate the legacy `AssetViewer` and its `UnsubscribePage` mount to same-origin delivery and remove the dangling presigned token/redirect helpers; implement `ZoomPanControls` (keyboard/pointer zoom/pan/reset with parent-owned transforms, no keyboard traps), the noninteractive same-image minimap hidden from assistive technology, skeleton loading and controlled unavailable/failure states in `DocModelViewer`, decoded-readiness measurement, and obsolete owner-context view clearing; preserve captions/table equivalents and the existing D1–D3 accessibility locks; no alternate delivery URLs anywhere.
- **Tests and evidence:** BFF asset-branch tests (bytes fidelity, cookie/cache/redirect-refusal/HEAD/denied/missing), viewer control, minimap and failure-state tests with accessible navigation, combined U1/U2 regressions, ≥80% line coverage for new/changed frontend code, real integration evidence as applicable; the mandated mid-implementation asset security review (SEC-8/SEC-9) runs during this pass and its disposition is recorded before completion.
- **Authority limits:** no real deployment or operational evidence is claimed; U1/U2 evidence and obligations are untouched; the existing suites must remain green.

Does this all look correct before I generate the planning artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
