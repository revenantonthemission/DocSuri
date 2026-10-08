# Interaction Specification — Phase 7 Frontend Wiring

## Sources and Boundaries

Use `mockups.md` M1–M5 and confirmed `refined-mockups-questions.md`, approved `../requirements-analysis/requirements.md`, `../user-stories/stories.md`, and `../practices-discovery/team-practices.md`. `../../ideation/rough-mockups/wireframes.md` and `user-flow.md` are historical layout inputs; their invented percentages, response-code assumptions, and retry-to-new-execution arrows are superseded. Source observations come from the existing PaperDetailIsland, SummaryModal and AssetViewer components and their styles.

Input names below describe required information, not finalized TypeScript signatures or new backend fields. Contract Design owns wire formats. Distinguish job state from connection state, and submission recovery from tracking recovery and asset reload.

## Initial Submission and Pre-Job Recovery (M1a/M2)

JobSubmissionForm presents the existing initial summary-level selector and applicable translation parameters in the centered dialog shell. Preserve supported values/defaults from the existing contract; do not invent options here. Opening, closing and selection changes do not submit. Explicit Submit captures an immutable original request through ContentJobApi. If the response is lost, keep the uncertain-outcome recovery surface in this component even before a job ID exists. Explicit Recover same request uses the captured original, not the editable draft. Return the actual backend identity/state to the stable parent before mounting JobStatus. A stored key without reconstructible original parameters disables resend with a persistent accessible explanation.

The selected failed-dispatch exception can produce a replacement identity after the backend released the key. Use neutral outcome wording unless authoritative evidence identifies ordinary replay or dispatch-failure replacement. Never infer the cause from network uncertainty alone, restart an old terminal job, or allow late responses from the old selection to overwrite the replacement. All states preserve Close/Return navigation; closing cannot promise backend cancellation.

### Recovery Focus Rule

Keep focus on a surviving current element. If the currently focused action is removed by successful pre-job handoff or tracking recovery, place focus on the resulting named status heading (programmatically focusable, visibly indicated). If the user moved focus elsewhere while waiting, preserve it when that target survives. If the entire fallback/dialog is removed and the current target cannot survive, use that status heading; never leave focus on body or a hidden/removed element. Background status events do not move focus. Apply the corresponding result-heading rule when successful read retry removes its focused retry control.

## JobStatus (M1/M2)

| Field | Value |
|---|---|
| Component | JobStatus in the paper-detail workflow |
| Category | Display, feedback, actions |
| Inputs | Selected authorized job identity; actual state/events/progress; current owner/access context; original request/key when recoverable |
| Placement | Sticky bottom above navigation/safe area, page-local |

### States and Actions

| Trigger | State and behavior | Focus/announcement |
|---|---|---|
| Submit starts (JobSubmissionForm) | Make repeat activation unavailable while pending; preserve request/key identity | Keep a focusable busy control; announce submitting once |
| Job receipt arrives | Track its actual job ID/state; do not assume 202/409 replay semantics | Announce meaningful state; no background focus movement |
| Submission outcome uncertain (JobSubmissionForm before job ID) | Explain uncertainty; offer same-request recovery only with exact captured context | Accessible error; retain current focus; follow Recovery Focus Rule on successful handoff |
| SSE opens | Connection becomes Live, independently of job state | Polite connectivity update |
| SSE interrupted | Mark last known state stale; use verified resume and polling behavior | Announce connectivity change once, not a fake retry counter |
| Polling fallback | SWR uses fixed two-second interval for the selected job | Explain degraded connectivity; do not repeat unchanged state announcements |
| Both channels unavailable | Show stale authorized state/timestamp with tracking recovery | Never fabricate COMPLETED/FAILED from a network error |
| Terminal job | Keep terminal presentation and result/error actions; stop unnecessary tracking | Announce actual terminal outcome; do not unmount before the user can read it |
| Hide status | Hide panel and expose Show job status in the paper view; stop hidden-view work as specified by lifecycle design | Focus Show job status; hiding does not cancel or clear identity |
| Show job status | Read/reconnect to the selected authorized job | Focus panel heading only because this was an explicit navigation action |
| Owner changes or access is known lost | Stop prior subscriptions, ignore late responses, remove protected prior content | Focus a surviving paper action or access message if the old control vanished |

Replay and older polling results cannot overwrite newer state. Do not compare state enum names to infer event order; use the verified contract. Native EventSource header behavior and recreated-connection cursor transport must be pinned in Contract Design. No unconfirmed retry count or backoff guarantee appears in the UI.

### Progress and ETA

