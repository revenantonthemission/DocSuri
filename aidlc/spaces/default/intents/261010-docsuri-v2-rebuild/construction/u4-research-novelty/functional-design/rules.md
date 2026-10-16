# U4 — Research and novelty · Business rules

Unit: `u4-research-novelty`. Owner component: `ResearchWorkspace`.

This file is the source of truth for the unit's decision logic. Ordered
behaviour (workflows and state transitions) is the source of truth in
`functional-spec.md`; entity shapes are the source of truth in `entities.md`.

```yaml
rules:
  - id: BR1.1
    statement: Every private read or write derives its owner from the authenticated request context and ignores any browser-supplied owner.
    category: authorization
    applies_to: ResearchWorkspace reads, writes, lists, events, assets and results
    trigger: Any request touching a private context, session, turn, attachment, draft or artifact
    logic: IF the request is not bound to an authenticated owner THEN refuse UNAUTHENTICATED; OTHERWISE derive accountId server-side and never trust a supplied owner field.
    violation_behaviour: Refuse with UNAUTHENTICATED or FORBIDDEN; reveal no resource existence.
    source: FR2.3, NFR4

  - id: BR1.2
    statement: Context scope is enforced within an owner, not merely between accounts.
    category: authorization
    applies_to: DraftRevision, PrivateAttachment, ResearchSession, ResearchTurn, NoveltyAnalysis, ResearchArtifact
    trigger: Any access that presents a context reference
    logic: IF the resolved context does not belong to the authenticated owner or is not the context recorded on the resource THEN refuse FORBIDDEN.
    violation_behaviour: Refuse FORBIDDEN; do not rebind the resource to the caller's context.
    source: FR2.3, NFR4

  - id: BR1.3
    statement: Private attachment and artifact identity never resolves through a public corpus route.
    category: authorization
    applies_to: PrivateAttachment, ResearchArtifact
    trigger: Any public-route resolution attempt using a private identifier
    logic: IF a private identifier is presented to a public corpus surface THEN refuse NOT_FOUND and log nothing that exposes private content.
    violation_behaviour: Refuse NOT_FOUND; never publish or copy private content to a public surface.
    source: FR2.3, FR13.2

  - id: BR1.4
    statement: Each private asset read is authorized individually; arbitrary paths and cross-context reuse are refused.
    category: authorization
    applies_to: PrivateAttachment assets
    trigger: An asset or download read
    logic: IF the requested asset is not an authorized reference of an attachment in the caller's context THEN refuse FORBIDDEN; never resolve a caller-supplied path.
    violation_behaviour: Refuse FORBIDDEN; traversal and unsafe rendered content cannot escape the permitted document scope.
    source: FR2.3, NFR4

  - id: BR1.5
    statement: A revoked, expired or anonymous session receives no private read, list, event or asset.
    category: authorization
    applies_to: All ResearchWorkspace read surfaces
    trigger: A request under a revoked or anonymous session
    logic: IF current authority is not verifiable THEN refuse UNAUTHENTICATED and return no pending or terminal private state.
    violation_behaviour: Refuse UNAUTHENTICATED; no cached private rendering is treated as authority.
    source: NFR4, FR14.2

  - id: BR2.1
    statement: A claim is linked to the exact accessible source, version and location that were actually read.
    category: constraint
    applies_to: EvidenceRecord of kind claim
    trigger: Preparing or reading turn/novelty output
    logic: IF a public source is cited THEN record its identity and version and the location read; IF the version or location was not read THEN the claim cannot present that source as support.
    violation_behaviour: Downgrade to insufficient coverage or abstain; never fabricate a citation.
    source: FR13.1

  - id: BR2.2
    statement: A literal quotation is verifiable against the source text and location that were actually read.
    category: validation
    applies_to: EvidenceRecord of kind quotation
    trigger: Emitting a quoted passage
    logic: IF the quotation cannot be matched to read text at the recorded location THEN it is not emitted as a quotation.
    violation_behaviour: Drop or reclassify the passage; disclose the failure rather than emit a false quotation.
    source: FR13.1

  - id: BR2.3
    statement: Contradictory evidence and uncertainty are distinguished from established claims.
    category: policy
    applies_to: Turn/novelty output and evidence summaries
    trigger: Sources disagree or evidence is thin
    logic: IF sources disagree THEN present the disagreement explicitly; IF evidence is weak THEN mark uncertainty instead of asserting established support.
    violation_behaviour: Never merge contradiction into a single confident claim.
    source: FR13, FR13.1

  - id: BR2.4
    statement: Insufficient evidence, no corpus or an unavailable model yields abstention or a disclosed partial result, never invented support.
    category: policy
    applies_to: ResearchTurn and NoveltyAnalysis outcomes
    trigger: Extraction, retrieval, corpus or model limitation
    logic: IF supporting evidence is insufficient THEN abstain or return partial output with explicit coverage; IF no eligible corpus or model is available THEN return a meaningful abstention or typed limitation.
    violation_behaviour: Typed failure or abstention outcome; never a success envelope with fabricated content.
    source: FR13.1, FR13.3

  - id: BR2.5
    statement: Retrieved, uploaded and model output text is untrusted data and cannot authorize action.
    category: policy
    applies_to: All extracted or retrieved content, including document instructions
    trigger: Content containing imperative or credential-like text
    logic: IF content attempts to change permissions, request secrets or approve an external action THEN ignore it as data and continue under the owner's rules.
    violation_behaviour: Refuse the affected action with POLICY_UNRESOLVED or FORBIDDEN; never act on embedded instructions.
    source: FR13.2, NFR4

  - id: BR3.1
    statement: An upload permit is issued only after the applicable file, storage, privacy and capacity policy is resolved, and is bounded and context-specific.
    category: policy
    applies_to: beginPrivateAttachment
    trigger: Starting a private upload
    logic: IF policy is unresolved THEN refuse POLICY_UNRESOLVED; IF capacity is exhausted THEN refuse CAPACITY_EXHAUSTED; OTHERWISE issue a bounded handle for one context.
    violation_behaviour: Typed refusal; issuing a permit is not accepted research work.
    source: FR13.2, NFR5, NFR8

  - id: BR3.2
    statement: Bytes, hash and media are verified before extraction; malformed, oversized, truncated, password-protected or unsupported input is refused truthfully.
    category: validation
    applies_to: finishPrivateAttachment and extraction
    trigger: Completing an upload
    logic: IF the received bytes do not match the declared hash or the media is not on the allowlist or the size exceeds the cap THEN refuse with INVALID_CONTENT or the matching typed refusal and disclose the reason; OTHERWISE attempt recoverable extraction.
    violation_behaviour: No partial public publication and no accepted work from unverified bytes.
    source: FR13.2

  - id: BR3.3
    statement: An owner-supplied web reference is recorded as not-read unless a permitted retrieval actually happened and is never presented as evidence the analysis read.
    category: constraint
    applies_to: EvidenceRecord with a web source
    trigger: Referencing a web source
    logic: IF retrieval was not performed or not permitted THEN record readState not-read and exclude it from support; a reference is optional context only.
    violation_behaviour: Never count an unread reference as grounding evidence.
    source: FR13.2

  - id: BR3.4
    statement: A private attachment or asset is never published to the public corpus.
    category: constraint
    applies_to: PrivateAttachment and derived assets
    trigger: Any processing of a private attachment
    logic: IF content originated from a private upload THEN keep it within its owner context; no public publication path is reachable.
    violation_behaviour: Block publication; record the attempt without exposing content.
    source: FR2.3, FR13.2

  - id: BR4.1
    statement: Only acknowledged draft revisions are recoverable; a failed or in-flight save promises nothing.
    category: constraint
    applies_to: DraftRevision
    trigger: Save, restore or read of a draft
    logic: IF the revision is not durably acknowledged THEN it must not be offered for recovery and the UI must not present it as saved.
    violation_behaviour: Restore returns only acknowledged unconsumed revisions; never a speculative one.
    source: FR14, NFR3

  - id: BR4.2
    statement: A draft save uses compare-and-set on the base revision; a conflict returns the authorized current revision and the proposed text without silently overwriting either.
    category: validation
    applies_to: saveDraft
    trigger: Saving owner text
    logic: IF baseRevision is null THEN create a new draft; IF the base revision is not current THEN refuse CONFLICT with the current authorized revision and the proposed text; OTHERWISE record a new immutable acknowledged revision.
    violation_behaviour: No silent overwrite; conflict is a normal outcome, not data loss.
    source: FR14, NFR3

  - id: BR4.3
    statement: An accepted submission consumes exactly the submitted draft revision, and a concurrent newer acknowledged revision survives.
    category: constraint
    applies_to: acceptResearchTurn, acceptNoveltyAnalysis, acceptNoveltyDiscussion
    trigger: A submitted draft is supplied with an accepted operation
    logic: IF owner, context, kind and content hash match the acknowledged revision THEN bind consumption of that exact revision to the accepted operation; IF they do not match THEN refuse without consuming anything.
    violation_behaviour: Never consume a newer edit; never silently submit different text.
    source: FR14, FR15

  - id: BR4.4
    statement: Restore returns only the retained acknowledged unconsumed revision for the same owner after authentication and never submits or produces an external effect.
    category: policy
    applies_to: restoreDraft
    trigger: A client asks to recover text
    logic: IF the owner is authenticated, the revision is acknowledged, unconsumed and not deleted THEN return it; OTHERWISE refuse with a typed outcome.
    violation_behaviour: Restoring text never creates a job, turn or export.
    source: FR14, NFR3

  - id: BR4.5
    statement: Discard targets the exact acknowledged revision; a stale discard cannot erase a newer edit.
    category: constraint
    applies_to: discardDraft
    trigger: A discard request
    logic: IF the presented revision is current THEN record the durable deletion boundary and discard it; IF a newer acknowledged revision exists THEN refuse CONFLICT and leave it intact.
    violation_behaviour: Refuse CONFLICT; never erase newer work.
    source: FR14, FR15

  - id: BR4.6
    statement: Durable draft persistence, restore, discard and consumption refuse with a policy-unresolved outcome until retention, erasure, storage and shared-device policy is resolved.
    category: policy
    applies_to: All durable-draft operations
    trigger: Any durable draft operation while policy is unresolved
    logic: IF the applicable policy is unresolved THEN refuse POLICY_UNRESOLVED and surface the state; the design must not promise draft recovery, shared-device isolation or erasure completeness before then.
    violation_behaviour: Typed policy refusal; no implied durability guarantee.
    source: NFR5

  - id: BR4.7
    statement: A session tombstone rejects late draft saves and restores.
    category: constraint
    applies_to: DraftRevision inside a deleted session
    trigger: A save or restore after deletion
    logic: IF the session or context deletion boundary is set THEN refuse the write and keep the tombstone authoritative over the late save.
    violation_behaviour: Refuse; deleted drafts cannot reappear on replay or restore.
    source: FR14.2

  - id: BR5.1
    statement: Opening or reading a session returns committed turns and authoritative pending state and never submits work.
    category: constraint
    applies_to: createResearchSession, readResearchSession, listResearchSessions
    trigger: Session open, read or list
    logic: IF the caller owns the session THEN return committed turn references and current pending/terminal state; never enqueue, regenerate or re-execute from a read.
    violation_behaviour: Reads are side-effect free; presentation never creates jobs.
    source: FR14.1

  - id: BR5.2
    statement: A repeated request does not duplicate the intended turn.
    category: constraint
    applies_to: acceptResearchTurn, acceptNoveltyAnalysis, acceptNoveltyDiscussion
    trigger: Retry, reconnect or duplicate delivery
    logic: IF the normalized intent matches an already accepted operation THEN return the existing accepted identity (or an idempotency conflict for the same key with different content) instead of accepting a second turn.
    violation_behaviour: Refuse IDEMPOTENCY_CONFLICT or return the existing operation; never double-accept.
    source: FR14.1, NFR3, FR15.2

  - id: BR5.3
    statement: Late worker completion binds to the correct session and immutable input, or is rejected.
    category: validation
    applies_to: completeResearchWork
    trigger: A worker completion fact arrives
    logic: IF the operation kind, context, active unexpired lease and input hash all match THEN commit the result; OTHERWISE reject the fact without changing state.
    violation_behaviour: Stale worker generations, revoked authority and mismatched inputs cannot overwrite or resurrect work.
    source: FR14.1, NFR3

  - id: BR5.4
    statement: Deleting one or all owned sessions affects only the owner's work, writes a durable tombstone before cleanup, and reports a failed commit with recoverable state.
    category: policy
    applies_to: deleteResearchSessions
    trigger: Session-set deletion
    logic: IF the caller owns the sessions THEN require explicit confirmation, CAS the boundary, write the durable tombstone, then clean up under the defined pending-work, draft, asset and derived-data disposition; IF the commit fails THEN report it and leave state recoverable.
    violation_behaviour: A's deletion never affects B; deletion failure is reported, not hidden.
    source: FR14.2

  - id: BR5.5
    statement: Deleted work cannot be reopened through a stale direct link or a stale list snapshot.
    category: constraint
    applies_to: Session and turn reads
    trigger: A stale link or expired snapshot
    logic: IF the tombstone boundary is set THEN refuse NOT_FOUND regardless of a stale list or link.
    violation_behaviour: Refuse NOT_FOUND; tombstones dominate late reads.
    source: FR14.2

  - id: BR6.1
    statement: Topic and manuscript novelty modes are distinct immutable input snapshots, and unsupported manuscript formats produce truthful limitations.
    category: validation
    applies_to: NoveltyAnalysis
    trigger: Accepting a novelty request
    logic: IF inputMode is topic THEN freeze the topic and source scope; IF inputMode is manuscript THEN require an eligible owner attachment and freeze its content reference; IF the format is unsupported THEN refuse with a truthful limitation.
    violation_behaviour: Typed limitation; never a fabricated result for unsupported input.
    source: FR15.1

  - id: BR6.2
    statement: A generated score or claim is never presented as proof of scientific novelty beyond the recorded evidence and method.
    category: policy
    applies_to: NoveltyAnalysis results and discussion
    trigger: Rendering novelty output
    logic: IF an optional assessment is shown THEN use its recorded `NoveltyAssessment` method scale with minimum <= score <= maximum and reference existing evidence IDs, and never claim proof of novelty.
    violation_behaviour: Present limitations and method; refuse a proof claim.
    source: FR15.1

  - id: BR6.3
    statement: A novelty discussion binds to the same owner's eligible immutable result and neither reruns analysis nor approves export.
    category: constraint
    applies_to: acceptNoveltyDiscussion
    trigger: Starting a discussion on a result
    logic: IF the referenced result belongs to the owner, is ready and is eligible THEN accept a separate discussion job bound to that immutable revision; OTHERWISE refuse SOURCE_INELIGIBLE.
    violation_behaviour: Refuse; discussion never recomputes analysis and never authorizes export.
    source: FR15.1, FR16.1

  - id: BR6.4
    statement: A cancellation request is not cancellation completion; compare-and-set decides the single terminal outcome and a completed result stays succeeded if completion won.
    category: policy
    applies_to: cancelNoveltyAnalysis and completion
    trigger: Cancellation racing completion
    logic: IF cancellation is requested first THEN return cancel_requested until cancellation authoritatively wins; IF completion commits first THEN the result stays succeeded and the cancellation reports cancelled only after it wins.
    violation_behaviour: Exactly one terminal outcome; no state is overwritten.
    source: FR15.2

  - id: BR6.5
    statement: After cancellation is acknowledged, late events do not resurrect the job or start an unapproved export.
    category: constraint
    applies_to: Cancelled novelty jobs
    trigger: A late worker fact or stream event after cancellation
    logic: IF the operation is terminally cancelled THEN reject late publication and any export initiation.
    violation_behaviour: Reject the fact; no resurrection, no automatic export.
    source: FR15.2, FR16.2

  - id: BR7.1
    statement: The tuple (artifactId, revision, contentHash) identifies immutable canonical output, and new content never overwrites it.
    category: constraint
    applies_to: ResearchArtifact
    trigger: Preparing or reading an artifact
    logic: IF content differs from the stored revision THEN it is recorded as a new revision with a new hash; the previous tuple remains unchanged.
    violation_behaviour: Refuse to overwrite; immutable tuple always returns identical bytes.
    source: FR15.2, FR16.2

  - id: BR7.2
    statement: An export read returns only a ready novelty result at its exact identity and content hash with current eligibility rechecked; changed bytes require a new revision.
    category: policy
    applies_to: readNoveltyArtifactForExport
    trigger: The ApprovedExport consumer reads a source artifact
    logic: IF the artifact is a ready novelty result, the identity/revision/hash match and eligibility holds THEN return the immutable content plus the eligibility revision; OTHERWISE refuse NOT_FOUND or SOURCE_INELIGIBLE.
    violation_behaviour: Refuse; eligibility revocation prevents a pending export.
    source: FR16.1, FR16.2

  - id: BR7.3
    statement: Artifacts and discussion stay owner-scoped and follow declared retention/expiry; unavailable, expired or deleted reads never regenerate work or trigger an export.
    category: policy
    applies_to: readResearchArtifact, readResearchTurn
    trigger: Reading an unavailable or expired artifact
    logic: IF availability is expired, deleted or unavailable THEN return the typed availability state without regeneration; no export is initiated.
    violation_behaviour: Disclose availability; never silently recompute or export.
    source: FR15.2

  - id: BR7.4
    statement: No artifact or evidence read succeeds without owner authority; a trusted consumer acts only for the current owner.
    category: authorization
    applies_to: ResearchArtifact and EvidenceRecord reads
    trigger: Any artifact read, browser or trusted consumer
    logic: IF the caller is the owner with current authority, or a trusted registered consumer acting for the current owner, THEN allow; OTHERWISE refuse FORBIDDEN.
    violation_behaviour: Refuse FORBIDDEN; no public or cross-owner read path.
    source: FR16.1, NFR4

  - id: BR8.1
    statement: Malformed model output cannot become a false successful result.
    category: validation
    applies_to: Turn/novelty completion
    trigger: Model or extraction output fails validation
    logic: IF the output cannot be validated against the expected shape and grounding THEN record a typed failure or abstention instead of a success.
    violation_behaviour: Failed or abstained outcome; never a success envelope.
    source: FR13.3

  - id: BR8.2
    statement: Truncation and partial coverage are disclosed.
    category: policy
    applies_to: Turn/novelty output
    trigger: Context or extraction limits are hit
    logic: IF output was truncated or covers part of the request THEN record and display the limit and the covered scope.
    violation_behaviour: Disclosed limitation; never presented as complete.
    source: FR13.3

  - id: BR8.3
    statement: Interruption and retries preserve committed inputs and prevent duplicate accepted work.
    category: constraint
    applies_to: Accepted turns and novelty jobs
    trigger: Lost response, restart or reconnect
    logic: IF a retry repeats a normalized intent THEN reuse the committed input and return the authoritative state; the committed input is never mutated by a retry.
    violation_behaviour: No duplicate accepted work and no lost committed input.
    source: FR13.3, NFR3

  - id: BR8.4
    statement: A worker fact is a proposal; only the owning domain commits state, sequence and result visibility.
    category: constraint
    applies_to: completeResearchWork and job snapshots
    trigger: A completion or progress fact arrives
    logic: IF the worker holds the matching active lease and input THEN the owner validates and commits the transition; a worker sequence or revision never carries owner authority.
    violation_behaviour: Reject facts that lack current authority; no worker-authored state.
    source: NFR10, NFR3

  - id: BR8.5
    statement: Each accepted turn or novelty job reconciles exactly one usage record for the intended work.
    category: calculation
    applies_to: Accepted research and novelty work
    trigger: Acceptance and completion
    logic: IF an operation is accepted then reconcile one usage record for that operation; a duplicate delivery or retry never books a second charge and never activates spending.
    violation_behaviour: Exactly one reconciliation; unknown usage is reported as unknown, not zero or invented.
    source: FR17.2

  - id: BR8.6
    statement: Capability and health signals distinguish observed, unknown and stale evidence and omit private text and credentials.
    category: policy
    applies_to: Emitted observations
    trigger: Emitting a capability or outcome observation
    logic: IF a value is not currently observed THEN emit unknown or stale with its age; never infer capability from process liveness.
    violation_behaviour: Honest signal class; no private text or credential in any observation.
    source: NFR9, FR19.2

  - id: BR8.7
    statement: Account, consent and lifecycle changes are rechecked before publishing outcomes or external effects.
    category: policy
    applies_to: Completion, result publication and export reads
    trigger: Authority or consent changed after acceptance
    logic: IF current authority or consent no longer permits the work THEN withhold publication or effect and record the disposition.
    violation_behaviour: Withhold and disclose; a queued effect rechecks current permission.
    source: FR6.3, FR8.1

  - id: BR9.1
    statement: Uploads, model work, retries and concurrency are bounded so public use cannot activate billable overages or unbounded work.
    category: policy
    applies_to: Private uploads and accepted work
    trigger: Capacity or queue pressure
    logic: IF a bound is reached THEN refuse with a bounded capacity outcome and backpressure; never fall back to a paid provider and never accept work that cannot be executed or recovered.
    violation_behaviour: Typed capacity refusal; no automatic purchase and no false success.
    source: NFR8, FR19.2

  - id: BR9.2
    statement: Destructive actions state their scope and consequences and require deliberate confirmation.
    category: policy
    applies_to: Session deletion, attachment and draft discard
    trigger: A destructive request
    logic: IF the action is destructive THEN present its exact scope and require a confirmation before committing the boundary.
    violation_behaviour: No destructive commit without explicit confirmation.
    source: NFR6, FR14.2
```

