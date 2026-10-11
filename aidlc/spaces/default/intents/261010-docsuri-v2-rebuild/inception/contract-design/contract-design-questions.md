# DocSuri v2 — Contract Design plan and confirmation

Date: 2026-10-11 (Asia/Seoul). Conversation language: English.
Mode: Guide me, carried forward from Intent Capture.

## Established decisions and evidence

The human approved [Units Generation](../units-generation/unit-of-work.md) on
2026-10-11. This stage specifies its interfaces without reopening the eight-unit
grouping, 13-component ownership model, full capability scope or $0 constraint.
No additional ordinary interview question is needed for a decision already
recorded below. The technical approach is a proposal awaiting the consolidated
confirmation. The contract draft now exists and has passed specification checks;
its save record must be renewed after this confirmation before independent review.

| Topic | Existing answer or evidence | Contract Design consequence |
|---|---|---|
| Product and access | Approved requirements: public registration, multiple users, private owner isolation and administrator/MFA boundaries | Specify access on each surface; keep current authority separate from a stored account reference |
| External commitments | Feasibility Q4: no known commitments beyond current capabilities; requirements O-02/IB-01/03 still require consumer reconciliation | Preserve retained integrations and specify browser, callback and operator interfaces; do not invent a supported third-party developer platform or promise that no consumers exist |
| Composition | Approved units: U1/U8 are successive assemblies of one application; U2–U6 embedded; U7 separate operator executable | Use explicit module contracts and independent operator authority, without turning every DAG edge into a network service |
| Ownership | Approved domain catalogue gives every business entity one owner | Spec ownership follows that domain owner; construction units implement contributions without acquiring another owner's write authority |
| Recovery | Approved requirements and mockups require truthful acknowledged state, restart recovery, duplicate protection, current authority and explicit export approval | Define errors, state transitions, revisions, acceptance, retries and uncertain-effect reconciliation at each relevant interface |
| Quality and resource values | No numeric targets until baseline; $0 free/local only; technology and hosting open | Define bounded behavior and required policy/configuration references without inventing performance promises, retry durations or a provider selection |
| Retention, drafts and continuity | Determine actual users/data, obligations and recoverable backups first; draft retention/storage/shared-device rules remain due before implementation | Preserve explicit blockers on affected data design and behavior; a contract field or policy reference is not approval of a retention period or migration |
| Git | CONVENTIONS.md and the human's completed-branch instruction | Completed work merges through a PR into develop under the interim CI policy; release promotion to main is separate |

## Bounded current-access check

Current source supports anonymous search: `backend/middleware/auth.py` lists
`/api/search` and `/auth/session` as optional-auth paths, and
`backend/modules/discovery/src/discovery/api/router.py` resolves an unauthenticated
search to a server-controlled identity instead of trusting a production
`X-User-Id` header. The middleware test
`test_auth_injection_optional_for_search_without_cookie` records the intended
anonymous-search behavior. This is source/test inspection, not a fresh executed
service or deployment test. It does not establish an exhaustive access matrix.

The proposal retains this existing guest search plus the required public account
entry/recovery/callback flows. It does not broaden anonymous access to saved or
private work, AI jobs or administrator operations. Exact route/token exceptions
and configured mounts will be reconciled when specifying the full matrix; an
actual behavior conflict requires evidence and a focused decision, not a silent
capability cut. Never copy incidental prefix matching as the v2 authorization
specification.

## Proposed contract plan

- Inventory every declared unit dependency and public/external boundary. Map
  reusable contract families back to each applicable edge, operation owner,
  provider unit, consumer and stable requirement; do not assume one edge equals
  one HTTP endpoint.
- Use typed synchronous module interfaces and shared schemas for embedded
  contributions. Specify HTTP/JSON at browser-facing boundaries, resumable job
  progress with authoritative snapshot/poll recovery, and durable command/fact
  envelopes for accepted background work. State delivery and acknowledgement
  semantics independently of the unselected broker/store/framework.
- Pin identities, revisions, access checks, validation, errors, cancellation,
  duplicate/retry behavior and compatibility. Keep accepted work, prepared result
  reads, drafts, committed messages and external effects distinct. A lost response
  cannot silently trigger a second usage debit, job, email or export.
