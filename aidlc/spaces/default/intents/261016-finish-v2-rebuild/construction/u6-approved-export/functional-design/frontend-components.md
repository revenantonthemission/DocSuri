# Frontend Components — U6 approved export

Date: 2026-10-19 (Asia/Seoul)
Unit: u6-approved-export (UI contribution). Sources: approved [wireframes](../../../ideation/rough-mockups/wireframes.md) W3/W4, [user flow 2](../../../ideation/rough-mockups/user-flow.md), confirmed [functional-design-questions.md](functional-design-questions.md) Q2, Q3, Q4 and Q8, [functional-spec.md](functional-spec.md) Workflows 1–7, the earlier record's mockup M10 and interaction spec C11, and the U5 topics view's established patterns (dialogs, status line, owner-bound navigation).

## Component hierarchy

```
ExportView (route page "내보내기"; h1)
+-- ConnectionPanel (h2 "Notion 연결")
|   +-- ConnectionStatus (state text + icon, connected workspace name, limitations)
|   +-- ConnectForm (write-only token field, submit; also used for "토큰 교체")
|   +-- DisconnectButton (destructive, opens DisconnectDialog)
+-- ExportHistory (h2 "내보내기 기록"; newest first, paged)
    +-- ExportHistoryRow (per approval: result title, destination title, state, time, reason)
        +-- PageLink (succeeded: the Notion page; "직접 확인됨" when owner-settled)
        +-- PossibleDuplicates (pages found carrying the same marker, if any)
        +-- NextCheckNote (unknown: "확인 중 · 다음 확인 <time>")
        +-- ContinueExportButton (approved, not started, and continuable: "이어서 내보내기" completes the earlier press)
        +-- CancelButton (approved, not started, or accepted: "취소")
        +-- SettleButton (unknown, once checks cannot decide: "직접 확인", opens SettleDialog)
        +-- FreshPreviewLink (invalidated: "미리보기 다시 만들기")

ExportFlow (step view opened from the novelty result screen; h2 per step)
+-- StepIndicator (연결 -> 대상 -> 미리보기 -> 결과; current step as accessible state)
+-- ConnectionStep (ConnectForm when not connected)
+-- DestinationStep
|   +-- DestinationPicker (shared pages: title or "(제목 없음)", location context, creation permission as far as known, unusable pages with reason)
|   +-- ListingNotice (partial / unavailable / empty with how-to-share, refresh action)
+-- PreviewStep
|   +-- SourceSummary (result title, completion time, identity line)
|   +-- DestinationSummary (title + location context; repeated beside the action on narrow screens)
|   +-- EarlierExportNotice (earlier exports of this pair: links, and "Notion에 있을 수 있음" entries)
|   +-- RenderedPreview (read-only, scrollable, exactly the page text incl. the marker line)
|   +-- ApproveExportButton ("승인하고 내보내기"; the only publishing control)
+-- OutcomeStep
    +-- OutcomeStatus (내보내는 중 / 내보냈습니다 + PageLink / 실패했습니다 + reason / 변경되어 내보내지 않았습니다 + reason / 취소했습니다 / 확인 중 + next check)
    +-- CancelButton (only while the export is accepted)

NoveltyExportAction (added to U4's novelty result screen: "Notion으로 내보내기", opens ExportFlow with the result's reference)

DisconnectDialog (names the consequences; confirm / keep)
SettleDialog (names destination and exported title; "있습니다" / "없습니다"; states the assumption; optional Notion page link for "있습니다")
```

<!-- Text fallback: the export view holds a connection panel and a paged export history whose rows carry continue, cancel, settle and fresh-preview actions by state; the export flow, opened from a novelty result, steps through connection, destination, read-only preview with a single approve-and-export button, and outcome; two dialogs handle disconnect and settling an unknown export. -->

## Props/state design

| Component | State | Notes |
|---|---|---|
| ExportView | `connection`, `history[]`, `viewState: loading\|empty\|error\|ready\|partial` | Five states: empty means not connected and no history, with the connect action first. Partial means the connection or history failed while the other loaded, and says so. The connection is read without knowing its id (A7). |
| ConnectForm | `token` (in memory only), `submitState: idle\|checking\|saved\|failed`, `expectedRevision` | The token is never put in browser storage or the URL, never echoed, and cleared after every submit (BR1.1). A stale revision says the connection changed elsewhere and reloads (BR1.3). |
| DestinationPicker | `destinations[]`, `selected`, `listingState: complete\|partial\|unavailable\|empty` | Untitled pages get a placeholder and same-titled pages get location context (BR1.5). A stale preselection is dropped with a notice. In the real composition, pages other than the activation destination are shown as not allowed (BR8.2). Choosing another destination means a fresh preview. |
| PreviewStep | `preview` (immutable revision), `previewState: preparing\|ready\|refused\|stale` | Refused shows the plain reason (not found, changed, not exportable, temporarily unavailable, too large, policy). Stale means an approve call found a changed binding, and offers "미리보기 다시 만들기" (BR3.1). |
| ApproveExportButton | `pressKey` (one per press, reused on retry), `pressState: idle\|approving\|binding\|done\|refused` | Disabled while a press is in flight. A retry of the same press reuses its key and gets the same approval and effect (BR3.2). A bind refusal (limits, unknown pair) says when or how to continue; the approval then waits in the history (BR5.1, BR5.2). |
| OutcomeStatus | `effect`, `lastAnnounced` | Follows the effect by polling its read (reads never export, BR2.2). Each state change is announced once. Unknown disables repeat publication and shows the next check time (BR4.4). While the export has not started, it notes that signing out before it starts stops it (BR3.3). |
| ExportHistoryRow | `entry` (one per approval), `busy` | Actions by state, as listed in the hierarchy. "이어서 내보내기" appears only when the entry is continuable (the approving session is current); otherwise the row offers a fresh preview. It completes the earlier press and is never a second approval (BR3.7). Settlement appears only when the entry says it is offered (BR4.5). |
| SettleDialog | `choice`, `pageLink`, `assumptionShown` | Recorded only with the assumption visible. The optional link must be a Notion page link (BR4.5). |
| DisconnectDialog | `open` | Names the consequences: approvals not yet started become invalid, exported pages stay in Notion, unclear exports can then only be settled by the owner (BR1.4, BR6.4). |

