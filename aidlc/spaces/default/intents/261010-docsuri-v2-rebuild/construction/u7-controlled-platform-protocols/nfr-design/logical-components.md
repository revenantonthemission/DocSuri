# U7 logical components

## Purpose

A component-level view of where the U7 NFR patterns apply and how failures are
contained. It bridges the NFR design with infrastructure design. These are
logical components inside one independently executable unit, not separately
deployed services.

## Component inventory

| Component | Responsibility | Failure domain | NFR patterns applied |
|---|---|---|---|
| `operator-cli` | Local stdin/stdout JSON envelope (`inspectEvidence`/`executeControlled`/`readReceipt`); parses/validates typed requests; prints plain-text results | operator process | Input validation, stable error vocabulary, accessible text feedback (NFR4.7, NFR6.1, NFR10.1) |
| `authority-provisioner` | Local OS-user-verified subcommand to provision/revoke `OperatorAuthority` grants | operator process | Independent authority, no network mint (NFR4.1–NFR4.6) |
| `evidence-producer` | Computes/persists a bound, finite-lived `PlatformEvidence` generation on demand | operator process + store | Finite validity, binding, no optimistic values (NFR1.1, NFR2.1, NFR9.2) |
| `guarded-store` | `PlatformControl` PostgreSQL schema + owner-scoped `SECURITY DEFINER` guard functions and bounded roles | shared local store | Atomic authorization, owner isolation, append-only receipts (NFR3.5, NFR4.1, NFR4.8) |
| `bounded-executor` | Runs one native effect in a bounded child process (deadline, resource cap, exit-status capture) | child process (blast-radius unit) | Bounded execution, crash containment, truthful failure (NFR2.2, NFR3.2, NFR8.1) |
| `native-adapter` | Real local filesystem/credential semantics for the admitted protocols; allowlist only | child process | No command/path/shell injection; native equivalence (NFR4.7, NFR4.9) |
| `receipt-reconciler` | On-demand reconciliation of an `unknown` receipt from the target; operator `reconcile` subcommand | operator process + store | No duplicate execution, append-only truth (NFR3.3, NFR3.7) |
| `observations-bridge` | Exposes outcomes to U8 through C10 (pull); C11 `recordObservation` push is a coordination item | operator process | Bounded, privacy-safe, outcome-independent telemetry (NFR9.3) |

## Boundaries and blast radius

- **Single operator process** hosts the CLI, provisioner, evidence producer and
  reconciler; a failure here is recoverable (durable receipts) and does not lose
  effect state.
- **Bounded child per effect** is the blast-radius unit for native effects: a
  hang/crash is contained and never blocks the operator process unboundedly.
- **Shared local PostgreSQL** is the shared resource; per-owner schema + guard
  functions bound what each consumer role can touch.

## Shared resources

| Resource | Shared with | Isolation |
|---|---|---|
| Local PostgreSQL 16 | the application's local stack | dedicated `PlatformControl` schema + bounded roles |
| Operator process | none (standalone) | independently executable, no application prerequisite |
| Native filesystem/keyring | the host | exercised through the bounded adapter with the operator's own authority |

## Reproducibility design (NFR7)

- **Clean-checkout setup (NFR7.1):** one documented setup path provisions the
  local PostgreSQL `PlatformControl` schema/roles and the operator CLI, reusing the
  shared project's local profile; no cloud resource is required.
- **Pinned runtime/deps (NFR7.2):** the operator runs on the shared project's
  pinned Python environment and introduces no unpinned runtime.
- **Safe synthetic fixtures (NFR7.3):** every acceptance behaviour (wrong
  actor/target, stale evidence, changed input, interrupted/duplicate execution,
  disk/permission failure) has a synthetic-target fixture; no real
  destructive/release effect runs.
- **Diagnosis and repair (NFR7.4):** a maintainer reproduces a representative
  defect from a clean checkout, identifies its boundary (CLI / guarded-store /
  executor), fixes it and runs a regression check plus the affected integration
  checks; effort is measured before agreeing a target.

## Sources

- [security-design.md](security-design.md), [reliability-design.md](reliability-design.md), [observability-design.md](observability-design.md)
- [functional-spec.md](../functional-design/functional-spec.md) — composition and boundaries