Progress is determinate only when the actual contract supports a valid value. Otherwise use indeterminate progress without aria-valuenow. An approximate ETA may be shown only during live RUNNING with enough actual increasing progress observations to support a finite estimate. A possible client estimate uses elapsed sample time divided by observed progress change; the exact validity/window policy belongs to Functional Design and must be tested. Zero/negative progress change, unavailable samples, terminal state, or stale connectivity removes the numeric ETA. The label always says Estimated; it is not an execution SLA. Never populate progress from guessed state percentages.

### Same-Request Recovery

| Context | Control state | Outcome |
|---|---|---|
| Owner, exact original parameters, and key available | Recover same request enabled | Send captured request/key; use actual returned identity/state, including a permitted failed-dispatch replacement |
| Terminal FAILED/ABSTAINED and original context available | Recovery may be enabled with explanation that the old job never restarts | Retained binding keeps terminal outcome; failed-dispatch released binding can return a replacement. Never infer dispatch failure or reset old terminal state |
| Only stored key survives reload | Resend disabled; visible explanation that original request details are unavailable | Do not reconstruct parameters from a hash or guess defaults |
| Known authorized job ID survives but original request does not | View job status available; resend unavailable | Read/reconnect only |
| Persistence failed but exact context remains in memory | Recovery available with a reload-persistence warning | Use the same in-memory request/key, not a new random key |
| Owner unresolved or access denied | Protected operations unavailable | Use existing sign-in/back navigation; do not retain previous-owner data |

Disabled resend has an adjacent persistent explanation reachable in reading order, not a tooltip requiring disabled-button focus. Returning to the paper or dismissing the message remains available. This specifies the unavailable-context branch identified by User Stories R-01; Functional Design must still define how valid original context is reconstructed without inventing sensitive-data storage.

### Responsive Behavior

The status panel has fluid width with an upper reading-width cap and reserved document-bottom space matching its rendered height. Account for existing navigation and `env(safe-area-inset-bottom)` once. Preserve sticky-bottom preference at ordinary viewport sizes. At widths below 480 CSS pixels or heights below 600 CSS pixels, use an in-flow panel near the paper actions; also fall back to in-flow if the panel would occupy more than one-third of the usable viewport. These are local proposed adaptation thresholds, not changes to global application breakpoints. Test 320 CSS pixels, text resize, zoom, landscape, and keyboard-visible layouts. Existing modal overlays remain above the status panel and make background controls unavailable to keyboard interaction while open.

### Accessibility

Use a named section with a concise live status message rather than making the entire history a live region. History/details use native disclosure controls. Static state/progress text is readable without unnecessary tab stops. Preserve visible focus, standard button activation, and text alongside color. Announce changed connectivity and safe errors; suppress unchanged polling/replay announcements. Details never expose raw stacks.

## Result Dialog and Copy Control (M3)

| Field | Value |
|---|---|
| Component | Existing summary/translation dialog presentation with a read-only completed-result path |
| Category | Navigation, display, feedback |
| Inputs | Task/result-view kind; authorized result content resolved through the verified contract; optional supplied asset ID; invoking control reference |
| Responsive behavior | Centered fluid dialog as in SummaryModal styles; scrollable body and reachable Close at narrow/zoomed layouts |

### States and Transitions

- **Open:** An explicit View result action opens the dialog, moves focus to its named heading/panel, and begins only the authorized result read. The current SummaryModal auto-runs useSummarize on mount; implementation must separate result display from that submission path.
- **Loading:** Keep Close operable and mark the content region busy. Announce loading without repeatedly announcing unchanged frames.
- **Available:** Render the exact prepared result bound to this job, including prepared personalization. Show recorded submitted summary level as read-only metadata or an explicit unavailable label. No editable selection, submit callback or recovery callback enters this surface; current persona/glossary defaults cannot alter the completed content.
- **Authentication/missing/expired:** Required amended semantics are 401 authentication-required, indistinguishable 404 unknown/not-owned, and 410 only for the owner's known expired result. Clear protected content and keep Close/return operable. Use generic unavailable text for 404; do not reveal another owner's job. These statuses require backend remediation, not merely a frontend label change.
- **Unsupported/legacy reference:** Explain that the result cannot be displayed; keep Close available, never guess a URL or generate replacement content. Do not offer a misleading Retry submission action.
- **Transient read failure:** Show a safe inline error with Retry result read and Close. Retry repeats the authorized read only, marks content busy and announces loading; it never generates/enqueues/submits or rotates identity. Keep the pending control focusable but guard repeat activation. If it disappears on success while focused, focus the result heading; preserve focus elsewhere when it survives. Announce outcome without otherwise moving focus.
- **Close:** Escape, Close, and the established backdrop behavior dismiss the dialog. Restore focus to the invoking View result button if present, otherwise the original Summarize/Translate action or surviving paper heading. Restore body scrolling; stop obsolete reads and ignore late responses.
- **Focus:** Trap Tab/Shift+Tab inside the active dialog, expose dialog name/modal semantics, and keep the background noninteractive. Existing source establishes initial focus/scroll locking, not proof of a complete focus trap or focus-return implementation; those are required integration work.