## Interaction flows

- **Connect:** paste the token and submit. The panel then shows the workspace name, or the field is cleared and a plain reason shown (BR1.2).
- **Export:** novelty result → "Notion으로 내보내기" → connection step (skipped when connected) → destination → read-only preview → one press (approve, then execute) → outcome. Closing before the press publishes nothing. Closing after it does not stop the export; its outcome stays in the history (BR2.2).
- **Interrupted press:** the approval appears in the history with "이어서 내보내기" and "취소". Continuing under a session that is no longer current leads to a fresh preview instead (BR3.7).
- **Changed before the write:** the outcome step and the history say what changed and offer a fresh preview (BR3.3).
- **Unknown:** "확인 중" with the next check time. When checks cannot decide, the history row offers "직접 확인" (BR4.4, BR4.5).
- **Status:** state text plus an icon, never color alone. Changes go through one polite live region, without repeated alerts.

## Form validation rules

- **Token:** required. It must not be blank, must contain only printable characters, and stays under a generous length. No prefix or exact-length rule applies; Notion validates it (BR1.2). A field error names the problem without echoing the value. After acceptance the panel shows the workspace name, never the token.
- **Destination:** chosen from the current listing; free-text page identifiers are not accepted.
- **Settle page link (optional):** if given, it must be a Notion page link; otherwise the field explains the expected form.
- **Refusal hints:** refusals at the first export get specific next steps: share the page with the connection, enable content insertion for the integration, or the free workspace has reached its block limit (BR4.2).
- **Labels:** every field has a visible label, never placeholder-only. A validation message keeps everything else the owner entered.
- **Trusted side:** every client-side rule is also enforced there.

## API integration points

- Connection: C09 configure (also replace), read and disconnect, without a connection id (A7).
- Destinations: C09 listDestinations (A1: `destinationId`, `title`, location context).
- Preview: C09 preparePreview.
- Approve and export: C09 approve, then C09 execute, under the same press key.
- Continue an interrupted press: C09 execute on the existing approvalId and bindingHash.
- Outcome: C09 readEffect.
- Cancel: C09 cancel. Its expected revision is the preview revision for an unconsumed approval and the effect revision for an accepted effect.
- History: the A2 list.
- Settle: the A3 settle operation.
- All calls go through the established Transport client: CSRF token and idempotency key on every mutation, owner isolation errors shown as plain refusals. The safe error codes listed in the functional spec are rendered in plain Korean rather than as a generic error.

## Data sources

Every value a screen shows comes from a named field of the frozen contract or of the amendments in [functional-spec.md](functional-spec.md):

| Screen datum | Wire field |
|---|---|
| Connection state, limitations | ExportConnection `state`, `limitations` (frozen) |
| Connected workspace name | ExportConnection `workspaceName` (A7) |
| Destination title, location context | ExportDestination `title`, `context` (A1) |
| Destination usable / readable / creation permission | inspection `readable`, `creationCapability`, frozen `writable` (A6) |
| Real-composition allowance | ExportConnection `destinationScopeIds` (A7) |
| Source title | ExportPreview `sourceTitle` (A5) |
| Source identity line | ExportPreview `source` (frozen) |
| Rendered page text, incl. the marker | ExportPreview `renderedText` (frozen) |
| Earlier exports | ExportPreview `earlierExports` (A5) |
| Outcome state, page link | ExportEffect `state`, `remoteUrl` (frozen) |
| Outcome reason, settled by owner | ExportEffect `outcomeReason`, `settledBy` (A4) |
| Next check time, settlement offered | ExportEffect `nextCheckAt`, `settlementOffered` (A4) |
| History rows | A2 history entries: approval state, invalidationReason, titles, continuable, and effect summary with possible duplicates |
| Why an approval ended | ExportApproval `invalidationReason` (A9) |

## Accessibility

- **Structure:** one `h1` per view and an `h2` per step or section. The step indicator exposes the current step as state, not color.
- **Keyboard:** every action is reachable by keyboard, with visible focus.
- **Dialogs:** they trap focus and close with Escape; focus returns to the trigger.
- **Approve-and-export:** a native button, activated only explicitly, never auto-submitted. When disabled, a textual reason is shown.
- **Outcome and changes:** the success link is named by the page title. A changed-preview notice receives focus. Status changes are announced via `aria-live="polite"`.
- **Visual and language:** contrast, target size and reflow meet WCAG 2.2 AA. Korean labels throughout; result and page titles keep their original language.
