# U7 CI/CD pipeline

## Scope

Delivery pipeline for the U7 operator under the $0/local budget and the interim
v2 CI policy. U7 has no cloud deployment: there is no deploy-on-merge and no
release promotion in this pipeline.

## Pipeline stages

| Stage | What runs | Gate |
|---|---|---|
| Setup | install the pinned Python environment and local PostgreSQL | must succeed |
| Lint | Ruff (Python); ESLint only if U7 gains TS/JS | must pass |
| Typecheck | strict typing for U7 modules | must pass |
| Unit / component tests | U7 component and store-boundary tests | must pass |
| Database-dependent tests | require a live local PostgreSQL; **documented as unexecuted required evidence in CI** (not silently skipped) | recorded, not a pass |
| Executor/native tests | require the host; recorded as unexecuted required evidence in CI | recorded, not a pass |
| Package | build the operator executable/package artifact | must succeed |
| Deploy | **none** | — |

A scoped workflow `.github/workflows/u7-controlled-platform-protocols.yml`
mirrors U1's scoped workflow. Per the interim policy, pre-existing legacy CI
failures are documented and do not by themselves block a completed unit; the
changed work is verified with the appropriate checks, and no failing run is
described as passing.

## Test-automation integration

- The U7 scoped test command runs component tests and the store-boundary tests
  reachable without a live database; database/executor phases are named as
  unexecuted required evidence with the reason and the environment they need.
- No mocked test claims to establish native filesystem/credential equivalence
  (NFR4.9).

## Deployment strategy and rollback

- **Deployment:** local installation through U7's setup/supervisor scripts on the
  host; no blue-green/canary (no hosted environment).
- **Rollback:** keep the previous operator version and its schema migration
  marker; `supervisor rollback` restores the previous executable and the schema
  is forward-compatible (additive migrations only) so a rollback never destroys
  receipts (NFR3.1, NFR3.7).

## Environment promotion

None. One local `synthetic-local` environment; no staging/production promotion
($0/local; no release).

## Secrets management in CI/CD

- **No secret** is stored in CI or committed: operator-native credentials come
  from the OS keyring/files the operator controls; the U7 database role
  credential comes from a local, non-committed config/env file resolved at
  runtime (NFR5.3, NFR4.9).
- CI runs lint/typecheck/scoped tests only; it never provisions cloud resources
  and never exercises a real destructive/release effect.

## Sources

- [infrastructure-specification.md](infrastructure-specification.md)
- [security-design.md](../nfr-design/security-design.md)
- CONVENTIONS.md — interim v2 integration policy
