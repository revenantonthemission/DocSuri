# U4 security and cross-cutting quality requirements

Unit: `u4-research-novelty`. Derived from the inception NFRs (NFR1–NFR10); each
requirement inherits its inception id and appends a sub-number.

## Scope and sources

Covers the private research and novelty behaviours specified in
`../functional-design/functional-spec.md` under `../functional-design/rules.md`.
Sources: [RQ] `inception/requirements-analysis/requirements.md` (NFR1–NFR10);
[CT] `inception/contract-design/contract-summary.md` (C07, C12, C14, C13);
[FD] this unit's functional design; [KB] the code knowledge base's
technology-stack record. Numeric latency, capacity and recovery targets are not
selected here; the measurement requirements are in `tech-stack-decisions.md`.

## Assets, trust boundaries and threat model

- **Assets**: owner-written drafts and private attachments; extracted text and
  retrieved web references; accepted turns, novelty analyses and their
  discussion; immutable research artifacts; evidence provenance; usage records.
- **Boundaries**: browser → service (untrusted input, untrusted rendered
  content); service → local model/extraction adapter (untrusted output, `C12`);
  service → durable execution and completion facts (`C14`); service →
  U6 export consumer (`C07` `readNoveltyArtifactForExport`); service → public
  corpus routes (must never resolve private identity).
- **Primary threats**: cross-owner and cross-context disclosure; private
  identity resolved through public routes; prompt/instruction injection from
  uploaded or retrieved content; silent overwrite or loss on draft conflict;
  duplicate submission and duplicate accounting; late worker facts resurrecting
  deleted or cancelled work; unread web references presented as evidence;
  fabricated grounding from malformed model output; unbounded upload or model
  work activating paid capacity.

## Derived requirements

### NFR1 — complete-task correctness

- **NFR1.1** A grounded turn produces source-associated output on controlled
  positive, contradictory and insufficient-evidence fixtures, and abstains or
  returns a disclosed partial result rather than invented support.
- **NFR1.2** An accepted turn or novelty job is recoverable end to end through
  the mounted host: committed input, authoritative progress and terminal state
  agree after interruption and restart.
- **NFR1.3** Every private surface (session, turn, draft, attachment, asset,
  artifact, job snapshot) denies a non-owner and a wrong-context request, and
  the denial is verified, not assumed.
- **NFR1.4** An owner-supplied web reference that was not actually retrieved is
  excluded from grounding evidence and is never presented as support the analysis
  read.
- **NFR1.5** Any optional novelty score is reported only with its recorded method
  scale (`minimum <= score <= maximum`) and the evidence IDs it cites, and is
  never presented as proof of scientific novelty.

### NFR2 — responsiveness and smooth interaction

- **NFR2.1** Save acknowledgement, reopen and progress feedback are distinct and
  timely, and a pending or unknown state is never rendered as a completed result.
- **NFR2.2** Progress is ordered and monotonic per operation; an older snapshot
  never overwrites a newer one, and no infinite loading or feedback loop occurs.
- **NFR2.3** A double action, slow response or reconnect does not submit the same
  intended work twice.

### NFR3 — durability and interruption recovery

- **NFR3.1** Accepted work recovers its authoritative state after lost response,
  offline/reconnect, sleep and process restart; an interrupted multi-step write
  is never presented as fully successful.
- **NFR3.2** The immutable accepted input is preserved across retries, and a
  retry never mutates it.
- **NFR3.3** A submission consumes exactly its submitted draft revision and a
  concurrent newer acknowledged revision survives.
- **NFR3.4** A session/context tombstone dominates late draft saves, late
  results and late reads.
- **NFR3.5** Cancellation and completion racing produce exactly one terminal
  outcome, and cancellation never implies remote export cancellation.

### NFR4 — multi-user security

- **NFR4.1** Owner **and** context are enforced server-side on every list,
  direct read, mutation, event, asset, draft and result path.
- **NFR4.2** Private attachment and artifact identity never resolves through a
  public corpus route, and per-asset reads reject arbitrary paths and
  cross-context reuse.
