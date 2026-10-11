# DocSuri v2 — Interaction Specification

Date: 2026-10-11 (Asia/Seoul). Basis: [requirements](../requirements-analysis/requirements.md), [confirmed answers](refined-mockups-questions.md) and [screen map](mockups.md). All contracts below describe observable behavior and component responsibilities; they do not select a frontend framework, storage technology or wire format.

## Interaction invariants

1. Separate read, prepare, mutate and external-effect actions. Name a retry according to its effect. Reading a prepared result, reopening a session or restoring a draft never starts new work.
2. Show success only after the relevant authoritative acknowledgement. Unknown outcomes remain unknown while reconciled; duplicate user actions resolve the same intended effect where required.
3. Treat owner, context, paper/version and operation identity as part of every private view and update. Clear stale private state before rendering a newly authenticated account.
4. Keep focus and committed context stable through refresh; route changes and explicit opens receive purposeful focus. Return from a paper restores its search query, refinements, order and result position; source/result navigation preserves paper/version and the relevant anchor. Reflect acknowledged saves consistently across reader and library. Do not announce every event or keystroke.
5. Every component uses inherited DocSuri blue/neutral semantic tokens, their accessible variants, and the shared state/responsive contract. Hover and press have visible cues, keyboard focus has a 3px outline with 2px offset, and disabled/busy controls explain why and prevent only the relevant effect. No hover-only action. Use consistent action-group sizing, with selective primary emphasis and quieter secondary actions.
6. Inputs and source markup are untrusted. No private draft/question/manuscript text in URLs, analytics, notification previews, normal logs or shared clipboard without the owner's deliberate action.
7. Local prototype feedback is illustrative. Only implemented boundary tests can prove these invariants.

