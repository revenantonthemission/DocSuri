# U3 Asset Security Review — SEC-8 / SEC-9 (mid-implementation)

Date: 2026-10-08 · Reviewer role: DevSecOps (independent pass over the U3 diff) · Scope: the uncommitted U3 secure-asset migration changes against `8a95bbd2`.
This is the project-mandated mid-implementation asset security review ("ALWAYS conduct security review mid-implementation (Week 2) for AssetViewer migration — SEC-8/SEC-9"). It is a source/diff review, not operational authorization.

## Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| U3-SEC-01 | Low | `frontend/lib/api/assetSrc.ts:22-24` | `browserAssetSrc` passed through any non-`/api/` URL verbatim, so a stale absolute/presigned manifest URL would have been emitted as `<img src>` (defense-in-depth gap: production CSP `img-src 'self' data:` and the backend's same-origin manifest blocked an active leak). | Fail closed: allow only canonical `/api/` paths (→ `/bff`) and `data:image/*` (dev mock); return `undefined` otherwise; pin with tests. | Resolved — hardened fail-closed and pinned by `test/u3AssetViewer.test.tsx` ("browserAssetSrc fails closed"). |
| U3-BLD-01 | Medium | `frontend/test/u3ViewerMinimap.test.tsx:7,83` | Imported the non-exported `SummarizationAssetRef`; the CI `typecheck` gate failed with exactly one TS2305. | Import the barrel alias `AssetRef`; update the casts. | Resolved — `npm run typecheck` is green. |
| U3-SEC-02 | Low | `shared/dtos/summarization.schema.json:304,311`; generated `frontend/types/wire/dtos.ts:1952,1979`; `backend/.../adapters/settings.py:46` | Wire-contract text still promises a "short-lived signed GET URL"/"presigned by U7" for `AssetRef.url`, contradicting SECURITY-08 and the migrated same-origin backend. | Update the schema description and regenerate the bindings; fix the backend comment. | Accepted risk (deferred) — no functional exposure remains (backend delivers same-origin paths; CSP blocks egress; `browserAssetSrc` now fails closed). The schema/regeneration and backend file are outside this unit's frontend scope; recorded for the stage/release. |
| U3-SCOPE-01 | Low | `frontend/components/UnsubscribePage.tsx:33,74` | The component is not mounted by any route (`app/unsubscribe/page.tsx` renders `UnsubscribeDigest`); its direct `fetch('/api/unsubscribe?token=…')` (a token-authorized email flow, not content-jobs) has no route in this repo. Not an SEC-8 violation, but the reviewed mount is dormant. | Confirm the intended mount or retire/or BFF-route it. | Accepted risk (deferred) — the migration keeps the dormant component compliant (no presigned path/token); no route change belongs to this unit; recorded for the owner decision. |

## Evidence (as reviewed, plus post-review fixes)

- `git diff 8a95bbd2 --stat`; per-file diffs of the BFF asset branch, viewer surfaces, and removed helpers; `rg` sweeps for `presign|signed|amazonaws|X-Amz|token=`, `dangerouslySetInnerHTML|innerHTML|eval`, all `<img`/`fetch(`/`EventSource(`.
- `redirect: 'manual'` is actually set on the asset upstream fetch; 3xx/denied/non-image collapse to an empty no-store 404 with no `Location` and no upstream body; real upstream `Set-Cookie` is relayed on every real response including errors and none is fabricated on timeout; only `image/*` passes, with `nosniff` and a `private, max-age=60` fallback; the request cookie is forwarded server-side.
- `getAssetUrl`/`issueAssetToken` are deleted with zero remaining references; all content-job calls use `/bff/api/content-jobs`; no injection sinks in changed client code; identifiers are `encodeURIComponent`-encoded; the minimap duplicates the same authorized `src` under `inert`/`aria-hidden`/`pointer-events:none`; the new `asset` diagnostic carries only outcome + a bounded duration.
- Validation after the two fixes: u3 lane 13 files / 69 tests green (coverage 87.28% lines); full suite 86 files / 490 tests green; `npm run typecheck` green; `npm run lint:u3` clean.
- Behaviors now pinned by tests: redirect refusal + 302→404 with no `Location`; cookie-on-error and no cookie on timeout; image-only + cache fallback + `nosniff`; HEAD no-body with `redirect:'manual'`; upstream `cache:'no-store'`; off-origin/absolute/relative manifest URLs refused by `browserAssetSrc`.

**Verdict: READY** for the unit review on security grounds, with U3-SEC-02 and U3-SCOPE-01 dispositioned as accepted-risk deferrals above.
