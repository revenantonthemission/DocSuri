# Deployment Pipeline Questions — u4-research-novelty

Answered from existing configuration (CI pipeline, infrastructure design, CONVENTIONS.md) rather than posed to the person, because the deployment pipeline already exists and is adequate.

| Question | Answer | Source |
|---|---|---|
| What deployment strategy? | Rolling replacement within one application release; no blue/green or canary (one-maintainer, /bin/zsh budget) | infrastructure-design/cicd-pipeline.md, team.md (/bin/zsh budget) |
| What environment promotion gates? | develop (merge via PR) → staging auto-deploy → main (release promotion, human-gated) | CONVENTIONS.md supersedes team.md direct-to-production; org.md prod gate on manual approval |
| What approval workflows for production? | Separate manual approval (tech lead + product owner) before promote develop → main | org.md production gate; CONVENTIONS.md release promotion |
| What rollback procedure? | Revert release artifact/config to previous pinned revision; migrations stay backward-compatible; re-run affected phases | infrastructure-design/cicd-pipeline.md rollback (code/config), rollback (data) |
| What feature flag strategy? | None — not needed for /bin/zsh budget; no CloudWatch Evidently or AppConfig | team.md (/bin/zsh only free/local stacks) |
| What CI tool? | GitHub Actions | .github/workflows/ci.yml, u4-research-novelty.yml |
| What branch naming convention? | develop, feature/, fix/, ci/, chore/, docs/, infra/ | branch-name-check.yml, CONVENTIONS.md |
| What smoke test/health check? | Required for production deployment; readiness probe via mounted host | org.md deployment procedures |

## Decisions

- **Deployment strategy**: Rolling replacement within the single application release. No blue/green or canary — one human maintainer, /bin/zsh budget, no infrastructure to support multiple environments simultaneously.
- **Environment promotion**: develop (auto-deploy to staging on merge via PR) → main (human-gated release promotion to production). This follows CONVENTIONS.md, which supersedes team.md's direct-to-production continuous deployment.
- **Production approval**: Human-gated (tech lead + product owner sign-off), per org.md production gate and CONVENTIONS.md release promotion.
- **Rollback**: Revert to previous pinned revision; migrations backward-compatible; re-run affected phases; tombstones never rewritten.
- **Feature flags**: None.
- **No paid infrastructure**: Only free/local stacks; no paid provider, endpoint, runner, or overage.

## Consolidated Summary Confirmation

Does this all look correct?

- Looks correct
- Request changes

[Answer]: Looks correct
