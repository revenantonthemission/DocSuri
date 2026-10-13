# U7 tech-stack decisions

## Scope

These selections cover the independently executable controlled operator
(`PlatformControl`). They reuse the proven local Python/PostgreSQL path from U1
and honour the $0/local budget and the C10 transport invariant.

## Decisions

| Area | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| Language/runtime | Python (the shared project code and the `docsuri_ops` package), one process | Matches the existing repository stack and U1's proven local path; no new runtime to maintain | A separate language/runtime (adds build and maintenance surface for no gain) |
| Transport | Local stdin/stdout JSON envelope (`inspectEvidence`/`executeControlled`/`readReceipt`) | C10 invariant; no network admin surface; simplest to bound and audit | A local HTTP admin server (wider attack surface; C10 keeps HTTP bindings compatibility-dependent only) |
| Durable store | The application's local PostgreSQL 16 with a dedicated `PlatformControl` schema and its own bounded, non-login role | Reuses the owner-isolation and privilege-separation pattern proven in U1; the local stack is already provisioned | A separate embedded store (a second persistence path to operate and secure) |
| Native execution | Real local subprocess/filesystem/keyring semantics via a bounded adapter, never a generic shell | Preserves native filesystem/credential semantics (NFR4.9); no arbitrary command/path/shell | A mock/shell bridge (cannot establish native equivalence) |
| Authority store | Locally provisioned grants in the `PlatformControl` schema; provisioned/revoked by an OS-user-verified subcommand | NFR4.6; independent of any network/app surface | A network authority service (violates local-only, adds a paid/ops dependency) |
| Observations | U7 exposes operation outcomes through its C10 read interface (`inspectEvidence`/`readReceipt`); any push of observations into the operations view uses the operations owner's `recordObservation` contract (C11) and requires U7 to be a registered provider — a recorded C10/C11 coordination item | NFR9; feeds U8's ops view without a telemetry vendor | A hosted telemetry vendor (paid; not $0); assuming an unregistered push contract |
| Deployment plumbing | Local supervisor scripts only; **no AWS CDK/cloud deployment** for U7 | $0 budget; CDK-era artifacts are recorded cloud-dependent dispositions, not runtime dependencies | AWS CDK deploy (paid/cloud; out of budget) |

## Reproducibility (NFR7)

| ID | Requirement | Source | Measure / closure |
|---|---|---|---|
| NFR7.1 | From a clean checkout, one maintainer can set up and run U7 with documented steps. | NFR7 | Clean-checkout setup fixture |
| NFR7.2 | Runtime and dependency versions are pinned and reproducible. | NFR7 | Lockfile/manifest assertion |
| NFR7.3 | Safe synthetic fixtures exist for every acceptance behaviour (no real destructive effect). | NFR7 | Fixture inventory |
| NFR7.4 | Diagnosis and repair of a representative defect is documented with a regression check. | NFR7 | Maintainer exercise (coordinated with U8) |

## Contract and integration consistency (NFR10)

| ID | Requirement | Source | Measure / closure |
|---|---|---|---|
| NFR10.1 | The operator interface conforms to contract C10's wire types (`OperatorEvidenceRequest`, `OperatorEvidence`, `OperatorExecuteRequest`, `OperatorReceiptRequest`, `OperatorReceipt`) and its stable error vocabulary (`INVALID_INPUT`, `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `POLICY_UNRESOLVED`, `DEPENDENCY_UNAVAILABLE`, `UNKNOWN_OUTCOME`). **U7's internal states are richer than the wire enums and project onto them via the mapping below.** | NFR10 | Contract fixtures assert wire shapes and error codes |
| NFR10.2 | Request/response types follow the shared type registry and schema version; no parallel handwritten wire contract is introduced, and every internal state has an explicit wire projection. | NFR10 | Generated-binding round-trip check plus the mapping table |
| NFR10.3 | The read-only evidence/receipt interface U8 consumes is executable and versioned; a change to externally relied-on behaviour is verified with its actual consumers first. | NFR10 | Consumer compatibility check |
| NFR10.4 | Test doubles are validated against the same contract as the real adapter and cannot establish native equivalence on their own. | NFR10 | Double-vs-contract fixture |

### U7 internal state → C10 wire projection

The functional design uses richer internal state names than the C10 wire enums.
The wire types are the interface and are unchanged; the internal states project
onto them. This resolves the apparent conflict without amending the contract or
introducing a parallel wire contract.

| U7 internal (functional design) | C10 wire field / value | Note |
|---|---|---|
| `PlatformEvidence.compatibility` = `current` | `OperatorEvidence.compatibility` = `compatible` | |
| `PlatformEvidence.compatibility` = `stale` | `OperatorEvidence.compatibility` = `incompatible` | the staleness reason is carried in `OperatorEvidence.checks[].name`/`outcome` |
| `PlatformEvidence.compatibility` = `mismatched` | `OperatorEvidence.compatibility` = `incompatible` | |
| `PlatformEvidence.compatibility` = `missing` | `OperatorEvidence.compatibility` = `unknown` | an absent required observation is honestly unknown |
| `PlatformEvidence.environmentBinding` / `ControlledOperation.environmentBinding` | **not a wire field** | internal binding context; the wire carries `targetId`/`inputHash`/`generation` (and `evidenceGeneration`), and the environment context participates in the internal input/policy digest |
| `ControlledOperation.state` = `authorized` | `OperatorReceipt.outcome` = `accepted` | |
| `ControlledOperation.state` = `executing` | `OperatorReceipt.outcome` = `running` | |
| `ControlledOperation.state` = `completed` | `OperatorReceipt.outcome` = `succeeded` | only with effect evidence |
| `ControlledOperation.state` = `failed` | `OperatorReceipt.outcome` = `failed` | |
| `ControlledOperation.state` = `unknown` | `OperatorReceipt.outcome` = `unknown` | |
| `OperationReceipt.reconciliationState` (`pending`/`not-applicable`/`unresolved`/`reconciled-*`) | **not a wire field** | an internal operator-store field; the wire exposes `OperatorReceipt.reconciliationEvidence[]` only |

Requirement NFR3.2's "never reported `completed`" means the wire outcome is
never `succeeded` on liveness alone.

## Open decisions

- The concrete per-protocol execution deadlines and evidence `maxAge` values are
  filled with the retained-inventory reconciliation; governance is fixed
  (explicit finite values, no implicit default), the numbers are not.
- Numeric capacity/latency targets remain deferred to a measured baseline.

## Sources

- [technology-stack.md](../../../../../codekb/DocSuri/technology-stack.md) — available stack
- [contract-summary.md](../../../inception/contract-design/contract-summary.md) — C10 transport
- [functional-spec.md](../functional-design/functional-spec.md) — workflows and boundaries
- [requirements.md](../../../inception/requirements-analysis/requirements.md) — NFR7, NFR8