- **NFR4.3** Uploaded, retrieved and model-generated content is untrusted: it can
  neither grant privilege nor authorize an external action.
- **NFR4.4** An anonymous, revoked or expired session receives no private read,
  list, event or asset.
- **NFR4.5** Credentials and secrets stay in protected configuration/storage and
  never enter browser responses, observations or untrusted prompts.
- **NFR4.6** Before any outbound retrieval of an owner-supplied web reference,
  the target is validated — allowed scheme and host, rejection of private,
  loopback and link-local addresses, and rejection of redirects to them — and a
  non-conforming target is refused with a typed error rather than fetched. This
  obligation is owned here and is not silently delegated to the `C12` adapter.

### NFR5 — privacy and permitted processing

- **NFR5.1** Private uploads, drafts, evidence and artifacts are classified, and
  their provenance and obligations are recorded before affected processing or
  storage choices are made.
- **NFR5.2** Durable draft persistence, restore, discard and consumption remain
  refused with a policy-unresolved outcome until retention, erasure, storage and
  shared-device policy is resolved; no durability or shared-device isolation is
  claimed before then.
- **NFR5.3** Deletion and revocation cover caches, derived artifacts and queued
  work, and controlled restore preserves owner relationships.
- **NFR5.4** A private upload is never published to the public corpus, and public
  access is never assumed to permit private ingestion or redistribution.
- **NFR5.5** A deletion acknowledgement is not erasure proof: deleted sessions,
  drafts, attachments and results cannot reappear through a stale link, replay or
  restore, and backup plus externally exported-copy treatment follows the
  resolved policy rather than being assumed. Until that policy is resolved, no
  erasure-completeness claim is made.

### NFR6 — usable and accessible controls

- **NFR6.1** Research and novelty interactions support keyboard operation,
  meaningful labels/status/error announcements, visible focus and preserved
  context on errors or re-authentication.
- **NFR6.2** Destructive actions (session deletion, attachment removal, draft
  discard) state their exact scope and require a deliberate confirmation.
- **NFR6.3** Research and novelty surfaces carry readable contrast and support
  zoom/reflow against the unit's WCAG 2.2 AA target, alongside the keyboard,
  announcement and focus behaviour of NFR6.1.

### NFR7 — repairability and reproducibility

- **NFR7.1** A clean checkout reproduces a representative research/novelty
  defect with safe synthetic fixtures and documented prerequisites.
- **NFR7.2** Diagnosis and recovery instructions cover draft, tombstone, job and
  artifact states, including the policy-suspended draft path.
- **NFR7.3** A repair is verified by a regression check plus the affected
  integration checks through the mounted host.

### NFR8 — sustainable $0 capacity

- **NFR8.1** Upload bytes, queue depth, retries and concurrency are bounded so
  public registration cannot cause unbounded work or silent billable overages.
- **NFR8.2** Only free/local extraction and model paths are used; exhaustion
  produces a bounded, honest refusal and never a paid fallback.

### NFR9 — actionable, privacy-aware observability

- **NFR9.1** A user-visible research or novelty failure links to the relevant
  job/dependency evidence through safe identifiers, without private text or
  credentials.
- **NFR9.2** Signals distinguish observed, estimated, unknown and stale evidence,
  and survive retries and restarts without erasing required evidence.

### NFR10 — contract and integration consistency

- **NFR10.1** U4's behaviour matches C07's operations, invariants, checks and
  state machines, with C12/C14 error and delivery semantics.
- **NFR10.2** The immutable `artifactId`/`revision`/`contentHash` identity and its
  eligibility recheck are agreed with U6 and verified by executable checks.
- **NFR10.3** Test doubles are held to the same contract as the real mounted
  path; mocks alone cannot establish normal-path parity.
- **NFR10.4** Exactly one usage record is reconciled per accepted turn or
  novelty job; retries and duplicate deliveries never book a second record,
  unknown usage is reported as unknown, and no accounting path activates
  spending.
