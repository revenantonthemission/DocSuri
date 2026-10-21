# Business Rules — U6 approved export

Date: 2026-10-19 (Asia/Seoul)
Unit: u6-approved-export. Sources: confirmed [functional-design-questions.md](functional-design-questions.md) (Q1–Q8 and the settled items), [requirements FR2 and NFR1–NFR6](../../../inception/requirements-analysis/requirements.md), [unit definition](../../../inception/units-generation/unit-of-work.md), the frozen export contract C09, its invariants and state machines (`../../../../261010-docsuri-v2-rebuild/inception/contract-design/contract-summary.md`), and Notion's developer documentation as checked on 2026-10-19. Values marked "policy" (waits, budgets, bounds, limits) are fixed in NFR requirements; the values here are the intended starting points.

Definition used throughout: an **export pair** is the owner, the source's `artifactId` and the destination's `destinationId`. U4 never changes a result in place (a re-run creates a new artifactId), so the artifactId alone identifies the source within a pair.

```yaml
rules:
  - id: BR1.1
    statement: "The Notion token is write-only and never leaves the protected export path."
    category: authorization
    appliesTo: ExportConnection
    trigger: "connection configure, any read of connection state, any error or log"
    logic: "IF a token is supplied THEN it is accepted only by the configure operation over the authenticated same-origin channel, held only as the connection's protected credential, and used only by connection validation, destination listing and reading, export writes, read-backs and reconciliation scans. It is never returned in any response, shown again in the UI, kept in browser storage, written to logs, evidence, errors or another record."
    violationBehaviour: "A path that would expose the token fails closed (the operation errors without echoing it); the token field is cleared after every submit, successful or not."
    source: FR2.1

  - id: BR1.2
    statement: "A token is stored only after Notion accepts it."
    category: validation
    appliesTo: ExportConnection
    trigger: "configure or replace"
    logic: "IF the token is empty after trimming, contains non-printable characters or exceeds a generous maximum length THEN reject with INVALID_ARGUMENT without contacting Notion; no prefix or exact-length rule is applied, because Notion treats tokens as opaque. ELSE ask Notion which integration the token belongs to; IF Notion refuses it THEN reject with INVALID_TOKEN and store nothing; IF Notion cannot be reached THEN reject with DEPENDENCY_UNAVAILABLE and store nothing; IF credential protection is unavailable THEN reject with POLICY_UNRESOLVED (BR8.3); ELSE store it protected together with the workspace name and the integration's own identity that Notion reported, set state connected, set the creation capability to unknown and advance the revision."
    violationBehaviour: "No unverified or unprotected token is ever stored; the previous connection, if any, stays exactly as it was."
    source: FR2.1

  - id: BR1.3
    statement: "One connection per owner, addressed as the owner's connection; replacing it is a compare-and-set on its revision."
    category: constraint
    appliesTo: ExportConnection
    trigger: "configure when a connection exists; read, list destinations, disconnect"
    logic: "IF the request's expected revision matches the current revision THEN the new token replaces the old one in place ELSE reject with CONFLICT and change nothing. Read, destination listing and disconnect act on the owner's single connection, so the browser never needs to know its identifier beforehand (amendment A7)."
    violationBehaviour: "Two concurrent configures cannot both win; the loser is told the connection changed and keeps no partial state."
    source: FR2.1

  - id: BR1.4
    statement: "Every connection change advances its revision and ends work bound to the older revision."
    category: constraint
    appliesTo: ExportConnection, ExportApproval, ExportEffect
    trigger: "replace, disconnect, provider-reported revocation (Notion refuses the token during any use)"
    logic: "IF the connection is replaced, disconnected or found revoked THEN advance its revision; on disconnect or revocation delete the protected token and set state disconnected or revoked; in the same step mark every approved (unconsumed) approval invalidated and every accepted effect invalidated, both with reason connection-changed. An effect already executing finishes its outstanding request and is recorded normally. An unknown effect stays unknown: it is reconciled against the identity of the integration that wrote it (BR4.4) when the current connection can read its destination, and otherwise waits for owner settlement (BR4.5)."
    violationBehaviour: "No export is ever written with a token or connection state the owner has since changed; pages already in Notion are not claimed deleted."
    source: FR2.5

  - id: BR1.5
    statement: "Destinations are pages shared with the connection that it can currently read; creation permission is reported as far as it is known."
    category: policy
    appliesTo: ExportConnection, ExportPreview
    trigger: "destination step"
    logic: "IF the owner opens the destination step THEN list the pages shared with the connection with a refresh action, because Notion's listing is neither immediate nor guaranteed complete; IF the listing is partial or unavailable THEN say so; IF it is complete and empty THEN say that no page is shared yet and how to share one. Show each page's title, a placeholder for an untitled page and enough location context to tell same-titled pages apart. A destination can be chosen only after a direct read confirms the connection can read that page's children (reconciliation needs it, BR4.4); an unreadable page is shown as unusable with the reason. Notion grants access per shared page but checks the connection-wide permission to create content only when writing, so creation permission is reported as the connection's creation capability: unknown until the first write, confirmed after a successful one, refused after a permission refusal (BR4.2); a destination is offered as writable unless it is unreadable or the capability is refused. This is how U6 reads C09's 'currently permitted destinations' (amendment A6). In the real composition only the activation destination is usable (BR8.2). Preselect lastDestinationId only when it is in the current listing and readable."
    violationBehaviour: "A destination that is not listed, not readable or not allowed cannot be chosen, and no destination claims a creation permission that Notion has not shown; a stale preselection is dropped with a notice."
    source: FR2.1

  - id: BR1.6
    statement: "A protected token that cannot be opened makes the connection unavailable, not changed."
    category: policy
    appliesTo: ExportConnection, ExportEffect
    trigger: "any use of the protected token"
    logic: "IF the protected token cannot be opened THEN set state unavailable without advancing the revision and invalidate nothing; work that needs the token waits as could-not-check (BR3.3). IF it can be opened again THEN return to connected."
    violationBehaviour: "A temporary protection problem never invalidates an owner's approval or export, and never lets one run without its token."
    source: FR2.1

  - id: BR2.1
    statement: "Only a ready novelty-analysis result, read through U4's export read, can be exported."
    category: validation
    appliesTo: ExportPreview
    trigger: "preview preparation, approval (BR3.1), continuing (BR3.7) and the pre-write check (BR3.3)"
    logic: "IF U4's export read returns the requested result at exactly the requested identity, revision and content hash, of kind novelty-result, ready, with its current eligibility re-checked THEN it may be previewed. U4's answers map as: absent or another owner's result → NOT_FOUND; a different revision or content hash → CONFLICT (a changed source); not a ready novelty result, expired, deleted or ineligible → SOURCE_INELIGIBLE; the read cannot be reached → DEPENDENCY_UNAVAILABLE. Research answers and discussion threads are not exportable in this release."
    violationBehaviour: "No preview, approval or write exists for an ineligible, expired, deleted or different result; a temporary read failure is never reported as ineligibility."
    source: FR2.2

  - id: BR2.2
    statement: "Reading, previewing, cancelling and closing never write to Notion and never approve."
    category: policy
    appliesTo: ExportPreview, ExportApproval, ExportEffect
    trigger: "preview preparation, any read, status polling, cancel, closing the flow"
    logic: "IF an operation is not the explicit approve-and-export press (approve, then execute) or the continuation of an interrupted press (execute on its existing approval, BR3.7) THEN it performs no Notion write and creates no approval or effect."
    violationBehaviour: "n/a (structural rule); verified by tests asserting zero provider writes for every other operation."
    source: FR2.2

  - id: BR2.3
    statement: "A preview revision freezes everything the owner approves, and shows exactly what will be written."
    category: constraint
    appliesTo: ExportPreview
    trigger: "preview preparation"
    logic: "IF a preview is prepared for an export pair THEN it is a new immutable revision of that pair's preview (same previewId, next revision; previews are identified by previewId and revision together). The versioned render policy maps the result deterministically to a canonical block tree: the page title, then the summary, assessments, evidence items (each one top-level block with its quote, claim and source nested under it), coverage, limitations and method, and as the last top-level block the export marker (BR4.1). renderedText is the plain-text projection of that tree shown to the owner; renderedContentHash covers the canonical tree itself, so the written blocks are exactly the hashed ones. The page title, which is also the preview's source title, is the result summary's first sentence cut at a word boundary (policy: about 60 characters), prefixed '신규성 분석 — ', with '신규성 분석 결과' and the artifact's short identifier as the fallback when the summary is empty. The preview records the source tuple (artifactId, revision, contentHash) and eligibility revision, the destination snapshot, the connection revision, the render policy and the marker. bindingHash is the canonical hash of: owner, source tuple, source eligibility revision, destinationId, connection revision, render policy and renderedContentHash."
    violationBehaviour: "Any change to a bound fact or to the rendering produces a different bindingHash, so an approval of an old revision can no longer match (BR3.1, BR3.3); the owner never approves text that differs from the written blocks."
    source: FR2.3

  - id: BR2.4
    statement: "The rendered block tree must fit one page-creation request, or the preview refuses."
    category: constraint
    appliesTo: ExportPreview
    trigger: "rendering"
    logic: "IF the canonical block tree fits Notion's single-request limits for creating a page with its content (at most 100 top-level blocks and 100 items in any block list, at most two nested levels below a top-level block, at most 1,000 blocks and 500 KB in total, text runs of at most 2,000 characters split at word or sentence boundaries) THEN the preview is offered ELSE the preview is refused with a plain reason. Content is never silently truncated and an export is never split across several write requests. U4's bounded result size (at most 32 KB and 32 evidence items) fits this layout. Text is written as plain text, never interpreted as markup. Limits as documented by Notion on 2026-10-19."
    violationBehaviour: "An oversized result cannot be exported in this release, and the owner is told why; no partial page can exist."
    source: FR2.4

  - id: BR2.5
    statement: "Earlier exports of the same export pair are shown before approval."
    category: policy
    appliesTo: ExportPreview
    trigger: "preview preparation"
    logic: "IF effects exist for the same export pair THEN the preview lists them: succeeded ones with date and page link, and ones that ended not-found-after-checks or owner-settled-not-delivered marked 'may exist in Notion'. ELSE no notice. (An unknown one blocks a new export, BR5.1.)"
    violationBehaviour: "A second copy is possible only as a deliberate, separately approved export, never silently."
    source: FR2.4

  - id: BR2.6
    statement: "Rendered copies of a result are kept only as long as they are needed."
    category: policy
    appliesTo: ExportPreview
    trigger: "approval, settlement, periodic housekeeping"
    logic: "IF a preview revision can no longer be approved (superseded by a newer revision, or its approval consumed, cancelled or invalidated) and any effect bound to it has settled (succeeded, failed, cancelled, invalidated) THEN its rendered tree and text are removed and only identifiers, source and destination titles, hashes, timestamps, outcome and link remain. An unapproved preview revision is removed entirely after the retention period (policy: 7 days)."
    violationBehaviour: "No full rendered copy of a research result outlives its use; the history and the earlier-export notice keep working from the summary."
    source: FR2.2

  - id: BR3.1
    statement: "Only the owner's explicit press approves, and only the current exact preview."
    category: authorization
    appliesTo: ExportApproval
    trigger: "approve call of the approve-and-export press"
    logic: "IF the request is a replay (BR3.2) THEN return the original. ELSE IF the request lacks explicitApproval true THEN it is malformed (INVALID_ARGUMENT). ELSE IF previewId, previewRevision and bindingHash do not name the owner's current preview revision of the pair THEN CONFLICT. ELSE re-derive the binding from current facts: the source re-read (BR2.1, mapped as there), the destination readable and allowed (BR1.5; FORBIDDEN in the real composition for another destination, BR8.2), the connection revision, the owner's session current; and no export of the pair succeeded after the preview was prepared (CONFLICT, so a fresh preview shows it, BR2.5). Any mismatch refuses and records nothing; otherwise record the approval."
    violationBehaviour: "Analysis completion, preview, reads, polling or cancel can never authorize an export; a stale preview leads to a fresh one, never to a write."
    source: FR2.3

  - id: BR3.2
    statement: "Replays return the original; one preview revision has at most one approval and one approval binds exactly one effect."
    category: constraint
    appliesTo: ExportApproval, ExportEffect
    trigger: "approve-and-export press, a repeated press, a second tab on the same preview revision, continuing an interrupted press"
    logic: "Idempotency keys are scoped per owner and per operation: the press sends its key on both calls, and the approve call and the execute call each keep their own record of it. IF the approve call's key was already used, or the preview revision already has an approval THEN return that approval (and its effect, if bound) before any other check. IF the execute call's key was already used, or the approval already has an effect THEN return that effect before any other check. ELSE the approve call records the approval (BR3.1) and the execute call binds its one effect in state accepted, durably, before any provider write; binding consumes the approval. A press interrupted between the two leaves the approval approved and unconsumed; it can be continued (BR3.7) or cancelled (BR3.6) from the export history."
    violationBehaviour: "Duplicate presses and parallel tabs on the same preview revision yield the same single effect; a reused key with a different payload on the approve call is IDEMPOTENCY_CONFLICT, and on the execute call returns the existing effect only when it names the same approval, otherwise CONFLICT."
    source: FR2.3

  - id: BR3.3
    statement: "Before every provider write, the bound facts are checked again; 'changed' and 'could not check' are different."
    category: authorization
    appliesTo: ExportEffect
    trigger: "each write attempt, including a resumed rate-limit retry"
    logic: "Check: the source re-read exactly as bound with the same eligibility revision (BR2.1); a direct read of the bound destination page; the connection revision unchanged; the approving owner's session current and the account active (as AccountAccess reports now; signing out, session expiry or an accepted withdraw or erase has already revoked it); in the real composition the destination allowed (BR8.2). IF something definitely changed THEN an accepted effect becomes invalidated, and an effect executing in a rate-limit wait becomes failed, with the reason source-changed, destination-changed, connection-changed or authority-revoked; nothing is written. IF something could not be checked (U4's read or Notion unreachable, credential unavailable BR1.6, policy unresolved BR8.3) THEN nothing is written and the effect waits and is checked again on later worker passes; when the wait bound (policy: 24 hours from the first could-not-check) passes it becomes failed (dependency-unavailable or policy-unresolved). When the check passes, the move accepted → executing and the recording of the attempt (start time, writer identity, connection revision) happen as one atomic step, a compare-and-set that fails if the effect changed meanwhile: this is U6's single point where a write becomes authorised, and no executing effect ever lacks its outstanding attempt."
    violationBehaviour: "No write ever uses stale authority, a changed result or a changed destination, a passing outage never destroys a valid approval, and a crash can never strand an executing effect without an attempt."
    source: FR2.5

  - id: BR3.4
    statement: "An unconsumed approval is invalidated by any change to what it approved."
    category: constraint
    appliesTo: ExportApproval
    trigger: "connection change (BR1.4), account withdrawal (BR6.1), a definite change found when continuing (BR3.7), or housekeeping (Workflow 9)"
    logic: "IF an approved, unconsumed approval's binding definitely changed THEN it becomes invalidated with reason source-changed, destination-changed, connection-changed, authority-revoked or account-withdrawn, and the owner is offered a fresh preview. Housekeeping on each worker pass invalidates an unconsumed approval whose approving session is no longer current (authority-revoked) and, while the session is current, one whose source U4 no longer exports (source-changed); its rendered copy is then trimmed (BR2.6). A consumed approval is never changed again: from then on its effect carries the outcome (BR3.3)."
    violationBehaviour: "An invalidated approval never authorizes a write and is never revived; only a new preview revision and approval can. No unconsumed approval lingers past its session or its source."
    source: FR2.5

  - id: BR3.5
    statement: "Approval validity is defined by the binding, not by a clock."
    category: policy
    appliesTo: ExportApproval
    trigger: "approval"
    logic: "IF an approval is recorded THEN its validity policy (recorded as its policy reference) is: valid exactly while everything it binds is unchanged, its approving session is current and the source stays exportable, which BR3.1, BR3.3, BR3.4 and BR3.7 check; it has no time-based expiry, so expiresAt stays empty and the contract's expired state is not used. An expired source is caught by the re-read (BR2.1) at the next check."
    violationBehaviour: "No arbitrary default duration is chosen, and an approval is never trusted past a change it did not see."
    source: FR2.5

  - id: BR3.6
    statement: "Cancelling is possible only before the write starts."
    category: constraint
    appliesTo: ExportApproval, ExportEffect
    trigger: "owner cancel from the outcome step or the export history"
    logic: "IF the approval is approved and unconsumed THEN it becomes cancelled (the compare-and-set expects its previewRevision and state approved). IF its effect is accepted THEN the effect becomes cancelled (reason owner-cancelled; the compare-and-set expects the effect's revision) and the approval stays consumed. IF the effect is executing THEN refuse with CONFLICT; IF unknown THEN refuse with OUTCOME_UNKNOWN and point to settlement (BR4.4, BR4.5)."
    violationBehaviour: "A started export is never claimed undone."
    source: FR2.3

  - id: BR3.7
    statement: "An interrupted press is continued only under the authority that approved it and only while its binding holds."
    category: authorization
    appliesTo: ExportApproval, ExportEffect
    trigger: "owner selects '이어서 내보내기' on an approved, unconsumed approval"
    logic: "'이어서 내보내기' is offered only while the approving session is current; otherwise the history offers a fresh preview instead. On continue: IF the approving session is no longer current THEN the approval becomes invalidated (authority-revoked). ELSE re-derive the binding exactly as the approve call does (BR3.1); IF it changed THEN the approval becomes invalidated with the matching reason and the owner is offered a fresh preview. ELSE run the execute call exactly as the press would (BR3.2, BR5.1, BR5.2); on success the approval is consumed by its one effect."
    violationBehaviour: "Continuing completes the owner's earlier approval; it is never a second approval, never runs under a different session and never binds a changed source or destination."
    source: FR2.5

  - id: BR4.1
    statement: "Every written page carries the DocSuri export marker, fixed at preview time."
    category: constraint
    appliesTo: ExportPreview, ExportEffect
    trigger: "rendering and every write"
    logic: "IF a preview revision is prepared THEN its marker is derived from previewId and revision (one preview revision → at most one approval → at most one effect, and failed effects are never retried in place) and is the text of the last top-level block of the canonical block tree; the bound effect copies it unchanged. A written page therefore carries exactly the marker the owner saw, in its last top-level block."
    violationBehaviour: "The approved, hashed content and the written page are identical; a page can always be matched to its export."
    source: FR2.4

  - id: BR4.2
    statement: "Each write response is classified as created, refused, rate-limited or uncertain; only Notion's documented retry signals are retried."
    category: calculation
    appliesTo: ExportEffect, ExportAttempt
    trigger: "end of a write attempt"
    logic: "Created → succeeded: Notion returns the created page; or Notion answers that the change was saved but the response could not be built in time and names the created page, and that page reads back under the bound destination, created by the integration that sent the attempt, with the effect's marker as its last top-level block. Refused → failed, with the matching reason: invalid token (token-invalid; also BR1.4), page not shared or missing (destination-missing), permission missing (no-access, with the hint to enable content insertion; the connection's creation capability becomes refused), the free workspace's block limit reached (workspace-block-limit), content rejected (content-rejected), or rate limiting that Notion marks as blocked, where retrying will not help (provider-blocked). Rate-limited, the only class that is retried: exactly the two answers Notion's documentation tells clients to retry for any request method, namely a rate-limit answer (HTTP 429, code rate_limited) not marked as blocked, and a service-overload answer (HTTP 529, code service_overload). For these the effect stays executing and is tried again after the provider's stated wait, within the retry budget (policy: about 3 attempts within 3 minutes); when the budget is spent → failed (rate-limit-budget-spent). Uncertain → unknown: everything else, conservatively, including a timeout, a lost response, any 5xx other than service_overload, a gateway timeout, a conflict, a saved-but-busy answer that names no page or whose named page fails any of the read-back checks, and any unreadable answer. The write's own timeout is longer than Notion's server deadline, so Notion's busy answer can arrive. After the first successful write the connection's creation capability becomes confirmed."
    violationBehaviour: "No response is guessed: only a returned or fully verified page counts as sent, only a definite refusal counts as failed, and only Notion's two documented retry answers are ever written again; any doubt leaves the outcome unknown."
    source: FR2.4

  - id: BR4.3
    statement: "An unknown or failed export is never written again in place."
    category: policy
    appliesTo: ExportEffect
    trigger: "unknown or failed outcome"
    logic: "IF an effect is unknown THEN no further write happens for it; it waits for reconciliation (BR4.4) or owner settlement (BR4.5). IF an effect is failed THEN it stays failed; another export needs a fresh preview revision and a new approval. U6 does not use C09's optional failed → accepted retry."
    violationBehaviour: "No silent duplicate page; the owner sees exactly one outcome per approval."
    source: FR2.4

  - id: BR4.4
    statement: "Unknown outcomes are reconciled by looking for the marker in the destination, within a bounded scan budget."
    category: policy
    appliesTo: ExportEffect, ReconciliationCheck
    trigger: "an unknown effect after the settling wait (policy: at least twice the write timeout, which exceeds Notion's maximum request time), then periodic scans with backoff while the scan budget lasts (policy: about 24 hours)"
    logic: "IF the current connection can read the destination THEN scan it completely: every child page, including pages inside toggles, columns and similar containers on that page, created by the integration recorded on the effect's attempts (not necessarily the connection's current one) at or after the first attempt's start minute less a clock margin (policy: 5 minutes, because DocSuri's clock and Notion's minute-rounded times are not assumed to agree); read each candidate's last top-level block for the marker. IF a page carries it THEN succeeded with that page and its link; if several do, record the earliest and keep the others on the check as possible duplicates shown to the owner. IF a complete scan finds none THEN record not-found; only a second complete scan at least one settling interval later that also finds none makes the effect failed (not-found-after-checks). IF a scan is partial THEN record listing-incomplete and keep unknown. IF the connection cannot read the destination (disconnected, revoked, unavailable, not shared any more) THEN record listing-unavailable and keep unknown. IF the scan budget is spent while the effect is still unknown, whatever the last result THEN scanning stops, the time is recorded, and owner settlement is offered (BR4.5)."
    violationBehaviour: "Silence never settles an outcome and no unknown effect is left without a way forward. Absence cannot be proven strictly (the owner may have moved, renamed or trashed the page), so the failure says 'not found after checks', never 'proven unwritten'; the evidence of every scan is recorded."
    source: FR2.4

  - id: BR4.5
    statement: "When automatic checks cannot decide, the owner settles an unknown export, with the assumption named."
    category: authorization
    appliesTo: ExportEffect
    trigger: "owner settles from the export history"
    logic: "IF the effect is unknown, the settling wait has passed, and either the latest scan was listing-unavailable or listing-incomplete, the connection can no longer read the destination, or scanning has stopped with the budget spent (BR4.4) THEN offer settlement: 'it is there' makes it succeeded (owner-settled-delivered, with an optional page link the owner supplies, accepted only as a Notion page link) and 'it is not there' makes it failed (owner-settled-not-delivered); record the assumption the owner accepted. Until then the owner sees '확인 중' with the time of the next check."
    violationBehaviour: "Only the owner of the effect can settle it, never before the automatic checks had their chance, and never twice."
    source: FR2.4

  - id: BR4.6
    statement: "Abandoned work is recovered: an interrupted request becomes unknown, an interrupted wait resumes."
    category: policy
    appliesTo: ExportEffect, ExportAttempt
    trigger: "recovery sweep and worker passes"
    logic: "IF an effect is executing, its latest attempt has no response class and no live worker holds it after the orphan threshold (policy: 15 minutes) THEN it becomes unknown and BR4.4 applies. IF an effect is executing in a rate-limit wait (its latest attempt is rate-limited), the wait has elapsed and no live worker holds it THEN a worker takes it up again: the BR3.3 check runs, then the next attempt (recorded atomically with its start, as in BR3.3) if the retry budget remains, else failed (rate-limit-budget-spent), because Notion processed nothing on any attempt. Because entering executing and recording the attempt are one atomic step (BR3.3), these two cases cover every executing effect."
    violationBehaviour: "A crash, restart or redeploy never leaves an export stuck, never repeats an uncertain write, and never blocks the owner's other exports or account lifecycle indefinitely."
    source: FR2.4

  - id: BR4.7
    statement: "Success links the page that was found or confirmed."
    category: constraint
    appliesTo: ExportEffect
    trigger: "succeeded outcome"
    logic: "IF the effect succeeded through a returned page, a verified read-back or a marker found by reconciliation THEN record that page's id as its identity and its link for display only, and show the link. IF the owner settled it as delivered THEN show the owner's link only when one was supplied, labelled as settled by the owner."
    violationBehaviour: "No success is shown without its basis."
    source: FR2.4

  - id: BR5.1
    statement: "Binding an export requires no other export in flight and no unsettled export of the same export pair."
    category: constraint
    appliesTo: ExportEffect
    trigger: "execute call: the press's second call, or continuing an interrupted press (BR3.7)"
    logic: "IF the owner already has an effect accepted or executing THEN refuse with CAPACITY_EXHAUSTED (wait for it) ELSE IF an unknown effect exists for the same export pair THEN refuse with OUTCOME_UNKNOWN (settle it first) ELSE bind. A refusal leaves the approval approved and unconsumed, so it can be continued later."
    violationBehaviour: "No race can produce two concurrent writes or a duplicate of an unsettled export."
    source: FR2.4

  - id: BR5.2
    statement: "Exports are paced per owner and are not metered against the usage plan."
    category: policy
    appliesTo: ExportEffect
    trigger: "execute call"
    logic: "IF the owner has bound the pace limit's number of effects within the rolling window (policy: 20 per hour) THEN refuse with CAPACITY_EXHAUSTED and the time when exporting is possible again, in plain Korean; the approval stays approved and unconsumed. Exports are not counted against the owner's usage plan in this release."
    violationBehaviour: "The free integration's rate limits are protected; a refusal never consumes an approval."
    source: NFR6

  - id: BR6.1
    statement: "Account withdrawal disconnects export at once and ends pending work."
    category: policy
    appliesTo: ExportConnection, ExportApproval, ExportEffect, ExportLifecycleEvidence
    trigger: "lifecycle request: withdraw (live_records and pending_work scopes)"
    logic: "IF withdrawal is requested THEN in one step: invalidate approved, unconsumed approvals and accepted effects (account-withdrawn), delete the protected token and set the connection disconnected; record evidence at once with counts (approvals invalidated, effects invalidated, exports still in flight, exports unknown). An export already executing finishes its outstanding request and records itself; unknown exports cannot be reconciled without the token and wait for owner settlement after any reactivation. The participant never defers."
    violationBehaviour: "Withdrawal never leaves a usable token or a pending write behind and never blocks on an in-flight request."
    source: FR2.5

  - id: BR6.2
    statement: "Account erasure deletes all of this module's records for the account."
    category: policy
    appliesTo: ExportConnection, ExportPreview, ExportApproval, ExportEffect, ExportAttempt, ReconciliationCheck, ExportLifecycleEvidence
    trigger: "lifecycle request: erase (live_records and pending_work scopes)"
    logic: "IF erasure is requested THEN apply BR6.1, then delete the account's connection, previews, approvals, effects, attempts and reconciliation checks, recording count-only evidence first. An export whose request is still outstanding may still create a page; its completion finds no record and stores nothing, and the evidence counts it as possibly creating an external copy."
    violationBehaviour: "No export record of an erased account remains except the count-only evidence."
    source: NFR3

  - id: BR6.3
    statement: "Reactivation does not restore a connection."
    category: policy
    appliesTo: ExportConnection
    trigger: "lifecycle request: reactivate"
    logic: "IF the account is reactivated THEN record evidence and change nothing; the owner connects again when they want to export."
    violationBehaviour: "n/a (no-op by design)."
    source: NFR3

  - id: BR6.4
    statement: "Pages already in the owner's Notion are the owner's copies: never touched, reported as retained."
    category: policy
    appliesTo: ExportLifecycleEvidence, ExportEffect
    trigger: "withdraw, erase, disconnect (external_copies scope)"
    logic: "IF lifecycle or disconnect processing runs THEN no Notion page is deleted, archived or edited. The external_copies evidence records that pages exported by this account (and possibly pages from in-flight or unknown exports) remain in the owner's Notion, under reason key external-copies-retained-by-owner, which AccountAccess reports as retained by policy (cross-unit amendment A8)."
    violationBehaviour: "DocSuri never claims external copies were removed."
    source: FR2.4

  - id: BR6.5
    statement: "Lifecycle participation writes only this module's records, once per request and scope, without deferring."
    category: constraint
    appliesTo: ExportLifecycleEvidence
    trigger: "any lifecycle ticket"
    logic: "IF a ticket arrives for this participant THEN act only on this module's records for that account, finish within the platform's claim lease and write evidence exactly once per (request, scope); a repeated ticket returns the recorded evidence."
    violationBehaviour: "No account data is written; replays have no further effect; the account's lifecycle request is never left blocked by this participant."
    source: NFR1

  - id: BR7.1
    statement: "Every read and write is confined to the current owner."
    category: authorization
    appliesTo: ExportConnection, ExportPreview, ExportApproval, ExportEffect
    trigger: "every operation"
    logic: "IF a referenced connection, preview, approval or effect does not belong to the authenticated account THEN respond exactly as for a nonexistent one ELSE proceed."
    violationBehaviour: "No cross-owner disclosure, approval, export or settlement; existence of other owners' records is not revealed."
    source: NFR1

  - id: BR7.2
    statement: "Logs, evidence and errors carry identifiers, states and categories only."
    category: policy
    appliesTo: ExportAttempt, ReconciliationCheck, ExportLifecycleEvidence, ExportEffect
    trigger: "any recording or error"
    logic: "IF something is logged, recorded as evidence or returned as an error THEN it contains no token, no page content, no provider response text and no personal data; outcome reasons use the fixed categories."
    violationBehaviour: "Diagnostics stay useful without becoming a leak."
    source: NFR3

  - id: BR8.1
    statement: "Synthetic mode writes only to a local fake Notion."
    category: policy
    appliesTo: ExportAttempt
    trigger: "any provider call in a synthetic profile"
    logic: "IF the application runs a synthetic profile THEN every provider call goes to the local fake Notion, which records requests and can simulate success, each refusal class, the two retry answers, saved-but-busy answers with and without a page, timeouts after success and listing outcomes; no request reaches Notion."
    violationBehaviour: "Tests can never create a real page."
    source: NFR6

  - id: BR8.2
    statement: "Real export is bounded to the owner's authorized test destination until U8."
    category: policy
    appliesTo: ExportConnection, ExportEffect, ExportAttempt
    trigger: "destination step, approval and the pre-write check in the real composition"
    logic: "IF the real composition is active THEN only the destination recorded in its activation is usable (other pages are shown as not allowed; approval of another destination is refused with FORBIDDEN and a plain Korean message; the pre-write check enforces the same bound), each export follows the owner's explicit approval of the exact rendered content, and every attempt is recorded with pathKind real."
    violationBehaviour: "No real page is created outside the approved test destination before U8 widens it."
    source: NFR6

  - id: BR8.3
    statement: "An unresolved policy blocks the affected operation; there is no paid fallback."
    category: policy
    appliesTo: ExportConnection, ExportEffect
    trigger: "configure, preview, approve or write"
    logic: "IF credential protection is unavailable, Notion's free terms for this integration are not verified and recorded (including the block limit for free workspaces with more than one member), or a required policy value is missing THEN configure, preview and approve fail with POLICY_UNRESOLVED naming the missing policy; a write that meets it waits as could-not-check and fails with policy-unresolved at the wait bound (BR3.3)."
    violationBehaviour: "No export runs on unverified terms or unprotected credentials, and nothing switches to a paid path."
    source: NFR6
```

