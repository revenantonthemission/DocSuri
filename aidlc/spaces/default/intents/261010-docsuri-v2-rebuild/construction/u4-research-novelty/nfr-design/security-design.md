# U4 — Research and novelty · Security and cross-cutting design

Unit: `u4-research-novelty`. Designs the patterns that satisfy the derived
requirements in `../nfr-requirements/security-requirements.md` (NFR1.1–NFR10.4)
within the contract surface of C07 (research/draft/novelty operations), C12
(provider adapter envelope) and C14 (durable accepted-work delivery).

## Design principles

1. **Authority is derived, never supplied.** Every private operation resolves
   owner and context server-side from the trusted request context; a
   browser-supplied owner, context or path is never authority (NFR4.1, NFR4.4).
2. **Immutable identities, mutable eligibility.** Accepted inputs, acknowledged
   draft revisions and prepared artifacts are immutable tuples; eligibility and
   lifecycle can change independently and dominate stale copies (NFR3.2, NFR3.3,
   NFR3.4).
3. **The owner commits state.** Workers propose facts (`C14`); only the owning
   domain validates a claim, fence and input hash and commits state, sequence and
   result visibility (NFR3.1, NFR10.1).
4. **Untrusted text is data.** Uploaded, retrieved and generated text can never
   grant privilege or authorize an external action (NFR1.4, NFR4.3).
5. **Truthful degradation over invention.** Insufficient evidence abstains; a
   missing model, corpus or capacity refuses with a typed outcome; nothing is
   silently upgraded to success (NFR1.1, NFR8.2).
6. **Policy gates close, they do not soften.** Where policy is unresolved (durable
   drafts, private retention) the operation refuses with a policy-unresolved
   outcome rather than promising a weaker behaviour (NFR5.2, NFR5.5).

## Authority and private-content enforcement

- One enforcement point per operation resolves owner, context and current
  lifecycle before any read or write; dependent records are re-resolved, never
  trusted from a stored reference (NFR4.1).
- Private identity (attachment, asset, artifact, session, draft) is bound to its
  owner and context and is never resolvable through a public corpus route; per-asset
  reads authorize an exact handle and reject arbitrary paths, traversal and
  cross-context reuse (NFR4.2).
- Direct reads, lists, events and job snapshots share the same check, so a stale
  list page or direct link cannot reveal deleted or cross-owner work (NFR3.4, NFR4.1).
- Error shapes are non-revealing: a refusal never discloses the existence of
  another owner's private resource (NFR4.1, NFR9.1).

## Durable accepted-work and completion integrity

- Acceptance commits the immutable input snapshot, the scope/kind and a
  recoverable dispatch obligation atomically (`C14`); acknowledgement never
  precedes that commit (NFR3.1, NFR10.1).
- Each accepted operation is identified by a normalized intent identity, so a
  retry, reconnect or duplicate delivery reuses the committed input instead of
  accepting a second turn or job (NFR2.3, NFR3.2).
- Progress is an owner-written ordered sequence; a worker fact claims a lease and
  carries the input hash, and a stale generation, expired claim or mismatched
  input is rejected (NFR3.1, NFR3.2).
- Completion validates the artifact hash and grounding before committing terminal
  state, and tombstones/cancellations dominate late publication (NFR3.4, NFR3.5).
- Exactly one usage reconciliation is committed per accepted operation; a
  duplicate never books a second record, unknown usage reports as unknown, and no
  path activates spending (NFR10.4).

## Draft and revision lifecycle under policy suspension

- A save is a compare-and-set on the base revision producing one immutable
  acknowledged revision with its exact content hash; a conflict returns the
  authorized current revision and the proposed text without overwriting either
  (NFR3.3).
- Consumption targets the exact submitted revision and binds it to the accepted
  operation; a concurrent newer acknowledged revision survives (NFR3.3).
- Restore returns only the retained acknowledged **unconsumed** revision for the
  same owner and produces no submission or external effect (NFR3.1).
- While retention, erasure, storage and shared-device policy is unresolved, the
  durable draft operations refuse with a policy-unresolved outcome; no durability,
  shared-device or erasure-completeness claim is made (NFR5.2, NFR5.5).
- A session/context tombstone rejects late draft saves, restores and result
  publication (NFR3.4).

## Attachment, extraction and untrusted content

- An upload permit is bounded, context-specific and issued only after policy and
  capacity resolve; the received bytes, hash and media are verified before any
  extraction (NFR5.1, NFR8.1).
- Extraction is recoverable and its output is stored as untrusted evidence with a
  typed disposition (extracted, unsupported, malformed, truncated, protected,
  failed); no partial public publication occurs and no private upload reaches the
  public corpus (NFR1.1, NFR5.4).
- Embedded instructions in uploaded, retrieved or generated text are ignored as
  data; no secret is read into a prompt and no external action is approved from
  content (NFR4.3, NFR4.5).

## Outbound retrieval safety

- Before any fetch of an owner-supplied web reference: allowed scheme and host
  only, rejection of private, loopback and link-local targets, and rejection of
  redirects to them; a non-conforming target refuses with a typed error
  (NFR4.6).
