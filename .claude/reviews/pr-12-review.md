# PR Review: #12 — infra(cdk): dev sizing profile (-c profile=dev) for personal-account deploy

**Reviewed**: 2026-08-04
**Author**: revenantonthemission
**Branch**: infra/dev-profile-sizing → develop
**Decision**: APPROVE (with comments) — posted as COMMENT (author-owned PR cannot self-approve)

## Summary
Adds an opt-in `-c profile=dev` sizing/topology profile (single-AZ trim, no docsuri.org estate, cross-stack refs replacing stale literals) plus the serverless migration plan. Default-prod synth stays byte-identical for search/compute/frontend (verified by empty template diffs during development); the change set is empirically validated by the full 8-stack dev deployment (readyz: 14 modules, 0 blocking) and 14/14 CI checks.

## Findings

### CRITICAL
None.

### HIGH
None.

### MEDIUM
1. **`ingestion_stack.py:551` / `summarization_stack.py:199` — RdsSg cross-stack ref applies to prod too.** Unlike the endpoint/secret (dev-conditional, prod keeps literals), the SG now reads `db.connections.security_groups[0]` unconditionally → prod templates gain an ImportValue on Compute's SG export. Consequence: a future prod deploy of either worker stack requires a Compute deploy first (to create the export), which regenerates the per-synth X-Origin-Verify secret — the exact churn the original ponytail note avoided. Acceptable if old-account prod is considered frozen (it is, per migration direction); otherwise make the SG ref dev-conditional with a corrected literal. Recommend a follow-up decision note in the serverless plan Phase 0.

### LOW
2. `compute_stack.py` / `frontend_stack.py` dev branch — CloudFront→ALB origin hop is plain HTTP (in-AWS path, X-Origin-Verify still enforced by the ALB rule). Intentional dev tradeoff; viewer side stays HTTPS. Fine as-is; do not copy to prod.
3. `compute_stack.py` dev `PUBLIC_APP_URL` defaults to `http://localhost:3000` until `-c dev_app_url` is passed — email-verify/OIDC redirect links are wrong until then. Documented in-code; consider baking the value after first deploy.
4. Prod literals `_RDS_ENDPOINT`/`_RDS_SECRET_ARN` still point at the old account (028317349537) — pre-existing, not introduced here; already tracked as mandatory Phase 0 fix in `serverless-migration-plan.md` §1 감사 노트 ①.
5. Dev SES identity is created unverified (no zone for DKIM) — dev email delivery inert; documented.

## Validation Results

| Check | Result |
|---|---|
| CI (14 lanes: shared/units/frontend/CodeQL/dep-review/security) | Pass (14/14) |
| Prod-parity synth diff (compute/frontend/search) | Pass (empty diffs) |
| Dev synth (cert/Route53 = 0 resources; bucket = 0 created) | Pass |
| Empirical deploy (8 stacks, /readyz 14 modules 0 blocking) | Pass |
| ruff (ops/cdk touched files) | Pass |

## Files Reviewed
- Added: `ops/cdk/stacks/profile.py`, `aidlc-docs/construction/plans/serverless-migration-plan.md`
- Modified: `ops/cdk/app.py`, `ops/cdk/cdk.context.json`, `ops/cdk/stacks/{search,compute,frontend,ingestion,summarization}_stack.py`
