# Deployment Strategy — u4-research-novelty

## Strategy Selection

**Rolling replacement within one application release.** No blue/green or canary deployment — one human maintainer, $0 budget, no infrastructure to run multiple environments simultaneously.

## Environment Promotion Matrix

| From | To | Trigger | Approval | Gate |
|---|---|---|---|---|
| feature branch | `develop` | PR merge | PR review (human) | CI passes (lint, typecheck, test:coverage, test:e2e) |
| `develop` | staging | Auto-deploy on merge to `develop` | None (auto) | CI passed; staging smoke test/health check |
| `develop` | `main` | Release promotion | Human (tech lead + product owner) | CI re-runs on `main`; production smoke test/health check |

## Approval Workflows

- **Staging deploy**: Automatic on merge to `develop` after CI passes. No human approval.
- **Production deploy**: Human-gated release promotion from `develop` to `main`. Requires tech lead + product owner sign-off. CI re-runs before promotion.

## Deployment Target

Single application release (Next.js standalone output, containerized deployment). U4 contributes the `ResearchWorkspace` embedded library with its C07 routes, worker responsibility, and scoped runner. No second service, broker, or store introduced.

## Rollback Triggers

- CI gate failure on `main` → block promotion, do not deploy.
- Production smoke test/health check failure → rollback to previous pinned revision.
- Post-deployment incident → rollback per rollback-runbook.md.

## $0 Budget Compliance

- Only free/local stacks; no paid provider, endpoint, runner, or overage.
- No auto-deploy to production on merge to `develop` (supersedes team.md direct-to-production; CONVENTIONS.md governs).
- No feature flag service (CloudWatch Evidently, AppConfig) — not needed, not in budget.
