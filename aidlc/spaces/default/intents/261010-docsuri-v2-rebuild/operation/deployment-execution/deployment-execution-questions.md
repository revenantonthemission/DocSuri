# Deployment Execution Questions — u4-research-novelty

Answered from existing configuration (CI pipeline, deployment strategy, environment inventory, build/test results) rather than posed to the person, because deployment execution for this project uses existing GitHub Actions CI/CD rather than cloud infrastructure deployment.

| Question | Answer | Source |
|---|---|---|
| Are all pre-deployment checks passing? | Yes — all CI gates pass: lint, typecheck, test:coverage (80% floor), test:e2e | construction/build-and-test/test-results.md, operation/deployment-pipeline/cd-config.md |
| Are database migrations required and tested? | Yes — 50 migrations applied; migration phase passed | construction/u4-research-novelty/code-generation/code-summary.md, operation/environment-provisioning/environment-inventory.md |
| Are dependent services available and healthy? | Yes — synthetic realms owned per unit; identity/ownership verified before use | operation/environment-provisioning/environment-inventory.md |
| What is the deployment window? | Rolling replacement within single application release; merge to develop triggers staging deploy; release promotion to main is human-gated | operation/deployment-pipeline/deployment-strategy.md |
| Is the deployment target available? | Yes — single application release (Next.js standalone output, containerized) | operation/deployment-pipeline/deployment-strategy.md |
| Are rollback procedures defined? | Yes — revert to previous pinned revision; migrations backward-compatible; tombstones never rewritten | operation/deployment-pipeline/rollback-runbook.md |

## Decisions

- **Deployment execution**: No cloud deployment executed; CI pipeline verifies all gates pass; artifacts staged for human-gated promotion to main
- **Staging deploy**: Auto-deploy on merge to develop after CI passes — no manual approval required
- **Production deploy**: Human-gated release promotion from develop to main — requires tech lead + product owner sign-off
- **Smoke tests**: Playwright browser journeys (6 tests) pass against synthetic realm
- **Health checks**: Readiness probe via mounted host validates deployment success
- **Database migrations**: 50 migrations applied in isolated synthetic realm; backward-compatible
- **/bin/zsh budget**: No paid infrastructure; no auto-deploy to production on merge to develop (CONVENTIONS.md governs)

## Open Items

- Production deployment requires human-gated release promotion (tech lead + product owner sign-off) — not executed as part of this stage
- No open items blocking deployment execution for staging

## Consolidated Summary Confirmation

Does this all look correct?

- Looks correct
- Request changes

[Answer]: Looks correct