The [Apple HIG-to-web mapping](design-system-mapping.md#apple-hig-to-web-mapping) grounds the layout, typography, grouping, action hierarchy, feedback and material treatment. Apply it through semantic browser controls and stable opaque reading surfaces. It adds no native-framework requirement. Keep browser navigation and text-selection conventions, the Korean-facing experience and the approved Light / Dark / System behavior.

## Durable draft lifecycle

Drafts are distinct from committed messages, accepted jobs and saved library work. The approved policy adds browser-restart recovery for acknowledged research-question and manuscript drafts; it does not promise recovery of a failed/unacknowledged latest edit.

| Event / state | User-visible behavior | Required outcome |
| --- | --- | --- |
| New authenticated input | “Unsaved changes” → “Saving…” | Scope to owner + session/analysis context + draft revision; debounce/batching policy selected after measurement |
| Durable acknowledgement | “Saved” with last confirmed time | A new browser session can recover this exact acknowledged revision after same-owner authentication |
| Storage unavailable, full, offline or save rejected | Persistent “Not saved — keep this page open and retry” | Keep permitted current input; never promise restart recovery for it; do not silently discard older acknowledged revision |
| Navigate within signed-in application | Preserve draft/context; if unacknowledged changes might be lost, offer Stay / Retry save / Discard changes | Do not rely on browser unload prompts as a reliable save mechanism |
| Browser closes/crashes | No guaranteed final callback | Recover the last acknowledged revision on next same-owner return; latest unacknowledged edits may be absent and must not be represented as saved |
| Session expires | Show a neutral sign-in panel; remove private text from rendered/accessibility surfaces | Suspend owner writes; same-owner reauthentication may restore acknowledged draft and still-available transient text; another owner sees neither |
| Explicit logout/account switch | Clear visible and transient private state and any browser-accessible prior-owner cache | A saved owner-bound draft remains recoverable only under its eventual approved retention policy; logout is not silently labeled deletion |
| Same-owner return/restart | “A saved draft is available” with context/time and Restore / Discard | Fetch only after authorization; never auto-send, auto-analyze or auto-export restored input |
| Two tabs edit from same revision | “This draft changed elsewhere” with both authorized versions and explicit Keep this / Use saved choice | Never last-write-wins silently; retain unresolved text until a chosen save is acknowledged |
| Submit/Analyze pressed | Show submitting with exact draft revision/input context | Bind one intended submission to the chosen revision; lost response reconciles it before retry |
| Submission accepted | Show committed turn/job separately; mark submitted revision consumed | Clear only that accepted revision; later edits remain a newer draft. Restart must not restore a consumed revision as new unsent work |
| Submission failed before acceptance | Show failure and keep draft | Retry the intended turn safely; no second turn from a restored draft |
| Discard draft | Confirm exact draft/context; show deleting then acknowledged discarded | Failure retains recoverable state; deletion/tombstone defeats late saves or events recreating it |
| Session/account deletion | Explain the approved scope of draft and pending-work deletion | Authoritative deletion, caches, derived artifacts and backups follow the approved data policy; no late revival |
| Retention expiry | State that a previously saved draft expired, where such metadata can lawfully remain | Warn according to the eventual policy; never fabricate recoverable text after erasure |

**Implementation dependency D-01:** choose storage placement, encryption/key/access behavior, retention/expiry and deletion/backup propagation only after privacy, security and free/local-capacity investigation. No private plaintext draft may be left in shared unauthenticated browser storage as a shortcut. This specifies a security outcome, not a claim that owner tags alone secure storage. Recovery across devices is not promised by the restart requirement. Offline persistence beyond the last acknowledged save is not claimed. The final user-facing retention text must contain the actual approved policy before release.

### Draft status and helper copy

The status and adjacent helper describe the same revision. Do not keep a generic “이 계정에서 다시 열 수 있어요” (you can reopen it in this account) helper beneath an unsaved, failed or conflicting latest edit. A confirmed time is displayed only when known; if no revision has been acknowledged, say that no saved draft is confirmed.

| State | Primary status example | Helper meaning / example |
| --- | --- | --- |
| Editing, no acknowledgement | “저장되지 않은 변경사항” (Unsaved changes) | Latest text is not confirmed saved; no restart recovery promise |
| Saving | “저장 중…” (Saving…) | “아직 저장이 확인되지 않았어요.” If an older acknowledgement exists, only that earlier revision is recoverable |
| Saved | “저장됨” (Saved), with confirmed time if known | The acknowledged revision can be restored after return to this authenticated account |
| Failed/offline | “최신 변경사항이 저장되지 않았어요” (Latest changes not saved) | Keep the page open and retry; identify only the older acknowledged revision as recoverable, or state none is confirmed |
| Recovery offered | “저장된 초안이 있어요” (A saved draft is available) | Identify its context and known save time; Restore / Discard is an explicit choice |
| Recovered | “저장된 초안을 복원했어요” (Saved draft restored) | This is the last acknowledged revision; edits made after its save may be absent |
| Conflict | “다른 곳에서 변경된 초안이 있어요” (Draft changed elsewhere) | Current local edits are not confirmed saved; compare the available revisions and choose explicitly before acknowledging a new save |
| Locked | “다시 로그인해 주세요” (Sign in again) | Neutral owner-safe copy only; no draft preview, private context or recoverable-text claim before authorization |

M08 submits with “질문 보내기” (Send question); M09 submits with “분석 시작” (Start analysis). Visible label, accessible name, simulated feedback and eventual handler must agree on the effect. Enter in a multiline field continues to insert a newline.

## State transitions with externally visible effects

| Flow | Allowed transitions and reconciliation |
| --- | --- |
| Paper work | idle → accepting → queued/running → succeeded or failed; acceptance-unknown → query original operation; connection state orthogonal to work state; terminal state never regresses |
| Result read | unread → reading → ready/pending/expired/failed/unauthorized; Retry read stays within read; Request again starts a separately confirmed new operation |
| Novelty cancellation | running → cancellation-requested → cancelled or completed if completion won; an acknowledged cancellation remains final |
| Save/remove/update | committed state → pending → acknowledged new state or explicit failure; unknown response queries original effect; refresh tabs to same committed state |
| Export | connected → current preview → explicit approved effect → executing → confirmed success/failure/unknown; unknown → reconcile; changed preview/destination → approval invalid |
| Destructive action | scope preview → deliberate confirmation → execution → acknowledged outcome; changed authority/precondition cancels stale confirmation, requiring recheck |
| Consent/unsubscribe | committed permission → revocation pending → revoked; eligible queued work rechecks current permission before effect; failure cannot show revoked |

Durations, input/file sizes, retry caps, queue limits and quota reset/refund rules require evidence and contract decisions before implementation acceptance. Do not expose invented numeric promises. An operation which cannot run at $0 stays explicitly unavailable with a tracked feasibility issue; that state does not satisfy normal-path parity.

## Common accessibility and responsive contract

Native controls first; visible labels and error descriptions; keyboard sequence follows reading order. Use a single main landmark, skip link, meaningful headings and a visible current destination. Status information uses polite announcements; urgent actionable errors use an alert once. Focus moves to an error summary only on an explicit failed submission, not on background updates. All interactive text meets the palette's intended AA contrast; non-text boundaries/focus cues meet their applicable 3:1 target. See [the checklist](accessibility-checklist.md) for exceptions and verification obligations.

Breakpoints: phone <768px; tablet/compact 768–1199px; desktop ≥1200px. These are starting layout decisions, with content-driven reflow at any viewport. Full functionality remains reachable. Native form/flow semantics, focus handling, disabled explanation, long-text wrapping, reduced-motion behavior and busy/empty/error rendering are shared responsibilities, not optional per-screen inventions.

## Component specifications

The following tables use framework-neutral input notation. Every component's state list supplements the shared hover/focus/disabled/loading/error/empty rules above. Text examples are documentation, not runnable API contracts.

### C01 — Workspace navigation

| Field | Value |
| --- | --- |
| Component | Workspace navigation |
| Description | Keep account, destination and paper context explicit. |
| Category | navigation |
| Traceability | M01–M16; NFR2/NFR4/NFR6 |

#### States

| State | Description / trigger |
| --- | --- |
| default | authorized destinations on entry |
| focus | visible link outline on Tab |
| active | current destination announced |
| loading | destination content busy |
| denied | protected content cleared |
| empty | no private shortcuts |
| error | navigation recovery preserves non-sensitive destination |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| destinations | list of authorized labels/URLs | yes | — | Role-filtered routes; server authorization still required |
| current | route identity | yes | — | aria-current location |
| owner | safe display identity or null | yes | null | Account switch clears prior private context |
| returnContext | authorized route + query/refinement/order/result position or paper/version/anchor | no | absent | Preserve useful context without putting private input in URLs; revalidate owner on return |

#### Responsive Behaviour

Desktop rail and context header; tablet compact rail; phone disclosure menu with all web destinations reachable. Moving between layouts keeps the active paper/session and deliberate return destination; a hidden secondary panel is still reachable through its labeled control.

#### Accessibility

nav landmark and actual links; menu button aria-expanded; Tab/Enter, Escape closes mobile panel; destination heading receives focus after route change; close restores menu trigger; no color-only current state. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
Navigate({current:'paper', owner:'synthetic-A', destinations:allowed})
```

### C02 — Query, filters and result list

| Field | Value |
| --- | --- |
| Component | Query, filters and result list |
| Description | Find the intended paper while preserving query/refinement context. |
| Category | input |
| Traceability | M03; FR1.1/FR1.2/FR1.3/FR5.1 |

#### States

| State | Description / trigger |
| --- | --- |
| default | previous query ready |
| loading | submitted result region busy; query/mode/order/filter controls remain available |
| success | results with mode/freshness |
| empty | confirmed no match in result region; Edit query / Clear filters available |
| invalid | field error before request |
| error | failed result region; preserve input and refinements; Retry search available |
| partial | fallback/incomplete results |
| stale | snapshot changed |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| query/filter/order | validated values | yes | retained defaults | Exact vocabulary reconciled from reference |
| resultSet | items + mode + snapshot + pagination | no | unknown | Never derive zero results from failure |
| onSearch/onSave | separate effect handlers | yes | — | No search-as-save coupling |

#### Responsive Behaviour

Filters wrap at desktop; tablet/phone labeled expandable filter region with applied chips always visible; result metadata wraps and actions stack.

The form and applied refinement controls are persistent siblings of the results/status region. Loading, empty and error must not replace the entire search workspace with a banner. Editing fields keeps focus and does not automatically submit; starting a revised search identifies the new submitted values while retaining safe return context. Clear filters is an explicit action with a visible outcome. Retry uses the intended submitted query/refinements, not silently modified values. When returning from a paper, restore the query/order/refinements and result position; if results changed, explain freshness instead of pretending the old position is unchanged.

#### Accessibility

search form with visible query label; native filter controls; submit by Enter only outside multiline fields; count/status announced politely once per response; validation associated with field; result title links remain keyboard reachable; no focus jump on background refresh. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
QueryResults({query:P1.query, state:'partial', actualMode:'lexical'})
```

### C03 — Paper identity and reading surface

| Field | Value |
| --- | --- |
| Component | Paper identity and reading surface |
| Description | Bind content, assets, source links and citations to the intended paper/version. |
| Category | display |
| Traceability | M04/M07; FR2.1/FR2.2/FR2.3/FR9.1/FR9.2 |

#### States

| State | Description / trigger |
| --- | --- |
| default | metadata available |
| loading | body loading |
| success | eligible readable content |
| source-only | metadata and authorized links |
| building/unsupported/failed/withdrawn | explicit disposition |
| restricted | no private content |
| partial | missing figure/section/graph |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| paper | identity/version/provenance/availability | yes | — | Required before content display |
| content | sanitized sections/figures/anchors | no | absent | Not raw trusted HTML |
| citations | bounded graph and equivalent list | no | unknown | Direction, freshness, eligible save |

#### Responsive Behaviour

Desktop contents + text + assistance; tablet assistance below; phone contents disclosure, bounded figure/table scroll regions; never crop reading text to fit.

#### Accessibility

article, semantic headings/figure captions and named regions; source navigation via links; informative figures require text alternatives supplied by content pipeline; decorative icons hidden; math has readable semantics/text fallback; graph actions duplicated in list; anchor focus target visible below headers. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
PaperReader({paper:{id:'1706.03762',version:'v7'}, availability:'source-only'})
```

### C04 — Activity card and prepared result

| Field | Value |
| --- | --- |
| Component | Activity card and prepared result |
| Description | Show authoritative work status and read results without accidental new work. |
| Category | feedback |
| Traceability | M05/M08/M09; FR3.1/FR3.2/FR3.3/FR3.4/FR14.1/FR15.2 |

#### States

| State | Description / trigger |
| --- | --- |
| default | action available |
| accepting | request in flight |
| uncertain | acceptance acknowledgement lost |
| queued/running | accepted identity known |
| reconnecting | last confirmed state labeled |
| succeeded | prepared result readable |
| failed | bounded recovery |
| expired | new request separately offered |
| unauthorized | private fields removed |
| cancellation-requested | awaiting outcome |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| activity | owner-bound identity/state/revision/updatedAt | yes | unknown | Ordering contract selected later |
| connection | live/reconnecting/offline | yes | unknown | Separate from job status |
| result | identity/version/operation/content/expiry | no | unavailable | Read permission checked anew |
| onRead/onRequest/onCancel | separate handlers | yes | — | Cancel only where retained |

#### Responsive Behaviour

Card stacks at every size; result is adjacent panel at desktop or named full-width panel on phones; long events use an optional disclosure.

#### Accessibility

One polite status region, terminal failure actionable alert once; no repeated stream announcement; do not use progressbar without meaningful numeric progress; event history keyboard operable; content heading focused on deliberate open; same job keeps focus during updates. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
Activity({state:'succeeded', connection:'offline', resultRead:'expired'})
```

### C05 — Durable research/manuscript composer

| Field | Value |
| --- | --- |
| Component | Durable research/manuscript composer |
| Description | Recover authenticated owner drafts while distinguishing them from submitted work. |
| Category | input |
| Traceability | M08/M09/M11; FR13/FR14/FR15; NFR3/NFR4/NFR5 |

#### States

| State | Description / trigger |
| --- | --- |
| default | empty owner context |
| editing | unsaved changes |
| saving | persistence request |
| saved | durable acknowledgement |
| failed/offline | restart recovery not promised for latest text |
| recovery-available | owner-authenticated saved revision offered for explicit restore |
| recovered | acknowledged revision restored; newer unsaved text may be absent |
| conflict | both available revisions retained |
| locked | expired/changed owner |
| submitting | reconcile input revision |
| discarded | acknowledged deletion |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| owner/context/draftId | opaque identity tuple | yes | — | Scope includes research session or novelty input mode |
| revision/baseRevision | opaque versions | yes | — | Prevents silent overwrite |
| saveState | enum + acknowledged revision/time | yes | unsaved | Only durable ack permits Saved; status and helper refer to the same revision |
| input | text + accepted attachment references | yes | empty | Secrets/private text excluded from URLs/telemetry |
| onSave/onSubmit/onDiscard | separate handlers | yes | — | No restored auto-submit |

#### Responsive Behaviour

Multiline area grows with text; desktop beside source scope; phone scope above input and save status below label; no sticky action covering the text/focus.

#### Accessibility

textarea label and instructions; Enter inserts newline, explicit Send/Analyze button submits; attach button has file constraints; draft saved/recovered announced politely without every-keystroke chatter; failure is persistent text; on lock remove private text from DOM/accessibility tree; same-owner recovery focuses heading before opt-in restore. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
DraftComposer({context:'research:S1', revision:'r3', saveState:'failed'})
```

### C06 — Saved-work list and write feedback

| Field | Value |
| --- | --- |
| Component | Saved-work list and write feedback |
| Description | Keep persisted state truthful and scopes of deletion clear. |
| Category | display |
| Traceability | M06/M03/M04; FR5.1/FR5.2/FR5.3/FR10.1/FR14.2 |

#### States

| State | Description / trigger |
| --- | --- |
| default | list read |
| loading | preserve last confirmed state labeled |
| empty | confirmed no records |
| saving/removing | pending effect |
| success | acknowledged state |
| uncertain | reconcile original effect |
| failed | old committed state retained |
| changed-source | explicit version/canonical/withdrawal disposition |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| collection | owner + kind + page + snapshot | yes | — | Papers/searches/history/recent/sessions |
| items | stable identity records | yes | unknown | Unavailable is not empty |
| mutation | operation identity + outcome | no | none | One intended effect on retries |

#### Responsive Behaviour

Desktop table/list; phones labeled cards with identical actions and identity/version; pagination controls stay reachable.

#### Accessibility

Semantic list/table with names; save toggle aria-pressed only for committed state; pending text separate; removal confirmation names scope; after removal focus next row or list heading; no focus loss when rows refresh. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
SavedList({kind:'history', mutation:'clear-failed', items:lastConfirmed})
```

### C07 — Dialog, confirmation and recovery panel

| Field | Value |
| --- | --- |
| Component | Dialog, confirmation and recovery panel |
| Description | Bound deliberate actions and restore focus reliably. |
| Category | layout |
| Traceability | M05/M06/M10/M11/M12/M16; NFR6 |

#### States

| State | Description / trigger |
| --- | --- |
| default | closed |
| opening | focus initial safe element |
| active | background inert |
| validation-error | focus summary/field |
| busy | one effect in flight |
| error | retained context and safe retry |
| closing | restore trigger |
| expired | disable stale action |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| title/description | plain text | yes | — | Action, object and consequences |
| initialFocus/returnFocus | safe element reference | yes | — | Destructive flow defaults to Cancel |
| confirmEffect | named handler | no | none | Absent for read-only result inspector |

#### Responsive Behaviour

Constrained readable width desktop; phone full width with scrollable body and reachable actions; no horizontal overflow or hidden close.

#### Accessibility

Native dialog or equivalent proven modal implementation; aria-labelledby/describedby, focus containment, Escape when safe, explicit close; backdrop click only for non-destructive read dialogs; Escape during submitted work closes view but does not imply cancellation; restore trigger or logical successor. Focus never obscured by fixed actions. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
ConfirmDialog({title:'Clear history?', confirm:'Clear history', initialFocus:'cancel'})
```

### C08 — Identity and settings form

| Field | Value |
| --- | --- |
| Component | Identity and settings form |
| Description | Use consistent validation, save feedback and accessible authentication. |
| Category | input |
| Traceability | M01/M02/M11/M12/M13/M14; FR4/FR6/FR7/FR8/FR10/FR11/FR12 |

#### States

| State | Description / trigger |
| --- | --- |
| default | known values |
| focus/hover | visible cue |
| invalid | linked field message |
| submitting | prevent duplicate effect |
| success | confirmed values |
| failed | retain permitted non-secret inputs |
| conflict | show committed vs edited values |
| provider-denied/link-expired | explicit recovery |
| abuse-limited | truthful bounded wait |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| fields | label/type/autocomplete/constraints/error | yes | — | Server validation authoritative |
| state | operation/status/committed revision | yes | idle | No false success |
| onSubmit | explicit handler | yes | — | Reauth does not resubmit destructive work |

#### Responsive Behaviour

One column forms with adjacent descriptions desktop where readable; all labels above controls phone; inline errors wrap.

#### Accessibility

Native input/label associations, required semantics and error summary links; correct autocomplete; password paste/managers permitted; show/hide labeled pressed button without dropping focus; no memory puzzle as sole auth path; MFA supports paste and accessible recovery; provider buttons identify destination. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
IdentityForm({mode:'verify-email', state:'delivery-failed'})
```

### C09 — Evidence, attachments and novelty result

| Field | Value |
| --- | --- |
| Component | Evidence, attachments and novelty result |
| Description | Keep claims, quotations, source coverage and limitations inspectable. |
| Category | display |
| Traceability | M08/M09; FR13.1/FR13.2/FR13.3/FR15.1 |

#### States

| State | Description / trigger |
| --- | --- |
| default | source scope shown |
| validating | attachment not yet accepted |
| rejected/truncated | precise limit |
| loading | analysis pending |
| success | grounded response |
| partial | missing coverage marked per claim |
| abstained | evidence insufficient |
| malformed | result unavailable |
| expired/restricted | access removed |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| sources | identity/type/read-status/coverage/eligibility | yes | — | Web/corpus/private visibly distinct |
| claims | statement + evidence refs + uncertainty | no | absent | No fabricated reference fallback |
| artifacts | owner-bound type/status/expiry | no | absent | Safe download permission check |

#### Responsive Behaviour

Wide evidence pane can sit beside answer; phone evidence becomes inline expandable detail; comparison tables reflow or get a named scroll region.

#### Accessibility

Semantic quotations/citations/lists, explicit source link text and accessible tables; no color-only confidence/coverage; attachment status announced once; return-to-claim link preserves focus; charts need textual results; file names treated as untrusted text. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
EvidenceResult({state:'partial', sources:[{kind:'web',read:false}]})
```

### C10 — Usage, administrative action and operation record

| Field | Value |
| --- | --- |
| Component | Usage, administrative action and operation record |
| Description | Expose allocation, authority, freshness and effects without overstating readiness. |
| Category | display |
| Traceability | M15/M16/O01/O02; FR17/FR18/FR19/FR20 |

#### States

| State | Description / trigger |
| --- | --- |
| default | target/context |
| loading | unknown measurements |
| success | fresh observation |
| stale/unknown | labeled timestamp |
| exhausted | bounded action refusal |
| confirming | target and proposed change |
| denied/stale-precondition | no effect |
| executing | outcome pending |
| failed/uncertain | reconciliation |
| verified | effect checked |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| actor/target | role and resource reference | yes | — | No secret material |
| observation | value + unit + observedAt + freshness | yes | unknown | Zero distinct from unavailable |
| operation | precondition/effect/authority/outcome | no | none | Existing operator interface, not runnable commands |

#### Responsive Behaviour

User quota cards/admin forms adapt to mobile; operator CLI/records retain their existing interface, with readable output and no invented mobile UI requirement.

#### Accessibility

Named values/units rather than color-only meters; accessible admin MFA/form/confirmation; operator output includes text status and reason, not ANSI color alone; destructive confirmation names target and scope; correlation IDs copyable with explicit feedback. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
Usage({used:null, state:'unknown', reset:{time:null,zone:null}})
```

### C11 — Export preview and approval

| Field | Value |
| --- | --- |
| Component | Export preview and approval |
| Description | Require explicit current approval for one external publishing effect. |
| Category | input |
| Traceability | M10; FR16.1/FR16.2 |

#### States

| State | Description / trigger |
| --- | --- |
| default | disconnected |
| connected | permitted owner/destination |
| previewing | content read |
| ready | current revision visible |
| approved/executing | effect bound |
| changed | approval invalidated |
| unknown | reconcile remote state |
| succeeded | actual destination link |
| failed/revoked/expired | repair then fresh review |

#### Props / Inputs

| Prop | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| owner/connection/destination | safe identity references | yes | — | Credentials never rendered |
| previewRevision/content | immutable review identity + sanitized content | yes | — | Changing either invalidates approval |
| approval | owner + preview + destination binding | no | none | Explicit action only |
| onPreview/onApproveExport/onReconcile | distinct handlers | yes | — | No auto-publish |

#### Responsive Behaviour

Preview and destination side by side desktop; stacked phone with destination repeated beside final action; long content remains scrollable and reviewable.

#### Accessibility

Step labels convey current state; native explicit approval button; disabled action has textual reason; focus changed-preview notice; success link named; unknown state announces pending reconciliation without repeated alerts. Contrast, target size and reflow follow the common contract and checklist.

#### Usage Example

```text
ExportPreview({revision:'p2', approvedRevision:'p1', state:'changed'})
```

## Verification and unresolved implementation decisions

Verify C01–C11 through the mockup walkthroughs V01–V09 and later real mounted browser/service/worker boundaries. In particular: typed input during a save/submission race, same-owner reauthentication versus a different account, cancelled work versus a lost connection, expired result versus a failed read, and an unknown export outcome versus a failed export must remain visibly different.

D-01–D-06 in [mockups.md](mockups.md) remain open. The accepted requirements-review concern about unsent input is elaborated here with an approved recovery outcome; its durable storage, retention/deletion and security implementation are not declared complete. No numeric service target, technology, migration decision or public deployment is selected.
