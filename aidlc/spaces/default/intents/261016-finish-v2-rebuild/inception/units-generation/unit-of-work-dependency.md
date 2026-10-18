# Unit of Work Dependency — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Workflow: 261016-finish-v2-rebuild

## Dependency DAG (topology only)

This workflow declares only the three units it builds. Dependencies on the built units (U1–U4, U7) are **satisfied prerequisites**: they are constructed, verified and merged to develop (U4 via PR #51), so they appear here as prose context, not as re-declared edges. Declaring them again would ask the runtime to rebuild finished work. [Q3]

- **U5 (u5-topics-digests)** depends on the satisfied prerequisites U1 (application), U2 (account controls and lifecycle coordination), U3 (corpus/content it digests). No in-workflow dependencies.
- **U6 (u6-approved-export)** depends on the satisfied prerequisites U1, U2, and U4 (immutable research artifact revisions it binds approvals to; merged via PR #51). No in-workflow dependencies.
- **U8 (u8-service-operations-integration)** depends on **U5 and U6** (in-workflow edges), plus every satisfied built unit.

The longest in-workflow chain is U5 → U8 or U6 → U8 (2 units); the built-unit prerequisites dominate the real work order, which Delivery Planning sequences economically. This artifact describes topology only and picks no build order or critical path.

## Machine-readable DAG

```yaml
units:
  - name: u5-topics-digests
    kind: library
    depends_on: []
  - name: u6-approved-export
    kind: library
    depends_on: []
  - name: u8-service-operations-integration
    kind: service
    depends_on: [u5-topics-digests, u6-approved-export]
```

## Integration points

| Boundary | Direction | Contract |
|---|---|---|
| U5 ↔ AccountAccess (built) | U5 consumes | Lifecycle participant registration: account withdrawal marks digests stopped; U5 reads outstanding lifecycle work and reports its own disposition. Consent changes stop delivery. [Q4] |
| U6 ↔ AccountAccess (built) | U6 consumes | Lifecycle participation: export authority dies with the account; owner-scoped connection state. |
| U6 ← U4 (built) | U6 consumes | Immutable artifact revision identity for approval binding — source/consumer revision binding verified jointly at integration. |
| U5/U6 → shared application (U8) | U8 consumes | Embedded module registration, mounted routes and UI contributions; U8 verifies the assembled whole cumulatively. [Q4] |

## Parallel development opportunities

U5 and U6 have no dependency between them — multiple valid topological orderings exist. The economic sequence (which ships first and why) is Delivery Planning's decision, not this artifact's.

## Assumptions & Open Questions

- None.