## Rules summary

| Group | Rules | Concern |
|---|---|---|
| BR1 | BR1.1–BR1.5 | Owner and context isolation; private identity never public; per-asset authorization; revoked-session refusal |
| BR2 | BR2.1–BR2.5 | Grounded claims and literal quotations; contradiction and uncertainty; abstention; untrusted content |
| BR3 | BR3.1–BR3.4 | Upload permit and policy; verified bytes and truthful refusals; unread web references; no public publication |
| BR4 | BR4.1–BR4.7 | Acknowledged-only recovery; CAS conflict; exact-revision consumption; restore; discard; policy suspension; tombstone dominance |
| BR5 | BR5.1–BR5.5 | Sessions and turns; idempotent acceptance; late-completion binding; owner-scoped deletion; stale-link refusal |
| BR6 | BR6.1–BR6.5 | Distinct novelty modes; no proof claims; eligible discussion binding; cancellation CAS; no resurrection |
| BR7 | BR7.1–BR7.4 | Immutable artifact tuple; export read binding; owner-scoped expiry; owner authority |
| BR8 | BR8.1–BR8.7 | Failure truthfulness; disclosed truncation; interruption safety; owner-committed state; usage reconciliation; honest observability; rechecked authority |
| BR9 | BR9.1–BR9.2 | Bounded capacity with no paid fallback; confirmed destructive actions |

Category counts: authorization 6, constraint 15, validation 6, policy 16, calculation 1 (44 rules).
Every rule traces to at least one FR or NFR; `traceability.json` maps the
acceptance rows assigned to this unit to these rules, and lists the rules that
intentionally carry no acceptance row.
