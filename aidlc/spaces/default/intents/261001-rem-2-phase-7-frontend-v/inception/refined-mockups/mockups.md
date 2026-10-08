# Refined Mockups — Phase 7 Frontend Wiring

## Sources and Design Basis

This is a screen/state specification, not an implemented or browser-verified prototype. It follows the confirmed `refined-mockups-questions.md` plan, approved `../requirements-analysis/requirements.md` and `../user-stories/stories.md`, and `../practices-discovery/team-practices.md`. Earlier `../../ideation/rough-mockups/wireframes.md` and `user-flow.md` supply starting layouts, not authority for superseded retry, progress, or endpoint assumptions.

Source checks: `frontend/components/SummaryModal.tsx` and its CSS show a centered dialog and existing summary/translation content; `PaperDetailIsland.tsx` supplies action controls and existing reading routes; `AssetViewer.tsx` requires the same-origin migration; `frontend/app/globals.css` defines semantic light/dark tokens. Exact BFF streaming, resultRef resolution, and accessible asset equivalents remain technical prerequisites.

English labels below describe intended meaning; implementation uses the application's established language consistently. Values in examples are illustrative supplied data, not promised progress, time, or response fields. All drawings use textual fallbacks with state details below them.

## M1 — Paper Detail and Persistent Status

### M1a — Initial Submission Dialog

```text
+----------------------------------------------------------+
| Summarize paper                                  [Close] |
| Summary level: [existing supported level selector]        |
| Selected initial level: current explicit selection        |
| [Submit summary]                                         |
+----------------------------------------------------------+
```

The initial submission surface preserves the existing supported summary-level options and default; Contract/Functional Design pins their values from the actual component contract. Translation preserves its supported initial parameters rather than inventing a summary-level toggle for translation. Opening the dialog or changing an initial selection does not submit. Only Submit sends the captured request. JobSubmissionForm owns submission and pre-job uncertain-outcome recovery; SummaryModal is a separate read-only result surface. Both may share the centered visual shell. Close does not imply cancellation of server work.

```text
+----------------------------------------------------------+
| Paper title                                              |
| Authors / abstract / existing reading content             |
| [Summarize] [Translate abstract] [Existing paper actions]  |
|                                                          |
| Existing paper content remains scrollable                 |
|                                                          |
+----------------------------------------------------------+
| Summarize: Running                        Live            |
| Progress: 45% (only when provided)                        |
| Estimated remaining: about 2 min (when supported)          |
| Last update: supplied timestamp                          |
| [Details and history] [Hide status]                       |
+----------------------------------------------------------+
| Existing bottom navigation / device safe area             |
+----------------------------------------------------------+
```

**Text fallback:** The existing paper view retains its actions and content. A sticky-bottom status panel displays the current job's task, state, connection condition, available progress, optional estimate, and disclosure controls above navigation. Reserve document space equal to the panel height so it cannot cover the last content or focused control. The panel is page-local, not a global job dashboard.

- No job: no empty status panel; submission controls remain discoverable.
- Submission pending: button shows submitting and prevents duplicate activation while that request is pending. A missing response is uncertain submission, not proof of job failure.
- Unknown progress: an indeterminate indicator and state text replace percentages. SUBMITTED, ACCEPTED, and QUEUED never synthesize 10/20/30 percent.
- ETA: label explicitly says estimated. Display only with usable real progress data; otherwise omit the number and say estimate unavailable in details. Do not claim backend execution deadlines.
- Details disclose safe error information and received event history/timestamps, never raw stacks, credentials, or internal paths.
- Hide status only hides the presentation; it does not cancel, resubmit, or delete the job's recovery identity. While the authorized job remains selected on this page, a visible Show job status control can restore the panel and refresh its state.
- Mobile/tablet/desktop are layout test ranges, not a mandate to replace the application's existing breakpoint system. At reflow/large-text constraints, use an in-flow panel rather than obstruct content. The layout rules are specified in `interaction-spec.md`.

## M2 — Connectivity, Terminal States, and Recovery

