# Functional Design Questions — U6 approved export

Date: 2026-10-19 (Asia/Seoul)
Unit: u6-approved-export (embedded library; ApprovedExport owns the owner's Notion connection, export previews, approvals and export effects). Inputs: [unit definition](../../../inception/units-generation/unit-of-work.md), [requirements FR2](../../../inception/requirements-analysis/requirements.md), approved [wireframes W3/W4](../../../ideation/rough-mockups/wireframes.md) and [user flow 2](../../../ideation/rough-mockups/user-flow.md), the earlier record's ApprovedExport component, ADR-006 and export contract C09 (`../../../../261010-docsuri-v2-rebuild/inception/`), U4's export read, and the built application.

Each question offers the design I recommend as A. Answer with a letter, or in your own words under X.

## Settled from the records (no question)

These follow from decisions already on record. If one should change, say so under X of the closest question.

- The frozen export contract (C09: configure, read and disconnect a connection, list destinations, prepare a preview, approve, execute, read an export, cancel) is implemented with its frozen shapes on its `/api/v2/c09/` surface. Its small internal gaps (the destination record lacks the identifier the provider messages use; the binding hash has two names; the unknown-outcome error has two spellings) are closed by additive contract amendments, not workarounds.
- How the token is protected at rest is decided in NFR design. This stage fixes the behaviour: the token is write-only, never returned, shown or logged, and only the export path can use it.
- The old (v1) Notion export stays untouched in U6. Its saved connections are not migrated (data migration is out of scope), so owners connect again in the new application. Retiring the old routes belongs to U8's cutover.
- A result can be exported only while U4 still holds it as ready; U4's retention rules decide how long that is.
- As with U5, registration in the shared lifecycle participant list happens at U8; U6 implements and tests its own participant.

## Q1. Which research results can be exported?

U4 already provides an export-only read that returns a ready novelty-analysis result at its exact identity with its eligibility re-checked. The finish plan's user flow says "research/analysis artifact", which could also mean research answers.

A. Ready novelty-analysis results only, read through U4's agreed export read (exact identity and content hash, current eligibility re-checked). Research answers and discussion threads are not exportable in this release. This matches the old Notion export, which exported novelty results.
B. Novelty results and research answers. This needs U4's export read extended to research answers, a change to built U4 code.
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q2. How does the owner connect Notion and choose where the page goes?

The frozen export contract connects with a Notion integration token (no OAuth) and treats destinations as parent pages that integration can write to. The old export stored one fixed parent page on the connection.

A. The owner pastes a Notion internal-integration token once, into a write-only field that never shows it again. DocSuri checks it and lists the pages that integration can write to. For each export the owner picks a parent page from that list, with the last used page preselected, and the export creates one new child page there. Replacing the token or disconnecting invalidates every pending approval.
B. The owner enters the token and one fixed parent page (ID or URL) at connection time, and every export goes under that page, as in the old export. Changing it means editing the connection.
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q3. What does the owner press to export, and what makes an approval stale?

The requirement asks for exactly one explicit approve-and-export action bound to the exact result and destination (FR2.3). The frozen contract records the approval and the export execution as two steps. Approvals must become invalid when what they approved changes (FR2.5).

A. One "승인하고 내보내기" (approve and export) button under the preview, with the result and destination shown above it.
   - Pressing it records an explicit approval bound to the exact preview: the result's identity, content hash and eligibility, the destination, the connection's revision and the rendered content's hash. It then immediately starts the single export bound to that approval. Retrying the same press never starts a second export.
   - Any change to those bound facts invalidates the approval and returns the owner to a fresh preview. So do the owner's session being revoked and the result expiring.
   - The approval is used up by its one export.
B. Two separate owner actions: "승인" (approve) records the approval, and a later "내보내기" (export) starts the export. The binding and invalidation rules are the same.
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q4. How are unclear export outcomes settled?

A Notion request can time out after Notion has already created the page. FR2.4 requires sent / failed / unknown outcomes, reconciliation and no silent duplicate. Notion's page creation has no idempotency key DocSuri can rely on, so DocSuri has to check the destination itself.

A. Each exported page carries a DocSuri export marker: a footer line naming the export record.
   - A definite refusal (invalid token, no access, page not found, invalid content) ends as failed, with a plain reason.
   - A rate-limit refusal means Notion processed nothing, so DocSuri waits and tries again within a small budget.
   - Anything uncertain (timeout, server error, conflict) ends as unknown. An unknown export is never written again automatically.
   - After a short settling wait, DocSuri lists the destination page's children and looks for the marker:
     - marker found: sent, with the page link recorded;
     - complete listing without the marker: not sent (failed), and the owner may approve a new export;
     - listing unavailable: stays unknown.
   - While evidence stays unavailable, the owner can settle it from the export's history row ("it is there" / "it is not there"), with the assumption named. This is the same pattern as U5 digests.
B. No automatic check: every unknown export waits for the owner to settle it.
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q5. What happens to exports when the owner withdraws or erases their account?

U6 takes part in the account lifecycle without writing account data. The earlier design left open what happens to already published copies, meaning the pages in the owner's own Notion workspace.

A. Withdrawal disconnects:
   - the protected token is deleted;
   - pending approvals and not-yet-started exports are cancelled;
   - an export already in flight finishes and is recorded.

   After reactivation the owner connects again. Erasure also deletes DocSuri's remaining export data (previews, approvals and export records) and records evidence. Pages already exported to the owner's Notion are the owner's own copies: DocSuri never deletes or edits them, and the evidence notes that such copies exist outside DocSuri.
B. Same as A, but withdrawal keeps the protected token so reactivation restores the connection.
C. Same as A, but erasure first tries to archive the exported pages in Notion (best effort, failures recorded), then deletes the token.

X. Other (please specify)

[Answer]: A

## Q6. Should U6 make one real export to your own Notion as evidence?

The $0 rule allows only free services, and Notion's free terms for token integrations are still recorded as unverified (feasibility assumption A3). U5 made one approved real email as evidence.

A. Build both modes. All automated tests use a local fake Notion that records requests and simulates timeouts and refusals. Then, with your explicit approval of the exact page content, make one real export to a test page in your own Notion workspace and record the evidence. For that you create a Notion internal integration, share one test page with it, and paste its token into the connection form, where it is stored protected. Real export stays bounded to that test until U8.
B. Synthetic only in U6; the first real Notion export happens during U8's production-level operation.
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q7. What limits apply to exporting?

Notion rate-limits each integration, and the account plan defines usage limits. The export requirements say nothing about metering.

A. Exports are not counted against the owner's usage plan in this release, so there is no new billing behaviour. Each owner has at most one export in flight, and a per-owner pace limit (for example 20 exports per hour) protects the integration. Hitting a limit is explained in plain Korean, with when to try again.
B. Count each export as a usage operation under the owner's plan, in addition to the pacing above.
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q8. Which screens and navigation does export get?

The approved wireframes add an export entry to the navigation (W4) and describe a stepped export view (W3, earlier mockup M10). U4's novelty result screen currently tells the owner that reading never exports.

A. Two entry points into one flow:
   - An "내보내기" (export) navigation entry opens the export view: Notion connection status and setup, plus the owner's export history with outcomes. Unknown exports are settled from that history.
   - The novelty result screen gets a "Notion으로 내보내기" (export to Notion) action, which opens the stepped flow for that exact result: connection and destination, then read-only preview, then one approve-and-export button, then the outcome.
   - The flow has five screen states (empty, loading, populated, error, partial) and Korean labels. It works by keyboard with visible focus and announces status changes in a polite live region.
   - An unknown outcome shows "확인 중" (checking) with the repeat button disabled. Success links the actual Notion page.
B. The flow only opens from the novelty result screen. Connection setup and export history live in Settings, with no separate navigation entry.
C. Not applicable

X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Q1: Only ready novelty-analysis results are exportable, read through U4's export read at their exact identity and content hash with eligibility re-checked. Research answers and discussions are not exportable in this release.
- Q2: The owner pastes a Notion internal-integration token once (write-only). DocSuri lists the pages it can write to, the owner picks a parent page per export (last used preselected), and each export creates one new child page. Replacing the token or disconnecting invalidates pending approvals.
- Q3: One "승인하고 내보내기" button records an approval bound to the result identity and hash, eligibility, destination, connection revision and rendered-content hash, then starts exactly one export. Retries never start a second export. Any change to a bound fact, a revoked session or an expired result invalidates the approval. An approval is used up by its export.
- Q4: Each page carries a DocSuri export marker.
  - Definite refusals end as failed.
  - A rate limit retries within a small budget.
  - Uncertain responses end as unknown and are never re-written automatically. After a settling wait, a listing of the destination's children decides: marker found means sent; a complete listing without it means failed; an unavailable listing stays unknown.
  - The owner can settle an unknown export from history, with the assumption named.
- Q5: Withdrawal deletes the protected token, cancels pending approvals and unstarted exports, and lets an in-flight export finish. Reactivation means connecting again. Erasure deletes all U6 data and records evidence. Pages in the owner's Notion are never deleted or edited.
- Q6: Both modes. A local fake Notion serves all automated tests. One real export to your own Notion test page follows, after your explicit approval of the exact content, and is bounded until U8.
- Q7: No usage-plan metering. At most one export in flight per owner, plus a per-owner pace limit (for example 20 per hour), explained in plain Korean.
- Q8: An "내보내기" navigation entry shows connection setup and export history, and unknown exports are settled there. The novelty result screen gets "Notion으로 내보내기", opening the stepped flow: destination, read-only preview, one approve-and-export button, outcome. The flow has five screen states, Korean labels, keyboard access and a polite live region. Unknown shows "확인 중" with repeat disabled, and success links the Notion page.

- Looks correct
- Request changes

[Answer]: Looks correct