### Copy State Table

| State | Button and feedback |
|---|---|
| No authorized supplied ID | No copy control and no guessed identifier |
| Ready | Copy asset ID, accessible name matching the visible label |
| Copy pending | Temporarily unavailable repeat action; retain focus |
| Success | Copied, polite announcement after the clipboard operation succeeds |
| Failure | Could not copy; selectable exact identifier remains for manual copy |
| Result access lost | Remove protected identifier and copy action; ignore late copy UI completion |

Visual wrapping must not change copied bytes. Success/failure feedback stays until the next copy attempt or view dismissal; no time-critical toast is required.

## AssetViewer and Overview (M4)

| Field | Value |
|---|---|
| Category | Display, input, feedback |
| Inputs | paperId, assetId, existing authorized caption/equivalent if available, actual loaded dimensions, access/load state |
| Default | Fit entire asset, transformation reset |
| Loading | Stable skeleton with accessible loading text; transformation controls unavailable |
| Error | Safe unavailable message and asset-only reload when appropriate |

### Transform Controls

Use the historical proposed 0.5x–4x relative-to-fit range with fit at 1x. Zoom buttons step by 0.25x and clamp at bounds; Reset to fit restores 1x and centered position. Pan only when content exceeds the viewport; pan buttons move by 10% of the corresponding viewport dimension and clamp so the image cannot be lost outside view. These are design parameters, not backend contracts or performance budgets.

- Named buttons support keyboard Enter/Space and single-pointer taps for zoom/pan/reset.
- Pointer dragging may pan when enlarged. Pointer cancellation does not activate another action.
- Optional `+`, `-`, arrows, and `0` shortcuts apply only while the viewer itself has focus, never globally or in text inputs; ordinary Tab leaves it.
- Pinch/drag gestures are supplementary; buttons provide alternatives. Browser page zoom remains available.
- The minimap is a noninteractive duplicate view of the same authorized image with a viewport rectangle. It is hidden from assistive technology as redundant; the main image retains its verified text equivalent and operable named controls.
- New asset, unmount, or known access loss clears transforms and the overview; it must never retain a previous owner's image.
- An image error event does not reveal its HTTP status. Show a generic load failure unless another verified response establishes denied/missing status. Do not add an authorization-probe endpoint solely to produce a more specific message.

### Responsive Behavior and Accessibility

Let the image use its natural aspect ratio within a bounded viewport rather than forcing every figure into 16:9. Put controls below the image on narrow layouts; keep all controls reachable at 320 CSS pixels and 200% text resize. Large figures/tables may use localized two-dimensional navigation while surrounding text/controls reflow. Preserve verified authorized captions/text equivalents; Contract Design must surface missing equivalents. A new OCR/description service is not assumed.

## Full-Page Render-Error Presentation (M5)

| Field | Value |
|---|---|
| Component | Stable parent fallback presentation outside the failed JobStatus subtree |
| Category | Feedback, recovery, navigation |
| Inputs | Safe error category, surviving authorized job context, paper identity, safe return target |
| Trigger | Caught descendant rendering failure, not generic network loss |

Close existing dialogs and replace the paper main-content presentation with the named full-page error view at the same paper route. Focus the error heading with programmatic focus; announce the safe message once. Render only safe context, not stacks or protected result text. Report scrubbed errors to Sentry without allowing telemetry failure to block the fallback.

- **Recover tracking:** Available only with authorized job identity. Reset the failed subtree and perform a state read/reconnection for the same job. Apply the Recovery Focus Rule on success, avoiding focus theft from a surviving target. On repeated failure, remain in the recoverable error view with actions still usable. No submit call is permitted.
- **Return to paper:** Restore paper presentation with result modal closed and failed tracking hidden; focus the corresponding paper action, or paper heading if it no longer exists. Do not immediately remount the failed tracking subtree.
- **Missing context/access lost:** Explain that tracking cannot be restored; provide safe return/sign-in navigation according to the existing app contract.

Functional Design owns the exact error-boundary/parent state arrangement; no new backend or error-page endpoint is required. The full-page visual choice does not widen the actual render boundary to unrelated components.

## Conceptual Component Inputs and Composition

These are UI input contracts for design, not backend DTOs or final TypeScript signatures. Required input absent means the corresponding protected operation is unavailable; never fabricate owner/job/asset identity. Callbacks are capabilities, not additional endpoints.

