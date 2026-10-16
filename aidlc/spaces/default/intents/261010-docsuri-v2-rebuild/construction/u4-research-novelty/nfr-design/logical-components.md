# U4 — Research and novelty · Logical components

Unit: `u4-research-novelty`. U4 is an embedded library contribution to the shared
application release: these are logical responsibilities inside the existing
`ResearchWorkspace` component, not separately deployed services.

## Logical component inventory

| Logical component | Responsibility | Contract surface |
|---|---|---|
| Research context service | Server-assigned private context; owner/context binding for every dependent record | C07 `createResearchContext` |
| Session and turn service | Sessions, committed turns, owner-only listing, tombstones; accepted grounded questions | C07 `createResearchSession`–`deleteResearchSessions`, `acceptResearchTurn`, `readResearchTurn` |
| Evidence and grounding service | Evidence records, coverage/abstention decisions, quotation verification, untrusted-text isolation | C07 turn/novelty reads; C12 `model.generate` |
| Private attachment service | Upload permits, byte/hash/media verification, recoverable extraction, per-asset authorization | C07 `beginPrivateAttachment`–`readPrivateAsset`; C12 `attachment.extract` |
| Draft service | Acknowledged immutable revisions, CAS conflict, exact-revision consumption, restore/discard under the policy gate | C07 `saveDraft`, `restoreDraft`, `discardDraft` |
| Novelty service | Distinct topic/manuscript analyses, discussion jobs, cancellation races, expiring owner-scoped artifacts | C07 `acceptNoveltyAnalysis`–`readResearchArtifact` |
| Dispatch and completion adapter | Accepted-work delivery, execution claims, completion facts, usage reconciliation | C14 `deliverAccepted`, `acquireExecutionClaim`, `recordCompletion` |
| Owner draft store (bounded) | Durable acknowledged revisions once policy permits | local persistence, policy-gated |
| Research views | WebWorkspace contribution: sessions, evidence, attachments, drafts, novelty and progress states, with the inherited WCAG 2.2 AA interaction contract (keyboard, focus, labels, announced status, contrast, zoom/reflow) and confirmed destructive scopes | C13 browser binding; security-design → "Accessibility and destructive-action design" |

## Research views (WebWorkspace contribution)

U4's views live inside the shared shell and own no application boundary. They
render acknowledged, pending, unknown and terminal states distinctly; keep
browser state untrusted; clear account-bound rendering on switch or sign-out;
restore only an authenticated acknowledged draft; and let a presentation read
create no job, turn or export. Destructive actions show their exact scope and
require confirmation, and the surfaces carry the inherited WCAG 2.2 AA
interaction contract (keyboard, focus, labels, announced status, contrast,
zoom/reflow) described in `security-design.md` → "Accessibility and
destructive-action design".

## Failure domains and blast radius

- The **draft service** and the **novelty service** are separate blast radii: a
  novelty worker failure never blocks drafting or session reads, and a draft
  conflict never affects an accepted job.
- A **model or extraction outage** degrades only grounded output and attachment
  extraction; sessions, drafts, progress reads and deletion remain available, and
  the affected operation returns a typed limitation instead of a false result.
- A **dispatch/execution outage** leaves accepted work in `accepted` with a
  recoverable dispatch obligation; reads continue to show authoritative pending
  state, and repair resumes from the claim rather than re-accepting the work.
- A **policy gate** (unresolved retention/shared-device) closes only the durable
  draft path and does not disable sessions, grounded questions, attachments or
  novelty.
- A **tombstone** closes reads and late writes for the deleted scope only.

## Isolation strategy and shared resources

- **One authority evaluation** per operation in the owning service; consumers
  (including U6's export read) authenticate as trusted components acting for the
  current owner and get no standing access (NFR4.1, NFR4.2).
- **Private storage** is owner-scoped and never addressed by caller path or
  presigned URL; assets are delivered through an authorized read (NFR4.2).
- **The local model runtime** is a shared, bounded resource: a single claim per
  execution, bounded queue and concurrency, no paid fallback (NFR8.1, NFR8.2).
- **Usage reconciliation** is owned by the entitlement boundary; U4 supplies the
  operation identity and never books a second effect (NFR10.4).
- **Read state** (`read` vs `not-read`) is a property of the evidence record, not
  of the view, so every consumer sees the same truth (NFR1.4).

## Bridge to Infrastructure Design

Infrastructure Design must resolve, for this unit: the persistence layout for
accepted operations, revisions, tombstones and evidence; the protected
object-store boundary and its retention/erasure policy (currently unresolved,
which keeps the draft gate closed); the bounded execution/queue topology behind
C14; the local model and extraction runtime pins and their resource envelope; and
the observation sink that keeps private text and credentials out of telemetry.
None of these selects a provider here.
