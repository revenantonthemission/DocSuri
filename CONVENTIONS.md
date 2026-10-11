# DocSuri Conventions

Team VCS conventions. AIDLC (`AGENTS.md`, `.aidlc-rule-details/`) governs the **document**
lifecycle; AIDLC is deliberately silent on git, so the git workflow is documented here.

## Branches (git-flow)

- **`main`** — production. What's deployed at https://docsuri.rvnnt.dev. Advanced only by promoting `develop`.
- **`develop`** — integration target. All work merges here first, via GitHub PR.
- Working branches are short-lived and merge into `develop` through a PR.
- Merge each working branch into `develop` when its purpose is fulfilled, then
  start the next piece of work on a fresh working branch based on `develop`.

### Interim v2 integration policy

The CI/CD pipeline has not yet been rewritten for v2. Until that work establishes
the replacement checks, follow the Git flow above and document known,
pre-existing legacy CI failures without treating those failures alone as a block
to completed work merging into `develop`. Verify the changed work with
appropriate checks, investigate new regressions, and report which checks failed
or did not run; do not describe a failing CI run as passing.

This records the user's 2026-10-11 instruction after reviewing the fix PR's
base-versus-head failures. It supersedes the earlier blanket passing-CI merge
rule for this interim `develop` integration case. It does not advance `main`;
production promotion remains a separate `develop` → `main` PR.

### Branch naming

`<type>/<short-kebab-description>` — optionally encoding the AIDLC Unit of Work or story id.

| Type       | Use                                   | Example                          |
|------------|---------------------------------------|----------------------------------|
| `feature/` | new functionality (often a Unit)      | `feature/u8-export-pdf`          |
| `fix/`     | bug fix                               | `fix/u3-accounts-session`        |
| `ci/`      | CI/CD pipeline                        | `ci/branch-naming-convention`    |
| `chore/`   | maintenance, tooling                  | `chore/aidlc-github-sync`        |
| `docs/`    | documentation only                    | `docs/system-infrastructure-design` |
| `infra/`   | infrastructure / IaC                  | `infra/cdk-scaffold`             |

- **Standardized on `feature/`** (not `feat/`) — the historical split is resolved in favour of the longer form.
- Construction re-passes after a review-gate rejection take a `-vN` suffix: `feature/u7-v2`, `feature/u7-v3`.
- Enforced by `.github/workflows/branch-name-check.yml`, which fails any PR whose source branch
  doesn't match an approved prefix. `develop` is allowed only as the source of `develop → main` release PRs.

## Version tags

- SemVer, `v` prefix, **annotated** tags on `main`: `v1.0.0`.
- Cut a tag when promoting `develop → main` for a release.
- `MAJOR.MINOR.PATCH`: bump **MINOR** for shipped features, **PATCH** for fixes,
  **MAJOR** for breaking API/contract changes.