- A reference that was not actually retrieved is recorded `not-read` and excluded
  from grounding evidence; it is never presented as support the analysis read
  (NFR1.4).

## Grounded output and assessment integrity

- Evidence records carry source identity, exact version, the location actually
  read, coverage and provenance; a literal quotation requires read text and a
  matching location (NFR1.1).
- Insufficient evidence yields abstention or a disclosed partial result;
  malformed model output and truncation become a typed failure or an explicit
  limitation, never a success envelope (NFR1.1, NFR1.5).
- An optional score is rendered only with its recorded method scale
  (`minimum <= score <= maximum`) and cited evidence IDs, and is never presented
  as proof of scientific novelty (NFR1.5).

## Degradation, capacity and $0 guardrails

| Trigger | Designed behaviour |
|---|---|
| Model unavailable / context limit | Typed limitation or abstention with the reason; no invented output (NFR1.1, NFR8.2) |
| Upload over cap / unsupported media | Typed refusal before extraction; nothing partially stored (NFR8.1) |
| Queue or concurrency bound reached | Bounded backpressure with a typed capacity outcome; no unbounded work, no paid fallback (NFR8.1, NFR8.2) |
| Policy unresolved (drafts, retention) | Policy-unresolved refusal; no weaker implied guarantee (NFR5.2) |
| Eligibility revoked after acceptance | Withhold publication/export; record the disposition (NFR3.5, NFR10.2) |

No path falls back to a paid provider, and no configuration can silently activate
billable work (NFR8.2).

## Observability, readiness and repairability

- Each accepted operation carries a safe correlation identifier that links a
  user-visible failure to its job, dispatch and dependency evidence without
  private text or credentials (NFR9.1).
- Readiness and capability signals distinguish observed, estimated, unknown and
  stale values with their age; process liveness never stands in for mounted
  capability (NFR9.2).
- Diagnosis covers draft, tombstone, job and artifact states — including the
  policy-suspended draft path — with synthetic fixtures and a documented
  reproduction procedure (NFR7.1, NFR7.2).
- A repair is verified by a regression check plus the affected integration
  checks through the mounted host (NFR7.3).

## Accessibility and destructive-action design

- Research and novelty surfaces inherit the workspace's WCAG 2.2 AA interaction
  contract: full keyboard operation, visible focus, meaningful labels, and status
  and error announcements for pending, unknown, failed and terminal states
  (NFR6.1, NFR6.3).
- Readable contrast and zoom/reflow hold at the inherited design-system tokens;
  no surface introduces a colour or layout that regresses them (NFR6.3).
- Committed context is preserved across errors and re-authentication: no
  operation clears owner text or scope state on a recoverable failure (NFR6.1).
- Every destructive action — session deletion, attachment removal, draft discard —
  states its exact scope and consequences and requires a deliberate confirmation
  before the boundary is committed (NFR6.2).

## Deletion, revocation and derived-data coverage

- A deletion acknowledgement sets a durable tombstone first, then applies the
  defined disposition to pending work, drafts, private attachments and derived
  artifacts; the tombstone dominates late saves, late results and stale reads
  (NFR3.4, NFR5.3).
- Revocation or lifecycle change after acceptance withholds publication, and any
  queued or dispatched work rechecks current authority and consent before it
  takes effect (NFR5.3, NFR10.2).
- Derived data — extraction output, evidence records, prepared artifacts and
  cached views of them — is owner-scoped and covered by the same disposition as
  its source; caches are never a path to resurrected content (NFR5.3).
- Backup and externally exported-copy treatment follows the resolved retention
  policy; until that policy exists, no erasure-completeness claim is made
  (NFR5.5).

## Verification approach and test doubles

- Contract conformance is verified through the mounted host and the real stores;
  a test double is only accepted when it is held to the same contract surface
  (same operations, error vocabulary and state transitions) as the mounted path
  (NFR10.3).
- Fixtures cover support, contradiction, insufficient evidence, unread web
  references, corrupt extraction and malformed model output, so abstention and
  limitation behaviour is exercised rather than assumed (NFR1.1, NFR1.4).
- Recovery checks restart and reconnect accepted work and confirm one terminal
  outcome with one usage reconciliation (NFR3.1, NFR10.4).

## Requirement mapping

NFR1.1–NFR1.5 → grounded output and assessment integrity, attachment handling.
NFR2.1–NFR2.3 → durable accepted-work delivery, degradation ladder.
NFR3.1–NFR3.5 → completion integrity, draft lifecycle, tombstone discipline.
NFR4.1–NFR4.6 → authority enforcement, untrusted content, outbound retrieval safety.
NFR5.1–NFR5.5 → attachment handling, draft policy suspension, deletion boundaries.
NFR6.1–NFR6.3 → the `WebWorkspace` boundary in `logical-components.md`.
NFR7.1–NFR7.3 → observability, readiness and repairability.
NFR8.1–NFR8.2 → degradation, capacity and $0 guardrails.
NFR9.1–NFR9.2 → observability, readiness and repairability.
NFR10.1–NFR10.4 → durable accepted-work and completion integrity, contract conformance.