## Rules summary

| Group | Rules | Gist |
|---|---|---|
| Connection and token | BR1.1–BR1.6 | Write-only token, verified before it is stored. One connection per owner, replaced by compare-and-set. Every change advances the revision and ends older pending work. Destinations are shared pages the connection can read, and creation permission is reported only as far as Notion has shown it. An unopenable token makes the connection unavailable, never changed. |
| Source and preview | BR2.1–BR2.6 | Only ready novelty results read through U4's export read, with its answers mapped honestly. Reading and previewing never write. Each preview revision freezes a canonical block tree and shows its projection. The tree fits one request. Earlier exports of the pair are shown. Rendered copies are kept only while needed. |
| Approval and execution | BR3.1–BR3.7 | Explicit press on the current exact preview. Idempotency is per operation, so replays return originals, and one approval binds one effect. Re-check before every write, separating changed from could-not-check, with an atomic start. Unconsumed approvals are invalidated by change or housekeeping. Validity is binding-defined. Cancel only before the write. Continuing re-derives the binding under the approving session. |
| Outcomes and reconciliation | BR4.1–BR4.7 | Marker in the last top-level block. Only Notion's two documented retry answers are retried; any doubt is unknown. Unknown or failed is never rewritten. Bounded marker scans by the recorded writer settle unknowns. Owner settlement when checks cannot decide or the budget is spent. Recovery covers every executing effect. Success links the real page. |
| Limits | BR5.1–BR5.2 | At bind time: one export in flight per owner, no duplicate of an unsettled pair. Per-owner pacing, no usage metering. |
| Lifecycle | BR6.1–BR6.5 | Withdrawal disconnects at once and ends pending work. Erasure deletes everything and counts possible external copies. Reactivation restores nothing. External copies are retained and reported as such. The participant never defers. |
| Isolation and privacy | BR7.1–BR7.2 | Owner-only access, with not-found for other owners' records. No secrets, content or provider text in logs, evidence or errors. |
| Modes and policy gates | BR8.1–BR8.3 | Synthetic mode uses a local fake Notion. Real export is bounded to the authorized test destination until U8. Unresolved policy blocks, with no paid fallback. |
