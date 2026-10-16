# Environment Inventory — u4-research-novelty

Environment inventory for the u4-research-novelty unit. All environments are synthetic/local; no cloud infrastructure is provisioned ($0 budget constraint).

## Environments

| Environment | Purpose | Owner | Lifecycle | Status |
|---|---|---|---|---|
| Synthetic realm (database phase) | Database schema validation, migrations | u4-research-novelty | Disposable per test run | Active (on demand) |
| Synthetic realm (repository phase) | Repository/owner-context operations | u4-research-novelty | Disposable per test run | Active (on demand) |
| Synthetic realm (component phase) | Component-level unit tests | u4-research-novelty | Disposable per test run | Active (on demand) |
| Synthetic realm (integration phase) | Mounted host integration tests | u4-research-novelty | Disposable per test run | Active (on demand) |
| Synthetic realm (browser phase) | Playwright browser journeys | u4-research-novelty | Disposable per test run | Active (on demand) |

## Environment Configuration

| Setting | Value | Source |
|---|---|---|
| Budget | $0 (free/local only) | team.md, project.md ($0 mandate) |
| PostgreSQL | Loopback port 15479 | u4-research-novelty code-summary.md |
| HTTPS | Loopback port 18079 | u4-research-novelty code-summary.md |
| Environment file | `/tmp/docsuri-u4-run/environment.json` | unit-test-instructions.md |
| Realm ownership | u4-research-novelty | unit-test-instructions.md |
| Realm expiration | Unexpired at test time | unit-test-instructions.md |
| Migration count | 50 migrations | code-summary.md (CI run evidence) |

## Environment Ownership

| Resource | Owner | Responsibility |
|---|---|---|
| Synthetic realm | u4-research-novelty | Identity/ownership checks precede use |
| Test fixtures | u4-research-novelty | Synthetic only; no real user data; no private content reused |
| Evidence artifacts | u4-research-novelty | Retained per run; redacted diagnostics |
| TLS material | u4-research-novelty | Re-minted when environment retention renewed |

## Disposal Policy

- Teardown preserves required evidence first
- Failed environments remain inspectable
- Realm identity and ownership verified before use
- Failed or expired environments are a failed prerequisite, never a skip
- No cross-realm data reuse

## CI Environments

| Environment | Purpose | CI Workflow |
|---|---|---|
| GitHub Actions runner | Build and test | `.github/workflows/ci.yml`, `u4-research-novelty.yml` |
| Digest-pinned Postgres | Database integration | `postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6` |

## Not Provisioned

| Resource | Reason |
|---|---|
| AWS VPC / subnets / security groups | Single local application release; no cloud infrastructure |
| AWS Secrets Manager / Parameter Store | Secrets in protected local configuration only |
| Cross-account connectivity | Single account, single application release |
| Production infrastructure | No public deployment; main promotion is human-gated and separate |