- Define contribution registration, capability/readiness and lifecycle
  participation contracts so U1 runs without future implementations and U8
  verifies the complete manifest. Missing acknowledgements and unknown outcomes
  remain visible; account code never writes another component's records.
- Resolve both accepted domain clarifications in the proposed specification:
  explicit corpus projection write/rebuild/publication and withdrawal
  responsibility, and immutable research artifact revision/content identity
  bound to export preview, approval and execution. Specification and later
  executable verification remain distinct closure evidence.
- Version contracts explicitly. Permit safe additive changes with documented
  consumer handling, coordinate breaking changes across affected consumers and
  tests, and gate removal of relied-on legacy behavior on consumer inventory and
  the approved transition. No fixed deprecation window is invented.
- Specify retained provider adapter obligations for Google/ORCID, source/citation
  retrieval, model/extraction, email and Notion. Separate DocSuri's controllable
  adapter contract from facts that still need verification against provider
  documentation, terms, configuration and sustainable free/local capacity.
- Produce one contract summary with a boundary table, actual inline formal specs,
  ownership/change rules, requirement links, validation evidence and an explicit
  unresolved-points/blockers table, then obtain an independent architecture
  review. No schemas, providers, deadlines or policy values are approved merely
  by being inherited from the old implementation.

## Ambiguity analysis

No unresolved contradiction was found in the decisions needed to propose this
contract plan. Evidence-dependent policy values and compatibility facts remain
open by explicit upstream decision. They will be named with affected contracts,
units, required evidence and decision owners; the contract must refuse to claim
an affected capability ready while its required policy is unresolved. A new
material policy conflict discovered during specification will return as a
focused question.

## Sources

- [Approved unit catalogue](../units-generation/unit-of-work.md),
  [dependency DAG](../units-generation/unit-of-work-dependency.md) and
  [requirement map](../units-generation/unit-of-work-story-map.md).
- [Approved domain catalogue](../domain-design/components.md),
  [decisions](../domain-design/decisions.md) and
  [accepted review findings](../domain-design/reviews/review-01.md).
- [Approved requirements](../requirements-analysis/requirements.md), including
  NFR10 and the explicit open questions/closure dependencies.
- [Feasibility answers](../../ideation/feasibility/feasibility-questions.md),
  [scope backlog](../../ideation/scope-definition/intent-backlog.md) and
  [approved interaction specification](../refined-mockups/interaction-spec.md).
- Current bounded source references above and the
  [reference API inventory](../../../../codekb/DocSuri/api-documentation.md).

## Consolidated Summary Confirmation

- Define formal interfaces across the approved eight units and retained external
  surfaces while keeping one shared application, embedded feature modules and
  a separately controlled operator executable.
- Specify typed module/shared-data contracts, browser HTTP/JSON and recoverable
  progress, and durable background-work messages without selecting a paid stack,
  framework, broker or hosting provider.
- Preserve public registration, existing anonymous search, private owner
  isolation and administrator/operator boundaries. Verify the detailed access
  matrix and actual external consumers; add no new public API product or broader
  guest capabilities.
- Pin identity/revision, acceptance, validation, errors, timeout/retry,
  idempotency, cancellation and recovery behavior. Keep acknowledged drafts,
  committed work, prepared results and explicitly approved external effects
  distinct; unknown remote outcomes require reconciliation.
- Define module registration, lifecycle participation and compatibility so the
  initial application runs independently of future modules and complete
  integration verifies every required participant.
- Make projection write/rebuild/withdrawal ownership explicit and bind export
  approval to the exact immutable research artifact revision and destination.
  Carry these through formal specs and later executable checks.
- Document versioning and coordinated breaking changes. Verify existing
  consumers before removing relied-on behavior; provider adapters retain their
  current capabilities under verified free/local constraints.
- Produce the contract summary with formal inline specifications, requirement
  mapping, ownership, error/recovery rules, validation and independent review.
  Keep users/data, backups, obligations, retention/shared-device treatment,
  migration, resource capacity and numeric targets as explicit prerequisites
  wherever their unresolved evidence blocks a decision or implementation.
- Follow CONVENTIONS.md: completed branches merge through PRs into develop under
  the interim CI policy; main promotion remains separate.

Does this all look correct before I re-save the artifact from this summary?

- Looks correct
- Request changes

[Answer]: Looks correct