| Component | Input / conceptual type | Required | Default or absence behavior |
|---|---|---|---|
| JobSubmissionForm | owner/paper context / identity context | Yes | No submit or recovery until authorized context exists |
| JobSubmissionForm | task and supported initial parameter choices / selection model | Yes | Reuse verified existing defaults; unresolved choices disable submit with explanation |
| JobSubmissionForm | explicit submit and accepted-job callbacks / actions | Yes | No operation without an action; never auto-submit on mount or selection |
| JobSubmissionForm | captured recovery reference and eligibility / optional recovery context | No | Recovery unavailable with reason; no guessed parameters |
| JobSubmissionForm | close/return target / navigation action | Yes | Return to invoking paper action; surviving paper heading as focus fallback |
| JobStatus | authorized selected job and current owner context / identity context | Yes | Do not mount a fictional tracking instance without a job ID |
| JobStatus | actual state/history / observed data | No initially | Connecting/read-pending presentation, no fabricated state or history |
| JobStatus | progress and ETA evidence / optional observations | No | Indeterminate progress; estimate unavailable |
| JobStatus | result-open and tracking-recovery actions / contextual callbacks | No | Offer only when authorized identity and required callback exist |
| JobStatus | same-request recovery eligibility/action / optional captured context | No | Persistent explanation when originals unavailable; never use current edited draft |
| SummaryModal | selected job/task and read capability / authorized read context | Yes | No protected read without context; close remains available |
| SummaryModal | submitted summary level / optional metadata | No | Submitted level unavailable; never substitute current default |
| SummaryModal | result-read state/content / view model | Yes | Initial loading; actual response determines subsequent state |
| SummaryModal | supplied asset ID / optional identifier | No | No copy action or invented identifier |
| SummaryModal | invoking control and close / focus reference and action | Close yes; reference optional | On dismissal use invoking control if present, then corresponding paper action, then paper heading |
| AssetViewer | paperId, assetId and access context / authorized identifiers | Yes | No image request or transform operation without valid context |
| AssetViewer | caption/text/table equivalent / optional semantic content | No in transport; meaningful equivalent required for conformance | Missing equivalent is an unresolved accessibility gap; do not set decorative alt solely because text is absent |
| AssetViewer | actual loaded dimensions / optional dimensions | No initially | Loading state; fit/transform calculations wait for decoded content |
| AssetViewer | transform / view state | No | Fit 1x centered; reset on asset/context change |
| ErrorBoundaryFallback | safe message and return action / feedback/navigation | Yes | Generic safe render-failure message; no raw exception text |
| ErrorBoundaryFallback | authorized job context and recovery action / optional context | No | Tracking recovery unavailable with explanation; Return remains usable |

Composition examples (conceptual, not executable code):

```text
PaperDetailIsland
  JobSubmissionForm(ownerPaperContext, initialSelections,
    submitExplicitly, recoverCapturedRequest, onActualJobReceived, close)
  ErrorBoundary
    JobStatus(selectedJobContext, observations, openResult, recoveryEligibility)
  SummaryModal(selectedJobContext, readResultOnly, submittedLevel?, suppliedAssetId?, close)
  DocModelViewer -> AssetViewer(paperId, assetId, accessContext, semanticEquivalent?)
  ErrorBoundaryFallback(safeMessage, authorizedJobContext?, recoverTracking?, returnToPaper)
```

Only the submission/recovery surfaces receive command capabilities. SummaryModal receives read capability only. ZoomPanControls emits actions to AssetViewer's transform owner, and the redundant minimap receives the same authorized image. The main image remains meaningful content even if its equivalent is missing; only the duplicate overview is decorative/redundant. Functional Design supplies concrete interfaces, validated defaults and data reconstruction without expanding these capabilities.

## Verification and Implementation Handoff

- Validate M1–M5 against US1–US8, including absent progress, unknown request parameters, copy failure, focus replacement, account switch, and repeated polling.
- Resolve BFF streaming/replay, resultRef consumption, request reconstruction, and asset equivalents before implementation claims.
- Preserve NFR9's staging profile: production build, real BFF/gateway, same-region authenticated desktop Chromium runner, one active job, no throttling, 100 sequential samples per metric, uncached 100 KiB figure, p95 strictly under 300/500/200 ms for the specified connection/decoded-image/committed-UI boundaries. UI motion cannot postpone those boundaries.
- Animation is cosmetic, never a source of job progress or extra polling. Use short CSS transitions; reduced motion removes movement/pulsing. All behavior and accessibility checks are pending runtime verification, not certified by this document.
