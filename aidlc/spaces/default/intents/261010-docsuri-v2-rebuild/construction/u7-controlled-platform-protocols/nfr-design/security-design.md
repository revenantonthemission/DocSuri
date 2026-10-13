# U7 security design

## Scope

Maps the U7 security and privacy requirements (NFR4.x, NFR5.x) to concrete design
solutions. U7 is a local controlled executable with one hardened surface: the
stdin/stdout JSON envelope. There is no network admin surface.

## Authority architecture

- **Independent operator authority** is stored as `OperatorAuthority` rows in the
  dedicated `PlatformControl` PostgreSQL schema: actor (verified local OS
  identity), explicit target scope, permitted-operation allowlist, class
  (`routine` | `destructive-release` | `evidence-reader`), and revocation.
- **Guard functions** (owner-scoped `SECURITY DEFINER`, owned by a non-login
  schema role) validate the typed purpose/session/source inputs against current
  authoritative rows and lock the target barrier **on the caller's existing
  transaction connection**. Only explicit consumer roles receive `EXECUTE`;
  `PUBLIC` execution and schema creation are revoked; no dynamic SQL, no
  arbitrary predicate/table/role parameter, no `SET ROLE` escape.
- **Application administrator identity is never an operator** (NFR4.1): the guard
  does not accept an application principal as the actor.
- **Destructive/release** requires a `destructive-release`-class grant (NFR4.4);
  a routine grant can never satisfy it.
- **Provisioning/revocation** happens only through a local, OS-user-verified
  subcommand writing to the `PlatformControl` schema (NFR4.6); no network/app
  surface can mint a grant.

## Atomic authorization before effect

The guarded transaction: acquire a **durable in-flight lease** for the target (a
lease row, or a conditional update that refuses when a current lease exists) →
re-check current authority and evidence compatibility → write the
`ControlledOperation` binding + receipt stub in state `authorized`/`accepted` →
commit. The target lease is now held durably, so a second concurrent
`executeControlled` for the same target is **refused** while it is held: the
one-in-flight-effect guarantee does not depend on holding a database transaction
open across the effect. The effect then runs in the `bounded-executor` child; on
return the parent settles the receipt and releases the lease. A lease left held
past its per-protocol deadline is reclaimable only through reconciliation, never
by silent re-execution. Any failure before the effect releases the lease with no
effect; the effect's own failure is recorded, never a `completed`/`succeeded`
outcome. (NFR4.8, NFR3.5, NFR8.1)

## Input safety

- The operation name must be a **retained-inventory allowlist** member; no raw
  command, path or shell is admissible, and no shell interpolation occurs
  (NFR4.7).
- Native filesystem/credential semantics are exercised through a bounded adapter,
  never a mock that claims equivalence (NFR4.9).
- Transport is local stdin/stdout JSON; any retained authenticated HTTP binding
  stays compatibility-dependent and bounded (NFR4.10).

## Privacy and secret hygiene

- Evidence, receipts and logs carry structured facts with **no credentials,
  secrets or private source text** (NFR5.1–NFR5.3); only safe correlation
  identifiers appear (NFR9.4).
- Receipts preserve the actor/target/effect binding across restart so an
  interrupted effect cannot be misattributed (NFR5.4).

## Threat model summary

| Threat | Mitigation |
|---|---|
| Privilege confusion (app admin / routine vs destructive) | Authority class separation enforced by guard functions |
| Replay / substitution | Same-key changed-input conflict; authority+evidence re-checked under lock |
| Command/path injection | Allowlist vocabulary; no shell/path interpolation |
| Secret exposure | Field-validated records; safe correlation only |
| Concurrent double effect | One in-flight effect per target under row lock |

## Sources

- [NFR security requirements](../nfr-requirements/security-requirements.md)
- [rules.md](../functional-design/rules.md) — BR2, BR3, BR5, BR6
- [contract-summary.md](../../../inception/contract-design/contract-summary.md) — C10