| State | Main content | Action and feedback |
|---|---|---|
| Connecting | Connecting to job updates; actual job state if known | No fictional progress; keep the original identity |
| Live | Actual state/progress and last-update time | Details/history; Hide status |
| Reconnecting | Connection interrupted; last known state marked stale | Do not display a fabricated attempt counter |
| Polling | Live stream unavailable; checking status periodically | Two-second SWR interval; explanatory text, not failure-red alone |
| Offline | Updates unavailable; last known authorized state with timestamp | Tracking-only recovery when context exists; no guessed terminal state |
| COMPLETED | Actual backend completion; result availability is checked separately | View result; copy asset ID only after an authorized result supplies it. No frontend completion inferred from elapsed time or a short reference |
| FAILED | Failed; user-safe reason if supplied | Same-request recovery only when original context exists; no restart promise |
| ABSTAINED | Work was not completed; actual safe abstention reason | Never equate abstention with user cancellation |
| Access lost/account changed | Access unavailable; prior protected content removed | Existing sign-in/back navigation; stop prior-owner tracking |

```text
+----------------------------------------------------------+
| Submission outcome could not be confirmed                |
| Resend the unchanged request to check its outcome.        |
| [Recover same request] [Return to paper]                  |
+----------------------------------------------------------+

+----------------------------------------------------------+
| Job failed                                               |
| This job remains failed. Recovery uses the same request.  |
| Failed dispatch may allow a replacement submission;      |
| the old job is not restarted.                            |
| [Recover same request] [Details] [Hide status]             |
+----------------------------------------------------------+

+----------------------------------------------------------+
| Original request details are unavailable after reload.   |
| We cannot safely resend this request.                    |
| [Recover same request: unavailable]                       |
| [View job status: if job identity is known]               |
| [Return to paper]                                        |
+----------------------------------------------------------+
```

**Text fallback:** Distinguish uncertain submission, actual terminal failure, and missing original request details. Same-request recovery keeps the captured original parameters/key and uses the actual returned job/state. A retained binding returns the original job; failed dispatch that released the binding may produce a replacement. Before a job ID is known, this inline message belongs to the submission surface, not a fabricated JobStatus instance. On receipt, the stable parent mounts tracking for the returned identity. Missing parameters make resend unavailable; a known authorized job ID can still support read-only tracking. A hash is neither a job ID nor recoverable parameters.

Recovery feedback: “Request outcome received” when cause is unknown; “Existing job recovered” only when supported by identity evidence; “Replacement submission received after dispatch failure” only with authoritative dispatch-failure/replacement evidence. The returned job's actual state is displayed separately, including FAILED or ABSTAINED. A lost response or an unexplained different ID alone does not prove dispatch failure. Old-job responses cannot overwrite a newly selected replacement. A result-read failure after actual completion stays a result availability issue, not a fabricated change to the job state.

Storage persistence failure within the same session is distinct: if the original owner/request/key remain available in memory, recovery may remain available with a warning that reload recovery is unavailable. No guessed parameters, random key, Retry with changes, or automatic POST on navigation is permitted.

## M3 — Result Dialog and Asset-ID Copy

```text
+----------------------------------------------------------+
| Summary or translation                           [Close] |
| Submitted summary level: recorded value (read-only)       |
| Existing authorized result content                       |
|                                                          |
| Asset ID: exact supplied identifier                       |
| [Copy asset ID]                                          |
| Copy feedback appears here                               |
+----------------------------------------------------------+
```

**Text fallback:** Use the centered reading dialog for the selected completed job's task. Summary-level metadata shows the submitted value, not today's user default; if it is unavailable, say “Submitted level unavailable” rather than invent a value. No editable persona/level toggle or submit/recovery command is present in this result surface. Display the exact prepared content, including its prepared personalization, without recomputing from current settings. Existing mount/persona-change request effects must be removed from this read-only path.

