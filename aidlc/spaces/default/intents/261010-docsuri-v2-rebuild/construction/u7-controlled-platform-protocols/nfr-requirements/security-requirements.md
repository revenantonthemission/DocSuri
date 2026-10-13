# U7 security requirements

## Scope and method

U7 owns **independent platform authority** and privacy-safe operator evidence
(NFR4, NFR5). Its security envelope is enforced by the rules in
[rules.md](../functional-design/rules.md) and contract C10. The single hardened
surface is a local stdin/stdout JSON executable; there is no network admin
surface.

## Authentication and independent authority

| ID | Requirement | Source | Measure / closure |
|---|---|---|---|
| NFR4.1 | Every effect requires a current, independent `OperatorAuthority` for the exact actor, operation and target; application administrator status never confers it. | NFR4 | Wrong-actor/app-admin fixtures are refused with no effect |
| NFR4.2 | Authority is target-scoped and explicit; empty, wildcard or implicit-all scope is invalid. | NFR4 | Scope validation fixtures |
| NFR4.3 | Revocation takes effect immediately at the next execution check. | NFR4 | Revoke-then-execute fixture refused |
| NFR4.4 | A destructive or release effect requires a separately provisioned `destructive-release` grant; a routine grant never satisfies it. | NFR4 | Class-mismatch fixture refused before effect |
| NFR4.5 | A bounded `evidence-reader` grant authorizes read-only access to evidence and receipts for its scope and can never authorize an effect. | NFR4 | Reader-execute fixture refused; reader-read allowed |
| NFR4.6 | Grants are provisioned and revoked only through the local, OS-user-verified subcommand; no network or application surface may mint one. | NFR4 | Provisioning fixtures from non-local surfaces refused |

## Authorization and input safety

| ID | Requirement | Source | Measure / closure |
|---|---|---|---|
| NFR4.7 | The operation vocabulary is the retained inventory; no arbitrary command, path or shell is admissible. | NFR4, NFR10 | Injection fixtures (command/path/shell) refused |
| NFR4.8 | Preconditions are re-checked under the exclusive target lock immediately before the effect; a failed recheck yields no effect. | NFR4 | Concurrent-change fixture yields no effect |
| NFR4.9 | Native filesystem and credential semantics are preserved; a mock never substitutes for and claims equivalence with them. | NFR4 | Native-behaviour fixtures run against real targets |
| NFR4.10 | The transport is local stdin/stdout JSON; any retained authenticated HTTP evidence binding stays compatibility-dependent and is never a public admin bypass. | NFR4, NFR10 | Binding fixtures authenticated and bounded |

## Data protection and privacy

| ID | Requirement | Source | Measure / closure |
|---|---|---|---|
| NFR5.1 | Observations, evidence and receipts exclude credentials, secrets and private source text. | NFR5 | Content scan fixtures find no secrets/private text |
| NFR5.2 | Evidence records are privacy-safe structured facts with a bound target/input/environment binding. | NFR5 | Field-level fixtures |
| NFR5.3 | Routine logs and operator feedback carry safe correlation identifiers only, never credentials or unnecessary private input. | NFR5, NFR9 | Log-content fixtures |
| NFR5.4 | Receipts preserve the actor/target/effect binding across restart, so an interrupted effect cannot be misattributed. | NFR5, NFR3 | Restart fixture preserves binding |

## Threat considerations

- Privilege confusion: app admin vs platform operator (NFR4.1) and routine vs
  destructive-release (NFR4.4) are separated by class, verified by fixtures.
- Replay/substitution: same-key changed input conflicts; session/actor
  substitution is refused before effect (NFR4.8, functional WF5).
- Unsafe input: no shell/path interpolation; schema-qualified, fixed semantics
  (NFR4.7).
- Secret exposure: no credentials in evidence, receipts, logs or feedback
  (NFR5.1, NFR5.3).

## Sources

- [rules.md](../functional-design/rules.md) — BR2, BR3, BR5, BR6
- [contract-summary.md](../../../inception/contract-design/contract-summary.md) — C10
- [requirements.md](../../../inception/requirements-analysis/requirements.md) — NFR4, NFR5