| Result/copy state | Presentation |
|---|---|
| Loading result | Loading text in the dialog; accessible busy state; Close remains available |
| Available | Render authorized content through the verified resultRef consumer path |
| Authentication required (401) | Clear protected content; sign-in guidance using existing navigation; Close remains available |
| Missing/not-owned (404) | Generic “Result unavailable”; do not disclose whether another user's job exists; Close remains available |
| Owner-expired (410) | “This result has expired”; no automatic generation or submission; Close remains available |
| Unsupported/legacy reference | “This result cannot be displayed”; no URL guessing or automatic repair by generation; Close remains available |
| Transient read failure | “Could not load the result”; Retry result read and Close, both keyboard operable; retry performs only the authorized read |
| No asset ID supplied | No invented ID or copy action; result itself remains readable |
| Copy pending | Keep identifier visible; prevent repeated activation until settled |
| Copy succeeds | Copied, announced politely without moving focus |
| Copy fails | Could not copy; identifier remains selectable for manual copying |

Long identifiers wrap visually without inserting characters into copied data. Copying an ID conveys no asset access rights. Closing returns focus to View result when it survives, otherwise the corresponding paper action.

Result messages use a concise live region. Retry clears its previous transient error and marks only the content area busy; keep focus on the retry control while pending. When it disappears after success, move focus to the result heading only if it still held focus; never steal focus from Close or another surviving element. Required 401/404/410 behavior is the approved backend amendment, not current-code certification. No result state or retry calls generation/enqueue.

## M4 — Authorized Figure/Table Viewer

```text
+----------------------------------------------------------+
| Existing caption / verified text alternative             |
|                                                          |
| Authorized image viewport                                |
|                                                          |
| [Overview thumbnail with current viewport outline]        |
|                                                          |
| [Zoom out] [Zoom in] [Reset to fit]                        |
| [Pan left] [Pan right] [Pan up] [Pan down]                 |
+----------------------------------------------------------+
```

**Text fallback:** Display the same-origin authorized asset, its existing caption/equivalent when supplied, a minimap of the same image, and named controls. Loading uses a skeleton; generic image failure uses a safe unavailable message rather than guessing an HTTP status from an image error event.

- Keyboard, click/tap buttons, and optional pointer drag support pan; buttons provide a single-pointer alternative to gestures.
- The overview is a noninteractive orientation aid in this design. It reuses the authorized image and adds no endpoint, signed URL, independent access claim, or new keyboard stop. Its viewport outline accompanies the operable main controls.
- Controls are unavailable before successful loading or after known access loss. Reset returns the entire asset to fit; changing assets resets the transformation.
- Captions are not automatically sufficient equivalents for every complex figure/table. Missing semantic content is a Contract Design/accessibility dependency, not permission for invented alt text or OCR scope.

## M5 — Full-Page Rendering Failure

```text
+----------------------------------------------------------+
| Job status could not be displayed                        |
| The job may still exist. This display failure does not    |
| establish that processing failed.                         |
|                                                          |
| [Recover tracking: if authorized job context survives]    |
| [Return to paper]                                        |
+----------------------------------------------------------+
```

**Text fallback:** Honor the selected full-page error presentation for a JobStatus render failure. A stable parent outside the failed subtree retains only authorized recovery context and presents the error view in the current paper route. This is a presentation transition, not a new backend route or a failed-job state. Existing dialogs close, the failing subtree is removed, and focus moves to the error heading.

Recover tracking resets the boundary and reconnects to the same job; it never calls submit. Return to paper restores the paper view with the result modal closed and the failed tracking panel hidden, so returning does not immediately remount the failing subtree. An explicit Show job status action may try tracking again. If job/session context was lost, recovery is unavailable with an explanation. Network errors use M2 and do not automatically navigate to M5.

## Coverage and Handoff

| Mockup | Story coverage |
|---|---|
| M1/M2 | US1.1–US1.5, US2.1–US2.6, US4.1–US4.2 |
| M3 | US3.1–US3.4 |
| M4 | US5.1–US5.3 |
| All screens | US6.1–US6.3, US8.1–US8.2 |
| M5 | US7.1–US7.3 |

US4.3 remains excluded. The interaction specification defines focus, feedback, and failure transitions; the design-system mapping distinguishes existing tokens from proposals; the accessibility checklist identifies required evidence rather than claiming conformance. BFF streaming/cursor propagation, authorized resultRef resolution, original-request reconstruction, and accessible asset metadata remain named technical prerequisites. The approved staging p95 targets remain SSE under 300 ms, decoded asset under 500 ms, and JobStatus mount under 200 ms under NFR9's exact profile.
